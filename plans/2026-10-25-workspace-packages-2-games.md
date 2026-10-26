# Workspace Packages, Part 2: The Other Five Games Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Clockwork Keep, Brave Adventurer, Brave Adventurer Papyrus, PaddleSlap and Drawing Fire out of the engine (`src/glitchygames/examples/`) into their own workspace member packages under `src/games/`, as Part 1 moved Mr. Muncher, leaving the engine's examples holding only the three demos and Bitmappy's resources.

**Architecture:** Each game follows the shared recipe, `docs/architecture/game_packages.md` ("Moving a game out of the engine", steps 1-9): code, tests and golden replay into `src/games/<game>/`, the member registered in every tool's configuration (`tests/test_workspace_config.py` fails on any omission), its package moved from `EXAMPLES_LAYERS` to `MEMBER_LAYERS`, one `RECORDING_PATH_RENAMES` line per moved recording. Recordings are never re-recorded: logical names make a move invisible to them. Two engine seams are opened first, because later moves need them: a public trajectory API on `BallSprite` (PaddleSlap reads a private one today) and browser bundles that ship more than one member archive (Papyrus needs Brave Adventurer's code too).

**Tech Stack:** Python 3.14, uv workspaces (hatchling members), pytest at 100% coverage on the dummy and cocoa drivers, ruff, basedpyright, ty, mkdocs strict, the golden-replay plugin and the run ledger.

