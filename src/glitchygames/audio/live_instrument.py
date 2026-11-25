"""A live instrument's voice: its parameters, routes and sources rendered chunk by chunk (M2).

Feature spec 5.3-5.4, implementation spec 4.3 and 7.5; plans/2026-11-14-sound-migration.md
step 5. An ``InstrumentVoice`` plays an ``Instrument(live=True)`` on a live pool channel. Its
channel and lifecycle are a ``live.LiveStream`` (start, one chunk queued, fades, pause, the
context's audible route, the pool's owner rules). A game reaches it through ``Sound.start()``
and its handle.

Rules:

1. Parameters: ``set(name, value)`` clamps to the parameter's range (each clamp counted) and
   stores the latest value; rendering reads it once per chunk, so updates coalesce. Each chunk
   glides one pole from the previous chunk's end value toward it (``live_controls.smoothed``).
   A name the instrument lacks is refused; a set once the voice is stopping returns False.
2. Routes (``live_controls`` rules 2 and 3), per sample from the smoothed parameter:

   - ``pitch`` (Hz) replaces the frequency the voice was started at;
   - ``level`` multiplies the voice's volume; several routes to it multiply;
   - ``sources.<name>.level`` replaces that source's own level; several multiply;
   - ``filter.cutoff`` moves the instrument's filter; it changes once per chunk, crossfaded
     across the chunk (``live.FilterState``), and starts where the parameters put it;
   - ``tremolo.rate`` and ``tremolo.depth`` move the instrument's tremolo per sample.

   ``Instrument`` refuses a second route to ``pitch``, ``filter.cutoff`` or a tremolo setting,
   a route to a filter or tremolo it lacks, and an output its destination cannot take.
3. Sources, each with its own oscillator phase: sine, square, saw and triangle (the plain
   oscillator, ``synth.oscillator``, as the older live voice renders them) and white noise
   (from the engine's ``audio.live`` stream, or the generator given). A source's level and
   ``semitones``/``detune_cents`` are rendered; they mix by level, unnormalized. Everything
   else (other waves, LFSR noise, a noise seed, a source's own pitch, glide, envelope or
   filter, the instrument's drive) is refused when the voice is made: later work
   (plans/future-work.md). The instrument's envelope is not applied: a live sound sustains
   until stopped, and ``stop`` fades it.
4. Each chunk: smooth, route, render and mix the sources, filter, tremolo, then the volume
   times the level. Steady settings render what the older ``LiveVoice`` (removed in migration
   step 7) rendered for the same waveform, frequency, volume, cutoff and tremolo: tested to
   rounding against its rendering, kept in tests/audio/test_live_instrument.py.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

import numpy as np

from glitchygames.audio.live import (
    DEFAULT_FADE_OUT,
    DEFAULT_LIVE_VOICE_OPTIONS,
    LIVE_RANDOM_STREAM,
    FilterState,
    LiveStream,
    LiveVoiceOptions,
    VoiceState,
)
from glitchygames.audio.live_controls import (
    MILLISECONDS_PER_SECOND,
    LinearGlide,
    route_output,
    smoothed,
)
from glitchygames.audio.synth import FloatArray, Waveform, oscillator, sample_count
from glitchygames.audio.voices import DEFAULT_STOP_FADE_SECONDS
from glitchygames.audio.waves import Wave
from glitchygames.randomness import numpy_stream

if TYPE_CHECKING:
    from collections.abc import Mapping

    import pygame

    from glitchygames.audio.effects import Tremolo
    from glitchygames.audio.instrument import Instrument, Source
    from glitchygames.audio.live_controls import Parameter, Route

# Rule 3: what a live voice renders now
LIVE_WAVEFORMS: Final[dict[str, Waveform]] = {
    'sine': Waveform.SINE,
    'square': Waveform.SQUARE,
    'saw': Waveform.SAWTOOTH,
    'triangle': Waveform.TRIANGLE,
}
LIVE_NOISE_KIND: Final[str] = 'white'
SEMITONES_PER_OCTAVE: Final[float] = 12.0
CENTS_PER_SEMITONE: Final[float] = 100.0
NYQUIST_FRACTION: Final[float] = 0.5
LIVE_SOURCES_TEXT: Final[str] = 'a live voice renders sine, square, saw, triangle and white noise'


class LiveSource:
    """One source as a live voice renders it: its oscillator, level and transposition."""

    def __init__(self, *, name: str, source: Source) -> None:
        """Resolve a source (rule 3).

        Raises:
            ValueError: For anything a live voice cannot render yet.
        """
        from glitchygames.audio.instrument import Noise

        self.name = name
        for setting in ('pitch', 'pitch_curve', 'envelope', 'filter'):
            if getattr(source, setting) is not None:
                message = f"source {name!r}: a live voice cannot render a source's {setting} yet"
                raise ValueError(message)
        content = source.content
        self.mix_level = source.level
        if isinstance(content, Noise):
            if content.kind != LIVE_NOISE_KIND:
                message = f'source {name!r}: {LIVE_SOURCES_TEXT}, not {content.kind} noise'
                raise ValueError(message)
            if content.seed is not None:
                message = f'source {name!r}: a live voice cannot give its noise a seed yet'
                raise ValueError(message)
            self.waveform = Waveform.NOISE
            self.mix_level *= content.level
        else:
            wave_name = content.name if isinstance(content, Wave) else content
            if wave_name not in LIVE_WAVEFORMS:
                shown = wave_name if wave_name is not None else 'a mix, blend or drawn wave'
                message = f'source {name!r}: {LIVE_SOURCES_TEXT}, not {shown}'
                raise ValueError(message)
            self.waveform = LIVE_WAVEFORMS[wave_name]
        semitones = source.semitones + source.detune_cents / CENTS_PER_SEMITONE
        self.frequency_ratio = 2.0 ** (semitones / SEMITONES_PER_OCTAVE)
        self.phase = 0.0


class InstrumentVoice:
    """A live instrument playing on a live pool channel (rules in the module docstring)."""

    def __init__(  # ruff: ignore[too-many-arguments] - the voice's whole setting
        self,
        *,
        channel: pygame.mixer.Channel | None,
        owner: object,
        instrument: Instrument,
        frequency: float,
        volume: float,
        sample_rate: int,
        parameters: Mapping[str, float] | None = None,
        options: LiveVoiceOptions = DEFAULT_LIVE_VOICE_OPTIONS,
        random_source: np.random.Generator | None = None,
    ) -> None:
        """Make a stopped voice; channel None makes a silent no-op voice.

        Args:
            channel: Its pool channel (``LiveAudio.create_instrument_voice``), or None.
            owner: The scene or transition whose life it follows.
            instrument: A live instrument.
            frequency: The pitch it plays at, in hertz, unless a route moves ``pitch``.
            volume: Its volume, 0-1 (a ``level`` route multiplies it).
            sample_rate: The mixer's rate.
            parameters: Starting values by name; the rest start at their defaults.
            options: Its chunk length, persist, priority, pan and bus gain (its stream's).
            random_source: The noise's generator; None is the engine's ``audio.live`` stream.

        Raises:
            ValueError: For an instrument that is not live, something rule 3 refuses, a
                parameter it lacks, or a cutoff at or above the Nyquist frequency.
        """
        if not instrument.live:
            message = 'an instrument plays as a live voice only with live=True'
            raise ValueError(message)
        if instrument.drive:
            message = 'a live voice cannot render drive yet'
            raise ValueError(message)
        self._instrument = instrument
        self._sample_rate = sample_rate
        self._frequency = LinearGlide(frequency)
        self._volume = LinearGlide(volume)
        self._tremolo = instrument.tremolo
        self._base_cutoff = None if instrument.filter is None else instrument.filter.cutoff_hz
        self._sources = [
            LiveSource(name=name, source=source) for name, source in instrument.sources
        ]
        self._parameters: dict[str, Parameter] = dict(instrument.parameters)
        self._routes: tuple[Route, ...] = instrument.routes
        self._random_source = (
            random_source if random_source is not None else numpy_stream(LIVE_RANDOM_STREAM)
        )
        self.clamp_count = 0
        self._targets = {name: parameter.default for name, parameter in self._parameters.items()}
        for name, value in (parameters or {}).items():
            self._store(name, value)
        self._current = dict(self._targets)
        # Rule 1's linear glides, by parameter (the one-pole ones need only _current)
        self._linear_glides = {
            name: LinearGlide(self._current[name])
            for name, parameter in self._parameters.items()
            if parameter.glide == 'linear'
        }
        self._refuse_cutoffs_at_or_above_nyquist()
        filter_spec = instrument.filter
        self._filter = FilterState(
            cutoff=self._cutoff_at(self._current),
            high_pass=filter_spec is not None and filter_spec.kind == 'high_pass',
            sample_rate=sample_rate,
        )
        self._tremolo_phase = 0.0
        self.stream = LiveStream(
            channel=channel,
            owner=owner,
            render=self._render_chunk,
            sample_rate=sample_rate,
            options=options,
        )

    @property
    def parameter_values(self) -> dict[str, float]:
        """The latest value set (or started with) of each parameter, by name."""
        return dict(self._targets)

    def set(self, name: str, value: float) -> bool:
        """Set a parameter; the next chunk glides toward it (rule 1).

        Args:
            name: One of the instrument's parameters.
            value: Its new value (clamped to the range, counted when it had to be).

        Returns:
            True when taken; False once the voice is stopping or stopped.
        """
        if not self.stream.accepts_changes:
            self._known(name)
            return False
        self._store(name, value)
        return True

    def set_frequency(self, frequency: float) -> bool:
        """Set the pitch straight, gliding in a line over the next chunk (the older voice's).

        Returns:
            True when taken; False once the voice is stopping or stopped.

        Raises:
            ValueError: For a frequency not above 0, or when a route moves ``pitch``.
        """
        self._refuse_what_a_route_moves(('pitch',))
        if frequency <= 0.0:
            message = f'frequency must be above 0, got {frequency}'
            raise ValueError(message)
        if not self.stream.accepts_changes:
            return False
        self._frequency.set(frequency, samples=self.stream.chunk_samples)
        return True

    def set_cutoff(self, cutoff: float | None) -> bool:
        """Set the filter's cutoff straight, crossfaded across the next chunk; None removes it.

        An instrument with no filter gains a low-pass.

        Returns:
            True when taken; False once the voice is stopping or stopped.

        Raises:
            ValueError: For a cutoff not above 0 or at or above the Nyquist frequency, or when a
                route moves ``filter.cutoff``.
        """
        self._refuse_what_a_route_moves(('filter.cutoff',))
        if cutoff is not None:
            nyquist = self._sample_rate * NYQUIST_FRACTION
            if cutoff <= 0.0:
                message = f'cutoff must be above 0, got {cutoff}'
                raise ValueError(message)
            if cutoff >= nyquist:
                message = f'a filter cutoff must stay below the Nyquist frequency, {nyquist:g} Hz'
                raise ValueError(message)
        if not self.stream.accepts_changes:
            return False
        self._base_cutoff = cutoff
        return True

    def set_tremolo(self, tremolo: Tremolo | None) -> bool:
        """Set the tremolo straight from the next chunk (its phase carries on); None removes it.

        Returns:
            True when taken; False once the voice is stopping or stopped.

        Raises:
            ValueError: For a rate not above 0 or a depth outside 0-1, or when a route moves
                ``tremolo.rate`` or ``tremolo.depth``.
        """
        self._refuse_what_a_route_moves(('tremolo.rate', 'tremolo.depth'))
        if tremolo is not None:
            if tremolo.rate_hz <= 0.0:
                message = f'a tremolo rate_hz must be above 0, got {tremolo.rate_hz}'
                raise ValueError(message)
            if not 0.0 <= tremolo.depth <= 1.0:
                message = f'a tremolo depth must be between 0 and 1, got {tremolo.depth}'
                raise ValueError(message)
        if not self.stream.accepts_changes:
            return False
        self._tremolo = tremolo
        return True

    def _refuse_what_a_route_moves(self, destinations: tuple[str, ...]) -> None:
        """Refuse a direct setting of something a route moves (plan step 7b.6, a call).

        Raises:
            ValueError: Naming the route.
        """
        for route in self._routes:
            if route.destination in destinations:
                message = (
                    f'a route moves {route.destination} (from {route.source!r}): set '
                    f'{route.source!r} instead'
                )
                raise ValueError(message)

    def _glided(self, name: str, target: float, count: int) -> FloatArray:
        """A parameter's values across a chunk: its one-pole or linear glide (rule 1).

        Returns:
            One value per sample.
        """
        parameter = self._parameters[name]
        linear = self._linear_glides.get(name)
        if linear is None:
            return smoothed(
                start=self._current[name],
                target=target,
                count=count,
                smoothing_ms=parameter.smoothing_ms,
                sample_rate=self._sample_rate,
            )
        if target != linear.target:
            linear.set(
                target,
                samples=round(parameter.smoothing_ms * self._sample_rate / MILLISECONDS_PER_SECOND),
            )
        return linear.values(count)

    def set_volume(self, volume: float, *, fade: float = 0.0) -> bool:
        """Glide the volume in a straight line, over ``fade`` seconds and at least one chunk.

        Args:
            volume: 0-1.
            fade: Seconds to take (0: one chunk, the older voice's ramp, so it never clicks).

        Returns:
            True when taken; False once the voice is stopping or stopped.

        Raises:
            ValueError: For a volume outside 0-1 or a negative fade.
        """
        if not 0.0 <= volume <= 1.0:
            message = f'volume must be between 0 and 1, got {volume}'
            raise ValueError(message)
        if fade < 0.0:
            message = f'fade must not be negative, got {fade}'
            raise ValueError(message)
        if not self.stream.accepts_changes:
            return False
        samples = max(sample_count(fade, self._sample_rate), self.stream.chunk_samples)
        self._volume.set(volume, samples=samples)
        return True

    def _known(self, name: str) -> Parameter:
        parameter = self._parameters.get(name)
        if parameter is None:
            names = ', '.join(sorted(self._parameters)) or 'none'
            message = f'the instrument has no parameter {name!r}; its parameters: {names}'
            raise ValueError(message)
        return parameter

    def _store(self, name: str, value: float) -> None:
        inside, was_clamped = self._known(name).clamped(value)
        self.clamp_count += int(was_clamped)
        self._targets[name] = inside

    def _cutoff_at(self, values: Mapping[str, float]) -> float | None:
        """The filter's cutoff for parameter values (its route's, else the one set or given).

        Returns:
            The cutoff in hertz, or None without a filter.
        """
        for route in self._routes:
            if route.destination == 'filter.cutoff':
                parameter = self._parameters[route.source]
                at = np.array([values[route.source]], dtype=np.float64)
                return float(route_output(route=route, parameter=parameter, values=at)[0])
        return self._base_cutoff

    def _refuse_cutoffs_at_or_above_nyquist(self) -> None:
        nyquist = self._sample_rate * NYQUIST_FRACTION
        cutoffs = [] if self._instrument.filter is None else [self._instrument.filter.cutoff_hz]
        cutoffs += [
            end
            for route in self._routes
            if route.destination == 'filter.cutoff'
            for end in route.output
        ]
        if any(cutoff >= nyquist for cutoff in cutoffs):
            message = f'a filter cutoff must stay below the Nyquist frequency, {nyquist:g} Hz'
            raise ValueError(message)

    def _render_chunk(self, count: int) -> FloatArray:
        """Render one chunk (rule 4).

        Returns:
            The chunk's samples, before any stopping fade.
        """
        values = {name: self._glided(name, target, count) for name, target in self._targets.items()}
        self._current = {name: float(series[-1]) for name, series in values.items()}
        routed: dict[str, list[FloatArray]] = {}
        for route in self._routes:
            output = route_output(
                route=route, parameter=self._parameters[route.source], values=values[route.source]
            )
            routed.setdefault(route.destination, []).append(output)

        pitch = routed['pitch'][0] if 'pitch' in routed else self._frequency.values(count)
        mixed = np.zeros(count)
        for source in self._sources:
            raw, source.phase = oscillator(
                source.waveform,
                pitch * source.frequency_ratio,
                count / self._sample_rate,
                sample_rate=self._sample_rate,
                phase=source.phase,
                random_source=self._random_source,
            )
            level_routes = routed.get(f'sources.{source.name}.level')
            mixed += raw * (math.prod(level_routes) if level_routes else source.mix_level)

        ramp = np.arange(1, count + 1) / count
        samples = self._filter.filtered(raw=mixed, ramp=ramp, cutoff=self._cutoff_at(self._current))
        tremolo = self._tremolo
        if tremolo is not None:
            rates = (
                routed['tremolo.rate'][0]
                if 'tremolo.rate' in routed
                else np.full(count, tremolo.rate_hz)
            )
            depths = routed['tremolo.depth'][0] if 'tremolo.depth' in routed else tremolo.depth
            samples *= self._tremolo_gains(rates=rates, depths=depths)
        level_routes = routed.get('level')
        volumes = self._volume.values(count)
        return samples * (volumes * math.prod(level_routes) if level_routes else volumes)

    def _tremolo_gains(self, *, rates: FloatArray, depths: FloatArray | float) -> FloatArray:
        """Gain 1 at phase 0 and 1 - depth half a cycle later (``synth.tremolo``), per sample.

        Returns:
            The gains; the phase carries into the next chunk.
        """
        steps = rates / self._sample_rate
        phases = self._tremolo_phase + np.concatenate(([0.0], np.cumsum(steps[:-1])))
        self._tremolo_phase = float((self._tremolo_phase + steps.sum()) % 1.0)
        return 1.0 - depths * (0.5 - 0.5 * np.cos(2.0 * math.pi * phases))


class LiveSoundHandle:
    """A started live sound (``Sound.start()``): set its parameters, release or stop it.

    Stale-safe: once the voice is stopping or stopped (or never had a pool), every call answers
    False and changes nothing. A handle with no voice is what a live sound no audio engine
    handed out, or an engine with no live pool, starts.
    """

    def __init__(self, voice: InstrumentVoice | None) -> None:
        """Hold a started voice, or None for a silent handle."""
        self._voice = voice

    @property
    def is_playing(self) -> bool:
        """Whether the voice is playing (its release fade included, paused counts)."""
        return self._voice is not None and self._voice.stream.is_playing

    @property
    def parameter_values(self) -> dict[str, float]:
        """The latest value of each parameter, by name (empty for a silent handle)."""
        return {} if self._voice is None else self._voice.parameter_values

    @property
    def clamp_count(self) -> int:
        """How many values set were outside their parameter's range."""
        return 0 if self._voice is None else self._voice.clamp_count

    def set(self, name: str, value: float) -> bool:
        """Set a parameter; the next chunk glides toward it (``InstrumentVoice.set``).

        Returns:
            True when taken; False once stopping or stopped, or for a silent handle.
        """
        return self._voice is not None and self._voice.set(name, value)

    @property
    def is_paused(self) -> bool:
        """Whether it is paused (by ``pause``, or behind a pause screen)."""
        return self._voice is not None and self._voice.stream.state is VoiceState.PAUSED

    def set_volume(self, volume: float, *, fade: float = 0.0) -> bool:
        """Glide its volume, over ``fade`` seconds and at least one chunk (``InstrumentVoice``).

        Returns:
            True when taken; False once stopping or stopped, or for a silent handle.
        """
        return self._voice is not None and self._voice.set_volume(volume, fade=fade)

    def pause(self) -> bool:
        """Pause it until ``resume`` (the owner rules never resume it meanwhile).

        Returns:
            Whether it was playing and is now paused.
        """
        return self._voice is not None and self._voice.stream.hold()

    def resume(self) -> bool:
        """Resume what ``pause`` paused.

        Returns:
            Whether a pause was ended.
        """
        return self._voice is not None and self._voice.stream.release_hold()

    def set_frequency(self, frequency: float) -> bool:
        """Set its pitch straight, gliding over a chunk (``InstrumentVoice.set_frequency``).

        Returns:
            True when taken; False once stopping or stopped, or for a silent handle.
        """
        return self._voice is not None and self._voice.set_frequency(frequency)

    def set_cutoff(self, cutoff: float | None) -> bool:
        """Set its filter's cutoff straight, or None to remove it (``InstrumentVoice``).

        Returns:
            True when taken; False once stopping or stopped, or for a silent handle.
        """
        return self._voice is not None and self._voice.set_cutoff(cutoff)

    def set_tremolo(self, tremolo: Tremolo | None) -> bool:
        """Set its tremolo straight, or None to remove it (``InstrumentVoice.set_tremolo``).

        Returns:
            True when taken; False once stopping or stopped, or for a silent handle.
        """
        return self._voice is not None and self._voice.set_tremolo(tremolo)

    def set_pan(self, pan: float) -> bool:
        """Pan it, -1 (left) to 1 (right), by the constant-power law every sound pans by.

        Heard from the next chunk's start, ramped across it (``LiveStream.set_pan``).

        Returns:
            True when taken; False once finished, or for a silent handle.
        """
        if self._voice is None or self._voice.stream.is_finished:
            return False
        self._voice.stream.set_pan(pan)
        return True

    def release(self) -> bool:
        """End the sound: it fades out over the live release (``live.DEFAULT_FADE_OUT``).

        Returns:
            Whether it began releasing.
        """
        return self._voice is not None and self._voice.stream.stop(fade_out=DEFAULT_FADE_OUT)

    def cancel(self) -> bool:
        """End the sound at once, the chunk already queued included (``LiveStream.stop_now``).

        ``release`` and ``stop`` render their fade into the next chunk, which plays after the
        one already queued (up to a chunk later); cancel is for a sound that must end on the
        frame it is called (the elevator motor as the car lands).

        Returns:
            Whether it was still sounding (False once finished, or for a silent handle).
        """
        if self._voice is None or self._voice.stream.is_finished:
            return False
        self._voice.stream.stop_now()
        return True

    def stop(self, *, fade: float = DEFAULT_STOP_FADE_SECONDS) -> bool:
        """End the sound sooner: a fade of ``fade`` seconds (the library's stop fade).

        The fade is heard up to about two chunks late: the chunk playing and the one queued
        play out first (``LiveStream.stop`` in glitchygames/audio/live.py).

        Returns:
            Whether it began stopping.
        """
        return self._voice is not None and self._voice.stream.stop(fade_out=fade)
