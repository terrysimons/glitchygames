"""Test the Text Input demo (glitchygames/examples/text_input_demo.py): real pygame and display.

The demo has no console script; it runs with ``python -m glitchygames.examples.text_input_demo``.
It shows one InputBox on a yellow background: a click or Tab gives it the keyboard, typing
edits its text, Return submits it (logged), Tab or Escape (released) gives the keyboard back.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import pygame
import pytest

from glitchygames.events.base import HashableEvent
from glitchygames.examples import text_input_demo
from glitchygames.fonts import FontManager
from glitchygames.fonts.font_manager import DEFAULT_FONT_NAME
from tests.examples.demo_runs import engine_run_environment, run_demo_main

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_mock import MockerFixture

# Where the demo puts its input box, and its size
BOX_TOPLEFT = (320, 240)
BOX_SIZE = (200, 20)
# The box's border colour (InputBox's default colour), and the yellow background
BOX_BORDER_RGB = (233, 248, 215)
YELLOW_RGB = (255, 255, 0)
BLACK_RGB = (0, 0, 0)
WHITE_RGB = (255, 255, 255)
# The demo's starting text
STARTING_TEXT = 'Test'
# InputBox's text: the bundled font at 14 points, 4 pixels in from the box's corner
BOX_FONT_SIZE = 14
TEXT_INSET = (4, 4)
# A display the demo's box at (320, 240) fits on (the tests' default 800x600 would too; the
# demo runs set their own size)
DEMO_DISPLAY_SIZE = (640, 480)


@pytest.fixture
def engine_run(mocker: MockerFixture) -> Generator[None]:
    """Let the test start a real engine (see demo_runs.engine_run_environment).

    Yields:
        None, while the environment is in place.

    """
    yield from engine_run_environment(mocker)


@pytest.fixture(autouse=True)
def key_repeat_restored() -> Generator[None]:
    """Put pygame's key repeat back after the test (the demo and its InputBox set it).

    Yields:
        None, while the test runs.

    """
    delay, interval = pygame.key.get_repeat()
    yield
    pygame.key.set_repeat(delay, interval)


@pytest.fixture(autouse=True)
def event_queue_emptied() -> Generator[None]:
    """Start and end the test with an empty event queue (a QUIT left behind ends a later run).

    Yields:
        None, while the test runs.

    """
    pygame.event.clear()
    yield
    pygame.event.clear()


@pytest.fixture(autouse=True)
def cursor_hidden(mocker: MockerFixture) -> None:
    """Hold the frame clock in the first half of a second, when the box's cursor is hidden.

    The cursor blinks with the frame clock (shown in the second half of each second), which a
    run advances by the measured frame times; the pictures compared here have no cursor.
    """
    mocker.patch('glitchygames.ui.inputs.frame_clock_seconds', return_value=0.0)


@pytest.fixture
def scene() -> text_input_demo.Game:
    """Return the demo's scene, set up, on a display its box fits on.

    Returns:
        The scene.

    """
    pygame.display.set_mode(DEMO_DISPLAY_SIZE)
    game = text_input_demo.Game(options={})
    game.setup()
    return game


def _key(event_type: int, key: int, *, unicode: str = '') -> HashableEvent:
    """Return a key event.

    Returns:
        The event.

    """
    return HashableEvent(event_type, key=key, mod=0, unicode=unicode, scancode=0)


def _expected_box(*, text: str, text_rgb: tuple[int, int, int]) -> pygame.Surface:
    """Draw the box as InputBox draws it with ``text`` (no cursor): black, text, border.

    Returns:
        The box's picture.

    """
    font = cast(
        'pygame.font.Font',
        FontManager.pygame_font(
            font_config={'font_name': DEFAULT_FONT_NAME, 'font_size': BOX_FONT_SIZE}
        ),
    )
    box = pygame.Surface(BOX_SIZE)
    box.fill(BLACK_RGB)
    box.blit(font.render(text, True, text_rgb), TEXT_INSET)  # ruff: ignore[boolean-positional-value-in-call]
    pygame.draw.rect(box, BOX_BORDER_RGB, (0, 0, *BOX_SIZE), 1)
    return box


def _shows_box(screen: pygame.Surface, *, text: str, text_rgb: tuple[int, int, int]) -> bool:
    """Return whether the screen shows the box holding ``text`` (any pixel format).

    Returns:
        True when every pixel of the box matches.

    """
    expected = _expected_box(text=text, text_rgb=text_rgb)
    actual = screen.subsurface(pygame.Rect(BOX_TOPLEFT, BOX_SIZE))
    return pygame.image.tobytes(expected, 'RGB') == pygame.image.tobytes(actual, 'RGB')


def _draw_frame(scene: text_input_demo.Game) -> pygame.Surface:
    """Draw one frame as the scene manager does: update, then render.

    Returns:
        The screen.

    """
    assert scene.screen is not None
    scene.update()
    scene.render(scene.screen)
    return scene.screen


def _rgb(screen: pygame.Surface, position: tuple[int, int]) -> tuple[int, int, int]:
    """Return the colour of one screen pixel, without its alpha.

    Returns:
        The red, green and blue values.

    """
    color = screen.get_at(position)
    return (color.r, color.g, color.b)


def _type(scene: text_input_demo.Game, text: str) -> None:
    """Type ``text`` (key downs carrying each character)."""
    for character in text:
        scene.on_key_down_event(_key(pygame.KEYDOWN, ord(character), unicode=character))


def test_first_frame_shows_the_box_with_its_text_on_yellow(scene: text_input_demo.Game) -> None:
    """The box shows 'Test' in its own colour; the rest of the screen is yellow."""
    screen = _draw_frame(scene)

    assert _shows_box(screen, text=STARTING_TEXT, text_rgb=BOX_BORDER_RGB)
    assert _rgb(screen, (10, 10)) == YELLOW_RGB
    assert scene.input_box.is_active is False


def test_setup_sets_the_key_repeat_delay(scene: text_input_demo.Game) -> None:
    """Held keys repeat after 350 ms."""
    assert pygame.key.get_repeat()[0] == 350


def test_typing_before_a_click_changes_nothing(scene: text_input_demo.Game) -> None:
    """Without the keyboard, key downs leave the text alone."""
    _type(scene, 'ab')

    assert _shows_box(_draw_frame(scene), text=STARTING_TEXT, text_rgb=BOX_BORDER_RGB)


def test_a_click_gives_the_box_the_keyboard(scene: text_input_demo.Game) -> None:
    """After a click, typed characters appear in the box (redrawn in white)."""
    scene.on_mouse_button_up_event(HashableEvent(pygame.MOUSEBUTTONUP, pos=(0, 0), button=1))
    _type(scene, 'ab')

    assert _shows_box(_draw_frame(scene), text=f'{STARTING_TEXT}ab', text_rgb=WHITE_RGB)


def test_tab_gives_the_box_the_keyboard_and_takes_it_back(scene: text_input_demo.Game) -> None:
    """Releasing Tab gives the box the keyboard; releasing it again takes it back."""
    scene.on_key_up_event(_key(pygame.KEYUP, pygame.K_TAB))
    _type(scene, 'a')
    scene.on_key_up_event(_key(pygame.KEYUP, pygame.K_TAB))
    _type(scene, 'b')

    assert _shows_box(_draw_frame(scene), text=f'{STARTING_TEXT}a', text_rgb=WHITE_RGB)


def test_releasing_escape_in_the_box_takes_the_keyboard_back_without_quitting(
    scene: text_input_demo.Game,
) -> None:
    """Escape while typing leaves the box, and does not quit the demo."""
    scene.on_key_up_event(_key(pygame.KEYUP, pygame.K_TAB))
    scene.record_key_press(key=pygame.K_ESCAPE)
    scene.on_key_down_event(_key(pygame.KEYDOWN, pygame.K_ESCAPE))
    scene.on_key_up_event(_key(pygame.KEYUP, pygame.K_ESCAPE))

    assert scene.input_box.is_active is False
    assert not pygame.event.peek(pygame.QUIT)


def test_escape_outside_the_box_quits_on_its_release_not_its_press(
    scene: text_input_demo.Game,
) -> None:
    """Escape quits when released; its press alone does not (it was routed as a release)."""
    # The scene manager notes each press it routes to the scene before the scene handles it
    scene.record_key_press(key=pygame.K_ESCAPE)
    scene.on_key_down_event(_key(pygame.KEYDOWN, pygame.K_ESCAPE))

    assert not pygame.event.peek(pygame.QUIT)

    scene.on_key_up_event(_key(pygame.KEYUP, pygame.K_ESCAPE))

    assert pygame.event.peek(pygame.QUIT)


def test_return_submits_the_text(
    scene: text_input_demo.Game, caplog: pytest.LogCaptureFixture
) -> None:
    """Return logs the box's text as submitted and leaves the text as it is."""
    scene.on_key_up_event(_key(pygame.KEYUP, pygame.K_TAB))
    _type(scene, 'ok')

    with caplog.at_level(logging.INFO, logger='game'):
        scene.on_key_down_event(_key(pygame.KEYDOWN, pygame.K_RETURN, unicode='\r'))

    submitted = [record.getMessage() for record in caplog.records if 'Got text input' in record.msg]
    assert submitted == [
        f'{scene.name} Got text input from: {scene.input_box.name}: {STARTING_TEXT}ok'
    ]
    assert _shows_box(_draw_frame(scene), text=f'{STARTING_TEXT}ok', text_rgb=WHITE_RGB)


