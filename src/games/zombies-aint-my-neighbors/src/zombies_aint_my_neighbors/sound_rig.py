"""Writes ``sounds/sounds.toml``: the game's sounds, as the sprites' rigs write theirs.

Feature plan 10 (plans/2026-11-15-zombies-aint-my-neighbors-10-first-sounds.md). The engine has no
vibrato in a baked sound yet (milestone M4), so each warble is a chain of swoops: tones each
sweeping its pitch with ``ease_in_out_sine``. A swoop lasts a whole number of its own cycles (its
mean pitch, by the easing's symmetry, times its length), so it ends where it began, at phase 0,
and the next starts there: the chain is one unbroken wave, with no overlap and no fade between
swoops (overlapping two tones of near pitch made them beat, a blip at each join). The waves are
sines, which start at zero, so a join steps nowhere; a sawtooth jumps every cycle anyway.

Per-tone tremolo restarts with each tone, so it would click at every join: only a single-tone
sound has it. Regenerate with ``uv run python -m zombies_aint_my_neighbors.sound_rig``; a test
keeps the file equal to this output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from zombies_aint_my_neighbors.sounds import (
    GATE,
    GROANS,
    KNOCKOUT,
    LASER_RISE,
    LASER_SHINE,
    LOSS,
    RESCUE,
    SOUND_FILE,
    SWITCH_OFF,
    TV_BREAK,
    TV_DESTROYED,
    TV_HIT,
    TV_SPAWN,
    ZAP,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

SWOOP_EASING: Final = 'ease_in_out_sine'
# Seconds the file's numbers keep (well under a sample at 44.1 kHz)
DECIMALS: Final = 6


class ToneSpec(BaseModel):
    """One ``[[effects.<name>.tones]]`` table."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    waveform: str
    start_frequency: float
    end_frequency: float | None = None
    offset: float = 0.0
    duration: float
    attack: float = 0.0
    decay: float = 0.0
    sustain_level: float = 1.0
    release: float = 0.0
    # None: the tone at full level (the file then leaves volume out)
    volume: float | None = None
    low_pass_cutoff: float | None = None
    high_pass_cutoff: float | None = None
    distortion: float | None = None
    tremolo: tuple[float, float] | None = None


class Shaping(BaseModel):
    """What every swoop of a chain shares: its wave, any filter or distortion, and its joins.

    With no crossfade the swoops join end to end, and a plain sine runs on as one unbroken wave.
    A filtered wave can't: its filter starts afresh with each tone, and a sawtooth restarts its
    ramp, so each join clicks. A crossfade overlaps neighbours instead: each later swoop starts
    before the last ends, fading in while the last fades out. Each overlap is the whole number of
    cycles at its join's pitch nearest ``crossfade`` seconds, so the two waves fade across each
    other in step (half a cycle apart, they would cancel: a dip in loudness at every join).
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    waveform: str = 'sine'
    low_pass_cutoff: float | None = None
    distortion: float | None = None
    # Seconds each join overlaps, roughly (0: end to end, with no fade between swoops)
    crossfade: float = 0.0


class EffectSpec(BaseModel):
    """One ``[effects.<name>]`` table: its volume, its tones, and the comment above it."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    name: str
    comment: tuple[str, ...]
    volume: float
    tones: tuple[ToneSpec, ...]


# A plain sine swoop: the warbles' wave
SINE: Final = Shaping()


def whole_cycle_seconds(*, start: float, end: float, about: float) -> float:
    """Return a swoop's length nearest ``about`` that holds a whole number of its cycles.

    Returns:
        Seconds.

    """
    mean_pitch = (start + end) / 2
    cycles = max(1, round(mean_pitch * about))
    return cycles / mean_pitch


