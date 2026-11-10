GlitchyGames is a wrapper around Pygame for games that run at 60 FPS on Raspberry Pi and other
low powered Linux systems. [Requirements](requirements.md) shows what each measured machine runs
today: at 60 FPS's 16.7 ms frame budget, the Raspberry Pi 5 runs every game measured, and the
Raspberry Pi 4 every game but Brave Adventurer, which fits a 30 FPS target there.

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
"""Bitrot Adventures: a pixel on the screen that the arrow keys move."""

import pygame

from glitchygames.engine import GameEngine
from glitchygames.input import ActionMap
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite
from glitchygames.world import CoordinateSpace

PIXELS_PER_SECOND = 60.0
# Each direction is a physical key position (a scancode): the same place on every layout
ARROW_KEYS = {
    'left': pygame.KSCAN_LEFT,
    'right': pygame.KSCAN_RIGHT,
    'up': pygame.KSCAN_UP,
    'down': pygame.KSCAN_DOWN,
}


class Pixel(Sprite):
    """One white pixel. A world sprite: the game moves world_x and world_y, the engine draws it."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(self, *, x, y, groups):
        super().__init__(x=x, y=y, width=1, height=1, name='Pixel', groups=groups)
        self.image.fill('white')
        self.world_x = x
        self.world_y = y


class BitrotAdventures(Scene):
    """A pixel on a black screen, moved by the arrow keys."""

    NAME = 'Bitrot Adventures'
    VERSION = '0.0.0'

    def __init__(self, options=None, groups=None):
        super().__init__(options=options, groups=groups)
        self.background_color = (0, 0, 0)
        width, height = self.screen.get_size()
        self.pixel = Pixel(x=width // 2, y=height // 2, groups=self.all_sprites)
        self.actions = ActionMap.from_engine_options(self.options)
        for direction, scancode in ARROW_KEYS.items():
            self.actions.bind(direction, scancode=scancode)

    def dt_tick(self, dt):
        """Game logic: move the pixel while an arrow key is held."""
        super().dt_tick(dt)
        step = PIXELS_PER_SECOND * dt
        if self.actions.is_held('left'):
            self.pixel.world_x -= step
        if self.actions.is_held('right'):
            self.pixel.world_x += step
        if self.actions.is_held('up'):
            self.pixel.world_y -= step
        if self.actions.is_held('down'):
            self.pixel.world_y += step
        # This frame's key events come after dt_tick
        self.actions.begin_frame()

    def on_key_down_event(self, event):
        self.actions.handle_event(event)

    def on_key_up_event(self, event):
        self.actions.handle_event(event)
        # The base scene quits on Escape or Q
        super().on_key_up_event(event)


def main():
    # Pass the Scene class uninitialized; the engine creates it
    GameEngine(game=BitrotAdventures).start()


if __name__ == '__main__':
    main()
```



<!-- ::: glitchygames.engine -->
