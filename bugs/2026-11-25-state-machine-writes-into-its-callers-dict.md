# The Animation State Machine Writes Into Its Caller's Dictionary

- **Description**: `AnimationStateMachine.evaluate` adds `timer` and `animation_complete` to the
  `context` dictionary it is given (`src/glitchygames/animation/state_machine.py`, lines 288 to
  294). A caller that keeps one dictionary and passes it again finds both keys in it, and the
  `animation_complete` of an earlier call stands for a sprite that does not report its own (the
  default is set only when the key is absent).
- **Status**: Open, not fixed.
- **Priority**: Low (each shipped caller, the player classes and the cobra, builds its dictionary
  for the call; no wrong behavior in a game is known).
- **Root Cause**: The built-in variables are added to the caller's dictionary itself, not to a copy.
- **Test gap**: `tests/animation/test_animation.py` asserts the writing (lines 818 and 829), so a
  fix must change those tests; none checks that a caller's dictionary is unchanged.
- **Found by**: The process-state sweep of 2026-11-24. `RUNNING_OFF_A_LEDGE_CONTEXT`, a module
  constant of two Brave Adventurer test files, went from 3 keys to 5.
- **Options** (unproven):
  1. Copy the dictionary at the start of `evaluate`, and have the two tests check the transition
     instead: one small copy a frame for each state machine.
  2. Keep writing, say so in the docstring, and copy in the two tests' files: no engine change, and
     the stale `animation_complete` stays possible.
- **Reporter**: The state-leak work (`fix/tests-leak-no-state`).
- **Date Reported**: 2026-11-25
- **Files**: `src/glitchygames/animation/state_machine.py`, `tests/animation/test_animation.py`,
  `src/games/brave-adventurer/tests/classic/test_brave_adventurer_classic.py`,
  `src/games/brave-adventurer/tests/papyrus/test_brave_adventurer_papyrus.py`
