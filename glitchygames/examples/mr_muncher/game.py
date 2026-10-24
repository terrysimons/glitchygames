"""Mr. Muncher: a maze chase at the movies.

You are Mr. Muncher, a popcorn bucket with an appetite. Eat every sprocket (they look like a
film strip's sprocket holes) to finish the reel; four munchers, spiky fuzzballs, hunt you. Eat
a snack (a wrapped candy) for a sugar rush: for a few seconds the munchers turn dull blue and
run, and you can catch them for 200, 400, 800 and 1600 points. Twice a reel a bonus film reel
appears under their house. You have three lives (each new one is the next take), and an extra
one at 10,000 points. Each reel is faster than the last.

Controls (every key by its position, ``ActionMap`` scancodes): the arrow keys or WASD steer, or
a gamepad's D-pad, hat or left stick; a direction pressed before a junction is remembered and
taken there. ESC or P (or the gamepad's Start) pauses; Q quits. The game pauses itself when its
window loses focus.

The munchers (``actors.py``) take turns retreating to their corners and chasing, each in its
own way: Chomper (purple) heads straight for you, Snapper (green) for the tiles in front of you,
Gnasher (orange) for the far side of you from Chomper, and Nibbles (magenta) chases from afar
but loses its nerve up close. ``--debug-overlay`` (or F3) marks each muncher's target tile.

A new game counts down like a film leader (3, 2, 1, ACTION!); each later life starts with its
take number and each reel with its number. A cleared reel is a CUT!, and the last life ends
with THE END.

Everything is deterministic: positions, timers and the frightened munchers' random turns run on
the scene's game time and the engine's seeded random streams, so ``--record-trace`` recordings
replay exactly. High scores are kept with the engine's saves (``open_saves``).
"""

from __future__ import annotations

import enum
import functools
import logging
import math
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames.audio.exceptions import AudioUnavailableError
from glitchygames.audio.recipes import SoundBank, Tremolo
from glitchygames.audio.synth import Waveform
from glitchygames.color import BLACK
from glitchygames.effects.shake import RumbleSettings, Shake, ShakeStyle, ShakeTarget
from glitchygames.engine import GameEngine
from glitchygames.examples.mr_muncher import drawing
from glitchygames.examples.mr_muncher.actors import (
    ChaseSituation,
    MazeGeometry,
    Muncher,
    MuncherState,
    Player,
    muncher_profiles,
)
from glitchygames.examples.mr_muncher.levels import (
    LevelSettings,
    frightened_is_flashing,
    mode_phase_index,
    munchers_chase,
    settings_for_level,
)
from glitchygames.examples.mr_muncher.maze import (
    SNACK,
    SPROCKET,
    Direction,
    Maze,
    build_maze,
)
from glitchygames.examples.mr_muncher.scenery import (
    Picture,
    SidePanel,
    Sprocket,
    bundled_font,
    fitted_font,
    render_text,
)
from glitchygames.examples.mr_muncher.sounds import ALL_RECIPES, CRUNCH_RECIPES
from glitchygames.input import ActionMap
from glitchygames.opacity import make_opaque
from glitchygames.scenes import Scene
from glitchygames.scenes.builtin_scenes.game_over_scene import GameOverScene, TextSprite
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.state import SaveManager, SaveNotFoundError, open_saves
from glitchygames.transitions import FadeTransition

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from glitchygames.audio.live import LiveVoice
    from glitchygames.camera import Camera2D
    from glitchygames.events.base import (
        ControllerAxisEvent,
        ControllerButtonEvent,
        JoyAxisEvent,
        JoyButtonEvent,
        JoyHatEvent,
        KeyEvent,
        WindowEvent,
    )

log = logging.getLogger('game')

type Color = tuple[int, int, int]

# Lives at the start (the one in play included), and the score that gives one more (once)
STARTING_LIVES = 3
EXTRA_LIFE_SCORE = 10_000

# Points
SPROCKET_POINTS = 10
SNACK_POINTS = 50
# The first muncher eaten on one snack is worth this; each next one doubles it
FIRST_MUNCHER_POINTS = 200

# The bonus reel appears under the house when this many sprockets have been eaten on a level,
# and stays for BONUS_SECONDS unless eaten
BONUS_SPROCKET_COUNTS: tuple[int, ...] = (70, 170)
BONUS_SECONDS = 9.5
# Where the bonus appears, and the messages show: in tiles below the house's centre
MESSAGE_ROWS_BELOW_HOUSE = 3

# The player and a muncher touch when their centres are closer than this (in tiles)
CONTACT_DISTANCE_TILES = 0.6
# Play is simulated in steps of at most this long, so nothing moves far enough in one step to
# pass through anything (actors move at most about 0.15 tiles a step)
MAX_STEP_SECONDS = 1.0 / 120.0

# How long each moment of the game lasts, in seconds of game time
INTRO_READY_SECONDS = 3.6  # A new game's countdown (3, 2, 1), then ACTION!
READY_SECONDS = 2.0  # The take or reel number before each later life or reel, then ACTION!
ACTION_SECONDS = 0.8  # ACTION! shows for the last part of either
COUNTDOWN_NUMBERS: tuple[int, ...] = (3, 2, 1)
EAT_PAUSE_SECONDS = 0.75  # Everything stops while a muncher's points show
DEATH_FREEZE_SECONDS = 0.8  # Everything stops when a muncher catches the player
DEATH_ANIMATION_SECONDS = 1.5  # Then the bucket sinks and its popcorn bursts out
DEATH_AFTER_SECONDS = 0.7  # A moment of empty maze before the next life
LEVEL_CLEAR_PAUSE_SECONDS = 1.0  # A cleared maze holds still, then flashes
LEVEL_CLEAR_FLASH_SECONDS = 2.0
LEVEL_CLEAR_FLASH_TOGGLE_SECONDS = 0.25
GAME_OVER_SECONDS = 2.5  # THE END shows in the maze, then the game-over screen fades in
BONUS_POINTS_SHOW_SECONDS = 2.0
GAME_OVER_FADE_SECONDS = 1.0

# A catch shakes the screen a little (and rumbles a gamepad)
CAUGHT_SHAKE = Shake(
    style=ShakeStyle.NOISE,
    strength=6.0,
    duration=0.4,
    frequency=30.0,
    rumble=RumbleSettings(low_frequency=0.8, high_frequency=0.4, scale_with_strength=False),
)

