"""Tests for the SaveManager."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from glitchygames.live_sources import LiveSources
from glitchygames.state.exceptions import (
    SaveCorruptedError,
    SaveNotFoundError,
    SaveVersionError,
)
from glitchygames.state.manager import (
    SAVE_FORMAT_VERSION,
    DiskSaveManager,
    observe_disk_save_changes,
    stop_observing_disk_save_changes,
)
from glitchygames.state.sandbox import MemorySaveManager
from glitchygames.state.serializers import TomlSerializer


class TestSaveAndLoad:
    """Tests for basic save/load operations."""

    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        """Data survives a save → load round trip."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        data = {'score': 100, 'level': 2}
        saves.save('slot_1', data)
        result = saves.load('slot_1')
        assert result == data

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        """Save creates the save directory if it doesn't exist."""
        save_dir = tmp_path / 'nested' / 'dir'
        saves = DiskSaveManager(app_name='test-game', save_dir=save_dir)
        saves.save('slot_1', {'key': 'value'})
        assert save_dir.exists()

    def test_save_returns_path(self, tmp_path: Path) -> None:
        """Save returns the path to the written file."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        path = saves.save('slot_1', {'key': 'value'})
        assert path.exists()
        assert path.name == 'slot_1.json'

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        """Saving to the same slot overwrites the previous data."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        saves.save('slot_1', {'score': 200})
        result = saves.load('slot_1')
        assert result == {'score': 200}

    def test_load_nested_data(self, tmp_path: Path) -> None:
        """Complex nested data survives a round trip."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        data = {
            'player': {'name': 'Hero', 'hp': 100, 'inventory': ['sword', 'potion']},
            'world': {'level': 3, 'seed': 42},
        }
        saves.save('progress', data)
        result = saves.load('progress')
        assert result == data


class TestLoadErrors:
    """Tests for error handling during load."""

    def test_load_missing_slot_raises(self, tmp_path: Path) -> None:
        """Loading a non-existent slot raises SaveNotFoundError."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        with pytest.raises(SaveNotFoundError) as exc_info:
            saves.load('nonexistent')
        assert exc_info.value.slot_name == 'nonexistent'

    def test_load_corrupted_json_raises(self, tmp_path: Path) -> None:
        """Loading a file with invalid JSON raises SaveCorruptedError."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        corrupt_file = tmp_path / 'bad_save.json'
        corrupt_file.write_text('{{{{not valid json}}}', encoding='utf-8')
        with pytest.raises(SaveCorruptedError) as exc_info:
            saves.load('bad_save')
        assert exc_info.value.path == corrupt_file

    def test_load_missing_metadata_raises(self, tmp_path: Path) -> None:
        """Loading a file without _meta raises SaveCorruptedError."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        no_meta_file = tmp_path / 'no_meta.json'
        no_meta_file.write_text('{"data": {"score": 100}}', encoding='utf-8')
        with pytest.raises(SaveCorruptedError, match='missing metadata'):
            saves.load('no_meta')

    def test_load_missing_data_raises(self, tmp_path: Path) -> None:
        """Loading a file without data section raises SaveCorruptedError."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        import json

        no_data_file = tmp_path / 'no_data.json'
        envelope = {
            '_meta': {'version': SAVE_FORMAT_VERSION, 'timestamp': '', 'app_name': 'test'},
        }
        no_data_file.write_text(json.dumps(envelope), encoding='utf-8')
        with pytest.raises(SaveCorruptedError, match='missing data'):
            saves.load('no_data')

    def test_load_wrong_version_raises(self, tmp_path: Path) -> None:
        """Loading a file with wrong version raises SaveVersionError."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        import json

        wrong_version_file = tmp_path / 'old_save.json'
        envelope = {
            '_meta': {'version': 999, 'timestamp': '', 'app_name': 'test'},
            'data': {'score': 100},
        }
        wrong_version_file.write_text(json.dumps(envelope), encoding='utf-8')
        with pytest.raises(SaveVersionError) as exc_info:
            saves.load('old_save')
        assert exc_info.value.file_version == 999
        assert exc_info.value.expected_version == SAVE_FORMAT_VERSION

    def test_load_non_numeric_version_raises(self, tmp_path: Path) -> None:
        """Loading a file whose metadata version is not a number raises SaveCorruptedError."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        (tmp_path / 'slot_1.json').write_text(
            '{"_meta": {"version": "x"}, "data": {}}', encoding='utf-8'
        )
        with pytest.raises(SaveCorruptedError, match='invalid version'):
            saves.load('slot_1')

    def test_a_file_that_cannot_be_read_is_not_reported_as_corrupt(
        self, tmp_path: Path, mocker
    ) -> None:
        """An OSError reading the file passes through: the save is unreadable, not corrupt."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        path_class = type(tmp_path)
        real_read_text = path_class.read_text

        def read_text_refusing_the_saves(path: Path, *args, **kwargs) -> str:
            # Only the save directory is unreadable. The patch is on the class, so refusing
            # every read also failed the memory guard's thread sampling /proc on Linux, an
            # error pytest then reported against the next test (BUGS.md #246)
            if path.is_relative_to(tmp_path):
                raise PermissionError(13, 'Permission denied')
            return real_read_text(path, *args, **kwargs)

        mocker.patch.object(
            path_class, 'read_text', autospec=True, side_effect=read_text_refusing_the_saves
        )

        with pytest.raises(PermissionError, match='Permission denied'):
            saves.load('slot_1')
        # list_slots skips the unreadable file instead of raising
        assert saves.list_slots() == []


