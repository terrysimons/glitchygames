# A Dotted Coverage Source Loaded the Engine Twice

- **Description**: `uv run pytest --cov=glitchygames.sprites.hud_label src/games/brave-adventurer/tests`
  (a dotted coverage source, to measure one module) failed 8 of 502 tests in a fixed order and 2
  with workers: Papyrus's player 1 pixel off (`(150, 318) == (149, 319)`), pose-before-collision
  and pit-edge checks, and the launcher recording diverging. Without it, or with `--cov=glitchygames`,
  all pass. First seen by session -99 on 7a3348672 (2026-11-26).
- **Status**: Guarded (2026-11-27, `fix/each-engine-module-loaded-once`): the run now stops at its
  start with the cause. The splitting itself is coverage's.
- **Priority**: Low for CI (its runs name packages, never a dotted source); high for whoever
  measures one module, because the failures look like real gameplay bugs.
- **Root Cause**: coverage 7.17.3 resolves a dotted source with `find_spec`, which imports the
  source's parents (`glitchygames.sprites`, and most of the engine with it), inside
  `sys_modules_saved()` (coverage/inorout.py:315), which deletes every module imported in the
  block from `sys.modules` afterwards. `glitchygames` itself was already imported (the pytest11
  plugin `glitchygames.testing.replays` loads before coverage starts), so the package kept the
  deleted submodules as attributes. The harness's `from glitchygames import pixel_snap` bound
  that first copy; the game's `from glitchygames.pixel_snap import ...` imported a second. Each
  copy has its own `ContextSlot` for the active snap mode, so the harness's
  `reset_default_snap_mode` reset a copy no game reads, and
  `test_terrain_collision_snaps_with_the_scene_mode`'s FLOOR mode reached the next tests.
- **Evidence**: Bisected (101 predecessors) to that test. A probe showed the snap mode still FLOOR
  after its teardown under the dotted source and back to NEAREST_HALF_UP under `--cov=glitchygames`,
  in the same engine context; `tests.harness.pixel_snap is sys.modules['glitchygames.pixel_snap']`
  was False only under the dotted source. An audit hook placed the first import inside pytest-cov's
  start (`pytest_cov/engine.py`) and the second in the conftest import.
- **Fix**: `tests/module_copies_guard.py` finds any project module (checkout `src` and `tests`, the
  installed engine) that some project module holds in a copy other than `sys.modules`' own, and
  tests/harness.py's `pytest_sessionstart` stops the run with pytest's usage error, naming the
  modules, the usual cause and what to run instead (`--cov=glitchygames`, then
  `coverage report --include=<path>`). The real command now stops before any test, naming
  `glitchygames.events` and `glitchygames.pixel_snap`.
- **Test gap**: Nothing checked that each module is loaded once; per-context resets assume it.
- **Invariant**: one module object per project module, checked at every run's start (and
  `test_this_run_loads_each_project_module_once` in the run itself).
  `test_a_dotted_coverage_source_stops_the_run_with_the_cause` failed before the hook (the inner
  run ended OK).
- **Files**: `tests/module_copies_guard.py`, `tests/harness.py`, `tests/test_module_copies_guard.py`.
- **Siblings (swept)**: Tests that remove modules on purpose (tests/test_import_failure_state.py,
  pytester's in-process runs) do it inside a test, after the check. A member's dotted source under
  `nox -s test` (installed members are outside the roots) is not covered.
