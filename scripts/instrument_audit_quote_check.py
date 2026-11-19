r"""Check that every quoted passage in an instrument audit sheet is on a page saved for its row.

The instrument catalog expansion (plans/2026-11-07-instrument-catalog-expansion-design.md) writes
one audit sheet per batch (plans/data/instrument-audit/batch-N.tsv). A row's notes quote its
sources between guillemets (``«...»``), and its sources are saved as raw pages, named for the row
with its spaces as hyphens: ``<pages>/<name>--<n>.txt`` (or .pdf, .png). This check is the one
batches 11 to 19 ran as a per-batch copy, made one script for every family:

* Every «passage» in every row's notes, whatever its status, is on one of the row's saved pages
  (whatever its line breaks; for a page with HTML tags, in the raw text or in its visible text,
  tags removed and entities unescaped), or else in a committed ledger file the notes may quote:
  the expansion's design, plans/future-features.md, another sheet or an audit file.
* A SHIP or SOUND_ALIKE row quotes a passage for its range (``Range:``), and for each trait its
  build makes, a passage on its saved pages: its organ footage (``Footage:``, when the row's
  footage is not ``none``; batch 13), its drones (``Drones:``, when the row's drones are not
  ``none``), its detune (``Detune:``, when its builder sets ``'cents'``) and its reeds
  (``Reeds:``, when its builder sets ``'footages'``). One whose source is Wikipedia has a
  citation after the passage in its own cell or paragraph, before any uncited tag.
* A page is read as UTF-8, else in the charset it declares, else as windows-1252, each read that
  is not UTF-8 listed in the output. A page none of them decodes is a finding, never read lossily.
* A saved page that is empty, an HTTP error page or only a Wikipedia redirect is a finding: an
  error page is never saved, since Wikimedia's prints the client's address
  (plans/future-features.md #87), and a redirect's target page is saved instead.
* Every saved page holding an email address is listed (its name only), for a person to judge: a
  private person's address is redacted from the page, an institution's stays.

The pages are kept out of the repository (they are other people's pages); the sheet's source
URLs name them.

It exits ``ExitCode.SUCCESS`` when there is no finding and ``FINDINGS`` (1, as
scripts/docs_claims.py for its claims) when there are some.

Usage:
    uv run python -m scripts.instrument_audit_quote_check plans/data/instrument-audit/batch-19.tsv \
        --pages build/batch-19-pages
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from glitchygames.exit_codes import ExitCode

if TYPE_CHECKING:
    from collections.abc import Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIRECTORY = PROJECT_ROOT / 'plans' / 'data' / 'instrument-audit'
# The exit status when some passage is not where it should be (a finding, as
# scripts/docs_claims.py's)
FINDINGS = 1
# A citation in Wikipedia's wikitext: a <ref> tag or a short-footnote template
CITATION = re.compile(r'<ref[ >/]|\{\{\s*(sfn|harvnb|r)\s*\|', re.IGNORECASE)
# An uncited tag in Wikipedia's wikitext
UNCITED_TAG = re.compile(r'\{\{\s*(citation needed|cn|fact)\s*[|}]', re.IGNORECASE)
# A page's own declaration, read from its first 4 KB: <meta charset="...">, the http-equiv
# Content-Type's charset=, or an XML declaration's encoding=
DECLARED_CHARSET = re.compile(
    rb"""(?:charset|encoding)\s*=\s*["']?([A-Za-z0-9_-]+)""",
    re.IGNORECASE,
)
DECLARATION_BYTES = 4096
# A page saved without curl's -f: Wikimedia's error page, or a title naming an HTTP error
ERROR_PAGE = re.compile(
    r'<title>[^<]*(Wikimedia Error|403|404|429|5[0-9][0-9]|Rate limited|Forbidden|Not Found'
    r'|Too Many Requests)[^<]*</title>',
    re.IGNORECASE,
)
# A Wikipedia redirect saved as a row's page
REDIRECT_PAGE = re.compile(r'\A\s*#REDIRECT\s*\[\[', re.IGNORECASE)
# An email address on a saved page: listed for a person to judge, never a finding by itself
EMAIL_ADDRESS = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
# The labels a row's notes put before its trait passages; a trait's passages run to the next label
TRAIT_LABELS = ('Range:', 'Footage:', 'Drones:', 'Detune:', 'Reeds:')
UTF8_NAMES = frozenset({'utf8', 'utf8mb4'})


