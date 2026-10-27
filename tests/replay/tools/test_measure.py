"""The ``measure``, ``unmeasured`` and ``clear-published`` tools (replay/tools/measure.py).

Moved from tests/test_replay_metrics.py with scripts/replay_metrics.py (Part 3, Stage D, Task D6),
on stand-ins: a stand-in game (tests/stand_in_games.py) recorded in tmp_path stands for our
games, and stand-in projects for this repository. The measurements are real: each recording is
rebaselined headless through the stand-in's console script, on this checkout. A published ledger
is read from a throwaway repository whose ``origin`` has a ``gh-pages`` branch
(tests/ledger_repositories.py); nothing here touches this repository's remotes or the network.

Design: plans/2026-10-23-recording-metrics-1-frame-performance-history.md.
"""

from __future__ import annotations

import os
import shutil
import sys
import types
from pathlib import Path

import pygame
import pytest

from glitchygames.build_info import (
    BUILD_STAMP_FILE_NAME,
    RevisionSource,
    SourceRevision,
    source_revision,
)
from glitchygames.bundled_demos import bundled_demos
from glitchygames.exit_codes import ExitCode
from glitchygames.process import CompletedProcess, OutputCapture, run_command
from glitchygames.recording_history import CONTENT_HASH_FIELD, MEASUREMENT_RUNS_HEADER_FIELD
from glitchygames.recording_metrics import (
    LedgerOrigin,
    ledger_text,
    publishable_rows,
    published_ledger_text,
    read_ledger_file,
    read_row_files,
)
from glitchygames.replay.driver import write_bookmarked_copy
from glitchygames.replay.tools import command, measure
from glitchygames.replay.tools.children import rebaseline_recording_headless
from glitchygames.replay.tools.identity import GameIdentity, console_script_identity
from glitchygames.replay.tools.measure import (
    MeasureSettings,
    UnreplayableRecording,
    clear_published,
    combined_exit_code,
    ensure_directory,
    missing_measurements,
    recording_ledger_name,
    rows_to_write,
    unclaimed_goldens,
)
from glitchygames.replay.tools.recordings import Recording
from glitchygames.replay.tools.registry import tool_named
from glitchygames.replay.tools.settings import (
    GITIGNORE_FILE_NAME,
    LOCAL_DIRECTORY_GITIGNORE,
    LOCAL_DIRECTORY_NAME,
    ProjectSettings,
)
from glitchygames.scenes import Scene
from glitchygames.tracing import FRAMES_FIELD, is_bookmarked_copy, read_trace
from tests.ledger_repositories import clone_with_published_ledger, git
from tests.replay.replay_helpers import rewrite_recording
from tests.replay.test_replay_plugin import REPO_FIXTURE
from tests.stand_in_games import (
    RECORD_TIMEOUT_SECONDS,
    STAND_IN_GAME_RESOLUTION,
    StandInGame,
    record_stand_in_game,
    stamp_stand_in_game,
    use_stand_in_game,
    write_stand_in_distribution,
    write_stand_in_game,
    write_stand_in_package,
    write_stand_in_recording,
)
from tests.test_recording_metrics import ledger_row, with_uncommitted_changes

# A stand-in project's published ledger, as REF:PATH ([tool.glitchygames] published-ledger)
STAND_IN_PUBLISHED_LEDGER_PATH = 'metrics/ledger.jsonl'
STAND_IN_PUBLISHED_LEDGER = f'origin/gh-pages:{STAND_IN_PUBLISHED_LEDGER_PATH}'
# A stand-in project's pending ledger ([tool.glitchygames] pending-ledger)
STAND_IN_PENDING_LEDGER = 'ledger/pending.jsonl'
# A stand-in recording that is read, never replayed: a bookmark on frame 1 needs at least 1
# frame, and 3 leave frames after it
STAND_IN_RECORDING_FRAMES = 3
# A code tree the measurements name (the pre-commit hook's), and another
TREE = '0123456789abcdef0123456789abcdef01234567'
OTHER_TREE = 'fedcba9876543210fedcba9876543210fedcba98'
# A moved recording, old path -> new (a stand-in project's recording-renames)
OLD_RALLY_PATH = 'glitchygames/examples/paddleslap_demos/rally.jsonl.gz'
NEW_RALLY_PATH = 'src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz'
STAND_IN_SETTINGS = ProjectSettings(recording_renames={OLD_RALLY_PATH: NEW_RALLY_PATH})
# A workspace member no environment installs, and its golden replay (relative to the project)
UNINSTALLED_MEMBER_DIRECTORY = Path('src') / 'games' / 'glitchygames-not-installed-game'
UNINSTALLED_MEMBER_GOLDEN = (
    UNINSTALLED_MEMBER_DIRECTORY / 'tests' / 'fixtures' / 'replays' / 'golden.jsonl.gz'
)
# Our members' layout of goldens, as a stand-in project's golden-globs
MEMBER_GOLDEN_GLOB = 'src/*/*/tests/fixtures/replays/golden*.jsonl.gz'
# Where a stand-in project's goldens are: another project's layout,
# tests/fixtures/replays/<console-script>/, which the default golden-globs read
GOLDEN_DIRECTORY_PARTS = ('tests', 'fixtures', 'replays')
# A console script no environment installs
NO_SUCH_GAME = 'glitchygames-no-such-game'


class GameThatIsNeverBuilt(Scene):
    """A game for the in-process engine test: its scene must never be built for ``--measure``."""

    NAME = 'GameThatIsNeverBuilt'
    VERSION = '1.0'

    def __init__(self, options=None, groups=None) -> None:
        """Fail at once: measuring runs children, never this scene.

        Raises:
            AssertionError: Always.

        """
        message = '--measure built the scene'
        raise AssertionError(message)


def clean_revision() -> SourceRevision:
    """Return the imported engine's revision, as if it had no uncommitted changes.

    The child rebaselines run the same installed engine and record its commit (``uv sync``: the
    checkout's git HEAD; nox: the build stamp its test session's install was built with); the
    tree's own state (changed while developing, clean in CI) must not decide the tests.

    Returns:
        The revision.

    """
    return source_revision().model_copy(update={'uncommitted_changes': False})


@pytest.fixture
def stand_in_game(tmp_path_factory, monkeypatch) -> StandInGame:
    """Install the stand-in game (tests/stand_in_games.py) for this test and its children.

    Its facts that matter here: one console script (``stand-in-rally``), seeded and
    deterministic, so its child rebaseline exits SUCCESS and changes no frame. It is stamped as
    a clean game of this checkout, as ours are: its runs name the engine's commit as the game's,
    with no uncommitted changes (the tree's own state must not decide the tests).

    Returns:
        The stand-in game.

    """
    install_directory = tmp_path_factory.mktemp('site-packages')
    game = write_stand_in_game(directory=install_directory)
    stamp_stand_in_game(game=game, revision=clean_revision())
    use_stand_in_game(install_directory=install_directory, monkeypatch=monkeypatch)
    return game


def mark_runs_from_a_clean_checkout(*, path: Path) -> None:
    """Record a recording's runs as made from a clean checkout, as a committed golden's are.

    A run with uncommitted changes is never written as a history row (``rows_to_write``), and
    the tree's own state must not decide the tests.
    """

    def clean(trace: dict) -> None:
        for recorded_run in trace[MEASUREMENT_RUNS_HEADER_FIELD]:
            recorded_run['source_revision']['uncommitted_changes'] = False
            recorded_run['game_source_revision']['uncommitted_changes'] = False

    rewrite_recording(recording_path=path, change=clean)


@pytest.fixture
def stand_in_golden(stand_in_game, tmp_path_factory) -> Path:
    """Return the stand-in game's recording: one paced live run, with its commit.

    Returns:
        Its path (outside the project tree the tests copy it into).

    """
    path = record_stand_in_game(
        game=stand_in_game, path=tmp_path_factory.mktemp('recorded') / 'golden.jsonl.gz'
    )
    mark_runs_from_a_clean_checkout(path=path)
    return path


def copied_golden(*, project_root: Path, game: StandInGame, golden: Path) -> list[tuple[str, Path]]:
    """Copy a stand-in game's recording into a project tree, laid out as a member's golden is.

    Returns:
        The recordings to measure.

    """
    target = project_root / f'src/games/{game.distribution}/tests/fixtures/replays/golden.jsonl.gz'
    target.parent.mkdir(parents=True)
    shutil.copy(golden, target)
    return [(game.console_script, target)]


def member_golden_ledger_name(*, game: StandInGame) -> str:
    """Return the ledger name of ``copied_golden``'s copy (its path in the project).

    Returns:
        The name.

    """
    return f'src/games/{game.distribution}/tests/fixtures/replays/golden.jsonl.gz'


def write_uninstalled_member(*, project_root: Path) -> None:
    """Write a project whose one workspace member, with a golden replay, is not installed."""
    member = project_root / UNINSTALLED_MEMBER_DIRECTORY
    (member / 'src' / 'not_installed_game').mkdir(parents=True)
    (member / 'pyproject.toml').write_text(
        '[project]\nname = "glitchygames-not-installed-game"\n', encoding='utf-8'
    )
    golden = project_root / UNINSTALLED_MEMBER_GOLDEN
    golden.parent.mkdir(parents=True)
    golden.write_text('recording\n', encoding='utf-8')


def measure_settings(
    *, project_root: Path, pending: Path, revision: SourceRevision
) -> MeasureSettings:
    """Return a measurement's settings in a stand-in project (``STAND_IN_SETTINGS``).

    The others keep their defaults; a test changes them with ``model_copy``.

    Returns:
        The settings.

    """
    return MeasureSettings(
        project_root=project_root,
        project_settings=STAND_IN_SETTINGS,
        pending_path=pending,
        revision=revision,
    )


