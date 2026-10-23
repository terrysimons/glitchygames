"""GlitchyGames UI slider, color well, and tab control components.

This module contains the SliderSprite, ColorWellSprite, and TabControlSprite widget classes,
and the one formatter and parser for the text typed into a slider's text box.
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

    from glitchygames.events.base import HashableEvent, MouseButtonEvent, MouseMotionEvent

    class SliderProtocol(Protocol):
        """Parent that hosts slider widgets and handles slider events."""

        slider_input_format: str

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

# The slider text box formats, as the tab control names them
DECIMAL_INPUT_FORMAT = '%d'
HEX_INPUT_FORMAT = '%X'
HEX_DIGIT_LETTERS = 'abcdef'


def format_channel(value: int, input_format: str) -> str:
    """Format a color channel value for a slider text box.

    Args:
        value: The channel value (0-255).
        input_format: The text box format, HEX_INPUT_FORMAT or DECIMAL_INPUT_FORMAT.

    Returns:
        str: Two hex digits ('FF') in the hex format, otherwise decimal ('255').

    """
    if input_format == HEX_INPUT_FORMAT:
        return f'{value:02X}'
    return str(value)


def parse_channel(text: str, input_format: str) -> int | None:
    """Parse the text typed into a slider text box as a color channel value.

    The text is hex in the hex format (where "10" is 16, BUGS.md #110 item 3) or when it
    contains hex letters; otherwise it is decimal.

    Args:
        text: The typed text.
        input_format: The text box format, HEX_INPUT_FORMAT or DECIMAL_INPUT_FORMAT.

    Returns:
        int | None: The value, or None when the text is empty, unparsable or outside 0-255.

    """
    stripped_text = text.strip().lower()
    if not stripped_text:
        return None
    is_hex = input_format == HEX_INPUT_FORMAT or any(
        character in HEX_DIGIT_LETTERS for character in stripped_text
    )
    try:
        value = int(stripped_text, 16 if is_hex else 10)
    except ValueError:
        return None
    if not (0 <= value <= MAX_COLOR_CHANNEL_VALUE):
        return None
    return value


class SliderSprite(BitmappySprite):
    """A slider sprite class."""

    log = logging.getLogger('game')

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

        # self.log is the class-level SliderSprite.log (logging.getLogger('game')).
        self.log.info('Initializing slider %s with parent %s', name, parent)

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            focusable=True,
            parent=parent,
            groups=groups,
        )

        # Initialize base values
        self._value = 0
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

        # The knob's left edge runs from the slider's left edge to 5 pixels (its width) short
        # of the right edge
        self.min_x = x
        self.max_x = x + width - 5

        # The track's gradient as last drawn, kept to repaint the image with (see
        # _current_gradient), and the image, size and name it was drawn for
        self._gradient: pygame.Surface | None = None
        self._gradient_drawn_on: pygame.Surface | None = None
        # The name is compared only; Sprite falls back to the class as a name (sprite.py)
        self._gradient_drawn_for: tuple[int | float, int | float, object] | None = None

        # Set up appearance
        self.update_slider_appearance()

        # Make sure we update
        self.dirty = 2
        self.slider_knob.dirty = 2

        # Now set the initial value
        self.value = self._value

    @property
    def value(self) -> int:
        """The slider value."""
        return self._value

    @value.setter
    def value(self, new_value: int) -> None:
        """Set the slider value, move the knob and show the value in the text box's format.

        Setting the value ends any editing in the text box.
        """
        # __init__ makes the knob and the text sprite before it first sets the value
        self._value = max(0, min(MAX_COLOR_CHANNEL_VALUE, new_value))
        self.slider_knob.rect.x = self.min_x + (
            self._value * (self.max_x - self.min_x) // MAX_COLOR_CHANNEL_VALUE
        )
        self.slider_knob.dirty = 2
        # Deactivate text sprite and update text
        self.text_sprite.is_active = False
        self.text_sprite.text = format_channel(self._value, self.input_format)
        self.text_sprite.update_text(self.text_sprite.text)
        self.text_sprite.dirty = 2  # Force redraw

    @property
    def input_format(self) -> str:
        """The text box format: the parent's slider_input_format, decimal without a parent."""
        return getattr(self.parent, 'slider_input_format', DECIMAL_INPUT_FORMAT)

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
                self.commit_text(event=event)
            elif event.key == pygame.K_ESCAPE:
                self._restore_original_value()
            elif (
                event.unicode.isdigit()
                or event.unicode.lower() in HEX_DIGIT_LETTERS
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
        """Restore the slider text to its original value, in the active format, and deactivate.

        It was always written in decimal, even on the hex tab.
        """
        self.text_sprite.text = format_channel(self.original_value, self.input_format)
        self.text_sprite.is_active = False
        self.text_sprite.update_text(self.text_sprite.text)

    def commit_text(self, *, event: HashableEvent) -> None:
        """Commit the text typed into the text box: the one path for Enter and click-away.

        Valid text sets the value and tells the parent, so the color well and the canvas
        color follow; empty, unparsable or out-of-range text restores the value the box held
        when editing began. Either way the text box stops editing.

        Args:
            event: The event that commits the text (the Enter key, or the click elsewhere).

        """
        new_value = parse_channel(self.text_sprite.text, self.input_format)
        if new_value is None:
            self._restore_original_value()
            return

        self.value = new_value
        # Update original value for future restorations
        self.original_value = new_value
        self._notify_parent(event=event)

    def _notify_parent(self, *, event: HashableEvent) -> None:
        """Tell the parent the slider's value changed, so it can update its color.

        Args:
            event: The event that changed the value.

        """
        if self.parent is None:
            self.log.info('Slider %s has no parent to notify', self.name)
            return
        trigger = pygame.event.Event(0, {'name': self.name, 'value': self._value})
        self.parent.on_slider_event(event=event, trigger=trigger)

    def _set_value_from_mouse(self, event: HashableEvent) -> None:
        """Set the value from the mouse's x position on the slider and notify the parent.

        Args:
            event: The mouse event.

        """
        mouse_x = max(self.min_x, min(event.pos[0], self.max_x))
        self.value = ((mouse_x - self.min_x) * MAX_COLOR_CHANNEL_VALUE) // (self.max_x - self.min_x)
        self._notify_parent(event=event)

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
        """Draw the slider's gradient on its image, column by column, and keep a copy of it."""
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
        self._gradient = self.image.copy()
        self._gradient_drawn_on = self.image
        self._gradient_drawn_for = (self.width, self.height, self.name)

    def _current_gradient(self) -> pygame.Surface | None:
        """The kept gradient, when it was drawn for the slider's image, size and name.

        The slider is dirty every frame (dirty = 2), but its gradient depends only on these,
        so it is drawn column by column only when one of them changed; otherwise the kept copy
        repaints the image in one blit. The image holds only the gradient: the knob and the
        text box are sprites of their own.

        Returns:
            pygame.Surface | None: The kept gradient, or None when it must be drawn again.

        """
        if self._gradient_drawn_on is not self.image or self._gradient_drawn_for != (
            self.width,
            self.height,
            self.name,
        ):
            return None
        return self._gradient

    @override
    def on_left_mouse_button_down_event(self, event: MouseButtonEvent) -> None:
        """Handle left mouse button down event."""
        self.log.info('Slider %s mouse down event at %s, rect: %s', self.name, event.pos, self.rect)
        if self.rect.collidepoint(event.pos):
            self.log.info('Mouse down on slider %s', self.name)
            self.dragging = True
            self._set_value_from_mouse(event)
        else:
            self.log.info('Mouse click not on slider %s rect', self.name)

    @override
    def on_left_mouse_button_up_event(self, event: MouseButtonEvent) -> None:
        """Handle left mouse button up event."""
        self.log.info('Slider %s mouse up event', self.name)
        self.dragging = False

    @override
    def on_mouse_motion_event(self, event: MouseMotionEvent) -> None:
        """Handle mouse motion event."""
        if self.dragging:
            self.log.info('Dragging slider %s', self.name)
            self._set_value_from_mouse(event)

    @override
    def update(self) -> None:
        """Update the slider."""
        if self.dirty:
            gradient = self._current_gradient()
            if gradient is None:
                self.update_slider_appearance()
            else:
                self.image.blit(gradient, (0, 0))
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

    @property
    def active_color(self: Self) -> tuple[int, int, int, int]:
        """The active color.

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
            self.alpha = active_color[3]
        else:
            self.alpha = 255  # Default to fully opaque if not specified
        self.dirty = 1

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
        self.tabs: list[str] = [DECIMAL_INPUT_FORMAT, HEX_INPUT_FORMAT]
        self.active_tab: int = 0  # Start with %d (decimal)

        # Visual properties
        self.tab_height = height
        self.tab_width = width // len(self.tabs)
        self.border_color = (128, 128, 128)
        self.active_color = (200, 200, 200)
        self.inactive_color = (100, 100, 100)
        self.text_color = (0, 0, 0)

    @override
    def on_left_mouse_button_down_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle left mouse button down event.

        Args:
            event (MouseButtonEvent): The pygame event.

        """
        if self.rect.collidepoint(event.pos):
            # Calculate which tab was clicked
            relative_x = int(event.pos[0] - self.rect.x)
            clicked_tab = relative_x // self.tab_width

            if 0 <= clicked_tab < len(self.tabs):
                self.active_tab = clicked_tab
                self.dirty = 2  # Force redraw
                self.log.info('Tab control: Switched to tab %s', self.tabs[self.active_tab])

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
                    text_surface = font.render(tab_text, True, self.text_color)  # ruff: ignore[boolean-positional-value-in-call]
                    text_rect = text_surface.get_rect(center=tab_rect.center)
                    self.image.blit(text_surface, text_rect)
                except pygame.error, AttributeError:
                    # Handle font loading errors gracefully
                    pass
