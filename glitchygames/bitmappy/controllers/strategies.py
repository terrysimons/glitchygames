"""Mode-specific button handling strategies for controller input.

Each strategy encapsulates the button-down and button-up behavior for a
single controller mode (Film Strip, Canvas, or Slider), replacing the
if/elif dispatch chain that was previously in ControllerEventHandler.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

import pygame

if TYPE_CHECKING:
    from glitchygames.bitmappy.controllers.event_handler import ControllerEventHandler

log = logging.getLogger('game.tools.bitmappy.controllers.strategies')
log.addHandler(logging.NullHandler())


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class ModeStrategy(Protocol):
    """Protocol for mode-specific button handling strategies."""

    def handle_button_down(self, controller_id: int, button: int) -> None:
        """Handle a controller button press for this mode."""
        ...

    def handle_button_up(self, controller_id: int, button: int) -> None:
        """Handle a controller button release for this mode."""
        ...


# ---------------------------------------------------------------------------
# Film Strip Mode
# ---------------------------------------------------------------------------


class FilmStripModeStrategy:
    """Button handling for film strip mode.

    In film strip mode, the D-pad and shoulder buttons navigate frames and
    animations, A selects the current frame, B undoes, X redoes, and Y
    toggles onion skinning.
    """

    def __init__(self, handler: ControllerEventHandler) -> None:
        """Initialize with a reference to the controller event handler."""
        self.handler = handler

    def handle_button_down(self, controller_id: int, button: int) -> None:
        """Handle a controller button press in film strip mode."""
        handler = self.handler
        editor = handler.editor

        button_handlers = {
            pygame.CONTROLLER_BUTTON_A: (
                'selecting current frame',
                lambda: handler.multi_controller_select_current_frame(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_B: (
                'UNDO',
                editor.handle_undo,
            ),
            pygame.CONTROLLER_BUTTON_Y: (
                'toggling onion skinning',
                lambda: handler.multi_controller_toggle_onion_skinning(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_DPAD_LEFT: (
                'previous frame',
                lambda: handler.multi_controller_previous_frame(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_DPAD_RIGHT: (
                'next frame',
                lambda: handler.multi_controller_next_frame(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_DPAD_UP: (
                'previous animation',
                lambda: handler.multi_controller_previous_animation(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_DPAD_DOWN: (
                'next animation',
                lambda: handler.multi_controller_next_animation(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_START: (
                'activate controller',
                lambda: handler.multi_controller_activate(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_LEFTSHOULDER: (
                'moving indicator left',
                lambda: handler.multi_controller_previous_frame(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_RIGHTSHOULDER: (
                'moving indicator right',
                lambda: handler.multi_controller_next_frame(controller_id),
            ),
        }

        if button == pygame.CONTROLLER_BUTTON_X:
            # X button (Square): RESERVED for redo operations (only when selected frame is visible)
            if editor.selected_frame_visible:
                handler.log.debug('Controller %s: X button pressed - REDO', controller_id)
                editor.handle_redo()
            else:
                handler.log.debug(
                    'Controller %s: X button pressed - DISABLED (selected frame hidden)', controller_id,
                )
            return

        if button in button_handlers:
            description, button_handler = button_handlers[button]
            handler.log.debug('Controller %s: button pressed - %s', controller_id, description)
            button_handler()
        else:
            # Unhandled buttons
            handler.log.debug('Controller %s: button %s pressed - UNHANDLED', controller_id, button)

    def handle_button_up(self, controller_id: int, button: int) -> None:
        """Handle a controller button release in film strip mode.

        Film strip mode has no continuous operations, so button releases
        are no-ops.
        """


# ---------------------------------------------------------------------------
# Canvas Mode
# ---------------------------------------------------------------------------


class CanvasModeStrategy:
    """Button handling for canvas mode.

    In canvas mode, the D-pad moves the cursor with continuous movement,
    A starts painting/drag, shoulder buttons jump or paint 8 pixels,
    B undoes, X redoes, and Y toggles frame visibility.
    """

    def __init__(self, handler: ControllerEventHandler) -> None:
        """Initialize with a reference to the controller event handler."""
        self.handler = handler

    def handle_button_down(self, controller_id: int, button: int) -> None:
        """Handle a controller button press in canvas mode."""
        handler = self.handler

        if button == pygame.CONTROLLER_BUTTON_A:
            self._handle_a_button(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_B:
            handler.log.debug('Controller %s: B button pressed - UNDO', controller_id)
            handler.editor.handle_undo()
        elif button == pygame.CONTROLLER_BUTTON_Y:
            self._handle_y_button(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_X:
            self._handle_x_button(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_LEFT:
            handler.log.debug(
                'Controller %s: D-pad left pressed - start continuous movement left', controller_id,
            )
            handler.start_canvas_continuous_movement(controller_id, -1, 0)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_RIGHT:
            handler.log.debug(
                'Controller %s: D-pad right pressed - start continuous movement right', controller_id,
            )
            handler.start_canvas_continuous_movement(controller_id, 1, 0)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_UP:
            handler.log.debug(
                'Controller %s: D-pad up pressed - start continuous movement up', controller_id,
            )
            handler.start_canvas_continuous_movement(controller_id, 0, -1)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_DOWN:
            handler.log.debug(
                'Controller %s: D-pad down pressed - start continuous movement down', controller_id,
            )
            handler.start_canvas_continuous_movement(controller_id, 0, 1)
        elif button == pygame.CONTROLLER_BUTTON_LEFTSHOULDER:
            self._handle_shoulder_button(controller_id, is_left=True)
        elif button == pygame.CONTROLLER_BUTTON_RIGHTSHOULDER:
            self._handle_shoulder_button(controller_id, is_left=False)
        else:
            handler.log.debug(
                'DEBUG: Controller %s: Button %s not handled in canvas mode', controller_id, button,
            )
            handler.log.debug(
                'Controller %s: Button %s not handled in canvas mode', controller_id, button,
            )

    def handle_button_up(self, controller_id: int, button: int) -> None:
        """Handle a controller button release in canvas mode.

        Stops continuous movement on D-pad release and ends drag on A
        release.
        """
        handler = self.handler

        if button in {
            pygame.CONTROLLER_BUTTON_DPAD_LEFT,
            pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
            pygame.CONTROLLER_BUTTON_DPAD_UP,
            pygame.CONTROLLER_BUTTON_DPAD_DOWN,
        }:
            handler.stop_canvas_continuous_movement(controller_id)

        if button == pygame.CONTROLLER_BUTTON_A:
            handler.handle_controller_drag_end(controller_id)

    # -- Private helpers for canvas button-down --

    def _handle_a_button(self, controller_id: int) -> None:
        """Handle A button press in canvas mode (start drag/paint)."""
        import time

        handler = self.handler
        editor = handler.editor

        if not editor.selected_frame_visible:
            handler.log.debug(
                'Controller %s: A button pressed - DISABLED (selected frame hidden)', controller_id,
            )
            return

        handler.log.debug(
            'Controller %s: A button pressed - starting controller drag', controller_id,
        )

        # Start drag operation for this controller
        handler.controller_drags[controller_id] = {
            'active': True,
            'start_position': editor.mode_switcher.get_controller_position(controller_id),
            'pixels_drawn': [],
            'start_time': time.time(),
        }

        # Paint at the current position
        handler.canvas_paint_at_controller_position(controller_id)

    def _handle_x_button(self, controller_id: int) -> None:
        """Handle X button press in canvas mode (redo)."""
        handler = self.handler
        if handler.editor.selected_frame_visible:
            handler.log.debug('Controller %s: X button pressed - REDO', controller_id)
            handler.editor.handle_redo()
        else:
            handler.log.debug(
                'Controller %s: X button pressed - DISABLED (selected frame hidden)', controller_id,
            )

    def _handle_y_button(self, controller_id: int) -> None:
        """Handle Y button press in canvas mode (toggle visibility or fill direction)."""
        handler = self.handler
        handler.log.debug(
            'Controller %s: Y button pressed - toggling selected frame visibility', controller_id,
        )
        handler.multi_controller_toggle_selected_frame_visibility(controller_id)

    def _handle_shoulder_button(self, controller_id: int, *, is_left: bool) -> None:
        """Handle shoulder button press in canvas mode (move/paint 8 pixels).

        Args:
            controller_id: The controller ID.
            is_left: True for left shoulder, False for right shoulder.

        """
        handler = self.handler
        editor = handler.editor

        if not (
            hasattr(editor, 'controller_selections')
            and controller_id in editor.controller_selections
        ):
            return

        fill_direction = editor.controller_selections[controller_id].get_fill_direction()
        a_button_held = handler.is_controller_button_held(controller_id, pygame.CONTROLLER_BUTTON_A)
        direction_label = 'LEFT' if is_left else 'RIGHT'
        distance = -8 if is_left else 8

        if fill_direction == 'HORIZONTAL':
            if a_button_held:
                handler.log.debug(
                    f'Controller {controller_id}: {direction_label} SHOULDER + A - paint 8 pixels'
                    f' {"left" if is_left else "right"}',
                )
                handler.canvas_paint_horizontal_line(controller_id, distance)
            else:
                handler.log.debug(
                    f'Controller {controller_id}: {direction_label} SHOULDER - jump 8 pixels'
                    f' {"left" if is_left else "right"}',
                )
                handler.canvas_jump_horizontal(controller_id, distance)
        elif a_button_held:
            handler.log.debug(
                f'Controller {controller_id}: {direction_label} SHOULDER + A - paint 8 pixels'
                f' {"up" if is_left else "down"}',
            )
            handler.canvas_paint_vertical_line(controller_id, distance)
        else:
            handler.log.debug(
                f'Controller {controller_id}: {direction_label} SHOULDER - jump 8 pixels'
                f' {"up" if is_left else "down"}',
            )
            handler.canvas_jump_vertical(controller_id, distance)


# ---------------------------------------------------------------------------
# Slider Mode
# ---------------------------------------------------------------------------


class SliderModeStrategy:
    """Button handling for slider mode (R, G, and B slider sub-modes).

    In slider mode, D-pad left/right adjusts the slider value with
    continuous adjustment, D-pad up/down navigates between R/G/B sliders,
    shoulder buttons adjust by 8, and other buttons are no-ops.
    """

    def __init__(self, handler: ControllerEventHandler) -> None:
        """Initialize with a reference to the controller event handler."""
        self.handler = handler

    def handle_button_down(self, controller_id: int, button: int) -> None:
        """Handle a controller button press in slider mode."""
        handler = self.handler
        handler.log.debug(
            'DEBUG: _handle_slider_button_press called for controller %s, button %s', controller_id, button,
        )

        if button == pygame.CONTROLLER_BUTTON_A:
            # A button: No action in slider mode
            handler.log.debug(
                'DEBUG: Controller %s: A button pressed - no action in slider mode', controller_id,
            )
            handler.log.debug(
                'Controller %s: A button pressed - no action in slider mode', controller_id,
            )
        elif button == pygame.CONTROLLER_BUTTON_DPAD_LEFT:
            # D-pad left: Start continuous decrease
            handler.log.debug(
                'DEBUG: Controller %s: D-pad left pressed - start continuous decrease', controller_id,
            )
            handler.log.debug(
                'Controller %s: D-pad left pressed - start continuous decrease', controller_id,
            )
            handler.start_slider_continuous_adjustment(controller_id, -1)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_RIGHT:
            # D-pad right: Start continuous increase
            handler.log.debug(
                'DEBUG: Controller %s: D-pad right pressed - start continuous increase', controller_id,
            )
            handler.log.debug(
                'Controller %s: D-pad right pressed - start continuous increase', controller_id,
            )
            handler.start_slider_continuous_adjustment(controller_id, 1)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_UP:
            # D-pad up: Navigate to previous slider mode (B -> G -> R)
            handler.log.debug(
                'DEBUG: Controller %s: D-pad up pressed - navigate to previous slider mode', controller_id,
            )
            handler.log.debug(
                'Controller %s: D-pad up pressed - navigate to previous slider mode', controller_id,
            )
            handler.handle_slider_mode_navigation('up', controller_id)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_DOWN:
            # D-pad down: Navigate to next slider mode (R -> G -> B)
            handler.log.debug(
                'DEBUG: Controller %s: D-pad down pressed - navigate to next slider mode', controller_id,
            )
            handler.log.debug(
                'Controller %s: D-pad down pressed - navigate to next slider mode', controller_id,
            )
            handler.handle_slider_mode_navigation('down', controller_id)
        elif button == pygame.CONTROLLER_BUTTON_LEFTSHOULDER:
            # Left shoulder (L1): Start continuous decrease by 8
            handler.log.debug(
                'DEBUG: Controller %s: Left shoulder pressed - start continuous decrease by 8', controller_id,
            )
            handler.log.debug(
                'Controller %s: Left shoulder pressed - start continuous decrease by 8', controller_id,
            )
            handler.start_slider_continuous_adjustment(controller_id, -8)
        elif button == pygame.CONTROLLER_BUTTON_RIGHTSHOULDER:
            # Right shoulder (R1): Start continuous increase by 8
            handler.log.debug(
                'DEBUG: Controller %s: Right shoulder pressed - start continuous increase by 8', controller_id,
            )
            handler.log.debug(
                'Controller %s: Right shoulder pressed - start continuous increase by 8', controller_id,
            )
            handler.start_slider_continuous_adjustment(controller_id, 8)
        else:
            # Other buttons not handled in slider mode (including B button)
            handler.log.debug(
                'DEBUG: Controller %s: Button %s not handled in slider mode', controller_id, button,
            )
            handler.log.debug(
                'Controller %s: Button %s not handled in slider mode', controller_id, button,
            )

    def handle_button_up(self, controller_id: int, button: int) -> None:
        """Handle a controller button release in slider mode.

        Stops continuous slider adjustment on D-pad/shoulder release and
        updates the color well.
        """
        handler = self.handler

        if button in {
            pygame.CONTROLLER_BUTTON_DPAD_LEFT,
            pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
            pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
            pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
        }:
            handler.stop_slider_continuous_adjustment(controller_id)
            handler.editor.update_color_well_from_sliders()