class Finding(BaseModel):
    """A sheet row's passage or page that fails the check."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    name: str
    problem: str


class QuoteCheckReport(BaseModel):
    """What the check found in one sheet, and how it read the pages."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    findings: list[Finding]
    decoded_as_declared: list[str]
    decoded_as_windows_1252: list[str]
    pages_with_email_address: list[str]


class PageText(BaseModel):
    """A saved page's text and the encoding it was read in."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    text: str
    encoding: str


def declared_charset(raw: bytes) -> str | None:
    """Find the charset a page declares for itself in its first 4 KB.

    Returns:
        The declared charset, lower-cased, or None when the page declares none.
    """
    match = DECLARED_CHARSET.search(raw[:DECLARATION_BYTES])
    return match.group(1).decode('ascii').lower() if match else None


def read_page(raw: bytes) -> PageText:
    """Read a saved page as UTF-8, else in its declared charset, else as windows-1252.

    UTF-8 comes first: a copy converted to UTF-8 keeps its original declaration, and real text in
    a single-byte charset with any non-ASCII letter is almost never valid UTF-8.

    A page that windows-1252 can not read either raises the decoder's UnicodeDecodeError, and a
    charset Python does not know raises LookupError.

    Returns:
        The page's text and the encoding that read it (``utf-8``, the declared charset, or
        ``cp1252``).
    """
    try:
        return PageText(text=raw.decode('utf-8'), encoding='utf-8')
    except UnicodeDecodeError:
        pass
    declared = declared_charset(raw)
    if declared is not None and declared.replace('-', '').replace('_', '') not in UTF8_NAMES:
        return PageText(text=raw.decode(declared), encoding=declared)
    return PageText(text=raw.decode('cp1252'), encoding='cp1252')


def visible_text(page: str) -> str:
    """Strip a page's HTML tags and unescape its entities.

    Returns:
        The page's text with each tag replaced by a space.
    """
    return html.unescape(re.sub(r'<[^>]+>', ' ', page))


def located(page: str, passage: str) -> tuple[int, int] | None:
    """Find a passage in a page, whatever whitespace stands between its words.

    Returns:
        The passage's start and end in the page, or None when it is not there.
    """
    words = passage.split()
    if not words:
        return None
    match = re.search(r'\s+'.join(re.escape(word) for word in words), page)
    return None if match is None else (match.start(), match.end())


def cited(page: str, span: tuple[int, int], passage: str) -> bool:
    """Tell whether a citation follows a passage in its cell or paragraph, before any uncited tag.

    A passage from a table row (one that starts with ``|``) ends at its line; any other ends at
    its paragraph's blank line.

    Returns:
        True when a citation follows the passage and no uncited tag comes before it.
    """
    start, end = span
    stop = page.find('\n' if passage.lstrip().startswith('|') else '\n\n', end)
    following = page[start:] if stop == -1 else page[start:stop]
    citation = CITATION.search(following)
    uncited = UNCITED_TAG.search(following)
    return citation is not None and (uncited is None or uncited.start() > citation.start())


def quoted_after(notes: str, label: str) -> list[str]:
    """Find the «passages» after a label in a row's notes, up to the next trait label.

    Returns:
        The passages, in the order the notes give them.
    """
    section = notes.partition(label)[2]
    ends = [section.find(other) for other in TRAIT_LABELS if other != label and other in section]
    if ends:
        section = section[: min(ends)]
    return re.findall(r'«(.+?)»', section, flags=re.DOTALL)


def on_page(page: str, passage: str) -> bool:
    """Tell whether a passage is in a page's raw text or in its visible text.

    Returns:
        True when the passage is in either.
    """
    return located(page, passage) is not None or located(visible_text(page), passage) is not None


def ledger_files(sheet: Path, audit_directory: Path) -> list[Path]:
    """List the committed files a sheet's notes may quote instead of a saved page.

    The expansion's design, plans/future-features.md, every sheet but this one and the audit
    files. A sheet is not its own ledger.

    Returns:
        The ledger files that exist.
    """
    plans = audit_directory.parent.parent
    candidates = [
        plans / '2026-11-07-instrument-catalog-expansion-design.md',
        plans / 'future-features.md',
        *sorted(audit_directory.glob('batch-*.tsv')),
        *sorted(audit_directory.glob('*.md')),
    ]
    return [path for path in candidates if path.exists() and path.resolve() != sheet.resolve()]


def trait_sections(row: dict[str, str]) -> list[tuple[str, list[str], str]]:
    """List the traits a shipped row must quote, each with its passages and its source URL.

    Every SHIP or SOUND_ALIKE row quotes its range; a row quotes its drones when they are not
    ``none``, its organ footage when it is not ``none``, its detune when its builder sets
    ``'cents'`` and its reeds when its builder sets ``'footages'``. A sheet from before a trait's
    column existed has no such trait.

    Returns:
        One (trait, passages, source URL) for each trait the row must quote.
    """
    notes = row['notes']
    builder = row.get('builder') or ''
    sections = [('range', quoted_after(notes, 'Range:'), row.get('range_source') or '')]
    if (row.get('footage') or 'none') != 'none':
        footage_source = row.get('footage_source') or ''
        sections.append(('footage', quoted_after(notes, 'Footage:'), footage_source))
    if (row.get('drones') or 'none') != 'none':
        sections.append(('drones', quoted_after(notes, 'Drones:'), row.get('drone_source') or ''))
    if "'cents'" in builder:
        sections.append(('detune', quoted_after(notes, 'Detune:'), row.get('sound_source') or ''))
    if "'footages'" in builder:
        sections.append(('reeds', quoted_after(notes, 'Reeds:'), row.get('sound_source') or ''))
    return sections


class SavedPage(BaseModel):
    """A row's saved page as the check read it: its text (None when unreadable) and findings."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    file_name: str
    text: str | None
    encoding: str | None
    holds_email_address: bool
    findings: list[Finding]