# The projector behind play: filtered noise that flutters like a film projector's shutter. It
# runs faster and brighter as sprockets run out, wobbles slow and low while the munchers are
# frightened, and races while eyes are going home.
PROJECTOR_VOLUME = 0.05
PROJECTOR_CUTOFF_HZ = 500.0
PROJECTOR_CUTOFF_CLIMB_HZ = 700.0  # Added at the last sprocket
PROJECTOR_FLUTTER_HZ = 20.0
PROJECTOR_FLUTTER_CLIMB_HZ = 10.0  # Added at the last sprocket
PROJECTOR_FLUTTER_DEPTH = 0.8
FRIGHTENED_PROJECTOR_CUTOFF_HZ = 300.0
FRIGHTENED_PROJECTOR_FLUTTER_HZ = 8.0
EYES_PROJECTOR_CUTOFF_HZ = 2000.0
EYES_PROJECTOR_FLUTTER_HZ = 40.0

# Layout: tiles fill the screen's height unless the side panels would get narrower than this
MINIMUM_PANEL_WIDTH = 100
MINIMUM_TILE_SIZE = 8

# Sprite layers (drawn bottom to top)
SPROCKET_LAYER = 0
BONUS_LAYER = 1
MUNCHER_LAYER = 2
PLAYER_LAYER = 3
POPUP_LAYER = 4
MESSAGE_LAYER = 5
PANEL_LAYER = 6

# Text
TITLE_COLOR: Color = (255, 200, 80)
LABEL_COLOR: Color = (190, 170, 150)
VALUE_COLOR: Color = (255, 255, 255)
HINT_COLOR: Color = (150, 135, 120)
MESSAGE_COLOR: Color = (255, 200, 80)
THE_END_COLOR: Color = (255, 90, 90)
MUNCHER_POINTS_COLOR: Color = (255, 255, 255)
BONUS_POINTS_COLOR: Color = (255, 190, 50)
MESSAGE_FONT_SIZE = 22
POPUP_FONT_SIZE = 16
# The side panels' fonts: the largest of these sizes at which their longest text fits
TITLE_FONT_SIZE = 20
LABEL_FONT_SIZE = 13
VALUE_FONT_SIZE = 20
HINT_FONT_SIZE = 12
# Space kept clear between the panel's text and its edges, in pixels
PANEL_TEXT_MARGIN = 6
TITLE_LINES: tuple[str, ...] = ('MR.', 'MUNCHER')
PANEL_LABELS: tuple[str, ...] = ('SCORE', 'HIGH SCORE', 'REEL', 'LIVES', 'BONUS')
# The widest score a panel is laid out for
WIDEST_VALUE = '9999990'
# The messages under the house
ACTION_MESSAGE = 'ACTION!'
CUT_MESSAGE = 'CUT!'
THE_END_MESSAGE = 'THE END'
# The controls, as (keys, what they do)
CONTROL_HINTS: tuple[tuple[str, str], ...] = (
    ('ARROWS/WASD', 'move'),
    ('ESC/P', 'pause'),
    ('Q', 'quit'),
)

# Saves: the high score table, best first
SAVE_APP_NAME = 'mr-muncher'
HIGH_SCORES_SAVE_NAME = 'high_scores'
HIGH_SCORE_ENTRIES = 10

# The directions' actions; when two are pressed in one frame the first in this order wins
DIRECTION_ACTIONS: tuple[tuple[str, Direction], ...] = (
    ('move_up', Direction.UP),
    ('move_left', Direction.LEFT),
    ('move_down', Direction.DOWN),
    ('move_right', Direction.RIGHT),
)
# A gamepad's left stick counts as a direction past this far from centre
STICK_THRESHOLD = 0.5


@functools.cache
def shared_sound_bank() -> SoundBank:
    """Return the game's sound bank, shared by every level (each sound renders only once).

    Returns:
        The sound bank.

    """
    return SoundBank(ALL_RECIPES)


class Phase(enum.Enum):
    """The moment the game is in."""

    READY = 'ready'  # The countdown, take or reel number, then ACTION!; nothing moves
    PLAYING = 'playing'
    MUNCHER_EATEN = 'muncher_eaten'  # A short stop while the points show
    DYING = 'dying'
    LEVEL_CLEAR = 'level_clear'
    GAME_OVER = 'game_over'


class GameProgress(BaseModel):
    """How far a game has come: what a reel starts with.

    Attributes:
        level: The reel's number (1 for a new game).
        score: The score so far.
        lives: The lives left, the one in play included.
        extra_life_awarded: Whether the extra life has been given already.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    level: int = 1
    score: int = 0
    lives: int = STARTING_LIVES
    extra_life_awarded: bool = False

    @property
    def is_new_game(self: Self) -> bool:
        """Whether this is a new game's first reel."""
        return self.level == 1 and self.score == 0