def swoops(
    *,
    pitches: Sequence[tuple[float, float]],
    abouts: Sequence[float],
    fade_in: float,
    fade_out: float,
    shaping: Shaping = SINE,
) -> tuple[ToneSpec, ...]:
    """Return a chain of sine-shaped pitch swoops, each a whole number of cycles.

    Joined end to end, or crossfaded as ``shaping`` says (see ``Shaping``).

    Args:
        pitches: Each swoop's start and end pitch, in hertz.
        abouts: Each swoop's rough length, in seconds (made a whole number of cycles).
        fade_in: The first swoop's attack.
        fade_out: The last swoop's release.
        shaping: What every swoop shares (a plain sine by default).

    Returns:
        The tones.

    """
    # Each join's overlap: whole cycles at the pitch the earlier swoop ends on
    overlaps = [
        round(max(1, round(end * shaping.crossfade)) / end, DECIMALS) if shaping.crossfade else 0.0
        for _, end in pitches[:-1]
    ]
    tones: list[ToneSpec] = []
    offset = 0.0
    for index, ((start, end), about) in enumerate(zip(pitches, abouts, strict=True)):
        duration = whole_cycle_seconds(start=start, end=end, about=about)
        fade_from_last = overlaps[index - 1] if index else fade_in
        fade_into_next = overlaps[index] if index < len(overlaps) else fade_out
        tones.append(
            ToneSpec(
                start_frequency=start,
                end_frequency=end,
                offset=round(offset, DECIMALS),
                duration=round(duration, DECIMALS),
                attack=fade_from_last,
                release=fade_into_next,
                waveform=shaping.waveform,
                low_pass_cutoff=shaping.low_pass_cutoff,
                distortion=shaping.distortion,
            )
        )
        offset += round(duration, DECIMALS) - (overlaps[index] if index < len(overlaps) else 0.0)
    return tuple(tones)


def chain_seconds(tones: Sequence[ToneSpec]) -> float:
    """Return how long a chain of tones lasts.

    Returns:
        Seconds.

    """
    return max(tone.offset + tone.duration for tone in tones)


def _zap() -> EffectSpec:
    swoop_tones = swoops(
        pitches=((620, 700), (700, 600), (600, 690), (690, 610), (610, 670), (670, 630)),
        abouts=(0.036,) * 6,
        fade_in=0.004,
        fade_out=0.03,
    )
    hiss = ToneSpec(
        waveform='noise',
        start_frequency=1000.0,
        duration=round(chain_seconds(swoop_tones), DECIMALS),
        attack=0.01,
        decay=0.05,
        sustain_level=0.5,
        release=0.05,
        volume=0.12,
        high_pass_cutoff=2500.0,
    )
    return EffectSpec(
        name=ZAP,
        comment=(
            "The remote's zap: warbly theremin radio waves (the owner, 2026-11-15). Six swoops",
            'between about 600 and 700 Hz, 0.22 s in all (under the 0.25 s firing rhythm), and a',
            'quiet high hiss for the radio.',
        ),
        volume=0.35,
        tones=(*swoop_tones, hiss),
    )


def _laser_rise() -> EffectSpec:
    return EffectSpec(
        name=LASER_RISE,
        comment=(
            "The laser's warm-up: wheeee, rising over its 0.4 s. Four swoops, each overshooting a",
            'little and settling back as the next begins, about 500 to 1400 Hz in all.',
        ),
        volume=0.3,
        tones=swoops(
            pitches=((500, 820), (780, 1060), (1020, 1300), (1260, 1420)),
            abouts=(0.1,) * 4,
            fade_in=0.005,
            fade_out=0.03,
        ),
    )


def _laser_shine() -> EffectSpec:
    return EffectSpec(
        name=LASER_SHINE,
        comment=(
            'The laser shining: a high wobble, looped while the dot shines (faded out by the game',
            'when it goes out). Four swoops in about 0.5 s with no fade at either end: it ends at',
            'the pitch and phase it starts at, so the loop runs on unbroken.',
        ),
        volume=0.3,
        tones=swoops(
            pitches=((1300, 1500), (1500, 1300), (1300, 1500), (1500, 1300)),
            abouts=(0.125,) * 4,
            fade_in=0.0,
            fade_out=0.0,
        ),
    )


