# MIDI Devices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MIDI ports are enumerated, opened, read and written only through the devices door, so
MIDI input arrives as recorded `MIDIIN` events and replays exactly, wired like joysticks.

**Architecture:** The devices door (`input/devices.py`) gains MIDI ports beside joysticks and
controllers (live, replay and stand-in registries); the live pump appends each opened input port's
messages to the frame's batch, which recording and replay already carry; `MidiEventManager` gets
one proxy per opened port. MIDI starts only when a port is named.

**Tech Stack:** Python 3.15 (3.14 syntax), pygame-ce 2.5.8 `pygame.midi` (PortMidi), pytest with
pytest-mock, ruff, basedpyright, ty.

**Spec:** `plans/2026-11-24-midi-devices.md` (approved by the owner 2026-11-24). Read it first.

## Global Constraints

- `pygame.midi` is called only in `src/glitchygames/input/devices.py` (the devices door).
- MIDI starts only when a port is named (`--midi-input NAME`, `--midi-output NAME`): with none
  named, `pygame.midi.init()` is never called and nothing about MIDI is asked or recorded.
- MIDI ports are their own namespace (kind + PortMidi port id), never keys in the joystick maps.
- Recordings made before this change load and replay unchanged: every new header or frame field
  is optional and absent means "no MIDI".
- `MidiEvent` fields are pygame's: `status`, `data1`, `data2`, `data3`, `timestamp`, `vice_id`.
- No PortMidi (`import_midi_module()` returns None) answers as zero ports.
- `MIDIOUT` has no producer; writes post no event.
- Tests: real files (`tmp_path`), `mocker` only for what can't run (real MIDI hardware); stand-in
  ports for everything else. 100% coverage, ruff, basedpyright and ty clean.
- Commit with `SKIP=replay-metrics`; stage nothing under `quality/replay-ledger/`.
- Before each commit: `uv run ruff format`, `uv run ruff check src tests scripts noxfile.py`,
  `uv run basedpyright`, then the task's tests with `uv run pytest <files> -n 4 --dummy-only`.

## Review Focus

1. A named port that isn't present: the run goes on, logs it once, and records the answer, so the
   replay gives the same answer (Task 4).
2. The same port named twice, or named by two games in one process: one open, one proxy (Task 2,
   Task 4).
3. A port that fails mid-run (`pygame.midi.MidiException` on read): logged, that port stops being
   read, the others go on, and the frame's batch is still recorded (Task 3).
4. A burst of messages larger than one read (`Input.read(n)` returns at most n): every pending
   message reaches the batch in the same frame, in arrival order (Task 3).
5. An instant replay started while a MIDI output port is open: writes during it reach no live port,
   and leaving it restores the live port (Task 5).

---

### Task 1: MIDI enumeration through the door

**Files:**
- Modify: `src/glitchygames/input/devices.py` (module docstring, constants, `EnumerationValue`,
  `DeviceRegistry`, `LiveDeviceRegistry`, `ReplayDeviceRegistry`)
- Modify: `src/glitchygames/input/stand_in_devices.py` (`StandInDeviceRegistry`)
- Modify: `src/glitchygames/events/midi.py` (imports the module from the door)
- Test: `tests/input/test_devices.py`, `tests/events/test_midi_events.py`

**Interfaces:**
- Produces: `import_midi_module() -> ModuleType | None` and `MIDI_MODULE` move to
  `input/devices.py` (`events/midi.py` re-imports them for its tests' sake only if a test needs
  it; otherwise update the test import). Constants `MIDI_INPUT_KIND = 'midi_input'`,
  `MIDI_OUTPUT_KIND = 'midi_output'`, `MIDI_PORT_COUNT_CALL = 'midi_port_count'`,
  `MIDI_PORT_INFO_CALL = 'midi_port_info'`, `DEFAULT_MIDI_INPUT_CALL = 'default_midi_input_id'`,
  `DEFAULT_MIDI_OUTPUT_CALL = 'default_midi_output_id'`.