**Spec:** `plans/2026-10-24-workspace-packages.md` (Part 2's outline, decisions 1-9, "What every part keeps true"); the recipe it argues through is `docs/architecture/game_packages.md`; how Part 1 did it, `plans/2026-10-24-workspace-packages-1-foundation.md` Task 9.

## Global Constraints

- Order: Clockwork Keep, then Brave Adventurer, then Brave Adventurer Papyrus (it depends on `brave-adventurer`), then PaddleSlap, then Drawing Fire (added to the outline: it postdates it), each to `src/games/<game>/`.
- Names (decision 1): directory and distribution = the console script (`clockwork-keep`, `brave-adventurer`, `brave-adventurer-papyrus`, `paddleslap`, `drawing-fire`); import package = the engine's package name today (`clockwork_keep`, `brave_adventurer`, `brave_adventurer_papyrus`, `paddleslap`, `drawing_fire`); console scripts unchanged.
- Recordings (decisions 8, 9): no recording's bytes change; each game's golden moves to `src/games/<game>/tests/fixtures/replays/golden.jsonl.gz` and replays strictly from there; PaddleSlap's demo moves to `src/games/paddleslap/paddleslap/demos/rally.jsonl.gz`; every moved recording gets a `RECORDING_PATH_RENAMES` line from each path it has had.
- PaddleSlap keeps the logical name `games.paddleslap:Game`: `Game` stays defined in the package itself (`paddleslap/__init__.py`), never re-exported from a submodule.
- A member uses only the engine's public API (no `_`-prefixed engine name, no `# type: ignore[attr-defined]` reaching into engine objects).
- `main` works after each game: the whole suite passes on both drivers at 100% coverage, every golden replay matches, `nox -s lint`, `static-analysis` and `lint-docs` pass. One game per task, verified (recipe step 8) before the next.
- Each layer extra names exactly its members: a moved game joins `games` in `[project.optional-dependencies]` (`tests/test_workspace_config.py`).
- Repo conventions: single quotes, Google docstrings, no abbreviated names, `# ruff: ignore[rule-name] - reason` (never noqa), no shared mocks, real pygame on the dummy driver; stage whole moves (`git add -A src tests scripts docs`) so the replay-metrics hook accepts the commit; commits stay local; nothing is pushed without the user's say-so.

## Review Focus

1. **A leftover example directory** (git-ignored `__pycache__` left in `src/glitchygames/examples/<game>/`) still imports, as an empty namespace package, so stale code can seem to work: each move task asserts the old package is gone (`test_the_old_example_package_is_gone`, Tasks 3-7).
2. **A golden replay or demo whose run-ledger history breaks** on the move: each move task's `RECORDING_PATH_RENAMES` test asserts the old path maps to the new one; PaddleSlap's demo, already moved once (`glitchygames/examples/...` -> `src/glitchygames/examples/...`), needs a line from both old paths (Task 6, `test_the_rally_demo_keeps_its_whole_history`).
3. **Papyrus in the browser without Brave Adventurer's code**: its bundle must ship both archives, or it fails at import on the page only (Task 2, `test_a_game_depending_on_a_member_ships_both_archives`; Task 5 sets it).
4. **An engine test silently testing a moved game through a stale import path** (collision, animation and golden-trace tests borrow these games): every `glitchygames.examples.<game>` reference outside `plans/` is gone after its move (Tasks 3-7: `git grep` in the verify step must print nothing).
5. **PaddleSlap's recordings renamed by accident**: its `Game.__module__` must stay `paddleslap` (Task 6, `test_paddleslap_game_keeps_its_logical_name`).

---

### Task 1: A public trajectory API on `BallSprite`

**Files:**
- Modify: `src/glitchygames/game_objects/ball.py` (the `_debug_positions` list), `src/glitchygames/examples/paddleslap.py` (its five uses), `tests/examples/test_paddleslap.py` (its reads)
- Test: `tests/game_objects/test_ball_trajectory.py` (new)

**Interfaces:**
- Produces: `BallSprite.trajectory -> tuple[tuple[float, float, float, float], ...]` (read-only: x, y, speed x, speed y per recorded point, oldest first); `BallSprite.record_trajectory_point(*, x: float, y: float, speed_x: float, speed_y: float, limit: int) -> None` (appends, dropping the oldest beyond `limit`). Nothing clears it (PaddleSlap's tests only check it is empty), so no clear method.

- [ ] **Step 1: Write the failing tests** — `test_a_new_ball_has_no_trajectory` (`ball.trajectory == ()`), `test_recorded_points_come_back_oldest_first`, `test_the_trajectory_keeps_only_the_latest_limit_points` (record `limit + 2` points: the first two are gone), `test_the_trajectory_cannot_be_changed_through_the_property` (it is a tuple).
- [ ] **Step 2: Run** `uv run pytest --dummy-only --no-cov tests/game_objects/test_ball_trajectory.py` → FAIL (no attribute).
- [ ] **Step 3: Implement** the API; keep the list private behind it. PaddleSlap calls `record_trajectory_point(..., limit=DEBUG_TRAJECTORY_HISTORY_SIZE)` and reads `trajectory`; remove its five `# type: ignore[attr-defined]`. Its tests read `trajectory`.
- [ ] **Step 4: Run** those tests, `tests/examples/test_paddleslap.py`, then the whole suite → PASS, 100%; `git grep -n "_debug_positions" -- src tests scripts` prints only `ball.py`.
- [ ] **Step 5: Commit** — `"BallSprite: a public trajectory API (PaddleSlap reads no private engine name)"`

### Task 2: Browser bundles that ship several member archives

**Files:**
- Modify: `scripts/build_browser_bundle.py` (`GameSpecification.member_package`, `pyscript_config`, `write_bundle`, the `GAMES` entry of `mr-muncher`), `tests/test_build_browser_bundle.py`

**Interfaces:**
- Produces: `GameSpecification.member_packages: tuple[str, ...] = ()` replacing `member_package: str | None` (each ships as `<package>.zip`, in the order given: dependencies first); `pyscript_config(*, wheel_name: str, member_packages: tuple[str, ...] = ()) -> str`.

- [ ] **Step 1: Write the failing tests** — update the existing ones to `member_packages=('mr_muncher',)`; add `test_a_game_depending_on_a_member_ships_both_archives` (a specification with `member_packages=('brave_adventurer', 'brave_adventurer_papyrus')` lists both zips in its pyscript config, dependency first, and `write_bundle` writes both).
- [ ] **Step 2: Run** `uv run pytest --dummy-only --no-cov tests/test_build_browser_bundle.py` → FAIL.
- [ ] **Step 3: Implement**; the docstring's example names both shapes.
- [ ] **Step 4: Run** the browser tests, then `uv run nox -s browser -- mr-muncher` builds (no page needs playing: the bundle's file list shows `mr_muncher.zip`), then the whole suite → PASS.
- [ ] **Step 5: Commit** — `"Browser bundles ship every member archive a game needs"`

### Task 3: Move Clockwork Keep

**Files:** the recipe's (`docs/architecture/game_packages.md`, steps 1-7), for package `clockwork_keep`, directory `src/games/clockwork-keep/`. This game's specifics:
- Tests: `tests/examples/test_clockwork_keep.py` → `src/games/clockwork-keep/tests/`; it computes its golden's path from its own location: point it at `tests/fixtures/replays/golden.jsonl.gz` beside it.
- Golden: `tests/fixtures/replays/clockwork-keep/golden.jsonl.gz`. Its golden trace (`tests/world/golden/clockwork_keep.jsonl.gz`, `GOLDEN_TRACE_GAMES`) stays with the engine's trace tests; only its imports change.
- Outside users: `scripts/audio_glitch_probe.py`, `tests/animation/test_animation.py`, `tests/world/test_golden_traces.py`, `tests/test_browser_touch_controls.py`.

**Interfaces:**
- Consumes: the recipe; `MEMBER_LAYERS`, `EXAMPLES_LAYERS` (`glitchygames/logical_names.py`); `RECORDING_PATH_RENAMES` (`glitchygames/recording_metrics.py`); `GAMES` (`scripts/build_browser_bundle.py`, `member_packages` from Task 2).
- Produces: member `clockwork-keep`; `MEMBER_LAYERS['clockwork_keep'] == 'games'`; `games` extra includes `clockwork-keep`.

- [ ] **Step 1: Write the failing tests** — in `src/games/clockwork-keep/tests/test_logical_names_after_the_move.py` (modelled on Mr. Muncher's): `test_clockwork_keep_keeps_its_logical_names` (`logical_name(scene_class=ClockworkKeepScene) == 'games.clockwork_keep.game:ClockworkKeepScene'`, for every scene its golden replay starts, as Mr. Muncher's test does) and `test_the_old_example_package_is_gone` (`importlib.util.find_spec('glitchygames.examples.clockwork_keep') is None`); in `tests/test_recording_metrics.py`, `test_clockwork_keeps_golden_keeps_its_history` (`RECORDING_PATH_RENAMES['tests/fixtures/replays/clockwork-keep/golden.jsonl.gz']` is the new path).
- [ ] **Step 2: Run** them → FAIL.
- [ ] **Step 3: Follow the recipe, steps 1-7.**
- [ ] **Step 4: Verify** — the recipe's step 8, plus `git grep -n "glitchygames.examples.clockwork_keep\|glitchygames/examples/clockwork_keep\|fixtures/replays/clockwork-keep" -- ':!plans' ':!quality'` prints nothing.
- [ ] **Step 5: Commit** (recipe step 9) — `"Workspace packages: Clockwork Keep as its own package"`

### Task 4: Move Brave Adventurer

**Files:** the recipe, for package `brave_adventurer`, directory `src/games/brave-adventurer/`. Specifics:
- Tests: `tests/examples/test_brave_adventurer_sounds.py` and its data `tests/examples/brave_adventurer_golden/*.npy` move together. `tests/examples/test_brave_adventurer_game.py` tests both editions: split it, the Brave Adventurer tests to this member now, the Papyrus tests to `tests/examples/test_brave_adventurer_papyrus_game.py` until Task 5 moves them (it imports this member's package; any helper both need goes in a module named for this member, `brave_adventurer_test_helpers.py`: test helper names must stay unique, BUGS.md #31). It imports `REPLAY_FIXTURE_DIRECTORY` from `scripts.record_scripted_session`: use its own fixture directory instead.
- Golden: `tests/fixtures/replays/brave-adventurer/golden.jsonl.gz`; `tests/benchmarks/test_benchmarks.py` reads it by path. Golden trace `tests/world/golden/brave_adventurer.jsonl.gz` stays (imports change).
- Outside users: `tests/collision/test_collision.py`, `tests/animation/test_animation.py`, `tests/world/test_golden_traces.py`, `tests/test_browser_touch_controls.py`.

**Interfaces:**
- Produces: member `brave-adventurer` (import package `brave_adventurer`), which Task 5 depends on.

- [ ] **Step 1: Write the failing tests** — `test_brave_adventurer_keeps_its_logical_names`, `test_the_old_example_package_is_gone`, `test_brave_adventurers_golden_keeps_its_history`, as in Task 3.
- [ ] **Step 2: Run** → FAIL. **Step 3:** the recipe, steps 1-7, and the test split above.
- [ ] **Step 4: Verify** — recipe step 8; the `git grep` for `glitchygames.examples.brave_adventurer\b`, `glitchygames/examples/brave_adventurer/` and `fixtures/replays/brave-adventurer/` prints nothing (Papyrus's own paths remain until Task 5).
- [ ] **Step 5: Commit** — `"Workspace packages: Brave Adventurer as its own package"`

### Task 5: Move Brave Adventurer Papyrus

**Files:** the recipe, for package `brave_adventurer_papyrus`, directory `src/games/brave-adventurer-papyrus/`. Specifics:
- A member depending on a member: `dependencies = ["glitchygames", "brave-adventurer"]`, `[tool.uv.sources] brave-adventurer = { workspace = true }`.
- Its sprites (`brave_adventurer_papyrus/sprites/*.toml`) ship as package data; it already reads them through `Path(__file__).parent / 'sprites'`. Outside users of that directory: `scripts/audit_hitboxes.py`, `tests/sprites/test_animated_sprite.py`, `tests/collision/test_collision.py`.
- Tests: `tests/examples/test_brave_adventurer_papyrus_game.py` (from Task 4) moves here.
- Browser: `GAMES['brave-adventurer-papyrus']` ships `member_packages=('brave_adventurer', 'brave_adventurer_papyrus')`.
- Golden: `tests/fixtures/replays/brave-adventurer-papyrus/golden.jsonl.gz`.

**Interfaces:**
- Consumes: member `brave-adventurer` (Task 4); `GameSpecification.member_packages` (Task 2).

- [ ] **Step 1: Write the failing tests** — `test_papyrus_keeps_its_logical_names`, `test_the_old_example_package_is_gone`, `test_papyrus_golden_keeps_its_history`; `test_papyrus_ships_brave_adventurers_archive_too` (its `GAMES` entry's `member_packages`, dependency first); `test_papyrus_sprites_ship_in_its_wheel` (`uv build --package brave-adventurer-papyrus`, then the wheel's file list holds every `sprites/*.toml`).
- [ ] **Step 2: Run** → FAIL. **Step 3:** the recipe, steps 1-7.
- [ ] **Step 4: Verify** — recipe step 8 (its browser bundle: `uv run nox -s browser -- brave-adventurer-papyrus` lists both zips); the `git grep` for its old paths prints nothing.
- [ ] **Step 5: Commit** — `"Workspace packages: Brave Adventurer Papyrus as its own package (it depends on Brave Adventurer)"`

### Task 6: Move PaddleSlap, and its bundled demo

**Files:** the recipe, for package `paddleslap`, directory `src/games/paddleslap/`. Specifics:
- One module becomes a package: `src/glitchygames/examples/paddleslap.py` → `src/games/paddleslap/paddleslap/__init__.py` (`git mv`, so its history follows), `Game` still defined there.
- Its demo: `src/glitchygames/examples/paddleslap_demos/rally.jsonl.gz` → `src/games/paddleslap/paddleslap/demos/rally.jsonl.gz` (`PADDLESLAP_DEMO_PATH` follows; read through `Path(__file__).parent / 'demos'`).
- Bundled-demo discovery: `glitchygames/testing/replays.py` `bundled_demo_paths` finds demos in each member package listed in `MEMBER_LAYERS` (`<package directory>/demos/*.jsonl.gz`, the package located with `importlib.util.find_spec`, its console script by `console_script_in_module(module=<package>)`), no longer in `glitchygames/examples/<game>_demos/`. Its examples-directory parameter, `EXAMPLES_DIRECTORY`/`BUNDLED_DEMO_DIRECTORY_SUFFIX` and `scripts/replay_metrics.py` `EXAMPLES_PATH` go (nothing else bundles a demo). Follow its callers and tests: `scripts/replay_metrics.py` (`--only paddleslap_demos` becomes the demo's new name in `tests/test_replay_metrics.py`), `tests/replay/test_bundled_demos.py`, `tests/replay/test_recording_logical_names.py`, `tests/replay/test_replay_plugin.py` (its entry point string becomes `paddleslap:main`), `tests/test_recording_metrics.py`, `tests/test_generate_performance_graphs.py`.
- `RECORDING_PATH_RENAMES`: the golden's line, and two for the demo (`glitchygames/examples/paddleslap_demos/rally.jsonl.gz` and `src/glitchygames/examples/paddleslap_demos/rally.jsonl.gz`, each to the new path): each lookup is one step.
- Re-key the root ruff per-file ignore naming `src/glitchygames/examples/paddleslap.py`.
- Tests: `tests/examples/test_paddleslap.py` (drop its `sys.path.insert`; its golden path follows). Engine tests that use PaddleSlap's `Game` to test engine behaviour (`tests/collision/test_ball_paddle_collision.py`, `tests/game_objects/test_ball_collision_physics.py`, `test_collision_scenarios.py`, `test_game_over_scene.py`, `tests/scenes/builtin_scenes/test_game_over.py`, `test_pause_screen.py`, `tests/replay/test_playback_scope.py`, `test_instant_replay.py`, `tests/test_browser_touch_controls.py`, `tests/replay/test_golden_replays.py`) stay in the engine's tests and import `paddleslap`.
- Golden: `tests/fixtures/replays/paddleslap/golden.jsonl.gz`; golden trace `tests/world/golden/paddleslap.jsonl.gz` stays.

**Interfaces:**
- Consumes: `BallSprite.trajectory` (Task 1).
- Produces: `bundled_demo_paths() -> list[tuple[str, Path]]` (members' demos, sorted by path).

- [ ] **Step 1: Write the failing tests** — `test_paddleslap_game_keeps_its_logical_name` (`logical_name(scene_class=Game) == 'games.paddleslap:Game'` and `Game.__module__ == 'paddleslap'`), `test_the_old_example_module_is_gone` (`find_spec('glitchygames.examples.paddleslap') is None`), `test_bundled_demos_are_found_in_member_packages` (`bundled_demo_paths()` returns `('paddleslap', <member>/paddleslap/demos/rally.jsonl.gz)`), `test_the_rally_demo_keeps_its_whole_history` (both old paths map to the new one), `test_paddleslaps_golden_keeps_its_history`.
- [ ] **Step 2: Run** → FAIL. **Step 3:** the recipe, steps 1-7, and the demo discovery above.
- [ ] **Step 4: Verify** — recipe step 8; `uv run python -m scripts.replay_metrics measure --only rally` (or the new `--only` name) measures the demo from its new place; the `git grep` for `glitchygames.examples.paddleslap`, `glitchygames/examples/paddleslap`, `paddleslap_demos` prints nothing outside the ledger history rows.
- [ ] **Step 5: Commit** — `"Workspace packages: PaddleSlap as its own package, its demo inside it"`

### Task 7: Move Drawing Fire

**Files:** the recipe, for package `drawing_fire`, directory `src/games/drawing-fire/`. Specifics:
- Its sprite `drawing_fire/sprites/soldier.toml` ships as package data (read through `Path(__file__).parent`; its tests use `drawing_fire.__file__`).
- Tests: `tests/examples/drawing_fire/` → `src/games/drawing-fire/tests/` (drop its `__init__.py`; its `conftest.py`, the event-queue drain, becomes the member's `tests/conftest.py`). `test_simulation.py` imports `scripts.simulate_drawing_fire`, which imports `battle` and `drivers`: update the script's imports.
- `tests/replay/test_golden_replays.py`: `DRAWING_FIRE_CONTROLS` (built from `drawing_fire.players`' scancode lists), `_drawing_fire_snapshot_control`, its `GAMEPLAY_ACTION_MAPS`, `ENGINE_SCENE_CONTROLS`, `GAMES_WITHOUT_A_PAUSE` and `UNEXERCISED_CONTROLS` entries, and `test_the_drawing_fire_golden_replay_holds_a_death_and_a_takeover` follow the import. `scripts/record_scripted_session.py` `POLLED_INPUT_GAMES` keys by game, so it needs no change; `scripts/record_golden_traces.py` imports `DrawingFireScene`, `LEAVE_HOLD_SECONDS` and `Stage`.
- Browser: `GAMES['drawing-fire']` gets `member_packages=('drawing_fire',)`; it stays in `GAMES_WITHOUT_TOUCH_CONTROLS`.
- Golden: `tests/fixtures/replays/drawing-fire/golden.jsonl.gz`.

- [ ] **Step 1: Write the failing tests** — `test_drawing_fire_keeps_its_logical_names` (`games.drawing_fire.game:DrawingFireScene`), `test_the_old_example_package_is_gone`, `test_drawing_fires_golden_keeps_its_history`, `test_the_soldier_sprite_ships_in_its_wheel` (`uv build --package drawing-fire`: the wheel holds `drawing_fire/sprites/soldier.toml`).
- [ ] **Step 2: Run** → FAIL. **Step 3:** the recipe, steps 1-7.
- [ ] **Step 4: Verify** — recipe step 8; `uv run python -m scripts.simulate_drawing_fire --seeds 2` runs; the `git grep` for its old paths prints nothing.
- [ ] **Step 5: Commit** — `"Workspace packages: Drawing Fire as its own package"`

### Task 8: Part 2's end state, docs and verification

**Files:**
- Modify: `src/glitchygames/logical_names.py` (`EXAMPLES_LAYERS` keeps only the three demos; its comment says Part 3 deletes it), `tests/test_logical_names.py`, `docs/glitchygames/examples/index.md` (only the demos), `docs/architecture/game_packages.md` (the layout's examples line; Part 2's lessons, if any changed the recipe), `README.md` and `CLAUDE.md` (every game is its own package), `plans/2026-10-24-workspace-packages.md` (Part 2 DONE, with its commits; Part 2's outline names Drawing Fire), `plans/future-features.md` (anything left over)
- Test: `tests/test_workspace_packages.py`

- [ ] **Step 1: Write the failing test** — `test_the_engines_examples_hold_only_the_demos_and_bitmappys_resources` (the entries of `src/glitchygames/examples/` other than `__init__.py`, `__pycache__` and `foo2.toml` are exactly `dt_demo.py`, `joystick_demo.py`, `text_input_demo.py`, `resources`); `test_the_root_goldens_are_the_engines_own` (`tests/fixtures/replays/` holds no game's directory).
- [ ] **Step 2: Run** → FAIL until the tables and docs follow; then make them follow.
- [ ] **Step 3: Verify the whole part** — `uv sync --all-extras --all-groups --all-packages`; `CI=true uv run nox -s test`; `uv run pytest` (both drivers, 100%); `uv run nox -s lint static-analysis lint-docs`; `uv run nox -s build-wheel` (the engine's wheel holds no game: its file list has no `clockwork_keep/`, `brave_adventurer*/`, `paddleslap`, `drawing_fire/`); `uv build --all-packages`; `uv run nox -s browser -- <each game>` builds; into a scratch venv, `pip install --find-links dist "glitchygames[games]"` from those built wheels (the games are not on PyPI) installs the engine and all six games, and each console script starts; `uv run nox -s docs-deploy -- --build-only`.
- [ ] **Step 4: Commit** — `"Workspace packages, Part 2: every game is its own package"`
