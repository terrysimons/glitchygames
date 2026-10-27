"""scripts/import_published_ledger.py: the published history moves into the repository's rows."""

from __future__ import annotations

from scripts.import_published_ledger import import_published_ledger

from glitchygames.recording_metrics import ledger_text, read_row_files
from tests.ledger_repositories import clone_with_published_ledger
from tests.test_recording_metrics import ledger_row


def test_every_published_row_becomes_a_row_file_once(tmp_path):
    """Each row once: an import run again adds nothing."""
    rows = [
        ledger_row(measured_at='2026-10-22T21:00:00+00:00'),
        ledger_row(measured_at='2026-10-23T21:00:00+00:00'),
    ]
    clone = clone_with_published_ledger(tmp_path=tmp_path, ledger=ledger_text(rows=rows))
    rows_directory = tmp_path / 'replay-ledger'

    written = import_published_ledger(project_root=clone, rows_directory=rows_directory)
    again = import_published_ledger(project_root=clone, rows_directory=rows_directory)

    assert len(written) == len(rows)
    assert again == []
    assert read_row_files(directory=rows_directory) == rows


def test_an_empty_publication_imports_nothing(tmp_path):
    """Nothing published yet: no files."""
    clone = clone_with_published_ledger(tmp_path=tmp_path, ledger='')

    assert import_published_ledger(project_root=clone, rows_directory=tmp_path / 'rows') == []
