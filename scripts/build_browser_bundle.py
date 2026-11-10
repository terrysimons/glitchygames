r"""Build (and optionally serve) a browser version of one GlitchyGames game.

The site runs on PyScript (Pyodide 314, Python 3.14) with GlitchyGames' own pygame-ce wheel,
built from the ``third_party/pygame-ce`` submodule (our fork, branch ``glitchygames-wasm``:
pygame-ce 2.5.8 plus its WebAssembly fixes).
Design: plans/2026-10-23-game-host-and-browser-runner.md.

It writes, into the output directory:

  index.html          browser/index.html for the game (the canvas, a click-to-play overlay)
  boot.py             browser/boot.py, which starts the game with GameEngine.start_async
  browser_*.py        the page's services for the engine (browser/): IndexedDB-backed saves,
                      the clipboard, and the player's own files (a file picker, downloads)
  touch_controls.js   on-screen buttons on touch devices (the layout in boot_config.json)
  boot_config.json    which game to start, and its command-line arguments
  <package>.zip       a member game's own package (mr_muncher.zip), unpacked beside the engine's
  glitchygames.zip    the engine package, without what only desktop tools use (the API server
                      and its services, test helpers, project templates, the large PNG assets,
                      and Bitmappy unless the build is Bitmappy itself); unpacked by PyScript
                      into Python's working directory
  wheels/             the pygame-ce wheel
  pyscript.toml       packages (our wheel, numpy, pydantic, tomli-w) and the engine archive

The wheel is reused when ``dist-pyodide/build-info.json`` in the submodule says it was built
from the submodule's current commit with no uncommitted changes; otherwise it is built with the
submodule's ``buildconfig/glitchygames/build_pyodide_wheel.sh`` (about 2 GB of toolchain, cached
under ~/.cache/glitchygames-pyodide-build; the first build takes several minutes).

``all`` builds every game into one site (default build/browser/site): a directory per game
and an index.html linking them, which ``nox -s docs-deploy`` publishes with the docs as play/
(scripts/mkdocs_hooks.py).

It imports ``scripts.*`` and runs as ``python -m scripts.build_browser_bundle`` from the
repository root.

Usage:
    uv run python -m scripts.build_browser_bundle paddleslap --serve
    uv run python -m scripts.build_browser_bundle all --serve
    uv run python -m scripts.build_browser_bundle mr-muncher --output build/browser/mr-muncher \\
        -- --target-fps 30
"""

from __future__ import annotations

import argparse
import dataclasses
import errno
import functools
import html
import importlib.metadata
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

from scripts.git_checkout import files_not_ignored
from scripts.workspace_packages import workspace_members

REPOSITORY_DIRECTORY = Path(__file__).resolve().parent.parent
PACKAGE_DIRECTORY = REPOSITORY_DIRECTORY / 'src' / 'glitchygames'
BROWSER_DIRECTORY = REPOSITORY_DIRECTORY / 'browser'
PYGAME_CE_DIRECTORY = REPOSITORY_DIRECTORY / 'third_party' / 'pygame-ce'
WHEEL_BUILD_SCRIPT = Path('buildconfig') / 'glitchygames' / 'build_pyodide_wheel.sh'
WHEEL_OUTPUT_DIRECTORY_NAME = 'dist-pyodide'

# The PyScript release whose pinned Pyodide (314.0.3) our wheel is built for: change both together
PYSCRIPT_RELEASE = '2026.7.3'
# Pyodide packages the engine imports (numpy for surfarray and the synth, pydantic, tomli-w)
PYODIDE_PACKAGES = ('numpy', 'pydantic', 'tomli-w')

# The game argument that builds every game into one site
ALL_GAMES = 'all'

# browser/boot.py's own modules, served next to it (pyscript.toml's [files])
BROWSER_MODULES = ('browser_storage.py', 'browser_clipboard.py', 'browser_user_files.py')
# The page's own scripts, served next to it (index.html loads them)
BROWSER_PAGE_SCRIPTS = ('touch_controls.js',)

