r"""Build (and optionally serve) a browser version of one GlitchyGames game.

The site runs on PyScript (Pyodide 314, Python 3.14) with GlitchyGames' own pygame-ce wheel,
built from the ``third_party/pygame-ce`` submodule (our fork, branch ``glitchygames-wasm``:
pygame-ce plus its WebAssembly fixes). Design: plans/2026-10-23-game-host-and-browser-runner.md.

It writes, into the output directory:

  index.html          browser/index.html for the game (the canvas, a click-to-play overlay)
  boot.py             browser/boot.py, which starts the game with GameEngine.start_async
  browser_storage.py  IndexedDB-backed saves (browser/browser_storage.py)
  boot_config.json    which game to start, and its command-line arguments
  glitchygames.zip    the engine package, without what only desktop tools use (Bitmappy, the
                      API server and its services, test helpers, project templates and the
                      large PNG assets); unpacked by PyScript into Python's working directory
  wheels/             the pygame-ce wheel
  pyscript.toml       packages (our wheel, numpy, pydantic, tomli-w) and the engine archive

The wheel is reused when ``dist-pyodide/build-info.json`` in the submodule says it was built
from the submodule's current commit with no uncommitted changes; otherwise it is built with the
submodule's ``buildconfig/glitchygames/build_pyodide_wheel.sh`` (about 2 GB of toolchain, cached
under ~/.cache/glitchygames-pyodide-build; the first build takes several minutes).

Usage:
    uv run python scripts/build_browser_bundle.py paddleslap --serve
    uv run python scripts/build_browser_bundle.py mr-muncher --output build/browser/mr-muncher \\
        -- --target-fps 30
"""

from __future__ import annotations

import argparse
import dataclasses
import errno
import functools
import json
import shutil
import string
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs the submodule's build script
import sys
import webbrowser
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import override

REPOSITORY_DIRECTORY = Path(__file__).resolve().parent.parent
PACKAGE_DIRECTORY = REPOSITORY_DIRECTORY / 'glitchygames'
BROWSER_DIRECTORY = REPOSITORY_DIRECTORY / 'browser'
PYGAME_CE_DIRECTORY = REPOSITORY_DIRECTORY / 'third_party' / 'pygame-ce'
WHEEL_BUILD_SCRIPT = Path('buildconfig') / 'glitchygames' / 'build_pyodide_wheel.sh'
WHEEL_OUTPUT_DIRECTORY_NAME = 'dist-pyodide'

# The PyScript release whose pinned Pyodide (314.0.3) our wheel is built for: change both together
PYSCRIPT_RELEASE = '2026.7.3'
# Pyodide packages the engine imports (numpy for surfarray and the synth, pydantic, tomli-w)
PYODIDE_PACKAGES = ('numpy', 'pydantic', 'tomli-w')

# Engine subpackages no game imports: desktop tools only (checked: nothing outside them refers
# to them, but sprites/animated.py's TOML sprite loading, which no bundled game uses)
EXCLUDED_SUBPACKAGES = frozenset({'bitmappy', 'api', 'services', 'testing', 'templates'})
# glitchygames/assets PNGs are Bitmappy's and the window icon (1.7 MB and 1 MB)
EXCLUDED_ASSET_SUFFIXES = frozenset({'.png'})
# Every archive member gets this timestamp, so the same sources make the same archive
ARCHIVE_TIMESTAMP = (2026, 1, 1, 0, 0, 0)

DEFAULT_PORT = 8000
# Without --port, the ports tried after DEFAULT_PORT is taken (another local server)
FALLBACK_PORT_COUNT = 20
DESCRIPTION = 'Build (and optionally serve) a browser version of one GlitchyGames game.'


def report(message: str) -> None:
    """Write one line to standard output."""
    sys.stdout.write(message + '\n')
    # Shown at once even when piped (the serving process runs until it is stopped)
    sys.stdout.flush()


@dataclasses.dataclass(frozen=True)
class GameSpecification:
    """One game the browser build can start.

    Attributes:
        module: The module holding the game's first scene class.
        scene_class: The scene class GameEngine is constructed with.
        title: The page title.

    """

    module: str
    scene_class: str
    title: str


GAMES: dict[str, GameSpecification] = {
    'paddleslap': GameSpecification(
        module='glitchygames.examples.paddleslap', scene_class='Game', title='Paddle Slap'
    ),
    'brave-adventurer': GameSpecification(
        module='glitchygames.examples.brave_adventurer.game',
        scene_class='BraveAdventurerScene',
        title='Brave Adventurer',
    ),
    'clockwork-keep': GameSpecification(
        module='glitchygames.examples.clockwork_keep.game',
        scene_class='ClockworkKeepScene',
        title='Clockwork Keep',
    ),
    'mr-muncher': GameSpecification(
        module='glitchygames.examples.mr_muncher.game',
        scene_class='MrMuncherScene',
        title='Mr. Muncher',
    ),
}