# Every groan's tone: a growly sawtooth, darkened and roughened. Its swoops overlap by about two
# cycles of its 80 to 125 Hz, long enough to hide the filter's restart (end to end, each join
# clicked: the owner heard it as clipping, 2026-11-16)
GROWL: Final = Shaping(waveform='sawtooth', low_pass_cutoff=700.0, distortion=0.3, crossfade=0.02)


def _groans() -> tuple[EffectSpec, ...]:
    falling = ToneSpec(
        start_frequency=115.0,
        end_frequency=80.0,
        duration=0.8,
        attack=0.08,
        decay=0.1,
        sustain_level=0.8,
        release=0.25,
        tremolo=(5.0, 0.35),
        waveform=GROWL.waveform,
        low_pass_cutoff=GROWL.low_pass_cutoff,
        distortion=GROWL.distortion,
    )
    shapes = (
        ("A zombie's moan, falling: a low growl sinking from about 115 to 80 Hz.", (falling,)),
        (
            'A zombie\'s moan, rising then falling: "uuhh-aaahh".',
            swoops(
                pitches=((85, 125), (125, 78)),
                abouts=(0.35, 0.5),
                fade_in=0.08,
                fade_out=0.25,
                shaping=GROWL,
            ),
        ),
        (
            "A zombie's moan, wavering as it trails off.",
            swoops(
                pitches=((100, 82), (82, 108), (108, 80)),
                abouts=(0.25, 0.22, 0.32),
                fade_in=0.08,
                fade_out=0.25,
                shaping=GROWL,
            ),
        ),
    )
    return tuple(
        EffectSpec(name=name, comment=(comment,), volume=0.5, tones=tones)
        for name, (comment, tones) in zip(GROANS, shapes, strict=True)
    )


# Feature plan 11 (plans/2026-11-18-zombies-aint-my-neighbors-11-the-rest-of-the-sounds.md). Each
# effect has at most one chain of swoops (a pitch that moves); its other layers hold one pitch, or
# are noise, so the chain rules above hold for every effect.


def _static(  # ruff: ignore[too-many-arguments] - one layer's knobs, all keywords
    *,
    duration: float,
    offset: float = 0.0,
    volume: float,
    high_pass: float | None = None,
    low_pass: float | None = None,
    distortion: float | None = None,
    attack: float = 0.003,
    decay: float = 0.05,
    sustain_level: float = 0.4,
    release: float = 0.05,
) -> ToneSpec:
    """Return a burst of noise: static, a crunch, a knock or a click.

    Returns:
        The tone.

    """
    return ToneSpec(
        waveform='noise',
        start_frequency=1000.0,
        offset=offset,
        duration=duration,
        attack=attack,
        decay=decay,
        sustain_level=sustain_level,
        release=release,
        volume=volume,
        high_pass_cutoff=high_pass,
        low_pass_cutoff=low_pass,
        distortion=distortion,
    )


def _held(  # ruff: ignore[too-many-arguments] - one layer's knobs, all keywords
    *,
    pitch: float,
    duration: float,
    offset: float = 0.0,
    volume: float,
    waveform: str = 'sine',
    attack: float = 0.003,
    release: float = 0.05,
) -> ToneSpec:
    """Return a tone held at one pitch: a tick, a chirp's note, a thud.

    Returns:
        The tone.

    """
    return ToneSpec(
        waveform=waveform,
        start_frequency=pitch,
        offset=offset,
        duration=duration,
        attack=attack,
        release=release,
        volume=volume,
    )


def _tv_spawn() -> EffectSpec:
    thump = swoops(pitches=((90, 45),), abouts=(0.25,), fade_in=0.004, fade_out=0.15)
    return EffectSpec(
        name=TV_SPAWN,
        comment=(
            'A zombie climbing out of a TV: the picture tube thumps (90 falling to 45 Hz) and the',
            'screen bursts into static.',
        ),
        volume=0.4,
        tones=(
            *thump,
            _static(
                duration=0.4, offset=0.05, volume=1.0, high_pass=2000.0, attack=0.02, release=0.15
            ),
        ),
    )


