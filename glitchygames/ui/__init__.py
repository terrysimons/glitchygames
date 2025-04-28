"""UI components for glitchygames."""

import logging
from typing import Callable, Dict, List, Optional, Tuple, Union

import pygame

from glitchygames.color import BLACK, WHITE, GRAY, LIGHT_GRAY, DARK_GRAY

LOG = logging.getLogger('game')

class UIElement:
    """Base class for UI elements."""
    
    def __init__(self, rect: pygame.Rect, bg_color=None, fg_color=WHITE, visible=True, enabled=True):
        """Initialize the UI element.
        
        Args:
            rect: Rectangle defining the element's position and size
            bg_color: Background color
            fg_color: Foreground color
            visible: Whether the element is visible
            enabled: Whether the element is enabled
        """
        self.rect = rect
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.visible = visible
        self.enabled = enabled
        self.hovered = False
        self.focused = False
        
    def update(self, events):
        """Update the element's state.
        
        Args:
            events: List of pygame events
        """
        if not self.visible or not self.enabled:
            return
            
        mouse_pos = pygame.mouse.get_pos()
        self.hovered = self.rect.collidepoint(mouse_pos)
        
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.hovered:
                    self.focused = True
                    self.on_click(event)
                else:
                    self.focused = False
                    
    def draw(self, surface: pygame.Surface):
        """Draw the element on a surface.
        
        Args:
            surface: Surface to draw on
        """
        if not self.visible:
            return
            
        if self.bg_color is not None:
            pygame.draw.rect(surface, self.bg_color, self.rect)
            
    def on_click(self, event):
        """Handle click events.
        
        Args:
            event: Pygame mouse event
        """
        pass

class Button(UIElement):
    """Button UI element."""
    
    def __init__(self, rect: pygame.Rect, text: str, callback: Callable = None, **kwargs):
        """Initialize the button.
        
        Args:
            rect: Rectangle defining the button's position and size
            text: Button text
            callback: Function to call when the button is clicked
            **kwargs: Additional arguments to pass to UIElement constructor
        """
        super().__init__(rect, **kwargs)
        
        self.text = text
        self.callback = callback
        self.font = pygame.font.Font(None, 24)
        
        # Default colors
        if self.bg_color is None:
            self.bg_color = LIGHT_GRAY
            
        self.hover_color = tuple(min(c + 20, 255) for c in self.bg_color)
        self.press_color = tuple(max(c - 20, 0) for c in self.bg_color)
        self.disabled_color = GRAY
        
        # State
        self.pressed = False
        
    def update(self, events):
        """Update the button's state.
        
        Args:
            events: List of pygame events
        """
        if not self.visible:
            return
            
        old_hovered = self.hovered
        super().update(events)
        
        # Handle mouse events
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.hovered and self.enabled:
                    self.pressed = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.pressed and self.hovered and self.enabled:
                    if self.callback:
                        self.callback()
                self.pressed = False
                
    def draw(self, surface: pygame.Surface):
        """Draw the button on a surface.
        
        Args:
            surface: Surface to draw on
        """
        if not self.visible:
            return
            
        # Determine button color based on state
        if not self.enabled:
            color = self.disabled_color
        elif self.pressed and self.hovered:
            color = self.press_color
        elif self.hovered:
            color = self.hover_color
        else:
            color = self.bg_color
            
        # Draw button background
        pygame.draw.rect(surface, color, self.rect)
        pygame.draw.rect(surface, DARK_GRAY, self.rect, 1)
        
        # Draw button text
        if self.text:
            text_surface = self.font.render(self.text, True, self.fg_color)
            text_rect = text_surface.get_rect(center=self.rect.center)
            surface.blit(text_surface, text_rect)

class Label(UIElement):
    """Label UI element."""
    
    def __init__(self, rect: pygame.Rect, text: str, **kwargs):
        """Initialize the label.
        
        Args:
            rect: Rectangle defining the label's position and size
            text: Label text
            **kwargs: Additional arguments to pass to UIElement constructor
        """
        super().__init__(rect, **kwargs)
        
        self.text = text
        self.font = pygame.font.Font(None, 24)
        self.align = 'left'  # 'left', 'center', 'right'
        
    def draw(self, surface: pygame.Surface):
        """Draw the label on a surface.
        
        Args:
            surface: Surface to draw on
        """
        if not self.visible:
            return
            
        super().draw(surface)
        
        if self.text:
            text_surface = self.font.render(self.text, True, self.fg_color)
            text_rect = text_surface.get_rect()
            
            if self.align == 'left':
                text_rect.midleft = self.rect.midleft
            elif self.align == 'center':
                text_rect.center = self.rect.center
            else:  # right
                text_rect.midright = self.rect.midright
                
            surface.blit(text_surface, text_rect)

