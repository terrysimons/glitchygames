# Command-Line Argument System

GlitchyGames uses a composable argparse architecture where the engine, event managers,
font system, and individual games each contribute argument groups to a single parser.
Every game built on the engine automatically inherits all engine-level flags, and can
extend the parser with its own game-specific options.

## How Arguments Are Assembled

The orchestration happens in `GameEngine.initialize_arguments()`, called from
`GameEngine.__init__()`. The flow is:

```mermaid
sequenceDiagram
    participant GE as GameEngine.__init__()
    participant IA as initialize_arguments(game_class)
    participant AP as ArgumentParser
    participant ENGINE as GameEngine.args()
    participant MGR as Event Manager .args() x10
    participant GAME as game_class.args()
    participant NS as Namespace

    GE->>IA: initialize_arguments(game_class)
    IA->>AP: ArgumentParser("GameName version X.Y")
    IA->>ENGINE: GameEngine.args(parser)

    Note over ENGINE: Adds "Graphics Options" group<br/>12 arguments

    ENGINE->>MGR: AudioEventManager.args(parser)
    Note over MGR: Adds "Sound Mixer Options" group<br/>(empty, reserved)

    ENGINE->>MGR: DropEventManager.args(parser)
    Note over MGR: Adds "Drop Options" group<br/>(empty, reserved)

    ENGINE->>MGR: ControllerEventManager.args(parser)
    Note over MGR: Adds "Controller Options" group<br/>1 argument

    ENGINE->>MGR: FontManager.args(parser)
    Note over MGR: Adds "Font Options" group<br/>7 arguments

    ENGINE->>MGR: GameEventManager.args(parser)
    Note over MGR: Adds "Game Options" group<br/>3 arguments

    ENGINE->>MGR: JoystickEventManager.args(parser)
    Note over MGR: Adds "Joystick Options" group<br/>(empty, reserved)

    ENGINE->>MGR: KeyboardEventManager.args(parser)
    Note over MGR: Adds "Keyboard Options" group<br/>(empty, reserved)

    ENGINE->>MGR: MidiEventManager.args(parser)
    Note over MGR: Adds "Midi Options" group<br/>(empty, reserved)

    ENGINE->>MGR: MouseEventManager.args(parser)
    Note over MGR: Adds "Mouse Options" group<br/>(empty, reserved)

    ENGINE->>MGR: WindowEventManager.args(parser)
    Note over MGR: Adds "Window Options" group<br/>(empty, reserved)

    ENGINE-->>IA: return parser

    IA->>AP: parser.add_argument_group("GameName vX.Y Options")
    IA->>GAME: game_class.args(game_group)
    Note over GAME: Adds game-specific arguments<br/>to its own group

    IA->>AP: parser.parse_args()
    AP-->>NS: Namespace with all arguments
    IA->>IA: GameEngine.OPTIONS = vars(args)
    IA->>IA: Derive synthetic: debug_events
    IA->>IA: Back-propagate: game.options = OPTIONS
```

## The Argument Group Hierarchy

Each layer adds its own `add_argument_group()`, producing clearly separated
sections in `--help` output. The hierarchy mirrors the engine architecture.

```mermaid
flowchart TD
    subgraph Parser["ArgumentParser: GameName version X.Y"]
        subgraph L1["Layer 1: Graphics Options (GameEngine)"]
            F1["-f, --target-fps"]
            F2["--fps-log-interval-ms"]
            F3["-w, --windowed"]
            F4["-r, --resolution"]
            F5["--use-gfxdraw"]
            F6["--update-type"]
            F7["--timer-backend"]
            F8["--sleep-granularity-ns"]
            F9["--windows-timer-1ms"]
            F10["--log-timer-jitter"]
            F11["--perf-trim-percent"]
            F12["--video-driver"]
        end

        subgraph L2["Layer 2: Event Manager Groups"]
            subgraph SM["Sound Mixer Options"]
                SM_EMPTY["(no arguments yet)"]
            end
            subgraph DO["Drop Options"]
                DO_EMPTY["(no arguments yet)"]
            end
            subgraph CO["Controller Options"]
                CO1["--input-mode"]
            end
            subgraph FO["Font Options"]
                FO1["--font-name"]
                FO2["--font-size"]
                FO3["--font-bold"]
                FO4["--font-italic"]
                FO5["--font-antialias"]
                FO6["--font-dpi"]
                FO7["--font-system"]
            end
            subgraph GO["Game Options"]
                GO1["-l, --log-level"]
                GO2["--no-unhandled-events"]
                GO3["-p, --profile"]
            end
            subgraph JO["Joystick Options"]
                JO_EMPTY["(no arguments yet)"]
            end
            subgraph KO["Keyboard Options"]
                KO_EMPTY["(no arguments yet)"]
            end
            subgraph MIO["Midi Options"]
                MIO_EMPTY["(no arguments yet)"]
            end
            subgraph MO["Mouse Options"]
                MO_EMPTY["(no arguments yet)"]
            end
            subgraph WO["Window Options"]
                WO_EMPTY["(no arguments yet)"]
            end
        end

        subgraph L3["Layer 3: Game-Specific Options"]
            GS["(varies per game)"]
        end
    end
```

## How Games Add Arguments

A game adds arguments by defining a `@classmethod` called `args()` on its scene class.
The engine discovers this method via `getattr(game, 'args', None)` and calls it with
a dedicated argument group. If the game does not define `args()`, the engine logs an
informational message and continues.