def maze_geometry(*, maze: Maze, screen_size: tuple[int, int]) -> MazeGeometry:
    """Size the maze's tiles to the screen and centre it, leaving room for the side panels.

    Args:
        maze: The maze.
        screen_size: The screen's (width, height).

    Returns:
        The geometry.

    """
    screen_width, screen_height = screen_size
    tile_size = max(
        MINIMUM_TILE_SIZE,
        min(screen_height // maze.rows, (screen_width - 2 * MINIMUM_PANEL_WIDTH) // maze.columns),
    )
    return MazeGeometry(
        tile_size=tile_size,
        left=(screen_width - maze.columns * tile_size) // 2,
        top=(screen_height - maze.rows * tile_size) // 2,
    )


class MrMuncherScene(Scene):
    """One level of Mr. Muncher: the maze, the player, the munchers and the side panels."""

    NAME = 'Mr. Muncher'
    VERSION = '2.0'
    # After a hitch (a window drag, focus loss) logic advances at most this much in one frame
    MAX_FRAME_SECONDS: ClassVar[float | None] = 0.05

    def __init__(
        self: Self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
        progress: GameProgress | Mapping[str, Any] | None = None,
    ) -> None:
        """Build a reel: the maze, its sprockets, the actors, the panels, and its countdown.

        Args:
            options: Command-line options.
            groups: The sprite group (a new one when None).
            progress: How far the game has come (None, or the default, for a new game); a
                mapping is read as one (replay_arguments gives one).

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        super().__init__(options=options, groups=groups)
        self.background_color = BLACK
        self.starting_progress = GameProgress.model_validate(
            progress if progress is not None else GameProgress()
        )
        self.settings: LevelSettings = settings_for_level(self.starting_progress.level)
        self.score = self.starting_progress.score
        self.lives = self.starting_progress.lives
        self.extra_life_awarded = self.starting_progress.extra_life_awarded

        self.maze = build_maze()
        self.geometry = maze_geometry(
            maze=self.maze, screen_size=(self.screen_width, self.screen_height)
        )
        self._draw_maze_backgrounds()
        house_column, house_row = self.maze.house_centre
        # The tile under the house where the bonus appears and the messages show
        self.message_cell = (house_column, house_row + MESSAGE_ROWS_BELOW_HOUSE)
        self._create_maze_sprites()
        self._create_text_sprites()

        # Play state
        self.phase = Phase.READY
        self.phase_seconds = 0.0
        self.counts_down = self.starting_progress.is_new_game
        self.ready_seconds = INTRO_READY_SECONDS if self.counts_down else READY_SECONDS
        # Each life on a reel is a take: the first is take 1
        self.take = 1
        # Seconds this life has been in play (munchers leave the house by it)
        self.life_seconds = 0.0
        # The scatter/chase clock: it stops while the munchers are frightened
        self.mode_seconds = 0.0
        self.frightened_seconds_left = 0.0
        self.munchers_eaten_this_fright = 0
        self.crunch_count = 0
        # The muncher whose points show during MUNCHER_EATEN
        self.eaten_muncher: Muncher | None = None
        self.game_over_requested = False

        self.saves: SaveManager = open_saves(app_name=SAVE_APP_NAME)
        self.high_score = max(self._best_saved_score(), self.score)
        self.sounds = shared_sound_bank()
        self.projector: LiveVoice | None = None
        # The projector's settings last given (cutoff, flutter rate), to change them only then
        self.projector_settings: tuple[float, float] | None = None
        self.actions = self._create_action_map(input_mode=self.options.get('input_mode', 'auto'))
        self._pose_sprites()

    def _draw_maze_backgrounds(self: Self) -> None:
        """Draw the maze onto the background, and a copy in the level-clear flash colours.

        Each is made opaque after the maze is drawn on it: on a display whose pixels carry
        alpha (macOS), blending onto the background's format leaves alpha 0, and every sprite
        later blended over such a pixel would show unblended (glitchygames/opacity.py).
        """
        self.maze_origin = (self.geometry.left, self.geometry.top)
        self.flash_background = self.background.copy()
        for background, flashing in ((self.background, False), (self.flash_background, True)):
            background.blit(
                drawing.maze_picture(
                    layout=self.maze.layout, tile_size=self.geometry.tile_size, flashing=flashing
                ),
                self.maze_origin,
            )
            make_opaque(surface=background)

    def _create_maze_sprites(self: Self) -> None:
        """Create the sprockets, the bonus, the munchers and the player (in layer order)."""
        self.sprockets: dict[tuple[int, int], Sprocket] = {
            cell: Sprocket(
                cell=cell,
                is_snack=character == SNACK,
                geometry=self.geometry,
                layer=SPROCKET_LAYER,
                groups=self.all_sprites,
            )
            for character in (SPROCKET, SNACK)
            for cell in self.maze.cells_holding(character=character)
        }
        self.sprockets_eaten = 0
        message_centre = self.geometry.pixel_centre(
            tile_x=self.message_cell[0], tile_y=self.message_cell[1]
        )
        self.bonus = Picture(
            image=drawing.bonus_reel_picture(size=round(self.geometry.tile_size * 1.3)),
            centre=message_centre,
            layer=BONUS_LAYER,
            name='Bonus',
            groups=self.all_sprites,
        )
        self.bonus.visible = 0
        self.bonus_seconds_left = 0.0
        self.munchers = [
            Muncher(
                profile=profile,
                maze=self.maze,
                geometry=self.geometry,
                layer=MUNCHER_LAYER,
                groups=self.all_sprites,
            )
            for profile in muncher_profiles(maze=self.maze)
        ]
        self.player = Player(
            maze=self.maze, geometry=self.geometry, layer=PLAYER_LAYER, groups=self.all_sprites
        )

    def _create_text_sprites(self: Self) -> None:
        """Create the fonts, the points pop-ups, the message under the house and the panels."""
        self.message_font = bundled_font(bold=True, size=MESSAGE_FONT_SIZE)
        self.popup_font = bundled_font(bold=True, size=POPUP_FONT_SIZE)
        holes_width = drawing.SPROCKET_HOLE_MARGIN * 2 + drawing.SPROCKET_HOLE_WIDTH
        text_width = self.geometry.left - holes_width - 2 * PANEL_TEXT_MARGIN
        self.title_font = fitted_font(
            bold=True, texts=TITLE_LINES, width=text_width, largest=TITLE_FONT_SIZE
        )
        self.label_font = fitted_font(
            bold=True, texts=PANEL_LABELS, width=text_width, largest=LABEL_FONT_SIZE
        )
        self.value_font = fitted_font(
            bold=True, texts=(WIDEST_VALUE,), width=text_width, largest=VALUE_FONT_SIZE
        )
        self.key_font = fitted_font(
            bold=True,
            texts=tuple(keys for keys, _ in CONTROL_HINTS),
            width=text_width,
            largest=HINT_FONT_SIZE,
        )
        self.hint_font = fitted_font(
            bold=False,
            texts=tuple(meaning for _, meaning in CONTROL_HINTS),
            width=text_width,
            largest=HINT_FONT_SIZE,
        )
        message_centre = self.geometry.pixel_centre(
            tile_x=self.message_cell[0], tile_y=self.message_cell[1]
        )
        self.muncher_points = Picture(
            image=render_text(font=self.popup_font, text='200', color=MUNCHER_POINTS_COLOR),
            centre=message_centre,
            layer=POPUP_LAYER,
            name='MuncherPoints',
            groups=self.all_sprites,
        )
        self.muncher_points.visible = 0
        self.bonus_points = Picture(
            image=render_text(font=self.popup_font, text='100', color=BONUS_POINTS_COLOR),
            centre=message_centre,
            layer=POPUP_LAYER,
            name='BonusPoints',
            groups=self.all_sprites,
        )
        self.bonus_points.visible = 0
        self.bonus_points_seconds_left = 0.0
        # The message's text and colour as last drawn (it is drawn again only when they change)
        self.message_shown: tuple[str, Color] = ('', MESSAGE_COLOR)
        self.message = Picture(
            image=render_text(font=self.message_font, text=' ', color=MESSAGE_COLOR),
            centre=message_centre,
            layer=MESSAGE_LAYER,
            name='Message',
            groups=self.all_sprites,
        )
        maze_right = self.geometry.left + self.maze.columns * self.geometry.tile_size
        self.left_panel = SidePanel(
            area=pygame.Rect(0, 0, self.geometry.left, self.screen_height),
            holes_on_left=True,
            layer=PANEL_LAYER,
            groups=self.all_sprites,
        )
        self.right_panel = SidePanel(
            area=pygame.Rect(maze_right, 0, self.screen_width - maze_right, self.screen_height),
            holes_on_left=False,
            layer=PANEL_LAYER,
            groups=self.all_sprites,
        )

    # --- Scene lifecycle ---

    @override
    def replay_arguments(self: Self) -> dict[str, Any]:
        """Rebuild this reel as it began.

        Returns:
            The progress it was built with (as a plain mapping: it round-trips through JSON).

        """
        return {'progress': self.starting_progress.model_dump()}

    @override
    def setup(self: Self) -> None:
        """Render the sounds now (none renders mid-frame) and show the reel's first message."""
        super().setup()
        self.sounds.prerender()
        # (Set up again when play resumes after a pause: only a reel still waiting to start
        # shows its message)
        if self.phase is Phase.READY:
            self._show_ready_message()
        log.info('Mr. Muncher: reel %d', self.settings.level)

    @override
    def cleanup(self: Self) -> None:
        """Stop the projector when the reel ends."""
        super().cleanup()
        self._stop_projector()

    @staticmethod
    def _create_action_map(*, input_mode: str) -> ActionMap:
        """Bind the controls (every key by its position, ActionMap module docstring).

        Arrows and WASD, a gamepad's D-pad and left stick steer; ESC, P or Start pause; Q quits.

        Args:
            input_mode: Gamepad event family: 'auto' (the engine's --input-mode default: both
                families), 'joystick' or 'controller'.

        Returns:
            The action map.

        """
        actions = ActionMap(input_mode=input_mode)
        bindings = (
            ('move_up', pygame.KSCAN_UP, pygame.KSCAN_W, pygame.CONTROLLER_BUTTON_DPAD_UP),
            ('move_left', pygame.KSCAN_LEFT, pygame.KSCAN_A, pygame.CONTROLLER_BUTTON_DPAD_LEFT),
            ('move_down', pygame.KSCAN_DOWN, pygame.KSCAN_S, pygame.CONTROLLER_BUTTON_DPAD_DOWN),
            (
                'move_right',
                pygame.KSCAN_RIGHT,
                pygame.KSCAN_D,
                pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
            ),
        )
        for action, arrow_scancode, letter_scancode, dpad_button in bindings:
            actions.bind(action, scancode=arrow_scancode, controller_button=dpad_button)
            actions.bind(action, scancode=letter_scancode)
        actions.bind('move_up', controller_axis=(pygame.CONTROLLER_AXIS_LEFTY, -STICK_THRESHOLD))
        actions.bind('move_down', controller_axis=(pygame.CONTROLLER_AXIS_LEFTY, STICK_THRESHOLD))
        actions.bind('move_left', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, -STICK_THRESHOLD))
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, STICK_THRESHOLD))
        actions.bind('pause', scancode=pygame.KSCAN_ESCAPE)
        actions.bind(
            'pause', scancode=pygame.KSCAN_P, controller_button=pygame.CONTROLLER_BUTTON_START
        )
        actions.bind('quit', scancode=pygame.KSCAN_Q)
        return actions

    # --- Logic (dt_tick) ---

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Run one frame of the game: input, the current phase, then every sprite's pose.

        Args:
            dt: The frame's seconds (capped at MAX_FRAME_SECONDS).

        """
        super().dt_tick(dt)
        self._read_direction_input()
        self.phase_seconds += dt
        self._run_phase(dt=dt)
        self._count_down_bonus_points(dt=dt)
        self._update_projector()
        self._pose_sprites()

    def _run_phase(self: Self, *, dt: float) -> None:
        """Run this frame of the current phase; each waiting phase moves on when its time is up.

        Args:
            dt: The frame's seconds.

        """
        match self.phase:
            case Phase.PLAYING:
                self._play(dt=dt)
            case Phase.DYING:
                self._die_a_little()
            case Phase.READY if self.phase_seconds < self.ready_seconds:
                self._show_ready_message()
            case _:
                # The other phases wait, then move on
                finishes: dict[Phase, tuple[float, Callable[[], None]]] = {
                    Phase.READY: (self.ready_seconds, self._start_playing),
                    Phase.MUNCHER_EATEN: (EAT_PAUSE_SECONDS, self._resume_after_eating),
                    Phase.LEVEL_CLEAR: (
                        LEVEL_CLEAR_PAUSE_SECONDS + LEVEL_CLEAR_FLASH_SECONDS,
                        self._go_to_next_level,
                    ),
                    Phase.GAME_OVER: (GAME_OVER_SECONDS, self._show_game_over_screen),
                }
                seconds, finish = finishes[self.phase]
                if self.phase_seconds >= seconds:
                    finish()

    def _read_direction_input(self: Self) -> None:
        """Remember the direction last pressed (a press before a junction is kept for it).

        Releasing the remembered direction while another is still held switches to that one,
        as a held joystick would.
        """
        for action, direction in DIRECTION_ACTIONS:
            if self.actions.just_pressed(action):
                self.player.wanted_direction = direction
                break
        else:
            wanted = self.player.wanted_direction
            wanted_actions = [
                action for action, direction in DIRECTION_ACTIONS if direction is wanted
            ]
            if wanted_actions and self.actions.just_released(wanted_actions[0]):
                held = [
                    direction
                    for action, direction in DIRECTION_ACTIONS
                    if self.actions.is_held(action)
                ]
                if held:
                    self.player.wanted_direction = held[0]
        self.actions.begin_frame()

    def _show_message(self: Self, *, text: str, color: Color = MESSAGE_COLOR) -> None:
        """Show a message under the house (it is drawn again only when it changes).

        Args:
            text: The message.
            color: Its colour.

        """
        if (text, color) != self.message_shown:
            self.message_shown = (text, color)
            self.message.change_image(
                image=render_text(font=self.message_font, text=text, color=color)
            )
        self.message.visible = 1

    def _ready_message_text(self: Self) -> tuple[str, str | None]:
        """Return what the message under the house says now, before play, and its cue sound.

        A new game counts down (3, 2, 1) with a beep a number; a later reel shows its number and
        a later life its take; ACTION! (with the clapperboard) ends every one.

        Returns:
            The text, and the sound that marks its start (None for none).

        """
        before_action = self.ready_seconds - ACTION_SECONDS
        if self.phase_seconds >= before_action:
            return (ACTION_MESSAGE, 'action')
        if self.counts_down:
            step_seconds = before_action / len(COUNTDOWN_NUMBERS)
            number = COUNTDOWN_NUMBERS[math.floor(self.phase_seconds / step_seconds)]
            return (str(number), 'countdown_beep')
        if self.take > 1:
            return (f'TAKE {self.take}', None)
        return (f'REEL {self.settings.level}', None)

    def _show_ready_message(self: Self) -> None:
        """Show this moment's message before play, sounding its cue when it first shows."""
        text, cue = self._ready_message_text()
        if text != self.message_shown[0] and cue is not None:
            self.sounds.play(cue)
        self._show_message(text=text)

    def _change_phase(self: Self, phase: Phase) -> None:
        """Enter a phase; its clock starts at zero.

        Args:
            phase: The phase.

        """
        self.phase = phase
        self.phase_seconds = 0.0

    def _start_playing(self: Self) -> None:
        """ACTION!: play."""
        self.message.visible = 0
        self._change_phase(Phase.PLAYING)
        self._start_projector()

    def _play(self: Self, *, dt: float) -> None:
        """Simulate a frame of play in short steps: move, eat, then check for contact.

        Args:
            dt: The frame's seconds.

        """
        steps = max(1, math.ceil(dt / MAX_STEP_SECONDS))
        step_seconds = dt / steps
        for _ in range(steps):
            self._advance_timers(seconds=step_seconds)
            player_speed = (
                self.settings.sugar_rush_speed
                if self.frightened_seconds_left > 0.0
                else self.settings.player_speed
            )
            self.player.travel(distance=player_speed * step_seconds)
            self._eat_at_player()
            if self.phase is not Phase.PLAYING or self._check_contacts():
                return
            situation = self._chase_situation()
            hurrying = self.sprockets_left <= self.settings.hurry_sprockets
            for muncher in self.munchers:
                muncher.travel(
                    distance=muncher.speed(settings=self.settings, hurrying=hurrying)
                    * step_seconds,
                    situation=situation,
                )
            if self._check_contacts():
                return

    def _advance_timers(self: Self, *, seconds: float) -> None:
        """Advance this life's clocks: house releases, the mode schedule, fright and bonus.

        Args:
            seconds: The step's seconds.

        """
        self.life_seconds += seconds
        waiting = [muncher for muncher in self.munchers if not muncher.profile.starts_outside]
        for muncher, release_seconds in zip(waiting, self.settings.release_seconds, strict=True):
            if muncher.state is MuncherState.WAITING and self.life_seconds >= release_seconds:
                muncher.state = MuncherState.LEAVING
        if self.frightened_seconds_left > 0.0:
            self.frightened_seconds_left = max(0.0, self.frightened_seconds_left - seconds)
            if self.frightened_seconds_left <= 0.0:
                self._end_fright()
        else:
            phase_before = mode_phase_index(
                schedule=self.settings.mode_schedule, elapsed_seconds=self.mode_seconds
            )
            self.mode_seconds += seconds
            phase_after = mode_phase_index(
                schedule=self.settings.mode_schedule, elapsed_seconds=self.mode_seconds
            )
            if phase_after != phase_before:
                self._turn_roaming_munchers_round()
        if self.bonus.visible:
            self.bonus_seconds_left -= seconds
            if self.bonus_seconds_left <= 0.0:
                self.bonus.visible = 0

    def _turn_roaming_munchers_round(self: Self) -> None:
        """Every muncher out in the maze turns round at once (a change of mode or a fright)."""
        for muncher in self.munchers:
            if muncher.state is MuncherState.ROAMING:
                muncher.reverse_soon = True

    @property
    def sprockets_left(self: Self) -> int:
        """How many sprockets (snacks included) are still to eat."""
        return len(self.sprockets) - self.sprockets_eaten

    def _chase_situation(self: Self) -> ChaseSituation:
        """Return what the munchers know when they choose their turns this step.

        Returns:
            The player's tile and facing, the chaser's tile, and whether they chase.

        """
        return ChaseSituation(
            player_cell=self.player.cell,
            player_facing=self.player.facing,
            chaser_cell=self.munchers[0].cell,
            chasing=munchers_chase(
                schedule=self.settings.mode_schedule, elapsed_seconds=self.mode_seconds
            ),
        )

    def _eat_at_player(self: Self) -> None:
        """Eat any sprocket or bonus on the player's tile; the last sprocket clears the level."""
        sprocket = self.sprockets.get(self.player.cell)
        if sprocket is not None and not sprocket.eaten:
            sprocket.eat()
            self.sprockets_eaten += 1
            self.sounds.play(CRUNCH_RECIPES[self.crunch_count % len(CRUNCH_RECIPES)].name)
            self.crunch_count += 1
            if sprocket.is_snack:
                self._add_points(SNACK_POINTS)
                self._start_fright()
            else:
                self._add_points(SPROCKET_POINTS)
            if self.sprockets_eaten in BONUS_SPROCKET_COUNTS:
                self.bonus.visible = 1
                self.bonus_seconds_left = BONUS_SECONDS
            if self.sprockets_left == 0:
                self._clear_level()
                return
        if self.bonus.visible and self.player.cell == self.message_cell:
            self.bonus.visible = 0
            self._add_points(self.settings.bonus_points)
            self.sounds.play('eat_bonus')
            self.bonus_points.change_image(
                image=render_text(
                    font=self.popup_font,
                    text=str(self.settings.bonus_points),
                    color=BONUS_POINTS_COLOR,
                )
            )
            self.bonus_points.visible = 1
            self.bonus_points_seconds_left = BONUS_POINTS_SHOW_SECONDS

    def _add_points(self: Self, points: int) -> None:
        """Add to the score; passing EXTRA_LIFE_SCORE the first time gives a life.

        Args:
            points: The points.

        """
        self.score += points
        self.high_score = max(self.high_score, self.score)
        if not self.extra_life_awarded and self.score >= EXTRA_LIFE_SCORE:
            self.extra_life_awarded = True
            self.lives += 1
            self.sounds.play('extra_life')

    def _start_fright(self: Self) -> None:
        """A snack: every muncher not already eaten turns blue, and those out turn round."""
        self.frightened_seconds_left = self.settings.frightened_seconds
        self.munchers_eaten_this_fright = 0
        self._turn_roaming_munchers_round()
        for muncher in self.munchers:
            if muncher.state not in {MuncherState.EATEN, MuncherState.ENTERING}:
                muncher.frightened = True
        self.sounds.play('sugar_rush')

    def _end_fright(self: Self) -> None:
        """The snack wore off: every muncher is dangerous again."""
        for muncher in self.munchers:
            muncher.frightened = False

    def _check_contacts(self: Self) -> bool:
        """Settle the first muncher touching the player: eat it if frightened, else die.

        Returns:
            True if a muncher touched the player (play stops for this frame).

        """
        for muncher in self.munchers:
            if muncher.can_touch_player and (
                self.maze.tile_distance(first=self.player.position, second=muncher.position)
                < CONTACT_DISTANCE_TILES
            ):
                if muncher.frightened:
                    self._eat_muncher(muncher)
                else:
                    self._catch_player()
                return True
        return False

    def _eat_muncher(self: Self, muncher: Muncher) -> None:
        """Eat a frightened muncher: its points show while everything stops; then its eyes go home.

        Args:
            muncher: The muncher.

        """
        points = FIRST_MUNCHER_POINTS * 2**self.munchers_eaten_this_fright
        self.munchers_eaten_this_fright += 1
        self._add_points(points)
        muncher.frightened = False
        muncher.state = MuncherState.EATEN
        muncher.hidden = True
        self.player.hidden = True
        self.eaten_muncher = muncher
        self.muncher_points.change_image(
            image=render_text(font=self.popup_font, text=str(points), color=MUNCHER_POINTS_COLOR)
        )
        self.muncher_points.move_to(
            centre=self.geometry.pixel_centre(tile_x=muncher.tile_x, tile_y=muncher.tile_y)
        )
        self.muncher_points.visible = 1
        self.sounds.play('camera_flash')
        self._change_phase(Phase.MUNCHER_EATEN)

    def _resume_after_eating(self: Self) -> None:
        """The points have shown: the eaten muncher's eyes appear, and play goes on."""
        assert self.eaten_muncher is not None  # Set by _eat_muncher, which began this phase
        self.muncher_points.visible = 0
        self.player.hidden = False
        self.eaten_muncher.hidden = False
        self.eaten_muncher = None
        self._change_phase(Phase.PLAYING)

    def _catch_player(self: Self) -> None:
        """A muncher caught the player: everything stops and the screen shakes; then it dies."""
        self._stop_projector()
        self.shake(CAUGHT_SHAKE, targets=ShakeTarget.SCREEN)
        self._change_phase(Phase.DYING)

    def _die_a_little(self: Self) -> None:
        """Run the dying moment: a freeze, the shrivel, an empty pause, then the next life."""
        animation_seconds = self.phase_seconds - DEATH_FREEZE_SECONDS
        if animation_seconds < 0.0:
            return
        if self.player.dying_progress is None:
            for muncher in self.munchers:
                muncher.hidden = True
            self.bonus.visible = 0
            self.sounds.play('film_snap')
        self.player.dying_progress = min(1.0, animation_seconds / DEATH_ANIMATION_SECONDS)
        if animation_seconds >= DEATH_ANIMATION_SECONDS + DEATH_AFTER_SECONDS:
            self._lose_life()

    def _lose_life(self: Self) -> None:
        """One life fewer: start the next one, or end the game."""
        self.lives -= 1
        if self.lives <= 0:
            self.player.hidden = True
            self._show_message(text=THE_END_MESSAGE, color=THE_END_COLOR)
            self._save_high_score()
            self.sounds.play('the_end')
            self._change_phase(Phase.GAME_OVER)
            return
        self._reset_actors()
        self.take += 1
        self.counts_down = False
        self.ready_seconds = READY_SECONDS
        self._change_phase(Phase.READY)
        self._show_ready_message()

    def _reset_actors(self: Self) -> None:
        """Put everyone back at the start of a life; this life's clocks start again."""
        self.player.reset()
        for muncher in self.munchers:
            muncher.reset()
        self.life_seconds = 0.0
        self.mode_seconds = 0.0
        self.frightened_seconds_left = 0.0

    def _clear_level(self: Self) -> None:
        """The last sprocket: CUT!, the munchers vanish and the maze flashes."""
        self._stop_projector()
        for muncher in self.munchers:
            muncher.hidden = True
        self.bonus.visible = 0
        self._show_message(text=CUT_MESSAGE)
        self.sounds.play('level_clear')
        self._change_phase(Phase.LEVEL_CLEAR)

    def _go_to_next_level(self: Self) -> None:
        """Start the next reel with this score and these lives (once)."""
        if self.next_scene is not self:
            return
        self.next_scene = MrMuncherScene(
            options=self.options,
            progress=GameProgress(
                level=self.settings.level + 1,
                score=self.score,
                lives=self.lives,
                extra_life_awarded=self.extra_life_awarded,
            ),
        )

    def _show_game_over_screen(self: Self) -> None:
        """Fade to the game-over screen with the score and the high score table (once)."""
        if self.game_over_requested:
            return
        self.game_over_requested = True
        game_over = MrMuncherGameOverScene(
            final_score=self.score,
            high_scores=self._saved_high_scores(),
            level_reached=self.settings.level,
            options=self.options,
        )
        self.transition_to(game_over, FadeTransition(duration=GAME_OVER_FADE_SECONDS))

    def _count_down_bonus_points(self: Self, *, dt: float) -> None:
        """Hide the bonus's points once they have shown long enough.

        Args:
            dt: The frame's seconds.

        """
        if self.bonus_points.visible:
            self.bonus_points_seconds_left -= dt
            if self.bonus_points_seconds_left <= 0.0:
                self.bonus_points.visible = 0

    # --- Saves ---

    def _saved_high_scores(self: Self) -> list[dict[str, int]]:
        """Return the saved high score table, best first (empty when there is none).

        Returns:
            Entries with 'score' and 'level'.

        """
        try:
            saved = self.saves.load(HIGH_SCORES_SAVE_NAME)
        except SaveNotFoundError:
            return []
        return list(saved.get('scores', []))

    def _best_saved_score(self: Self) -> int:
        """Return the best saved score (0 when there is none).

        Returns:
            The score.

        """
        scores = self._saved_high_scores()
        return scores[0].get('score', 0) if scores else 0

    def _save_high_score(self: Self) -> None:
        """Add this game to the high score table (best HIGH_SCORE_ENTRIES kept)."""
        scores = self._saved_high_scores()
        scores.append({'score': self.score, 'level': self.settings.level})
        scores.sort(key=lambda entry: entry.get('score', 0), reverse=True)
        self.saves.save(HIGH_SCORES_SAVE_NAME, {'scores': scores[:HIGH_SCORE_ENTRIES]})

    # --- Sound ---

    def _start_projector(self: Self) -> None:
        """Start the projector's flutter behind play (none when no live voice or audio is free)."""
        try:
            projector = self.scene_manager.live_audio.create_voice(
                owner=self,
                waveform=Waveform.NOISE,
                frequency=1.0,
                volume=PROJECTOR_VOLUME,
                low_pass_cutoff=PROJECTOR_CUTOFF_HZ,
                tremolo=Tremolo(rate_hz=PROJECTOR_FLUTTER_HZ, depth=PROJECTOR_FLUTTER_DEPTH),
            )
            projector.start()
        except ValueError, AudioUnavailableError:
            log.warning('No live voice or audio available; Mr. Muncher plays without its projector')
            return
        self.projector = projector
        self.projector_settings = None

    def _stop_projector(self: Self) -> None:
        """Stop the projector (if it is running)."""
        if self.projector is not None:
            self.projector.stop()
            self.projector = None

    def _projector_sound(self: Self) -> tuple[float, float]:
        """Return how the projector sounds now: its low-pass cutoff and flutter rate (Hz).

        Returns:
            (cutoff, flutter rate).

        """
        if any(muncher.state is MuncherState.EATEN for muncher in self.munchers):
            return (EYES_PROJECTOR_CUTOFF_HZ, EYES_PROJECTOR_FLUTTER_HZ)
        if self.frightened_seconds_left > 0.0:
            return (FRIGHTENED_PROJECTOR_CUTOFF_HZ, FRIGHTENED_PROJECTOR_FLUTTER_HZ)
        progress = self.sprockets_eaten / len(self.sprockets)
        return (
            PROJECTOR_CUTOFF_HZ + PROJECTOR_CUTOFF_CLIMB_HZ * progress,
            PROJECTOR_FLUTTER_HZ + PROJECTOR_FLUTTER_CLIMB_HZ * progress,
        )

    def _update_projector(self: Self) -> None:
        """Set the projector's sound for this moment (only when it changes)."""
        if self.projector is None:
            return
        cutoff, flutter = self._projector_sound()
        if (cutoff, flutter) != self.projector_settings:
            self.projector_settings = (cutoff, flutter)
            self.projector.low_pass_cutoff = cutoff
            self.projector.tremolo = Tremolo(rate_hz=flutter, depth=PROJECTOR_FLUTTER_DEPTH)

    # --- Pictures (the pose of every sprite, drawn in dt_tick: the pose rule) ---

    def _pose_sprites(self: Self) -> None:
        """Draw every sprite's picture for this moment, and the side panels."""
        flashing = frightened_is_flashing(
            remaining_seconds=self.frightened_seconds_left,
            frightened_seconds=self.settings.frightened_seconds,
        )
        for muncher in self.munchers:
            muncher.pose(game_time=self.game_time, flashing=flashing)
        self.player.pose()
        for sprocket in self.sprockets.values():
            sprocket.pose(game_time=self.game_time if self.phase is Phase.PLAYING else 0.0)
        self._draw_panels()

    def _draw_panels(self: Self) -> None:
        """Redraw a side panel when what it shows has changed.

        The left panel shows the title, score, high score and level; the right one the spare
        lives, this level's bonus and the controls.
        """
        left_contents = (self.score, self.high_score, self.settings.level)
        if self.left_panel.contents != left_contents:
            self.left_panel.draw(contents=left_contents, items=self._left_panel_items())
        reserve_lives = max(0, self.lives - 1)
        right_contents = (reserve_lives, self.settings.level)
        if self.right_panel.contents != right_contents:
            self.right_panel.draw(
                contents=right_contents, items=self._right_panel_items(reserve_lives=reserve_lives)
            )

    def _left_panel_items(self: Self) -> tuple[tuple[pygame.Surface, int], ...]:
        """Lay out the left panel: the title, then the score, high score and reel.

        Returns:
            Each line's picture and top.

        """
        tile_size = self.geometry.tile_size
        items: list[tuple[pygame.Surface, int]] = []
        top = tile_size
        for text in TITLE_LINES:
            items.append((render_text(font=self.title_font, text=text, color=TITLE_COLOR), top))
            top += self.title_font.get_linesize()
        top += tile_size
        for label, value in (
            ('SCORE', self.score),
            ('HIGH SCORE', self.high_score),
            ('REEL', self.settings.level),
        ):
            items.append((render_text(font=self.label_font, text=label, color=LABEL_COLOR), top))
            top += self.label_font.get_linesize()
            items.append((
                render_text(font=self.value_font, text=str(value), color=VALUE_COLOR),
                top,
            ))
            top += self.value_font.get_linesize() + tile_size // 2
        return tuple(items)

    def _right_panel_items(
        self: Self, *, reserve_lives: int
    ) -> tuple[tuple[pygame.Surface, int], ...]:
        """Lay out the right panel: spare lives, this reel's bonus, and the controls.

        Args:
            reserve_lives: The lives left after the one in play.

        Returns:
            Each line's picture and top.

        """
        tile_size = self.geometry.tile_size
        items: list[tuple[pygame.Surface, int]] = []
        top = tile_size
        items.append((render_text(font=self.label_font, text='LIVES', color=LABEL_COLOR), top))
        top += self.label_font.get_linesize() + 2
        if reserve_lives:
            items.append((self._life_icons(count=reserve_lives), top))
        top += tile_size * 2
        items.append((render_text(font=self.label_font, text='BONUS', color=LABEL_COLOR), top))
        top += self.label_font.get_linesize() + 2
        reel_size = round(tile_size * 1.1)
        items.append((drawing.bonus_reel_picture(size=reel_size), top))
        top += reel_size + 2
        bonus_text = str(self.settings.bonus_points)
        items.append((
            render_text(font=self.label_font, text=bonus_text, color=BONUS_POINTS_COLOR),
            top,
        ))
        hint_line = self.key_font.get_linesize() + self.hint_font.get_linesize()
        hint_top = self.screen_height - tile_size - hint_line * len(CONTROL_HINTS)
        for keys, meaning in CONTROL_HINTS:
            items.append((render_text(font=self.key_font, text=keys, color=LABEL_COLOR), hint_top))
            hint_top += self.key_font.get_linesize()
            items.append((
                render_text(font=self.hint_font, text=meaning, color=HINT_COLOR),
                hint_top,
            ))
            hint_top += self.hint_font.get_linesize()
        return tuple(items)

    def _life_icons(self: Self, *, count: int) -> pygame.Surface:
        """Draw a row of spare-life icons (little popcorn buckets), at most four.

        Args:
            count: How many spare lives.

        Returns:
            The row.

        """
        most_shown = 4
        icon_size = self.geometry.tile_size
        gap = 4
        shown = min(count, most_shown)
        row = pygame.Surface((shown * (icon_size + gap) - gap, icon_size), pygame.SRCALPHA)
        icon = drawing.player_picture(size=icon_size, looking=Direction.LEFT, mouth_fraction=0.6)
        for index in range(shown):
            row.blit(icon, (index * (icon_size + gap), 0))
        return row

    # --- Drawing ---

    @override
    def render(self: Self, screen: pygame.Surface) -> None:
        """Draw the whole frame: the maze (flashing as a level ends), then every sprite.

        Args:
            screen: The display surface.

        """
        background = self.background
        if self.phase is Phase.LEVEL_CLEAR and self.phase_seconds >= LEVEL_CLEAR_PAUSE_SECONDS:
            flash_step = math.floor(
                (self.phase_seconds - LEVEL_CLEAR_PAUSE_SECONDS) / LEVEL_CLEAR_FLASH_TOGGLE_SECONDS
            )
            if flash_step % 2 == 0:
                background = self.flash_background
        screen.blit(background, (0, 0))
        # The group clears with the background it was last given: give it this frame's
        self.all_sprites.clear(screen, background)
        self.all_sprites.draw(screen)
        self.rects = None  # The whole screen is presented

    def debug_draw(self: Self, surface: pygame.Surface, camera: Camera2D) -> None:
        """Mark each muncher's target tile with a cross in its colour (the debug overlay).

        Args:
            surface: The overlay surface (screen coordinates).
            camera: The scene's camera (the maze never scrolls).

        """
        for muncher in self.munchers:
            if muncher.target is None or not muncher.can_touch_player:
                continue
            target_x, target_y = camera.apply(
                *self.geometry.pixel_centre(tile_x=muncher.target[0], tile_y=muncher.target[1])
            )
            muncher_x, muncher_y = camera.apply(
                *self.geometry.pixel_centre(tile_x=muncher.tile_x, tile_y=muncher.tile_y)
            )
            arm = self.geometry.tile_size // 2
            color = muncher.profile.color
            pygame.draw.line(
                surface,
                color,
                (target_x - arm, target_y - arm),
                (target_x + arm, target_y + arm),
                2,
            )
            pygame.draw.line(
                surface,
                color,
                (target_x - arm, target_y + arm),
                (target_x + arm, target_y - arm),
                2,
            )
            pygame.draw.line(surface, color, (muncher_x, muncher_y), (target_x, target_y), 1)

    # --- Input handlers ---

    def _pause(self: Self) -> None:
        """Pause behind the engine's pause screen (not once the game is over)."""
        if self.phase is not Phase.GAME_OVER:
            self.next_scene = PauseScene(options=self.options)

    @override
    def on_window_focus_lost_event(self: Self, event: WindowEvent) -> None:
        """Pause when the window loses focus (Cmd-Tab, etc.).

        Args:
            event: The focus lost event.

        """
        super().on_window_focus_lost_event(event)
        self._pause()

    @override
    def on_key_down_event(self: Self, event: KeyEvent) -> None:
        """Steer; ESC or P pauses; Q quits; other keys go to the base scene.

        Args:
            event: The key down event.

        """
        self.actions.handle_event(event)
        action = self.actions.get_action(event)
        if action == 'pause':
            self._pause()
        elif action == 'quit':
            # A QUIT event ends the run (next_scene = None does not: the scene manager reads it
            # as no switch pending)
            self.scene_manager.quit()
        elif action is None:
            super().on_key_down_event(event)

    @override
    def on_key_up_event(self: Self, event: KeyEvent) -> None:
        """Track released keys (never the base scene's quit on release: ESC pauses here).

        Args:
            event: The key up event.

        """
        self.actions.handle_event(event)

    @override
    def on_joy_button_down_event(self: Self, event: JoyButtonEvent) -> None:
        """Steer with the D-pad; Start pauses (joystick input mode).

        Args:
            event: The joystick button down event.

        """
        self.actions.handle_event(event)
        if self.actions.get_action(event) == 'pause':
            self._pause()

    @override
    def on_joy_button_up_event(self: Self, event: JoyButtonEvent) -> None:
        """Track released buttons (joystick input mode).

        Args:
            event: The joystick button up event.

        """
        self.actions.handle_event(event)

    @override
    def on_joy_axis_motion_event(self: Self, event: JoyAxisEvent) -> None:
        """Steer with the left stick (joystick input mode).

        Args:
            event: The joystick axis motion event.

        """
        self.actions.handle_event(event)

    @override
    def on_joy_hat_motion_event(self: Self, event: JoyHatEvent) -> None:
        """Steer with a joystick's hat (a pad whose D-pad is a hat): the way it is pushed.

        Args:
            event: The joystick hat motion event (its value is (x, y), y up).

        """
        hat_x, hat_y = event.value
        if hat_x:
            self.player.wanted_direction = Direction.RIGHT if hat_x > 0 else Direction.LEFT
        elif hat_y:
            self.player.wanted_direction = Direction.UP if hat_y > 0 else Direction.DOWN

    @override
    def on_controller_button_down_event(self: Self, event: ControllerButtonEvent) -> None:
        """Steer with the D-pad; Start pauses (controller input mode).

        Args:
            event: The controller button down event.

        """
        self.actions.handle_event(event)
        if self.actions.get_action(event) == 'pause':
            self._pause()

    @override
    def on_controller_button_up_event(self: Self, event: ControllerButtonEvent) -> None:
        """Track released buttons (controller input mode).

        Args:
            event: The controller button up event.

        """
        self.actions.handle_event(event)

    @override
    def on_controller_axis_motion_event(self: Self, event: ControllerAxisEvent) -> None:
        """Steer with the left stick (controller input mode).

        Args:
            event: The controller axis motion event.

        """
        self.actions.handle_event(event)


