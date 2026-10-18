"""Tests for the SaveManager."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from glitchygames.state.exceptions import (
    SaveCorruptedError,
    SaveNotFoundError,
    SaveVersionError,
)
from glitchygames.state.manager import SAVE_FORMAT_VERSION, SaveManager
from glitchygames.state.serializers import TomlSerializer


class TestSaveAndLoad:
    """Tests for basic save/load operations."""

    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        """Data survives a save → load round trip."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        data = {'score': 100, 'level': 2}
        saves.save('slot_1', data)
        result = saves.load('slot_1')
        assert result == data

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        """Save creates the save directory if it doesn't exist."""
        save_dir = tmp_path / 'nested' / 'dir'
        saves = SaveManager(app_name='test-game', save_dir=save_dir)
        saves.save('slot_1', {'key': 'value'})
        assert save_dir.exists()

    def test_save_returns_path(self, tmp_path: Path) -> None:
        """Save returns the path to the written file."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        path = saves.save('slot_1', {'key': 'value'})
        assert path.exists()
        assert path.name == 'slot_1.json'

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        """Saving to the same slot overwrites the previous data."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        saves.save('slot_1', {'score': 200})
        result = saves.load('slot_1')
        assert result == {'score': 200}

    def test_load_nested_data(self, tmp_path: Path) -> None:
        """Complex nested data survives a round trip."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
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
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        with pytest.raises(SaveNotFoundError) as exc_info:
            saves.load('nonexistent')
        assert exc_info.value.slot_name == 'nonexistent'

    def test_load_corrupted_json_raises(self, tmp_path: Path) -> None:
        """Loading a file with invalid JSON raises SaveCorruptedError."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        corrupt_file = tmp_path / 'bad_save.json'
        corrupt_file.write_text('{{{{not valid json}}}', encoding='utf-8')
        with pytest.raises(SaveCorruptedError) as exc_info:
            saves.load('bad_save')
        assert exc_info.value.path == corrupt_file

    def test_load_missing_metadata_raises(self, tmp_path: Path) -> None:
        """Loading a file without _meta raises SaveCorruptedError."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        no_meta_file = tmp_path / 'no_meta.json'
        no_meta_file.write_text('{"data": {"score": 100}}', encoding='utf-8')
        with pytest.raises(SaveCorruptedError, match='missing metadata'):
            saves.load('no_meta')

    def test_load_missing_data_raises(self, tmp_path: Path) -> None:
        """Loading a file without data section raises SaveCorruptedError."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
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
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
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


class TestLoadRaw:
    """Tests for load_raw() which returns the full envelope."""

    def test_load_raw_includes_metadata(self, tmp_path: Path) -> None:
        """load_raw() returns both _meta and data."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        raw = saves.load_raw('slot_1')
        assert '_meta' in raw
        assert 'data' in raw
        assert raw['data'] == {'score': 100}

    def test_load_raw_metadata_fields(self, tmp_path: Path) -> None:
        """Metadata contains expected fields."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        raw = saves.load_raw('slot_1')
        meta = raw['_meta']
        assert meta['version'] == SAVE_FORMAT_VERSION
        assert meta['app_name'] == 'test-game'
        assert 'timestamp' in meta
        assert 'engine_version' in meta

    def test_load_raw_skips_version_check(self, tmp_path: Path) -> None:
        """load_raw() does not raise on version mismatch."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        import json

        old_save = tmp_path / 'old.json'
        envelope = {
            '_meta': {'version': 999, 'timestamp': '', 'app_name': 'test'},
            'data': {'legacy': True},
        }
        old_save.write_text(json.dumps(envelope), encoding='utf-8')
        raw = saves.load_raw('old')
        assert raw['data'] == {'legacy': True}


class TestExistsAndDelete:
    """Tests for exists() and delete() operations."""

    def test_exists_true_after_save(self, tmp_path: Path) -> None:
        """exists() returns True for a saved slot."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        assert saves.exists('slot_1') is True

    def test_exists_false_for_missing(self, tmp_path: Path) -> None:
        """exists() returns False for a non-existent slot."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        assert saves.exists('nonexistent') is False

    def test_delete_removes_file(self, tmp_path: Path) -> None:
        """delete() removes the save file."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        saves.delete('slot_1')
        assert saves.exists('slot_1') is False

    def test_delete_missing_raises(self, tmp_path: Path) -> None:
        """delete() raises SaveNotFoundError for missing slot."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        with pytest.raises(SaveNotFoundError):
            saves.delete('nonexistent')


class TestListSlots:
    """Tests for list_slots()."""

    def test_empty_directory(self, tmp_path: Path) -> None:
        """list_slots() returns empty list for empty directory."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        assert saves.list_slots() == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """list_slots() returns empty list for non-existent directory."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path / 'nope')
        assert saves.list_slots() == []

    def test_lists_saved_slots(self, tmp_path: Path) -> None:
        """list_slots() includes all saved slots."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        saves.save('slot_2', {'score': 200})
        slots = saves.list_slots()
        slot_names = {slot.name for slot in slots}
        assert slot_names == {'slot_1', 'slot_2'}

    def test_slot_info_fields(self, tmp_path: Path) -> None:
        """SaveSlotInfo contains correct metadata."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
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
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})
        # Create a non-save file
        (tmp_path / 'readme.txt').write_text('not a save', encoding='utf-8')
        slots = saves.list_slots()
        assert len(slots) == 1


class TestTomlSerializer:
    """Tests for saving with TOML serializer."""

    def test_save_and_load_toml(self, tmp_path: Path) -> None:
        """TOML serializer works for save/load round trip."""
        toml_serializer = TomlSerializer()
        saves = SaveManager(
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
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
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
