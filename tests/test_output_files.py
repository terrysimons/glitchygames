"""Tests for the output-file checks and writes (glitchygames/output_files.py).

The engine-level refusals (an unwritable --record-trace, --rebaseline or --replay-digest file)
are tested through the engine in tests/world/test_gameplay_recording.py and
tests/world/test_gameplay_replay.py; these tests pin the helper's own file handling.
"""

from __future__ import annotations

import contextlib
import os
from typing import TYPE_CHECKING

import pytest

from glitchygames.output_files import output_refusal, write_text_whole
from tests.interrupted_writes import cut_writes_short

if TYPE_CHECKING:
    from pathlib import Path


class TestOutputRefusal:
    """output_refusal checks a file can be written and leaves what it found as it was."""

    def test_a_new_file_is_writable_and_not_left_behind(self, tmp_path: Path) -> None:
        """A file the check created is removed again; the parent directories it made stay."""
        output_path = tmp_path / 'nested' / 'recording.jsonl.gz'

        assert output_refusal(path=output_path) is None
        assert not output_path.exists()
        assert output_path.parent.is_dir()

    def test_an_existing_file_is_writable_and_kept_unchanged(self, tmp_path: Path) -> None:
        """A file that was already there is not removed, and its contents are not touched."""
        output_path = tmp_path / 'recording.jsonl.gz'
        output_path.write_bytes(b'earlier contents')

        assert output_refusal(path=output_path) is None
        assert output_path.read_bytes() == b'earlier contents'

    def test_a_directory_is_refused(self, tmp_path: Path) -> None:
        """A directory cannot be an output file: the reason names the path."""
        assert output_refusal(path=tmp_path) == f'{tmp_path} is a directory'


class TestWriteTextWhole:
    """A durable file is replaced whole, synced to the disk, or left as it was."""

    TEXT = 'first line\nsecond line\n'

    def test_a_new_file_holds_the_text(self, tmp_path: Path) -> None:
        destination = tmp_path / 'record.txt'

        write_text_whole(destination=destination, text=self.TEXT)

        assert destination.read_text(encoding='utf-8') == self.TEXT

    def test_a_write_stopped_anywhere_leaves_the_old_text_or_the_new(
        self, mocker, tmp_path: Path
    ) -> None:
        for characters in range(len(self.TEXT) + 1):
            destination = tmp_path / f'{characters}' / 'record.txt'
            destination.parent.mkdir()
            destination.write_text('earlier\n', encoding='utf-8')
            with (
                contextlib.suppress(KeyboardInterrupt),
                cut_writes_short(mocker=mocker, characters=characters),
            ):
                write_text_whole(destination=destination, text=self.TEXT)

            assert destination.read_text(encoding='utf-8') in {'earlier\n', self.TEXT}
            assert [path.name for path in destination.parent.iterdir()] == ['record.txt']

    def test_the_text_is_synced_before_it_replaces_the_file(self, mocker, tmp_path: Path) -> None:
        """A power cut after the write keeps the text (a Pi's SD card, a laptop's battery)."""
        destination = tmp_path / 'record.txt'
        destination.write_text('earlier\n', encoding='utf-8')
        seen_at_sync: list[str] = []
        real_fsync = os.fsync

        def fsync_noting_the_destination(descriptor: int) -> None:
            seen_at_sync.append(destination.read_text(encoding='utf-8'))
            real_fsync(descriptor)

        mocker.patch.object(os, 'fsync', side_effect=fsync_noting_the_destination)

        write_text_whole(destination=destination, text=self.TEXT)

        assert seen_at_sync == ['earlier\n']
        assert destination.read_text(encoding='utf-8') == self.TEXT

    def test_a_directory_destination_raises_and_leaves_no_partial_file(
        self, tmp_path: Path
    ) -> None:
        destination = tmp_path / 'record'
        destination.mkdir()

        # The platform picks which: replacing a directory with a file is refused
        with pytest.raises((IsADirectoryError, PermissionError)):
            write_text_whole(destination=destination, text=self.TEXT)

        assert sorted(path.name for path in tmp_path.iterdir()) == ['record']
