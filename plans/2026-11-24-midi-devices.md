# MIDI Devices: Input and Output Through the Devices Door

Design, 2026-11-24. Status: built on `feature/midi-devices` (Tasks 1-6 of the implementation
plan), not yet merged; what is left is under "Not built". Implementation plan:
`plans/2026-11-24-midi-devices-implementation.md`.
Roadmap: `plans/future-work.md` ("Output record ...", which names MIDI out as a sink and MIDI in as
device input through the input door).

## Intent

MIDI is one more game tool many games will want. It's a mostly mechanical wiring of pygame-ce's
`pygame.midi` into the engine's existing event infrastructure, done the way every other event
subsystem is wired (the owner, 2026-11-24: "wired up the same way other event subsystems are";
"we probably need to wire up the event proxy and all that"), so the engine is event-driven in a
more complete way.

Before this work only dispatch existed: since #300 (`b4a83774`) a `MIDIIN` or `MIDIOUT` already in
the queue reaches `MidiEventManager` and the active scene's `on_midi_*_event`. Nothing opened a
MIDI port, read one, or wrote one, and MIDI was not in the doors, so it could not be recorded or
replayed.

## Goals

- MIDI ports are enumerated and opened only through the devices door
  (`active_sources().devices()`, `src/glitchygames/input/devices.py`), as joysticks and
  controllers are: live play opens real `pygame.midi.Input` / `Output` ports and remembers each
  enumeration answer and a descriptor of each opened port for the recorder; a replay answers from
  the recording with stand-ins and never touches MIDI hardware. A port is described to the game
  by its descriptor on both sides, so live and replay answer alike.
- MIDI input becomes `MIDIIN` events in the engine's event batch, once per frame, so it is
  recorded and replayed with no new recording machinery.
