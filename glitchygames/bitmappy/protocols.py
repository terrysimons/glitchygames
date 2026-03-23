"""Protocols for the Bitmappy editor subsystem interfaces.

Defines the EditorContext protocol that captures what extracted subsystem managers
(ControllerEventHandler, AIIntegrationManager, FileIOManager, etc.) need from the
editor. This makes cross-class dependencies explicit and type-safe.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import pygame

    from glitchygames.bitmappy.animated_canvas import AnimatedCanvasSprite
    from glitchygames.bitmappy.controllers.manager import MultiControllerManager
    from glitchygames.bitmappy.controllers.modes import ModeSwitcher
    from glitchygames.bitmappy.controllers.selection import ControllerSelection
    from glitchygames.bitmappy.film_strip import FilmStripWidget
    from glitchygames.bitmappy.film_strip_sprite import FilmStripSprite
    from glitchygames.bitmappy.history.operations import (
        CanvasOperationTracker,
        ControllerPositionOperationTracker,
    )
    from glitchygames.bitmappy.history.undo_redo import UndoRedoManager
    from glitchygames.bitmappy.indicators.collision import VisualCollisionManager
    from glitchygames.ui import ColorWellSprite, SliderSprite


class EditorContext(Protocol):
    """Protocol defining what extracted subsystem managers need from the editor.

    This protocol captures the public API surface that ControllerEventHandler,
    AIIntegrationManager, FileIOManager, and other extracted classes depend on.
    BitmapEditorScene satisfies this protocol structurally (no explicit inheritance needed).
    """

    # ── Manager objects ──────────────────────────────────────────────────

    multi_controller_manager: MultiControllerManager
    mode_switcher: ModeSwitcher
    visual_collision_manager: VisualCollisionManager
    canvas_operation_tracker: CanvasOperationTracker
    controller_position_operation_tracker: ControllerPositionOperationTracker
    undo_redo_manager: UndoRedoManager

    # ── State collections ────────────────────────────────────────────────

    controller_selections: dict[int, ControllerSelection]
    film_strips: dict[str, FilmStripWidget]
    film_strip_sprites: dict[str, FilmStripSprite]
    current_pixel_changes: list[Any]
    current_pixel_changes_dict: dict[Any, Any]

    # ── Canvas & sprites ─────────────────────────────────────────────────

    canvas: AnimatedCanvasSprite
    all_sprites: pygame.sprite.LayeredDirty[Any]

    # ── UI components ────────────────────────────────────────────────────

    red_slider: SliderSprite
    green_slider: SliderSprite
    blue_slider: SliderSprite
    alpha_slider: SliderSprite
    color_well: ColorWellSprite
    debug_text: Any  # MultiLineTextBox at runtime

    # ── Selection state ──────────────────────────────────────────────────

    selected_animation: str | None
    selected_frame: int | None
    selected_frame_visible: bool
    film_strip_scroll_offset: int
    max_visible_strips: int
    dirty: int

    # ── Cross-class API methods ──────────────────────────────────────────

    def handle_undo(self) -> None:
        """Perform an undo operation."""
        ...

    def handle_redo(self) -> None:
        """Perform a redo operation."""
        ...

    def get_current_color(self) -> tuple[int, ...]:
        """Get the current drawing color from the sliders."""
        ...

    def update_color_well_from_sliders(self) -> None:
        """Update the color well widget with current slider values."""
        ...

    def update_film_strip_visibility(self) -> None:
        """Update which film strips are visible based on scroll offset."""
        ...

    def update_scroll_arrows(self) -> None:
        """Update scroll arrow visibility based on scroll position."""
        ...

    def on_film_strip_frame_selected(
        self, film_strip_widget: Any, animation: str, frame: int
    ) -> None:
        """Handle a frame selection event from a film strip widget."""
        ...

    def update_film_strip_selection_state(self) -> None:
        """Synchronize film strip selection highlights with current state."""
        ...

    def on_slider_event(self, event: Any, trigger: Any) -> None:
        """Handle a slider value change event."""
        ...