class TestThePublishedLedger:
    """The ledger a project publishes is read from its local ref (origin/gh-pages here)."""

    def test_the_published_ledger_is_read_from_origin_gh_pages(self, tmp_path):
        text = ledger_text(rows=[ledger_row()])
        clone = clone_with_published_ledger(
            tmp_path=tmp_path, ledger=text, published_path=STAND_IN_PUBLISHED_LEDGER_PATH
        )
        assert (
            published_ledger_text(project_root=clone, published_ledger=STAND_IN_PUBLISHED_LEDGER)
            == text
        )

    def test_no_ref_no_file_or_no_repository_is_an_empty_ledger(self, tmp_path):
        clone = clone_with_published_ledger(
            tmp_path=tmp_path, ledger='', published_path=STAND_IN_PUBLISHED_LEDGER_PATH
        )
        assert not published_ledger_text(
            project_root=clone, published_ledger=f'origin/missing:{STAND_IN_PUBLISHED_LEDGER_PATH}'
        )
        # main has no ledger file
        assert not published_ledger_text(
            project_root=clone, published_ledger=f'origin/main:{STAND_IN_PUBLISHED_LEDGER_PATH}'
        )
        not_a_repository = tmp_path / 'plain'
        not_a_repository.mkdir()
        assert not published_ledger_text(
            project_root=not_a_repository, published_ledger=STAND_IN_PUBLISHED_LEDGER
        )

    def test_a_project_that_publishes_nothing_has_an_empty_published_ledger(self, tmp_path):
        """No published-ledger (the default): nothing is read, even where one is published."""
        clone = clone_with_published_ledger(
            tmp_path=tmp_path,
            ledger=ledger_text(rows=[]),
            published_path=STAND_IN_PUBLISHED_LEDGER_PATH,
        )
        assert not published_ledger_text(project_root=clone, published_ledger=None)

    def test_a_missing_git_is_an_empty_ledger(self, tmp_path, mocker):
        mocker.patch.dict(os.environ, {'PATH': str(tmp_path)})
        assert not published_ledger_text(
            project_root=tmp_path, published_ledger=STAND_IN_PUBLISHED_LEDGER
        )

    def test_a_missing_pending_file_is_empty(self, tmp_path):
        assert read_ledger_file(path=tmp_path / 'none.jsonl').rows == ()


class TestRecordingLedgerNames:
    """A recording in the project by its project path, else by its install name."""

    def test_a_recording_in_the_project_is_named_by_its_project_path(self, tmp_path):
        """Inside the project the project path wins, whatever import path also holds it."""
        golden = tmp_path / 'src/games/rally/tests/fixtures/replays/golden.jsonl.gz'

        assert recording_ledger_name(path=golden, project_root=tmp_path, demo_packages=()) == (
            'src/games/rally/tests/fixtures/replays/golden.jsonl.gz'
        )

    def test_a_recording_in_site_packages_is_named_by_its_install_name(self, tmp_path, monkeypatch):
        """An installed system with no project: its bundled demo record's install name."""
        site_packages = tmp_path / 'lib' / 'site-packages'
        demo_directory = write_stand_in_package(
            directory=site_packages, package='stand_in_game', demo_names=('rally.jsonl.gz',)
        )
        # The directory above is an import path too: the record names it from the innermost
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.syspath_prepend(site_packages)
        (demo,) = bundled_demos(packages=('stand_in_game',))

        name = recording_ledger_name(
            path=demo_directory / 'rally.jsonl.gz',
            project_root=tmp_path / 'no-project',
            demo_packages=('stand_in_game',),
        )

        assert name == 'stand_in_game/demos/rally.jsonl.gz' == demo.install_name

    def test_a_recording_under_an_import_path_that_is_no_bundled_demo_is_refused(
        self, tmp_path, monkeypatch
    ):
        """Outside the project only a bundled demo's record names it, not the import paths."""
        site_packages = tmp_path / 'site-packages'
        write_stand_in_package(
            directory=site_packages, package='stand_in_game', demo_names=('rally.jsonl.gz',)
        )
        monkeypatch.syspath_prepend(site_packages)
        # Under the same import path as the demo, but not in its package's demos/
        stray = site_packages / 'stand_in_game' / 'rally.jsonl.gz'
        shutil.copy(REPO_FIXTURE, stray)

        with pytest.raises(ValueError, match='nor an installed bundled demo'):
            recording_ledger_name(
                path=stray, project_root=tmp_path / 'no-project', demo_packages=('stand_in_game',)
            )

    def test_a_recording_neither_in_the_project_nor_installed_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match='neither in the project'):
            recording_ledger_name(
                path=tmp_path / 'elsewhere' / 'rally.jsonl.gz',
                project_root=tmp_path / 'project',
                demo_packages=(),
            )


class TestMeasuringIntoRowFiles:
    """The pre-commit hook's measurement: row files naming the code tree measured."""

    def measure_tree(self, *, project_root, recordings, pending, rows_directory, code_tree):
        """Measure the recordings for a code tree into row files (the hook's measure call).

        Returns:
            What was measured.

        """
        return measure.measure(
            settings=measure_settings(
                project_root=project_root,
                pending=pending,
                revision=clean_revision().model_copy(update={'uncommitted_changes': True}),
            ).model_copy(
                update={
                    'allow_dirty': True,
                    'code_tree': code_tree,
                    'rows_directory': rows_directory,
                }
            ),
            recordings=recordings,
            published_text='',
        )

    def test_a_measurement_writes_row_files_naming_the_code_tree(
        self, tmp_path, stand_in_game, stand_in_golden
    ):
        project_root = tmp_path / 'project'
        recordings = copied_golden(
            project_root=project_root, game=stand_in_game, golden=stand_in_golden
        )
        pending = tmp_path / 'pending.jsonl'
        rows_directory = tmp_path / 'replay-ledger'

        result = self.measure_tree(
            project_root=project_root,
            recordings=recordings,
            pending=pending,
            rows_directory=rows_directory,
            code_tree=TREE,
        )

        assert result.exit_code == ExitCode.SUCCESS
        assert not pending.exists()
        rows = read_row_files(directory=rows_directory)
        measured = [row for row in rows if row.origin == LedgerOrigin.REPLAY_METRICS]
        recorded = [row for row in rows if row.origin == LedgerOrigin.RECORDING]
        # Only the run just measured names the code tree; this directory is no repository with
        # an origin/main, so none of the recording's own (history) runs has landed: none written
        assert [row.code_tree for row in measured] == [TREE]
        assert recorded == []
        assert not measured[0].from_uncommitted_changes
        assert measured[0].recording == member_golden_ledger_name(game=stand_in_game)
        assert measured[0].console_script == stand_in_game.console_script

    def test_a_missing_origin_main_is_said_once(
        self, tmp_path, capsys, stand_in_game, stand_in_golden
    ):
        project_root = tmp_path / 'project'

        self.measure_tree(
            project_root=project_root,
            recordings=copied_golden(
                project_root=project_root, game=stand_in_game, golden=stand_in_golden
            ),
            pending=tmp_path / 'pending.jsonl',
            rows_directory=tmp_path / 'replay-ledger',
            code_tree=TREE,
        )

        output = capsys.readouterr().out
        assert output.count('origin/main') == 1
        assert 'no history rows written' in output

    def test_the_same_code_tree_is_measured_once_per_machine(
        self, tmp_path, stand_in_game, stand_in_golden
    ):
        project_root = tmp_path / 'project'
        recordings = copied_golden(
            project_root=project_root, game=stand_in_game, golden=stand_in_golden
        )
        arguments = {
            'project_root': project_root,
            'recordings': recordings,
            'pending': tmp_path / 'pending.jsonl',
            'rows_directory': tmp_path / 'replay-ledger',
        }
        self.measure_tree(**arguments, code_tree=TREE)

        again = self.measure_tree(**arguments, code_tree=TREE)
        other_code = self.measure_tree(**arguments, code_tree=OTHER_TREE)

        assert again.measured == ()
        assert len(again.skipped) == 1
        assert len(other_code.measured) == 1

    def test_the_summary_names_the_rows_directory(
        self, tmp_path, capsys, stand_in_game, stand_in_golden
    ):
        project_root = tmp_path / 'project'
        rows_directory = tmp_path / 'replay-ledger'

        self.measure_tree(
            project_root=project_root,
            recordings=copied_golden(
                project_root=project_root, game=stand_in_game, golden=stand_in_golden
            ),
            pending=tmp_path / 'pending.jsonl',
            rows_directory=rows_directory,
            code_tree=TREE,
        )

        summary = capsys.readouterr().out.splitlines()[-1]
        assert summary.endswith(f'into {rows_directory}')
        assert 'code tree 0123456789ab' in summary


class TestRowsToWrite:
    """The rows a measurement writes: the newest run, and history runs that have landed."""

    @pytest.fixture
    def landed_repository(self, tmp_path):
        """Return a repository whose origin/main is its first commit, with one commit ahead.

        Returns:
            ``(repository, landed commit, branch commit)``.

        """
        git(repository=tmp_path, arguments=['init', '--quiet'])
        (tmp_path / 'README').write_text('one\n', encoding='utf-8')
        git(repository=tmp_path, arguments=['add', 'README'])
        git(repository=tmp_path, arguments=['commit', '--quiet', '-m', 'One'])
        landed = git(repository=tmp_path, arguments=['rev-parse', 'HEAD']).strip()
        git(repository=tmp_path, arguments=['update-ref', 'refs/remotes/origin/main', landed])
        (tmp_path / 'README').write_text('two\n', encoding='utf-8')
        git(repository=tmp_path, arguments=['commit', '--quiet', '-am', 'Two'])
        branch = git(repository=tmp_path, arguments=['rev-parse', 'HEAD']).strip()
        return tmp_path, landed, branch

    def history_row(self, *, commit, measured_at='2026-10-20T10:00:00+00:00'):
        """Return a row of a run the recording held.

        Returns:
            The row.

        """
        return ledger_row(commit=commit, measured_at=measured_at).model_copy(
            update={'origin': LedgerOrigin.RECORDING}
        )

    def written(self, *, rows, repository, held_keys=frozenset(), origin_main_present=True):
        """Return ``rows_to_write``'s rows in a stand-in project landing on origin/main.

        Returns:
            The rows.

        """
        return rows_to_write(
            rows=rows,
            held_keys=set(held_keys),
            repository=repository,
            origin_main_present=origin_main_present,
            settings=STAND_IN_SETTINGS,
        )

    def test_a_history_run_measured_on_a_landed_commit_is_written(self, landed_repository):
        repository, landed, _ = landed_repository
        newest = ledger_row(measured_at='2026-10-25T10:00:00+00:00')
        history = self.history_row(commit=landed)

        assert self.written(rows=[newest, history], repository=repository) == [newest, history]

    def test_a_history_run_measured_on_a_commit_not_on_origin_main_is_not(self, landed_repository):
        repository, _, branch = landed_repository
        newest = ledger_row(measured_at='2026-10-25T10:00:00+00:00')

        written = self.written(
            rows=[newest, self.history_row(commit=branch)], repository=repository
        )

        assert written == [newest]

    def test_a_history_run_with_uncommitted_changes_is_not_written(self, landed_repository):
        repository, landed, _ = landed_repository
        dirty = self.history_row(commit=landed)
        dirty = dirty.model_copy(update={'run': with_uncommitted_changes(dirty.run)})
        newest = ledger_row(measured_at='2026-10-25T10:00:00+00:00')

        assert self.written(rows=[newest, dirty], repository=repository) == [newest]

    def test_a_history_run_of_an_unknown_commit_is_not_written(self, landed_repository):
        repository, _, _ = landed_repository
        newest = ledger_row(measured_at='2026-10-25T10:00:00+00:00')

        written = self.written(rows=[newest, self.history_row(commit=None)], repository=repository)

        assert written == [newest]

    def test_without_origin_main_no_history_run_is_written(self, landed_repository):
        repository, landed, _ = landed_repository
        newest = ledger_row(measured_at='2026-10-25T10:00:00+00:00')

        written = self.written(
            rows=[newest, self.history_row(commit=landed)],
            repository=repository,
            origin_main_present=False,
        )

        assert written == [newest]

    def test_a_run_held_under_a_moved_recordings_old_path_is_not_written_again(
        self, landed_repository
    ):
        repository, landed, _ = landed_repository
        held = ledger_row(recording=OLD_RALLY_PATH, commit=landed)
        again = ledger_row(recording=NEW_RALLY_PATH, commit=landed)
        newest = ledger_row(recording=NEW_RALLY_PATH, measured_at='2026-10-25T10:00:00+00:00')

        written = self.written(
            rows=[newest, again],
            repository=repository,
            held_keys={held.held_key(recording_renames=STAND_IN_SETTINGS.recording_renames)},
        )

        assert written == [newest]

    def test_the_landed_ref_is_the_projects_own(self, landed_repository):
        """A project landing on another ref: what landed is judged by that ref, not origin/main."""
        repository, _, branch = landed_repository
        git(repository=repository, arguments=['update-ref', 'refs/remotes/upstream/trunk', branch])
        newest = ledger_row(measured_at='2026-10-25T10:00:00+00:00')
        history = self.history_row(commit=branch)

        written = rows_to_write(
            rows=[newest, history],
            held_keys=set(),
            repository=repository,
            origin_main_present=True,
            settings=ProjectSettings(landed_ref='upstream/trunk'),
        )

        assert written == [newest, history]
        assert self.written(rows=[newest, history], repository=repository) == [newest]


