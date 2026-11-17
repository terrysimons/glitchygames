"""The game's sounds, as they render: the remote's warble, the laser's wheee, the groans.

Feature plan 10 (plans/2026-11-15-zombies-aint-my-neighbors-10-first-sounds.md). Nobody can listen
in a test, so each sound's shape is measured from its rendered samples: its pitch through time,
taken as the loudest frequency of short overlapping windows.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Final

import numpy as np
import pytest

import zombies_aint_my_neighbors
from glitchygames.audio.assets import load_sound_file
from zombies_aint_my_neighbors import sound_rig
from zombies_aint_my_neighbors.kid import FIRE_SECONDS
from zombies_aint_my_neighbors.laser import WARM_UP_SECONDS
from zombies_aint_my_neighbors.roster_scene import RosterScene
from zombies_aint_my_neighbors.sounds import (
    GROANS,
    LASER_RISE,
    LASER_SHINE,
    SOUND_FILE,
    ZAP,
)

SAMPLE_RATE: Final = 44100
# Pitch windows: 20 ms each, every 5 ms; zero-padded so the peak lands within a few hertz
WINDOW_SECONDS: Final = 0.02
# A groan's: 60 ms, since 20 ms holds under two cycles of an 80 Hz moan, too few to measure
LOW_WINDOW_SECONDS: Final = 0.06
# The windows that count as a sound's beginning and its end
EDGE_WINDOWS: Final = 5
HOP_SECONDS: Final = 0.005
PADDED_WINDOW: Final = 1 << 15
# Windows quieter than this share of the loudest are skipped (a sound's fade in and out)
QUIET_SHARE: Final = 0.25
# A click: a step between neighbouring samples this many times the sound's own largest steps
# (its 99.9th percentile). Measured 2026-11-16: the clean sounds' largest steps are at most 1.5
# times it, the groans' clicking swoop joins 12 to 14 times
CLICK_STEP_RATIO: Final = 3.0
# A crossfaded join may be no quieter than this share of the sound 50 ms either side of it.
# Measured 2026-11-16: in step, within 8%; half a cycle apart, 30% down
JOIN_LOUDNESS_SHARE: Final = 0.85
JOIN_NEIGHBOURHOOD_SECONDS: Final = 0.05
# Loudness is measured over 20 ms, about two cycles of a groan
LOUDNESS_WINDOW_SECONDS: Final = 0.02
EVERY_EFFECT: Final = tuple(effect.name for effect in sound_rig.effects())


def rendered(name: str) -> np.ndarray:
    """Render one of the game's sounds, mono.

    Returns:
        Its samples.

    """
    effect = load_sound_file(SOUND_FILE).sounds[name].effect
    assert effect is not None, f'{name} is not an effect'
    samples = np.asarray(effect.render(sample_rate=SAMPLE_RATE), dtype=float)
    return samples if samples.ndim == 1 else samples.mean(axis=1)


def pitch_track(
    samples: np.ndarray, *, lowest: float, highest: float, window_seconds: float = WINDOW_SECONDS
) -> list[float]:
    """Return the loudest frequency between two bounds in each loud enough window, in order.

    Returns:
        Hertz, a value per window.

    """
    window = round(window_seconds * SAMPLE_RATE)
    hop = round(HOP_SECONDS * SAMPLE_RATE)
    taper = np.hanning(window)
    frequencies = np.fft.rfftfreq(PADDED_WINDOW, d=1.0 / SAMPLE_RATE)
    band = (frequencies >= lowest) & (frequencies <= highest)
    loudest = float(np.max(np.abs(samples)))
    track = []
    for start in range(0, len(samples) - window, hop):
        segment = samples[start : start + window]
        if float(np.max(np.abs(segment))) < QUIET_SHARE * loudest:
            continue
        spectrum = np.abs(np.fft.rfft(segment * taper, n=PADDED_WINDOW))
        track.append(float(frequencies[band][np.argmax(spectrum[band])]))
    return track


def turns(track: list[float], *, swing: float) -> int:
    """Count how often a pitch track changes direction by at least ``swing`` hertz.

    Returns:
        The turns.

    """
    count = 0
    # 0 until the pitch first moves by a swing, then 1 rising or -1 falling
    direction = 0
    extreme = track[0]
    for value in track[1:]:
        if direction == 0:
            if abs(value - extreme) >= swing:
                direction = 1 if value > extreme else -1
                extreme = value
        elif (value - extreme) * direction > 0:
            extreme = value
        elif abs(value - extreme) >= swing:
            count += 1
            direction = -direction
            extreme = value
    return count


def seconds(name: str) -> float:
    """Return how long one of the game's sounds lasts.

    Returns:
        Seconds.

    """
    return len(rendered(name)) / SAMPLE_RATE


def test_every_sound_the_game_plays_is_an_effect_in_its_file():
    """The zap, the laser's two, and the three groans, each an effect the file defines."""
    sounds = load_sound_file(SOUND_FILE).sounds

    for name in (ZAP, LASER_RISE, LASER_SHINE, *GROANS):
        assert sounds[name].effect is not None, name


