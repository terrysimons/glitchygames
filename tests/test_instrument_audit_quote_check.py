"""Tests for scripts/instrument_audit_quote_check.py: an audit sheet's quotes against saved pages.

Each test writes a small sheet and its saved pages to a throwaway directory: a passage on a page
(across line breaks, behind HTML tags and entities) or in a ledger file, and one on neither; a
shipped row's trait passages and a Wikipedia source's citation; the page encodings the check
reads and the one it refuses; the saved pages that are findings themselves (empty, an error page,
a redirect); and the command line's exit statuses.
"""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING

import pytest
from scripts.instrument_audit_quote_check import (
    FINDINGS,
    check_sheet,
    ledger_files,
    main,
    read_page,
)

from glitchygames.exit_codes import ExitCode

if TYPE_CHECKING:
    from pathlib import Path

    from scripts.instrument_audit_quote_check import QuoteCheckReport

SHEET_COLUMNS = (
    'name',
    'status',
    'builder',
    'range_source',
    'sound_source',
    'drones',
    'drone_source',
    'footage',
    'footage_source',
    'notes',
)
WIKIPEDIA_SOURCE = 'https://en.wikipedia.org/wiki/Kazoo'
MAKER_SOURCE = 'https://example.org/kazoo'


def write_sheet(directory: Path, rows: list[dict[str, str]]) -> Path:
    """Write rows as a tab-separated audit sheet, every column the check reads present.

    Returns:
        The sheet's path.
    """
    sheet = directory / 'batch-20.tsv'
    with sheet.open('w', encoding='utf-8', newline='') as sheet_file:
        writer = csv.DictWriter(sheet_file, fieldnames=SHEET_COLUMNS, delimiter='\t', restval='')
        writer.writeheader()
        writer.writerows(rows)
    return sheet


def save_page(pages: Path, file_name: str, content: str | bytes) -> None:
    """Save a page under a row's slugged name, as text (UTF-8) or as raw bytes."""
    pages.mkdir(exist_ok=True)
    raw = content.encode('utf-8') if isinstance(content, str) else content
    (pages / file_name).write_bytes(raw)


def run_check(
    tmp_path: Path,
    rows: list[dict[str, str]],
    ledgers: list[Path] | None = None,
) -> QuoteCheckReport:
    """Check a sheet of rows against tmp_path/pages and the given ledger files.

    Returns:
        The check's report.
    """
    pages = tmp_path / 'pages'
    pages.mkdir(exist_ok=True)
    return check_sheet(write_sheet(tmp_path, rows), pages, ledgers or [])


def problems(report: QuoteCheckReport) -> list[tuple[str, str]]:
    """List a report's findings as (name, problem) pairs.

    Returns:
        The findings in the order the check made them.
    """
    return [(finding.name, finding.problem) for finding in report.findings]


def test_a_quote_on_the_rows_saved_page_whatever_its_line_breaks_is_no_finding(tmp_path: Path):
    """A WAIT row's passage is found on its page though the page breaks the line mid-passage."""
    save_page(tmp_path / 'pages', 'tin-kazoo--1.txt', 'A kazoo is\na membranophone.')
    report = run_check(
        tmp_path,
        [{'name': 'tin kazoo', 'status': 'WAIT', 'notes': 'Page: «kazoo is a membranophone»'}],
    )
    assert problems(report) == []


def test_a_quote_behind_html_tags_and_entities_is_found_in_the_pages_visible_text(
    tmp_path: Path,
):
    """A passage the raw page splits with tags and spells with an entity is still on the page."""
    save_page(tmp_path / 'pages', 'kazoo--1.txt', '<p>A <b>kazoo</b> &amp; a comb</p>')
    report = run_check(
        tmp_path,
        [{'name': 'kazoo', 'status': 'DROP', 'notes': 'Page: «A kazoo & a comb»'}],
    )
    assert problems(report) == []


def test_a_quote_on_no_page_and_in_no_ledger_is_a_finding(tmp_path: Path):
    """A passage neither the row's pages nor any ledger file holds is listed, cut to 60 letters."""
    save_page(tmp_path / 'pages', 'kazoo--1.txt', 'A kazoo is a membranophone.')
    report = run_check(
        tmp_path,
        [{'name': 'kazoo', 'status': 'WAIT', 'notes': 'Page: «a kazoo is a flute»'}],
    )
    assert problems(report) == [
        ('kazoo', 'quote on no saved page or ledger file: a kazoo is a flute'),
    ]


