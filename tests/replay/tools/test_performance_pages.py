"""The ``performance-pages`` tool (replay/tools/performance_pages.py): the ledger's graph pages.

Moved from tests/test_generate_performance_graphs.py with the rendering half of
scripts/generate_performance_graphs.py and its source merge (Part 3, Stage D, Task D7), on
stand-ins: a stand-in project's settings (another ledger directory, published path and pending
ledger than ours) and a stand-in game's recordings and console script. The published ledger
comes from a throwaway repository whose ``origin`` has a ``gh-pages`` branch
(tests/ledger_repositories.py); nothing here touches this repository's remotes or the network.
The docs snippet our site includes stays the script's (tests/test_generate_performance_graphs.py).

Design: plans/2026-10-23-recording-metrics-1-frame-performance-history.md.
"""

from __future__ import annotations

import errno
import filecmp
import json
import os
import re
import sys
from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames.__main__ import PYGAME_BANNER_VARIABLE
from glitchygames.code_tree import staged_code_tree
from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command
from glitchygames.recording_history import FrameTimeSummary
from glitchygames.recording_metrics import (
    FrameProfile,
    LedgerOrigin,
    LedgerRow,
    ledger_text,
    parse_ledger,
    performance_series,
    write_row_files,
)
from glitchygames.replay.tools import command, performance_pages
from glitchygames.replay.tools.performance_pages import (
    DEFAULT_LEDGER_NAME,
    PLOTLY_JS_URL,
    graph_page_name,
    merged_ledger,
    recording_charts,
    write_performance_pages,
)
from glitchygames.replay.tools.registry import tool_named
from glitchygames.replay.tools.settings import (
    GITIGNORE_FILE_NAME,
    LOCAL_DIRECTORY_NAME,
    ProjectSettings,
)
from tests.ledger_repositories import clone_with_published_ledger, git
from tests.replay.tools.test_report import hand_built_recording
from tests.stand_in_games import (
    RECORD_TIMEOUT_SECONDS,
    GameThatIsNeverBuilt,
    use_stand_in_game,
    write_stand_in_game,
)
from tests.test_recording_metrics import (
    NEWER_COMMIT,
    OLDER_COMMIT,
    ledger_row,
    run,
    with_uncommitted_changes,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tests.stand_in_games import StandInGame

# A stand-in game's console script and recordings (its golden, and a bundled demo)
STAND_IN_CONSOLE_SCRIPT = 'stand-in-rally'
GOLDEN = 'tests/fixtures/replays/stand-in-rally/golden.jsonl.gz'
DEMO = 'src/stand_in_rally/demos/serve.jsonl.gz'
# A stand-in project's settings, none of them ours: where it publishes its ledger, where its
# rows wait, where its row files are, and what its code tree holds
STAND_IN_PUBLISHED_LEDGER_PATH = 'site/numbers/ledger.jsonl'
STAND_IN_PUBLISHED_LEDGER = f'origin/gh-pages:{STAND_IN_PUBLISHED_LEDGER_PATH}'
STAND_IN_PENDING_LEDGER = 'waiting/pending.jsonl'
STAND_IN_LEDGER_DIRECTORY = 'measured-rows'
STAND_IN_SETTINGS = ProjectSettings(
    published_ledger=STAND_IN_PUBLISHED_LEDGER,
    pending_ledger=STAND_IN_PENDING_LEDGER,
    ledger_directory=STAND_IN_LEDGER_DIRECTORY,
    measured_paths=('src',),
)
STAND_IN_PYPROJECT = (
    '[tool.glitchygames]\n'
    f'published-ledger = {STAND_IN_PUBLISHED_LEDGER!r}\n'
    f'pending-ledger = {STAND_IN_PENDING_LEDGER!r}\n'
    f'ledger-directory = {STAND_IN_LEDGER_DIRECTORY!r}\n'
    "measured-paths = ['src']\n"
)
# The published ledger's file name, which the pages' directory holds
STAND_IN_LEDGER_NAME = 'ledger.jsonl'
OLDER_COMMITTED_AT = '2026-10-22T12:00:00-07:00'
OLDER_PROFILE = FrameProfile(
    frame_count=4, max_microseconds=(100, 200, None, 400), scene_runs=((0, 'Game'), (3, 'Pause'))
)
NEWER_PROFILE = FrameProfile(
    frame_count=4, max_microseconds=(150, 250, 350, 450), scene_runs=((0, 'Game'),)
)


def stand_in_row(**fields) -> LedgerRow:
    """Return a ledger row of the stand-in game (``ledger_row``'s, with its golden by default).

    Returns:
        The row.

    """
    fields.setdefault('recording', GOLDEN)
    return ledger_row(**fields).model_copy(update={'console_script': STAND_IN_CONSOLE_SCRIPT})


def page_charts(*, path: Path) -> dict:
    """Return the charts a graph page plots.

    Returns:
        The charts' JSON.

    """
    match = re.search(r'const charts = (.*);\n', path.read_text(encoding='utf-8'))
    assert match is not None
    return json.loads(match.group(1))


def live_row() -> LedgerRow:
    """Return a paced live run of the golden with its frame times.

    Returns:
        The row.

    """
    row = stand_in_row(commit=OLDER_COMMIT, committed_at=OLDER_COMMITTED_AT)
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

    The clone is a stand-in project: its pyproject.toml holds the stand-in settings.

    Returns:
        The clone (its origin/gh-pages publishes the ledger), the pending file and the rows.

    """
    older = stand_in_row(
        commit=OLDER_COMMIT,
        committed_at=OLDER_COMMITTED_AT,
        measured_at='2026-10-22T21:00:00+00:00',
        p50=0.001,
    ).model_copy(update={'profile': OLDER_PROFILE})
    newer = stand_in_row(p50=0.002).model_copy(
        update={
            'run': with_uncommitted_changes(run(commit=NEWER_COMMIT)),
            'profile': NEWER_PROFILE,
        }
    )
    demo = stand_in_row(recording=DEMO)
    clone = clone_with_published_ledger(
        tmp_path=tmp_path,
        ledger=ledger_text(rows=[older, live_row()]) + 'unreadable\n',
        published_path=STAND_IN_PUBLISHED_LEDGER_PATH,
    )
    (clone / 'pyproject.toml').write_text(STAND_IN_PYPROJECT, encoding='utf-8')
    pending = clone / STAND_IN_PENDING_LEDGER
    pending.parent.mkdir()
    pending.write_text(ledger_text(rows=[newer, older, demo]), encoding='utf-8')
    return clone, pending, [older, live_row(), newer, demo]


def test_the_ledgers_merge_into_the_directory_with_a_page_per_recording(tmp_path, caplog):
    """The merged ledger (by the published one's name) and one graph page per recording."""
    clone, pending, rows = published_and_pending(tmp_path=tmp_path)
    pages = tmp_path / 'pages'

    sources = merged_ledger(
        project_root=clone,
        settings=STAND_IN_SETTINGS,
        pending_path=pending,
        include_uncommitted_changes=True,
    )
    written = write_performance_pages(
        rows=sources.rows, directory=pages, settings=STAND_IN_SETTINGS
    )

    assert (len(sources.rows), sources.published_rows, sources.pending_rows) == (4, 2, 3)
    assert (sources.repository_rows, sources.unreadable_lines) == (0, 1)
    assert 'Skipped 1 unreadable ledger lines' in caplog.text
    merged = parse_ledger(text=(pages / STAND_IN_LEDGER_NAME).read_text(encoding='utf-8')).rows
    assert {row.key for row in merged} == {row.key for row in rows}
    assert written.pages == {
        DEMO: 'stand-in-rally-serve.html',
        GOLDEN: 'stand-in-rally-golden.html',
    }
    assert set(written.written) == {STAND_IN_LEDGER_NAME, *written.pages.values()}
    assert [series.recording for series in written.series] == [DEMO, GOLDEN, GOLDEN]
    golden_page = (pages / 'stand-in-rally-golden.html').read_text(encoding='utf-8')
    assert PLOTLY_JS_URL in golden_page
    charts = page_charts(path=pages / 'stand-in-rally-golden.html')
    assert charts['commits'] == ['abc1234', 'def5678']
    assert [trace['name'] for trace in charts['frame_time']] == [
        'Apple M4 Max, paced live run: p50',
        'Apple M4 Max, paced live run: p99',
        'Apple M4 Max, paced live run: max',
    ]
    p50 = charts['processing'][0]
    assert (p50['x'], p50['y']) == (['abc1234', 'def5678'], [1.0, 2.0])
    assert 'uncommitted changes' in p50['customdata'][1]

    (heatmap,) = charts['heatmaps']
    assert heatmap['name'] == 'Apple M4 Max, unpaced replay'
    assert heatmap['y'] == ['abc1234', 'def5678']
    assert heatmap['x'] == [0, 1, 2, 3]
    assert heatmap['z'] == [[0.1, 0.2, None, 0.4], [0.15, 0.25, 0.35, 0.45]]
    assert heatmap['customdata'][0][3] == 'frames 3-3, scene Pause, max 0.400 ms'
    assert heatmap['customdata'][0][2] == 'frames 2-2, scene Game, not timed'
    assert 'whether the work changed' in golden_page
    # The behaviour-change map is the engine's report tool, not the script it was
    assert '<code>glitchygames report</code>' in golden_page

    again = write_performance_pages(rows=sources.rows, directory=pages, settings=STAND_IN_SETTINGS)
    assert again.written == ()


def test_the_engines_published_build_leaves_out_rows_from_uncommitted_changes(tmp_path):
    """The merged ledger and every graph lose the trial; the rest is kept."""
    clone, pending, rows = published_and_pending(tmp_path=tmp_path)
    pages = tmp_path / 'pages'

    sources = merged_ledger(
        project_root=clone,
        settings=STAND_IN_SETTINGS,
        pending_path=pending,
        include_uncommitted_changes=False,
    )
    write_performance_pages(rows=sources.rows, directory=pages, settings=STAND_IN_SETTINGS)

    assert len(sources.rows) == 3
    merged = parse_ledger(text=(pages / STAND_IN_LEDGER_NAME).read_text(encoding='utf-8')).rows
    assert not any(row.from_uncommitted_changes for row in merged)
    assert len(merged) == len(rows) - 1
    charts = page_charts(path=pages / 'stand-in-rally-golden.html')
    assert charts['commits'] == ['abc1234']
    assert charts['heatmaps'][0]['y'] == ['abc1234']


def test_pages_of_recordings_that_left_the_ledger_are_removed(tmp_path):
    """A stale graph page is removed; a project that publishes nothing names its ledger file."""
    pages = tmp_path / 'pages'
    pages.mkdir()
    (pages / 'gone-golden.html').write_text('old', encoding='utf-8')
    (pages / 'notes.md').write_text('kept', encoding='utf-8')

    sources = merged_ledger(
        project_root=tmp_path,
        settings=ProjectSettings(),
        pending_path=tmp_path / 'none.jsonl',
        include_uncommitted_changes=False,
    )
    written = write_performance_pages(
        rows=sources.rows, directory=pages, settings=ProjectSettings()
    )

    assert written.removed == ('gone-golden.html',)
    assert not (pages / 'gone-golden.html').exists()
    assert (pages / 'notes.md').is_file()
    assert written.pages == {}
    assert not (pages / DEFAULT_LEDGER_NAME).read_text(encoding='utf-8')


def test_a_series_without_a_budget_has_no_over_budget_trace():
    """Uncapped recordings have no frame budget: nothing to count."""
    row = stand_in_row()
    assert row.summary is not None
    uncapped = row.model_copy(
        update={'summary': row.summary.model_copy(update={'frames_over_budget': None})}
    )
    charts = recording_charts(series_list=performance_series(rows=[uncapped], recording_renames={}))
    assert charts['over_budget'] == []
    assert charts['frame_time'] == []
    # Rows without a profile have no heatmap line
    assert charts['heatmaps'] == []


def test_graph_page_names():
    """The console script and the recording's name, without the suffix."""
    assert graph_page_name(recording=GOLDEN, console_script='stand-in-maze') == (
        'stand-in-maze-golden.html'
    )


def test_a_moved_recording_is_one_page_under_its_new_path(tmp_path):
    """The project's recording-renames join a moved recording's rows on its new path's page."""
    old_path = 'tests/fixtures/replays/old-golden.jsonl.gz'
    settings = ProjectSettings(recording_renames={old_path: GOLDEN})
    rows = [
        stand_in_row(recording=old_path, commit=OLDER_COMMIT, committed_at=OLDER_COMMITTED_AT),
        stand_in_row(),
    ]

    written = write_performance_pages(rows=rows, directory=tmp_path, settings=settings)

    assert written.pages == {GOLDEN: 'stand-in-rally-golden.html'}
    charts = page_charts(path=tmp_path / 'stand-in-rally-golden.html')
    assert charts['commits'] == ['abc1234', 'def5678']


def clone_with_measured_rows(*, tmp_path: Path) -> tuple[Path, LedgerRow, LedgerRow, str]:
    """Commit a code change carrying two row files: one of its own code tree, one of another.

    The first landed (its tree is the commit's code tree); the second names a tree no commit
    has (an intermediate commit's, or a branch's that was behind main). The rows are in the
    stand-in project's ledger directory, and its code tree is its measured paths' (``src``).

    Returns:
        The clone, the landed row, the unlanded row and the commit the first landed in.

    """
    clone = clone_with_published_ledger(
        tmp_path=tmp_path, ledger='', published_path=STAND_IN_PUBLISHED_LEDGER_PATH
    )
    code = clone / 'src' / 'stand_in_rally' / 'world.py'
    code.parent.mkdir(parents=True, exist_ok=True)
    code.write_text('gravity = 9.8\n', encoding='utf-8')
    git(repository=clone, arguments=['add', 'src/stand_in_rally/world.py'])
    tree = staged_code_tree(repository=clone, paths=STAND_IN_SETTINGS.code_tree_paths)
    landed = stand_in_row(measured_at='2026-10-25T10:00:00+00:00').model_copy(
        update={'code_tree': tree, 'allowed_uncommitted_changes': True}
    )
    unlanded = stand_in_row(measured_at='2026-10-25T09:00:00+00:00').model_copy(
        update={'code_tree': '2' * 40, 'allowed_uncommitted_changes': True}
    )
    write_row_files(rows=[landed, unlanded], directory=clone / STAND_IN_LEDGER_DIRECTORY)
    git(repository=clone, arguments=['add', STAND_IN_LEDGER_DIRECTORY])
    git(repository=clone, arguments=['commit', '--quiet', '-m', 'Gravity, measured'])
    commit = git(repository=clone, arguments=['rev-parse', 'HEAD']).strip()
    return clone, landed, unlanded, commit


def test_the_engines_published_build_shows_the_rows_whose_code_landed(tmp_path):
    """The project's row files: the landed one labelled with its commit, the other left out."""
    clone, landed, _unlanded, commit = clone_with_measured_rows(tmp_path=tmp_path)

    sources = merged_ledger(
        project_root=clone,
        settings=STAND_IN_SETTINGS,
        pending_path=tmp_path / 'no-pending.jsonl',
        include_uncommitted_changes=False,
    )

    assert sources.repository_rows == 2
    assert [row.code_tree for row in sources.rows] == [landed.code_tree]
    assert sources.rows[0].commit == commit


def test_the_engines_local_build_also_shows_rows_whose_code_has_not_landed(tmp_path):
    """A branch's rows show locally before it merges."""
    clone, _landed, _unlanded, _commit = clone_with_measured_rows(tmp_path=tmp_path)

    sources = merged_ledger(
        project_root=clone,
        settings=STAND_IN_SETTINGS,
        pending_path=tmp_path / 'no-pending.jsonl',
        include_uncommitted_changes=True,
    )

    assert len(sources.rows) == 2


def run_stand_in_game(
    *, game: StandInGame, arguments: list[str], working_directory: Path
) -> tuple[int, str, str]:
    """Run the stand-in game in a child with a tool flag (pygame's banner hidden).

    Returns:
        The child's exit status, standard output and standard error.

    """
    completed = run_command(
        command=[sys.executable, '-c', f'import {game.package}; {game.package}.main()', *arguments],
        environment={**os.environ, PYGAME_BANNER_VARIABLE: '1'},
        timeout_seconds=RECORD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.APART,
        working_directory=working_directory,
    )
    return completed.returncode, completed.stdout or '', completed.stderr or ''


@pytest.fixture
def stand_in_game(tmp_path_factory, monkeypatch) -> StandInGame:
    """Install the stand-in game (tests/stand_in_games.py) for this test and its children.

    Returns:
        The stand-in game.

    """
    install_directory = tmp_path_factory.mktemp('site-packages')
    game = write_stand_in_game(directory=install_directory)
    use_stand_in_game(install_directory=install_directory, monkeypatch=monkeypatch)
    return game


def assert_the_report_flag_prints_what_the_command_prints(
    *, game: StandInGame, project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--report`` on the game (a child, in the project) prints what the command prints."""
    recording = tmp_path / 'changed.jsonl.gz'
    hand_built_recording(path=recording)
    options = ['--threshold', '50', '--minimum-ms', '0.5', '--spans', '1']

    flag_status, flag_output, flag_errors = run_stand_in_game(
        game=game, arguments=['--report', str(recording), *options], working_directory=project
    )
    capsys.readouterr()
    command_status = command.main(['report', str(recording), *options])

    assert flag_status == ExitCode.SUCCESS, flag_errors
    assert command_status == ExitCode.SUCCESS
    assert flag_output == capsys.readouterr().out
    assert 'frames 4-8 (scene Game): slower' in flag_output


def assert_the_pages_flag_writes_what_the_command_writes(
    *, game: StandInGame, project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--performance-pages`` on the game and ``glitchygames performance-pages`` write alike.

    The game finds the project from the directory it runs in; the command is given it with
    ``--project-root`` and a DIRECTORY relative to where it runs.
    """
    flag_status, flag_output, flag_errors = run_stand_in_game(
        game=game,
        arguments=['--performance-pages', str(tmp_path / 'flag-pages')],
        working_directory=project,
    )
    capsys.readouterr()
    command_status = command.main([
        'performance-pages',
        'command-pages',
        '--project-root',
        str(project),
    ])

    assert flag_status == ExitCode.SUCCESS, flag_errors
    assert command_status == ExitCode.SUCCESS
    expected = [STAND_IN_LEDGER_NAME, 'stand-in-rally-golden.html', 'stand-in-rally-serve.html']
    assert sorted(path.name for path in (tmp_path / 'flag-pages').iterdir()) == sorted(expected)
    comparison = filecmp.dircmp(tmp_path / 'flag-pages', tmp_path / 'command-pages')
    assert (comparison.left_only, comparison.right_only) == ([], [])
    assert filecmp.cmpfiles(
        tmp_path / 'flag-pages', tmp_path / 'command-pages', expected, shallow=False
    ) == (expected, [], [])
    summary = (
        'Graphed 2 recordings from 4 ledger rows (0 in the repository, 2 published, 3 pending)'
    )
    assert summary in flag_output
    assert f'{summary} into command-pages' in capsys.readouterr().out


def test_report_and_performance_pages_as_a_flag_and_a_command(
    tmp_path, capsys, monkeypatch, stand_in_game
):
    """Each tool, as the stand-in game's flag (in a child) and as the command, does the same.

    ``report`` prints the same report. ``performance-pages`` writes the same pages from the
    stand-in project's settings: its published ledger, its pending rows, its ledger file's name.
    """
    project, _pending, _rows = published_and_pending(tmp_path=tmp_path)
    monkeypatch.chdir(tmp_path)

    assert_the_report_flag_prints_what_the_command_prints(
        game=stand_in_game, project=project, tmp_path=tmp_path, capsys=capsys
    )
    assert_the_pages_flag_writes_what_the_command_writes(
        game=stand_in_game, project=project, tmp_path=tmp_path, capsys=capsys
    )


def test_performance_pages_never_builds_the_game(mocker, tmp_path, monkeypatch, capsys):
    """``--performance-pages`` on a game runs while the engine is built: no pygame, no scene."""
    from glitchygames.replay.tools.golden_traces import GoldenTraceEngine

    clone, _pending, _rows = published_and_pending(tmp_path=tmp_path)
    monkeypatch.chdir(clone)
    pygame_started = mocker.spy(pygame, 'init')
    mocker.patch.object(sys, 'argv', ['the-game', '--performance-pages', 'pages'])

    with pytest.raises(SystemExit) as exit_information:
        GoldenTraceEngine(game=GameThatIsNeverBuilt)

    assert exit_information.value.code == ExitCode.SUCCESS
    pygame_started.assert_not_called()
    assert (clone / 'pages' / 'stand-in-rally-golden.html').is_file()
    assert 'Graphed 2 recordings from 4 ledger rows' in capsys.readouterr().out


def test_a_project_without_settings_gets_its_pages_from_the_defaults(tmp_path, capsys):
    """No pyproject.toml: the defaults, said; no rows yet; the local directory is out of git."""
    project = tmp_path / 'project'
    project.mkdir()
    pages = project / LOCAL_DIRECTORY_NAME / 'pages'

    status = command.main(['performance-pages', str(pages), '--project-root', str(project)])

    assert status == ExitCode.SUCCESS
    output = capsys.readouterr()
    assert 'using the default settings' in output.err
    assert 'Graphed 0 recordings from 0 ledger rows' in output.out
    assert not (pages / DEFAULT_LEDGER_NAME).read_text(encoding='utf-8')
    assert (project / LOCAL_DIRECTORY_NAME / GITIGNORE_FILE_NAME).is_file()


def test_settings_that_cannot_be_read_are_unusable_input(tmp_path, capsys):
    """An unknown setting: the tool says which and writes nothing."""
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.glitchygames]\nno-such-setting = 1\n', encoding='utf-8'
    )

    status = command.main(['performance-pages', 'pages', '--project-root', str(tmp_path)])

    assert status == ExitCode.UNUSABLE_INPUT
    assert "unknown setting 'no-such-setting'" in capsys.readouterr().err
    assert not (tmp_path / 'pages').exists()


def test_row_files_outside_a_git_repository_are_unusable_input(tmp_path, capsys, monkeypatch):
    """Row files git cannot date (no repository): said, not a traceback."""
    (tmp_path / 'pyproject.toml').write_text(STAND_IN_PYPROJECT, encoding='utf-8')
    write_row_files(rows=[stand_in_row()], directory=tmp_path / STAND_IN_LEDGER_DIRECTORY)
    # No repository above it either: git would search the parent directories
    monkeypatch.setenv('GIT_CEILING_DIRECTORIES', str(tmp_path.parent))

    status = command.main(['performance-pages', 'pages', '--project-root', str(tmp_path)])

    assert status == ExitCode.UNUSABLE_INPUT
    assert 'git log' in capsys.readouterr().err


def test_a_directory_that_cannot_be_written_is_cannot_write_output(tmp_path, capsys):
    """DIRECTORY is a file: said, and the tool exits CANNOT_WRITE_OUTPUT."""
    blocking_file = tmp_path / 'pages'
    blocking_file.write_text('a file, not a directory', encoding='utf-8')

    status = command.main([
        'performance-pages',
        str(blocking_file),
        '--project-root',
        str(tmp_path),
    ])

    assert status == ExitCode.CANNOT_WRITE_OUTPUT
    assert 'could not write the performance pages' in capsys.readouterr().err


def test_a_row_without_a_frame_count_and_profiles_of_different_lengths():
    """The hover omits an unknown frame count; a shorter profile's missing buckets are gaps.

    A bucket whose scene is unknown is hovered without one.
    """
    longer = stand_in_row(commit=OLDER_COMMIT, committed_at=OLDER_COMMITTED_AT).model_copy(
        update={
            'profile': FrameProfile(frame_count=3, max_microseconds=(100, 200, 300), scene_runs=())
        }
    )
    shorter = stand_in_row().model_copy(
        update={
            'frame_count': None,
            'profile': FrameProfile(frame_count=2, max_microseconds=(150, 250), scene_runs=()),
        }
    )

    charts = recording_charts(
        series_list=performance_series(rows=[longer, shorter], recording_renames={})
    )

    hovers = charts['processing'][0]['customdata']
    assert 'frames' in hovers[0]
    assert 'frames' not in hovers[1]
    (heatmap,) = charts['heatmaps']
    assert heatmap['z'] == [[0.1, 0.2, 0.3], [0.15, 0.25, None]]
    assert heatmap['customdata'][0][0] == 'frames 0-0, max 0.100 ms'
    assert not heatmap['customdata'][1][2]


def project_with_trials_and_unlanded_rows(*, tmp_path: Path) -> tuple[Path, set[str], set[str]]:
    """A stand-in project whose sources hold rows only a local build shows.

    Its row files: one landed, one whose code never landed. Its pending ledger: a clean row and
    a trial (measured on uncommitted changes).

    Returns:
        The project, the keys of the rows both builds show, and of those only a local one does.

    """
    project, landed, unlanded, _commit = clone_with_measured_rows(tmp_path=tmp_path)
    (project / 'pyproject.toml').write_text(STAND_IN_PYPROJECT, encoding='utf-8')
    clean = stand_in_row(recording=DEMO)
    trial = stand_in_row(measured_at='2026-10-26T09:00:00+00:00').model_copy(
        update={'run': with_uncommitted_changes(run(commit=NEWER_COMMIT))}
    )
    pending = project / STAND_IN_PENDING_LEDGER
    pending.parent.mkdir()
    pending.write_text(ledger_text(rows=[clean, trial]), encoding='utf-8')
    return project, {landed.key, clean.key}, {unlanded.key, trial.key}


def ledger_keys(*, directory: Path) -> set[str]:
    """Return the keys of the rows of the ledger file a build wrote.

    Returns:
        The keys.

    """
    text = (directory / STAND_IN_LEDGER_NAME).read_text(encoding='utf-8')
    return {row.key for row in parse_ledger(text=text).rows}


def test_the_published_switch_builds_what_a_deploy_publishes(
    tmp_path, capsys, monkeypatch, stand_in_game
):
    """``--published`` leaves out exactly the trials and the unlanded rows, on both front ends.

    Without it the build is local (both kinds shown); with it, as the game's flag or the
    command's option, the same published pages.
    """
    project, both, local_only = project_with_trials_and_unlanded_rows(tmp_path=tmp_path)
    monkeypatch.chdir(tmp_path)

    local = command.main(['performance-pages', 'local', '--project-root', str(project)])
    published = command.main([
        'performance-pages',
        'published',
        '--published',
        '--project-root',
        str(project),
    ])
    flag_status, _flag_output, flag_errors = run_stand_in_game(
        game=stand_in_game,
        arguments=['--performance-pages', str(tmp_path / 'flag-published'), '--published'],
        working_directory=project,
    )

    assert (local, published, flag_status) == (ExitCode.SUCCESS,) * 3, flag_errors
    assert ledger_keys(directory=tmp_path / 'local') == both | local_only
    assert ledger_keys(directory=tmp_path / 'published') == both
    comparison = filecmp.dircmp(tmp_path / 'published', tmp_path / 'flag-published')
    assert (comparison.left_only, comparison.right_only, comparison.diff_files) == ([], [], [])
    assert 'Graphed 2 recordings from 2 ledger rows' in capsys.readouterr().out
    published_switch = [option.flag for option in tool_named(name='performance-pages').options]
    assert published_switch == ['--published']


@pytest.mark.parametrize('unreadable', ['not permitted', 'not utf-8'])
def test_an_unreadable_pending_ledger_is_unusable_input_naming_it(
    tmp_path, capsys, mocker, unreadable
):
    """A pending ledger that can't be read (no permission, not UTF-8): said, never a traceback.

    The missing permission is injected at the read: ``chmod(0)`` blocks no read on Windows or
    for root, so a real one would not fail everywhere this runs.
    """
    (tmp_path / 'pyproject.toml').write_text(STAND_IN_PYPROJECT, encoding='utf-8')
    pending = tmp_path / STAND_IN_PENDING_LEDGER
    pending.parent.mkdir()
    if unreadable == 'not permitted':
        pending.write_text(ledger_text(rows=[stand_in_row()]), encoding='utf-8')
        mocker.patch.object(
            performance_pages,
            'read_ledger_file',
            side_effect=PermissionError(errno.EACCES, 'Permission denied', str(pending)),
        )
    else:
        pending.write_bytes(b'\xff\xfe not a ledger\n')

    status = command.main(['performance-pages', 'pages', '--project-root', str(tmp_path)])

    assert status == ExitCode.UNUSABLE_INPUT
    errors = capsys.readouterr().err
    assert f'{pending}: the ledger cannot be read' in errors
    assert not (tmp_path / 'pages').exists()
