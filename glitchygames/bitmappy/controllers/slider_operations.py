"""Slider-related controller operations for the Bitmappy editor.

Provides the SliderOperations delegate with methods for slider mode navigation,
value adjustment, continuous adjustment with acceleration, and slider
previous/next navigation.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from glitchygames import events
from glitchygames.bitmappy.constants import (
    CONTROLLER_ACCEL_LEVEL1_TIME,
    CONTROLLER_ACCEL_LEVEL2_TIME,
    CONTROLLER_ACCEL_LEVEL3_TIME,
)
from glitchygames.bitmappy.controllers.modes import ControllerMode

if TYPE_CHECKING:
    from glitchygames.bitmappy.controllers.event_handler import ControllerEventHandler

log = logging.getLogger('game.tools.bitmappy.controllers.slider_operations')
log.addHandler(logging.NullHandler())


class SliderOperations:
    """Delegate providing slider-related controller operations.

    All handler state is accessed via self.handler (the ControllerEventHandler).
    """

    def __init__(self, handler: ControllerEventHandler) -> None:
        """Initialize the slider operations delegate.

        Args:
            handler: The ControllerEventHandler that owns this delegate.

        """
        self.handler = handler

    def handle_slider_mode_navigation(
        self,
        direction: str,
        controller_id: int | None = None,
    ) -> None:
        """Handle arrow key navigation between slider modes."""
        if not hasattr(self.handler.editor, 'mode_switcher'):
            return

        # If no specific controller provided, find the first controller in slider mode (for keyboard
        # navigation)
        if controller_id is None:
            target_controller_id = None
            for cid in self.handler.editor.mode_switcher.controller_modes:
                controller_mode = self.handler.editor.mode_switcher.get_controller_mode(cid)
                if controller_mode and controller_mode.value in {
                    'r_slider',
                    'g_slider',
                    'b_slider',
                }:
                    target_controller_id = cid
                    break
        else:
            # Use the specific controller (for D-pad navigation)
            target_controller_id = controller_id

        if target_controller_id is None:
            return

        current_mode = self.handler.editor.mode_switcher.get_controller_mode(target_controller_id)
        if not current_mode:
            return

        # Define the slider mode cycle
        slider_cycle = [ControllerMode.R_SLIDER, ControllerMode.G_SLIDER, ControllerMode.B_SLIDER]

        # Find current position in cycle
        if current_mode not in slider_cycle:
            return

        current_index = slider_cycle.index(current_mode)

        # Calculate new index based on direction
        if direction == 'up':
            # B -> G -> R
            new_index = (current_index - 1) % len(slider_cycle)
        else:  # direction == "down"
            # R -> G -> B
            new_index = (current_index + 1) % len(slider_cycle)

        new_mode = slider_cycle[new_index]

        # Switch to new mode
        current_time = time.time()
        self.handler.editor.mode_switcher.controller_modes[target_controller_id].switch_to_mode(
            new_mode,
            current_time,
        )

        self.handler.log.debug(
            f'DEBUG: Slider mode navigation - switched controller {target_controller_id} from'
            f' {current_mode.value} to {new_mode.value}',
        )
        self.handler.log.debug(
            f'Slider mode navigation - switched controller {target_controller_id} from'
            f' {current_mode.value} to {new_mode.value}',
        )

    def _slider_adjust_value(self, controller_id: int, delta: int) -> None:
        """Adjust the current slider's value."""
        self.handler.log.debug(
            f'DEBUG: _slider_adjust_value called for controller {controller_id}, delta {delta}',
        )

        # Get the controller's current mode to determine which slider
        if hasattr(self.handler.editor, 'mode_switcher'):
            controller_mode = self.handler.editor.mode_switcher.get_controller_mode(controller_id)
            self.handler.log.debug(
                f'DEBUG: Controller {controller_id} mode:'
                f' {controller_mode.value if controller_mode else "None"}',
            )

            # Adjust the appropriate slider based on mode
            if controller_mode and controller_mode.value == 'r_slider':
                old_value = self.handler.editor.red_slider.value
                new_value = max(0, min(255, old_value + delta))
                self.handler.log.debug(f'DEBUG: R slider: {old_value} -> {new_value}')
                # Update the slider value
                self.handler.editor.red_slider.value = new_value
                # Create a trigger event to properly update the color well
                trigger = events.HashableEvent(0, name='R', value=new_value)
                self.handler.editor.on_slider_event(events.HashableEvent(0), trigger)
                self.handler.log.debug(f'DEBUG: Adjusted R slider to {new_value}')
            elif controller_mode and controller_mode.value == 'g_slider':
                old_value = self.handler.editor.green_slider.value
                new_value = max(0, min(255, old_value + delta))
                self.handler.log.debug(f'DEBUG: G slider: {old_value} -> {new_value}')
                # Update the slider value
                self.handler.editor.green_slider.value = new_value
                # Create a trigger event to properly update the color well
                trigger = events.HashableEvent(0, name='G', value=new_value)
                self.handler.editor.on_slider_event(events.HashableEvent(0), trigger)
                self.handler.log.debug(f'DEBUG: Adjusted G slider to {new_value}')
            elif controller_mode and controller_mode.value == 'b_slider':
                old_value = self.handler.editor.blue_slider.value
                new_value = max(0, min(255, old_value + delta))
                self.handler.log.debug(f'DEBUG: B slider: {old_value} -> {new_value}')
                # Update the slider value
                self.handler.editor.blue_slider.value = new_value
                # Create a trigger event to properly update the color well
                trigger = events.HashableEvent(0, name='B', value=new_value)
                self.handler.editor.on_slider_event(events.HashableEvent(0), trigger)
                self.handler.log.debug(f'DEBUG: Adjusted B slider to {new_value}')
            else:
                self.handler.log.debug(
                    'DEBUG: No matching slider mode for'
                    f' {controller_mode.value if controller_mode else "None"}',
                )
        else:
            self.handler.log.debug('DEBUG: No mode_switcher found')

    def start_slider_continuous_adjustment(
        self,
        controller_id: int,
        direction: int,
    ) -> None:
        """Start continuous slider adjustment with acceleration."""
        # Do the first tick immediately for responsive feel
        self._slider_adjust_value(controller_id, direction)

        # Initialize continuous adjustment for this controller
        # Set last_adjustment to current time so the next adjustment waits for the full interval
        current_time = time.time()
        self.handler.slider_continuous_adjustments[controller_id] = {
            'direction': direction,
            'start_time': current_time,
            'last_adjustment': current_time,
            'acceleration_level': 0,
        }
        self.handler.log.debug(
            f'DEBUG: Started continuous slider adjustment for controller {controller_id}, direction'
            f' {direction} (immediate first tick)',
        )

    def stop_slider_continuous_adjustment(
        self,
        controller_id: int,
    ) -> None:
        """Stop continuous slider adjustment."""
        if (
            hasattr(self.handler, 'slider_continuous_adjustments')
            and controller_id in self.handler.slider_continuous_adjustments
        ):
            del self.handler.slider_continuous_adjustments[controller_id]
            self.handler.log.debug(
                f'DEBUG: Stopped continuous slider adjustment for controller {controller_id}',
            )

    def update_slider_continuous_adjustments(self) -> None:
        """Update continuous slider adjustments with acceleration."""
        if not hasattr(self.handler, 'slider_continuous_adjustments'):
            return

        current_time = time.time()

        for controller_id, adjustment_data in list(
            self.handler.slider_continuous_adjustments.items(),
        ):
            # Calculate time since start and since last adjustment
            time_since_start = current_time - adjustment_data['start_time']
            time_since_last = current_time - adjustment_data['last_adjustment']

            # Calculate acceleration level (0-3)
            # 0-0.8s: level 0 (1 tick per 0.15s) - longer delay for precision
            # 0.8-1.5s: level 1 (2 ticks per 0.1s)
            # 1.5-2.5s: level 2 (4 ticks per 0.05s)
            # 2.5s+: level 3 (8 ticks per 0.025s)
            if time_since_start < CONTROLLER_ACCEL_LEVEL1_TIME:
                acceleration_level = 0
                interval = 0.15  # ~6.7 ticks per second
            elif time_since_start < CONTROLLER_ACCEL_LEVEL2_TIME:
                acceleration_level = 1
                interval = 0.1  # 10 ticks per second
            elif time_since_start < CONTROLLER_ACCEL_LEVEL3_TIME:
                acceleration_level = 2
                interval = 0.05  # 20 ticks per second
            else:
                acceleration_level = 3
                interval = 0.025  # 40 ticks per second

            # Update acceleration level if changed
            if acceleration_level != adjustment_data['acceleration_level']:
                adjustment_data['acceleration_level'] = acceleration_level
                self.handler.log.debug(
                    f'DEBUG: Controller {controller_id} slider acceleration level'
                    f' {acceleration_level}',
                )

            # Check if enough time has passed for next adjustment
            if time_since_last >= interval:
                # Calculate delta based on acceleration level (1, 2, 4, 8)
                delta = adjustment_data['direction'] * (2**acceleration_level)
                delta = max(-8, min(8, delta))  # Cap at +/-8

                # Apply the adjustment
                self._slider_adjust_value(controller_id, delta)

                # Update color well during continuous adjustment
                controller_mode = self.handler.editor.mode_switcher.get_controller_mode(
                    controller_id,
                )
                self.handler.log.debug(
                    f'DEBUG: Continuous adjustment - controller {controller_id} mode:'
                    f' {controller_mode.value if controller_mode else "None"}',
                )
                if controller_mode and controller_mode.value in {
                    'r_slider',
                    'g_slider',
                    'b_slider',
                }:
                    self.handler.log.debug(
                        'DEBUG: Calling _update_color_well_from_sliders during continuous '
                        'adjustment',
                    )
                    self.handler.editor.update_color_well_from_sliders()
                else:
                    self.handler.log.debug(
                        'DEBUG: Not updating color well - controller not in slider mode',
                    )

                # Update last adjustment time
                adjustment_data['last_adjustment'] = current_time

    def _slider_previous(self, controller_id: int) -> None:
        """Move to the previous slider (now handled by L2/R2 mode switching)."""
        self.handler.log.debug(f'DEBUG: Controller {controller_id} moved to previous slider')
        # This is now handled by L2/R2 mode switching, so this is just for D-pad compatibility

    def _slider_next(self, controller_id: int) -> None:
        """Move to the next slider (now handled by L2/R2 mode switching)."""
        self.handler.log.debug(f'DEBUG: Controller {controller_id} moved to next slider')
        # This is now handled by L2/R2 mode switching, so this is just for D-pad compatibility
