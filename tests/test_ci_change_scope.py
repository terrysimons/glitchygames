"""Tests for scripts/ci_change_scope.py: which tests a CircleCI pipeline runs for a change.

A change whose every path is Markdown (the pre-commit hooks' own definition) skips the test jobs
and runs the Markdown checks instead; anything else, main, or a change it can't read runs
everything (the owner, 2026-11-20, via the coordinator: docs-only PRs skip the test jobs).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

import pytest
import yaml
from scripts import ci_change_scope

from glitchygames.process import OutputCapture, run_command
from tests.ledger_repositories import PROJECT_ROOT, git

# Changes of Markdown only: plans, bugs, the docs' prose, the rules, the root files, a member's
MARKDOWN_PATHS = (
    'plans/future-work.md',
    'bugs/2026-11-20-a-bug.md',
    'docs/architecture/sound.md',
    '.claude/rules/website.md',
    'CLAUDE.md',
    'BUGS.md',
    'src/apps/bitmappy/BITMAPPY_ARCHITECTURE.md',
)
# Paths that run everything: code, tests, CI, the noxfile, the project's settings and lock, a
# docs file that isn't Markdown (an image, a script, the site's configuration), near misses
OTHER_PATHS = (
    'src/glitchygames/engine/__init__.py',
    'tests/test_claude_md.py',
    '.circleci/config.yml',
    '.circleci/continue_config.yml',
    'noxfile.py',
    'pyproject.toml',
    'uv.lock',
    '.pre-commit-config.yaml',
    'docs/images/arcade.png',
    'docs/javascripts/extra.js',
    'docs/includes/abbreviations.md.bak',
    'zensical.yml',
    'scripts/ci_change_scope.py',
    'README.markdown',
    'docs/NOTES.MD',
)


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway repository: a main branch with code and docs, and a branch checked out."""
    for name in [name for name in os.environ if name.startswith('GIT_')]:
        monkeypatch.delenv(name)
    root = tmp_path / 'repository'
    root.mkdir()
    git(repository=root, arguments=['init', '--quiet', '--initial-branch=main'])
    (root / 'engine.py').write_text('VALUE = 1\n', encoding='utf-8')
    (root / 'notes.md').write_text('# Notes\n', encoding='utf-8')
    git(repository=root, arguments=['add', '.'])
    git(repository=root, arguments=['commit', '--quiet', '-m', 'main'])
    git(repository=root, arguments=['switch', '--quiet', '-c', 'feature'])
    return root


def test_a_markdown_only_change_skips_the_test_jobs():
    """Every path Markdown, on a branch: the Markdown checks only."""
    for paths in ([path] for path in MARKDOWN_PATHS):
        assert ci_change_scope.choose_test_scope(branch='feature', paths=paths) == 'markdown'
    assert (
        ci_change_scope.choose_test_scope(branch='feature', paths=list(MARKDOWN_PATHS))
        == 'markdown'
    )


def test_any_other_path_runs_everything():
    """One path that isn't Markdown, alone or among Markdown, runs every test job."""
    for path in OTHER_PATHS:
        assert ci_change_scope.choose_test_scope(branch='feature', paths=[path]) == 'all', path
        assert (
            ci_change_scope.choose_test_scope(branch='feature', paths=[*MARKDOWN_PATHS, path])
            == 'all'
        ), path


def test_main_and_unknown_changes_run_everything():
    """Main always runs everything; so does no branch (a tag), no paths, or paths unread."""
    markdown = list(MARKDOWN_PATHS)

    assert ci_change_scope.choose_test_scope(branch='main', paths=markdown) == 'all'
    assert ci_change_scope.choose_test_scope(branch=None, paths=markdown) == 'all'
    assert ci_change_scope.choose_test_scope(branch='', paths=markdown) == 'all'
    assert ci_change_scope.choose_test_scope(branch='feature', paths=[]) == 'all'
    assert ci_change_scope.choose_test_scope(branch='feature', paths=None) == 'all'


def test_the_definition_is_the_pre_commit_hooks_own():
    """The hooks' ``exclude`` (a Markdown-only change runs no hook) is this script's pattern.

    One definition: .pre-commit-config.yaml names the pattern, and the script decides with the
    same one, so a path the hooks treat as Markdown is the one CI treats as Markdown.
    """
    hooks = yaml.safe_load((PROJECT_ROOT / '.pre-commit-config.yaml').read_text(encoding='utf-8'))

    assert hooks['exclude'] == ci_change_scope.MARKDOWN_PATTERN
    for path in (*MARKDOWN_PATHS, *OTHER_PATHS):
        hooks_skip = re.search(hooks['exclude'], path) is not None
        assert hooks_skip == ci_change_scope.changes_only_markdown(paths=[path]), path


def _bash_path(path: Path) -> str:
    """A path as bash reads it in a script: forward slashes, quoted.

    Git Bash on Windows takes ``C:/...``, but an unquoted Windows path loses its backslashes
    to bash (CircleCI job 4618), and a space would split it in two.

    Returns:
        The path, ready to paste into the setup step's text.

    """
    return shlex.quote(path.as_posix())