class TextInput(UIElement):
    """Text input UI element."""
    
    def __init__(self, rect: pygame.Rect, placeholder: str = "", max_length: int = 100, **kwargs):
        """Initialize the text input.
        
        Args:
            rect: Rectangle defining the input's position and size
            placeholder: Placeholder text
            max_length: Maximum text length
            **kwargs: Additional arguments to pass to UIElement constructor
        """
        if 'bg_color' not in kwargs:
            kwargs['bg_color'] = WHITE
        super().__init__(rect, **kwargs)
        
        self.text = ""
        self.placeholder = placeholder
        self.max_length = max_length
        self.font = pygame.font.Font(None, 24)
        self.cursor_visible = True
        self.cursor_timer = 0
        self.cursor_blink_rate = 500  # ms
        
    def update(self, events):
        """Update the text input's state.
        
        Args:
            events: List of pygame events
        """
        super().update(events)
        
        if not self.visible or not self.enabled:
            return
            
        # Handle cursor blinking
        self.cursor_timer += pygame.time.get_ticks()
        if self.cursor_timer >= self.cursor_blink_rate:
            self.cursor_timer = 0
            self.cursor_visible = not self.cursor_visible
            
        # Handle keyboard events
        for event in events:
            if event.type == pygame.KEYDOWN and self.focused:
                if event.key == pygame.K_BACKSPACE:
                    self.text = self.text[:-1]
                elif event.key == pygame.K_RETURN:
                    self.focused = False
                elif event.unicode and len(self.text) < self.max_length:
                    self.text += event.unicode
                    
    def draw(self, surface: pygame.Surface):
        """Draw the text input on a surface.
        
        Args:
            surface: Surface to draw on
        """
        if not self.visible:
            return
            
        super().draw(surface)
        
        # Draw border
        border_color = DARK_GRAY
        if self.focused:
            border_color = (0, 120, 215)  # Highlight color
        pygame.draw.rect(surface, border_color, self.rect, 1)
        
        # Draw text or placeholder
        padding = 5
        if self.text:
            text_surface = self.font.render(self.text, True, self.fg_color)
        else:
            text_surface = self.font.render(self.placeholder, True, GRAY)
            
        text_rect = text_surface.get_rect(midleft=(self.rect.left + padding, self.rect.centery))
        
        # Clip text if it's too long
        if text_rect.width > self.rect.width - 2 * padding:
            clip_rect = pygame.Rect(0, 0, self.rect.width - 2 * padding, text_rect.height)
            text_surface = text_surface.subsurface(clip_rect)
            text_rect = text_surface.get_rect(midleft=(self.rect.left + padding, self.rect.centery))
            
        surface.blit(text_surface, text_rect)
        
        # Draw cursor
        if self.focused and self.cursor_visible and self.text:
            cursor_x = text_rect.right
            if cursor_x < self.rect.right - padding:
                pygame.draw.line(
                    surface,
                    self.fg_color,
                    (cursor_x, self.rect.top + padding),
                    (cursor_x, self.rect.bottom - padding)
                )

class Checkbox(UIElement):
    """Checkbox UI element."""
    
    def __init__(self, rect: pygame.Rect, text: str = "", checked: bool = False, callback: Callable = None, **kwargs):
        """Initialize the checkbox.
        
        Args:
            rect: Rectangle defining the checkbox's position and size
            text: Checkbox text
            checked: Whether the checkbox is checked
            callback: Function to call when the checkbox is toggled
            **kwargs: Additional arguments to pass to UIElement constructor
        """
        super().__init__(rect, **kwargs)
        
        self.text = text
        self.checked = checked
        self.callback = callback
        self.font = pygame.font.Font(None, 24)
        
        # Calculate checkbox size
        self.box_size = min(rect.height - 4, 20)
        self.box_rect = pygame.Rect(
            rect.left + 2,
            rect.centery - self.box_size // 2,
            self.box_size,
            self.box_size
        )
        
    def update(self, events):
        """Update the checkbox's state.
        
        Args:
            events: List of pygame events
        """
        if not self.visible or not self.enabled:
            return
            
        old_hovered = self.hovered
        super().update(events)
        
    def on_click(self, event):
        """Handle click events.
        
        Args:
            event: Pygame mouse event
        """
        if self.enabled:
            self.checked = not self.checked
            if self.callback:
                self.callback(self.checked)
                
    def draw(self, surface: pygame.Surface):
        """Draw the checkbox on a surface.
        
        Args:
            surface: Surface to draw on
        """
        if not self.visible:
            return
            
        # Draw checkbox
        pygame.draw.rect(surface, WHITE, self.box_rect)
        pygame.draw.rect(surface, DARK_GRAY, self.box_rect, 1)
        
        # Draw check mark
        if self.checked:
            inner_rect = self.box_rect.inflate(-6, -6)
            pygame.draw.rect(surface, self.fg_color, inner_rect)
            
        # Draw text
        if self.text:
            text_surface = self.font.render(self.text, True, self.fg_color)
            text_rect = text_surface.get_rect(
                midleft=(self.box_rect.right + 5, self.rect.centery)
            )
            surface.blit(text_surface, text_rect)

