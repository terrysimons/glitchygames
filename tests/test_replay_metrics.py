"""scripts/replay_metrics.py measures recordings into the run ledger's pending rows.

Design: plans/2026-10-23-recording-metrics-1-frame-performance-history.md. The measurements are
real: each recording (a copy of a golden replay or bundled demo in tmp_path) is rebaselined
headless through its console script, on this checkout. The published ledger is read from a
throwaway repository whose ``origin`` has a ``gh-pages`` branch; nothing here touches this
repository's remotes or the network.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from scripts import replay_metrics
from scripts.replay_metrics import (
    PENDING_LEDGER_PATH,
    MeasureSettings,
    UnreplayableRecording,
    clear_published,
    measure,
    metric_recordings,
    rows_to_write,
    run,
)

from glitchygames.build_info import RevisionSource, SourceRevision, source_revision
from glitchygames.exit_codes import ExitCode
from glitchygames.process import run_command
from glitchygames.recording_history import MEASUREMENT_RUNS_HEADER_FIELD
from glitchygames.recording_metrics import (
    PUBLISHED_LEDGER_PATH,
    PUBLISHED_LEDGER_REF,
    LedgerOrigin,
    ledger_text,
    publishable_rows,
    published_ledger_text,
    read_ledger_file,
    read_row_files,
)
from glitchygames.replay.driver import write_bookmarked_copy
from glitchygames.tracing import is_bookmarked_copy, read_trace
from tests.replay.test_replay_plugin import REPO_FIXTURE
from tests.test_recording_metrics import ledger_row, with_uncommitted_changes

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GIT_TIMEOUT_SECONDS = 60.0
# A real golden to copy into a stand-in member (its header names the classic game)
BRAVE_ADVENTURER_GOLDEN = (
    PROJECT_ROOT / 'src/games/brave-adventurer/tests/fixtures/replays/golden-classic.jsonl.gz'
)


def clean_revision() -> SourceRevision:
    """Return the imported engine's revision, as if it had no uncommitted changes.

    The child rebaselines run the same installed engine and record its commit (``uv sync``: the
    checkout's git HEAD; nox: the build stamp its test session's install was built with); the
    tree's own state (changed while developing, clean in CI) must not decide the tests.

    Returns:
        The revision.

    """
    return source_revision().model_copy(update={'uncommitted_changes': False})


def copied_golden(*, project_root: Path) -> list[tuple[str, Path]]:
    """Copy PaddleSlap's golden replay into a project tree laid out as this one is.

    Returns:
        The recordings to measure.

    """
    target = project_root / 'tests' / 'fixtures' / 'replays' / 'paddleslap' / 'golden.jsonl.gz'
    target.parent.mkdir(parents=True)
    shutil.copy(REPO_FIXTURE, target)
    return [('paddleslap', target)]


# A workspace member no environment installs, and its golden replay (relative to the project)
UNINSTALLED_MEMBER_DIRECTORY = Path('src') / 'games' / 'glitchygames-not-installed-game'
UNINSTALLED_MEMBER_GOLDEN = (
    UNINSTALLED_MEMBER_DIRECTORY / 'tests' / 'fixtures' / 'replays' / 'golden.jsonl.gz'
)


def write_uninstalled_member(*, project_root: Path) -> None:
    """Write a project whose one workspace member, with a golden replay, is not installed."""
    member = project_root / UNINSTALLED_MEMBER_DIRECTORY
    (member / 'src' / 'not_installed_game').mkdir(parents=True)
    (project_root / 'pyproject.toml').write_text(
        '[project]\nname = "stand-in"\n\n[tool.uv.workspace]\n'
        f'members = ["{UNINSTALLED_MEMBER_DIRECTORY.as_posix()}"]\n',
        encoding='utf-8',
    )
    (member / 'pyproject.toml').write_text(
        '[project]\nname = "glitchygames-not-installed-game"\n\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["src/not_installed_game"]\n',
        encoding='utf-8',
    )
    golden = project_root / UNINSTALLED_MEMBER_GOLDEN
    golden.parent.mkdir(parents=True)
    golden.write_text('recording\n', encoding='utf-8')


def git(*, repository: Path, arguments: list[str]) -> str:
    """Run git in a throwaway repository (fixed author, no signing).

    Returns:
        git's standard output.

    """
    completed = run_command(
        command=[
            'git',
            '-c',
            'user.name=Metrics Test',
            '-c',
            'user.email=metrics@example.com',
            '-c',
            'commit.gpgsign=false',
            *arguments,
        ],
        environment=os.environ,
        timeout_seconds=GIT_TIMEOUT_SECONDS,
        capture_output=True,
        working_directory=repository,
    )
    assert completed.returncode == 0, completed.stdout
    return completed.stdout or ''


def clone_with_published_ledger(*, tmp_path: Path, ledger: str) -> Path:
    """Make an origin whose gh-pages branch publishes ``ledger``, and clone it.

    Returns:
        The clone (its ``origin/gh-pages`` holds the ledger).

    """
    origin = tmp_path / 'origin'
    origin.mkdir()
    git(repository=origin, arguments=['init', '--quiet', '--initial-branch', 'main'])
    (origin / 'README').write_text('main\n', encoding='utf-8')
    git(repository=origin, arguments=['add', 'README'])
    git(repository=origin, arguments=['commit', '--quiet', '-m', 'main'])
    git(repository=origin, arguments=['checkout', '--quiet', '--orphan', 'gh-pages'])
    git(repository=origin, arguments=['rm', '--quiet', '-r', '-f', '.'])
    published = origin / PUBLISHED_LEDGER_PATH
    published.parent.mkdir(parents=True)
    published.write_text(ledger, encoding='utf-8')
    git(repository=origin, arguments=['add', PUBLISHED_LEDGER_PATH])
    git(repository=origin, arguments=['commit', '--quiet', '-m', 'site'])
    git(repository=origin, arguments=['checkout', '--quiet', 'main'])
    clone = tmp_path / 'clone'
    git(repository=tmp_path, arguments=['clone', '--quiet', str(origin), str(clone)])
    return clone


class TestThePublishedLedger:
    """The ledger published on gh-pages is read from the local origin/gh-pages ref."""

    def test_the_published_ledger_is_read_from_origin_gh_pages(self, tmp_path):
        text = ledger_text(rows=[ledger_row()])
        clone = clone_with_published_ledger(tmp_path=tmp_path, ledger=text)
        assert published_ledger_text(project_root=clone) == text

    def test_no_ref_no_file_or_no_repository_is_an_empty_ledger(self, tmp_path):
        clone = clone_with_published_ledger(tmp_path=tmp_path, ledger='')
        assert not published_ledger_text(project_root=clone, ref='origin/missing')
        # main has no ledger file
        assert not published_ledger_text(project_root=clone, ref='origin/main')
        not_a_repository = tmp_path / 'plain'
        not_a_repository.mkdir()
        assert not published_ledger_text(project_root=not_a_repository)
        assert PUBLISHED_LEDGER_REF == 'origin/gh-pages'

    def test_a_missing_git_is_an_empty_ledger(self, tmp_path, mocker):
        mocker.patch.dict(os.environ, {'PATH': str(tmp_path)})
        assert not published_ledger_text(project_root=tmp_path)

    def test_a_missing_pending_file_is_empty(self, tmp_path):
        assert read_ledger_file(path=tmp_path / 'none.jsonl').rows == ()


class TestTheRecordings:
    """Every golden replay and every bundled demo is measured."""

    def test_this_projects_recordings(self):
        recordings = metric_recordings(project_root=PROJECT_ROOT)
        paths = {path.relative_to(PROJECT_ROOT).as_posix() for _, path in recordings.replayable}
        assert 'tests/fixtures/replays/paddleslap/golden.jsonl.gz' in paths
        assert 'src/glitchygames/examples/paddleslap_demos/rally.jsonl.gz' in paths
        assert (
            'mr-muncher',
            PROJECT_ROOT / 'src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz',
        ) in (recordings.replayable)
        assert all(console_script for console_script, _ in recordings.replayable)
        assert not recordings.unreplayable

    @pytest.mark.parametrize(
        ('console_script', 'golden'),
        [
            ('brave-adventurer', 'golden-classic.jsonl.gz'),
            ('brave-adventurer-papyrus', 'golden-papyrus.jsonl.gz'),
        ],
    )
    def test_each_game_of_a_member_with_several_is_measured(self, console_script, golden):
        """Brave Adventurer's goldens are named apart (golden-<game>): each is measured."""
        recordings = metric_recordings(project_root=PROJECT_ROOT)

        assert (
            console_script,
            PROJECT_ROOT / 'src/games/brave-adventurer/tests/fixtures/replays' / golden,
        ) in recordings.replayable

    def test_a_bookmarked_copy_beside_a_members_golden_is_not_measured(self, tmp_path):
        """golden-classic.bookmarked.jsonl.gz matches golden*: it is a copy, not a golden."""
        member = tmp_path / 'src' / 'games' / 'brave-adventurer'
        (member / 'src' / 'brave_adventurer').mkdir(parents=True)
        (tmp_path / 'pyproject.toml').write_text(
            '[project]\nname = "stand-in"\n\n[tool.uv.workspace]\n'
            'members = ["src/games/brave-adventurer"]\n',
            encoding='utf-8',
        )
        (member / 'pyproject.toml').write_text(
            '[project]\nname = "brave-adventurer"\n\n'
            '[tool.hatch.build.targets.wheel]\npackages = ["src/brave_adventurer"]\n',
            encoding='utf-8',
        )
        fixtures = member / 'tests' / 'fixtures' / 'replays'
        fixtures.mkdir(parents=True)
        golden = fixtures / 'golden-classic.jsonl.gz'
        shutil.copy(BRAVE_ADVENTURER_GOLDEN, golden)
        bookmarked = fixtures / 'golden-classic.bookmarked.jsonl.gz'
        write_bookmarked_copy(recording_path=golden, bookmarks=[1], destination=bookmarked)
        assert is_bookmarked_copy(path=bookmarked)

        recordings = metric_recordings(project_root=tmp_path)

        assert recordings.replayable == (('brave-adventurer', golden),)
        assert not recordings.unreplayable

    def test_a_member_that_is_not_installed_is_named_with_the_fix(self, tmp_path):
        """A plain `uv sync` uninstalls the members: one line naming `uv sync --all-packages`."""
        write_uninstalled_member(project_root=tmp_path)

        recordings = metric_recordings(project_root=tmp_path)

        assert recordings.replayable == ()
        golden = tmp_path / UNINSTALLED_MEMBER_GOLDEN
        [unreplayable] = recordings.unreplayable
        assert unreplayable.path == golden
        assert 'uv sync --all-packages' in unreplayable.reason
        assert "'glitchygames-not-installed-game'" in unreplayable.reason
        assert '\n' not in unreplayable.reason
        assert str(golden) not in unreplayable.reason


