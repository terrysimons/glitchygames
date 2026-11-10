"""Paired runs: two versions of the behaviour suite asked the same questions, on one server.

One run's pass rate moves about 8 points from run to run (plans/lucid-circuit-5-load-harness.md,
Part 2b), so two separate runs can't show a smaller change. Here every question and repeat is
asked of both versions back to back on one llama-server, in an order a seeded coin picks, so drift
and warmth fall on both alike; ``report.py`` then compares them pair by pair (McNemar's exact
test), which only the questions one version passed and the other failed can move.

A version is a git ref, or ``WORKTREE`` for the working tree as it stands. A ref's ``scripts/`` is
exported (``git archive``) into a temporary directory. Snapshots are generated, not committed, so
every version reads the working tree's. Each version answers in a worker process of its own whose
current directory is its tree, so ``scripts.ai_behaviour`` there is that version's: the worker is
``WORKER_PROGRAM``, handed over with ``python -c``, and needs only ``run.ask(target=, question=)``
and ``questions.QUESTIONS``, which every version since the suite began has.

Writes ``OUTPUT/old/GAME/`` and ``OUTPUT/new/GAME/`` (each like ``run.py``'s, every result with its
``pair``) and ``OUTPUT/pairing.json``. Report with
``uv run python -m scripts.ai_behaviour.report OUTPUT/old OUTPUT/new``.

Usage (the old version is HEAD and the new one the working tree, unless ``--old``/``--new`` say):
    uv run python -m scripts.ai_behaviour.paired --game paddleslap --output test-results/paired
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs this interpreter, never a shell
import sys
import tarfile
import tempfile
from contextlib import ExitStack
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Self

from glitchygames.ai_link import install_root
from scripts.ai_behaviour.capture import FIXTURES_DIRECTORY
from scripts.ai_behaviour.questions import QUESTIONS, BehaviourQuestion
from scripts.ai_behaviour.run import DEFAULT_CONFIGURATION, DEFAULT_REPEATS, summary
from scripts.ai_model_comparison import (
    COMPARISON_PORT,
    AskedOf,
    parse_configuration,
    running_server,
    say,
    service_is_running,
)
from scripts.git_checkout import run_git

if TYPE_CHECKING:
    from collections.abc import Iterator

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WORKING_TREE = 'WORKTREE'
VERSIONS = ('old', 'new')
DEFAULT_SEED = 20261107
WORKER_CLOSE_SECONDS = 30.0
EXIT_OPTIONS_REFUSED = 64
# Run from a version's tree: its first line on stdin is the server, then one question name a line.
# Anything the version prints goes to stderr, so stdout carries only one result a line
WORKER_PROGRAM = """
import json
import sys

answers = sys.stdout
sys.stdout = sys.stderr
from scripts.ai_behaviour.questions import QUESTIONS
from scripts.ai_behaviour.run import ask
from scripts.ai_model_comparison import AskedOf

target = AskedOf.model_validate_json(sys.stdin.readline())
by_name = {question.name: question for question in QUESTIONS}
for line in sys.stdin:
    name = line.strip()
    if name in by_name:
        result = ask(target=target, question=by_name[name])
    else:
        result = {'missing': name}
    answers.write(json.dumps(result) + '\\n')
    answers.flush()
"""


class VersionError(RuntimeError):
    """A version couldn't be exported, or its worker stopped answering."""


def exported_tree(*, ref: str, directory: Path) -> Path:
    """Give a version's tree: the working tree itself, or a ref's ``scripts/`` exported.

    Args:
        ref: A git ref, or ``WORKING_TREE``.
        directory: Where to export it: an empty directory, made if missing.

    Returns:
        The directory a worker runs in.

    Raises:
        VersionError: If git can't export the ref.

    """
    if ref == WORKING_TREE:
        return PROJECT_ROOT
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / 'scripts.tar'
    returncode, output = run_git(
        arguments=['archive', f'--output={archive}', ref, 'scripts'], directory=PROJECT_ROOT
    )
    if returncode != 0:
        message = f'git could not export {ref}: {output.strip()}'
        raise VersionError(message)
    with tarfile.open(archive) as exported:
        exported.extractall(directory, filter='data')
    archive.unlink()
    (directory / 'scripts' / 'ai_behaviour' / 'fixtures').symlink_to(FIXTURES_DIRECTORY)
    return directory