def test_the_sound_file_ships_with_the_game():
    """It sits in the game's package, beside its sprites, so a wheel carries it."""
    package = Path(zombies_aint_my_neighbors.__file__).parent

    assert package / 'sounds' / 'sounds.toml' == SOUND_FILE
    assert SOUND_FILE.is_file()


def test_the_title_and_the_neighborhood_compile_every_sound_before_play():
    """Declared on RosterScene, so the engine compiles them while the game starts (decision 11)."""
    declared = set(RosterScene.SOUNDS)

    for name in (ZAP, LASER_RISE, LASER_SHINE, *GROANS):
        assert f'{SOUND_FILE}#{name}' in declared, name


def test_a_zap_ends_before_the_next_shot():
    """Shorter than the firing rhythm, so held fire never piles zaps up."""
    assert 0.15 <= seconds(ZAP) < FIRE_SECONDS


def test_a_zap_wavers_like_a_theremin():
    """Its pitch rises and falls at least four times, staying near 600 to 700 Hz."""
    track = pitch_track(rendered(ZAP), lowest=300.0, highest=1500.0)

    assert min(track) >= 580.0
    assert max(track) <= 720.0
    assert turns(track, swing=40.0) >= 4


def test_the_lasers_rise_lasts_its_warm_up():
    """The wheee spans the 0.4 s before the dot lights."""
    assert seconds(LASER_RISE) == pytest.approx(WARM_UP_SECONDS, abs=0.02)


def test_the_lasers_rise_climbs_to_twice_its_start():
    """Wheeee: it ends at least an octave above where it began."""
    track = pitch_track(rendered(LASER_RISE), lowest=300.0, highest=3000.0)

    assert np.median(track[-EDGE_WINDOWS:]) >= 2.0 * np.median(track[:EDGE_WINDOWS])


def test_the_lasers_shine_wobbles_high():
    """While the dot shines: a high pitch, wobbling, near 1300 to 1500 Hz."""
    track = pitch_track(rendered(LASER_SHINE), lowest=600.0, highest=3000.0)

    assert min(track) >= 1250.0
    assert max(track) <= 1550.0
    assert turns(track, swing=80.0) >= 3


def test_the_lasers_shine_loops_without_a_jump_in_pitch():
    """Played looping, its end runs into its start at the same pitch."""
    track = pitch_track(rendered(LASER_SHINE), lowest=600.0, highest=3000.0)

    assert track[-1] == pytest.approx(track[0], abs=60.0)


@pytest.mark.parametrize('name', GROANS)
def test_every_groan_is_low(name):
    """A zombie's moan stays under 150 Hz."""
    track = pitch_track(
        rendered(name), lowest=40.0, highest=1000.0, window_seconds=LOW_WINDOW_SECONDS
    )

    assert max(track) < 150.0