class Slider(UIElement):
    """Slider UI element."""
    
    def __init__(self, rect: pygame.Rect, min_value: float = 0, max_value: float = 100, value: float = 50, callback: Callable = None, **kwargs):
        """Initialize the slider.
        
        Args:
            rect: Rectangle defining the slider's position and size
            min_value: Minimum value
            max_value: Maximum value
            value: Initial value
            callback: Function to call when the slider value changes
            **kwargs: Additional arguments to pass to UIElement constructor
        """
        super().__init__(rect, **kwargs)
        
        self.min_value = min_value
        self.max_value = max_value
        self.value = max(min_value, min(max_value, value))
        self.callback = callback
        self.dragging = False
        
        # Calculate handle size and position
        self.handle_width = 10
        self.handle_height = self.rect.height + 4
        self.update_handle_rect()
        
    def update_handle_rect(self):
        """Update the handle rectangle based on the current value."""
        value_range = self.max_value - self.min_value
        if value_range == 0:
            position = 0
        else:
            position = (self.value - self.min_value) / value_range
            
        handle_x = self.rect.left + int(position * self.rect.width) - self.handle_width // 2
        self.handle_rect = pygame.Rect(
            handle_x,
            self.rect.centery - self.handle_height // 2,
            self.handle_width,
            self.handle_height
        )
        
    def update(self, events):
        """Update the slider's state.
        
        Args:
            events: List of pygame events
        """
        if not self.visible or not self.enabled:
            return
            
        mouse_pos = pygame.mouse.get_pos()
        self.hovered = self.handle_rect.collidepoint(mouse_pos)
        
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.hovered:
                    self.dragging = True
                    self.focused = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.dragging = False
                
        if self.dragging:
            # Update value based on mouse position
            position = (mouse_pos[0] - self.rect.left) / self.rect.width
            position = max(0, min(1, position))
            self.value = self.min_value + position * (self.max_value - self.min_value)
            self.update_handle_rect()
            
            if self.callback:
                self.callback(self.value)
                
    def draw(self, surface: pygame.Surface):
        """Draw the slider on a surface.
        
        Args:
            surface: Surface to draw on
        """
        if not self.visible:
            return
            
        # Draw track
        pygame.draw.rect(surface, GRAY, self.rect)
        
        # Draw handle
        handle_color = LIGHT_GRAY
        if self.dragging:
            handle_color = DARK_GRAY
        elif self.hovered:
            handle_color = tuple(min(c + 20, 255) for c in LIGHT_GRAY)
            
        pygame.draw.rect(surface, handle_color, self.handle_rect)
        pygame.draw.rect(surface, DARK_GRAY, self.handle_rect, 1)

class ProgressBar(UIElement):
    """Progress bar UI element."""
    
    def __init__(self, rect: pygame.Rect, value: float = 0, max_value: float = 100, **kwargs):
        """Initialize the progress bar.
        
        Args:
            rect: Rectangle defining the progress bar's position and size
            value: Initial value
            max_value: Maximum value
            **kwargs: Additional arguments to pass to UIElement constructor
        """
        if 'bg_color' not in kwargs:
            kwargs['bg_color'] = GRAY
        if 'fg_color' not in kwargs:
            kwargs['fg_color'] = (0, 120, 215)  # Blue
        super().__init__(rect, **kwargs)
        
        self.value = max(0, min(max_value, value))
        self.max_value = max_value
        
    def set_value(self, value: float):
        """Set the progress bar value.
        
        Args:
            value: New value
        """
        self.value = max(0, min(self.max_value, value))
        
    def draw(self, surface: pygame.Surface):
        """Draw the progress bar on a surface.
        
        Args:
            surface: Surface to draw on
        """
        if not self.visible:
            return
            
        # Draw background
        pygame.draw.rect(surface, self.bg_color, self.rect)
        pygame.draw.rect(surface, DARK_GRAY, self.rect, 1)
        
        # Draw progress
        if self.max_value > 0:
            progress_width = int((self.value / self.max_value) * self.rect.width)
            if progress_width > 0:
                progress_rect = pygame.Rect(
                    self.rect.left,
                    self.rect.top,
                    progress_width,
                    self.rect.height
                )
                pygame.draw.rect(surface, self.fg_color, progress_rect)