- `MidiEventManager` has one proxy per opened port, like `JoystickEventManager`: the proxy
  lists the port among its proxies, so a game calls an output port's own methods
  (`write_short()`, `note_on()`, ...) through it. The manager itself gives MIDI events to the game.
  An input port is read by the door alone: a game holds a handle that has nothing to read, live as
  in a replay. `get_device_info()`
  is the proxy's own and answers from the descriptor the port was opened with: pygame's ports
  have no such method (pygame's is a module function), and asking PortMidi would let a replay
  differ from its recording.
- MIDI output goes through the opened port; a replay's output port accepts writes and drops them,
  as a replay controller drops rumble.
- Where pygame has no PortMidi (`import_midi_module()` returns None: the browser builds), MIDI
  answers "no ports", and that answer is recorded like any other.

## Non-goals

- Web MIDI in the browser builds.
- Hot-plugging: PortMidi lists ports at `pygame.midi.init()` and pygame posts no MIDI device
  events, so the ports are those present at start.
- A note or instrument layer (mapping MIDI notes to the sound engine's live instruments). Games
  can build it on the events; it is not part of this wiring.
- Recording MIDI output in the output record: the output record does not exist yet
  (`plans/future-work.md`); when it does, MIDI out becomes one of its sinks.

## Anti-goals

- Any use of `pygame.midi` outside the devices door. `tests/test_engine_doors.py` watches it (and
  PortMidi's extension module under it, `pygame.pypm` / `pygame.midi._pypm`) in every literal form:
  `import`, `from`-import, alias, attribute access on `pygame`, a string load
  (`importlib.import_module('pygame.midi')`, `__import__`). Only `input/devices.py` may.
- A replay that differs from its recording because a MIDI device is or isn't plugged in.
- A game that must special-case "no PortMidi": no ports is an ordinary answer.

## Constraints

- **The doors rule** (CLAUDE.md, "Gameplay Recording and Replay"): devices are enumerated and
  opened only through `active_sources().devices()`; polled input is never read from a device
  directly.
- **PortMidi refuses a second `Input(device_id)` on an open port.** The door hands back the port
  it already opened, as `joystick_for_instance` does for joysticks: ports are opened **once per
  registry** (one engine context's live doors), not once per process. A process-wide owner was
  the first design and was not built: a second live context would need a decision who reads a
  shared input (a message is read once), which has no case to test today, because an inner game
  (the Arcade's tiles) is always a replay with stand-in doors. So the limit is stated, not hidden:
  two live contexts naming one port is a logged, skipped port in the second (`plans/future-work.md`,
  "MIDI ports across live engine contexts").
- **PortMidi's failures are plain `Exception`** (its Cython `Input`/`Output` constructors,
  `Poll`, `Read` and `Close`; its message may be bytes), never `pygame.midi.MidiException`, and
  neither is a `pygame.error`. The door turns an open's failure into the one remembered
  `pygame.error`, so a replay raises the same.
- **pygame-ce 2.5.8's `close()` does not close a PortMidi port**: reopening one in the same
  process fails until `pygame.midi.quit()`. A port's life therefore ends at the engine's
  teardown, where the door closes every opened port and quits PortMidi.
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
  `open_midi_output(port_id=...)`, and `midi_input_for_port` / `midi_output_for_port` to look up
  a port already opened (the per-registry rule above; an open of an open port hands it back). An
  input is handed out as a `MidiInputHandle`, live as in a replay (`ReplayMidiInput` is one):
  `poll()` is False, `read()` is empty, `close()` closes nothing. The live registry alone holds the
  raw input port, reads it and closes it.
- `LiveDeviceRegistry` calls `pygame.midi.init()` once, opens real ports, remembers answers and a
  descriptor per opened port, and reads every opened input port when the pump asks it to
  (`read_midi_input()`, below).
- `ReplayDeviceRegistry` answers from the recording and opens stand-ins: `ReplayMidiInput` (reads
  nothing; its events come from the recording's batches) and `ReplayMidiOutput` (accepts every
  write and drops it).
- The stand-in registry (`src/glitchygames/input/stand_in_devices.py`) gets stand-in MIDI ports for
  tests, with messages a test queues. It refuses an open of a port that is missing or goes the
  other way as live does (`openable_midi_port`), so a game's handling of the failure can be tested.
- A second descriptor type, `MidiPortDescriptor` (kind, port id, name, interface), because the
  joystick fields don't apply to a port; recordings made before this change still load.
- No PortMidi: every call answers as a machine with no MIDI ports.
- **Port identity (my call):** MIDI ports are their own namespace, keyed by kind and PortMidi port
  id (inputs and outputs are numbered together by PortMidi, but kept apart by kind here), never
  mixed with SDL instance ids in the joystick maps. A replay matches ports by their recorded id:
  the events it serves carry recorded ids, and it never sees the replaying machine's ports.
- `import_midi_module()` moves from `events/midi.py` to the door (`input/devices.py`), which owns
  every `pygame.midi` call; the manager asks the door. The module-level `MIDI_MODULE` constant is
  gone: it was import-time state, and a function answers at call time.

### Input into the event batch

- `LiveSources.pump_events()` returns SDL's events and then the door's `read_midi_input()`: for
  each opened input port, the `MIDIIN` events its pending messages make (`midis2events`, with the
  port id as `device_id`).
  `RecordingSources` already records the batch as returned; the replay driver and playback scopes
  already serve recorded batches. A recording therefore holds MIDI input as ordinary pumped
  events, and needs no format change for them.
- **Reading** (`MidiInputReader`, one code path for the live and the stand-in registries): each
  opened input is read in port-id order until a read returns nothing, up to a per-frame cap
  (`MIDI_MESSAGES_PER_PORT_PER_FRAME`, the rest the next frame, in order). It is read first, never
  asked `poll()` whether messages wait: a full PortMidi buffer hands over what it holds, then its
  `poll()` is False and it refuses all further input until a `read` raises the overflow, once
  (verified on a CoreMIDI virtual port, PortMidi 2.0.7); the next read works. So an overflow is
  **lost input, not a dead port**: logged (bounded: once per port per burst), the batch lost, the
  port kept and read on. Any other failure of a read drops that port for the rest of the run
  (logged once, never closed: it is a device that went away), and the others go on.
- The read happens in the door, during the pump, never in a manager or a game. Only live play
  reads: `read_midi_input()` is `LiveDeviceRegistry`'s (and the stand-in registry's, for tests),
  called by `LiveSources.pump_events()`, so it is not on the `EngineSources` or `DeviceRegistry`
  protocol. `HostSources` and `RecordingSources` already pass the inner pump's batch through, and
  replays serve recorded batches. MIDI events follow SDL's in the batch.
- **`MIDIOUT` stays without a producer (my call):** pygame never builds one, and a write through an
  output port posts nothing. Recording what was sent belongs to the future output record.
- **Game side:** a scene defines `on_midi_in_event(event)` and receives each message as a
  `MidiEvent` (`status`, `data1`-`data3`, `timestamp`, `vice_id`: the port id), in the frame it
  was read. It writes through the proxy in `current_engine().midi_manager.ports` (keyed `(kind,
  port id)`, with the port's `descriptor`), whose methods are the output port's; a replay accepts
  and drops them.

### `MidiEventManager` (`src/glitchygames/events/midi.py`)

- Like `JoystickEventManager`, a bigger change than it looks (today the manager builds one proxy
  and has no open or adopt methods): `MidiEventProxy` becomes per port, opened through the door
  (or handed back by it), with `proxies = [game, port]` and no event handler (an event names its
  port, `vice_id`, and the proxy has no state to keep from it, unlike a joystick's); the manager
  keeps them by port id and opens the connected ports at start (`open_connected_midi_ports`, which
  `GameEngine.enter_playback_devices` calls with the scope's door, as it does for joysticks).
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
- **A recording's port names come from the recording.** Both options are recorded with the
  run's options and are not `REPLAY_LOCAL_OPTIONS`, so a replay opens the ports the recorded run
  named (never the replaying command's, never the machine's), and a recording made before the
  options existed opens none.
- **What a playback scope does with MIDI** (`replay/playback.py`): live MIDI input is in the
  doors' batch during a scope and is the player's, as a joystick's is, told by its message. A note
  played is a press: it ends a scope that exits on input, and no other (a pedal's press never
  does). A note-off, a note-on at velocity 0 and the channel's letting go (all sound off, reset
  all controllers, all notes off) are releases: held, and handed to the live game after the scope.
  A control moved (pitch bend, channel and polyphonic pressure, controllers below 120, pedals
  included) is held as its latest message per port, channel and control, because MIDI has no
  polled state to read again. The parameter numbers and their data (controllers 6, 38, 96-101) are
  dropped: a lone data entry could change the wrong parameter, so a parameter set during a scope
  is lost. Program changes, local control and the system and real-time messages are motion and
  dropped. The scope's ports are stand-ins, so nothing written during it reaches a live port.
- The proxy no longer lists the raw `pygame.midi` module among its proxies: today a game could call
  `pygame.midi.Input(...)` through it and go around the door. Nothing in the repository uses that
  passthrough (checked 2026-11-24); enumeration is the door's (`midi_port_count()`, ...), offered
  through the manager.
- A scene without its own handler still gets `unhandled_event` (raises under
  `--no-unhandled-events`).

### Guards and docs

- `tests/test_engine_doors.py`: `pygame.midi` (and `pygame.pypm`, `pygame.midi._pypm`) allowed
  only in the devices door, in every literal form (see Anti-goals), each proved with a plant.
- Each new slot or audited state row checked (`tests/test_engine_context.py`,
  `tests/test_process_state_guard.py`).
- `docs/architecture/event_system.md` (ports, what a game receives and sends, stand-in ports in a
  test, limitations), `gameplay_replay.md` (what is recorded, playback scopes),
  `argument_system.md` (the options), `playback/recording-file.md` (the fields). `CLAUDE.md`'s
  doors line does not name the device kinds, so it is unchanged.

## Tests, as behaviours

- A message on a stand-in input port arrives as one `MIDIIN` event with pygame's fields, in the
  frame it was queued, at the scene's `on_midi_in_event`.
- A recorded run with MIDI input replays it exactly, with no MIDI port present at replay.
- A replay never opens or reads a real MIDI port (the doors guard, and a test with
  `pygame.midi` made to raise).
- Opening a port that is already open hands back the same port, with no second open.
- A game that reads, polls or closes its input takes nothing from the frame's events and closes
  no port, live, on stand-ins and in a replay.
- Recorded port names of the wrong shape are refused by a replay and by a playback scope.
- A read that meets an overflow loses that batch, logs once, keeps the port, and the next read
  works; any other read failure drops that port only. The fakes follow PortMidi's observed
  contract (`poll()` False until a read reports the overflow).
- A burst past the per-frame cap arrives over the next frames, in order.
- A playback scope holds a note-off and a control's latest message for the live game, and
  drops a parameter's data.
- A write through a replay output port is accepted and goes nowhere; live, it reaches the port.
- With no port named, PortMidi is never initialized and a run's recording has no MIDI answers.
- An instant replay of a scene with MIDI ports adopts replay stand-ins, and leaving it puts the
  live ports back; a write during it reaches no live port.
- With no PortMidi, the door answers zero ports and the manager opens none; a recording made that
  way replays the same answers.
- Recordings made before this change load and replay unchanged.
- Live, stand-in and replay answer the same enumeration calls the same way (as the joystick tests
  compare them).

## Not built (deferred; `plans/future-work.md`, "MIDI ports across live engine contexts")

- Two live engine contexts naming one port, and who reads a shared input.
- Notes still sounding on a live output port when a playback scope starts (the scope writes
  nothing to a live port, a note-off included).
- `InnerGame.finish()` closing ports, and a live inner context not shutting PortMidi down under
  the outer one.
- Hot-plugging, Web MIDI, a note or instrument layer, and the output record (non-goals above).
- On macOS an unplugged port raises nothing on read: the port just stays silent.

## Decisions record

- 2026-11-24, the owner: plan MIDI before building; wire it like the other event subsystems
  (devices door, per-device proxies); approach 1.
- 2026-11-24, the owner, after the builder check: MIDI starts only when a port is named; instant
  replay is in scope.
- 2026-11-24, built: ports open once per registry, not once per process (a process-wide owner
  would settle who reads a shared input, with no live inner game to test it; deferred); PortMidi's
  failures are plain `Exception`; an overflow is met by a read and is lost input, not a dead
  port; the proxy's `get_device_info()` answers from the descriptor; `MIDI_MODULE` removed; the
  guard watches `pygame.midi` and PortMidi's extension module in every literal form.
- 2026-11-24, after the whole-branch review: a game never reads a live input port (the door's reader
  alone holds it; the handle is the replay stand-in's, because a read would take messages from
  the recording); the proxy's `on_midi_*_event` are removed (nothing called them); recorded port
  names that are not lists of names are refused, in a replay and a playback scope alike; a recorded
  port count past `MAXIMUM_MIDI_PORT_COUNT` is no count; a stand-in registry refuses a missing or
  wrong-way port as live does.