class TestHistoryRunsInThePendingFile:
    """The pending file is published too: it takes the same landed history runs as row files."""

    def measure_into_pending(self, *, tmp_path, game: StandInGame, golden: Path):
        """Measure the stand-in golden into a pending file (no rows directory).

        The golden holds one history run with a commit: the stand-in's paced live run.

        Returns:
            The pending rows.

        """
        project_root = tmp_path / 'project'
        measure.measure(
            settings=measure_settings(
                project_root=project_root,
                pending=tmp_path / 'pending.jsonl',
                revision=clean_revision(),
            ),
            recordings=copied_golden(project_root=project_root, game=game, golden=golden),
            published_text='',
        )
        return read_ledger_file(path=tmp_path / 'pending.jsonl').rows

    def test_a_history_run_on_a_commit_not_on_origin_main_is_not_appended(
        self, tmp_path, capsys, stand_in_game, stand_in_golden
    ):
        rows = self.measure_into_pending(
            tmp_path=tmp_path, game=stand_in_game, golden=stand_in_golden
        )

        assert [row.origin for row in rows] == [LedgerOrigin.REPLAY_METRICS]
        assert capsys.readouterr().out.count('origin/main') == 1

    def test_a_history_run_on_a_commit_on_origin_main_is_appended(
        self, mocker, tmp_path, stand_in_game, stand_in_golden
    ):
        mocker.patch.object(measure, 'landed_ref_exists', return_value=True)
        mocker.patch.object(measure, 'commit_has_landed', return_value=True)

        rows = self.measure_into_pending(
            tmp_path=tmp_path, game=stand_in_game, golden=stand_in_golden
        )

        assert LedgerOrigin.RECORDING in {row.origin for row in rows}


class TestMeasuring:
    """Each recording is rebaselined into a temporary file and its runs become pending rows."""

    @pytest.fixture(autouse=True)
    def history_has_landed(self, mocker):
        """Treat every recorded run as landed (the landed rules have their own tests above)."""
        mocker.patch.object(measure, 'landed_ref_exists', return_value=True)
        mocker.patch.object(measure, 'commit_has_landed', return_value=True)

    def golden_runs_with_a_commit(self, *, golden: Path):
        """Return how many runs a golden holds that name a commit (the others are not landed).

        Returns:
            The count.

        """
        runs = read_trace(path=golden)[MEASUREMENT_RUNS_HEADER_FIELD]
        return sum(1 for run in runs if run.get('source_revision'))

    def test_a_measurement_appends_rows_and_a_second_one_skips(
        self, tmp_path, capsys, stand_in_game, stand_in_golden
    ):
        project_root = tmp_path / 'project'
        recordings = copied_golden(
            project_root=project_root, game=stand_in_game, golden=stand_in_golden
        )
        ledger_name = member_golden_ledger_name(game=stand_in_game)
        frame_count = len(read_trace(path=stand_in_golden)[FRAMES_FIELD])
        pending = tmp_path / 'pending.jsonl'
        revision = clean_revision()

        result = measure.measure(
            settings=measure_settings(
                project_root=project_root, pending=pending, revision=revision
            ),
            recordings=recordings,
            published_text='',
        )

        assert result.exit_code == ExitCode.SUCCESS
        rows = read_ledger_file(path=pending).rows
        measured, recorded, *older_recorded = rows
        assert measured.origin == LedgerOrigin.REPLAY_METRICS
        assert measured.recording == ledger_name
        assert measured.console_script == stand_in_game.console_script
        assert measured.commit == revision.commit
        assert measured.rebaseline_exit == ExitCode.SUCCESS.describe()
        # The stand-in is deterministic and was recorded on this code: its rebaseline changes no
        # frame
        assert measured.frames_changed == 0
        assert measured.summary is not None
        assert not measured.run.processing_paced
        assert measured.run.machine_state is not None
        # The golden's one older run: the stand-in's paced live run
        assert recorded.origin == LedgerOrigin.RECORDING
        assert recorded.run.processing_paced
        # One recorded row per run the golden holds, the measurement on top
        assert len(older_recorded) + 1 == self.golden_runs_with_a_commit(golden=stand_in_golden)
        assert f'{ledger_name}: {frame_count} frames' in capsys.readouterr().out

        again = measure.measure(
            settings=measure_settings(
                project_root=project_root, pending=pending, revision=revision
            ),
            recordings=recordings,
            published_text='',
        )
        assert again.measured == ()
        assert again.skipped == (ledger_name,)
        assert 'already measured' in capsys.readouterr().out
        assert read_ledger_file(path=pending).rows == rows

        forced = measure.measure(
            settings=measure_settings(
                project_root=project_root, pending=pending, revision=revision
            ).model_copy(update={'force': True}),
            recordings=recordings,
            published_text=ledger_text(rows=rows),
        )
        # The recording's own run is already known: only the new measurement is appended
        assert len(forced.measured) == 1
        assert len(read_ledger_file(path=pending).rows) == len(rows) + 1

    def test_a_measured_change_counts_the_frames_the_newest_run_changed(
        self, tmp_path, stand_in_game, stand_in_golden
    ):
        """The measured row's frames_changed is the newest pair's, not an older pair's.

        The newest pair is the measurement against the golden's newest run.

        The golden holds two runs: the stand-in's live run, and a rebaseline of it (the newest).
        Their stored content hashes are altered as if the code had drawn frames differently: the
        newest run's at one frame, the live run's at that frame (to another value) and the next.
        The measurement (deterministic, the stand-in as recorded) then differs from the newest run
        in 1 frame, while the newest run differs from the live run in 2: a row taking the older
        pair's count, or none, fails.
        """
        rebaselined = tmp_path / 'rebaselined.jsonl.gz'
        completed = rebaseline_recording_headless(
            console_script=stand_in_game.console_script, path=stand_in_golden, new_path=rebaselined
        )
        assert completed.returncode == ExitCode.SUCCESS, completed.stdout
        mark_runs_from_a_clean_checkout(path=rebaselined)

        def change_the_stored_runs(trace: dict) -> None:
            frames = trace[FRAMES_FIELD]
            for run_index, positions, digit in ((0, (5,), 'a'), (1, (5, 6), 'b')):
                for position in positions:
                    hashes = frames[position][CONTENT_HASH_FIELD]
                    hashes[run_index] = digit * len(hashes[run_index])

        rewrite_recording(recording_path=rebaselined, change=change_the_stored_runs)
        project_root = tmp_path / 'project'
        recordings = copied_golden(
            project_root=project_root, game=stand_in_game, golden=rebaselined
        )
        pending = tmp_path / 'pending.jsonl'

        result = measure.measure(
            settings=measure_settings(
                project_root=project_root, pending=pending, revision=clean_revision()
            ),
            recordings=recordings,
            published_text='',
        )

        assert result.exit_code == ExitCode.SUCCESS
        measured = read_ledger_file(path=pending).rows[0]
        assert measured.origin == LedgerOrigin.REPLAY_METRICS
        # The newest pair (the measurement against the newest stored run): frame 5 only; the
        # older pair (the newest stored run against the live run): frames 5 and 6
        assert measured.frames_changed == 1

    def test_a_published_measurement_counts_as_measured(
        self, tmp_path, stand_in_game, stand_in_golden
    ):
        project_root = tmp_path / 'project'
        recordings = copied_golden(
            project_root=project_root, game=stand_in_game, golden=stand_in_golden
        )
        revision = clean_revision()
        assert revision.commit is not None
        # Measured on this machine (its label is the platform when no machine state is known)
        published_run = ledger_row(commit=revision.commit).run.model_copy(
            update={'machine_state': None, 'machine': measure.this_machine()}
        )
        published = ledger_row(recording=member_golden_ledger_name(game=stand_in_game)).model_copy(
            update={'run': published_run}
        )
        result = measure.measure(
            settings=measure_settings(
                project_root=project_root, pending=tmp_path / 'pending.jsonl', revision=revision
            ),
            recordings=recordings,
            published_text=ledger_text(rows=[published]),
        )
        assert result.skipped == (member_golden_ledger_name(game=stand_in_game),)

    def test_uncommitted_changes_are_refused_unless_allowed(
        self, tmp_path, capsys, stand_in_game, stand_in_golden
    ):
        project_root = tmp_path / 'project'
        recordings = copied_golden(
            project_root=project_root, game=stand_in_game, golden=stand_in_golden
        )
        pending = tmp_path / 'pending.jsonl'
        dirty = clean_revision().model_copy(update={'uncommitted_changes': True})
        refused = measure.measure(
            settings=measure_settings(project_root=project_root, pending=pending, revision=dirty),
            recordings=recordings,
            published_text='',
        )
        assert refused.exit_code == ExitCode.OPTIONS_REFUSED
        assert "the game's checkout has uncommitted changes" in capsys.readouterr().err
        assert not pending.exists()

        allowed = measure.measure(
            settings=measure_settings(
                project_root=project_root, pending=pending, revision=dirty
            ).model_copy(update={'allow_dirty': True}),
            recordings=recordings,
            published_text='',
        )
        assert allowed.exit_code == ExitCode.SUCCESS
        measured = read_ledger_file(path=pending).rows[0]
        assert measured.allowed_uncommitted_changes

    def test_an_unknown_commit_is_refused_unless_allowed(self, tmp_path, capsys):
        """The controller's ruling (Task D3): refused as uncommitted changes are."""
        settings = measure_settings(
            project_root=tmp_path,
            pending=tmp_path / 'pending.jsonl',
            revision=SourceRevision(source=RevisionSource.UNKNOWN),
        )

        refused = measure.measure(settings=settings, recordings=[], published_text='')
        refusal = capsys.readouterr().err
        allowed = measure.measure(
            settings=settings.model_copy(update={'allow_dirty': True}),
            recordings=[],
            published_text='',
        )

        assert refused.exit_code == ExitCode.OPTIONS_REFUSED
        assert 'not a git checkout' in refusal
        assert allowed.exit_code == ExitCode.SUCCESS
        assert 'at an unknown commit' in capsys.readouterr().out

    def test_failures_are_reported_and_measured_rows_kept(
        self, tmp_path, capsys, stand_in_game, stand_in_golden
    ):
        project_root = tmp_path / 'project'
        recordings = copied_golden(
            project_root=project_root, game=stand_in_game, golden=stand_in_golden
        )
        # A second recording of the stand-in's, which fails: not a recording at all
        broken = recordings[0][1].with_name('broken.jsonl.gz')
        broken.write_text('not a recording', encoding='utf-8')
        pending = tmp_path / 'pending.jsonl'
        result = measure.measure(
            settings=measure_settings(
                project_root=project_root, pending=pending, revision=clean_revision()
            ),
            recordings=[(stand_in_game.console_script, broken), *recordings],
            published_text='',
        )
        assert result.exit_code == ExitCode.INTERNAL_ERROR
        assert result.failures == (
            f'src/games/{stand_in_game.distribution}/tests/fixtures/replays/broken.jsonl.gz',
        )
        assert 'UNUSABLE_INPUT' in capsys.readouterr().err
        assert len(read_ledger_file(path=pending).rows) == 1 + self.golden_runs_with_a_commit(
            golden=stand_in_golden
        )

    def test_a_recording_with_no_ledger_name_is_a_failure_and_the_others_are_measured(
        self, tmp_path, capsys, stand_in_game, stand_in_golden
    ):
        """A PATH outside the project that is no bundled demo: one line, and why."""
        project_root = tmp_path / 'project'
        recordings = copied_golden(
            project_root=project_root, game=stand_in_game, golden=stand_in_golden
        )
        outside = tmp_path / 'elsewhere' / 'run.jsonl.gz'

        result = measure.measure(
            settings=measure_settings(
                project_root=project_root,
                pending=tmp_path / 'pending.jsonl',
                revision=clean_revision(),
            ),
            recordings=[(stand_in_game.console_script, outside), *recordings],
            published_text='',
        )

        assert result.exit_code == ExitCode.INTERNAL_ERROR
        assert result.failures == (outside.as_posix(),)
        assert 'neither in the project' in capsys.readouterr().err
        assert result.measured == (member_golden_ledger_name(game=stand_in_game),)

    def test_a_replay_of_another_commit_is_a_failure(
        self, tmp_path, capsys, stand_in_game, stand_in_golden
    ):
        project_root = tmp_path / 'project'
        recordings = copied_golden(
            project_root=project_root, game=stand_in_game, golden=stand_in_golden
        )
        other_commit = clean_revision().model_copy(update={'commit': 'f' * 40})
        result = measure.measure(
            settings=measure_settings(
                project_root=project_root, pending=tmp_path / 'pending.jsonl', revision=other_commit
            ),
            recordings=recordings,
            published_text='',
        )
        assert result.exit_code == ExitCode.INTERNAL_ERROR
        assert "not the game's" in capsys.readouterr().err