def _setup_step_command(*, files_directory: Path) -> tuple[str, Path]:
    """.circleci/config.yml's choosing step, as this checkout runs it.

    Everything but the fetch (the repository's main stands in for origin/main), with this
    checkout's script and the test's Python in place of ``python3 scripts/...``, and its two
    files (the changed paths, the parameters) in files_directory. Every path pasted in goes
    through ``_bash_path``.

    Returns:
        The step's script, for ``bash -c``, and where it writes the parameters.

    """
    setup = yaml.safe_load((PROJECT_ROOT / '.circleci' / 'config.yml').read_text(encoding='utf-8'))
    (job,) = setup['jobs'].values()
    command = '\n'.join(
        line for line in job['steps'][1]['run']['command'].splitlines() if 'git fetch' not in line
    )
    command = command.replace(
        'python3 scripts/ci_change_scope.py',
        f'{_bash_path(Path(sys.executable))} '
        f'{_bash_path(PROJECT_ROOT / "scripts" / "ci_change_scope.py")}',
    )
    files = re.search(r'--paths (?P<paths>\S+) \\\n\s+--output (?P<output>\S+)', command)
    assert files is not None, command
    for name in ('paths', 'output'):
        command = command.replace(files[name], _bash_path(files_directory / Path(files[name]).name))
    return command, files_directory / Path(files['output']).name


def _run_the_setup_step(*, repository: Path, files_directory: Path) -> tuple[str, dict[str, str]]:
    """Run the choosing step in a repository, as CircleCI runs it.

    Returns:
        What the step printed, and the parameters it wrote.

    """
    command, output = _setup_step_command(files_directory=files_directory)
    git(repository=repository, arguments=['update-ref', 'refs/remotes/origin/main', 'main'])
    environment = {
        name: value for name, value in os.environ.items() if not name.startswith('GIT_')
    } | {'CIRCLE_BRANCH': 'feature'}
    completed = run_command(
        command=['bash', '-c', command],
        environment=environment,
        timeout_seconds=60.0,
        capture_output=OutputCapture.TOGETHER,
        working_directory=repository,
    )
    assert completed.returncode == 0, completed.stdout
    parameters = json.loads(output.read_text(encoding='utf-8'))
    return completed.stdout or '', parameters


def test_the_setup_step_reads_the_branchs_change_since_it_left_main(repository, tmp_path):
    """Markdown changed since the merge-base: markdown, and the step names the path."""
    (repository / 'notes.md').write_text('# Notes, revised\n', encoding='utf-8')
    git(repository=repository, arguments=['commit', '--quiet', '-am', 'notes'])

    printed, parameters = _run_the_setup_step(repository=repository, files_directory=tmp_path)

    assert parameters == {'test-scope': 'markdown'}
    assert 'Test scope: markdown' in printed
    assert 'notes.md' in printed


def test_the_setup_step_runs_everything_for_a_code_change(repository, tmp_path):
    """Code changed alongside Markdown: all."""
    (repository / 'notes.md').write_text('# Notes, revised\n', encoding='utf-8')
    (repository / 'engine.py').write_text('VALUE = 2\n', encoding='utf-8')
    git(repository=repository, arguments=['commit', '--quiet', '-am', 'both'])

    _, parameters = _run_the_setup_step(repository=repository, files_directory=tmp_path)

    assert parameters == {'test-scope': 'all'}


def test_a_code_file_renamed_to_markdown_runs_everything(repository, tmp_path):
    """Both sides of a rename are listed, so renaming code to .md is not a Markdown-only change."""
    git(repository=repository, arguments=['mv', 'engine.py', 'engine.md'])
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'rename'])

    printed, parameters = _run_the_setup_step(repository=repository, files_directory=tmp_path)

    assert parameters == {'test-scope': 'all'}
    assert 'engine.md, engine.py' in printed


def test_the_setup_step_takes_paths_bash_would_otherwise_split_or_unescape(repository, tmp_path):
    """Its files in a folder whose name has a space and a backslash: the step still writes them.

    Windows' paths reached bash unquoted and lost their backslashes (CircleCI job 4618); this
    checks the same substitution on any platform.
    """
    (repository / 'notes.md').write_text('# Notes, revised\n', encoding='utf-8')
    git(repository=repository, arguments=['commit', '--quiet', '-am', 'notes'])
    files_directory = tmp_path / 'step files\\here'
    files_directory.mkdir()

    _, parameters = _run_the_setup_step(repository=repository, files_directory=files_directory)

    assert parameters == {'test-scope': 'markdown'}
    assert (files_directory / 'changed-paths.txt').read_text(encoding='utf-8') == 'notes.md\n'


def test_no_list_of_changed_paths_runs_everything(tmp_path, monkeypatch, capsys):
    """No list (git found no merge-base): all, and the script says why."""
    monkeypatch.setenv('CIRCLE_BRANCH', 'feature')
    output = tmp_path / 'parameters.json'

    exit_code = ci_change_scope.main([
        '--paths',
        str(tmp_path / 'missing.txt'),
        '--output',
        str(output),
    ])

    assert exit_code == 0
    assert json.loads(output.read_text(encoding='utf-8')) == {'test-scope': 'all'}
    assert 'git could not tell' in capsys.readouterr().out
