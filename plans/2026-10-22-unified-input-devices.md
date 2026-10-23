# Unified Input Devices — Plan

- **Date:** 2026-10-22
- **Status:** Approved 2026-10-22 ("Do both now", with the typed events plan); implemented
  2026-10-22 on `cleanup/post-replay` (steps 0-5 done; see Done below). Decisions (the user, 2026-10-22): a mapped gamepad dispatches its
  controller-layer events only, an unmapped device its joystick events ("Controller if mapped");
  `--input-mode` stays, as a filter restricting which devices a game sees (default: both).
- **Why:** joysticks and controllers are meant to run together (the user, 2026-10-22: "in theory
  if joysticks and controllers both worked together ... we could run both and not need to select
  one"), but the engine models them as two separate managers, one of which is switched off. Game
  code that shows or reads devices has to pick a mode and branch on it (`examples/joystick_demo.py`
  re-checks an `input_mode` string in about ten methods), and the manager dicts are typed
  `dict[int, Any]`, so every reader of a device gets `Any` (the 12 ANN401 sites left in the demo,
  `plans/2026-10-20-lint-ignores-cleanup.md`, Phase 4).
- **Constraint (the user):** game ergonomics first, game code as lean as possible; internal
  semantics may change if that makes the game layer cleaner.

## Today

- `GameEngine` (`engine/game_engine.py`, ~1420-1450) picks one `input_mode`: `joystick` (the
  default on pygame-ce) blocks every controller event and creates no `ControllerEventManager`;
  `controller` creates both managers.
- SDL sees a mapped gamepad as one device with two layers: the raw joystick layer (axes, buttons,
  hats, by index) and the controller layer (`CONTROLLER_AXIS_*`/`CONTROLLER_BUTTON_*`), with one
  instance id. With both managers on, each tracks the same pad, and every press arrives twice
  (`JOYBUTTONDOWN` and `CONTROLLERBUTTONDOWN`).
- `JoystickEventManager.joysticks` is keyed by instance id; `ControllerEventManager.controllers`
  by **device index**, but looked up by the event's **instance id** (BUGS.md #181: a crash after a
  replug).
- Underneath, the engine is already per physical device: the devices door
  (`input/devices.py`) records a `DeviceDescriptor` (kind, device index, instance id, name, GUID,
  axis/button/hat counts) for every opened device, and the input snapshot (`input/state.py`) keeps
  both layers keyed by instance id (`axis`/`button`/`hat`, `controller_axis`/`controller_button`).

## Proposal

1. **One registry of physical devices**, keyed by instance id: `InputDevices` (engine-owned, built
   on the devices door; replaces the two managers' dicts as the source of truth).
2. **`InputDevice`** (a Protocol for games; one concrete class used live and in replays):
   - `descriptor: DeviceDescriptor` (the one the door already records);
   - `joystick: JoystickLayer` — always present: `axis(index)`, `button(index)`, `hat(index)`,
     counts, read from the frame's snapshot;
   - `controller: ControllerLayer | None` — present when SDL maps the device:
     `axis(CONTROLLER_AXIS_*)`, `button(CONTROLLER_BUTTON_*)`;
   - `rumble(...)` routed as today (dropped in replays).
3. **Games** get `engine.input_devices` (iterable of `InputDevice`, plus added/removed events with
   the device). A game that only wants buttons reads `device.controller` when present, else the
   joystick layer. `input_mode` becomes, at most, a preference for which layer the engine
   *dispatches events from* (see 5).
4. **The demo** lists every device with no mode: name, GUID, ids from the descriptor, then the
   controller layer when present, else the joystick layer — one rendering path, no `Any`, no
   `hasattr`, no private reads. Expected to shrink by about 150 lines.
5. **Duplicate events** (the open question, the real work behind "both together"): with both layers
   on, choose per device which layer's events reach `on_*_event` handlers (controller layer for a
   mapped device, joystick layer otherwise is the natural default), so each press is delivered once.
   Polling through the layers is unaffected. Recordings and replays already record both event
   streams; check the golden replays (no joystick input in them today) and add a recording with a
   device to pin it.
