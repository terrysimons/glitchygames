"""How each level plays: speeds, how long munchers stay frightened, their mode schedule, bonuses.

Every level is a little faster and meaner than the one before, until level ``LAST_RAMP_LEVEL``,
after which levels stay the same. Speeds are in tiles per second (the game scales tiles to the
screen), times in seconds of game time.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict

# The level at which the ramp stops: every later level plays like this one
LAST_RAMP_LEVEL = 8

# The player's speed on level 1, and how much faster each level is (up to LAST_RAMP_LEVEL)
PLAYER_SPEED_LEVEL_ONE = 7.5
PLAYER_SPEED_STEP_PER_LEVEL = 0.15
# Munchers run at this fraction of the player's speed on level 1, rising per level to the most
MUNCHER_SPEED_FRACTION_LEVEL_ONE = 0.82
MUNCHER_SPEED_FRACTION_STEP_PER_LEVEL = 0.018
MUNCHER_SPEED_FRACTION_MOST = 0.95
# Fractions of the player's speed for frightened munchers, munchers in the tunnel, munchers
# moving in or out of the house, and the eyes of an eaten muncher going home
FRIGHTENED_SPEED_FRACTION = 0.55
TUNNEL_SPEED_FRACTION = 0.50
HOUSE_SPEED_FRACTION = 0.45
EYES_SPEED_FRACTION = 2.0
# The player is this much faster while munchers are frightened
SUGAR_RUSH_SPEED_FACTOR = 1.1
# The red muncher speeds up by this factor once few sprockets remain ("in a hurry")
HURRY_SPEED_FACTOR = 1.08
HURRY_SPROCKETS_LEVEL_ONE = 20
HURRY_SPROCKETS_STEP_PER_LEVEL = 5

# How long munchers stay frightened after a snack: shorter each level, never below the
# shortest; they flash white for the last FRIGHTENED_FLASH_SECONDS (or all of it, when shorter)
FRIGHTENED_SECONDS_LEVEL_ONE = 8.0
FRIGHTENED_SECONDS_STEP_PER_LEVEL = 0.9
FRIGHTENED_SECONDS_SHORTEST = 2.0
FRIGHTENED_FLASH_SECONDS = 2.0

# The munchers' mode schedule: scatter, chase, scatter, chase, ... (seconds each); the last
# chase never ends. Level 1 gives the player longer breathers than later levels.
LEVEL_ONE_MODE_SCHEDULE: tuple[float, ...] = (9.0, 15.0, 9.0, 15.0, 7.0, 20.0, 5.0)
LATER_MODE_SCHEDULE: tuple[float, ...] = (5.0, 20.0, 5.0, 20.0, 3.0, 30.0, 1.0)

# Seconds after a life starts at which each muncher in the house leaves it, in house order
# (the red muncher starts outside); level 1 lets them out slower
LEVEL_ONE_RELEASE_SECONDS: tuple[float, ...] = (0.5, 4.0, 8.0)
LATER_RELEASE_SECONDS: tuple[float, ...] = (0.5, 2.5, 5.0)

# The bonus reel's points on each level (the last applies to every later level)
BONUS_POINTS_BY_LEVEL: tuple[int, ...] = (100, 300, 500, 700, 1000, 2000, 3000, 5000)


class LevelSettings(BaseModel):
    """Everything that changes from level to level.

    Attributes:
        level: The level number (1 is the first).
        player_speed: The player's speed, in tiles per second.
        sugar_rush_speed: The player's speed while munchers are frightened.
        muncher_speed: A muncher's speed in the open maze.
        frightened_speed: A frightened muncher's speed.
        tunnel_speed: A muncher's speed in the tunnel.
        house_speed: A muncher's speed moving in or out of the house.
        eyes_speed: The speed of an eaten muncher's eyes going home.
        hurry_speed: The red muncher's speed once ``hurry_sprockets`` or fewer sprockets remain.
        hurry_sprockets: How few sprockets left make the red muncher hurry.
        frightened_seconds: How long a snack frightens the munchers.
        mode_schedule: Seconds of scatter, chase, scatter, ...; the chase after the last never
            ends.
        release_seconds: When each muncher in the house leaves, in seconds after a life starts.
        bonus_points: What the bonus reel is worth.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    level: int
    player_speed: float
    sugar_rush_speed: float
    muncher_speed: float
    frightened_speed: float
    tunnel_speed: float
    house_speed: float
    eyes_speed: float
    hurry_speed: float
    hurry_sprockets: int
    frightened_seconds: float
    mode_schedule: tuple[float, ...]
    release_seconds: tuple[float, ...]
    bonus_points: int


