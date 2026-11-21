# The Onion-Skin Indicator Is Covered Only by State an Earlier Test Leaves Behind

- **Description**: `src/apps/bitmappy/src/bitmappy/film_strip_rendering.py`'s
  `_render_onion_skinning_indicator` drawing branch (lines 210-227 on main at `60f6207a`) is
  covered in some runs and not in others: Bitmappy's tests reached 100% serially (`-n 0`) and in
  one `-n auto` run, and 99.95% (those 18 lines missed) in another `-n auto` run of the same tree
  (2026-11-20, found while running the Bitmappy assert sweep). The suite's 100% coverage rule can
  therefore fail by chance, on any branch.
- **Status**: Fixed (2026-11-21, branch `fix/onion-skin-coverage-isolation`)
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
- **Fix as planned**: an autouse fixture in Bitmappy's conftest giving each test the manager's startup
  state (as `isolated_onion_skinning` in `test_bitmappy_canvas_interfaces.py` already does for its
  golden tests), and a rendering test that switches one frame on and asserts the indicator's
  yellow pixels in that frame's top-right corner (and none on a frame that is off).
- **A second branch of the same class (2026-11-21, relayed by the coordinator)**: #257's Linux
  coverage combine failed at 99.99% on `onion_skinning.py` 133->exit
  (`clear_animation_onion_skinning`'s false branch), now frequent because #257 shuffles test order.
  f9 is adding one deterministic test to #257: clearing an animation with no onion-skin state is a
  no-op. The fix here builds on that test rather than adding a second one.
- **Scope, as agreed with the coordinator**: the autouse reset of the shared manager's state, the
  indicator test above, and a sweep for other branches whose coverage comes only from state an
  earlier test left. The defect class is coverage that depends on test order; with shuffling on
  main, such branches will show up as coverage flakes.
- **Known members of the class (the sweep's starting list)**: `film_strip_rendering.py`'s indicator
  drawing branch (above); `onion_skinning.py` 133->exit (now covered on purpose by f9's #257 test);
  `onion_skinning.py` line 114, `is_global_onion_skinning_enabled`'s return. f9 found line 114 is
  not covered when `test_bitmappy_onion_skinning*.py` runs alone; only other files reach it.
- **Fixed (2026-11-21)**:
  - `src/apps/bitmappy/tests/conftest.py`'s autouse `fresh_onion_skinning_manager` gives every
    test a new manager (a patch of `onion_skinning.onion_skinning_manager`) and puts the old one
    back after it. `test_bitmappy_canvas_interfaces.py`'s `isolated_onion_skinning`, which did the
    same for its golden tests, is removed (the goldens are unchanged).
  - Deliberate tests: `test_bitmappy_film_strip_rendering.py`'s `TestOnionSkinningIndicator` (a
    switched-on frame changes exactly the 12x12 square 2 pixels in from its top-right corner,
    toward yellow; a frame left off and global onion skinning off change nothing), and line 114
    in `test_bitmappy_onion_skinning.py`. Run alone, the onion-skinning test files cover
    `onion_skinning.py` at 100% (line and branch).
  - The conservation checks: `TestEveryTestGetsAFreshSharedManager` (every test sees the startup
    state, then leaves state behind for the next to catch), and
    `TestNothingHoldsTheSharedManagerByName`, an AST scan of Bitmappy's source and tests: a
    by-name import or copy of the manager would keep the old instance and escape the reset.
  - Checked by planting: with the reset removed, the leftovers fail the indicator tests, the
    startup check, the `onion_skinned` golden and `test_manager_state_persistence` (an existing
    test that toggles a frame and so broke whenever an earlier test left it on); a planted
    by-name import fails the scan.
- **The class, swept** (a branch whose coverage depends on state an earlier test left):
  - Bitmappy's other process-wide state (`tests/test_process_state_guard.py`'s Bitmappy rows):
    `MultiControllerManager._instance` is reset per test (`fresh_controller_manager`);
    `masterhub._REGISTRY` is reset by the tests that set it; the pixel and AI caches hold values,
    not state a branch depends on. `constants.ai_training_state` was not reset:
    `load_ai_training_data()` appends to it, and seven tests in `test_bitmappy.py` set its
    `format` or `data` and put them back only when they passed. Now the autouse
    `fresh_ai_training_state` gives every test the startup values, those tests use
    `mocker.patch.dict`, and `test_bitmappy_state.py` checks the startup state the same way
    (proven by planting a second reader with the reset removed).
  - Order comparison (Bitmappy's tests only, serially): reversed, and shuffled with seeds 1121 and
    20261121, each 100% line and branch with the fix, so no other branch was found. Not shown:
    coverage under other xdist splits (CI's combine remains the check).
- **Reporter**: Claude (session 21f7657c), during the Bitmappy assert sweep
- **Date Reported**: 2026-11-20
- **Files**: `src/apps/bitmappy/src/bitmappy/onion_skinning.py`,
  `src/apps/bitmappy/src/bitmappy/constants.py`,
  `src/apps/bitmappy/src/bitmappy/film_strip_rendering.py`, `src/apps/bitmappy/tests/conftest.py`
