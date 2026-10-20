"""Tests for the dummy SDL driver defaults that tests/conftest.py applies to every test run."""

import os

from tests.sdl_defaults import (
    SDL_DRIVER_VARIABLES,
    default_sdl_drivers_to_dummy,
)


def test_drivers_are_dummy_unless_the_invoker_set_them(sdl_variables_defaulted_at_startup):
    """Each driver is 'dummy' for this run, unless the process started with its own value."""
    for name in SDL_DRIVER_VARIABLES:
        if name in sdl_variables_defaulted_at_startup:
            assert os.environ[name] == 'dummy'
        else:
            assert os.environ[name], f'{name} was set by the invoker and must not be empty'


def test_defaulting_sets_unset_drivers_to_dummy(monkeypatch):
    """Unset driver variables become 'dummy', and are reported as defaulted."""
    for name in SDL_DRIVER_VARIABLES:
        monkeypatch.delenv(name, raising=False)

    assert default_sdl_drivers_to_dummy() == SDL_DRIVER_VARIABLES
    for name in SDL_DRIVER_VARIABLES:
        assert os.environ[name] == 'dummy'


def test_defaulting_keeps_a_value_the_invoker_set(monkeypatch):
    """A driver the invoker already chose is left alone and not reported as defaulted."""
    monkeypatch.setenv('SDL_VIDEODRIVER', 'cocoa')
    monkeypatch.delenv('SDL_AUDIODRIVER', raising=False)

    assert default_sdl_drivers_to_dummy() == ('SDL_AUDIODRIVER',)
    assert os.environ['SDL_VIDEODRIVER'] == 'cocoa'
    assert os.environ['SDL_AUDIODRIVER'] == 'dummy'
