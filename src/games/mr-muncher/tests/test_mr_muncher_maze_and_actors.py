"""Tests for Mr. Muncher's parts: the maze, the levels, the actors, the pictures and the autopilot.

Real pygame and the real display (800x480, as the game runs by default); pictures are checked
by their pixels. The scene itself (flow, scoring, input) is tested in test_mr_muncher.py.
"""

from __future__ import annotations

import math
from collections import deque

import pygame
import pytest
from pydantic import ValidationError

from glitchygames.display_mode import set_display_mode
from glitchygames.randomness import random_stream, reset_streams
from mr_muncher import drawing, scenery
from mr_muncher.actors import (
    ACTOR_SIZE_TILES,
    AMBUSH_TILES_AHEAD,
    HOUSE_BOB_TILES,
    MUNCHER_RANDOM_STREAM,
    SHY_DISTANCE_TILES,
    ChaseSituation,
    MazeGeometry,
    Muncher,
    MuncherProfile,
    MuncherState,
    Personality,
    Player,
    chase_target,
    muncher_profiles,
    nearest_cell,
)
from mr_muncher.autopilot import (
    Autopilot,
    WayOn,
    corridor_distances,
    decision_point,
    shortest_way,
)
from mr_muncher.game import MrMuncherScene, Phase
from mr_muncher.levels import (
    BONUS_POINTS_BY_LEVEL,
    FRIGHTENED_FLASH_SECONDS,
    FRIGHTENED_SECONDS_LEVEL_ONE,
    FRIGHTENED_SECONDS_SHORTEST,
    LAST_RAMP_LEVEL,
    LATER_MODE_SCHEDULE,
    LEVEL_ONE_MODE_SCHEDULE,
    MUNCHER_SPEED_FRACTION_LEVEL_ONE,
    MUNCHER_SPEED_FRACTION_MOST,
    MUNCHER_SPEED_FRACTION_STEP_PER_LEVEL,
    PLAYER_SPEED_LEVEL_ONE,
    frightened_is_flashing,
    mode_phase_index,
    munchers_chase,
    settings_for_level,
)
from mr_muncher.maze import (
    DIRECTION_PREFERENCE,
    DOOR,
    HOUSE,
    MAZE_LAYOUT,
    SNACK,
    SPROCKET,
    TUNNEL,
    WALL,
    Direction,
    Maze,
    build_maze,
)
from mr_muncher.sounds import ALL_RECIPES, CRUNCH_RECIPES

SCREEN_SIZE = (800, 480)
TEST_SEED = 20261023
TILE_SIZE = 20
GEOMETRY = MazeGeometry(tile_size=TILE_SIZE, left=130, top=0)
TRANSPARENT = 0
SETTINGS = settings_for_level(1)

# A small maze with a dead end (column 3 of row 1) and a tunnel row, for rules the real maze
# never exercises
DEAD_END_LAYOUT = (
    '#######',
    '#P.#..#',
    '#.##..#',
    'T.....T',
    '#######',
)


@pytest.fixture(autouse=True)
def display():
    """The game's display: 800x480."""
    if not pygame.get_init():
        pygame.init()
    surface = pygame.display.get_surface()
    if surface is None or surface.get_size() != SCREEN_SIZE:
        set_display_mode(size=SCREEN_SIZE)


@pytest.fixture
def maze() -> Maze:
    """Mr. Muncher's maze."""
    return build_maze()


@pytest.fixture
def group() -> pygame.sprite.LayeredDirty:
    """A sprite group for actors made in a test."""
    return pygame.sprite.LayeredDirty()


def _player(maze: Maze, group) -> Player:
    return Player(maze=maze, geometry=GEOMETRY, layer=0, groups=group)


def _muncher(maze: Maze, group, *, index: int = 0) -> Muncher:
    return Muncher(
        profile=muncher_profiles(maze=maze)[index],
        maze=maze,
        geometry=GEOMETRY,
        layer=0,
        groups=group,
    )


def _situation(
    *,
    player_cell=(13, 18),
    facing=Direction.LEFT,
    chaser_cell=(13, 8),
    chasing=True,
) -> ChaseSituation:
    return ChaseSituation(
        player_cell=player_cell, player_facing=facing, chaser_cell=chaser_cell, chasing=chasing
    )


def _alpha(surface: pygame.Surface, position: tuple[int, int]) -> int:
    return surface.get_at(position).a


def _rgb(surface: pygame.Surface, position: tuple[int, int]) -> tuple[int, int, int]:
    color = surface.get_at(position)
    return (color.r, color.g, color.b)


def _colors(surface: pygame.Surface) -> set[tuple[int, int, int]]:
    """Every opaque colour in a picture."""
    width, height = surface.get_size()
    return {
        _rgb(surface, (x, y))
        for x in range(width)
        for y in range(height)
        if _alpha(surface, (x, y)) == 255
    }


