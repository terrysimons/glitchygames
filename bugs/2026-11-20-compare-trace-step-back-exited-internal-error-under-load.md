# A Compare-Trace Step-Back Test Exited With INTERNAL_ERROR Once Under Load

- **Description**: the pre-push gate's driver comparison (`nox -s compare-drivers`, 2026-11-20,
  branch `fix/httpcore2-import-keyerror-triage` at `52549e08`, macOS, load average 40-66 from
  several sessions' gates) refused the push: on the `cocoa` run,
  `tests/replay/tools/test_compare_trace.py::test_a_step_back_across_a_pause_keeps_old_in_step`
  failed (15.3 s) with `assert <ExitCode.INTERNAL_ERROR: 70> == <ExitCode.SUCCESS: 0>` for its
  second watched replay (the restarted one), which presented frames 4 and 5 and then ended with 70.
  Both `dummy` runs passed it, and the comparison's own re-run of the test on `cocoa` passed
  ("not reproduced"); the reported frame difference is that failed run's last frame.
- **Status**: Open
- **Priority**: Low (one occurrence; a gate flake under heavy load)
- **What is known**: the branch changes no replay or compare code (a test plugin, a script, bug
  records). The restarted replay starts OLD's child replay and waits for its frame stream
  (`compare.CHILD_CONNECT_TIMEOUT_SECONDS`), so a heavily loaded machine is a plausible cause, but
  that is reasoning, not evidence: the junit record holds no captured log, so what returned 70 is
  not known.
- **Test gap**: the failure kept no log of the watched replay's exit, so its cause cannot be read
  after the fact.
- **Next step**: on the next occurrence, keep the run's log (the comparison's `cocoa/junit.xml` and
  `gw*.jsonl` under `test-results/driver-comparison/nox/`), and find where the watched replay's
  70 came from; reproduce under load (for example several `-n auto` runs at once) before any fix.
- **Reporter**: Claude (session 21f7657c), from its own push
- **Date Reported**: 2026-11-20
- **Files**: `tests/replay/tools/test_compare_trace.py`, `src/glitchygames/replay/tools/compare.py`
