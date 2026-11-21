"""Choose which tests a CircleCI pipeline runs: every test job, or only the Markdown checks.

A change whose every path is Markdown (``MARKDOWN_PATTERN``, the pre-commit hooks' own
``exclude``: a Markdown-only change runs no hook) leaves out the test jobs and runs the Markdown
checks instead: the strict docs build and the tests that read Markdown (the owner, 2026-11-20, via
the coordinator: a plan-only pull request waited hours for the single macOS queue). Main always
runs everything, as does a pipeline with no branch (a tag) or a change this can't read.

CircleCI's setup configuration (.circleci/config.yml) runs this before anything is installed, so
it uses Python's standard library only and runs nothing itself: the setup step lists the change
with git (every path that differs between the branch and its merge-base with origin/main, both
sides of a rename, ``--no-renames``, so code renamed to ``.md`` runs everything) into a file, or
leaves no file when git can't tell, and this reads it and writes the ``test-scope`` parameter the
continuation passes to .circleci/continue_config.yml::

    python3 scripts/ci_change_scope.py --paths CHANGED_PATHS_FILE --output PARAMETERS_FILE

Tests: tests/test_ci_change_scope.py; the configuration's side: tests/test_ci_config.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

# A Markdown path: .pre-commit-config.yaml's exclude, the one definition (a test holds them equal)
MARKDOWN_PATTERN: Final = r'\.md$'
TEST_SCOPE_ALL: Final = 'all'
TEST_SCOPE_MARKDOWN: Final = 'markdown'
# continue_config.yml's test-scope values, in its enum's order
TEST_SCOPES: Final = (TEST_SCOPE_ALL, TEST_SCOPE_MARKDOWN)
# The branch whose every pipeline runs everything (merges, and the deploys after them)
ALWAYS_TESTED_BRANCH: Final = 'main'


def changes_only_markdown(*, paths: Sequence[str]) -> bool:
    """Tell whether a change holds Markdown only.

    Args:
        paths: The changed paths, as git names them.

    Returns:
        True when there is at least one path and every one is Markdown.

    """
    return bool(paths) and all(re.search(MARKDOWN_PATTERN, path) for path in paths)


def choose_test_scope(*, branch: str | None, paths: Sequence[str] | None) -> str:
    """Choose the pipeline's test scope.

    Args:
        branch: The pipeline's branch (``CIRCLE_BRANCH``), or None or empty for a tag.
        paths: The changed paths, or None when they couldn't be read.

    Returns:
        ``markdown`` for a branch other than main whose change is Markdown only, else ``all``.

    """
    if not branch or branch == ALWAYS_TESTED_BRANCH or paths is None:
        return TEST_SCOPE_ALL
    return TEST_SCOPE_MARKDOWN if changes_only_markdown(paths=paths) else TEST_SCOPE_ALL


def read_changed_paths(*, paths_file: Path) -> list[str] | None:
    """Read the change the setup step listed: one path a line.

    Args:
        paths_file: The list git wrote (``git diff --name-only --no-renames``).

    Returns:
        The paths, sorted; None when there is no list (git couldn't tell).

    """
    if not paths_file.is_file():
        return None
    return sorted(line for line in paths_file.read_text(encoding='utf-8').splitlines() if line)


def main(argv: Sequence[str] | None = None) -> int:
    """Write the pipeline's parameters for the continuation and print the choice.

    Args:
        argv: The arguments (``--paths``, ``--output``), or None for the command line's.

    Returns:
        0: the parameters are written whatever the choice.

    """
    parser = argparse.ArgumentParser(description='Choose which tests a CircleCI pipeline runs.')
    parser.add_argument('--paths', type=Path, required=True, help="git's list of changed paths")
    parser.add_argument('--output', type=Path, required=True, help='the parameters JSON file')
    arguments = parser.parse_args(argv)
    branch = os.environ.get('CIRCLE_BRANCH')
    paths = read_changed_paths(paths_file=arguments.paths)
    scope = choose_test_scope(branch=branch, paths=paths)
    arguments.output.write_text(json.dumps({'test-scope': scope}) + '\n', encoding='utf-8')
    if paths is None:
        changed = f'no list of changed paths ({arguments.paths}): git could not tell'
    else:
        changed = f'{len(paths)} changed path(s): ' + ', '.join(paths)
    sys.stdout.write(f'Test scope: {scope} (branch {branch or "none"}; {changed})\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
