"""A run names the game's commit beside the engine's (``MeasurementRun.game_source_revision``).

A ledger row's commit and uncommitted-changes flag are the game's (Part 3, Stage D, Task D3): a
game outside this repository records its own checkout's commit, not the engine's. A recording
or row from before the field has none, and falls back to the engine's, as before. In this
repository the game and the engine are one checkout, so our rows don't change.

On stand-in games (tests/stand_in_games.py), each in its own temporary git repository, never
one of our members. The recording and the row from before the field are fixed copies in
``tests/fixtures/provenance/`` (see ``PROVENANCE_FIXTURES``), never the live files: a rebaseline
or a new measurement must not change what these tests pin.
"""

from __future__ import annotations

import os
import shutil
import types
from typing import TYPE_CHECKING

import pytest

from glitchygames.build_info import (
    UNKNOWN_REVISION,
    RevisionSource,
    SourceRevision,
    engine_source_revision,
)
from glitchygames.code_tree import LandedCommit
from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command
from glitchygames.recording_history import MeasurementRun, recorded_measurement_runs
from glitchygames.recording_metrics import (
    LedgerOrigin,
    LedgerRow,
    is_measured,
    landed_rows,
    ledger_rows_from_rebaseline,
    merge_ledgers,
    parse_ledger,
    short_commit,
)
from glitchygames.replay.tools.children import rebaseline_recording_headless
from glitchygames.replay.tools.identity import game_source_revision
from glitchygames.scenes import Scene
from glitchygames.tracing import read_trace
from tests.harness import PROJECT_ROOT
from tests.stand_in_games import (
    StandInGame,
    record_stand_in_game,
    use_stand_in_game,
    write_stand_in_game,
)

if TYPE_CHECKING:
    from pathlib import Path

# Fixed copies of a recording and a ledger row from before game_source_revision existed. Each
# file's bytes are the committed file at 4e6f7e86 (the commit before Task D3), copied with
# ``git show 4e6f7e86:<path>``, and never change:
PROVENANCE_FIXTURES = PROJECT_ROOT / 'tests' / 'fixtures' / 'provenance'
# - src/games/clockwork-keep/tests/fixtures/replays/golden.jsonl.gz (last changed in a97efbe9):
#   its runs name the engine's commit and nothing of the game's
GOLDEN_FROM_BEFORE_THE_FIELD = (
    PROVENANCE_FIXTURES / 'clockwork-keep-golden-before-game-source-revision.jsonl.gz'
)
# - quality/replay-ledger/<this name>: a row the pre-commit hook measured before the field
ROW_FILE_FROM_BEFORE_THE_FIELD = PROVENANCE_FIXTURES / (
    '0220a12030cd-apple-m4-max-202610270503432821460000-'
    'src-games-brave-adventurer-tests-fixtures-replays-golden-classic.json'
)
GIT_TIMEOUT_SECONDS = 30.0
# A commit no checkout here has: what another repository's game names
ANOTHER_REPOSITORYS_COMMIT = 'a' * 40
LANDED_COMMIT = LandedCommit(commit='b' * 40, committed_at='2026-10-26T12:00:00+00:00')
CODE_TREE = 'c' * 40
MACHINE = 'a machine'
# The engine's commit in the hand-built runs
ENGINE_COMMIT = 'e' * 40


def git(*arguments: str, directory: Path) -> str:
    """Run git in a directory with a fixed identity and no user configuration.

    Returns:
        Its standard output, stripped.

    """
    git_program = shutil.which('git')
    assert git_program is not None, 'these tests need git'
    completed = run_command(
        command=[git_program, '-C', str(directory), *arguments],
        environment={
            **os.environ,
            'GIT_CONFIG_GLOBAL': os.devnull,
            'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_AUTHOR_NAME': 'Test',
            'GIT_AUTHOR_EMAIL': 'test@example.com',
            'GIT_COMMITTER_NAME': 'Test',
            'GIT_COMMITTER_EMAIL': 'test@example.com',
        },
        timeout_seconds=GIT_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
    )
    assert completed.returncode == 0, completed.stdout
    return completed.stdout.strip()


@pytest.fixture
def game_in_its_own_repository(tmp_path, monkeypatch) -> StandInGame:
    """Write the stand-in game into a new git repository with one commit, and install it there.

    The package directory is inside the repository's work tree and tracked (git_checkout_revision
    asks ``git ls-files``); the child processes import it from there (``PYTHONPATH``), as nothing
    else installs it.

    Returns:
        The stand-in game.

    """
    repository = tmp_path / 'game-repository'
    repository.mkdir()
    game = write_stand_in_game(directory=repository)
    git('init', '--quiet', '--initial-branch=main', directory=repository)
    git('add', '.', directory=repository)
    git('commit', '--quiet', '--message', 'the game', directory=repository)
    use_stand_in_game(install_directory=repository, monkeypatch=monkeypatch)
    return game


