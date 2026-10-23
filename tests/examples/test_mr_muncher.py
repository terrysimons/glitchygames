"""Tests for the Mr. Muncher example game: real pygame, the real display, pixels not calls.

Mr. Muncher is a Pac-Man style maze game: the player (a yellow disc) collects film strip
sprockets while three red munchers wander the maze at random; a muncher's touch starts the
player over. The maze, the sprockets and the munchers' turns come from the engine's seeded
random streams, so the tests seed them (``reset_streams``) and predict each draw from a copy of
the stream's state.
"""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import TYPE_CHECKING, override

import pygame
import pytest
from scripts.record_golden_traces import GoldenTraceEngine, GoldenTraceSceneManager, command_line

from glitchygames.display_mode import set_display_mode
from glitchygames.events.base import HashableEvent
from glitchygames.examples import mr_muncher
from glitchygames.examples.mr_muncher import game as mr_muncher_game
from glitchygames.examples.mr_muncher.game import (
    MUNCHER_CATCH_DISTANCE,
    MUNCHER_RANDOM_STREAM,
    MUNCHER_SPEED_PIXELS_PER_SECOND,
    MUNCHER_TURN_CHANCE_PER_ORIGINAL_FRAME,
    ORIGINAL_FRAME_SECONDS,
    PLAYER_COLOR,
    PLAYER_SPEED_PIXELS_PER_SECOND,
    SPROCKET_COLLECT_DISTANCE,
    SPROCKET_COLOR,
    SPROCKET_POINTS,
    TEXT_COLOR,
    TEXT_FONT_SIZE,
    WALL_COLOR,
    WIN_MESSAGE,
    Direction,
    MrMuncherScene,
)
from glitchygames.examples.mr_muncher.maze import (
    GRID_SIZE,
    INNER_WALL_FIRST_COLUMN,
    INNER_WALL_FIRST_ROW,
    Maze,
    build_maze,
    sprocket_centres,
)
from glitchygames.exit_codes import ExitCode
from glitchygames.randomness import random_stream, reset_streams
from glitchygames.testing.keys import qwerty_scancode

if TYPE_CHECKING:
    from glitchygames.examples.mr_muncher.game import Disc

SCREEN_SIZE = (800, 480)
# The grid at SCREEN_SIZE
COLUMNS = SCREEN_SIZE[0] // GRID_SIZE
ROWS = SCREEN_SIZE[1] // GRID_SIZE
TEST_SEED = 20261023
BLACK_RGB = (0, 0, 0)

GOLDEN_REPLAY_PATH = (
    Path(__file__).parent.parent / 'fixtures' / 'replays' / 'mr-muncher' / 'golden.jsonl.gz'
)


class FixedDraws(random.Random):
    """A random generator whose ``random()`` always returns the same value."""

    def __init__(self, *, value: float) -> None:
        """Seed the generator; ``random()`` then always returns ``value``."""
        super().__init__(0)
        self.value = value

    @override
    def random(self) -> float:
        return self.value


@pytest.fixture
def scene():
    """A Mr. Muncher scene on an 800x480 display, its random streams seeded."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None or pygame.display.get_surface().get_size() != (
        SCREEN_SIZE
    ):
        set_display_mode(size=SCREEN_SIZE)
    reset_streams(seed=TEST_SEED)
    return MrMuncherScene(options={'input_mode': 'joystick'})


def _key_event(event_type: int, key: int) -> HashableEvent:
    return HashableEvent(event_type, key=key, mod=0, unicode='', scancode=qwerty_scancode(key=key))


def _press(scene: MrMuncherScene, key: int) -> None:
    scene.on_key_down_event(_key_event(pygame.KEYDOWN, key))


def _release(scene: MrMuncherScene, key: int) -> None:
    scene.on_key_up_event(_key_event(pygame.KEYUP, key))


def _place(disc: Disc, *, x: float, y: float) -> None:
    disc.centre_x = x
    disc.centre_y = y
    disc.place()


def _park_munchers(scene: MrMuncherScene) -> None:
    """Move the munchers far from the player's start, where they cannot reach it in a test."""
    for muncher in scene.munchers:
        _place(muncher, x=GRID_SIZE * (COLUMNS - 3), y=GRID_SIZE * (ROWS - 3))