# Engine subpackages no game imports: desktop tools only (checked: nothing outside them refers
# to them). Bitmappy is a workspace member now, shipped as its own bitmappy.zip
EXCLUDED_SUBPACKAGES = frozenset({'api', 'services', 'testing', 'templates'})
# glitchygames/assets PNGs are the window icon (1 MB)
EXCLUDED_ASSET_SUFFIXES = frozenset({'.png'})
# Every archive member gets this timestamp, so the same sources make the same archive
ARCHIVE_TIMESTAMP = (2026, 1, 1, 0, 0, 0)

# Every page's tab icon, inline (an SVG data URL), so no page asks for a /favicon.ico the bundle
# does not have (a 404 on each load). No "$": it is substituted into the page template
TAB_ICON_LINK = (
    '<link rel="icon" href="data:image/svg+xml,'
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'>"
    "<rect width='16' height='16' rx='3' fill='%23000'/>"
    "<text x='8' y='12.5' font-size='12' font-family='monospace' font-weight='bold' "
    "text-anchor='middle' fill='%239cf'>G</text></svg>\">"
)
DEFAULT_PORT = 8000
# Without --port, the ports tried after DEFAULT_PORT is taken (another local server)
FALLBACK_PORT_COUNT = 20
DESCRIPTION = 'Build (and optionally serve) a browser version of one GlitchyGames game.'


def report(message: str) -> None:
    """Write one line to standard output."""
    sys.stdout.write(message + '\n')
    # Shown at once even when piped (the serving process runs until it is stopped)
    sys.stdout.flush()


# The play/ index's sections, in page order; each lists its entries by title (the owner,
# 2026-10-28: sorted alphabetically, Bitmappy below the games in its own "Tools" section)
SECTION_GAMES = 'Games'
SECTION_TOOLS = 'Tools'
INDEX_SECTIONS = (SECTION_GAMES, SECTION_TOOLS)


@dataclasses.dataclass(frozen=True)
class GameSpecification:
    """One game the browser build can start.

    Attributes:
        module: The module holding the game's first scene class.
        scene_class: The scene class GameEngine is constructed with.
        title: The page title.
        member_packages: The import packages of the workspace members holding the game's code,
            the ones depended on first. A game in one package names it (``('mr_muncher',)``);
            a project of layered packages names every one it starts, the shared core first
            (Brave Adventurer's launcher: ``('brave_adventurer_core', 'brave_adventurer',
            'brave_adventurer_papyrus', 'brave_adventurer_modes')``). The bundle ships each as
            ``<package>.zip``, apart from the engine's archive. Empty for a game inside the
            engine package.
        section: The play/ index's section listing it (``SECTION_GAMES`` or ``SECTION_TOOLS``).
        browser_modules: Page-side modules this game needs served beside it (and listed in
            pyscript.toml's ``[files]``), on top of the engine's own ``BROWSER_MODULES``. Each is
            a file in ``browser/`` that only this game's page loads -- bitmappy's
            ``masterhub_bridge.py`` (the MasterHUB web-hub bridge), say -- so other games' bundles
            never ship it. Empty for a game that needs only the engine's page modules.

    """

    module: str
    scene_class: str
    title: str
    member_packages: tuple[str, ...] = ()
    section: str = SECTION_GAMES
    browser_modules: tuple[str, ...] = ()


# The keys a touch button can press, by DOM KeyboardEvent.code: the event's key, its legacy
# keyCode (Emscripten passes keyCode and code to SDL, which maps code to the scancode the games
# bind) and the name shown under the button ('' for an arrow, whose label is the arrow)
TOUCH_KEYS: dict[str, tuple[str, int, str]] = {
    'ArrowUp': ('ArrowUp', 38, ''),
    'ArrowDown': ('ArrowDown', 40, ''),
    'ArrowLeft': ('ArrowLeft', 37, ''),
    'ArrowRight': ('ArrowRight', 39, ''),
    'Space': (' ', 32, 'Space'),
    'Escape': ('Escape', 27, 'Esc'),
    'KeyW': ('w', 87, 'W'),
    'KeyS': ('s', 83, 'S'),
    'KeyP': ('p', 80, 'P'),
    'ShiftLeft': ('Shift', 16, 'Shift'),
}


@dataclasses.dataclass(frozen=True)
class TouchButton:
    """One on-screen button: held, it holds its key down.

    Attributes:
        label: What it does ('Jump'), or an arrow.
        code: The key it presses (a ``TOUCH_KEYS`` code).

    """

    label: str
    code: str