def rebaselined_rows(*, game: StandInGame, tmp_path: Path) -> tuple[dict, list[LedgerRow]]:
    """Record the game's session, rebaseline it through its console script, and read the rows.

    Returns:
        The rebaselined recording's header (and frames), and its ledger rows.

    """
    recording = record_stand_in_game(game=game, path=tmp_path / 'recorded' / 'run.jsonl.gz')
    rebaselined = tmp_path / 'rebaselined' / 'run.jsonl.gz'
    rebaselined.parent.mkdir()
    completed = rebaseline_recording_headless(
        console_script=game.console_script, path=recording, new_path=rebaselined
    )
    assert completed.returncode == ExitCode.SUCCESS, completed.stdout
    trace = read_trace(path=rebaselined)
    rows = ledger_rows_from_rebaseline(
        recording='run.jsonl.gz',
        console_script=game.console_script,
        trace=trace,
        rebaseline_exit=ExitCode.describe_status(completed.returncode),
        allowed_uncommitted_changes=False,
    )
    return trace, rows


def test_a_stand_in_game_in_its_own_repository_records_its_own_commit(
    game_in_its_own_repository, tmp_path
):
    """The header names the game's checkout, and the row's commit is it, not the engine's."""
    repository = game_in_its_own_repository.install_directory
    game_commit = git('rev-parse', 'HEAD', directory=repository)

    trace, rows = rebaselined_rows(game=game_in_its_own_repository, tmp_path=tmp_path)

    newest = trace['measurement_runs'][0]
    assert newest['game_source_revision']['source'] == RevisionSource.GIT_CHECKOUT
    assert newest['game_source_revision']['commit'] == game_commit
    assert newest['game_source_revision']['uncommitted_changes'] is False
    # The engine's own revision is still recorded beside it
    assert newest['source_revision']['commit'] == engine_source_revision().commit
    # The rebaselined run, and the live run it held: each names the game's commit
    assert [row.commit for row in rows] == [game_commit, game_commit]
    assert rows[0].commit != engine_source_revision().commit
    assert not rows[0].measured_uncommitted_changes
    assert short_commit(run=rows[0].run) == game_commit[:7]


def test_a_dirty_game_checkout_marks_the_row_dirty(game_in_its_own_repository, tmp_path):
    """A tracked file of the game changed since its commit: the row measured uncommitted code."""
    repository = game_in_its_own_repository.install_directory
    game_commit = git('rev-parse', 'HEAD', directory=repository)
    package_source = repository / game_in_its_own_repository.package / '__init__.py'
    package_source.write_text(
        package_source.read_text(encoding='utf-8') + '# changed after the commit\n',
        encoding='utf-8',
    )

    trace, rows = rebaselined_rows(game=game_in_its_own_repository, tmp_path=tmp_path)

    assert trace['measurement_runs'][0]['game_source_revision']['uncommitted_changes'] is True
    assert rows[0].commit == game_commit
    assert rows[0].measured_uncommitted_changes
    assert rows[0].from_uncommitted_changes


def copied_golden_trace(*, tmp_path: Path) -> dict:
    """Copy the golden from before the field into tmp_path, and read it.

    Returns:
        Its header fields and frames.

    """
    copy = tmp_path / 'golden.jsonl.gz'
    shutil.copyfile(GOLDEN_FROM_BEFORE_THE_FIELD, copy)
    return read_trace(path=copy)


def rows_of(*, trace: dict) -> list[LedgerRow]:
    """Return a recording's rows as a measurement reads them (``ledger_rows_from_rebaseline``).

    Returns:
        The rows, newest first.

    """
    return ledger_rows_from_rebaseline(
        recording='golden.jsonl.gz',
        console_script='clockwork-keep',
        trace=trace,
        rebaseline_exit=ExitCode.describe_status(ExitCode.SUCCESS),
        allowed_uncommitted_changes=False,
    )


def test_a_recording_without_game_source_revision_still_loads_and_uses_the_engines(tmp_path):
    """A committed golden from before the field: every run loads, and names the engine's commit."""
    trace = copied_golden_trace(tmp_path=tmp_path)
    stored_runs = trace['measurement_runs']
    assert all('game_source_revision' not in stored_run for stored_run in stored_runs)

    runs = recorded_measurement_runs(header=trace)
    rows = rows_of(trace=trace)

    assert all(run is not None and run.game_source_revision is None for run in runs)
    assert [row.commit for row in rows] == [
        (stored_run.get('source_revision') or {}).get('commit') for stored_run in stored_runs
    ]
    assert rows[0].commit is not None
    assert rows[0].measured_uncommitted_changes is bool(
        stored_runs[0]['source_revision']['uncommitted_changes']
    )


