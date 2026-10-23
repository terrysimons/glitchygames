"""Mr. Muncher: a Pac-Man style maze game whose dots are film strip sprockets.

You are the yellow disc. Steer it through a blue-walled maze with the arrow keys (or the
D-pad) and collect the grey-brown sprockets, 10 points each. Three red munchers wander the maze
at random; touching one sends you back to the start with your score at 0 and every sprocket
back in place. Collect them all and the game says you win (it keeps running: ESC or Q quits).

The maze, the sprockets and the munchers' wandering are random, drawn from the engine's seeded
streams (``glitchygames/randomness.py``), so ``--random-seed`` fixes them and a replay is
exact. Movement is frame-rate independent (pixels per second); the speeds are the original
toy's per-frame speeds at 60 frames per second.
"""

from __future__ import annotations

import enum
import math
from typing import TYPE_CHECKING, Any, Self, override

import pygame

from glitchygames.color import BLACK
from glitchygames.engine import GameEngine
from glitchygames.examples.mr_muncher.maze import GRID_SIZE, Maze, build_maze, sprocket_centres
from glitchygames.input import ActionMap
from glitchygames.randomness import random_stream
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite

if TYPE_CHECKING:
    from glitchygames.events.base import ControllerButtonEvent, JoyButtonEvent, KeyEvent

# Colours
PLAYER_COLOR = (255, 255, 0)
MUNCHER_COLOR = (255, 0, 0)
WALL_COLOR = (0, 0, 255)
SPROCKET_COLOR = (60, 50, 40)  # Grey-brown, like the sprocket holes of a film strip
TEXT_COLOR = (255, 255, 0)

# Engine random streams (glitchygames/randomness.py): the maze and its sprockets draw from one,
# the munchers' wandering from another, so the munchers never change the next maze
MAZE_RANDOM_STREAM = 'mr_muncher.maze'
MUNCHER_RANDOM_STREAM = 'mr_muncher.munchers'

# The original toy moved its discs a fixed distance per frame at 60 frames per second
ORIGINAL_FRAME_SECONDS = 1.0 / 60.0
PLAYER_SPEED_PIXELS_PER_SECOND = 0.2 / ORIGINAL_FRAME_SECONDS
MUNCHER_SPEED_PIXELS_PER_SECOND = 0.1 / ORIGINAL_FRAME_SECONDS
# A muncher turns a random way with this chance every ORIGINAL_FRAME_SECONDS
MUNCHER_TURN_CHANCE_PER_ORIGINAL_FRAME = 0.02

# The player and the munchers are discs of this radius
DISC_RADIUS = 8
# The player collects a sprocket whose centre is closer than this
SPROCKET_COLLECT_DISTANCE = 15
# A muncher catches the player when their centres are closer than this
MUNCHER_CATCH_DISTANCE = 16
# A sprocket is a rounded square of this side, centred on its cell
SPROCKET_SIDE = 6
SPROCKET_CORNER_RADIUS = 3
SPROCKET_POINTS = 10

# Text: pygame's default font at this size, the score in the top left corner, the win message
# starting WIN_TEXT_LEFT_OF_CENTRE pixels left of the screen's centre, its top at the middle
TEXT_FONT_SIZE = 36
SCORE_TEXT_POSITION = (10, 10)
WIN_TEXT_LEFT_OF_CENTRE = 150
WIN_MESSAGE = 'YOU WIN! Press ESC to quit'


class Direction(enum.Enum):
    """A direction of travel, as its (x, y) unit step."""

    RIGHT = (1, 0)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    UP = (0, -1)


# The action held for each direction; when several are held, the first in this order wins
DIRECTION_ACTIONS: tuple[tuple[str, Direction], ...] = (
    ('move_right', Direction.RIGHT),
    ('move_down', Direction.DOWN),
    ('move_left', Direction.LEFT),
    ('move_up', Direction.UP),
)


