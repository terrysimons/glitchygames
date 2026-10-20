# Gameplay Recording and Replay

GlitchyGames can record a play session and replay it exactly through the real engine. Same
engine version and same recording give bit-identical sprite traces: every frame's sprite
`rect` and `visible` match the recording. Audio is played during a replay but is not compared.

This page covers the replay core: recording, exact replay, the determinism audit, and the rules
game code follows so its sessions replay. Watched-replay controls, headless replay, rebaselining
and in-game playback (demos, instant replay, ghosts) are planned. See
`plans/2026-10-19-gameplay-replay.md` for the design and `plans/future-work.md` for what is
pending.

## Quick start

```bash
# Record a session
uv run paddleslap --record-trace session.jsonl.gz

# Replay it exactly, comparing every frame with the recording
uv run paddleslap --replay-trace session.jsonl.gz

# Check that it replays the same way twice, in fresh processes with different hash seeds
uv run paddleslap --replay-trace session.jsonl.gz --audit
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
streams with its seed. It refuses, logging the reason and exiting with status 2, when:

- the recording is of another game;
- the file is missing or unreadable, or its format version is not supported;
- `--record-trace` is given too (recording over a replay is not supported yet).

A recording made by a different engine version replays with one warning. A version-2 recording
replays with one warning too: it has no input snapshots, so polled input reads as idle.

Each frame, the replay serves the recorded events, `dt`, input, devices, saves and clocks. Then
it compares the frame with the recording: the active scene's class, then each recorded sprite in
draw order (present, `rect`, `visible`), along with the frame's internal events, control events
and pump count. The first difference stops the replay and is logged on one line:

```text
Replay diverged: frame 6120: sprite Ball#2 rect expected [412, 300, 16, 16], got [412, 301, 16, 16]
```

The replay also stops at the last recorded frame (`Replay matched N frames`) or when the window
is closed.

While a replay runs, real keyboard, mouse, touch, joystick, controller, device and window events
are blocked at SDL, so they never reach the game. The block is applied again on every pump
(event managers created mid-run allow their types again). Each type's earlier blocked state is
restored exactly when the replay ends, normally or after an error. QUIT, the window's close event
and custom event types are never blocked, so closing the window still ends the replay. Blocking
also refuses posts of those types: game code that fakes input by posting `KEYDOWN` loses the
post, which shows up as a missing internal event divergence. Recorded window references in
events are served as `None`, as live events of the display window carry.

### `--replay-fps {recorded,real}`

With `recorded` (the default), FPS events, the performance statistics and the debug overlay's
performance panel use the recorded frame times, and FPS events are compared exactly. With
`real`, they use this machine's measured frame times and FPS events are not compared; sprites
that draw the FPS value may then diverge. Logic always receives the recorded `dt`.

## The determinism audit (`--audit`)

`--replay-trace PATH --audit` does not replay in-process. It runs the same command again as two
headless child processes, with `PYTHONHASHSEED` set to 1 and 2, and each child writes a SHA-256
digest of every replayed frame. The audit passes (exit 0) when both runs match the recording and
their digests match each other; otherwise it reports the first differing frame and exits 1.
Fresh processes and different hash seeds make set and dict ordering bugs show up.

The audit compares only what the replay samples: the scene class and each sprite's `rect`,
`visible` and draw order. Pixels, audio and game state that never moves, hides or reorders a
sprite are not compared. It is refused (exit 2) with `--replay-fps real` and under `python -E`
or `-I`, which would keep `PYTHONHASHSEED` from reaching the children.

## Golden replays

`tests/fixtures/replays/<game>/golden.jsonl.gz` holds a recorded session of each example game
(PaddleSlap, Clockwork Keep and both Brave Adventurer editions).
`scripts/record_scripted_session.py` recorded them through the real engine loop, with a
supervisor posting each game's golden input script. `tests/replay/test_golden_replays.py`
replays each one with `--replay-trace` and requires an exact match. Re-record a fixture only
deliberately, after finding out why it stopped replaying; the commands are in the script's
docstring.
