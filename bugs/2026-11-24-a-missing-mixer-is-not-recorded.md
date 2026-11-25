# A Mixer Missing Live Is Not Recorded

- **Description**: Live without a mixer (no audio device, a driver that can't start), a play gives a
  silent handle whose `is_playing` is False. A headless replay always has the dummy mixer, so the
  same play answers True, and a game that branches on it diverges.
- **Reproduction**: Reproduced 2026-11-24 at `5006bcb6` (macOS arm64, Python 3.15.1, pygame-ce
  2.5.8, SDL 2.32.10) in child processes on the dummy drivers, with `HOME`, the sound cache root and
  the AI install root in a scratch folder.
  - The game is a throwaway scene of one 4x4 sprite that quits itself at frame 90 and moves the
    sprite when the branch is taken; it is recorded with `--headless --no-ai --record-trace
    run.jsonl.gz` and replayed with `--headless --replay-trace run.jsonl.gz`. It plays a library
    sound at frame 5 and moves 1 px per frame `is_playing`. Recorded with `SDL_VIDEODRIVER=dummy
    SDL_AUDIODRIVER=nosuch --no-ai` and no `--headless` (`Audio unavailable, running silently`),
    replayed `--headless`: exit 1, `Replay diverged at frame 4: sprite Mover#0 rect expected [0, 0,
    4, 4], got [1, 0, 4, 4]`.
  - The same with a live voice: `Replay diverged at frame 4`, the same difference.
- **Status**: Open
- **Priority**: Low. A recording made on a machine with no sound, with a game that branches on a
  handle; none of the games does today.
- **Root Cause**: The voice table asks `pygame.mixer.get_init()` at play time
  (`src/glitchygames/audio/voices.py:1551`), the live pool at `src/glitchygames/audio/live.py:464`,
  the live engine at `src/glitchygames/audio/engine.py:1000`; whether the mixer ran is not in the
  header and no door gives it.
- **Test gap**: No test records without a mixer and replays with one.
- **Solution**: Not chosen. Options, all unproven:
  - Record whether the mixer ran, and replay with a table that answers as it did.
  - Make what the game sees independent of the mixer: the voice table goes on silent (time and state
    as if heard), as it already does for a muted context.
- **Known limits**: Reproduced by naming an audio driver that does not exist; a device lost mid-run
  was not tried. The inverse (mixer live, none in the replay) needs a machine whose dummy mixer
  fails.
- **Sweep**: Covered: the three places above. `src/glitchygames/audio/voices.py` reads `get_init()`
  in 8 other places (338-1163), which set channels and were not traced to what a game sees.
- **Related**: [No real
  stimulus](../plans/lucid-circuit-4b-mirror.md#no-real-stimulus-the-owner-2026-11-24) in the
  mirror's plan.
- **Reporter**: The mirror game's hardware inventory, the coordinator
- **Date Reported**: 2026-11-24
- **Files**: `src/glitchygames/audio/voices.py`, `src/glitchygames/audio/live.py`,
  `src/glitchygames/audio/engine.py`
