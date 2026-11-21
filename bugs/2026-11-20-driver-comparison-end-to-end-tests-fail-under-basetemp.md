# Three Driver-Comparison End-to-End Tests Fail When pytest Is Given --basetemp

- **Description**: `tests/test_driver_comparison.py::TestEndToEnd::test_dummy_only_runs_one_driver`, `::test_a_frame_difference_fails_the_run_with_images` and `::test_a_failure_in_the_second_run_fails_this_run` fail whenever the outer pytest run is given `--basetemp` (relative or absolute), and pass without it. Found 2026-11-20 by the process-stop reproducer (`scripts/reproduce_process_stop_under_load.py`, which passes `--basetemp` to keep each test's `tmp_path`): they failed in 20 of 20 rounds there (the second in 14). Isolated on the first: `--basetemp` relative, absolute, with or without the probe on `PYTHONPATH`: fails; no `--basetemp`, with or without coverage, in this worktree or another: passes. Failures seen: `ExitCode.TESTS_FAILED` where `OK` was expected; `ValueError: Pytest terminal summary report not found`; `nomatch: '*driver comparison: dummy vs dummy-2*'`.
- **Status**: Open (recorded under the owner's freeze on new work, 2026-11-20; cause not looked for)
- **Priority**: Low (test only; nothing in the project passes `--basetemp` to the suite today, but a triage tool that does can't run these tests)
- **Root Cause**: not established. A guess to check first: the tests start an inner pytest run whose temporary directory or output parsing assumes pytest's default basetemp, so an inherited `--basetemp` (pytest passes it to `pytester` and its children) makes the inner run share or move it.
- **Test gap**: no test runs the suite with `--basetemp`.
- **Workaround in the reproducer**: it deselects these three tests.
- **Reporter**: Claude
- **Date Reported**: 2026-11-20
- **Files**: `tests/test_driver_comparison.py` (`TestEndToEnd`), `tests/driver_comparison.py`
