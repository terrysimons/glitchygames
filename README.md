# GlitchyGames

A Pygame wrapper designed to support 20-25FPS minimum games on Raspberry Pi and other low-powered Linux systems.

## Features

- Scene-based game architecture
- Enhanced event handling
- Sprite management
- UI components
- Color utilities
- Font management
- Movement systems
- Pixel manipulation utilities

## Installation

```bash
pip install glitchygames
```

Or install from source:

```bash
git clone https://github.com/terrysimons/glitchygames.git
cd glitchygames
pip install -e .
```

## Quick Start

Here's a simple example to get you started:

```python
#!/usr/bin/env python3
"""Simple example game."""

import pygame
from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene

class MyGame(Scene):
    """A simple game scene."""
    
    NAME = "My Game"
    VERSION = "0.1.0"
    
    def __init__(self, options):
        super().__init__(options)
        self.background_color = (0, 0, 128)  # Dark blue
        
    def update(self):
        """Update game state."""
        super().update()
        
    def draw(self, surface):
        """Draw the scene."""
        surface.fill(self.background_color)
        
        # Draw a white rectangle in the center
        pygame.draw.rect(surface, (255, 255, 255), 
                         pygame.Rect(350, 250, 100, 100))
        
def main():
    """Main entry point."""
    GameEngine(game=MyGame).start()
    
if __name__ == "__main__":
    main()
```

## Documentation

For more detailed documentation, see the [docs](./docs) directory.

## Examples

Check out the [examples](./glitchygames/examples) directory for more examples.

## License

MIT License