def first_answers(*, seed: int, count: int) -> Iterator[tuple[str, str]]:
    """Toss a seeded coin for each pair: which version answers first.

    Args:
        seed: The coin's seed, so a run can be repeated exactly.
        count: How many pairs.

    Yields:
        The versions in the order they answer, one pair at a time.

    """
    coin = random.Random(seed)  # ruff: ignore[suspicious-non-cryptographic-random-usage] - an order, not a secret
    for _pair in range(count):
        order = list(VERSIONS)
        coin.shuffle(order)
        yield order[0], order[1]


class Worker:
    """One version's answering process, asked one question at a time."""

    def __init__(self, *, tree: Path, target: AskedOf, log: IO[str]) -> None:
        """Start the worker in its tree, and tell it the server.

        Args:
            tree: The version's tree.
            target: The server both versions ask.
            log: Where the worker's own output goes.

        """
        self.tree = tree
        self.log_name = log.name
        self.process = subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] - this interpreter and our own program
            [sys.executable, '-c', WORKER_PROGRAM],
            cwd=tree,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
            env=dict(os.environ),
        )
        self._send(target.model_dump_json())

    def _send(self, line: str) -> None:
        """Write one line to the worker.

        Raises:
            VersionError: If the worker has no input pipe.

        """
        if self.process.stdin is None:
            message = 'the worker has no input'
            raise VersionError(message)
        self.process.stdin.write(line + '\n')
        self.process.stdin.flush()

    def ask(self, *, question_name: str) -> dict[str, Any]:
        """Have the version answer one question.

        Returns:
            Its result, as ``run.ask`` gives it.

        Raises:
            VersionError: If the worker stopped, or this version has no such question.

        """
        self._send(question_name)
        line = self.process.stdout.readline() if self.process.stdout else ''
        if not line:
            message = f'the worker in {self.tree} stopped: see {self.log_name}'
            raise VersionError(message)
        result: dict[str, Any] = json.loads(line)
        if 'missing' in result:
            message = f'the version in {self.tree} has no question {question_name}'
            raise VersionError(message)
        return result

    def close(self) -> None:
        """End the worker: no more questions."""
        if self.process.stdin is not None:
            self.process.stdin.close()
        self.process.wait(timeout=WORKER_CLOSE_SECONDS)
        if self.process.stdout is not None:
            self.process.stdout.close()

    def __enter__(self) -> Self:
        """Use it in a with block.

        Returns:
            Itself.

        """
        return self

    def __exit__(self, *_exception: object) -> None:
        """End the worker as the block ends."""
        self.close()


def ask_pairs(
    *,
    workers: dict[str, Worker],
    pairs: list[tuple[int, BehaviourQuestion]],
    seed: int,
    files: dict[str, IO[str]],
) -> dict[str, list[dict[str, Any]]]:
    """Ask every pair of both versions, in the coin's order, keeping each result as it comes.

    Args:
        workers: Each version's worker.
        pairs: Each repeat and question.
        seed: The coin's seed.
        files: Each version's open ``results.jsonl``.

    Returns:
        Each version's results.

    """
    results: dict[str, list[dict[str, Any]]] = {version: [] for version in VERSIONS}
    for (repeat, question), order in zip(
        pairs, first_answers(seed=seed, count=len(pairs)), strict=True
    ):
        for position, version in enumerate(order):
            result = {
                'repeat': repeat,
                'pair': f'{question.name}#{repeat}',
                'answered_first': position == 0,
                **workers[version].ask(question_name=question.name),
            }
            results[version].append(result)
            files[version].write(json.dumps(result) + '\n')
            files[version].flush()
        verdicts = (
            f'{version} {"pass" if results[version][-1]["passed"] else "FAIL"}'
            for version in VERSIONS
        )
        say(f'{question.name} #{repeat}: {", ".join(verdicts)}')
    return results


