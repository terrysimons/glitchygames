# GlitchyGames

GlitchyGames is a wrapper around Pygame that aims to support 20-25FPS minimum games on Raspberry Pi and other low-powered Linux systems.

## Features

- Scene-based architecture for easy game state management
- Enhanced event handling system
- Sprite management with animation support
- UI components (buttons, labels, sliders, etc.)
- Color utilities
- Font management
- Movement utilities
- Pixel manipulation

## Installation

```bash
pip install -e .
```

## Usage

Here's a simple example of how to use GlitchyGames:

```python
#!/usr/bin/env python3
"""Simple game example using glitchygames."""

import pygame

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from glitchygames.color import WHITE, BLACK

class MyGame(Scene):
    """Simple game scene."""
    
    NAME = "My Game"
    VERSION = "0.1.0"
    
    def __init__(self, options=None, groups=None):
        """Initialize the game scene."""
        super().__init__(options=options, groups=groups)
        
        self.background_color = BLACK
        self.font = pygame.font.Font(None, 36)
        
    def update(self):
        """Update the game state."""
        pass
        
    def draw(self, surface):
        """Draw the game scene."""
        # Clear the screen
        surface.fill(self.background_color)
        
        # Draw text
        text = "Hello, GlitchyGames!"
        text_surface = self.font.render(text, True, WHITE)
        text_rect = text_surface.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2))
        surface.blit(text_surface, text_rect)
        
    def on_key_down(self, event):
        """Handle key down events."""
        super().on_key_down(event)
        
        if event.key == pygame.K_SPACE:
            print("Space pressed!")

def main():
    """Main entry point."""
    GameEngine(
        game=MyGame,
        title="My Game"
    ).start()

if __name__ == "__main__":
    main()
```

## Examples

Check out the `examples` directory for more examples of how to use GlitchyGames.

## Documentation

For more detailed documentation, see the `docs` directory.

## License

MIT