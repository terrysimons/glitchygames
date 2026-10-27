"""scripts/replay_metrics.py measures recordings into the run ledger's pending rows.

Design: plans/2026-10-23-recording-metrics-1-frame-performance-history.md. The measurements are
real: each recording (a stand-in game's, tests/stand_in_games.py, recorded in tmp_path) is
rebaselined headless through its console script, on this checkout. The published ledger is read
from a throwaway repository whose ``origin`` has a ``gh-pages`` branch; nothing here touches this
repository's remotes or the network.
"""

from __future__ import annotations

import os
import shutil
from functools import partial
from pathlib import Path

import pytest
from scripts import replay_metrics
from scripts.replay_metrics import (
    PENDING_LEDGER_PATH,
    MeasureSettings,
    UnreplayableRecording,
    clear_published,
    golden_replay_globs,
    measure,
    metric_recordings,
    recording_ledger_name,
    rows_to_write,
    run,
)

from glitchygames.build_info import RevisionSource, SourceRevision, source_revision
from glitchygames.bundled_demos import bundled_demos
from glitchygames.exit_codes import ExitCode
from glitchygames.process import run_command
from glitchygames.recording_history import CONTENT_HASH_FIELD, MEASUREMENT_RUNS_HEADER_FIELD
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
from glitchygames.testing.replays import rebaseline_recording_headless
from glitchygames.tracing import FRAMES_FIELD, is_bookmarked_copy, read_trace
from paddleslap import PADDLESLAP_DEMO_PATH
from tests.replay.replay_helpers import rewrite_recording
from tests.replay.test_replay_plugin import REPO_FIXTURE
from tests.stand_in_games import (
    StandInGame,
    record_stand_in_game,
    use_stand_in_game,
    write_stand_in_distribution,
    write_stand_in_game,
    write_stand_in_package,
    write_stand_in_recording,
)
from tests.test_recording_metrics import ledger_row, with_uncommitted_changes

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GIT_TIMEOUT_SECONDS = 60.0
# A stand-in recording that is read, never replayed: a bookmark on frame 1 needs at least 1
# frame, and 3 leave frames after it
STAND_IN_RECORDING_FRAMES = 3
# A project's root pyproject: a workspace without members (metric_recordings reads it)
ROOT_PYPROJECT = '[project]\nname = "stand-in"\n'


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
    deterministic, so its child rebaseline exits SUCCESS and changes no frame.

    Returns:
        The stand-in game.

    """
    install_directory = tmp_path_factory.mktemp('site-packages')
    game = write_stand_in_game(directory=install_directory)
    use_stand_in_game(install_directory=install_directory, monkeypatch=monkeypatch)
    return game


def mark_runs_from_a_clean_checkout(*, path: Path) -> None:
    """Record a recording's runs as made from a clean checkout, as a committed golden's are.

    The child that recorded it read this checkout's state, which has uncommitted changes while
    the code is being changed (clean in CI): a run with uncommitted changes is never written as
    a history row (``rows_to_write``), and the tree's own state must not decide the tests.
    """

    def clean(trace: dict) -> None:
        for recorded_run in trace[MEASUREMENT_RUNS_HEADER_FIELD]:
            recorded_run['source_revision']['uncommitted_changes'] = False

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
        paths = {
            recording_ledger_name(path=path, project_root=PROJECT_ROOT)
            for _, path in recordings.replayable
        }
        assert 'src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz' in paths
        # The repository path under an editable install, the install name under a built one
        assert recording_ledger_name(path=PADDLESLAP_DEMO_PATH, project_root=PROJECT_ROOT) in paths
        assert (
            'mr-muncher',
            PROJECT_ROOT / 'src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz',
        ) in (recordings.replayable)
        assert all(console_script for console_script, _ in recordings.replayable)
        assert not recordings.unreplayable

    @pytest.mark.parametrize('golden', ['golden-classic.jsonl.gz', 'golden-papyrus.jsonl.gz'])
    def test_each_game_of_a_member_with_several_is_measured(self, golden):
        """Brave Adventurer's goldens are named apart (golden-<game>): each is measured.

        Both through the member's one console script, the launcher, which starts the game the
        recording's header names.
        """
        recordings = metric_recordings(project_root=PROJECT_ROOT)

        assert (
            'brave-adventurer',
            PROJECT_ROOT / 'src/games/brave-adventurer/tests/fixtures/replays' / golden,
        ) in recordings.replayable

    def test_a_bookmarked_copy_beside_a_members_golden_is_not_measured(self, tmp_path, monkeypatch):
        """golden-classic.bookmarked.jsonl.gz matches golden*: it is a copy, not a golden.

        A stand-in member whose distribution has one console script (so the golden's header is
        not read to choose one), and a stand-in recording of 3 frames named ``golden-<game>``,
        as a member with a golden per game names them, so the ``golden*`` glob takes it.
        """
        member = tmp_path / 'src' / 'games' / 'stand-in-adventurer'
        (member / 'src' / 'stand_in_adventurer').mkdir(parents=True)
        (tmp_path / 'pyproject.toml').write_text(
            '[project]\nname = "stand-in"\n\n[tool.uv.workspace]\n'
            'members = ["src/games/stand-in-adventurer"]\n',
            encoding='utf-8',
        )
        (member / 'pyproject.toml').write_text(
            '[project]\nname = "stand-in-adventurer"\n\n'
            '[tool.hatch.build.targets.wheel]\npackages = ["src/stand_in_adventurer"]\n',
            encoding='utf-8',
        )
        installed = tmp_path / 'site-packages'
        write_stand_in_distribution(
            directory=installed,
            distribution='stand-in-adventurer',
            console_scripts={'stand-in-adventurer': 'stand_in_adventurer:main'},
        )
        monkeypatch.syspath_prepend(installed)
        fixtures = member / 'tests' / 'fixtures' / 'replays'
        golden = fixtures / 'golden-classic.jsonl.gz'
        write_stand_in_recording(path=golden, frame_count=STAND_IN_RECORDING_FRAMES)
        bookmarked = fixtures / 'golden-classic.bookmarked.jsonl.gz'
        write_bookmarked_copy(recording_path=golden, bookmarks=[1], destination=bookmarked)
        assert is_bookmarked_copy(path=bookmarked)

        recordings = metric_recordings(project_root=tmp_path, demo_packages=())

        assert recordings.replayable == (('stand-in-adventurer', golden),)
        assert not recordings.unreplayable

    def test_the_root_layout_finds_each_games_golden_and_skips_a_bookmarked_copy(
        self, tmp_path, monkeypatch
    ):
        """The root layout's glob is the member's (golden*): golden-<game> too, not the copies.

        The folder is named for a stand-in console script; the goldens are stand-in recordings
        of 3 frames (read, never replayed).
        """
        installed = tmp_path / 'site-packages'
        write_stand_in_distribution(
            directory=installed,
            distribution='stand-in-rally',
            console_scripts={'stand-in-rally': 'stand_in_rally:main'},
        )
        monkeypatch.syspath_prepend(installed)
        # A repository without members: only the root layout's goldens are found
        (tmp_path / 'pyproject.toml').write_text(ROOT_PYPROJECT, encoding='utf-8')
        fixtures = tmp_path / 'tests' / 'fixtures' / 'replays' / 'stand-in-rally'
        golden = fixtures / 'golden.jsonl.gz'
        write_stand_in_recording(path=golden, frame_count=STAND_IN_RECORDING_FRAMES)
        game_golden = fixtures / 'golden-rally.jsonl.gz'
        write_stand_in_recording(path=game_golden, frame_count=STAND_IN_RECORDING_FRAMES)
        bookmarked = fixtures / 'golden-rally.bookmarked.jsonl.gz'
        write_bookmarked_copy(recording_path=game_golden, bookmarks=[1], destination=bookmarked)
        assert is_bookmarked_copy(path=bookmarked)

        recordings = metric_recordings(project_root=tmp_path, demo_packages=())

        assert recordings.replayable == (
            ('stand-in-rally', game_golden),
            ('stand-in-rally', golden),
        )
        assert not recordings.unreplayable

    def test_a_member_that_is_not_installed_is_named_with_the_fix(self, tmp_path):
        """A plain `uv sync` uninstalls the members: one line naming `uv sync --all-packages`."""
        write_uninstalled_member(project_root=tmp_path)

        recordings = metric_recordings(project_root=tmp_path, demo_packages=())

        assert recordings.replayable == ()
        golden = tmp_path / UNINSTALLED_MEMBER_GOLDEN
        [unreplayable] = recordings.unreplayable
        assert unreplayable.path == golden
        assert 'uv sync --all-packages' in unreplayable.reason
        assert "'glitchygames-not-installed-game'" in unreplayable.reason
        assert '\n' not in unreplayable.reason
        assert str(golden) not in unreplayable.reason

    def test_a_demo_no_console_script_replays_is_reported_not_raised(self, tmp_path, monkeypatch):
        """This caller's reaction to such a demo: one unreplayable line; the others are measured.

        Two stand-in packages with a demo each: one with a stand-in console script whose entry
        point is in it, one without.
        """
        installed = tmp_path / 'site-packages'
        replayable_demo_directory = write_stand_in_package(
            directory=installed, package='stand_in_rally', demo_names=('rally.jsonl.gz',)
        )
        write_stand_in_distribution(
            directory=installed,
            distribution='stand-in-rally',
            console_scripts={'stand-in-rally': 'stand_in_rally:main'},
        )
        demo_directory = write_stand_in_package(
            directory=installed,
            package='stand_in_game_without_a_script',
            demo_names=('rally.jsonl.gz',),
        )
        monkeypatch.syspath_prepend(installed)
        # A repository without members or goldens: only the demos are found
        (tmp_path / 'pyproject.toml').write_text(ROOT_PYPROJECT, encoding='utf-8')

        recordings = metric_recordings(
            project_root=tmp_path,
            demo_packages=('stand_in_rally', 'stand_in_game_without_a_script'),
        )

        assert recordings.replayable == (
            ('stand-in-rally', replayable_demo_directory / 'rally.jsonl.gz'),
        )
        [unreplayable_demo] = recordings.unreplayable
        assert unreplayable_demo.path == demo_directory / 'rally.jsonl.gz'
        assert unreplayable_demo.reason == (
            'no installed console script has its entry point in stand_in_game_without_a_script'
        )

    def test_the_measured_demos_are_exactly_the_engines_bundled_demos(self):
        """One lookup (glitchygames.bundled_demos), under an editable install or a built one.

        By console script and ledger name: the repository path when the package is installed
        from it (editable), else its install name (a built install, as nox's test sessions run).
        """
        recordings = metric_recordings(project_root=PROJECT_ROOT)
        goldens = {
            path
            for glob in golden_replay_globs(project_root=PROJECT_ROOT)
            for path in PROJECT_ROOT.glob(glob)
        }
        measured_demos = {
            (console_script, recording_ledger_name(path=path, project_root=PROJECT_ROOT))
            for console_script, path in recordings.replayable
            if path not in goldens
        }
        engine_demos = {
            (
                demo.console_script,
                demo.path.relative_to(PROJECT_ROOT).as_posix()
                if demo.path.is_relative_to(PROJECT_ROOT)
                else demo.install_name,
            )
            for demo in bundled_demos()
        }

        assert measured_demos == engine_demos
        assert ('paddleslap', 'paddleslap/demos/rally.jsonl.gz') in {
            (demo.console_script, demo.install_name) for demo in bundled_demos()
        }


class TestRecordingLedgerNames:
    """A recording in the repository by its repository path, else by its install name."""

    def test_a_recording_in_the_repository_is_named_by_its_repository_path(self):
        """Inside the repository the repository path wins, whatever import path also holds it."""
        golden = PROJECT_ROOT / 'src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz'

        assert recording_ledger_name(path=golden, project_root=PROJECT_ROOT) == (
            'src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz'
        )

    def test_a_recording_in_site_packages_is_named_by_its_install_name(self, tmp_path, monkeypatch):
        """An installed system with no repository: its bundled demo record's install name."""
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
            project_root=tmp_path / 'no-repository',
            demo_packages=('stand_in_game',),
        )

        assert name == 'stand_in_game/demos/rally.jsonl.gz' == demo.install_name

    def test_a_recording_under_an_import_path_that_is_no_bundled_demo_is_refused(
        self, tmp_path, monkeypatch
    ):
        """Outside the repository only a bundled demo's record names it, not the import paths."""
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
                path=stray,
                project_root=tmp_path / 'no-repository',
                demo_packages=('stand_in_game',),
            )

    def test_a_recording_neither_in_the_repository_nor_installed_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match='neither in the repository'):
            recording_ledger_name(
                path=tmp_path / 'elsewhere' / 'rally.jsonl.gz', project_root=tmp_path / 'project'
            )


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
            code_tree=self.TREE,
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
        self.measure_tree(**arguments, code_tree=self.TREE)

        again = self.measure_tree(**arguments, code_tree=self.TREE)
        other_code = self.measure_tree(**arguments, code_tree=self.OTHER_TREE)

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
        new_path = 'src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz'
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

    def measure_into_pending(self, *, tmp_path, game: StandInGame, golden: Path):
        """Measure the stand-in golden into a pending file (no rows directory).

        The golden holds one history run with a commit: the stand-in's paced live run.

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
        mocker.patch.object(replay_metrics, 'origin_main_exists', return_value=True)
        mocker.patch.object(replay_metrics, 'commit_is_on_origin_main', return_value=True)

        rows = self.measure_into_pending(
            tmp_path=tmp_path, game=stand_in_game, golden=stand_in_golden
        )

        assert LedgerOrigin.RECORDING in {row.origin for row in rows}


class TestMeasuring:
    """Each recording is rebaselined into a temporary file and its runs become pending rows."""

    @pytest.fixture(autouse=True)
    def history_has_landed(self, mocker):
        """Treat every recorded run as landed (the landed rules have their own tests above)."""
        mocker.patch.object(replay_metrics, 'origin_main_exists', return_value=True)
        mocker.patch.object(replay_metrics, 'commit_is_on_origin_main', return_value=True)

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
        assert again.skipped == (ledger_name,)
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

        result = measure(
            settings=MeasureSettings(
                project_root=project_root,
                pending_path=pending,
                revision=clean_revision(),
                force=False,
                allow_dirty=False,
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
            update={'machine_state': None, 'machine': replay_metrics.this_machine()}
        )
        published = ledger_row(recording=member_golden_ledger_name(game=stand_in_game)).model_copy(
            update={'run': published_run}
        )
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
        assert result.skipped == (member_golden_ledger_name(game=stand_in_game),)

    def test_uncommitted_changes_are_refused_unless_allowed(
        self, tmp_path, capsys, stand_in_game, stand_in_golden
    ):
        project_root = tmp_path / 'project'
        recordings = copied_golden(
            project_root=project_root, game=stand_in_game, golden=stand_in_golden
        )
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
        result = measure(
            settings=MeasureSettings(
                project_root=project_root,
                pending_path=pending,
                revision=clean_revision(),
                force=False,
                allow_dirty=False,
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

    def test_an_unreplayable_recording_is_one_line_and_the_others_are_measured(
        self, tmp_path, capsys, stand_in_game, stand_in_golden
    ):
        project_root = tmp_path / 'project'
        recordings = copied_golden(
            project_root=project_root, game=stand_in_game, golden=stand_in_golden
        )
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
        assert len(read_ledger_file(path=pending).rows) == 1 + self.golden_runs_with_a_commit(
            golden=stand_in_golden
        )

    def test_a_replay_of_another_commit_is_a_failure(
        self, tmp_path, capsys, stand_in_game, stand_in_golden
    ):
        project_root = tmp_path / 'project'
        recordings = copied_golden(
            project_root=project_root, game=stand_in_game, golden=stand_in_golden
        )
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


def stand_in_project_with_a_demo(
    *, mocker, project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Make the command line measure a stand-in project whose one recording is a bundled demo.

    The stand-in game is installed inside the project (so the demo's ledger name is its
    repository path) and its ``demos/rally.jsonl.gz`` is a session it recorded. The command
    line measures ``replay_metrics.PROJECT_ROOT`` with ``metric_recordings``' default demo
    packages (every member's): both are replaced, so it sees the stand-in project and package.

    Returns:
        The demo's path.

    """
    (project_root / 'pyproject.toml').parent.mkdir(parents=True)
    (project_root / 'pyproject.toml').write_text(ROOT_PYPROJECT, encoding='utf-8')
    install_directory = project_root / 'site-packages'
    game = write_stand_in_game(directory=install_directory)
    use_stand_in_game(install_directory=install_directory, monkeypatch=monkeypatch)
    demo_path = install_directory / game.package / 'demos' / 'rally.jsonl.gz'
    demo_path.parent.mkdir()
    record_stand_in_game(game=game, path=demo_path)
    mocker.patch.object(replay_metrics, 'PROJECT_ROOT', project_root)
    mocker.patch.object(
        replay_metrics,
        'metric_recordings',
        partial(metric_recordings, demo_packages=(game.package,)),
    )
    return demo_path


