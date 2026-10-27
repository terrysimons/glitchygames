"""scripts/generate_performance_graphs.py: our docs site's performance pages and their snippet.

Design: plans/2026-10-23-recording-metrics-1-frame-performance-history.md. The pages are the
engine's (glitchygames/replay/tools/performance_pages.py, tested in
tests/replay/tools/test_performance_pages.py since Part 3, Stage D, Task D7); what is tested here
is the script's: the snippet docs/quality/performance.md includes, the settings it is given, and
the mkdocs hook that runs it. The published ledger comes from a throwaway repository whose
``origin`` has a ``gh-pages`` branch (tests/ledger_repositories.py); the pending rows are a file
in tmp_path.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import pytest
from mkdocs.exceptions import PluginError
from scripts import mkdocs_hooks
from scripts.generate_performance_graphs import (
    LEDGER_NAME,
    PROJECT_SETTINGS,
    SNIPPET_NAME,
    generate_performance_page,
    published_ledger_path,
)

from glitchygames.code_tree import staged_code_tree
from glitchygames.recording_history import FrameTimeSummary
from glitchygames.recording_metrics import (
    FrameProfile,
    LedgerOrigin,
    LedgerRow,
    ledger_text,
    parse_ledger,
    write_row_files,
)
from glitchygames.replay.tools.settings import ProjectSettings
from tests.ledger_repositories import clone_with_published_ledger, git
from tests.test_code_tree import LEDGER_DIRECTORY, PATHS
from tests.test_recording_metrics import (
    NEWER_COMMIT,
    OLDER_COMMIT,
    ledger_row,
    run,
    with_uncommitted_changes,
)

if TYPE_CHECKING:
    from pathlib import Path

GOLDEN = 'src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz'
DEMO = 'src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz'
OLDER_COMMITTED_AT = '2026-10-22T12:00:00-07:00'
OLDER_PROFILE = FrameProfile(
    frame_count=4, max_microseconds=(100, 200, None, 400), scene_runs=((0, 'Game'), (3, 'Pause'))
)
NEWER_PROFILE = FrameProfile(
    frame_count=4, max_microseconds=(150, 250, 350, 450), scene_runs=((0, 'Game'),)
)


def page_charts(*, path: Path) -> dict:
    """Return the charts a graph page plots.

    Returns:
        The charts' JSON.

    """
    match = re.search(r'const charts = (.*);\n', path.read_text(encoding='utf-8'))
    assert match is not None
    return json.loads(match.group(1))


def live_row() -> LedgerRow:
    """Return a paced live run of the golden replay with its frame times.

    Returns:
        The row.

    """
    row = ledger_row(commit=OLDER_COMMIT, committed_at=OLDER_COMMITTED_AT)
    assert row.summary is not None
    frame_time = FrameTimeSummary(
        p50_seconds=0.0166, p99_seconds=0.0168, max_seconds=0.018, late_frames=0
    )
    return row.model_copy(
        update={
            'origin': LedgerOrigin.RECORDING,
            'run': run(
                commit=OLDER_COMMIT,
                committed_at=OLDER_COMMITTED_AT,
                measured_at='2026-10-22T20:00:00+00:00',
                processing_paced=True,
                rebaselined_from=None,
            ),
            'summary': row.summary.model_copy(update={'frame_time': frame_time}),
        }
    )


def published_and_pending(*, tmp_path: Path) -> tuple[Path, Path, list[LedgerRow]]:
    """Publish an older measurement and a live run; leave newer ones (and a copy) pending.

    Returns:
        The clone (its origin/gh-pages publishes the ledger), the pending file and the rows.

    """
    older = ledger_row(
        commit=OLDER_COMMIT,
        committed_at=OLDER_COMMITTED_AT,
        measured_at='2026-10-22T21:00:00+00:00',
        p50=0.001,
    ).model_copy(update={'profile': OLDER_PROFILE})
    newer = ledger_row(p50=0.002).model_copy(
        update={
            'run': with_uncommitted_changes(run(commit=NEWER_COMMIT)),
            'profile': NEWER_PROFILE,
        }
    )
    demo = ledger_row(recording=DEMO)
    clone = clone_with_published_ledger(
        tmp_path=tmp_path, ledger=ledger_text(rows=[older, live_row()]) + 'unreadable\n'
    )
    pending = tmp_path / 'pending.jsonl'
    pending.write_text(ledger_text(rows=[newer, older, demo]), encoding='utf-8')
    return clone, pending, [older, live_row(), newer, demo]


def test_the_snippet_follows_the_pages_in_the_docs_tree(tmp_path):
    """The engine's ledger and pages, then the snippet that frames them; nothing again unchanged."""
    clone, pending, rows = published_and_pending(tmp_path=tmp_path)
    metrics = tmp_path / 'docs' / 'quality' / 'metrics'

    page = generate_performance_page(
        project_root=clone,
        settings=PROJECT_SETTINGS,
        metrics_directory=metrics,
        pending_path=pending,
        include_uncommitted_changes=True,
    )

    assert (page.rows, page.published_rows, page.pending_rows) == (4, 2, 3)
    assert page.unreadable_lines == 1
    merged = parse_ledger(text=(metrics / LEDGER_NAME).read_text(encoding='utf-8')).rows
    assert {row.key for row in merged} == {row.key for row in rows}
    assert page.graph_pages == ('paddleslap-rally.html', 'paddleslap-golden.html')
    assert page.written == (LEDGER_NAME, *page.graph_pages, SNIPPET_NAME)
    charts = page_charts(path=metrics / 'paddleslap-golden.html')
    assert charts['commits'] == ['abc1234', 'def5678']
    snippet = (metrics / SNIPPET_NAME).read_text(encoding='utf-8')
    assert 'Generated from 4 ledger rows (0 in the repository, 2 published, 3 pending)' in snippet
    assert '`def5678 (uncommitted changes)`' in snippet
    assert '<iframe src="../metrics/paddleslap-golden.html"' in snippet
    assert f'[{LEDGER_NAME}](metrics/{LEDGER_NAME})' in snippet
    assert snippet.index('paddleslap/demos/rally.jsonl.gz`') < snippet.index(
        'replays/golden.jsonl.gz`'
    )

    again = generate_performance_page(
        project_root=clone,
        settings=PROJECT_SETTINGS,
        metrics_directory=metrics,
        pending_path=pending,
        include_uncommitted_changes=True,
    )
    assert again.written == ()