```mermaid
flowchart TD
    subgraph Engine["GameEngine.initialize_arguments()"]
        CHECK{"getattr(game, 'args', None)"}
        CHECK -->|"method exists"| GROUP["parser.add_argument_group(\nGameName vX.Y Options)"]
        GROUP --> CALL["game.args(group)"]
        CHECK -->|"None"| LOG["log.info: Game does not\nimplement arguments"]
    end

    subgraph GameCode["Your Game Scene"]
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
class JoystickDemo(Scene):
    NAME = 'Joystick Demo'
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
| `-f`, `--target-fps` | `float` | `0.0` (infinite) | Cap the framerate |
| `--fps-log-interval-ms` | `float` | `1000` | How often to log the FPS counter in ms |
| `-w`, `--windowed` | `store_true` | `True` | Run in windowed mode |
| `-r`, `--resolution` | `str` | `800x480` | Display resolution (WxH) |
| `--use-gfxdraw` | `store_true` | `False` | Use pygame.gfxdraw for rendering |
| `--update-type` | `choice` | `update` | Display update method: `update` or `flip` |
| `--timer-backend` | `choice` | `pygame` | Timer backend: `pygame` or `fast` |
| `--sleep-granularity-ns` | `int` | `1000000` | Minimum sleep granularity for pacing (ns); 0 to uncap |
| `--windows-timer-1ms` | `store_true` | `False` | On Windows, request 1ms system timer resolution |
| `--log-timer-jitter` | `store_true` | `False` | Log frame pacing jitter statistics periodically |
| `--perf-trim-percent` | `float` | `5.0` | Percent of frames to trim from top and bottom in FPS report |
| `--video-driver` | `choice` | `None` | Platform-specific video driver (see below) |

**`--video-driver` choices by platform:**

| Platform | Choices |
|----------|---------|
| Linux | `wayland`, `x11`, `dga`, `fbcon`, `directfb`, `ggi`, `vgl`, `svgalib`, `aalib` |
| Windows | `windib`, `directx` |
| macOS | (none currently defined) |

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
| `--input-mode` | `choice` | `controller` | Input event family: `joystick` or `controller` |

### Font Options

Added by `FontManager.args()` in `glitchygames/fonts/font_manager.py`.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--font-name` | `str` | `arial` | Font name |
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
| Sound Mixer Options | `events/audio.py` | `AudioEventManager` |
| Drop Options | `events/drop.py` | `DropEventManager` |
| Joystick Options | `events/joystick.py` | `JoystickEventManager` |
| Keyboard Options | `events/keyboard.py` | `KeyboardEventManager` |
| Midi Options | `events/midi.py` | `MidiEventManager` |
| Mouse Options | `events/mouse.py` | `MouseEventManager` |
| Window Options | `events/window.py` | `WindowEventManager` |

### Synthetic Options (Not from argparse)

These are derived after parsing and injected into the OPTIONS dict.

| Key | Type | Derived From | Description |
|-----|------|-------------|-------------|
| `debug_events` | `bool` | `log_level` | `True` when log_level is `debug`, `critical`, or `error` |

## Bitmappy Game-Specific Arguments

Added by `BitmapEditorScene.args()` in `glitchygames/tools/bitmappy.py`.
These appear under the heading **"Bitmappy vX.Y Options"** in `--help`.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-v`, `--version` | `store_true` | `False` | Print the game version and exit |
| `-s`, `--size` | `str` | `32x32` | Canvas size (WxH in pixels) |

## Example Game Arguments

Other games in the project demonstrate the pattern:

| Game | File | Arguments |
|------|------|-----------|
| Paddle Slap | `examples/paddleslap.py` | `-v, --version` |
| DT Demo | `examples/dt_demo.py` | `-v, --version` |
| Joystick Demo | `examples/joystick_demo.py` | `--time` (int, default 10), `-v, --version` |
| Bitrot Adventures | `scripts/bitrotadventures.py` | `-s, --some-game-specific-option` |
| Animation Demo | `scripts/animation_scene_full_demo.py` | `-v, --version` |

## What `--help` Looks Like

When a user runs `uv run bitmappy --help`, argparse produces output structured
like this (argument groups appear in registration order):

```
usage: Bitmappy version X.Y [-h] [-f TARGET_FPS] [...]

options:
  -h, --help            show this help message and exit

Graphics Options:
  -f, --target-fps      cap the framerate (default: infinite)
  --fps-log-interval-ms how often to log the FPS counter in ms (default: 1000)
  -w, --windowed        run the program in windowed mode
  -r, --resolution      the resolution to use (default: 1024x768)
  --use-gfxdraw
  --update-type         update or flip (default: update)
  --timer-backend       timer backend for draw loop pacing (pygame|fast)
  --sleep-granularity-ns minimum sleep granularity for pacing (ns); 0 to uncap
  --windows-timer-1ms   on Windows, request 1ms system timer resolution
  --log-timer-jitter    log frame pacing jitter statistics periodically
  --perf-trim-percent   percent of frames to trim in global FPS report
  --video-driver

Sound Mixer Options:

Drop Options:

Controller Options:
  --input-mode          Choose input event family to use (default: controller)

Font Options:
  --font-name
  --font-size
  --font-bold
  --font-italic
  --font-antialias
  --font-dpi
  --font-system         Font system to use: freetype or pygame

Game Options:
  -l, --log-level       set the logging level
  --no-unhandled-events fail on unhandled events
  -p, --profile         enable profiling

Joystick Options:

Keyboard Options:

Midi Options:

Mouse Options:

Window Options:

Bitmappy vX.Y Options:
  -v, --version         print the game version and exit
  -s, --size
```

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
