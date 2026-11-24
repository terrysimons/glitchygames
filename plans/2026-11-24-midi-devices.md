# MIDI Devices: Input and Output Through the Devices Door

Design, 2026-11-24. Implementation plan: `plans/2026-11-24-midi-devices-implementation.md`.
Roadmap: `plans/future-work.md` ("Output record ...", which names MIDI out as a sink and MIDI in as
device input through the input door).

## Intent

MIDI is one more game tool many games will want. It's a mostly mechanical wiring of pygame-ce's
`pygame.midi` into the engine's existing event infrastructure, done the way every other event
subsystem is wired (the owner, 2026-11-24: "wired up the same way other event subsystems are";
"we probably need to wire up the event proxy and all that"), so the engine is event-driven in a
more complete way.

Today only dispatch exists: since #300 (`b4a83774`) a `MIDIIN` or `MIDIOUT` already in the queue
reaches `MidiEventManager` and the active scene's `on_midi_*_event`. Nothing opens a MIDI port,
reads one, or writes one, and MIDI is not in the doors, so it could not be recorded or replayed.

## Goals

- MIDI ports are enumerated and opened only through the devices door
  (`active_sources().devices()`, `src/glitchygames/input/devices.py`), as joysticks and
  controllers are: live play opens real `pygame.midi.Input` / `Output` ports and remembers each
  enumeration answer and a descriptor of each opened port for the recorder; a replay answers from
  the recording with stand-ins and never touches MIDI hardware.
- MIDI input becomes `MIDIIN` events in the engine's event batch, once per frame, so it is
  recorded and replayed with no new recording machinery.
- `MidiEventManager` has one proxy per opened port, like `JoystickEventManager`: the proxy
  forwards the port's events to the game and lists the port among its proxies, so a game calls the
  port's own methods (`get_device_info()`, `write_short()`, `note_on()`, ...) through it.
- MIDI output goes through the opened port; a replay's output port accepts writes and drops them,
  as a replay controller drops rumble.
