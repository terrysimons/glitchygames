"""After collection, every project logger is still at NOTSET and logging is not disabled (#235).

BUGS.md #235 and #236 were modules setting a shared logger's level when imported: the suite
imports them at collection (``scripts/raw_sprite_loader.py`` through ``tests/sprites/``,
the text input demo through its tests), and from then on every ``game.*`` logger logged what
``--log-level`` and ``--log-cli-level`` dropped, kept in memory by pytest until the serial Linux
CI run was killed at 2 GB. This checks that mechanism where it hurt, in the test process, once
everything collected has been imported, whatever imported what: every logger named ``game`` or
``glitchygames`` (or under them) must be at NOTSET, and ``logging.disable`` off. A run that fails
it stops before any test, naming each logger and its level.

The static guard (tests/test_logger_level_source_guard.py) and the import guard
(tests/test_logger_levels_at_import.py) name the line or module; this catches what they cannot
see, in the files the suite really imports. Registered in the root conftest.py's
``pytest_plugins``. Tests: tests/test_collection_logger_levels.py.
"""

from __future__ import annotations

import logging

import pytest

# The project's logger names: the engine's and the games' are under these
PROJECT_LOGGER_ROOTS = ('game', 'glitchygames')


def is_project_logger(name: str) -> bool:
    """Tell whether a logger is the project's (``game``, ``game.paddle``, ``glitchygames.x``).

    Returns:
        True when its name is a project root or under one.

    """
    return any(name == root or name.startswith(f'{root}.') for root in PROJECT_LOGGER_ROOTS)


def project_logger_settings() -> list[str]:
    """Return what is set that should not be: project loggers' levels, and logging.disable.

    Returns:
        ``<logger> is at <LEVEL>`` for each project logger with a level, sorted, then
        ``logging.disable is at <LEVEL>`` when logging is disabled.

    """
    settings = sorted(
        f'{name} is at {logging.getLevelName(logger.level)}'
        for name, logger in logging.root.manager.loggerDict.items()
        if isinstance(logger, logging.Logger)
        and is_project_logger(name)
        and logger.level != logging.NOTSET
    )
    if logging.root.manager.disable:
        settings.append(
            f'logging.disable is at {logging.getLevelName(logging.root.manager.disable)}'
        )
    return settings


def pytest_collection_finish(session: pytest.Session) -> None:
    """Stop the run if anything imported at collection set a project logger's level.

    Raises:
        pytest.UsageError: Naming each logger and its level.

    """
    del session
    settings = project_logger_settings()
    if settings:
        message = (
            'importing the collected tests set logging levels the command line should set '
            f'(BUGS.md #235, #236): {"; ".join(settings)}'
        )
        raise pytest.UsageError(message)
