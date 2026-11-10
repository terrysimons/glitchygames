"""Tests for the bus tree: default buses, reservations, gains, mute and solo (impl spec 7.4)."""

import math

import pytest

from glitchygames.audio.buses import DEFAULT_BUS_NAMES, MASTER_BUS, BusTree


def test_the_default_buses_hang_under_master():
    """master, music, effects, ui, ambience and dialogue exist; every default hangs under master."""
    buses = BusTree()

    assert DEFAULT_BUS_NAMES == ('master', 'music', 'effects', 'ui', 'ambience', 'dialogue')
    assert buses[MASTER_BUS].parent is None
    for name in DEFAULT_BUS_NAMES[1:]:
        assert buses[name].name == name
        assert buses[name].parent == MASTER_BUS


def test_ui_and_music_reserve_two_channels_each_and_the_rest_none():
    """The default reservations: ui 2, music 2 (feature spec 6.1)."""
    buses = BusTree()

    reservations = {name: buses[name].reserved_channels for name in DEFAULT_BUS_NAMES}

    assert reservations == {
        'master': 0,
        'music': 2,
        'effects': 0,
        'ui': 2,
        'ambience': 0,
        'dialogue': 0,
    }
    assert buses.names() == DEFAULT_BUS_NAMES


def test_the_effective_gain_is_the_product_of_the_volumes_along_the_path():
    """A custom bus under effects multiplies its volume by effects' and master's."""
    buses = BusTree()
    buses.add('footsteps', parent='effects', volume=0.5)
    buses['effects'].volume = 0.8
    buses['master'].volume = 0.5

    assert math.isclose(buses['footsteps'].effective_gain(), 0.5 * 0.8 * 0.5)
    assert math.isclose(buses['effects'].effective_gain(), 0.8 * 0.5)
    assert math.isclose(buses['ui'].effective_gain(), 0.5)


def test_mute_silences_the_bus_and_its_subtree_only():
    """A muted bus and its children have gain 0; its siblings keep theirs."""
    buses = BusTree()
    buses.add('footsteps', parent='effects')
    buses['effects'].mute = True

    assert buses['effects'].effective_gain() == 0.0
    assert buses['footsteps'].effective_gain() == 0.0
    assert buses['music'].effective_gain() == 1.0

    buses['effects'].mute = False

    assert buses['footsteps'].effective_gain() == 1.0


def test_solo_mutes_non_soloed_siblings():
    """Soloing music mutes the other buses under master (and their children), not music's own."""
    buses = BusTree()
    buses.add('footsteps', parent='effects')
    buses.add('drums', parent='music', volume=0.5)
    buses['music'].solo = True

    assert buses['music'].effective_gain() == 1.0
    assert buses['drums'].effective_gain() == 0.5
    assert buses['effects'].effective_gain() == 0.0
    assert buses['footsteps'].effective_gain() == 0.0
    assert buses['ui'].effective_gain() == 0.0
    assert buses['master'].effective_gain() == 1.0


def test_solo_applies_at_every_level_of_the_tree():
    """A soloed child mutes its own siblings; two soloed siblings both play."""
    buses = BusTree()
    buses.add('footsteps', parent='effects')
    buses.add('explosions', parent='effects')
    buses['footsteps'].solo = True

    assert buses['explosions'].effective_gain() == 0.0
    assert buses['footsteps'].effective_gain() == 1.0
    assert buses['ui'].effective_gain() == 1.0

    buses['explosions'].solo = True

    assert buses['explosions'].effective_gain() == 1.0


def test_every_change_moves_the_revision():
    """Volume, mute, solo and add each change the revision, so playing voices re-apply gains."""
    buses = BusTree()
    revisions = [buses.revision]

    buses['effects'].volume = 0.5
    revisions.append(buses.revision)
    buses['effects'].mute = True
    revisions.append(buses.revision)
    buses['effects'].solo = True
    revisions.append(buses.revision)
    buses.add('footsteps', parent='effects')
    revisions.append(buses.revision)

    assert len(set(revisions)) == len(revisions)


def test_setting_the_same_value_keeps_the_revision():
    """Re-setting an unchanged value does not make the voice table re-apply gains."""
    buses = BusTree()
    revision = buses.revision

    buses['effects'].volume = 1.0
    buses['effects'].mute = False
    buses['effects'].solo = False

    assert buses.revision == revision


def test_an_unknown_bus_is_a_key_error_naming_the_buses():
    """Looking up or parenting to a missing bus raises KeyError naming the known buses."""
    buses = BusTree()

    with pytest.raises(KeyError, match='effects'):
        buses['sfx']
    with pytest.raises(KeyError, match="'sfx'"):
        buses.add('footsteps', parent='sfx')


def test_adding_a_bus_twice_is_refused():
    """A bus name is unique in the tree."""
    buses = BusTree()

    with pytest.raises(ValueError, match="'music' already exists"):
        buses.add('music')


@pytest.mark.parametrize('volume', [-0.1, 1.5, math.nan])
def test_a_volume_outside_zero_to_one_is_refused(volume):
    """Bus volumes run 0-1, on add and on assignment."""
    buses = BusTree()

    with pytest.raises(ValueError, match='volume'):
        buses.add('footsteps', volume=volume)
    with pytest.raises(ValueError, match='volume'):
        buses['effects'].volume = volume


def test_a_negative_reservation_is_refused():
    """reserved_channels is a count of channels."""
    buses = BusTree()

    with pytest.raises(ValueError, match='reserved_channels'):
        buses.add('footsteps', reserved_channels=-1)


def test_an_added_bus_keeps_its_reservation():
    """A custom bus may reserve channels too."""
    buses = BusTree()

    bus = buses.add('dialogue_lines', parent='dialogue', reserved_channels=1)

    assert bus is buses['dialogue_lines']
    assert bus.reserved_channels == 1
    assert bus.parent == 'dialogue'
