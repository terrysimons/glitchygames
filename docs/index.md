GlitchyGames is a wrapper around Pygame that aims to support 20-25FPS minimum games on Raspberry Pi and other low powered Linux systems.

The engine is written to provide:

- Readability as a first principle
- Scene primitives
- Advanced event handling
- Human readable/editable sprite file formats

# Example Game

Let's make a new game called Bitrot Adventures.

The goal of our game will be to draw a pixel on the screen and handle key events to move the pixel around.

```python
#!/usr/bin/env python3
"""Bitrot Adventures"""
import argparse

import pygame

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene

class BitrotAdventures(Scene):
    """Draws a pixel to the screen"""
    def __init__(self, options):
        super().__init__(options=options, groups=None)

def main():
    GameEngine().start()

if __name__ == "__main__":
    main()
```



<!-- ::: glitchygames.engine -->