def is_bundled(*, relative_path: Path) -> bool:
    """Return whether a file of the package (relative to it) belongs in the browser bundle.

    Returns:
        False for byte code, the excluded subpackages and the large assets.

    """
    parts = relative_path.parts
    if '__pycache__' in parts or relative_path.suffix == '.pyc':
        return False
    if parts[0] in EXCLUDED_SUBPACKAGES:
        return False
    return not (parts[0] == 'assets' and relative_path.suffix in EXCLUDED_ASSET_SUFFIXES)


def bundled_package_files(*, package_directory: Path) -> list[Path]:
    """Return the package's files that go into the bundle, relative to the package, sorted.

    Returns:
        The files.

    """
    return sorted(
        path.relative_to(package_directory)
        for path in package_directory.rglob('*')
        if path.is_file() and is_bundled(relative_path=path.relative_to(package_directory))
    )


def write_engine_archive(*, package_directory: Path, archive_path: Path) -> int:
    """Zip the bundled package files as ``glitchygames/...`` with fixed timestamps.

    Returns:
        How many files were archived.

    """
    files = bundled_package_files(package_directory=package_directory)
    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for relative_path in files:
            member = zipfile.ZipInfo(
                filename=(Path(package_directory.name) / relative_path).as_posix(),
                date_time=ARCHIVE_TIMESTAMP,
            )
            member.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(member, (package_directory / relative_path).read_bytes())
    return len(files)


def pyscript_config(*, wheel_name: str) -> str:
    """Return pyscript.toml: our pygame-ce wheel, the engine's packages and its archive.

    Returns:
        The TOML text.

    """
    packages = [f'./wheels/{wheel_name}', *PYODIDE_PACKAGES]
    package_lines = ''.join(f'  "{package}",\n' for package in packages)
    return (
        '# Written by scripts/build_browser_bundle.py\n'
        f'packages = [\n{package_lines}]\n'
        '\n'
        '[files]\n'
        '"./glitchygames.zip" = "./*"\n'
        '"./browser_storage.py" = "./browser_storage.py"\n'
        '"./boot_config.json" = "./boot_config.json"\n'
    )


def boot_config(*, game: str, arguments: list[str]) -> dict[str, object]:
    """Return what browser/boot.py starts: the game, its scene class and arguments.

    Returns:
        The configuration (written as boot_config.json).

    """
    specification = GAMES[game]
    return {
        'game': game,
        'module': specification.module,
        'scene_class': specification.scene_class,
        'title': specification.title,
        'arguments': arguments,
    }


def render_page(*, template: str, game: str) -> str:
    """Return index.html for ``game`` from the template.

    Returns:
        The page.

    """
    return string.Template(template).substitute(
        title=GAMES[game].title, pyscript_release=PYSCRIPT_RELEASE
    )


def submodule_commit(*, pygame_ce_directory: Path) -> str:
    """Return the pygame-ce submodule's checked-out commit.

    Returns:
        The commit hash.

    """
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed git call
        ['git', '-C', str(pygame_ce_directory), 'rev-parse', 'HEAD'],  # ruff: ignore[start-process-with-partial-path] - git from PATH
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def reusable_wheel(*, wheel_directory: Path, commit: str) -> Path | None:
    """Return the built wheel when its build-info says it is this commit's, clean; else None.

    Returns:
        The wheel's path, or None.

    """
    info_path = wheel_directory / 'build-info.json'
    if not info_path.is_file():
        return None
    info = json.loads(info_path.read_text())
    wheel_path = wheel_directory / str(info.get('wheel', ''))
    if (
        info.get('source_commit') == commit
        and info.get('uncommitted_tracked_changes') == 0
        and wheel_path.is_file()
    ):
        return wheel_path
    return None


def build_wheel(*, pygame_ce_directory: Path) -> Path:
    """Build the pygame-ce wheel with the submodule's script and return its path.

    Returns:
        The wheel's path.

    """
    wheel_directory = pygame_ce_directory / WHEEL_OUTPUT_DIRECTORY_NAME
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - the submodule's script
        [
            str(pygame_ce_directory / WHEEL_BUILD_SCRIPT),
            str(pygame_ce_directory),
            str(wheel_directory),
        ],
        check=True,
    )
    info = json.loads((wheel_directory / 'build-info.json').read_text())
    return wheel_directory / str(info['wheel'])


def write_bundle(
    *, game: str, output_directory: Path, wheel_path: Path, arguments: list[str]
) -> None:
    """Write the browser site for ``game`` into ``output_directory`` (replacing what was there)."""
    if output_directory.exists():
        shutil.rmtree(output_directory)
    (output_directory / 'wheels').mkdir(parents=True)
    shutil.copy2(wheel_path, output_directory / 'wheels' / wheel_path.name)
    shutil.copy2(BROWSER_DIRECTORY / 'boot.py', output_directory / 'boot.py')
    shutil.copy2(BROWSER_DIRECTORY / 'browser_storage.py', output_directory / 'browser_storage.py')
    template = (BROWSER_DIRECTORY / 'index.html').read_text(encoding='utf-8')
    (output_directory / 'index.html').write_text(
        render_page(template=template, game=game), encoding='utf-8'
    )
    (output_directory / 'pyscript.toml').write_text(
        pyscript_config(wheel_name=wheel_path.name), encoding='utf-8'
    )
    (output_directory / 'boot_config.json').write_text(
        json.dumps(boot_config(game=game, arguments=arguments), indent=2) + '\n', encoding='utf-8'
    )
    file_count = write_engine_archive(
        package_directory=PACKAGE_DIRECTORY, archive_path=output_directory / 'glitchygames.zip'
    )
    report(f'{output_directory}: {GAMES[game].title}, {file_count} engine files, {wheel_path.name}')