def test_a_quote_in_a_ledger_file_needs_no_saved_page(tmp_path: Path):
    """A passage an earlier sheet or plan holds is no finding, though the row has no page."""
    ledger = tmp_path / 'future-features.md'
    ledger.write_text('Ruled: the kazoo waits for a sourced range.', encoding='utf-8')
    report = run_check(
        tmp_path,
        [{'name': 'kazoo', 'status': 'WAIT', 'notes': '«the kazoo waits for a sourced range»'}],
        ledgers=[ledger],
    )
    assert problems(report) == []


def test_a_ledger_file_list_leaves_out_the_sheet_being_checked(tmp_path: Path):
    """The sheets and audit files are ledgers, but never the sheet the check reads."""
    audit = tmp_path / 'plans' / 'data' / 'instrument-audit'
    audit.mkdir(parents=True)
    for file_name in ('batch-1.tsv', 'batch-2.tsv', 'brass.md'):
        (audit / file_name).write_text('', encoding='utf-8')
    (tmp_path / 'plans' / 'future-features.md').write_text('', encoding='utf-8')

    ledgers = ledger_files(audit / 'batch-2.tsv', audit)

    assert [path.name for path in ledgers] == ['future-features.md', 'batch-1.tsv', 'brass.md']


def test_a_shipped_row_with_no_saved_page_is_a_finding(tmp_path: Path):
    """A SHIP row must have a saved page for its range, whatever its notes."""
    report = run_check(tmp_path, [{'name': 'kazoo', 'status': 'SHIP', 'notes': 'Range: none'}])
    assert ('kazoo', 'no saved page') in problems(report)


def test_a_shipped_row_must_quote_its_range_on_its_saved_page(tmp_path: Path):
    """A SOUND_ALIKE with no Range: passage, and one whose passage is only in a ledger, fail."""
    ledger = tmp_path / 'design.md'
    ledger.write_text('from C4 to C6', encoding='utf-8')
    save_page(tmp_path / 'pages', 'kazoo--1.txt', 'A kazoo.')
    save_page(tmp_path / 'pages', 'comb--1.txt', 'A comb.')
    report = run_check(
        tmp_path,
        [
            {'name': 'kazoo', 'status': 'SOUND_ALIKE', 'notes': 'Range: none quoted'},
            {'name': 'comb', 'status': 'SOUND_ALIKE', 'notes': 'Range: «from C4 to C6»'},
        ],
        ledgers=[ledger],
    )
    assert problems(report) == [
        ('kazoo', 'no «passage» for the range'),
        ('comb', 'range not on a saved page: from C4 to C6'),
    ]


def test_a_wikipedia_range_needs_a_citation_in_its_paragraph(tmp_path: Path):
    """A citation after the passage in its paragraph passes; one past the blank line does not."""
    save_page(
        tmp_path / 'pages',
        'kazoo--1.txt',
        'It sounds from C4 to C6.<ref>Book</ref>\n\nIt sounds from D4 to D6.\n\n<ref>Book</ref>',
    )
    report = run_check(
        tmp_path,
        [
            {
                'name': 'kazoo',
                'status': 'SHIP',
                'range_source': WIKIPEDIA_SOURCE,
                'notes': 'Range: «from C4 to C6» and «from D4 to D6»',
            },
        ],
    )
    assert problems(report) == [('kazoo', 'range uncited: from D4 to D6')]


def test_an_uncited_tag_before_the_citation_leaves_the_passage_uncited(tmp_path: Path):
    """A {{citation needed}} between the passage and its <ref> means the passage is uncited."""
    save_page(
        tmp_path / 'pages',
        'kazoo--1.txt',
        'It sounds from C4 to C6.{{citation needed|date=May 2020}} More.<ref>Book</ref>',
    )
    report = run_check(
        tmp_path,
        [
            {
                'name': 'kazoo',
                'status': 'SHIP',
                'range_source': WIKIPEDIA_SOURCE,
                'notes': 'Range: «from C4 to C6»',
            },
        ],
    )
    assert problems(report) == [('kazoo', 'range uncited: from C4 to C6')]


def test_a_table_row_passage_needs_its_citation_on_its_own_line(tmp_path: Path):
    """A passage quoted from a wikitext table row (starting with |) ends at its line."""
    save_page(
        tmp_path / 'pages',
        'kazoo--1.txt',
        '| Kazoo || C4-C6\n| Comb || D4-D6 <ref>Book</ref>',
    )
    report = run_check(
        tmp_path,
        [
            {
                'name': 'kazoo',
                'status': 'SHIP',
                'range_source': WIKIPEDIA_SOURCE,
                'notes': 'Range: «| Kazoo || C4-C6»',
            },
        ],
    )
    assert problems(report) == [('kazoo', 'range uncited: | Kazoo || C4-C6')]