class TestMazeLayout:
    """The hand-designed maze is fair: symmetric, no dead ends, connected, corridors one wide."""

    def test_the_layout_is_symmetric_left_to_right(self):
        for row in MAZE_LAYOUT:
            assert row == row[::-1]

    def test_every_corridor_tile_has_at_least_two_ways_on(self, maze):
        for row in range(maze.rows):
            for column in range(maze.columns):
                if maze.is_open_for_player(column=column, row=row):
                    ways = sum(
                        maze.is_open_for_player(
                            column=column + direction.step_x, row=row + direction.step_y
                        )
                        for direction in Direction
                    )
                    # The tile above the door also opens down, into the house (munchers only)
                    if (column, row) == maze.house_entrance:
                        ways += 1
                    assert ways >= 2, (column, row)

    def test_every_corridor_tile_can_be_reached(self, maze):
        open_tiles = {
            (column, row)
            for row in range(maze.rows)
            for column in range(maze.columns)
            if maze.is_open_for_player(column=column, row=row)
        }
        seen = {maze.player_start}
        queue = deque([maze.player_start])
        while queue:
            column, row = queue.popleft()
            for direction in Direction:
                neighbour = ((column + direction.step_x) % maze.columns, row + direction.step_y)
                if neighbour in open_tiles and neighbour not in seen:
                    seen.add(neighbour)
                    queue.append(neighbour)
        assert seen == open_tiles

    def test_corridors_are_one_tile_wide(self, maze):
        for row in range(maze.rows - 1):
            for column in range(maze.columns - 1):
                square = [
                    (column, row),
                    (column + 1, row),
                    (column, row + 1),
                    (column + 1, row + 1),
                ]
                assert not all(maze.is_open_for_player(column=c, row=r) for c, r in square)

    def test_the_maze_holds_sprockets_four_snacks_and_a_house(self, maze):
        assert len(maze.cells_holding(character=SPROCKET)) == 252
        assert maze.cells_holding(character=SNACK) == [(1, 1), (25, 1), (1, 18), (25, 18)]
        assert maze.door == (13, 9)
        assert maze.house_entrance == (13, 8)
        assert maze.house_centre == (13, 11)
        assert maze.tile(column=13, row=11) == HOUSE
        assert maze.player_start == (13, 18)


class TestMazeQuestions:
    """What the game asks the maze."""

    def test_rows_outside_the_maze_are_wall_and_columns_wrap(self, maze):
        assert maze.tile(column=5, row=-1) == WALL
        assert maze.tile(column=5, row=maze.rows) == WALL
        assert maze.tile(column=-1, row=4) == TUNNEL
        assert maze.tile(column=maze.columns, row=22) == TUNNEL

    def test_the_player_never_enters_walls_the_house_or_the_door(self, maze):
        assert not maze.is_open_for_player(column=0, row=0)
        assert not maze.is_open_for_player(column=13, row=11)
        assert maze.tile(column=13, row=9) == DOOR
        assert not maze.is_open_for_player(column=13, row=9)
        assert maze.is_open_for_player(column=13, row=18)
        assert maze.is_open_for_player(column=0, row=4)

    def test_the_tunnels_are_the_long_corridors_ends(self, maze):
        assert maze.is_tunnel(column=0, row=4)
        assert maze.is_tunnel(column=26, row=22)
        assert not maze.is_tunnel(column=1, row=4)

    @pytest.mark.parametrize(
        ('x', 'wrapped'), [(-0.6, 26.4), (-0.5, -0.5), (26.5, -0.5), (26.4, 26.4), (13.0, 13.0)]
    )
    def test_positions_past_half_a_tile_beyond_an_edge_wrap(self, maze, x, wrapped):
        assert maze.wrap_x(x) == pytest.approx(wrapped)

    def test_distance_is_measured_the_short_way_round_the_tunnel(self, maze):
        assert maze.tile_distance(first=(0, 4), second=(26, 4)) == pytest.approx(1.0)
        assert maze.tile_distance(first=(1, 1), second=(4, 5)) == pytest.approx(5.0)

    def test_a_layout_must_be_a_rectangle(self):
        with pytest.raises(ValidationError, match='same width'):
            Maze(layout=('###', '#P', '###'))

    @pytest.mark.parametrize('layout', [('#.#',), ('PP#',)])
    def test_a_layout_needs_exactly_one_player_start(self, layout):
        with pytest.raises(ValidationError, match='exactly one player start'):
            Maze(layout=layout)

    def test_directions_know_their_steps_and_opposites(self):
        assert (Direction.RIGHT.step_x, Direction.RIGHT.step_y) == (1, 0)
        assert (Direction.UP.step_x, Direction.UP.step_y) == (0, -1)
        assert {direction: direction.opposite for direction in Direction} == {
            Direction.UP: Direction.DOWN,
            Direction.DOWN: Direction.UP,
            Direction.LEFT: Direction.RIGHT,
            Direction.RIGHT: Direction.LEFT,
        }
        assert DIRECTION_PREFERENCE == (
            Direction.UP,
            Direction.LEFT,
            Direction.DOWN,
            Direction.RIGHT,
        )


