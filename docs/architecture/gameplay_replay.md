# Gameplay Recording and Replay

GlitchyGames can record a play session and replay it exactly through the real engine. Same
engine version and same recording give bit-identical sprite traces: every frame's sprite
`rect` and `visible` match the recording. Audio is played during a replay but is not compared.

This page covers the replay core: recording, exact replay, watching a replay (with step back
and bookmarks), headless runs, the determinism audit, golden replays and rebaselining them,
and the rules game code follows so its sessions replay. In-game playback (demos, instant
replay, ghosts) is planned. See
`plans/2026-10-19-gameplay-replay.md` for the design and `plans/future-work.md` for what is
pending.

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
```

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

- `glitchygames/sources.py`: the `EngineSources` protocol and the registry (`active_sources()`,
  `install_sources(sources=...)`, `reset_sources()`) and the frame clock. It is a leaf module
  with no engine imports, which avoids an import cycle between the engine and the scenes.
  `install_sources` is allowed only before the first frame, so a run never mixes live and
  recorded input.
- `glitchygames/live_sources.py`: `LiveSources`.
- `glitchygames/recording.py`: `RecordingSources`, which wraps the live doors under
  `--record-trace` and records what passes through them.
- `glitchygames/replay/driver.py`: `ReplaySources`, the comparison and the divergence report.

`tests/test_engine_doors.py` scans the package and fails if anything outside the doors reads
the raw clock, polls pygame's keyboard or mouse, reads or posts pygame events directly, or
enumerates or opens joysticks and controllers. Its `ALLOWED_BYPASSES` lists the few exceptions,
each with its reason.

## Rules for game code

### Time

Read time from `glitchygames/clock.py` or `Scene.game_time`, never from `time`, `datetime` or
`pygame.time`:

| Use | For |
|---|---|
| `Scene.game_time` | gameplay timers and cooldowns; stops while the scene is paused |
| `frame_clock_seconds()`, `frame_clock_milliseconds()` | blinks, animation, "how long since" in UI; never pauses |
| `wall_clock_time()`, `wall_clock_epoch_seconds()` | timestamps (save metadata, undo history, logs) |
| `elapsed_seconds()` | throttles, debounces, repeat intervals, timeouts (subtract two readings) |
| `measured_seconds()` | real durations for logs and metrics only |

`elapsed_seconds()` is the frame clock, live and in a replay, so a throttle near its threshold
decides the same way both times; such timers advance once per frame. `measured_seconds()` is real
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
snapshot.key_pressed(pygame.K_LEFT)
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

### Devices

Enumerate and open joysticks and controllers only through `active_sources().devices()`
(`glitchygames/input/devices.py`): `joystick_count()`, `controller_count()`,
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
are never touched. Both are `SaveManager`s, which hold every rule of the save format.

### Events and randomness

- Post events with `glitchygames.recording.post_event`, not `pygame.event.post`, so a recording
  can mark them internal. Replay delivers internal events from the code that posts them again;
  an SDL-type event posted directly would be delivered twice.
- Draw random numbers from the seeded named streams in `glitchygames/randomness.py`
  (`random_stream('name')`, `numpy_stream('name')`), never from the global `random` functions,
  `secrets` or an unseeded numpy generator.

## The supervisor hook and control events

A supervisor (`glitchygames/supervision.py`) is called once per frame at a fixed place: after
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
`saves_opened` and `device_enumeration` (each written only when not empty). The header holds the
game, scene and versions, every option, the start time, the random seed, and the saves and
devices the run took in before recording started. The full format is described in the
`glitchygames/recording.py` module docstring.

## Replay (`--replay-trace PATH`)

At startup the replay reads the recording, applies its recorded options and seeds the random
streams with its seed. It refuses, logging the reason and exiting with one of the
[exit codes](#exit-codes), when:

- the recording is of another game, cannot be read (not gzip, no permission, a directory) or
  has an unsupported format version: `UNUSABLE_INPUT` (65);
- the file does not exist: `MISSING_INPUT` (66);
- `--record-trace` is given too: `OPTIONS_REFUSED` (64). Recording over a replay is what
  [`--rebaseline`](#rebaselining-rebaseline-new) does, and only it.

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
[exit codes](#exit-codes)).

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
(`glitchygames/replay/viewer.py`). The outer loop, the replay viewer, owns the window: it ticks
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
(`glitchygames/ui/message_screen.py`) with its own message and look, as an overlay on the
presented frame: switching to a real pause scene would change the recorded scene sequence.
Nothing runs while the replay is held: no frame, no frame clock, no recorded input. The viewer's
keys go to the replay's controls (`glitchygames/replay/controls.py`), never to the game. Each
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
restart the replay in a fresh process (`glitchygames/replay/rebuild.py`) with the same command
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
(`bookmarks already saved to ...`).

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
warning.

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
the code it exits with as `Exiting with OPTIONS_REFUSED (64)`.

| Code | `ExitCode` member | Meaning |
|---|---|---|
| 0 | `SUCCESS` | Success; the replay matched; the audit is deterministic; the rebaseline was written |
| 1 | `REPLAY_DIVERGED` | A replay's frames differ from the recording |
| 2 | `ARGUMENT_PARSER_ERROR` | A usage error from argparse; the engine never exits with it itself |
| 3 | `AUDIT_NONDETERMINISTIC` | `--audit`'s two runs differ from each other or from the recording |
| 4 | `GENERATION_REJECTED` | The API server rejected the sprite client's generation request |
| 5 | `EXTRACTION_REJECTED` | The API server rejected the sprite client's frame extraction |
| 6 | `AUDIO_DROPOUT_RISK` | `scripts/audio_glitch_probe.py` found a risk of audio dropouts |
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

## Golden replays

`tests/fixtures/replays/<game>/golden.jsonl.gz` holds a recorded session of each example game
(PaddleSlap, Clockwork Keep and both Brave Adventurer editions).
`scripts/record_scripted_session.py` recorded them through the real engine loop, with a
supervisor posting each game's golden input script. Each recording is a test item of its own:
the pytest plugin `glitchygames/testing/replays.py` (loaded by the root `conftest.py`) collects
every `.../fixtures/replays/<console-script>/<name>.jsonl.gz` as `<console-script>/<name>`,
replays it headless in a child process through the console script's entry point
(`--replay-trace PATH --headless`) and fails, with the exit code and the child's output (the
divergence report), unless it exits `ExitCode.SUCCESS`. A directory that is not a console script
is a collection error. Another project's games can use the plugin the same way
(`pytest_plugins = ['glitchygames.testing.replays']`). Re-record a fixture only deliberately,
after finding out why it stopped replaying; the commands are in the script's docstring. After
an intentional change, rebaseline it instead (below), so it keeps its recorded inputs.

## Rebaselining (`--rebaseline NEW`)

`--replay-trace OLD --rebaseline NEW --headless` replays OLD's inputs on the current code and
writes what that code did to NEW: the same inputs and a new picture. The contract is
`glitchygames/replay/rebaseline.py`'s docstring.

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
  that crashes or is interrupted writes nothing. If the move fails (say NEW is a directory),
  the finished `NEW.partial` is kept, its path logged and printed, and the run exits
  `CANNOT_WRITE_OUTPUT` (73). NEW is never OLD, and `NEW.partial` is never OLD either.
- It prints one line to stdout and exits `SUCCESS` (0):

```text
Rebaselined 9800 frames to NEW: 412 frames differ (first at 6120: sprite Ball#2 rect expected [412, 300, 16, 16], got [412, 301, 16, 16]); sprites affected: Ball#2, Ball#3
```

  or `Rebaselined 9800 frames to NEW: no frames differ`. Lost input (above) is added to the
  line and logged as a warning, e.g. `; 3 recorded input events not delivered (first at frame
  812); ended at frame 500 of 9800`. The run still exits `SUCCESS`: NEW is written, and the
  summary is what you review before using it.

It is refused (`OPTIONS_REFUSED`, 64) without `--replay-trace` or without `--headless` (a watched
replay holds frames and takes the viewer's keys, so it is refused rather than made headless
quietly), when NEW or `NEW.partial` is OLD's file, and with `--record-trace`, `--audit`,
`--replay-digest` (the audit's tools; a rebaseline is not audited) or `--replay-fps real` (FPS
events from this machine's frame times would become the baseline). An unusable OLD is
refused like any replay (`UNUSABLE_INPUT`, `MISSING_INPUT`).

NEW replays on the current code with no divergence. Replacing a golden fixture with it stays a
deliberate, reviewed step: read the summary, check the change is the intended one, then move
NEW over the fixture yourself.