def test_the_groans_are_three_different_moans():
    """Falling, rising then falling, and wavering: no two sound alike."""
    tracks = [
        pitch_track(rendered(name), lowest=40.0, highest=1000.0, window_seconds=LOW_WINDOW_SECONDS)
        for name in GROANS
    ]

    assert len(GROANS) == 3
    assert len({tuple(round(value) for value in track) for track in tracks}) == 3


@pytest.mark.parametrize('name', EVERY_EFFECT)
def test_no_sound_clicks(name):
    """No jump between neighbouring samples stands far out of the sound's own steps.

    A tone that starts or stops abruptly, such as a filtered sawtooth restarting where two swoops
    join, clicks: one step many times the waveform's largest (the owner heard the groans'
    joins as clipping, 2026-11-16).
    """
    steps = np.abs(np.diff(rendered(name)))

    assert steps.max() <= CLICK_STEP_RATIO * np.percentile(steps, 99.9), (
        f'a click at {np.argmax(steps) / SAMPLE_RATE:.4f} s'
    )


def loudness(samples: np.ndarray, *, at_seconds: float) -> float:
    """Return a sound's root-mean-square level over a short window centred on a moment.

    Returns:
        The level.

    """
    half = round(LOUDNESS_WINDOW_SECONDS * SAMPLE_RATE / 2)
    centre = round(at_seconds * SAMPLE_RATE)
    window = samples[max(0, centre - half) : centre + half]
    return float(np.sqrt(np.mean(window**2)))


@pytest.mark.parametrize('name', EVERY_EFFECT)
def test_no_crossfaded_join_dips(name):
    """Two swoops fading across each other stay as loud as the sound around them.

    Out of step (half a cycle apart) they cancel, and the moan ducks at every join.
    """
    samples = rendered(name)
    effect = load_sound_file(SOUND_FILE).sounds[name].effect
    assert effect is not None
    for tone in effect.tones[1:]:
        if tone.envelope.attack == 0.0 or tone.offset == 0.0:
            continue
        join = tone.offset + tone.envelope.attack / 2
        around = min(
            loudness(samples, at_seconds=join - JOIN_NEIGHBOURHOOD_SECONDS),
            loudness(samples, at_seconds=join + JOIN_NEIGHBOURHOOD_SECONDS),
        )

        assert loudness(samples, at_seconds=join) >= JOIN_LOUDNESS_SHARE * around, (
            f'a dip at {join:.3f} s'
        )


def test_the_sound_file_is_its_rigs_output():
    """Written by sound_rig.py, never by hand: the file equals what the rig writes now."""
    assert SOUND_FILE.read_text(encoding='utf-8') == sound_rig.document()


def test_every_swoop_holds_whole_cycles_and_joins_end_to_end_or_crossfaded():
    """Each swoop holds a whole number of its cycles; each join is one of two kinds.

    End to end with no fade, so a plain sine warble is one unbroken wave (overlapped tones beat,
    a blip at each join); or crossfaded, the overlap exactly the earlier swoop's fade out and the
    later one's fade in, so a filtered wave's restart is hidden under the fade.
    """
    for effect in sound_rig.effects():
        swoop_tones = [tone for tone in effect.tones if tone.end_frequency is not None]
        for tone in swoop_tones:
            assert tone.end_frequency is not None
            cycles = (tone.start_frequency + tone.end_frequency) / 2 * tone.duration
            assert cycles == pytest.approx(round(cycles), abs=0.01), effect.name
        for earlier, later in itertools.pairwise(swoop_tones):
            overlap = earlier.offset + earlier.duration - later.offset
            assert overlap == pytest.approx(earlier.release, abs=1e-6), effect.name
            assert overlap == pytest.approx(later.attack, abs=1e-6), effect.name


def test_running_the_rig_writes_the_sound_file(tmp_path, monkeypatch):
    """``python -m zombies_aint_my_neighbors.sound_rig`` writes the file the game loads."""
    target = tmp_path / 'sounds.toml'
    monkeypatch.setattr(sound_rig, 'SOUND_FILE', target)

    sound_rig.main()

    assert target.read_text(encoding='utf-8') == sound_rig.document()
