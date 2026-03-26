"""Protocols for the Bitmappy editor subsystem interfaces.

Defines the EditorContext protocol that captures what extracted subsystem managers
(ControllerEventHandler, AIManager, FileIOManager, FilmStripCoordinator, etc.)
need from the editor. This makes cross-class dependencies explicit and type-safe.
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
        FilmStripOperationTracker,
    )
    from glitchygames.bitmappy.history.undo_redo import UndoRedoManager
    from glitchygames.bitmappy.indicators.collision import VisualCollisionManager
    from glitchygames.bitmappy.scroll_arrow import ScrollArrowSprite
    from glitchygames.ui import ColorWellSprite, SliderSprite, TabControlSprite


class EditorContext(Protocol):
    """Protocol defining what extracted subsystem managers need from the editor.

    This protocol captures the public API surface that ControllerEventHandler,
    AIManager, FileIOManager, FilmStripCoordinator, and other extracted classes
    depend on. BitmapEditorScene satisfies this protocol structurally.
    """

    # ── Manager objects ──────────────────────────────────────────────────

    multi_controller_manager: MultiControllerManager
    mode_switcher: ModeSwitcher
    visual_collision_manager: VisualCollisionManager
    canvas_operation_tracker: CanvasOperationTracker
    controller_position_operation_tracker: ControllerPositionOperationTracker
    film_strip_operation_tracker: FilmStripOperationTracker
    undo_redo_manager: UndoRedoManager

    # ── Subsystem managers ───────────────────────────────────────────────

    controller_handler: Any  # ControllerEventHandler (avoids circular import)

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
    tab_control: TabControlSprite
    slider_input_format: str
    debug_text: Any  # MultiLineTextBox at runtime
    scroll_up_arrow: ScrollArrowSprite | None
    film_strip_widget: FilmStripWidget | None  # Legacy reference

    # ── Selection state ──────────────────────────────────────────────────

    selected_animation: str | None
    selected_frame: int | None
    selected_frame_visible: bool
    film_strip_scroll_offset: int
    max_visible_strips: int
    dirty: int

    # ── Screen / display ─────────────────────────────────────────────────

    screen: pygame.Surface | None
    screen_width: int
    screen_height: int
    background: pygame.Surface
    dt: float  # Delta time from scene update

    # ── Film strip drag state ────────────────────────────────────────────

    is_dragging_film_strips: bool
    film_strip_drag_start_y: int | None
    film_strip_drag_start_offset: int | None

    # ── Scene support ────────────────────────────────────────────────────

    options: dict[str, Any]
    name: Any  # Class attribute NAME on Scene, type varies
    log: Any  # Logger
    screenshot: Any  # Screenshot surface or method
    confirmation_dialog: Any  # Confirmation dialog or None

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
        self, film_strip_widget: Any, animation: str, frame: int,
    ) -> None:
        """Handle a frame selection event from a film strip widget."""
        ...

    def update_film_strip_selection_state(self) -> None:
        """Synchronize film strip selection highlights with current state."""
        ...

    def on_slider_event(self, event: Any, trigger: Any) -> None:
        """Handle a slider value change event."""
        ...

    def _reset_canvas_for_new_file(self, width: int, height: int, pixel_size: int) -> None:
        """Reset the canvas for a new file."""
        ...

    def on_new_file_event(self, dimensions: str) -> None:
        """Handle new file creation."""
        ...

    def _init_undo_redo_system(self) -> None:
        """Initialize the undo/redo system."""
        ...
