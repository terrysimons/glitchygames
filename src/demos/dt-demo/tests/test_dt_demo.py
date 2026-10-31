"""Test the Delta Time demo (the dt_demo package): real pygame, the real display.

The demo runs with its ``dt-demo`` console script or ``python -m dt_demo``. Space starts a white
square moving at 300 pixels per second, frame-rate independently; the time it takes to cross the
screen is shown when it leaves.
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, cast

import pygame
import pytest

import dt_demo
from glitchygames.color import WHITE
from glitchygames.events.base import HashableEvent
from glitchygames.fonts import FontManager
from glitchygames.fonts.font_manager import DEFAULT_FONT_NAME
from glitchygames.input.state import InputSnapshot, set_current_input
from tests.demo_runs import engine_run_environment, run_demo_main

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_mock import MockerFixture

# The demo's square: 40 pixels wide, its top 30 pixels below the middle of the screen
SQUARE_SIZE = 40
SQUARE_BELOW_MIDDLE = 30
# Pixels per second the square moves once started
SQUARE_SPEED = 300
# Size of the demo's text (the bundled font)
DEMO_FONT_SIZE = 40
BLACK_RGB = (0, 0, 0)


@pytest.fixture
def engine_run(mocker: MockerFixture) -> Generator[None]:
    """Let the test start a real engine (see demo_runs.engine_run_environment).

    Yields:
        None, while the environment is in place.

    """
    yield from engine_run_environment(mocker)


def _hold_keys(*keys: int) -> None:
    """Make the frame's polled input hold exactly ``keys``."""
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(),
            modifiers=0,
            mouse_position=(0, 0),
            mouse_buttons=(False, False, False),
            mouse_focused=True,
            held_key_codes=frozenset(keys),
        )
    )


def _key_down(key: int) -> HashableEvent:
    """Return a KEYDOWN event for ``key``.

    Returns:
        The event.

    """
    return HashableEvent(pygame.KEYDOWN, key=key, mod=0, unicode='', scancode=0)


def _demo_text(text: str) -> pygame.Surface:
    """Render ``text`` as the demo draws it: the bundled font, size 40, white, antialiased.

    Returns:
        The rendered text.

    """
    font = cast(
        'pygame.font.Font',
        FontManager.pygame_font(
            font_config={'font_name': DEFAULT_FONT_NAME, 'font_size': DEMO_FONT_SIZE}
        ),
    )
    return font.render(text, True, WHITE)  # ruff: ignore[boolean-positional-value-in-call]


def _shows(screen: pygame.Surface, *, image: pygame.Surface, topleft: tuple[int, int]) -> bool:
    """Return whether ``screen`` shows ``image`` on black at ``topleft`` (any pixel format).

    Returns:
        True when every pixel of that region matches.

    """
    expected = pygame.Surface(image.get_size())
    expected.fill(BLACK_RGB)
    expected.blit(image, (0, 0))
    actual = screen.subsurface(pygame.Rect(topleft, image.get_size()))
    return pygame.image.tobytes(expected, 'RGB') == pygame.image.tobytes(actual, 'RGB')


def _square_center_y(scene: dt_demo.Game) -> int:
    """Return the y of the middle of the demo's square.

    Returns:
        The y coordinate.

    """
    return scene.screen_height // 2 + SQUARE_BELOW_MIDDLE + SQUARE_SIZE // 2


def _rgb(screen: pygame.Surface, position: tuple[int, int]) -> tuple[int, int, int]:
    """Return the colour of one screen pixel, without its alpha.

    Returns:
        The red, green and blue values.

    """
    color = screen.get_at(position)
    return (color.r, color.g, color.b)


@pytest.fixture
def scene() -> dt_demo.Game:
    """Return the demo's scene, on the test display.

    Returns:
        The scene.

    """
    return dt_demo.Game(options={})


