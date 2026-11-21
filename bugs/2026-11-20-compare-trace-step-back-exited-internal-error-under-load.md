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
- **Ruled out (2026-11-20)**: CPU load alone. The test alone (`-n 0`), looped for 18 minutes with
  32 busy-loop processes (two per core, load average 114-134), passed 110 of 110 on `cocoa` and
  109 of 109 on `dummy` (unloaded control: 25 of 25 on each). The failure happened only in a
  full-suite run under `-n auto` (many workers and child processes at once), as did the other
  session's process-stop flake (80 of 80 under CPU load alone).
- **A candidate the code shows**: the test's `watched_replay` answers each viewer wait (start
  screen, paused) with the next of its `keys`; the restarted run is given one. A wait after the
  last key failed the helper's own `assert` inside `engine.start()`, which the engine reports as
  `INTERNAL_ERROR`: exactly the 70 seen, after frames 4 and 5. So one more viewer wait than the test
  expects would explain it; not shown.
- **Done (the diagnosis)**: a test callback that runs inside a game's run is wrapped by
  `tests/replay/replay_helpers.py`'s `failing_the_test`: its failure becomes `pytest.fail`, whose
  exception is a `BaseException` the engine's crash boundary (which catches `Exception`) passes
  through, so the test fails at once with the callback's message ("a test callback failed inside
  the run (wait): AssertionError: the replay waited for the viewer N times, but only K keys were
  given"), never as the engine's 70. Checked with planted runs given too few keys, in both helpers
  below.
- **The class, swept** (test callbacks run inside a game's run whose failure the engine would
  report as its own exit status; `side_effect` callbacks with a check, in test files that run an
  engine, then each helper's indirect callbacks):
  - Uncovered, now wrapped: `test_compare_trace.py`'s `watched_replay` (viewer sleeps and flip),
    `live_play` (flip) and `connect_once_the_listener_is_gone` (the frame stream's connect);
    `test_gameplay_replay.py`'s `FakeMeasuredClock` sleeps, which run `press_keys_while_held`'s
    key presses and its callers' `before_each_press` (used by `test_gameplay_replay.py`,
    `tests/engine/test_game_engine.py` and `tests/replay/test_playback_scope.py`).
  - Covered (no check that can fail): `tests/replay/test_viewer.py`'s fake sleeps (not inside an
    engine run), and the `side_effect` lambdas that only record or read a value.
- **Next step**: on the next occurrence, the test names its own failure if it was a callback's;
  otherwise keep the run's log (the comparison's `cocoa/junit.xml` and
  `gw*.jsonl` under `test-results/driver-comparison/nox/`), and find where the watched replay's
  70 came from; reproduce under load (for example several `-n auto` runs at once) before any fix.
- **Reporter**: Claude (session 21f7657c), from its own push
- **Date Reported**: 2026-11-20
- **Files**: `tests/replay/tools/test_compare_trace.py`, `src/glitchygames/replay/tools/compare.py`
