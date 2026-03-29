"""Film strip controller operations for the Bitmappy editor.

Provides the FilmStripOperations delegate with methods for multi-controller
film strip navigation, frame/animation traversal, onion skinning toggle,
frame visibility toggle, and controller system reinitialization.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from glitchygames.bitmappy.controllers.selection import ControllerSelection

if TYPE_CHECKING:
    from glitchygames.bitmappy.controllers.event_handler import ControllerEventHandler

log = logging.getLogger('game.tools.bitmappy.controllers.film_strip_operations')
log.addHandler(logging.NullHandler())


class FilmStripOperations:
    """Delegate providing film strip controller operations.

    All handler state is accessed via self.handler (the ControllerEventHandler).
    """

    def __init__(self, handler: ControllerEventHandler) -> None:
        """Initialize the film strip operations delegate.

        Args:
            handler: The ControllerEventHandler that owns this delegate.

        """
        self.handler = handler

    # ------------------------------------------------------------------
    # Deprecated single-controller methods (kept for compatibility)
    # ------------------------------------------------------------------

    def _select_current_frame(self) -> None:
        """Select the currently highlighted frame."""
        if not hasattr(self.handler.editor, 'selected_animation') or not hasattr(
            self.handler.editor,
            'selected_frame',
        ):
            return

        # Find the active film strip
        if hasattr(self.handler.editor, 'film_strips') and self.handler.editor.film_strips:
            for strip_name, strip_widget in self.handler.editor.film_strips.items():
                if (
                    strip_name == self.handler.editor.selected_animation
                    and self.handler.editor.selected_animation is not None
                    and self.handler.editor.selected_frame is not None
                ):
                    # Trigger frame selection
                    self.handler.editor.on_film_strip_frame_selected(
                        strip_widget,
                        self.handler.editor.selected_animation,
                        self.handler.editor.selected_frame,
                    )
                    break

    def controller_cancel(self) -> None:
        """Handle controller cancel action."""
        # For now, just log the action
        self.handler.log.debug('Controller cancel action')

    def _controller_select_current_frame(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        self.handler.log.debug(
            '_controller_select_current_frame called but DISABLED - use multi-controller system '
            'instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _controller_previous_frame(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        self.handler.log.debug(
            '_controller_previous_frame called but DISABLED - use multi-controller system instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _controller_next_frame(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        self.handler.log.debug(
            '_controller_next_frame called but DISABLED - use multi-controller system instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _controller_previous_animation(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        self.handler.log.debug(
            '_controller_previous_animation called but DISABLED - use multi-controller system '
            'instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _controller_next_animation(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        self.handler.log.debug(
            '_controller_next_animation called but DISABLED - use multi-controller system instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _validate_controller_selection(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        self.handler.log.debug(
            '_validate_controller_selection called but DISABLED - use multi-controller system '
            'instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _initialize_controller_selection(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        self.handler.log.debug(
            '_initialize_controller_selection called but DISABLED - use multi-controller system '
            'instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _controller_select_frame(
        self,
        _animation: str,
        _frame: int,
    ) -> None:
        """Deprecate old single-controller system in favor of multi-controller system.

        This method is kept for compatibility but should not be used.
        Use the new multi-controller system instead.
        """
        self.handler.log.debug(
            'DEBUG: _controller_select_frame called but DISABLED - use multi-controller system '
            'instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    # ------------------------------------------------------------------
    # Multi-controller activation and navigation
    # ------------------------------------------------------------------

    def multi_controller_activate(
        self,
        controller_id: int,
    ) -> None:
        """Activate a controller for navigation.

        Args:
            controller_id: Controller ID to activate

        """
        if controller_id not in self.handler.editor.controller_selections:
            self.handler.log.debug(f'DEBUG: Controller {controller_id} not found for activation')
            return

        controller_selection = self.handler.editor.controller_selections[controller_id]
        controller_selection.activate()

        # Assign color based on activation order using singleton
        from .manager import MultiControllerManager

        manager = MultiControllerManager.get_instance()
        self.handler.log.debug(f'DEBUG: About to assign color to controller {controller_id}')
        self.handler.log.debug(
            f'DEBUG: Available controllers in manager: {list(manager.controllers.keys())}',
        )
        for instance_id, info in manager.controllers.items():
            self.handler.log.debug(
                f'DEBUG: Controller instance_id={instance_id}, controller_id={info.controller_id},'
                f' color={info.color}',
            )
        manager.assign_color_to_controller(controller_id)

        # Initialize to first available animation if not set
        if (
            not controller_selection.get_animation()
            and hasattr(self.handler.editor, 'film_strips')
            and self.handler.editor.film_strips
        ):
            first_animation = next(iter(self.handler.editor.film_strips.keys()))
            controller_selection.set_selection(first_animation, 0)
            self.handler.log.debug(
                f"DEBUG: Controller {controller_id} initialized to '{first_animation}', frame 0",
            )

        # Update visual collision manager
        self._update_controller_visual_indicator(controller_id)

        # Mark all film strips as dirty to update colors
        if hasattr(self.handler.editor, 'film_strips') and self.handler.editor.film_strips:
            for film_strip in self.handler.editor.film_strips.values():
                film_strip.mark_dirty()
        if (
            hasattr(self.handler.editor, 'film_strip_sprites')
            and self.handler.editor.film_strip_sprites
        ):
            for film_strip_sprite in self.handler.editor.film_strip_sprites.values():
                film_strip_sprite.dirty = 1

        self.handler.log.debug(f'DEBUG: Controller {controller_id} activated')

    def multi_controller_previous_frame(
        self,
        controller_id: int,
    ) -> None:
        """Move to previous frame for a controller.

        Args:
            controller_id: Controller ID

        """
        if controller_id not in self.handler.editor.controller_selections:
            self.handler.log.debug(
                f'DEBUG: Controller {controller_id} not found for previous frame',
            )
            return

        controller_selection = self.handler.editor.controller_selections[controller_id]
        animation, frame = controller_selection.get_selection()

        if not animation or animation not in self.handler.editor.film_strips:
            self.handler.log.debug(
                f'DEBUG: Controller {controller_id} has no valid animation for previous frame',
            )
            return

        strip_widget = self.handler.editor.film_strips[animation]
        if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
            frame_count = strip_widget.animated_sprite.current_animation_frame_count
            new_frame = (frame - 1) % frame_count
            controller_selection.set_frame(new_frame)

            # Scroll the film strip to show the selected frame if it's off-screen
            if hasattr(strip_widget, 'update_scroll_for_frame'):
                strip_widget.update_scroll_for_frame(new_frame)
                self.handler.log.debug(
                    f'DEBUG: Controller {controller_id} previous frame: Scrolled film strip to show'
                    f' frame {new_frame}',
                )

            # Update visual indicator
            self._update_controller_visual_indicator(controller_id)

            self.handler.log.debug(
                f'DEBUG: Controller {controller_id} previous frame: {frame} -> {new_frame}',
            )

    def multi_controller_next_frame(
        self,
        controller_id: int,
    ) -> None:
        """Move to next frame for a controller.

        Args:
            controller_id: Controller ID

        """
        if controller_id not in self.handler.editor.controller_selections:
            self.handler.log.debug(
                f'DEBUG: Controller {controller_id} not found for next frame',
            )
            return

        controller_selection = self.handler.editor.controller_selections[controller_id]
        animation, frame = controller_selection.get_selection()

        if not animation or animation not in self.handler.editor.film_strips:
            self.handler.log.debug(
                f'DEBUG: Controller {controller_id} has no valid animation for next frame',
            )
            return

        strip_widget = self.handler.editor.film_strips[animation]
        if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
            frame_count = strip_widget.animated_sprite.current_animation_frame_count
            new_frame = (frame + 1) % frame_count
            controller_selection.set_frame(new_frame)

            # Scroll the film strip to show the selected frame if it's off-screen
            if hasattr(strip_widget, 'update_scroll_for_frame'):
                strip_widget.update_scroll_for_frame(new_frame)
                self.handler.log.debug(
                    f'DEBUG: Controller {controller_id} next frame: Scrolled film strip to show'
                    f' frame {new_frame}',
                )

            # Update visual indicator
            self._update_controller_visual_indicator(controller_id)

            self.handler.log.debug(
                f'DEBUG: Controller {controller_id} next frame: {frame} -> {new_frame}',
            )

    def multi_controller_previous_animation(
        self,
        controller_id: int,
    ) -> None:
        """Move to previous animation for a controller.

        Args:
            controller_id: Controller ID

        """
        if controller_id not in self.handler.editor.controller_selections:
            self.handler.log.debug(
                f'DEBUG: Controller {controller_id} not found for previous animation',
            )
            return

        controller_selection = self.handler.editor.controller_selections[controller_id]
        current_animation, _current_frame = controller_selection.get_selection()

        if not hasattr(self.handler.editor, 'film_strips') or not self.handler.editor.film_strips:
            self.handler.log.debug(
                'DEBUG: No film strips available for controller %s previous animation',
                controller_id,
            )
            return

        # Get all animation names in order
        animation_names = list(self.handler.editor.film_strips.keys())
        if not animation_names:
            self.handler.log.debug(
                f'DEBUG: No animations available for controller {controller_id} previous animation',
            )
            return

        # Find current animation index
        try:
            current_index = animation_names.index(current_animation)
        except ValueError:
            current_index = 0

        # Move to previous animation
        new_index = (current_index - 1) % len(animation_names)
        new_animation = animation_names[new_index]

        # Try to preserve the frame index from the previous animation
        prev_strip_animated_sprite = self.handler.editor.film_strips[new_animation].animated_sprite
        assert prev_strip_animated_sprite is not None
        target_frame = controller_selection.preserve_frame_for_animation(
            new_animation,
            prev_strip_animated_sprite.current_animation_frame_count,
        )

        self.handler.log.debug(
            f"DEBUG: Controller {controller_id} previous animation: Moving to '{new_animation}',"
            f' frame {target_frame}',
        )
        controller_selection.set_selection(new_animation, target_frame)

        # Scroll the film strip view to show the selected animation if it's off-screen
        self._scroll_to_controller_animation(new_animation)

        # Update visual indicator
        self._update_controller_visual_indicator(controller_id)

    def multi_controller_next_animation(
        self,
        controller_id: int,
    ) -> None:
        """Move to next animation for a controller.

        Args:
            controller_id: Controller ID

        """
        if controller_id not in self.handler.editor.controller_selections:
            self.handler.log.debug(
                f'DEBUG: Controller {controller_id} not found for next animation',
            )
            return

        controller_selection = self.handler.editor.controller_selections[controller_id]
        current_animation, _current_frame = controller_selection.get_selection()

        if not hasattr(self.handler.editor, 'film_strips') or not self.handler.editor.film_strips:
            self.handler.log.debug(
                f'DEBUG: No film strips available for controller {controller_id} next animation',
            )
            return

        # Get all animation names in order
        animation_names = list(self.handler.editor.film_strips.keys())
        if not animation_names:
            self.handler.log.debug(
                f'DEBUG: No animations available for controller {controller_id} next animation',
            )
            return

        # Find current animation index
        try:
            current_index = animation_names.index(current_animation)
        except ValueError:
            current_index = 0

        # Move to next animation
        new_index = (current_index + 1) % len(animation_names)
        new_animation = animation_names[new_index]

        # Try to preserve the frame index from the previous animation
        next_strip_animated_sprite = self.handler.editor.film_strips[new_animation].animated_sprite
        assert next_strip_animated_sprite is not None
        target_frame = controller_selection.preserve_frame_for_animation(
            new_animation,
            next_strip_animated_sprite.current_animation_frame_count,
        )

        self.handler.log.debug(
            f"DEBUG: Controller {controller_id} next animation: Moving to '{new_animation}', frame"
            f' {target_frame}',
        )
        controller_selection.set_selection(new_animation, target_frame)

        # Scroll the film strip view to show the selected animation if it's off-screen
        self._scroll_to_controller_animation(new_animation)

        # Update visual indicator
        self._update_controller_visual_indicator(controller_id)

    # ------------------------------------------------------------------
    # Visual indicator update (internal to film strip operations)
    # ------------------------------------------------------------------

    def _update_controller_visual_indicator(
        self,
        controller_id: int,
    ) -> None:
        """Update visual indicator for a controller.

        Args:
            controller_id: Controller ID

        """
        if controller_id not in self.handler.editor.controller_selections:
            return

        controller_selection = self.handler.editor.controller_selections[controller_id]
        animation, _frame = controller_selection.get_selection()

        if not animation or animation not in self.handler.editor.film_strips:
            return

        # Get controller color
        controller_info = None
        for info in self.handler.editor.multi_controller_manager.controllers.values():
            if info.controller_id == controller_id:
                controller_info = info
                break

        if not controller_info:
            return

        # Calculate position (this would need to be implemented based on your UI layout)
        # For now, we'll use a placeholder position
        position = (100 + controller_id * 50, 100)

        # Add or update visual indicator
        if controller_id not in self.handler.editor.visual_collision_manager.indicators:
            self.handler.editor.visual_collision_manager.add_controller_indicator(
                controller_id,
                controller_info.instance_id,
                controller_info.color,
                position,
            )
        else:
            self.handler.editor.visual_collision_manager.update_controller_position(
                controller_id,
                position,
            )

    # ------------------------------------------------------------------
    # Onion skinning and frame visibility
    # ------------------------------------------------------------------

    def multi_controller_toggle_onion_skinning(
        self,
        controller_id: int,
    ) -> None:
        """Toggle onion skinning for the controller's selected frame.

        Args:
            controller_id: Controller ID to toggle onion skinning for

        """
        if controller_id not in self.handler.editor.controller_selections:
            self.handler.log.debug(
                f'DEBUG: Controller {controller_id} not found for onion skinning toggle',
            )
            return

        controller_selection = self.handler.editor.controller_selections[controller_id]
        animation, frame = controller_selection.get_selection()

        if not animation or frame is None:  # type: ignore[reportUnnecessaryComparison]
            self.handler.log.debug(
                f'DEBUG: Controller {controller_id} has no valid selection for onion skinning'
                f' toggle',
            )
            return

        # Get onion skinning manager
        from glitchygames.bitmappy.onion_skinning import get_onion_skinning_manager

        onion_manager = get_onion_skinning_manager()

        # Toggle onion skinning for this frame
        is_enabled = onion_manager.toggle_frame_onion_skinning(animation, frame)
        status = 'enabled' if is_enabled else 'disabled'

        self.handler.log.debug(
            f'DEBUG: Controller {controller_id}: Onion skinning {status} for {animation}[{frame}]',
        )
        self.handler.log.debug(
            f'Controller {controller_id}: Onion skinning {status} for {animation}[{frame}]',
        )

        # Force redraw of the canvas to show the change
        if hasattr(self.handler.editor, 'canvas') and self.handler.editor.canvas:
            self.handler.editor.canvas.force_redraw()

    def multi_controller_toggle_selected_frame_visibility(
        self,
        controller_id: int,
    ) -> None:
        """Toggle visibility of the selected frame on the canvas for comparison.

        Args:
            controller_id: Controller ID (not used but kept for consistency)

        """
        # Toggle the selected frame visibility
        self.handler.editor.selected_frame_visible = not self.handler.editor.selected_frame_visible
        status = 'visible' if self.handler.editor.selected_frame_visible else 'hidden'

        self.handler.log.debug(
            f'DEBUG: Controller {controller_id}: Selected frame {status} on canvas',
        )
        self.handler.log.debug(
            f'Controller {controller_id}: Selected frame {status} on canvas',
        )

        # Force redraw of the canvas to show the change
        if hasattr(self.handler.editor, 'canvas') and self.handler.editor.canvas:
            self.handler.editor.canvas.force_redraw()

    # ------------------------------------------------------------------
    # Frame selection
    # ------------------------------------------------------------------

    def multi_controller_select_current_frame(
        self,
        controller_id: int,
    ) -> None:
        """Select the current frame that the controller is pointing to.

        Args:
            controller_id: The ID of the controller.

        """
        self.handler.log.debug(
            f'DEBUG: multi_controller_select_current_frame called for controller {controller_id}',
        )

        if controller_id not in self.handler.editor.controller_selections:
            self.handler.log.debug(
                f'DEBUG: Controller {controller_id} not found in selections',
            )
            return

        controller_selection = self.handler.editor.controller_selections[controller_id]
        if not controller_selection.is_active():
            self.handler.log.debug(f'DEBUG: Controller {controller_id} is not active')
            return

        animation, frame = controller_selection.get_selection()
        self.handler.log.debug(
            f"DEBUG: Controller {controller_id} selecting frame {frame} in animation '{animation}'",
        )
        self.handler.log.debug(
            'DEBUG: Current global selection before update:'
            f" animation='{getattr(self.handler, 'selected_animation', 'None')}',"
            f' frame={getattr(self.handler, "selected_frame", "None")}',
        )

        # Update the canvas to show this frame
        if animation in self.handler.editor.film_strips:
            strip_widget = self.handler.editor.film_strips[animation]
            if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
                if animation in strip_widget.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                    if frame < len(strip_widget.animated_sprite._animations[animation]):  # type: ignore[reportPrivateUsage]
                        # Update the canvas to show this frame using the same mechanism as keyboard
                        # selection
                        self.handler.log.debug(
                            "DEBUG: Updating canvas to show animation '%s', frame %s",
                            animation,
                            frame,
                        )
                        self.handler.editor.canvas.show_frame(animation, frame)

                        # Store global selection state (same as keyboard selection)
                        self.handler.log.debug(
                            f"DEBUG: Setting global selection state to animation '{animation}',"
                            f' frame {frame}',
                        )
                        self.handler.editor.selected_animation = animation
                        self.handler.editor.selected_frame = frame

                        # Update film strip selection state (same as keyboard selection)
                        self.handler.log.debug(
                            'DEBUG: Calling _update_film_strip_selection_state()',
                        )
                        self.handler.editor.update_film_strip_selection_state()

                        self.handler.log.debug(
                            'DEBUG: Controller selection updated keyboard selection to animation'
                            f" '{animation}', frame {frame}",
                        )
                        selected_anim = self.handler.editor.selected_animation
                        selected_frm = self.handler.editor.selected_frame
                        self.handler.log.debug(
                            f"DEBUG: Final global selection: animation='{selected_anim}',"
                            f' frame={selected_frm}',
                        )
                    else:
                        self.handler.log.debug(
                            f"DEBUG: Frame {frame} is out of bounds for animation '{animation}'"
                            f' (max:'
                            f' {len(strip_widget.animated_sprite._animations[animation]) - 1})',  # type: ignore[reportPrivateUsage]
                        )
                else:
                    self.handler.log.debug(
                        f"DEBUG: Animation '{animation}' not found in"
                        f' strip_widget.animated_sprite._animations',
                    )
            else:
                self.handler.log.debug(
                    'DEBUG: strip_widget has no animated_sprite or animated_sprite is None',
                )
        else:
            self.handler.log.debug(f"DEBUG: Animation '{animation}' not found in film_strips")

    def _multi_controller_cancel(
        self,
        controller_id: int,
    ) -> None:
        """Cancel controller selection.

        Args:
            controller_id: The ID of the controller.

        """
        if controller_id not in self.handler.editor.controller_selections:
            return

        controller_selection = self.handler.editor.controller_selections[controller_id]
        controller_selection.deactivate()
        self.handler.log.debug(f'DEBUG: Controller {controller_id} cancelled')

    # ------------------------------------------------------------------
    # Scroll to animation
    # ------------------------------------------------------------------

    def _scroll_to_controller_animation(
        self,
        animation_name: str,
    ) -> None:
        """Scroll film strips to show the specified animation for multi-controller system."""
        if not hasattr(self.handler.editor, 'film_strips') or not self.handler.editor.film_strips:
            return

        # Get all animation names in order
        animation_names = list(self.handler.editor.film_strips.keys())
        if animation_name not in animation_names:
            return

        # Find the index of the target animation
        target_index = animation_names.index(animation_name)

        # Calculate the scroll offset needed to show this animation
        # We want to show the target animation in the visible area
        if target_index < self.handler.editor.film_strip_scroll_offset:
            # Target animation is above the visible area, scroll up
            self.handler.editor.film_strip_scroll_offset = target_index
        elif (
            target_index
            >= self.handler.editor.film_strip_scroll_offset + self.handler.editor.max_visible_strips
        ):
            # Target animation is below the visible area, scroll down
            self.handler.editor.film_strip_scroll_offset = (
                target_index - self.handler.editor.max_visible_strips + 1
            )

        # Update visibility and scroll arrows
        self.handler.editor.update_film_strip_visibility()
        self.handler.editor.update_scroll_arrows()

        self.handler.log.debug(
            f"DEBUG: Scrolled to show animation '{animation_name}' at index {target_index}, scroll"
            f' offset: {self.handler.editor.film_strip_scroll_offset}',
        )

    # ------------------------------------------------------------------
    # Reinitialize multi-controller system
    # ------------------------------------------------------------------

    def reinitialize_multi_controller_system(
        self,
        preserved_controller_selections: dict[int, tuple[str, int]] | None = None,
    ) -> None:
        """Reinitialize the multi-controller system when film strips are reconstructed.

        This ensures that existing controller selections are preserved and properly
        initialized when film strips are recreated (e.g., when loading an animation file).

        Args:
            preserved_controller_selections: Optional dict of preserved controller selections
                from before film strip reconstruction.

        """
        if 'pytest' not in sys.modules:
            self.handler.log.debug('DEBUG: Reinitializing multi-controller system')
            selection_keys = list(self.handler.editor.controller_selections.keys())
            self.handler.log.debug(f'DEBUG: Current controller_selections: {selection_keys}')
            self.handler.log.debug(
                f'DEBUG: Current film_strips: {
                    list(self.handler.editor.film_strips.keys())
                    if hasattr(self.handler.editor, "film_strips")
                    and self.handler.editor.film_strips
                    else "None"
                }',
            )

        if not self.handler.editor.controller_selections:
            if 'pytest' not in sys.modules:
                self.handler.log.debug(
                    'DEBUG: controller_selections is empty - scene was likely recreated',
                )
            return

        active_controllers = self._get_active_controllers(preserved_controller_selections)
        self.handler.log.debug(
            f'DEBUG: Found {len(active_controllers)} active controllers to preserve',
        )

        self.handler.editor.multi_controller_manager.scan_for_controllers()
        controller_count = len(self.handler.editor.multi_controller_manager.controllers)
        self.handler.log.debug(f'DEBUG: Found {controller_count} controllers in manager')

        self._reinitialize_controller_selections(active_controllers)

        selection_count = len(self.handler.editor.controller_selections)
        self.handler.log.debug(
            f'DEBUG: Multi-controller system reinitialized with'
            f' {selection_count} controller selections',
        )

    def _get_active_controllers(
        self,
        preserved_controller_selections: dict[int, tuple[str, int]] | None,
    ) -> dict[int, tuple[str, int]]:
        """Get the active controller state, either preserved or current.

        Args:
            preserved_controller_selections: Optional preserved selections.

        Returns:
            Dict mapping controller_id to (animation, frame) tuples.

        """
        if preserved_controller_selections is not None:
            self.handler.log.debug(
                f'DEBUG: Using preserved controller selections: {preserved_controller_selections}',
            )
            return preserved_controller_selections

        active_controllers: dict[int, tuple[str, int]] = {}
        num_selections = len(self.handler.editor.controller_selections)
        self.handler.log.debug(
            f'DEBUG: Checking {num_selections} existing controller selections',
        )
        for (
            controller_id,
            controller_selection,
        ) in self.handler.editor.controller_selections.items():
            is_active = controller_selection.is_active()
            self.handler.log.debug(f'DEBUG: Controller {controller_id} is_active: {is_active}')
            if is_active:
                animation, frame = controller_selection.get_selection()
                active_controllers[controller_id] = (animation, frame)
                self.handler.log.debug(
                    f'DEBUG: Storing active controller {controller_id} with animation'
                    f" '{animation}', frame {frame}",
                )
        return active_controllers

    def _reinitialize_controller_selections(
        self,
        active_controllers: dict[int, tuple[str, int]],
    ) -> None:
        """Reinitialize controller selections from the multi-controller manager.

        Args:
            active_controllers: Dict mapping controller_id to (animation, frame) tuples.

        """
        for (
            instance_id,
            controller_info,
        ) in self.handler.editor.multi_controller_manager.controllers.items():
            self.handler.log.debug(
                f'DEBUG: Processing controller {instance_id}, status:'
                f' {controller_info.status.value}',
            )
            if controller_info.status.value not in {'connected', 'assigned', 'active'}:
                continue

            controller_id = controller_info.controller_id
            self._ensure_controller_selection_exists(controller_id, instance_id)
            self._restore_controller_active_state(controller_id, active_controllers)

    def _ensure_controller_selection_exists(
        self,
        controller_id: int,
        instance_id: int,
    ) -> None:
        """Ensure a controller selection exists for the given controller.

        Args:
            controller_id: The controller ID.
            instance_id: The instance ID for creating new selections.

        """
        if controller_id not in self.handler.editor.controller_selections:
            self.handler.editor.controller_selections[controller_id] = ControllerSelection(
                controller_id,
                instance_id,
            )
            self.handler.log.debug(
                'DEBUG: Created new controller selection for controller %s (inactive)',
                controller_id,
            )
        else:
            controller_selection = self.handler.editor.controller_selections[controller_id]
            controller_selection.update_activity()
            self.handler.log.debug(
                f'DEBUG: Updated existing controller selection for controller {controller_id}',
            )

    def _restore_controller_active_state(
        self,
        controller_id: int,
        active_controllers: dict[int, tuple[str, int]],
    ) -> None:
        """Restore a controller's active state after reinitialization.

        Args:
            controller_id: The controller ID.
            active_controllers: Dict mapping controller_id to (animation, frame) tuples.

        """
        controller_selection = self.handler.editor.controller_selections[controller_id]

        if controller_id not in active_controllers:
            self.handler.log.debug(
                f'DEBUG: Controller {controller_id} was not active before reconstruction,'
                f' keeping it inactive',
            )
            return

        if not self.handler.editor.film_strips:
            self.handler.log.debug(
                f'DEBUG: No film strips available for active controller {controller_id}',
            )
            return

        # Always reset to first strip and frame 0 when loading new files
        # since animation names and structure will be different
        first_animation = next(iter(self.handler.editor.film_strips.keys()))
        controller_selection.set_selection(first_animation, 0)
        controller_selection.activate()
        self.handler.log.debug(
            f'DEBUG: Reset active controller {controller_id} to first animation'
            f" '{first_animation}', frame 0 (ignoring previous selection)",
        )
        self.handler.log.debug(
            f'DEBUG: Controller {controller_id} is now active: {controller_selection.is_active()}',
        )
        self.handler.log.debug(
            f'DEBUG: Controller {controller_id} selection: {controller_selection.get_selection()}',
        )
        self.handler.log.debug(
            f'DEBUG: Available film strips: {list(self.handler.editor.film_strips.keys())}',
        )
