# Bitmappy's Save and Load Dialogs Read and Write Real Files in a Replay

- **Description**: Confirming Bitmappy's Save or Load dialog uses the file name typed, as it is on
  the machine that replays. A replay of a save writes the file again, and a replay of a load reads
  today's file or diverges.
- **Reproduction**: Reproduced 2026-11-24 at `5006bcb6` (macOS arm64, Python 3.15.1, pygame-ce
  2.5.8, SDL 2.32.10) in child processes on the dummy drivers, with `HOME`, the sound cache root and
  the AI install root in a scratch folder.
  - Bitmappy recorded (`--headless --no-ai --record-trace`) with external input: the Save menu,
    `a.toml`, Enter. Replayed unpatched in an empty folder: matched 220 frames, and `a.toml` was
    written there.
  - The same with the Load menu and an `a.toml` in the folder, replayed in an empty folder: exit 1,
    `Replay diverged at frame 129: sprite FilmStripSprite#1 present expected True, got False`.
- **Status**: Open
- **Priority**: High. A replay can overwrite the player's drawing with what was drawn when it was
  recorded.
- **Root Cause**: `SaveDialogScene.on_confirm_event` (`src/glitchygames/ui/dialogs.py:468`) and
  `LoadDialogScene.on_confirm_event` (`src/glitchygames/ui/dialogs.py:403`) call the canvas's
  `on_save_file_event` and `on_load_file_event`
  (`src/apps/bitmappy/src/bitmappy/animated_canvas.py:1260`, 1332), which write through
  `AnimatedSprite.save` (`src/glitchygames/sprites/animated.py:2028`, called at
  `src/apps/bitmappy/src/bitmappy/animated_canvas.py:1777` and through the serializer at 1299) and
  load with no door.
- **Test gap**: No test records a dialog's save and replays it in another folder; the saves door's
  tests cover game saves only.
- **Solution**: Not chosen. Options, all unproven:
  - A files door as for the PNG drop
    (bugs/2026-11-24-replayed-png-drop-writes-and-reads-real-files.md).
  - Refuse file writes in a replay, and serve recorded contents for loads.
- **Known limits**: Recorded loads of earlier recordings hold no contents. A failed save is shown in
  the editor, and is not recorded either.
- **Sweep**: Covered: the two dialogs of `src/glitchygames/ui/dialogs.py`. In the browser the files
  go through `src/glitchygames/user_files.py` (not run). Read: the AI manager's temporary TOML
  (`src/apps/bitmappy/src/bitmappy/ai_manager.py:370`), only with an AI answer.
- **Related**: [No real
  stimulus](../plans/lucid-circuit-4b-mirror.md#no-real-stimulus-the-owner-2026-11-24) in the
  mirror's plan.
- **Reporter**: The mirror game's hardware inventory, the coordinator
- **Date Reported**: 2026-11-24
- **Files**: `src/glitchygames/ui/dialogs.py`, `src/apps/bitmappy/src/bitmappy/animated_canvas.py`,
  `src/glitchygames/sprites/animated.py`
