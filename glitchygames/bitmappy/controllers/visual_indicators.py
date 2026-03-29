"""Visual indicator operations for the Bitmappy editor's controller system.

Provides the VisualIndicators delegate with methods for rendering, drawing, creating,
and updating visual indicators, collision avoidance, and mode change dirty marking.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pygame

from glitchygames.bitmappy.controllers.modes import ControllerMode  # noqa: TC001 - used at runtime
from glitchygames.bitmappy.controllers.selection import (
    ControllerSelection,  # noqa: TC001 - used at runtime
)
from glitchygames.sprites import BitmappySprite

if TYPE_CHECKING:
    from glitchygames.bitmappy.controllers.event_handler import ControllerEventHandler
    from glitchygames.bitmappy.indicators import VisualIndicator

log = logging.getLogger('game.tools.bitmappy.controllers.visual_indicators')
log.addHandler(logging.NullHandler())


class VisualIndicators:
    """Delegate providing visual indicator operations for controllers.

    All handler state is accessed via self.handler (the ControllerEventHandler).
    """

    def __init__(self, handler: ControllerEventHandler) -> None:
        """Initialize the visual indicators delegate.

        Args:
            handler: The ControllerEventHandler that owns this delegate.

        """
        self.handler = handler

    # ------------------------------------------------------------------
    # Canvas visual indicator update
    # ------------------------------------------------------------------

    def update_controller_canvas_visual_indicator(
        self,
        controller_id: int,
    ) -> None:
        """Update the visual indicator for a controller's canvas position."""
        # Get controller info
        controller_info = self.handler.editor.multi_controller_manager.get_controller_info(
            controller_id,
        )
        if not controller_info:
            return

        # Get current canvas position
        position = self.handler.editor.mode_switcher.get_controller_position(controller_id)
        if not position:
            return

        # Update visual indicator
        if hasattr(self.handler.editor, 'visual_collision_manager'):
            # Remove old indicator
            self.handler.editor.visual_collision_manager.remove_controller_indicator(controller_id)

            # Add new canvas indicator
            from glitchygames.bitmappy.indicators.collision import LocationType

            self.handler.editor.visual_collision_manager.add_controller_indicator(
                controller_id,
                controller_info.instance_id,
                controller_info.color,
                position.position,
                LocationType.CANVAS,
            )

    # ------------------------------------------------------------------
    # Mode change visual indicator update
    # ------------------------------------------------------------------

    def update_controller_visual_indicator_for_mode(
        self,
        controller_id: int,
        new_mode: ControllerMode,
    ) -> None:
        """Update visual indicator for controller's new mode.

        Args:
            controller_id: Controller ID
            new_mode: New mode (ControllerMode enum)

        """
        self.handler.log.debug(
            f'DEBUG: Updating visual indicator for controller {controller_id} to mode'
            f' {new_mode.value} (selected controller)',
        )

        # Get controller info
        controller_info = self.handler.editor.multi_controller_manager.get_controller_info(
            controller_id,
        )
        if not controller_info:
            self.handler.log.debug(
                f'DEBUG: No controller info found for controller {controller_id}',
            )
            return

        # Get location type for new mode
        location_type = self.handler.editor.mode_switcher.get_controller_location_type(
            controller_id,
        )
        if not location_type:
            self.handler.log.debug(
                f'DEBUG: No location type found for controller {controller_id}',
            )
            return

        self.handler.log.debug(
            f'DEBUG: Location type for controller {controller_id}: {location_type}',
        )

        position = self._get_controller_mode_position(controller_id, new_mode)

        self._update_visual_collision_indicator(
            controller_id,
            controller_info,
            position,
            location_type,
        )
        self._mark_dirty_for_mode_change(controller_id, location_type)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]

    def _get_controller_mode_position(
        self,
        controller_id: int,
        new_mode: ControllerMode,
    ) -> tuple[int, int]:
        """Get the position for a controller in its new mode.

        Args:
            controller_id: Controller ID.
            new_mode: New mode (ControllerMode enum).

        Returns:
            The (x, y) position tuple.

        """
        position_data = self.handler.editor.mode_switcher.get_controller_position(controller_id)
        if position_data and position_data.is_valid:
            self.handler.log.debug(
                f'DEBUG: Using saved position for controller {controller_id}:'
                f' {position_data.position}',
            )
            return position_data.position

        # Default position based on mode
        if new_mode.value == 'canvas':
            position = (0, 0)  # Start at top-left of canvas
        elif new_mode.value in {'r_slider', 'g_slider', 'b_slider'}:
            position = (0, 0)  # Start at top of slider
        else:  # film_strip
            position = (100, 100)  # Default position
        self.handler.log.debug(
            f'DEBUG: Using default position for controller {controller_id}: {position}',
        )
        return position

    def _update_visual_collision_indicator(
        self,
        controller_id: int,
        controller_info: Any,
        position: tuple[int, int],
        location_type: Any,
    ) -> None:
        """Update the visual collision manager indicator for a controller.

        Args:
            controller_id: Controller ID.
            controller_info: Controller info object with instance_id and color.
            position: The (x, y) position.
            location_type: The LocationType for the indicator.

        """
        if not hasattr(self.handler.editor, 'visual_collision_manager'):
            self.handler.log.debug('DEBUG: No visual_collision_manager found')
            return

        self.handler.log.debug(
            f'DEBUG: Adding new indicator for controller {controller_id} at {position} with'
            f' location type {location_type}',
        )
        # Remove any existing indicator for this controller first
        self.handler.editor.visual_collision_manager.remove_controller_indicator(controller_id)
        # Add new indicator for the new mode
        self.handler.editor.visual_collision_manager.add_controller_indicator(
            controller_id,
            controller_info.instance_id,
            controller_info.color,
            position,
            location_type,
        )
        self.handler.log.debug(
            f'DEBUG: Updated visual indicator for controller {controller_id} at {position}',
        )

    # ------------------------------------------------------------------
    # Mode change dirty marking
    # ------------------------------------------------------------------

    def _mark_dirty_for_mode_change(
        self,
        controller_id: int,
        location_type: str,
    ) -> None:
        """Mark appropriate areas as dirty after a controller mode change.

        Args:
            controller_id: Controller ID.
            location_type: The LocationType for the new mode.

        """
        self._mark_dirty_for_specific_mode(controller_id, location_type)

        # Also mark film strips as dirty to ensure old triangles are removed
        # This is needed because film strips use controller_selections, not
        # VisualCollisionManager
        if hasattr(self.handler.editor, 'film_strips'):
            for strip_widget in self.handler.editor.film_strips.values():
                strip_widget.mark_dirty()
            self.handler.log.debug('DEBUG: Marked film strips as dirty to remove old indicators')

        # Also force canvas redraw to ensure old canvas indicators are removed
        # This is needed because canvas visual indicators are drawn on the canvas surface
        if hasattr(self.handler.editor, 'canvas'):
            self.handler.editor.canvas.force_redraw()
            self.handler.log.debug('DEBUG: Forced canvas redraw to remove old indicators')

    def _mark_dirty_for_specific_mode(
        self,
        controller_id: int,
        location_type: str,
    ) -> None:
        """Mark mode-specific areas as dirty.

        Args:
            controller_id: Controller ID.
            location_type: The LocationType for the new mode.

        """
        from glitchygames.bitmappy.indicators.collision import LocationType

        if location_type == LocationType.CANVAS:
            if hasattr(self.handler.editor, 'canvas'):
                self.handler.editor.canvas.force_redraw()
                self.handler.log.debug(
                    f'DEBUG: Forced canvas redraw for controller {controller_id}',
                )
        elif location_type == LocationType.SLIDER:
            if hasattr(self.handler.editor, 'red_slider'):
                self.handler.editor.red_slider.text_sprite.dirty = 2
            if hasattr(self.handler.editor, 'green_slider'):
                self.handler.editor.green_slider.text_sprite.dirty = 2
            if hasattr(self.handler.editor, 'blue_slider'):
                self.handler.editor.blue_slider.text_sprite.dirty = 2
            self.handler.editor.dirty = 1
            self.handler.log.debug(
                f'DEBUG: Marked sliders and scene as dirty for controller {controller_id}',
            )
        elif location_type == LocationType.FILM_STRIP:
            if hasattr(self.handler.editor, 'film_strips'):
                for strip_widget in self.handler.editor.film_strips.values():
                    strip_widget.mark_dirty()
            self.handler.log.debug(
                f'DEBUG: Marked film strips as dirty for controller {controller_id}',
            )

    # ------------------------------------------------------------------
    # Render visual indicators (main entry point)
    # ------------------------------------------------------------------

    def render_visual_indicators(self) -> None:
        """Render visual indicators for multi-controller system."""
        # Initialize controller selections if needed
        if not hasattr(self.handler.editor, 'controller_selections'):
            self.handler.editor.controller_selections = {}

        # Initialize mode switcher if needed
        if not hasattr(self.handler.editor, 'mode_switcher'):
            from glitchygames.bitmappy.controllers.modes import ModeSwitcher

            self.handler.editor.mode_switcher = ModeSwitcher()

        # Initialize multi-controller manager if needed
        if not hasattr(self.handler.editor, 'multi_controller_manager'):
            from glitchygames.bitmappy.controllers.manager import MultiControllerManager

            self.handler.editor.multi_controller_manager = MultiControllerManager()

        # Scan for new controllers
        if hasattr(self.handler.editor, 'multi_controller_manager'):
            self.handler.editor.multi_controller_manager.scan_for_controllers()

        # Register any new controllers
        self._register_new_controllers()

        # Get the screen surface
        screen = pygame.display.get_surface()
        if not screen:
            return

        # Update all slider indicators with collision avoidance
        self._update_all_slider_indicators()

        # Update film strip controller selections
        self._update_film_strip_controller_selections()

        # Update canvas indicators
        self._update_canvas_indicators()

    # ------------------------------------------------------------------
    # Slider indicator sprites
    # ------------------------------------------------------------------

    def _create_slider_indicator_sprite(
        self,
        controller_id: int,
        color: tuple[int, ...],
        slider_rect: pygame.FRect | pygame.Rect,
    ) -> BitmappySprite:
        """Create a proper Bitmappy sprite for slider indicator.

        Returns:
            BitmappySprite: The result.

        """
        # Create a circular indicator sprite
        indicator_size = 16
        center_x = slider_rect.x + slider_rect.width / 2
        center_y = slider_rect.y + slider_rect.height / 2

        # Create the sprite
        indicator = BitmappySprite(
            name=f'SliderIndicator_{controller_id}',
            x=center_x - indicator_size // 2,
            y=center_y - indicator_size // 2,
            width=indicator_size,
            height=indicator_size,
            groups=self.handler.editor.all_sprites,
        )

        # Make the background transparent
        indicator.image.set_colorkey((0, 0, 0))  # Make black transparent
        indicator.image.fill((0, 0, 0))  # Fill with black first

        # Draw the indicator on the sprite surface
        pygame.draw.circle(indicator.image, color, (indicator_size // 2, indicator_size // 2), 8)
        pygame.draw.circle(
            indicator.image,
            (255, 255, 255),
            (indicator_size // 2, indicator_size // 2),
            8,
            2,
        )

        return indicator

    def _update_slider_indicator(
        self,
        controller_id: int,
        color: tuple[int, ...],
    ) -> None:
        """Update or create slider indicator for a controller."""
        # Remove any existing indicator for this controller
        self._remove_slider_indicator(controller_id)

        # Get the controller's current mode to determine which slider
        if hasattr(self.handler.editor, 'mode_switcher'):
            controller_mode = self.handler.editor.mode_switcher.get_controller_mode(controller_id)

            # Create indicator on the appropriate slider based on mode
            if (
                controller_mode
                and controller_mode.value == 'r_slider'
                and hasattr(self.handler.editor, 'red_slider')
            ):
                indicator = self._create_slider_indicator_sprite(
                    controller_id,
                    color,
                    self.handler.editor.red_slider.rect,
                )
                self.handler.slider_indicators[controller_id] = indicator

            elif (
                controller_mode
                and controller_mode.value == 'g_slider'
                and hasattr(self.handler.editor, 'green_slider')
            ):
                indicator = self._create_slider_indicator_sprite(
                    controller_id,
                    color,
                    self.handler.editor.green_slider.rect,
                )
                self.handler.slider_indicators[controller_id] = indicator

            elif (
                controller_mode
                and controller_mode.value == 'b_slider'
                and hasattr(self.handler.editor, 'blue_slider')
            ):
                indicator = self._create_slider_indicator_sprite(
                    controller_id,
                    color,
                    self.handler.editor.blue_slider.rect,
                )
                self.handler.slider_indicators[controller_id] = indicator

    def _update_all_slider_indicators(self) -> None:
        """Update all slider indicators with collision avoidance."""
        # Clear all existing slider indicators
        for controller_id in list(self.handler.slider_indicators.keys()):
            self._remove_slider_indicator(controller_id)

        slider_groups = self._group_controllers_by_slider()

        # Create indicators for each slider with collision avoidance
        for slider_mode, controllers in slider_groups.items():
            if controllers and len(controllers) > 0:
                self._create_slider_indicators_with_collision_avoidance(slider_mode, controllers)

    def _group_controllers_by_slider(
        self,
    ) -> dict[str, list[dict[str, Any]]]:
        """Group active controllers by their slider mode.

        Returns:
            Dict mapping slider mode strings to lists of controller info dicts.

        """
        slider_groups: dict[str, list[dict[str, Any]]] = {
            'r_slider': [],
            'g_slider': [],
            'b_slider': [],
        }

        selections = self.handler.editor.controller_selections
        for controller_id, controller_selection in selections.items():
            if not (
                controller_selection.is_active() and hasattr(self.handler.editor, 'mode_switcher')
            ):
                continue

            controller_mode = self.handler.editor.mode_switcher.get_controller_mode(controller_id)
            if not (controller_mode and controller_mode.value in slider_groups):
                continue

            controller_info = self.handler.find_controller_info(controller_id)
            if controller_info:
                slider_groups[controller_mode.value].append({
                    'controller_id': controller_id,
                    'color': controller_info.color,
                })

        return slider_groups

    def _create_slider_indicators_with_collision_avoidance(  # noqa: C901
        self,
        slider_mode: str,
        controllers: list[dict[str, Any]],
    ) -> None:
        """Create slider indicators with collision avoidance for multiple controllers."""
        # Get the appropriate slider
        slider = None
        if slider_mode == 'r_slider' and hasattr(self.handler.editor, 'red_slider'):
            slider = self.handler.editor.red_slider
        elif slider_mode == 'g_slider' and hasattr(self.handler.editor, 'green_slider'):
            slider = self.handler.editor.green_slider
        elif slider_mode == 'b_slider' and hasattr(self.handler.editor, 'blue_slider'):
            slider = self.handler.editor.blue_slider

        if not slider:
            return

        # Sort controllers by color priority (same as film strip)
        def get_color_priority(controller: dict[str, object]) -> int:
            color = controller['color']
            if color == (255, 0, 0):  # Red
                return 0
            if color == (0, 255, 0):  # Green
                return 1
            if color == (0, 0, 255):  # Blue
                return 2
            if color == (255, 255, 0):  # Yellow
                return 3
            return 999  # Unknown colors go last

        controllers.sort(key=get_color_priority)

        # Calculate positioning with collision avoidance
        indicator_size = 16
        indicator_spacing = 20  # Space between indicator centers

        # Calculate total width needed for all indicators
        total_width = (len(controllers) - 1) * indicator_spacing

        # Calculate starting position to center the group
        slider_rect = slider.rect
        assert slider_rect is not None
        start_x = int(slider_rect.centerx) - (total_width // 2)
        center_y = int(slider_rect.centery)

        # Create indicators with proper spacing
        current_x = start_x
        for controller in controllers:
            self._create_single_slider_indicator(
                controller,
                current_x,
                center_y,
                indicator_size,
            )
            current_x += indicator_spacing

    def _create_single_slider_indicator(
        self,
        controller: dict[str, Any],
        center_x: int,
        center_y: int,
        indicator_size: int,
    ) -> None:
        """Create a single slider indicator sprite for a controller.

        Args:
            controller: Controller info dict with 'controller_id' and 'color'.
            center_x: X center position for the indicator.
            center_y: Y center position for the indicator.
            indicator_size: Size of the indicator in pixels.

        """
        indicator = BitmappySprite(
            name=f'SliderIndicator_{controller["controller_id"]}',
            x=int(center_x - indicator_size // 2),
            y=int(center_y - indicator_size // 2),
            width=indicator_size,
            height=indicator_size,
            groups=self.handler.editor.all_sprites,
        )

        # Make the background transparent
        indicator.image.set_colorkey((0, 0, 0))
        indicator.image.fill((0, 0, 0))

        # Draw the indicator
        half_size = indicator_size // 2
        pygame.draw.circle(
            indicator.image,
            controller['color'],
            (half_size, half_size),
            8,
        )
        pygame.draw.circle(
            indicator.image,
            (255, 255, 255),
            (half_size, half_size),
            8,
            2,
        )

        # Store the indicator
        self.handler.slider_indicators[controller['controller_id']] = indicator

    # ------------------------------------------------------------------
    # Film strip controller selections
    # ------------------------------------------------------------------

    def _update_film_strip_controller_selections(self) -> None:
        """Update film strip controller selections for all animations."""
        self.handler.film_strip_controller_selections.clear()

        if not hasattr(self.handler.editor, 'controller_selections'):
            return

        selections = self.handler.editor.controller_selections
        for controller_id, controller_selection in selections.items():
            self._process_film_strip_controller_selection(controller_id, controller_selection)

    def _process_film_strip_controller_selection(
        self,
        controller_id: int,
        controller_selection: ControllerSelection,
    ) -> None:
        """Process a single controller selection for film strip mode.

        Args:
            controller_id: The controller ID.
            controller_selection: The controller selection object.

        """
        if not controller_selection.is_active():
            return

        controller_mode = None
        if hasattr(self.handler.editor, 'mode_switcher'):
            controller_mode = self.handler.editor.mode_switcher.get_controller_mode(controller_id)

        if not (controller_mode and controller_mode.value == 'film_strip'):
            return

        animation, frame = controller_selection.get_selection()

        controller_info = self.handler.find_controller_info(controller_id)
        if not controller_info:
            return

        # Only include controllers that have been properly initialized (not default gray)
        if not animation or controller_info.color == (128, 128, 128):
            return

        # Group by animation
        if animation not in self.handler.film_strip_controller_selections:
            self.handler.film_strip_controller_selections[animation] = {}

        self.handler.film_strip_controller_selections[animation][controller_id] = {
            'controller_id': controller_id,
            'frame': frame,
            'color': controller_info.color,
        }

    # ------------------------------------------------------------------
    # Canvas indicators
    # ------------------------------------------------------------------

    def _update_canvas_indicators(self) -> None:
        """Update canvas indicators for controllers in canvas mode."""
        if not hasattr(self.handler.editor, 'canvas') or not self.handler.editor.canvas:
            return

        canvas_controllers = self._collect_canvas_controllers()

        if canvas_controllers:
            self.handler.canvas_controller_indicators = canvas_controllers
            if hasattr(self.handler.editor.canvas, 'canvas_interface'):
                self.handler.editor.canvas.canvas_interface.controller_indicators = (  # type: ignore[attr-defined] # ty: ignore[invalid-assignment]
                    canvas_controllers
                )
            self.handler.editor.canvas.force_redraw()
        else:
            self.handler.canvas_controller_indicators = []
            if hasattr(self.handler.editor.canvas, 'canvas_interface'):
                self.handler.editor.canvas.canvas_interface.controller_indicators = []  # type: ignore[attr-defined] # ty: ignore[invalid-assignment]

    def _collect_canvas_controllers(self) -> list[dict[str, Any]]:
        """Collect all active controllers in canvas mode with their positions.

        Returns:
            List of dicts with controller_id, position, and color.

        """
        canvas_controllers: list[dict[str, Any]] = []
        selections = self.handler.editor.controller_selections
        for controller_id, controller_selection in selections.items():
            if not controller_selection.is_active():
                continue

            controller_mode = None
            if hasattr(self.handler.editor, 'mode_switcher'):
                controller_mode = self.handler.editor.mode_switcher.get_controller_mode(
                    controller_id,
                )

            if not (controller_mode and controller_mode.value == 'canvas'):
                continue

            controller_info = self.handler.find_controller_info(controller_id)
            if not controller_info:
                continue

            position = self.handler.editor.mode_switcher.get_controller_position(controller_id)
            if position and position.is_valid:
                canvas_controllers.append({
                    'controller_id': controller_id,
                    'position': position.position,
                    'color': controller_info.color,
                })
        return canvas_controllers

    # ------------------------------------------------------------------
    # Controller registration
    # ------------------------------------------------------------------

    def _register_new_controllers(self) -> None:
        """Register any new controllers that have been detected."""
        if not hasattr(self.handler.editor, 'multi_controller_manager'):
            return

        # Check for any controllers that aren't registered yet
        for (
            instance_id,
            controller_info,
        ) in self.handler.editor.multi_controller_manager.controllers.items():
            controller_id = controller_info.controller_id
            if controller_id not in self.handler.editor.controller_selections:
                # Register new controller
                from glitchygames.bitmappy.controllers.selection import ControllerSelection

                self.handler.editor.controller_selections[controller_id] = ControllerSelection(
                    controller_id,
                    instance_id,
                )

                # Activate the controller
                self.handler.editor.controller_selections[controller_id].activate()

                # Register with mode switcher
                if hasattr(self.handler.editor, 'mode_switcher'):
                    from glitchygames.bitmappy.controllers.modes import ControllerMode

                    self.handler.editor.mode_switcher.register_controller(
                        controller_id,
                        ControllerMode.FILM_STRIP,
                    )

                self.handler.log.debug(
                    f'BitmapEditorScene: Registered and activated new controller {controller_id}'
                    f' (instance {instance_id})',
                )

    def _remove_slider_indicator(self, controller_id: int) -> None:
        """Remove slider indicator for a controller."""
        if (
            hasattr(self.handler, 'slider_indicators')
            and controller_id in self.handler.slider_indicators
        ):
            indicator = self.handler.slider_indicators[controller_id]
            # Remove from sprite groups
            if hasattr(self.handler.editor, 'all_sprites'):
                self.handler.editor.all_sprites.remove(indicator)
            # Remove from tracking
            del self.handler.slider_indicators[controller_id]

    def _draw_visual_indicator(
        self,
        screen: pygame.Surface,
        indicator: VisualIndicator,
    ) -> None:
        """Draw a single visual indicator on the screen."""
        if not indicator.is_visible:
            self.handler.log.debug(
                f'DEBUG: Indicator for controller {indicator.controller_id} is not visible',
            )
            return

        # Calculate final position with offset
        final_x = indicator.position[0] + indicator.offset[0]
        final_y = indicator.position[1] + indicator.offset[1]

        self.handler.log.debug(
            f'DEBUG: Drawing indicator for controller {indicator.controller_id} at ({final_x},'
            f' {final_y}) with shape {indicator.shape.value}',
        )

        # Draw based on shape
        if indicator.shape.value == 'triangle':
            # Draw triangle (film strip indicator)
            points = [
                (final_x, final_y - indicator.size // 2),
                (final_x - indicator.size // 2, final_y + indicator.size // 2),
                (final_x + indicator.size // 2, final_y + indicator.size // 2),
            ]
            pygame.draw.polygon(screen, indicator.color, points)
        elif indicator.shape.value == 'square':
            # Draw square (canvas indicator)
            rect = pygame.Rect(
                final_x - indicator.size // 2,
                final_y - indicator.size // 2,
                indicator.size,
                indicator.size,
            )
            pygame.draw.rect(screen, indicator.color, rect)
        elif indicator.shape.value == 'circle':
            # Draw circle (slider indicator)
            pygame.draw.circle(screen, indicator.color, (final_x, final_y), indicator.size // 2)
