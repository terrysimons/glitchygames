# A Save That Failed to Write Live Always Succeeds in a Replay

- **Description**: Live, a save to a full disk or a folder that can't be written raises `OSError`. A
  replay's `MemorySaveManager` never fails, so a game that handles the error goes the other way.
- **Reproduction**: Reproduced 2026-11-24 at `5006bcb6` (macOS arm64, Python 3.15.1, pygame-ce
  2.5.8, SDL 2.32.10) in child processes on the dummy drivers, with `HOME`, the sound cache root and
  the AI install root in a scratch folder.
  - The game is a throwaway scene of one 4x4 sprite that quits itself at frame 90 and moves the
    sprite when the branch is taken; it is recorded with `--headless --no-ai --record-trace
    run.jsonl.gz` and replayed with `--headless --replay-trace run.jsonl.gz`. At frame 10 it saves
    to a store whose folder is read-only, and moves 50 px on `OSError`: exit 1, `Replay diverged at
    frame 9: sprite Mover#0 rect expected [50, 0, 4, 4], got [0, 0, 4, 4]`.
  - When the game does not catch it, the live run ends with exit 70 at frame 10, and its recording,
    9 frames, replays and matches: the crash is not shown by the replay.
- **Status**: Open
- **Priority**: Low (no game catches it today). It hides the crash a player reports.
- **Root Cause**: `DiskSaveManager._write_slot` (`src/glitchygames/state/manager.py:630`, the write
  at 643) may raise; `MemorySaveManager._write_slot` (`src/glitchygames/state/sandbox.py:182`)
  cannot, and the header and the records hold only what was opened and read.
- **Test gap**: The sandbox's tests compare reads, unreadable slots included, with a disk store;
  none makes a write fail.
- **Solution**: Not chosen. Options, all unproven:
  - Record each failed write (its error) with its call, and raise it in the replay.
  - Mark the run as ended by a save error, so the replay says so.
- **Known limits**: A slow or partly written save was not tried. Reads that fail are recorded (an
  unreadable slot).
- **Sweep**: Covered: `save` and, by reading, `delete` (`src/glitchygames/state/manager.py`,
  `_delete_slot`), which has the same shape. High scores
  (`src/glitchygames/state/high_scores.py:149`) save through it and do not catch `OSError`.
- **Related**: [No real
  stimulus](../plans/lucid-circuit-4b-mirror.md#no-real-stimulus-the-owner-2026-11-24) in the
  mirror's plan.
- **Reporter**: The mirror game's hardware inventory, the coordinator
- **Date Reported**: 2026-11-24
- **Files**: `src/glitchygames/state/manager.py`, `src/glitchygames/state/sandbox.py`,
  `src/glitchygames/state/high_scores.py`
