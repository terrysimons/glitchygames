# Effects Tables Are Not Short Names

- **Description**: a version 1 sound file's `[effects.<name>]` table loads as one of the file's
  sounds (`load_sound_file(...).sounds['jump']`), and a path to it works
  (`audio.sound('sounds/sfx.toml#jump')`), but its name was not a short name:
  `audio.sound('jump')`, with the file in the scene's `SOUND_DIRECTORY`, raised
  `KeyError: "no sound named 'jump' in ..."`. The module docstring of
  `src/glitchygames/audio/assets.py` says an effects table is a sound effect "under a short name",
  and the loader refuses a name used by both a `[sounds.x]` and an `[effects.x]` table because "a
  short name names one". Found 2026-11-22 by the audio docs scrub (`docs/scrub-audio`), checking
  `docs/architecture/sound.md`'s "Short names and paths" against the code; reproduced with
  `ShortNameIndex` on a one-effect file. No game was affected: Zombies Ain't My Neighbors, the only
  game whose sound file has effects tables, asks for every sound by path.
- **Status**: Fixed (2026-11-22, `fix/effects-tables-are-short-names`)
- **Priority**: Low (nothing used the short name yet; any game that did would have failed at once)
- **Root Cause**: the short-name index reads a file's table names itself
  (`assets._table_names`), apart from the loader, and read only `[sounds.*]` (and a version 0
  file's `[recipes.*]`). When `[effects.*]` tables were added to the loader (sound migration,
  plans/2026-11-14-sound-migration.md), the index's own copy of the rule was not changed.
- **Test gap**: `tests/audio/test_assets.py::test_an_effects_table_in_a_sound_file_is_a_short_name`
  checked only that `load_sound_file` builds the effect, never that the index finds it, and
  nothing tied the index's names to the loader's.
- **Fix**: `_table_names` reads `[effects.*]` beside `[sounds.*]`, each name once (a name in both
  is the loader's to refuse, with its own message).
- **Regression tests** (each failed before the fix with the `KeyError` above):
  - `tests/audio/test_sound_names.py::test_an_effects_table_is_a_short_name` (the index);
  - `tests/audio/test_audio_engine.py::TestSceneDirectories::test_an_effects_table_is_asked_for_by_its_short_name`
    (`AudioEngine.sound`).
- **The class and its invariant**: a sound the loader makes from a file that its directory's index
  cannot find. `tests/audio/test_sound_names.py::test_every_sound_a_file_loads_is_a_short_name_for_it`
  holds every name in `load_sound_file(path).sounds` to be indexed for that file, for every sound
  file the games ship and the engine's fixtures (version 1 and version 0) and for a file with one
  table of every kind the loader reads (waves, instruments, sounds, effects). It failed before the
  fix for Zombies' own `sounds.toml` (`zap`, an effects table) and for that file (`jump`). A new
  table kind the loader turns into a sound fails it until the index reads it too.
- **Sweep** (every reader of a sound file's names):
  - Covered, through the loader's `sounds` mapping: the library's `path#name` lookup
    (`library.py`, `_entry_in`), `sound-render` and `sound-migrate`
    (`replay/tools/sound_tools.py`), the startup compile of `SOUNDS` and `sound-cache-fill`
    (both through `audio.sound`).
  - The index was the only reader with its own copy of the table rule.
  - Not checked: GG Sound Studio, outside this repository.
- **Reporter**: Claude (session 21f7657c)
- **Date Reported**: 2026-11-22
- **Files**: `src/glitchygames/audio/assets.py`, `tests/audio/test_sound_names.py`,
  `tests/audio/test_audio_engine.py`
