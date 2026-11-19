# The AI Console's History File Could Be Read Part Written

- **Description**: `AiConsole._write_history` rewrote the history file in place (`Path.write_text`: truncate, then write), so between the truncate and the data the file existed and was empty. CircleCI's Windows job 3672 (the zombies branch, `f7a42676`) failed `tests/test_ai_console.py::test_cancelling_stops_listening_at_once` with `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`: the test waits for the file to exist, then reads it, and on a slow disk read it empty. A crash in that moment would also have lost every earlier record.
- **Status**: Fixed (2026-11-17, branch `chore/keep-memory-triage-records`)
- **Priority**: Low (a flaky test on slow disks; the history is a convenience)
- **Root Cause**: an in-place rewrite of the file's only copy; the console's own reads run on the same worker, so only an outside reader (a test, a person, a crash) could see the gap
- **Test gap**: the tests read the history only after the worker had finished on fast disks; nothing read it mid-write
- **Solution**: the record is written aside, then moved into place (`output_files.write_aside_then_replace`), so the file is only ever seen whole
- **Tests**: `tests/test_ai_console.py::test_a_history_file_is_only_ever_seen_whole` reads the history from inside every write to the history folder: it found the file empty before the fix. The CI failure reproduced locally by slowing the write (truncate, pause 0.2 s, write): 2 runs out of 2 failed before the fix and 2 out of 2 passed after it, `test_history_is_kept_searched_bounded_and_forgotten` included (it waits the same way).
- **Siblings** (files rewritten in place, swept in `src/glitchygames`): `replay/tools/measure.py` rewrites the pending replay ledger, its only copy of unpublished rows, in place (not fixed: a crash or a full disk mid-write would lose them). The other in-place writes create fresh outputs (`replay/audit.py`, `recording_metrics.py`'s row files, `performance_pages.py`, `build_info.py`'s stamp, `listening/renders.py`'s index, `replay/tools/settings.py`'s `.gitignore`, the sprite client's outputs).
- **Reporter**: Claude
- **Date Reported**: 2026-11-17
- **Files**: `src/glitchygames/ai_console.py`, `tests/test_ai_console.py`
