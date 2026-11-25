# A Faulthandler Test Fails When an Earlier Test on Its Worker Left Faulthandler Off

- **Description**: On 2026-11-24 CircleCI's Windows job 5309 (#293, `ci/format-check-really-checks`,
  head `b75082bb`) failed one test of 31,196:
  `tests/engine/test_engine_fatal_signals.py::test_an_enabled_faulthandler_is_left_as_it_is`, at
  its first assert, `assert faulthandler.is_enabled()` with `False` (line 165). Every other job of
  the run passed. #293's change (a `format-check` nox session, its CI step and its tests) does not
  touch faulthandler or the engine.
- **Second failure**: 2026-11-24, CircleCI's macOS job 5952, main's own run at `c72ec6d8`
  (shuffled, seed 1009600162, worker `gw1`), the same assert.
- **Status**: Fixed on `fix/faulthandler-left-off`. Reproduced: either of the leaking tests below,
  then this test, on one worker fails every time. That the two CI failures were this is inferred:
  in job 5952 all three leaking tests come before it in the report; their worker is not recorded.
- **Priority**: Medium (a red required check on an unrelated PR; the split CI job cannot rerun one
  machine's failed tests).
- **Root Cause**: Of the test: it asserted on process-wide state it does not own. Of the state:
  three tests of `tests/test_frame_fingerprints.py` (an image request without the fingerprints
  option, and an unreadable one, two cases) run pytest in process, ended by the usage error they
  check. It is raised in our plugin's `pytest_configure`, before pytest's own faulthandler plugin
  is configured (pytest 9.1.1), so that plugin has saved nothing; its `pytest_unconfigure` still
  calls `faulthandler.disable()`. Found by checking faulthandler after each of 748 tests of the
  files that run pytest inside a test: those three and no other left it off.
- **Test gap**: Nothing checked that a test leaves faulthandler as it found it, so the failure
  landed on an innocent test. Until something turned it on again, a crash on that worker printed
  no traceback.
- **Solution**: (1) those inner runs get `-p no:faulthandler` (the `inner_tests` fixture);
  (2) an autouse check in `tests/harness.py` (`tests/faulthandler_guard.py`) fails a test that
  leaves faulthandler off, by name, and turns it back on; (3) this test sets its own state.
- **Known limits**: the check turns faulthandler back on on the process's stderr, as Python does
  not say which stream it used. It sees faulthandler off, not on for another stream (an inner run
  that ends normally leaves it on its own).
- **Sweep**: the whole suite runs under the check. Not done: other process-wide state pytest or a
  plugin sets (`sys.stderr`, warnings filters, the logging root) read by a test that does not set
  it.
- **Tests**: `tests/test_faulthandler_guard.py`. With the check and without (1), exactly those three
  tests fail.
- **Reporter**: The coordinator (Ledger), from #293's CI.
- **Date Reported**: 2026-11-24
- **Files**: `tests/faulthandler_guard.py`, `tests/test_frame_fingerprints.py`,
  `tests/engine/test_engine_fatal_signals.py`,
  `src/glitchygames/engine/game_engine.py` (`report_fatal_signals_with_faulthandler`, lines
  292-330), `tests/harness.py`; pytest's `_pytest/faulthandler.py`.
