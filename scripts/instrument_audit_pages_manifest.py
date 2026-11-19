r"""Write the manifest of the source pages the instrument audit saved under build/.

The instrument catalog expansion's batches saved each audit row's sources as raw pages under
build/ (build/batch-N-pages/<name, spaces as hyphens>--<n>.txt, and before batch 11 the
unnumbered build/pages/<page title>.txt and .raw). The pages stay out of the repository: most are
other people's pages, not all openly licensed, and some held personal data that was redacted
(plans/future-features.md #87). The manifest is what the repository keeps instead: one line per
saved page with its size and SHA-256, so an archived copy can be shown to be the page the audit
read, and for a batch's page, the source URLs its sheet row gives
(plans/data/instrument-audit/batch-N.tsv).

Columns, tab-separated with a header row, sorted by folder then file:

  folder        The page's folder under build/ (``batch-19-pages``, ``pages``).
  file          The page's file name.
  bytes         Its size.
  sha256        Its SHA-256, in hex.
  modified_utc  The date it was last written (UTC): when it was saved, or redacted after.
  sources       Its row's source URLs, space-separated in the sheet's column order, for a
                batch's page whose sheet lists the row; empty otherwise.

Usage:
    uv run python -m scripts.instrument_audit_pages_manifest
    uv run python -m scripts.instrument_audit_pages_manifest --build build --output manifest.tsv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from glitchygames.exit_codes import ExitCode

if TYPE_CHECKING:
    from collections.abc import Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIRECTORY = PROJECT_ROOT / 'plans' / 'data' / 'instrument-audit'
MANIFEST = AUDIT_DIRECTORY / 'saved-pages.tsv'
# A batch's pages folder, and the folder the batches before 11 saved into
BATCH_PAGES_FOLDER = re.compile(r'batch-([0-9]+)-pages')
UNNUMBERED_PAGES_FOLDER = 'pages'
# A batch page's file name: the row's name with its spaces as hyphens, then --<n>, and for an
# image of one of a saved PDF's pages, -page-<n> (bayan--4-page-5.png)
BATCH_PAGE_FILE = re.compile(r'(?P<slug>[a-z0-9-]+?)--[0-9]+(-page-[0-9]+)?\.[a-z]+')
# The sheet columns that hold a row's source URLs, in the order the manifest lists them
SOURCE_COLUMNS = ('range_source', 'sound_source', 'drone_source', 'footage_source')
MANIFEST_COLUMNS: tuple[str, ...] = ('folder', 'file', 'bytes', 'sha256', 'modified_utc', 'sources')


class ManifestRow(BaseModel):
    """One saved page's line in the manifest."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    folder: str
    file: str
    bytes: int
    sha256: str
    modified_utc: str
    sources: str


def pages_folders(build_directory: Path) -> list[Path]:
    """List the pages folders under build/: build/pages and every build/batch-N-pages.

    Returns:
        The folders that exist, build/pages first, then the batches in batch order.
    """
    numbered = [
        (int(match.group(1)), path)
        for path in build_directory.iterdir()
        if path.is_dir() and (match := BATCH_PAGES_FOLDER.fullmatch(path.name))
    ]
    unnumbered = build_directory / UNNUMBERED_PAGES_FOLDER
    return ([unnumbered] if unnumbered.is_dir() else []) + [path for _, path in sorted(numbered)]


def sheet_sources(sheet: Path) -> dict[str, str]:
    """Read each row's source URLs from a batch's sheet.

    Returns:
        Each row's name with its distinct source URLs, space-separated in column order.
    """
    with sheet.open(encoding='utf-8', newline='') as sheet_file:
        rows = list(csv.DictReader(sheet_file, delimiter='\t'))
    sources: dict[str, str] = {}
    for row in rows:
        urls = [row.get(column) or '' for column in SOURCE_COLUMNS]
        distinct = dict.fromkeys(url for url in urls if url.startswith('http'))
        sources[row['name']] = ' '.join(distinct)
    return sources


def folder_sources(folder: Path, audit_directory: Path) -> dict[str, str]:
    """Find a pages folder's sheet and read its rows' sources.

    Returns:
        Each row's sources, or nothing for build/pages or a batch with no sheet.
    """
    match = BATCH_PAGES_FOLDER.fullmatch(folder.name)
    sheet = audit_directory / f'batch-{match.group(1)}.tsv' if match else None
    return sheet_sources(sheet) if sheet is not None and sheet.exists() else {}


def manifest_rows(build_directory: Path, audit_directory: Path) -> list[ManifestRow]:
    """Describe every saved page in every pages folder.

    Returns:
        One row per file, sorted by folder (build/pages, then batch order) then file name.
    """
    rows: list[ManifestRow] = []
    for folder in pages_folders(build_directory):
        sources = folder_sources(folder, audit_directory)
        for path in sorted(path for path in folder.iterdir() if path.is_file()):
            if path.name.startswith('.'):
                continue
            raw = path.read_bytes()
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            match = BATCH_PAGE_FILE.fullmatch(path.name)
            name = match.group('slug').replace('-', ' ') if match else ''
            rows.append(
                ManifestRow(
                    folder=folder.name,
                    file=path.name,
                    bytes=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    modified_utc=modified.date().isoformat(),
                    sources=sources.get(name, ''),
                ),
            )
    return rows


def write_manifest(rows: Sequence[ManifestRow], output: Path) -> None:
    """Write the manifest rows as a tab-separated file with a header row."""
    with output.open('w', encoding='utf-8', newline='') as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=MANIFEST_COLUMNS,
            delimiter='\t',
            lineterminator='\n',
        )
        writer.writeheader()
        writer.writerows(row.model_dump() for row in rows)


def main(argv: Sequence[str] | None = None) -> int:
    """Write the manifest and say how many pages it lists.

    Returns:
        ``ExitCode.SUCCESS``.
    """
    parser = argparse.ArgumentParser(
        description='Write the manifest of the source pages the instrument audit saved.',
    )
    parser.add_argument(
        '--build',
        type=Path,
        default=PROJECT_ROOT / 'build',
        help='the build directory holding the pages folders',
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=MANIFEST,
        help='the manifest to write',
    )
    arguments = parser.parse_args(argv)
    rows = manifest_rows(arguments.build, AUDIT_DIRECTORY)
    write_manifest(rows, arguments.output)
    sys.stdout.write(f'{len(rows)} pages in {arguments.output}\n')
    return ExitCode.SUCCESS


if __name__ == '__main__':
    sys.exit(main())