def test_the_box_joins_the_sprite_group_it_is_given() -> None:
    """A sprite group passed in holds the box; without one the scene makes its own."""
    pygame.display.set_mode(DEMO_DISPLAY_SIZE)
    group: pygame.sprite.LayeredDirty[pygame.sprite.DirtySprite] = pygame.sprite.LayeredDirty()

    game = text_input_demo.Game(options={}, groups=group)

    assert game.input_box in group
    assert game.all_sprites is not group
    default_game = text_input_demo.Game(options={})
    assert any(
        isinstance(sprite_group, pygame.sprite.LayeredDirty) and sprite_group is not group
        for sprite_group in default_game.input_box.groups()
        if sprite_group is not default_game.all_sprites
    )


@pytest.mark.usefixtures('engine_run')
def test_main_runs_the_demo_and_types_into_the_box(mocker: MockerFixture) -> None:
    """``python -m glitchygames.examples.text_input_demo``: a click and typing show in the box."""
    script = run_demo_main(
        mocker=mocker,
        module=text_input_demo,
        main=text_input_demo.main,
        resolution='x'.join(str(length) for length in DEMO_DISPLAY_SIZE),
        events_by_frame={
            0: [
                pygame.event.Event(
                    pygame.MOUSEBUTTONUP, pos=(330, 245), button=1, touch=False, window=None
                )
            ],
            1: [
                pygame.event.Event(
                    pygame.KEYDOWN, key=pygame.K_x, mod=0, unicode='x', scancode=0, window=None
                )
            ],
        },
    )

    assert all(isinstance(seen, text_input_demo.Game) for seen in script.scenes_seen)
    screen = pygame.display.get_surface()
    assert screen is not None
    assert _shows_box(screen, text=f'{STARTING_TEXT}x', text_rgb=WHITE_RGB)