- Produces: `type EnumerationValue = int | bool | str | list[str | int | bool] | None`.
- Produces on `DeviceRegistry` and all three registries: `midi_port_count() -> int`,
  `midi_port_info(*, port_id: int) -> MidiPortInfo | None`, `default_midi_input_id() -> int`,
  `default_midi_output_id() -> int` (-1 when none, as PortMidi says).
- Produces: `MidiPortInfo`, a frozen pydantic model (`extra='forbid'`): `interface: str`,
  `name: str`, `is_input: bool`, `is_output: bool`; recorded as the answer value
  `[interface, name, is_input, is_output]`.
- Produces: `find_midi_port(*, devices: DeviceRegistry, name: str, kind: str) -> int | None`
  (the first port whose name matches and whose direction fits `kind`).

- [ ] **Step 1: Write the failing tests**

  - `test_live_midi_enumeration_is_remembered` (mock `pygame.midi` module functions: `get_count`
    returns 2, `get_device_info` returns `(b'CoreMIDI', b'Keys', 1, 0, 0)` and
    `(b'CoreMIDI', b'Synth', 0, 1, 0)`): `midi_port_count() == 2`;
    `midi_port_info(port_id=0) == MidiPortInfo(interface='CoreMIDI', name='Keys', is_input=True,
    is_output=False)`; `take_enumeration_answers()` holds the count and both infos in call order.
  - `test_replay_answers_midi_enumeration_as_recorded`: a `ReplayDeviceRegistry` built from those
    answers gives the same values with `pygame.midi` patched to raise on any call.
  - `test_no_portmidi_answers_zero_midi_ports` (`import_midi_module` patched to None): count 0,
    defaults -1, `midi_port_info(port_id=0) is None`, and those answers are recorded.
  - `test_find_midi_port_matches_name_and_direction`: `'Keys'` as input → 0; `'Keys'` as output →
    None; `'Synth'` as output → 1.
  - `test_midi_enumeration_never_initializes_portmidi_until_asked`: building a
    `LiveDeviceRegistry` calls no `pygame.midi` function; the first MIDI call calls `init()` once.

- [ ] **Step 2: Run them to verify they fail**

  Run: `uv run pytest tests/input/test_devices.py -k midi -n 4 --dummy-only`
  Expected: FAIL (`midi_port_count` not defined).

- [ ] **Step 3: Implement** the constants, `MidiPortInfo`, the four calls on the three registries
  (live: lazy `init()` on first MIDI call; answers and failures remembered through the existing
  `_remember_answer` / `_remember_failure`; replay: from recorded answers, as joysticks), and
  `find_midi_port`. Move `import_midi_module` / `MIDI_MODULE`; `events/midi.py` imports them from
  the door.

- [ ] **Step 4: Run them to verify they pass**, plus `tests/events/test_midi_events.py`.

- [ ] **Step 5: Commit** — "MIDI devices: the door enumerates MIDI ports, recorded and replayed".

### Task 2: Opening ports, once per process, recorded

**Files:**
- Modify: `src/glitchygames/input/devices.py`, `src/glitchygames/input/stand_in_devices.py`
- Modify: `src/glitchygames/recording.py` (frame field), `src/glitchygames/replay/driver.py`
  (header field into `ReplayDeviceRegistry`)
- Test: `tests/input/test_devices.py`, `tests/test_recording.py` (or the file that tests
  `devices_opened` today: find it with `rg devices_opened tests`)

**Interfaces:**
- Consumes: Task 1's calls and `MidiPortInfo`.
- Produces: `MidiPortDescriptor`, a frozen pydantic model: `kind: str` (`MIDI_INPUT_KIND` or
  `MIDI_OUTPUT_KIND`), `port_id: int`, `name: str`, `interface: str`; `to_json()` / `from_json()`.