class TestLevels:
    """Each level is faster and meaner, up to LAST_RAMP_LEVEL."""

    def test_level_one(self):
        settings = settings_for_level(1)
        assert settings.player_speed == pytest.approx(PLAYER_SPEED_LEVEL_ONE)
        assert settings.muncher_speed == pytest.approx(
            PLAYER_SPEED_LEVEL_ONE * MUNCHER_SPEED_FRACTION_LEVEL_ONE
        )
        assert settings.muncher_speed < settings.player_speed
        assert settings.frightened_speed < settings.muncher_speed
        assert settings.eyes_speed > settings.player_speed
        assert settings.hurry_speed > settings.muncher_speed
        assert settings.sugar_rush_speed > settings.player_speed
        assert settings.frightened_seconds == pytest.approx(FRIGHTENED_SECONDS_LEVEL_ONE)
        assert settings.mode_schedule == LEVEL_ONE_MODE_SCHEDULE
        assert settings.bonus_points == BONUS_POINTS_BY_LEVEL[0]

    def test_later_levels_are_faster_with_shorter_frights(self):
        first, second = settings_for_level(1), settings_for_level(2)
        assert second.player_speed > first.player_speed
        assert second.muncher_speed / second.player_speed > first.muncher_speed / first.player_speed
        assert second.frightened_seconds < first.frightened_seconds
        assert second.mode_schedule == LATER_MODE_SCHEDULE
        assert second.release_seconds < first.release_seconds

    def test_the_ramp_stops_and_frights_never_drop_below_the_shortest(self):
        last, much_later = settings_for_level(LAST_RAMP_LEVEL), settings_for_level(50)
        assert much_later.model_dump(exclude={'level'}) == last.model_dump(exclude={'level'})
        assert much_later.frightened_seconds == FRIGHTENED_SECONDS_SHORTEST
        ramped_fraction = min(
            MUNCHER_SPEED_FRACTION_MOST,
            MUNCHER_SPEED_FRACTION_LEVEL_ONE
            + MUNCHER_SPEED_FRACTION_STEP_PER_LEVEL * (LAST_RAMP_LEVEL - 1),
        )
        assert much_later.muncher_speed / much_later.player_speed == pytest.approx(ramped_fraction)
        assert much_later.bonus_points == BONUS_POINTS_BY_LEVEL[-1]

    def test_there_is_no_level_zero(self):
        with pytest.raises(ValueError, match='levels start at 1'):
            settings_for_level(0)

    def test_munchers_scatter_first_then_chase_and_finally_chase_for_good(self):
        schedule = (2.0, 3.0, 1.0)
        assert mode_phase_index(schedule=schedule, elapsed_seconds=0.0) == 0
        assert not munchers_chase(schedule=schedule, elapsed_seconds=1.9)
        assert munchers_chase(schedule=schedule, elapsed_seconds=2.0)
        assert not munchers_chase(schedule=schedule, elapsed_seconds=5.5)
        assert mode_phase_index(schedule=schedule, elapsed_seconds=6.0) == len(schedule)
        assert munchers_chase(schedule=schedule, elapsed_seconds=6.0)
        assert munchers_chase(schedule=(2.0, 3.0), elapsed_seconds=10.0)

    def test_frightened_munchers_flash_white_and_blue_at_the_end(self):
        assert not frightened_is_flashing(remaining_seconds=5.0, frightened_seconds=7.0)
        assert frightened_is_flashing(remaining_seconds=1.9, frightened_seconds=7.0)
        assert not frightened_is_flashing(remaining_seconds=1.7, frightened_seconds=7.0)
        # A fright shorter than the flash window flashes all the way
        assert frightened_is_flashing(remaining_seconds=0.9, frightened_seconds=1.0)
        assert pytest.approx(2.0) == FRIGHTENED_FLASH_SECONDS


class TestGeometryAndCells:
    """Tiles to pixels, and positions to tiles."""

    def test_a_tile_centre_in_pixels(self):
        assert GEOMETRY.pixel_centre(tile_x=0, tile_y=0) == (140.0, 10.0)
        assert GEOMETRY.pixel_centre(tile_x=13, tile_y=18.5) == (400.0, 380.0)

    def test_the_nearest_tile_rounds_halves_up_and_wraps(self, maze):
        assert nearest_cell(tile_x=12.5, tile_y=4.49, maze=maze) == (13, 4)
        assert nearest_cell(tile_x=-0.4, tile_y=4.0, maze=maze) == (0, 4)
        assert nearest_cell(tile_x=26.6, tile_y=4.0, maze=maze) == (0, 4)


class TestPlayerMovement:
    """The player moves centre to centre, turns where asked, and reverses at once."""

    def test_the_player_starts_on_its_tile_heading_left(self, maze, group):
        player = _player(maze, group)
        assert player.position == (13.0, 18.0)
        assert player.direction is Direction.LEFT
        assert player.wanted_direction is Direction.LEFT
        size = round(TILE_SIZE * ACTOR_SIZE_TILES)
        assert (player.world_x, player.world_y) == (400 - size / 2, 370 - size / 2)

    def test_it_walks_its_distance_and_lands_exactly_on_centres(self, maze, group):
        player = _player(maze, group)
        player.travel(distance=2.5)
        assert player.position == (10.5, 18.0)
        assert player.direction is Direction.LEFT
        player.travel(distance=0.5)
        assert player.tile_x == 10.0
        assert player.is_at_tile_centre

    def test_a_wall_stops_it_and_it_keeps_facing_its_way(self, maze, group):
        player = _player(maze, group)
        player.place_at(position=(1, 1))
        player.wanted_direction = Direction.UP
        player.travel(distance=1.0)
        assert player.position == (1.0, 1.0)
        assert player.direction is None
        assert player.facing is Direction.LEFT

    def test_a_direction_asked_early_is_taken_at_the_first_open_junction(self, maze, group):
        player = _player(maze, group)
        # Row 18 heading left: (12, 18) opens up (row 17 column 12)
        player.wanted_direction = Direction.UP
        player.travel(distance=0.5)
        assert player.position == (12.5, 18.0)
        player.travel(distance=1.0)
        assert player.position == (12.0, 17.5)
        assert player.facing is Direction.UP

    def test_a_blocked_wanted_direction_waits_while_it_goes_straight_on(self, maze, group):
        player = _player(maze, group)
        player.place_at(position=(7, 18))
        player.direction = Direction.LEFT
        player.wanted_direction = Direction.DOWN
        # (7, 19) is wall, (6, 19) is open: it turns down one tile on
        player.travel(distance=1.5)
        assert player.position == (6.0, 18.5)

    def test_reversing_is_immediate_between_centres(self, maze, group):
        player = _player(maze, group)
        player.travel(distance=0.3)
        player.wanted_direction = Direction.RIGHT
        player.travel(distance=0.2)
        assert player.position == pytest.approx((12.9, 18.0))
        assert player.facing is Direction.RIGHT

    def test_it_wraps_through_the_tunnel(self, maze, group):
        player = _player(maze, group)
        player.place_at(position=(1, 4))
        player.wanted_direction = Direction.LEFT
        player.travel(distance=1.4)
        assert player.position == pytest.approx((-0.4, 4.0))
        player.travel(distance=0.2)
        assert player.position == pytest.approx((26.4, 4.0))
        assert player.cell == (26, 4)
        player.travel(distance=0.4)
        assert player.position == (26.0, 4.0)

    def test_the_next_tile_ahead(self, maze, group):
        player = _player(maze, group)
        assert player.next_cell_ahead() == (13, 18)
        player.travel(distance=0.25)
        assert player.next_cell_ahead() == (12, 18)
        player.wanted_direction = Direction.RIGHT
        player.travel(distance=0.5)
        assert player.next_cell_ahead() == (14, 18)
        player.place_at(position=(12, 17))
        player.direction = Direction.DOWN
        player.tile_y = 17.25
        assert player.next_cell_ahead() == (12, 18)
        player.direction = Direction.UP
        assert player.next_cell_ahead() == (12, 17)
        player.tile_y = 17.0
        assert player.next_cell_ahead() == (12, 17)

    def test_reset_puts_it_back_for_a_new_life(self, maze, group):
        player = _player(maze, group)
        player.travel(distance=3.0)
        player.dying_progress = 0.5
        player.hidden = True
        player.wanted_direction = Direction.UP
        player.reset()
        assert player.position == (13.0, 18.0)
        assert player.dying_progress is None
        assert not player.hidden
        assert player.wanted_direction is Direction.LEFT