def test_a_published_build_leaves_out_rows_from_uncommitted_changes(tmp_path):
    """The merged ledger and the table lose the trial; the rest is kept."""
    clone, pending, rows = published_and_pending(tmp_path=tmp_path)
    metrics = tmp_path / 'metrics'

    page = generate_performance_page(
        project_root=clone,
        settings=PROJECT_SETTINGS,
        metrics_directory=metrics,
        pending_path=pending,
        include_uncommitted_changes=False,
    )

    assert page.rows == 3
    merged = parse_ledger(text=(metrics / LEDGER_NAME).read_text(encoding='utf-8')).rows
    assert not any(row.from_uncommitted_changes for row in merged)
    assert len(merged) == len(rows) - 1
    snippet = (metrics / SNIPPET_NAME).read_text(encoding='utf-8')
    assert 'uncommitted changes' not in snippet
    assert 'Generated from 3 ledger rows' in snippet


def test_an_empty_ledger_says_how_to_measure(tmp_path):
    """A stale graph page is removed (the engine's rule), and the snippet says how to measure."""
    metrics = tmp_path / 'metrics'
    metrics.mkdir()
    (metrics / 'gone-golden.html').write_text('old', encoding='utf-8')

    page = generate_performance_page(
        project_root=tmp_path,
        settings=PROJECT_SETTINGS,
        metrics_directory=metrics,
        pending_path=tmp_path / 'none.jsonl',
        include_uncommitted_changes=False,
    )

    assert page.removed == ('gone-golden.html',)
    assert not (metrics / 'gone-golden.html').exists()
    assert 'No measurements yet' in (metrics / SNIPPET_NAME).read_text(encoding='utf-8')
    assert not (metrics / LEDGER_NAME).read_text(encoding='utf-8')