class BundleRequestHandler(SimpleHTTPRequestHandler):
    """Serves the bundle with the MIME types Pyodide needs, uncached (a rebuild shows at once)."""

    extensions_map = {  # ruff: ignore[mutable-class-default] - the stdlib attribute it extends
        **SimpleHTTPRequestHandler.extensions_map,
        '.py': 'text/plain',
        '.toml': 'text/plain',
        '.whl': 'application/zip',
        '.wasm': 'application/wasm',
    }

    @override
    def end_headers(self) -> None:
        """Ask the browser not to cache, then end the headers."""
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


class PortUnavailableError(OSError):
    """No port to serve on: the one asked for, or every default one, is taken."""


def bind_server(*, directory: Path, port: int | None) -> ThreadingHTTPServer:
    """Bind the bundle's server on localhost.

    Args:
        directory: The bundle to serve.
        port: The port to use; None tries DEFAULT_PORT and the FALLBACK_PORT_COUNT after it.

    Returns:
        The bound server (not yet serving).

    Raises:
        PortUnavailableError: When the port, or every port tried, is in use.
        OSError: When binding fails for another reason (re-raised as is).

    """
    handler = functools.partial(BundleRequestHandler, directory=str(directory))
    candidates = (
        [port] if port is not None else range(DEFAULT_PORT, DEFAULT_PORT + FALLBACK_PORT_COUNT + 1)
    )
    for candidate in candidates:
        try:
            return ThreadingHTTPServer(('127.0.0.1', candidate), handler)
        except OSError as error:
            if error.errno != errno.EADDRINUSE:
                raise
    message = (
        f'port {port} is in use (choose another with --port)'
        if port is not None
        else f'ports {DEFAULT_PORT}-{DEFAULT_PORT + FALLBACK_PORT_COUNT} are all in use '
        '(choose one with --port)'
    )
    raise PortUnavailableError(errno.EADDRINUSE, message)


def serve(*, server: ThreadingHTTPServer, directory: Path, open_browser: bool) -> None:
    """Serve on ``server`` until interrupted, opening the page in the default browser."""
    with server:
        url = f'http://127.0.0.1:{server.server_address[1]}/'
        report(f'Serving {directory} at {url} (Ctrl-C to stop)')
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            report('Stopped.')


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, build the bundle and optionally serve it.

    Returns:
        The exit status: 0, or 1 when the bundle cannot be served (no free port).

    """
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('game', choices=sorted(GAMES))
    parser.add_argument('--output', type=Path, default=None, help='default: build/browser/<game>')
    parser.add_argument('--wheel', type=Path, default=None, help='use this pygame-ce wheel')
    parser.add_argument('--rebuild-wheel', action='store_true', help='build even if up to date')
    parser.add_argument('--serve', action='store_true', help='serve the bundle and open it')
    parser.add_argument(
        '--port',
        type=int,
        default=None,
        help=f'default: {DEFAULT_PORT}, or the next free port after it',
    )
    parser.add_argument('--no-open', action='store_true', help='serve without opening a browser')
    parser.add_argument('game_arguments', nargs='*', help='after --: the game command line')
    arguments = parser.parse_args(argv)

    output_directory = (
        arguments.output or REPOSITORY_DIRECTORY / 'build' / 'browser' / arguments.game
    )
    wheel_path = arguments.wheel
    if wheel_path is None:
        wheel_directory = PYGAME_CE_DIRECTORY / WHEEL_OUTPUT_DIRECTORY_NAME
        commit = submodule_commit(pygame_ce_directory=PYGAME_CE_DIRECTORY)
        wheel_path = (
            None
            if arguments.rebuild_wheel
            else reusable_wheel(wheel_directory=wheel_directory, commit=commit)
        )
        if wheel_path is None:
            report(
                f'Building the pygame-ce wheel for {commit[:9]} (several minutes the first time)'
            )
            wheel_path = build_wheel(pygame_ce_directory=PYGAME_CE_DIRECTORY)
    write_bundle(
        game=arguments.game,
        output_directory=output_directory,
        wheel_path=wheel_path,
        arguments=arguments.game_arguments,
    )
    if arguments.serve:
        try:
            server = bind_server(directory=output_directory, port=arguments.port)
        except PortUnavailableError as error:
            report(f'Cannot serve the bundle: {error.strerror}')
            return 1
        serve(server=server, directory=output_directory, open_browser=not arguments.no_open)
    return 0


if __name__ == '__main__':
    sys.exit(main())
