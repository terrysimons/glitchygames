# A Replayed Drop of a PNG Writes a TOML Beside It and Reads a File Not Recorded

- **Description**: Dropping a PNG on Bitmappy's canvas converts it and writes `NAME.toml` beside it.
  A replay of that session does it again, over whatever is there now. Only the path is recorded, so
  the replay reads the file's contents of today, and diverges when the file changed or is gone.
- **Reproduction**: Reproduced 2026-11-24 at `5006bcb6` (macOS arm64, Python 3.15.1, pygame-ce
  2.5.8, SDL 2.32.10) in child processes on the dummy drivers, with `HOME`, the sound cache root and
  the AI install root in a scratch folder.
  - Bitmappy recorded with a `DROPFILE` of a PNG at (100, 100) posted as external input (`--headless
    --no-ai --record-trace`); the TOML it wrote was moved away. `bitmappy --headless --replay-trace`
    (nothing patched): matched 220 frames, and wrote the TOML beside the PNG again.
  - The PNG moved away, same replay: exit 1, `Replay diverged at frame 59: sprite FilmStripSprite#1
    present expected True, got False`.
- **Status**: Open
- **Priority**: High. A replay overwrites a file of the player's, whole or nothing but without
  asking; a recording can't be replayed elsewhere.
- **Root Cause**: `FileIOManager.on_drop_file_event`
  (`src/apps/bitmappy/src/bitmappy/file_io.py:68`, its `stat` at 81) and `_try_canvas_drop` act on
  the path in the event with no door; the write is `write_text_whole` at
  `src/apps/bitmappy/src/bitmappy/file_io.py:396`, read back at 413; the image is loaded at 253 and
  309.
- **Test gap**: The drop tests call the handlers live; no test records a drop and replays it with
  the file changed, or checks that a replay leaves the folder as it was.
- **Solution**: Not chosen. Options, all unproven:
  - A files door: a replay serves the recorded contents (by hash, with the bytes) and drops writes.
  - Refuse the write in a replay and read the recorded contents only.
- **Known limits**: Recording contents has a size and privacy cost. The write is to the dropped
  file's folder, so nothing outside it is touched.
- **Sweep**: Covered: the canvas drop. Read, not run: a drop on the film strip loads the image
  (`src/apps/bitmappy/src/bitmappy/film_strip_sprite.py:463`, 668), and a dropped TOML is loaded
  (`_load_converted_sprite`). The dialogs are
  bugs/2026-11-24-bitmappy-dialogs-touch-real-files-in-a-replay.md.
- **Related**: [No real
  stimulus](../plans/lucid-circuit-4b-mirror.md#no-real-stimulus-the-owner-2026-11-24) in the
  mirror's plan.
- **Reporter**: The mirror game's hardware inventory, the coordinator
- **Date Reported**: 2026-11-24
- **Files**: `src/apps/bitmappy/src/bitmappy/file_io.py`,
  `src/apps/bitmappy/src/bitmappy/film_strip_sprite.py`, `src/glitchygames/output_files.py`