def settings_for_level(level: int) -> LevelSettings:
    """Return how a level plays.

    Args:
        level: The level number, 1 or more.

    Returns:
        The level's settings.

    Raises:
        ValueError: If the level is below 1.

    """
    if level < 1:
        message = f'levels start at 1, got {level}'
        raise ValueError(message)
    steps = min(level, LAST_RAMP_LEVEL) - 1
    player_speed = PLAYER_SPEED_LEVEL_ONE + PLAYER_SPEED_STEP_PER_LEVEL * steps
    muncher_speed = player_speed * min(
        MUNCHER_SPEED_FRACTION_MOST,
        MUNCHER_SPEED_FRACTION_LEVEL_ONE + MUNCHER_SPEED_FRACTION_STEP_PER_LEVEL * steps,
    )
    is_level_one = level == 1
    return LevelSettings(
        level=level,
        player_speed=player_speed,
        sugar_rush_speed=player_speed * SUGAR_RUSH_SPEED_FACTOR,
        muncher_speed=muncher_speed,
        frightened_speed=player_speed * FRIGHTENED_SPEED_FRACTION,
        tunnel_speed=player_speed * TUNNEL_SPEED_FRACTION,
        house_speed=player_speed * HOUSE_SPEED_FRACTION,
        eyes_speed=player_speed * EYES_SPEED_FRACTION,
        hurry_speed=muncher_speed * HURRY_SPEED_FACTOR,
        hurry_sprockets=HURRY_SPROCKETS_LEVEL_ONE + HURRY_SPROCKETS_STEP_PER_LEVEL * steps,
        frightened_seconds=max(
            FRIGHTENED_SECONDS_SHORTEST,
            FRIGHTENED_SECONDS_LEVEL_ONE - FRIGHTENED_SECONDS_STEP_PER_LEVEL * steps,
        ),
        mode_schedule=LEVEL_ONE_MODE_SCHEDULE if is_level_one else LATER_MODE_SCHEDULE,
        release_seconds=LEVEL_ONE_RELEASE_SECONDS if is_level_one else LATER_RELEASE_SECONDS,
        bonus_points=BONUS_POINTS_BY_LEVEL[min(level, len(BONUS_POINTS_BY_LEVEL)) - 1],
    )


def mode_phase_index(*, schedule: tuple[float, ...], elapsed_seconds: float) -> int:
    """Return which phase of the schedule a mode time falls in (len(schedule) after the last).

    Two mode times in different phases mean the munchers changed mode between them.

    Args:
        schedule: Seconds of each phase.
        elapsed_seconds: Mode time since the life started.

    Returns:
        The phase index.

    """
    phase_end = 0.0
    for phase_index, phase_seconds in enumerate(schedule):
        phase_end += phase_seconds
        if elapsed_seconds < phase_end:
            return phase_index
    return len(schedule)


def munchers_chase(*, schedule: tuple[float, ...], elapsed_seconds: float) -> bool:
    """Return whether the munchers chase (True) or scatter (False) after some mode time.

    The schedule alternates scatter and chase phases, starting with scatter; after the last
    phase the munchers chase for good.

    Args:
        schedule: Seconds of each phase (``LevelSettings.mode_schedule``).
        elapsed_seconds: Mode time since the life started (it stops while they are frightened).

    Returns:
        True for chase, False for scatter.

    """
    phase_index = mode_phase_index(schedule=schedule, elapsed_seconds=elapsed_seconds)
    return phase_index == len(schedule) or phase_index % 2 == 1


def frightened_is_flashing(*, remaining_seconds: float, frightened_seconds: float) -> bool:
    """Whether frightened munchers flash white now (they are about to recover).

    They flash for the last FRIGHTENED_FLASH_SECONDS (all of a shorter frightened time),
    alternating blue and white every quarter second, white first.

    Args:
        remaining_seconds: Frightened time left.
        frightened_seconds: The full frightened time of this level.

    Returns:
        True while they show white.

    """
    flash_window = min(FRIGHTENED_FLASH_SECONDS, frightened_seconds)
    if remaining_seconds > flash_window:
        return False
    flash_quarter_seconds = 4
    return math.floor(remaining_seconds * flash_quarter_seconds) % 2 == 1
