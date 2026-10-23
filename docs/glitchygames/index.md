# glitchygames API Reference

[glitchygames.color](./color/index.md)

glitchygames.color provides color utilities like palettes, helpers to do color conversion, etc...


[glitchygames.engine](./engine/index.md)

The glitchygames.engine module handles game initialization, event routing, minimal event loop that calls into the active scene's update method.

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
pygame-ce 2.5.8 (SDL 2.32.10, Python 3.14.8)
usage: Bitrot Adventures version 0.0.0 [-h] [-f TARGET_FPS] [--fps-log-interval-ms FPS_LOG_INTERVAL_MS] [-w] [-r RESOLUTION]
                                       [--use-gfxdraw] [--update-type {update,flip}] [--timer-backend {auto,fast,pygame}]
                                       [--sleep-granularity-ns SLEEP_GRANULARITY_NS] [--windows-timer-1ms] [--log-timer-jitter]
                                       [--perf-trim-percent PERF_TRIM_PERCENT] [--fps-histogram {equal-range,target-relative}]
                                       [--debug-overlay | --no-debug-overlay] [--record-trace PATH] [--replay-trace PATH]
                                       [--replay-fps {recorded,real}] [--audit | --no-audit] [--compare-processing]
                                       [--max-processing-slowdown PERCENT] [--replay-pause-at-frame N] [--rebaseline NEW]
                                       [--replay-digest PATH] [--random-seed RANDOM_SEED]
                                       [--screen-shake-intensity SCREEN_SHAKE_INTENSITY] [--rumble-intensity RUMBLE_INTENSITY]
                                       [--live-voice-pool LIVE_VOICE_POOL] [--default-background {test-pattern,channel-3}]
                                       [--video-driver {}] [--headless] [--input-mode {auto,joystick,controller}]
                                       [--font-name FONT_NAME] [--font-size FONT_SIZE] [--font-bold] [--font-italic]
                                       [--font-antialias] [--font-dpi FONT_DPI] [--font-system {pygame,freetype}]
                                       [-l {debug,info,warning,error,critical}] [--no-unhandled-events] [-p]
                                       [-s SOME_GAME_SPECIFIC_OPTION]

options:
  -h, --help            show this help message and exit

Graphics Options:
  -f, --target-fps TARGET_FPS
                        cap the framerate (default: the game's TARGET_FPS, else 60.01; 0 = uncapped)
  --fps-log-interval-ms FPS_LOG_INTERVAL_MS
                        how often to log the FPS counter in ms (default: 1000)
  -w, --windowed        run the program in windowed mode
  -r, --resolution RESOLUTION
                        the resolution to use (default: 1024x768)
  --use-gfxdraw
  --update-type {update,flip}
                        update or flip (default: update)
  --timer-backend {auto,fast,pygame}
                        timer backend for draw loop pacing (default: auto, the fast backend with this machine's sleep delay
                        measured, so each sleep wakes in time; fast assumes sleeps wake on time; pygame is the legacy backend)
  --sleep-granularity-ns SLEEP_GRANULARITY_NS
                        how long before each frame deadline the fast backend is to wake from its sleep and spin (ns); 0 spins
                        only
  --windows-timer-1ms   on Windows, request 1ms system timer resolution
  --random-seed RANDOM_SEED
                        master seed for every engine random stream (default: a random 64-bit seed, logged in recordings)
  --screen-shake-intensity SCREEN_SHAKE_INTENSITY
                        screen shake strength from 0.0 (off) to 1.0 (default: 1.0)
  --rumble-intensity RUMBLE_INTENSITY
                        controller rumble strength from 0.0 (off) to 1.0 (default: 1.0)
  --live-voice-pool LIVE_VOICE_POOL
                        mixer channels reserved for real-time synth voices (default: 4)
  --default-background {test-pattern,channel-3}
                        the background of a scene that sets none: the TV test pattern or the channel 3 blue screen (default:
                        test-pattern)
  --video-driver {}

Diagnostics Options:
  --log-timer-jitter    log frame pacing jitter statistics periodically
  --perf-trim-percent PERF_TRIM_PERCENT
                        percent of frames to trim from top and bottom in global FPS report
  --fps-histogram {equal-range,target-relative}
                        FPS histogram buckets in the shutdown report: equal-range (10 equal buckets spanning the analyzed min to
                        max, default) or target-relative (10% steps of the target FPS)
  --debug-overlay, --no-debug-overlay
                        show the debug overlay at startup (F3 toggles, F4 cycles panels)
  --record-trace PATH   record the session (sprites, frame times, input events, random seed) to a gzip JSON Lines trace for
                        inspection and later replay (default: off)
  --replay-trace PATH   replay a --record-trace recording exactly through the engine, comparing every frame with it and
                        reporting the first divergence (default: off)
  --replay-fps {recorded,real}
                        with --replay-trace: post FPS events from the recorded frame times (recorded, the default: exact, and
                        compared with the recording) or from this machine's measured frame times (real: what this machine
                        achieves; FPS events are then not compared, and sprites that draw the FPS value may diverge)
  --audit, --no-audit   with --replay-trace: instead of replaying, replay the recording twice in fresh headless processes with
                        different hash seeds and compare every frame with the recording and between the runs; exits 0 when both
                        match, 3 otherwise, 70 if a run could not finish
  --compare-processing  with --replay-trace --headless: measure each frame's processing time (its work, without presenting or
                        pacing) and report how it compares with the recording's (only meaningful on the machine that recorded)
  --max-processing-slowdown PERCENT
                        with --replay-trace --headless (implies --compare-processing): a replay that matched but took more than
                        PERCENT longer than the recording's processing time exits 8; a recording without processing times exits
                        65
  --replay-pause-at-frame N
                        with --replay-trace, watched: skip the start screen, run frames 0 to N - 1 without showing them, then
                        pause with frame N next (what step back restarts with; ignored with --headless)
  --rebaseline NEW      with --replay-trace OLD and --headless: replay OLD on the current code without stopping at divergences,
                        write the run's recording (OLD's inputs, the current sprites) to NEW, print a summary of the frames and
                        sprites that changed and exit 0
  --replay-digest PATH  with --replay-trace: write a SHA-256 of every replayed frame, then the divergence, to PATH as JSON lines
                        (used by --audit)
  --headless            run on SDL's dummy video and audio drivers: no window, no sound. With --replay-trace the replay also
                        runs unpaced and prints its report to stdout (exit 0 when it matches, 1 when it diverges, 65 for a
                        truncated recording)

