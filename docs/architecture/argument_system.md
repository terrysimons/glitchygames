# Command-Line Argument System

GlitchyGames uses a composable argparse architecture where the engine, event managers,
font system, and individual games each contribute argument groups to a single parser.
Every game built on the engine automatically inherits all engine-level flags, and can
extend the parser with its own game-specific options.

## How Arguments Are Assembled

`GameEngine.initialize_arguments()`, called from `GameEngine.__init__()`, builds one parser from
three layers. Here is what happens when you run Bitmappy (`uv run bitmappy`): the Engine box
adds layers 1 and 2, the Bitmappy box layer 3, and argparse's `ArgumentParser` is outside both.

```mermaid
sequenceDiagram
    participant PARSER as ArgumentParser
    box rgb(232,238,255) Engine
    participant INIT as initialize_arguments
    participant ENGINE as GameEngine.args
    participant MANAGERS as the 12 event managers
    end
    box rgb(255,243,224) Bitmappy
    participant GAME as BitmapEditorScene.args
    end

    INIT->>PARSER: ArgumentParser("Bitmappy version 1.0")
    INIT->>ENGINE: GameEngine.args(parser)
    Note over ENGINE: Layer 1<br/>Graphics Options (15)<br/>Diagnostics Options (14, 2 hidden)
    loop for each of the 12
        ENGINE->>MANAGERS: manager.args(parser)
    end
    Note over MANAGERS: Layer 2, in this order<br/>App, Audio, Controller (1), Drop,<br/>Font (7), Game (3), Joystick, Keyboard,<br/>Midi, Mouse, Touch, Window<br/>(the 9 without a count add empty groups)
    INIT->>PARSER: add_argument_group("Bitmappy v1.0 Options")
    INIT->>GAME: BitmapEditorScene.args(group)
    Note over GAME: Layer 3<br/>-v, -s
    INIT->>PARSER: parse_args()
    PARSER-->>INIT: the parsed options
    Note over INIT: GameEngine.OPTIONS = the options<br/>target_fps resolved, debug_events derived<br/>game.options = OPTIONS
```

### What each layer adds (Bitmappy's `--help`)

`uv run bitmappy --help` lists every option, grouped by the layer that added it. Bitmappy adds
only two of its own; everything else every game gets from the engine.

