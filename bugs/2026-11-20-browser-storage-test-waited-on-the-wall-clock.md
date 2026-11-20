# The Browser Storage Tests Waited on the Wall Clock

- **Description**: `tests/test_browser_storage.py` (#238) failed once under pytest-randomly with seed 4023912552 (reported by the coordinating session, 2026-11-20): a write-back was still pending when the assertions ran.
- **Status**: Fixed (2026-11-20, branch `fix/bug-sweep-2026-11-20`)
- **Priority**: Low (test only)
- **Root Cause**: The stand-in `FS.syncfs` finished after `call_later(0.01)`, `settle()` slept 20 x 0.01 s of real time, and the "requests while a flush runs" test relied on real time passing between requests. Under load the event loop could run late, so the assertions saw a pass still pending. The project's rule: wall-clock timings never belong in the normal suite.
- **Test gap**: The stand-in modelled the duration of a write-back, which the contract (`FS.syncfs(populate, callback)`: asynchronous, callback called once, JS null on success) does not give.
- **Solution**: `StandInFileSystem.syncfs` only records the callback; the test finishes write-backs with `finish_one()` (the callback runs through `loop.call_soon`). `settle()` yields `asyncio.sleep(0)`, finishing pending write-backs, until nothing is scheduled, running or pending, and fails after 1000 turns. The "more requests while a pass runs" test makes its requests while a write-back is unfinished, asserts none started, then finishes it and asserts exactly one more pass and never more than one in flight.
- **Verified**: a planted flush-per-request defect in `browser/browser_storage.py` fails two of the three tests (10 and 5 write-backs where 1 is required); 200 consecutive runs of the file pass. Not reproduced: the original flake did not fail in 25 runs of the old file with four busy-loop processes running, so its failure is shown by reasoning from the code, not by a measurement.
- **Reporter**: The coordinating session
- **Date Reported**: 2026-11-20
- **Files**: `tests/test_browser_storage.py`