def _tv_hit() -> EffectSpec:
    return EffectSpec(
        name=TV_HIT,
        comment=('A zap on a TV: a glassy tick and a blip of static.',),
        volume=0.3,
        tones=(
            _held(pitch=2400.0, duration=0.03, volume=0.5, attack=0.002, release=0.02),
            _static(duration=0.1, volume=0.5, high_pass=3000.0, decay=0.03, sustain_level=0.3),
        ),
    )


def _crunch(*, volume: float) -> ToneSpec:
    """Return breaking glass: rough, bright noise.

    Returns:
        The tone.

    """
    return _static(
        duration=0.25,
        volume=volume,
        low_pass=5000.0,
        distortion=2.0,
        attack=0.002,
        decay=0.08,
        sustain_level=0.3,
        release=0.12,
    )


def _tv_break() -> EffectSpec:
    return EffectSpec(
        name=TV_BREAK,
        comment=('A TV breaking into its next stage: a crunch of glass, a shard ringing.',),
        volume=0.4,
        tones=(
            _crunch(volume=0.8),
            _held(pitch=3100.0, duration=0.15, offset=0.03, volume=0.2, release=0.1),
        ),
    )


def _tv_destroyed() -> EffectSpec:
    boom = swoops(pitches=((70, 35),), abouts=(0.6,), fade_in=0.005, fade_out=0.35)
    return EffectSpec(
        name=TV_DESTROYED,
        comment=(
            'A TV destroyed: the crunch, a low boom (70 falling to 35 Hz) and the tube fizzling',
            'out.',
        ),
        volume=0.5,
        tones=(
            _crunch(volume=0.5),
            *boom,
            _static(
                duration=0.6,
                offset=0.25,
                volume=0.15,
                high_pass=4000.0,
                attack=0.05,
                sustain_level=0.3,
                release=0.3,
            ),
        ),
    )


def _rescue() -> EffectSpec:
    # E5, A5 and C#6: an A major arpeggio, up
    notes = ((659.26, 0.0, 0.09), (880.0, 0.09, 0.09), (1108.73, 0.18, 0.12))
    return EffectSpec(
        name=RESCUE,
        comment=('A neighbor rescued: three bright notes chirping up (E5, A5, C#6).',),
        volume=0.35,
        tones=tuple(
            _held(
                pitch=pitch,
                duration=duration,
                offset=offset,
                volume=0.8,
                waveform='triangle',
                attack=0.005,
                release=0.03,
            )
            for pitch, offset, duration in notes
        ),
    )


def _loss() -> EffectSpec:
    wail = swoops(
        pitches=((900, 700), (700, 760), (760, 420)),
        abouts=(0.12, 0.08, 0.2),
        fade_in=0.01,
        fade_out=0.06,
    )
    return EffectSpec(
        name=LOSS,
        comment=('A neighbor lost: a wail wavering down from 900 to 420 Hz, then a thud.',),
        volume=0.4,
        tones=(
            *wail,
            _held(
                pitch=60.0,
                duration=0.15,
                offset=round(chain_seconds(wail), DECIMALS),
                volume=0.8,
                release=0.1,
            ),
        ),
    )


def _knockout() -> EffectSpec:
    bonk = swoops(pitches=((700, 170),), abouts=(0.18,), fade_in=0.002, fade_out=0.1)
    return EffectSpec(
        name=KNOCKOUT,
        comment=('A kid knocked out: a cartoon bonk, the pitch dropping, and a knock.',),
        volume=0.4,
        tones=(
            *bonk,
            _static(
                duration=0.03,
                volume=0.6,
                low_pass=1500.0,
                attack=0.001,
                decay=0.01,
                sustain_level=0.5,
                release=0.02,
            ),
        ),
    )


