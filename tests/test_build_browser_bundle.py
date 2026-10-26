"""The browser bundle builder (scripts/build_browser_bundle.py)."""

from __future__ import annotations

import dataclasses
import errno
import functools
import importlib.metadata
import json
import socket
import threading
import tomllib
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from scripts import build_browser_bundle
from scripts.build_browser_bundle import (
    GAMES,
    PACKAGE_DIRECTORY,
    PYSCRIPT_RELEASE,
    REPOSITORY_DIRECTORY,
    TOUCH_LAYOUTS,
    BundleRequestHandler,
    PortUnavailableError,
    bind_server,
    boot_config,
    bundled_package_files,
    installed_engine_version,
    is_bundled,
    main,
    pyscript_config,
    render_page,
    reusable_wheel,
    touch_controls_config,
    write_engine_archive,
)
from scripts.git_checkout import NotAGitCheckoutError, run_git
from scripts.workspace_packages import declared_console_scripts, workspace_members

COMMIT = 'a' * 40
WHEEL_NAME = 'pygame_ce-2.5.8.post1-cp314-cp314-pyemscripten_2026_0_wasm32.whl'


def git(*, arguments: list[str], directory: Path) -> None:
    """Run git in a directory and require it to succeed."""
    returncode, output = run_git(arguments=arguments, directory=directory)
    assert returncode == 0, output


def make_package(root: Path) -> Path:
    """Make a small package tree, tracked in a git repository, with files bundled and not.

    Returns:
        The package directory.

    """
    package = root / 'glitchygames'
    for relative, content in {
        '__init__.py': '',
        'engine/game_engine.py': 'ENGINE = 1\n',
        'engine/__pycache__/game_engine.cpython-314.pyc': 'bytecode',
        'fonts/bitstream_vera/Vera.ttf': 'font',
        'assets/glitch.png': 'png',
        'assets/eraser.toml': 'toml',
        'api/main.py': 'API = 1\n',
        'examples/paddleslap.py': 'GAME = 1\n',
    }.items():
        path = package / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        # Bytes, not text: write_text would write Windows line endings there
        path.write_bytes(content.encode('utf-8'))
    # Bundles hold tracked files only, so the tree is a repository with every file added
    git(arguments=['init', '--quiet'], directory=root)
    git(arguments=['add', '.'], directory=root)
    return package


class TestPackageSelection:
    """Which package files go into the browser bundle."""

    @pytest.mark.parametrize(
        ('relative', 'bundled'),
        [
            ('engine/game_engine.py', True),
            ('fonts/bitstream_vera/Vera.ttf', True),
            ('assets/eraser.toml', True),
            ('examples/paddleslap.py', True),
            ('engine/__pycache__/game_engine.cpython-314.pyc', False),
            ('assets/glitch.png', False),
            ('api/main.py', False),
            ('services/renderer_service.py', False),
            ('testing/frame_fingerprints.py', False),
            ('templates/game.py', False),
        ],
    )
    def test_is_bundled(self, relative, bundled):
        assert is_bundled(relative_path=Path(relative)) is bundled

    def test_bundled_package_files_are_sorted_and_filtered(self, tmp_path):
        package = make_package(tmp_path)

        assert bundled_package_files(package_directory=package) == [
            Path('__init__.py'),
            Path('assets/eraser.toml'),
            Path('engine/game_engine.py'),
            Path('examples/paddleslap.py'),
            Path('fonts/bitstream_vera/Vera.ttf'),
        ]

    def test_an_ignored_file_is_not_bundled(self, tmp_path):
        """An ignored .DS_Store stays out of the bundle; a new file not yet added is in it."""
        package = make_package(tmp_path)
        (tmp_path / '.gitignore').write_text('.DS_Store\n', encoding='utf-8')
        (package / '.DS_Store').write_bytes(b'finder')
        (package / 'engine' / '.DS_Store').write_bytes(b'finder')
        (package / 'engine' / 'untracked.py').write_text('UNTRACKED = 1\n', encoding='utf-8')

        files = bundled_package_files(package_directory=package)

        assert Path('.DS_Store') not in files
        assert Path('engine/.DS_Store') not in files
        assert Path('engine/untracked.py') in files
        assert Path('engine/game_engine.py') in files

    def test_outside_a_checkout_is_an_error(self, tmp_path):
        package = tmp_path / 'glitchygames'
        package.mkdir()
        (package / '__init__.py').write_text('', encoding='utf-8')

        with pytest.raises(NotAGitCheckoutError, match=str(package)):
            bundled_package_files(package_directory=package)

    def test_a_missing_git_is_an_error(self, tmp_path, mocker):
        mocker.patch('scripts.git_checkout.shutil.which', return_value=None)

        with pytest.raises(FileNotFoundError, match='git is not on PATH'):
            bundled_package_files(package_directory=tmp_path)