class MrMuncherGameOverScene(GameOverScene):
    """Mr. Muncher's game-over screen: the score, the reel reached, the high score table.

    SPACE (or a gamepad's A or Start) starts a new game; ESC quits.
    """

    def __init__(
        self: Self,
        final_score: int | None = None,
        high_scores: list[dict[str, int]] | None = None,
        level_reached: int = 1,
        **kwargs: Any,
    ) -> None:
        """Remember the game that ended.

        Args:
            final_score: Its score.
            high_scores: The high score table, best first (this game included).
            level_reached: The reel it ended on.
            **kwargs: Scene keyword arguments (``options``).

        """
        super().__init__(final_score=final_score, high_scores=high_scores, **kwargs)
        self.level_reached = level_reached

    @override
    def replay_arguments(self: Self) -> dict[str, Any]:
        """Return what this screen was built with.

        Returns:
            The final score, the high score table and the reel reached.

        """
        return {
            'final_score': self.final_score,
            'high_scores': [dict(entry) for entry in self.high_scores],
            'level_reached': self.level_reached,
        }

    @override
    def setup(self: Self) -> None:
        """Lay out the screen, then add the reel reached (and a new best, if it is one)."""
        super().setup()
        best = self.high_scores[0].get('score', 0) if self.high_scores else 0
        is_new_best = (
            self.final_score is not None and self.final_score > 0 and self.final_score >= best
        )
        headline = (
            f'NEW HIGH SCORE!  Reel {self.level_reached}'
            if is_new_best
            else f'You reached reel {self.level_reached}'
        )
        self.all_sprites.add(
            TextSprite(
                headline,
                (self.screen_width // 2, self.screen_height // 4 - 50),
                color=TITLE_COLOR,
                font_size=28,
            )
        )

    @override
    def on_joy_button_down_event(self: Self, event: JoyButtonEvent) -> None:
        """A gamepad's A or Start starts a new game (joystick input mode).

        Args:
            event: The joystick button down event.

        """
        if event.button in {pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_START}:
            self.resume()

    @override
    def on_controller_button_down_event(self: Self, event: ControllerButtonEvent) -> None:
        """A gamepad's A or Start starts a new game (controller input mode).

        Args:
            event: The controller button down event.

        """
        if event.button in {pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_START}:
            self.resume()

    @override
    def resume(self: Self) -> None:
        """Start a new game (explicitly: the previous scene depends on how this was reached)."""
        self.scene_manager.switch_to_scene(MrMuncherScene(options=self.options))


def main() -> None:
    """Run Mr. Muncher."""
    GameEngine(game=MrMuncherScene).start()


if __name__ == '__main__':
    main()
