"""Tests for atomic write safety in SaveManager."""

from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import patch

from glitchygames.state.manager import SaveManager


class TestAtomicWrites:
    """Tests for atomic write behavior."""

    def test_save_file_is_complete(self, tmp_path: Path) -> None:
        """Saved files contain complete, valid data."""
        import json

        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})

        # Read the raw file and verify it's valid JSON
        content = (tmp_path / 'slot_1.json').read_text(encoding='utf-8')
        envelope = json.loads(content)
        assert envelope['data'] == {'score': 100}

    def test_no_temp_files_left_on_success(self, tmp_path: Path) -> None:
        """No .tmp files remain after a successful save."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        saves.save('slot_1', {'score': 100})

        tmp_files = list(tmp_path.glob('*.tmp'))
        assert tmp_files == []

    def test_original_preserved_on_write_failure(self, tmp_path: Path) -> None:
        """If the write fails, the original save file is not corrupted."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)

        # First, save valid data
        saves.save('slot_1', {'score': 100})

        # Now simulate a failure during the replace step
        with (
            patch.object(Path, 'replace', side_effect=OSError('disk full')),
            contextlib.suppress(OSError),
        ):
            saves.save('slot_1', {'score': 999})

        # Original data should still be intact
        result = saves.load('slot_1')
        assert result == {'score': 100}

    def test_no_temp_files_left_on_failure(self, tmp_path: Path) -> None:
        """No .tmp files remain after a failed save."""
        saves = SaveManager(app_name='test-game', save_dir=tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)

        with (
            patch.object(Path, 'replace', side_effect=OSError('disk full')),
            contextlib.suppress(OSError),
        ):
            saves.save('slot_1', {'score': 100})

        tmp_files = list(tmp_path.glob('*.tmp'))
        assert tmp_files == []