# Rows of buttons, top to bottom; None leaves a gap (a D-pad's corners)
type TouchRows = tuple[tuple[TouchButton | None, ...], ...]


@dataclasses.dataclass(frozen=True)
class TouchLayout:
    """A game's touch controls: a cluster for each thumb, and one between them.

    Attributes:
        left: Usually movement.
        center: Pause and the like.
        right: Usually actions.

    """

    left: TouchRows = ()
    center: TouchRows = ()
    right: TouchRows = ()


UP = TouchButton('▲', 'ArrowUp')
DOWN = TouchButton('▼', 'ArrowDown')
LEFT = TouchButton('◀', 'ArrowLeft')
RIGHT = TouchButton('▶', 'ArrowRight')
# The shared pause and game-over screens resume or restart with Space and quit with Esc, so a
# button names its key as well as its action: their "Press SPACE" prompts then point at it
JUMP = TouchButton('Jump', 'Space')
PAUSE_ESCAPE = TouchButton('Pause', 'Escape')

# Each game's touch controls (keys from its action maps; checked by
# tests/test_browser_touch_controls.py). Bitmappy has none: the editor needs a pointer and a
# keyboard
TOUCH_LAYOUTS: dict[str, TouchLayout] = {
    # Two players on one phone, a thumb each: W/S and the arrows
    'paddleslap': TouchLayout(
        left=((TouchButton('▲', 'KeyW'),), (TouchButton('▼', 'KeyS'),)),
        center=((TouchButton('Pause', 'Space'),),),
        right=((UP,), (DOWN,)),
    ),
    # Both games, and the title screen choosing between them: the arrows choose a game there
    # and Jump (Space) starts it
    'brave-adventurer': TouchLayout(
        left=((LEFT, RIGHT),), center=((PAUSE_ESCAPE,),), right=((JUMP,),)
    ),
    'clockwork-keep': TouchLayout(
        left=((LEFT, RIGHT),),
        center=((PAUSE_ESCAPE,),),
        right=((TouchButton('Use', 'KeyW'), JUMP), (TouchButton('Run', 'ShiftLeft'),)),
    ),
    # P pauses here (Esc too, but on the pause screen Esc quits)
    'mr-muncher': TouchLayout(
        left=((None, UP, None), (LEFT, None, RIGHT), (None, DOWN, None)),
        center=((TouchButton('Pause', 'KeyP'),),),
        right=((TouchButton('Start', 'Space'),),),
    ),
}


def touch_controls_config(
    *, layout: TouchLayout
) -> dict[str, list[list[dict[str, object] | None]]]:
    """Return a layout as boot_config.json holds it: each button with its key's event fields.

    Returns:
        The clusters (left, center, right), each a list of rows of buttons or None (a gap).

    """

    def button_config(button: TouchButton | None) -> dict[str, object] | None:
        if button is None:
            return None
        key, key_code, key_name = TOUCH_KEYS[button.code]
        return {
            'label': button.label,
            'key_name': key_name,
            'code': button.code,
            'key': key,
            'key_code': key_code,
        }

    return {
        cluster: [[button_config(button) for button in row] for row in rows]
        for cluster, rows in (
            ('left', layout.left),
            ('center', layout.center),
            ('right', layout.right),
        )
    }


GAMES: dict[str, GameSpecification] = {
    'paddleslap': GameSpecification(
        module='paddleslap',
        scene_class='Game',
        title='Paddle Slap',
        member_packages=('paddleslap',),
    ),
    # Both Brave Adventurer games, Classic (drawn in code) and Papyrus (sprite-sheet art), from
    # the launcher's title screen: its four packages, the shared core first and the launcher last
    'brave-adventurer': GameSpecification(
        module='brave_adventurer_modes.title',
        scene_class='TitleScene',
        title='Brave Adventurer',
        member_packages=(
            'brave_adventurer_core',
            'brave_adventurer',
            'brave_adventurer_papyrus',
            'brave_adventurer_modes',
        ),
    ),
    'clockwork-keep': GameSpecification(
        module='clockwork_keep.game',
        scene_class='ClockworkKeepScene',
        title='Clockwork Keep',
        member_packages=('clockwork_keep',),
    ),
    'mr-muncher': GameSpecification(
        module='mr_muncher.game',
        scene_class='MrMuncherScene',
        title='Mr. Muncher',
        member_packages=('mr_muncher',),
    ),
    'drawing-fire': GameSpecification(
        module='drawing_fire.game',
        scene_class='DrawingFireScene',
        title='Drawing Fire',
        member_packages=('drawing_fire',),
    ),
    # The pixel-art editor: its AI sprite generation is off in browser builds (the
    # bitmappy.constants.AI_FEATURES_ENABLED feature flag)
    'bitmappy': GameSpecification(
        module='bitmappy.editor',
        scene_class='BitmapEditorScene',
        title='Bitmappy',
        member_packages=('bitmappy',),
        section=SECTION_TOOLS,
        browser_modules=('masterhub_bridge.py',),  # the MasterHUB web-hub bridge (bitmappy only)
    ),
}


