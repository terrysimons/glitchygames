r"""Build SDL with its x11 video driver for macOS, so pygame-ce can draw on XQuartz.

pygame-ce's macOS wheel bundles an SDL without x11 (``SDL_VIDEODRIVER=x11`` fails with "x11 not
available"). SDL's dynamic API loads another SDL at run time instead of the bundled one: when
``SDL_DYNAMIC_API`` names a library, the bundled SDL's first call fills its jump table from that
library's ``SDL_DYNAPI_entry``, and every SDL call from then on (pygame's, SDL_image's,
SDL_mixer's, SDL_ttf's) runs the other library's code (SDL's docs/README-dynapi.md and
src/dynapi/SDL_dynapi.c, ``SDL_InitDynamicAPILocked``). So this script builds the very SDL
version the wheel reports (``pygame.get_sdl_version()``) with x11 enabled against XQuartz's
libraries in /opt/X11, and the driver comparison's ``x11-macos`` configuration runs the suite with
``SDL_DYNAMIC_API`` pointing at it (scripts/driver_configurations.py). The wheel is unchanged.

The build:

1. downloads the release tarball from GitHub (libsdl-org/SDL releases) with curl and checks its
   SHA-256 against ``SDL_RELEASE_SHA256`` (pinned per version; a version not listed is refused);
2. configures it with SDL's autotools ``configure`` (SDL 2's CMake build never enables x11 on
   Apple platforms: its X11 check runs only in the ``UNIX AND NOT APPLE`` block, while the
   autotools build checks X11 on Darwin too), out of tree, with ``CONFIGURE_OPTIONS``;
3. runs ``make`` and ``make install`` into the cache directory (never a system path):
   ``~/Library/Caches/glitchygames/sdl-x11/<version>/install/lib/libSDL2-2.0.0.dylib``;
4. writes ``build.json`` (the version, the archive's hash and the options) last: a version
   directory without it, or with other options, is removed and built again; with it, the build
   is reused.

``check`` starts a child Python with the library, ``SDL_VIDEODRIVER=x11``, dummy audio and
XQuartz's ``DISPLAY``, which opens a window, fills it and reports the driver
(``ProbeResult``); anything but ``x11`` and the fill colour fails.

Usage:
    uv run python scripts/build_sdl_x11.py build [--version 2.32.10] [--cache-root DIR] \\
        [--output FILE] [--check]
    uv run python scripts/build_sdl_x11.py check --library PATH

Exit codes: ``SUCCESS``; ``OPTIONS_REFUSED`` off macOS or for a version without a pinned hash;
``UNUSABLE_INPUT`` for a download whose hash differs; ``INTERNAL_ERROR`` for a failed build step
or check (the step's log is named).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from pydantic import BaseModel, ConfigDict

from glitchygames.exit_codes import ExitCode
from glitchygames.process import TimeoutExpired, run_command

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# The SHA-256 of each SDL release tarball this script builds, from GitHub's digest of the
# release asset (`gh api repos/libsdl-org/SDL/releases/tags/release-2.32.10 --jq
# '.assets[] | select(.name == "SDL2-2.32.10.tar.gz") | .digest'`, read 2026-10-23, and the
# downloaded file matched it). Add a version's line when pygame-ce moves to a new SDL.
SDL_RELEASE_SHA256 = {
    '2.32.10': '5f5993c530f084535c65a6879e9b26ad441169b3e25d789d83287040a9ca5165',
}
SDL_RELEASE_URL = (
    'https://github.com/libsdl-org/SDL/releases/download/release-{version}/SDL2-{version}.tar.gz'
)
# XQuartz's install prefix: its X11 headers and libraries
X11_PREFIX = Path('/opt/X11')
CONFIGURE_OPTIONS = (
    '--disable-static',
    '--enable-video-x11',
    f'--x-includes={X11_PREFIX / "include"}',
    f'--x-libraries={X11_PREFIX / "lib"}',
    # pygame-ce's bundled SDL is loaded too and keeps its Cocoa, Metal and MFi code; a second
    # copy of their Objective-C classes in one process makes the runtime warn ("Class
    # SDLApplication is implemented in both ...") and risks crashes, and x11 needs none of them
    '--disable-video-cocoa',
    '--disable-video-metal',
    '--disable-render-metal',
    '--disable-video-vulkan',
    '--disable-joystick-mfi',
    '--disable-video-opengles',
    # No OpenGL (GLX) either, as in the Linux container, which has no libGL. With it, SDL on
    # macOS marks every window OpenGL (SDL_DefaultGraphicsBackends), loading XQuartz's libGL and
    # Apple's Xplugin into the process, and draws window surfaces through an OpenGL texture.
    # Under load that ended pytest workers with no traceback: an X error (GLXBadContext in
    # X_GLXMakeCurrent) through Xlib's default error handler, and a crash in SkyLight on
    # Xplugin's event thread. Without it, window surfaces are drawn in software (XShm)
    '--disable-video-opengl',
)
# The library SDL_DYNAMIC_API names (SDL 2's macOS install name)
LIBRARY_NAME = 'libSDL2-2.0.0.dylib'
STAMP_NAME = 'build.json'
# The most make jobs (keeps the machine usable)
MAXIMUM_MAKE_JOBS = 4
DOWNLOAD_TIMEOUT_SECONDS = 600.0
CONFIGURE_TIMEOUT_SECONDS = 600.0
MAKE_TIMEOUT_SECONDS = 1800.0
CHECK_TIMEOUT_SECONDS = 60.0
# The check's window and fill colour (wider than XQuartz's smallest window, which widens a
# 64-pixel window to 72)
PROBE_WINDOW_SIZE = (320, 240)
PROBE_COLOR = (10, 200, 30)
PROBE_PIXEL = (1, 1)
# XQuartz's display when DISPLAY is not set (its socket, /tmp/.X11-unix/X0)
DEFAULT_DISPLAY = ':0'


class BuildError(Exception):
    """A build step failed, or the download's hash differs."""


