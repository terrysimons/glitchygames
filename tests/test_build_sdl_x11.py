"""scripts/build_sdl_x11.py builds SDL with x11 for macOS into a cache and checks it draws.

Nothing is downloaded: the builds use a fabricated "release" tarball served by a file:// URL
(curl reads it as it would GitHub's), whose ``configure`` script writes a Makefile that builds
and installs a stand-in library, so every step (download, hash check, extraction, configure,
make, install, stamp) runs for real. The x11 check's child is real where it can be (a library
that does not exist), and fabricated (``run_command`` patched) where a real one would need
XQuartz.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import sys
import tarfile
from pathlib import Path

import pygame
import pytest
from scripts import build_sdl_x11
from scripts.build_sdl_x11 import (
    CONFIGURE_OPTIONS,
    LIBRARY_NAME,
    PROBE_COLOR,
    ArchiveMismatchError,
    BuildError,
    BuildStep,
    ProbeResult,
    SdlX11Build,
    UnpinnedVersionError,
    check_library,
    configure_command,
    default_cache_root,
    download_command,
    ensure_built,
    extract_archive,
    file_sha256,
    make_command,
    make_jobs,
    pinned_sha256,
    probe_display,
    run,
    run_step,
    verify_archive,
    wheel_sdl_version,
    x11_environment,
)

from glitchygames.exit_codes import ExitCode
from glitchygames.process import CompletedProcess, TimeoutExpired

TEST_VERSION = '9.9.9'
# The real build steps run curl and make (macOS has both; a slim Linux image may not)
NEEDS_BUILD_TOOLS = pytest.mark.skipif(
    shutil.which('curl') is None or shutil.which('make') is None,
    reason='the build needs curl and make',
)
# The stand-in release's configure script: it reads --prefix and writes a Makefile whose default
# target builds a stand-in library and whose install target copies it into the prefix
CONFIGURE_START = (
    '#!/bin/sh\n'
    'prefix=""\n'
    'for argument in "$@"; do\n'
    '    case "$argument" in --prefix=*) prefix="${argument#--prefix=}" ;; esac\n'
    'done\n'
)
FAILING_CONFIGURE = '#!/bin/sh\necho configure went wrong\nexit 3\n'


def release_tarball(*, path: Path, installs_library: bool = True, fails: bool = False) -> Path:
    """Write a fabricated SDL release tarball (its top folder holds only ``configure``).

    Args:
        path: The tarball to write.
        installs_library: Its ``make install`` installs the library (else does nothing).
        fails: Its configure script fails.

    Returns:
        The tarball.

    """
    install = (
        f'    printf \'\\tmkdir -p %s/lib\\n\\tcp {LIBRARY_NAME} %s/lib/\\n\' "$prefix" "$prefix"\n'
        if installs_library
        else ''
    )
    script = (
        CONFIGURE_START
        + '{\n'
        + f"    printf 'all:\\n\\techo built > {LIBRARY_NAME}\\ninstall:\\n'\n"
        + install
        + '} > Makefile\n'
    )
    data = (FAILING_CONFIGURE if fails else script).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, 'w:gz') as tar_file:
        member = tarfile.TarInfo(f'SDL2-{TEST_VERSION}/configure')
        member.size = len(data)
        member.mode = 0o755
        tar_file.addfile(member, io.BytesIO(data))
    return path


@pytest.fixture
def release(tmp_path, monkeypatch) -> Path:
    """Serve a fabricated release of TEST_VERSION from a file:// URL, its hash pinned.

    Returns:
        The tarball.

    """
    tarball = release_tarball(path=tmp_path / 'releases' / 'SDL2.tar.gz')
    monkeypatch.setattr(build_sdl_x11, 'SDL_RELEASE_URL', f'file://{tarball}?{{version}}')
    monkeypatch.setitem(build_sdl_x11.SDL_RELEASE_SHA256, TEST_VERSION, file_sha256(path=tarball))
    return tarball


@pytest.fixture
def build(tmp_path) -> SdlX11Build:
    """A build of TEST_VERSION in a cache under tmp_path.

    Returns:
        The build.

    """
    return SdlX11Build(version=TEST_VERSION, cache_root=tmp_path / 'cache')


class TestPathsAndCommands:
    """Where a build's parts go, and the commands that make them."""

    def test_the_paths(self, tmp_path):
        build = SdlX11Build(version='2.32.10', cache_root=tmp_path)

        assert build.source_url == (
            'https://github.com/libsdl-org/SDL/releases/download/release-2.32.10/'
            'SDL2-2.32.10.tar.gz'
        )
        assert build.archive_path == tmp_path / '2.32.10' / 'download' / 'SDL2-2.32.10.tar.gz'
        assert build.source_directory == tmp_path / '2.32.10' / 'source' / 'SDL2-2.32.10'
        assert build.library_path == (
            tmp_path / '2.32.10' / 'install' / 'lib' / 'libSDL2-2.0.0.dylib'
        )
        assert build.stamp_path == tmp_path / '2.32.10' / 'build.json'

    def test_the_cache_is_in_the_users_caches(self, tmp_path):
        assert default_cache_root(home=tmp_path) == (
            tmp_path / 'Library' / 'Caches' / 'glitchygames' / 'sdl-x11'
        )

    @pytest.mark.parametrize(('cpu_count', 'jobs'), [(None, 1), (1, 1), (3, 3), (16, 4)])
    def test_make_jobs_are_bounded(self, cpu_count, jobs):
        assert make_jobs(cpu_count=cpu_count) == jobs

    def test_the_download_command(self, tmp_path):
        build = SdlX11Build(version='2.32.10', cache_root=tmp_path)

        command = download_command(build=build, destination=tmp_path / 'file')

        assert command[0] == 'curl'
        assert {'--fail', '--location'} <= set(command)
        assert command[-3:] == ['--output', str(tmp_path / 'file'), build.source_url]

    def test_the_configure_command_enables_x11_against_xquartz(self, build):
        command = configure_command(build=build)

        assert command[0] == str(build.source_directory / 'configure')
        assert command[1] == f'--prefix={build.install_directory}'
        assert command[2:] == list(CONFIGURE_OPTIONS)
        assert '--enable-video-x11' in command
        assert '--x-includes=/opt/X11/include' in command
        assert '--disable-video-cocoa' in command
        # No OpenGL: XQuartz's libGL (and Apple's Xplugin with it) never loads in-process
        assert '--disable-video-opengl' in command

    def test_the_make_commands(self, build):
        assert make_command(build=build, jobs=3) == [
            'make',
            '-C',
            str(build.build_directory),
            '-j3',
        ]
        assert make_command(build=build, jobs=1, target='install')[-1] == 'install'

    def test_the_wheel_sdl_version(self):
        assert wheel_sdl_version() == '.'.join(str(part) for part in pygame.get_sdl_version())


