"""Level data for Clockwork Keep — vertical tower climb.

Each floor is hand-designed with varied platform layouts. The tower
is 1 screen wide with walls on each side, leaving a 600px playfield.
Platforms mix widths, spacing, and horizontal positions for variety.

Coordinate system: (0, 0) is top-left. Y increases downward.
The Tinker spawns near the bottom and climbs upward.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict

from glitchygames.examples.clockwork_keep.constants import (
    PLAYFIELD_LEFT,
    PLAYFIELD_RIGHT,
    PLAYFIELD_WIDTH,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)

# Shorthand for platform placement
_L = PLAYFIELD_LEFT  # Left edge of playfield (100)
_R = PLAYFIELD_RIGHT  # Right edge of playfield (700)
_M = _L + PLAYFIELD_WIDTH // 2  # Center of playfield (400)
_W = PLAYFIELD_WIDTH  # Full playfield width (600)


class MovingGearData(BaseModel):
    """Where a moving gear platform rides and how (terrain.MovingGear's arguments).

    Attributes:
        world_x: Left edge of the gear at the centre of its movement range.
        world_y: Top of the gear at the centre of its movement range.
        move_range_x: Horizontal movement amplitude in pixels.
        move_range_y: Vertical movement amplitude in pixels.
        speed: Movement speed (radians/sec).
        size: Gear width in pixels (its height is a quarter of it).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    world_x: int
    world_y: int
    move_range_x: float = 0.0
    move_range_y: float = 0.0
    speed: float = 1.5
    size: int = 40


@dataclass
class FloorData:
    """Definition for one floor of the clockwork tower.

    Attributes:
        name: Display name.
        height: Total height in pixels.
        platforms: List of (x, y, width) tuples.
        elevators: List of (x, y) tuples.
        collectibles: List of (x, y, type) tuples.
        enemies: List of (type, x, y, kwargs) tuples.
        moving_gears: Moving gear platforms.
        spawn_x: Player spawn X.
        spawn_y: Player spawn Y.

    """

    name: str
    height: int
    platforms: list[tuple[int, int, int]] = field(default_factory=list)
    elevators: list[tuple[int, int]] = field(default_factory=list)
    collectibles: list[tuple[int, int, str]] = field(default_factory=list)
    enemies: list[tuple[str, int, int, dict[str, Any]]] = field(default_factory=list)
    moving_gears: list[MovingGearData] = field(default_factory=list)
    spawn_x: int = SCREEN_WIDTH // 2
    spawn_y: int = 0

    @property
    def width(self) -> int:
        """Floor width (always 1 screen)."""
        return SCREEN_WIDTH


# ---------------------------------------------------------------------------
# Floor 0: Boiler Room (2 screens tall = 960px)
# Tutorial floor — easy jumps, wide platforms, gentle introduction.
# ---------------------------------------------------------------------------
_bh = SCREEN_HEIGHT * 2  # 960

FLOOR_BOILER_ROOM = FloorData(
    name='Boiler Room',
    height=_bh,
    spawn_x=_M,
    spawn_y=_bh - 60,
    platforms=[
        # Ground — full width, safe starting area
        (_L, _bh - 24, _W),
        # First steps up — wide, close together, easy walking jumps
        (_L + 20, _bh - 80, 250),  # Step up left
        (_R - 280, _bh - 80, 260),  # Step up right (can walk to either)
        # Second tier — still easy, slightly higher gaps
        (_L + 60, _bh - 150, 200),  # Left
        (_M - 80, _bh - 170, 180),  # Center (slightly higher)
        (_R - 230, _bh - 150, 210),  # Right
        # Third tier — a wide bridge
        (_L + 40, _bh - 240, 520),  # Wide bridge across most of playfield
        # Fourth tier — start introducing choices
        (_L + 20, _bh - 320, 180),  # Left path
        (_R - 200, _bh - 340, 180),  # Right path (slightly higher)
        # Fifth tier — converge back to center
        (_M - 120, _bh - 420, 240),  # Center landing
        # Sixth tier — one more split
        (_L + 30, _bh - 500, 160),  # Left
        (_R - 190, _bh - 520, 160),  # Right (slightly higher)
        # Top landing — wide, leads to elevator
        (_L + 50, _bh - 600, 500),  # Wide top platform
        # Elevator shelf
        (_M - 50, _bh - 670, 100),  # Small platform right at elevator
    ],
    elevators=[
        (_M - 30, _bh - 678),
    ],
    collectibles=[
        (_M, _bh - 100, 'bronze'),  # Easy grab near spawn
        (_L + 150, _bh - 180, 'bronze'),  # On second tier left
        (_R - 150, _bh - 180, 'bronze'),  # On second tier right
        (_M, _bh - 270, 'bronze'),  # On the bridge
        (_M, _bh - 450, 'silver'),  # Center convergence
        (_M, _bh - 630, 'gold'),  # Top platform reward
    ],
)


# ---------------------------------------------------------------------------
# Floor 1: Gear Works (3 screens tall = 1440px)
# Medium difficulty — narrower platforms, bigger gaps, some require running.
# ---------------------------------------------------------------------------
_gh = SCREEN_HEIGHT * 3  # 1440

FLOOR_GEAR_WORKS = FloorData(
    name='Gear Works',
    height=_gh,
    spawn_x=_M,
    spawn_y=_gh - 60,
    platforms=[
        # Ground
        (_L, _gh - 24, _W),
        # Section 1: comfortable warmup
        (_L + 40, _gh - 90, 200),
        (_R - 240, _gh - 90, 200),
        (_M - 100, _gh - 160, 200),
        # Section 2: zigzag up (medium gaps)
        (_L + 20, _gh - 240, 180),
        (_R - 200, _gh - 320, 180),
        (_L + 40, _gh - 400, 180),
        (_R - 220, _gh - 470, 160),
        # Section 3: narrow bridge + choice
        (_M - 60, _gh - 550, 120),  # Narrow center
        (_L + 20, _gh - 640, 150),  # Left (easier path)
        (_R - 170, _gh - 660, 140),  # Right (harder, higher reward)
        # Section 4: vertical corridor
        (_M - 80, _gh - 740, 160),
        (_L + 30, _gh - 830, 200),
        (_R - 180, _gh - 910, 170),
        (_M - 100, _gh - 990, 200),
        # Section 5: top approach — needs running jumps
        (_L + 50, _gh - 1080, 150),
        (_R - 200, _gh - 1170, 150),
        # Top landing
        (_L + 30, _gh - 1260, 540),
        # Elevator shelf
        (_M - 50, _gh - 1330, 100),
    ],
    elevators=[
        (_M - 30, _gh - 1338),
    ],
    collectibles=[
        (_L + 130, _gh - 120, 'bronze'),
        (_R - 140, _gh - 120, 'bronze'),
        (_M, _gh - 190, 'bronze'),
        (_L + 100, _gh - 430, 'bronze'),
        (_R - 140, _gh - 500, 'bronze'),
        (_L + 80, _gh - 670, 'silver'),  # Easier path reward
        (_R - 100, _gh - 690, 'silver'),  # Harder path reward
        (_M, _gh - 1020, 'silver'),
        (_M, _gh - 1290, 'gold'),
    ],
)


# ---------------------------------------------------------------------------
# Floor 2: Clock Face (4 screens tall = 1920px)
# Hard — tight platforms, running jumps required, precision climbing.
# The final approach rides a moving gear across the clock face.
# No elevator — reaching the top is victory.
# ---------------------------------------------------------------------------
_ch = SCREEN_HEIGHT * 4  # 1920

FLOOR_CLOCK_FACE = FloorData(
    name='Clock Face',
    height=_ch,
    spawn_x=_M,
    spawn_y=_ch - 60,
    platforms=[
        # Ground
        (_L, _ch - 24, _W),
        # Section 1: easy start
        (_L + 50, _ch - 90, 220),
        (_R - 270, _ch - 90, 220),
        (_M - 100, _ch - 170, 200),
        # Section 2: ascending spiral
        (_L + 20, _ch - 250, 160),
        (_R - 180, _ch - 340, 160),
        (_L + 40, _ch - 420, 140),
        (_R - 180, _ch - 500, 160),
        (_M - 70, _ch - 570, 140),
        # Section 3: long climb with narrow platforms
        (_L + 30, _ch - 660, 130),
        (_R - 160, _ch - 750, 130),
        (_L + 50, _ch - 830, 120),
        (_R - 170, _ch - 910, 130),
        (_M - 60, _ch - 980, 120),
        # Section 4: precision zone — running jumps needed
        (_L + 20, _ch - 1070, 140),
        (_R - 160, _ch - 1160, 130),
        (_L + 40, _ch - 1260, 120),
        (_R - 150, _ch - 1360, 120),
        # Section 5: final approach — the centre step, then the moving gear (moving_gears)
        # carries the climber right to the last step
        (_M - 80, _ch - 1450, 160),
        (_R - 180, _ch - 1630, 150),
        # Victory platform — wide and welcoming
        (_L + 80, _ch - 1740, 440),
    ],
    # The final approach's ferry: the gear sweeps along the step the centre step jumps to
    # (90 px up, inside a walking jump's ~96 px), from the left wall's side (x 140) to just
    # short of the last step (its right edge at 504, 16 px before the step at 520, which is
    # 90 px higher). It pauses at each end of its sweep, so the hops on and off are timed
    # there; a missed hop falls back onto the steps below. The only way up: the centre step
    # is 180 px below the last step, beyond a running jump's ~140 px.
    moving_gears=[
        MovingGearData(
            world_x=_L + 190,
            world_y=_ch - 1540,
            move_range_x=150.0,
            speed=1.2,  # A 5.2 s round trip, 180 px/s at most
            size=64,
        ),
    ],
    elevators=[],  # No elevator — top is victory
    collectibles=[
        (_L + 150, _ch - 120, 'bronze'),
        (_R - 170, _ch - 120, 'bronze'),
        (_M, _ch - 200, 'bronze'),
        (_L + 100, _ch - 450, 'bronze'),
        (_R - 100, _ch - 530, 'bronze'),
        (_M, _ch - 600, 'silver'),
        (_L + 80, _ch - 860, 'silver'),
        (_R - 100, _ch - 940, 'silver'),
        (_M, _ch - 1010, 'silver'),
        (_L + 80, _ch - 1290, 'silver'),
        (_R - 80, _ch - 1390, 'silver'),
        (_M, _ch - 1480, 'gold'),
        (_L + 56, _ch - 1576, 'silver'),  # Reward for riding the gear to the far end
        (_M, _ch - 1770, 'gold'),  # Victory cog
    ],
)


ALL_FLOORS: list[FloorData] = [
    FLOOR_BOILER_ROOM,
    FLOOR_GEAR_WORKS,
    FLOOR_CLOCK_FACE,
]
