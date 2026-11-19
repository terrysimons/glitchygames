# Orphaned Test Processes: Stop Child Test Runs Like Ctrl-C, and Catch What Tests Leave Running

**Status:** DONE (2026-11-13, branch `fix/orphaned-test-processes`: all six tasks; Tasks 4 and
5 in one commit). Decisions made while building it, beyond the text below: the guard keeps the
`Popen` objects, not pids (a reused pid cannot fool `poll()`); a zombie the test never waited for
is reaped by the guard and not reported (nothing runs); the guard is listed with the harness's
process-state fixtures (`PROCESS_STATE_AUTOUSE_FIXTURES`), not in `engine_service_resets`; each
child run's `--basetemp` is under the system's temporary directory, not the synced checkout; the
controller sweeps at its terminal summary in every run, comparing or not, and lists without
failing. Measured afterwards (BUGS.md #275): SIGTERM to the controller alone also leaves the
tool (the triage below found nothing there).

**Bug:** BUGS.md #275 (planned as #273, which another bug took first). Same family as #266, whose
cause was "not reproduced"; this triage reproduced it.

## The triage (2026-10-30, re-checked against main 3ab23ff0 on 2026-11-11)

Two processes were found orphaned after a local suite run: a `glitchygames record-trace` tool
(parent PID 1, its own process group) and the sleeping game it started, both from
`tests/replay/tools/test_command_crash_boundary.py::test_a_signal_stops_and_reaps_the_commands_child_and_exits_with_its_code`.

Reproduction (a `-n 2` pytest of that test, stopped mid-test the ways the suite's own tooling
can stop it; 4 trials each):

| How the run was stopped | When | Left running |
|---|---|---|
| `process.stop_command(run)`: SIGTERM to its group (what `DriverComparison.stop_native_run` does) | tool started, not yet signalled | tool + game, 4 of 4 |
| SIGKILL to the xdist worker (crash, OOM) | tool started | tool + game, 4 of 4 |
| SIGINT to the run's group (Ctrl-C) | tool started | nothing, 4 of 4 |
| SIGINT to the run's group | as the game wrote its pid | the game alone, 4 of 4 |
| SIGTERM to the controller only | either | nothing |

Normal runs never leak (51 runs: alone, `-n auto`, under 16 busy processes, both drivers).

**Root cause.** pytest and its xdist workers have no SIGTERM handler, so SIGTERM kills a worker
on the spot: no `finally`, no fixture teardown. `stop_command` sends SIGTERM to the child run's
process group. A test that started its own child with `start_command` gave that child a
session of its own (`start_new_session=True`), so the group SIGTERM misses it, and the test's
cleanup that would have stopped it never runs. `stop_native_run` runs when the dummy run is
interrupted, when the native run passes `NATIVE_RUN_TIMEOUT_SECONDS` (3600 s), and in
`pytest_unconfigure`; image re-runs are stopped the same way after `IMAGE_RUN_TIMEOUT_SECONDS`.
`stop_command`'s docstring ("ends that child with every process it started") is untrue for a
grandchild with a session of its own.

**Second defect (the test's own cleanup).** Its `finally` SIGKILLs the tool alone. A SIGKILLed
tool cannot stop its game, and the game is killed only when the test already read `child.pid`;
a KeyboardInterrupt landing in `wait_for_file` after the game wrote its pid leaves the game
running (the fourth row). Killing the tool's whole group instead took that row to 0 (3 of 3).

#266's orphan (a `never_ending_game.py --measure` child that ran ten days and held the Mac's
audio) fits the same shape: a worker killed without unwinding. #266 gave that one stand-in a
600-second give-up; nothing stops the next one.

## The fix (recommended: root cause plus complements)

1. **Stop child pytest runs as Ctrl-C does, then escalate** (root cause).
   `process.stop_command` gains `first_signal: int = signal.SIGTERM` (keyword-only), sent to the
   group first; after `STOP_GRACE_SECONDS` a still-running group gets SIGTERM (when the first was
   SIGINT), then SIGKILL after another grace. `DriverComparison` (the native run, its stop on
   interrupt, timeout and unconfigure, and the image re-runs) passes `first_signal=signal.SIGINT`:
   pytest and xdist turn it into an orderly KeyboardInterrupt in every worker, so every test's
   `finally` and fixture teardown runs. The engine's caller (`replay/tools/compare.py`, OLD's
   child, a game that installs `exit_on_signal`) keeps SIGTERM. Windows has no group SIGINT
   here: it stays terminate-then-kill, documented. The docstring says what the group signal does
   and does not reach.