@pytest.mark.parametrize(
    ('command', 'shows_uncommitted_changes'),
    [('gh-deploy', False), ('build', True), ('serve', True), (None, False)],
)
def test_the_mkdocs_hook_shows_trials_only_in_a_local_build(
    tmp_path, mocker, command, shows_uncommitted_changes
):
    """gh-deploy (or no startup event) publishes without them; build and serve show them."""
    clone, pending, _ = published_and_pending(tmp_path=tmp_path)
    performance_script = mkdocs_hooks.load_performance_script()
    metrics = tmp_path / 'metrics'
    mocker.patch.object(performance_script, 'PROJECT_ROOT', clone)
    mocker.patch.object(performance_script, 'METRICS_DIR', metrics)
    mocker.patch.object(performance_script, 'PENDING_LEDGER_PATH', pending)
    # Restored after the test: on_startup sets it for the whole mkdocs invocation
    mocker.patch.object(mkdocs_hooks.BUILD_STATE, 'command', None)
    if command is not None:
        mkdocs_hooks.on_startup(command=command, dirty=False)

    mkdocs_hooks.generate_performance_graphs()

    snippet = (metrics / SNIPPET_NAME).read_text(encoding='utf-8')
    assert ('uncommitted changes' in snippet) is shows_uncommitted_changes
    assert mkdocs_hooks.load_performance_script() is performance_script


def test_the_mkdocs_hook_stops_the_build_when_a_file_cannot_be_written(tmp_path, mocker):
    """An unwritable metrics directory becomes mkdocs's PluginError."""
    performance_script = mkdocs_hooks.load_performance_script()
    blocking_file = tmp_path / 'metrics'
    blocking_file.write_text('a file, not a directory', encoding='utf-8')
    mocker.patch.object(performance_script, 'PROJECT_ROOT', tmp_path)
    mocker.patch.object(performance_script, 'METRICS_DIR', blocking_file)
    mocker.patch.object(performance_script, 'PENDING_LEDGER_PATH', tmp_path / 'none.jsonl')

    with pytest.raises(PluginError, match='Could not generate the performance graphs'):
        mkdocs_hooks.generate_performance_graphs()


def clone_with_measured_rows(*, tmp_path: Path) -> tuple[Path, LedgerRow, LedgerRow, str]:
    """Commit a code change carrying two row files: one of its own code tree, one of another.

    The first landed (its tree is the commit's code tree); the second names a tree no commit
    has (an intermediate commit's, or a branch's that was behind main).

    Returns:
        The clone, the landed row, the unlanded row and the commit the first landed in.

    """
    clone = clone_with_published_ledger(tmp_path=tmp_path, ledger='')
    code = clone / 'src' / 'glitchygames' / 'world.py'
    code.parent.mkdir(parents=True, exist_ok=True)
    code.write_text('gravity = 9.8\n', encoding='utf-8')
    git(repository=clone, arguments=['add', 'src/glitchygames/world.py'])
    tree = staged_code_tree(repository=clone, paths=PATHS)
    landed = ledger_row(measured_at='2026-10-25T10:00:00+00:00').model_copy(
        update={'code_tree': tree, 'allowed_uncommitted_changes': True}
    )
    unlanded = ledger_row(measured_at='2026-10-25T09:00:00+00:00').model_copy(
        update={'code_tree': '2' * 40, 'allowed_uncommitted_changes': True}
    )
    write_row_files(rows=[landed, unlanded], directory=clone / LEDGER_DIRECTORY)
    git(repository=clone, arguments=['add', LEDGER_DIRECTORY])
    git(repository=clone, arguments=['commit', '--quiet', '-m', 'Gravity, measured'])
    commit = git(repository=clone, arguments=['rev-parse', 'HEAD']).strip()
    return clone, landed, unlanded, commit


