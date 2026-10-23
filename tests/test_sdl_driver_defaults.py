"""Tests for the SDL driver defaults that tests/conftest.py applies to every test run.

Also the driver isolation it applies after each test (tests/sdl_driver_isolation.py): a test
that moved the SDL driver variables, display or mixer off the run's drivers (an engine run with
--headless) is put back on them. The run's drivers are 'dummy' on a dummy run, so these tests
move things off them by naming other drivers, which works on any run.
"""

import os

import pygame

from tests.display_canvas import (
    TEST_DISPLAY_SIZE,
    canvas_color_at,
    display_looks_entirely_black,
    real_display_surface,
)
from tests.sdl_defaults import (
    SDL_DRIVER_ENVIRONMENT_FOR_RUN,
    SDL_DRIVER_VARIABLES,
    default_sdl_drivers_to_dummy,
)
from tests.sdl_driver_isolation import (
    MixerState,
    SdlDriverState,
    live_sdl_driver_state,
    restore_run_sdl_drivers,
)

# Driver names no run uses: a run state naming them makes the live drivers differ from the run's
OTHER_VIDEO_DRIVER = 'other-video-driver'
OTHER_AUDIO_DRIVER = 'other-audio-driver'
# A mixer format and channel count unlike pygame's defaults (44100 Hz, 16-bit, stereo, 8)
OTHER_MIXER_FORMAT = (22050, -16, 1)
OTHER_MIXING_CHANNEL_COUNT = 5


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


def test_the_run_environment_is_the_variables_after_defaulting():
    """The run's variables are the ones decided at startup, for every driver variable."""
    assert tuple(SDL_DRIVER_ENVIRONMENT_FOR_RUN) == SDL_DRIVER_VARIABLES
    for name in SDL_DRIVER_VARIABLES:
        assert SDL_DRIVER_ENVIRONMENT_FOR_RUN[name]


def test_the_run_state_is_what_every_test_starts_on(run_sdl_driver_state):
    """Each test starts on the run's display and mixer drivers, with the run's mixer format."""
    assert run_sdl_driver_state.video_driver is not None
    assert run_sdl_driver_state.mixer is not None
    assert live_sdl_driver_state().driver_names() == run_sdl_driver_state.driver_names()
    for name in SDL_DRIVER_VARIABLES:
        assert os.environ[name] == SDL_DRIVER_ENVIRONMENT_FOR_RUN[name]


def test_nothing_is_restored_when_nothing_changed(run_sdl_driver_state):
    """A test that changed no driver costs a few reads: the display is not reopened."""
    display_before = real_display_surface()

    restored = restore_run_sdl_drivers(
        run_environment=SDL_DRIVER_ENVIRONMENT_FOR_RUN, run_state=run_sdl_driver_state
    )

    assert restored == []
    assert real_display_surface() is display_before


def test_driver_variables_a_test_changed_are_put_back(monkeypatch, run_sdl_driver_state):
    """What --headless leaves behind: the variables naming another driver are set back."""
    monkeypatch.setenv('SDL_VIDEODRIVER', OTHER_VIDEO_DRIVER)
    monkeypatch.delenv('SDL_AUDIODRIVER')

    restored = restore_run_sdl_drivers(
        run_environment=SDL_DRIVER_ENVIRONMENT_FOR_RUN, run_state=run_sdl_driver_state
    )

    assert restored == [
        f"SDL_VIDEODRIVER (was '{OTHER_VIDEO_DRIVER}')",
        'SDL_AUDIODRIVER (was None)',
    ]
    for name in SDL_DRIVER_VARIABLES:
        assert os.environ[name] == SDL_DRIVER_ENVIRONMENT_FOR_RUN[name]


def test_a_display_on_another_driver_is_reopened_on_the_runs_showing_the_canvas(
    run_sdl_driver_state,
):
    """The display is restarted on the run's driver and shows the canvas, never black.

    The run state names another driver, so the live display differs from it on any run; it
    is restarted on the driver the run's variables name (the live one here).
    """
    live_video_driver = pygame.display.get_driver()
    pygame.display.get_surface().fill((0, 0, 0))
    pygame.display.set_mode((320, 200))
    other_run_state = run_sdl_driver_state.model_copy(update={'video_driver': OTHER_VIDEO_DRIVER})

    restored = restore_run_sdl_drivers(
        run_environment=SDL_DRIVER_ENVIRONMENT_FOR_RUN, run_state=other_run_state
    )

    assert restored == [f"the display (video driver '{live_video_driver}')"]
    display = real_display_surface()
    assert display is not None
    assert display.get_size() == TEST_DISPLAY_SIZE
    assert not display_looks_entirely_black(display)
    assert display.get_at((0, 0))[:3] == canvas_color_at(x=0, y=0)[:3]
    assert live_sdl_driver_state().driver_names() == run_sdl_driver_state.driver_names()


def test_a_mixer_on_another_driver_is_restarted_with_the_runs_format(run_sdl_driver_state):
    """The mixer comes back on the run's driver with the run's format and channel count."""
    run_mixer = run_sdl_driver_state.mixer
    assert run_mixer is not None
    other_run_state = SdlDriverState(
        video_driver=run_sdl_driver_state.video_driver,
        mixer=MixerState(
            audio_driver=OTHER_AUDIO_DRIVER,
            mixer_format=OTHER_MIXER_FORMAT,
            mixing_channel_count=OTHER_MIXING_CHANNEL_COUNT,
        ),
    )
    try:
        restored = restore_run_sdl_drivers(
            run_environment=SDL_DRIVER_ENVIRONMENT_FOR_RUN, run_state=other_run_state
        )

        assert restored == [f"the mixer (audio driver '{run_mixer.audio_driver}')"]
        assert pygame.mixer.get_init() == OTHER_MIXER_FORMAT
        assert pygame.mixer.get_num_channels() == OTHER_MIXING_CHANNEL_COUNT
    finally:
        # The run's own mixer back for the next test: the live one now differs from a state
        # naming yet another driver, so it is restarted with the run's format
        restore_run_sdl_drivers(
            run_environment=SDL_DRIVER_ENVIRONMENT_FOR_RUN,
            run_state=run_sdl_driver_state.model_copy(
                update={'mixer': run_mixer.model_copy(update={'audio_driver': OTHER_AUDIO_DRIVER})}
            ),
        )
    assert live_sdl_driver_state() == run_sdl_driver_state


def test_a_mixer_a_test_stopped_is_started_again(run_sdl_driver_state):
    """A stopped mixer is started again with the run's format, as every test starts with one."""
    pygame.mixer.quit()

    restored = restore_run_sdl_drivers(
        run_environment=SDL_DRIVER_ENVIRONMENT_FOR_RUN, run_state=run_sdl_driver_state
    )

    assert restored == ['the mixer (audio driver None)']
    assert live_sdl_driver_state() == run_sdl_driver_state


def test_without_pygame_running_only_the_variables_are_put_back(monkeypatch, run_sdl_driver_state):
    """After pygame.quit() nothing is started: the next test's setup starts pygame."""
    monkeypatch.setenv('SDL_AUDIODRIVER', OTHER_AUDIO_DRIVER)
    pygame.quit()

    restored = restore_run_sdl_drivers(
        run_environment=SDL_DRIVER_ENVIRONMENT_FOR_RUN, run_state=run_sdl_driver_state
    )

    assert restored == [f"SDL_AUDIODRIVER (was '{OTHER_AUDIO_DRIVER}')"]
    assert not pygame.get_init()
    assert live_sdl_driver_state() == SdlDriverState(video_driver=None, mixer=None)
