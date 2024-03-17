# glitchygames API Reference

[glitchygames.color](./color/index.md)

glitchygames.color provides color utilities like palettes, helpers to do color conversion, etc...


[glitchygames.engine](./engine/index.md)

The glitchygame.engine module handles game initialization, event routing, minimal event loop that calls into the active scene's update method.

To start your game, pass your main Scene class to the engine.

```py
#!/usr/bin/env python3
"""Bitrot Adventures."""
import argparse
import logging
import pathlib

import pygame
from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene

# Instantiate a logger called "game" to enable glitchygames
# logging module. This is optional, but recommended.
LOG = logging.getLogger('game')

# Think of a scene as an encapsulated pygame screen.
#
# Each scene can handle its own events, update its own
# state, and draw its own graphics.
#
# The engine will handle switching between scenes
# and passing events to the current scene.
#
# The engine will also handle drawing the current
# scene to the screen.
class BitrotAdventures(Scene):
    """Draws a pixel to the screen"""

    NAME = 'Bitrot Adventures'
    VERSION = '0.0.0'

    def __init__(self, options):
        super().__init__(options=options)

    # This is called by glitchygames.GameEngine before
    # the class is instantiated.
    #
    # Note that GameEngine defines a few command line
    # options that are intended to be common across all
    # games, so it's worth checking your game with --help
    # before adding new options to ensure that you haven't
    # clobbered an existing option.
    @classmethod
    def args(cls, parser: argparse.ArgumentParser):
        """Game specific command line arguments."""
        parser.add_argument('-s', '--some-game-specific-option',
                            help='foo help')
        return parser



def main():
    # Note that the Scene (BitrotAdventures) is
    # passed in uninitialized - the engine
    # will initialize it for you.
    GameEngine(
        game=BitrotAdventures,
        icon='/path/to/icon'
    ).start()

if __name__ == '__main__':
    main()
```

When we run `./bitrotadventures.py` with the `-h` flag, we can see our command line option, along with options the engine and scene manager provide to us:

```sh
$ ./bitrotadventures.py -h
pygame 2.5.2 (SDL 2.28.3, Python 3.12.1)
Hello from the pygame community. https://www.pygame.org/contribute.html
usage: Bitrot Adventures version 0.0.0 [-h] [-f TARGET_FPS] [--fps-refresh-rate FPS_REFRESH_RATE] [-w] [-r RESOLUTION]
                                       [--use-gfxdraw] [--update-type {update,flip}] [--video-driver {}] [--font-name FONT_NAME]
                                       [--font-size FONT_SIZE] [--font-bold] [--font-italic] [--font-antialias]
                                       [--font-dpi FONT_DPI] [-l {debug,info,warning,error,critical}] [--no-unhandled-events] [-p]
                                       [-s SOME_GAME_SPECIFIC_OPTION]

options:
  -h, --help            show this help message and exit

Graphics Options:
  -f TARGET_FPS, --target-fps TARGET_FPS
                        cap the framerate (default: infinite)
  --fps-refresh-rate FPS_REFRESH_RATE
                        how often to update the FPS counter in ms (default: 1000)
  -w, --windowed        run the program in windowed mode
  -r RESOLUTION, --resolution RESOLUTION
                        the resolution to use (default: 1024x768)
  --use-gfxdraw
  --update-type {update,flip}
                        update or flip (default: update)
  --video-driver {}

Font Options:
  --font-name FONT_NAME
  --font-size FONT_SIZE
  --font-bold
  --font-italic
  --font-antialias
  --font-dpi FONT_DPI

Game Options:
  -l {debug,info,warning,error,critical}, --log-level {debug,info,warning,error,critical}
                        set the logging level
  --no-unhandled-events
                        fail on unhandled events
  -p, --profile         enable profiling

Bitrot Adventures v0.0.0 Options:
  -s SOME_GAME_SPECIFIC_OPTION, --some-game-specific-option SOME_GAME_SPECIFIC_OPTION
                        foo help
```

[glitchygames.events](./events/index.md)

The glitchygames.events module extends the pygame event subsystem by giving you on_*_event callbacks.  Note that you can use the normal pygame raw event mode by simply implementing a "process_events" method in your Scene.

This can be especially useful for porting games to glitchygames, but there are some advantages to using glitchygames' event subsystem.

The glitchygames.events subsystem dynamically detects events that your game does not handle and can suppress them automatically.  This helps mitigate the overhead introduced by processing pygame events into on_*_event handlers.

Note that if you bypass the glitchygames game engine event processing, you'll lose some functionality like `esc` and `q` to quit, along with  on_*_event handler support.

It is recommended that you use the glitchygames event subsystem.

TODO: Add some benchmark data comparing the two methods in various user scenarios to highlight the performance implications.


[glitchygames.fonts](./fonts/index.md)

The glitchygames.fonts module is a module that extends pygame's font mechanisms.


[glitchygames.interfaces](./interfaces/index.md)

The glitchygames.interfaces module implements various interfaces, notably the Sprite and Scene interfaces, which provide an API contract for subclasses.

Note: Migrating to these interfaces is a work in progress.  More to come.


[glitchygames.movement](./movement/index.md)

The glitchygames.movement module defines some common movement schemes.


[glitchygames.pixels](./pixels/index.md)

The glitchygames.pixels module provides common pixel manipulation operations such as 565 conversion.


[glitchygames.sprites](./sprites/index.md)

The glitchygames.sprites module provides extended subclasses for sprite handling that will enable glitchygames to provide common tools and file formats that are human readible and templatable in addition to common sprite sheet formats and other goodies.


[glitchygames.ui](./ui/index.md)

The glichtchygames.ui module provides common UI elements such as menubars, buttons, sliders, etc...

<!-- ::: glitchygames
    options:
      heading_level: 2
      inherited_members: true
      show_submodules: true -->


<!-- ## glitchygames.api

::: glitchygames.api
    name: "glitchygames.api"
    options:
      heading_level: 2
      inherited_members: true
      show_submodules: true -->
<!--
## glitchygames.color

::: glitchygames.color
    options:
      heading_level: 2
      inherited_members: true
      show_submodules: true

## glitchygames.engine

::: glitchygames.engine
    options:
      heading_level: 2
      inherited_members: true
      show_submodules: true

## glitchygames.events

::: glitchygames.events
    options:
      heading_level: 2
      inherited_members: true
      show_submodules: true

## glitchygames.examples

::: glitchygames.examples
    options:
      heading_level: 2
      inherited_members: true
      show_submodules: true
 -->
