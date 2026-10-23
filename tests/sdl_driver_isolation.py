"""Keep SDL's video and audio drivers from leaking between tests (used by conftest.py).

The run's drivers are decided at startup (tests/sdl_defaults.py: 'dummy' unless the invoker
chose, e.g. ``SDL_VIDEODRIVER=cocoa``). A test that constructs an engine with ``--headless``
sets ``SDL_VIDEODRIVER``/``SDL_AUDIODRIVER`` to 'dummy' and restarts a display and mixer already
running on another driver on the dummy one (``GameEngine._enter_headless_mode``). The engine
puts the variables back when its run ends, but a test that only constructs the engine, or that
puts the variables back itself (``monkeypatch``, ``mocker.patch.dict(os.environ)``) while the
display and mixer stay on 'dummy', would leave every later test on the worker on the dummy
drivers: no window, no sound. ``restore_run_sdl_drivers`` puts both back after each test, and
does nothing (a few cheap reads) when nothing changed.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pygame
from pydantic import BaseModel, ConfigDict

from tests.display_canvas import TEST_DISPLAY_SIZE, show_canvas

if TYPE_CHECKING:
    from collections.abc import Mapping

# The real pygame functions, captured before any test can patch them: the check runs in the
# autouse fixture's teardown, while a test's mocker patches may still be in place
_REAL_PYGAME_GET_INIT = pygame.get_init
_REAL_DISPLAY_GET_INIT = pygame.display.get_init
_REAL_DISPLAY_GET_DRIVER = pygame.display.get_driver
_REAL_DISPLAY_INIT = pygame.display.init
_REAL_DISPLAY_QUIT = pygame.display.quit
_REAL_DISPLAY_SET_MODE = pygame.display.set_mode
_REAL_MIXER_GET_INIT = pygame.mixer.get_init
_REAL_MIXER_GET_DRIVER = pygame.mixer.get_driver
_REAL_MIXER_GET_NUM_CHANNELS = pygame.mixer.get_num_channels
_REAL_MIXER_INIT = pygame.mixer.init
_REAL_MIXER_QUIT = pygame.mixer.quit
_REAL_MIXER_SET_NUM_CHANNELS = pygame.mixer.set_num_channels


class MixerState(BaseModel):
    """The driver and format pygame's mixer runs with.

    Attributes:
        audio_driver: The mixer's audio driver.
        mixer_format: The mixer's (frequency, size, output channels).
        mixing_channel_count: The mixer's number of mixing channels.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    audio_driver: str
    mixer_format: tuple[int, int, int]
    mixing_channel_count: int


class SdlDriverState(BaseModel):
    """The drivers pygame's display and mixer run on.

    Attributes:
        video_driver: The display's video driver, or None when pygame or its display is not
            running.
        mixer: The mixer's driver and format, or None when pygame or its mixer is not running.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    video_driver: str | None
    mixer: MixerState | None

    def driver_names(self) -> tuple[str | None, str | None]:
        """Return the video and audio driver names, without the mixer's format.

        The mixing channel count is not the run's after a test that ran an engine (it reserves
        its live voice channels), so tests about drivers compare these.

        Returns:
            tuple[str | None, str | None]: The video driver and the mixer's audio driver (None
            for what is not running).

        """
        return (self.video_driver, None if self.mixer is None else self.mixer.audio_driver)


def live_sdl_driver_state() -> SdlDriverState:
    """Read the drivers pygame's display and mixer run on now (through the real functions).

    Returns:
        SdlDriverState: The live drivers, with the mixer's format and channel count.

    """
    if not _REAL_PYGAME_GET_INIT():
        return SdlDriverState(video_driver=None, mixer=None)
    video_driver = _REAL_DISPLAY_GET_DRIVER() if _REAL_DISPLAY_GET_INIT() else None
    mixer_format = _REAL_MIXER_GET_INIT()
    if mixer_format is None:
        return SdlDriverState(video_driver=video_driver, mixer=None)
    return SdlDriverState(
        video_driver=video_driver,
        mixer=MixerState(
            audio_driver=_REAL_MIXER_GET_DRIVER(),
            mixer_format=mixer_format,
            mixing_channel_count=_REAL_MIXER_GET_NUM_CHANNELS(),
        ),
    )


def restore_run_sdl_drivers(
    *, run_environment: Mapping[str, str], run_state: SdlDriverState
) -> list[str]:
    """Put the run's SDL driver variables back, and the display and mixer on the run's drivers.

    Only what differs is touched, so a test that changed nothing costs a few reads:

    - Each variable in ``run_environment`` that differs is set back first, as SDL reads them
      when the display or mixer starts.
    - When pygame is not running (a test quit it), that is all: the next test's setup starts it
      again, on the run's drivers.
    - A running display on another driver than ``run_state``'s is stopped and started again on
      the run's driver, at the test display size, showing the canvas (a new display is black,
      and a black window must never be left behind: tests/display_canvas.py). A display that is
      not running is left alone: the next test's setup opens one, on the run's driver.
    - A mixer on another driver than ``run_state``'s, or not running when the run's was, is
      started (again) on the run's driver with the run's format and number of mixing channels,
      as the engine's own --headless restart keeps a mixer's. Nothing is done when the run had
      no mixer (it could not start).

    Args:
        run_environment: The run's SDL driver variables, by name (tests/sdl_defaults.py).
        run_state: The drivers the run's display and mixer run on, read before any test ran.

    Returns:
        list[str]: Descriptions of what was put back; empty when nothing had changed.

    """
    restored: list[str] = []
    for name, run_value in run_environment.items():
        test_value = os.environ.get(name)
        if test_value != run_value:
            restored.append(f'{name} (was {test_value!r})')
            os.environ[name] = run_value
    if not _REAL_PYGAME_GET_INIT():
        return restored
    live_state = live_sdl_driver_state()
    if live_state.video_driver not in {None, run_state.video_driver}:
        restored.append(f'the display (video driver {live_state.video_driver!r})')
        _REAL_DISPLAY_QUIT()
        _REAL_DISPLAY_INIT()
        _REAL_DISPLAY_SET_MODE(TEST_DISPLAY_SIZE)
        show_canvas()
    run_mixer = run_state.mixer
    live_audio_driver = None if live_state.mixer is None else live_state.mixer.audio_driver
    if run_mixer is not None and live_audio_driver != run_mixer.audio_driver:
        restored.append(f'the mixer (audio driver {live_audio_driver!r})')
        frequency, size, output_channels = run_mixer.mixer_format
        _REAL_MIXER_QUIT()
        _REAL_MIXER_INIT(frequency=frequency, size=size, channels=output_channels)
        _REAL_MIXER_SET_NUM_CHANNELS(run_mixer.mixing_channel_count)
    return restored
