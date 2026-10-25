"""The battlefield's ground: flat paper with a few seeded hills."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from random import Random

# The flat ground's y, as a fraction of the height
GROUND_BASELINE_FRACTION = 0.78
HILL_COUNT_RANGE = (2, 3)
# A hill's height, as a fraction of the screen height
HILL_HEIGHT_FRACTION_RANGE = (0.06, 0.14)
# A hill's width, as a fraction of the screen width
HILL_WIDTH_FRACTION_RANGE = (0.15, 0.25)
# Hills keep this fraction of the width clear at each edge, so the armies stand on flat ground
HILL_EDGE_MARGIN_FRACTION = 0.2


@dataclass(frozen=True)
class Terrain:
    """The ground: one ground y for every x pixel of the field."""

    width: int
    height: int
    ground: tuple[float, ...]

    def ground_y(self, x: float) -> float:
        """Find the ground's y at an x, interpolated between pixels and clamped to the field.

        Args:
            x: The x position (outside the field it is the nearest edge's).

        Returns:
            The ground's y at x.

        """
        clamped_x = min(max(x, 0.0), float(len(self.ground) - 1))
        left_index = math.floor(clamped_x)
        right_index = min(left_index + 1, len(self.ground) - 1)
        fraction = clamped_x - left_index
        return self.ground[left_index] * (1.0 - fraction) + self.ground[right_index] * fraction


def build_terrain(*, width: int, height: int, random: Random) -> Terrain:
    """Build hilly ground, the same for the same random stream.

    Args:
        width: The field's width in pixels.
        height: The field's height in pixels.
        random: The seeded stream the hills are drawn from.

    Returns:
        The terrain.

    """
    baseline = height * GROUND_BASELINE_FRACTION
    margin = width * HILL_EDGE_MARGIN_FRACTION
    hills: list[tuple[float, float, float]] = []
    for _ in range(random.randint(*HILL_COUNT_RANGE)):
        hill_width = width * random.uniform(*HILL_WIDTH_FRACTION_RANGE)
        centre = random.uniform(margin + hill_width / 2, width - margin - hill_width / 2)
        hill_height = height * random.uniform(*HILL_HEIGHT_FRACTION_RANGE)
        hills.append((centre, hill_width, hill_height))

    ground: list[float] = []
    for x in range(width):
        rise = 0.0
        for centre, hill_width, hill_height in hills:
            offset = abs(x - centre)
            if offset < hill_width / 2:
                # A raised cosine: a smooth bump, flat where it meets the ground
                bump = (1.0 + math.cos(2.0 * math.pi * offset / hill_width)) / 2.0
                rise = max(rise, hill_height * bump)
        ground.append(baseline - rise)
    return Terrain(width=width, height=height, ground=tuple(ground))
