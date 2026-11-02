"""Tests for named waves, mixes, blends, harmonics, wave points and the wave registry."""

import numpy as np
import pytest

from glitchygames.audio.waves import (
    BUILT_IN_WAVE_NAMES,
    CYCLE,
    LEVEL,
    WAVE_TABLE_LENGTH,
    Harmonics,
    Wave,
    WavePoint,
    WaveRegistry,
)

GHOST_POINTS = (
    WavePoint(at=CYCLE.START, level=LEVEL.CENTER),
    WavePoint(at=CYCLE.EIGHTH, level=0.8),
    WavePoint(at=CYCLE.QUARTER, level=0.3),
    WavePoint(at=CYCLE.HALF, level=LEVEL.CENTER),
    WavePoint(at=CYCLE.THREE_QUARTERS, level=-0.6),
    WavePoint(at=CYCLE.END, level=LEVEL.CENTER),
)


@pytest.mark.parametrize('name', BUILT_IN_WAVE_NAMES)
def test_every_built_in_wave_has_a_full_table(name):
    """Every built in wave has a full table."""
    table = Wave(name).table()
    assert table.shape == (WAVE_TABLE_LENGTH,)
    assert np.max(np.abs(table)) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ('name', 'expected_duty'),
    [('square', 0.5), ('pulse_12', 0.125), ('pulse_25', 0.25), ('pulse_75', 0.75)],
)
def test_pulse_duty_is_the_high_fraction_of_the_cycle(name, expected_duty):
    """Pulse duty is the high fraction of the cycle."""
    wave = Wave(name)
    assert wave.duty == expected_duty
    assert np.mean(wave.table() > 0) == pytest.approx(expected_duty)


def test_pulse_takes_an_explicit_duty():
    """Pulse takes an explicit duty."""
    wave = Wave('pulse', duty=0.125)
    assert np.mean(wave.table() > 0) == pytest.approx(0.125)
    assert Wave('pulse').duty == 0.5


