# Two Fingerprint Tests Failed Whenever the Run Compared Drivers

- **Description**: `tests/test_frame_fingerprints.py::TestEnvironmentActivation::test_variables_for_this_process_record_and_seed`
  and `::test_options_win_over_the_variables` failed in every local `pytest` run that compares
  drivers (the default outside CI): their inner run recorded no frames. They passed with
  `--dummy-only` and in CI, which do not compare.
- **Status**: Fixed (2026-11-26, `fix/event-queue-leak`, found by its full local run).
- **Priority**: Medium. The plain `pytest` the project documents failed on main for anyone running
  it locally; CI and the pre-push hook's runs did not see it.
- **Root Cause**: A comparing run sets `GLITCHYGAMES_FRAME_FINGERPRINTS_DRAWING_ONLY=1` (added in
  #287), so its runs record only the tests marked `draws_frames`. The file's autouse
  `no_recording_variables` cleared the other recording variables but not this one, and these two
  tests name their own process as the owner, so the variable applied to their inner run, whose one
  test is not marked: nothing was recorded.
- **Evidence**: The class fails 2 of 3 on main's code with comparison on (`uv run pytest -p
  no:randomly -n0 --no-cov tests/test_frame_fingerprints.py::TestEnvironmentActivation`) and passes
  with `--dummy-only`; with the variable cleared, the file passes both ways (68 of 68).
- **Fix**: `no_recording_variables` clears `DRAWING_ONLY_VARIABLE` too.
- **Test gap**: The fixture's list was written before the variable existed, and nothing ties the list
  to the variables the plugin reads; the suite's own CI runs never compare drivers.
- **Files**: `tests/test_frame_fingerprints.py`.
- **Siblings (swept)**: `tests/test_driver_comparison.py`'s `inner_project` clears the same list
  without it, but also clears the owner variable, and the plugin reads the variables only for the
  process the owner names: covered. No other test reads the fingerprint variables.