class TestMeasuringIntoRowFiles:
    """The pre-commit hook's measurement: row files naming the code tree measured."""

    TREE = '0123456789abcdef0123456789abcdef01234567'
    OTHER_TREE = 'fedcba9876543210fedcba9876543210fedcba98'

    def measure_tree(self, *, project_root, recordings, pending, rows_directory, code_tree):
        """Measure the recordings for a code tree into row files (the hook's measure call).

        Returns:
            What was measured.

        """
        return measure(
            settings=MeasureSettings(
                project_root=project_root,
                pending_path=pending,
                revision=clean_revision().model_copy(update={'uncommitted_changes': True}),
                force=False,
                allow_dirty=True,
                code_tree=code_tree,
                rows_directory=rows_directory,
            ),
            recordings=recordings,
            published_text='',
        )

    def test_a_measurement_writes_row_files_naming_the_code_tree(self, tmp_path):
        project_root = tmp_path / 'project'
        recordings = copied_golden(project_root=project_root)
        pending = tmp_path / 'pending.jsonl'
        rows_directory = tmp_path / 'replay-ledger'

        result = self.measure_tree(
            project_root=project_root,
            recordings=recordings,
            pending=pending,
            rows_directory=rows_directory,
            code_tree=self.TREE,
        )

        assert result.exit_code == ExitCode.SUCCESS
        assert not pending.exists()
        rows = read_row_files(directory=rows_directory)
        measured = [row for row in rows if row.origin == LedgerOrigin.REPLAY_METRICS]
        recorded = [row for row in rows if row.origin == LedgerOrigin.RECORDING]
        # Only the run just measured names the code tree; this directory is no repository with
        # an origin/main, so none of the recording's own (history) runs has landed: none written
        assert [row.code_tree for row in measured] == [self.TREE]
        assert recorded == []
        assert not measured[0].from_uncommitted_changes

    def test_a_missing_origin_main_is_said_once(self, tmp_path, capsys):
        project_root = tmp_path / 'project'

        self.measure_tree(
            project_root=project_root,
            recordings=copied_golden(project_root=project_root),
            pending=tmp_path / 'pending.jsonl',
            rows_directory=tmp_path / 'replay-ledger',
            code_tree=self.TREE,
        )

        output = capsys.readouterr().out
        assert output.count('origin/main') == 1
        assert 'no history rows written' in output

    def test_the_same_code_tree_is_measured_once_per_machine(self, tmp_path):
        project_root = tmp_path / 'project'
        recordings = copied_golden(project_root=project_root)
        arguments = {
            'project_root': project_root,
            'recordings': recordings,
            'pending': tmp_path / 'pending.jsonl',
            'rows_directory': tmp_path / 'replay-ledger',
        }
        self.measure_tree(**arguments, code_tree=self.TREE)

        again = self.measure_tree(**arguments, code_tree=self.TREE)
        other_code = self.measure_tree(**arguments, code_tree=self.OTHER_TREE)

        assert again.measured == ()
        assert len(again.skipped) == 1
        assert len(other_code.measured) == 1

    def test_the_summary_names_the_rows_directory(self, tmp_path, capsys):
        project_root = tmp_path / 'project'
        rows_directory = tmp_path / 'replay-ledger'

        self.measure_tree(
            project_root=project_root,
            recordings=copied_golden(project_root=project_root),
            pending=tmp_path / 'pending.jsonl',
            rows_directory=rows_directory,
            code_tree=self.TREE,
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

    def test_a_history_run_measured_on_a_landed_commit_is_written(self, landed_repository):
        repository, landed, _ = landed_repository
        newest = ledger_row(measured_at='2026-10-25T10:00:00+00:00')
        history = self.history_row(commit=landed)

        written = rows_to_write(
            rows=[newest, history], held_keys=set(), repository=repository, origin_main_present=True
        )

        assert written == [newest, history]

    def test_a_history_run_measured_on_a_commit_not_on_origin_main_is_not(self, landed_repository):
        repository, _, branch = landed_repository
        newest = ledger_row(measured_at='2026-10-25T10:00:00+00:00')

        written = rows_to_write(
            rows=[newest, self.history_row(commit=branch)],
            held_keys=set(),
            repository=repository,
            origin_main_present=True,
        )

        assert written == [newest]

    def test_a_history_run_with_uncommitted_changes_is_not_written(self, landed_repository):
        repository, landed, _ = landed_repository
        dirty = self.history_row(commit=landed)
        dirty = dirty.model_copy(update={'run': with_uncommitted_changes(dirty.run)})
        newest = ledger_row(measured_at='2026-10-25T10:00:00+00:00')

        written = rows_to_write(
            rows=[newest, dirty], held_keys=set(), repository=repository, origin_main_present=True
        )

        assert written == [newest]

    def test_a_history_run_of_an_unknown_commit_is_not_written(self, landed_repository):
        repository, _, _ = landed_repository
        newest = ledger_row(measured_at='2026-10-25T10:00:00+00:00')

        written = rows_to_write(
            rows=[newest, self.history_row(commit=None)],
            held_keys=set(),
            repository=repository,
            origin_main_present=True,
        )

        assert written == [newest]

    def test_without_origin_main_no_history_run_is_written(self, landed_repository):
        repository, landed, _ = landed_repository
        newest = ledger_row(measured_at='2026-10-25T10:00:00+00:00')

        written = rows_to_write(
            rows=[newest, self.history_row(commit=landed)],
            held_keys=set(),
            repository=repository,
            origin_main_present=False,
        )

        assert written == [newest]

    def test_a_run_held_under_a_moved_recordings_old_path_is_not_written_again(
        self, landed_repository
    ):
        repository, landed, _ = landed_repository
        old_path = 'glitchygames/examples/paddleslap_demos/rally.jsonl.gz'
        new_path = 'src/glitchygames/examples/paddleslap_demos/rally.jsonl.gz'
        held = ledger_row(recording=old_path, commit=landed)
        again = ledger_row(recording=new_path, commit=landed)
        newest = ledger_row(recording=new_path, measured_at='2026-10-25T10:00:00+00:00')

        written = rows_to_write(
            rows=[newest, again],
            held_keys={held.held_key},
            repository=repository,
            origin_main_present=True,
        )

        assert written == [newest]


class TestHistoryRunsInThePendingFile:
    """The pending file is published too: it takes the same landed history runs as row files."""

    def measure_into_pending(self, *, tmp_path):
        """Measure the golden into a pending file (no rows directory).

        Returns:
            The pending rows.

        """
        project_root = tmp_path / 'project'
        measure(
            settings=MeasureSettings(
                project_root=project_root,
                pending_path=tmp_path / 'pending.jsonl',
                revision=clean_revision(),
                force=False,
                allow_dirty=False,
            ),
            recordings=copied_golden(project_root=project_root),
            published_text='',
        )
        return read_ledger_file(path=tmp_path / 'pending.jsonl').rows

    def test_a_history_run_on_a_commit_not_on_origin_main_is_not_appended(self, tmp_path, capsys):
        rows = self.measure_into_pending(tmp_path=tmp_path)

        assert [row.origin for row in rows] == [LedgerOrigin.REPLAY_METRICS]
        assert capsys.readouterr().out.count('origin/main') == 1

    def test_a_history_run_on_a_commit_on_origin_main_is_appended(self, mocker, tmp_path):
        mocker.patch.object(replay_metrics, 'origin_main_exists', return_value=True)
        mocker.patch.object(replay_metrics, 'commit_is_on_origin_main', return_value=True)

        rows = self.measure_into_pending(tmp_path=tmp_path)

        assert LedgerOrigin.RECORDING in {row.origin for row in rows}


class TestMeasuring:
    """Each recording is rebaselined into a temporary file and its runs become pending rows."""

    @pytest.fixture(autouse=True)
    def history_has_landed(self, mocker):
        """Treat every recorded run as landed (the landed rules have their own tests above)."""
        mocker.patch.object(replay_metrics, 'origin_main_exists', return_value=True)
        mocker.patch.object(replay_metrics, 'commit_is_on_origin_main', return_value=True)

    def golden_runs_with_a_commit(self):
        """Return how many runs the golden holds that name a commit (the others are not landed).

        Returns:
            The count.

        """
        runs = read_trace(path=REPO_FIXTURE)[MEASUREMENT_RUNS_HEADER_FIELD]
        return sum(1 for run in runs if run.get('source_revision'))

    def test_a_measurement_appends_rows_and_a_second_one_skips(self, tmp_path, capsys):
        project_root = tmp_path / 'project'
        recordings = copied_golden(project_root=project_root)
        pending = tmp_path / 'pending.jsonl'
        revision = clean_revision()

        result = measure(
            settings=MeasureSettings(
                project_root=project_root,
                pending_path=pending,
                revision=revision,
                force=False,
                allow_dirty=False,
            ),
            recordings=recordings,
            published_text='',
        )

        assert result.exit_code == ExitCode.SUCCESS
        rows = read_ledger_file(path=pending).rows
        measured, recorded, *older_recorded = rows
        assert measured.origin == LedgerOrigin.REPLAY_METRICS
        assert measured.recording == 'tests/fixtures/replays/paddleslap/golden.jsonl.gz'
        assert measured.console_script == 'paddleslap'
        assert measured.commit == revision.commit
        assert measured.rebaseline_exit == ExitCode.SUCCESS.describe()
        assert measured.frames_changed == 0
        assert measured.summary is not None
        assert not measured.run.processing_paced
        assert measured.run.machine_state is not None
        assert recorded.origin == LedgerOrigin.RECORDING
        # One recorded row per run the golden holds, the measurement on top
        assert len(older_recorded) + 1 == self.golden_runs_with_a_commit()
        assert 'tests/fixtures/replays/paddleslap/golden.jsonl.gz: 622 frames' in (
            capsys.readouterr().out
        )

        again = measure(
            settings=MeasureSettings(
                project_root=project_root,
                pending_path=pending,
                revision=revision,
                force=False,
                allow_dirty=False,
            ),
            recordings=recordings,
            published_text='',
        )
        assert again.measured == ()
        assert again.skipped == ('tests/fixtures/replays/paddleslap/golden.jsonl.gz',)
        assert 'already measured' in capsys.readouterr().out
        assert read_ledger_file(path=pending).rows == rows

        forced = measure(
            settings=MeasureSettings(
                project_root=project_root,
                pending_path=pending,
                revision=revision,
                force=True,
                allow_dirty=False,
            ),
            recordings=recordings,
            published_text=ledger_text(rows=rows),
        )
        # The recording's own run is already known: only the new measurement is appended
        assert len(forced.measured) == 1
        assert len(read_ledger_file(path=pending).rows) == len(rows) + 1

    def test_a_published_measurement_counts_as_measured(self, tmp_path):
        project_root = tmp_path / 'project'
        recordings = copied_golden(project_root=project_root)
        revision = clean_revision()
        assert revision.commit is not None
        # Measured on this machine (its label is the platform when no machine state is known)
        published_run = ledger_row(commit=revision.commit).run.model_copy(
            update={'machine_state': None, 'machine': replay_metrics.this_machine()}
        )
        published = ledger_row().model_copy(update={'run': published_run})
        result = measure(
            settings=MeasureSettings(
                project_root=project_root,
                pending_path=tmp_path / 'pending.jsonl',
                revision=revision,
                force=False,
                allow_dirty=False,
            ),
            recordings=recordings,
            published_text=ledger_text(rows=[published]),
        )
        assert result.skipped == ('tests/fixtures/replays/paddleslap/golden.jsonl.gz',)

    def test_uncommitted_changes_are_refused_unless_allowed(self, tmp_path, capsys):
        project_root = tmp_path / 'project'
        recordings = copied_golden(project_root=project_root)
        pending = tmp_path / 'pending.jsonl'
        dirty = source_revision().model_copy(update={'uncommitted_changes': True})
        refused = measure(
            settings=MeasureSettings(
                project_root=project_root,
                pending_path=pending,
                revision=dirty,
                force=False,
                allow_dirty=False,
            ),
            recordings=recordings,
            published_text='',
        )
        assert refused.exit_code == ExitCode.OPTIONS_REFUSED
        assert 'uncommitted changes' in capsys.readouterr().err
        assert not pending.exists()

        allowed = measure(
            settings=MeasureSettings(
                project_root=project_root,
                pending_path=pending,
                revision=dirty,
                force=False,
                allow_dirty=True,
            ),
            recordings=recordings,
            published_text='',
        )
        assert allowed.exit_code == ExitCode.SUCCESS
        measured = read_ledger_file(path=pending).rows[0]
        assert measured.allowed_uncommitted_changes

    def test_an_unknown_commit_is_refused(self, tmp_path, capsys):
        result = measure(
            settings=MeasureSettings(
                project_root=tmp_path,
                pending_path=tmp_path / 'pending.jsonl',
                revision=SourceRevision(source=RevisionSource.UNKNOWN),
                force=False,
                allow_dirty=False,
            ),
            recordings=[],
            published_text='',
        )
        assert result.exit_code == ExitCode.OPTIONS_REFUSED
        assert 'git checkout' in capsys.readouterr().err

    def test_failures_are_reported_and_measured_rows_kept(self, tmp_path, capsys):
        project_root = tmp_path / 'project'
        recordings = copied_golden(project_root=project_root)
        broken = project_root / 'tests' / 'fixtures' / 'replays' / 'paddleslap' / 'broken.jsonl.gz'
        broken.write_text('not a recording', encoding='utf-8')
        pending = tmp_path / 'pending.jsonl'
        result = measure(
            settings=MeasureSettings(
                project_root=project_root,
                pending_path=pending,
                revision=clean_revision(),
                force=False,
                allow_dirty=False,
            ),
            recordings=[('paddleslap', broken), *recordings],
            published_text='',
        )
        assert result.exit_code == ExitCode.INTERNAL_ERROR
        assert result.failures == ('tests/fixtures/replays/paddleslap/broken.jsonl.gz',)
        assert 'UNUSABLE_INPUT' in capsys.readouterr().err
        assert len(read_ledger_file(path=pending).rows) == 1 + self.golden_runs_with_a_commit()

    def test_an_unreplayable_recording_is_one_line_and_the_others_are_measured(
        self, tmp_path, capsys
    ):
        project_root = tmp_path / 'project'
        recordings = copied_golden(project_root=project_root)
        missing = project_root / UNINSTALLED_MEMBER_GOLDEN
        pending = tmp_path / 'pending.jsonl'
        result = measure(
            settings=MeasureSettings(
                project_root=project_root,
                pending_path=pending,
                revision=clean_revision(),
                force=False,
                allow_dirty=False,
            ),
            recordings=recordings,
            unreplayable=[
                UnreplayableRecording(path=missing, reason='not installed: uv sync --all-packages')
            ],
            published_text='',
        )
        assert result.exit_code == ExitCode.INTERNAL_ERROR
        assert result.failures == (UNINSTALLED_MEMBER_GOLDEN.as_posix(),)
        error_lines = capsys.readouterr().err.splitlines()
        assert error_lines == [
            f'{UNINSTALLED_MEMBER_GOLDEN.as_posix()}: not installed: uv sync --all-packages'
        ]
        assert len(read_ledger_file(path=pending).rows) == 1 + self.golden_runs_with_a_commit()

    def test_a_replay_of_another_commit_is_a_failure(self, tmp_path, capsys):
        project_root = tmp_path / 'project'
        recordings = copied_golden(project_root=project_root)
        other_commit = clean_revision().model_copy(update={'commit': 'f' * 40})
        result = measure(
            settings=MeasureSettings(
                project_root=project_root,
                pending_path=tmp_path / 'pending.jsonl',
                revision=other_commit,
                force=False,
                allow_dirty=False,
            ),
            recordings=recordings,
            published_text='',
        )
        assert result.exit_code == ExitCode.INTERNAL_ERROR
        assert 'measured commit' in capsys.readouterr().err


class TestClearingPublishedRows:
    """After a deploy, pending rows the published ledger now holds are removed."""

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

    def test_rows_from_uncommitted_changes_stay_pending_after_a_deploy(self, tmp_path):
        """A deploy publishes only clean rows, so the trial stays local and pending."""
        pending = tmp_path / 'pending.jsonl'
        clean = ledger_row()
        trial = ledger_row(measured_at='2026-10-24T09:00:00+00:00').model_copy(
            update={'allowed_uncommitted_changes': True}
        )
        pending.write_text(ledger_text(rows=[clean, trial]), encoding='utf-8')
        # What a gh-deploy build published (scripts/generate_performance_graphs.py)
        published = ledger_text(rows=publishable_rows(rows=[clean, trial]))
        clear_published(pending_path=pending, published_text=published)
        assert read_ledger_file(path=pending).rows == (trial,)


class TestTheCommandLine:
    """``measure`` and ``clear-published``, as nox -s replay-metrics and docs-deploy run them."""

    def test_measure_one_recording_then_clear(self, tmp_path, mocker, capsys):
        mocker.patch.object(replay_metrics, 'source_revision', return_value=clean_revision())
        # Nothing is published from this checkout's point of view in a test: otherwise a docs
        # deploy that measured this commit on this machine makes the measurement skip it
        mocker.patch.object(replay_metrics, 'published_ledger_text', return_value='')
        pending = tmp_path / 'pending.jsonl'
        arguments = ['--pending', str(pending), '--only', 'paddleslap_demos']
        assert run(arguments=['measure', *arguments]) == ExitCode.SUCCESS
        rows = read_ledger_file(path=pending).rows
        assert {row.recording for row in rows} == {
            'src/glitchygames/examples/paddleslap_demos/rally.jsonl.gz'
        }
        assert 'Measured 1 recording' in capsys.readouterr().out
        # Nothing published: clearing the published rows keeps every pending one
        assert run(arguments=['clear-published', '--pending', str(pending)]) == ExitCode.SUCCESS
        assert read_ledger_file(path=pending).rows == rows

    def test_skip_dirty_measures_nothing(self, tmp_path, mocker, capsys):
        dirty = source_revision().model_copy(update={'uncommitted_changes': True})
        mocker.patch.object(replay_metrics, 'source_revision', return_value=dirty)
        pending = tmp_path / 'pending.jsonl'
        assert run(arguments=['measure', '--pending', str(pending), '--skip-dirty']) == (
            ExitCode.SUCCESS
        )
        assert not pending.exists()
        assert 'Not measuring' in capsys.readouterr().out

    def test_the_hooks_command_line_writes_row_files_naming_the_tree(self, tmp_path, mocker):
        """Measure --allow-dirty --code-tree TREE --rows-directory DIR, as the hook runs it."""
        dirty = source_revision().model_copy(update={'uncommitted_changes': True})
        mocker.patch.object(replay_metrics, 'source_revision', return_value=dirty)
        rows_directory = tmp_path / 'replay-ledger'
        tree = '0123456789abcdef0123456789abcdef01234567'

        exit_code = run(
            arguments=[
                'measure',
                '--pending',
                str(tmp_path / 'pending.jsonl'),
                '--allow-dirty',
                '--code-tree',
                tree,
                '--rows-directory',
                str(rows_directory),
                '--only',
                'paddleslap_demos',
            ]
        )

        assert exit_code == ExitCode.SUCCESS
        trees = {row.code_tree for row in read_row_files(directory=rows_directory)}
        assert tree in trees
        assert not (tmp_path / 'pending.jsonl').exists()

    def test_allow_dirty_and_skip_dirty_together_are_refused(self, capsys):
        with pytest.raises(SystemExit) as exit_info:
            run(arguments=['measure', '--allow-dirty', '--skip-dirty'])
        assert exit_info.value.code == ExitCode.ARGUMENT_PARSER_ERROR
        assert 'not allowed with' in capsys.readouterr().err

    def test_the_default_pending_file_is_gitignored(self):
        assert PENDING_LEDGER_PATH.relative_to(PROJECT_ROOT).parts[0] == 'test-results'