# The gate's creak: a dark, rough sawtooth, crossfaded as the groans are
CREAK: Final = Shaping(waveform='sawtooth', low_pass_cutoff=1200.0, distortion=0.2, crossfade=0.02)


def _gate() -> EffectSpec:
    return EffectSpec(
        name=GATE,
        comment=(
            'The exit gate swinging open: an iron creak wavering between about 300 and 460 Hz,',
            'outlasting the swing a little, as a heavy gate settles.',
        ),
        volume=0.35,
        tones=swoops(
            pitches=((300, 420), (420, 330), (330, 460), (460, 350)),
            abouts=(0.12, 0.1, 0.14, 0.16),
            fade_in=0.03,
            fade_out=0.1,
            shaping=CREAK,
        ),
    )


def _switch_off() -> EffectSpec:
    whine = swoops(pitches=((1600, 60),), abouts=(0.55,), fade_in=0.002, fade_out=0.1)
    return EffectSpec(
        name=SWITCH_OFF,
        comment=(
            'The TV switching off (the game over): the tube whine falling from 1600 to 60 Hz as',
            'the picture collapses, and the switch clicking.',
        ),
        volume=0.35,
        tones=(
            *whine,
            _static(
                duration=0.02,
                offset=0.55,
                volume=0.5,
                attack=0.001,
                decay=0.005,
                sustain_level=0.5,
                release=0.01,
            ),
        ),
    )


def effects() -> tuple[EffectSpec, ...]:
    """Return every effect the game plays, in the file's order.

    Returns:
        The effects.

    """
    return (
        _zap(),
        _laser_rise(),
        _laser_shine(),
        *_groans(),
        _tv_spawn(),
        _tv_hit(),
        _tv_break(),
        _tv_destroyed(),
        _rescue(),
        _loss(),
        _knockout(),
        _gate(),
        _switch_off(),
    )


def _number(value: float) -> str:
    return repr(float(value))


def _tone_lines(effect_name: str, tone: ToneSpec) -> list[str]:
    lines = [
        '',
        f'[[effects.{effect_name}.tones]]',
        f'waveform = "{tone.waveform}"',
        f'start_frequency = {_number(tone.start_frequency)}',
    ]
    if tone.end_frequency is not None:
        lines += [f'end_frequency = {_number(tone.end_frequency)}', f'easing = "{SWOOP_EASING}"']
    lines += [f'offset = {_number(tone.offset)}', f'duration = {_number(tone.duration)}']
    if tone.volume is not None:
        lines.append(f'volume = {_number(tone.volume)}')
    for field in ('low_pass_cutoff', 'high_pass_cutoff', 'distortion'):
        value = getattr(tone, field)
        if value is not None:
            lines.append(f'{field} = {_number(value)}')
    lines.append(
        f'envelope = {{ attack = {_number(tone.attack)}, decay = {_number(tone.decay)}, '
        f'sustain_level = {_number(tone.sustain_level)}, release = {_number(tone.release)} }}'
    )
    if tone.tremolo is not None:
        rate, depth = tone.tremolo
        lines.append(f'tremolo = {{ rate_hz = {_number(rate)}, depth = {_number(depth)} }}')
    return lines


def document() -> str:
    """Return the sound file's text.

    Returns:
        The TOML.

    """
    lines = [
        "# The game's sounds, written by zombies_aint_my_neighbors/sound_rig.py (do not edit by",
        '# hand: change the rig and run it). Feature plans 10 and 11.',
        '',
        '[glitchygames]',
        'kind = "sounds"',
        'version = 1',
    ]
    for effect in effects():
        lines += ['', *(f'# {line}' for line in effect.comment), f'[effects.{effect.name}]']
        lines.append(f'volume = {_number(effect.volume)}')
        for tone in effect.tones:
            lines += _tone_lines(effect.name, tone)
    return '\n'.join(lines) + '\n'


def main() -> None:
    """Write the sound file."""
    SOUND_FILE.write_text(document(), encoding='utf-8')


if __name__ == '__main__':
    main()
