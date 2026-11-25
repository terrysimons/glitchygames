"""No ``assert`` outside tests, in any Python file the repository tracks.

``python -O`` strips every ``assert``, so a check written as one is no check at all in an
optimized run (the owner's rule: never ``assert`` outside tests; a None-check is
``glitchygames.checks.required``, anything else an explicit raise). ruff's S101 enforces it
wherever ruff lints, and security-scan's bandit B101 run in the shipped packages. This covers
the rest: ruff's ``include`` leaves some tracked files out (``browser/``, ``ansible/``,
``src/quicklook/``, the root ``conftest.py``), and bandit scans only the packages.

Where an assert is allowed is read from ruff's own per-file ignores (a glob whose ignores hold
S101), in every tracked pyproject.toml that has them (the repository's, and a nested project's
such as services/ai-service/, whose globs are relative to its folder as ruff reads them), so
there is one definition of "a test file", not a second copy here.
"""

from __future__ import annotations

import ast
import os
import tomllib
from pathlib import Path, PurePosixPath

from glitchygames.process import OutputCapture, run_command
from tests.ast_scanning import PROJECT_ROOT

GIT_TIMEOUT_SECONDS = 60
ASSERT_RULE = 'S101'
# A file that holds an assert, and one that doesn't
ASSERTING_SOURCE = 'def ready(value):\n    assert value is not None\n    return value\n'
PLAIN_SOURCE = 'VALUE = 1\n'
# Where an assert is allowed in the stand-in projects below
STAND_IN_TEST_GLOBS = ('tests/**/*.py', 'src/games/*/tests/**/*.py')


def globs_allowing_asserts(*, project_root: Path, files: list[str]) -> tuple[str, ...]:
    """Return ruff's per-file-ignore globs whose ignores hold S101: where tests live.

    Each tracked pyproject.toml with ruff per-file ignores contributes its globs, made relative
    to the repository (ruff reads a nested project's globs relative to its own folder).

    Args:
        project_root: The repository.
        files: The tracked files, relative to it.

    Returns:
        The globs, by configuration file, each in its file's order.

    """
    globs: list[str] = []
    for name in sorted(files):
        if PurePosixPath(name).name != 'pyproject.toml':
            continue
        settings = tomllib.loads((project_root / name).read_text(encoding='utf-8'))
        per_file_ignores: dict[str, list[str]] = (
            settings.get('tool', {}).get('ruff', {}).get('lint', {}).get('per-file-ignores', {})
        )
        folder = PurePosixPath(name).parent
        globs.extend(
            (folder / glob).as_posix()
            for glob, rules in per_file_ignores.items()
            if ASSERT_RULE in rules
        )
    return tuple(globs)


def tracked_files(*, project_root: Path, pattern: str) -> list[str]:
    """Return every file git tracks in the repository matching ``pattern``, relative to it.

    Returns:
        The paths, POSIX-style.

    """
    completed = run_command(
        command=['git', 'ls-files', '-z', '--', pattern],
        environment=os.environ,
        working_directory=project_root,
        capture_output=OutputCapture.APART,
        timeout_seconds=GIT_TIMEOUT_SECONDS,
    )
    return [name for name in completed.stdout.split('\0') if name]


def asserts_outside_tests(
    *, project_root: Path, files: list[str], test_globs: tuple[str, ...]
) -> dict[str, list[int]]:
    """Find every assert in ``files`` that no test glob covers.

    Returns:
        The line of each assert, by file, for each file holding one.

    """
    found: dict[str, list[int]] = {}
    for name in files:
        if any(PurePosixPath(name).full_match(glob) for glob in test_globs):
            continue
        source_path = project_root / name
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        lines = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Assert)]
        if lines:
            found[name] = sorted(lines)
    return found


def write_stand_in_project(*, project_root: Path, files: dict[str, str]) -> list[str]:
    """Write a stand-in project's files.

    Returns:
        The files' names, as git would list them.

    """
    for name, source in files.items():
        path = project_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')
    return sorted(files)


def test_no_tracked_python_file_outside_the_tests_holds_an_assert():
    """Raise instead: ``required(value, what=...)`` for a None-check, else the error that fits."""
    test_globs = globs_allowing_asserts(
        project_root=PROJECT_ROOT,
        files=tracked_files(project_root=PROJECT_ROOT, pattern='*pyproject.toml'),
    )
    files = tracked_files(project_root=PROJECT_ROOT, pattern='*.py')

    found = asserts_outside_tests(project_root=PROJECT_ROOT, files=files, test_globs=test_globs)

    assert found == {}, f'raise instead of asserting (file: lines): {found}'


def test_the_test_globs_come_from_ruff_and_cover_the_suites():
    """The globs are read, not empty: the engine's, each member layer's and the service's."""
    test_globs = globs_allowing_asserts(
        project_root=PROJECT_ROOT,
        files=tracked_files(project_root=PROJECT_ROOT, pattern='*pyproject.toml'),
    )

    assert {
        'tests/**/*.py',
        'src/games/*/tests/**/*.py',
        'src/demos/*/tests/**/*.py',
        'src/apps/*/tests/**/*.py',
        'services/ai-service/tests/**',
    } <= set(test_globs)


def test_a_nested_projects_globs_are_read_relative_to_its_folder(tmp_path: Path):
    """A nested pyproject.toml's S101 glob is prefixed with its folder; other rules are not read."""
    files = write_stand_in_project(
        project_root=tmp_path,
        files={
            'pyproject.toml': (
                '[tool.ruff.lint.per-file-ignores]\n'
                '"tests/**/*.py" = ["S101"]\n"tools/*.py" = ["T201"]\n'
            ),
            'services/helper/pyproject.toml': (
                '[tool.ruff.lint.per-file-ignores]\n"tests/**" = ["D", "S101"]\n'
            ),
            'src/games/rally/pyproject.toml': '[project]\nname = "rally"\n',
        },
    )

    assert globs_allowing_asserts(project_root=tmp_path, files=files) == (
        'tests/**/*.py',
        'services/helper/tests/**',
    )


def test_the_scan_reads_the_files_ruff_does_not_lint():
    """The tracked files include ones outside ruff's include, as browser/'s are."""
    files = tracked_files(project_root=PROJECT_ROOT, pattern='*.py')

    assert 'browser/boot.py' in files
    assert 'src/glitchygames/checks.py' in files


def test_an_assert_in_a_file_ruff_does_not_lint_is_found(tmp_path: Path):
    """A planted assert in browser/ is reported with its line; a test's own assert is not."""
    files = write_stand_in_project(
        project_root=tmp_path,
        files={
            'browser/boot.py': ASSERTING_SOURCE,
            'tests/test_boot.py': ASSERTING_SOURCE,
        },
    )

    found = asserts_outside_tests(
        project_root=tmp_path, files=files, test_globs=STAND_IN_TEST_GLOBS
    )

    assert found == {'browser/boot.py': [2]}


def test_an_assert_in_a_member_module_is_found(tmp_path: Path):
    """A planted assert in a game's source is reported; its tests' asserts are not."""
    files = write_stand_in_project(
        project_root=tmp_path,
        files={
            'src/games/rally/src/rally/game.py': ASSERTING_SOURCE,
            'src/games/rally/src/rally/__init__.py': PLAIN_SOURCE,
            'src/games/rally/tests/test_rally.py': ASSERTING_SOURCE,
        },
    )

    found = asserts_outside_tests(
        project_root=tmp_path, files=files, test_globs=STAND_IN_TEST_GLOBS
    )

    assert found == {'src/games/rally/src/rally/game.py': [2]}