class TestClearingPublishedRows:
    """After a publish, pending rows the published ledger now holds are removed."""

    def test_published_rows_leave_the_pending_file(self, tmp_path, capsys):
        pending = tmp_path / 'pending.jsonl'
        published_row = ledger_row()
        unpublished_row = ledger_row(measured_at='2026-10-24T09:00:00+00:00')
        pending.write_text(ledger_text(rows=[published_row, unpublished_row]), encoding='utf-8')
        clear_published(pending_path=pending, published_text=ledger_text(rows=[published_row]))
        assert read_ledger_file(path=pending).rows == (unpublished_row,)
        assert '1 published row removed, 1 still pending' in capsys.readouterr().out
        clear_published(pending_path=pending, published_text=ledger_text(rows=[unpublished_row]))
        assert not pending.exists()
        clear_published(pending_path=pending, published_text='')
        assert 'No pending rows' in capsys.readouterr().out

    def test_rows_from_uncommitted_changes_stay_pending_after_a_publish(self, tmp_path):
        """A publish takes only clean rows, so the trial stays local and pending."""
        pending = tmp_path / 'pending.jsonl'
        clean = ledger_row()
        trial = ledger_row(measured_at='2026-10-24T09:00:00+00:00').model_copy(
            update={'allowed_uncommitted_changes': True}
        )
        pending.write_text(ledger_text(rows=[clean, trial]), encoding='utf-8')
        # What a gh-deploy build published (performance_pages.merged_ledger, through
        # scripts/generate_performance_graphs.py)
        published = ledger_text(rows=publishable_rows(rows=[clean, trial]))
        clear_published(pending_path=pending, published_text=published)
        assert read_ledger_file(path=pending).rows == (trial,)


class TestWhatIsMissing:
    """``missing_measurements``: what ``measure`` would measure (and ``unmeasured`` lists)."""

    def here(self, *, recording: str, commit: str | None, code_tree: str | None = None):
        """Return a row measured on this machine.

        Returns:
            The row.

        """
        row = ledger_row(recording=recording, commit=commit)
        return row.model_copy(
            update={
                'code_tree': code_tree,
                'run': row.run.model_copy(
                    update={'machine_state': None, 'machine': measure.this_machine()}
                ),
            }
        )

    def test_by_code_tree_only_that_trees_rows_on_this_machine_count(self):
        rows = [self.here(recording='a.jsonl.gz', commit='c' * 40, code_tree=TREE)]
        machine = measure.this_machine()

        assert missing_measurements(
            rows=rows, recordings=['a.jsonl.gz', 'b.jsonl.gz'], code_tree=TREE, machine=machine
        ) == ['b.jsonl.gz']
        assert missing_measurements(
            rows=rows, recordings=['a.jsonl.gz'], code_tree=OTHER_TREE, machine=machine
        ) == ['a.jsonl.gz']
        assert missing_measurements(
            rows=rows, recordings=['a.jsonl.gz'], code_tree=TREE, machine='Another Machine'
        ) == ['a.jsonl.gz']

    def test_by_commit_a_row_of_that_commit_counts_and_an_unknown_commit_never(self):
        commit = 'c' * 40
        rows = [self.here(recording='a.jsonl.gz', commit=commit)]
        machine = measure.this_machine()

        assert not missing_measurements(
            rows=rows, recordings=['a.jsonl.gz'], code_tree=None, machine=machine, commit=commit
        )
        assert missing_measurements(
            rows=rows, recordings=['a.jsonl.gz'], code_tree=None, machine=machine, commit='d' * 40
        ) == ['a.jsonl.gz']
        assert missing_measurements(
            rows=rows, recordings=['a.jsonl.gz'], code_tree=None, machine=machine, commit=None
        ) == ['a.jsonl.gz']


class TestUnclaimedGoldens:
    """A golden none of the measured games replays is reported, with why (never silently left)."""

    def test_a_member_that_is_not_installed_names_the_distribution_looked_for(self, tmp_path):
        """A plain `uv sync` uninstalls the members: one line naming the distribution looked for."""
        write_uninstalled_member(project_root=tmp_path)

        [unclaimed] = unclaimed_goldens(
            games=['a-game'],
            settings=ProjectSettings(golden_globs=(MEMBER_GOLDEN_GLOB,)),
            project_root=tmp_path,
        )

        golden = tmp_path / UNINSTALLED_MEMBER_GOLDEN
        assert unclaimed.path == golden
        assert 'no distribution of that name is installed' in unclaimed.reason
        assert "'glitchygames-not-installed-game'" in unclaimed.reason
        assert '\n' not in unclaimed.reason
        assert str(golden) not in unclaimed.reason

    def test_a_golden_of_a_game_not_measured_says_so_and_a_bookmarked_copy_is_no_golden(
        self, tmp_path, monkeypatch
    ):
        installed = tmp_path / 'site-packages'
        write_stand_in_distribution(
            directory=installed,
            distribution='stand-in-games',
            console_scripts={
                'stand-in-rally': 'stand_in_rally:main',
                'stand-in-tower': 'stand_in_tower:main',
            },
        )
        monkeypatch.syspath_prepend(installed)
        fixtures = tmp_path.joinpath(*GOLDEN_DIRECTORY_PARTS)
        rally = fixtures / 'stand-in-rally' / 'golden.jsonl.gz'
        tower = fixtures / 'stand-in-tower' / 'golden-tower.jsonl.gz'
        for golden in (rally, tower):
            write_stand_in_recording(path=golden, frame_count=STAND_IN_RECORDING_FRAMES)
        bookmarked = tower.with_name('golden-tower.bookmarked.jsonl.gz')
        write_bookmarked_copy(recording_path=tower, bookmarks=[1], destination=bookmarked)
        assert is_bookmarked_copy(path=bookmarked)

        unclaimed = unclaimed_goldens(
            games=['stand-in-rally'], settings=ProjectSettings(), project_root=tmp_path
        )

        assert unclaimed == [
            UnreplayableRecording(
                path=tower,
                reason=(
                    'replayed by stand-in-tower, which is not one of the games measured '
                    '([tool.glitchygames] games)'
                ),
            )
        ]