class TestLoadRaw:
    """Tests for load_raw() which returns the full envelope."""

    def test_load_raw_includes_metadata(self, tmp_path: Path) -> None:
        """load_raw() returns both _meta and data."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        raw = saves.load_raw('slot_1')
        assert '_meta' in raw
        assert 'data' in raw
        assert raw['data'] == {'score': 100}

    def test_load_raw_metadata_fields(self, tmp_path: Path) -> None:
        """Metadata contains expected fields."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        raw = saves.load_raw('slot_1')
        meta = raw['_meta']
        assert meta['version'] == SAVE_FORMAT_VERSION
        assert meta['app_name'] == 'test-game'
        assert 'timestamp' in meta
        assert 'engine_version' in meta

    def test_save_timestamp_comes_from_the_wall_clock_door(self, tmp_path: Path, mocker) -> None:
        """The envelope's timestamp is glitchygames.clock.wall_clock_time(), so replays match."""
        recorded_now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
        mocker.patch.object(LiveSources, 'wall_clock_time', return_value=recorded_now)
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        assert saves.load_raw('slot_1')['_meta']['timestamp'] == recorded_now.isoformat()

    def test_load_raw_skips_version_check(self, tmp_path: Path) -> None:
        """load_raw() does not raise on version mismatch."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        import json

        old_save = tmp_path / 'old.json'
        envelope = {
            '_meta': {'version': 999, 'timestamp': '', 'app_name': 'test'},
            'data': {'legacy': True},
        }
        old_save.write_text(json.dumps(envelope), encoding='utf-8')
        raw = saves.load_raw('old')
        assert raw['data'] == {'legacy': True}


class TestSaveDirectory:
    """Where a DiskSaveManager keeps its files."""

    def test_an_explicit_save_directory_is_used(self, tmp_path: Path) -> None:
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        assert saves.save_dir == tmp_path
        assert saves.save('slot_1', {'score': 1}).parent == tmp_path

    def test_the_default_save_directory_is_the_platform_one(self, tmp_path: Path, mocker) -> None:
        """Without save_dir, the directory comes from get_save_directory(app_name)."""
        get_save_directory = mocker.patch(
            'glitchygames.state.manager.get_save_directory', return_value=tmp_path / 'platform'
        )
        saves = DiskSaveManager(app_name='test-game')
        assert saves.save_dir == tmp_path / 'platform'
        get_save_directory.assert_called_once_with('test-game')


class TestEngineVersion:
    """The engine version written into each save's metadata."""

    def test_an_uninstalled_engine_is_recorded_as_unknown(self, tmp_path: Path, mocker) -> None:
        """Running from a source tree with no installed package metadata: 'unknown'."""
        import importlib.metadata

        mocker.patch.object(
            importlib.metadata,
            'version',
            side_effect=importlib.metadata.PackageNotFoundError('glitchygames'),
        )
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 1})
        assert saves.load_raw('slot_1')['_meta']['engine_version'] == 'unknown'