- Produces on the registries: `open_midi_input(*, port_id: int) -> OpenedMidiInput`,
  `open_midi_output(*, port_id: int) -> OpenedMidiOutput`,
  `midi_input_for_port(*, port_id: int) -> OpenedMidiInput | None`,
  `midi_output_for_port(*, port_id: int) -> OpenedMidiOutput | None`,
  `take_opened_midi_ports() -> list[MidiPortDescriptor]`.
- Produces: `OpenedMidiInput` / `OpenedMidiOutput` type aliases (live `pygame.midi.Input` /
  `Output`, or `ReplayMidiInput` / `ReplayMidiOutput`); `ReplayMidiInput.poll() -> False`,
  `.read(n) -> []`; `ReplayMidiOutput` accepts `write_short`, `write`, `note_on`, `note_off`,
  `set_instrument`, `pitch_bend`, `write_sys_ex` and returns None without effect.
- Produces: recording fields `MIDI_PORTS_HEADER_FIELD = 'midi_ports'` (ports opened before the
  first frame) and the frame field `midi_ports_opened`, both absent when no port opened.
- Open calls are recorded as `EnumerationAnswer`s (`OPEN_MIDI_INPUT_CALL`,
  `OPEN_MIDI_OUTPUT_CALL`), value the port id, failures with their error, as joysticks.

- [ ] **Step 1: Write the failing tests**
  - `test_opening_an_open_midi_port_hands_back_the_same_port`: two `open_midi_input(port_id=0)`
    calls on a live registry construct `pygame.midi.Input` once and return the same object.
  - `test_opened_midi_ports_are_taken_once_by_the_recorder`: one descriptor, then empty.
  - `test_replay_midi_output_drops_writes`: `note_on(60, 100)` on a `ReplayMidiOutput` returns
    None and calls no `pygame.midi` function.
  - `test_a_failed_midi_open_is_recorded_and_fails_the_same_in_replay` (mirror of the joystick
    test of that name).
  - `test_a_recording_without_midi_fields_loads_with_no_ports`: a header without `midi_ports`
    gives a replay registry with no MIDI ports and no warning.

- [ ] **Step 2: Run them to verify they fail.**
- [ ] **Step 3: Implement** the descriptor, the open and lookup calls (live keeps
  `dict[tuple[str, int], port]`), the replay stand-ins, and the recorder and replay fields.
- [ ] **Step 4: Run them to verify they pass**, plus `tests/input/` and the recording tests.
- [ ] **Step 5: Commit** — "MIDI devices: ports open through the door once per process; replays
  open stand-ins".

### Task 3: MIDI input into the frame's events

**Files:**
- Modify: `src/glitchygames/input/devices.py` (`LiveDeviceRegistry.read_midi_input`),
  `src/glitchygames/input/stand_in_devices.py` (queued messages),
  `src/glitchygames/live_sources.py` (`pump_events`)
- Test: `tests/input/test_devices.py`, `tests/engine/test_engine_event_system.py`

**Interfaces:**
- Consumes: Task 2's opened inputs.
- Produces: `LiveDeviceRegistry.read_midi_input() -> list[pygame.event.Event]` (every opened
  input port, in port-id order; for each, `read(MIDI_READ_BATCH)` until `poll()` is false, then
  `pygame.midi.midis2events(messages, port_id)`); `MIDI_READ_BATCH = 64`.
- Produces: `StandInDeviceRegistry.queue_midi_input(*, port_id: int, messages:
  list[tuple[list[int], int]]) -> None` and its `read_midi_input()` returning them as events.
- `LiveSources.pump_events()` returns SDL's batch, then `self.devices().read_midi_input()` when
  the registry has that method (live and stand-in), after `without_discarded_scope_posts`.