def test_a_run_over_several_games_exits_with_its_first_failure():
    """``combined_exit_code``: the first failure's own code; a signal's status is internal."""
    assert combined_exit_code(statuses=[]) == ExitCode.SUCCESS
    assert combined_exit_code(statuses=[0, 0]) == ExitCode.SUCCESS
    assert combined_exit_code(statuses=[0, 64, 70]) == ExitCode.OPTIONS_REFUSED
    assert combined_exit_code(statuses=[-9, 64]) == ExitCode.INTERNAL_ERROR


def test_a_directory_in_the_local_directory_is_made_through_its_helper(tmp_path):
    """Under .glitchygames/ the helper writes the .gitignore first; elsewhere nothing extra."""
    nested = ensure_directory(
        directory=tmp_path / LOCAL_DIRECTORY_NAME / 'ledger', project_root=tmp_path
    )
    elsewhere = ensure_directory(directory=tmp_path / 'replay-ledger', project_root=tmp_path)

    assert nested.is_dir()
    assert (tmp_path / LOCAL_DIRECTORY_NAME / GITIGNORE_FILE_NAME).read_text(
        encoding='utf-8'
    ) == LOCAL_DIRECTORY_GITIGNORE
    assert elsewhere.is_dir()
    assert not (elsewhere / GITIGNORE_FILE_NAME).exists()


# The front ends: --measure, --unmeasured and --clear-published on a game, and the command


def write_stand_in_project(
    *, project_root: Path, game: StandInGame, games: tuple[str, ...] = (), goldens=()
) -> Path:
    """Write a project naming the stand-in game, its pending ledger ``STAND_IN_PENDING_LEDGER``.

    Args:
        project_root: Where.
        game: The stand-in game (``games``, first).
        games: More console scripts for ``games``.
        goldens: Recordings copied in as the game's goldens
            (``tests/fixtures/replays/<console-script>/``).

    Returns:
        The project's root.

    """
    project_root.mkdir(parents=True, exist_ok=True)
    named = ', '.join(repr(name) for name in (game.console_script, *games))
    (project_root / 'pyproject.toml').write_text(
        f'[project]\nname = "stand-in-project"\n\n[tool.glitchygames]\ngames = [{named}]\n'
        f'pending-ledger = {STAND_IN_PENDING_LEDGER!r}\n',
        encoding='utf-8',
    )
    directory = project_root.joinpath(*GOLDEN_DIRECTORY_PARTS, game.console_script)
    for golden in goldens:
        directory.mkdir(parents=True, exist_ok=True)
        shutil.copy(golden, directory / golden.name)
    return project_root


def stand_in_golden_ledger_name(*, game: StandInGame, name: str = 'golden.jsonl.gz') -> str:
    """Return a golden's ledger name in ``write_stand_in_project``'s layout.

    Returns:
        The name.

    """
    return '/'.join((*GOLDEN_DIRECTORY_PARTS, game.console_script, name))


def run_game_flag(
    *, game: StandInGame, arguments: list[str], working_directory: Path
) -> tuple[int, str]:
    """Run the stand-in game in a child with a tool flag.

    Returns:
        The child's exit status and its output (standard output and error together).

    """
    completed = run_command(
        command=[
            sys.executable,
            '-c',
            f'import {game.package}; {game.package}.main()',
            '--log-level',
            'info',
            '--resolution',
            STAND_IN_GAME_RESOLUTION,
            '--headless',
            *arguments,
        ],
        environment=os.environ,
        timeout_seconds=RECORD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=working_directory,
    )
    return completed.returncode, completed.stdout or ''


def measured_recordings(*, project_root: Path) -> list[str]:
    """Return the recordings of the measurement rows in a stand-in project's pending ledger.

    Returns:
        Their ledger names, in order.

    """
    return [
        row.recording
        for row in read_ledger_file(path=project_root / STAND_IN_PENDING_LEDGER).rows
        if row.origin == LedgerOrigin.REPLAY_METRICS
    ]


def test_measure_a_stand_in_game_as_a_flag_and_a_command(
    tmp_path, capfd, stand_in_game, stand_in_golden
):
    """Both front ends rebaseline the game's golden into its [tool.glitchygames] pending ledger.

    The flag measures it once; again, it is already measured; the command with ``--force``
    measures it again through the game's own ``--measure``. Each row names the golden by its
    project path, and the game's console script and commit.
    """
    project = write_stand_in_project(
        project_root=tmp_path / 'project', game=stand_in_game, goldens=(stand_in_golden,)
    )
    golden = stand_in_golden_ledger_name(game=stand_in_game)

    flag_status, flag_output = run_game_flag(
        game=stand_in_game, arguments=['--measure'], working_directory=project
    )
    again_status, again_output = run_game_flag(
        game=stand_in_game, arguments=['--measure'], working_directory=project
    )
    flag_rows = read_ledger_file(path=project / STAND_IN_PENDING_LEDGER).rows
    capfd.readouterr()
    command_status = command.main(['measure', '--force', '--project-root', str(project)])

    assert flag_status == ExitCode.SUCCESS, flag_output
    assert f'{golden}: ' in flag_output
    assert 'Measured 1 recording at' in flag_output
    assert again_status == ExitCode.SUCCESS, again_output
    assert f'{golden}: already measured' in again_output
    (measured,) = [row for row in flag_rows if row.origin == LedgerOrigin.REPLAY_METRICS]
    assert measured.recording == golden
    assert measured.console_script == stand_in_game.console_script
    assert measured.commit == clean_revision().commit
    assert not measured.allowed_uncommitted_changes
    assert command_status == ExitCode.SUCCESS
    command_output = capfd.readouterr()
    assert f'running {stand_in_game.console_script}' in command_output.err
    assert 'Measured 1 recording at' in command_output.out
    assert measured_recordings(project_root=project) == [golden, golden]


def test_unmeasured_lists_then_empties(tmp_path, capsys, stand_in_game, stand_in_golden):
    """Both front ends list the golden until it is measured, then nothing (for a code tree too)."""
    project = write_stand_in_project(
        project_root=tmp_path / 'project', game=stand_in_game, goldens=(stand_in_golden,)
    )
    golden = stand_in_golden_ledger_name(game=stand_in_game)
    by_tree = ['--code-tree', TREE, '--rows-directory', str(tmp_path / 'replay-ledger')]

    def listed_by_both(*, arguments: list[str]) -> tuple[list[str], list[str]]:
        flag_status, flag_output = run_game_flag(
            game=stand_in_game, arguments=['--unmeasured', *arguments], working_directory=project
        )
        assert flag_status == ExitCode.SUCCESS, flag_output
        capsys.readouterr()
        command_status = command.main(['unmeasured', *arguments, '--project-root', str(project)])
        assert command_status == ExitCode.SUCCESS
        command_lines = capsys.readouterr().out.splitlines()
        return [line for line in flag_output.splitlines() if line == golden], command_lines

    assert listed_by_both(arguments=[]) == ([golden], [golden])
    assert listed_by_both(arguments=by_tree) == ([golden], [golden])

    status, output = run_game_flag(
        game=stand_in_game, arguments=['--measure'], working_directory=project
    )
    assert status == ExitCode.SUCCESS, output
    assert listed_by_both(arguments=[]) == ([], [])
    # By code tree only that tree's rows count: none yet
    assert listed_by_both(arguments=by_tree) == ([golden], [golden])
    status, output = run_game_flag(
        game=stand_in_game, arguments=['--measure', *by_tree], working_directory=project
    )
    assert status == ExitCode.SUCCESS, output
    assert listed_by_both(arguments=by_tree) == ([], [])


def test_measure_in_a_project_without_settings_creates_the_ledger_directory(
    tmp_path, stand_in_game, stand_in_golden
):
    """No pyproject at all: the defaults. The pending ledger goes in .glitchygames/, gitignored."""
    project = tmp_path / 'player'
    goldens = project.joinpath(*GOLDEN_DIRECTORY_PARTS, stand_in_game.console_script)
    goldens.mkdir(parents=True)
    shutil.copy(stand_in_golden, goldens / 'run.jsonl.gz')
    local_directory = project / LOCAL_DIRECTORY_NAME

    status, output = run_game_flag(
        game=stand_in_game, arguments=['--measure'], working_directory=project
    )

    assert status == ExitCode.SUCCESS, output
    assert 'measure: no pyproject.toml in' in output
    assert (local_directory / GITIGNORE_FILE_NAME).read_text(
        encoding='utf-8'
    ) == LOCAL_DIRECTORY_GITIGNORE
    rows = read_ledger_file(path=project / ProjectSettings().pending_ledger).rows
    assert [row.recording for row in rows if row.origin == LedgerOrigin.REPLAY_METRICS] == [
        stand_in_golden_ledger_name(game=stand_in_game, name='run.jsonl.gz')
    ]


def test_measure_from_inside_a_member_writes_the_roots_ledger(
    tmp_path, stand_in_game, stand_in_golden
):
    """A member without [tool.glitchygames] belongs to the root that has it (the D5 ruling)."""
    project = write_stand_in_project(
        project_root=tmp_path / 'workspace', game=stand_in_game, goldens=(stand_in_golden,)
    )
    member = project / 'src' / 'games' / 'member'
    member.mkdir(parents=True)
    (member / 'pyproject.toml').write_text('[project]\nname = "member"\n', encoding='utf-8')

    status, output = run_game_flag(
        game=stand_in_game, arguments=['--measure'], working_directory=member
    )

    assert status == ExitCode.SUCCESS, output
    assert not (member / STAND_IN_PENDING_LEDGER).exists()
    assert not (member / LOCAL_DIRECTORY_NAME).exists()
    assert measured_recordings(project_root=project) == [
        stand_in_golden_ledger_name(game=stand_in_game)
    ]