def test_a_ledger_row_from_before_game_source_revision_still_loads():
    """A row file committed before the field loads unchanged, naming its engine's commit."""
    parsed = parse_ledger(text=ROW_FILE_FROM_BEFORE_THE_FIELD.read_text(encoding='utf-8'))

    assert parsed.unreadable_lines == 0
    assert parsed.rows
    for row in parsed.rows:
        assert row.run.game_source_revision is None
        assert row.run.source_revision is not None
        assert row.commit == row.run.source_revision.commit


class StandInSceneOfThisRepository(Scene):
    """A game whose package (``tests``) is tracked in this repository's checkout."""


def test_our_games_rows_are_unchanged(tmp_path):
    """In this repository the game's revision is the engine's, so every row reads as before.

    A game of ours is in this checkout (its package is tracked here), as the engine is: its
    revision names the engine's commit and uncommitted-changes state. A golden's runs given that
    revision (as a run of ours now records) give the same commits, flags, labels, order,
    measured-already answers and landing as the same runs without it.
    """
    game_revision = game_source_revision(game=StandInSceneOfThisRepository)
    assert game_revision is not None
    assert game_revision.commit == engine_source_revision().commit
    assert game_revision.uncommitted_changes == engine_source_revision().uncommitted_changes

    trace = copied_golden_trace(tmp_path=tmp_path)
    before = rows_of(trace=trace)
    as_ours_now = {
        **trace,
        'measurement_runs': [
            {**stored_run, 'game_source_revision': stored_run.get('source_revision')}
            for stored_run in trace['measurement_runs']
        ],
    }
    after = rows_of(trace=as_ours_now)

    assert after[0].run.game_source_revision is not None
    assert [row.commit for row in after] == [row.commit for row in before]
    assert [row.measured_uncommitted_changes for row in after] == [
        row.measured_uncommitted_changes for row in before
    ]
    assert [row.from_uncommitted_changes for row in after] == [
        row.from_uncommitted_changes for row in before
    ]
    assert [short_commit(run=row.run) for row in after] == [
        short_commit(run=row.run) for row in before
    ]
    assert [row.key for row in merge_ledgers(ledgers=[after])] == [
        row.key for row in merge_ledgers(ledgers=[before])
    ]
    commit = before[0].commit
    assert commit is not None
    assert is_measured(
        rows=after, recording='golden.jsonl.gz', commit=commit, machine=after[0].machine
    ) == is_measured(
        rows=before, recording='golden.jsonl.gz', commit=commit, machine=before[0].machine
    )
    landing = {CODE_TREE: LANDED_COMMIT}
    landed_before = landed_rows(
        rows=[before[0].model_copy(update={'code_tree': CODE_TREE})],
        landed=landing,
        keep_unlanded=False,
    )
    landed_after = landed_rows(
        rows=[after[0].model_copy(update={'code_tree': CODE_TREE})],
        landed=landing,
        keep_unlanded=False,
    )
    assert landed_after[0].commit == landed_before[0].commit == LANDED_COMMIT.commit
    # One checkout: the engine's revision is relabelled with the game's, as before
    assert landed_after[0].run.source_revision == landed_before[0].run.source_revision


def scene_class_in(*, module: str) -> type[Scene]:
    """Return a scene class whose module is ``module`` (as if defined there).

    Returns:
        The class.

    """
    return types.new_class(
        'StandInScene', (Scene,), exec_body=lambda body: body.update({'__module__': module})
    )


def test_a_game_whose_package_is_not_found_records_no_game_revision():
    """No package directory: no game revision, and the run's commit is the engine's."""
    revision = game_source_revision(game=scene_class_in(module='no_such_game_package.game'))

    assert revision is None
    row = a_row(run=a_run(engine_revision=ENGINE_REVISION, game_revision=revision))
    assert row.commit == ENGINE_COMMIT
    assert short_commit(run=row.run) == ENGINE_COMMIT[:7]


def test_a_game_outside_any_checkout_names_an_unknown_revision(tmp_path, monkeypatch):
    """A game found, but in no checkout, archive or stamp: unknown, never the engine's commit."""
    game = write_stand_in_game(directory=tmp_path)
    use_stand_in_game(install_directory=tmp_path, monkeypatch=monkeypatch)

    revision = game_source_revision(game=scene_class_in(module=f'{game.package}.game'))

    assert revision == UNKNOWN_REVISION