def is_bundled(
    *, relative_path: Path, excluded_subpackages: frozenset[str] = EXCLUDED_SUBPACKAGES
) -> bool:
    """Return whether a file of the package (relative to it) belongs in the browser bundle.

    Returns:
        False for byte code, the excluded subpackages and the large assets.

    """
    parts = relative_path.parts
    if '__pycache__' in parts or relative_path.suffix == '.pyc':
        return False
    if parts[0] in excluded_subpackages:
        return False
    return not (parts[0] == 'assets' and relative_path.suffix in EXCLUDED_ASSET_SUFFIXES)


def bundled_package_files(
    *, package_directory: Path, excluded_subpackages: frozenset[str] = EXCLUDED_SUBPACKAGES
) -> list[Path]:
    """Return the package's files that go into the bundle, relative to it, sorted.

    Files git ignores (macOS Finder's ``.DS_Store``) never ship; tracked files and new files not
    yet added do. Bundles are built from a checkout, so a directory outside one raises
    ``NotAGitCheckoutError``.

    Returns:
        The files.

    """
    return sorted(
        relative_path
        for relative_path in files_not_ignored(directory=package_directory)
        if (package_directory / relative_path).is_file()
        and is_bundled(relative_path=relative_path, excluded_subpackages=excluded_subpackages)
    )


def write_engine_archive(
    *,
    package_directory: Path,
    archive_path: Path,
    excluded_subpackages: frozenset[str] = EXCLUDED_SUBPACKAGES,
    engine_version: str | None = None,
) -> int:
    """Zip a package's bundled files (the engine's or a member game's) with fixed timestamps.

    Entries are named after ``package_directory`` (``glitchygames/...``, ``mr_muncher/...``).

    With ``engine_version``, the archive also holds the package's metadata
    (``glitchygames-<version>.dist-info/METADATA``): the package is unpacked, not installed, and
    ``importlib.metadata`` finds the version there (a replay compares it with the recording's).

    Returns:
        How many package files were archived.

    """
    files = bundled_package_files(
        package_directory=package_directory, excluded_subpackages=excluded_subpackages
    )
    members = [
        (
            (Path(package_directory.name) / relative_path).as_posix(),
            (package_directory / relative_path).read_bytes(),
        )
        for relative_path in files
    ]
    if engine_version is not None:
        metadata = (
            f'Metadata-Version: 2.1\nName: {package_directory.name}\nVersion: {engine_version}\n'
        )
        members.append((
            f'{package_directory.name}-{engine_version}.dist-info/METADATA',
            metadata.encode('utf-8'),
        ))
    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, contents in members:
            member = zipfile.ZipInfo(filename=name, date_time=ARCHIVE_TIMESTAMP)
            member.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(member, contents)
    return len(files)


def installed_engine_version() -> str | None:
    """Return the version of the glitchygames package this script runs with.

    Returns:
        The version, or None when the package metadata is not installed.

    """
    try:
        return importlib.metadata.version('glitchygames')
    except importlib.metadata.PackageNotFoundError:
        return None


