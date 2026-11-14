"""Tests for scripts/instrument_audit_pages_manifest.py: the manifest of the audit's saved pages.

Each test lays out a throwaway build/ with pages folders and an audit directory with a sheet:
which folders are read and in what order, each page's size, checksum and date, the source URLs a
batch page takes from its sheet row (and a page no row names, or a batch with no sheet), and the
file the command line writes.
"""

from __future__ import annotations

import csv
import hashlib
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from scripts import instrument_audit_pages_manifest
from scripts.instrument_audit_pages_manifest import (
    MANIFEST_COLUMNS,
    main,
    manifest_rows,
    pages_folders,
)

from glitchygames.exit_codes import ExitCode

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from pytest_mock import MockerFixture

RANGE_SOURCE = 'https://en.wikipedia.org/wiki/Kazoo'
SOUND_SOURCE = 'https://example.org/kazoo'


def make_folder(build: Path, folder: str, files: dict[str, bytes]) -> None:
    """Make a pages folder under build/ holding the given files."""
    directory = build / folder
    directory.mkdir(parents=True)
    for file_name, content in files.items():
        (directory / file_name).write_bytes(content)


def write_sheet(audit: Path, number: int, rows: list[dict[str, str]]) -> None:
    """Write a batch's sheet with the name and source columns."""
    audit.mkdir(parents=True, exist_ok=True)
    columns = ['name', 'range_source', 'sound_source', 'drone_source', 'footage_source']
    with (audit / f'batch-{number}.tsv').open('w', encoding='utf-8', newline='') as sheet_file:
        writer = csv.DictWriter(sheet_file, fieldnames=columns, delimiter='\t', restval='')
        writer.writeheader()
        writer.writerows(rows)


def test_the_pages_folders_are_build_pages_then_each_batch_in_batch_order(tmp_path: Path):
    """build/pages comes first, batch-2-pages before batch-10-pages; other folders are left out."""
    for folder in ('batch-10-pages', 'pages', 'batch-2-pages', 'pipes', 'batch-3-notes'):
        (tmp_path / folder).mkdir()
    (tmp_path / 'batch-4-pages').write_text('a file, not a folder', encoding='utf-8')

    assert [folder.name for folder in pages_folders(tmp_path)] == [
        'pages',
        'batch-2-pages',
        'batch-10-pages',
    ]


def test_each_page_is_listed_with_its_size_checksum_and_date(tmp_path: Path):
    """A page's bytes, SHA-256 and last-written UTC date are its row's; dot files are skipped."""
    build = tmp_path / 'build'
    content = b'A kazoo is a membranophone.'
    make_folder(build, 'pages', {'Kazoo.txt': content, '.DS_Store': b'x'})
    written = datetime(2026, 11, 12, 23, 30, tzinfo=UTC).timestamp()
    os.utime(build / 'pages' / 'Kazoo.txt', (written, written))

    rows = manifest_rows(build, tmp_path / 'audit')

    assert [row.model_dump() for row in rows] == [
        {
            'folder': 'pages',
            'file': 'Kazoo.txt',
            'bytes': len(content),
            'sha256': hashlib.sha256(content).hexdigest(),
            'modified_utc': '2026-11-12',
            'sources': '',
        },
    ]


def test_a_batch_page_takes_its_rows_distinct_sources_in_column_order(tmp_path: Path):
    """A page named for a row lists that row's URLs once each; a non-URL cell is left out.

    The image of a saved PDF's page (``--4-page-5.png``) is its row's too, and a page no row
    names (a reference page) has no sources.
    """
    build = tmp_path / 'build'
    audit = tmp_path / 'audit'
    make_folder(
        build,
        'batch-20-pages',
        {
            'tin-kazoo--1.txt': b'page',
            'tin-kazoo--4-page-5.png': b'image',
            'hornbostel-sachs-aerophones--1.txt': b'reference',
        },
    )
    write_sheet(
        audit,
        20,
        [
            {
                'name': 'tin kazoo',
                'range_source': RANGE_SOURCE,
                'sound_source': SOUND_SOURCE,
                'drone_source': RANGE_SOURCE,
                'footage_source': 'none',
            },
        ],
    )

    sources = {row.file: row.sources for row in manifest_rows(build, audit)}

    assert sources == {
        'hornbostel-sachs-aerophones--1.txt': '',
        'tin-kazoo--1.txt': f'{RANGE_SOURCE} {SOUND_SOURCE}',
        'tin-kazoo--4-page-5.png': f'{RANGE_SOURCE} {SOUND_SOURCE}',
    }


def test_a_batch_with_no_sheet_lists_its_pages_without_sources(tmp_path: Path):
    """A batch-N-pages folder whose batch-N.tsv is missing is still listed."""
    build = tmp_path / 'build'
    make_folder(build, 'batch-21-pages', {'kazoo--1.txt': b'page'})

    rows = manifest_rows(build, tmp_path / 'audit')

    assert [(row.folder, row.file, row.sources) for row in rows] == [
        ('batch-21-pages', 'kazoo--1.txt', ''),
    ]


def test_main_writes_the_manifest_with_its_header(
    tmp_path: Path,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
):
    """The command line writes a tab-separated manifest, header first, and says how many pages."""
    build = tmp_path / 'build'
    audit = tmp_path / 'audit'
    make_folder(build, 'batch-20-pages', {'kazoo--1.txt': b'page'})
    write_sheet(audit, 20, [{'name': 'kazoo', 'range_source': RANGE_SOURCE}])
    mocker.patch.object(instrument_audit_pages_manifest, 'AUDIT_DIRECTORY', audit)
    output = tmp_path / 'saved-pages.tsv'

    status = main(['--build', str(build), '--output', str(output)])

    assert status == ExitCode.SUCCESS
    lines = output.read_text(encoding='utf-8').splitlines()
    assert lines[0].split('\t') == list(MANIFEST_COLUMNS)
    assert lines[1].split('\t')[:3] == ['batch-20-pages', 'kazoo--1.txt', '4']
    assert lines[1].split('\t')[-1] == RANGE_SOURCE
    assert len(lines) == 1 + 1
    assert capsys.readouterr().out == f'1 pages in {output}\n'