Controller Options:
  --input-mode {auto,joystick,controller}
                        Which gamepads the game sees (default: auto, every device; a mapped pad sends controller events, any
                        other device joystick events; joystick: every device sends joystick events; controller: mapped pads
                        only)

Font Options:
  --font-name FONT_NAME
                        Font to use (default: the bundled Vera; the bundled variants are Vera, VeraBd, VeraIt and VeraBI; any
                        other name is looked up among the system's fonts)
  --font-size FONT_SIZE
  --font-bold
  --font-italic
  --font-antialias
  --font-dpi FONT_DPI
  --font-system {pygame,freetype}
                        Font system to use: freetype (enhanced, default) or pygame (built-in)

Game Options:
  -l, --log-level {debug,info,warning,error,critical}
                        set the logging level
  --no-unhandled-events
                        fail on unhandled events
  -p, --profile         enable profiling

Bitrot Adventures v0.0.0 Options:
  -s, --some-game-specific-option SOME_GAME_SPECIFIC_OPTION
                        foo help
```

[glitchygames.events](./events/index.md)

The glitchygames.events module extends the pygame event subsystem by giving you on_*_event callbacks.  Note that you can use the normal pygame raw event mode by simply implementing a `process_event(event)` method in your Scene: the engine then calls it once for each raw pygame event, in order, instead of dispatching on_*_event callbacks.

This can be especially useful for porting games to glitchygames, but there are some advantages to using glitchygames' event subsystem.

The glitchygames.events subsystem detects events that your game does not handle: each type is reported once (with `debug_events`), raised as an error under `--no-unhandled-events`, and counted in a table the engine logs at shutdown. See [Event System](../architecture/event_system.md).

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

The glitchygames.sprites module provides extended subclasses for sprite handling that will enable glitchygames to provide common tools and file formats that are human readable and templatable in addition to common sprite sheet formats and other goodies.


[glitchygames.ui](./ui/index.md)

The glitchygames.ui module provides common UI elements such as menubars, buttons, sliders, etc...

Also in the reference: [glitchygames.audio](./audio/index.md) (synthesis, recipes, live voices),
[glitchygames.collision](./collision/index.md) (layers and hitbox-aware detection),
[glitchygames.effects](./effects/index.md) (easing, tweens, screen shake),
[glitchygames.input](./input/index.md) (action maps, devices, the per-frame input snapshot, rumble),
[glitchygames.physics](./physics/index.md), [glitchygames.replay](./replay/index.md) (gameplay replay),
[glitchygames.state](./state/index.md) (saves) and [glitchygames.transitions](./transitions/index.md)
(scene transitions).

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
