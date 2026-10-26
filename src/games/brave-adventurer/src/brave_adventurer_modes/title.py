"""The title screen: both Brave Adventurer games, a line each on how they differ; choose one.

The screen draws the desert from the shared primitives (brave_adventurer_core's sky and
pyramids), the title, a card for each game (``GAME_CHOICES``) and a line of help. One card is
chosen at a time.

Controls, all through the scene's ActionMap (as the games read theirs), keyboard by key position:

- Up or Left, Down or Right (a gamepad's D-pad): choose the other game (the two wrap around).
- Space or Return (a gamepad's A or Start): start the chosen game, on the release of a press this
  screen saw, as the pause and game-over screens go on (glitchygames/scenes/builtin_scenes/
  gamepad_choice.py): the game then never gets the release of the key that started it.
- Q (a gamepad's B or Back): quit, on the press. Q quits on its press in the games too, and
  Escape (or B or Back) quits on the pause and game-over screens.
- Escape does nothing here, on its press or its release: the browser build's touch Pause button
  sends Escape, so a phone player who taps it before choosing a game must not end the run.

Starting a game sets ``next_scene`` to a new scene of that game, built with the run's options,
in the same engine: the game runs as it does from its own ``main()``, which builds that scene.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING, Any, Self, override

import pygame

from brave_adventurer.game import BraveAdventurerScene
from brave_adventurer_core.constants import HUD_SHADOW_COLOR, HUD_TEXT_COLOR, SKY_COLOR
from brave_adventurer_core.drawing import draw_pyramids, draw_sky
from brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene
from glitchygames.input import ActionMap
from glitchygames.scenes import Scene
from glitchygames.scenes.builtin_scenes.game_over_scene import TextSprite
from glitchygames.sprites import Sprite

if TYPE_CHECKING:
    import argparse

    from glitchygames.events.base import ControllerButtonEvent, JoyButtonEvent, KeyEvent

log = logging.getLogger('game')

# The title, and the line of help under the cards
TITLE_TEXT = 'BRAVE ADVENTURER'
TITLE_FONT_SIZE = 72
TITLE_CENTER_Y = 70
# Drawn this far down and right of the title, in HUD_SHADOW_COLOR, so it reads over the sky
TITLE_SHADOW_OFFSET = 3
SUBTITLE_TEXT = 'Choose your adventure'
SUBTITLE_FONT_SIZE = 30
SUBTITLE_CENTER_Y = 120
HELP_TEXT = 'Arrows or D-pad: choose    Return, Space or A: start    Q or Back: quit'
HELP_FONT_SIZE = 24
HELP_BOTTOM_MARGIN = 28

# The cards: one per game, stacked, centred
CARD_SIZE = (620, 96)
CARD_TOP_Y = 160
CARD_GAP = 20
CARD_PADDING = 16
CARD_NAME_FONT_SIZE = 40
CARD_DESCRIPTION_FONT_SIZE = 26
CARD_BORDER_RADIUS = 10
# The chosen card: a darker panel with a gold border and a gold name; the other is fainter
CHOSEN_PANEL_COLOR = (20, 16, 8, 190)
CHOSEN_BORDER_COLOR = (240, 200, 80)
CHOSEN_BORDER_WIDTH = 4
CHOSEN_NAME_COLOR = (250, 215, 100)
OTHER_PANEL_COLOR = (20, 16, 8, 110)
OTHER_BORDER_COLOR = (200, 190, 160)
OTHER_BORDER_WIDTH = 1
OTHER_NAME_COLOR = HUD_TEXT_COLOR
DESCRIPTION_COLOR = (235, 228, 210)

# The scene's actions (its ActionMap)
PREVIOUS_ACTION = 'previous'
NEXT_ACTION = 'next'
CHOOSE_ACTION = 'choose'
QUIT_ACTION = 'quit'


@dataclasses.dataclass(frozen=True)
class GameChoice:
    """One game the title screen offers.

    Attributes:
        name: The game's name on the command line (``--game``) and in the launcher's tables.
        title: The name on its card.
        description: The line on its card: how this game differs from the other.
        scene_class: The game's scene, which its own ``main()`` starts.

    """

    name: str
    title: str
    description: str
    scene_class: type[Scene]


# The games, in the order the title screen shows them (the first is chosen at the start)
GAME_CHOICES: tuple[GameChoice, ...] = (
    GameChoice(
        name='classic',
        title='Classic',
        description='Every sprite drawn in code, from pygame primitives',
        scene_class=BraveAdventurerScene,
    ),
    GameChoice(
        name='papyrus',
        title='Papyrus',
        description='The Egyptian edition, with hand-drawn sprite-sheet art',
        scene_class=PapyrusBraveAdventurerScene,
    ),
)


def add_game_argument(parser: argparse.ArgumentParser) -> None:
    """Add ``--game classic|papyrus``: the launcher reads it (the title screen's help lists it).

    Args:
        parser: The parser, or an argument group of one.

    """
    parser.add_argument(
        '--game',
        choices=[choice.name for choice in GAME_CHOICES],
        default=None,
        help='start this game at once, without the title screen',
    )


class TitleBackdrop(Sprite):
    """The desert behind the title: the games' sky and pyramids, drawn once."""

    def __init__(
        self: Self, *, size: tuple[int, int], groups: pygame.sprite.LayeredDirty[Any]
    ) -> None:
        """Draw the backdrop.

        Args:
            size: The screen's (width, height).
            groups: The scene's sprites.

        """
        width, height = size
        super().__init__(x=0, y=0, width=width, height=height, groups=groups)
        # The games' own background layers, as they look with the camera at the level's start
        draw_sky(self.image, 0.0, 0.0)
        draw_pyramids(self.image, 0.0, 0.0)
        self.dirty = 1


class GameChoiceCard(Sprite):
    """A game's card: its name and how it differs, framed in gold while it is the chosen one."""

    def __init__(
        self: Self,
        *,
        choice: GameChoice,
        center: tuple[int, int],
        selected: bool,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Draw the card.

        Args:
            choice: The game.
            center: Where its centre goes on the screen.
            selected: Whether it is the chosen card.
            groups: The scene's sprites.

        """
        width, height = CARD_SIZE
        super().__init__(
            x=center[0] - width // 2,
            y=center[1] - height // 2,
            width=width,
            height=height,
            groups=groups,
        )
        self.choice = choice
        self.selected = selected
        self._name_font = pygame.font.Font(None, CARD_NAME_FONT_SIZE)
        self._description_font = pygame.font.Font(None, CARD_DESCRIPTION_FONT_SIZE)
        self._draw()

    def select(self: Self, *, selected: bool) -> None:
        """Draw the card chosen or not.

        Args:
            selected: Whether it is the chosen card.

        """
        self.selected = selected
        self._draw()

    def _draw(self: Self) -> None:
        """Draw the panel, its border, the game's name and its line; mark the card for redrawing."""
        image = pygame.Surface(CARD_SIZE, pygame.SRCALPHA)
        panel_color, border_color, border_width, name_color = (
            (CHOSEN_PANEL_COLOR, CHOSEN_BORDER_COLOR, CHOSEN_BORDER_WIDTH, CHOSEN_NAME_COLOR)
            if self.selected
            else (OTHER_PANEL_COLOR, OTHER_BORDER_COLOR, OTHER_BORDER_WIDTH, OTHER_NAME_COLOR)
        )
        card_rect = image.get_rect()
        pygame.draw.rect(image, panel_color, card_rect, border_radius=CARD_BORDER_RADIUS)
        pygame.draw.rect(
            image, border_color, card_rect, width=border_width, border_radius=CARD_BORDER_RADIUS
        )
        name = self._name_font.render(self.choice.title, True, name_color)  # ruff: ignore[boolean-positional-value-in-call] - pygame's antialias argument
        description = self._description_font.render(
            self.choice.description,
            True,  # ruff: ignore[boolean-positional-value-in-call] - pygame's antialias argument
            DESCRIPTION_COLOR,
        )
        image.blit(name, (CARD_PADDING, CARD_PADDING))
        image.blit(
            description, (CARD_PADDING, CARD_SIZE[1] - CARD_PADDING - description.get_height())
        )
        self.image = image
        self.dirty = 1


class TitleScene(Scene):
    """The launcher's title screen: choose Classic or Papyrus.

    Attributes:
        NAME: The command's name in its help and ``--version`` (the Classic game's name, which
            the command printed before it became the launcher).
        VERSION: Its version.

    """

    NAME = 'Brave Adventurer'
    VERSION = '1.0'

    def __init__(
        self: Self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Build the screen: the backdrop, the title, a card per game and the help line.

        Args:
            options: Command-line options dict from GameEngine.
            groups: Sprite group (created if not provided).

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        super().__init__(options=options, groups=groups)
        # Named, so no part of the screen the backdrop leaves shows the test pattern
        self.background_color = SKY_COLOR
        self.actions = self._create_action_map(input_mode=self.options.get('input_mode', 'auto'))
        # The chosen game (an index into GAME_CHOICES)
        self.selected_index = 0
        # A choose control's press reached this screen, so its release starts the game
        self._choose_pressed = False

        # Drawn in this order, each over the one before (LayeredDirty keeps the order it was given)
        center_x = self.screen_width // 2
        TitleBackdrop(size=(self.screen_width, self.screen_height), groups=self.all_sprites)
        for color, offset in ((HUD_SHADOW_COLOR, TITLE_SHADOW_OFFSET), (CHOSEN_NAME_COLOR, 0)):
            self.all_sprites.add(
                TextSprite(
                    TITLE_TEXT,
                    (center_x + offset, TITLE_CENTER_Y + offset),
                    color=color,
                    font_size=TITLE_FONT_SIZE,
                )
            )
        self.all_sprites.add(
            TextSprite(
                SUBTITLE_TEXT,
                (center_x, SUBTITLE_CENTER_Y),
                color=HUD_TEXT_COLOR,
                font_size=SUBTITLE_FONT_SIZE,
            )
        )
        card_height = CARD_SIZE[1]
        self.cards = [
            GameChoiceCard(
                choice=choice,
                center=(center_x, CARD_TOP_Y + index * (card_height + CARD_GAP) + card_height // 2),
                selected=index == self.selected_index,
                groups=self.all_sprites,
            )
            for index, choice in enumerate(GAME_CHOICES)
        ]
        self.all_sprites.add(
            TextSprite(
                HELP_TEXT,
                (center_x, self.screen_height - HELP_BOTTOM_MARGIN),
                color=HUD_TEXT_COLOR,
                font_size=HELP_FONT_SIZE,
            )
        )

    @staticmethod
    def _create_action_map(*, input_mode: str) -> ActionMap:
        """Bind the controls: keys by position, and a gamepad's D-pad, A, Start, B and Back.

        Args:
            input_mode: Gamepad event family ('joystick', 'controller' or 'auto').

        Returns:
            The action map.

        """
        actions = ActionMap(input_mode=input_mode)
        for action, scancodes, buttons in (
            (
                PREVIOUS_ACTION,
                (pygame.KSCAN_UP, pygame.KSCAN_LEFT),
                (pygame.CONTROLLER_BUTTON_DPAD_UP, pygame.CONTROLLER_BUTTON_DPAD_LEFT),
            ),
            (
                NEXT_ACTION,
                (pygame.KSCAN_DOWN, pygame.KSCAN_RIGHT),
                (pygame.CONTROLLER_BUTTON_DPAD_DOWN, pygame.CONTROLLER_BUTTON_DPAD_RIGHT),
            ),
            (
                CHOOSE_ACTION,
                (pygame.KSCAN_SPACE, pygame.KSCAN_RETURN),
                (pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_START),
            ),
            (
                QUIT_ACTION,
                (pygame.KSCAN_Q,),
                (pygame.CONTROLLER_BUTTON_B, pygame.CONTROLLER_BUTTON_BACK),
            ),
        ):
            for scancode in scancodes:
                actions.bind(action, scancode=scancode)
            for button in buttons:
                actions.bind(action, controller_button=button)
        return actions

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> None:
        """Add the command's arguments: ``--game`` (read by the launcher first) and the version.

        Args:
            parser: The argument parser to add arguments to.

        """
        add_game_argument(parser)
        # argparse prints the version and exits as it parses (before the title screen starts)
        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'{cls.NAME} {cls.VERSION}',
            help='print the game version and exit',
        )

    def start_chosen_game(self: Self) -> None:
        """Switch to a new scene of the chosen game, with the run's options, after this frame."""
        choice = GAME_CHOICES[self.selected_index]
        log.info('Starting %s from the title screen', choice.title)
        self.next_scene = choice.scene_class(options=self.options)

    def _select(self: Self, *, step: int) -> None:
        """Choose the game ``step`` cards on (wrapping round), and redraw both cards.

        Args:
            step: -1 for the previous game, 1 for the next.

        """
        self.selected_index = (self.selected_index + step) % len(GAME_CHOICES)
        for index, card in enumerate(self.cards):
            card.select(selected=index == self.selected_index)

    def _on_action_pressed(self: Self, action: str) -> None:
        """Act on a control's press: move the choice, arm starting the game, or quit.

        Args:
            action: The control's action.

        """
        if action == PREVIOUS_ACTION:
            self._select(step=-1)
        elif action == NEXT_ACTION:
            self._select(step=1)
        elif action == CHOOSE_ACTION:
            self._choose_pressed = True
        else:
            # QUIT_ACTION. A QUIT event ends the run, as the games' Q does
            self.scene_manager.quit()

    def _on_action_released(self: Self, action: str | None) -> None:
        """Start the chosen game on the release of a choose control pressed on this screen.

        Args:
            action: The released control's action, or None for an unbound one.

        """
        if action == CHOOSE_ACTION and self._choose_pressed:
            self._choose_pressed = False
            self.start_chosen_game()

    @override
    def on_key_down_event(self: Self, event: KeyEvent) -> None:
        """Act on a bound key's press; pass any other to the base scene (the debug keys).

        Args:
            event: The key down event.

        """
        self.actions.handle_event(event)
        action = self.actions.get_action(event)
        if action is None:
            super().on_key_down_event(event)
        else:
            self._on_action_pressed(action)

    @override
    def on_key_up_event(self: Self, event: KeyEvent) -> None:
        """Act on a key's release (Q quits on its press: not again here; Escape does nothing).

        Args:
            event: The key up event.

        """
        self.actions.handle_event(event)
        self._on_action_released(self.actions.get_action(event))

    @override
    def on_controller_button_down_event(self: Self, event: ControllerButtonEvent) -> None:
        """Act on a mapped gamepad's button press.

        Args:
            event: The controller button down event.

        """
        self._on_button_down(event)

    @override
    def on_controller_button_up_event(self: Self, event: ControllerButtonEvent) -> None:
        """Act on a mapped gamepad's button release.

        Args:
            event: The controller button up event.

        """
        self._on_button_up(event)

    @override
    def on_joy_button_down_event(self: Self, event: JoyButtonEvent) -> None:
        """Act on any other gamepad's button press.

        Args:
            event: The joystick button down event.

        """
        self._on_button_down(event)

    @override
    def on_joy_button_up_event(self: Self, event: JoyButtonEvent) -> None:
        """Act on any other gamepad's button release.

        Args:
            event: The joystick button up event.

        """
        self._on_button_up(event)

    def _on_button_down(self: Self, event: ControllerButtonEvent | JoyButtonEvent) -> None:
        """Act on a gamepad button's press, from either event layer.

        Args:
            event: The button down event.

        """
        self.actions.handle_event(event)
        action = self.actions.get_action(event)
        if action is not None:
            self._on_action_pressed(action)

    def _on_button_up(self: Self, event: ControllerButtonEvent | JoyButtonEvent) -> None:
        """Act on a gamepad button's release, from either event layer.

        Args:
            event: The button up event.

        """
        self.actions.handle_event(event)
        self._on_action_released(self.actions.get_action(event))
