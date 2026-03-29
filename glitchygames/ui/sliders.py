"""GlitchyGames UI slider, color well, and tab control components.

This module contains the SliderSprite, ColorWellSprite, and TabControlSprite widget classes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self, override

import pygame
from pygame import Rect

from glitchygames.color import MAX_COLOR_CHANNEL_VALUE, RGBA_COMPONENT_COUNT
from glitchygames.sprites import (
    BitmappySprite,
)
from glitchygames.ui.text_widgets import TextSprite

if TYPE_CHECKING:
    from typing import Protocol

    from glitchygames.events.base import HashableEvent

    class SliderProtocol(Protocol):
        """Parent that hosts slider widgets and handles slider events."""

        red_slider: SliderSprite
        green_slider: SliderSprite
        blue_slider: SliderSprite
        alpha_slider: SliderSprite
        color_well: ColorWellSprite
        slider_input_format: str
        visual_collision_manager: object

        def on_slider_event(self, event: HashableEvent, trigger: HashableEvent) -> None:
            """Handle slider value change events."""
            ...

    class TabProtocol(Protocol):
        """Parent that handles tab change events."""

        def on_tab_change_event(self, tab: object) -> None:
            """Handle tab selection change events."""
            ...


LOG = logging.getLogger('game.ui')
LOG.addHandler(logging.NullHandler())

MAX_COLOR_TEXT_INPUT_LENGTH = 3


class SliderSprite(BitmappySprite):
    """A slider sprite class."""

    log = logging.getLogger('game')

    class SliderKnobSprite(BitmappySprite):
        """A slider knob sprite class."""

        log = logging.getLogger('game')

        def __init__(
            self: Self,
            x: int,
            y: int,
            width: int,
            height: int,
            *,
            name: str | None = None,
            parent: object | None = None,
            groups: pygame.sprite.LayeredDirty[Any] | None = None,
        ) -> None:
            """Initialize a SliderKnobSprite.

            Args:
                x (int): The x coordinate of the slider knob sprite.
                y (int): The y coordinate of the slider knob sprite.
                width (int): The width of the slider knob sprite.
                height (int): The height of the slider knob sprite.
                name (str): The name of the slider knob sprite.
                parent (object): The parent object.
                groups (pygame.sprite.LayeredDirty[Any] | None): The groups.

            """
            if groups is None:
                groups = pygame.sprite.LayeredDirty()

            super().__init__(
                x=x,
                y=y,
                width=width,
                height=height,
                name=name,
                parent=parent,
                groups=groups,
            )

            self.value = 0

            self.image.fill((255, 255, 255))
            self.rect = Rect(x, y, self.width, self.height)
            self.x = x
            self.y = y

        @override
        def on_left_mouse_drag_event(
            self: Self,
            event: HashableEvent,
            trigger: HashableEvent,
        ) -> None:
            """Handle left mouse drag events.

            Args:
                event (HashableEvent): The event to handle.
                trigger (HashableEvent): The object that triggered the event.

            """
            # There's not a good way to pass any useful info, so for now, pass None
            # since we're not using the event for anything in this class.
            self.on_left_mouse_button_down_event(event)
            self.dirty = 1

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int = 256,
        height: int = 9,
        *,
        name: str | None = None,
        parent: SliderProtocol | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize a SliderSprite.

        Args:
            x (int): The x coordinate of the slider sprite.
            y (int): The y coordinate of the slider sprite.
            width (int): The width of the slider sprite.
            height (int): The height of the slider sprite.
            name (str): The name of the slider sprite.
            parent (SliderProtocol | None): The parent object.
            groups (pygame.sprite.LayeredDirty[Any] | None): The sprite groups to add the sprite to.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        # Store parent in a temporary variable
        self._temp_parent = parent

        self.log = logging.getLogger('game')  # type: ignore[misc]
        self.log.info('Initializing slider %s with parent %s', name, parent)

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            focusable=True,
            groups=groups,
        )

        # Force set parent after super init
        self.parent = self._temp_parent
        del self._temp_parent

        self.log.info(f'After super().__init__, parent is now {self.parent}')

        # Initialize base values
        self._value = 0
        self.min_x = x
        self.max_x = x + width - 5
        self.dragging = False

        # Initialize the slider knob
        self.slider_knob = BitmappySprite(
            x=x,
            y=y,
            width=5,
            height=height,
            name=f'{name}_knob',
            groups=groups,
        )
        self.slider_knob.image.fill((200, 200, 200))

        # Create text sprite and event handlers
        self._init_text_sprite(x, y, width, height, groups)

        # Ensure slider rect is properly set for mouse detection
        self.rect = pygame.Rect(x, y, width, height)

        # Ensure drag boundaries are properly set
        self.min_x = x
        self.max_x = x + width - 5

        # Set color based on slider name
        if name == 'R':
            self.color = (255, 0, 0)
        elif name == 'G':
            self.color = (0, 255, 0)
        elif name == 'B':
            self.color = (0, 0, 255)
        else:
            self.color = (128, 128, 128)

        # Set up appearance
        self.update_slider_appearance()

        # Make sure we update
        self.dirty = 2
        self.slider_knob.dirty = 2

        # Now set the initial value
        self.value = self._value

        self.log.info(f'Finished initializing slider {name}, final parent is {self.parent}')

    @property
    def value(self) -> int:
        """Get the slider value."""
        return self._value

    @value.setter
    def value(self, new_value: int) -> None:
        """Set the slider value."""
        if hasattr(self, 'slider_knob'):  # Only update knob if it exists
            self._value = max(0, min(255, new_value))
            self.slider_knob.rect.x = self.min_x + (self._value * (self.max_x - self.min_x) // 255)
            self.slider_knob.dirty = 2
            if hasattr(self, 'text_sprite'):
                # Deactivate text sprite and update text
                self.text_sprite.is_active = False
                self.text_sprite.text = str(self._value)
                self.text_sprite.update_text(self.text_sprite.text)

    def _init_text_sprite(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Initialize the text sprite and its event handlers."""
        text_x = x + width + 4  # 4 pixel gap to prevent overlap
        # Center the text sprite vertically with the slider's center, moved down 2 pixels
        text_height = 20
        slider_center_y = y + height // 2
        text_y = slider_center_y - text_height // 2 + 2

        # Calculate text box width to fit between slider end and color well start
        # This will be set by the parent scene after color well is created
        text_width = 44  # Default width, will be updated by parent scene (4 pixels wider)

        self.text_sprite = TextSprite(
            x=text_x,
            y=text_y,
            width=text_width,
            height=text_height,
            text='0',
            background_color=(0, 0, 0),  # Solid black background like color well
            groups=groups,
        )
        # Make text sprite interactive for editing
        self.text_sprite.focusable = True
        self.text_sprite.is_active = False  # Start inactive

        # Store original value for restoration
        self.original_value = self._value

        # Add keyboard event handling for text input
        def handle_text_input(event: HashableEvent) -> None:
            if not self.text_sprite.is_active:
                return
            if event.key == pygame.K_RETURN:
                self._handle_text_enter(event)
            elif event.key == pygame.K_ESCAPE:
                self._restore_original_value()
            elif (
                event.unicode.isdigit()
                or event.unicode.lower() in 'abcdef'
                or event.key == pygame.K_BACKSPACE
            ):
                self._handle_text_character_input(event)

        self.text_sprite.on_key_down_event = handle_text_input  # ty: ignore[invalid-assignment]

        # Add mouse click handling to activate text editing
        def handle_text_click(event: HashableEvent) -> bool:
            if self.text_sprite.rect.collidepoint(event.pos):
                # Store current value as original for restoration
                self.original_value = self._value
                # Clear the text box for editing
                self.text_sprite.text = ''
                self.text_sprite.is_active = True
                self.text_sprite.update_text(self.text_sprite.text)
                self.text_sprite.dirty = 2
                return True
            return False

        self.text_sprite.on_left_mouse_button_down_event = handle_text_click  # type: ignore[assignment] # ty: ignore[invalid-assignment]

    def _restore_original_value(self) -> None:
        """Restore the slider text to its original value and deactivate."""
        self.text_sprite.text = str(self.original_value)
        self.text_sprite.is_active = False
        self.text_sprite.update_text(self.text_sprite.text)

    def _handle_text_enter(self, event: HashableEvent) -> None:
        """Handle Enter key press in the slider text input."""
        if not self.text_sprite.text.strip():
            # Empty text, restore original value
            self._restore_original_value()
            return

        # Validate and apply new value
        try:
            # Check if input is hex (contains letters) or decimal
            text = self.text_sprite.text.strip().lower()
            base = 16 if any(c in 'abcdef' for c in text) else 10
            new_value = int(text, base)

            if not (0 <= new_value <= MAX_COLOR_CHANNEL_VALUE):
                self._restore_original_value()
                return

            # Valid value, update slider
            self.value = new_value

            # Convert text to appropriate format based on parent's format setting
            # Convert text to appropriate format based on parent's format setting
            if (
                hasattr(self.parent, 'slider_input_format')
                and self.parent.slider_input_format == '%X'
            ):
                self.text_sprite.text = f'{new_value:02X}'
            else:
                self.text_sprite.text = str(new_value)

            self.text_sprite.is_active = False
            self.text_sprite.update_text(self.text_sprite.text)
            self.text_sprite.dirty = 2  # Force redraw
            # Update parent scene
            if hasattr(self.parent, 'on_slider_event'):
                trigger = pygame.event.Event(0, {'name': self.name, 'value': new_value})
                self.parent.on_slider_event(event=event, trigger=trigger)
        except ValueError:
            self._restore_original_value()

    def _handle_text_character_input(self, event: HashableEvent) -> None:
        """Handle character input in the slider text input."""
        if event.key == pygame.K_BACKSPACE:
            self.text_sprite.text = self.text_sprite.text[:-1]
        else:
            self.text_sprite.text += event.unicode.lower()

        # Limit to 3 characters to allow both "255" (decimal) and "FF" (hex)
        if len(self.text_sprite.text) > MAX_COLOR_TEXT_INPUT_LENGTH:
            self.text_sprite.text = self.text_sprite.text[:MAX_COLOR_TEXT_INPUT_LENGTH]

        # Force text sprite to update and redraw
        self.text_sprite.update_text(self.text_sprite.text)
        self.text_sprite.dirty = 2

    def update_slider_appearance(self) -> None:
        """Update the slider's gradient appearance based on its color."""
        for x in range(int(self.width)):
            intensity = int((x / self.width) * 255)
            if self.name == 'R':
                color = (intensity, 0, 0)
            elif self.name == 'G':
                color = (0, intensity, 0)
            elif self.name == 'B':
                color = (0, 0, intensity)
            else:
                color = (intensity, intensity, intensity)
            pygame.draw.line(self.image, color, (x, 0), (x, self.height))

        # Draw visual indicators for multi-controller system
        self._draw_slider_visual_indicators()

    def _draw_slider_visual_indicators(self) -> None:
        """Draw visual indicators for multi-controller system on sliders."""
        if not hasattr(self, 'parent') or not self.parent:
            return

        # Check if parent has visual collision manager
        if not hasattr(self.parent, 'visual_collision_manager'):
            return

        from glitchygames.bitmappy.indicators import LocationType

        # Get slider indicators from the visual collision manager
        slider_indicators = self.parent.visual_collision_manager.get_indicators_by_location(
            LocationType.SLIDER,
        )
        if not slider_indicators:
            return

        LOG.debug('Drawing %d slider indicators on %s slider', len(slider_indicators), self.name)

        # Draw each indicator on this slider
        for indicator in slider_indicators.values():
            # Calculate position relative to this slider
            slider_x = self.rect.x
            slider_y = self.rect.y
            slider_width = self.rect.width

            # Map indicator position to slider coordinates
            # For now, use a simple mapping - this could be improved
            indicator_x = slider_x + (indicator.position[0] % slider_width)
            indicator_y = slider_y + indicator.position[1]

            # Draw the indicator based on its shape
            if indicator.shape.value == 'circle':
                # Draw circle (slider indicator)
                pygame.draw.circle(
                    self.image,
                    indicator.color,
                    (indicator_x - slider_x, indicator_y - slider_y),
                    indicator.size // 2,
                )
            elif indicator.shape.value == 'square':
                # Draw square
                rect = pygame.Rect(
                    indicator_x - slider_x - indicator.size // 2,
                    indicator_y - slider_y - indicator.size // 2,
                    indicator.size,
                    indicator.size,
                )
                pygame.draw.rect(self.image, indicator.color, rect)
            elif indicator.shape.value == 'triangle':
                # Draw triangle
                points = [
                    (indicator_x - slider_x, indicator_y - slider_y - indicator.size // 2),
                    (
                        indicator_x - slider_x - indicator.size // 2,
                        indicator_y - slider_y + indicator.size // 2,
                    ),
                    (
                        indicator_x - slider_x + indicator.size // 2,
                        indicator_y - slider_y + indicator.size // 2,
                    ),
                ]
                pygame.draw.polygon(self.image, indicator.color, points)

    def update_color_well(self) -> None:
        """Update the color well with current value."""
        if hasattr(self.parent, 'color_well'):
            if self.name == 'R':
                self.parent.red_slider.value = self._value
            elif self.name == 'G':
                self.parent.green_slider.value = self._value
            elif self.name == 'B':
                self.parent.blue_slider.value = self._value
            elif self.name == 'A':
                self.parent.alpha_slider.value = self._value

            self.parent.color_well.active_color = (
                self.parent.red_slider.value,
                self.parent.green_slider.value,
                self.parent.blue_slider.value,
                self.parent.alpha_slider.value,
            )

    @override
    def on_left_mouse_button_down_event(self, event: HashableEvent) -> None:
        """Handle left mouse button down event."""
        self.log.info(f'Slider {self.name} mouse down event at {event.pos}, rect: {self.rect}')
        if self.rect.collidepoint(event.pos):
            self.log.info(f'Mouse down on slider {self.name}')
            self.dragging = True
            # Update value based on click position
            click_x = max(self.min_x, min(event.pos[0], self.max_x))
            self._value = ((click_x - self.min_x) * 255) // (self.max_x - self.min_x)

            # Create trigger event exactly like right-click does
            trigger = pygame.event.Event(0, {'name': self.name, 'value': self._value})
            if hasattr(self.parent, 'on_slider_event'):
                self.log.info(
                    f'Slider {self.name} calling on_slider_event with value {self._value}',
                )
                self.parent.on_slider_event(event=event, trigger=trigger)
            else:
                self.log.info(f'Parent {self.parent} has no on_slider_event')

            self.value = self._value  # Update display after event

            # Update text display based on current format
            if (
                hasattr(self.parent, 'slider_input_format')
                and self.parent.slider_input_format == '%X'
            ):
                self.text_sprite.text = f'{self._value:02X}'
            else:
                self.text_sprite.text = str(self._value)
            self.text_sprite.update_text(self.text_sprite.text)
            self.text_sprite.dirty = 2  # Force redraw
        else:
            self.log.info(f'Mouse click not on slider {self.name} rect')

    @override
    def on_left_mouse_button_up_event(self, event: HashableEvent) -> None:
        """Handle left mouse button up event."""
        self.log.info(f'Slider {self.name} mouse up event')
        self.dragging = False

    @override
    def on_mouse_motion_event(self, event: HashableEvent) -> None:
        """Handle mouse motion event."""
        if self.dragging:
            self.log.info(f'Dragging slider {self.name}')
            # Update value based on drag position
            drag_x = max(self.min_x, min(event.pos[0], self.max_x))
            self._value = ((drag_x - self.min_x) * 255) // (self.max_x - self.min_x)

            # Create trigger event exactly like right-click does
            trigger = pygame.event.Event(0, {'name': self.name, 'value': self._value})
            if hasattr(self.parent, 'on_slider_event'):
                self.log.info(
                    f'Slider {self.name} calling on_slider_event with value {self._value}',
                )
                self.parent.on_slider_event(event=event, trigger=trigger)
            else:
                self.log.info(f'Parent {self.parent} has no on_slider_event')

            self.value = self._value  # Update display after event

            # Update text display based on current format
            if (
                hasattr(self.parent, 'slider_input_format')
                and self.parent.slider_input_format == '%X'
            ):
                self.text_sprite.text = f'{self._value:02X}'
            else:
                self.text_sprite.text = str(self._value)
            self.text_sprite.update_text(self.text_sprite.text)
            self.text_sprite.dirty = 2  # Force redraw

    @override
    def update(self) -> None:
        """Update the slider."""
        if self.dirty:
            self.update_slider_appearance()
        super().update()
        self.slider_knob.update()
        self.text_sprite.update()


class ColorWellSprite(BitmappySprite):
    """A color well sprite class."""

    log = LOG

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str,
        *,
        parent: object | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize a ColorWellSprite.

        Args:
            x (int): The x coordinate of the color well sprite.
            y (int): The y coordinate of the color well sprite.
            width (int): The width of the color well sprite.
            height (int): The height of the color well sprite.
            name (str): The name of the color well sprite.
            parent (object): The parent object.
            groups (pygame.sprite.LayeredDirty[Any] | None): The sprite groups to add the sprite to.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            parent=parent,
            groups=groups,
        )

        # Override the surface to support alpha
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)

        self.red = 0
        self.green = 0
        self.blue = 0
        self.alpha = 255
        # Ensure callbacks attribute is initialized (inheritance issue fix)
        if not hasattr(self, 'callbacks'):
            self.callbacks = {}

    @property
    def active_color(self: Self) -> tuple[int, int, int, int]:
        """Get the active color.

        Args:
            None

        Returns:
            tuple[R: int, G: int, B: int, A: int]: The active color.

        """
        return (self.red, self.green, self.blue, self.alpha)

    @active_color.setter
    def active_color(
        self: Self,
        active_color: tuple[int, int, int] | tuple[int, int, int, int],
    ) -> None:
        """Set the active color.

        Args:
            active_color: The new active color as
                (R, G, B) or (R, G, B, A) tuple.

        """
        self.red = active_color[0]
        self.green = active_color[1]
        self.blue = active_color[2]
        # Handle both RGB and RGBA tuples
        if len(active_color) == RGBA_COMPONENT_COUNT:
            self.alpha = active_color[3]  # ty: ignore[index-out-of-bounds]
        else:
            self.alpha = 255  # Default to fully opaque if not specified
        self.dirty = 1

    @property
    def hex_color(self: Self) -> str:
        """Get the hex color.

        Args:
            None

        Returns:
            str: The hex color in #RRGGBBAA format.

        """
        hex_str = '{:02X}'
        red, green, blue, alpha = self.active_color

        red = hex_str.format(red)
        green = hex_str.format(green)
        blue = hex_str.format(blue)
        alpha = hex_str.format(alpha)

        return f'#{red}{green}{blue}{alpha}'

    @override
    def update_nested_sprites(self: Self) -> None:
        """Update the nested sprites.

        Args:
            None

        """

    @override
    def update(self: Self) -> None:
        """Update the color well sprite.

        Args:
            None

        """
        pygame.draw.rect(self.image, (128, 128, 255), Rect(0, 0, self.width, self.height), 1)

        # Draw the color directly on the alpha-compatible surface
        pygame.draw.rect(self.image, self.active_color, Rect(1, 1, self.width - 2, self.height - 2))


