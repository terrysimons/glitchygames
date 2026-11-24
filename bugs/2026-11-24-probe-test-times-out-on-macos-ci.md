# The Process-Stop Probe Test Times Out on CircleCI's macOS Job

- **Description**: `tests/test_reproduce_process_stop_under_load.py::test_the_probe_does_nothing_without_its_log_variable`
  failed twice on 2026-11-24 in CircleCI's `test-python-3-15-macos` job, both times with
  `subprocess.TimeoutExpired: ... timed out after 60 seconds` from `probed_run` (line 106), after
  60.057 s and 60.052 s:
  - job 5603, #301's first run (`fix/sprite-saves-are-atomic` at `1d2f338b`, worker `gw1`);
  - job 5687, main's own run at `9e5ed33e` (pipeline 1502, worker `gw0`), beside the Mr. Muncher
    golden worker crash.
  Neither change touches the probe, the reproducer or process stopping. #301's next run, on the
  same code merged with main (`d34c5d70`), passed.
- **Status**: Open. Not reproduced; cause unknown.
- **Priority**: Medium (it fails the macOS job, CI's bottleneck, and costs a full run).
- **What the test runs**: `probed_run` starts `sys.executable -c PARENT_TERMINATING_ITS_CHILD`
  with `PYTHONPATH` set to the probe's folder (`scripts/process_stop_probe/`) and no
  `PROCESS_STOP_PROBE_LOG`, through `run_command(..., timeout_seconds=60)`. The parent starts a
  child that installs a SIGTERM handler (`sys.exit(0)`), writes the `ready` file and sleeps 60 s;
  the parent busy-waits for `ready`, sends `terminate()` and waits for the child.
- **Fingerprint (not a cause)**: both failures took the timeout to within 60 ms. The child sleeps
  exactly as long as the timeout, so a child that never acts on its SIGTERM would keep the parent
  waiting just past 60 s, which matches. A parent that never sees `ready` would spin until the
  timeout too. A slow machine alone would not land this close to 60 s twice. Unverified: which
  process was still alive is not recorded.
- **Root Cause**: Unknown. Suspects to check, none measured: the SIGTERM lost or not acted on in
  the child under load; the parent's spin starving the child on a loaded runner; interpreter
  start-up under coverage in the `.nox` environment.
- **Test gap**: the timeout equals the child's sleep, so a lost signal and a slow start fail the
  same way, and the failure says nothing about the state at the timeout (whether `ready` existed,
  whether the child was alive, which signal it got).
- **Solution**: Not chosen. Next steps: (1) make the failure report whether `ready` existed and
  the child's state when the timeout hit; (2) give the child a sleep well past the timeout, so a
  lost signal and slowness tell apart; (3) reproduce under a load window agreed with the owner
  (no CPU burners while other sessions test).
- **Sweep**: Not done yet: other tests whose child sleeps as long as their own timeout.
- **Tests**: None yet.
- **Reporter**: The coordinator (Ledger), from CircleCI jobs 5603 and 5687.
- **Date Reported**: 2026-11-24
- **Files**: `tests/test_reproduce_process_stop_under_load.py` (`probed_run`,
  `PARENT_TERMINATING_ITS_CHILD`), `scripts/reproduce_process_stop_under_load.py`,
  `scripts/process_stop_probe/sitecustomize.py`. Related:
  `bugs/2026-11-20-process-stop-tests-failed-under-load.md`.
