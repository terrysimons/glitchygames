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

from zombies_aint_my_neighbors.sounds import GROANS, LASER_RISE, LASER_SHINE, SOUND_FILE, ZAP

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
    """What every swoop of a chain shares: its wave, and any filter or distortion."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    waveform: str = 'sine'
    low_pass_cutoff: float | None = None
    distortion: float | None = None


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
    """Return a chain of sine-shaped pitch swoops, end to end, each a whole number of cycles.

    Args:
        pitches: Each swoop's start and end pitch, in hertz.
        abouts: Each swoop's rough length, in seconds (made a whole number of cycles).
        fade_in: The first swoop's attack (none between swoops).
        fade_out: The last swoop's release.
        shaping: What every swoop shares (a plain sine by default).

    Returns:
        The tones.

    """
    tones: list[ToneSpec] = []
    offset = 0.0
    for index, ((start, end), about) in enumerate(zip(pitches, abouts, strict=True)):
        duration = whole_cycle_seconds(start=start, end=end, about=about)
        tones.append(
            ToneSpec(
                start_frequency=start,
                end_frequency=end,
                offset=round(offset, DECIMALS),
                duration=round(duration, DECIMALS),
                attack=fade_in if index == 0 else 0.0,
                release=fade_out if index == len(pitches) - 1 else 0.0,
                waveform=shaping.waveform,
                low_pass_cutoff=shaping.low_pass_cutoff,
                distortion=shaping.distortion,
            )
        )
        offset += round(duration, DECIMALS)
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


# Every groan's tone: a growly sawtooth, darkened and roughened
GROWL: Final = Shaping(waveform='sawtooth', low_pass_cutoff=700.0, distortion=0.3)


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


def effects() -> tuple[EffectSpec, ...]:
    """Return every effect the game plays, in the file's order.

    Returns:
        The effects.

    """
    return (_zap(), _laser_rise(), _laser_shine(), *_groans())


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
        '# hand: change the rig and run it). Feature plan 10.',
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