def saved_page(name: str, path: Path) -> SavedPage:
    """Read one of a row's saved pages and find what is wrong with the page itself.

    An empty page, a page no encoding reads, a Wikipedia redirect and an HTTP error page are
    findings.

    Returns:
        The page as read, with its findings.
    """
    raw = path.read_bytes()
    findings = [Finding(name=name, problem=f'saved page is empty: {path.name}')] if not raw else []
    try:
        page = read_page(raw)
    except UnicodeDecodeError, LookupError:
        problem = f'page neither UTF-8, its declared charset nor windows-1252: {path.name}'
        findings.append(Finding(name=name, problem=problem))
        return SavedPage(
            file_name=path.name,
            text=None,
            encoding=None,
            holds_email_address=False,
            findings=findings,
        )
    if REDIRECT_PAGE.match(page.text):
        findings.append(Finding(name=name, problem=f'saved page is a redirect: {path.name}'))
    if ERROR_PAGE.search(page.text):
        findings.append(Finding(name=name, problem=f'saved page is an error page: {path.name}'))
    return SavedPage(
        file_name=path.name,
        text=page.text,
        encoding=page.encoding,
        holds_email_address=EMAIL_ADDRESS.search(page.text) is not None,
        findings=findings,
    )


def check_sheet(sheet: Path, pages_directory: Path, ledgers: Sequence[Path]) -> QuoteCheckReport:
    """Check every row of a sheet against its saved pages and the ledger files.

    Returns:
        The findings, the pages read in a declared charset or as windows-1252, and the pages
        holding an email address.
    """
    with sheet.open(encoding='utf-8', newline='') as sheet_file:
        rows = list(csv.DictReader(sheet_file, delimiter='\t'))
    ledger_texts = [path.read_text(encoding='utf-8') for path in ledgers]
    findings: list[Finding] = []
    readings: list[SavedPage] = []
    for row in rows:
        name = row['name']
        saved = [
            saved_page(name, path)
            for path in sorted(pages_directory.glob(f'{name.replace(" ", "-")}--*.txt'))
        ]
        readings += saved
        findings += [finding for page in saved for finding in page.findings]
        pages = [page.text for page in saved if page.text is not None]
        if row['status'] in {'SHIP', 'SOUND_ALIKE'}:
            findings += shipped_row_findings(row, pages)
        for passage in re.findall(r'«(.+?)»', row['notes'], flags=re.DOTALL):
            on_a_page = any(on_page(page, passage) for page in pages)
            if not on_a_page and not any(located(text, passage) for text in ledger_texts):
                problem = 'quote on no saved page or ledger file: ' + passage[:60]
                findings.append(Finding(name=name, problem=problem))
    return QuoteCheckReport(
        findings=findings,
        decoded_as_declared=[
            f'{page.file_name} ({page.encoding})'
            for page in readings
            if page.encoding not in {None, 'utf-8', 'cp1252'}
        ],
        decoded_as_windows_1252=[page.file_name for page in readings if page.encoding == 'cp1252'],
        pages_with_email_address=sorted(
            {page.file_name for page in readings if page.holds_email_address},
        ),
    )


