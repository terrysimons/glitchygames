# The Memory Guard's Plugin Test Raced the Guard's Own Sampling Thread

- **Description**: `tests/test_memory_guard.py::test_the_plugin_stops_a_run_past_the_limit_naming_its_test` failed on CircleCI's Windows job (PR #249, job 4569) with `AssertionError: GLITCHYGAMES_TEST_RSS_LIMIT_MB: this process's resident memory (/proc/self/statm) reached 300 MiB, past the limit of 200 MiB, between tests; the run was stopped`. The test expects the stop to name `test_first`, the test running when the limit was first seen.
- **Status**: Fixed (2026-11-21, branch `fix/memory-guard-test-race`)
- **Priority**: Medium (a red CI job on an unrelated PR; the guard itself was right)
- **Root Cause**: The plugin starts the guard's sampling thread in `pytest_configure` (`tests/memory_guard.py`), sampling every 0.25 s (`SAMPLE_INTERVAL_SECONDS`). The test fakes `statm` at 300 MiB, over its 200 MiB limit from the start. When the inner run took more than 0.25 s between configure and `test_first` starting (a slow collection on a loaded Windows machine), the thread sampled first, with no test running, and stopped the run "between tests". That is the right report for memory over the limit before any test; the test, which claims to check the hooks' path, left the thread racing that path. The test couldn't slow the thread down: `ResidentMemoryGuard`'s `interval_seconds` defaulted to `SAMPLE_INTERVAL_SECONDS` when the class was defined, and `guard_from_environment` didn't pass it.
- **Reproduction**: the test's inner run with a conftest that sleeps 0.6 s in `pytest_collection_finish` failed 3 runs out of 3 with CI's exact message; without the sleep it passed.
- **Fix**: `guard_from_environment` passes `interval_seconds=SAMPLE_INTERVAL_SECONDS`, read when the guard is built, so a test can set it. The test sets it to an hour, so only the hooks' start check can stop the run. It keeps the 0.6 s collection delay as the regression: with the guard as it was, the test failed 3 runs out of 3; with the fix, all 38 of the file's tests pass.
- **Test gap**: nothing made the thread sample before the first test, and fast machines never did.
- **Sweep** (every test that starts the thread or runs the plugin in-process):
  - `test_the_thread_samples_until_the_limit_is_passed` calls `test_started` before `start()`: deterministic.
  - `test_the_run_summary_names_the_peak_the_guard_saw` and `test_the_run_summary_names_the_containers_slab` stay under the limit, so the peak is the same whoever samples first.
  - `test_the_plugin_does_nothing_unset` and `test_an_xdist_worker_makes_no_guard` make no guard.
  Only this test was exposed.
- **Reporter**: Claude
- **Date Reported**: 2026-11-21
- **Files**: `tests/memory_guard.py`, `tests/test_memory_guard.py`
