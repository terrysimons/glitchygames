"""UI components for glitchygames."""

import logging
from typing import Callable, Dict, List, Optional, Tuple, Union

import pygame

from glitchygames.fonts import get_font, render_text

LOG = logging.getLogger('game')

class UIElement:
    """Base class for UI elements."""
    
    def __init__(self, rect: pygame.Rect, visible: bool = True):
        """Initialize the UI element.
        
        Args:
            rect: Rectangle defining the element's position and size
            visible: Whether the element is visible
        """
        self.rect = rect
        self.visible = visible
        self.enabled = True
        self.focused = False
        self.hovered = False
        
    def update(self, events: List[pygame.event.Event]):
        """Update the element's state based on events.
        
        Args:
            events: List of pygame events
        """
        if not self.visible or not self.enabled:
            return
            
        # Check for mouse hover
        mouse_pos = pygame.mouse.get_pos()
        self.hovered = self.rect.collidepoint(mouse_pos)
        
    def draw(self, surface: pygame.Surface):
        """Draw the element to the surface.
        
        Args:
            surface: Surface to draw on
        """
        if not self.visible:
            return
            
class Button(UIElement):
    """Button UI element."""
    
    def __init__(self, 
                 rect: pygame.Rect, 
                 text: str,
                 callback: Optional[Callable] = None,
                 bg_color: Tuple[int, int, int] = (100, 100, 100),
                 hover_color: Tuple[int, int, int] = (150, 150, 150),
                 text_color: Tuple[int, int, int] = (255, 255, 255),
                 font: Optional[pygame.font.Font] = None,
                 visible: bool = True):
        """Initialize the button.
        
        Args:
            rect: Rectangle defining the button's position and size
            text: Button text
            callback: Function to call when the button is clicked
            bg_color: Background color
            hover_color: Background color when hovered
            text_color: Text color
            font: Font to use for text
            visible: Whether the button is visible
        """
        super().__init__(rect, visible)
        
        self.text = text
        self.callback = callback
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.font = font or get_font(size=16)
        self.pressed = False
        
    def update(self, events: List[pygame.event.Event]):
        """Update the button's state based on events.
        
        Args:
            events: List of pygame events
        """
        super().update(events)
        
        if not self.visible or not self.enabled:
            return
            
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.hovered:
                    self.pressed = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.pressed and self.hovered and self.callback:
                    self.callback()
                self.pressed = False
                
    def draw(self, surface: pygame.Surface):
        """Draw the button to the surface.
        
        Args:
            surface: Surface to draw on
        """
        if not self.visible:
            return
            
        # Draw the button background
        color = self.hover_color if self.hovered else self.bg_color
        pygame.draw.rect(surface, color, self.rect)
        
        # Draw a border
        border_color = (50, 50, 50)
        pygame.draw.rect(surface, border_color, self.rect, 2)
        
        # Draw the text
        text_surface = render_text(self.text, self.font, self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)
        
class Label(UIElement):
    """Label UI element."""
    
    def __init__(self, 
                 rect: pygame.Rect, 
                 text: str,
                 text_color: Tuple[int, int, int] = (255, 255, 255),
                 bg_color: Optional[Tuple[int, int, int]] = None,
                 font: Optional[pygame.font.Font] = None,
                 align: str = 'left',
                 visible: bool = True):
        """Initialize the label.
        
        Args:
            rect: Rectangle defining the label's position and size
            text: Label text
            text_color: Text color
            bg_color: Background color (or None for transparent)
            font: Font to use for text
            align: Text alignment ('left', 'center', or 'right')
            visible: Whether the label is visible
        """
        super().__init__(rect, visible)
        
        self.text = text
        self.text_color = text_color
        self.bg_color = bg_color
        self.font = font or get_font(size=16)
        self.align = align
        
    def draw(self, surface: pygame.Surface):
        """Draw the label to the surface.
        
        Args:
            surface: Surface to draw on
        """
        if not self.visible:
            return
            
        # Draw the background if specified
        if self.bg_color is not None:
            pygame.draw.rect(surface, self.bg_color, self.rect)
            
        # Draw the text
        text_surface = render_text(self.text, self.font, self.text_color)
        
        # Position the text based on alignment
        if self.align == 'left':
            text_rect = text_surface.get_rect(midleft=(self.rect.left + 5, self.rect.centery))
        elif self.align == 'right':
            text_rect = text_surface.get_rect(midright=(self.rect.right - 5, self.rect.centery))
        else:  # center
            text_rect = text_surface.get_rect(center=self.rect.center)
            
        surface.blit(text_surface, text_rect)
        
class Panel(UIElement):
    """Panel UI element that can contain other elements."""
    
    def __init__(self, 
                 rect: pygame.Rect, 
                 bg_color: Optional[Tuple[int, int, int]] = None,
                 border_color: Optional[Tuple[int, int, int]] = None,
                 border_width: int = 0,
                 visible: bool = True):
        """Initialize the panel.
        
        Args:
            rect: Rectangle defining the panel's position and size
            bg_color: Background color (or None for transparent)
            border_color: Border color (or None for no border)
            border_width: Border width
            visible: Whether the panel is visible
        """
        super().__init__(rect, visible)
        
        self.bg_color = bg_color
        self.border_color = border_color
        self.border_width = border_width
        self.elements = []
        
    def add_element(self, element: UIElement):
        """Add a UI element to the panel.
        
        Args:
            element: UI element to add
        """
        self.elements.append(element)
        
        # Adjust the element's rect to be relative to the panel
        element.rect.x += self.rect.x
        element.rect.y += self.rect.y
        
    def update(self, events: List[pygame.event.Event]):
        """Update the panel and its elements.
        
        Args:
            events: List of pygame events
        """
        super().update(events)
        
        if not self.visible or not self.enabled:
            return
            
        # Update all elements
        for element in self.elements:
            element.update(events)
            
    def draw(self, surface: pygame.Surface):
        """Draw the panel and its elements.
        
        Args:
            surface: Surface to draw on
        """
        if not self.visible:
            return
            
        # Draw the panel background
        if self.bg_color is not None:
            pygame.draw.rect(surface, self.bg_color, self.rect)
            
        # Draw the border
        if self.border_color is not None and self.border_width > 0:
            pygame.draw.rect(surface, self.border_color, self.rect, self.border_width)
            
        # Draw all elements
        for element in self.elements:
            element.draw(surface)