class TestPinnedHashes:
    """Each version's tarball hash is pinned; others are refused."""

    def test_the_wheels_version_is_pinned(self):
        assert len(pinned_sha256(version='2.32.10')) == 64

    def test_an_unpinned_version_is_refused(self):
        with pytest.raises(UnpinnedVersionError, match=r'SDL 1\.0\.0 has no pinned SHA-256'):
            pinned_sha256(version='1.0.0')

    def test_a_matching_archive_passes(self, tmp_path):
        archive = tmp_path / 'a.tar.gz'
        archive.write_bytes(b'sdl')

        verify_archive(path=archive, expected_sha256=hashlib.sha256(b'sdl').hexdigest())

    def test_a_differing_archive_is_refused(self, tmp_path):
        archive = tmp_path / 'a.tar.gz'
        archive.write_bytes(b'not sdl')

        with pytest.raises(ArchiveMismatchError, match='expected 0000'):
            verify_archive(path=archive, expected_sha256='0000')


class TestExtractArchive:
    """Extraction keeps every member inside the destination."""

    def test_members_are_extracted(self, tmp_path):
        archive = release_tarball(path=tmp_path / 'a.tar.gz')

        extract_archive(archive=archive, destination=tmp_path / 'out')

        assert (tmp_path / 'out' / f'SDL2-{TEST_VERSION}' / 'configure').is_file()

    def test_a_member_outside_the_destination_is_refused(self, tmp_path):
        archive = tmp_path / 'evil.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar_file:
            member = tarfile.TarInfo('../escaped')
            member.size = 1
            tar_file.addfile(member, io.BytesIO(b'x'))

        with pytest.raises(tarfile.OutsideDestinationError):
            extract_archive(archive=archive, destination=tmp_path / 'out')
        assert not (tmp_path / 'escaped').exists()


