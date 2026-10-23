# Unified Input Devices — Plan

- **Date:** 2026-10-22
- **Status:** Proposed, for the user's review (the user's choice, 2026-10-22: "Plan it first"). No
  code yet.
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

## Open questions for the user

- Is "controller layer when mapped, else joystick layer" the right default for event dispatch, or
  should a game choose per device?
- Keep `input_mode` as a compatibility option, or remove it once both layers work together?
