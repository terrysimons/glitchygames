"""Sound recipes: sounds described as layered tones, rendered with the synth toolkit.

Recipes are data (to_dict/from_dict and TOML files), so a sound can live next to sprites and
be edited without code. Processing order per tone: oscillator, distortion, filters, tremolo,
envelope, volume. Tones are mixed at their offsets and the result normalized to `peak`.
"""

from __future__ import annotations

import dataclasses
import logging
import tomllib
from typing import TYPE_CHECKING, Any

import numpy as np

from glitchygames.audio.exceptions import AudioUnavailableError, SoundRecipeError
from glitchygames.audio.synth import (
    Envelope,
    FloatArray,
    Waveform,
    apply_envelope,
    distort,
    frequency_curve,
    high_pass,
    low_pass,
    mix,
    mixer_sample_rate,
    normalize,
    oscillator,
    to_sound,
    tremolo,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    import pygame

log: logging.Logger = logging.getLogger('game.audio.recipes')

RECIPE_NOISE_SEED = 0  # Fixed so a recipe sounds identical every time it renders


@dataclasses.dataclass(frozen=True)
class Tremolo:
    """Amplitude modulation settings."""

    rate_hz: float
    depth: float


@dataclasses.dataclass(frozen=True)
class Tone:
    """One layer of a sound."""

    waveform: Waveform
    start_frequency: float
    duration: float
    envelope: Envelope
    end_frequency: float | None = None  # None: constant pitch
    easing: str = 'linear'
    volume: float = 1.0
    offset: float = 0.0
    low_pass_cutoff: float | None = None
    high_pass_cutoff: float | None = None
    distortion: float | None = None
    tremolo: Tremolo | None = None

    def __post_init__(self) -> None:
        """Validate the settings.

        Raises:
            ValueError: If duration is not positive or offset/volume are negative.

        """
        if self.duration <= 0.0:
            message = f'duration must be > 0, got {self.duration}'
            raise ValueError(message)
        if self.offset < 0.0:
            message = f'offset must be >= 0, got {self.offset}'
            raise ValueError(message)
        if self.volume < 0.0:
            message = f'volume must be >= 0, got {self.volume}'
            raise ValueError(message)

    def render(self, *, sample_rate: int) -> FloatArray:
        """Render this tone (without its offset).

        Returns:
            The tone's samples.

        """
        if self.waveform is Waveform.NOISE or self.end_frequency is None:
            frequency: float | FloatArray = self.start_frequency
        else:
            frequency = frequency_curve(
                self.start_frequency,
                self.end_frequency,
                self.duration,
                easing=self.easing,
                sample_rate=sample_rate,
            )
        samples, _ = oscillator(
            self.waveform,
            frequency,
            self.duration,
            sample_rate=sample_rate,
            random_source=np.random.default_rng(RECIPE_NOISE_SEED),
        )
        if self.distortion is not None:
            samples = distort(samples, self.distortion)
        if self.low_pass_cutoff is not None:
            samples = low_pass(samples, self.low_pass_cutoff, sample_rate=sample_rate)
        if self.high_pass_cutoff is not None:
            samples = high_pass(samples, self.high_pass_cutoff, sample_rate=sample_rate)
        if self.tremolo is not None:
            samples, _ = tremolo(
                samples,
                self.tremolo.rate_hz,
                self.tremolo.depth,
                sample_rate=sample_rate,
            )
        return apply_envelope(samples, self.envelope, sample_rate=sample_rate) * self.volume


@dataclasses.dataclass(frozen=True)
class SoundRecipe:
    """A named sound made of tones."""

    name: str
    tones: tuple[Tone, ...]
    volume: float = 0.5
    peak: float = 0.9

    def render(self, *, sample_rate: int | None = None) -> FloatArray:
        """Mix every tone at its offset and normalize to peak.

        Returns:
            The sound's samples.

        """
        rate = mixer_sample_rate() if sample_rate is None else sample_rate
        layers = [(tone.render(sample_rate=rate), tone.offset) for tone in self.tones]
        return normalize(mix(*layers, sample_rate=rate), peak=self.peak)

    def to_sound(self) -> pygame.mixer.Sound:
        """Render at the mixer's rate and wrap as a pygame Sound.

        Returns:
            The sound.

        """
        return to_sound(self.render(), volume=self.volume)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain data (TOML/JSON friendly).

        Returns:
            The recipe as a dict (without its name, which is the key it is stored under).

        """
        return {
            'volume': self.volume,
            'peak': self.peak,
            'tones': [_tone_to_dict(tone) for tone in self.tones],
        }

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> SoundRecipe:
        """Build a recipe from to_dict() output.

        Returns:
            The recipe.

        Raises:
            SoundRecipeError: Naming the recipe and field that is invalid.

        """
        tones: list[Tone] = []
        for index, tone_data in enumerate(data.get('tones', [])):
            tones.append(_tone_from_dict(name=name, index=index, data=tone_data))
        try:
            return cls(
                name=name,
                tones=tuple(tones),
                volume=float(data.get('volume', 0.5)),
                peak=float(data.get('peak', 0.9)),
            )
        except (TypeError, ValueError) as error:
            message = f'{name}: {error}'
            raise SoundRecipeError(message) from error


def _tone_to_dict(tone: Tone) -> dict[str, Any]:
    data: dict[str, Any] = {
        'waveform': tone.waveform.value,
        'start_frequency': tone.start_frequency,
        'duration': tone.duration,
        'envelope': dataclasses.asdict(tone.envelope),
        'easing': tone.easing,
        'volume': tone.volume,
        'offset': tone.offset,
    }
    for optional in ('end_frequency', 'low_pass_cutoff', 'high_pass_cutoff', 'distortion'):
        value = getattr(tone, optional)
        if value is not None:
            data[optional] = value
    if tone.tremolo is not None:
        data['tremolo'] = dataclasses.asdict(tone.tremolo)
    return data


def _tone_from_dict(*, name: str, index: int, data: dict[str, Any]) -> Tone:
    location = f'{name}.tones[{index}]'
    try:
        waveform = Waveform(data['waveform'])
    except (KeyError, ValueError) as error:
        message = f'{location}.waveform: {data.get("waveform")!r} is not a waveform'
        raise SoundRecipeError(message) from error
    try:
        envelope = Envelope(**data['envelope'])
    except (KeyError, TypeError) as error:
        message = f'{location}.envelope: {error}'
        raise SoundRecipeError(message) from error
    tremolo_data = data.get('tremolo')
    try:
        return Tone(
            waveform=waveform,
            start_frequency=float(data['start_frequency']),
            duration=float(data['duration']),
            envelope=envelope,
            end_frequency=data.get('end_frequency'),
            easing=data.get('easing', 'linear'),
            volume=float(data.get('volume', 1.0)),
            offset=float(data.get('offset', 0.0)),
            low_pass_cutoff=data.get('low_pass_cutoff'),
            high_pass_cutoff=data.get('high_pass_cutoff'),
            distortion=data.get('distortion'),
            tremolo=Tremolo(**tremolo_data) if tremolo_data is not None else None,
        )
    except (KeyError, TypeError, ValueError) as error:
        message = f'{location}: {error}'
        raise SoundRecipeError(message) from error


def load_sound_recipes(path: Path) -> dict[str, SoundRecipe]:
    """Load every [recipes.<name>] table from a TOML file.

    Returns:
        Recipes by name.

    """
    with path.open('rb') as recipe_file:
        document = tomllib.load(recipe_file)
    return {
        name: SoundRecipe.from_dict(name, data)
        for name, data in document.get('recipes', {}).items()
    }


class SoundBank:
    """Plays recipes by name, rendering each on first use."""

    def __init__(self, recipes: Iterable[SoundRecipe]) -> None:
        """Index the recipes by name.

        Raises:
            ValueError: If two recipes share a name.

        """
        self._recipes: dict[str, SoundRecipe] = {}
        for recipe in recipes:
            if recipe.name in self._recipes:
                message = f'duplicate sound recipe name {recipe.name!r}'
                raise ValueError(message)
            self._recipes[recipe.name] = recipe
        self._sounds: dict[tuple[str, int], pygame.mixer.Sound] = {}
        self._unavailable_logged = False

    def play(self, name: str) -> None:
        """Play a sound; a no-op (logged once) when audio is unavailable.

        Raises:
            KeyError: If no recipe has this name.

        """
        recipe = self._recipes.get(name)
        if recipe is None:
            message = f'no sound recipe named {name!r}'
            raise KeyError(message)
        sound = self._render_cached(recipe)
        if sound is None:
            return
        # The pygame stub types Sound.play() as returning a Channel, but at runtime it returns
        # None when no unreserved channel is free. A Channel is always truthy, so test truthiness.
        if not sound.play():
            log.debug('No free mixer channel for sound %r', name)

    def prerender(self) -> None:
        """Render and cache every recipe at the mixer rate, so no sound renders mid-frame.

        A no-op (logged once, like play) when audio is unavailable.
        """
        for recipe in self._recipes.values():
            if self._render_cached(recipe) is None:
                return

    def _render_cached(self, recipe: SoundRecipe) -> pygame.mixer.Sound | None:
        """Return the recipe's Sound for the current mixer rate, rendering it on first use.

        Returns:
            The cached Sound, or None when audio is unavailable (logged once).

        """
        cache_key = (recipe.name, mixer_sample_rate())
        if cache_key not in self._sounds:
            try:
                self._sounds[cache_key] = to_sound(recipe.render(), volume=recipe.volume)
            except AudioUnavailableError:
                if not self._unavailable_logged:
                    log.warning('Audio unavailable; sound effects are silent')
                    self._unavailable_logged = True
                return None
        return self._sounds[cache_key]
