"""Elevator ride transition for Clockwork Keep.

A custom transition where the player appears to ride an elevator
upward through the tower. The old floor scrolls up off screen,
tower walls stream past, and the new floor scrolls in from below.
The elevator and player are pinned at center screen throughout.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

import pygame

from glitchygames.opacity import make_opaque
from glitchygames.transitions.base import Transition

if TYPE_CHECKING:
    from collections.abc import Callable


class ElevatorTransition(Transition):
    """Elevator ride between floors.

    Builds a tall composite surface: [old floor | shaft | new floor]
    and scrolls it upward. The elevator sprite stays pinned at
    screen center, giving the illusion of ascending.

    Args:
        duration: Ride duration in seconds.
        easing: Easing function name.
        shaft_height: Height of the empty shaft between floors.
        wall_color: Tower wall color for the shaft section.
        wall_accent: Brick/mortar accent color.
        player_surface: Optional sprite drawn standing on the elevator.
        on_update: Called with this transition after every running update().

    """

    def __init__(  # ruff: ignore[too-many-arguments, too-many-positional-arguments]
        self,
        duration: float = 1.5,
        easing: str = 'ease_in_out_quad',
        shaft_height: int = 400,
        wall_color: tuple[int, int, int] = (60, 40, 25),
        wall_accent: tuple[int, int, int] = (80, 55, 30),
        player_surface: pygame.Surface | None = None,
        on_update: Callable[[Transition], None] | None = None,
    ) -> None:
        """Initialize the elevator transition."""
        super().__init__(duration=duration, easing=easing, on_update=on_update)
        self._shaft_height = shaft_height
        self._wall_color = wall_color
        self._wall_accent = wall_accent
        self._player_surface = player_surface.copy() if player_surface else None
        self._composite: pygame.Surface | None = None
        self._elevator_surface: pygame.Surface | None = None
        self._total_scroll: int = 0

    @override
    def start(
        self,
        old_surface: pygame.Surface,
        new_surface: pygame.Surface,
    ) -> None:
        """Build the composite scroll surface and begin the ride.

        The composite is arranged vertically:
        - Top: new floor screenshot (destination, scrolls INTO view)
        - Middle: tower shaft (walls only, scrolls past)
        - Bottom: old floor screenshot (source, scrolls OUT of view)

        We scroll from showing the bottom (old floor) to the top (new floor).

        Args:
            old_surface: Screenshot of the departing floor.
            new_surface: Screenshot of the arriving floor.

        """
        super().start(old_surface, new_surface)

        screen_width = old_surface.get_width()
        screen_height = old_surface.get_height()

        # Build composite: new on top, shaft in middle, old on bottom. Both are made in the
        # screenshots' format (the display's), so on a display with per-pixel alpha (cocoa's)
        # they carry an alpha channel without SRCALPHA: blending the screenshots onto the
        # composite leaves alpha 0 there (BUGS.md #142). It is made opaque once built, or the
        # display would take that alpha 0, and the player blitted onto it would copy its
        # transparent pixels as black (a black box around the player; glitchygames/opacity.py)
        composite_height = screen_height + self._shaft_height + screen_height
        self._composite = pygame.Surface((screen_width, composite_height), 0, old_surface)
        self._composite.fill((0, 0, 0))

        # New floor at top
        self._composite.blit(new_surface, (0, 0))

        # Shaft in middle — draw tower walls
        shaft_surface = pygame.Surface((screen_width, self._shaft_height), 0, old_surface)
        shaft_surface.fill((20, 15, 10))
        self._draw_shaft_walls(shaft_surface)
        self._composite.blit(shaft_surface, (0, screen_height))

        # Old floor at bottom
        self._composite.blit(old_surface, (0, screen_height + self._shaft_height))
        make_opaque(surface=self._composite)

        # Total distance to scroll: from old floor visible to new floor visible
        self._total_scroll = screen_height + self._shaft_height

        # Elevator platform sprite (drawn on top of everything)
        elevator_width = 60
        elevator_height = 8
        self._elevator_surface = pygame.Surface(
            (elevator_width, elevator_height),
            pygame.SRCALPHA,
        )
        self._elevator_surface.fill((120, 100, 50))
        # Caution stripes
        stripe_color = (180, 150, 40)
        for stripe_x in range(0, elevator_width, 16):
            stripe_rect = (stripe_x, 0, 8, elevator_height)
            pygame.draw.rect(self._elevator_surface, stripe_color, stripe_rect)

    @override
    def _render_frame(
        self,
        screen: pygame.Surface,
        old_surface: pygame.Surface,
        new_surface: pygame.Surface,
    ) -> None:
        """Render the elevator ride frame.

        Scrolls the composite surface upward based on eased progress.
        Draws the elevator platform at a fixed screen position.

        Args:
            screen: Display surface.
            old_surface: Unused (composite replaces it).
            new_surface: Unused (composite replaces it).

        """
        # start() made the composite and the platform; render() draws only after start()
        assert self._composite is not None
        assert self._elevator_surface is not None

        screen_height = screen.get_height()
        screen_width = screen.get_width()
        # Overshooting easings (ease_in_back -0.10, ease_in_elastic -0.37, ease_out_back > 1)
        # would scroll past the composite and show black
        progress = min(1.0, max(0.0, self.eased_progress))

        # Calculate scroll offset — start showing old floor, end showing new floor
        # The composite has: [new floor (top)] [shaft (middle)] [old floor (bottom)]
        # At progress=0: show old floor (bottom of composite)
        # At progress=1: show new floor (top of composite)
        scroll_y = int(self._total_scroll * (1.0 - progress))

        # Blit the visible portion of the composite
        source_rect = pygame.Rect(0, scroll_y, screen_width, screen_height)
        screen.blit(self._composite, (0, 0), area=source_rect)

        # Draw elevator platform pinned at center-bottom of screen
        elevator_x = (screen_width - self._elevator_surface.get_width()) // 2
        elevator_y = screen_height - screen_height // 3
        screen.blit(self._elevator_surface, (elevator_x, elevator_y))

        # Draw the Tinker standing on the elevator
        if self._player_surface is not None:
            player_x = (
                elevator_x
                + (self._elevator_surface.get_width() - self._player_surface.get_width()) // 2
            )
            player_y = elevator_y - self._player_surface.get_height()
            screen.blit(self._player_surface, (player_x, player_y))

    def _draw_shaft_walls(self, surface: pygame.Surface) -> None:
        """Draw tower walls for the shaft section between floors.

        Args:
            surface: Surface to draw the shaft walls onto.

        """
        width = surface.get_width()
        height = surface.get_height()
        wall_width = 100
        playfield_right = width - wall_width

        # Left wall
        pygame.draw.rect(surface, self._wall_color, (0, 0, wall_width, height))
        # Right wall
        pygame.draw.rect(surface, self._wall_color, (playfield_right, 0, wall_width, height))

        # Brick pattern
        brick_height = 20
        for brick_y in range(0, height, brick_height):
            pygame.draw.line(surface, self._wall_accent, (0, brick_y), (wall_width, brick_y), 1)
            pygame.draw.line(
                surface,
                self._wall_accent,
                (playfield_right, brick_y),
                (width, brick_y),
                1,
            )

        # Shaft background — dark with some pipes
        pipe_color = (40, 30, 20)
        for pipe_x in range(wall_width + 40, playfield_right, 80):
            pygame.draw.rect(surface, pipe_color, (pipe_x, 0, 6, height))