class TestEngineArchive:
    """The engine archive PyScript unpacks."""

    def test_members_are_under_the_package_name(self, tmp_path):
        package = make_package(tmp_path)
        archive_path = tmp_path / 'glitchygames.zip'

        count = write_engine_archive(package_directory=package, archive_path=archive_path)

        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            assert archive.read('glitchygames/engine/game_engine.py') == b'ENGINE = 1\n'
        assert count == 5
        assert names[0] == 'glitchygames/__init__.py'
        assert 'glitchygames/api/main.py' not in names

    def test_the_engine_version_is_readable_where_the_archive_is_unpacked(self, tmp_path):
        """Unpacked (not installed), the engine still knows its version: a replay checks it."""
        package = make_package(tmp_path)
        archive_path = tmp_path / 'glitchygames.zip'
        unpacked = tmp_path / 'unpacked'

        write_engine_archive(
            package_directory=package, archive_path=archive_path, engine_version='1.2.3'
        )
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(unpacked)

        (distribution,) = importlib.metadata.distributions(path=[str(unpacked)])
        assert distribution.metadata['Name'] == 'glitchygames'
        assert distribution.version == '1.2.3'

    def test_without_package_metadata_no_version_is_bundled(self, mocker):
        mocker.patch.object(
            importlib.metadata,
            'version',
            side_effect=importlib.metadata.PackageNotFoundError('glitchygames'),
        )

        assert installed_engine_version() is None

    def test_the_same_sources_make_the_same_archive(self, tmp_path):
        """Fixed timestamps and order: a rebuild of unchanged sources is byte-identical."""
        package = make_package(tmp_path)
        first, second = tmp_path / 'first.zip', tmp_path / 'second.zip'

        write_engine_archive(package_directory=package, archive_path=first)
        (package / 'engine' / 'game_engine.py').touch()
        write_engine_archive(package_directory=package, archive_path=second)

        assert first.read_bytes() == second.read_bytes()


