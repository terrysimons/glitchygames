# Gameplay Recording and Replay

GlitchyGames can record a play session and replay it exactly through the real engine. Same
engine version and same recording give bit-identical sprite traces: every frame's sprite
`rect` and `visible` match the recording. Audio is played during a replay but is not compared.

This page covers recording, exact replay, watching a replay (with step back and bookmarks),
headless runs, the determinism audit, golden replays and rebaselining them, the tools any game
gets (as its own flags and as the `glitchygames` command), in-game playback (demos, instant
replay, ghosts), and the rules game code follows so its sessions replay. See
`plans/2026-10-19-gameplay-replay.md` for the design and `plans/future-work.md` for the
follow-ups.

## Quick start

```bash
# Record a session
uv run paddleslap --record-trace session.jsonl.gz

# Watch it replay exactly, comparing every frame with the recording (press Space to start)
uv run paddleslap --replay-trace session.jsonl.gz

# The same with no window, no sound and no pacing; the report goes to stdout, and the exit
# code says whether it matched (0) or diverged (1)
uv run paddleslap --replay-trace session.jsonl.gz --headless

# Check that it replays the same way twice, in fresh processes with different hash seeds
uv run paddleslap --replay-trace session.jsonl.gz --audit

# After an intentional change: replay the same inputs on the current code, write what it does
# to a new recording and print what changed
uv run paddleslap --replay-trace session.jsonl.gz --rebaseline new-session.jsonl.gz --headless

# Did the code get slower? Compare this machine's processing time per frame with the
# recording's; with a limit, more than 10% slower exits 8
uv run paddleslap --replay-trace session.jsonl.gz --headless --max-processing-slowdown 10

# Onion skin: watch a replay with another recording's items drawn over it, half transparent
uv run paddleslap --replay-trace new-session.jsonl.gz --compare-trace session.jsonl.gz

# Play live against a recording: its items drawn over your game, half transparent
uv run paddleslap --compare-trace session.jsonl.gz

# The same tools as the glitchygames command (the game comes from the recording), and a
# recording's runs, speed changes and behavior changes
uv run glitchygames replay-trace session.jsonl.gz --headless
uv run glitchygames report session.jsonl.gz
```

Every flag above is one of the engine's tools, which every game has without declaring anything;
[Tools for any game](#tools-for-any-game) lists them all.

## The doors

The engine takes everything from the outside world through a small set of **doors**, and game
code reaches them only through the engine. Live play plugs live providers into the doors;
replay plugs in providers that serve the recording. The game cannot tell which one it is
talking to, so a replay runs the real engine and the real game code again.

| Door | Live (`LiveSources`) | Replay (`ReplaySources`) |
|---|---|---|
| Event pump | pygame's queue | recorded batch N for pump call N |
| Frame time | the measured start-to-start time | the recorded `dt` |
| Polled input | captured from pygame once per frame | the recorded snapshot |
| Devices | real joysticks and controllers | stand-ins built from the recording |
| Saves | files on disk (`DiskSaveManager`) | in memory (`MemorySaveManager`), seeded from the recording |
| Wall clock | the real time | the recording's start time plus the frame clock |
| Random seed | `--random-seed` or 64 random bits | the recorded seed |
| Pacing | the target FPS | the target FPS; none under `--headless` |

The modules:

- `src/glitchygames/sources.py`: the `EngineSources` protocol and the registry (`active_sources()`,
  `install_sources(sources=...)`, `reset_sources()`) and the frame clock. It is a leaf module
  with no engine imports, which avoids an import cycle between the engine and the scenes.
  `install_sources` is allowed only before the first frame, so a run never mixes live and
  recorded input.
- `src/glitchygames/live_sources.py`: `LiveSources`.
- `src/glitchygames/recording.py`: `RecordingSources`, which wraps the live doors under
  `--record-trace` and records what passes through them.
- `src/glitchygames/replay/driver.py`: `ReplaySources`, the comparison and the divergence report.

`tests/test_engine_doors.py` scans the package and fails if any file but
`src/glitchygames/clock.py` uses the `time` module (a read, `time.sleep`, anything) or reads
`datetime`'s now, or if anything outside the doors polls pygame's keyboard or mouse, reads or
posts pygame events directly, uses pygame's timers, or enumerates or opens joysticks and
controllers. Its `ALLOWED_BYPASSES` lists the few exceptions, each with its reason. The engine's
own pacing, measurement and diagnostics read real time through the clock module's raw functions
(`raw_counter_ns()`, `raw_counter_seconds()`, `raw_sleep()`, `raw_wall_clock_time()`), which are
never replayed and are not for game code.

## Rules for game code

### Time

Read time from `src/glitchygames/clock.py` or `Scene.game_time`, never from `time`, `datetime` or
`pygame.time`:

| Use | For |
|---|---|
| `Scene.game_time` | gameplay timers and cooldowns; stops while the scene is paused |
| `frame_clock_seconds()`, `frame_clock_milliseconds()` | blinks, animation, "how long since" in UI; never pauses |
| `wall_clock_time()`, `wall_clock_epoch_seconds()` | timestamps (save metadata, undo history, logs) |
| `elapsed_seconds()` | throttles, debounces, repeat intervals, timeouts (subtract two readings) |
| `measured_seconds()` | real durations for logs and metrics only |

`elapsed_seconds()` is the frame clock, live and in a replay, so a throttle near its threshold
decides the same way both times; such timers advance once per frame. In a recorded run (and its
replay) `wall_clock_time()` is the recording's start time (`recorded_at`) plus the frame clock,
so a timestamp the game shows replays exactly; live play without recording reads the real wall
clock. `measured_seconds()` is real
monotonic time and is never replayed: never let its value change what is drawn, played or
recorded.

Text-widget cursor blinks use the frame clock, not `Scene.game_time`. A paused scene's widgets
are neither updated nor drawn, so a blink cannot be seen advancing while the game is paused.

### Polled input

Read held keys, modifiers, the mouse and device positions from the frame's input snapshot, never
from pygame:

```python
from glitchygames.input.state import current_input

snapshot = current_input()          # or GameEngine.input
snapshot.key_pressed(pygame.K_LEFT)                # by key code (follows the layout)
snapshot.scancode_pressed(scancode=pygame.KSCAN_W)  # by physical position (every layout)
snapshot.modifiers                  # KMOD bits
snapshot.mouse_position             # (x, y)
snapshot.mouse_buttons              # (left, middle, right)
snapshot.axis(device_id=instance_id, axis=0)                 # joystick layer, -1.0 .. 1.0
snapshot.button(device_id=instance_id, button=3)
snapshot.hat(device_id=instance_id, hat=0)
snapshot.controller_axis(device_id=instance_id, axis=pygame.CONTROLLER_AXIS_LEFTX)  # int scale
snapshot.controller_button(device_id=instance_id, button=pygame.CONTROLLER_BUTTON_A)
```

The snapshot is immutable and is taken once per frame, right after the frame's first event pump.
`dt_tick` runs before the pump, so there it is the previous frame's snapshot (the same lag as
polling pygame had). Devices are keyed by instance id. A game controller is read on two layers:
its joystick view (`axis`, `button`, `hat`) and the controller layer (`controller_axis`,
`controller_button`).

Held keys are physical positions (scancodes), and a key code depends on the keyboard layout (the
key in the A position is `K_q` on AZERTY). A recording therefore also holds the key codes the
held keys had on the recording machine, and a replay answers `key_pressed(pygame.K_q)` as that
machine did, whatever the replaying machine's layout. Only pygame's `K_*` key codes are recorded.