def _open_cell_centre(maze: Maze, *, first_row: int = 2) -> tuple[float, float]:
    """Return the centre of an open cell with an open cell to its right.

    Args:
        maze: The maze.
        first_row: The first row searched.

    Returns:
        The cell's centre, in pixels.

    Raises:
        AssertionError: If the maze has no such cell.

    """
    for row in range(first_row, maze.rows - 2):
        for column in range(2, maze.columns - 3):
            if not maze.is_wall_cell(column=column, row=row) and not maze.is_wall_cell(
                column=column + 1, row=row
            ):
                return (column * GRID_SIZE + GRID_SIZE / 2, row * GRID_SIZE + GRID_SIZE / 2)
    raise AssertionError


def _rendered(scene: MrMuncherScene) -> pygame.Surface:
    assert scene.screen is not None
    scene.render(scene.screen)
    return scene.screen


def _rgb(surface: pygame.Surface, position: tuple[int, int]) -> tuple[int, int, int]:
    color = surface.get_at(position)
    return (color.r, color.g, color.b)


class TestMaze:
    """The maze: a border of walls, chance-built L-shaped pieces inside, sprockets."""

    def test_the_border_is_wall_and_the_inside_open_when_no_piece_is_built(self):
        maze = build_maze(columns=COLUMNS, rows=ROWS, random_generator=FixedDraws(value=0.99))

        border = {
            (column, row)
            for column in range(COLUMNS)
            for row in range(ROWS)
            if column in {0, COLUMNS - 1} or row in {0, ROWS - 1}
        }
        assert set(maze.wall_cells()) == border

    def test_every_tried_piece_is_built_when_the_chance_always_hits(self):
        maze = build_maze(columns=COLUMNS, rows=ROWS, random_generator=FixedDraws(value=0.0))

        inner_walls = {
            (column, row)
            for column, row in maze.wall_cells()
            if 0 < column < COLUMNS - 1 and 0 < row < ROWS - 1
        }
        # At 40x24 cells pieces are tried at rows 5 and 13, columns 10 and 25
        corners = [(column, row) for row in (5, 13) for column in (10, 25)]
        assert (INNER_WALL_FIRST_COLUMN, INNER_WALL_FIRST_ROW) in corners
        assert inner_walls == {
            cell
            for column, row in corners
            for cell in ((column, row), (column + 1, row), (column, row + 1))
        }

    def test_positions_outside_the_grid_count_as_wall(self):
        maze = build_maze(columns=COLUMNS, rows=ROWS, random_generator=FixedDraws(value=0.99))

        assert maze.is_wall_at(x=-1.0, y=50.0)
        assert maze.is_wall_at(x=50.0, y=SCREEN_SIZE[1] + 5.0)
        assert maze.is_wall_at(x=5.0, y=50.0)
        assert not maze.is_wall_at(x=50.0, y=50.0)

    def test_sprockets_fill_every_open_cell_away_from_the_edges_when_the_chance_hits(self):
        maze = build_maze(columns=COLUMNS, rows=ROWS, random_generator=FixedDraws(value=0.0))

        centres = sprocket_centres(maze=maze, random_generator=FixedDraws(value=0.0))

        expected = [
            (column * GRID_SIZE + GRID_SIZE // 2, row * GRID_SIZE + GRID_SIZE // 2)
            for row in range(2, ROWS - 2)
            for column in range(2, COLUMNS - 2)
            if not maze.is_wall_cell(column=column, row=row)
        ]
        assert centres == expected
        assert all(not maze.is_wall_at(x=x, y=y) for x, y in centres)

    def test_no_sprockets_when_the_chance_never_hits(self):
        maze = build_maze(columns=COLUMNS, rows=ROWS, random_generator=FixedDraws(value=0.0))

        assert sprocket_centres(maze=maze, random_generator=FixedDraws(value=0.99)) == []

    def test_the_maze_is_immutable(self):
        maze = build_maze(columns=COLUMNS, rows=ROWS, random_generator=FixedDraws(value=0.0))

        with pytest.raises(ValueError, match='frozen'):
            maze.columns = 3


class TestSceneSetup:
    """The scene builds its maze from the seeded stream and places everything."""

    def test_the_same_seed_builds_the_same_maze_and_sprockets(self, scene):
        reset_streams(seed=TEST_SEED)
        again = MrMuncherScene(options={'input_mode': 'joystick'})

        assert again.maze == scene.maze
        assert [sprocket.rect.topleft for sprocket in again.sprockets] == [
            sprocket.rect.topleft for sprocket in scene.sprockets
        ]

    def test_the_maze_fills_the_screen_and_holds_sprockets(self, scene):
        assert (scene.maze.columns, scene.maze.rows) == (COLUMNS, ROWS)
        assert scene.sprockets
        assert all(not sprocket.collected for sprocket in scene.sprockets)

    def test_the_player_and_munchers_start_at_their_corners(self, scene):
        assert (scene.player.centre_x, scene.player.centre_y) == (GRID_SIZE * 2, GRID_SIZE * 2)
        assert [(muncher.centre_x, muncher.centre_y) for muncher in scene.munchers] == [
            (GRID_SIZE * (COLUMNS - 3), GRID_SIZE * (ROWS - 3)),
            (GRID_SIZE * 3, GRID_SIZE * (ROWS - 3)),
            (GRID_SIZE * (COLUMNS - 3), GRID_SIZE * 3),
        ]
        assert all(muncher.direction is Direction.RIGHT for muncher in scene.munchers)

    def test_a_given_sprite_group_is_used(self):
        if pygame.display.get_surface() is None:
            set_display_mode(size=SCREEN_SIZE)
        group = pygame.sprite.LayeredDirty()

        built = MrMuncherScene(options={'input_mode': 'joystick'}, groups=group)

        assert built.all_sprites is group
        assert built.player in group

    def test_the_scene_builds_without_options(self, scene):
        built = MrMuncherScene()

        assert built.actions is not None
        assert not built.win_text.visible

    def test_the_package_runs_the_games_main(self):
        assert mr_muncher.main is mr_muncher_game.main


class TestRendering:
    """Each frame is the black background with blue walls, then every sprite."""

    def test_walls_are_blue_and_open_cells_black(self, scene):
        screen = _rendered(scene)

        assert _rgb(screen, (GRID_SIZE // 2, GRID_SIZE // 2)) == WALL_COLOR
        # Row 4 and below: clear of the player, who starts at the top left
        open_x, open_y = _open_cell_centre(scene.maze, first_row=4)
        open_pixel = (int(open_x) - GRID_SIZE // 2 + 1, int(open_y) - GRID_SIZE // 2 + 1)
        assert _rgb(screen, open_pixel) == BLACK_RGB
        assert scene.rects is None

    def test_the_player_is_a_yellow_disc_drawn_at_its_centre(self, scene):
        _park_munchers(scene)
        _place(scene.player, x=60.7, y=70.2)
        screen = _rendered(scene)

        reference = pygame.Surface(SCREEN_SIZE)
        pygame.draw.circle(reference, PLAYER_COLOR, (60, 70), 8)
        for x in range(50, 71):
            for y in range(60, 81):
                is_disc_pixel = _rgb(reference, (x, y)) == PLAYER_COLOR
                assert (_rgb(screen, (x, y)) == PLAYER_COLOR) is is_disc_pixel, (x, y)

    def test_a_muncher_is_red_and_a_sprocket_grey_brown(self, scene):
        muncher = scene.munchers[0]
        sprocket = scene.sprockets[0]
        screen = _rendered(scene)

        assert _rgb(screen, (int(muncher.centre_x), int(muncher.centre_y))) == (255, 0, 0)
        assert _rgb(screen, (sprocket.centre_x, sprocket.centre_y)) == SPROCKET_COLOR
        # The rounded corner leaves the sprocket's corner pixel to the background
        assert _rgb(screen, sprocket.rect.topleft) == BLACK_RGB

    def test_a_collected_sprocket_is_not_drawn(self, scene):
        sprocket = scene.sprockets[0]
        sprocket.collected = True
        screen = _rendered(scene)

        assert _rgb(screen, (sprocket.centre_x, sprocket.centre_y)) == BLACK_RGB

    def test_the_score_is_drawn_in_yellow_in_the_top_left(self, scene):
        reference_font = pygame.font.Font(None, TEXT_FONT_SIZE)
        antialias = True
        expected = reference_font.render('Score: 0', antialias, TEXT_COLOR)

        assert pygame.image.tobytes(scene.score_text.image, 'RGBA') == pygame.image.tobytes(
            expected, 'RGBA'
        )
        assert scene.score_text.rect.topleft == (10, 10)


class TestPlayerMovement:
    """Held arrow keys (or D-pad buttons) move the player at its speed; walls block it."""

    def test_a_held_arrow_moves_the_player_at_its_speed(self, scene):
        _park_munchers(scene)
        start_x = scene.player.centre_x
        _press(scene, pygame.K_RIGHT)

        scene.dt_tick(0.5)

        assert scene.player.centre_x == pytest.approx(start_x + PLAYER_SPEED_PIXELS_PER_SECOND / 2)
        assert scene.player.rect.topleft == (
            int(scene.player.centre_x) - 8,
            int(scene.player.centre_y) - 8,
        )

    def test_the_original_per_frame_speeds_are_kept(self):
        assert pytest.approx(0.2) == PLAYER_SPEED_PIXELS_PER_SECOND * ORIGINAL_FRAME_SECONDS
        assert pytest.approx(0.1) == MUNCHER_SPEED_PIXELS_PER_SECOND * ORIGINAL_FRAME_SECONDS

    @pytest.mark.parametrize(
        ('held_keys', 'step'),
        [
            ((pygame.K_RIGHT, pygame.K_DOWN, pygame.K_LEFT, pygame.K_UP), (1, 0)),
            ((pygame.K_DOWN, pygame.K_LEFT, pygame.K_UP), (0, 1)),
            ((pygame.K_LEFT, pygame.K_UP), (-1, 0)),
            ((pygame.K_UP,), (0, -1)),
        ],
    )
    def test_right_beats_down_beats_left_beats_up(self, scene, held_keys, step):
        _park_munchers(scene)
        open_x, open_y = _open_cell_centre(scene.maze)
        _place(scene.player, x=open_x, y=open_y)
        for key in held_keys:
            _press(scene, key)

        scene.dt_tick(0.25)

        distance = PLAYER_SPEED_PIXELS_PER_SECOND * 0.25
        assert (scene.player.centre_x, scene.player.centre_y) == pytest.approx((
            open_x + step[0] * distance,
            open_y + step[1] * distance,
        ))

    def test_a_released_arrow_stops_the_player(self, scene):
        _park_munchers(scene)
        _press(scene, pygame.K_DOWN)
        scene.dt_tick(0.25)
        _release(scene, pygame.K_DOWN)
        stopped_at = (scene.player.centre_x, scene.player.centre_y)

        scene.dt_tick(0.25)

        assert (scene.player.centre_x, scene.player.centre_y) == stopped_at

    def test_a_wall_blocks_the_player(self, scene):
        _park_munchers(scene)
        _press(scene, pygame.K_LEFT)

        # A second's move would put the centre in the border wall (x < 20)
        scene.dt_tick(2.0)

        assert (scene.player.centre_x, scene.player.centre_y) == (GRID_SIZE * 2, GRID_SIZE * 2)

    def test_controller_dpad_buttons_move_the_player(self, scene):
        reset_streams(seed=TEST_SEED)
        scene = MrMuncherScene(options={'input_mode': 'controller'})
        _park_munchers(scene)
        start_x = scene.player.centre_x
        press = HashableEvent(
            pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_DPAD_RIGHT, instance_id=0
        )
        release = HashableEvent(
            pygame.CONTROLLERBUTTONUP, button=pygame.CONTROLLER_BUTTON_DPAD_RIGHT, instance_id=0
        )

        scene.on_controller_button_down_event(press)
        scene.dt_tick(0.25)
        scene.on_controller_button_up_event(release)
        scene.dt_tick(0.25)

        assert scene.player.centre_x == pytest.approx(start_x + PLAYER_SPEED_PIXELS_PER_SECOND / 4)

    def test_joystick_buttons_move_the_player(self, scene):
        _park_munchers(scene)
        start_y = scene.player.centre_y
        press = HashableEvent(
            pygame.JOYBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_DPAD_DOWN, instance_id=0
        )
        release = HashableEvent(
            pygame.JOYBUTTONUP, button=pygame.CONTROLLER_BUTTON_DPAD_DOWN, instance_id=0
        )

        scene.on_joy_button_down_event(press)
        scene.dt_tick(0.25)
        scene.on_joy_button_up_event(release)
        scene.dt_tick(0.25)

        assert scene.player.centre_y == pytest.approx(start_y + PLAYER_SPEED_PIXELS_PER_SECOND / 4)


class TestMunchers:
    """Munchers move on, turn a random way now and then, and turn when a wall blocks them."""

    @staticmethod
    def _stream_copy() -> random.Random:
        """Return a generator in the munchers' stream's current state (to predict its draws)."""
        copy = random.Random()
        copy.setstate(random_stream(MUNCHER_RANDOM_STREAM).getstate())
        return copy

    def test_a_muncher_moves_on_when_it_does_not_turn(self, scene):
        muncher = scene.munchers[1]
        open_x, open_y = _open_cell_centre(scene.maze)
        _place(muncher, x=open_x, y=open_y)
        predicted = self._stream_copy()

        # dt 0: no chance to turn (the draw is still made), and no distance to move
        muncher.wander(dt=0.0, maze=scene.maze)

        predicted.random()
        assert random_stream(MUNCHER_RANDOM_STREAM).getstate() == predicted.getstate()
        assert muncher.direction is Direction.RIGHT
        assert (muncher.centre_x, muncher.centre_y) == (open_x, open_y)

    def test_a_muncher_moves_at_its_speed(self, scene):
        muncher = scene.munchers[1]
        open_x, open_y = _open_cell_centre(scene.maze)
        _place(muncher, x=open_x, y=open_y)
        frame_seconds = ORIGINAL_FRAME_SECONDS
        predicted = self._stream_copy()
        turns = predicted.random() < MUNCHER_TURN_CHANCE_PER_ORIGINAL_FRAME
        direction = predicted.choice(list(Direction)) if turns else Direction.RIGHT

        muncher.wander(dt=frame_seconds, maze=scene.maze)

        step = MUNCHER_SPEED_PIXELS_PER_SECOND * frame_seconds
        assert (muncher.centre_x, muncher.centre_y) == pytest.approx((
            open_x + direction.value[0] * step,
            open_y + direction.value[1] * step,
        ))

    def test_a_long_frame_turns_the_muncher_first(self, scene):
        muncher = scene.munchers[1]
        # A maze of border walls only, so a 60 pixel move from the middle is never blocked
        scene.maze = build_maze(columns=COLUMNS, rows=ROWS, random_generator=FixedDraws(value=0.99))
        _place(muncher, x=400.0, y=240.0)
        seconds = 10.0
        turn_chance = 1.0 - (1.0 - MUNCHER_TURN_CHANCE_PER_ORIGINAL_FRAME) ** (
            seconds / ORIGINAL_FRAME_SECONDS
        )
        predicted = self._stream_copy()
        assert predicted.random() < turn_chance  # 1 - 0.98 ** 600: true for this seed
        turned_to = predicted.choice(list(Direction))

        muncher.wander(dt=seconds, maze=scene.maze)

        step = MUNCHER_SPEED_PIXELS_PER_SECOND * seconds
        assert muncher.direction is turned_to
        assert (muncher.centre_x, muncher.centre_y) == pytest.approx((
            400.0 + turned_to.value[0] * step,
            240.0 + turned_to.value[1] * step,
        ))
        assert random_stream(MUNCHER_RANDOM_STREAM).getstate() == predicted.getstate()

    def test_a_blocked_muncher_stays_and_turns_a_random_way(self, scene):
        muncher = scene.munchers[1]
        # Inside the left border wall: even a move of 0 pixels is blocked there
        _place(muncher, x=GRID_SIZE / 2, y=50.0)
        muncher.direction = Direction.LEFT
        predicted = self._stream_copy()
        predicted.random()  # The turn-chance draw: at dt 0 the chance is 0
        turned_to = predicted.choice(list(Direction))

        muncher.wander(dt=0.0, maze=scene.maze)

        assert (muncher.centre_x, muncher.centre_y) == (GRID_SIZE / 2, 50.0)
        assert muncher.direction is turned_to
        assert random_stream(MUNCHER_RANDOM_STREAM).getstate() == predicted.getstate()


class TestSprocketsAndCatches:
    """Touching a sprocket collects it; a muncher's touch starts the player over."""

    def test_touching_a_sprocket_collects_it_for_ten_points(self, scene):
        _park_munchers(scene)
        sprocket = scene.sprockets[0]
        _place(
            scene.player, x=sprocket.centre_x + SPROCKET_COLLECT_DISTANCE - 0.5, y=sprocket.centre_y
        )

        scene.dt_tick(0.0)

        assert sprocket.collected
        assert not sprocket.visible
        assert scene.score == SPROCKET_POINTS
        assert scene.score_text.text == f'Score: {SPROCKET_POINTS}'

    def test_a_sprocket_just_out_of_reach_is_not_collected(self, scene):
        _park_munchers(scene)
        sprocket = scene.sprockets[0]
        _place(scene.player, x=sprocket.centre_x + SPROCKET_COLLECT_DISTANCE, y=sprocket.centre_y)

        scene.dt_tick(0.0)

        assert not sprocket.collected
        assert scene.score == 0

    def test_a_collected_sprocket_scores_once(self, scene):
        _park_munchers(scene)
        sprocket = scene.sprockets[0]
        _place(scene.player, x=sprocket.centre_x, y=sprocket.centre_y)

        scene.dt_tick(0.0)
        scene.dt_tick(0.0)

        assert scene.score == SPROCKET_POINTS

    def test_a_munchers_touch_starts_the_player_over(self, scene):
        _park_munchers(scene)
        sprocket = scene.sprockets[0]
        _place(scene.player, x=sprocket.centre_x, y=sprocket.centre_y)
        scene.dt_tick(0.0)
        muncher = scene.munchers[0]
        _place(muncher, x=sprocket.centre_x + MUNCHER_CATCH_DISTANCE - 0.5, y=sprocket.centre_y)
        muncher_position = (muncher.centre_x, muncher.centre_y)

        scene._check_for_catch()

        assert (scene.player.centre_x, scene.player.centre_y) == (GRID_SIZE * 2, GRID_SIZE * 2)
        assert scene.player.rect.topleft == (GRID_SIZE * 2 - 8, GRID_SIZE * 2 - 8)
        assert scene.score == 0
        assert not any(each.collected for each in scene.sprockets)
        # The munchers stay where they are
        assert (muncher.centre_x, muncher.centre_y) == muncher_position

    def test_a_muncher_just_out_of_reach_does_not_catch(self, scene):
        _park_munchers(scene)
        _place(scene.player, x=100.0, y=100.0)
        _place(scene.munchers[0], x=100.0 + MUNCHER_CATCH_DISTANCE, y=100.0)

        scene._check_for_catch()

        assert (scene.player.centre_x, scene.player.centre_y) == (100.0, 100.0)

    def test_collecting_every_sprocket_shows_the_win_message(self, scene):
        _park_munchers(scene)
        for sprocket in scene.sprockets[1:]:
            sprocket.collected = True
        scene.dt_tick(0.0)
        assert not scene.has_won
        assert not scene.win_text.visible

        last = scene.sprockets[0]
        _place(scene.player, x=last.centre_x, y=last.centre_y)
        scene.dt_tick(0.0)

        assert scene.has_won
        assert scene.win_text.visible
        assert scene.win_text.text == WIN_MESSAGE
        assert scene.win_text.rect.topleft == (SCREEN_SIZE[0] // 2 - 150, SCREEN_SIZE[1] // 2)
        screen = _rendered(scene)
        text_area = scene.win_text.rect
        yellow_pixels = [
            (x, y)
            for x in range(text_area.left, text_area.right)
            for y in range(text_area.top, text_area.bottom)
            if _rgb(screen, (x, y)) == TEXT_COLOR
        ]
        assert yellow_pixels


class TestQuitKeys:
    """ESC and Q (by key position) end the game; other keys go to the base scene."""

    @pytest.mark.parametrize('key', [pygame.K_ESCAPE, pygame.K_q])
    def test_a_quit_key_ends_the_game(self, scene, key):
        _press(scene, key)

        assert scene.next_scene is None

    def test_another_key_leaves_the_game_running(self, scene):
        _press(scene, pygame.K_a)

        assert scene.next_scene is scene


def test_main_runs_the_game_through_the_engine(mocker, capsys):
    """main() starts Mr. Muncher in the engine: here a headless replay of the golden run.

    GoldenTraceEngine is the GameEngine without the SCALED display flag, which SDL's dummy
    video driver cannot honour; pygame.quit is patched because later tests on this worker
    need pygame (as tests/replay/replay_helpers.replay_through_engine does).
    """
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')
    mocker.patch.dict(os.environ)  # --headless sets the SDL driver variables
    mocker.patch.object(mr_muncher_game, 'GameEngine', GoldenTraceEngine)
    GoldenTraceSceneManager.install()
    try:
        with (
            command_line([
                '--log-level',
                'warning',
                '--replay-trace',
                str(GOLDEN_REPLAY_PATH),
                '--headless',
            ]),
            pytest.raises(SystemExit) as exit_info,
        ):
            mr_muncher_game.main()
    finally:
        pygame.event.clear()
        GoldenTraceSceneManager.uninstall()

    assert exit_info.value.code == ExitCode.SUCCESS
    assert 'Replay matched' in capsys.readouterr().out