class TestGeneratedFiles:
    """pyscript.toml, boot_config.json and index.html."""

    def test_pyscript_config_loads_our_wheel_and_the_engine(self):
        config = tomllib.loads(pyscript_config(wheel_name=WHEEL_NAME))

        assert config['packages'] == [f'./wheels/{WHEEL_NAME}', 'numpy', 'pydantic', 'tomli-w']
        assert config['files']['./glitchygames.zip'] == './*'
        assert config['files']['./boot_config.json'] == './boot_config.json'
        for module in ('browser_storage.py', 'browser_clipboard.py', 'browser_user_files.py'):
            assert config['files'][f'./{module}'] == f'./{module}'

    def test_a_member_games_package_is_its_own_archive(self):
        """Mr. Muncher's bundle ships mr_muncher.zip beside the engine's archive."""
        config = pyscript_config(wheel_name=WHEEL_NAME, member_packages=('mr_muncher',))

        assert '"./glitchygames.zip" = "./*"' in config
        assert '"./mr_muncher.zip" = "./*"' in config
        assert (
            './mr_muncher.zip' not in tomllib.loads(pyscript_config(wheel_name=WHEEL_NAME))['files']
        )

    @pytest.mark.parametrize(
        'moved_package',
        [
            'mr_muncher',
            'brave_adventurer',
            'brave_adventurer_papyrus',
            'clockwork_keep',
            'drawing_fire',
        ],
    )
    def test_the_engine_archive_no_longer_holds_the_moved_game(self, moved_package):
        """The moved games' code is not under src/glitchygames/ any more."""
        files = bundled_package_files(package_directory=PACKAGE_DIRECTORY)

        assert not any(path.parts[:2] == ('examples', moved_package) for path in files)

    def test_the_engine_archive_no_longer_holds_paddleslap_or_its_demo(self):
        """PaddleSlap was one module (examples/paddleslap.py) with its demo folder beside it."""
        files = {
            path.as_posix() for path in bundled_package_files(package_directory=PACKAGE_DIRECTORY)
        }

        assert 'examples/paddleslap.py' not in files
        assert not any(name.startswith('examples/paddleslap_demos/') for name in files)

    def test_only_member_games_name_member_packages(self):
        assert GAMES['mr-muncher'].member_packages == ('mr_muncher',)
        assert GAMES['clockwork-keep'].member_packages == ('clockwork_keep',)
        assert GAMES['paddleslap'].member_packages == ('paddleslap',)
        assert GAMES['drawing-fire'].member_packages == ('drawing_fire',)
        assert GAMES['bitmappy'].member_packages == ('bitmappy',)
        assert [name for name, game in GAMES.items() if game.member_packages] == [
            'paddleslap',
            'brave-adventurer',
            'clockwork-keep',
            'mr-muncher',
            'drawing-fire',
            'bitmappy',
        ]

    def test_brave_adventurer_starts_its_title_screen_with_both_games(self):
        """One page for both games: the launcher's title screen, and all four packages."""
        brave_adventurer = GAMES['brave-adventurer']

        assert (brave_adventurer.module, brave_adventurer.scene_class) == (
            'brave_adventurer_modes.title',
            'TitleScene',
        )
        assert brave_adventurer.member_packages == (
            'brave_adventurer_core',
            'brave_adventurer',
            'brave_adventurer_papyrus',
            'brave_adventurer_modes',
        )
        (member,) = [
            member
            for member in workspace_members(project_root=REPOSITORY_DIRECTORY)
            if member.distribution == 'brave-adventurer'
        ]
        assert set(brave_adventurer.member_packages) == set(member.import_packages)

    def test_a_game_depending_on_a_member_ships_both_archives(self, tmp_path, monkeypatch):
        """A game needing a shared core lists both archives, the one depended on first."""
        member_packages = ('brave_adventurer_core', 'brave_adventurer_papyrus')
        config_text = pyscript_config(wheel_name=WHEEL_NAME, member_packages=member_packages)
        archive_lines = [
            line.split(' = ')[0].strip('"') for line in config_text.splitlines() if '.zip' in line
        ]

        assert archive_lines == [
            './glitchygames.zip',
            './brave_adventurer_core.zip',
            './brave_adventurer_papyrus.zip',
        ]

        written_packages = []

        def record_archive(*, package_directory, archive_path, **_ignored):
            written_packages.append(archive_path.name)
            return 0

        game = dataclasses.replace(GAMES['mr-muncher'], member_packages=member_packages)
        monkeypatch.setitem(GAMES, 'two-archive-game', game)
        monkeypatch.setattr(build_browser_bundle, 'write_engine_archive', record_archive)
        monkeypatch.setattr(
            build_browser_bundle,
            'member_package_directory',
            lambda *, import_package: tmp_path / import_package,
        )
        wheel_path = tmp_path / WHEEL_NAME
        wheel_path.write_bytes(b'')
        build_browser_bundle.write_bundle(
            game='two-archive-game',
            output_directory=tmp_path / 'site',
            wheel_path=wheel_path,
            arguments=[],
        )

        assert written_packages == [
            'glitchygames.zip',
            'brave_adventurer_core.zip',
            'brave_adventurer_papyrus.zip',
        ]

    def test_boot_config_names_the_game_and_its_arguments(self):
        assert boot_config(game='mr-muncher', arguments=['--target-fps', '30']) == {
            'game': 'mr-muncher',
            'module': 'mr_muncher.game',
            'scene_class': 'MrMuncherScene',
            'title': 'Mr. Muncher',
            'arguments': ['--target-fps', '30'],
            'touch_controls': touch_controls_config(layout=TOUCH_LAYOUTS['mr-muncher']),
        }

    def test_render_page_fills_the_title_and_pyscript_release(self):
        page = render_page(template='<title>$title</title> $pyscript_release', game='paddleslap')

        assert page == f'<title>Paddle Slap</title> {PYSCRIPT_RELEASE}'

    def test_every_game_module_has_its_scene_class(self):
        """The table names real modules and classes (what boot.py imports in the browser)."""
        for specification in GAMES.values():
            module = __import__(specification.module, fromlist=[specification.scene_class])
            assert hasattr(module, specification.scene_class)