def test_a_published_build_shows_the_rows_whose_code_landed(tmp_path):
    """The repository's row files: the landed one labelled with its commit, the other left out."""
    clone, landed, _unlanded, commit = clone_with_measured_rows(tmp_path=tmp_path)
    metrics = tmp_path / 'metrics'

    page = generate_performance_page(
        project_root=clone,
        settings=PROJECT_SETTINGS,
        metrics_directory=metrics,
        pending_path=tmp_path / 'no-pending.jsonl',
        include_uncommitted_changes=False,
    )

    merged = parse_ledger(text=(metrics / LEDGER_NAME).read_text(encoding='utf-8')).rows
    assert page.repository_rows == 2
    assert [row.code_tree for row in merged] == [landed.code_tree]
    assert merged[0].commit == commit
    assert 'Generated from 1 ledger rows (2 in the repository, 0 published, 0 pending)' in (
        (metrics / SNIPPET_NAME).read_text(encoding='utf-8')
    )


def test_a_local_build_also_shows_rows_whose_code_has_not_landed(tmp_path):
    """A branch's rows show locally before it merges."""
    clone, _landed, _unlanded, _commit = clone_with_measured_rows(tmp_path=tmp_path)

    page = generate_performance_page(
        project_root=clone,
        settings=PROJECT_SETTINGS,
        metrics_directory=tmp_path / 'metrics',
        pending_path=tmp_path / 'no-pending.jsonl',
        include_uncommitted_changes=True,
    )

    assert page.rows == 2


def test_the_published_ledger_path_is_the_settings_path():
    """Ours is published on gh-pages at quality/metrics/; the pages are generated beside it."""
    settings = ProjectSettings(published_ledger='origin/gh-pages:quality/metrics/ledger.jsonl')

    assert published_ledger_path(settings=settings) == 'quality/metrics/ledger.jsonl'


def test_a_project_that_publishes_no_ledger_is_refused_naming_the_setting():
    """The docs pages need a published ledger: without published-ledger, an error, not a crash."""
    with pytest.raises(ValueError, match='published-ledger'):
        published_ledger_path(settings=ProjectSettings())


def test_the_settings_given_are_the_ones_read(tmp_path):
    """Another project's settings: its ledger directory and published path, never ours."""
    published = ledger_row(commit=OLDER_COMMIT, committed_at=OLDER_COMMITTED_AT)
    clone = clone_with_published_ledger(
        tmp_path=tmp_path,
        ledger=ledger_text(rows=[published]),
        published_path='elsewhere/ledger.jsonl',
    )
    settings = ProjectSettings(
        published_ledger='origin/gh-pages:elsewhere/ledger.jsonl', ledger_directory='rows'
    )
    # Our ledger directory's row files would be read by our settings: not by these
    write_row_files(rows=[ledger_row()], directory=clone / LEDGER_DIRECTORY)

    theirs = generate_performance_page(
        project_root=clone,
        settings=settings,
        metrics_directory=tmp_path / 'theirs',
        pending_path=tmp_path / 'no-pending.jsonl',
        include_uncommitted_changes=True,
    )
    ours = generate_performance_page(
        project_root=clone,
        settings=PROJECT_SETTINGS,
        metrics_directory=tmp_path / 'ours',
        pending_path=tmp_path / 'no-pending.jsonl',
        include_uncommitted_changes=True,
    )

    assert (theirs.published_rows, theirs.repository_rows) == (1, 0)
    assert (ours.published_rows, ours.repository_rows) == (0, 1)
