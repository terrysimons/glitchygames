# Rumble and Light Answers and the Power Level Differ Between Live and a Replay

- **Description**: A replay's stand-in devices answer `rumble` True, `set_led` False and
  `get_power_level` `unknown`. A live controller answers as its hardware does: rumble can be False,
  a light True, the power level real. None is recorded, so a game or console that branches on one
  diverges.
- **Reproduction**:
  - Not reproduced live (no controller was plugged in). The stand-ins' answers, run against the
    code: `controller rumble True set_led False | joystick rumble True set_led False power unknown`.
  - Smallest test: record a stand-in device whose registry answers `rumble` False and `set_led` True
    (the pattern of `tests/input/stand_in_devices.py`), with a scene that moves a sprite by the
    answer, and replay it.
- **Status**: Open
- **Priority**: Low. No game reads the answers: Zombies ignores `rumble`'s, `set_led` and the power
  level have no reader in the members.
- **Root Cause**: `ReplayJoystick` and `ReplayController` (`src/glitchygames/input/devices.py:788`,
  882, 900, 1016, 1034) hard-code the answers. Live: `src/glitchygames/input/input_devices.py:461`
  (rumble), `src/glitchygames/events/controller.py:314` (`set_led`),
  `src/glitchygames/events/joystick.py:136` (power level, read once at open).
- **Test gap**: The stand-in's tests check their own answers; nothing compares them with a live
  device's, and a `DeviceDescriptor` has no such field.
- **Solution**: Not chosen. Options, all unproven:
  - Record each answer with its call and serve it (optional fields, so old recordings load).
  - Add `power_level` to the descriptor (read once at open), and leave the calls' answers fixed but
    documented.
- **Known limits**: Rumble failures live (`pygame.error`) come back as False and are logged.
- **Sweep**: Covered: rumble, light, power level on both layers. Also without a recorded answer, by
  reading: the sustained rumble (`src/glitchygames/input/rumble.py:267`), whose answer is dropped.
- **Related**: [No real
  stimulus](../plans/lucid-circuit-4b-mirror.md#no-real-stimulus-the-owner-2026-11-24) in the
  mirror's plan.
- **Reporter**: The mirror game's hardware inventory, the coordinator
- **Date Reported**: 2026-11-24
- **Files**: `src/glitchygames/input/devices.py`, `src/glitchygames/input/input_devices.py`,
  `src/glitchygames/events/controller.py`, `src/glitchygames/events/joystick.py`