- [ ] **Step 1: Write the failing tests**
  - `test_midi_input_reaches_the_scenes_handler_in_its_frame` (stand-in sources, one queued
    note-on `([0x90, 60, 100, 0], 1234)` on port 3): the recording scene's `on_midi_in_event` gets
    one `MidiEvent` with `status=0x90`, `data1=60`, `data2=100`, `data3=0`, `timestamp=1234`,
    `vice_id=3`, in the same frame.
  - `test_a_burst_larger_than_one_read_arrives_whole_and_in_order` (200 queued messages): 200
    events, timestamps ascending, one frame.
  - `test_a_failing_midi_port_is_dropped_and_the_others_still_read` (one stand-in port raises
    `pygame.midi.MidiException`): logged once, the other port's events still arrive, the next
    frame reads only the good port.
  - `test_recorded_midi_input_replays_exactly`: record a run with queued MIDI input to `tmp_path`,
    replay it headless with `pygame.midi` patched to raise: the scene receives identical events
    and the replay reports no divergence.

- [ ] **Step 2: Run them to verify they fail.**
- [ ] **Step 3: Implement** `read_midi_input` (live and stand-in) and the pump's append.
- [ ] **Step 4: Run them to verify they pass**, plus `tests/test_engine_doors.py` and the replay
  tests (`tests/replay/`).
- [ ] **Step 5: Commit** — "MIDI devices: input arrives as recorded MIDIIN events".

### Task 4: `MidiEventManager` with per-port proxies and the port options

**Files:**
- Modify: `src/glitchygames/events/midi.py`, `src/glitchygames/engine/game_engine.py`
  (`_initialize_event_managers`, argument wiring)
- Test: `tests/events/test_midi_events.py`, `tests/engine/test_game_engine.py`

**Interfaces:**
- Consumes: Task 1's `find_midi_port`, Task 2's opens.
- Produces: `MidiEventManager.args` adds `--midi-input NAME` and `--midi-output NAME`
  (`action='append'`, default empty; a game may set its own default in its options).
- Produces: `MidiEventManager.MidiEventProxy(*, game: object, port: OpenedMidiInput |
  OpenedMidiOutput, descriptor: MidiPortDescriptor)` with `proxies = [game, port]`;
  `MidiEventManager.ports: dict[tuple[str, int], MidiEventProxy]`;
  `MidiEventManager.open_connected_midi_ports(*, input_names: Sequence[str], output_names:
  Sequence[str]) -> dict[tuple[str, int], MidiEventProxy]`.
- The manager no longer lists the `pygame.midi` module among any proxies.
- `on_midi_in_event` / `on_midi_out_event` forward to the game, as today.

- [ ] **Step 1: Write the failing tests**
  - `test_no_named_port_means_portmidi_is_never_initialized`: an engine started with default
    options never calls `pygame.midi.init` and its recording has no MIDI answers.
  - `test_a_named_input_port_opens_one_proxy` (stand-in port `'Keys'`): `--midi-input Keys` gives
    one proxy keyed `(MIDI_INPUT_KIND, 0)`, and `proxy.get_device_info` reaches the port.
  - `test_a_named_port_that_is_absent_is_logged_and_skipped` (`--midi-input Nope`): no proxy, one
    warning naming `Nope`, the run continues, and the answers are recorded.
  - `test_naming_a_port_twice_opens_it_once`.
  - `test_the_proxy_no_longer_reaches_pygame_midi`: `getattr(proxy, 'Input')` raises
    `AttributeError`.

- [ ] **Step 2: Run them to verify they fail.**
- [ ] **Step 3: Implement** the options, the per-port proxies and `open_connected_midi_ports`;
  the engine passes the parsed names when it builds the manager.
- [ ] **Step 4: Run them to verify they pass**, plus `tests/engine/` and `tests/events/`.
- [ ] **Step 5: Commit** — "MIDI devices: MidiEventManager opens the named ports, one proxy each".

### Task 5: Playback scopes and instant replay

**Files:**
- Modify: `src/glitchygames/engine/game_engine.py` (`LiveDevicesBehindScope`,
  `enter_playback_devices`, `exit_playback_devices`),
  `src/glitchygames/input/input_devices.py` (`RecordedDevices`, `scene_start_devices_record`),
  `src/glitchygames/input/devices.py` (`ReplayDeviceRegistry.adopt_midi_port`),
  `src/glitchygames/events/midi.py` (`adopt_midi_ports`)