class TestReusableWheel:
    """When the submodule's built wheel is reused instead of rebuilt."""

    @staticmethod
    def write_build(directory: Path, **info_overrides: object) -> Path:
        """Write a wheel and its build-info.json into ``directory``.

        Returns:
            The wheel's path.

        """
        directory.mkdir(parents=True, exist_ok=True)
        wheel = directory / WHEEL_NAME
        wheel.write_bytes(b'wheel')
        info = {'wheel': WHEEL_NAME, 'source_commit': COMMIT, 'uncommitted_tracked_changes': 0}
        info.update(info_overrides)
        (directory / 'build-info.json').write_text(json.dumps(info))
        return wheel

    def test_a_clean_build_of_this_commit_is_reused(self, tmp_path):
        wheel = self.write_build(tmp_path)

        assert reusable_wheel(wheel_directory=tmp_path, commit=COMMIT) == wheel

    def test_no_build_info_means_no_wheel(self, tmp_path):
        assert reusable_wheel(wheel_directory=tmp_path, commit=COMMIT) is None

    def test_another_commits_build_is_not_reused(self, tmp_path):
        self.write_build(tmp_path, source_commit='b' * 40)

        assert reusable_wheel(wheel_directory=tmp_path, commit=COMMIT) is None

    def test_a_build_with_uncommitted_changes_is_not_reused(self, tmp_path):
        self.write_build(tmp_path, uncommitted_tracked_changes=2)

        assert reusable_wheel(wheel_directory=tmp_path, commit=COMMIT) is None

    def test_a_missing_wheel_file_is_not_reused(self, tmp_path):
        self.write_build(tmp_path).unlink()

        assert reusable_wheel(wheel_directory=tmp_path, commit=COMMIT) is None