def a_run(
    *, engine_revision: SourceRevision | None, game_revision: SourceRevision | None
) -> MeasurementRun:
    """Return a run naming the given revisions.

    Returns:
        The run.

    """
    return MeasurementRun(
        machine=MACHINE,
        processing_paced=False,
        engine_version=None,
        pygame_version='2.0',
        python_version='3.14',
        measured_at='2026-10-26T12:00:00+00:00',
        rebaselined_from=None,
        hash_scheme=1,
        source_revision=engine_revision,
        game_source_revision=game_revision,
    )


def a_row(*, run: MeasurementRun, code_tree: str | None = None) -> LedgerRow:
    """Return a measured row of a run.

    Returns:
        The row.

    """
    return LedgerRow(
        recording='run.jsonl.gz',
        console_script='stand-in-rally',
        origin=LedgerOrigin.REPLAY_METRICS,
        run=run,
        summary=None,
        content_hash=None,
        frame_count=None,
        frames_changed=None,
        rebaseline_exit=None,
        allowed_uncommitted_changes=False,
        code_tree=code_tree,
    )


ENGINE_REVISION = SourceRevision(
    source=RevisionSource.BUILD_STAMP,
    commit=ENGINE_COMMIT,
    committed_at='2026-10-20T12:00:00+00:00',
    uncommitted_changes=False,
)
GAME_REVISION = SourceRevision(
    source=RevisionSource.GIT_CHECKOUT,
    commit=ANOTHER_REPOSITORYS_COMMIT,
    committed_at='2026-10-25T12:00:00+00:00',
    uncommitted_changes=True,
)


def test_a_run_without_a_game_revision_uses_the_engines():
    """A run from before the field names the engine's revision, and its row the engine's commit."""
    run = a_run(engine_revision=ENGINE_REVISION, game_revision=None)

    assert run.game_or_engine_revision == ENGINE_REVISION
    assert a_row(run=run).commit == ENGINE_REVISION.commit


def test_a_runs_game_revision_names_its_commit_and_state():
    """The game's commit, date and uncommitted changes, not the engine's."""
    row = a_row(run=a_run(engine_revision=ENGINE_REVISION, game_revision=GAME_REVISION))

    assert row.run.game_or_engine_revision == GAME_REVISION
    assert row.commit == ANOTHER_REPOSITORYS_COMMIT
    assert row.measured_uncommitted_changes
    assert short_commit(run=row.run) == ANOTHER_REPOSITORYS_COMMIT[:7]


def test_an_unknown_game_revision_is_not_replaced_by_the_engines():
    """A game whose revision is unknown has no commit: the engine's is never put in its place."""
    row = a_row(run=a_run(engine_revision=ENGINE_REVISION, game_revision=UNKNOWN_REVISION))

    assert row.commit is None
    assert not row.measured_uncommitted_changes
    assert short_commit(run=row.run) is None


def test_rows_are_ordered_by_the_games_commit_date():
    """The game's commit date orders the rows, not the engine's."""
    older_game = GAME_REVISION.model_copy(update={'committed_at': '2026-10-01T12:00:00+00:00'})
    newer_engine = ENGINE_REVISION.model_copy(update={'committed_at': '2026-10-30T12:00:00+00:00'})
    first = a_row(run=a_run(engine_revision=newer_engine, game_revision=older_game))
    second = a_row(
        run=a_run(engine_revision=ENGINE_REVISION, game_revision=GAME_REVISION).model_copy(
            update={'machine': 'another machine'}
        )
    )

    assert merge_ledgers(ledgers=[[second, first]]) == [first, second]


def test_another_repositorys_landed_row_relabels_only_the_games_revision():
    """The code tree is the game's project's: its landing commit is the game's, not the engine's."""
    row = a_row(
        run=a_run(engine_revision=ENGINE_REVISION, game_revision=GAME_REVISION),
        code_tree=CODE_TREE,
    )

    (landed,) = landed_rows(rows=[row], landed={CODE_TREE: LANDED_COMMIT}, keep_unlanded=False)

    assert landed.commit == LANDED_COMMIT.commit
    assert landed.run.game_source_revision == GAME_REVISION.model_copy(
        update={
            'commit': LANDED_COMMIT.commit,
            'committed_at': LANDED_COMMIT.committed_at,
            'uncommitted_changes': False,
        }
    )
    assert landed.run.source_revision == ENGINE_REVISION


def test_an_unknown_engine_revision_is_not_labelled_with_the_games_landing():
    """Two unknown commits are not one checkout: only the game's revision takes the landing."""
    row = a_row(
        run=a_run(engine_revision=UNKNOWN_REVISION, game_revision=UNKNOWN_REVISION),
        code_tree=CODE_TREE,
    )

    (landed,) = landed_rows(rows=[row], landed={CODE_TREE: LANDED_COMMIT}, keep_unlanded=False)

    assert landed.commit == LANDED_COMMIT.commit
    assert landed.run.source_revision == UNKNOWN_REVISION