class TabControlSprite(BitmappySprite):
    """A tab control sprite class."""

    log = LOG

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        name: str | None = None,
        parent: TabProtocol | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize a TabControlSprite.

        Args:
            x (int): The x coordinate of the tab control sprite.
            y (int): The y coordinate of the tab control sprite.
            width (int): The width of the tab control sprite.
            height (int): The height of the tab control sprite.
            name (str | None): The name of the tab control sprite.
            parent (object | None): The parent object.
            groups (pygame.sprite.LayeredDirty[Any] | None): The sprite groups.

        """
        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            parent=parent,
            groups=groups,
        )

        # Tab options
        self.tabs = ['%d', '%X']
        self.active_tab = 0  # Start with %d (decimal)

        # Visual properties
        self.tab_height = height
        self.tab_width = width // len(self.tabs)
        self.border_color = (128, 128, 128)
        self.active_color = (200, 200, 200)
        self.inactive_color = (100, 100, 100)
        self.text_color = (0, 0, 0)

    @override
    def on_left_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle left mouse button down event.

        Args:
            event (pygame.event.Event): The pygame event.

        """
        if self.rect.collidepoint(event.pos):
            # Calculate which tab was clicked
            relative_x = event.pos[0] - self.rect.x
            clicked_tab = relative_x // self.tab_width

            if 0 <= clicked_tab < len(self.tabs):
                self.active_tab = clicked_tab
                self.dirty = 2  # Force redraw
                self.log.info(f'Tab control: Switched to tab {self.tabs[self.active_tab]}')

                # Notify parent if it has a tab change handler
                if hasattr(self.parent, 'on_tab_change_event'):
                    self.parent.on_tab_change_event(self.tabs[self.active_tab])

    @override
    def update(self: Self) -> None:
        """Update the tab control sprite.

        Args:
            None

        """
        if self.dirty:
            # Clear the surface
            self.image.fill((0, 0, 0, 0))  # Transparent background

            # Draw tabs
            for i, tab_text in enumerate(self.tabs):
                tab_x = i * self.tab_width
                tab_rect = pygame.Rect(tab_x, 0, self.tab_width, self.tab_height)

                # Choose colors based on active state
                bg_color = self.active_color if i == self.active_tab else self.inactive_color

                # Draw tab background
                pygame.draw.rect(self.image, bg_color, tab_rect)
                pygame.draw.rect(self.image, self.border_color, tab_rect, 1)

                # Draw tab text
                try:
                    font = pygame.font.Font(None, 16)
                    text_surface = font.render(tab_text, True, self.text_color)  # noqa: FBT003
                    text_rect = text_surface.get_rect(center=tab_rect.center)
                    self.image.blit(text_surface, text_rect)
                except pygame.error, AttributeError:
                    # Handle font loading errors gracefully
                    pass
