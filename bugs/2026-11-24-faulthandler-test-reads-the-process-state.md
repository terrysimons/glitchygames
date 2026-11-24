# A Faulthandler Test Fails When an Earlier Test on Its Worker Left Faulthandler Off

- **Description**: On 2026-11-24 CircleCI's Windows job 5309 (#293, `ci/format-check-really-checks`,
  head `b75082bb`) failed one test of 31,196:
  `tests/engine/test_engine_fatal_signals.py::test_an_enabled_faulthandler_is_left_as_it_is`, at
  its first assert, `assert faulthandler.is_enabled()` with `False` (line 165). Every other job of
  the run passed. #293's change (a `format-check` nox session, its CI step and its tests) does not
  touch faulthandler or the engine.
- **Status**: Open. Not reproduced; the mechanism is a hypothesis.
- **Priority**: Medium (a red required check on an unrelated PR; the split CI job cannot rerun one
  machine's failed tests).
- **Root Cause**: Of the test: it asserts on process-wide state it does not own. It expects
  faulthandler to be on because pytest's faulthandler plugin turns it on at configure, so any
  earlier test on the same worker that leaves faulthandler off fails it. Its sibling
  (`test_each_fatal_signal_goes_back_to_its_default_then_faulthandler_reports_it`) patches
  `faulthandler.is_enabled` instead. Of the state: unverified. No test on main calls
  `faulthandler.disable()` (`git grep` on `13b208fa`). A suspect is a test that runs pytest
  in-process (`pytester.runpytest_inprocess`: `tests/test_ci_config.py`,
  `tests/test_circleci_test_split.py`, `tests/replay/test_replay_plugin.py`): the inner session's
  `_pytest.faulthandler.pytest_unconfigure` (pytest 9.1.1) calls `faulthandler.disable()` and turns
  it back on only on the stderr descriptor it saved at configure, and only if faulthandler was on
  then. On macOS, `tests/test_circleci_test_split.py` followed by the test on one worker passed
  (86 passed); Windows was not tried. Why `--dist worksteal` (#291) would expose it: the tests a
  worker runs before this one now change from run to run.
- **Test gap**: Nothing checks that a test leaves faulthandler as it found it, so whichever test
  turns it off goes unnamed, and the failure lands on an innocent test that reads the state.
- **Solution**: Not chosen. Recommended: (1) the test patches `faulthandler.is_enabled` to `True`
  as its sibling patches it to `False`, so it tests `report_fatal_signals_with_faulthandler`'s
  branch, not the worker's history; (2) the invariant that catches the class: an autouse check in
  `tests/harness.py` that faulthandler is still enabled after each test, failing the test that
  turned it off. That check also finds the real culprit on its first Windows run.
- **Known limits**: Seen once in the 44 Windows jobs of the last 60 pipelines; CircleCI's
  flaky-test list does not hold it.
- **Sweep**: Not done yet: other tests that assert on process-wide state set by pytest or a plugin
  (signal handlers, `sys.stderr`, warnings filters, the logging root) without setting it themselves.
- **Tests**: None yet.
- **Reporter**: The coordinator (Ledger), from #293's CI.
- **Date Reported**: 2026-11-24
- **Files**: `tests/engine/test_engine_fatal_signals.py`,
  `src/glitchygames/engine/game_engine.py` (`report_fatal_signals_with_faulthandler`, lines
  292-330), `tests/harness.py`; pytest's `_pytest/faulthandler.py`.