class TestRunStep:
    """A step's output goes to its log; a failure or timeout is a BuildError."""

    def test_a_step_writes_its_log(self, build, tmp_path):
        run_step(
            step=BuildStep(
                name='hello',
                command=(sys.executable, '-c', 'import os; print("in", os.getcwd())'),
                timeout_seconds=30.0,
                working_directory=tmp_path,
            ),
            build=build,
            environment={},
        )

        assert (build.logs_directory / 'hello.log').read_text(encoding='utf-8') == (
            f'in {tmp_path.resolve()}\n'
        )

    def test_a_failing_step(self, build):
        with pytest.raises(BuildError, match=r"'broken' failed \(exit 4\); see .*broken\.log"):
            run_step(
                step=BuildStep(
                    name='broken',
                    command=(sys.executable, '-c', 'raise SystemExit(4)'),
                    timeout_seconds=30.0,
                ),
                build=build,
                environment={},
            )

    def test_a_step_whose_program_is_not_installed(self, build):
        with pytest.raises(BuildError, match="'fetch' needs no-such-program-here, which is not"):
            run_step(
                step=BuildStep(
                    name='fetch', command=('no-such-program-here',), timeout_seconds=30.0
                ),
                build=build,
                environment=_path_only(),
            )

    def test_a_step_that_takes_too_long(self, build):
        with pytest.raises(BuildError, match="'slow' took longer than 0 s"):
            run_step(
                step=BuildStep(
                    name='slow',
                    command=(sys.executable, '-c', 'import time; time.sleep(30)'),
                    timeout_seconds=0.2,
                ),
                build=build,
                environment={},
            )


@NEEDS_BUILD_TOOLS
class TestEnsureBuilt:
    """The whole build, then reuse while the stamp matches."""

    def test_a_build_from_scratch(self, release, build):
        log = io.StringIO()

        library = ensure_built(build=build, environment=dict(_path_only()), jobs=2, log=log)

        assert library == build.library_path
        assert library.read_text(encoding='utf-8') == 'built\n'
        assert build.archive_path.is_file()
        assert build.expected_stamp().model_dump_json(indent=2) == build.stamp_path.read_text(
            encoding='utf-8'
        )
        assert log.getvalue().splitlines() == [
            f'SDL {TEST_VERSION} with x11: building in {build.version_directory}',
            f'SDL {TEST_VERSION} with x11: built {library}',
        ]

    def test_a_finished_build_is_reused(self, release, build):
        ensure_built(build=build, environment=dict(_path_only()), jobs=1, log=io.StringIO())
        log = io.StringIO()

        ensure_built(build=build, environment={}, jobs=1, log=log)

        assert log.getvalue() == (f'SDL {TEST_VERSION} with x11: reusing {build.library_path}\n')

    def test_other_options_rebuild(self, release, build, monkeypatch):
        ensure_built(build=build, environment=dict(_path_only()), jobs=1, log=io.StringIO())
        monkeypatch.setattr(build_sdl_x11, 'CONFIGURE_OPTIONS', (*CONFIGURE_OPTIONS, '--more'))
        log = io.StringIO()

        ensure_built(build=build, environment=dict(_path_only()), jobs=1, log=log)

        assert 'building in' in log.getvalue()

    def test_an_unreadable_stamp_rebuilds(self, release, build):
        ensure_built(build=build, environment=dict(_path_only()), jobs=1, log=io.StringIO())
        build.stamp_path.write_text('{', encoding='utf-8')
        log = io.StringIO()

        ensure_built(build=build, environment=dict(_path_only()), jobs=1, log=log)

        assert 'building in' in log.getvalue()

    def test_a_differing_download_is_refused(self, release, build, monkeypatch):
        monkeypatch.setitem(build_sdl_x11.SDL_RELEASE_SHA256, TEST_VERSION, '0' * 64)

        with pytest.raises(ArchiveMismatchError):
            ensure_built(build=build, environment=dict(_path_only()), jobs=1, log=io.StringIO())
        assert not build.archive_path.exists()

    def test_a_failing_configure(self, release, build):
        release_tarball(path=release, fails=True)
        build_sdl_x11.SDL_RELEASE_SHA256[TEST_VERSION] = file_sha256(path=release)

        with pytest.raises(BuildError, match="'configure' failed"):
            ensure_built(build=build, environment=dict(_path_only()), jobs=1, log=io.StringIO())
        assert 'configure went wrong' in (build.logs_directory / 'configure.log').read_text(
            encoding='utf-8'
        )

    def test_a_build_that_installs_no_library(self, release, build):
        release_tarball(path=release, installs_library=False)
        build_sdl_x11.SDL_RELEASE_SHA256[TEST_VERSION] = file_sha256(path=release)

        with pytest.raises(BuildError, match='installed no'):
            ensure_built(build=build, environment=dict(_path_only()), jobs=1, log=io.StringIO())
        assert not build.stamp_path.exists()


