"""Tests for atomic write safety in SaveManager."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

import pytest

from glitchygames.state.manager import DiskSaveManager


class TestAtomicWrites:
    """Tests for atomic write behavior."""

    def test_save_file_is_complete(self, tmp_path: Path) -> None:
        """Saved files contain complete, valid data."""
        import json

        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})

        # Read the raw file and verify it's valid JSON
        content = (tmp_path / 'slot_1.json').read_text(encoding='utf-8')
        envelope = json.loads(content)
        assert envelope['data'] == {'score': 100}

    def test_save_file_has_the_os_line_ends(self, tmp_path: Path) -> None:
        """A save is written in text mode: CRLF on Windows, LF elsewhere (the owner, 2026-11-22)."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100, 'name': 'café'})

        raw = (tmp_path / 'slot_1.json').read_bytes()
        text = raw.decode('utf-8').replace('\r\n', '\n')
        assert '\n' in text
        assert raw == text.replace('\n', os.linesep).encode('utf-8')

    @pytest.mark.parametrize('line_end', ['\n', '\r\n', '\r'], ids=['lf', 'crlf', 'lone-cr'])
    def test_a_slots_size_is_its_text_as_read_whatever_the_line_ends(
        self, tmp_path: Path, line_end: str
    ) -> None:
        """The size counts the save's text read with LF, as the replay sandbox counts it.

        So a slot lists at the same size live and in a replay, on Windows (CRLF on disk) as on
        a Mac, and a save moved between them lists as it did.
        """
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        path = saves.save('slot_1', {'score': 100, 'name': 'café'})
        text = path.read_bytes().decode('utf-8').replace('\r\n', '\n')
        path.write_bytes(text.replace('\n', line_end).encode('utf-8'))

        assert saves.list_slots()[0].size_bytes == len(text.encode('utf-8'))

    def test_no_temp_files_left_on_success(self, tmp_path: Path) -> None:
        """No .tmp files remain after a successful save."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})

        tmp_files = list(tmp_path.glob('*.tmp'))
        assert tmp_files == []

    def test_original_preserved_on_write_failure(self, tmp_path: Path, mocker) -> None:
        """If the write fails, the original save file is not corrupted."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)

        # First, save valid data
        saves.save('slot_1', {'score': 100})

        # Now simulate a failure during the replace step
        mocker.patch.object(Path, 'replace', side_effect=OSError('disk full'))
        with contextlib.suppress(OSError):
            saves.save('slot_1', {'score': 999})

        # Original data should still be intact
        result = saves.load('slot_1')
        assert result == {'score': 100}

    def test_no_temp_files_left_on_failure(self, tmp_path: Path, mocker) -> None:
        """No .tmp files remain after a failed save."""
        saves = DiskSaveManager(app_name='test-game', save_dir=tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)

        mocker.patch.object(Path, 'replace', side_effect=OSError('disk full'))
        with contextlib.suppress(OSError):
            saves.save('slot_1', {'score': 100})

        tmp_files = list(tmp_path.glob('*.tmp'))
        assert tmp_files == []
