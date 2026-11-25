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
- **Third failure**: 2026-11-24, a local pre-push gate on macOS (`feature/midi-devices` at `dd6391fb`,
  shuffled, seed 1971020982, worker `gw10`), again `TimeoutExpired` after 60 s.
- **Status**: Fixed on `fix/process-probe-signal-race`. The mechanism is reproduced; that the three
  failures above were it is inferred from the fingerprint (none recorded the child's state).
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
- **Root Cause**: Python runs a signal's handler between bytecodes or when a system call is
  interrupted. A SIGTERM that lands after the last check and before `time.sleep` enters its system
  call interrupts nothing, so the child acts on it only when its 60 s sleep ends, as the test's own
  60 s timeout expires. Measured on this Mac: with the signal sent 0 to 600 microseconds after
  `ready`, 10 of 3,000 children slept their whole 1 s sleep first. A signal lost while `ready` is
  being written was tested and not seen (0 of 200). The rate in the real test was not measured.
- **Test gap**: the timeout equalled the child's sleep, and no test sent a signal that interrupts
  no sleep.
- **Solution**: A child that handles a signal waits in 0.05 s sleeps
  (`tests/stoppable_children.py`), so such a signal is acted on at the next step: the worst of
  1,500 was 55 ms, where one long sleep took 1,005 ms.
- **Known limits**: a signal in the gap is acted on up to 0.05 s late. Not chosen: a longer timeout
  (it passes but costs 60 s), and `signal.set_wakeup_fd` (it removes the gap; more machinery than
  a test child needs).
- **Sweep**: the children that install a Python handler and then sleep were this one and two in
  `tests/test_process.py` (`child_reporting_its_signal`, `CHILD_THAT_SAYS_IT_WAS_TERMINATED`); all
  three are changed. A child that ignores a signal or keeps its default action has no handler to
  delay. Not covered: children that end through SIGINT's `KeyboardInterrupt` (a nested pytest run
  sleeping in a test), which is a Python handler too; `stop_command` escalates past it.
- **Tests**: `test_a_child_acts_on_a_signal_that_interrupts_no_sleep` (three cases) and
  `test_the_probed_child_acts_on_a_signal_that_interrupts_no_sleep`. Another thread takes the
  signal, so the main thread's sleep is never interrupted: the gap, every time. All four fail with
  one long sleep.
- **Reporter**: The coordinator (Ledger), from CircleCI jobs 5603 and 5687.
- **Date Reported**: 2026-11-24
- **Files**: `tests/stoppable_children.py`, `tests/test_process.py`,
  `tests/test_reproduce_process_stop_under_load.py` (`probed_run`,
  `PARENT_TERMINATING_ITS_CHILD`), `scripts/reproduce_process_stop_under_load.py`,
  `scripts/process_stop_probe/sitecustomize.py`. Related:
  `bugs/2026-11-20-process-stop-tests-failed-under-load.md`.