class TestMain:
    """The command line, end to end (no serving)."""

    def test_main_writes_the_bundle_with_a_given_wheel(self, tmp_path):
        wheel = tmp_path / WHEEL_NAME
        wheel.write_bytes(b'wheel')
        output = tmp_path / 'site'

        status = main(['paddleslap', '--wheel', str(wheel), '--output', str(output), '--', '-x'])

        assert status == 0
        assert sorted(path.name for path in output.iterdir()) == [
            'boot.py',
            'boot_config.json',
            'browser_clipboard.py',
            'browser_storage.py',
            'browser_user_files.py',
            'glitchygames.zip',
            'index.html',
            'paddleslap.zip',
            'pyscript.toml',
            'touch_controls.js',
            'wheels',
        ]
        assert (output / 'wheels' / WHEEL_NAME).read_bytes() == b'wheel'
        assert json.loads((output / 'boot_config.json').read_text())['arguments'] == ['-x']
        assert '<title>Paddle Slap</title>' in (output / 'index.html').read_text()
        with zipfile.ZipFile(output / 'glitchygames.zip') as archive:
            names = set(archive.namelist())
        assert 'glitchygames/host.py' in names
        assert not any(name.startswith('glitchygames/api/') for name in names)

    def test_all_writes_every_game_and_a_page_linking_them(self, tmp_path):
        """The site published with the docs (play/): one bundle per game, and an index."""
        wheel = tmp_path / WHEEL_NAME
        wheel.write_bytes(b'wheel')
        output = tmp_path / 'site'

        status = main(['all', '--wheel', str(wheel), '--output', str(output)])

        assert status == 0
        assert sorted(path.name for path in output.iterdir()) == sorted([*GAMES, 'index.html'])
        index = (output / 'index.html').read_text()
        for game, specification in GAMES.items():
            assert (output / game / 'index.html').is_file()
            assert f'<a href="{game}/">{specification.title}</a>' in index

    def test_all_takes_no_game_arguments(self, tmp_path, capsys):
        wheel = tmp_path / WHEEL_NAME
        wheel.write_bytes(b'wheel')

        with pytest.raises(SystemExit) as exit_info:
            main(['all', '--wheel', str(wheel), '--output', str(tmp_path / 'site'), '--', '-x'])

        assert exit_info.value.code == 2
        assert 'a game command line needs one game' in capsys.readouterr().err

    def test_only_the_bitmappy_bundle_holds_the_editor(self, tmp_path):
        """Bitmappy's bundle ships its package as bitmappy.zip; no engine archive holds it."""
        wheel = tmp_path / WHEEL_NAME
        wheel.write_bytes(b'wheel')

        engine_archives = {}
        for game in ('bitmappy', 'paddleslap'):
            main([game, '--wheel', str(wheel), '--output', str(tmp_path / game)])
            with zipfile.ZipFile(tmp_path / game / 'glitchygames.zip') as archive:
                engine_archives[game] = set(archive.namelist())
        with zipfile.ZipFile(tmp_path / 'bitmappy' / 'bitmappy.zip') as archive:
            bitmappy_names = set(archive.namelist())

        assert 'bitmappy/editor.py' in bitmappy_names
        assert not (tmp_path / 'paddleslap' / 'bitmappy.zip').exists()
        for engine_names in engine_archives.values():
            assert not any(
                name.startswith(('bitmappy/', 'glitchygames/bitmappy/')) for name in engine_names
            )
        assert not any(name.startswith('glitchygames/api/') for name in engine_archives['bitmappy'])

    def test_a_member_games_bundle_holds_its_package_apart_from_the_engine(self, tmp_path):
        wheel = tmp_path / WHEEL_NAME
        wheel.write_bytes(b'wheel')

        main(['mr-muncher', '--wheel', str(wheel), '--output', str(tmp_path / 'muncher')])

        with zipfile.ZipFile(tmp_path / 'muncher' / 'mr_muncher.zip') as archive:
            member_names = set(archive.namelist())
        with zipfile.ZipFile(tmp_path / 'muncher' / 'glitchygames.zip') as archive:
            engine_names = set(archive.namelist())
        assert 'mr_muncher/game.py' in member_names
        assert not any(name.startswith('glitchygames/') for name in member_names)
        assert not any(name.startswith('mr_muncher/') for name in engine_names)
        assert '"./mr_muncher.zip" = "./*"' in (tmp_path / 'muncher' / 'pyscript.toml').read_text()

    def test_bitmappys_bundle_ships_the_engine_and_its_app_package(self, tmp_path):
        """Bitmappy is a member of the apps layer: it ships glitchygames.zip and bitmappy.zip."""
        wheel = tmp_path / WHEEL_NAME
        wheel.write_bytes(b'wheel')

        main(['bitmappy', '--wheel', str(wheel), '--output', str(tmp_path / 'bitmappy')])

        assert sorted(path.name for path in (tmp_path / 'bitmappy').glob('*.zip')) == [
            'bitmappy.zip',
            'glitchygames.zip',
        ]
        assert '"./bitmappy.zip" = "./*"' in (tmp_path / 'bitmappy' / 'pyscript.toml').read_text()

    def test_drawing_fires_bundle_ships_its_sprite_in_its_package(self, tmp_path):
        """The soldier sprite is package data: it ships in drawing_fire.zip, not the engine's."""
        wheel = tmp_path / WHEEL_NAME
        wheel.write_bytes(b'wheel')

        main(['drawing-fire', '--wheel', str(wheel), '--output', str(tmp_path / 'fire')])

        with zipfile.ZipFile(tmp_path / 'fire' / 'drawing_fire.zip') as archive:
            member_names = set(archive.namelist())
        assert {'drawing_fire/game.py', 'drawing_fire/sprites/soldier.toml'} <= member_names
        assert '"./drawing_fire.zip" = "./*"' in (tmp_path / 'fire' / 'pyscript.toml').read_text()

    def test_paddleslaps_bundle_ships_its_demo_in_its_package(self, tmp_path):
        """The attract-mode demo is package data: it ships in paddleslap.zip, not the engine's."""
        wheel = tmp_path / WHEEL_NAME
        wheel.write_bytes(b'wheel')

        main(['paddleslap', '--wheel', str(wheel), '--output', str(tmp_path / 'slap')])

        with zipfile.ZipFile(tmp_path / 'slap' / 'paddleslap.zip') as archive:
            member_names = set(archive.namelist())
        assert {'paddleslap/__init__.py', 'paddleslap/demos/rally.jsonl.gz'} <= member_names
        assert '"./paddleslap.zip" = "./*"' in (tmp_path / 'slap' / 'pyscript.toml').read_text()

    def test_main_replaces_an_earlier_bundle(self, tmp_path):
        wheel = tmp_path / WHEEL_NAME
        wheel.write_bytes(b'wheel')
        output = tmp_path / 'site'
        output.mkdir()
        (output / 'stale.txt').write_text('old')

        main(['paddleslap', '--wheel', str(wheel), '--output', str(output)])

        assert not (output / 'stale.txt').exists()

    def test_main_reuses_the_submodules_wheel(self, tmp_path, mocker):
        """Without --wheel, a clean build of the submodule's commit is used, not rebuilt."""
        wheel_directory = tmp_path / 'pygame-ce' / 'dist-pyodide'
        wheel = TestReusableWheel.write_build(wheel_directory)
        mocker.patch.object(build_browser_bundle, 'PYGAME_CE_DIRECTORY', tmp_path / 'pygame-ce')
        mocker.patch.object(build_browser_bundle, 'submodule_commit', return_value=COMMIT)
        build_wheel = mocker.patch.object(build_browser_bundle, 'build_wheel')

        main(['paddleslap', '--output', str(tmp_path / 'site')])

        build_wheel.assert_not_called()
        assert (tmp_path / 'site' / 'wheels' / wheel.name).is_file()