def test_before_space_the_square_waits_at_the_left_edge(scene: dt_demo.Game) -> None:
    """Time passes but nothing moves until Space: the clock shows 0 and the square is at x 0."""
    scene.dt_tick(0.5)
    scene.update()

    assert scene.screen is not None
    assert _shows(scene.screen, image=_demo_text('Time: 0.0'), topleft=(0, 0))
    assert _rgb(scene.screen, (SQUARE_SIZE // 2, _square_center_y(scene))) == WHITE[:3]
    assert _rgb(scene.screen, (SQUARE_SIZE * 2, _square_center_y(scene))) == BLACK_RGB


def test_space_starts_the_square_moving_frame_rate_independently(scene: dt_demo.Game) -> None:
    """After Space the square moves 300 pixels a second and the clock counts the seconds."""
    _hold_keys(pygame.K_SPACE)
    scene.on_key_down_event(_key_down(pygame.K_SPACE))

    # Two short frames move it as far as one long frame would
    scene.dt_tick(0.25)
    scene.dt_tick(0.25)
    scene.update()

    assert scene.screen is not None
    assert _shows(scene.screen, image=_demo_text('Time: 0.5'), topleft=(0, 0))
    square_left = SQUARE_SPEED // 2
    assert (
        _rgb(scene.screen, (square_left + SQUARE_SIZE // 2, _square_center_y(scene))) == (WHITE[:3])
    )
    assert _rgb(scene.screen, (SQUARE_SIZE // 2, _square_center_y(scene))) == BLACK_RGB


def test_other_keys_do_not_start_it(scene: dt_demo.Game) -> None:
    """A key down while Space is not held leaves the square where it is."""
    _hold_keys(pygame.K_a)
    scene.on_key_down_event(_key_down(pygame.K_a))

    scene.dt_tick(0.5)
    scene.update()

    assert scene.screen is not None
    assert _shows(scene.screen, image=_demo_text('Time: 0.0'), topleft=(0, 0))
    assert _rgb(scene.screen, (SQUARE_SIZE // 2, _square_center_y(scene))) == WHITE[:3]


def test_crossing_the_screen_shows_the_time_it_took(scene: dt_demo.Game) -> None:
    """When the square has left the screen, the time it took is shown, and kept."""
    assert scene.screen is not None
    crossing_seconds = (scene.screen_width + 1) / SQUARE_SPEED
    _hold_keys(pygame.K_SPACE)
    scene.on_key_down_event(_key_down(pygame.K_SPACE))
    scene.dt_tick(crossing_seconds)
    scene.update()

    record_text = _demo_text(f'Time: {round(crossing_seconds, 2)}')
    record_position = (scene.screen_width // 4, scene.screen_height // 2)
    assert _shows(scene.screen, image=record_text, topleft=record_position)

    # Later frames keep the first crossing time, while the clock runs on
    scene.dt_tick(1.0)
    scene.update()

    assert _shows(scene.screen, image=record_text, topleft=record_position)
    assert _shows(
        scene.screen, image=_demo_text(f'Time: {round(crossing_seconds + 1.0, 2)}'), topleft=(0, 0)
    )


def test_the_text_uses_the_bundled_font_never_a_system_font(mocker: MockerFixture) -> None:
    """The demo never asks for a system font (it asked for Calibri: BUGS.md #173 item 3)."""
    system_font = mocker.patch.object(pygame.font, 'SysFont')

    dt_demo.Game(options={})

    system_font.assert_not_called()


def test_the_scene_draws_the_sprite_group_it_is_given() -> None:
    """A sprite group passed in is the scene's group; without one the scene makes its own."""
    group: pygame.sprite.LayeredDirty[pygame.sprite.DirtySprite] = pygame.sprite.LayeredDirty()

    assert dt_demo.Game(options={}, groups=group).all_sprites is group
    assert isinstance(dt_demo.Game(options={}).all_sprites, pygame.sprite.LayeredDirty)


def test_args_add_the_demos_options() -> None:
    """The demo adds -v/--version and -b/--balls (default 1) to the command line."""
    parser = argparse.ArgumentParser()
    dt_demo.Game.args(parser)

    assert parser.parse_args([]) == argparse.Namespace(version=False, balls=1)
    assert parser.parse_args(['--version', '--balls', '3']) == argparse.Namespace(
        version=True, balls=3
    )


@pytest.mark.usefixtures('engine_run')
def test_main_runs_the_demo_until_it_quits(mocker: MockerFixture) -> None:
    """``python -m dt_demo`` (and ``dt-demo``) runs the demo, which draws its first frames."""
    script = run_demo_main(mocker=mocker, module=dt_demo, main=dt_demo.main)

    assert script.scenes_seen
    assert all(isinstance(seen, dt_demo.Game) for seen in script.scenes_seen)
    screen = pygame.display.get_surface()
    assert screen is not None
    assert _shows(screen, image=_demo_text('Time: 0.0'), topleft=(0, 0))