def pyscript_config(
    *,
    wheel_name: str,
    member_packages: tuple[str, ...] = (),
    browser_modules: tuple[str, ...] = (),
) -> str:
    """Return pyscript.toml: our pygame-ce wheel, the engine's packages and its archive.

    Args:
        wheel_name: The pygame-ce wheel's file name.
        member_packages: The import packages of a workspace member game, each listed as its
            own archive beside the engine's, in the order given (dependencies first).
        browser_modules: The game's own page modules (``GameSpecification.browser_modules``),
            served and listed beside the engine's ``BROWSER_MODULES``.

    Returns:
        The TOML text.

    """
    packages = [f'./wheels/{wheel_name}', *PYODIDE_PACKAGES]
    package_lines = ''.join(f'  "{package}",\n' for package in packages)
    member_lines = ''.join(f'"./{package}.zip" = "./*"\n' for package in member_packages)
    module_lines = ''.join(
        f'"./{module}" = "./{module}"\n' for module in (*BROWSER_MODULES, *browser_modules)
    )
    return (
        '# Written by scripts/build_browser_bundle.py\n'
        f'packages = [\n{package_lines}]\n'
        '\n'
        '[files]\n'
        '"./glitchygames.zip" = "./*"\n'
        f'{member_lines}'
        f'{module_lines}'
        '"./boot_config.json" = "./boot_config.json"\n'
    )


def boot_config(*, game: str, arguments: list[str]) -> dict[str, object]:
    """Return what browser/boot.py starts, and the touch controls the page shows.

    browser/boot.py starts the game (its module, scene class and arguments);
    browser/touch_controls.js builds the on-screen buttons.

    Returns:
        The configuration (written as boot_config.json).

    """
    specification = GAMES[game]
    layout = TOUCH_LAYOUTS.get(game)
    return {
        'game': game,
        'module': specification.module,
        'scene_class': specification.scene_class,
        'title': specification.title,
        'arguments': arguments,
        # browser/touch_controls.js builds the on-screen buttons from it (None: no buttons)
        'touch_controls': None if layout is None else touch_controls_config(layout=layout),
    }


