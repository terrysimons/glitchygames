"""scripts/patch_pre_push_hook.py: the pre-push hook survives a non-blocking stdout and stderr.

The hook under test is the one the real ``pre-commit install`` writes (the contract is
pre-commit's own template), with its interpreter replaced by a stand-in that "runs pre-commit"
by writing one large burst of output, as the real one does when a hook ends. The pipe is the
one ``git push 2>&1 | tail`` makes with OpenSSH in the middle: its write end is non-blocking
(OpenSSH sets O_NONBLOCK on the shared open file description) and its reader is slow.
"""

from __future__ import annotations

import io
import os
import shutil
import stat
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from scripts import patch_pre_push_hook
from scripts.patch_pre_push_hook import (
    CLEARING_STEP,
    PATCH_MARKER,
    SHIM_ANCHOR,
    PatchOutcome,
    patch_hook,
    patched_text,
    pre_push_hook_path,
    run,
)

from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command, start_command, stop_command

if TYPE_CHECKING:
    from typing import TextIO

BURST_BYTES = 512 * 1024
# The slow reader: 4 KiB per millisecond at most, far slower than a writer's write calls
READ_CHUNK_BYTES = 4096
READ_PAUSE_SECONDS = 0.001
GIT_TIMEOUT_SECONDS = 60.0
HOOK_TIMEOUT_SECONDS = 120.0


def clean_environment() -> dict[str, str]:
    """Return this process's environment without git's own variables (a push hook sets them)."""
    return {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}