def write_outcome(
    *,
    output: Path,
    pairing: dict[str, Any],
    results: dict[str, list[dict[str, Any]]],
    server: dict[str, Any],
) -> None:
    """Write each version's server facts and summary, and what the pairing was.

    Args:
        output: The run's directory.
        pairing: The game, both refs, the seed, the repeats and the configuration.
        results: Each version's results.
        server: The server's facts, which both versions shared.

    """
    for version in VERSIONS:
        directory = output / version / pairing['game']
        (directory / 'server.json').write_text(json.dumps(server), encoding='utf-8')
        (directory / 'summary.md').write_text(summary(results=results[version]), encoding='utf-8')
    (output / 'pairing.json').write_text(json.dumps(pairing), encoding='utf-8')
    say(f'Report: uv run python -m scripts.ai_behaviour.report {output / "old"} {output / "new"}')


def parse_options(arguments: list[str] | None) -> argparse.Namespace:
    """Read the command line.

    Returns:
        The options.

    """
    parser = argparse.ArgumentParser(description='Paired AI behaviour runs of two versions.')
    parser.add_argument('--game', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--old', default='HEAD', help=f'A git ref, or {WORKING_TREE}')
    parser.add_argument('--new', default=WORKING_TREE, help=f'A git ref, or {WORKING_TREE}')
    parser.add_argument('--configuration', default=DEFAULT_CONFIGURATION)
    parser.add_argument('--repeats', type=int, default=DEFAULT_REPEATS)
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED)
    parser.add_argument('--only', default='', help='Only questions with this in their name')
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    """Ask a game's questions of two versions, in pairs.

    Returns:
        The exit code: 0 when every pair was asked, whatever the answers.

    """
    options = parse_options(arguments)
    root = install_root()
    if service_is_running(root=root):
        say('The AI service is running: stop it first (ai-service.sh stop).')
        return EXIT_OPTIONS_REFUSED
    refs = {'old': options.old, 'new': options.new}
    for version in VERSIONS:
        (options.output / version / options.game).mkdir(parents=True, exist_ok=True)
    configuration = parse_configuration(options.configuration)
    pairs = [
        (repeat, question)
        for repeat in range(options.repeats)
        for question in QUESTIONS
        if question.game == options.game and options.only in question.name
    ]
    with ExitStack() as stack:
        trees = {
            version: exported_tree(
                ref=refs[version],
                directory=Path(stack.enter_context(tempfile.TemporaryDirectory())),
            )
            for version in VERSIONS
        }
        target, load_seconds, read_footprint = stack.enter_context(
            running_server(
                root=root,
                configuration=configuration,
                port=COMPARISON_PORT,
                log_path=options.output / f'server-{configuration.name}.log',
            )
        )
        workers = {
            version: stack.enter_context(
                Worker(
                    tree=trees[version],
                    target=target,
                    log=stack.enter_context(
                        (options.output / f'worker-{version}.log').open('w', encoding='utf-8')
                    ),
                )
            )
            for version in VERSIONS
        }
        files = {
            version: stack.enter_context(
                (options.output / version / options.game / 'results.jsonl').open(
                    'w', encoding='utf-8'
                )
            )
            for version in VERSIONS
        }
        results = ask_pairs(workers=workers, pairs=pairs, seed=options.seed, files=files)
        server = {
            'configuration': configuration.name,
            'load_seconds': load_seconds,
            'footprint_mebibytes': read_footprint(),
        }
    write_outcome(
        output=options.output,
        pairing={
            'game': options.game,
            **refs,
            'seed': options.seed,
            'repeats': options.repeats,
            'configuration': configuration.name,
        },
        results=results,
        server=server,
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