def test_a_maker_range_needs_no_citation(tmp_path: Path):
    """A passage whose source is not Wikipedia passes on its page alone."""
    save_page(tmp_path / 'pages', 'kazoo--1.txt', 'It sounds from C4 to C6.')
    report = run_check(
        tmp_path,
        [
            {
                'name': 'kazoo',
                'status': 'SHIP',
                'range_source': MAKER_SOURCE,
                'notes': 'Range: «from C4 to C6»',
            },
        ],
    )
    assert problems(report) == []


@pytest.mark.parametrize(
    ('row', 'trait'),
    [
        ({'drones': 'A3', 'drone_source': MAKER_SOURCE}, 'drones'),
        ({'footage': '8', 'footage_source': MAKER_SOURCE}, 'footage'),
        ({'builder': "_clarinet(cents=8)  # 'cents'", 'sound_source': MAKER_SOURCE}, 'detune'),
        (
            {'builder': "_reed(footages=(8, 4))  # 'footages'", 'sound_source': MAKER_SOURCE},
            'reeds',
        ),
    ],
)
def test_a_shipped_row_quotes_each_trait_its_build_makes(
    tmp_path: Path,
    row: dict[str, str],
    trait: str,
):
    """Drones, an organ footage, a detune and reeds each need their own passage.

    The range's passages stop at the trait's label, so a trait passage never counts as the
    range's, and a row with the trait but no passage for it is a finding.
    """
    save_page(tmp_path / 'pages', 'kazoo--1.txt', 'It sounds from C4 to C6.')
    shipped = {
        'name': 'kazoo',
        'status': 'SHIP',
        'range_source': MAKER_SOURCE,
        'notes': 'Range: «from C4 to C6» Drones: Footage: Detune: Reeds:',
        **row,
    }
    report = run_check(tmp_path, [shipped])
    assert problems(report) == [('kazoo', f'no «passage» for the {trait}')]


def test_a_range_passage_stops_at_the_next_trait_label(tmp_path: Path):
    """A footage passage after Footage: is checked against the footage source, not the range's.

    The range's source is Wikipedia and the footage's is a maker's page, so the footage passage
    needs no citation; read as part of the range it would.
    """
    save_page(
        tmp_path / 'pages',
        'kazoo--1.txt',
        'It sounds from C4 to C6.<ref>Book</ref>\n\nIt is of 8 ft. pitch.',
    )
    report = run_check(
        tmp_path,
        [
            {
                'name': 'kazoo',
                'status': 'SHIP',
                'range_source': WIKIPEDIA_SOURCE,
                'footage': '8',
                'footage_source': MAKER_SOURCE,
                'notes': 'Range: «from C4 to C6» Footage: «of 8 ft. pitch»',
            },
        ],
    )
    assert problems(report) == []


def test_a_page_is_read_as_utf_8_before_its_declaration():
    """A UTF-8 page that still declares windows-1251 (a converted copy) is read as UTF-8."""
    page = read_page('<meta charset="windows-1251">Гусли'.encode())
    assert (page.text, page.encoding) == ('<meta charset="windows-1251">Гусли', 'utf-8')


def test_a_page_that_is_not_utf_8_is_read_in_its_declared_charset():
    """A windows-1251 page that says so is read as windows-1251, never as windows-1252 garble."""
    page = read_page('<meta charset="windows-1251">Гусли'.encode('windows-1251'))
    assert (page.text, page.encoding) == ('<meta charset="windows-1251">Гусли', 'windows-1251')


def test_a_page_with_no_declaration_falls_back_to_windows_1252():
    """A page that is not UTF-8 and declares nothing is read as windows-1252."""
    page = read_page('Caf\u00e9 \u2013 kazoo'.encode('cp1252'))
    assert (page.text, page.encoding) == ('Caf\u00e9 \u2013 kazoo', 'cp1252')


def test_a_page_declaring_utf_8_that_is_not_falls_back_to_windows_1252():
    """A page that declares UTF-8 but is not is read as windows-1252, not refused."""
    page = read_page('<meta charset="utf-8">Café'.encode('cp1252'))
    assert page.encoding == 'cp1252'


