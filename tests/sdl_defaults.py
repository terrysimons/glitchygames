"""SDL defaults tests/conftest.py applies before pygame is imported: dummy drivers, no real pads."""

import os

SDL_DRIVER_VARIABLES = ('SDL_VIDEODRIVER', 'SDL_AUDIODRIVER')
# SDL's joystick drivers on macOS. Each alone finds pads (measured with a DualSense and a
# Logitech Dual Action, 2026-10-24, through --list-input-devices: HIDAPI the DualSense, MFi and
# IOKit both), so all three are off for a test run. Hints: SDL_HINT_JOYSTICK_HIDAPI,
# SDL_HINT_JOYSTICK_MFI, SDL_HINT_JOYSTICK_IOKIT (SDL2's SDL_hints.h). Windows' and Linux's
# drivers are not covered (no pad there to check with; CI has none)
SDL_JOYSTICK_DRIVER_VARIABLES = ('SDL_JOYSTICK_HIDAPI', 'SDL_JOYSTICK_MFI', 'SDL_JOYSTICK_IOKIT')


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


def default_joystick_drivers_off() -> tuple[str, ...]:
    """Default each of SDL's joystick drivers to off, keeping any value already set.

    A pad attached to the machine reached tests and changed what they saw (a recording test
    recorded the real DualSense); tests use stand-ins through the devices door instead
    (tests/input/stand_in_devices.py). Keeping an existing value means
    `SDL_JOYSTICK_MFI=1 uv run pytest ...` still sees a real pad. The native child run
    (tests/driver_comparison.py) inherits them with the rest of the environment.

    Returns:
        The names of the variables this call defaulted (the ones that were not already set).

    """
    defaulted = tuple(name for name in SDL_JOYSTICK_DRIVER_VARIABLES if name not in os.environ)
    for name in SDL_JOYSTICK_DRIVER_VARIABLES:
        os.environ.setdefault(name, '0')
    return defaulted


# Runs at import, so importing this module before pygame is enough to set the defaults
SDL_VARIABLES_DEFAULTED_AT_STARTUP = default_sdl_drivers_to_dummy()
default_joystick_drivers_off()

# The run's SDL driver variables, by name, as decided at startup: the test harness puts back any
# a test changed (tests/sdl_driver_isolation.py), e.g. one that ran an engine with --headless
SDL_DRIVER_ENVIRONMENT_FOR_RUN: dict[str, str] = {
    name: os.environ[name] for name in SDL_DRIVER_VARIABLES
}
