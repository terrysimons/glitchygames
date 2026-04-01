"""Cross-platform save directory resolution.

Resolves the appropriate user data directory for each platform
without requiring external dependencies like platformdirs.

Platforms:
    macOS:   ~/Library/Application Support/<app_name>/
    Linux:   $XDG_DATA_HOME/<app_name>/ (default ~/.local/share/<app_name>/)
    Windows: %APPDATA%/<app_name>/
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

    if not _APP_NAME_PATTERN.match(app_name):
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