Limitation (BUGS.md #83): keys a layout adds that pygame names no `K_*` constant for, such as
French `é`, German `ß` or Spanish `ñ` (SDL gives them their character's code point as the key
code), are not in that list. The recorder can only find the held key codes by trying every
`K_*` constant (pygame lets Python ask a key code's position, not a position's key code), so a
game that polls one, say `key_pressed(ord('é'))`, reads it held live but not held in a replay,
even on the machine that recorded it. Key events are unaffected (a recorded KEYDOWN or KEYUP
keeps its `key`, whatever its value), and so are positional controls (`scancode_pressed`,
`ActionMap.bind(scancode=...)`). Handle such keys through events or by position, not by
polling their key code.

For positional controls (movement, say), poll `scancode_pressed(scancode=pygame.KSCAN_*)`: no
keymap is consulted, so it is the same key on every layout, live or replayed, as
`ActionMap.bind(scancode=...)` is for events.

### Devices

Enumerate and open joysticks and controllers only through `active_sources().devices()`
(`src/glitchygames/input/devices.py`): `joystick_count()`, `controller_count()`,
`is_controller(device_index=...)`, `name_for_index(device_index=...)`,
`open_joystick(device_index=...)`, `open_controller(device_index=...)` and
`joystick_for_instance(instance_id=...)`. A recording stores every answer (failures included) and
a descriptor of every opened device. A replay gives the recorded answers and stand-ins
(`ReplayJoystick`, `ReplayController`) whose positions come from the snapshot and whose rumble is
dropped, so it never needs the recorded hardware and never sees a device that happens to be
plugged in.

### Saves

Open a save store with `glitchygames.state.open_saves(app_name=...)`. Live play gets a
`DiskSaveManager`. A replay gets a `MemorySaveManager` seeded from the recording's snapshot of
that namespace: reads see what the original session saw, writes stay in memory, and real saves
are never touched. Both are `SaveManager`s, which hold every rule of the save format. A
recording's header holds each store as it was first opened, so a first scene whose `setup()`
writes to its saves (adds one to a play count) replays from the saves it found. Slots saved at
the same time are listed by name, so `list_slots()` gives the same order everywhere.

### Events and randomness

- Post events with `glitchygames.recording.post_event`, not `pygame.event.post`, so a recording
  can mark them internal. Replay delivers internal events from the code that posts them again;
  an SDL-type event posted directly would be delivered twice.
- Code that drives the game from outside its logic, as a player would (a supervisor, a test
  harness, a tool), posts with `glitchygames.recording.post_input_event` instead. The event is
  recorded as external input, whatever its type, so `--replay-trace`, instant replays and demos
  serve it whether or not they run the poster again (a copy the replayed code posts is
  dropped). A supervisor that posts with `post_event` is taken for the game itself, and a
  replay that does not run it diverges. While a demo or instant replay plays, its input posts
  of SDL types (keys, buttons, device and window events) are the player's input: a press ends
  a demo, a release is held for the live game, exactly as a replay of the session without the
  supervisor serves them.
- A supervisor may post any event this way, game events (`GAMEEVENT`, `MENUEVENT`, any
  `pygame.event.custom_type()`) included. The rule: input of an SDL type posted during a demo
  or instant replay counts as the player's; everything else reaches the game (after the
  demo or instant replay, if one is playing), live and replayed alike.
- Draw random numbers from the seeded named streams in `src/glitchygames/randomness.py`
  (`random_stream('name')`, `numpy_stream('name')`), never from the global `random` functions,
  `secrets` or an unseeded numpy generator.

## The supervisor hook and control events

A supervisor (`src/glitchygames/supervision.py`) is called once per frame at a fixed place: after
logic and events, before frame services, camera aim and positioning. What it changes is drawn
that frame and seen by collision on the next one.

```python
scene_manager.add_supervisor(supervisor=my_supervisor)   # my_supervisor.on_frame(frame_number=..., scene=...)
scene_manager.add_control_event_handler(kind='breakpoint', handler=on_breakpoint)
scene_manager.record_control_event(kind='breakpoint', data={'label': 'ball through paddle'})
```

A control event is a supervisor action recorded in the frame it happened in. A replay applies
the recorded control events again at the same frame's supervisor slot, so sessions with
supervisor actions replay exactly. A future cheat device will use this hook and channel.

## Recording (`--record-trace PATH`)

A recording is a gzip JSON Lines trace (format version 3; versions 2 and 3 can be read): a
header line, then exactly one line per main-loop frame. Each frame holds its `dt`, every event
batch the engine read from SDL's queue (each event tagged `external` or `internal`) and the
sprites. Format 3 adds per-frame `input_changes`, `control_events`, `devices_opened`,
`saves_opened`, `device_enumeration` and `scene_start` (each written only when not empty). The
header holds the game, scene and versions, every option, the start time, the random seed, and the
saves and devices the run took in before recording started. The full format is described in the
`src/glitchygames/recording.py` module docstring.

### Scene starts

A recording also holds how each scene began, so in-game playback (demos, instant replay) can
rebuild a scene from its start: the scene's first logic frame (the first frame whose `dt_tick`
runs on it) carries its `scene_start` (its class's module and qualified name, so two loaded
scenes of the same name are told apart, `replay_arguments()`, every random stream's
state and the frame clock as its `__init__` began and again as its first `setup()` began, the
saves as they were before its `__init__` ran, and the state its first logic frame began in;
`src/glitchygames/scene_start.py`). A playback starts there. Frame 0 holds the first scene's start when the run was started
with `--record-trace` (or `--rebaseline`). Starts are captured only while they can be used
(recording, playback, or a scene that opts into instant replay), so live play pays nothing. A
scene that cannot be rebuilt on its own sets `CAPTURES_SCENE_START = False` (the pause screen
does). A replay never compares starts.

A scene built with arguments besides `options` (Clockwork Keep's next floor carries the score
and lives) returns them from `replay_arguments()`, as they were when it was built; they must
read back from JSON exactly as returned:

```python
class FloorScene(Scene):
    def __init__(self, floor_index=0, player_score=0, options=None, groups=None):
        super().__init__(options=options, groups=groups)  # first: the start capture begins here
        self.floor_index = floor_index
        self.starting_player_score = player_score

    def replay_arguments(self):
        return {'floor_index': self.floor_index, 'player_score': self.starting_player_score}
```

Draw random numbers only after `super().__init__()`: the capture begins there.

## Replay (`--replay-trace PATH`)