class TestTheCommandLine:
    """``measure`` and ``clear-published``, as nox -s replay-metrics and docs-deploy run them."""

    def test_measure_one_recording_then_clear(self, tmp_path, mocker, capsys, monkeypatch):
        mocker.patch.object(replay_metrics, 'source_revision', return_value=clean_revision())
        # Nothing is published from this checkout's point of view in a test: otherwise a docs
        # deploy that measured this commit on this machine makes the measurement skip it
        mocker.patch.object(replay_metrics, 'published_ledger_text', return_value='')
        project_root = tmp_path / 'project'
        demo_path = stand_in_project_with_a_demo(
            mocker=mocker, project_root=project_root, monkeypatch=monkeypatch
        )
        pending = tmp_path / 'pending.jsonl'
        arguments = ['--pending', str(pending), '--only', 'stand_in_rally/demos']
        assert run(arguments=['measure', *arguments]) == ExitCode.SUCCESS
        rows = read_ledger_file(path=pending).rows
        # The demo's repository path: the stand-in is installed inside the project
        assert {row.recording for row in rows} == {
            recording_ledger_name(path=demo_path, project_root=project_root)
        }
        assert rows[0].recording == 'site-packages/stand_in_rally/demos/rally.jsonl.gz'
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

    def test_the_hooks_command_line_writes_row_files_naming_the_tree(
        self, tmp_path, mocker, monkeypatch
    ):
        """Measure --allow-dirty --code-tree TREE --rows-directory DIR, as the hook runs it."""
        dirty = source_revision().model_copy(update={'uncommitted_changes': True})
        mocker.patch.object(replay_metrics, 'source_revision', return_value=dirty)
        stand_in_project_with_a_demo(
            mocker=mocker, project_root=tmp_path / 'project', monkeypatch=monkeypatch
        )
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
                'stand_in_rally/demos',
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