| Layer | Group | Options |
|---|---|---|
| 1, the engine | Graphics Options | `-f/--target-fps`, `--fps-log-interval-ms`, `-w/--windowed`, `-r/--resolution`, `--use-gfxdraw`, `--update-type`, `--timer-backend`, `--sleep-granularity-ns`, `--windows-timer-1ms`, `--random-seed`, `--screen-shake-intensity`, `--rumble-intensity`, `--live-voice-pool`, `--default-background`, `--video-driver` |
| 1, the engine | Diagnostics Options | `--log-timer-jitter`, `--perf-trim-percent`, `--fps-histogram`, `--debug-overlay`, `--record-trace`, `--replay-trace`, `--replay-fps`, `--audit`, `--compare-processing`, `--max-processing-slowdown`, `--replay-pause-at-frame`, `--rebaseline`, `--replay-digest`, `--headless` (2 more are hidden: the watched replay's restart internals) |
| 2, event managers | Controller Options | `--input-mode` |
| 2, fonts | Font Options | `--font-name`, `--font-size`, `--font-bold`, `--font-italic`, `--font-antialias`, `--font-dpi`, `--font-system` |
| 2, event managers | Game Options | `-l/--log-level`, `--no-unhandled-events`, `-p/--profile` |
| 2, event managers | App, Sound Mixer, Drop, Joystick, Keyboard, Midi, Mouse, Touch, Window | none yet (`--help` leaves empty groups out) |
| 3, the game | Bitmappy v1.0 Options | `-v/--version`, `-s/--size` (the canvas size, `WIDTHxHEIGHT`, default `32x32`) |

What each option does is in the [Complete Flag Reference](#complete-flag-reference).

## The Argument Group Hierarchy

Each layer adds its own `add_argument_group()`, so `--help` shows clearly separated sections, in
the order of the layers. The layers mirror the engine's architecture.

```mermaid
%%{init: {"flowchart": {"wrappingWidth": 500}}}%%
flowchart TB
    subgraph ENGINE_ARGUMENT_LAYERS["Engine"]
        L1["<b>Layer 1: the engine</b> (GameEngine.args)<br/>Graphics Options, Diagnostics Options"]
        L2["<b>Layer 2: event managers and fonts</b> (each one's args)<br/>Controller Options, Font Options, Game Options,<br/>and 9 reserved groups with no options yet"]
    end
    subgraph GAME_ARGUMENT_LAYERS["Your game"]
        L3["<b>Layer 3: your game</b> (its scene's args)<br/>GameName vX.Y Options"]
    end
    L1 --> L2 --> L3
```

| Group | Layer | Options | What they cover |
|---|---|---|---|
| Graphics Options | 1 | 15 | frame rate, window and resolution, timing, random seed, shake, rumble, voices, background, video driver |
| Diagnostics Options | 1 | 14, plus 2 hidden | debug overlay, timer jitter and FPS reports, recording, replay, audit, rebaseline, processing comparison, headless |
| Controller Options | 2 | 1 | `--input-mode` |
| Font Options | 2 | 7 | font name, size, style, antialiasing, DPI, system fonts |
| Game Options | 2 | 3 | log level, profiling, unhandled events |
| App, Sound Mixer, Drop, Joystick, Keyboard, Midi, Mouse, Touch, Window | 2 | 0 | reserved; `--help` leaves empty groups out |
| GameName vX.Y Options | 3 | the game's | whatever the game adds (Paddle Slap: `-v`, `-b`, `--ball-spawn-mode`) |

The counts are what `uv run paddleslap --help` shows; the two hidden diagnostics options are the
watched replay's restart internals. Every option is listed in the
[Complete Flag Reference](#complete-flag-reference).

## How Games Add Arguments

A game adds arguments by defining a `@classmethod` called `args()` on its scene class.
The engine discovers this method via `getattr(game, 'args', None)` and calls it with
a dedicated argument group. If the game does not define `args()`, the engine logs an
informational message and continues.

```mermaid
flowchart TD
    subgraph Engine["Engine: GameEngine.initialize_arguments()"]
        CHECK{"getattr(game, 'args', None)"}
        CHECK -->|"method exists"| GROUP["parser.add_argument_group(\nGameName vX.Y Options)"]
        GROUP --> CALL["game.args(group)"]
        CHECK -->|"None"| LOG["log.info: Game does not\nimplement arguments"]
    end

    subgraph GameCode["Your game: its scene class"]
        ARGS["@classmethod\ndef args(cls, parser):\n    parser.add_argument(...)"]
    end

    CALL --> ARGS
```

### Pattern: Minimal Game

```python
class MyGame(Scene):
    NAME = 'My Game'
    VERSION = '1.0'

    @classmethod
    def args(cls, parser):
        parser.add_argument(
            '-v', '--version',
            action='store_true',
            help='print the game version and exit',
        )
```

### Pattern: Game with Custom Options

```python
class TimedDemo(Scene):
    NAME = 'Timed Demo'
    VERSION = '1.0'

    @classmethod
    def args(cls, parser):
        parser.add_argument(
            '--time', type=int, default=10,
            help='time in seconds to wait before quitting',
        )
        parser.add_argument(
            '-v', '--version',
            action='store_true',
            help='print the game version and exit',
        )
```

Note that the game receives an **argument group**, not the root parser. This means
game arguments appear under their own heading in `--help` output.

## OPTIONS Dictionary Flow

After parsing, the `Namespace` is converted to a plain dict and propagated to
every component that needs it.

```mermaid
flowchart TD
    PARSE["parser.parse_args()"] --> VARS["vars(args)\nNamespace -> dict"]
    VARS --> OPT["GameEngine.OPTIONS (class var)"]

    OPT --> SYNTH{"log_level in\nDEBUG/CRITICAL/ERROR?"}
    SYNTH -->|"Yes"| DEBUG_T["OPTIONS['debug_events'] = True"]
    SYNTH -->|"No"| DEBUG_F["OPTIONS['debug_events'] = False"]

    DEBUG_T & DEBUG_F --> BACKPROP["game.options = OPTIONS"]
    BACKPROP --> SM_OPT["SceneManager.OPTIONS = OPTIONS"]
    SM_OPT --> SCENE_INIT["Scene.__init__(options=OPTIONS)"]
    SCENE_INIT --> SELF_OPT["self.options = OPTIONS"]

    subgraph Access["Runtime Access"]
        A1["self.options['target_fps']"]
        A2["self.options['font_name']"]
        A3["self.options['log_level']"]
        A4["self.options['debug_events']"]
        A5["GameEngine.OPTIONS['resolution']"]
    end

    SELF_OPT --> Access
```

## Complete Flag Reference

### Graphics Options

Added by `GameEngine.args()` in `glitchygames/engine/game_engine.py`.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-f`, `--target-fps` | `float` | `None` (the game's `TARGET_FPS`, else 60.01) | Cap the framerate; `0` = uncapped |
| `--fps-log-interval-ms` | `float` | `1000` | How often to log the FPS counter in ms |
| `-w`, `--windowed` | `store_true` | `True` | Run in windowed mode (the default is already `True`, so the flag changes nothing) |
| `-r`, `--resolution` | `str` | `800x480` | Display resolution (WxH) |
| `--use-gfxdraw` | `store_true` | `False` | Use pygame.gfxdraw for rendering |
| `--update-type` | `choice` | `update` | Display update method: `update` or `flip` |
| `--timer-backend` | `choice` | `auto` | Timer backend: `auto` (the fast backend with this machine's sleep delay measured, so each sleep wakes in time), `fast` (assumes sleeps wake on time) or `pygame` (legacy) |
| `--sleep-granularity-ns` | `int` | `1000000` | How long before each frame deadline the fast backend is to wake from its sleep and spin (ns); 0 spins only |
| `--windows-timer-1ms` | `store_true` | `False` | On Windows, request 1ms system timer resolution |
| `--video-driver` | `choice` | `None` | Platform-specific video driver (see below) |
| `--random-seed` | `int` | random 64-bit | Master seed for every engine random stream |
| `--screen-shake-intensity` | `float` | `1.0` | Screen shake strength, 0.0 (off) to 1.0 |
| `--rumble-intensity` | `float` | `1.0` | Controller rumble strength, 0.0 (off) to 1.0 |
| `--live-voice-pool` | `int` | `4` | Mixer channels reserved for real-time synth voices |
| `--default-background` | `choice` | `test-pattern` | Background of a scene that sets none: `test-pattern` (the TV test pattern) or `channel-3` (the channel 3 blue screen) |

**`--video-driver` choices by platform:**

| Platform | Choices |
|----------|---------|
| Linux | `wayland`, `x11`, `dga`, `fbcon`, `directfb`, `ggi`, `vgl`, `svgalib`, `aalib` |
| Windows | `windib`, `directx` |
| macOS | (none currently defined; the code checks `platform.system() == 'MacOS'`, which never matches, so macOS falls through to no choices either way) |

### Diagnostics Options

Added by `GameEngine.args()` right after the Graphics Options: how any run is watched,
recorded, replayed or diagnosed, whatever the game. They change no game settings.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--log-timer-jitter` | `store_true` | `False` | Log frame pacing jitter statistics periodically |
| `--perf-trim-percent` | `float` | `5.0` | Percent of frames to trim from top and bottom in FPS report |
| `--fps-histogram` | `choice` | `equal-range` | FPS histogram buckets in the shutdown report: `equal-range` or `target-relative` |
| `--debug-overlay` / `--no-debug-overlay` | `bool` | `False` | Show the debug overlay at startup (F3 toggles, F4 cycles panels) |
| `--record-trace` | `PATH` | `None` | Record the session to a gzip JSON Lines trace ([Gameplay Recording and Replay](gameplay_replay.md)) |
| `--replay-trace` | `PATH` | `None` | Replay a recording exactly, reporting the first divergence |
| `--replay-fps` | `choice` | `None` (read as `recorded`) | With `--replay-trace`: FPS events from the `recorded` or the `real` frame times |
| `--audit` / `--no-audit` | `bool` | `False` | With `--replay-trace`: replay twice in fresh processes and compare (exit 0, 3 when nondeterministic, 70 when a run could not finish; see [exit codes](gameplay_replay.md#exit-codes)) |
| `--replay-digest` | `PATH` | `None` | With `--replay-trace`: write a SHA-256 per replayed frame (used by `--audit`) |
| `--compare-processing` | `store_true` | `False` | With `--replay-trace --headless`: report how each frame's processing time compares with the recording's |
| `--max-processing-slowdown` | `PERCENT` | `None` | With `--replay-trace --headless` (implies `--compare-processing`): exit 8 when a matched replay took more than PERCENT longer |
| `--rebaseline` | `NEW` | `None` | With `--replay-trace OLD --headless`: replay OLD on the current code without stopping at divergences and write the run's recording to NEW |
| `--replay-pause-at-frame` | `N` (non-negative int) | `None` | With `--replay-trace`, watched: skip the start screen, rebuild frames 0 to N - 1 unpresented, then pause with frame N next (what step back restarts with; ignored with `--headless`; [step back](gameplay_replay.md#step-back-home-and-d)) |
| `--headless` | `store_true` | `False` | Run on SDL's dummy video and audio drivers (no window, no sound); a replay also runs unpaced and prints its report to stdout ([headless runs](gameplay_replay.md#headless-runs-headless)) |

### Game Options

Added by `GameEventManager.args()` in `glitchygames/events/game.py`.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-l`, `--log-level` | `choice` | `info` | Logging level: `debug`, `info`, `warning`, `error`, `critical` |
| `--no-unhandled-events` | `store_true` | `False` | Raise `UnhandledEventError` on unhandled events |
| `-p`, `--profile` | `store_true` | `False` | Enable cProfile profiling |

### Controller Options

Added by `ControllerEventManager.args()` in `glitchygames/events/controller.py`.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--input-mode` | `choice` | `auto` | Which gamepads the game sees: `auto` (every device; a mapped pad sends controller events, any other device joystick events), `joystick` (every device sends joystick events) or `controller` (mapped pads only). See [Event System](event_system.md#one-device-one-event-layer) |

### Font Options

Added by `FontManager.args()` in `glitchygames/fonts/font_manager.py`.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--font-name` | `str` | `Vera` | Font name: the bundled `Vera`, `VeraBd`, `VeraIt` or `VeraBI`; any other name is looked up among the system's fonts |
| `--font-size` | `int` | `14` | Font size in points |
| `--font-bold` | `store_true` | `False` | Bold font |
| `--font-italic` | `store_true` | `False` | Italic font |
| `--font-antialias` | `store_true` | `False` | Enable font antialiasing |
| `--font-dpi` | `int` | `72` | Font DPI |
| `--font-system` | `choice` | `freetype` | Font system: `freetype` (enhanced) or `pygame` (built-in) |

### Reserved Groups (Empty, No Arguments Yet)

These groups exist as extension points. Each event manager creates its argument group
but does not currently populate it with any flags.

| Group Name | Source File | Manager Class |
|------------|------------|---------------|
| App Options | `events/app.py` | `AppEventManager` |
| Sound Mixer Options | `events/audio.py` | `AudioEventManager` |
| Drop Options | `events/drop.py` | `DropEventManager` |
| Joystick Options | `events/joystick.py` | `JoystickEventManager` |
| Keyboard Options | `events/keyboard.py` | `KeyboardEventManager` |
| Midi Options | `events/midi.py` | `MidiEventManager` |
| Mouse Options | `events/mouse.py` | `MouseEventManager` |
| Touch Options | `events/touch.py` | `TouchEventManager` |
| Window Options | `events/window.py` | `WindowEventManager` |

### Synthetic Options (Not from argparse)

These are derived after parsing and injected into the OPTIONS dict.

| Key | Type | Derived From | Description |
|-----|------|-------------|-------------|
| `debug_events` | `bool` | `log_level` | Meant to be `True` for the `debug`, `critical` and `error` levels, but the code compares with upper-case names while `--log-level` is lower case, so it is always `False` (BUGS.md #74) |

## Bitmappy Game-Specific Arguments

Added by `BitmapEditorScene.args()` in `glitchygames/bitmappy/editor.py`.
These appear under the heading **"Bitmappy vX.Y Options"** in `--help`.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-v`, `--version` | `store_true` | `False` | Print the game version and exit |
| `-s`, `--size` | `str` | `32x32` | Canvas size (WxH in pixels) |

## Example Game Arguments

Other games in the project demonstrate the pattern:

| Game | File | Arguments |
|------|------|-----------|
| Paddle Slap | `glitchygames/examples/paddleslap.py` | `-v, --version`, `-b, --balls` (int, default 1), `--ball-spawn-mode` (choice, default `paddle_only`) |
| DT Demo | `glitchygames/examples/dt_demo.py` | `-v, --version`, `-b, --balls` (int, default 1) |
| Clockwork Keep | `glitchygames/examples/clockwork_keep/game.py` | `--floor` (int, default 0) |
| Brave Adventurer (both editions) | `glitchygames/examples/brave_adventurer/game.py`, `glitchygames/examples/brave_adventurer_papyrus/game.py` | `-v, --version` |
| Joystick Demo | `glitchygames/examples/joystick_demo.py` | none (the engine's `--input-mode` chooses what it shows) |
| Bitrot Adventures | `scripts/bitrotadventures.py` | `-s, --some-game-specific-option` |
| Animation Demo | `scripts/animation_scene_full_demo.py` | `-v, --version` |

## What `--help` Looks Like

When a user runs `uv run bitmappy --help`, argparse produces output structured
like this (argument groups appear in registration order; argparse leaves out groups with no
arguments, such as App Options):

```
usage: Bitmappy version X.Y [-h] [-f TARGET_FPS] [...]

options:
  -h, --help            show this help message and exit

Graphics Options:
  -f, --target-fps      cap the framerate (default: the game's TARGET_FPS, else 60.01; 0 = uncapped)
  --fps-log-interval-ms how often to log the FPS counter in ms (default: 1000)
  -w, --windowed        run the program in windowed mode
  -r, --resolution      the resolution to use (default: 1024x768)
  --use-gfxdraw
  --update-type         update or flip (default: update)
  --timer-backend       timer backend for draw loop pacing (default: auto, the fast backend with this
                        machine's sleep delay measured, so each sleep wakes in time; fast assumes sleeps
                        wake on time; pygame is the legacy backend)
  --sleep-granularity-ns how long before each frame deadline the fast backend is to wake from its sleep
                        and spin (ns); 0 spins only
  --windows-timer-1ms   on Windows, request 1ms system timer resolution
  --random-seed         master seed for every engine random stream (...)
  --screen-shake-intensity, --rumble-intensity, --live-voice-pool
  --default-background  the background of a scene that sets none (...)
  --video-driver

Diagnostics Options:
  --log-timer-jitter    log frame pacing jitter statistics periodically
  --perf-trim-percent   percent of frames to trim from top and bottom in global FPS report
  --fps-histogram       FPS histogram buckets in the shutdown report (...)
  --debug-overlay, --no-debug-overlay
                        show the debug overlay at startup (F3 toggles, F4 cycles panels)
  --record-trace PATH   record the session (...)
  --replay-trace PATH   replay a --record-trace recording exactly (...)
  --replay-fps, --audit, --no-audit, --compare-processing, --max-processing-slowdown PERCENT,
  --replay-pause-at-frame N, --rebaseline NEW, --replay-digest PATH
                        (replay options)
  --headless            run on SDL's dummy video and audio drivers: no window, no sound (...)

Controller Options:
  --input-mode          Which gamepads the game sees (default: auto, ...)

Font Options:
  --font-name           Font to use (default: the bundled Vera; ...)
  --font-size
  --font-bold
  --font-italic
  --font-antialias
  --font-dpi
  --font-system         Font system to use: freetype (enhanced, default) or pygame (built-in)

Game Options:
  -l, --log-level       set the logging level
  --no-unhandled-events fail on unhandled events
  -p, --profile         enable profiling

Bitmappy vX.Y Options:
  -v, --version         print the game version and exit
  -s, --size
```

The `--resolution` help text says 1024x768, but the default is `800x480` (BUGS.md #76).

## How to Add Arguments to a New Event Manager

If you are adding arguments to a currently-empty event manager group, follow the
existing pattern:

```python
# In glitchygames/events/mouse.py

@classmethod
def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    group = parser.add_argument_group('Mouse Options')

    group.add_argument(
        '--mouse-sensitivity',
        type=float,
        default=1.0,
        help='Mouse sensitivity multiplier (default: 1.0)',
    )

    return parser
```

The engine already calls your manager's `args()` method — you just need to
add `add_argument()` calls to the existing group.

## How to Create a New Game with Arguments

```python
from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene


class MyGame(Scene):
    NAME = 'My Game'
    VERSION = '1.0'

    @classmethod
    def args(cls, parser):
        """Add game-specific arguments.

        Args:
            parser: An argument group (not the root parser).
        """
        parser.add_argument(
            '-v', '--version',
            action='store_true',
            help='print the game version and exit',
        )
        parser.add_argument(
            '--difficulty',
            choices=['easy', 'medium', 'hard'],
            default='medium',
            help='game difficulty level',
        )

    def __init__(self, options):
        super().__init__(options=options)
        # Access your arguments via self.options
        self.difficulty = self.options['difficulty']


def main():
    GameEngine(game=MyGame).start()
```

Your arguments will automatically appear under **"My Game v1.0 Options"** in
the `--help` output, separate from all engine-level flags.