def test_the_report_lists_how_each_page_that_was_not_utf_8_was_read(tmp_path: Path):
    """Pages read in their declared charset and pages read as windows-1252 are each listed."""
    pages = tmp_path / 'pages'
    save_page(pages, 'kazoo--1.txt', '<meta charset="windows-1251">Гусли'.encode('windows-1251'))
    save_page(pages, 'kazoo--2.txt', 'Café'.encode('cp1252'))
    save_page(pages, 'kazoo--3.txt', 'plain')
    report = run_check(tmp_path, [{'name': 'kazoo', 'status': 'WAIT', 'notes': ''}])
    assert report.decoded_as_declared == ['kazoo--1.txt (windows-1251)']
    assert report.decoded_as_windows_1252 == ['kazoo--2.txt']


def test_a_page_no_encoding_reads_is_a_finding_and_never_read_lossily(tmp_path: Path):
    """A page declaring a charset Python does not know is refused, and its text is not used."""
    save_page(tmp_path / 'pages', 'kazoo--1.txt', b'<meta charset="no-such-charset">\xff kazoo')
    report = run_check(
        tmp_path,
        [{'name': 'kazoo', 'status': 'WAIT', 'notes': '«kazoo»'}],
    )
    assert problems(report) == [
        ('kazoo', 'page neither UTF-8, its declared charset nor windows-1252: kazoo--1.txt'),
        ('kazoo', 'quote on no saved page or ledger file: kazoo'),
    ]


@pytest.mark.parametrize(
    ('content', 'problem'),
    [
        ('', 'saved page is empty'),
        ('<title>Wikimedia Error</title>Your IP', 'saved page is an error page'),
        ('<title>404 Not Found</title>', 'saved page is an error page'),
        ('<title>429 Too Many Requests</title>', 'saved page is an error page'),
        ('#REDIRECT [[Kazoo]]', 'saved page is a redirect'),
    ],
)
def test_a_saved_page_that_is_not_the_source_is_a_finding(
    tmp_path: Path,
    content: str,
    problem: str,
):
    """An empty page, an HTTP error page and a bare Wikipedia redirect are each a finding."""
    save_page(tmp_path / 'pages', 'kazoo--1.txt', content)
    report = run_check(tmp_path, [{'name': 'kazoo', 'status': 'WAIT', 'notes': ''}])
    assert problems(report) == [('kazoo', f'{problem}: kazoo--1.txt')]


def test_a_page_with_an_email_address_is_listed_by_name_and_is_no_finding(tmp_path: Path):
    """A page holding an address is listed for a person to judge; the address is not printed."""
    save_page(tmp_path / 'pages', 'kazoo--1.txt', 'Write to shop@example.org for a kazoo.')
    report = run_check(tmp_path, [{'name': 'kazoo', 'status': 'WAIT', 'notes': ''}])
    assert report.pages_with_email_address == ['kazoo--1.txt']
    assert problems(report) == []


def test_main_exits_with_success_when_there_is_no_finding(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    """The command line prints its lists and a zero count, and exits with success."""
    pages = tmp_path / 'pages'
    save_page(pages, 'kazoo--1.txt', 'A kazoo.')
    sheet = write_sheet(tmp_path, [{'name': 'kazoo', 'status': 'WAIT', 'notes': '«A kazoo»'}])

    status = main([str(sheet), '--pages', str(pages)])

    assert status == ExitCode.SUCCESS
    assert capsys.readouterr().out.splitlines() == [
        'decoded as declared: []',
        'decoded as windows-1252: []',
        'pages with an email address: []',
        'findings: 0',
    ]


def test_main_exits_with_findings_and_prints_each_one(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    """Each finding is printed as name: problem, and the exit status is FINDINGS."""
    pages = tmp_path / 'pages'
    pages.mkdir()
    sheet = write_sheet(tmp_path, [{'name': 'kazoo', 'status': 'WAIT', 'notes': '«A kazoo»'}])

    status = main([str(sheet), '--pages', str(pages)])

    assert status == FINDINGS
    output = capsys.readouterr().out.splitlines()
    assert 'kazoo: quote on no saved page or ledger file: A kazoo' in output
    assert output[-1] == 'findings: 1'


def test_main_requires_the_pages_directory(tmp_path: Path):
    """Without --pages the command line is a usage error, argparse's exit status."""
    with pytest.raises(SystemExit) as raised:
        main([str(tmp_path / 'batch-20.tsv')])
    assert raised.value.code == ExitCode.ARGUMENT_PARSER_ERROR
