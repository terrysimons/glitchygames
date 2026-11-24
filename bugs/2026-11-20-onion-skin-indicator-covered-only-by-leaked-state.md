# The Onion-Skin Indicator Is Covered Only by State an Earlier Test Leaves Behind

- **Description**: `src/apps/bitmappy/src/bitmappy/film_strip_rendering.py`'s
  `_render_onion_skinning_indicator` drawing branch (lines 210-227 on main at `60f6207a`) is
  covered in some runs and not in others: Bitmappy's tests reached 100% serially (`-n 0`) and in
  one `-n auto` run, and 99.95% (those 18 lines missed) in another `-n auto` run of the same tree
  (2026-11-20, found while running the Bitmappy assert sweep). The suite's 100% coverage rule can
  therefore fail by chance, on any branch.
- **Status**: Open
- **Priority**: Low (test only; it can fail a coverage gate by chance)
- **Root cause (evidence so far)**: the branch runs only when
  `get_onion_skinning_manager().is_frame_onion_skinned(animation, frame)` is true, which needs the
  process-wide manager (`bitmappy/onion_skinning.py`, `onion_skinning_manager`) to have that frame
  switched on. No fixture resets the manager between tests (unlike `MultiControllerManager`, which
  `src/apps/bitmappy/tests/conftest.py`'s autouse `fresh_controller_manager` resets), and several
  tests switch frames on in the real manager without restoring it (for example
  `test_bitmappy_onion_skinning_rendering.py::TestOnionSkinningIntegration::test_onion_skinning_manager_integration`
  toggles `('test_animation', 0)`). Per-test coverage contexts of a serial run (`COVERAGE_CORE=ctrace`,
  `--cov-context=test`) show line 215 reached by about 80 tests, most of which set up no onion
  skinning at all (the film strip coordinator's, navigation and integration tests): they draw the
  indicator only because an earlier test on the same worker left a frame switched on. Which test
  leaves it, and on which worker, depends on how xdist distributes the files. Not yet shown: the
  exact leaking test of the run that missed the lines.
- **Test gap**: no test switches a frame's onion skinning on, in isolation, and checks the
  indicator is drawn; the branch's coverage is incidental.
- **Fix to make**: an autouse fixture in Bitmappy's conftest giving each test the manager's startup
  state (as `isolated_onion_skinning` in `test_bitmappy_canvas_interfaces.py` already does for its
  golden tests), and a rendering test that switches one frame on and asserts the indicator's
  yellow pixels in that frame's top-right corner (and none on a frame that is off).
- **Reporter**: Claude (session 21f7657c), during the Bitmappy assert sweep
- **Date Reported**: 2026-11-20
- **Files**: `src/apps/bitmappy/src/bitmappy/onion_skinning.py`,
  `src/apps/bitmappy/src/bitmappy/film_strip_rendering.py`, `src/apps/bitmappy/tests/conftest.py`
