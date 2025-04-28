#!/usr/bin/env python3
"""UI components demo using glitchygames."""

import pygame

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from glitchygames.ui import Button, Label, TextInput, Checkbox, Slider, ProgressBar
from glitchygames.color import WHITE, BLACK, GRAY, LIGHT_GRAY

class UIDemo(Scene):
    """UI demo scene."""
    
    NAME = "UI Demo"
    VERSION = "0.1.0"
    
    def __init__(self, options=None, groups=None):
        """Initialize the UI demo scene."""
        super().__init__(options=options, groups=groups)
        
        self.background_color = LIGHT_GRAY
        self.font = pygame.font.Font(None, 24)
        self.ui_elements = []
        
        # Create UI elements
        self._create_ui_elements()
        
    def _create_ui_elements(self):
        """Create UI elements."""
        # Title label
        self.title_label = Label(
            pygame.Rect(0, 20, 800, 40),
            "GlitchyGames UI Components Demo",
            fg_color=BLACK
        )
        self.title_label.font = pygame.font.Font(None, 36)
        self.title_label.align = 'center'
        self.ui_elements.append(self.title_label)
        
        # Button
        self.button = Button(
            pygame.Rect(50, 100, 200, 40),
            "Click Me!",
            callback=self._button_clicked,
            fg_color=BLACK
        )
        self.ui_elements.append(self.button)
        
        # Button label
        self.button_label = Label(
            pygame.Rect(50, 150, 200, 20),
            "Button clicks: 0",
            fg_color=BLACK
        )
        self.ui_elements.append(self.button_label)
        
        # Text input
        self.text_input = TextInput(
            pygame.Rect(50, 200, 200, 40),
            placeholder="Enter text...",
            fg_color=BLACK
        )
        self.ui_elements.append(self.text_input)
        
        # Text input label
        self.text_input_label = Label(
            pygame.Rect(50, 250, 200, 20),
            "Text Input",
            fg_color=BLACK
        )
        self.ui_elements.append(self.text_input_label)
        
        # Checkbox
        self.checkbox = Checkbox(
            pygame.Rect(50, 300, 200, 40),
            "Enable Feature",
            callback=self._checkbox_changed,
            fg_color=BLACK
        )
        self.ui_elements.append(self.checkbox)
        
        # Checkbox label
        self.checkbox_label = Label(
            pygame.Rect(50, 350, 200, 20),
            "Feature: Disabled",
            fg_color=BLACK
        )
        self.ui_elements.append(self.checkbox_label)
        
        # Slider
        self.slider = Slider(
            pygame.Rect(350, 100, 200, 20),
            min_value=0,
            max_value=100,
            value=50,
            callback=self._slider_changed
        )
        self.ui_elements.append(self.slider)
        
        # Slider label
        self.slider_label = Label(
            pygame.Rect(350, 130, 200, 20),
            "Value: 50",
            fg_color=BLACK
        )
        self.ui_elements.append(self.slider_label)
        
        # Progress bar
        self.progress_bar = ProgressBar(
            pygame.Rect(350, 200, 200, 30),
            value=75,
            max_value=100
        )
        self.ui_elements.append(self.progress_bar)
        
        # Progress bar label
        self.progress_label = Label(
            pygame.Rect(350, 240, 200, 20),
            "Progress: 75%",
            fg_color=BLACK
        )
        self.ui_elements.append(self.progress_label)
        
        # Progress bar buttons
        self.decrease_button = Button(
            pygame.Rect(350, 270, 95, 30),
            "-10%",
            callback=self._decrease_progress,
            fg_color=BLACK
        )
        self.ui_elements.append(self.decrease_button)
        
        self.increase_button = Button(
            pygame.Rect(455, 270, 95, 30),
            "+10%",
            callback=self._increase_progress,
            fg_color=BLACK
        )
        self.ui_elements.append(self.increase_button)
        
        # Instructions
        self.instructions = Label(
            pygame.Rect(0, 500, 800, 20),
            "Press ESC or Q to quit",
            fg_color=BLACK
        )
        self.instructions.align = 'center'
        self.ui_elements.append(self.instructions)
        
        # Button click counter
        self.button_clicks = 0
        
    def _button_clicked(self):
        """Handle button click."""
        self.button_clicks += 1
        self.button_label.text = f"Button clicks: {self.button_clicks}"
        
    def _checkbox_changed(self, checked):
        """Handle checkbox change."""
        self.checkbox_label.text = f"Feature: {'Enabled' if checked else 'Disabled'}"
        
    def _slider_changed(self, value):
        """Handle slider change."""
        self.slider_label.text = f"Value: {int(value)}"
        
    def _decrease_progress(self):
        """Decrease progress bar value."""
        new_value = max(0, self.progress_bar.value - 10)
        self.progress_bar.set_value(new_value)
        self.progress_label.text = f"Progress: {int(new_value)}%"
        
    def _increase_progress(self):
        """Increase progress bar value."""
        new_value = min(100, self.progress_bar.value + 10)
        self.progress_bar.set_value(new_value)
        self.progress_label.text = f"Progress: {int(new_value)}%"
        
    def update(self):
        """Update the scene state."""
        # Get pygame events
        events = pygame.event.get()
        
        # Update UI elements
        for element in self.ui_elements:
            element.update(events)
            
        # Put events back in the queue for the engine to process
        for event in events:
            pygame.event.post(event)
        
    def draw(self, surface):
        """Draw the scene."""
        # Clear the screen
        surface.fill(self.background_color)
        
        # Draw UI elements
        for element in self.ui_elements:
            element.draw(surface)

def main():
    """Main entry point."""
    GameEngine(
        game=UIDemo,
        title="UI Components Demo"
    ).start()

if __name__ == "__main__":
    main()