def test_the_games_own_revision_is_refused_when_dirty_or_unknown_unless_allowed(
    tmp_path, stand_in_game, stand_in_golden
):
    """The game's revision decides (the D3 ruling), not the engine's: both cases, both ends.

    Restamped with uncommitted changes the game is refused, skipped with --skip-dirty, and
    measured as a trial with --allow-dirty; with its stamp removed (in no checkout, so its
    commit is unknown) it is refused alike, and measured with --allow-dirty, its row naming no
    commit.
    """
    project = write_stand_in_project(
        project_root=tmp_path / 'project', game=stand_in_game, goldens=(stand_in_golden,)
    )
    stamp_stand_in_game(
        game=stand_in_game,
        revision=clean_revision().model_copy(update={'uncommitted_changes': True}),
    )

    dirty_status, dirty_output = run_game_flag(
        game=stand_in_game, arguments=['--measure'], working_directory=project
    )
    dirty_command = command.main(['measure', '--project-root', str(project)])
    skip_status, skip_output = run_game_flag(
        game=stand_in_game, arguments=['--measure', '--skip-dirty'], working_directory=project
    )
    trial_status, trial_output = run_game_flag(
        game=stand_in_game, arguments=['--measure', '--allow-dirty'], working_directory=project
    )
    (stand_in_game.install_directory / stand_in_game.package / BUILD_STAMP_FILE_NAME).unlink()
    unknown_status, unknown_output = run_game_flag(
        game=stand_in_game, arguments=['--measure'], working_directory=project
    )
    unknown_command = command.main(['measure', '--project-root', str(project)])
    allowed_status, allowed_output = run_game_flag(
        game=stand_in_game, arguments=['--measure', '--allow-dirty'], working_directory=project
    )

    assert dirty_status == ExitCode.OPTIONS_REFUSED
    assert "the game's checkout has uncommitted changes" in dirty_output
    assert dirty_command == ExitCode.OPTIONS_REFUSED
    assert skip_status == ExitCode.SUCCESS, skip_output
    assert 'Not measuring the replays' in skip_output
    assert trial_status == ExitCode.SUCCESS, trial_output
    assert unknown_status == ExitCode.OPTIONS_REFUSED
    assert 'not a git checkout, so its commit is unknown' in unknown_output
    assert unknown_command == ExitCode.OPTIONS_REFUSED
    assert allowed_status == ExitCode.SUCCESS, allowed_output
    assert 'at an unknown commit' in allowed_output
    trial, unknown = [
        row
        for row in read_ledger_file(path=project / STAND_IN_PENDING_LEDGER).rows
        if row.origin == LedgerOrigin.REPLAY_METRICS
    ]
    assert trial.allowed_uncommitted_changes
    assert trial.commit == clean_revision().commit
    assert unknown.allowed_uncommitted_changes
    assert unknown.commit is None


def test_measure_refuses_a_random_seed_on_both_front_ends(
    tmp_path, capsys, stand_in_game, stand_in_golden
):
    """Each recording is rebaselined under its own seed (decision 17): a seed is refused."""
    project = write_stand_in_project(
        project_root=tmp_path / 'project', game=stand_in_game, goldens=(stand_in_golden,)
    )

    flag_status, flag_output = run_game_flag(
        game=stand_in_game, arguments=['--random-seed', '7', '--measure'], working_directory=project
    )
    statuses = [
        command.main(['measure', '--random-seed', '7', '--project-root', str(project)]),
        command.main(['measure', '--project-root', str(project), '--', '--random-seed', '7']),
    ]

    assert flag_status == ExitCode.OPTIONS_REFUSED
    assert '--random-seed is refused' in flag_output
    assert statuses == [ExitCode.OPTIONS_REFUSED, ExitCode.OPTIONS_REFUSED]
    error = capsys.readouterr().err
    assert error.count('--random-seed is refused') == 2
    assert 'running' not in error
    assert measured_recordings(project_root=project) == []


def test_allow_dirty_and_skip_dirty_together_are_refused_on_both_front_ends(
    tmp_path, caplog, capsys
):
    """One mutually exclusive pair, refused before anything runs (the script's argparse did)."""
    flag_status = measure.measure_on_the_game(
        options={'measure': [], 'allow_dirty': True, 'skip_dirty': True},
        game=GameThatIsNeverBuilt,
    )
    command_status = command.main([
        'measure',
        '--allow-dirty',
        '--skip-dirty',
        '--project-root',
        str(tmp_path),
    ])

    assert flag_status == command_status == ExitCode.OPTIONS_REFUSED
    assert 'refused together' in caplog.text
    assert 'refused together' in capsys.readouterr().err


def test_the_hooks_command_line_writes_row_files_naming_the_tree(
    tmp_path, stand_in_game, stand_in_golden
):
    """``measure --allow-dirty --code-tree TREE --rows-directory DIR``, as the hook runs it."""
    project = write_stand_in_project(
        project_root=tmp_path / 'project', game=stand_in_game, goldens=(stand_in_golden,)
    )
    rows_directory = tmp_path / 'replay-ledger'

    status = command.main([
        'measure',
        '--allow-dirty',
        '--code-tree',
        TREE,
        '--rows-directory',
        str(rows_directory),
        '--project-root',
        str(project),
    ])

    assert status == ExitCode.SUCCESS
    assert {row.code_tree for row in read_row_files(directory=rows_directory)} == {TREE}
    assert measured_recordings(project_root=project) == []


def test_the_command_measures_named_recordings_with_their_game(
    tmp_path, capsys, stand_in_game, stand_in_golden
):
    """With PATHs: the header's game, or the one --game; a missing PATH fails on its own line."""
    project = write_stand_in_project(project_root=tmp_path / 'project', game=stand_in_game)
    recording = project / 'runs' / 'run.jsonl.gz'
    recording.parent.mkdir()
    shutil.copy(stand_in_golden, recording)
    missing = project / 'runs' / 'missing.jsonl.gz'
    root = ['--project-root', str(project)]

    by_header = command.main(['measure', str(missing), str(recording), *root])
    by_header_error = capsys.readouterr().err
    by_game = command.main([
        'measure',
        str(recording),
        '--force',
        '--game',
        stand_in_game.console_script,
        *root,
    ])
    two_games = command.main(['measure', str(recording), '--game', 'a', '--game', 'b', *root])
    unknown_game = command.main(['measure', str(recording), '--game', NO_SUCH_GAME, *root])

    assert by_header == ExitCode.MISSING_INPUT
    assert f'{missing.as_posix()}: no such recording' in by_header_error
    assert by_game == ExitCode.SUCCESS
    assert two_games == ExitCode.OPTIONS_REFUSED
    assert unknown_game == ExitCode.OPTIONS_REFUSED
    assert measured_recordings(project_root=project) == ['runs/run.jsonl.gz', 'runs/run.jsonl.gz']


def test_a_golden_no_game_replays_and_an_unknown_game_fail_and_the_others_are_measured(
    tmp_path, capsys, stand_in_game, stand_in_golden
):
    """The settings' games: an unclaimed golden is a failure line, an unknown game is refused."""
    project = write_stand_in_project(
        project_root=tmp_path / 'project',
        game=stand_in_game,
        games=(NO_SUCH_GAME,),
        goldens=(stand_in_golden,),
    )
    stray = project.joinpath(*GOLDEN_DIRECTORY_PARTS, 'not-a-game', 'golden.jsonl.gz')
    stray.parent.mkdir()
    shutil.copy(stand_in_golden, stray)

    status = command.main(['measure', '--project-root', str(project)])
    only_status = command.main(['measure', '--only', 'not-a-game', '--project-root', str(project)])

    error = capsys.readouterr().err
    assert status == ExitCode.INTERNAL_ERROR
    assert "tests/fixtures/replays/not-a-game/golden.jsonl.gz: the directory 'not-a-game'" in error
    assert NO_SUCH_GAME in error
    assert only_status == ExitCode.INTERNAL_ERROR
    assert measured_recordings(project_root=project) == [
        stand_in_golden_ledger_name(game=stand_in_game)
    ]


def test_the_unmeasured_command_reads_a_console_script_game_without_starting_it(
    tmp_path, mocker, capsys, stand_in_game, stand_in_golden
):
    """No child for a game named by its installed console script."""
    project = write_stand_in_project(
        project_root=tmp_path / 'project', game=stand_in_game, goldens=(stand_in_golden,)
    )
    started = mocker.spy(measure, 'child_unmeasured')

    status = command.main(['unmeasured', '--project-root', str(project)])

    assert status == ExitCode.SUCCESS
    started.assert_not_called()
    assert capsys.readouterr().out.splitlines() == [stand_in_golden_ledger_name(game=stand_in_game)]


@pytest.mark.parametrize('form', ['script', 'entry-point'])
def test_the_unmeasured_command_merges_the_list_of_a_game_named_another_way(
    tmp_path, capsys, form, stand_in_game, stand_in_golden
):
    """A script path or MODULE:CALLABLE game lists its own as a child; its list joins the parent's.

    So the command's standard output (what the pre-commit hook reads, redirected in its own
    process) holds every game's recordings, and the summary counts them; an unknown game beside
    it is refused, and the others still listed.
    """
    project = write_stand_in_project(
        project_root=tmp_path / 'project', game=stand_in_game, goldens=(stand_in_golden,)
    )
    script = project / 'script_game.py'
    script.write_text(
        f'import {stand_in_game.package}\n{stand_in_game.package}.main()\n', encoding='utf-8'
    )
    game = str(script) if form == 'script' else f'{stand_in_game.package}:main'
    golden = stand_in_golden_ledger_name(game=stand_in_game)

    status = command.main([
        'unmeasured',
        '--game',
        game,
        '--game',
        stand_in_game.console_script,
        '--game',
        NO_SUCH_GAME,
        '--project-root',
        str(project),
    ])

    output = capsys.readouterr()
    assert status == ExitCode.OPTIONS_REFUSED
    assert output.out.splitlines() == [golden, golden]
    assert 'glitchygames unmeasured: 2 of 2 recordings not measured' in output.err
    assert NO_SUCH_GAME in output.err