def render_page(*, template: str, game: str) -> str:
    """Return index.html for ``game`` from the template.

    Returns:
        The page.

    """
    return string.Template(template).substitute(
        title=GAMES[game].title, pyscript_release=PYSCRIPT_RELEASE, tab_icon_link=TAB_ICON_LINK
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


def member_package_directory(*, import_package: str) -> Path:
    """Return the source directory of a workspace member's import package.

    Args:
        import_package: The package's import name (``mr_muncher``).

    Returns:
        The directory.

    Raises:
        LookupError: If no workspace member holds the package.

    """
    for member in workspace_members(project_root=REPOSITORY_DIRECTORY):
        for package_directory in member.package_directories:
            if package_directory.name == import_package:
                return package_directory
    message = f'No workspace member holds the package {import_package}'
    raise LookupError(message)


def write_bundle(
    *, game: str, output_directory: Path, wheel_path: Path, arguments: list[str]
) -> None:
    """Write the browser site for ``game`` into ``output_directory`` (replacing what was there)."""
    if output_directory.exists():
        shutil.rmtree(output_directory)
    (output_directory / 'wheels').mkdir(parents=True)
    shutil.copy2(wheel_path, output_directory / 'wheels' / wheel_path.name)
    shutil.copy2(BROWSER_DIRECTORY / 'boot.py', output_directory / 'boot.py')
    for file_name in (*BROWSER_MODULES, *GAMES[game].browser_modules, *BROWSER_PAGE_SCRIPTS):
        shutil.copy2(BROWSER_DIRECTORY / file_name, output_directory / file_name)
    template = (BROWSER_DIRECTORY / 'index.html').read_text(encoding='utf-8')
    (output_directory / 'index.html').write_text(
        render_page(template=template, game=game), encoding='utf-8'
    )
    (output_directory / 'pyscript.toml').write_text(
        pyscript_config(
            wheel_name=wheel_path.name,
            member_packages=GAMES[game].member_packages,
            browser_modules=GAMES[game].browser_modules,
        ),
        encoding='utf-8',
    )
    (output_directory / 'boot_config.json').write_text(
        json.dumps(boot_config(game=game, arguments=arguments), indent=2) + '\n', encoding='utf-8'
    )
    # Each archive's file count, the engine's first, then each member package's
    file_counts = {
        'glitchygames': write_engine_archive(
            package_directory=PACKAGE_DIRECTORY,
            archive_path=output_directory / 'glitchygames.zip',
            excluded_subpackages=EXCLUDED_SUBPACKAGES,
            engine_version=installed_engine_version(),
        )
    }
    for member_package in GAMES[game].member_packages:
        file_counts[member_package] = write_engine_archive(
            package_directory=member_package_directory(import_package=member_package),
            archive_path=output_directory / f'{member_package}.zip',
            excluded_subpackages=frozenset(),
        )
    archives = ', '.join(f'{package} {count}' for package, count in file_counts.items())
    report(
        f'{output_directory}: {GAMES[game].title}, {sum(file_counts.values())} files '
        f'({archives}), {wheel_path.name}'
    )


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


# Windows' WSAEACCES: what binding a port a listening socket holds gives there, since
# HTTPServer binds with SO_REUSEADDR (CircleCI's Windows job, 2026-10-24); elsewhere EADDRINUSE
WINDOWS_ACCESS_DENIED_ERROR = 10013


def port_is_taken(error: OSError) -> bool:
    """Return whether binding failed because another socket holds the port.

    Returns:
        True for EADDRINUSE, and on Windows for WSAEACCES (``WINDOWS_ACCESS_DENIED_ERROR``).

    """
    return (
        error.errno == errno.EADDRINUSE
        or getattr(error, 'winerror', None) == WINDOWS_ACCESS_DENIED_ERROR
    )


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
            if not port_is_taken(error):
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


def site_index_page() -> str:
    """Return the site's index.html: a link to each game's page, by section, sorted by title.

    Returns:
        The page.

    """
    sections = ''
    for section in INDEX_SECTIONS:
        entries = sorted(
            (
                (specification.title, game)
                for game, specification in GAMES.items()
                if specification.section == section
            ),
            key=lambda entry: entry[0].casefold(),
        )
        if not entries:
            continue
        links = ''.join(
            f'      <li><a href="{html.escape(game)}/">{html.escape(title)}</a></li>\n'
            for title, game in entries
        )
        sections += f'    <h2>{html.escape(section)}</h2>\n    <ul>\n{links}    </ul>\n'

    return (
        '<!doctype html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '  <title>GlitchyGames in the browser</title>\n'
        f'  {TAB_ICON_LINK}\n'
        '  <style>\n'
        '    :root { color-scheme: dark; }\n'
        '    body { margin: 0; padding: 24px 16px; background: #000; color: #ddd;\n'
        '           font-family: system-ui, sans-serif; }\n'
        '    main { max-width: 40rem; margin: 0 auto; }\n'
        '    a { color: #9cf; }\n'
        '    li { margin: 0.5rem 0; font-size: 1.2rem; }\n'
        '  </style>\n'
        '</head>\n'
        '<body>\n'
        '  <main>\n'
        '    <h1>GlitchyGames in the browser</h1>\n'
        '    <p>Python and pygame-ce in WebAssembly (PyScript). The first load takes a few\n'
        '      seconds; then click the game to start it.</p>\n'
        f'{sections}'
        '    <p><a href="../">GlitchyGames documentation</a></p>\n'
        '  </main>\n'
        '</body>\n'
        '</html>\n'
    )


def write_site(*, output_directory: Path, wheel_path: Path) -> None:
    """Write every game's bundle into ``output_directory/<game>`` and an index linking them."""
    if output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True)
    for game in GAMES:
        write_bundle(
            game=game, output_directory=output_directory / game, wheel_path=wheel_path, arguments=[]
        )
    (output_directory / 'index.html').write_text(site_index_page(), encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, build the bundle and optionally serve it.

    Returns:
        The exit status: 0, or 1 when the bundle cannot be served (no free port).

    """
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('game', choices=[*sorted(GAMES), ALL_GAMES])
    parser.add_argument(
        '--output', type=Path, default=None, help='default: build/browser/<game> (all: site)'
    )
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
    builds_site = arguments.game == ALL_GAMES
    if builds_site and arguments.game_arguments:
        parser.error('a game command line needs one game, not all')

    output_directory = arguments.output or REPOSITORY_DIRECTORY / 'build' / 'browser' / (
        'site' if builds_site else arguments.game
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
    if builds_site:
        write_site(output_directory=output_directory, wheel_path=wheel_path)
    else:
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