class TestPlayerPictures:
    """Mr. Muncher is a popcorn bucket: it chomps as it moves and spills when it is caught."""

    @staticmethod
    def _count(surface: pygame.Surface, color: tuple[int, int, int]) -> int:
        width, height = surface.get_size()
        return sum(
            _rgb(surface, (x, y)) == color and _alpha(surface, (x, y)) == 255
            for x in range(width)
            for y in range(height)
        )

    def test_it_is_a_striped_bucket_with_popcorn_and_a_face(self, maze, group):
        player = _player(maze, group)
        colors = _colors(player.image)
        for color in (
            drawing.BUCKET_RED,
            drawing.BUCKET_WHITE,
            drawing.POPCORN_COLOR,
            drawing.PUPIL_COLOR,
            drawing.MOUTH_COLOR,
        ):
            assert color in colors

    def test_the_mouth_opens_and_shuts_as_it_travels(self, maze, group):
        player = _player(maze, group)
        player.facing = Direction.DOWN  # The mouth moves no way sideways
        openings = []
        for step in range(8):
            player.travelled = step / 8
            player.pose()
            openings.append(self._count(player.image, drawing.MOUTH_COLOR))
        shut, narrow, half, wide = openings[:4]
        assert shut < narrow < half < wide
        assert openings[4:] == [wide, wide, half, narrow]

    def test_its_eyes_look_the_way_it_goes(self, maze, group):
        player = _player(maze, group)
        pupils = {}
        for looking in Direction:
            player.facing = looking
            player.pose()
            pupil_pixels = [
                (x, y)
                for x in range(player.picture_size)
                for y in range(player.picture_size)
                if _rgb(player.image, (x, y)) == drawing.PUPIL_COLOR
            ]
            pupils[looking] = (
                sum(x for x, _ in pupil_pixels) / len(pupil_pixels),
                sum(y for _, y in pupil_pixels) / len(pupil_pixels),
            )
        assert pupils[Direction.RIGHT][0] > pupils[Direction.LEFT][0]
        assert pupils[Direction.DOWN][1] > pupils[Direction.UP][1]

    def test_caught_it_sinks_and_spills_until_it_is_gone(self, maze, group):
        player = _player(maze, group)
        size = player.picture_size
        top_of_bucket = (size // 2, round(size * drawing.BUCKET_TOP_FRACTION) + 2)
        player.dying_progress = 0.0
        player.pose()
        assert _rgb(player.image, top_of_bucket) in {drawing.BUCKET_RED, drawing.BUCKET_WHITE}
        player.dying_progress = 0.75
        player.pose()
        assert _alpha(player.image, top_of_bucket) < 255
        assert drawing.BUCKET_RED in _colors(player.image)
        player.dying_progress = 1.0
        player.pose()
        assert _colors(player.image) == set()


class TestChaseTargets:
    """Each muncher hunts its own way."""

    def test_the_chaser_aims_at_the_player(self):
        assert chase_target(
            personality=Personality.CHASER, situation=_situation(), own_cell=(1, 1), corner=(0, 0)
        ) == (13, 18)

    def test_the_ambusher_aims_ahead_of_the_player(self):
        situation = _situation(facing=Direction.UP)
        assert chase_target(
            personality=Personality.AMBUSHER, situation=situation, own_cell=(1, 1), corner=(0, 0)
        ) == (13, 18 - AMBUSH_TILES_AHEAD)

    def test_the_flanker_aims_opposite_the_chaser(self):
        situation = _situation(player_cell=(10, 10), facing=Direction.RIGHT, chaser_cell=(8, 10))
        # Pivot two tiles ahead of the player: (12, 10); the chaser's offset from it, doubled
        assert chase_target(
            personality=Personality.FLANKER, situation=situation, own_cell=(1, 1), corner=(0, 0)
        ) == (16, 10)

    def test_the_shy_one_chases_from_afar_and_retreats_up_close(self):
        situation = _situation(player_cell=(13, 18))
        far = (13, 18 - math.ceil(SHY_DISTANCE_TILES) - 1)
        near = (13, 16)
        assert chase_target(
            personality=Personality.SHY, situation=situation, own_cell=far, corner=(0, 24)
        ) == (13, 18)
        assert chase_target(
            personality=Personality.SHY, situation=situation, own_cell=near, corner=(0, 24)
        ) == (0, 24)

    def test_the_four_munchers(self, maze):
        profiles = muncher_profiles(maze=maze)
        assert [profile.name for profile in profiles] == [
            'Chomper',
            'Snapper',
            'Gnasher',
            'Nibbles',
        ]
        assert [profile.personality for profile in profiles] == list(Personality)
        assert [profile.starts_outside for profile in profiles] == [True, False, False, False]
        assert len({profile.color for profile in profiles}) == len(profiles)
        assert profiles[0].seat == maze.house_entrance
        assert {profile.seat[1] for profile in profiles[1:]} == {maze.house_centre[1]}


class TestMuncherStates:
    """Munchers wait, walk out, roam, and their eyes go home."""

    def test_the_chomper_starts_roaming_and_the_others_wait(self, maze, group):
        chomper, snapper = _muncher(maze, group, index=0), _muncher(maze, group, index=1)
        assert chomper.state is MuncherState.ROAMING
        assert chomper.can_touch_player
        assert snapper.state is MuncherState.WAITING
        assert not snapper.can_touch_player

    def test_a_waiting_muncher_bobs_on_its_seat(self, maze, group):
        snapper = _muncher(maze, group, index=1)
        seat_row = snapper.profile.seat[1]
        snapper.travel(distance=HOUSE_BOB_TILES + 0.1, situation=_situation())
        assert snapper.tile_y == pytest.approx(seat_row - HOUSE_BOB_TILES)
        assert snapper.looking is Direction.DOWN
        snapper.travel(distance=2 * HOUSE_BOB_TILES + 0.1, situation=_situation())
        assert snapper.tile_y == pytest.approx(seat_row + HOUSE_BOB_TILES)
        assert snapper.looking is Direction.UP

    def test_a_released_muncher_walks_across_then_up_and_out(self, maze, group):
        gnasher = _muncher(maze, group, index=2)  # Two tiles left of the door's column
        gnasher.state = MuncherState.LEAVING
        gnasher.travel(distance=1.0, situation=_situation())
        assert gnasher.position == (12.0, 11.0)
        assert gnasher.looking is Direction.RIGHT
        gnasher.travel(distance=2.0, situation=_situation())
        assert gnasher.position == (13.0, 10.0)
        assert gnasher.looking is Direction.UP
        gnasher.travel(distance=5.0, situation=_situation())
        assert gnasher.position == maze.house_entrance
        assert gnasher.state is MuncherState.ROAMING

    def test_a_leaving_muncher_level_with_the_door_only_walks_across(self, maze, group):
        snapper = _muncher(maze, group, index=1)
        snapper.state = MuncherState.LEAVING
        snapper.place_at(position=(12.75, 8))
        snapper.travel(distance=0.5, situation=_situation())
        assert snapper.position == maze.house_entrance
        assert snapper.state is MuncherState.ROAMING

    def test_eyes_go_home_down_into_the_house_and_walk_out_again(self, maze, group):
        chomper = _muncher(maze, group)
        chomper.place_at(position=(9, 8))
        chomper.direction = Direction.RIGHT
        chomper.state = MuncherState.EATEN
        chomper.travel(distance=10.0, situation=_situation())
        assert chomper.position == maze.house_entrance
        assert chomper.state is MuncherState.ENTERING
        chomper.travel(distance=1.0, situation=_situation())
        assert chomper.position == (13.0, 9.0)
        chomper.frightened = True
        chomper.travel(distance=5.0, situation=_situation())
        assert chomper.position == maze.house_centre
        assert chomper.state is MuncherState.LEAVING
        assert not chomper.frightened

    def test_scattering_munchers_head_for_their_corners(self, maze, group):
        chomper = _muncher(maze, group)
        chomper.direction = Direction.UP  # As if just out of the house: either way is open
        chomper.travel(distance=0.5, situation=_situation(chasing=False))
        assert chomper.target == chomper.profile.corner
        assert chomper.direction is Direction.RIGHT  # Its corner is top right

    def test_chasing_munchers_head_for_their_prey(self, maze, group):
        chomper = _muncher(maze, group)
        chomper.travel(distance=0.5, situation=_situation(player_cell=(1, 8)))
        assert chomper.target == (1, 8)
        assert chomper.direction is Direction.LEFT

    def test_a_muncher_never_turns_back_by_itself(self, maze, group):
        chomper = _muncher(maze, group)
        chomper.place_at(position=(12, 8))
        chomper.direction = Direction.RIGHT
        # Its target is behind it, but going back is not an option: up is the nearer way on
        chomper.travel(distance=0.5, situation=_situation(player_cell=(9, 8)))
        assert chomper.direction is Direction.UP

    def test_a_mode_change_turns_it_round_at_once(self, maze, group):
        chomper = _muncher(maze, group)
        chomper.place_at(position=(12.5, 8))
        chomper.direction = Direction.RIGHT
        chomper.reverse_soon = True
        chomper.travel(distance=0.25, situation=_situation())
        assert chomper.position == (12.25, 8.0)
        assert not chomper.reverse_soon

    def test_a_frightened_muncher_turns_at_random_from_the_seeded_stream(self, maze, group):
        reset_streams(seed=TEST_SEED)
        expected_stream = random_stream(MUNCHER_RANDOM_STREAM)
        state = expected_stream.getstate()
        chomper = _muncher(maze, group)
        chomper.place_at(position=(12, 8))
        chomper.direction = Direction.LEFT
        chomper.frightened = True
        chomper.travel(distance=0.25, situation=_situation())
        expected_stream.setstate(state)
        options = [Direction.UP, Direction.LEFT]  # From (12, 8) heading left: no way back
        assert chomper.direction is expected_stream.choice(options)
        assert chomper.target is None

    def test_at_a_dead_end_the_only_way_on_is_back(self, group):
        maze = Maze(layout=DEAD_END_LAYOUT)
        profile = MuncherProfile(
            name='Tester',
            color=(1, 2, 3),
            personality=Personality.CHASER,
            corner=(0, 0),
            seat=(2, 1),
            starts_outside=True,
        )
        muncher = Muncher(profile=profile, maze=maze, geometry=GEOMETRY, layer=0, groups=group)
        muncher.direction = Direction.RIGHT
        muncher.travel(distance=0.5, situation=_situation(player_cell=(5, 3)))
        assert muncher.direction is Direction.LEFT
        assert muncher.position == (1.5, 1.0)

    def test_reset_seats_it_again(self, maze, group):
        snapper = _muncher(maze, group, index=1)
        snapper.state = MuncherState.EATEN
        snapper.frightened = True
        snapper.reverse_soon = True
        snapper.hidden = True
        snapper.place_at(position=(1, 1))
        snapper.reset()
        assert snapper.position == snapper.profile.seat
        assert snapper.state is MuncherState.WAITING
        assert not (snapper.frightened or snapper.reverse_soon or snapper.hidden)


class TestMuncherSpeeds:
    """How fast a muncher goes depends on what it is doing and where."""

    def test_speeds(self, maze, group):
        chomper = _muncher(maze, group)
        assert chomper.speed(settings=SETTINGS, hurrying=False) == SETTINGS.muncher_speed
        assert chomper.speed(settings=SETTINGS, hurrying=True) == SETTINGS.hurry_speed
        chomper.frightened = True
        assert chomper.speed(settings=SETTINGS, hurrying=True) == SETTINGS.frightened_speed
        chomper.place_at(position=(0, 4))
        assert chomper.speed(settings=SETTINGS, hurrying=False) == SETTINGS.tunnel_speed
        chomper.state = MuncherState.EATEN
        assert chomper.speed(settings=SETTINGS, hurrying=False) == SETTINGS.eyes_speed
        chomper.state = MuncherState.LEAVING
        assert chomper.speed(settings=SETTINGS, hurrying=False) == SETTINGS.house_speed

    def test_only_the_chaser_hurries(self, maze, group):
        snapper = _muncher(maze, group, index=1)
        snapper.state = MuncherState.ROAMING
        snapper.place_at(position=(1, 1))
        assert snapper.speed(settings=SETTINGS, hurrying=True) == SETTINGS.muncher_speed


class TestMuncherPictures:
    """Munchers are spiky fuzzballs looking their way; frightened, dull blue (white at the end).

    An eaten muncher is its eyes in a faint ring of its colour.
    """

    def test_its_body_colour_and_eyes(self, maze, group):
        chomper = _muncher(maze, group)
        chomper.pose(game_time=0.0, flashing=False)
        colors = _colors(chomper.image)
        assert chomper.profile.color in colors
        assert drawing.EYE_WHITE_COLOR in colors
        left_image = chomper.image
        chomper.looking = Direction.RIGHT
        chomper.pose(game_time=0.0, flashing=False)
        assert chomper.image is not left_image

    def test_the_skirt_waves_with_game_time(self, maze, group):
        chomper = _muncher(maze, group)
        chomper.pose(game_time=0.0, flashing=False)
        first = chomper.image
        chomper.pose(game_time=0.2, flashing=False)
        assert chomper.image is not first

    def test_frightened_and_flashing(self, maze, group):
        chomper = _muncher(maze, group)
        chomper.frightened = True
        chomper.pose(game_time=0.0, flashing=False)
        assert drawing.FRIGHTENED_COLOR in _colors(chomper.image)
        chomper.pose(game_time=0.0, flashing=True)
        assert drawing.FLASHING_COLOR in _colors(chomper.image)

    def test_eaten_munchers_are_only_eyes(self, maze, group):
        chomper = _muncher(maze, group)
        chomper.state = MuncherState.EATEN
        chomper.pose(game_time=0.0, flashing=False)
        colors = _colors(chomper.image)
        assert drawing.EYE_WHITE_COLOR in colors
        assert chomper.profile.color not in colors


class TestPictures:
    """The maze, sprockets, the bonus and the side panels."""

    def test_the_maze_has_black_corridors_and_edged_walls(self, maze):
        picture = drawing.maze_picture(layout=maze.layout, tile_size=TILE_SIZE)
        assert picture.get_size() == (maze.columns * TILE_SIZE, maze.rows * TILE_SIZE)
        assert _rgb(picture, (13 * TILE_SIZE + 10, 18 * TILE_SIZE + 10)) == drawing.CORRIDOR_COLOR
        # Inside the block of rows 2 and 3, columns 2 to 5
        assert _rgb(picture, (4 * TILE_SIZE, 3 * TILE_SIZE)) == drawing.WALL_FILL_COLOR
        assert drawing.WALL_EDGE_COLOR in _colors(picture)
        door_x, door_y = 13 * TILE_SIZE + 10, 9 * TILE_SIZE + 10
        assert _rgb(picture, (door_x, door_y)) == drawing.DOOR_COLOR

    def test_the_flashing_maze_has_white_edges(self, maze):
        picture = drawing.maze_picture(layout=maze.layout, tile_size=TILE_SIZE, flashing=True)
        assert drawing.WALL_FLASH_EDGE_COLOR in _colors(picture)
        assert _rgb(picture, (4 * TILE_SIZE, 3 * TILE_SIZE)) == drawing.WALL_FLASH_FILL_COLOR

    def test_sprockets_and_snacks(self):
        sprocket = drawing.sprocket_picture(tile_size=TILE_SIZE)
        assert _rgb(sprocket, (10, 10)) == drawing.SPROCKET_COLOR
        assert _alpha(sprocket, (2, 2)) == TRANSPARENT
        lit = drawing.snack_picture(tile_size=TILE_SIZE, lit=True)
        assert lit.get_size() == (30, 30)
        assert drawing.SNACK_COLOR in _colors(lit)
        assert drawing.SNACK_WRAPPER_COLOR in _colors(lit)
        # Its glow is faint (not opaque); the dim twinkle has none, but still a candy
        assert 0 < _alpha(lit, (15, 4)) < 255
        dim = drawing.snack_picture(tile_size=TILE_SIZE, lit=False)
        assert _alpha(dim, (15, 4)) == TRANSPARENT
        assert drawing.SNACK_COLOR in _colors(dim)

    def test_the_bonus_reel_has_holes(self):
        reel = drawing.bonus_reel_picture(size=26)
        assert _rgb(reel, (13, 13)) == drawing.REEL_RIM_COLOR  # Its hub
        hole_y = round(13 - (13 - drawing.SUPERSAMPLE / drawing.SUPERSAMPLE) * 0.5)
        assert _alpha(reel, (13, hole_y)) < 255
        assert drawing.REEL_COLOR in _colors(reel)

    @pytest.mark.parametrize('holes_on_left', [True, False])
    def test_the_side_panels_are_film_strip_edges(self, holes_on_left):
        panel = drawing.film_strip_panel(width=130, height=480, holes_on_left=holes_on_left)
        hole_x = drawing.SPROCKET_HOLE_MARGIN + drawing.SPROCKET_HOLE_WIDTH // 2
        hole_x = hole_x if holes_on_left else 130 - hole_x
        assert (
            _rgb(panel, (hole_x, drawing.SPROCKET_HOLE_SPACING // 2)) == drawing.SPROCKET_HOLE_COLOR
        )
        assert _rgb(panel, (65, 5)) == drawing.FILM_COLOR


class TestScenery:
    """Text helpers and the still sprites."""

    def test_a_fitted_font_shrinks_until_its_texts_fit(self):
        font = scenery.fitted_font(bold=True, texts=('MUNCHER',), width=96, largest=20)
        assert font.size('MUNCHER')[0] <= 96
        assert scenery.bundled_font(bold=True, size=font.get_height()) is not font
        bigger = scenery.fitted_font(bold=True, texts=('MUNCHER',), width=200, largest=20)
        assert bigger.size('MUNCHER')[0] > font.size('MUNCHER')[0]

    def test_a_fitted_font_stops_at_the_smallest_size(self):
        font = scenery.fitted_font(bold=False, texts=('far too wide',), width=1, largest=12)
        assert font.size('x') == scenery.bundled_font(bold=False, size=8).size('x')

    def test_rendered_text_is_drawn_in_its_colour(self):
        line = scenery.render_text(
            font=scenery.bundled_font(bold=True, size=20), text='#', color=(255, 0, 0)
        )
        assert (255, 0, 0) in _colors(line)

    def test_a_sprocket_is_eaten_and_a_snack_twinkles(self, maze, group):
        sprocket = scenery.Sprocket(
            cell=(1, 1), is_snack=False, geometry=GEOMETRY, layer=0, groups=group
        )
        assert sprocket.rect.center == (160, 30)
        image = sprocket.image
        sprocket.pose(game_time=0.3)
        assert sprocket.image is image
        assert not sprocket.eaten
        sprocket.eat()
        assert sprocket.eaten
        snack = scenery.Sprocket(
            cell=(1, 1), is_snack=True, geometry=GEOMETRY, layer=0, groups=group
        )
        snack.pose(game_time=0.0)
        lit = snack.image
        snack.pose(game_time=scenery.SNACK_TWINKLE_SECONDS)
        assert snack.image is not lit
        assert _colors(snack.image)

    def test_a_picture_stays_centred_on_its_point(self, group):
        picture = scenery.Picture(
            image=pygame.Surface((10, 4)), centre=(100, 50), layer=0, name='Test', groups=group
        )
        assert picture.rect.center == (100, 50)
        picture.change_image(image=pygame.Surface((30, 8)))
        assert picture.rect.size == (30, 8)
        assert picture.rect.center == (100, 50)
        picture.move_to(centre=(20, 20))
        assert picture.rect.center == (20, 20)

    def test_a_side_panel_draws_its_items_on_its_text_column(self, group):
        panel = scenery.SidePanel(
            area=pygame.Rect(0, 0, 130, 480), holes_on_left=True, layer=0, groups=group
        )
        assert panel.contents == ()
        dot = pygame.Surface((4, 4), pygame.SRCALPHA)
        dot.fill((255, 0, 0, 255))
        panel.draw(contents=('red dot',), items=((dot, 100),))
        assert panel.contents == ('red dot',)
        assert _rgb(panel.image, (panel.text_centre_x, 101)) == (255, 0, 0)
        right = scenery.SidePanel(
            area=pygame.Rect(670, 0, 130, 480), holes_on_left=False, layer=0, groups=group
        )
        assert right.text_centre_x < panel.text_centre_x


class TestSounds:
    """Every recipe renders; eating alternates two popcorn crunches."""

    @pytest.mark.parametrize('recipe', ALL_RECIPES, ids=lambda recipe: recipe.name)
    def test_every_recipe_renders(self, recipe):
        samples = recipe.render(sample_rate=22050)
        assert len(samples) > 0
        assert abs(samples).max() == pytest.approx(recipe.peak)

    def test_eating_crunches_two_ways(self):
        assert [recipe.name for recipe in CRUNCH_RECIPES] == ['crunch_one', 'crunch_two']


class TestAutopilot:
    """The autopilot eats, avoids munchers, hunts blue ones, and can walk into one on purpose."""

    @pytest.fixture
    def scene(self, tmp_path, mocker):
        mocker.patch(
            'glitchygames.state.manager.get_save_directory',
            side_effect=lambda app_name: tmp_path / app_name,
        )
        reset_streams(seed=TEST_SEED)
        scene = MrMuncherScene(options={'input_mode': 'joystick'})
        scene._start_playing()
        return scene

    def test_distances_along_the_corridors(self, maze):
        distances = corridor_distances(maze=maze, sources=[(13, 18)])
        assert distances[13, 18] == 0
        assert distances[12, 18] == 1
        assert distances[1, 1] > 0
        limited = corridor_distances(maze=maze, sources=[(13, 18)], allowed={(12, 18)})
        assert set(limited) == {(13, 18), (12, 18)}

    def test_the_shortest_way_to_a_goal(self):
        left = WayOn(direction=Direction.LEFT, reach={(1, 1): 5}, territory={(1, 1): 5})
        right = WayOn(direction=Direction.RIGHT, reach={(1, 1): 3}, territory={})
        assert shortest_way(ways=[left, right], goals={(1, 1)}, safely=True) is Direction.LEFT
        assert shortest_way(ways=[left, right], goals={(1, 1)}, safely=False) is Direction.RIGHT
        assert shortest_way(ways=[left, right], goals={(9, 9)}, safely=False) is None

    def test_it_decides_at_the_next_tile_or_the_one_after_when_too_close(self, scene):
        player = scene.player
        # On its start, already heading left: the decision is at the next tile
        assert decision_point(scene=scene) == ((12, 18), Direction.LEFT)
        player.direction = None
        assert decision_point(scene=scene) == ((13, 18), None)
        player.direction = Direction.LEFT
        player.tile_x = 12.5
        assert decision_point(scene=scene) == ((12, 18), Direction.LEFT)
        # Too close to (12, 18) for a key to count there: the wanted way on (up) is settled
        player.tile_x = 12.1
        player.wanted_direction = Direction.UP
        assert decision_point(scene=scene) == ((12, 17), Direction.UP)
        # A blocked wanted way: straight on
        player.wanted_direction = Direction.DOWN
        assert decision_point(scene=scene) == ((11, 18), Direction.LEFT)
        # Against a wall, with nowhere open: it stops at the tile
        player.place_at(position=(1, 1))
        player.direction = Direction.UP
        player.tile_y = 1.05
        player.wanted_direction = Direction.LEFT
        assert decision_point(scene=scene) == ((1, 1), Direction.UP)

    def test_it_heads_for_the_nearest_sprocket(self, scene):
        # It decides at (12, 18), whose sprocket neighbours lie up and left
        assert Autopilot().choose_direction(scene=scene) in {Direction.UP, Direction.LEFT}
        for sprocket in scene.sprockets.values():
            sprocket.eat()
        scene.sprockets[3, 1].visible = 1
        scene.player.place_at(position=(1, 4))
        assert Autopilot().choose_direction(scene=scene) is Direction.UP

    def test_it_hunts_a_frightened_muncher_it_can_catch(self, scene):
        chomper = scene.munchers[0]
        chomper.place_at(position=(9, 18))
        chomper.frightened = True
        scene.frightened_seconds_left = 5.0
        scene.player.place_at(position=(13, 18))
        for cell in ((12, 18), (11, 18), (10, 18)):
            scene.sprockets[cell].eat()
        assert Autopilot().choose_direction(scene=scene) is Direction.LEFT

    def test_it_goes_for_the_bonus(self, scene):
        scene.bonus.visible = 1
        scene.player.place_at(position=(13, 14))
        scene.player.place_at(position=(17, 14))
        assert Autopilot().choose_direction(scene=scene) is Direction.LEFT

    def test_it_takes_a_snack_when_a_muncher_is_close(self, scene):
        scene.player.place_at(position=(1, 5))
        chomper = scene.munchers[0]
        chomper.place_at(position=(6, 9))
        chomper.direction = Direction.UP
        assert Autopilot().choose_direction(scene=scene) is Direction.UP

    def test_it_avoids_a_muncher_in_its_way(self, scene):
        scene.player.place_at(position=(13, 18))
        chomper = scene.munchers[0]
        chomper.place_at(position=(10, 18))
        chomper.direction = Direction.RIGHT
        assert Autopilot().choose_direction(scene=scene) is Direction.RIGHT

    def test_trapped_it_runs_for_the_roomiest_way(self, scene):
        # Munchers close in from both sides of the bottom corridor
        scene.player.place_at(position=(5, 22))
        scene.player.direction = Direction.RIGHT
        for muncher, position, heading in zip(
            scene.munchers[:2], [(2, 22), (8, 22)], [Direction.RIGHT, Direction.LEFT], strict=True
        ):
            muncher.state = MuncherState.ROAMING
            muncher.place_at(position=position)
            muncher.direction = heading
        direction = Autopilot().choose_direction(scene=scene)
        assert direction in {Direction.LEFT, Direction.RIGHT}

    def test_with_nothing_left_to_eat_it_keeps_to_the_roomiest_way(self, scene):
        for sprocket in scene.sprockets.values():
            sprocket.eat()
        assert Autopilot().choose_direction(scene=scene) in set(Direction)

    def test_it_walks_into_a_muncher_once_when_asked(self, scene):
        autopilot = Autopilot(seek_capture_after_seconds=0.0)
        chomper = scene.munchers[0]
        chomper.place_at(position=(9, 18))
        chomper.direction = Direction.RIGHT
        assert autopilot.choose_direction(scene=scene) is Direction.LEFT
        scene.phase = Phase.DYING
        autopilot.choose_direction(scene=scene)
        assert autopilot.has_been_caught
        scene.phase = Phase.PLAYING
        # Caught once, it plays on: away from the muncher, up to the sprockets
        assert autopilot.choose_direction(scene=scene) is Direction.UP

    def test_it_waits_before_seeking_capture(self, scene):
        autopilot = Autopilot(seek_capture_after_seconds=60.0)
        assert not autopilot._is_seeking_capture(scene=scene)

    def test_on_a_tile_with_no_way_on_it_says_nothing(self, scene):
        scene.player.place_at(position=(0, 0))
        assert Autopilot().choose_direction(scene=scene) is None
