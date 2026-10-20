"""Dummy SDL driver defaults applied by tests/conftest.py before pygame is imported."""

import os

SDL_DRIVER_VARIABLES = ('SDL_VIDEODRIVER', 'SDL_AUDIODRIVER')


def default_sdl_drivers_to_dummy() -> tuple[str, ...]:
    """Default each SDL driver variable to 'dummy', keeping any value already set.

    Every test run, in CI or local, gets the dummy drivers so the suite opens no windows and makes
    no sound. Keeping an existing value means `SDL_VIDEODRIVER=cocoa uv run pytest ...` still shows
    a real window.

    Returns:
        The names of the variables this call defaulted (the ones that were not already set).

    """
    defaulted = tuple(name for name in SDL_DRIVER_VARIABLES if name not in os.environ)
    for name in SDL_DRIVER_VARIABLES:
        os.environ.setdefault(name, 'dummy')
    return defaulted


# Runs at import, so importing this module before pygame is enough to set the defaults
SDL_VARIABLES_DEFAULTED_AT_STARTUP = default_sdl_drivers_to_dummy()