def _path_only() -> dict[str, str]:
    """Return an environment with this process's PATH alone (the build finds sh, curl, make).

    Returns:
        The environment.

    """
    return {'PATH': os.environ['PATH']}


class TestX11Environment:
    """The environment that runs pygame on x11 through the built SDL."""

    def test_the_variables(self, tmp_path):
        library = tmp_path / LIBRARY_NAME

        assert x11_environment(environment={'HOME': '/home'}, library=library) == {
            'HOME': '/home',
            'SDL_DYNAMIC_API': str(library),
            'SDL_VIDEODRIVER': 'x11',
            'SDL_AUDIODRIVER': 'dummy',
            'DISPLAY': ':0',
        }

    def test_the_display_is_kept_or_given(self, tmp_path):
        library = tmp_path / LIBRARY_NAME

        kept = x11_environment(environment={'DISPLAY': '/private/xquartz:0'}, library=library)
        given = x11_environment(environment={'DISPLAY': ':5'}, library=library, display=':1')

        assert kept['DISPLAY'] == '/private/xquartz:0'
        assert given['DISPLAY'] == ':1'


class TestProbeAndCheck:
    """The check's child opens and fills a window; the parent judges its driver and fill."""

    def test_the_probe_reports_its_driver(self, tmp_path):
        result_path = tmp_path / 'result.json'

        result = probe_display(result_path=result_path)

        # This run's own driver (dummy, or the native one in a local run's native half)
        assert result.driver == os.environ['SDL_VIDEODRIVER']
        assert result.color_matches
        assert result.window_size == build_sdl_x11.PROBE_WINDOW_SIZE
        assert ProbeResult.model_validate_json(result_path.read_text(encoding='utf-8')) == result

    def test_a_library_that_does_not_load_fails_the_check(self, tmp_path):
        # SDL falls back to the wheel's own SDL, which has no x11: the child fails
        with pytest.raises(BuildError, match='the x11 check failed'):
            check_library(
                library=tmp_path / 'missing.dylib',
                environment=_path_only(),
                result_path=tmp_path / 'result.json',
            )

    def fabricated_child(self, mocker, *, result: ProbeResult | None, returncode: int = 0):
        """Replace the check's child: it writes ``result`` (if any) and exits ``returncode``."""

        def child(*, command, environment, timeout_seconds, capture_output):
            if result is not None:
                Path(command[-1].partition('=')[2]).write_text(
                    result.model_dump_json(), encoding='utf-8'
                )
            child.environment = environment
            return CompletedProcess(args=command, returncode=returncode, stdout='')

        return mocker.patch.object(build_sdl_x11, 'run_command', side_effect=child)

    def test_a_child_on_x11_passes(self, tmp_path, mocker):
        drawn = ProbeResult(
            driver='x11', sdl_version='2.32.10', window_size=(320, 240), color_matches=True
        )
        child = self.fabricated_child(mocker, result=drawn)

        result = check_library(
            library=tmp_path / LIBRARY_NAME,
            environment={'DISPLAY': ':3'},
            result_path=tmp_path / 'result.json',
        )

        assert result == drawn
        environment = child.call_args.kwargs['environment']
        assert environment['SDL_VIDEODRIVER'] == 'x11'
        assert environment['DISPLAY'] == ':3'
        assert environment['SDL_DYNAMIC_API'] == str(tmp_path / LIBRARY_NAME)

    def test_a_child_on_another_driver_fails(self, tmp_path, mocker):
        self.fabricated_child(
            mocker,
            result=ProbeResult(
                driver='cocoa', sdl_version='2.32.10', window_size=(320, 240), color_matches=True
            ),
        )

        with pytest.raises(BuildError, match="drew on 'cocoa'"):
            check_library(
                library=tmp_path / LIBRARY_NAME, environment={}, result_path=tmp_path / 'r.json'
            )

    def test_a_child_that_takes_too_long(self, tmp_path, mocker):
        mocker.patch.object(
            build_sdl_x11, 'run_command', side_effect=TimeoutExpired(cmd='python', timeout=60)
        )

        with pytest.raises(BuildError, match='took longer than 60 s'):
            check_library(
                library=tmp_path / LIBRARY_NAME, environment={}, result_path=tmp_path / 'r.json'
            )


