"""GlitchyGames UI text display components.

This module contains TextSprite, TextBoxSprite, Scrollbar, and MultiLineTextBox widget classes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self, override

try:
    import pyperclip
except ImportError:
    pyperclip = None  # ty: ignore[invalid-assignment]

import pygame
from pygame import Rect

from glitchygames.color import WHITE
from glitchygames.fonts import FontManager, GameFont
from glitchygames.sprites import (
    BitmappySprite,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Protocol

    from glitchygames.events.base import HashableEvent

    class TextSubmitProtocol(Protocol):
        """Parent that handles text submission events."""

        def on_text_submit_event(self, text: str) -> None:
            """Handle text submission events."""
            ...


LOG = logging.getLogger('game.ui')
LOG.addHandler(logging.NullHandler())

CURSOR_BLINK_FRAME_INTERVAL = 30
CURSOR_BLINK_HALF_SECOND = 0.5
PYGAME_MOUSE_SCROLL_UP_BUTTON = 4
PYGAME_MOUSE_SCROLL_DOWN_BUTTON = 5


class TextSprite(BitmappySprite):
    """A text sprite class."""

    log = LOG

    def __init__(
        self: Self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        name: str | None = None,
        background_color: tuple[int, ...] = (255, 0, 255),
        text_color: tuple[int, ...] = WHITE,
        alpha: int = 0,
        text: str = 'Text',
        parent: object | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize the text sprite.

        Args:
            x: X position
            y: Y position
            width: Width of the sprite
            height: Height of the sprite
            name: Name of the sprite
            background_color: Background color tuple
            text_color: Text color tuple
            alpha: Alpha value
            text: Text content
            parent: Parent object
            groups: Sprite groups

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            focusable=True,
            groups=groups,
        )

        # Store coordinates
        self._x = x
        self._y = y
        self.background_color: tuple[int, ...] = background_color
        self.text_color: tuple[int, ...] = text_color

        self.alpha: int = alpha
        self._text: str = text
        self.parent: object | None = parent
        self.all_sprites: pygame.sprite.LayeredDirty[Any] = groups

        # Make this instance also act as its own text_box for compatibility
        self.text_box = self

        # Font for text rendering (can be overridden by callers)
        self.font: GameFont = FontManager.get_font()

        # Border width for text box rendering
        self.border_width: int = 0

        # Initialize cursor state for blinking
        self._cursor_timer = 0
        self._cursor_visible = True

        self.update_text(text)

    @property
    def x(self) -> int | float:
        """Get the x position."""
        return self._x

    @x.setter
    def x(self, value: float) -> None:
        """Set the x position."""
        self._x = value
        self.rect.x = value
        self.dirty = 2

    @property
    def y(self) -> int | float:
        """Get the y position."""
        return self._y

    @y.setter
    def y(self, value: float) -> None:
        """Set the y position."""
        self._y = value
        self.rect.y = value
        self.dirty = 2

    @property
    def text(self) -> str:
        """Get the text content."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        """Set the text content."""
        if value != self._text:  # Only update if text has changed
            self._text = str(value)
            self.update_text(self._text)
            self.dirty = 2

    @override
    def update(self) -> None:
        """Update the sprite."""
        # Handle cursor blinking for active text boxes
        if self.is_active:
            old_visible = self._cursor_visible
            self._cursor_timer += 1
            # Blink every 30 frames (0.5 seconds at 60fps)
            if self._cursor_timer >= CURSOR_BLINK_FRAME_INTERVAL:
                self._cursor_visible = not self._cursor_visible
                self._cursor_timer = 0
                # Force redraw when cursor visibility changes
                if old_visible != self._cursor_visible:
                    self.dirty = 2
            # Always mark as dirty when active to ensure continuous updates
            self.dirty = 2
        else:
            # Reset dirty flag when not active
            self.dirty = 1

        if self.dirty:
            self.update_text(self._text)

    def update_text(self, text: str) -> None:
        """Update the text surface."""
        # Check if background is transparent (alpha = 0)
        rgba_length = 4
        is_transparent = len(self.background_color) == rgba_length and self.background_color[3] == 0

        # Create surface with alpha support
        self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.image = self.image.convert_alpha()

        # Fill with the sprite's background color
        if is_transparent:
            self.image.fill((0, 0, 0, 0))
        elif self.is_active:
            self.image.fill((50, 50, 50))  # Darker background when editing
        else:
            self.image.fill(self.background_color)

        font: GameFont = FontManager.get_font()
        current_text_color: tuple[int, ...] = self.text_color  # Use original text color

        text_surface, text_rect = self._render_text_with_font(
            font,
            text,
            current_text_color,
            is_transparent=is_transparent,
        )

        # Position the text in the center of our surface
        if text_rect is None:
            text_rect = text_surface.get_rect()
        target_rect = self.image.get_rect()
        text_rect.centerx = target_rect.centerx
        text_rect.centery = target_rect.centery

        # Blit text onto our surface
        self.image.blit(text_surface, text_rect)

        # Add blinking cursor if text box is active
        if self.is_active:
            self._draw_cursor(text_rect, font)

    def _render_text_with_font(
        self,
        font: GameFont,
        text: str,
        text_color: tuple[int, ...],
        *,
        is_transparent: bool,
    ) -> tuple[pygame.Surface, pygame.Rect | None]:
        """Render text using the appropriate font system.

        Handles both pygame.freetype.Font and pygame.font.Font.

        Returns:
            Tuple of (text_surface, text_rect). text_rect may be None.

        """
        text_rect = None

        if hasattr(font, 'render_to'):
            # This is a pygame.freetype.Font
            try:
                if is_transparent:
                    text_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                    text_surface.fill((0, 0, 0, 0))
                    text_rect = font.render_to(text_surface, (0, 0), str(text), text_color)
                else:
                    render_result = font.render(str(text), text_color, self.background_color)
                    if isinstance(render_result, tuple):
                        text_surface, text_rect = render_result
                    else:
                        text_surface = render_result
            except TypeError, ValueError:
                # Fall back to pygame.font style (returns surface)
                text_surface = self._render_with_pygame_font(
                    font,
                    text,
                    text_color,
                    is_transparent=is_transparent,
                )
        else:
            text_surface = self._render_with_pygame_font(
                font,
                text,
                text_color,
                is_transparent=is_transparent,
            )

        return text_surface, text_rect  # ty: ignore[invalid-return-type]

    def _render_with_pygame_font(
        self,
        font: GameFont,
        text: str,
        text_color: tuple[int, ...],
        *,
        is_transparent: bool,
    ) -> pygame.Surface:
        """Render text using pygame.font.Font.

        Returns:
            The rendered text surface.

        """
        if is_transparent:
            return (  # pyright: ignore[reportReturnType, reportUnknownVariableType]
                font.render(str(text), True, text_color)[0]  # noqa: FBT003  # pyright: ignore[reportIndexIssue, reportArgumentType]  # ty: ignore[invalid-return-type, not-subscriptable, invalid-argument-type]
                if isinstance(font.render(str(text), True, text_color), tuple)  # noqa: FBT003  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
                else font.render(str(text), True, text_color)  # noqa: FBT003  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            )
        return (  # pyright: ignore[reportReturnType, reportUnknownVariableType]
            font.render(str(text), True, text_color)[0]  # noqa: FBT003  # pyright: ignore[reportIndexIssue, reportArgumentType]  # ty: ignore[invalid-return-type, not-subscriptable, invalid-argument-type]
            if isinstance(font.render(str(text), True, text_color), tuple)  # noqa: FBT003  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            else font.render(str(text), True, text_color)  # noqa: FBT003  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        )

    def _draw_cursor(self, text_rect: pygame.Rect, _font: GameFont) -> None:
        """Draw a blinking cursor at the end of the text."""
        if self._cursor_visible:
            try:
                # Calculate cursor position at the end of the text
                cursor_x = text_rect.right + 2  # 2 pixels after the text
                cursor_y = text_rect.top
                cursor_height = text_rect.height

                # Ensure cursor is within bounds
                if cursor_x < self.width and cursor_y < self.height:
                    # Set cursor color (hover disabled)
                    cursor_color = self.text_color  # Use original text color

                    # Draw a vertical line for the cursor
                    pygame.draw.line(
                        self.image,
                        cursor_color,
                        (cursor_x, cursor_y),
                        (cursor_x, cursor_y + cursor_height),
                        2,  # 2 pixel wide cursor
                    )
            except TypeError, AttributeError:
                # Handle mock objects in tests - just skip cursor drawing
                pass

    @override
    def on_mouse_motion_event(self, event: HashableEvent) -> None:
        """Handle mouse motion events for hover effects (disabled)."""
        # Hover effects disabled for TextSprite


class TextBoxSprite(BitmappySprite):
    """A text box sprite class."""

    log = LOG

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        name: str | None = None,
        _callbacks: Callable[..., Any] | None = None,
        parent: object | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize a TextBoxSprite.

        Args:
            x (int): The x coordinate of the text box sprite.
            y (int): The y coordinate of the text box sprite.
            width (int): The width of the text box sprite.
            height (int): The height of the text box sprite.
            name (str): The name of the text box sprite.
            _callbacks (Callable): The callbacks to call when events occur.
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
        self.value = None
        self.background_color = (0, 0, 0)
        self.border_width = 1

        self.callbacks: dict[str, Any] = {}

        self.text_box = TextSprite(
            background_color=self.background_color,
            x=x,
            y=y,
            width=self.width - self.border_width,
            height=self.height - self.border_width,
            text=self.value if self.value is not None else '',
            parent=self,
            groups=groups,
        )

        self.x = x
        self.y = y

        self.text_box.x = self.x
        self.text_box.y = self.y

        self.proxies = [self.parent]

    @override
    def update_nested_sprites(self: Self) -> None:
        """Update the nested sprites.

        Args:
            None

        """
        self.text_box.dirty = self.dirty

    @override
    def update(self: Self) -> None:
        """Update the text box sprite.

        Args:
            None

        """
        if self.text_box:
            self.text_box.background_color = self.background_color
            self.image.blit(self.text_box.image, (self.x, self.y, self.width, self.height))

        # Border drawn with fixed color; hover/click visual feedback not yet implemented
        if self.border_width:
            pygame.draw.rect(
                self.image,
                (128, 128, 128),
                Rect(0, 0, self.width, self.height),
                self.border_width,
            )

    @override
    def on_left_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle left mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.background_color = (128, 128, 128)
        self.dirty = 1

    @override
    def on_left_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle left mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.background_color = (0, 0, 0)
        self.dirty = 1


class Scrollbar:
    """A reusable scrollbar component for scrollable widgets.

    Handles rendering and interaction for vertical scrollbars.
    """

    def __init__(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        total_items: int,
        visible_items: int,
        scroll_offset: float = 0,
    ) -> None:
        """Initialize the scrollbar.

        Args:
            x: X position relative to parent surface
            y: Y position relative to parent surface
            width: Scrollbar width in pixels
            height: Scrollbar track height in pixels
            total_items: Total number of items (e.g., total lines)
            visible_items: Number of visible items (e.g., visible lines)
            scroll_offset: Current scroll position (0 to max_scroll)

        """
        self.x: int | float = x
        self.y: int | float = y
        self.width: int | float = width
        self.height: int | float = height
        self.total_items: int = total_items
        self.visible_items: int = visible_items
        self.scroll_offset: float = scroll_offset

        # Visual styling
        self.track_color = (40, 40, 40)
        self.thumb_color = (128, 128, 128)
        self.thumb_hover_color = (160, 160, 160)
        self.thumb_drag_color = (180, 180, 180)

        # Interaction state
        self.is_dragging = False
        self.is_hovering = False
        self.drag_start_y = 0
        self.drag_start_offset = 0

    @property
    def max_scroll(self) -> float:
        """Maximum scroll offset."""
        return max(0, self.total_items - self.visible_items)

    @property
    def is_visible(self) -> bool:
        """Whether scrollbar should be visible."""
        return self.total_items > self.visible_items

    @property
    def thumb_height(self) -> int | float:
        """Calculate thumb height based on content ratio."""
        if self.total_items <= 0:
            return self.height
        ratio = self.visible_items / self.total_items
        return max(20, int(ratio * self.height))

    @property
    def thumb_y(self) -> int | float:
        """Calculate thumb Y position."""
        if self.max_scroll <= 0:
            return self.y
        ratio = self.scroll_offset / self.max_scroll
        available_space = self.height - self.thumb_height
        return self.y + int(ratio * available_space)

    def get_thumb_rect(self) -> pygame.Rect:
        """Get the thumb rectangle for hit testing.

        Returns:
            pygame.Rect: The thumb rect.

        """
        return pygame.Rect(self.x, self.thumb_y, self.width, self.thumb_height)

    def update(self, total_items: int, visible_items: int, scroll_offset: float) -> None:
        """Update scrollbar state.

        Args:
            total_items: New total items count
            visible_items: New visible items count
            scroll_offset: New scroll offset

        """
        self.total_items = total_items
        self.visible_items = visible_items
        self.scroll_offset = max(0, min(scroll_offset, self.max_scroll))

    def handle_mouse_down(self, mouse_pos: tuple[int, int]) -> bool:
        """Handle mouse button down event.

        Args:
            mouse_pos: Absolute mouse position

        Returns:
            True if event was handled

        """
        if not self.is_visible:
            return False

        thumb_rect = self.get_thumb_rect()

        if thumb_rect.collidepoint(mouse_pos):
            # Start dragging thumb
            self.is_dragging = True
            self.drag_start_y = mouse_pos[1]
            self.drag_start_offset = self.scroll_offset
            return True

        # Check if clicked on track (above or below thumb)
        track_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        if track_rect.collidepoint(mouse_pos):
            # Jump to clicked position
            # mouse_pos is already relative to widget, self.y is scrollbar's y in widget
            # So we need to subtract self.y to get position within scrollbar
            relative_y = mouse_pos[1] - self.y
            # Clamp to valid range
            relative_y = max(0, min(relative_y, self.height))
            ratio = relative_y / self.height
            new_offset = ratio * self.max_scroll
            self.scroll_offset = max(0, min(new_offset, self.max_scroll))
            return True

        return False

    def handle_mouse_up(self, _mouse_pos: tuple[int, int]) -> bool:
        """Handle mouse button up event.

        Args:
            _mouse_pos: Absolute mouse position

        Returns:
            True if event was handled

        """
        if self.is_dragging:
            self.is_dragging = False
            return True
        return False

    def handle_mouse_motion(self, mouse_pos: tuple[int, int]) -> bool:
        """Handle mouse motion event.

        Args:
            mouse_pos: Absolute mouse position

        Returns:
            True if event was handled

        """
        if not self.is_visible:
            self.is_hovering = False
            return False

        # Update hover state
        thumb_rect = self.get_thumb_rect()
        self.is_hovering = thumb_rect.collidepoint(mouse_pos)

        # Handle dragging
        if self.is_dragging:
            delta_y = mouse_pos[1] - self.drag_start_y
            # Convert pixel delta to scroll offset delta
            if self.height > self.thumb_height:
                scroll_per_pixel = self.max_scroll / (self.height - self.thumb_height)
                delta_scroll = delta_y * scroll_per_pixel
                new_offset = self.drag_start_offset + delta_scroll
                self.scroll_offset = max(0, min(new_offset, self.max_scroll))
            return True

        return False

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the scrollbar on the given surface.

        Args:
            surface: Surface to draw on (parent widget's image)

        """
        if not self.is_visible:
            return

        # Draw track
        pygame.draw.rect(surface, self.track_color, (self.x, self.y, self.width, self.height))

        # Choose thumb color based on state
        if self.is_dragging:
            thumb_color = self.thumb_drag_color
        elif self.is_hovering:
            thumb_color = self.thumb_hover_color
        else:
            thumb_color = self.thumb_color

        # Draw thumb
        pygame.draw.rect(
            surface,
            thumb_color,
            (self.x, self.thumb_y, self.width, self.thumb_height),
        )