class UnpinnedVersionError(BuildError):
    """The SDL version has no pinned SHA-256 (``SDL_RELEASE_SHA256``)."""


class ArchiveMismatchError(BuildError):
    """The downloaded tarball's SHA-256 is not the pinned one."""


class BuildStamp(BaseModel):
    """What a finished build was made from (``build.json``): reused only when all match."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    version: str
    archive_sha256: str
    configure_options: tuple[str, ...]


class BuildStep(BaseModel):
    """One command of the build: its name (and log's), command, time limit and directory."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    name: str
    command: tuple[str, ...]
    timeout_seconds: float
    # The command's working directory (None: this process's)
    working_directory: Path | None = None


class ProbeResult(BaseModel):
    """What the check's child saw: its video driver, SDL version and whether the fill shows."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    driver: str
    sdl_version: str
    window_size: tuple[int, int]
    color_matches: bool


class SdlX11Build(BaseModel):
    """One SDL version's build in the cache: where each of its parts goes."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    version: str
    cache_root: Path

    @property
    def version_directory(self) -> Path:
        """The version's directory: everything below is this build's."""
        return self.cache_root / self.version

    @property
    def source_url(self) -> str:
        """The release tarball's URL on GitHub."""
        return SDL_RELEASE_URL.format(version=self.version)

    @property
    def archive_path(self) -> Path:
        """Where the tarball is downloaded."""
        return self.version_directory / 'download' / f'SDL2-{self.version}.tar.gz'

    @property
    def source_directory(self) -> Path:
        """The extracted source tree (the tarball's top folder)."""
        return self.version_directory / 'source' / f'SDL2-{self.version}'

    @property
    def build_directory(self) -> Path:
        """The out-of-tree build directory (configure's working directory)."""
        return self.version_directory / 'build'

    @property
    def install_directory(self) -> Path:
        """The install prefix."""
        return self.version_directory / 'install'

    @property
    def library_path(self) -> Path:
        """The built library, the value of SDL_DYNAMIC_API."""
        return self.install_directory / 'lib' / LIBRARY_NAME

    @property
    def stamp_path(self) -> Path:
        """The finished build's stamp."""
        return self.version_directory / STAMP_NAME

    @property
    def logs_directory(self) -> Path:
        """Each step's output."""
        return self.version_directory / 'logs'

    def expected_stamp(self) -> BuildStamp:
        """Return the stamp a build with the current options writes.

        Returns:
            The stamp (``pinned_sha256`` raises for a version without a pinned hash).

        """
        return BuildStamp(
            version=self.version,
            archive_sha256=pinned_sha256(version=self.version),
            configure_options=CONFIGURE_OPTIONS,
        )


def pinned_sha256(*, version: str) -> str:
    """Return a version's pinned tarball SHA-256.

    Args:
        version: The SDL version, e.g. ``2.32.10``.

    Returns:
        The hex digest.

    Raises:
        UnpinnedVersionError: If the version is not in ``SDL_RELEASE_SHA256``.

    """
    try:
        return SDL_RELEASE_SHA256[version]
    except KeyError:
        message = (
            f'SDL {version} has no pinned SHA-256: add it to SDL_RELEASE_SHA256 in '
            f'scripts/build_sdl_x11.py (from the release asset digest on GitHub)'
        )
        raise UnpinnedVersionError(message) from None


def wheel_sdl_version() -> str:
    """Return the SDL version pygame-ce reports (its bundled SDL's).

    Returns:
        For example ``2.32.10``.

    """
    import pygame

    return '.'.join(str(part) for part in pygame.get_sdl_version())


def default_cache_root(*, home: Path) -> Path:
    """Return the builds' cache directory, outside the checkout.

    Args:
        home: The user's home directory.

    Returns:
        ``~/Library/Caches/glitchygames/sdl-x11``.

    """
    return home / 'Library' / 'Caches' / 'glitchygames' / 'sdl-x11'


def make_jobs(*, cpu_count: int | None) -> int:
    """Return the make job count: the CPU count, at most ``MAXIMUM_MAKE_JOBS``.

    Args:
        cpu_count: ``os.process_cpu_count()`` (None when unknown).

    Returns:
        At least 1.

    """
    return max(1, min(MAXIMUM_MAKE_JOBS, cpu_count or 1))


def download_command(*, build: SdlX11Build, destination: Path) -> list[str]:
    """Return the curl command that downloads the tarball.

    Args:
        build: The build.
        destination: The file to write.

    Returns:
        The command: fail on an HTTP error, follow GitHub's redirect, no progress meter.

    """
    return [
        'curl',
        '--fail',
        '--location',
        '--silent',
        '--show-error',
        '--output',
        str(destination),
        build.source_url,
    ]


def configure_command(*, build: SdlX11Build) -> list[str]:
    """Return SDL's configure command (run in the build directory).

    Args:
        build: The build.

    Returns:
        The command.

    """
    return [
        str(build.source_directory / 'configure'),
        f'--prefix={build.install_directory}',
        *CONFIGURE_OPTIONS,
    ]


def make_command(*, build: SdlX11Build, jobs: int, target: str | None = None) -> list[str]:
    """Return a make command in the build directory.

    Args:
        build: The build.
        jobs: Parallel jobs.
        target: The make target (None: the default, the library).

    Returns:
        The command.

    """
    return [
        'make',
        '-C',
        str(build.build_directory),
        f'-j{jobs}',
        *([] if target is None else [target]),
    ]


def file_sha256(*, path: Path) -> str:
    """Return a file's SHA-256.

    Args:
        path: The file.

    Returns:
        The hex digest.

    """
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def verify_archive(*, path: Path, expected_sha256: str) -> None:
    """Check a downloaded tarball's SHA-256.

    Args:
        path: The tarball.
        expected_sha256: The pinned digest.

    Raises:
        ArchiveMismatchError: If the digests differ.

    """
    actual = file_sha256(path=path)
    if actual != expected_sha256:
        message = f'{path}: SHA-256 {actual}, expected {expected_sha256}'
        raise ArchiveMismatchError(message)


def extract_archive(*, archive: Path, destination: Path) -> None:
    """Extract a tarball, refusing members that would land outside ``destination``.

    Args:
        archive: The tarball.
        destination: The folder to extract into (made if missing).

    """
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tar_file:
        # The 'data' filter refuses absolute paths, links out of the folder and special files
        tar_file.extractall(destination, filter='data')


def run_step(*, step: BuildStep, build: SdlX11Build, environment: Mapping[str, str]) -> None:
    """Run one build step, its output in ``logs/<name>.log``.

    Args:
        step: The step.
        build: The build.
        environment: The step's environment.

    Raises:
        BuildError: If the step fails, times out (the message names its log) or its program is
            not installed.

    """
    build.logs_directory.mkdir(parents=True, exist_ok=True)
    log_path = build.logs_directory / f'{step.name}.log'
    try:
        completed = run_command(
            command=step.command,
            environment=environment,
            timeout_seconds=step.timeout_seconds,
            capture_output=True,
            working_directory=step.working_directory,
        )
    except TimeoutExpired:
        message = f'SDL build step {step.name!r} took longer than {step.timeout_seconds:.0f} s'
        raise BuildError(message) from None
    except FileNotFoundError:
        message = f'SDL build step {step.name!r} needs {step.command[0]}, which is not installed'
        raise BuildError(message) from None
    log_path.write_text(completed.stdout or '', encoding='utf-8')
    if completed.returncode != 0:
        message = (
            f'SDL build step {step.name!r} failed (exit {completed.returncode}); see {log_path}'
        )
        raise BuildError(message)


def finished_build(*, build: SdlX11Build) -> bool:
    """Tell whether the cache holds this build, made with the current options.

    Args:
        build: The build.

    Returns:
        True when its stamp matches and its library exists.

    """
    expected = build.expected_stamp()
    if not build.stamp_path.is_file() or not build.library_path.is_file():
        return False
    try:
        stamp = BuildStamp.model_validate_json(build.stamp_path.read_text(encoding='utf-8'))
    except ValueError:
        return False
    return stamp == expected


def ensure_built(
    *, build: SdlX11Build, environment: Mapping[str, str], jobs: int, log: TextIO
) -> Path:
    """Build SDL with x11 into the cache unless it is there already.

    Args:
        build: The build.
        environment: The build steps' environment.
        jobs: make's parallel jobs.
        log: Where progress lines go.

    Returns:
        The library (SDL_DYNAMIC_API's value).

    Raises:
        BuildError: If the build installed no library (a version without a pinned hash, a
            download whose hash differs and a failed step raise BuildError's subclasses, or
            BuildError itself, from the functions this calls).

    """
    expected = build.expected_stamp()
    if finished_build(build=build):
        say(log=log, text=f'SDL {build.version} with x11: reusing {build.library_path}\n')
        return build.library_path
    say(log=log, text=f'SDL {build.version} with x11: building in {build.version_directory}\n')
    shutil.rmtree(build.version_directory, ignore_errors=True)
    build.archive_path.parent.mkdir(parents=True)
    partial = build.archive_path.with_name(f'{build.archive_path.name}.partial')
    run_step(
        step=BuildStep(
            name='download',
            command=tuple(download_command(build=build, destination=partial)),
            timeout_seconds=DOWNLOAD_TIMEOUT_SECONDS,
        ),
        build=build,
        environment=environment,
    )
    verify_archive(path=partial, expected_sha256=expected.archive_sha256)
    partial.replace(build.archive_path)
    extract_archive(archive=build.archive_path, destination=build.source_directory.parent)
    build.build_directory.mkdir(parents=True)
    steps = [
        BuildStep(
            name='configure',
            command=tuple(configure_command(build=build)),
            timeout_seconds=CONFIGURE_TIMEOUT_SECONDS,
            working_directory=build.build_directory,
        ),
        *(
            BuildStep(
                name=target or 'make',
                command=tuple(make_command(build=build, jobs=jobs, target=target)),
                timeout_seconds=MAKE_TIMEOUT_SECONDS,
            )
            for target in (None, 'install')
        ),
    ]
    for step in steps:
        run_step(step=step, build=build, environment=environment)
    if not build.library_path.is_file():
        message = f'the SDL build installed no {build.library_path}'
        raise BuildError(message)
    build.stamp_path.write_text(expected.model_dump_json(indent=2), encoding='utf-8')
    say(log=log, text=f'SDL {build.version} with x11: built {build.library_path}\n')
    return build.library_path


def say(*, log: TextIO, text: str) -> None:
    """Write a progress line and flush it (the build's output arrives as it happens).

    Args:
        log: Where it goes (sys.stderr on the command line).
        text: The line, with its newline.

    """
    log.write(text)
    log.flush()


def x11_environment(
    *, environment: Mapping[str, str], library: Path, display: str | None = None
) -> dict[str, str]:
    """Return a process environment that runs pygame on x11 through the built SDL.

    Args:
        environment: The base environment.
        library: The built library.
        display: The X display (None: the base's DISPLAY, else ``DEFAULT_DISPLAY``).

    Returns:
        The base with SDL_DYNAMIC_API, SDL_VIDEODRIVER=x11, SDL_AUDIODRIVER=dummy and DISPLAY.

    """
    return {
        **environment,
        'SDL_DYNAMIC_API': str(library),
        'SDL_VIDEODRIVER': 'x11',
        'SDL_AUDIODRIVER': 'dummy',
        'DISPLAY': display or environment.get('DISPLAY') or DEFAULT_DISPLAY,
    }


def probe_display(*, result_path: Path) -> ProbeResult:
    """Open a window on this process's SDL drivers, fill it and present it (the check's child).

    Args:
        result_path: Where the result is written (JSON).

    Returns:
        The result.

    """
    import pygame

    pygame.display.init()
    try:
        surface = pygame.display.set_mode(PROBE_WINDOW_SIZE)
        surface.fill(PROBE_COLOR)
        pygame.display.flip()
        shown = surface.get_at(PROBE_PIXEL)
        result = ProbeResult(
            driver=pygame.display.get_driver(),
            sdl_version='.'.join(str(part) for part in pygame.get_sdl_version()),
            window_size=surface.get_size(),
            color_matches=(shown.r, shown.g, shown.b) == PROBE_COLOR,
        )
    finally:
        pygame.display.quit()
    result_path.write_text(result.model_dump_json(), encoding='utf-8')
    return result


def check_library(
    *, library: Path, environment: Mapping[str, str], result_path: Path
) -> ProbeResult:
    """Check that pygame draws on x11 through the library: a child opens and fills a window.

    Args:
        library: The built library.
        environment: The base environment (its DISPLAY is XQuartz's).
        result_path: Where the child writes its result.

    Returns:
        The child's result.

    Raises:
        BuildError: If the child failed, or its driver is not x11 or the fill did not show.

    """
    result_path.unlink(missing_ok=True)
    child_environment = x11_environment(environment=environment, library=library)
    try:
        completed = run_command(
            command=[
                sys.executable,
                str(Path(__file__).resolve()),
                'probe',
                f'--result={result_path}',
            ],
            environment=child_environment,
            timeout_seconds=CHECK_TIMEOUT_SECONDS,
            capture_output=True,
        )
    except TimeoutExpired:
        message = f'the x11 check took longer than {CHECK_TIMEOUT_SECONDS:.0f} s'
        raise BuildError(message) from None
    if completed.returncode != 0 or not result_path.is_file():
        message = (
            f'the x11 check failed (exit {completed.returncode}, DISPLAY '
            f'{child_environment["DISPLAY"]}): {(completed.stdout or "").strip()[-2000:]}'
        )
        raise BuildError(message)
    result = ProbeResult.model_validate_json(result_path.read_text(encoding='utf-8'))
    if result.driver != 'x11' or not result.color_matches:
        message = f'the x11 check drew on {result.driver!r} (fill shown: {result.color_matches})'
        raise BuildError(message)
    return result


def argument_parser() -> argparse.ArgumentParser:
    """Build the command line parser.

    Returns:
        The parser, with the build, check and probe commands.

    """
    parser = argparse.ArgumentParser(description='Build SDL with x11 for macOS (XQuartz)')
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('build', help='build (or reuse) SDL with x11; print its library')
    build.add_argument(
        '--version', default=None, help="the SDL version (default: pygame-ce's own SDL's)"
    )
    build.add_argument('--cache-root', type=Path, default=None, help='the builds directory')
    build.add_argument(
        '--output', type=Path, default=None, help="also write the library's path to this file"
    )
    build.add_argument('--check', action='store_true', help='then check it draws on XQuartz')
    check = commands.add_parser('check', help='check a built library draws on XQuartz')
    check.add_argument('--library', type=Path, required=True, help='the built library')
    probe = commands.add_parser('probe', help="(the check's child) open a window, write a result")
    probe.add_argument('--result', type=Path, required=True, help='the result file')
    return parser


def build_and_check(
    *, options: argparse.Namespace, environment: Mapping[str, str], home: Path, log: TextIO
) -> Path:
    """Run the build or check command (on macOS).

    Args:
        options: The parsed command line.
        environment: The process environment.
        home: The user's home directory.
        log: Where progress goes.

    Returns:
        The library built (``build``) or checked (``check``).

    """
    if options.command == 'build':
        build = SdlX11Build(
            version=options.version or wheel_sdl_version(),
            cache_root=options.cache_root or default_cache_root(home=home),
        )
        library = ensure_built(
            build=build,
            environment=environment,
            jobs=make_jobs(cpu_count=os.process_cpu_count()),
            log=log,
        )
        if options.output is not None:
            options.output.parent.mkdir(parents=True, exist_ok=True)
            options.output.write_text(f'{library}\n', encoding='utf-8')
    else:
        library = options.library
    if options.command == 'check' or options.check:
        result = check_library(
            library=library, environment=environment, result_path=library.parent / 'x11-check.json'
        )
        width, height = result.window_size
        say(log=log, text=f'SDL {result.sdl_version} drew a {width}x{height} window on x11\n')
    return library


def run(
    *,
    arguments: Sequence[str],
    environment: Mapping[str, str],
    platform: str,
    home: Path,
    log: TextIO,
) -> ExitCode:
    """Run a command.

    Args:
        arguments: The command line arguments (without the program name).
        environment: The process environment.
        platform: ``sys.platform``.
        home: The user's home directory.
        log: Where progress and errors go.

    Returns:
        The exit code.

    """
    options = argument_parser().parse_args(arguments)
    if options.command == 'probe':
        probe_display(result_path=options.result)
        return ExitCode.SUCCESS
    if platform != 'darwin':
        say(log=log, text='SDL with x11 is built for macOS only (Linux has x11 in its own SDL)\n')
        return ExitCode.OPTIONS_REFUSED
    try:
        library = build_and_check(options=options, environment=environment, home=home, log=log)
    except UnpinnedVersionError as error:
        say(log=log, text=f'{error}\n')
        return ExitCode.OPTIONS_REFUSED
    except ArchiveMismatchError as error:
        say(log=log, text=f'{error}\n')
        return ExitCode.UNUSABLE_INPUT
    except BuildError as error:
        say(log=log, text=f'{error}\n')
        return ExitCode.INTERNAL_ERROR
    sys.stdout.write(f'{library}\n')
    return ExitCode.SUCCESS


def main() -> None:
    """Command line: see the module docstring."""
    # Only the library's path goes to standard output, without pygame's greeting
    os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
    sys.exit(
        run(
            arguments=sys.argv[1:],
            environment=os.environ,
            platform=sys.platform,
            home=Path.home(),
            log=sys.stderr,
        )
    )


if __name__ == '__main__':
    main()