def test_the_server_sends_python_as_text_and_never_caches(tmp_path):
    """The local server gives Pyodide the MIME types it needs and turns caching off."""
    # Bytes, not text: write_text would write Windows line endings there
    (tmp_path / 'boot.py').write_bytes(b'print(1)\n')
    handler = functools.partial(BundleRequestHandler, directory=str(tmp_path))
    with ThreadingHTTPServer(('127.0.0.1', 0), handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/boot.py') as response:
                content_type = response.headers['Content-Type']
                cache_control = response.headers['Cache-Control']
                body = response.read()
        finally:
            server.shutdown()

    assert content_type == 'text/plain'
    assert cache_control == 'no-store'
    assert body == b'print(1)\n'


def occupied_port() -> socket.socket:
    """Bind and listen on a free localhost port, holding it.

    Returns:
        The listening socket (close it when done).

    """
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(('127.0.0.1', 0))
    holder.listen()
    return holder


class TestServerPort:
    """A taken default port falls back to the next free one; an asked-for port does not."""

    def test_a_taken_default_port_falls_back_to_a_later_one(self, tmp_path, mocker):
        holder = occupied_port()
        taken = holder.getsockname()[1]
        mocker.patch.object(build_browser_bundle, 'DEFAULT_PORT', taken)
        try:
            server = bind_server(directory=tmp_path, port=None)
            try:
                assert server.server_address[1] > taken
            finally:
                server.server_close()
        finally:
            holder.close()

    def test_a_taken_port_asked_for_is_an_error(self, tmp_path):
        holder = occupied_port()
        taken = holder.getsockname()[1]
        try:
            with pytest.raises(PortUnavailableError, match=f'port {taken} is in use'):
                bind_server(directory=tmp_path, port=taken)
        finally:
            holder.close()

    def test_every_default_port_taken_is_an_error(self, tmp_path, mocker):
        holder = occupied_port()
        mocker.patch.object(build_browser_bundle, 'DEFAULT_PORT', holder.getsockname()[1])
        mocker.patch.object(build_browser_bundle, 'FALLBACK_PORT_COUNT', 0)
        try:
            with pytest.raises(PortUnavailableError, match='are all in use'):
                bind_server(directory=tmp_path, port=None)
        finally:
            holder.close()

    def test_other_bind_errors_are_raised_as_they_are(self, tmp_path, mocker):
        mocker.patch.object(
            build_browser_bundle,
            'ThreadingHTTPServer',
            side_effect=PermissionError(errno.EACCES, 'denied'),
        )
        with pytest.raises(PermissionError):
            bind_server(directory=tmp_path, port=80)

    def test_windows_access_denied_on_a_held_port_is_a_taken_port(self, tmp_path, mocker):
        """Windows refuses a port another socket holds with WSAEACCES, not WSAEADDRINUSE.

        HTTPServer binds with SO_REUSEADDR, and Windows answers that for a port a listening
        socket holds with WSAEACCES (CircleCI's Windows job, 2026-10-24).
        """
        held = PermissionError(errno.EACCES, 'forbidden')
        held.winerror = build_browser_bundle.WINDOWS_ACCESS_DENIED_ERROR
        mocker.patch.object(build_browser_bundle, 'ThreadingHTTPServer', side_effect=held)

        with pytest.raises(PortUnavailableError, match='port 8123 is in use'):
            bind_server(directory=tmp_path, port=8123)

    def test_main_reports_a_taken_port_and_exits_1(self, tmp_path, capsys):
        wheel = tmp_path / WHEEL_NAME
        wheel.write_bytes(b'wheel')
        holder = occupied_port()
        taken = holder.getsockname()[1]
        try:
            status = main([
                'paddleslap',
                '--wheel',
                str(wheel),
                '--output',
                str(tmp_path / 'site'),
                '--serve',
                '--port',
                str(taken),
            ])
        finally:
            holder.close()

        assert status == 1
        assert f'Cannot serve the bundle: port {taken} is in use' in capsys.readouterr().out


# Console scripts that are not games (the API server and client): no browser build
NOT_GAME_CONSOLE_SCRIPTS = frozenset({'glitchygames-server', 'glitchygames-client'})


def test_every_game_has_a_browser_build():
    """Each game's console script is a page under play/ (Papyrus was once left out).

    Brave Adventurer's two games are one console script and one page: the launcher's title
    screen offers both.
    """
    scripts = declared_console_scripts(project_root=REPOSITORY_DIRECTORY)

    assert set(GAMES) == set(scripts) - NOT_GAME_CONSOLE_SCRIPTS