def test_triangle_starts_at_center_and_peaks_a_quarter_in():
    """Triangle starts at center and peaks a quarter in."""
    table = Wave('triangle').table()
    assert table[0] == pytest.approx(0.0)
    assert table[WAVE_TABLE_LENGTH // 4] == pytest.approx(1.0)
    assert table[3 * WAVE_TABLE_LENGTH // 4] == pytest.approx(-1.0)


@pytest.mark.parametrize(
    ('name', 'is_polyblep'),
    [
        ('sine', False),
        ('triangle', False),
        ('saw', True),
        ('square', True),
        ('pulse', True),
        ('pulse_12', True),
        ('pulse_25', True),
        ('pulse_75', True),
    ],
)
def test_saw_square_and_pulses_are_flagged_for_polyblep(name, is_polyblep):
    """Saw square and pulses are flagged for polyblep."""
    assert Wave(name).is_built_in_polyblep is is_polyblep


def test_derived_waves_are_not_polyblep_and_have_no_name():
    """Derived waves are not polyblep and have no name."""
    mixed = Wave.mix(square=1.0, saw=1.0)
    assert mixed.is_built_in_polyblep is False
    assert mixed.name is None
    assert Wave('sine').name == 'sine'


@pytest.mark.parametrize(
    ('arguments', 'match'),
    [
        ({'name': 'nonsense'}, 'unknown wave'),
        ({'name': 'square', 'duty': 0.3}, 'only applies to the pulse'),
        ({'name': 'pulse', 'duty': 0.001}, 'duty must be between'),
        ({'name': 'pulse', 'duty': 0.995}, 'duty must be between'),
    ],
)
def test_bad_built_in_waves_are_refused(arguments, match):
    """Bad built in waves are refused."""
    with pytest.raises(ValueError, match=match):
        Wave(**arguments)


def test_mix_by_name_normalizes_weights():
    """Mix by name normalizes weights."""
    mixed = Wave.mix(square=1.0, triangle=1.0).table()
    expected = 0.5 * Wave('square').table() + 0.5 * Wave('triangle').table()
    np.testing.assert_allclose(mixed, expected / np.max(np.abs(expected)), atol=1e-9)


@pytest.mark.parametrize(
    ('weights', 'match'),
    [({}, 'at least one'), ({'sine': -1.0}, 'negative'), ({'sine': 0.0}, 'all be zero')],
)
def test_bad_mix_weights_are_refused(weights, match):
    """Bad mix weights are refused."""
    with pytest.raises(ValueError, match=match):
        Wave.mix(**weights)


def test_blend_is_a_crossfade_toward_the_other_wave():
    """Blend is a crossfade toward the other wave."""
    np.testing.assert_allclose(
        Wave('saw').blend('sine', amount=1.0).table(), Wave('sine').table(), atol=1e-9
    )


def test_blend_of_zero_is_the_same_wave_and_accepts_a_wave():
    """Blend of zero is the same wave and accepts a wave."""
    saw = Wave('saw')
    assert saw.blend(Wave('sine'), amount=0.0) == saw


def test_blend_amount_outside_zero_to_one_is_refused():
    """Blend amount outside zero to one is refused."""
    with pytest.raises(ValueError, match='amount must be between 0 and 1'):
        Wave('saw').blend('sine', amount=1.5)


def test_harmonics_by_musical_name_set_the_spectrum():
    """Harmonics by musical name set the spectrum."""
    table = Wave.from_harmonics(Harmonics(fundamental=1.0, octave=0.5, two_octaves=0.25)).table()
    magnitudes = np.abs(np.fft.rfft(table))[1:5]
    ratios_db = 20 * np.log10(magnitudes / magnitudes[0] + 1e-30)
    assert ratios_db[1] == pytest.approx(20 * np.log10(0.5), abs=0.1)
    assert ratios_db[3] == pytest.approx(20 * np.log10(0.25), abs=0.1)
    assert np.max(np.abs(table)) == pytest.approx(1.0)


def test_higher_numbered_harmonics_land_on_their_bins():
    """Higher numbered harmonics land on their bins."""
    table = Wave.from_harmonics(Harmonics(fundamental=0.0, harmonic_32=1.0)).table()
    assert np.argmax(np.abs(np.fft.rfft(table))) == 32


def test_sub_octave_makes_the_cycle_one_period_of_the_lowest_tone():
    """Sub octave makes the cycle one period of the lowest tone."""
    table = Wave.from_harmonics(Harmonics(sub_octave=1.0, fundamental=0.5)).table()
    magnitudes = np.abs(np.fft.rfft(table))
    assert np.argmax(magnitudes) == 1
    assert magnitudes[2] / magnitudes[1] == pytest.approx(0.5, abs=1e-6)
    other_bins = np.delete(magnitudes, [1, 2])
    assert np.max(other_bins) < 1e-9 * magnitudes[1]


def test_fifth_sits_at_bin_three_when_the_cycle_is_halved():
    """Fifth sits at bin three when the cycle is halved."""
    table = Wave.from_harmonics(Harmonics(fifth=1.0, fundamental=1.0)).table()
    magnitudes = np.abs(np.fft.rfft(table))
    assert {int(index) for index in np.argsort(magnitudes)[-2:]} == {2, 3}


def test_all_zero_or_negative_harmonics_are_refused():
    """All zero or negative harmonics are refused."""
    with pytest.raises(ValueError, match='no variation'):
        Wave.from_harmonics(Harmonics(fundamental=0.0))
    with pytest.raises(ValueError, match='negative'):
        Wave.from_harmonics(Harmonics(octave=-0.5))


def test_drawbars_read_nine_digits():
    """Drawbars read nine digits."""
    assert Harmonics.drawbars('008000000') == Harmonics(fundamental=1.0)


def test_drawbars_map_each_digit_to_its_harmonic():
    """Drawbars map each digit to its harmonic."""
    harmonics = Harmonics.drawbars('876543210')
    assert harmonics.levels_by_harmonic() == {
        0.5: 1.0,
        1.5: 7 / 8,
        1.0: 6 / 8,
        2.0: 5 / 8,
        3.0: 4 / 8,
        4.0: 3 / 8,
        5.0: 2 / 8,
        6.0: 1 / 8,
    } | {1.5: 7 / 8}
    assert harmonics.harmonic_8 == 0.0


@pytest.mark.parametrize('setting', ['00800000', '0080000000', '009000000', '00800000x', ''])
def test_malformed_drawbars_are_refused(setting):
    """Malformed drawbars are refused."""
    with pytest.raises(ValueError, match='drawbars need'):
        Harmonics.drawbars(setting)


def test_points_reproduce_and_lose_their_dc():
    """Points reproduce and lose their dc."""
    wave = Wave.from_points((
        WavePoint(at=CYCLE.START, level=LEVEL.CENTER),
        WavePoint(at=CYCLE.QUARTER, level=LEVEL.TOP),
        WavePoint(at=CYCLE.THREE_QUARTERS, level=LEVEL.BOTTOM),
        WavePoint(at=CYCLE.END, level=LEVEL.CENTER),
    ))
    table = wave.table()
    assert abs(table.mean()) < 1e-9
    assert np.max(np.abs(table)) == pytest.approx(1.0)
    assert table[WAVE_TABLE_LENGTH // 4] == pytest.approx(1.0)


def test_unnormalized_points_keep_their_scale():
    """Unnormalized points keep their scale."""
    wave = Wave.from_points(
        (WavePoint(at=0.0, level=0.0), WavePoint(at=0.5, level=0.2), WavePoint(at=1.0, level=0.0)),
        normalize=False,
    )
    assert np.max(np.abs(wave.table())) < 0.2


def test_smooth_points_never_overshoot_between_points():
    """Smooth points never overshoot between points."""
    wave = Wave.from_points(GHOST_POINTS, shape='smooth', normalize=False)
    raw_levels = [point.level for point in GHOST_POINTS]
    table = wave.table()
    # DC removal shifts the whole wave; compare the spread, which it leaves alone
    assert np.max(table) - np.min(table) <= max(raw_levels) - min(raw_levels) + 1e-9


def test_smooth_points_pass_through_their_points():
    """Smooth points pass through their points."""
    points = (
        WavePoint(at=0.0, level=-1.0),
        WavePoint(at=0.5, level=1.0),
        WavePoint(at=0.75, level=1.0),
        WavePoint(at=1.0, level=-1.0),
    )
    table = Wave.from_points(points, shape='smooth', normalize=False).table()
    shifted = table - table[0]
    assert shifted[WAVE_TABLE_LENGTH // 2] == pytest.approx(2.0)
    assert np.max(shifted) == pytest.approx(2.0)  # the flat top holds, no overshoot


def test_smooth_points_with_steep_neighbours_are_limited():
    """Smooth points with steep neighbours are limited."""
    points = (
        WavePoint(at=0.0, level=0.0),
        WavePoint(at=0.01, level=0.9),
        WavePoint(at=0.5, level=1.0),
        WavePoint(at=1.0, level=0.0),
    )
    table = Wave.from_points(points, shape='smooth', normalize=False).table()
    assert np.max(table) - np.min(table) <= 1.0 + 1e-9


def test_step_points_hold_each_level_until_the_next_point():
    """Step points hold each level until the next point."""
    wave = Wave.from_points(
        (
            WavePoint(at=0.0, level=1.0),
            WavePoint(at=0.5, level=-1.0),
            WavePoint(at=1.0, level=-1.0),
        ),
        shape='steps',
    )
    table = wave.table()
    assert table[0] > 0 > table[-1]
    assert np.mean(table > 0) == pytest.approx(0.5)


def test_a_flat_wave_is_refused():
    """A flat wave is refused."""
    with pytest.raises(ValueError, match='no variation'):
        Wave.from_points((WavePoint(at=0.0, level=0.5), WavePoint(at=1.0, level=0.5)))


@pytest.mark.parametrize(
    ('points', 'shape', 'match'),
    [
        ((WavePoint(at=0.0, level=0.5),), 'linear', 'at least two'),
        ((WavePoint(at=0.0, level=0.5), WavePoint(at=1.0, level=0.0)), 'wobbly', 'shape must be'),
        ((WavePoint(at=0.1, level=0.5), WavePoint(at=1.0, level=0.0)), 'linear', 'start at'),
        ((WavePoint(at=0.0, level=0.5), WavePoint(at=0.9, level=0.0)), 'linear', 'end at'),
        (
            (
                WavePoint(at=0.0, level=0.5),
                WavePoint(at=0.5, level=0.0),
                WavePoint(at=0.5, level=0.2),
                WavePoint(at=1.0, level=0.0),
            ),
            'linear',
            'strictly increase',
        ),
        ((WavePoint(at=0.0, level=2.0), WavePoint(at=1.0, level=0.0)), 'linear', 'between -1'),
    ],
)
def test_bad_points_are_refused(points, shape, match):
    """Bad points are refused."""
    with pytest.raises(ValueError, match=match):
        Wave.from_points(points, shape=shape)


def test_waves_are_immutable_and_hashable_by_their_table():
    """Waves are immutable and hashable by their table."""
    first = Wave.mix(sine=1.0, triangle=1.0)
    second = Wave.mix(sine=2.0, triangle=2.0)
    assert first == second
    assert hash(first) == hash(second)
    assert first != Wave('sine')
    assert first != 'not a wave'
    assert len({first, second, Wave('sine')}) == 2
    with pytest.raises(ValueError, match='read-only'):
        first.table()[0] = 0.5
    assert repr(Wave('sine')) == "Wave('sine')"
    assert repr(first) == "Wave('custom')"


def test_registered_waves_mix_like_built_ins_and_built_in_names_are_reserved():
    """Registered waves mix like built ins and built in names are reserved."""
    registry = WaveRegistry()
    registry.register('ghost', Wave.from_points(GHOST_POINTS, shape='smooth'))
    assert registry['ghost'].table().shape == (WAVE_TABLE_LENGTH,)
    with pytest.raises(ValueError, match='built-in'):
        registry.register('square', Wave('sine'))


def test_registry_mixes_registered_and_built_in_waves():
    """Registry mixes registered and built in waves."""
    registry = WaveRegistry()
    ghost = Wave.from_points(GHOST_POINTS, shape='smooth')
    registry.register('ghost', ghost)
    mixed = registry.mix(ghost=0.5, square=0.5)
    expected = 0.5 * ghost.table() + 0.5 * Wave('square').table()
    np.testing.assert_allclose(mixed.table(), expected / np.max(np.abs(expected)))


def test_registry_lookup_contains_and_errors():
    """Registry lookup contains and errors."""
    registry = WaveRegistry()
    registry.register('ghost', Wave('sine'))
    assert registry['square'] == Wave('square')
    assert 'ghost' in registry
    assert 'square' in registry
    assert 'missing' not in registry
    with pytest.raises(KeyError, match='no wave named'):
        registry['missing']
    with pytest.raises(ValueError, match='cannot be empty'):
        registry.register('', Wave('sine'))