def git(*arguments: str, working_directory: Path) -> str:
    """Run git in a directory; return its output.

    Returns:
        Standard output.

    """
    finished = run_command(
        command=['git', *arguments],
        environment=clean_environment(),
        timeout_seconds=GIT_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=working_directory,
    )
    assert finished.returncode == 0, finished.stdout
    return finished.stdout


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A git repository whose pre-push hook the real ``pre-commit install`` wrote."""
    root = tmp_path / 'repository'
    root.mkdir()
    git('init', '--quiet', working_directory=root)
    (root / '.pre-commit-config.yaml').write_text('repos: []\n', encoding='utf-8')
    finished = run_command(
        command=[sys.executable, '-m', 'pre_commit', 'install', '--hook-type', 'pre-push'],
        environment=clean_environment(),
        timeout_seconds=GIT_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=root,
    )
    assert finished.returncode == 0, finished.stdout
    return root


def installed_hook(*, repository: Path) -> Path:
    """Return the pre-push hook pre-commit installed."""
    return repository / '.git' / 'hooks' / 'pre-push'


class TestPatching:
    """The step goes in once, before pre-commit starts, and nothing else changes."""

    def test_the_real_shim_gets_the_step_before_it_starts_pre_commit(self, repository: Path):
        hook = installed_hook(repository=repository)
        original = hook.read_text(encoding='utf-8')

        assert patch_hook(path=hook) is PatchOutcome.PATCHED

        patched = hook.read_text(encoding='utf-8')
        assert patched.replace(CLEARING_STEP, '') == original
        assert patched.index(PATCH_MARKER) < patched.index(SHIM_ANCHOR)
        assert 'os.set_blocking(1, True); os.set_blocking(2, True)' in patched

    def test_patching_twice_changes_nothing_the_second_time(self, repository: Path):
        hook = installed_hook(repository=repository)
        patch_hook(path=hook)
        once = hook.read_text(encoding='utf-8')

        assert patch_hook(path=hook) is PatchOutcome.ALREADY_PATCHED

        assert hook.read_text(encoding='utf-8') == once
        assert once.count(PATCH_MARKER) == 1

    def test_the_hook_stays_executable(self, repository: Path):
        hook = installed_hook(repository=repository)
        mode = hook.stat().st_mode

        patch_hook(path=hook)

        assert hook.stat().st_mode == mode
        assert hook.stat().st_mode & stat.S_IXUSR

    def test_pre_commit_reinstalling_the_shim_is_patched_again(self, repository: Path):
        hook = installed_hook(repository=repository)
        patch_hook(path=hook)
        hook.write_text(hook.read_text(encoding='utf-8').replace(CLEARING_STEP, ''))

        assert patch_hook(path=hook) is PatchOutcome.PATCHED

    def test_a_missing_hook_is_reported(self, tmp_path: Path):
        assert patch_hook(path=tmp_path / 'pre-push') is PatchOutcome.MISSING

    def test_a_hook_that_is_not_a_known_shim_is_refused_and_left_alone(self, tmp_path: Path):
        hook = tmp_path / 'pre-push'
        hook.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')

        assert patch_hook(path=hook) is PatchOutcome.UNRECOGNISED
        assert hook.read_text(encoding='utf-8') == '#!/bin/sh\nexit 0\n'
        assert patched_text(text='no anchor here\n') is None


class TestWhereTheHookIs:
    """The hooks folder is found as git finds it."""

    def test_a_repository(self, repository: Path):
        assert pre_push_hook_path(working_directory=repository).resolve() == (
            installed_hook(repository=repository).resolve()
        )

    def test_a_worktree_shares_its_repositorys_hooks(self, repository: Path, tmp_path: Path):
        git(
            '-c',
            'user.name=t',
            '-c',
            'user.email=t@example.com',
            'commit',
            '--allow-empty',
            '--quiet',
            '-m',
            'first',
            working_directory=repository,
        )
        worktree = tmp_path / 'worktree'
        git(
            'worktree', 'add', '--quiet', '-b', 'other', str(worktree), working_directory=repository
        )

        assert pre_push_hook_path(working_directory=worktree).resolve() == (
            installed_hook(repository=repository).resolve()
        )

    def test_core_hooks_path_is_honoured(self, repository: Path, tmp_path: Path):
        elsewhere = tmp_path / 'elsewhere'
        git('config', 'core.hooksPath', str(elsewhere), working_directory=repository)

        assert pre_push_hook_path(working_directory=repository) == elsewhere / 'pre-push'

    def test_outside_a_repository_is_an_error(self, tmp_path: Path):
        with pytest.raises(RuntimeError, match='git rev-parse'):
            pre_push_hook_path(working_directory=tmp_path)


def stand_in_pre_commit(*, folder: Path, result_file: Path) -> Path:
    """Write an interpreter stand-in: ``-c`` runs real Python; pre-commit is a burst of output.

    Args:
        folder: Where to write it.
        result_file: Where the burst writer records ``written`` or ``BlockingIOError``.

    Returns:
        The stand-in's path (the shim's ``INSTALL_PYTHON``).

    """
    burst = folder / 'burst.py'
    burst.write_text(
        'import os, sys\n'
        f'stream = sys.stdout if os.environ["BURST_STREAM"] == "stdout" else sys.stderr\n'
        'try:\n'
        f'    stream.buffer.write(b"x" * {BURST_BYTES})\n'
        '    stream.buffer.flush()\n'
        'except BlockingIOError:\n'
        f'    open({str(result_file)!r}, "w").write("BlockingIOError")\n'
        '    os._exit(1)\n'
        f'open({str(result_file)!r}, "w").write("written")\n',
        encoding='utf-8',
    )
    stand_in = folder / 'python-stand-in'
    stand_in.write_text(
        '#!/bin/sh\n'
        f'case "$1" in -c) exec {sys.executable} "$@";; *) exec {sys.executable} {burst};; esac\n',
        encoding='utf-8',
    )
    stand_in.chmod(0o755)
    return stand_in


def run_hook_into_a_slow_nonblocking_pipe(
    *, hook: Path, stream: str, result_file: Path
) -> tuple[int, int, str]:
    """Run a pre-push hook with stdout and stderr on a non-blocking pipe with a slow reader.

    The pipe's write end is non-blocking as OpenSSH leaves it, shared by the hook's fd 1 and
    fd 2; the reader takes 4 KiB at a time with a pause between.

    Returns:
        The hook's exit code, the bytes the reader received, and what the burst recorded.

    """
    read_end, write_end = os.pipe()
    os.set_blocking(write_end, False)
    received = 0

    def read_slowly() -> None:
        nonlocal received
        with os.fdopen(read_end, 'rb', buffering=0) as reader:
            while chunk := reader.read(READ_CHUNK_BYTES):
                received += len(chunk)
                time.sleep(READ_PAUSE_SECONDS)

    reader_thread = threading.Thread(target=read_slowly)
    reader_thread.start()
    try:
        environment = {**clean_environment(), 'BURST_STREAM': stream}
        with os.fdopen(write_end, 'w') as write_file:
            finished = run_hook_on(hook=hook, environment=environment, output=write_file)
    finally:
        reader_thread.join(timeout=60)
    recorded = result_file.read_text(encoding='utf-8') if result_file.exists() else ''
    return finished, received, recorded


def run_hook_on(*, hook: Path, environment: dict[str, str], output: TextIO) -> int:
    """Run a pre-push hook with standard output and error on one open file; return its code."""
    process = start_command(
        command=['bash', str(hook), 'origin', 'url'], environment=environment, output=output
    )
    try:
        return process.wait(timeout=HOOK_TIMEOUT_SECONDS)
    finally:
        stop_command(process=process)


class TestTheBlockingPipeFailure:
    """Reproduction: the unpatched hook dies writing a burst; the patched one does not."""

    @pytest.fixture
    def hook(self, repository: Path, tmp_path: Path) -> tuple[Path, Path]:
        result_file = tmp_path / 'result.txt'
        hook = installed_hook(repository=repository)
        text = hook.read_text(encoding='utf-8')
        installed = next(line for line in text.splitlines() if line.startswith('INSTALL_PYTHON='))
        stand_in = stand_in_pre_commit(folder=tmp_path, result_file=result_file)
        hook.write_text(text.replace(installed, f'INSTALL_PYTHON={stand_in}'), encoding='utf-8')
        return hook, result_file

    @pytest.mark.parametrize('stream', ['stdout', 'stderr'])
    def test_without_the_step_the_burst_raises_blocking_io_error(self, hook, stream: str):
        hook_path, result_file = hook

        code, _received, recorded = run_hook_into_a_slow_nonblocking_pipe(
            hook=hook_path, stream=stream, result_file=result_file
        )

        assert recorded == 'BlockingIOError'
        assert code != 0

    @pytest.mark.parametrize('stream', ['stdout', 'stderr'])
    def test_with_the_step_the_burst_arrives_whole(self, hook, stream: str):
        hook_path, result_file = hook
        assert patch_hook(path=hook_path) is PatchOutcome.PATCHED

        code, received, recorded = run_hook_into_a_slow_nonblocking_pipe(
            hook=hook_path, stream=stream, result_file=result_file
        )

        assert recorded == 'written'
        assert code == 0
        assert received == BURST_BYTES

    def test_the_patched_hook_still_runs_pre_commit_and_passes_its_arguments(
        self, repository: Path, tmp_path: Path
    ):
        hook = installed_hook(repository=repository)
        record = tmp_path / 'arguments.txt'
        stand_in = tmp_path / 'python-stand-in'
        stand_in.write_text(
            '#!/bin/sh\n'
            f'case "$1" in -c) exec {sys.executable} "$@";; esac\n'
            f'echo "$@" > {record}\n'
            'exit 7\n',
            encoding='utf-8',
        )
        stand_in.chmod(0o755)
        text = hook.read_text(encoding='utf-8')
        installed = next(line for line in text.splitlines() if line.startswith('INSTALL_PYTHON='))
        hook.write_text(text.replace(installed, f'INSTALL_PYTHON={stand_in}'), encoding='utf-8')
        patch_hook(path=hook)

        finished = run_command(
            command=['bash', str(hook), 'origin', 'url'],
            environment=clean_environment(),
            timeout_seconds=GIT_TIMEOUT_SECONDS,
            capture_output=OutputCapture.TOGETHER,
        )

        assert finished.returncode == 7, finished.stdout
        arguments = record.read_text(encoding='utf-8')
        assert arguments.startswith('-mpre_commit hook-impl')
        assert '--hook-type=pre-push' in arguments
        assert arguments.rstrip().endswith('-- origin url')

    def test_the_patched_hook_goes_on_when_no_interpreter_can_clear_the_flag(
        self, repository: Path, tmp_path: Path
    ):
        """No interpreter and no pre-commit on PATH: the step is skipped, the shim's tail runs."""
        hook = installed_hook(repository=repository)
        text = hook.read_text(encoding='utf-8')
        installed = next(line for line in text.splitlines() if line.startswith('INSTALL_PYTHON='))
        hook.write_text(text.replace(installed, 'INSTALL_PYTHON=/nonexistent'), encoding='utf-8')
        patch_hook(path=hook)
        only_dirname = tmp_path / 'bin'
        only_dirname.mkdir()
        (only_dirname / 'dirname').symlink_to(shutil.which('dirname') or '/usr/bin/dirname')

        finished = run_command(
            command=[shutil.which('bash') or '/bin/bash', str(hook), 'origin', 'url'],
            environment={'PATH': str(only_dirname)},
            timeout_seconds=GIT_TIMEOUT_SECONDS,
            capture_output=OutputCapture.TOGETHER,
        )

        assert finished.returncode == 1
        assert '`pre-commit` not found' in finished.stdout
        assert 'command not found' not in finished.stdout


