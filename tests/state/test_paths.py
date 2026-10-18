"""Tests for cross-platform save directory resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from glitchygames.state.paths import get_save_directory, validate_app_name


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

    def test_macos_path(self, mocker: object) -> None:
        """MacOS uses ~/Library/Application Support/."""
        import glitchygames.state.paths as paths_module

        mocker.patch.object(paths_module.sys, 'platform', 'darwin')  # type: ignore[union-attr]
        mocker.patch.object(Path, 'home', return_value=Path('/Users/testuser'))  # type: ignore[union-attr]

        result = get_save_directory('mygame')
        assert result == Path('/Users/testuser/Library/Application Support/mygame')

    def test_linux_default_path(self, mocker: object) -> None:
        """Linux without XDG_DATA_HOME uses ~/.local/share/."""
        import glitchygames.state.paths as paths_module

        mocker.patch.object(paths_module.sys, 'platform', 'linux')  # type: ignore[union-attr]
        mocker.patch.object(Path, 'home', return_value=Path('/home/testuser'))  # type: ignore[union-attr]
        mocker.patch.dict(paths_module.os.environ, {}, clear=True)  # type: ignore[union-attr]

        result = get_save_directory('mygame')
        assert result == Path('/home/testuser/.local/share/mygame')

    def test_linux_xdg_path(self, mocker: object) -> None:
        """Linux with XDG_DATA_HOME uses that directory."""
        import glitchygames.state.paths as paths_module

        mocker.patch.object(paths_module.sys, 'platform', 'linux')  # type: ignore[union-attr]
        mocker.patch.dict(  # type: ignore[union-attr]
            paths_module.os.environ,
            {'XDG_DATA_HOME': '/custom/data'},
            clear=True,
        )

        result = get_save_directory('mygame')
        assert result == Path('/custom/data/mygame')

    def test_windows_appdata_path(self, tmp_path: Path, mocker: object) -> None:
        """Windows uses %APPDATA%."""
        import glitchygames.state.paths as paths_module

        fake_appdata = str(tmp_path / 'appdata')
        mocker.patch.object(paths_module.sys, 'platform', 'win32')  # type: ignore[union-attr]
        mocker.patch.dict(  # type: ignore[union-attr]
            paths_module.os.environ,
            {'APPDATA': fake_appdata},
            clear=True,
        )

        result = get_save_directory('mygame')
        assert result == Path(fake_appdata) / 'mygame'

    def test_invalid_name_raises(self) -> None:
        """Invalid app name raises ValueError."""
        with pytest.raises(ValueError, match='Invalid app_name'):
            get_save_directory('Invalid Name!')
