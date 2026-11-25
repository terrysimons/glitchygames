# The Driver Comparison's Native Run Crashes When pytest Runs Without Its Cache Provider

- **Description**: On macOS, outside CI, a `pytest` run given `-p no:cacheprovider` passes its own
  tests and then fails (exit 1) because the driver comparison's native run crashes before it
  collects anything. The command that reproduces it (2026-11-24, the owner's Mac, Python 3.15.1,
  pytest 9.1.1; any test file will do, this one is from `triage/sys-modules-watcher`):

  ```bash
  uv run pytest tests/test_module_removals.py -k interrupted_install -n 1 --no-cov -p no:cacheprovider
  ```

  The dummy run says `1 passed`. Then the summary:

  ```text
  cocoa run: exit 3 after 1.3 s (1 workers); its output: .../test-results/driver-comparison/pytest/native/pytest.log
  The cocoa run failed (0 listed):
  ```

  That log ends with pytest's internal error, whose last line is:

  ```text
  INTERNALERROR> pytest.PytestConfigWarning: Unknown config option: cache_dir
  ```

  Without the option, the same comparison runs (two files of undrawn tests: cocoa exit 5, "no
  drawing tests selected", the run passes).
- **Status**: Open. No fix chosen.
- **Priority**: Low (only a run that turns the cache provider off; it fails a run that passed, and
  the summary does not say why).
- **Root Cause**: `child_pytest_command` gives the native run this run's own arguments, so
  `-p no:cacheprovider` too, and always appends `-o cache_dir=...` (`tests/driver_comparison.py:258`).
  `cache_dir` is the cache provider's option: with the plugin blocked pytest does not know it and
  warns, and the project's `filterwarnings = ["error", ...]` makes the warning an error, raised in
  pytest's own collection hook (INTERNALERROR, exit 3). "0 listed" because `failure_summary_lines`
  keeps only the log's `FAILED ...` and `ERROR ...` lines, and an internal error writes neither.
- **Test gap**: `tests/test_driver_comparison.py` checks that the command holds `cache_dir=`, but
  starts no native run whose own arguments block the cache provider; and no test gives the summary
  a log that ends in an internal error.
- **Solution**: Not chosen. Options:
  - Append `-o cache_dir=...` only when this run has the cache provider loaded, as `-n` and
    `--no-cov` already depend on their plugins (unproven).
  - Set the child's cache directory some way that needs no plugin (unproven, no such way found).
  - Beside either: when a failed native run lists nothing, show its log's `INTERNALERROR>` lines or
    last lines, so any crash names itself (unproven).
- **Known limits**: Not checked: Linux and Windows; the module's other child, the re-run that saves
  a differing test's frames (built by the same function, so probably the same crash); the places
  that pass the option themselves (`noxfile.py`'s `test-linux-x11` and `compare-drivers` in the
  Linux container, `scripts/memory_triage.py`, `scripts/mark_drawing_tests.py`,
  `scripts/reproduce_orphaned_test_processes.py`), and whether a native run starts under any of
  them; runs without xdist; pytest's other ways of blocking the plugin.
- **Sweep**: Not done: other options this module appends that belong to a plugin a run can block
  (`--junitxml` is one to check).
- **Tests**: None yet.
- **Reporter**: The triage session of `triage/sys-modules-watcher`, while finding out why the
  reviewer's copy printed "The cocoa run failed (0 listed)"; that copy's native log has the same
  last line. The reviewer's command line was not seen.
- **Date Reported**: 2026-11-24
- **Files**: `tests/driver_comparison.py` (`child_pytest_command`, `failure_summary_lines`,
  `DriverComparison.compare`), `tests/test_driver_comparison.py`, `pyproject.toml`
  (`filterwarnings`).