def test_a_game_no_console_script_starts_lists_and_measures_none_and_refuses_paths(
    tmp_path, mocker, monkeypatch, caplog, capsys
):
    """Its rows could name no console script: no recordings of its own, PATHs refused."""
    (tmp_path / 'pyproject.toml').write_text('', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    mocker.patch.object(measure, 'game_revision', return_value=clean_revision())
    options = {'measure': [], 'force': False, 'allow_dirty': False, 'skip_dirty': False}

    own = measure.measure_on_the_game(options=options, game=GameThatIsNeverBuilt)
    own_output = capsys.readouterr().out
    named = measure.measure_on_the_game(
        options={**options, 'measure': ['run.jsonl.gz']}, game=GameThatIsNeverBuilt
    )
    listed = measure.unmeasured_on_the_game(options={}, game=GameThatIsNeverBuilt)

    assert own == ExitCode.SUCCESS
    assert 'Measured 0 recordings' in own_output
    assert named == ExitCode.OPTIONS_REFUSED
    assert 'no console script starts this game' in caplog.text
    assert listed == ExitCode.SUCCESS
    assert '0 of 0 recordings not measured' in capsys.readouterr().err


def test_the_game_flag_measures_without_building_the_game(mocker, tmp_path, monkeypatch):
    """``--measure`` on a game runs while the engine is built: no pygame, no scene, its exit code.

    The rebaseline child is stood in for (it fails, so nothing is written); the game's other
    arguments reach it, measure's own do not.
    """
    from glitchygames.replay.tools.golden_traces import GoldenTraceEngine

    (tmp_path / 'pyproject.toml').write_text('', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    recording = tmp_path / 'run.jsonl.gz'
    recording.write_bytes(b'')
    mocker.patch.object(measure, 'game_revision', return_value=clean_revision())
    # A game a console script starts: the command's own will do
    mocker.patch.object(
        measure,
        'game_identity',
        return_value=console_script_identity(console_script='glitchygames'),
    )
    rebaselined = mocker.patch.object(
        measure,
        'rebaseline_recording_headless',
        return_value=CompletedProcess(args=[], returncode=ExitCode.UNUSABLE_INPUT, stdout='no\n'),
    )
    pygame_started = mocker.spy(pygame, 'init')
    mocker.patch.object(
        sys,
        'argv',
        ['the-game', '--target-fps', '30', '--measure', str(recording), '--only', 'run', '--force'],
    )

    with pytest.raises(SystemExit) as exit_information:
        GoldenTraceEngine(game=GameThatIsNeverBuilt)

    assert exit_information.value.code == ExitCode.INTERNAL_ERROR
    pygame_started.assert_not_called()
    (call,) = rebaselined.call_args_list
    assert call.kwargs['path'] == recording
    assert call.kwargs['game_arguments'] == ('--target-fps', '30')


def test_clear_published_on_both_front_ends(tmp_path, capsys, monkeypatch):
    """A publish took one pending row: both front ends remove it from the project's pending."""
    published = ledger_row()
    unpublished = ledger_row(measured_at='2026-10-24T09:00:00+00:00')
    clone = clone_with_published_ledger(
        tmp_path=tmp_path,
        ledger=ledger_text(rows=[published]),
        published_path=STAND_IN_PUBLISHED_LEDGER_PATH,
    )
    (clone / 'pyproject.toml').write_text(
        f'[tool.glitchygames]\npublished-ledger = {STAND_IN_PUBLISHED_LEDGER!r}\n'
        f'pending-ledger = {STAND_IN_PENDING_LEDGER!r}\n',
        encoding='utf-8',
    )
    pending = clone / STAND_IN_PENDING_LEDGER
    pending.parent.mkdir()

    def pend() -> None:
        """Write both rows into the pending ledger."""
        pending.write_text(ledger_text(rows=[published, unpublished]), encoding='utf-8')

    pend()
    monkeypatch.chdir(clone)
    flag_status = measure.clear_published_on_the_game(options={}, game=GameThatIsNeverBuilt)
    assert read_ledger_file(path=pending).rows == (unpublished,)
    pend()
    command_status = command.main(['clear-published', '--project-root', str(clone)])
    assert read_ledger_file(path=pending).rows == (unpublished,)
    other = tmp_path / 'other.jsonl'
    other.write_text(ledger_text(rows=[published]), encoding='utf-8')
    given_status = command.main([
        'clear-published',
        '--pending',
        str(other),
        '--project-root',
        str(clone),
    ])

    assert flag_status == command_status == given_status == ExitCode.SUCCESS
    assert not other.exists()
    assert capsys.readouterr().out.count('1 published row removed') == 3


def test_settings_that_cannot_be_read_refuse_each_tool(tmp_path, monkeypatch, capsys, caplog):
    """A ``[tool.glitchygames]`` that can't be read is unusable input, on both front ends."""
    (tmp_path / 'pyproject.toml').write_text('[tool.glitchygames]\nno-such-setting = 1\n')
    monkeypatch.chdir(tmp_path)

    statuses = [
        measure.measure_on_the_game(options={'measure': []}, game=GameThatIsNeverBuilt),
        measure.unmeasured_on_the_game(options={}, game=GameThatIsNeverBuilt),
        measure.clear_published_on_the_game(options={}, game=GameThatIsNeverBuilt),
        *(
            command.main([name, '--project-root', str(tmp_path)])
            for name in ('measure', 'unmeasured', 'clear-published')
        ),
    ]

    assert statuses == [ExitCode.UNUSABLE_INPUT] * 6
    assert "unknown setting 'no-such-setting'" in caplog.text
    assert capsys.readouterr().err.count("unknown setting 'no-such-setting'") == 4


def test_the_three_tools_are_each_one_tool_on_both_front_ends():
    """Measure takes PATHs and --game; unmeasured and clear-published take no value, run no game."""
    measuring = tool_named(name='measure')
    unmeasured = tool_named(name='unmeasured')
    clearing = tool_named(name='clear-published')

    assert [option.flag for option in measuring.options] == [
        '--force',
        '--allow-dirty',
        '--skip-dirty',
        '--only',
        '--code-tree',
        '--rows-directory',
        '--pending',
        '--random-seed',
    ]
    assert measuring.runs_game
    assert measuring.value_kind == 'paths'
    assert [option.flag for option in unmeasured.options] == [
        '--code-tree',
        '--rows-directory',
        '--pending',
    ]
    assert [option.flag for option in clearing.options] == ['--pending']
    assert not unmeasured.runs_game
    assert not clearing.runs_game
    assert unmeasured.value_kind == clearing.value_kind == 'flag'
    # One --only for verify and measure (the controller's note to Task D6)
    assert tool_named(name='verify').options[0] is measuring.options[3]


def test_the_game_flag_refuses_a_seed_and_skips_a_trial_before_finding_anything(
    tmp_path, mocker, caplog, capsys
):
    """In process: a seed is refused first; --skip-dirty on a trial measures nothing, says so."""
    mocker.patch.object(measure, 'verify_project_root', return_value=tmp_path)
    found = mocker.patch.object(measure, 'game_recordings')
    mocker.patch.object(
        measure,
        'game_revision',
        return_value=clean_revision().model_copy(update={'uncommitted_changes': True}),
    )

    seeded = measure.measure_on_the_game(
        options={'measure': [], 'random_seed': 7}, game=GameThatIsNeverBuilt
    )
    skipped = measure.measure_on_the_game(
        options={'measure': [], 'skip_dirty': True}, game=GameThatIsNeverBuilt
    )

    assert seeded == ExitCode.OPTIONS_REFUSED
    assert '--random-seed is refused' in caplog.text
    assert skipped == ExitCode.SUCCESS
    output = capsys.readouterr()
    assert 'Not measuring the replays' in output.out
    # No pyproject.toml where the project was looked for: the defaults, said once
    assert f'measure: no pyproject.toml in {tmp_path}' in output.err
    found.assert_not_called()


def test_the_game_flag_measures_its_own_recordings_that_only_keeps(tmp_path, mocker, monkeypatch):
    """No PATHs: the game's recordings; --only keeps those whose ledger name contains TEXT.

    A recording with no ledger name (outside the project, no demo) is kept, so measuring it
    says why it can't be.
    """
    (tmp_path / 'pyproject.toml').write_text('', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    mocker.patch.object(measure, 'game_revision', return_value=clean_revision())
    identity = console_script_identity(console_script='glitchygames')
    mocker.patch.object(measure, 'game_identity', return_value=identity)
    kept = tmp_path / 'tests' / 'fixtures' / 'replays' / 'rally.jsonl.gz'
    dropped = tmp_path / 'tests' / 'fixtures' / 'replays' / 'pong.jsonl.gz'
    outside = tmp_path.parent / 'elsewhere' / 'rally-outside.jsonl.gz'
    mocker.patch.object(
        measure,
        'game_recordings',
        return_value=[
            Recording(console_script='glitchygames', path=path, kind='golden')
            for path in (kept, dropped, outside)
        ],
    )
    measured = mocker.patch.object(
        measure, 'measure', return_value=measure.MeasureResult(exit_code=ExitCode.SUCCESS)
    )

    status = measure.measure_on_the_game(
        options={'measure': [], 'only': 'rally'}, game=GameThatIsNeverBuilt
    )

    assert status == ExitCode.SUCCESS
    assert measured.call_args.kwargs['recordings'] == [
        ('glitchygames', kept),
        ('glitchygames', outside),
    ]
    settings = measured.call_args.kwargs['settings']
    assert settings.pending_path == tmp_path / ProjectSettings().pending_ledger
    assert settings.demo_packages == ('glitchygames',)
    # Without --only every one is measured
    measure.measure_on_the_game(options={'measure': []}, game=GameThatIsNeverBuilt)
    assert len(measured.call_args.kwargs['recordings']) == 3


def test_the_command_with_no_games_says_so_and_only_keeps_unclaimed_goldens_too(
    tmp_path, capsys, stand_in_game, stand_in_golden
):
    """Games = []: nothing runs (said); an unclaimed golden --only drops is no failure."""
    project = tmp_path / 'project'
    stray = project.joinpath(*GOLDEN_DIRECTORY_PARTS, 'not-a-game', 'golden.jsonl.gz')
    stray.parent.mkdir(parents=True)
    shutil.copy(stand_in_golden, stray)
    (project / 'pyproject.toml').write_text('[tool.glitchygames]\ngames = []\n', encoding='utf-8')

    kept_out = command.main(['measure', '--only', 'rally', '--project-root', str(project)])
    reported = command.main(['measure', '--project-root', str(project)])
    named = command.main(['measure', '--game', NO_SUCH_GAME, '--project-root', str(project)])

    error = capsys.readouterr().err
    assert kept_out == ExitCode.SUCCESS
    assert reported == ExitCode.INTERNAL_ERROR
    # A game named with --game is measured alone: the settings' goldens are not judged
    assert named == ExitCode.OPTIONS_REFUSED
    assert error.count('no games to measure') == 2
    assert error.count("the directory 'not-a-game' is not a console script") == 1
    assert stand_in_game.console_script not in error


def test_the_unmeasured_command_lists_a_golden_no_game_replays_and_why(
    tmp_path, capsys, stand_in_game, stand_in_golden
):
    """It is never measured (measure fails on it), so it is listed, its reason on stderr."""
    project = write_stand_in_project(
        project_root=tmp_path / 'project', game=stand_in_game, goldens=(stand_in_golden,)
    )
    stray = project.joinpath(*GOLDEN_DIRECTORY_PARTS, 'not-a-game', 'golden.jsonl.gz')
    stray.parent.mkdir()
    shutil.copy(stand_in_golden, stray)

    status = command.main(['unmeasured', '--project-root', str(project)])

    output = capsys.readouterr()
    assert status == ExitCode.SUCCESS
    assert output.out.splitlines() == [
        stand_in_golden_ledger_name(game=stand_in_game),
        'tests/fixtures/replays/not-a-game/golden.jsonl.gz',
    ]
    assert "the directory 'not-a-game' is not a console script" in output.err
    assert '2 of 2 recordings not measured' in output.err


def test_a_games_revision_is_its_own_else_the_engines():
    """The revision a game's rows name (``MeasurementRun.game_or_engine_revision``'s rule)."""
    in_this_checkout = measure.game_revision(game=GameThatIsNeverBuilt)
    script_scene = types.new_class(
        'ScriptScene', (Scene,), exec_body=lambda body: body.update({'__module__': 'no_such_game'})
    )

    assert in_this_checkout.commit == source_revision().commit
    # A package that can't be found has no revision of its own: the engine's
    assert measure.game_revision(game=script_scene) == source_revision()
    assert (
        measure.identity_revision(
            identity=GameIdentity(
                package='no_such_game',
                package_directory=None,
                console_script=None,
                distribution=None,
            )
        )
        == source_revision()
    )


def write_package_with_a_demo(*, directory: Path, package: str, demo: Path) -> Path:
    """Write an import package holding ``demo`` as ``<package>/demos/<name>``.

    Returns:
        The demo's path.

    """
    (directory / package / 'demos').mkdir(parents=True)
    (directory / package / '__init__.py').write_text('', encoding='utf-8')
    target = directory / package / 'demos' / demo.name
    shutil.copy(demo, target)
    return target


def test_a_demo_no_measured_game_bundles_is_found_in_the_project(
    tmp_path, stand_in_game, stand_in_golden
):
    """Only a top-level package's demos/; a claimed package's, hidden and venv trees are not."""
    project = tmp_path / 'project'
    lost = write_package_with_a_demo(
        directory=project / 'src', package='orphan_game', demo=stand_in_golden
    )
    write_package_with_a_demo(
        directory=project / 'src', package=stand_in_game.package, demo=stand_in_golden
    )
    # A layer directory named demos (no package above it), a subpackage's demos, a hidden tree
    # and a virtual environment hold no bundled demo
    (project / 'src' / 'demos').mkdir()
    shutil.copy(stand_in_golden, project / 'src' / 'demos' / 'layer.jsonl.gz')
    write_package_with_a_demo(
        directory=project / 'src' / 'orphan_game', package='inner', demo=stand_in_golden
    )
    write_package_with_a_demo(
        directory=project / '.cache', package='hidden_game', demo=stand_in_golden
    )
    (project / 'venv').mkdir()
    (project / 'venv' / 'pyvenv.cfg').write_text('', encoding='utf-8')
    write_package_with_a_demo(
        directory=project / 'venv' / 'lib', package='installed_game', demo=stand_in_golden
    )

    unclaimed = measure.unclaimed_demos(games=[stand_in_game.console_script], project_root=project)

    assert [recording.path for recording in unclaimed] == [lost]
    assert 'orphan_game' in unclaimed[0].reason
    assert '[tool.glitchygames] games' in unclaimed[0].reason


def test_a_demo_no_measured_game_bundles_fails_measure_and_is_listed_unmeasured(
    tmp_path, capsys, stand_in_game, stand_in_golden
):
    """As an unclaimed golden is: a failure line naming the fix, and listed as unmeasured."""
    project = write_stand_in_project(project_root=tmp_path / 'project', game=stand_in_game)
    write_package_with_a_demo(
        directory=project / 'src', package='orphan_game', demo=stand_in_golden
    )
    name = 'src/orphan_game/demos/golden.jsonl.gz'

    measured = command.main(['measure', '--project-root', str(project)])
    measured_error = capsys.readouterr().err
    listed = command.main(['unmeasured', '--project-root', str(project)])
    listing = capsys.readouterr()

    assert measured == ExitCode.INTERNAL_ERROR
    assert f'{name}: a demo bundled in orphan_game' in measured_error
    assert listed == ExitCode.SUCCESS
    assert listing.out.splitlines() == [name]
    assert f'{name}: a demo bundled in orphan_game' in listing.err


@pytest.mark.parametrize('form', ['entry-point', 'module'])
def test_a_game_named_another_way_claims_its_packages_demo(
    tmp_path, capsys, monkeypatch, form, stand_in_game
):
    """``games = ['pkg:main']`` or ``['pkg']``: the package's demo is the game's, not unclaimed.

    The reviewer's case: the game is installed with a console script too, so its child measures
    the demo; were it also unclaimed, ``measure`` would fail and ``unmeasured`` list it twice.
    """
    project = tmp_path / 'project'
    game = write_stand_in_game(directory=project / 'src', package='stand_in_lobby')
    stamp_stand_in_game(game=game, revision=clean_revision())
    use_stand_in_game(install_directory=project / 'src', monkeypatch=monkeypatch)
    # Runnable as a module too (python -m stand_in_lobby), as the module form starts it
    (project / 'src' / game.package / '__main__.py').write_text(
        f'from {game.package} import main\n\nmain()\n', encoding='utf-8'
    )
    demo = project / 'src' / game.package / 'demos' / 'run.jsonl.gz'
    demo.parent.mkdir()
    record_stand_in_game(game=game, path=demo)
    named = f'{game.package}:main' if form == 'entry-point' else game.package
    (project / 'pyproject.toml').write_text(
        f'[tool.glitchygames]\ngames = [{named!r}]\npending-ledger = {STAND_IN_PENDING_LEDGER!r}\n',
        encoding='utf-8',
    )
    name = f'src/{game.package}/demos/run.jsonl.gz'

    assert measure.game_packages(games=[named]) == {game.package}
    assert not measure.unclaimed_demos(games=[named], project_root=project)
    listed = command.main(['unmeasured', '--project-root', str(project)])
    listing = capsys.readouterr()
    measured = command.main(['measure', '--project-root', str(project)])

    assert listed == ExitCode.SUCCESS
    assert listing.out.splitlines() == [name]
    assert 'a demo bundled in' not in listing.err
    assert measured == ExitCode.SUCCESS
    assert measured_recordings(project_root=project) == [name]


def test_a_script_games_package_is_the_one_its_script_is_in(tmp_path):
    """A script inside a package claims that top-level package; a plain script claims none."""
    package = tmp_path / 'scripted_game'
    (package / 'levels').mkdir(parents=True)
    (package / '__init__.py').write_text('', encoding='utf-8')
    (package / 'levels' / '__init__.py').write_text('', encoding='utf-8')
    inside = package / 'levels' / 'play.py'
    inside.write_text('', encoding='utf-8')
    plain = tmp_path / 'play.py'
    plain.write_text('', encoding='utf-8')

    assert measure.game_packages(games=[str(inside)]) == {'scripted_game'}
    assert measure.game_packages(games=[str(plain)]) == set()


def test_an_unmeasured_childs_total_is_read_from_its_summary(
    tmp_path, capsys, stand_in_game, stand_in_golden
):
    """A child with one measured and one unmeasured recording: 1 of 2, not the 1 it listed."""
    project = write_stand_in_project(
        project_root=tmp_path / 'project', game=stand_in_game, goldens=(stand_in_golden,)
    )
    second = project.joinpath(
        *GOLDEN_DIRECTORY_PARTS, stand_in_game.console_script, 'second.jsonl.gz'
    )
    shutil.copy(stand_in_golden, second)
    status, output = run_game_flag(
        game=stand_in_game, arguments=['--measure', '--only', 'second'], working_directory=project
    )
    assert status == ExitCode.SUCCESS, output
    script = project / 'script_game.py'
    script.write_text(
        f'import {stand_in_game.package}\n{stand_in_game.package}.main()\n', encoding='utf-8'
    )

    listed = command.main(['unmeasured', '--game', str(script), '--project-root', str(project)])

    output = capsys.readouterr()
    assert listed == ExitCode.SUCCESS
    assert output.out.splitlines() == [stand_in_golden_ledger_name(game=stand_in_game)]
    assert 'glitchygames unmeasured: 1 of 2 recordings not measured' in output.err
    assert measure.unmeasured_total(text='x: 3 of 1 recording not measured at y') == 1
    assert measure.unmeasured_total(text='no summary') is None


def test_a_demo_in_a_git_ignored_tree_is_not_the_projects(tmp_path, stand_in_golden):
    """In a git checkout, ignored trees (build/, other checkouts) hold none of its demos."""
    project = tmp_path / 'project'
    project.mkdir()
    git(repository=project, arguments=['init', '--quiet'])
    (project / '.gitignore').write_text('build/\n', encoding='utf-8')
    kept = write_package_with_a_demo(
        directory=project / 'src', package='orphan_game', demo=stand_in_golden
    )
    write_package_with_a_demo(
        directory=project / 'build' / 'lib', package='orphan_game', demo=stand_in_golden
    )

    assert measure.project_demo_paths(project_root=project) == [kept]
    # Not a checkout: everything is walked (but hidden trees and environments)
    not_a_checkout = tmp_path / 'plain'
    shutil.copytree(project / 'src', not_a_checkout / 'src')
    shutil.copytree(project / 'build', not_a_checkout / 'build')
    assert len(measure.project_demo_paths(project_root=not_a_checkout)) == 2


def test_without_git_the_project_is_walked(tmp_path, mocker, stand_in_golden):
    """No git to ask (a player's machine): every file is walked, as for a project not in git."""
    demo = write_package_with_a_demo(
        directory=tmp_path / 'project', package='orphan_game', demo=stand_in_golden
    )
    mocker.patch.dict(os.environ, {'PATH': str(tmp_path / 'no-programs')})

    assert measure.git_listed_files(project_root=tmp_path / 'project') is None
    assert measure.project_demo_paths(project_root=tmp_path / 'project') == [demo]