class TestExistsAndDelete:
    """Tests for exists() and delete() operations."""

    def test_exists_true_after_save(self, tmp_path: Path) -> None:
        """exists() returns True for a saved slot."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        assert saves.exists('slot_1') is True

    def test_exists_false_for_missing(self, tmp_path: Path) -> None:
        """exists() returns False for a non-existent slot."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        assert saves.exists('nonexistent') is False

    def test_delete_removes_file(self, tmp_path: Path) -> None:
        """delete() removes the save file."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        saves.delete('slot_1')
        assert saves.exists('slot_1') is False

    def test_delete_missing_raises(self, tmp_path: Path) -> None:
        """delete() raises SaveNotFoundError for missing slot."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        with pytest.raises(SaveNotFoundError):
            saves.delete('nonexistent')


class TestListSlots:
    """Tests for list_slots()."""

    def test_empty_directory(self, tmp_path: Path) -> None:
        """list_slots() returns empty list for empty directory."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        assert saves.list_slots() == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """list_slots() returns empty list for non-existent directory."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path / 'nope')
        assert saves.list_slots() == []

    def test_lists_saved_slots(self, tmp_path: Path) -> None:
        """list_slots() includes all saved slots."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        saves.save('slot_2', {'score': 200})
        slots = saves.list_slots()
        slot_names = {slot.name for slot in slots}
        assert slot_names == {'slot_1', 'slot_2'}

    def test_slot_info_fields(self, tmp_path: Path) -> None:
        """SaveSlotInfo contains correct metadata."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('progress', {'score': 100})
        slots = saves.list_slots()
        assert len(slots) == 1
        slot = slots[0]
        assert slot.name == 'progress'
        assert slot.version == SAVE_FORMAT_VERSION
        assert slot.app_name == 'test-game'
        assert slot.size_bytes > 0
        assert slot.path.exists()

    def test_ignores_non_save_files(self, tmp_path: Path) -> None:
        """list_slots() ignores files without recognized extensions."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        # Create a non-save file
        (tmp_path / 'readme.txt').write_text('not a save', encoding='utf-8')
        slots = saves.list_slots()
        assert len(slots) == 1

    def test_skips_unparseable_files(self, tmp_path: Path) -> None:
        """list_slots() skips a file that is not valid JSON instead of raising."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        (tmp_path / 'broken.json').write_text('{{{{not valid json}}}', encoding='utf-8')
        assert [slot.name for slot in saves.list_slots()] == ['slot_1']
        assert saves.slot_names() == ['broken', 'slot_1']

    def test_skips_files_that_are_not_utf8(self, tmp_path: Path) -> None:
        """list_slots() skips a file that is not valid UTF-8 instead of raising."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        (tmp_path / 'stray.json').write_bytes(b'\xff\xfe{')
        assert [slot.name for slot in saves.list_slots()] == ['slot_1']

    def test_skips_files_whose_metadata_is_not_a_table(self, tmp_path: Path) -> None:
        """list_slots() skips a file whose metadata is not a mapping (here a list)."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        (tmp_path / 'stray.json').write_text('{"_meta": [1], "data": {}}', encoding='utf-8')
        assert [slot.name for slot in saves.list_slots()] == ['slot_1']

    def test_skips_files_with_a_non_numeric_version(self, tmp_path: Path) -> None:
        """list_slots() skips a file whose metadata version is not a number."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        (tmp_path / 'stray.json').write_text(
            '{"_meta": {"version": "x"}, "data": {}}', encoding='utf-8'
        )
        assert [slot.name for slot in saves.list_slots()] == ['slot_1']

    @pytest.mark.parametrize(
        ('file_name', 'content'),
        [
            ('stray.json', '{"_meta": {"version": Infinity}, "data": {}}'),
            ('stray.json', '{"_meta": {"version": 1e999}, "data": {}}'),
            ('stray.toml', '[_meta]\nversion = inf\n[data]\n'),
        ],
    )
    def test_skips_files_with_an_infinite_version(
        self, tmp_path: Path, file_name: str, content: str
    ) -> None:
        """list_slots() skips a file whose metadata version is infinite."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        (tmp_path / file_name).write_text(content, encoding='utf-8')
        assert [slot.name for slot in saves.list_slots()] == ['slot_1']

    def test_sorts_timestamps_with_and_without_a_time_zone(self, tmp_path: Path) -> None:
        """A timestamp without a time zone is sorted as UTC instead of raising TypeError."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        (tmp_path / 'old.json').write_text(
            '{"_meta": {"version": 1, "timestamp": "2000-01-01T00:00:00"}, "data": {}}',
            encoding='utf-8',
        )
        assert [slot.name for slot in saves.list_slots()] == ['slot_1', 'old']

    def test_slots_saved_at_the_same_time_are_listed_by_name(self, tmp_path: Path, mocker) -> None:
        """Ties are listed by name, whatever order the files are found in (replayable)."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        same_time = (
            '{"_meta": {"version": 1, "timestamp": "2026-10-19T12:00:00+00:00"}, "data": {}}'
        )
        for name in ('beta', 'gamma', 'alpha'):
            (tmp_path / f'{name}.json').write_text(same_time, encoding='utf-8')
        found_order = [tmp_path / 'gamma.json', tmp_path / 'alpha.json', tmp_path / 'beta.json']
        mocker.patch.object(saves, '_slot_file_paths', return_value=found_order)
        assert [slot.name for slot in saves.list_slots()] == ['alpha', 'beta', 'gamma']