At startup the replay reads the recording, applies its recorded options and seeds the random
streams with its seed. It refuses, logging the reason and exiting with one of the
[exit codes](#exit-codes), when:

- the recording is of another game (the header's `game` and each scene start's `scene` name
  their classes by logical names, `src/glitchygames/logical_names.py`: the layer, the module path
  inside the game's package, then `:` and the qualified name, as in
  `games.mr_muncher.game:MrMuncherScene`, which stay the same when the game's code moves; a
  recording made before logical names is compared by its exact `game_module` and
  `scene_module`, and a `--rebaseline` of it writes the logical names), cannot be read (not gzip,
  no permission, a directory) or has an unsupported format version: `UNUSABLE_INPUT` (65);
- the recording's game or scene has the same class name as the one loaded but another logical
  module (any class that moved to another logical module, for instance Bitmappy's scene, which
  left `glitchygames.bitmappy.editor` for `apps.bitmappy.editor:BitmapEditorScene`): a plain replay
  cannot tell a moved class from a different class of that name, so it refuses with
  `UNUSABLE_INPUT` (65) and a message naming the remedy,
  `--replay-trace OLD --rebaseline NEW --headless` (`REBASELINE_REMEDY` in
  `src/glitchygames/replay/driver.py`). A `--rebaseline` compares such records by qualified name
  alone (`modules_not_compared`, used for the game by `check_recorded_game` and for each scene
  start by `find_scene_class` in `src/glitchygames/replay/playback.py`), and NEW holds the current
  logical names;
- the file does not exist: `MISSING_INPUT` (66);
- `--record-trace` is given too: `OPTIONS_REFUSED` (64). Recording over a replay is what
  [`--rebaseline`](#rebaselining-rebaseline-new) does, and only it;
- its window does not open at the recorded display size: `UNUSABLE_INPUT` (65), with one line
  naming both sizes (`Cannot replay PATH: it was recorded on a 800x600 display, but the window
  opened at 800x480 (the window manager chose another size); refusing to replay it`).

Games read the display's size (PaddleSlap places its paddles at half the screen height), so the
replay opens its window at the size the recorded display had (the header's `screen_size`), not
at the recorded `--resolution`: a window manager may have given the recorded window another size
than it asked for. A headless replay always gets that size; a watched one gets it unless the
window manager refuses, and then the replay is refused as above. A recording whose header holds
no `screen_size` (the engine's recorder always writes one; a hand-made header may not) replays at
its recorded `--resolution` with a warning. A window resized during the recorded run is not
recorded, so a game that reads the live size every frame can still diverge.

A recording made by a different engine version replays with one warning. A version-2 recording
replays with one warning too: it has no input snapshots, so polled input reads as idle.

Each frame, the replay serves the recorded events, `dt`, input, devices, saves and clocks. Then
it compares the frame with the recording: the active scene's class, then each recorded sprite in
draw order (present, `rect`, `visible`), along with the frame's internal events, control events
and pump count. The first difference stops a headless replay, as does the last recorded frame;
a [watched replay](#watching-a-replay) pauses there instead. Closing the window stops any
replay. Then it reports how it went (logged, or printed to stdout under
[`--headless`](#headless-runs-headless)). A sprite divergence lists that sprite in
the last 20 frames up to the divergent one, as recorded and as replayed:

```text
Replay diverged at frame 6120: sprite Ball#2 rect expected [412, 300, 16, 16], got [412, 301, 16, 16]
Ball#2, last 20 frames (expected | got):
  6100: [400, 290, 16, 16] visible | [400, 290, 16, 16] visible
  ...
  6120: [412, 300, 16, 16] visible | [412, 301, 16, 16] visible
```

Other divergences (the scene, an event, the frame or pump count) are reported on their one line.
A replay that matched reports `Replay matched 9800 frames (end of recording)` (or `(quit before
the end)`, when the window was closed or a watched replay's viewer pressed Esc), and one that matched up to the cut-off of a truncated recording `Replay ended
early at frame 4312: the recording is truncated`.

Every replay that ends normally, watched or headless, exits with its result: `SUCCESS` (0) when
it matched or was quit before the end, `REPLAY_DIVERGED` (1) when it diverged, `UNUSABLE_INPUT`
(65) for a truncated recording. A crash, Ctrl-C, a signal or the game's own exit ends the run
as for any run, and the report then says only where the replay stopped (`Replay stopped at frame
12: the run ended with INTERNAL_ERROR (70)`); if the replay had already reached its result, the
report gives it, then `then the run ended with ...` (see
[exit codes](#exit-codes)). The game's own successful exit (`sys.exit(0)`) before the replay
reached its result exits `REPLAY_DIVERGED` (1), never `SUCCESS`, which would say it matched
(a rebaseline takes it as the game ending early instead: below).
A recording whose header or first frame cannot be decoded (a malformed device, saves or input
field) is refused as unusable (`UNUSABLE_INPUT`, 65), like an unreadable file.

While a replay runs, real keyboard, mouse, touch, joystick, controller, device and window events
are blocked at SDL, so they never reach the game (a watched replay leaves key presses and
releases unblocked for its controls, which never pass them on to the game). The block is applied again on every pump
(event managers created mid-run allow their types again). Each type's earlier blocked state is
restored exactly when the replay ends, normally or after an error. QUIT, the window's close event
and custom event types are never blocked, so closing the window still ends the replay. Blocking
also refuses posts of those types: game code that fakes input by posting `KEYDOWN` loses the
post, which shows up as a missing internal event divergence. A watched replay leaves `KEYDOWN`
and `KEYUP` unblocked, so such a post arrives there and matches its recording: a recording of a
game that posts keys can match watched and diverge headless (and under `--audit`). Recorded window references in
events are served as `None`, as live events of the display window carry.

### Watching a replay

A replay without `--headless` is watched: a read-only game inside a game
(`src/glitchygames/replay/viewer.py`). The outer loop, the replay viewer, owns the window: it ticks
60 times a second of real time whatever the speed and whether paused, reads the viewer's keys,
and presents the recorded game's latest frame with the status bar drawn on it. The inner loop,
the recorded game, runs its frames in full (logic, update and render) at their recorded frame
times: each tick runs as many as the real time since the last tick, times the speed, pays for
(at most `MAX_INNER_FRAMES_PER_TICK`, and only within an 11 ms real-time budget per tick, so
keys and drawing keep their 60 Hz). It never owes more than one tick's worth: after a stall it
runs one bounded burst and drops the rest, and when the recorded game cannot keep up with the
speed the status bar says so and shows the real speed (`can't keep up: ×3.2`). So 1x shows
about one recorded frame per tick, 8x about eight, 1/4x one every fourth tick. Which frames run
when never changes what they do, so a watched replay is exactly as exact as a headless one.

It first runs frame 0, then holds on a start screen: that frame dimmed, "Press Spacebar to Start
Game Replay" centred, and a smaller line naming the debug overlay's keys (`F3: debug overlay
F4: next panel`). Frame 0's sounds play before Space, and a one-frame recording reaches its end
at the start screen. The screen is drawn by the pause screen's `MessageScreen`
(`src/glitchygames/ui/message_screen.py`) with its own message and look, as an overlay on the
presented frame: switching to a real pause scene would change the recorded scene sequence.
Nothing runs while the replay is held: no frame, no frame clock, no recorded input. The viewer's
keys go to the replay's controls (`src/glitchygames/replay/controls.py`), never to the game. Each
key acts once per press (the key repeat games turn on is ignored); `.` and `,` held act once,
then after 300 ms ten times a second:

| Key | Action |
| --- | --- |
| Space | Start the replay from the start screen, then pause or resume |
| `.` | While paused, run one frame |
| `,` | While paused, step back one frame (held: one more frame back per repeat, restarting once on release) |
| Home | Restart at the beginning, paused after frame 0 |
| D | Restart just before the divergence, once the replay has found one |
| `]` / `[` | Double or halve the playback speed (0.25 to 8) |
| B | Bookmark the frame shown in the status bar |
| S | Save a copy of the recording with the bookmarks as breakpoints |
| Esc | Quit the replay |
| F3 / F4 | Toggle the debug overlay / show its next panel |

A status bar at the bottom centre shows `frame 6120 / 9800 · 1:42.0 · ×1 · paused · diverged at
6120` (the parts that apply), drawn on the presented frame after the debug overlay, so it is never
in a screenshot or a trace. At a divergence or the end of the recording the replay pauses with
the debug overlay on and a banner above the status bar (`Diverged at frame 6120: ...` or `End of
recording`); stepping past the end does nothing, and Esc ends the run with the replay's result.

#### Step back, Home and D

A replay cannot run backwards, and the engine cannot be rebuilt in-process, so these keys
restart the replay in a fresh process (`src/glitchygames/replay/rebuild.py`) with the same command
line (every option kept, `--replay-fps` included) plus `--replay-pause-at-frame N`, an explicit
`--debug-overlay` or `--no-debug-overlay`, and the viewer's speed, debug panel and the divergence
found so far (`--replay-viewer-state`, internal; D works at once after a restart). The window
closes and a new one opens; the end-of-run performance reports wait for the last replay. The
restarted replay skips the start screen and rebuilds: frames 0 to N - 1 run in full, unpresented
and unpaced, in silence (each frame's sounds are stopped after it and music is paused until the
rebuild ends, unless the game paused it itself), with `Rebuilding: frame k / N` shown on a cleared window every 0.1 s and printed
every second (Esc still quits). It then pauses with frame N next, showing frame N - 1's picture;
frame 0 always runs, so Home pauses after it. The first replay process supervises the restarts:
each later replay that steps back hands its restart command to it (`--replay-restart-handoff`,
internal) instead of starting a process of its own, so there are never more than two (the
supervisor keeps the memory its own replay used). The run exits with the last replay's status,
but `REPLAY_DIVERGED` once any of the runs diverged; SIGTERM or SIGHUP to the supervisor ends the
child too (killed with SIGKILL, without its teardown: a replay never records, so nothing is
lost). Stepping back from far into a long recording takes as long as rebuilding up to there.
`--replay-pause-at-frame` is ignored with `--headless` (nothing could unpause the replay).

#### Bookmarks (B and S)

B bookmarks the frame the status bar shows (`frame N`: paused with frame N next). S writes a
copy of the recording next to it, `x.bookmarked.jsonl.gz` for `x.jsonl.gz`, with a
`{"kind": "breakpoint", "label": "bookmark"}` control event added to frame N - 1 (the frame whose
picture was shown) for each bookmark, and logs where. With no bookmarks it writes nothing and
says `no bookmarks to save`. Saving the same bookmarks again writes nothing
(`bookmarks already saved to ...`), unless that copy was deleted since. A copy an earlier session
saved from the same recording keeps its bookmarks: a new save adds to them. A file of that name
that is a copy of another recording is never written over.

The copy's header names its source (`bookmarked_copy_of`), and only a file with that field is
ever updated in place. The original recording is never written, even one you named
`something.bookmarked.jsonl.gz` yourself; its copy is `something.bookmarked.bookmarked.jsonl.gz`.
The copy is written aside and then moved into place.

The copy replays exactly like its source, headless included:

- Breakpoints are applied again on their frame and never compared.
- A truncated source's copy is marked `source_truncated`, so it still ends as truncated
  (`UNUSABLE_INPUT` headless, the truncated banner when watched).
- A version-2 source's copy is marked `input_capture_format_version: 2`, so it keeps the
  version-2 input warning and does not compare control events.

A watched replay of the copy pauses at each breakpoint, showing `frame N` again with
`breakpoint: bookmark`. A rebuild after a restart runs past breakpoints to its own pause frame.

Stepping back (or Home, or D) with bookmarks saves the copy first and restarts on the copy, so
bookmarks survive restarts. In the restarted replay:

- The bookmark list starts with the copy's bookmarks, so S keeps them.
- Playing forward pauses at every earlier bookmark again.
- If the copy cannot be saved, the restart uses the recording it was replaying and logs a
  warning naming the bookmarks lost.

### Onion skin (`--compare-trace OLD`)

`--replay-trace NEW --compare-trace OLD` watches NEW as usual, with OLD's items from the frame of
the same number drawn over each frame shown, at `--compare-alpha PERCENT` opacity (default 50; 0
to 100, anything else is refused by the parser). NEW itself stays fully opaque: OLD's background
is never drawn. The status bar stays on top.

**What counts as one of OLD's items.** Each frame is judged on its own. OLD's background
colors are the colors that cover at least 5% of OLD's frame: a floor, a wall. One of OLD's items
is a pixel where OLD differs from NEW and OLD's color is none of those. It is blended over
whatever NEW shows there; every other pixel is NEW's, exactly. So:

| Your dot | OLD's dot | What you see there |
|---|---|---|
| there | there | your dot |
| there | eaten | your dot, solid |
| eaten | there | OLD's dot, half transparent, over your floor |
| eaten | eaten | your floor |

A frame both runs share draws nothing. Three costs of the rule: a part of OLD's sprite drawn in
a background color (the floor's) is not shown; a background made of many small colors (a
texture, a gradient) may show some of them as items; and one color covering 5% or more of OLD's
frame is background even when it is OLD's item (a large sprite, about 139x139 pixels at
800x480, many pickups of one color, a full-screen overlay), so it vanishes from the ghost. The
blend costs about 2.4 ms a frame when the runs match and 4.7 ms with a few sprites apart, for an
800x480 window; a frame whose every pixel has a color of its own (noise) costs about 19 ms, and
a textured backdrop falls in between. OLD's items are drawn over NEW's whole finished frame, so
an item OLD still has where NEW's character stands (an uneaten dot under NEW's Mr. Muncher) is
drawn over that character; painting the two games layer by layer fixes it once OLD can run in the
same process (decision 20 of the Part 3 plan). NEW replays, compares and
exits exactly as it would alone: only the shown copy is drawn on. The `glitchygames` command
takes the same options (`glitchygames replay-trace NEW --compare-trace OLD`).

OLD is replayed by a headless child process (OLD's own game, under OLD's own seed), which
streams each frame's pixels to the viewer over a loopback socket, proving itself with a token
drawn for that run. The viewer reads one frame per frame it shows, so pausing and stepping move
both runs together, and only one OLD frame is held in memory. Stepping back (or Home, or D)
restarts the child at the same frame as the restarted replay; the child rebuilds alongside the
replay's own rebuild.

- **OLD shorter than NEW:** OLD's last frame stays, labelled `OLD ended at frame N`. OLD that
  diverges on the current code stops at its divergence, so it ends there (the log says why).
- **NEW shorter than OLD:** the replay ends as usual, and the child is stopped.
- **OLD stalls** (its child sends nothing for a minute): OLD ends there, labelled and logged as
  above, the child is stopped, and NEW's replay goes on.
- **The same recording under another seed** shows what the seed changes:
  `--replay-trace OLD --random-seed 7 --compare-trace OLD` draws OLD's own run over its run under
  seed 7 (a replay under another seed compares and writes nothing).
- **Refused before anything runs:** with `--headless` (an onion skin is watched; headless, a
  replay under another seed or a `--rebaseline` reports what changed), `--audit` or
  `--rebaseline` (exit 64), and an OLD recorded at another screen size than NEW, or no readable
  recording (65; a header without its seed counts, as OLD's child could not replay it), or
  missing (66).

The child always ends with the replay: when it ends, fails, is interrupted or restarts. The
contract is the docstring of `src/glitchygames/replay/tools/compare.py`.

#### Live play against OLD (`<game> --compare-trace OLD`)

Without `--replay-trace`, `--compare-trace OLD [--compare-alpha PERCENT]` lets you play the game
live, with real input, while OLD's frame of the same number is drawn over each frame you see.
OLD is replayed by the same headless child as above.

- **Pausing freezes the ghost.** Frames are paired by game frames: the frames a game's own
  logic ran in, not its pause screen's. While you are paused, OLD's frame stays where it was,
  and it moves on when the game does. OLD's own pauses are skipped the same way, so your game
  frame N meets OLD's game frame N. A replay pairs frames the same way, so
  `--record-trace NEW --compare-trace OLD`, and later `--replay-trace NEW --compare-trace OLD`,
  show the same pairs. Recordings themselves still count every frame.
- **The seed:** the game plays under OLD's recorded seed, so the ghost starts in the same world,
  unless `--random-seed N` is given. The log names the seed either way.
- **OLD shorter than your play:** OLD's last frame stays, labelled `OLD ended at frame N`, and
  play goes on. The child is stopped when the game quits, fails or is interrupted.
- **Refused before anything runs:** with `--headless` (exit 64), an OLD that is missing (66) or
  not a readable recording (65; a header without its seed counts), or one recorded at another
  screen size than the game's window (65). `--record-trace NEW` may be given too, and records the
  seed played. There is no step back in live play, and this is a game flag only.
- **Not in a browser:** OLD's child is a separate process, which a browser page cannot start, so
  `--compare-trace` (live or with a replay) is refused there before anything starts (exit 64).

### `--replay-fps {recorded,real}`

With `recorded` (the default), FPS events, the performance statistics and the debug overlay's
performance panel use the recorded frame times, and FPS events are compared exactly. With
`real`, they use this machine's measured frame times and FPS events are not compared; sprites
that draw the FPS value may then diverge. Logic always receives the recorded `dt`.

## Headless runs (`--headless`)

`--headless` runs any game on SDL's dummy video and audio drivers: no window and no sound. It sets
`SDL_VIDEODRIVER` and `SDL_AUDIODRIVER` to `dummy` as soon as the options are read, before
pygame starts its display and mixer. If pygame was already started before the engine (by code
run at import), a display or mixer on another driver is restarted on the dummy one, with a
warning. When the run ends, after the engine has shut pygame down, both variables are put back as
they were (one that was not set is removed), so a program that goes on after a headless run
starts pygame on its own drivers again.

A live headless run is paced to the target FPS as usual (an unpaced live frame would last about
a millisecond of game time) and ends however the game ends. A headless replay is not paced at
all, since its frame times come from the recording, never waits (no start screen, no pause at
a divergence or the end; its key events stay blocked), prints its report to stdout instead of
logging it, and exits with its result as above.

## The determinism audit (`--audit`)

`--replay-trace PATH --audit` does not replay in-process. It runs the same command again, with
`--headless` added, as two child processes, with `PYTHONHASHSEED` set to 1 and 2, and each child
writes a SHA-256 digest of every replayed frame. The audit passes (exit `SUCCESS`, 0) when both runs match the
recording and their digests match each other; otherwise it reports the first differing frame
and exits `AUDIT_NONDETERMINISTIC` (3). A child that cannot start, hangs, crashes (exits with any
status but 0, or 1 with a recorded divergence) or writes no digests means the audit could not
run: `INTERNAL_ERROR` (70).
Fresh processes and different hash seeds make set and dict ordering bugs show up.

The audit compares only what the replay samples: the scene class and each sprite's `rect`,
`visible` and draw order. Pixels, audio and game state that never moves, hides or reorders a
sprite are not compared. It is refused (`OPTIONS_REFUSED`, 64) with `--replay-fps real`, under
`python -E` or `-I` (which would keep `PYTHONHASHSEED` from reaching the children) and without
`--replay-trace`. A truncated recording is refused before the children start
(`UNUSABLE_INPUT`, 65): an audit needs the whole recording.

## Exit codes

The exit code alone says who refused the run and why. Every code is a member of
`glitchygames.exit_codes.ExitCode` (also importable from `glitchygames.engine`); the engine logs
the code it exits with as `Exiting with OPTIONS_REFUSED (64)`, at INFO (shown with
`--log-level info`; a game's default is warning).

| Code | `ExitCode` member | Meaning |
|---|---|---|
| 0 | `SUCCESS` | Success; the replay matched; the audit is deterministic; the rebaseline was written |
| 1 | `REPLAY_DIVERGED` | A replay's frames differ from the recording |
| 2 | `ARGUMENT_PARSER_ERROR` | A usage error from argparse; the engine never exits with it itself |
| 3 | `AUDIT_NONDETERMINISTIC` | `--audit`'s two runs differ from each other or from the recording |
| 4 | `GENERATION_REJECTED` | The API server rejected the sprite client's generation request |
| 5 | `EXTRACTION_REJECTED` | The API server rejected the sprite client's frame extraction |
| 6 | `AUDIO_DROPOUT_RISK` | `scripts/audio_glitch_probe.py` found a risk of audio dropouts |
| 7 | `REBASELINE_INPUT_LOST` | `--rebaseline` wrote NEW, but the run never received some of OLD's input (it ended early, or did not pump a recorded batch) |
| 8 | `PROCESSING_SLOWER` | A replay matched, but its processing time exceeded the recording's by more than `--max-processing-slowdown` |
| 64 | `OPTIONS_REFUSED` | The engine refuses the options given (a combination it will not run) |
| 65 | `UNUSABLE_INPUT` | The recording or input data is unusable (another game's recording, an unsupported format version, a corrupt or unreadable file, a bad server response) |
| 66 | `MISSING_INPUT` | The input file does not exist |
| 69 | `SERVICE_UNAVAILABLE` | A required service (the API server) cannot be reached |
| 70 | `INTERNAL_ERROR` | An uncaught exception during a run or its teardown (logged with its traceback, after the teardown), or an audit that could not run |
| 73 | `CANNOT_WRITE_OUTPUT` | An output file or directory cannot be created or written (a rebaseline's new recording could not be moved into place) |
| 129 | `HANGUP` | Stopped by SIGHUP (Unix only) |
| 130 | `INTERRUPTED` | Stopped by SIGINT (Ctrl-C) |
| 143 | `TERMINATED` | Stopped by SIGTERM |
| 149 | `BREAK` | Stopped by SIGBREAK (Windows only: Ctrl-Break) |

0, 64-70 and 73 have the values of BSD `sysexits.h` (Python's `os.EX_OK`, `os.EX_USAGE` and so on,
which exist only on Unix, so the values are defined in the engine). The signal codes are
128 + the signal number. A run stopped by one of those signals exits only after the normal
teardown, so a recording is complete: the engine handles SIGTERM, SIGHUP and SIGBREAK for the
whole run (unless the game installed its own handler) and turns off SDL's own signal handling
(`SDL_NO_SIGNAL_HANDLERS`), which would otherwise turn SIGINT and SIGTERM into a QUIT event.
SIGKILL and SIGSTOP cannot be caught, Python ignores SIGPIPE, and SIGQUIT keeps its core-dump
convention. An engine started off the main thread cannot install its handlers, so SIGTERM then
ends it the system's default way, without the teardown. An exception raised before the run
starts (while the engine is being constructed) exits with Python's default status 1.

## Comparing processing time (`--compare-processing`)

A recording holds each frame's **processing time** (`processing_seconds`): the frame's work
(logic, events, frame services, positioning and rendering), without presenting it, without the
recorder's own writing and without the pacing sleep. The header's latest measurement run
(`measurement_runs[0]`, see "Content hashes and measurement history" below) names the machine
it was measured on (system, version and architecture, never the host name). These are
diagnostics: a replay never compares them with the recording to decide whether it matched, and
never serves them to the game. The comparison uses the newest entry, `processing_seconds[0]`.

`--replay-trace PATH --headless --compare-processing` measures this machine's processing time
for every replayed frame the same way and prints one line after the replay's report:

```text
Replay matched 9800 frames (end of recording)
Processing: the replay took 14.2% longer than the recording (9800 frames: 30.410 s against 26.630 s; median frame 3.100 ms against 2.710 ms); slowest against the recording: frame 812 +6.100 ms, frame 813 +5.920 ms, frame 4400 +3.010 ms
```

`--max-processing-slowdown PERCENT` (which implies `--compare-processing`) makes it a check: a
replay that matched but took more than PERCENT longer in total exits `PROCESSING_SLOWER` (8). A
divergence still exits `REPLAY_DIVERGED` (1), and a recording without processing times (made
before they were recorded) cannot be checked: `UNUSABLE_INPUT` (65), with `Processing: nothing
to compare` after the report.

Why processing time and not wall-clock time: a live run is paced (most of each frame is the
sleep before the next) and a headless replay is not paced at all, so their total times measure
different things. Processing time measures the same work in both. It only compares on the same
machine, so make the baseline on the machine that will check it (a CI runner); the report says
so when the recording names another machine.

Pacing still slows the work itself: between paced frames the processor idles and clocks down,
so a live recording's frames take longer than the same frames in an unpaced replay (one
Clockwork Keep session measured about 65% faster replayed than recorded live). So make the
baseline with a rebaseline, which is measured unpaced as every later replay is, and check
against it:

```bash
# Once, on the CI machine: the baseline (the same inputs, measured unpaced)
uv run clockwork-keep --replay-trace session.jsonl.gz --rebaseline baseline.jsonl.gz --headless

# On every change: fail if the work got more than 10% slower
uv run clockwork-keep --replay-trace baseline.jsonl.gz --headless --max-processing-slowdown 10
```

Replays of the same session against such a baseline land within about 1% of it. The latest
measurement run says whether it paced its frames (`processing_paced`; a live run with a target
FPS, as recording began) and names its frame-pacing timer, paced or not (`pacing_timer`: the
timer backend, its final spin and the sleep model `--timer-backend auto` measured, null if it
never did; `src/glitchygames/timing.py`),
and the report adds a note when the baseline was paced. `--compare-processing` needs `--headless` (a
watched replay presents, steps and rebuilds frames as its viewer asks) and is refused
(`OPTIONS_REFUSED`, 64) with `--audit` and with `--rebaseline` (a rebaseline's NEW records the
current code's own processing times anyway). The contract is
`src/glitchygames/replay/processing.py`'s docstring.

## Content hashes and measurement history

Every frame a recorder writes carries two histories, newest first, and the header a third
(design: `plans/2026-10-20-recording-content-hash-and-history.md`; contract:
`src/glitchygames/recording_history.py`):

| Where | Field | Each entry | Depth constant (10) |
|---|---|---|---|
| frame | `content_hash` | the frame's content hash | `CONTENT_HASH_HISTORY_DEPTH` |
| frame | `processing_seconds` | its processing time (`null` when not measured) | `PROCESSING_SECONDS_HISTORY_DEPTH` |
| header | `measurement_runs` | the run's provenance: machine, `processing_paced`, `pacing_timer` (its frame-pacing timer, paced or not: backend, final spin, and the sleep model `--timer-backend auto` measured, `null` if it never did), engine, pygame and Python versions, `measured_at`, `rebaselined_from`, `hash_scheme`, and `frame_count` (how many frames it wrote; filled in when the next rebaseline stacks onto it, `null` for the newest run, whose count is the file's) | `MEASUREMENT_RUNS_HISTORY_DEPTH` |

A fresh recording writes one entry in each. A rebaseline puts its own in front of the replayed
recording's and drops the oldest past the depth, so index `i` means run `i` in every list. If
the runs' depth is tuned below the hash depth, the deeper hashes have no run, so no
`hash_scheme`: treat their scheme as unknown. A reader takes the fields of a run it knows and
ignores fields a newer engine added.

The **content hash** is the first 64 bits of SHA-256 of the frame's content fields as a JSON
reader decodes them (string keys, lists), encoded as compact, key-sorted JSON (hash scheme 1),
so the stored hash is the one a reader recomputes from the frame it reads. Content is everything the game did or took in: `dt`, the event
batches, input, control events, devices, saves, scene starts, the scene and its sprites.
Measurements (the two history fields) are left out. Every frame field is one or the other, and
the hash refuses a field that is neither, so a new field cannot slip in or out unnoticed.

A rebaseline copies the inputs, `dt` included, so an unchanged game gives the same hash one
entry deeper, and a changed one shows exactly which frames changed. Two fresh recordings of the
same script differ anyway (each measures its own `dt`, and the game moves by it). A recording's
own hash, for any run, is derived from its frames' hashes:
`recording_content_hash(frames=..., run_index=i)`; it is not stored.

Neither history is compared by a replay or served to the game. They are the record the
baselines in the repository keep: behaviour (hashes) and speed (processing times) over time.

## Golden replays

Each game's workspace member holds a recorded session of it in
`<member>/tests/fixtures/replays/golden.jsonl.gz` (PaddleSlap, Clockwork Keep, Mr. Muncher and
Drawing Fire; both Brave Adventurer editions as `golden-classic.jsonl.gz` and
`golden-papyrus.jsonl.gz`).
`scripts/record_scripted_session.py` recorded them through the real engine loop (on the
engine's scripted-session recorder, the `record-session` tool below, with our games' input
scripts and controls tails from `scripts/golden_inputs.py`), with a
supervisor posting each game's golden input script, then the game's controls tail: input that
presses the controls the script does not, pauses and resumes, and ends with the game's own quit
control, so every golden replay ends on a QUIT the game posted and diverges when a control stops
working. `tests/replay/test_golden_replays.py` enforces it: every control the game binds (its
ActionMaps, plus the keys the engine's pause screen hard-codes) must be pressed in its golden
replay, or be listed in `UNEXERCISED_CONTROLS` with the reason (gamepad controls: no scripted
session has a gamepad). Each recording is a test item of its own:
the pytest plugin `src/glitchygames/testing/replays.py` (registered by the engine's `pytest11`
entry point, `glitchygames.testing.replays`, in every pytest run with glitchygames installed) collects
every `.../fixtures/replays/<console-script>/<name>.jsonl.gz` as `<console-script>/<name>`,
replays it headless in a child process through the console script's entry point
(`--replay-trace PATH --headless`) and fails, with the exit code and the child's output (the
divergence report), unless it exits `ExitCode.SUCCESS`. A directory that is not a console script
is a collection error. Another project's games get the plugin the same way, with nothing to
configure; loading it by name as well (`pytest_plugins = ['glitchygames.testing.replays']` or
`-p glitchygames.testing.replays`) still loads it once, and `-p no:glitchygames.testing.replays`
turns it off. The plugin imports no pygame (and prints no banner) until it finds a recording, so
a project that is no game gets no item and no output from it. Re-record a fixture only deliberately,
after finding out why it stopped replaying; the commands are in the script's docstring. After
an intentional change, rebaseline it instead (below), so it keeps its recorded inputs.

## Rebaselining (`--rebaseline NEW`)

`--replay-trace OLD --rebaseline NEW --headless` replays OLD's inputs on the current code and
writes what that code did to NEW: the same inputs and a new picture. The contract is
`src/glitchygames/replay/rebaseline.py`'s docstring.

- A recording whose game or scene classes moved to another logical module is converted here and
  only here: the run matches them by qualified name alone, and NEW holds the current logical
  names (a plain replay refuses it, above).
- The replay does not stop at a divergence: it runs to OLD's last frame (or until the game
  ends), counting every frame that differs and naming every sprite that differs in them.
- NEW holds OLD's inputs as the replay served them: the event batches with their origins
  (code-posted events stay `internal`, so replaying NEW delivers nothing twice), `dt`,
  `input_changes`, re-applied control events, and each frame's `saves_opened`,
  `devices_opened` and `device_enumeration` copied from OLD. Its sprites and markers are the
  current code's. Its header is OLD's (seed, start time, options, saves, devices) with
  `rebaselined_from` naming OLD and this run's engine, pygame and Python versions.
- A cut-off (truncated) OLD gives NEW `source_truncated`: NEW ends as truncated too, so its
  replay exits `UNUSABLE_INPUT` (65) at the cut-off, `--audit` refuses it, and it cannot be a
  golden fixture (the plugin expects `SUCCESS`). Rebaseline a complete recording for those.
- A version-2 OLD (no input snapshots) gives an honest format-3 NEW: its polled input is the
  idle input the replay served, recorded as such, and its markers are compared when NEW is
  replayed (OLD's were not).
- Input OLD has that the run never received is not moved anywhere else (that would invent an
  input sequence OLD does not have); it is reported. That is the external events of batches a
  frame did not pump (the current code pumped fewer times than recorded), and OLD's frames
  after the game ended early.
- NEW is written to `NEW.partial` and moved into place only when the run ends normally; a run
  that crashes, is interrupted or fails its own exit (`sys.exit(1)`) writes nothing; the game's
  own successful exit (`sys.exit(0)`) ends it early as `quit_game()` does (NEW holds the frames
  that ran, exit `REBASELINE_INPUT_LOST`). If the move fails (say NEW is a directory),
  the finished `NEW.partial` is kept, its path logged and printed, and the run exits
  `CANNOT_WRITE_OUTPUT` (73). NEW is never OLD, and `NEW.partial` is never OLD either. A
  `NEW.partial` that cannot be written at all is refused before the replay starts, with one
  line and `CANNOT_WRITE_OUTPUT` (73), as is an unwritable `--record-trace` or
  `--replay-digest` file. NEW is an original, never a bookmarked copy (OLD's
  `bookmarked_copy_of` is dropped), so S on a replay of NEW never rewrites it.
- It prints one line to stdout and exits `SUCCESS` (0), however many frames differ:

```text
Rebaselined 9800 frames to NEW: 412 frames differ (first at 6120: sprite Ball#2 rect expected [412, 300, 16, 16], got [412, 301, 16, 16]); sprites affected: Ball#2, Ball#3
```

  or `Rebaselined 9800 frames to NEW: no frames differ`. Lost input (above) is added to the
  line and logged as a warning, e.g. `; 3 recorded input events not delivered (first at frame
  812); ended at frame 500 of 9800`. NEW is still written (it replays clean), but the run
  exits `REBASELINE_INPUT_LOST` (7) instead, so a script that replaces fixtures notices that
  NEW is not a faithful re-run of OLD's session.

It is refused (`OPTIONS_REFUSED`, 64) without `--replay-trace` or without `--headless` (a watched
replay holds frames and takes the viewer's keys, so it is refused rather than made headless
quietly), when NEW or `NEW.partial` is OLD's file, and with `--record-trace`, `--audit`,
`--replay-digest` (the audit's tools; a rebaseline is not audited) or `--replay-fps real` (FPS
events from this machine's frame times would become the baseline). An unusable OLD is
refused like any replay (`UNUSABLE_INPUT`, `MISSING_INPUT`).

NEW replays on the current code with no divergence when the rebaseline replayed all of OLD: a
truncated OLD gives a truncated NEW, whose replay matches up to its cut-off and exits
`UNUSABLE_INPUT` (65) like any truncated recording. Replacing a golden fixture with it stays a
deliberate, reviewed step: read the summary, check the change is the intended one, then move
NEW over the fixture yourself.

## Tools for any game

Every recording, replay and measurement tool belongs to the engine
(`src/glitchygames/replay/tools/`), so a game the engine has never seen can record, replay,
verify, rebaseline, measure, report on and graph its recordings with only the `glitchygames`
wheel installed. A game passes itself to the engine (`GameEngine(game=Game)`) and declares
nothing else: its package, package directory, console script and git revision all come from that
object (`identity.py`).

Each tool is reachable two ways, with the same name and the same options:

- **As a flag on the game.** `GameEngine.args` adds every tool to every game's command line
  (`uv run paddleslap --report session.jsonl.gz`). A tool that does not run the game, or runs it
  in a harness of its own, runs in place of the game, before the engine starts pygame: no window
  opens and no scene is built.
- **As the `glitchygames` command** (also `python -m glitchygames`), one subcommand per tool
  (`uv run glitchygames report session.jsonl.gz`). A subcommand whose tool runs the game starts
  the game as a child process with the tool's flag. Arguments after a bare `--` go to that game
  unchanged (`glitchygames record-trace paddleslap run.jsonl.gz -- --resolution 640x480`).
  `--project-root DIR` is, for the tools that read the project's settings (`verify`, `measure`,
  `unmeasured`, `clear-published`, `performance-pages`), the project they work on (default: the
  nearest directory at or above the current one whose `pyproject.toml` has
  `[tool.glitchygames]`, else the nearest with a `pyproject.toml`, else the current directory);
  for `record-trace`, `replay-trace`, `record-golden-trace` and `record-session`, the directory
  the game runs in (default: the current directory); `report` reads only its recording.

Both front ends are generated from one table, `TOOLS` in
`src/glitchygames/replay/tools/registry.py`, which is the reference for every flag, option,
default and help text (`glitchygames --help` lists each tool with its options;
`glitchygames TOOL --help` describes them). `tests/replay/tools/test_registry.py` walks the table
and fails if a tool or option differs between the front ends, and
`tests/replay/tools/test_an_unseen_game.py` runs every tool, both ways, on a stand-in game in its
own git repository.

| Tool | Runs the game? | On the game | As the command |
|---|---|---|---|
| `record-trace` | yes | `--record-trace PATH [--random-seed N] [--headless]` | `glitchygames record-trace GAME PATH` with the same options |
| `replay-trace` | yes | `--replay-trace PATH` with `--headless`, `--replay-fps`, `--replay-pause-at-frame N`, `--audit`, `--rebaseline NEW`, `--compare-processing`, `--max-processing-slowdown PERCENT`, `--replay-digest PATH`, `--random-seed N`, `--compare-trace OLD`, `--compare-alpha PERCENT` | `glitchygames replay-trace PATH [the same options] [--game GAME]` (the game comes from the recording's header) |
| `record-golden-trace` | in its harness | `--record-golden-trace PATH --input-script MODULE:NAME --frame-count N [--random-seed N] [--headless]` | `glitchygames record-golden-trace GAME PATH` with the same options |
| `record-session` | in its recorder | `--record-session PATH --input-script MODULE:NAME --frame-count N [--controls-tail MODULE:NAME] [--polled-input] [--input-only-placements] [--random-seed N] [--headless]` | `glitchygames record-session GAME PATH` with the same options |
| `verify` | in children | `--verify [PATH ...] [--only TEXT]` (default: the game's own recordings) | `glitchygames verify [PATH ...] [--only TEXT] [--game GAME ...]` (default: `[tool.glitchygames] games`) |
| `measure` | in children | `--measure [PATH ...] [--force] [--allow-dirty \| --skip-dirty] [--only TEXT] [--code-tree TREE] [--rows-directory DIRECTORY] [--pending PATH]` | `glitchygames measure [PATH ...]` with the same options `[--game GAME ...]` |
| `unmeasured` | no | `--unmeasured [--code-tree TREE] [--rows-directory DIRECTORY] [--pending PATH]` | `glitchygames unmeasured` with the same options `[--game GAME ...]` |
| `clear-published` | no | `--clear-published [--pending PATH]` | `glitchygames clear-published [--pending PATH]` |
| `report` | no | `--report PATH [--threshold PERCENT] [--minimum-ms MS] [--spans N]` | `glitchygames report PATH` with the same options |
| `performance-pages` | no | `--performance-pages DIRECTORY [--published]` | `glitchygames performance-pages DIRECTORY [--published]` |

- An option several tools list is one flag on the game: `--random-seed` (every tool that runs
  the game) and `--headless` (the four that record or replay). `--random-seed` is never needed:
  a recording rolls a seed (kept in it) and a replay uses the recording's. `verify` and
  `measure` refuse one (exit 64): they always compare, and measure each recording under its own
  seed.
- **Rebaseline and audit are options of `replay-trace`** (`--rebaseline NEW`, `--audit`), since
  they take the same recording and find the game the same way; so is the onion skin
  (`--compare-trace OLD`, above). `--replay-frame-stream PORT:TOKEN` is a hidden option the
  onion skin gives OLD's child; it is in neither front end's help.
- **One tool at a time:** a game given two tool flags is refused (exit 64), and so is a tool
  missing a required option (`--input-script`, `--frame-count`).
- **Reserved names.** Every tool's flag and option is added to every game's parser, so a game
  must not define an argument of the same name (`--threshold`, `--spans`, `--only`, `--force`,
  ...). A game that does is refused on every run, before anything starts (exit 64), with a
  message naming the flag and saying the engine reserves it. Our games are checked by a test;
  the full list is `glitchygames --help`.

### `GAME`

The command's `GAME` (and `--game`) takes three forms, read in this order; the command says
which one it used (`glitchygames replay-trace: running paddleslap (an installed console
script)`):

| `GAME` looks like | Meaning | The child it runs |
|---|---|---|
| contains `/` or ends in `.py` | a script path | `python <path> --<tool> ...` |
| contains `:` | an entry point `MODULE:CALLABLE` | `python -c` calling it, with the flags in `sys.argv` |
| a plain name | an installed console script, else an importable module | the console script's entry point, else `python -m <module>` |

A plain name matching nothing is refused with all three forms named. Every form ends in the
game's own `GameEngine(game=Game)`, which adds the flags, so the game never knows how it was
started. `replay-trace` takes the game from the recording's header and asks for `--game` when
that game's module no longer imports (a script that moved).

### A game's own recordings

`--verify` and `--measure` with no paths take the game's own recordings: the goldens that match
`[tool.glitchygames] golden-globs` and that the game's console script replays, plus its bundled
demos (`<package>/demos/*.jsonl.gz`; `recordings.py`). A golden in
`fixtures/replays/<console-script>/` is that script's; one directly in a project's
`tests/fixtures/replays/` is the project's own distribution's (`[project] name` in its
`pyproject.toml`, whatever its checkout's directory is called; a directory with no
`pyproject.toml` is read as named after its distribution). The command with no paths runs
`GAME --verify` (or `--measure`) for each `--game`, else for each of `[tool.glitchygames]
games`; with paths, each recording is replayed by the game its header names (or by the one
`--game`). With the games from the settings, a golden or demo that none of them replays fails
both tools, on a line naming it and why (exit 70): none is skipped without a word.

- `verify` replays each recording headless in a child process, prints `PASS <name>: <result>`
  or `FAIL <name>: <exit code>: <why>` per recording and `verify: N of M recordings passed`, and
  exits 0 only when every one matched (or none was found, which it says), 1 when the only
  failures diverged, else the first other failure's code.
- `measure` rebaselines each recording headless in a child into the run ledger (see
  [Replay Performance](../quality/performance.md)), skipping what this machine already measured
  for the game's commit. A row's commit is the game's own (its package directory's checkout),
  not the engine's. A game with uncommitted changes, or no known commit, is refused (exit 64)
  unless `--allow-dirty` (a trial row, never published) or `--skip-dirty` (nothing measured,
  exit 0). `unmeasured` lists what `measure` would measure, without running a game.

### Input scripts

`record-golden-trace` and `record-session` drive the game with an input script:
`--input-script MODULE:NAME` names a callable taking no arguments that returns an `InputScript`
(`glitchygames.replay.tools.golden_traces`: `press`/`release` per frame, and placements), its
module looked for in the current directory first. `--controls-tail MODULE:NAME` (record-session)
names the keys played after the script's frames, ending with the game's own quit. A golden
trace runs the game's scene in a headless harness at 1/60 second per frame and samples every
sprite each frame; a session runs the game for real, at its own pace, with `--record-trace`.
Our five games' scripts and controls tails are test data in `scripts/golden_inputs.py`
(`--input-script scripts.golden_inputs:paddleslap_script`, run from the repository root);
`scripts/record_golden_traces.py` and `scripts/record_scripted_session.py` keep only our
games' tables and call the engine.

### Project settings (`[tool.glitchygames]`)

A project's settings for the tools live in `[tool.glitchygames]` in its `pyproject.toml`
(`src/glitchygames/replay/tools/settings.py`). Every key has a default that fits a standard
layout, so a project without the table (a player's own local runs) works as it is. Keys are
kebab-case, an unknown key is refused by name, and every path is relative to the project root.
A path that does not exist yet (no ledger directory before the first measurement) is created
by the tool that writes it, or reported; it is never a traceback.

| Key | Default | Ours (the root `pyproject.toml`) |
|---|---|---|
| `games` | the project's `[project.scripts]` | the nine members' console scripts |
| `golden-globs` | `["tests/fixtures/replays/**/*.jsonl.gz"]` | `["src/*/*/tests/fixtures/replays/golden*.jsonl.gz"]` |
| `ledger-directory` | `"replay-ledger"` | `"quality/replay-ledger"` |
| `pending-ledger` | `".glitchygames/pending-ledger.jsonl"` | `"test-results/replay-metrics/pending.jsonl"` |
| `published-ledger` | none (nothing published) | `"origin/gh-pages:quality/metrics/replay-ledger.jsonl"` (`REF:PATH`) |
| `landed-ref` | `"origin/main"` | `"origin/main"` |
| `measured-paths` | `["src", "tests/fixtures/replays", "pyproject.toml"]` | the same, and `uv.lock` |
| `unmeasured-paths` | `[]` | the members' `tests/`, but for their `tests/fixtures/replays/` |
| `recording-renames` | `{}` | each moved recording, old path to new (one hop: refused if a new path is itself an old one; each new path must exist, `tests/test_our_stored_paths.py`) |
| `game-timeout-seconds` | `3600` (an hour) | the default |

`game-timeout-seconds` bounds each game that `glitchygames verify` and `glitchygames measure`
start (`GAME --verify`, `GAME --measure`, one per game): a game still running after it is
stopped (asked first, so it can stop its own replays, then killed), reaped, and failed with a
line naming the game and the timeout (exit 70). Each recording's replay inside it has its own
timeout too. It guards against a console script that is no game (an editor or a server among
`[project.scripts]`, which `games` defaults to) hanging the run; it has no flag, since only the
command starts a game per child (`--game` names the games instead, or set `games`).

The project's local directory, `.glitchygames/`, holds what the tools write and nobody commits;
it gets a `.gitignore` of `*` when it is made.

**Stored paths are relative to the project root.** The project root is the anchor of every
path above and of every path the tools write into a file: a recording header's path options
(`--record-trace`, `--rebaseline`, ...), a rebaselined recording's `rebaselined_from` (in its
header and its newest run, which a ledger row copies) and a ledger row's recording. It is the
nearest project above the current directory (`find_project_root`), or `--project-root` where a
subcommand takes it; the tools start each game in it. A path inside the project is stored
relative to it, POSIX-style. A path inside another checkout of the same project (a clone or a
worktree: the nearest directory above the path whose `pyproject.toml` has the same
`[project] name`) is stored relative to that checkout's root. Any other path (another project,
no project) is stored as its file name only (`stored_path`), so no user name, home or scratch
directory is ever written.
`tests/test_our_stored_paths.py` checks every committed recording header and ledger row.

### The golden-replay pytest plugin

The pytest plugin `glitchygames.testing.replays` registers itself through the engine's `pytest11`
entry point (named after its module), so every pytest run of a project with glitchygames
installed collects that project's recordings (Golden replays, above) with no conftest line.

- A project that is no game gets no item and no output from it, unless it has a
  `fixtures/replays/<directory>/*.jsonl.gz`: a directory there that is not a console script is a
  collection error. `pytest -p no:glitchygames.testing.replays` turns the plugin off.
- Under a wheel install, pytest rewrites the asserts of the whole `glitchygames` package (it
  rewrites every module of a distribution that has a `pytest11` entry point): harmless, but it
  writes `*-pytest-*.pyc` files into `site-packages`.
- The engine wheel also ships `glitchygames.testing.frame_comparison` (comparing the frames
  test runs presented on different SDL drivers, with `glitchygames.testing.frame_fingerprints`,
  which records them); `scripts/compare_driver_frames.py` and `scripts/driver_frame_matrix.py`
  are its command lines.

## In-game playback

A running game can play a recording to a rebuilt scene and then go on: attract-mode demos,
instant replays and ghosts. Demos and instant replays run in a **playback scope**, not a new
engine run (`src/glitchygames/replay/playback.py`'s docstring is the contract): the scene is
rebuilt from its start (see Scene starts above) on scoped doors that serve the recording, the
live scene is stashed untouched, saves are a sandbox, the random streams, clocks and FPS timer
are put back afterwards, and the live game's own posts and the player's releases, device and
window events are held and handed back when the scope ends. A `--record-trace` session that
plays a scope records it, and replays it exactly. An error inside the scope ends the scope
(logged) and the live game goes on. `scene_manager.last_playback_outcome` says how the last
scope ended (its kind, reason and frames played).

What belongs to the scope ends with it: supervisors and control event handlers its scene adds
(in `setup()`, `cleanup()` or an event handler; a live supervisor's additions stay), and the
playback scene's own events still queued when it ends (posted in `update()` or an event handler
after its last pump: the live game never receives them, so a goal posted there cannot start a
second instant replay). What the live game's own supervisors and handlers post while it plays
stays the live game's: a supervisor that calls `end_playback()` and then posts an event has it
delivered to the live game after the scope. Their `post_input_event` posts of SDL types are the
exception: those stand in for the player, so they reach the scope's exit check as the player's
presses do (a scripted key ends a demo) and their releases are held with the player's. Their
`post_input_event` posts of other types (a game event) are held and delivered to the live game
after the scope, and a replay of the session without the supervisor delivers them at the same
frame. A playback never rumbles the player's controllers,
and the live scene's synth voices (and those of the game behind a pause screen the instant
replay began from) pause behind it and play on after. Inside a scope, a replay of the session still
applies the session's breakpoints (a bookmark on a frame a demo played pauses there); the
played recording's own breakpoints are never applied again. A `--record-trace` recording of a
session that played a scope replays exactly, but cannot itself be played in-game from a frame
inside or after that scope (only an instant-replay journal records what a scene's playback
requests got and how it resumed).

### Demos

```python
scene_manager.play_recording(path=DEMO_PATH, then=self)   # any key or button returns to `then`
```

A demo plays at the game's speed from the start of the next frame and ends at the recording's
end, at the player's first press (consumed: it never reaches `then`), at the recording's own
quit, or at a divergence (logged at WARNING as `demo diverged: ...`, then back to `then`). A
recording that cannot be played (missing, unreadable, another game's, no scene start) is logged
at WARNING and nothing starts. Record a demo with
`scripts/record_scripted_session.py --script-only --output PATH` (it runs `--record-trace`, so
its first frame holds the scene start; `--script-only` leaves out the controls tail, whose quit
would end the demo).

Bundled demos are recordings shipped in a game's package as package data,
`<package>/demos/<name>.jsonl.gz`: PaddleSlap's `paddleslap/demos/rally.jsonl.gz`, which its
game-over screen plays after 10 seconds without a press. The engine finds them, for any tool or
installed game, with `glitchygames.bundled_demos.bundled_demos()`: each `BundledDemo` (a frozen
record) holds the game's console script (None when no installed console script is in the
package), the demo's installed path and its install name (`paddleslap/demos/rally.jsonl.gz`,
the same under any install). It searches the installed packages its caller names (required,
with no default: a game's own package for `--verify`, `MEMBER_LAYERS`' for our tests;
`importlib.util.find_spec`, importing no game), leaves out bookmarked copies and sorts them by
path. `tests/replay/test_bundled_demos.py` replays every one headless (through
`glitchygames.testing.replays.bundled_demo_paths`, which refuses a demo nothing replays), so a
change that makes a demo diverge fails in CI before it ships; `glitchygames measure` measures
the same demos (each game's `--measure` takes its own package's, as `--verify` does).

### Instant replay

```python
class Match(Scene):
    INSTANT_REPLAY_SECONDS = 5.0                       # opt in: show the last 5 seconds
    MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS = 60.0     # the default budget

    def on_goal(self):
        self.scene_manager.instant_replay()            # False (logged) when it cannot play
```

A scene class that sets `INSTANT_REPLAY_SECONDS` keeps, in memory, the recording of every frame
since its first logic frame (`src/glitchygames/instant_replay.py`), sprites included: about 0.5 MB
per minute for one sprite moving every frame, about 1.5 MB per minute for PaddleSlap. The
journal ends when another scene is presented, and once it holds more frame time than
`MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS` (paused frames count: all are re-simulated), after
which `instant_replay()` returns `False`; longer scenes would need state snapshots.

`instant_replay()` rebuilds the scene from its start, runs the frames before the last
`INSTANT_REPLAY_SECONDS` of frame time unseen, unpaced and silent, shows the rest at the game's
pace with their sounds, then the live scene goes on exactly where it was. The player's presses
do not end it. To let the player skip it, read the player's input in a supervisor and end the
playback there (`end_playback()` is honoured only from a supervisor or between frames):

```python
class SkipReplayOnPress:
    def on_frame(self, *, frame_number, scene):
        player_input = scene_manager.playback_player_input   # None outside a playback
        if player_input is not None and player_input.key_pressed(pygame.K_SPACE):
            scene_manager.end_playback()
```

Instant replays can follow one another (a replay after every goal): a playback suspends the
journal, which resumes afterwards, and a request the scene's own code makes while its journal
plays back gets the answer it got live.

### Ghosts

A ghost is a recorded sprite's path and looks drawn beside live play, a time-trial ghost
(`src/glitchygames/replay/ghosts.py`'s docstring is the contract). Ghosts are appearance, not
play: they have no hitbox and change nothing the game does.

```python
from glitchygames.replay.ghosts import (
    GhostRecorder, GhostSprite, GhostTrack, images_from_animated_sprite,
)

# Recording: from the scene's start until the lap ends
recorder = GhostRecorder(sprite=self.player, scene=self)
...
track = recorder.finish()
saves.save('best_lap', track.to_json())

# Playing it in the next run of the scene (in setup())
track = GhostTrack.from_json(saves.load('best_lap'))
ghost = GhostSprite(track=track, image_for=images_from_animated_sprite(self.player))
ghost.scene = self                     # the ghost follows this scene's game_time
self.all_sprites.add(ghost)            # never to a collision group
```

- `GhostRecorder` is a supervisor: once per frame, after the frame's logic, it samples the
  scene's `game_time`, the sprite's `world_x`/`world_y`, its appearance (animation, frame,
  horizontal flip and draw offset of an `AnimatedSprite`; pass `appearance=` for anything else)
  and whether the game shows it (`not hidden`). It samples only live frames of the scene it
  was given, and only when that scene's game time advanced: not behind the pause screen, not
  in a demo or instant replay. It reads game state only, so recording a ghost changes nothing.
- Supervisors added while a demo or instant replay plays belong to that playback and are
  removed when it ends, so a recorder the rebuilt scene's `setup()` makes never outlives it.
- Samples are keyed by `Scene.game_time`, which stops while the scene is paused. The ghost
  shows the last sample not after the current `game_time`, so it lines up with the live run
  from the scene's start at any frame rate, and waits while the game is paused.
- `GhostSprite` is a world-space sprite: the engine positions and culls it. Its position is
  read from the track whenever the engine reads it, so it is drawn in this frame's place, not
  last frame's. Its image is `image_for(sample)` drawn translucent (`alpha`, default 96).
  Hide it with `ghost.hidden = True` (the game's own flag, as for every world sprite). With
  nothing to show (before the track's first sample, or a sample the game had hidden) its image
  is empty, so the engine culls it.
- A ghost in `all_sprites` is in a recording's sprite trace like any sprite. Store tracks in
  saves: a replay serves the saves the recording saw, so a session with a ghost replays
  exactly.
