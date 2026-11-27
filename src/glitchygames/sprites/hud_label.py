"""A line of HUD text as a sprite: rendered when its text changes, drawn by the scene's group.

Every game object is a sprite in the scene's groups (CLAUDE.md), the HUD included: a label has a
stable id, takes part in replay comparison and shows in the debug hitboxes, and it renders its
text once per change instead of once per frame (plans/2026-11-20-game-code-into-the-engine.md,
Sub-plan 3, part A).

A label's look is one frozen ``HudLabelStyle`` (font, color, anchor, shadow, layer), so labels
that look alike share one style and a label is made from where it is, what it says and how it
looks. A style is built when a scene sets up its labels, never per frame.

A label whose style has a ``shadow_color`` owns a second label, its shadow: the same text in the
shadow's color at ``shadow_offset``, added to the group just before the label in the same layer,
and kept in step with it. Two sprites rather than one image with the shadow composited in, because
antialiased text has per-pixel alpha: blending the text onto the shadow first and the result onto
the screen rounds differently at the glyph edges from blending each onto the screen, which is
what a HUD drawn with two blits does and what two sprites do.

``anchor`` says which point of the text ``position`` names, so a label whose width changes
stays put: its left edge (``TOP_LEFT``), its right edge (``TOP_RIGHT``) or its middle
(``TOP_CENTER``, at ``(2 * x - width) // 2``, which is ``(screen width - width) // 2`` for a
label centred on a screen: half a pixel left of ``Rect.centerx`` for an odd width).

A label is screen space (no ``COORDINATE_SPACE``) and redrawn every frame (``dirty = 2``), for
scenes that fill the screen each frame. Text renders through ``font_manager.render_line``, so
antialiasing follows ``FontManager.antialias()``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Self

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames.fonts import font_manager

from .sprite import Sprite


class HudAnchor(StrEnum):
    """Which point of a label's text its position names."""

    TOP_LEFT = 'top_left'
    TOP_CENTER = 'top_center'
    TOP_RIGHT = 'top_right'


class HudLabelStyle(BaseModel):
    """How a HUD label looks: its font, colors, anchor, shadow and layer.

    Attributes:
        font: The font.
        color: The text's color.
        anchor: Which point of the text the label's position names.
        shadow_color: The shadow's color (None: no shadow).
        shadow_offset: Where the shadow sits, relative to the text.
        layer: The group layer the label (and its shadow) draws in.

    """

    # A pygame Font is not a pydantic type: it is held as it is, never validated or copied
    model_config = ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    font: pygame.font.Font
    color: tuple[int, int, int]
    anchor: HudAnchor = HudAnchor.TOP_LEFT
    shadow_color: tuple[int, int, int] | None = None
    shadow_offset: tuple[int, int] = (1, 1)
    layer: int = 0


class HudLabel(Sprite):
    """A line of HUD text, rendered when it changes (a plain class: it holds a Surface)."""

    def __init__(
        self: Self,
        *,
        groups: pygame.sprite.LayeredDirty[Any],
        text: str,
        position: tuple[int, int],
        style: HudLabelStyle,
    ) -> None:
        """Render the text and add the label (after its shadow, if it has one) to the group.

        Args:
            groups: The scene's sprite group.
            text: The text to show first.
            position: The anchor point, in screen pixels.
            style: How the label looks.

        """
        self.shadow: HudLabel | None = None
        if style.shadow_color is not None:
            shadow_x, shadow_y = style.shadow_offset
            self.shadow = HudLabel(
                groups=groups,
                text=text,
                position=(position[0] + shadow_x, position[1] + shadow_y),
                style=HudLabelStyle(
                    font=style.font,
                    color=style.shadow_color,
                    anchor=style.anchor,
                    layer=style.layer,
                ),
            )
        self.style = style
        self.position = position
        # The group reads the layer when the sprite is added (pygame's LayeredUpdates.add)
        self._layer = style.layer
        image = font_manager.render_line(font=style.font, text=text, color=style.color)
        super().__init__(
            x=0, y=0, width=image.get_width(), height=image.get_height(), groups=groups
        )
        self.dirty = 2
        self._text = text
        self._show(image=image)

    @property
    def sprites_in_draw_order(self: Self) -> tuple[HudLabel, ...]:
        """The label's sprites as its group draws them: its shadow (if it has one), then itself."""
        if self.shadow is None:
            return (self,)
        return (self.shadow, self)

    @property
    def text(self: Self) -> str:
        """The text the label shows; setting other text renders it (and the shadow's)."""
        return self._text

    @text.setter
    def text(self: Self, text: str) -> None:
        if text == self._text:
            return
        self._text = text
        if self.shadow is not None:
            self.shadow.text = text
        self._show(
            image=font_manager.render_line(font=self.style.font, text=text, color=self.style.color)
        )

    def _show(self: Self, *, image: pygame.Surface) -> None:
        """Show a rendered line, placed by the label's anchor."""
        self.image = image
        x, y = self.position
        width = image.get_width()
        if self.style.anchor is HudAnchor.TOP_CENTER:
            left = (2 * x - width) // 2
        elif self.style.anchor is HudAnchor.TOP_RIGHT:
            left = x - width
        else:
            left = x
        self.rect = image.get_rect(topleft=(left, y))