class TestCommandLine:
    """build, check and probe; their exit codes."""

    def run_command_line(self, arguments: list[str], *, home: Path, platform: str = 'darwin'):
        """Run the command line; return its exit code and progress log."""
        log = io.StringIO()
        exit_code = run(
            arguments=arguments, environment=_path_only(), platform=platform, home=home, log=log
        )
        return exit_code, log.getvalue()

    @NEEDS_BUILD_TOOLS
    def test_build_prints_and_writes_the_library(self, release, tmp_path, capsys):
        output = tmp_path / 'out' / 'library.txt'

        exit_code, _ = self.run_command_line(
            ['build', f'--version={TEST_VERSION}', f'--output={output}'], home=tmp_path
        )

        library = default_cache_root(home=tmp_path) / TEST_VERSION / 'install' / 'lib'
        assert exit_code == ExitCode.SUCCESS
        assert output.read_text(encoding='utf-8') == f'{library / LIBRARY_NAME}\n'
        assert capsys.readouterr().out == f'{library / LIBRARY_NAME}\n'

    @NEEDS_BUILD_TOOLS
    def test_build_then_check(self, release, tmp_path, mocker):
        checked = mocker.patch.object(
            build_sdl_x11,
            'check_library',
            return_value=ProbeResult(
                driver='x11', sdl_version=TEST_VERSION, window_size=(320, 240), color_matches=True
            ),
        )

        exit_code, log = self.run_command_line(
            ['build', f'--version={TEST_VERSION}', f'--cache-root={tmp_path / "c"}', '--check'],
            home=tmp_path,
        )

        assert exit_code == ExitCode.SUCCESS
        assert checked.call_args.kwargs['library'] == (
            tmp_path / 'c' / TEST_VERSION / 'install' / 'lib' / LIBRARY_NAME
        )
        assert log.endswith(f'SDL {TEST_VERSION} drew a 320x240 window on x11\n')

    def test_check_alone(self, tmp_path, mocker):
        mocker.patch.object(
            build_sdl_x11,
            'check_library',
            return_value=ProbeResult(
                driver='x11', sdl_version='2.32.10', window_size=(320, 240), color_matches=True
            ),
        )

        exit_code, _ = self.run_command_line(
            ['check', f'--library={tmp_path / LIBRARY_NAME}'], home=tmp_path
        )

        assert exit_code == ExitCode.SUCCESS

    def test_off_macos_it_is_refused(self, tmp_path):
        exit_code, log = self.run_command_line(['build'], home=tmp_path, platform='linux')

        assert exit_code == ExitCode.OPTIONS_REFUSED
        assert 'macOS only' in log

    def test_an_unpinned_version_is_refused(self, tmp_path):
        exit_code, log = self.run_command_line(['build', '--version=1.0.0'], home=tmp_path)

        assert exit_code == ExitCode.OPTIONS_REFUSED
        assert 'no pinned SHA-256' in log

    @NEEDS_BUILD_TOOLS
    def test_a_differing_download(self, release, tmp_path, monkeypatch):
        monkeypatch.setitem(build_sdl_x11.SDL_RELEASE_SHA256, TEST_VERSION, '0' * 64)

        exit_code, _ = self.run_command_line(['build', f'--version={TEST_VERSION}'], home=tmp_path)

        assert exit_code == ExitCode.UNUSABLE_INPUT

    def test_a_failed_check(self, tmp_path, mocker):
        mocker.patch.object(
            build_sdl_x11, 'check_library', side_effect=BuildError('the x11 check failed')
        )

        exit_code, log = self.run_command_line(
            ['check', f'--library={tmp_path / LIBRARY_NAME}'], home=tmp_path
        )

        assert exit_code == ExitCode.INTERNAL_ERROR
        assert log == 'the x11 check failed\n'

    def test_probe_writes_its_result(self, tmp_path):
        result_path = tmp_path / 'result.json'

        exit_code, _ = self.run_command_line(
            ['probe', f'--result={result_path}'], home=tmp_path, platform='linux'
        )

        assert exit_code == ExitCode.SUCCESS
        assert ProbeResult.model_validate_json(result_path.read_text(encoding='utf-8')).driver
        assert PROBE_COLOR == build_sdl_x11.PROBE_COLOR

    def test_main_exits_with_the_code(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            sys, 'argv', ['build_sdl_x11', 'probe', f'--result={tmp_path / "result.json"}']
        )

        with pytest.raises(SystemExit) as raised:
            build_sdl_x11.main()

        assert raised.value.code == ExitCode.SUCCESS