class TestTomlSerializer:
    """Tests for saving with TOML serializer."""

    def test_save_and_load_toml(self, tmp_path: Path) -> None:
        """TOML serializer works for save/load round trip."""
        toml_serializer = TomlSerializer()
        saves = DiskSaveManager(
            app_name='test-game',
            save_dir=tmp_path,
            default_serializer=toml_serializer,
        )
        data = {'volume': 0.8, 'fullscreen': False}
        saves.save('settings', data)
        result = saves.load('settings')
        assert result == data

    def test_per_slot_serializer_override(self, tmp_path: Path) -> None:
        """Per-slot serializer override works."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        # Save game state with default JSON
        saves.save('progress', {'score': 100})
        # Save settings with TOML
        saves.save('settings', {'volume': 0.8}, serializer=TomlSerializer())

        # Both should load correctly
        assert saves.load('progress') == {'score': 100}
        assert saves.load('settings', serializer=TomlSerializer()) == {'volume': 0.8}

        # Verify file extensions
        assert (tmp_path / 'progress.json').exists()
        assert (tmp_path / 'settings.toml').exists()


class TestDiskSaveChangeObservers:
    """Observers hear of each save file a DiskSaveManager writes or deletes (a browser flushes)."""

    def test_a_write_and_a_delete_are_each_observed_after_they_happen(self, tmp_path):
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        observed: list[tuple[Path, bool]] = []

        def observer(path: Path) -> None:
            # Recorded with whether the file exists then: the change is complete when told
            observed.append((path, path.exists()))

        observe_disk_save_changes(observer=observer)
        try:
            saves.save('slot_1', {'score': 7})
            saves.delete('slot_1')
        finally:
            stop_observing_disk_save_changes(observer=observer)

        assert observed == [(tmp_path / 'slot_1.json', True), (tmp_path / 'slot_1.json', False)]

    def test_a_stopped_observer_is_not_told(self, tmp_path):
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        observed: list[Path] = []
        observe_disk_save_changes(observer=observed.append)
        stop_observing_disk_save_changes(observer=observed.append)

        saves.save('slot_1', {'score': 7})

        assert observed == []

    def test_stopping_an_observer_that_never_observed_does_nothing(self):
        stop_observing_disk_save_changes(observer=print)

    def test_memory_saves_are_never_observed(self):
        """A replay's stores (MemorySaveManager) never touch real storage, so never notify."""
        saves = MemorySaveManager(app_name='test-game', snapshot={})
        observed: list[Path] = []
        observe_disk_save_changes(observer=observed.append)
        try:
            saves.save('slot_1', {'score': 7})
        finally:
            stop_observing_disk_save_changes(observer=observed.append)

        assert observed == []