def _centre_distance(*, first: Disc, second_x: float, second_y: float) -> float:
    """Return the distance from a disc's centre to a point.

    Args:
        first: The disc.
        second_x: The point's x, in pixels.
        second_y: The point's y, in pixels.

    Returns:
        The distance in pixels.

    """
    return math.hypot(first.centre_x - second_x, first.centre_y - second_y)


class Disc(Sprite):
    """A filled disc that moves through the maze: the player or a muncher.

    Its centre is kept in float pixels; it is drawn with that centre truncated to whole pixels.
    Only the centre is checked against the walls, so a disc may overlap a wall by up to its
    radius (as in the original toy).
    """

    def __init__(
        self: Self,
        *,
        centre_x: float,
        centre_y: float,
        color: tuple[int, int, int],
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Draw the disc and place it.

        Args:
            centre_x: The centre's x, in pixels.
            centre_y: The centre's y, in pixels.
            color: The disc's colour.
            groups: The sprite group to add the disc to.

        """
        diameter = DISC_RADIUS * 2
        super().__init__(
            x=0, y=0, width=diameter, height=diameter, name=type(self).__name__, groups=groups
        )
        self.image = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        pygame.draw.circle(self.image, color, (DISC_RADIUS, DISC_RADIUS), DISC_RADIUS)
        self.centre_x = centre_x
        self.centre_y = centre_y
        self.dirty = 2
        self.place()

    def place(self: Self) -> None:
        """Put the drawn disc at its centre (truncated to whole pixels)."""
        self.rect.topleft = (int(self.centre_x) - DISC_RADIUS, int(self.centre_y) - DISC_RADIUS)

    def try_move(self: Self, *, direction: Direction, distance: float, maze: Maze) -> bool:
        """Move the centre unless that would put it in a wall cell.

        Args:
            direction: Which way to move.
            distance: How far, in pixels.
            maze: The maze whose walls block the move.

        Returns:
            True if the disc moved, False if a wall blocked it.

        """
        step_x, step_y = direction.value
        new_x = self.centre_x + step_x * distance
        new_y = self.centre_y + step_y * distance
        if maze.is_wall_at(x=new_x, y=new_y):
            return False
        self.centre_x = new_x
        self.centre_y = new_y
        self.place()
        return True


class Player(Disc):
    """The yellow disc the player steers."""

    def __init__(
        self: Self, *, centre_x: float, centre_y: float, groups: pygame.sprite.LayeredDirty[Any]
    ) -> None:
        """Create the player at its start.

        Args:
            centre_x: The start's x, in pixels.
            centre_y: The start's y, in pixels.
            groups: The sprite group to add the player to.

        """
        super().__init__(centre_x=centre_x, centre_y=centre_y, color=PLAYER_COLOR, groups=groups)
        self.start_x = centre_x
        self.start_y = centre_y

    def return_to_start(self: Self) -> None:
        """Put the player back at its start."""
        self.centre_x = self.start_x
        self.centre_y = self.start_y
        self.place()


class MrMuncher(Disc):
    """A red muncher wandering the maze at random.

    It keeps going one way, turns a random way now and then, and turns a random way whenever a
    wall blocks it (possibly the same way, which it then tries again next frame).
    """

    def __init__(
        self: Self, *, centre_x: float, centre_y: float, groups: pygame.sprite.LayeredDirty[Any]
    ) -> None:
        """Create a muncher heading right.

        Args:
            centre_x: The centre's x, in pixels.
            centre_y: The centre's y, in pixels.
            groups: The sprite group to add the muncher to.

        """
        super().__init__(centre_x=centre_x, centre_y=centre_y, color=MUNCHER_COLOR, groups=groups)
        self.direction = Direction.RIGHT

    def wander(self: Self, *, dt: float, maze: Maze) -> None:
        """Maybe turn a random way, then move on, turning a random way if a wall blocks it.

        The chance of a turn is MUNCHER_TURN_CHANCE_PER_ORIGINAL_FRAME for every
        ORIGINAL_FRAME_SECONDS of ``dt``, whatever the frame rate.

        Args:
            dt: The frame's seconds.
            maze: The maze whose walls block the muncher.

        """
        turn_chance = 1.0 - (1.0 - MUNCHER_TURN_CHANCE_PER_ORIGINAL_FRAME) ** (
            dt / ORIGINAL_FRAME_SECONDS
        )
        if random_stream(MUNCHER_RANDOM_STREAM).random() < turn_chance:
            self.direction = self._random_direction()
        if not self.try_move(
            direction=self.direction, distance=MUNCHER_SPEED_PIXELS_PER_SECOND * dt, maze=maze
        ):
            self.direction = self._random_direction()

    @staticmethod
    def _random_direction() -> Direction:
        """Return a direction drawn from the munchers' random stream.

        Returns:
            The direction.

        """
        return random_stream(MUNCHER_RANDOM_STREAM).choice(list(Direction))


class Sprocket(Sprite):
    """A sprocket (the game's dot): a small rounded square, hidden once collected."""

    def __init__(
        self: Self, *, centre_x: int, centre_y: int, groups: pygame.sprite.LayeredDirty[Any]
    ) -> None:
        """Draw the sprocket centred on a point.

        Args:
            centre_x: The centre's x, in pixels.
            centre_y: The centre's y, in pixels.
            groups: The sprite group to add the sprocket to.

        """
        half_side = SPROCKET_SIDE // 2
        super().__init__(
            x=centre_x - half_side,
            y=centre_y - half_side,
            width=SPROCKET_SIDE,
            height=SPROCKET_SIDE,
            name='Sprocket',
            groups=groups,
        )
        self.image = pygame.Surface((SPROCKET_SIDE, SPROCKET_SIDE), pygame.SRCALPHA)
        pygame.draw.rect(
            self.image,
            SPROCKET_COLOR,
            self.image.get_rect(),
            border_radius=SPROCKET_CORNER_RADIUS,
        )
        self.centre_x = centre_x
        self.centre_y = centre_y
        self.dirty = 2

    @property
    def collected(self: Self) -> bool:
        """Whether the player has collected this sprocket (it is then not drawn)."""
        return not self.visible

    @collected.setter
    def collected(self: Self, is_collected: bool) -> None:
        """Collect the sprocket (hide it), or put it back.

        Args:
            is_collected: True to collect it, False to put it back.

        """
        self.visible = 0 if is_collected else 1


class TextLine(Sprite):
    """One line of yellow text in pygame's default font."""

    def __init__(
        self: Self,
        *,
        text: str,
        topleft: tuple[int, int],
        font: pygame.font.Font,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Render the text at a position.

        Args:
            text: The text.
            topleft: Where the text's top left corner goes.
            font: The font to render it in.
            groups: The sprite group to add the text to.

        """
        super().__init__(
            x=topleft[0], y=topleft[1], width=1, height=1, name='TextLine', groups=groups
        )
        self.font = font
        self.text = ''
        self.dirty = 2
        self.show(text=text)

    def show(self: Self, *, text: str) -> None:
        """Render new text in place (nothing is rendered when it is unchanged).

        Args:
            text: The text.

        """
        if text == self.text:
            return
        self.text = text
        antialias = True
        self.image = self.font.render(text, antialias, TEXT_COLOR)
        self.rect.size = self.image.get_size()


class MrMuncherScene(Scene):
    """The maze, the player, the munchers and the sprockets."""

    NAME = 'Mr. Muncher - Film Strip Edition'
    VERSION = '1.0'

    def __init__(
        self: Self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Build the maze and place everything in it.

        The maze fills the screen: one cell per GRID_SIZE pixels (the original toy's 800x600
        window is 40 by 30 cells).

        Args:
            options: Command-line options.
            groups: The sprite group (a new one when None).

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        super().__init__(options=options, groups=groups)
        self.background_color = BLACK

        columns = self.screen_width // GRID_SIZE
        rows = self.screen_height // GRID_SIZE
        self.maze = build_maze(
            columns=columns, rows=rows, random_generator=random_stream(MAZE_RANDOM_STREAM)
        )
        self._draw_walls_on_background()

        # Drawn in the order they are added: sprockets, the player, munchers, then the text
        self.sprockets = [
            Sprocket(centre_x=centre_x, centre_y=centre_y, groups=self.all_sprites)
            for centre_x, centre_y in sprocket_centres(
                maze=self.maze, random_generator=random_stream(MAZE_RANDOM_STREAM)
            )
        ]
        self.player = Player(
            centre_x=GRID_SIZE * 2, centre_y=GRID_SIZE * 2, groups=self.all_sprites
        )
        self.munchers = [
            MrMuncher(
                centre_x=GRID_SIZE * (columns - 3),
                centre_y=GRID_SIZE * (rows - 3),
                groups=self.all_sprites,
            ),
            MrMuncher(
                centre_x=GRID_SIZE * 3, centre_y=GRID_SIZE * (rows - 3), groups=self.all_sprites
            ),
            MrMuncher(
                centre_x=GRID_SIZE * (columns - 3), centre_y=GRID_SIZE * 3, groups=self.all_sprites
            ),
        ]
        self.score = 0
        font = pygame.font.Font(None, TEXT_FONT_SIZE)
        self.score_text = TextLine(
            text=self._score_message(),
            topleft=SCORE_TEXT_POSITION,
            font=font,
            groups=self.all_sprites,
        )
        self.win_text = TextLine(
            text=WIN_MESSAGE,
            topleft=(self.screen_width // 2 - WIN_TEXT_LEFT_OF_CENTRE, self.screen_height // 2),
            font=font,
            groups=self.all_sprites,
        )
        self.win_text.visible = 0

        self.actions = self._create_action_map(
            input_mode=self.options.get('input_mode', 'joystick')
        )

    @staticmethod
    def _create_action_map(*, input_mode: str) -> ActionMap:
        """Bind the controls: arrows and D-pad move, ESC and Q quit.

        Every key binds a physical key position (a scancode: the same place on every keyboard
        layout), quit included (ActionMap module docstring).

        Args:
            input_mode: Gamepad event family ('joystick' or 'controller').

        Returns:
            The action map.

        """
        actions = ActionMap(input_mode=input_mode)
        actions.bind(
            'move_right',
            scancode=pygame.KSCAN_RIGHT,
            controller_button=pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
        )
        actions.bind(
            'move_down',
            scancode=pygame.KSCAN_DOWN,
            controller_button=pygame.CONTROLLER_BUTTON_DPAD_DOWN,
        )
        actions.bind(
            'move_left',
            scancode=pygame.KSCAN_LEFT,
            controller_button=pygame.CONTROLLER_BUTTON_DPAD_LEFT,
        )
        actions.bind(
            'move_up', scancode=pygame.KSCAN_UP, controller_button=pygame.CONTROLLER_BUTTON_DPAD_UP
        )
        actions.bind('quit', scancode=pygame.KSCAN_ESCAPE)
        actions.bind('quit', scancode=pygame.KSCAN_Q)
        return actions

    def _draw_walls_on_background(self: Self) -> None:
        """Paint the maze's walls onto the background (they never change).

        The sprite group already clears with this background surface (the background_color
        setter gave it), so it clears to the walls too.
        """
        for column, row in self.maze.wall_cells():
            pygame.draw.rect(
                self.background,
                WALL_COLOR,
                (column * GRID_SIZE, row * GRID_SIZE, GRID_SIZE, GRID_SIZE),
            )

    def _score_message(self: Self) -> str:
        """Return the score line's text.

        Returns:
            The text.

        """
        return f'Score: {self.score}'

    @property
    def has_won(self: Self) -> bool:
        """Whether every sprocket is collected."""
        return all(sprocket.collected for sprocket in self.sprockets)

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Move the player and the munchers, collect sprockets, check for a catch.

        Args:
            dt: The frame's seconds.

        """
        super().dt_tick(dt)
        self.actions.begin_frame()

        held_direction = next(
            (direction for action, direction in DIRECTION_ACTIONS if self.actions.is_held(action)),
            None,
        )
        if held_direction is not None:
            self.player.try_move(
                direction=held_direction,
                distance=PLAYER_SPEED_PIXELS_PER_SECOND * dt,
                maze=self.maze,
            )
        for muncher in self.munchers:
            muncher.wander(dt=dt, maze=self.maze)

        self._collect_sprockets()
        self._check_for_catch()

        self.score_text.show(text=self._score_message())
        self.win_text.visible = 1 if self.has_won else 0

    def _collect_sprockets(self: Self) -> None:
        """Collect every sprocket the player is touching, 10 points each."""
        for sprocket in self.sprockets:
            if not sprocket.collected and (
                _centre_distance(
                    first=self.player, second_x=sprocket.centre_x, second_y=sprocket.centre_y
                )
                < SPROCKET_COLLECT_DISTANCE
            ):
                sprocket.collected = True
                self.score += SPROCKET_POINTS

    def _check_for_catch(self: Self) -> None:
        """Start over if a muncher touches the player.

        The player goes back to its start, the score to 0 and every sprocket back in place; the
        munchers stay where they are.
        """
        for muncher in self.munchers:
            if (
                _centre_distance(
                    first=self.player, second_x=muncher.centre_x, second_y=muncher.centre_y
                )
                < MUNCHER_CATCH_DISTANCE
            ):
                self.player.return_to_start()
                self.score = 0
                for sprocket in self.sprockets:
                    sprocket.collected = False

    @override
    def render(self: Self, screen: pygame.Surface) -> None:
        """Draw the whole frame: the background with its walls, then every sprite.

        Args:
            screen: The display surface.

        """
        screen.blit(self.background, (0, 0))
        self.all_sprites.draw(screen)
        self.rects = None  # The whole screen is presented

    # --- Input handlers ---

    @override
    def on_key_down_event(self: Self, event: KeyEvent) -> None:
        """Track held movement keys; ESC or Q quits.

        Args:
            event: The key down event.

        """
        self.actions.handle_event(event)
        action = self.actions.get_action(event)
        if action == 'quit':
            self.next_scene = None
        elif action is None:
            super().on_key_down_event(event)

    @override
    def on_key_up_event(self: Self, event: KeyEvent) -> None:
        """Track released movement keys.

        Args:
            event: The key up event.

        """
        self.actions.handle_event(event)

    @override
    def on_joy_button_down_event(self: Self, event: JoyButtonEvent) -> None:
        """Track held D-pad buttons (joystick input mode).

        Args:
            event: The joystick button down event.

        """
        self.actions.handle_event(event)

    @override
    def on_joy_button_up_event(self: Self, event: JoyButtonEvent) -> None:
        """Track released D-pad buttons (joystick input mode).

        Args:
            event: The joystick button up event.

        """
        self.actions.handle_event(event)

    @override
    def on_controller_button_down_event(self: Self, event: ControllerButtonEvent) -> None:
        """Track held D-pad buttons (controller input mode).

        Args:
            event: The controller button down event.

        """
        self.actions.handle_event(event)

    @override
    def on_controller_button_up_event(self: Self, event: ControllerButtonEvent) -> None:
        """Track released D-pad buttons (controller input mode).

        Args:
            event: The controller button up event.

        """
        self.actions.handle_event(event)


def main() -> None:
    """Run Mr. Muncher."""
    GameEngine(game=MrMuncherScene).start()


if __name__ == '__main__':
    main()
