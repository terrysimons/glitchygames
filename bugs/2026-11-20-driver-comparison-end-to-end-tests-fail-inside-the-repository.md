# Three Driver-Comparison End-to-End Tests Fail When Their Temporary Folder Is Inside the Repository

- **Description**: `tests/test_driver_comparison.py::TestEndToEnd::test_dummy_only_runs_one_driver`, `::test_a_frame_difference_fails_the_run_with_images` and `::test_a_failure_in_the_second_run_fails_this_run` fail whenever pytest's temporary folder is inside the repository, and pass when it is outside. Found 2026-11-20 by the process-stop reproducer (`scripts/reproduce_process_stop_under_load.py`), which first put each round's `--basetemp` under the repository's `build/`: they failed in 20 of 20 rounds there (the third in 14). Isolated (2026-11-20):
  - inside the repository: `--basetemp build/…` (relative), `--basetemp /…/<repository>/build/…` (absolute), with or without the probe on `PYTHONPATH`, and `PYTEST_DEBUG_TEMPROOT=<repository>/build/…` (no `--basetemp`): fail;
  - outside it: pytest's default temporary folder, `--basetemp` in the scratch folder, `PYTEST_DEBUG_TEMPROOT` in the scratch folder: pass.
  Failures seen: `ExitCode.TESTS_FAILED` where `OK` was expected; `ValueError: Pytest terminal summary report not found`; `nomatch: '*driver comparison: dummy vs dummy-2*'`.
- **Status**: Open (recorded under the owner's freeze on new work, 2026-11-20)
- **Priority**: Low (test only; the suite's default temporary folder is outside the repository, but a run that places it inside, as a triage tool did, can't run these tests)
- **Root Cause**: not established. Likely: each test writes an inner project (its own `pytest.ini` and test file) under its `tmp_path` and runs pytest on it; under the repository, the inner run also finds the repository's own configuration (`pyproject.toml`'s pytest settings, `conftest.py`, its plugins), so it runs as the project's suite rather than the inner project's. To confirm: run one inside the repository and compare the inner run's header (rootdir, configfile, plugins) with a run outside.
- **Test gap**: the tests assume their `tmp_path` lies outside any project; nothing checks that assumption, and no run places the temporary folder inside the repository.
- **Workaround**: `scripts/reproduce_process_stop_under_load.py` puts each round's `--basetemp` in a fresh folder outside the repository and moves it into the round's folder only when the round fails.
- **Reporter**: Claude
- **Date Reported**: 2026-11-20
- **Files**: `tests/test_driver_comparison.py` (`TestEndToEnd`), `tests/driver_comparison.py`
