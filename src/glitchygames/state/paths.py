"""Cross-platform save and cache directory resolution.

Resolves the appropriate user data and cache directories for each platform
without requiring external dependencies like platformdirs.

Saves (``get_save_directory``):
    macOS:   ~/Library/Application Support/<app_name>/
    Linux:   $XDG_DATA_HOME/<app_name>/ (default ~/.local/share/<app_name>/)
    Windows: %APPDATA%/<app_name>/

Caches (``get_cache_directory``: what can be made again, such as rendered sounds; sound engine
implementation spec 6.4):
    macOS:   ~/Library/Caches/<app_name>/
    Linux:   $XDG_CACHE_HOME/<app_name>/ (default ~/.cache/<app_name>/)
    Windows: %LOCALAPPDATA%/<app_name>/Cache/
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Valid app names: lowercase letters, digits, hyphens, underscores
_APP_NAME_PATTERN = re.compile(r'^[a-z0-9_-]+$')


def validate_app_name(app_name: str) -> None:
    """Validate that an app name is safe for use as a directory name.

    App names must contain only lowercase letters, digits, hyphens,
    and underscores. This prevents path traversal, hidden directories,
    and Windows reserved names.

    Args:
        app_name: The application name to validate.

    Raises:
        ValueError: If the app name is empty or contains invalid characters.

    """
    if not app_name:
        msg = 'app_name must not be empty'
        raise ValueError(msg)

    if not _APP_NAME_PATTERN.fullmatch(app_name):
        msg = (
            f"Invalid app_name '{app_name}': must contain only "
            f'lowercase letters, digits, hyphens, and underscores'
        )
        raise ValueError(msg)


def get_save_directory(app_name: str) -> Path:
    """Get the platform-specific save directory for an application.

    The directory is NOT created by this function — that happens
    on the first save operation.

    Args:
        app_name: Application name (used as the directory name).
            Must match [a-z0-9_-]+.

    Returns:
        Path to the application's save directory.

    """
    validate_app_name(app_name)

    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / app_name

    if sys.platform.startswith('win'):
        appdata = os.environ.get('APPDATA')
        if appdata:
            return Path(appdata) / app_name
        return Path.home() / 'AppData' / 'Roaming' / app_name

    # Linux and other POSIX
    xdg_data_home = os.environ.get('XDG_DATA_HOME')
    if xdg_data_home:
        return Path(xdg_data_home) / app_name
    return Path.home() / '.local' / 'share' / app_name


def get_cache_directory(app_name: str) -> Path:
    """Get the platform-specific cache directory for an application.

    Everything under it can be made again, so the user or the system may delete it at any time.
    The directory is not created here.

    Args:
        app_name: Application name (used as the directory name). Must match [a-z0-9_-]+.

    Returns:
        Path to the application's cache directory.

    """
    validate_app_name(app_name)

    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Caches' / app_name

    if sys.platform.startswith('win'):
        local_app_data = os.environ.get('LOCALAPPDATA')
        if local_app_data:
            return Path(local_app_data) / app_name / 'Cache'
        return Path.home() / 'AppData' / 'Local' / app_name / 'Cache'

    # Linux and other POSIX
    xdg_cache_home = os.environ.get('XDG_CACHE_HOME')
    if xdg_cache_home:
        return Path(xdg_cache_home) / app_name
    return Path.home() / '.cache' / app_name