- Where pygame has no PortMidi (`events/midi.py`'s `MIDI_MODULE is None`: the browser builds),
  MIDI answers "no ports", and that answer is recorded like any other.

## Non-goals

- Web MIDI in the browser builds.
- Hot-plugging: PortMidi lists ports at `pygame.midi.init()` and pygame posts no MIDI device
  events, so the ports are those present at start.
- A note or instrument layer (mapping MIDI notes to the sound engine's live instruments). Games
  can build it on the events; it is not part of this wiring.
- Recording MIDI output in the output record: the output record does not exist yet
  (`plans/future-work.md`); when it does, MIDI out becomes one of its sinks.

## Anti-goals

- Any read of `pygame.midi` outside the devices door. `tests/test_engine_doors.py` does not watch
  `pygame.midi` today (it is not in `WATCHED_DOOR_MODULES`, and `events/midi.py` imports it through
  `importlib`); this work extends the guard so it fails on one.
- A replay that differs from its recording because a MIDI device is or isn't plugged in.
- A game that must special-case "no PortMidi": no ports is an ordinary answer.

## Constraints

- **The doors rule** (CLAUDE.md, "Gameplay Recording and Replay"): devices are enumerated and
  opened only through `active_sources().devices()`; polled input is never read from a device
  directly.
- **PortMidi opens a port once per process.** A second `Input(device_id)` on an open port fails.
  The door must hand back the port it already opened, as `joystick_for_instance` does for
  joysticks, which matters when several games share a process (the Arcade).
- **Timestamps.** `pygame.midi.Input.read()` gives each message a PortMidi timestamp
  (`pygame.midi.time()`, milliseconds). It travels inside the recorded event (`MidiEvent.timestamp`),
  so a replay serves the recorded value and never reads PortMidi's clock. The engine's own
  timing never uses it.
- **Field names.** `pygame.midi.midis2events` builds events with `status`, `data1`-`data3`,
  `timestamp` and `vice_id` (pygame's spelling of the device id); `MidiEvent`
  (`events/base.py`) already matches.
- `DeviceDescriptor.from_json` is `cls(**record)`: anything a MIDI port adds must be optional with
  a default, or a separate type, so recordings made before this change still load.
- New process- or module-level state is a context slot or an audited row
  (`tests/test_process_state_guard.py`, `docs/architecture/engine_context.md`).
- Python 3.14 syntax only (Pyodide); pydantic for new data classes unless a hot path is measured.

## Approaches considered

1. **A device family behind the doors (chosen).** MIDI ports join the device registry beside
   joysticks and controllers (live, replay, stand-in); input is read once per frame in the live
   pump and returned in the batch; `MidiEventManager` gets per-port proxies. The most code, about
   the size of the joystick path, and the only approach that keeps replays exact and passes the
   doors guard.
2. **The manager reads `pygame.midi` itself and posts events.** Much less code, but it goes around
   the devices door: the doors guard fails it, and a replay still opens real hardware to list ports.
3. **Each game opens `pygame.midi`.** Breaks the doors rule outright and repeats the code in every
   game.

The owner chose 1 (2026-11-24).

## The design

### The devices door (`src/glitchygames/input/devices.py`)

- New kinds `MIDI_INPUT_KIND` and `MIDI_OUTPUT_KIND`, and enumeration calls recorded as
  `EnumerationAnswer`s: the port count, each port's info (`pygame.midi.get_device_info`: interface,
  name, is-input, is-output, opened), the default input and output ids, and the opens.
- `DeviceRegistry` gains `midi_port_count()`, `midi_port_info(port_id=...)`,
  `default_midi_input_id()`, `default_midi_output_id()`, `open_midi_input(port_id=...)`,
  `open_midi_output(port_id=...)`, and `midi_input_for_port` / `midi_output_for_port` to hand back
  a port already opened (the per-process constraint).
- `LiveDeviceRegistry` calls `pygame.midi.init()` once, opens real ports, remembers answers and a
  descriptor per opened port, and reads every opened input port when the pump asks it to
  (`read_midi_input()`, below).
- `ReplayDeviceRegistry` answers from the recording and opens stand-ins: `ReplayMidiInput` (reads
  nothing; its events come from the recording's batches) and `ReplayMidiOutput` (accepts every
  write and drops it).
- The stand-in registry (`src/glitchygames/input/stand_in_devices.py`) gets stand-in MIDI ports for
  tests, with messages a test queues.
- `DeviceDescriptor` gains what a MIDI port needs (its port id, name, interface, direction); the
  joystick fields don't apply to a port. Whether that is new optional fields or a second
  descriptor type is the builder's call, as long as recordings made before this change still load.
- No PortMidi: every call answers as a machine with no MIDI ports.
- **Port identity (my call):** MIDI ports are their own namespace, keyed by kind and PortMidi port
  id (inputs and outputs are numbered together by PortMidi, but kept apart by kind here), never
  mixed with SDL instance ids in the joystick maps. A replay matches ports by their recorded id:
  the events it serves carry recorded ids, and it never sees the replaying machine's ports.
- `import_midi_module` and `MIDI_MODULE` move from `events/midi.py` to the door
  (`input/devices.py`), which owns every `pygame.midi` call; the manager asks the door.

### Input into the event batch

- `LiveSources.pump_events()` returns SDL's events and then the door's `read_midi_input()`: for
  each opened input port, the `MIDIIN` events its pending messages make (`midis2events`, with the
  port id as `device_id`).
  `RecordingSources` already records the batch as returned; the replay driver and playback scopes
  already serve recorded batches. A recording therefore holds MIDI input as ordinary pumped
  events, and needs no format change for them.
- The read happens in the door, during the pump, never in a manager or a game. Only live play
  reads: `read_midi_input()` is `LiveDeviceRegistry`'s (and the stand-in registry's, for tests),
  called by `LiveSources.pump_events()`, so it is not on the `EngineSources` or `DeviceRegistry`
  protocol. `HostSources` and `RecordingSources` already pass the inner pump's batch through, and
  replays serve recorded batches. MIDI events follow SDL's in the batch.
- **`MIDIOUT` stays without a producer (my call):** pygame never builds one, and a write through an
  output port posts nothing. Recording what was sent belongs to the future output record.

### `MidiEventManager` (`src/glitchygames/events/midi.py`)

- Like `JoystickEventManager`, a bigger change than it looks (today the manager builds one proxy
  and has no open or adopt methods): `MidiEventProxy` becomes per port, opened through the door (or
  handed back by it), with `proxies = [game, port]`; the manager keeps them by port id and opens
  the connected ports at start (`open_connected_midi_ports`, which `GameEngine.enter_playback_devices`
  calls with the scope's door, as it does for joysticks).
- **Instant replay is in scope (the owner, 2026-11-24).** The instant-replay journal records the
  opened MIDI ports' descriptors beside the joysticks' (`RecordedDevices.scene_start_devices`), an
  instant replay adopts them as it adopts joysticks (replay stand-ins, so a write during the replay
  goes nowhere), and leaving the playback scope puts the live ports back
  (`_live_devices_behind_scope`), as for joysticks.
- **MIDI starts only when a port is named (the owner, 2026-11-24).** `--midi-input NAME` and
  `--midi-output NAME` (in `MidiEventManager.args`, repeatable; a game may give its own defaults)
  name the ports to open. With none named, PortMidi is never initialized, the door is asked
  nothing about MIDI, and no MIDI answers are recorded, so every game, golden and test that names
  no port runs and records exactly as before. A named port that isn't present is an ordinary
  answer (logged, recorded; the run goes on without it).
- The proxy no longer lists the raw `pygame.midi` module among its proxies: today a game could call
  `pygame.midi.Input(...)` through it and go around the door. Nothing in the repository uses that
  passthrough (checked 2026-11-24); enumeration is the door's (`midi_port_count()`, ...), offered
  through the manager.
- A scene without its own handler still gets `unhandled_event` (raises under
  `--no-unhandled-events`).

### Guards and docs

- `tests/test_engine_doors.py`: `pygame.midi` allowed only in the devices door.
- Each new slot or audited state row checked (`tests/test_engine_context.py`,
  `tests/test_process_state_guard.py`).
- `docs/architecture/event_system.md` (the MIDI section and the dispatch table, which #308 brings
  up to date), `docs/architecture/gameplay_replay.md` (devices), `CLAUDE.md`'s doors line if it
  names the device kinds.

## Tests, as behaviours

- A message on a stand-in input port arrives as one `MIDIIN` event with pygame's fields, in the
  frame it was queued, at the scene's `on_midi_in_event`.
- A recorded run with MIDI input replays it exactly, with no MIDI port present at replay.
- A replay never opens or reads a real MIDI port (the doors guard, and a test with
  `pygame.midi` made to raise).
- Opening a port that is already open hands back the same port, with no second open.
- A write through a replay output port is accepted and goes nowhere; live, it reaches the port.
- With no port named, PortMidi is never initialized and a run's recording has no MIDI answers.
- An instant replay of a scene with MIDI ports adopts replay stand-ins, and leaving it puts the
  live ports back; a write during it reaches no live port.
- With no PortMidi, the door answers zero ports and the manager opens none; a recording made that
  way replays the same answers.
- Recordings made before this change load and replay unchanged.
- Live, stand-in and replay answer the same enumeration calls the same way (as the joystick tests
  compare them).

## Left to the builder

- The descriptor's shape (above).
- The exact names of the new constants and calls, within the project's naming rules.

## Decisions record

- 2026-11-24, the owner: plan MIDI before building; wire it like the other event subsystems
  (devices door, per-device proxies); approach 1.
- 2026-11-24, the owner, after the builder check: MIDI starts only when a port is named; instant
  replay is in scope.