def shipped_row_findings(row: dict[str, str], pages: Sequence[str]) -> list[Finding]:
    """Check a SHIP or SOUND_ALIKE row's trait passages against its saved pages.

    Returns:
        A finding for a row with no saved page, a trait with no passage, a passage on no saved
        page, and a Wikipedia passage with no citation after it.
    """
    name = row['name']
    if not pages:
        return [Finding(name=name, problem='no saved page')]
    findings: list[Finding] = []
    for trait, passages, source in trait_sections(row):
        if not passages:
            findings.append(Finding(name=name, problem=f'no «passage» for the {trait}'))
        for passage in passages:
            found = [(page, span) for page in pages if (span := located(page, passage)) is not None]
            if not found and not any(on_page(page, passage) for page in pages):
                problem = f'{trait} not on a saved page: ' + passage[:60]
                findings.append(Finding(name=name, problem=problem))
            elif 'wikipedia.org' in source and not any(
                cited(page, span, passage) for page, span in found
            ):
                findings.append(Finding(name=name, problem=f'{trait} uncited: ' + passage[:60]))
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    """Check one sheet and print what the check found.

    Returns:
        ``ExitCode.SUCCESS`` when there is no finding, ``FINDINGS`` when there are some.
    """
    parser = argparse.ArgumentParser(
        description="Check an audit sheet's quoted passages against its saved pages.",
    )
    parser.add_argument('sheet', type=Path, help='the audit sheet, batch-N.tsv')
    parser.add_argument(
        '--pages',
        type=Path,
        required=True,
        help="the directory holding the sheet rows' saved pages",
    )
    arguments = parser.parse_args(argv)
    report = check_sheet(
        arguments.sheet,
        arguments.pages,
        ledger_files(arguments.sheet, AUDIT_DIRECTORY),
    )
    sys.stdout.write(f'decoded as declared: {report.decoded_as_declared}\n')
    sys.stdout.write(f'decoded as windows-1252: {report.decoded_as_windows_1252}\n')
    sys.stdout.write(f'pages with an email address: {report.pages_with_email_address}\n')
    sys.stdout.writelines(f'{finding.name}: {finding.problem}\n' for finding in report.findings)
    sys.stdout.write(f'findings: {len(report.findings)}\n')
    return FINDINGS if report.findings else ExitCode.SUCCESS


if __name__ == '__main__':
    sys.exit(main())
