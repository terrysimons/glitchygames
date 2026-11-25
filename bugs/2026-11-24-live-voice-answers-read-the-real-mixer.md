# Live Voices Answer From the Real Mixer's Time, So a Replay Can Diverge

- **Description**: `LiveSoundHandle.is_playing` and `cancel()` (and `LiveStream.is_finished`,
  `set_pan`) depend on when the mixer drains a chunk. A headless replay runs uncapped, so the answer
  differs from the live run's. Library sounds (`SoundHandle`) follow the served `dt` and do not.
- **Reproduction**: Reproduced 2026-11-24 at `5006bcb6` (macOS arm64, Python 3.15.1, pygame-ce
  2.5.8, SDL 2.32.10) in child processes on the dummy drivers, with `HOME`, the sound cache root and
  the AI install root in a scratch folder.
  - The game is a throwaway scene of one 4x4 sprite that quits itself at frame 90 and moves the
    sprite when the branch is taken; it is recorded with `--headless --no-ai --record-trace
    run.jsonl.gz` and replayed with `--headless --replay-trace run.jsonl.gz`. It starts a live sine
    at frame 5 and calls `release()` at frame 20, moving 1 px on every frame `is_playing`: exit 1,
    `Replay diverged at frame 29: sprite Mover#0 rect expected [25, 0, 4, 4], got [26, 0, 4, 4]`.
  - The same, calling `cancel()` at frame 60 and moving 50 px when it answers True: exit 1, `Replay
    diverged at frame 59: sprite Mover#0 rect expected [0, 0, 4, 4], got [50, 0, 4, 4]`.
- **Status**: Open
- **Priority**: Low today: no game branches on them (Mr. Muncher calls `release()`, Clockwork Keep
  `cancel()`, both ignoring the answer). High for the mirror and for the first game that does.
- **Root Cause**: `LiveStream.is_playing` and `is_finished` (`src/glitchygames/audio/live.py:193`,
  202) read `Channel.get_busy()` while draining, and the fade that leads there is rendered as
  `update` (262) finds the queue empty. `LiveSoundHandle.is_playing`
  (`src/glitchygames/audio/live_instrument.py:467`), `set_pan` (548) and `cancel` (571) use them.
- **Test gap**: `tests/audio/test_live.py` covers the states, not a recorded run replayed at another
  speed.
- **Solution**: Not chosen. Options, all unproven:
  - Live voices end by played time (the served `dt`), as library voices do; the device is then only
    an output.
  - Record the answers per call and serve them in the replay.
- **Known limits**: `release()` and `stop()` answers do not depend on the mixer: they read states
  that only the game's own calls leave. (The inventory and the plan list them; `cancel()` is the
  one.) Run on the dummy mixer.
- **Sweep**: Covered: every use of `Channel.get_busy` and `is_finished` in
  `src/glitchygames/audio/live.py` and `live_instrument.py`. Read: `LiveAudio.update` frees a
  finished voice's channel (538), so whether a full pool steals or refuses a new voice
  (`take_channel`, 475, `ValueError`) also follows the mixer's time.
- **Related**: [No real
  stimulus](../plans/lucid-circuit-4b-mirror.md#no-real-stimulus-the-owner-2026-11-24) in the
  mirror's plan.
- **Reporter**: The mirror game's hardware inventory, the coordinator
- **Date Reported**: 2026-11-24
- **Files**: `src/glitchygames/audio/live.py`, `src/glitchygames/audio/live_instrument.py`
