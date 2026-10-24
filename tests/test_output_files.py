"""Tests for the output-file checks and writes (glitchygames/output_files.py).

The engine-level refusals (an unwritable --record-trace, --rebaseline or --replay-digest file)
are tested through the engine in tests/world/test_gameplay_recording.py and
tests/world/test_gameplay_replay.py; these tests pin the helper's own file handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from glitchygames.output_files import output_refusal

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