2. **The test ends the tool's whole group.** In
   `test_a_signal_stops_and_reaps_the_commands_child_and_exits_with_its_code`, the `finally`
   calls `stop_command(process=running)` (the tool gets the chance to reap its game, then the
   group is killed), and `start_command` moves inside the `try`, so no interrupt lands between
   the start and the cleanup. A sweep of the suite for the same shape (a test that starts a
   child and cleans up only that child) is part of this task; each one found is fixed the same
   way and listed in the BUGS entry.
3. **A harness guard: a test that leaves a process running fails.** An autouse fixture in
   `tests/child_process_guard.py`, joined to `engine_service_resets` in `tests/harness.py`.
   At session start it wraps `subprocess.Popen.__init__` to record each child's pid against the
   running test (one list append per child; most tests start none). At teardown, only for a
   test that started a child, one `ps -A -ww -o pid=,ppid=,pgid=,command=` call finds each such
   pid still running, every process in its process group, and every descendant of either; each
   is killed (its group, SIGKILL), reaped where it is ours, and the test errors naming each
   command line. Zombies of ours count (nobody else reaps them). POSIX only: on Windows the
   guard records nothing and checks nothing (said in its docstring). Limit: a grandchild that
   both left the group (`setsid`) and lost its parent is not found; item 4 catches what names
   the run's temporary directory.
4. **A session sweep for hard deaths** (SIGKILL, crash, `os._exit`: nothing in-process runs).
   `DriverComparison` gives the native run and each image re-run an explicit `--basetemp` under
   its output directory; when that run ends or is stopped, every process whose command line
   names that directory is killed (its group) and listed in the summary
   (`left running by the cocoa run: ...`). The dummy controller sweeps its own basetemp in
   `pytest_unconfigure` the same way. One `ps` per run.

**Shortcuts considered, not recommended alone:** start the test's tool without a session of its
own (it then dies with the group SIGTERM: covers only that path and still skips the test's
cleanup); or install a SIGTERM-to-KeyboardInterrupt handler in workers (conflicts with the
engine's `install_exit_on_signal_handlers`, which takes SIGTERM only while it is SIG_DFL, and
with `tests/signal_handlers.py`).

## The triage tools (staged, per the owner's rule)

- `scripts/reproduce_orphaned_test_processes.py MODE WHEN` (from the triage's
  `simulate_stop.py`): runs a `-n 2` pytest of the crash-boundary test under its own TMPDIR,
  stops it mid-test (`stop-command`, `sigint-group`, `sigterm-leader`, `sigkill-worker`; at
  `tool` or `game`), reports the survivors by command line, kills them. Each row of the table
  above is one invocation. Its test drives it with a stand-in test, so it needs no game.
- The guard prototype becomes item 3 itself.

## Tasks

Each task is TDD (the failing test first), lint before tests, one commit each.

1. **`stop_command(first_signal=...)`**: `tests/test_process.py`: a group whose leader ignores
   nothing gets SIGINT first and ends (a child that records the signal it got); a leader that
   ignores SIGINT gets SIGTERM after the grace, then SIGKILL; the default stays SIGTERM (the
   existing tests); the Windows branch unchanged (the stand-in child tests). Docstring corrected.
2. **`DriverComparison` stops with SIGINT**: the native run's three stop paths and the image
   re-runs pass `first_signal=signal.SIGINT`. Regression test (the triage's reproduction made
   automatic): a child pytest of a stand-in test that starts a session child and waits, stopped
   through `DriverComparison.stop_native_run`'s path; no process naming its TMPDIR survives.
   Before the change it leaves two.
3. **The crash-boundary test's cleanup**, and the sweep for the same shape (item 2).
4. **The guard** (item 3): `tests/test_child_process_guard.py` (a test leaving a session child
   and its child errors and both are gone; a test whose children all ended passes; a test that
   started nothing calls no `ps`). The whole suite passes under it, or each leak it finds is a
   fixed test listed in the BUGS entry.
5. **The sweep** (item 4), with its test (a process naming a run's basetemp is killed and listed).
6. **The reproducer script** and its test; BUGS.md #275 (and a pointer from #266); CLAUDE.md's
   Testing Guidelines (the guard, the SIGINT stop) and `docs/quality/driver_comparison.md`.

## Open questions for the owner

- The guard fails the test (an error at teardown). Should it also fail when a test's child is
  still running but the test deliberately hands it to a fixture of wider scope? None is known
  today; an opt-out marker would be added only when one appears.