- Test: the playback-scope device tests (find them with `rg enter_playback_devices tests`),
  `tests/input/test_input_devices.py`

**Interfaces:**
- Consumes: Task 2's descriptors and stand-ins, Task 4's `ports`.
- Produces: `LiveDevicesBehindScope.midi_ports: dict[tuple[str, int],
  MidiEventManager.MidiEventProxy]`; `RecordedDevices.scene_start_midi_ports:
  tuple[MidiPortDescriptor, ...] | None`, written by `scene_start_devices_record` under the key
  `midi_ports` (absent in older journals means none);
  `ReplayDeviceRegistry.adopt_midi_port(*, descriptor: MidiPortDescriptor) -> ReplayMidiInput |
  ReplayMidiOutput`; `MidiEventManager.adopt_midi_ports(*, descriptors:
  Sequence[MidiPortDescriptor], registry: ReplayDeviceRegistry) -> dict[...]`.
- A recording file's scope opens its recording's ports through the scope's door
  (`open_connected_midi_ports` with the recorded names); an instant replay adopts them.

- [ ] **Step 1: Write the failing tests**
  - `test_an_instant_replay_adopts_stand_in_midi_ports_and_restores_the_live_ones`: during the
    scope `manager.ports` hold replay stand-ins; after `exit_playback_devices` they are the live
    proxies again (same objects).
  - `test_a_write_during_an_instant_replay_reaches_no_live_port`: a mocked live `Output` sees no
    call while the scope plays.
  - `test_a_journal_without_midi_ports_adopts_none`.

- [ ] **Step 2: Run them to verify they fail.**
- [ ] **Step 3: Implement** as the joystick path does it.
- [ ] **Step 4: Run them to verify they pass**, plus `tests/replay/` and `tests/engine/`.
- [ ] **Step 5: Commit** — "MIDI devices: playback scopes and instant replays hold their own
  ports".

### Task 6: Guards and docs

**Files:**
- Modify: `tests/test_engine_doors.py` (`WATCHED_DOOR_MODULES` gains `'pygame.midi'`; the scan
  also resolves `importlib.import_module('pygame.midi')`; allowlist: `input/devices.py` only)
- Modify: `tests/test_process_state_guard.py` rows / `tests/test_engine_context.py` checks for
  any new module-level state (the live registry's lazy-init flag belongs to the registry, not the
  module)
- Modify: `docs/architecture/event_system.md` (MIDI section and table: ports, options, proxies),
  `docs/architecture/gameplay_replay.md` (devices: MIDI ports), `CLAUDE.md` (the doors line if it
  lists device kinds; run `uv run pytest tests/test_claude_md.py`), `plans/future-work.md` (link
  this plan from the output-record entry's MIDI lines), `plans/2026-11-24-midi-devices.md`
  (status line)

- [ ] **Step 1: Write the failing guard test** `test_pygame_midi_is_called_only_in_the_devices_door`
  with a planted `pygame.midi.get_count()` in a temporary engine module: the guard reports it;
  remove the plant.
- [ ] **Step 2: Run it** (`uv run pytest tests/test_engine_doors.py -n 4 --dummy-only`): FAIL
  before the scan change, PASS after.
- [ ] **Step 3: Update the docs**; run `uv run nox -s lint-docs`, `uv run python -m
  scripts.docs_claims` (0 claims), `uv run pytest tests/test_docs_claims.py tests/test_claude_md.py`.
- [ ] **Step 4: Commit** — "MIDI devices: the doors guard watches pygame.midi; docs".

## Done means

All six tasks committed; `uv run pytest -n 4 --dummy-only` on the touched test folders green;
`uv run glitchygames verify` all PASS (no golden changes: MIDI is off unless a port is named);
then the pre-push gate on a Ledger slot.
