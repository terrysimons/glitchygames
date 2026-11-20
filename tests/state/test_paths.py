"""Tests for cross-platform save and cache directory resolution."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import glitchygames.state.paths as paths_module
from glitchygames.state.paths import (
    get_cache_directory,
    get_save_directory,
    platform_data_home,
    validate_app_name,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


class TestValidateAppName:
    """Tests for app name validation."""

    def test_valid_simple(self) -> None:
        """Simple lowercase name is valid."""
        validate_app_name('mygame')

    def test_valid_with_hyphens(self) -> None:
        """Name with hyphens is valid."""
        validate_app_name('brave-adventurer')

    def test_valid_with_underscores(self) -> None:
        """Name with underscores is valid."""
        validate_app_name('paddle_slap')

    def test_valid_with_digits(self) -> None:
        """Name with digits is valid."""
        validate_app_name('game2d')

    def test_empty_raises(self) -> None:
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match='must not be empty'):
            validate_app_name('')

    def test_uppercase_raises(self) -> None:
        """Uppercase letters raise ValueError."""
        with pytest.raises(ValueError, match='Invalid app_name'):
            validate_app_name('MyGame')

    def test_spaces_raise(self) -> None:
        """Spaces raise ValueError."""
        with pytest.raises(ValueError, match='Invalid app_name'):
            validate_app_name('my game')

    def test_path_separator_raises(self) -> None:
        """Path separators raise ValueError."""
        with pytest.raises(ValueError, match='Invalid app_name'):
            validate_app_name('my/game')

    def test_trailing_newline_raises(self) -> None:
        """A trailing newline raises ValueError (``$`` alone matches before a final newline)."""
        with pytest.raises(ValueError, match='Invalid app_name'):
            validate_app_name('game\n')

    def test_dot_prefix_raises(self) -> None:
        """Leading dot raises ValueError (would create hidden directory)."""
        with pytest.raises(ValueError, match='Invalid app_name'):
            validate_app_name('.hidden')

    def test_special_characters_raise(self) -> None:
        """Special characters raise ValueError."""
        with pytest.raises(ValueError, match='Invalid app_name'):
            validate_app_name('game@home!')


class TestGetSaveDirectory:
    """Tests for platform-specific save directory resolution."""

    def test_macos_path(self, mocker: MockerFixture) -> None:
        """MacOS uses ~/Library/Application Support/."""
        mocker.patch.object(paths_module.sys, 'platform', 'darwin')
        mocker.patch.object(Path, 'home', return_value=Path('/Users/testuser'))

        result = get_save_directory('mygame')
        assert result == Path('/Users/testuser/Library/Application Support/mygame')

    def test_linux_default_path(self, mocker: MockerFixture) -> None:
        """Linux without XDG_DATA_HOME uses ~/.local/share/."""
        mocker.patch.object(paths_module.sys, 'platform', 'linux')
        mocker.patch.object(Path, 'home', return_value=Path('/home/testuser'))
        mocker.patch.dict(paths_module.os.environ, {}, clear=True)

        result = get_save_directory('mygame')
        assert result == Path('/home/testuser/.local/share/mygame')

    def test_linux_xdg_path(self, mocker: MockerFixture) -> None:
        """Linux with XDG_DATA_HOME uses that directory."""
        mocker.patch.object(paths_module.sys, 'platform', 'linux')
        mocker.patch.dict(
            paths_module.os.environ,
            {'XDG_DATA_HOME': '/custom/data'},
            clear=True,
        )

        result = get_save_directory('mygame')
        assert result == Path('/custom/data/mygame')

    def test_windows_appdata_path(self, tmp_path: Path, mocker: MockerFixture) -> None:
        """Windows uses %APPDATA%."""
        fake_appdata = str(tmp_path / 'appdata')
        mocker.patch.object(paths_module.sys, 'platform', 'win32')
        mocker.patch.dict(
            paths_module.os.environ,
            {'APPDATA': fake_appdata},
            clear=True,
        )

        result = get_save_directory('mygame')
        assert result == Path(fake_appdata) / 'mygame'

    def test_windows_without_appdata_uses_the_roaming_folder(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """Windows with no (or an empty) %APPDATA% falls back to ~/AppData/Roaming."""
        mocker.patch.object(paths_module.sys, 'platform', 'win32')
        mocker.patch.dict(
            paths_module.os.environ,
            {'APPDATA': ''},
            clear=True,
        )
        mocker.patch.object(paths_module.Path, 'home', return_value=tmp_path)

        result = get_save_directory('mygame')
        assert result == tmp_path / 'AppData' / 'Roaming' / 'mygame'

    def test_invalid_name_raises(self) -> None:
        """Invalid app name raises ValueError."""
        with pytest.raises(ValueError, match='Invalid app_name'):
            get_save_directory('Invalid Name!')


class TestGetCacheDirectory:
    """The cache root for rendered sounds (sound engine implementation spec 6.4)."""

    def test_macos_uses_the_library_caches_folder(self, mocker: MockerFixture) -> None:
        mocker.patch.object(paths_module.sys, 'platform', 'darwin')
        mocker.patch.object(Path, 'home', return_value=Path('/Users/testuser'))

        assert get_cache_directory('glitchygames') == Path(
            '/Users/testuser/Library/Caches/glitchygames'
        )

    def test_linux_uses_xdg_cache_home_when_set(self, mocker: MockerFixture) -> None:
        mocker.patch.object(paths_module.sys, 'platform', 'linux')
        mocker.patch.dict(paths_module.os.environ, {'XDG_CACHE_HOME': '/custom/cache'}, clear=True)

        assert get_cache_directory('glitchygames') == Path('/custom/cache/glitchygames')

    def test_linux_defaults_to_the_dot_cache_folder(self, mocker: MockerFixture) -> None:
        mocker.patch.object(paths_module.sys, 'platform', 'linux')
        mocker.patch.object(Path, 'home', return_value=Path('/home/testuser'))
        mocker.patch.dict(paths_module.os.environ, {}, clear=True)

        assert get_cache_directory('glitchygames') == Path('/home/testuser/.cache/glitchygames')

    def test_windows_uses_local_app_data_when_set(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(paths_module.sys, 'platform', 'win32')
        mocker.patch.dict(paths_module.os.environ, {'LOCALAPPDATA': str(tmp_path)}, clear=True)

        assert get_cache_directory('glitchygames') == tmp_path / 'glitchygames' / 'Cache'

    def test_windows_without_local_app_data_uses_the_local_folder(
        self, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(paths_module.sys, 'platform', 'win32')
        mocker.patch.object(Path, 'home', return_value=Path('/Users/testuser'))
        mocker.patch.dict(paths_module.os.environ, {}, clear=True)

        assert get_cache_directory('glitchygames') == Path(
            '/Users/testuser/AppData/Local/glitchygames/Cache'
        )

    def test_an_invalid_app_name_is_refused_as_for_saves(self) -> None:
        with pytest.raises(ValueError, match='Invalid app_name'):
            get_cache_directory('Invalid Name!')


FIXED_HOME = Path('/Users/testuser')


@pytest.mark.parametrize(
    ('platform', 'environment', 'expected'),
    [
        ('darwin', {}, FIXED_HOME / 'Library' / 'Application Support'),
        ('win32', {'APPDATA': '/appdata'}, Path('/appdata')),
        ('win32', {}, FIXED_HOME / 'AppData' / 'Roaming'),
        ('linux', {'XDG_DATA_HOME': '/xdg'}, Path('/xdg')),
        ('linux', {}, FIXED_HOME / '.local' / 'share'),
    ],
    ids=['macos', 'windows-appdata', 'windows-default', 'linux-xdg', 'linux-default'],
)
def test_platform_data_home_is_what_saves_used_on_every_platform(
    platform: str, environment: dict[str, str], expected: Path, mocker: MockerFixture
) -> None:
    """The save folder is the data home joined with the app name, as it was before the lift."""
    mocker.patch.object(paths_module.sys, 'platform', platform)
    mocker.patch.object(Path, 'home', return_value=FIXED_HOME)
    mocker.patch.dict(paths_module.os.environ, environment, clear=True)

    assert platform_data_home() == expected
    assert get_save_directory('paddleslap') == expected / 'paddleslap'