class MultiLineTextBox(BitmappySprite):
    """A multi-line text box sprite class."""

    log = LOG

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        name: str | None = None,
        text: str = '',
        parent: TextSubmitProtocol | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize a MultiLineTextBox."""
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        self.log.debug(
            'Creating MultiLineTextBox: name=%s, pos=(%s, %s), size=(%s, %s)',
            name,
            x,
            y,
            width,
            height,
        )

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            parent=parent,
            groups=groups,
            focusable=True,
        )

        # Store original text for cursor position mapping first
        self._original_text = text
        self._text = text
        self.text = text
        self.is_active = False
        self.cursor_visible = True
        self.cursor_blink_time = pygame.time.get_ticks()
        self.cursor_blink_rate = 530
        self.cursor_pos = len(text)
        self._last_update_time = pygame.time.get_ticks()
        self._frame_count = 0

        # Initialize selection attributes
        self.selection_start = None
        self.selection_end = None

        # Initialize hover tracking
        self.is_hovered = False

        # Force continuous updates
        self.dirty = 2

        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.image = self.image.convert_alpha()

        # Use FontManager for consistent font handling
        self.font: GameFont = FontManager.get_font()
        self.text_color: tuple[int, ...] = WHITE
        self.cursor_color: tuple[int, ...] = WHITE
        self.base_text_color: tuple[int, ...] = WHITE  # Store base color for hover effects

        # Add scroll tracking
        self.scroll_offset: int = 0
        # Calculate line height - handle both pygame.font and pygame.freetype
        if hasattr(self.font, 'get_linesize'):
            line_height: int = self.font.get_linesize()
        else:
            # For freetype fonts, use the size attribute (it's a float, not a tuple)
            line_height = int(getattr(self.font, 'size', 24))
        # Account for top/bottom padding (5px each = 10px total)
        self.visible_lines: int = int((self.height - 10) // line_height)

        # Create scrollbar component
        scrollbar_width = 8
        self.scrollbar = Scrollbar(
            x=self.width - scrollbar_width - 2,
            y=2,
            width=scrollbar_width,
            height=self.height - 4,
            total_items=1,  # Will be updated when text is set
            visible_items=self.visible_lines,
            scroll_offset=0,
        )

    def _get_text_width(self, text: str) -> int:
        """Get text width for both pygame.font and pygame.freetype fonts.

        Returns:
            int: The text width.

        """
        if hasattr(self.font, 'get_rect'):
            # pygame.freetype.Font - use get_rect() method
            return self.font.get_rect(text).width
        # pygame.font.Font - size() is a method
        return self.font.size(text)[0]

    def _wrap_text(self, text: str, max_width: float) -> str:
        """Wrap text to fit within the specified width.

        Returns:
            str: The resulting string.

        """
        if not text:
            return text

        lines: list[str] = text.split('\n')
        wrapped_lines: list[str] = []

        for line in lines:
            if not line:  # Empty line
                wrapped_lines.append('')
                continue

            # If line already fits, keep it as is
            if self._get_text_width(line) <= max_width:
                wrapped_lines.append(line)
                continue

            # Split line into words and wrap
            words = line.split(' ')
            current_line = ''

            for word in words:
                test_line = current_line + (' ' if current_line else '') + word
                if self._get_text_width(test_line) <= max_width:
                    current_line = test_line
                elif current_line:
                    # Current line is full, start a new one
                    wrapped_lines.append(current_line)
                    current_line = word
                else:
                    # Single word is too long, force it on its own line
                    wrapped_lines.append(word)
                    current_line = ''

            # Add the last line if there's content
            if current_line:
                wrapped_lines.append(current_line)

        return '\n'.join(wrapped_lines)

    def _map_cursor_pos_to_wrapped_text(self, original_pos: int) -> int:
        """Map cursor position from original text to wrapped text position.

        Returns:
            int: The resulting integer value.

        """
        if original_pos >= len(self._original_text):
            return len(self._text)

        # Find the character at the original position
        target_char = self._original_text[original_pos]

        # Count how many times this character appears before the target position
        char_count_before_target = self._original_text[:original_pos].count(target_char)

        # Find the corresponding position in wrapped text
        wrapped_pos = 0
        char_count = 0

        for i, char in enumerate(self._text):
            if char == target_char:
                if char_count == char_count_before_target:
                    return i
                char_count += 1
            wrapped_pos = i

        # If we can't find an exact match, return the closest position
        return min(wrapped_pos, len(self._text))

    def _get_cursor_line_and_column_in_wrapped_text(
        self,
        original_cursor_pos: int,
    ) -> tuple[int, int]:
        """Get the line and column of the cursor in the wrapped text.

        Returns:
            tuple[int, int]: The cursor line and column in wrapped text.

        """
        # Map cursor position to wrapped text
        wrapped_cursor_pos = self._map_cursor_pos_to_wrapped_text(original_cursor_pos)

        # Count lines before cursor in wrapped text
        lines_before_cursor = self._text[:wrapped_cursor_pos].count('\n')

        # Find the start of the current line in wrapped text
        current_line_start = (
            self._text[:wrapped_cursor_pos].rindex('\n') + 1
            if '\n' in self._text[:wrapped_cursor_pos]
            else 0
        )

        # Calculate column position
        column_pos = wrapped_cursor_pos - current_line_start

        return lines_before_cursor, column_pos

    def _move_cursor_up(self) -> None:
        """Move cursor up one line in the wrapped text."""
        current_line, current_column = self._get_cursor_line_and_column_in_wrapped_text(
            self.cursor_pos,
        )

        if current_line > 0:
            # Move to the previous line
            wrapped_lines = self._text.split('\n')
            prev_line = wrapped_lines[current_line - 1]

            # Try to maintain the same column position, but don't exceed the line length
            target_column = min(current_column, len(prev_line))

            # Calculate the new cursor position in the original text
            new_cursor_pos = self._map_wrapped_position_to_original(current_line - 1, target_column)
            self.cursor_pos = new_cursor_pos
        else:
            # Already at the top line, move to the beginning
            self.cursor_pos = 0

    def _move_cursor_down(self) -> None:
        """Move cursor down one line in the wrapped text."""
        current_line, current_column = self._get_cursor_line_and_column_in_wrapped_text(
            self.cursor_pos,
        )

        wrapped_lines = self._text.split('\n')
        if current_line < len(wrapped_lines) - 1:
            # Move to the next line
            next_line = wrapped_lines[current_line + 1]

            # Try to maintain the same column position, but don't exceed the line length
            target_column = min(current_column, len(next_line))

            # Calculate the new cursor position in the original text
            new_cursor_pos = self._map_wrapped_position_to_original(current_line + 1, target_column)
            self.cursor_pos = new_cursor_pos
        else:
            # Already at the bottom line, move to the end
            self.cursor_pos = len(self._original_text)

    def _map_wrapped_position_to_original(self, line: int, column: int) -> int:
        """Map a position in wrapped text (line, column) back to original text position.

        Returns:
            int: The resulting integer value.

        """
        wrapped_lines = self._text.split('\n')

        if line >= len(wrapped_lines):
            return len(self._original_text)

        # Get the text up to the target position in wrapped text
        target_wrapped_pos = sum(len(wrapped_lines[i]) + 1 for i in range(line)) + column
        target_wrapped_pos = min(target_wrapped_pos, len(self._text))

        # Find the corresponding position in original text
        # Map character by character, checking position BEFORE incrementing
        for i, _char in enumerate(self._original_text):
            if i >= target_wrapped_pos:
                return i  # Return current position when we've reached target

        # If we've gone through the whole text, return the end position
        return len(self._original_text)

    @property
    def text(self) -> str:
        """Get the text content."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        """Set the text content with automatic wrapping and auto-scroll to bottom."""
        if value != self._original_text:
            # Store the original text before wrapping
            self._original_text = str(value)
            # Calculate available width for text (accounting for padding)
            available_width = self.width - 10  # 5px padding on each side
            wrapped_text = self._wrap_text(str(value), available_width)
            self._text = wrapped_text

            # Move cursor to end of ORIGINAL text for auto-scroll to work
            self.cursor_pos = len(self._original_text)

            # Auto-scroll to bottom to show latest content
            total_lines = len(self._text.split('\n'))
            if total_lines > self.visible_lines:
                self.scroll_offset = total_lines - self.visible_lines
            else:
                self.scroll_offset = 0

            # Update scrollbar state
            self.scrollbar.update(total_lines, self.visible_lines, self.scroll_offset)

            self.dirty = 2

    def _get_line_height(self) -> int:
        """Get the line height for the current font.

        Returns:
            Line height in pixels.

        """
        if hasattr(self.font, 'get_linesize'):
            return self.font.get_linesize()
        # For freetype fonts, use the size attribute (it's a float, not a tuple)
        return int(self.font.size) if hasattr(self.font, 'size') else 24  # type: ignore[arg-type]

    def _get_border_color(self) -> tuple[int, int, int]:
        """Get the border color based on active/hover state.

        Returns:
            RGB color tuple.

        """
        if self.is_active:
            return (64, 64, 255)
        if self.is_hovered:
            return (100, 150, 255)
        return WHITE

    def _render_visible_lines(self, text_color: tuple[int, ...], line_height: int) -> None:
        """Render visible text lines with scrolling."""
        if not self._text:
            return

        lines = self._text.split('\n')

        # Only auto-scroll to keep cursor visible when the textbox is active (being edited)
        if self.is_active:
            cursor_line, _ = self._get_cursor_line_and_column_in_wrapped_text(self.cursor_pos)
            if cursor_line - self.scroll_offset >= self.visible_lines:
                self.scroll_offset = cursor_line - self.visible_lines + 1
                self.scrollbar.scroll_offset = self.scroll_offset
            elif cursor_line < self.scroll_offset:
                self.scroll_offset = cursor_line
                self.scrollbar.scroll_offset = self.scroll_offset

        start_idx = int(self.scroll_offset)
        end_idx = int(self.scroll_offset + self.visible_lines)
        visible_lines = lines[start_idx:end_idx]

        y_offset = 5
        for line in visible_lines:
            if line:  # Only render non-empty lines
                if hasattr(self.font, 'get_rect'):
                    render_result = self.font.render(line, text_color)
                    if isinstance(render_result, tuple):
                        text_surface = render_result[0]
                    else:
                        text_surface = render_result
                else:
                    font_result = self.font.render(line, True, text_color)  # type: ignore[arg-type]  # noqa: FBT003
                    text_surface = font_result[0] if isinstance(font_result, tuple) else font_result
                self.image.blit(text_surface, (5, y_offset))  # ty: ignore[invalid-argument-type]
            y_offset += line_height

    def _update_cursor_blink(self, current_time: int, line_height: int) -> None:
        """Handle cursor blinking and drawing."""
        if not self.is_active:
            return

        time_since_blink = current_time - self.cursor_blink_time
        if time_since_blink >= self.cursor_blink_rate:
            self.cursor_visible = not self.cursor_visible
            self.cursor_blink_time = current_time

        if not self.cursor_visible:
            return

        lines_before_cursor, column_pos = self._get_cursor_line_and_column_in_wrapped_text(
            self.cursor_pos,
        )

        # Only draw cursor if it's in the visible range
        if not (
            self.scroll_offset <= lines_before_cursor < self.scroll_offset + self.visible_lines
        ):
            return

        # Get the current line text in wrapped text
        wrapped_lines = self._text.split('\n')
        if lines_before_cursor < len(wrapped_lines):
            current_line_text = wrapped_lines[lines_before_cursor]
            text_up_to_cursor = current_line_text[:column_pos]
            text_width = self._get_text_width(text_up_to_cursor)
        else:
            text_width = 0

        cursor_x = text_width + 5
        cursor_y = 5 + ((lines_before_cursor - self.scroll_offset) * line_height)

        pygame.draw.line(
            self.image,
            self.cursor_color,
            (cursor_x, cursor_y),
            (cursor_x, cursor_y + 20),
            2,
        )

    @override
    def update(self) -> None:
        """Update the multi-line text box."""
        self._frame_count += 1
        current_time = pygame.time.get_ticks()
        time_since_last_update = current_time - self._last_update_time
        line_height = self._get_line_height()

        self.log.debug(f'\n--- Frame {self._frame_count} ---')
        self.log.debug('Update called after %sms', time_since_last_update)
        self.log.debug(f'State: active={self.is_active}, cursor_visible={self.cursor_visible}')
        self.log.debug(f'Dirty flag: {self.dirty}')

        self._last_update_time = current_time

        # Clear background
        self.image.fill((32, 32, 32, 200))

        # Draw border
        border_color = self._get_border_color()
        pygame.draw.rect(self.image, border_color, (0, 0, self.width, self.height), 1)

        # Set text color based on hover state
        if self.is_hovered and not self.is_active:
            current_text_color = (150, 200, 255)
        else:
            current_text_color = self.base_text_color

        self._render_visible_lines(current_text_color, line_height)
        self._update_cursor_blink(current_time, line_height)

        # Update and draw scrollbar
        if self._text:
            total_lines = len(self._text.split('\n'))
            self.scrollbar.update(total_lines, self.visible_lines, self.scroll_offset)
            self.scrollbar.draw(self.image)

        # Force continuous updates
        self.dirty = 2

    @override
    def on_left_mouse_button_down_event(self, event: HashableEvent) -> None:
        """Handle left mouse button down events."""
        self.log.debug('\n--- Mouse Event ---')
        self.log.debug(f'Mouse down at {event.pos}')
        self.log.debug(f'Current rect: {self.rect}')
        self.log.debug(
            f'Current state: active={self.is_active}, cursor_visible={self.cursor_visible}'
        )

        # Convert absolute mouse position to widget-relative coordinates
        if self.rect.collidepoint(event.pos):
            relative_pos = (event.pos[0] - self.rect.x, event.pos[1] - self.rect.y)

            # Check if scrollbar handled the event
            if self.scrollbar.handle_mouse_down(relative_pos):
                # Immediately sync scroll offset from scrollbar
                self.scroll_offset = int(self.scrollbar.scroll_offset)
                self.dirty = 2
                return

        if self.rect.collidepoint(event.pos):
            self.is_active = True
            self.cursor_visible = True
            self.cursor_blink_time = pygame.time.get_ticks()
            pygame.key.start_text_input()
            # Enable key repeat for backspace
            pygame.key.set_repeat(500, 50)  # 500ms delay, 50ms interval

            # Calculate cursor position based on wrapped text, then map to original
            x_rel = event.pos[0] - self.rect.x - 5
            y_rel = event.pos[1] - self.rect.y - 5

            # Get line height
            if hasattr(self.font, 'get_linesize'):
                line_height = self.font.get_linesize()
            else:
                line_height = self.font.size if hasattr(self.font, 'size') else 24

            # Determine which line was clicked
            clicked_line = max(0, int(y_rel // line_height))

            # Get the wrapped lines
            wrapped_lines = self._text.split('\n')
            if clicked_line >= len(wrapped_lines):
                clicked_line = len(wrapped_lines) - 1

            # Find the character position within the clicked line
            clicked_line_text = wrapped_lines[clicked_line]
            text_width = 0
            char_pos_in_line = 0

            for i, char in enumerate(clicked_line_text):
                char_width = self._get_text_width(char)
                if text_width + (char_width / 2) > x_rel:
                    char_pos_in_line = i
                    break
                text_width += char_width
            else:
                char_pos_in_line = len(clicked_line_text)

            # Map the wrapped position back to original text position
            self.cursor_pos = self._map_wrapped_position_to_original(clicked_line, char_pos_in_line)

            self.log.debug(f'Activated: cursor_pos={self.cursor_pos}')
            self.log.debug('Text input started')
            self.dirty = 2
        else:
            self.is_active = False
            pygame.key.stop_text_input()
            # Disable key repeat when inactive
            pygame.key.set_repeat()  # Calling with no args disables repeat
            self.log.debug('Deactivated, text input stopped')

    @override
    def on_key_down_event(self, event: HashableEvent) -> None:
        """Handle key down events."""
        if not self.is_active:
            return

        # Handle Escape key to deactivate
        if event.key == pygame.K_ESCAPE:
            self.is_active = False
            pygame.key.stop_text_input()
            pygame.key.set_repeat()  # Disable key repeat
            self.log.debug('Deactivated by Escape key')
            self.dirty = 2
            return

        mods = pygame.key.get_mods()
        is_ctrl = bool(mods & pygame.KMOD_CTRL) or bool(mods & pygame.KMOD_META)

        # Handle Ctrl+D (or Cmd+D) to clear contents
        if event.key == pygame.K_d and is_ctrl:
            self.text = ''
            self._text = ''
            self.cursor_pos = 0
            self.selection_start = None
            self.selection_end = None
            self.dirty = 2
            self.log.debug('Cleared text contents with Ctrl+D')
            return

        is_shift = bool(mods & pygame.KMOD_SHIFT)

        # Handle Ctrl+Enter for submission
        if event.key == pygame.K_RETURN and is_ctrl:
            self._handle_ctrl_enter_submit()
            return

        # Handle selection with shift+arrow keys
        if event.key in {pygame.K_LEFT, pygame.K_RIGHT} and is_shift:
            self._handle_shift_arrow(event)
            return

        # Clear selection on non-shift arrow keys
        if event.key in {pygame.K_LEFT, pygame.K_RIGHT}:
            self.selection_start = None
            self.selection_end = None

        # Handle clipboard operations or delete with selection
        clipboard_handled = self._handle_clipboard_operation(event, is_ctrl=is_ctrl)
        if clipboard_handled or self._handle_delete_selection(event):
            return

        # Handle regular key events
        self._handle_regular_key(event)

        self.cursor_visible = True
        self.cursor_blink_time = pygame.time.get_ticks()
        self.dirty = 1

    def _handle_ctrl_enter_submit(self) -> None:
        """Handle Ctrl+Enter to submit text."""
        if self.parent and hasattr(self.parent, 'on_text_submit_event'):
            self.parent.on_text_submit_event(self._text)
            self.is_active = False
            pygame.key.stop_text_input()
            pygame.key.set_repeat()  # Disable key repeat
            self.log.debug('Deactivated after submission')

    def _handle_shift_arrow(self, event: HashableEvent) -> None:
        """Handle shift+arrow key for text selection."""
        if self.selection_start is None:
            self.selection_start = self.cursor_pos

        if event.key == pygame.K_LEFT:
            self.cursor_pos = max(0, self.cursor_pos - 1)
        else:
            self.cursor_pos = min(len(self._original_text), self.cursor_pos + 1)
        self.selection_end = self.cursor_pos

    def _handle_clipboard_operation(self, event: HashableEvent, *, is_ctrl: bool) -> bool:
        """Handle copy, paste, cut, and select-all operations.

        Returns:
            True if a clipboard operation was handled (caller should return).

        """
        if not is_ctrl:
            return False

        if event.key == pygame.K_c and self._text:
            self._handle_copy()
            return True
        if event.key == pygame.K_v:
            self._handle_paste()
            return True
        if event.key == pygame.K_x and self._original_text:
            self._handle_cut()
            return True
        if event.key == pygame.K_a:
            self.selection_start = 0
            self.selection_end = len(self._original_text)
            self.cursor_pos = len(self._original_text)
            return True
        return False

    def _handle_copy(self) -> None:
        """Handle copy operation."""
        try:
            if pyperclip is None:
                self.log.warning('pyperclip not available, cannot copy text')
                return

            if self.selection_start is not None and self.selection_end is not None:
                start = min(self.selection_start, self.selection_end)
                end = max(self.selection_start, self.selection_end)
                pyperclip.copy(self._text[start:end])
            else:
                pyperclip.copy(self._text)
        except ImportError, AttributeError:
            self.log.error('Error copying text')  # noqa: TRY400

    def _handle_paste(self) -> None:
        """Handle paste operation."""
        try:
            clipboard_text = None
            if pyperclip:
                clipboard_text = pyperclip.paste()
            if clipboard_text:
                before_cursor = self._original_text[: self.cursor_pos]
                after_cursor = self._original_text[self.cursor_pos :]
                self.text = before_cursor + clipboard_text + after_cursor
                self.cursor_pos += len(clipboard_text)
        except ImportError, AttributeError:
            self.log.error('Error pasting text')  # noqa: TRY400

    def _handle_cut(self) -> None:
        """Handle cut operation."""
        try:
            if pyperclip and self.selection_start is not None and self.selection_end is not None:
                start = min(self.selection_start, self.selection_end)
                end = max(self.selection_start, self.selection_end)
                pyperclip.copy(self._original_text[start:end])
                self.text = self._original_text[:start] + self._original_text[end:]
                self.cursor_pos = start
                self.selection_start = None
                self.selection_end = None
            else:
                assert pyperclip is not None
                pyperclip.copy(self._original_text)
                self.text = ''
                self.cursor_pos = 0
        except ImportError, AttributeError:
            self.log.error('Error cutting text')  # noqa: TRY400

    def _handle_delete_selection(self, event: HashableEvent) -> bool:
        """Handle delete key with active selection.

        Returns:
            True if the delete was handled.

        """
        if event.key != pygame.K_DELETE:
            return False
        if self.selection_start is None or self.selection_end is None:
            return False
        start = min(self.selection_start, self.selection_end)
        end = max(self.selection_start, self.selection_end)
        self.text = self._original_text[:start] + self._original_text[end:]
        self.cursor_pos = start
        self.selection_start = None
        self.selection_end = None
        return True

    def _handle_regular_key(self, event: HashableEvent) -> None:
        """Handle regular key events (navigation, text input, backspace, delete)."""
        # Note: self.text setter moves cursor to end, so we save intended position first
        if event.key == pygame.K_RETURN:
            self._handle_return_key()
        elif event.key == pygame.K_BACKSPACE:
            self._handle_backspace_key()
        elif event.key == pygame.K_DELETE:
            self._handle_delete_key()
        elif event.key == pygame.K_LEFT:
            self.cursor_pos = max(0, self.cursor_pos - 1)
        elif event.key == pygame.K_RIGHT:
            self.cursor_pos = min(len(self._original_text), self.cursor_pos + 1)
        elif event.key == pygame.K_UP:
            self._move_cursor_up()
        elif event.key == pygame.K_DOWN:
            self._move_cursor_down()
        elif event.unicode and event.unicode >= ' ':
            self._handle_text_insert(event.unicode)

    def _handle_return_key(self) -> None:
        """Insert a newline at the current cursor position."""
        new_cursor_pos = self.cursor_pos + 1
        before_cursor = self._original_text[: self.cursor_pos]
        after_cursor = self._original_text[self.cursor_pos :]
        self.text = before_cursor + '\n' + after_cursor
        self.cursor_pos = new_cursor_pos

    def _handle_backspace_key(self) -> None:
        """Delete the character before the cursor."""
        if self.cursor_pos > 0:
            new_cursor_pos = self.cursor_pos - 1
            self.text = (
                self._original_text[: self.cursor_pos - 1] + self._original_text[self.cursor_pos :]
            )
            self.cursor_pos = new_cursor_pos

    def _handle_delete_key(self) -> None:
        """Delete the character at the cursor position."""
        if self.cursor_pos < len(self._original_text):
            new_cursor_pos = self.cursor_pos
            self.text = (
                self._original_text[: self.cursor_pos] + self._original_text[self.cursor_pos + 1 :]
            )
            self.cursor_pos = new_cursor_pos

    def _handle_text_insert(self, character: str) -> None:
        """Insert a character at the current cursor position.

        Args:
            character: The character to insert.

        """
        new_cursor_pos = self.cursor_pos + 1
        before_cursor = self._original_text[: self.cursor_pos]
        after_cursor = self._original_text[self.cursor_pos :]
        self.text = before_cursor + character + after_cursor
        self.cursor_pos = new_cursor_pos

    def on_mouse_up_event(self, event: HashableEvent) -> None:
        """Handle mouse up events to activate text input."""
        if self.rect.collidepoint(event.pos):
            self.activate()
        else:
            self.deactivate()

    def activate(self) -> None:
        """Activate the text box for input."""
        self.is_active = True
        pygame.key.start_text_input()
        pygame.key.set_repeat(200)  # Enable key repeat
        self.log.debug('MultiLineTextBox activated')

    def deactivate(self) -> None:
        """Deactivate the text box."""
        self.is_active = False
        pygame.key.stop_text_input()
        pygame.key.set_repeat()  # Disable key repeat
        self.log.debug('MultiLineTextBox deactivated')

    @override
    def on_mouse_motion_event(self, event: HashableEvent) -> None:
        """Handle mouse motion events for hover effects and scrollbar."""
        # Convert absolute mouse position to widget-relative coordinates
        relative_pos = (event.pos[0] - self.rect.x, event.pos[1] - self.rect.y)

        # Check if scrollbar handled the event
        if self.scrollbar.handle_mouse_motion(relative_pos):
            # Sync scroll offset from scrollbar
            self.scroll_offset = int(self.scrollbar.scroll_offset)
            self.dirty = 2
            return

        if self.rect.collidepoint(event.pos):
            # Mouse is over the textbox - set hover state
            if not self.is_hovered:
                self.is_hovered = True
                self.dirty = 1  # Mark for redraw to show hover effects
        # Mouse is outside the textbox - clear hover state
        elif self.is_hovered:
            self.is_hovered = False
            self.dirty = 1  # Mark for redraw to remove hover effects

    @override
    def on_left_mouse_button_up_event(self, event: HashableEvent) -> None:
        """Handle left mouse button up events."""
        # Convert absolute mouse position to widget-relative coordinates
        relative_pos = (event.pos[0] - self.rect.x, event.pos[1] - self.rect.y)

        # Check if scrollbar handled the event
        if self.scrollbar.handle_mouse_up(relative_pos):
            # Sync scroll offset from scrollbar
            self.scroll_offset = int(self.scrollbar.scroll_offset)
            self.dirty = 2
            return

    @override
    def on_mouse_wheel_event(
        self,
        event: HashableEvent,
        trigger: HashableEvent | None = None,
    ) -> None:
        """Handle mouse wheel events for scrolling."""
        if not self.rect.collidepoint(pygame.mouse.get_pos()):
            return

        # Get total lines for boundary checking
        total_lines = len(self._text.split('\n')) if self._text else 0
        max_scroll = max(0, total_lines - self.visible_lines)

        # Scroll by 3 lines per wheel notch
        scroll_amount = 3

        if hasattr(event, 'y'):
            # pygame 2.0+ style
            self.scroll_offset -= event.y * scroll_amount
        elif hasattr(event, 'button'):
            # pygame 1.9 style (button 4 = up, button 5 = down)
            if event.button == PYGAME_MOUSE_SCROLL_UP_BUTTON:  # Scroll up
                self.scroll_offset -= scroll_amount
            elif event.button == PYGAME_MOUSE_SCROLL_DOWN_BUTTON:  # Scroll down
                self.scroll_offset += scroll_amount

        # Clamp scroll offset
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

        # Sync scrollbar
        self.scrollbar.scroll_offset = self.scroll_offset

        self.dirty = 2
