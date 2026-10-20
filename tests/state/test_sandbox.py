"""The saves door (glitchygames/state/sandbox.py): live disk stores, replay memory stores."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from glitchygames.live_sources import LiveSources
from glitchygames.sources import install_sources
from glitchygames.state import (
    DiskSaveManager,
    MemorySaveManager,
    SaveError,
    SaveManager,
    SaveNotFoundError,
)
from glitchygames.state.manager import SAVE_FORMAT_VERSION
from glitchygames.state.sandbox import open_saves, save_namespace_snapshot
from glitchygames.state.serializers import TomlSerializer

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

SLOT_NAME = 'high_scores'
APP_NAME = 'demo'


def write_valid_slot(*, save_directory: Path) -> None:
    """Save a slot the normal way."""
    DiskSaveManager(app_name=APP_NAME, save_dir=save_directory).save(
        SLOT_NAME, {'scores': [{'score': 900}]}
    )


def write_old_version_slot(*, save_directory: Path) -> None:
    """Write a slot whose save format version this engine does not accept."""
    envelope = {
        '_meta': {'version': SAVE_FORMAT_VERSION + 1, 'timestamp': '2026-01-02T03:04:05+00:00'},
        'data': {'value': 1},
    }
    (save_directory / f'{SLOT_NAME}.json').write_text(json.dumps(envelope), encoding='utf-8')


def write_corrupt_slot(*, save_directory: Path) -> None:
    """Write a slot file that is not valid JSON."""
    (save_directory / f'{SLOT_NAME}.json').write_text('{{{{not valid json}}}', encoding='utf-8')


def write_no_slot(*, save_directory: Path) -> None:
    """Write nothing (the slot is missing)."""
    del save_directory


def write_slot_without_metadata(*, save_directory: Path) -> None:
    """Write a slot with data but no metadata (listed with the file time, unloadable)."""
    envelope = {'data': {'value': 1}}
    (save_directory / f'{SLOT_NAME}.json').write_text(json.dumps(envelope), encoding='utf-8')


def write_slot_without_data(*, save_directory: Path) -> None:
    """Write a slot with metadata but no data section."""
    envelope = {'_meta': {'version': SAVE_FORMAT_VERSION, 'timestamp': '2026-01-02T03:04:05'}}
    (save_directory / f'{SLOT_NAME}.json').write_text(json.dumps(envelope), encoding='utf-8')


def write_toml_slot(*, save_directory: Path) -> None:
    """Write a TOML slot, which a JSON store lists but cannot load."""
    DiskSaveManager(
        app_name=APP_NAME, save_dir=save_directory, default_serializer=TomlSerializer()
    ).save(SLOT_NAME, {'value': 1})


def write_non_object_slot(*, save_directory: Path) -> None:
    """Write a slot whose top-level JSON value is not an object."""
    (save_directory / f'{SLOT_NAME}.json').write_text('[1, 2, 3]', encoding='utf-8')


SLOT_WRITERS: dict[str, Callable[..., None]] = {
    'valid': write_valid_slot,
    'old_version': write_old_version_slot,
    'corrupt': write_corrupt_slot,
    'missing': write_no_slot,
    'missing_metadata': write_slot_without_metadata,
    'missing_data': write_slot_without_data,
    'toml_in_json_store': write_toml_slot,
    'non_object': write_non_object_slot,
}


def outcome_of(*, action: Callable[[], Any]) -> tuple[str, Any]:
    """Return what an action returned, or the type of what it raised.

    Returns:
        ``('returned', value)`` or ``('raised', exception type)``.

    """
    try:
        return ('returned', action())
    except (SaveError, OSError, TypeError, ValueError) as error:
        return ('raised', type(error))


def listing_of(*, saves: SaveManager) -> list[tuple[Any, ...]]:
    """Return what list_slots reports, without the path (a memory store has no files).

    Returns:
        One tuple per slot.

    """
    return [
        (slot.name, slot.timestamp, slot.version, slot.app_name, slot.size_bytes)
        for slot in saves.list_slots()
    ]


def stores_for(*, case: str, save_directory: Path) -> tuple[DiskSaveManager, MemorySaveManager]:
    """Return a disk store holding the case's slot and a memory store seeded from its snapshot.

    Returns:
        ``(disk, memory)``.

    """
    SLOT_WRITERS[case](save_directory=save_directory)
    disk = DiskSaveManager(app_name=APP_NAME, save_dir=save_directory)
    memory = MemorySaveManager(app_name=APP_NAME, snapshot=save_namespace_snapshot(saves=disk))
    return disk, memory


@pytest.mark.parametrize('case', sorted(SLOT_WRITERS))
def test_memory_store_answers_exactly_like_the_disk_store(case, tmp_path):
    """exists, load, load_raw, list_slots and delete give the same answers and exception types."""
    disk, memory = stores_for(case=case, save_directory=tmp_path)
    for saves_action in (
        lambda saves: saves.exists(SLOT_NAME),
        lambda saves: saves.load(SLOT_NAME),
        lambda saves: saves.load_raw(SLOT_NAME),
        lambda saves: listing_of(saves=saves),
        lambda saves: saves.slot_names(),
        lambda saves: saves.delete(SLOT_NAME),
        lambda saves: saves.exists(SLOT_NAME),
    ):
        disk_outcome = outcome_of(action=lambda action=saves_action: action(disk))
        memory_outcome = outcome_of(action=lambda action=saves_action: action(memory))
        assert memory_outcome == disk_outcome


@pytest.mark.parametrize('case', sorted(SLOT_WRITERS))
def test_snapshot_of_a_memory_store_round_trips(case, tmp_path):
    """Snapshotting the memory store gives back the snapshot it was seeded from."""
    disk, memory = stores_for(case=case, save_directory=tmp_path)
    assert save_namespace_snapshot(saves=memory) == save_namespace_snapshot(saves=disk)


def test_writes_answer_exactly_like_the_disk_store(tmp_path):
    """A write reads back through the serializer (tuples become lists) and lists the same size."""
    disk = DiskSaveManager(app_name=APP_NAME, save_dir=tmp_path)
    memory = MemorySaveManager(app_name=APP_NAME, snapshot={})
    for saves in (disk, memory):
        saves.save(SLOT_NAME, {'position': (1, 2), 'name': 'café'})
    assert memory.load(SLOT_NAME) == disk.load(SLOT_NAME) == {'position': [1, 2], 'name': 'café'}
    # Timestamps are the write times, so compare everything else
    assert [entry[:1] + entry[2:] for entry in listing_of(saves=memory)] == [
        entry[:1] + entry[2:] for entry in listing_of(saves=disk)
    ]


def test_unserializable_data_raises_the_same_error(tmp_path):
    """Data the serializer cannot write raises the same error in both stores."""
    disk = DiskSaveManager(app_name=APP_NAME, save_dir=tmp_path)
    memory = MemorySaveManager(app_name=APP_NAME, snapshot={})
    disk_outcome = outcome_of(action=lambda: disk.save(SLOT_NAME, {'value': object()}))
    assert disk_outcome == ('raised', TypeError)
    assert outcome_of(action=lambda: memory.save(SLOT_NAME, {'value': object()})) == disk_outcome


def test_memory_store_reads_the_snapshot_and_discards_writes(tmp_path):
    """A memory store reads its snapshot; its writes never reach the disk."""
    disk, memory = stores_for(case='valid', save_directory=tmp_path)
    memory.save(SLOT_NAME, {'scores': [{'score': 800}]})
    assert memory.load(SLOT_NAME) == {'scores': [{'score': 800}]}
    assert disk.load(SLOT_NAME) == {'scores': [{'score': 900}]}


def test_snapshot_holds_every_slot_envelope(tmp_path):
    """A snapshot of a disk store holds each slot's full envelope."""
    write_valid_slot(save_directory=tmp_path)
    snapshot = save_namespace_snapshot(saves=DiskSaveManager(app_name=APP_NAME, save_dir=tmp_path))
    assert snapshot[SLOT_NAME]['data'] == {'scores': [{'score': 900}]}