6. **Types**: the manager dicts become `dict[int, JoystickEventProxy]` /
   `dict[int, ControllerEventProxy]` immediately (step 0, no behaviour change); the proxies'
   `joystick`/`controller` attributes are `OpenedJoystick`/`OpenedController`.

## Steps

0. Type the manager dicts and proxy attributes; fix BUGS.md #181 (key controllers by instance id,
   as the joystick manager does), test first. Small, independent.
1. `InputDevice` + layers over the snapshot; `InputDevices` registry from the door; tests with
   `ReplayJoystick`/`ReplayController` stand-ins (real objects, no mocks).
2. Engine exposes `input_devices` and device added/removed with the `InputDevice`.
3. Rewrite the joystick demo on it; delete the mode branches; ANN401 sites gone.
4. Event de-duplication per device (5), behind an option first; golden replays unchanged; a new
   recording with a device.
5. Docs: CLAUDE.md Devices paragraph, `docs/`, the demo's docstring.

## Decided (2026-10-22)

- Event dispatch: controller layer when SDL maps the device, else the joystick layer; each press
  reaches `on_*_event` handlers once. Polling either layer always works.
- `--input-mode`: kept as a filter (`joystick` = only the joystick layer's devices and events,
  `controller` = only mapped devices, `auto`/default = both).

## Done (2026-10-22)

0. The manager dicts are `dict[int, JoystickEventProxy]` / `dict[int, ControllerEventProxy]`,
   the proxies' devices `OpenedJoystick` / `OpenedController`, both proxies with public
   `instance_id` and `device_index`. BUGS.md #181 (and its duplicate #68) resolved: controllers
   keyed by instance id; a remap looked up by the instance id its event carries (it read a
   `device_index` the event does not have); a controller gone before it opened is skipped.
1. `glitchygames/input/input_devices.py` (its docstring holds the rules): `InputDevice`
   (Protocol: `descriptor`, `instance_id`, `name`, `joystick: JoystickLayer`,
   `controller: ControllerLayer | None`, `event_layer`, `rumble(...)`, `stop_rumble()`), the one
   concrete `ConnectedInputDevice`, the layers (`axis(axis=...)`, `button(button=...)`,
   `hat(hat=...)`, counts, and `axes` / `buttons` / `hats` tuples, all from the snapshot), and the
   registry `InputDevices` (`synchronize(joysticks=..., controllers=...) -> InputDeviceChanges`,
   `dispatches(event_type=..., instance_id=...)`, `get(instance_id=...)`, iteration). The devices
   door gained `descriptor_for_instance` (a game controller keeps its controller descriptor).
   The registry follows the managers and opens nothing; in `auto` mode it asks the door
   `is_controller` for a joystick the controller manager does not hold yet, so a mapped pad is
   added once, with both layers.
2. `GameEngine.input_devices`, `Scene.input_devices`, and `Scene.on_input_device_added` /
   `on_input_device_removed(device=...)` (through the scene manager, after each device event).
   `--input-mode` is the filter (`auto` no longer means joystick mode on pygame-ce);
   `ActionMap` gained `auto` (its default: both families bound).
3. The demo rewritten (1,422 to 318 lines; BUGS.md #185): one column per device, no mode
   branches, no `Any`; the shapes, tiles, tabs and unused arguments dropped.
4. `GameEngine.process_joystick_event` / `process_controller_event` drop an input event whose
   layer is not its device's `event_layer` (handled, not unhandled). Golden replays unchanged
   (recorded in joystick mode); `tests/world/test_gameplay_replay.py::TestDeviceDispatchReplays`
   records a session with a fake stick and pad through the real doors and replays it with the
   same dispatch, and no hardware.
5. Docs: CLAUDE.md (Devices, Input devices), `docs/architecture/event_system.md` (One device, one
   event layer), `docs/architecture/argument_system.md`, the demo's docstring, BUGS.md.

Follow-ups (BUGS.md #184): rumble through `InputDevice.rumble` for every device (today it still
picks the controller manager's controllers, else the joysticks), a playback scope's device events
and rumble, and a hardware check of `auto` with real pads.