class TestCommandLine:
    """The command patches this repository's hook, or the one given."""

    def test_patches_the_given_hook_and_says_so(self, repository: Path):
        log = io.StringIO()
        hook = installed_hook(repository=repository)

        assert run(arguments=[f'--hook={hook}'], log=log) == ExitCode.SUCCESS
        assert f'{hook}: patched' in log.getvalue()
        assert run(arguments=[f'--hook={hook}'], log=log) == ExitCode.SUCCESS
        assert f'{hook}: already patched' in log.getvalue()

    def test_a_missing_hook_exits_missing_input(self, tmp_path: Path):
        assert run(arguments=[f'--hook={tmp_path / "none"}'], log=io.StringIO()) == (
            ExitCode.MISSING_INPUT
        )

    def test_an_unknown_shim_exits_unusable_input_and_says_why(self, tmp_path: Path):
        hook = tmp_path / 'pre-push'
        hook.write_text('exit 0\n', encoding='utf-8')
        log = io.StringIO()

        assert run(arguments=[f'--hook={hook}'], log=log) == ExitCode.UNUSABLE_INPUT
        assert 'pre-commit changed its hook template' in log.getvalue()

    def test_without_a_hook_argument_it_finds_this_repositorys(
        self, repository: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(repository)

        assert run(arguments=[], log=io.StringIO()) == ExitCode.SUCCESS
        assert PATCH_MARKER in installed_hook(repository=repository).read_text(encoding='utf-8')

    def test_main_exits_with_the_command_code(self, mocker, tmp_path: Path):
        mocker.patch.object(sys, 'argv', ['patch_pre_push_hook', f'--hook={tmp_path / "none"}'])

        with pytest.raises(SystemExit) as exit_information:
            patch_pre_push_hook.main()

        assert exit_information.value.code == ExitCode.MISSING_INPUT


def test_envrc_patches_the_hook_whether_or_not_it_was_just_installed():
    """.envrc runs the patch outside the install-when-missing branch, so old clones get it."""
    envrc = (Path(__file__).parent.parent / '.envrc').read_text(encoding='utf-8')
    install_branch_end = envrc.index('  fi\n', envrc.index('pre-commit install'))

    assert 'scripts.patch_pre_push_hook' in envrc
    assert envrc.index('scripts.patch_pre_push_hook') > install_branch_end
