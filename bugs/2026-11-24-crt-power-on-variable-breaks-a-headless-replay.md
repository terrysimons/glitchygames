# GLITCHYGAMES_CRT_POWER_ON=on Makes a Headless Replay Play the Power-On and Diverge at Frame 0

- **Description**: With the environment variable set to `on`, a replay plays the CRT power-on before
  frame 0 (60 frames with real sleeps) and its extra pump diverges. The same value given as the
  option is refused.
- **Reproduction**: Reproduced 2026-11-24 at `5006bcb6` (macOS arm64, Python 3.15.1, pygame-ce
  2.5.8, SDL 2.32.10) in child processes on the dummy drivers, with `HOME`, the sound cache root and
  the AI install root in a scratch folder.
  - The game is a throwaway scene of one 4x4 sprite that quits itself at frame 90 and moves the
    sprite when the branch is taken; it is recorded with `--headless --no-ai --record-trace
    run.jsonl.gz` and replayed with `--headless --replay-trace run.jsonl.gz`. With
    `GLITCHYGAMES_CRT_POWER_ON=on`: exit 1, `Replay diverged at frame 0: length recording pump count
    expected 1, got 2`. Without it: matched 90 frames.
  - `--crt-power-on on --replay-trace run.jsonl.gz`: exit 64, `Cannot play the CRT power-on sequence
    with --replay-trace`.
  - With the variable and `--record-trace`: the run was accepted, and its recording replayed and
    matched (90 frames), so only a replay under the variable is shown to break.
- **Status**: Open
- **Priority**: Medium. A player who sets the variable breaks every replay, `--audit` and `verify`
  with a message that does not name the cause; a mirror inherits the variable.
- **Root Cause**: `_refuse_a_forced_power_on_during_a_run`
  (`src/glitchygames/engine/game_engine.py:2976`) reads only the parsed option (2986), while
  `_power_on_plays` (4054) resolves the variable (`resolve_mode`,
  `src/glitchygames/crt_power_on.py:66`) and `should_play` (`src/glitchygames/crt_power_on.py:94`)
  returns True for `on` before it looks at the replay options.
- **Test gap**: `tests/sdl_defaults.py` sets the variable to `off` for every test, and the refusal's
  tests give the option, not the variable.
- **Solution**: Not chosen. Options, all unproven:
  - Refuse the resolved mode (option or variable), naming where it came from.
  - Let a replay, recording, audit or rebaseline force `off` for a value that came from the
    variable, with a warning.
- **Known limits**: The variable is not recorded. Only `on` is affected; `auto` is off in a replay
  and recording.
- **Sweep**: Covered: the power-on's other modes, the recorded run. Read: `resolve_mode` is the only
  reader of the variable (`src/glitchygames/crt_power_on.py:79`). Not covered: other variables a
  mirror inherits.
- **Related**: [No real
  stimulus](../plans/lucid-circuit-4b-mirror.md#no-real-stimulus-the-owner-2026-11-24) in the
  mirror's plan.
- **Reporter**: The mirror game's hardware inventory, the coordinator
- **Date Reported**: 2026-11-24
- **Files**: `src/glitchygames/engine/game_engine.py`, `src/glitchygames/crt_power_on.py`
