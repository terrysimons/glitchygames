"""The shared pause-style message screen (glitchygames/ui/message_screen.py).

Kept out of tests/scenes: tests there run with pygame's drawing mocked (tests/conftest.py), and
these compare real pixels.
"""

from __future__ import annotations

import types

import pygame
import pytest

from glitchygames.color import WHITE
from glitchygames.scenes.builtin_scenes.pause_scene import PauseOverlay
from glitchygames.ui.message_screen import MessageScreen

SCREEN_SIZE = (320, 240)


@pytest.fixture
def screenshot() -> pygame.Surface:
    """A game picture with some detail for the dimming to change.

    Returns:
        The surface.

    """
    pygame.init()
    surface = pygame.Surface(SCREEN_SIZE)
    surface.fill((40, 120, 200))
    pygame.draw.rect(surface, (250, 200, 10), pygame.Rect(20, 30, 100, 60))
    return surface


def pause_screen_as_before(*, screenshot: pygame.Surface, screen_size: tuple[int, int]) -> bytes:
    """Draw the pause screen with the code PauseOverlay had before MessageScreen existed.

    Returns:
        The picture's pixels.

    """
    overlay = pygame.Surface(screen_size)
    overlay.fill((0, 0, 0))
    overlay.set_alpha(128)
    font = pygame.font.Font(None, 72)
    text_surface = font.render('PAUSED', antialias=True, color=WHITE)
    text_rect = text_surface.get_rect()
    text_rect.center = (screen_size[0] // 2, screen_size[1] // 2)
    image = screenshot.copy()
    image.blit(overlay, (0, 0))
    image.blit(text_surface, text_rect)
    return pygame.image.tobytes(image, 'RGB')


def test_the_pause_screen_renders_as_before(screenshot):
    """PauseOverlay's picture is pixel for pixel what it drew before the shared screen."""
    game = types.SimpleNamespace(screen_width=SCREEN_SIZE[0], screen_height=SCREEN_SIZE[1])
    overlay = PauseOverlay(game, screenshot)
    assert pygame.image.tobytes(overlay.image, 'RGB') == pause_screen_as_before(
        screenshot=screenshot, screen_size=SCREEN_SIZE
    )
    assert overlay.rect == pygame.Rect((0, 0), SCREEN_SIZE)


def test_a_screenshot_smaller_than_the_screen_still_centres_on_the_screen(screenshot):
    """A custom screenshot need not be the screen's size; the layout follows the screen."""
    small_screenshot = screenshot.subsurface(pygame.Rect(0, 0, 200, 150)).copy()
    game = types.SimpleNamespace(screen_width=SCREEN_SIZE[0], screen_height=SCREEN_SIZE[1])
    overlay = PauseOverlay(game, small_screenshot)
    assert pygame.image.tobytes(overlay.image, 'RGB') == pause_screen_as_before(
        screenshot=small_screenshot, screen_size=SCREEN_SIZE
    )


def test_the_message_is_centred_and_the_pause_screen_has_no_hint(screenshot):
    """The message's rect is centred on the area; without hint_text there is no hint line."""
    message_rect, hint_rect = MessageScreen().text_rects(size=SCREEN_SIZE)
    assert message_rect.center == (SCREEN_SIZE[0] // 2, SCREEN_SIZE[1] // 2)
    assert hint_rect is None


def test_render_leaves_the_backdrop_alone(screenshot):
    """render() draws on a copy."""
    before = pygame.image.tobytes(screenshot, 'RGB')
    MessageScreen().render(backdrop=screenshot)
    assert pygame.image.tobytes(screenshot, 'RGB') == before
