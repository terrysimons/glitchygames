# A Module-Scoped Fixture Ran Before the Test Display Existed

- **Description**: A pre-push `test-random` run (seed 1957271441, 2026-11-21, pushing `ci/docs-only-prs-skip-tests` at `03992da5`) errored every test of `src/games/zombies-aint-my-neighbors/tests/test_zombies_aint_my_neighbors_demo_route.py` in setup: `assert self.screen is not None` (`src/glitchygames/scenes/scene.py`, `Scene.__init__`), raised while the module-scoped `demo_plan` fixture built its planning scene (`scripts/plan_neighborhood_route.py`, `plan_demo`). The worker's previous test was `tests/test_logging.py::test_logging`.
- **Status**: Fixed (2026-11-22, branch `fix/demo-plan-fixture-needs-its-own-display`)
- **Priority**: Medium (a red pre-push gate on an unrelated change, in a rare shuffled order; nothing in the shipped code was wrong)
- **Reproduction**: `uv run pytest tests/test_logging.py::test_logging src/games/zombies-aint-my-neighbors/tests/test_zombies_aint_my_neighbors_demo_route.py --dummy-only --no-cov -p no:randomly -n0` gave 3 passed, 8 errors every time; the demo-route file alone passed 10 of 10.
- **Root Cause**: `test_logging` ends with `pygame.quit()`, which the harness allows: `ensure_pygame_graceful_quit` starts pygame and the 800x600 display again before each test. But pytest sets up a module-scoped fixture before the function-scoped fixtures of the first test that asks for it, so `demo_plan` ran before that restart and found no display. `plan_demo`'s docstring says a test has the harness's display, which was true only for a function-scoped caller.
- **Fix**: the harness's `pytest_fixture_setup` hook (`tests/harness.py`) starts pygame and the test display before any fixture wider than one test (module, class, package, session) is set up, using the same helper as `ensure_pygame_graceful_quit`. That fixes the whole class in one place, not only this fixture.
- **Test gap**: nothing ran a wide fixture after a test that quit pygame; in written order the demo-route file always followed a test that left a display.
- **Regression tests**: `tests/test_harness_opens_the_display_for_wide_fixtures.py` runs, under the harness in a fresh interpreter, a test that quits pygame and then a module- or session-scoped fixture that reads the display and paints it. The test then checks it starts on the canvas pattern, so the early display still gets the per-test reset. Results:
  - Without the hook, both cases fail, and the reproduction above gives 8 errors.
  - Without the per-test canvas, both cases fail too. The paint keeps the harness's black-frame backstop from hiding that.
  - With the fix, both pass, and the reproduction passes 11 of 11.
- **Nothing relies on pygame being stopped**: the three tests that assert pygame or its display is not started (`tests/test_sdl_driver_defaults.py`, `tests/engine/test_game_engine.py::TestGameEngineShutdown`) check right after their own body quits pygame, with no fixture set up in between; they pass. No wide fixture opens a display of its own.
- **Sweep** (every module-, class-, package- or session-scoped fixture, 22 in all):
  - Exposed: only `demo_plan`, which built a scene in the test process.
  - Not exposed:
    - 12 record their stand-in games in a child process (`record_stand_in_game_once`);
    - the channel-fade recordings run in a child process;
    - the unseen-game templates only write files;
    - the two parsed-file cache fixtures only clear a cache;
    - the harness's session fixtures start the display themselves;
    - Drawing Fire's `frames` calls `pygame.init()` and loads frames without a display mode.
  With the hook, every one of them now sees the test display anyway.
- **Reporter**: Claude
- **Date Reported**: 2026-11-22
- **Files**: `tests/harness.py`, `tests/test_harness_opens_the_display_for_wide_fixtures.py`