def test_snapshot_is_a_copy(tmp_path):
    """Changing a snapshot does not change the memory store it came from or seeded."""
    _disk, memory = stores_for(case='valid', save_directory=tmp_path)
    snapshot = save_namespace_snapshot(saves=memory)
    snapshot[SLOT_NAME]['data']['scores'] = []
    assert memory.load(SLOT_NAME) == {'scores': [{'score': 900}]}


def test_unreadable_slot_raises_the_same_error_in_replay(tmp_path, mocker):
    """A slot the disk could not read (permissions) raises OSError in the memory store too."""
    write_valid_slot(save_directory=tmp_path)
    disk = DiskSaveManager(app_name=APP_NAME, save_dir=tmp_path)
    mocker.patch.object(disk, 'load_raw', side_effect=PermissionError('permission denied'))
    memory = MemorySaveManager(app_name=APP_NAME, snapshot=save_namespace_snapshot(saves=disk))
    assert memory.exists(SLOT_NAME)
    with pytest.raises(OSError, match='permission denied'):
        memory.load(SLOT_NAME)


def test_memory_store_missing_slot_raises_like_the_disk_store():
    """Loading or deleting a missing slot raises SaveNotFoundError."""
    memory = MemorySaveManager(app_name=APP_NAME, snapshot={})
    with pytest.raises(SaveNotFoundError):
        memory.load(SLOT_NAME)
    with pytest.raises(SaveNotFoundError):
        memory.delete(SLOT_NAME)
    assert not memory.exists(SLOT_NAME)


def test_live_open_saves_is_a_disk_save_manager(tmp_path, mocker):
    """Live play opens a DiskSaveManager for the app name."""
    mocker.patch('glitchygames.state.manager.get_save_directory', return_value=tmp_path)
    saves = open_saves(app_name=APP_NAME)
    assert isinstance(saves, DiskSaveManager)
    assert saves.app_name == APP_NAME


def test_live_sources_remember_opened_namespaces(tmp_path, mocker):
    """LiveSources remembers each opened store by namespace (for recording)."""
    mocker.patch('glitchygames.state.manager.get_save_directory', return_value=tmp_path)
    sources = LiveSources(random_seed=1)
    install_sources(sources=sources)
    open_saves(app_name=APP_NAME)
    assert list(sources.opened_save_namespaces) == [APP_NAME]


def test_live_sources_return_the_already_opened_store(tmp_path, mocker):
    """Opening a namespace twice returns the same store."""
    mocker.patch('glitchygames.state.manager.get_save_directory', return_value=tmp_path)
    sources = LiveSources(random_seed=1)
    install_sources(sources=sources)
    assert open_saves(app_name=APP_NAME) is open_saves(app_name=APP_NAME)
