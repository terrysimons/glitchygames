"""set_display_mode waits for a window whose new size arrives after set_mode returns.

On SDL's x11 driver a resize of an existing window is asynchronous: SDL waits 100 ms for the
window manager, then gives up and reports the old size (pygame-ce warns "Requested window was
forcibly resized by the OS"); the real size arrives later, over the network for a remote X
server. The dummy driver resizes at once, so the slow window manager is stood in for: pygame's
set_mode answers with the old size and the warning, and the resize lands on a later pump.
"""

from __future__ import annotations

import warnings

import pygame
import pytest

from glitchygames.display_mode import FORCIBLY_RESIZED_MESSAGE, set_display_mode
from tests.display_canvas import show_canvas
from tests.slow_window_manager import (
    REAL_SET_MODE,
    SlowWindowManager,
    forcibly_resized_warning,
    install_window_manager,
)

ORIGINAL_SIZE = (320, 240)
REQUESTED_SIZE = (400, 300)
WIDENED_SIZE = (408, 300)


@pytest.fixture
def original_display():
    """The display at ORIGINAL_SIZE (the conftest puts the test display back afterwards).

    Returns:
        pygame.Surface: The display surface.

    """
    return REAL_SET_MODE(ORIGINAL_SIZE)


@pytest.mark.usefixtures('original_display')
class TestSetDisplayMode:
    """The display has the requested size when set_display_mode returns, or it warns."""

    def test_a_size_taken_at_once_returns_without_pumping(self, mocker):
        pump = mocker.spy(pygame.event, 'pump')

        with warnings.catch_warnings():
            warnings.simplefilter('error')
            surface = set_display_mode(size=REQUESTED_SIZE)

        assert surface.get_size() == REQUESTED_SIZE
        assert pump.call_count == 0
        # A new display is black: show the canvas (the test display rule)
        show_canvas()

    def test_a_late_resize_is_waited_for_without_a_warning(self, mocker):
        window_manager = SlowWindowManager(pumps_until_resized=3, final_size=REQUESTED_SIZE)
        install_window_manager(mocker, window_manager=window_manager)

        with warnings.catch_warnings():
            warnings.simplefilter('error')
            surface = set_display_mode(size=REQUESTED_SIZE)

        assert surface.get_size() == REQUESTED_SIZE
        assert pygame.display.get_surface().get_size() == REQUESTED_SIZE
        assert window_manager.pumps == 3
        # A new display is black: show the canvas (the test display rule)
        show_canvas()

    def test_a_window_manager_choosing_another_size_warns_with_it(self, mocker):
        """It stops at the first change (as SDL does) and warns with the size it got."""
        window_manager = SlowWindowManager(pumps_until_resized=2, final_size=WIDENED_SIZE)
        install_window_manager(mocker, window_manager=window_manager)

        with pytest.warns(RuntimeWarning, match=FORCIBLY_RESIZED_MESSAGE) as caught:
            surface = set_display_mode(size=REQUESTED_SIZE)

        assert surface.get_size() == WIDENED_SIZE
        assert window_manager.pumps == 2
        assert len(caught) == 1
        assert str(caught[0].message).endswith(
            f'Requested window size: {REQUESTED_SIZE}\n\tNew window size: {WIDENED_SIZE}'
        )
        # A new display is black: show the canvas (the test display rule)
        show_canvas()

    def test_a_resize_that_never_lands_warns_after_the_wait(self, mocker):
        window_manager = SlowWindowManager(pumps_until_resized=None, final_size=REQUESTED_SIZE)
        install_window_manager(mocker, window_manager=window_manager)

        with pytest.warns(RuntimeWarning, match=FORCIBLY_RESIZED_MESSAGE) as caught:
            surface = set_display_mode(size=REQUESTED_SIZE, settle_polls=5)

        assert surface.get_size() == ORIGINAL_SIZE
        assert window_manager.pumps == 5
        assert len(caught) == 1
        assert str(caught[0].message).endswith(f'New window size: {ORIGINAL_SIZE}')
        # A new display is black: show the canvas (the test display rule)
        show_canvas()

    def test_other_warnings_from_set_mode_are_passed_on(self, mocker):
        def warning_set_mode(size, flags=0):
            warnings.warn('no fast renderer available', UserWarning, stacklevel=2)
            return REAL_SET_MODE(size, flags)

        mocker.patch.object(pygame.display, 'set_mode', side_effect=warning_set_mode)

        with pytest.warns(UserWarning, match='no fast renderer available'):
            surface = set_display_mode(size=REQUESTED_SIZE)

        assert surface.get_size() == REQUESTED_SIZE
        # A new display is black: show the canvas (the test display rule)
        show_canvas()

    def test_the_flags_reach_set_mode(self, mocker):
        set_mode = mocker.spy(pygame.display, 'set_mode')

        set_display_mode(size=REQUESTED_SIZE, flags=pygame.NOFRAME)

        set_mode.assert_called_once_with(REQUESTED_SIZE, pygame.NOFRAME)
        # A new display is black: show the canvas (the test display rule)
        show_canvas()


def test_a_first_window_is_not_waited_for(mocker):
    """With no window before, there is no old size to wait out: the warning passes on."""
    pygame.display.quit()
    pygame.display.init()

    def widening_set_mode(size, flags=0):
        surface = REAL_SET_MODE(WIDENED_SIZE, flags)
        forcibly_resized_warning(requested=tuple(size), got=WIDENED_SIZE)
        return surface

    mocker.patch.object(pygame.display, 'set_mode', side_effect=widening_set_mode)
    pump = mocker.spy(pygame.event, 'pump')

    with pytest.warns(RuntimeWarning, match=FORCIBLY_RESIZED_MESSAGE):
        surface = set_display_mode(size=REQUESTED_SIZE)

    assert surface.get_size() == WIDENED_SIZE
    assert pump.call_count == 0
    # A new display is black: show the canvas (the test display rule)
    show_canvas()
