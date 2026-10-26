# Workspace Packages, Part 2: The Other Five Games Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Clockwork Keep, Brave Adventurer, Brave Adventurer Papyrus, PaddleSlap and Drawing Fire out of the engine (`src/glitchygames/examples/`) into their own workspace member packages under `src/games/`, as Part 1 moved Mr. Muncher, leaving the engine's examples holding only the three demos and Bitmappy's resources.

**Architecture:** Each game follows the shared recipe, `docs/architecture/game_packages.md` ("Moving a game out of the engine", steps 1-9): code, tests and golden replay into `src/games/<game>/`, the member registered in every tool's configuration (`tests/test_workspace_config.py` fails on any omission), its package moved from `EXAMPLES_LAYERS` to `MEMBER_LAYERS`, one `RECORDING_PATH_RENAMES` line per moved recording. Recordings are never re-recorded: logical names make a move invisible to them. Two engine seams are opened first, because later moves need them: a public trajectory API on `BallSprite` (PaddleSlap reads a private one today) and browser bundles that ship more than one member archive (Papyrus needs Brave Adventurer's code too).

**Tech Stack:** Python 3.14, uv workspaces (hatchling members), pytest at 100% coverage on the dummy and cocoa drivers, ruff, basedpyright, ty, mkdocs strict, the golden-replay plugin and the run ledger.

**Spec:** `plans/2026-10-24-workspace-packages.md` (Part 2's outline, decisions 1-9, "What every part keeps true"); the recipe it argues through is `docs/architecture/game_packages.md`; how Part 1 did it, `plans/2026-10-24-workspace-packages-1-foundation.md` Task 9.

## Global Constraints

- Order: Clockwork Keep, then Brave Adventurer and Papyrus as one project (`src/games/brave-adventurer/`: two games and a launcher, the user's decision 2026-10-25, Tasks 4-6), then PaddleSlap, then Drawing Fire (added to the outline: it postdates it), each to `src/games/<game>/`.
- Names (decision 1): directory and distribution = the console script (`clockwork-keep`, `brave-adventurer`, `paddleslap`, `drawing-fire`); import package = the engine's package name today (`clockwork_keep`, `brave_adventurer` and `brave_adventurer_papyrus` with the new `brave_adventurer_core` and `brave_adventurer_modes`, `paddleslap`, `drawing_fire`); console scripts unchanged but one: `brave-adventurer-papyrus` goes, Papyrus is reached through the `brave-adventurer` launcher (Task 5).
- Recordings (decisions 8, 9): no recording's bytes change; each game's golden moves to `src/games/<game>/tests/fixtures/replays/golden.jsonl.gz` and replays strictly from there; PaddleSlap's demo moves to `src/games/paddleslap/paddleslap/demos/rally.jsonl.gz`; every moved recording gets a `RECORDING_PATH_RENAMES` line from each path it has had.
- PaddleSlap keeps the logical name `games.paddleslap:Game`: `Game` stays defined in the package itself (`paddleslap/__init__.py`), never re-exported from a submodule.
- A member uses only the engine's public API (no `_`-prefixed engine name, no `# type: ignore[attr-defined]` reaching into engine objects).
- `main` works after each game: the whole suite passes on both drivers at 100% coverage, every golden replay matches, `nox -s lint`, `static-analysis` and `lint-docs` pass. One game per task, verified (recipe step 8) before the next.
- Each layer extra names exactly its members: a moved game joins `games` in `[project.optional-dependencies]` (`tests/test_workspace_config.py`).
- Repo conventions: single quotes, Google docstrings, no abbreviated names, `# ruff: ignore[rule-name] - reason` (never noqa), no shared mocks, real pygame on the dummy driver; stage whole moves (`git add -A src tests scripts docs`) so the replay-metrics hook accepts the commit; commits stay local; nothing is pushed without the user's say-so.

## Review Focus

1. **A leftover example directory** (git-ignored `__pycache__` left in `src/glitchygames/examples/<game>/`) still imports, as an empty namespace package, so stale code can seem to work: each move task asserts the old package is gone (`test_the_old_example_package_is_gone`, Tasks 3, 4, 7, 8).
2. **A golden replay or demo whose run-ledger history breaks** on the move: each move task's `RECORDING_PATH_RENAMES` test asserts the old path maps to the new one; PaddleSlap's demo, already moved once (`glitchygames/examples/...` -> `src/glitchygames/examples/...`), needs a line from both old paths (Task 7, `test_the_rally_demo_keeps_its_whole_history`).
3. **A Brave Adventurer recording replayed as the wrong game, or the title screen waiting forever in a headless replay**: the launcher must start the game a recording's header names, and refuse a recording of any other game (Task 5, `test_a_recording_starts_its_own_game`, `test_a_recording_of_another_game_is_an_error`); in the browser, a game missing its core archive fails at import on the page only (Task 2, `test_a_game_depending_on_a_member_ships_both_archives`).
4. **An engine test silently testing a moved game through a stale import path** (collision, animation and golden-trace tests borrow these games): every `glitchygames.examples.<game>` reference outside `plans/` is gone after its move (Tasks 3, 4, 7, 8: `git grep` in the verify step must print nothing).
5. **PaddleSlap's recordings renamed by accident**: its `Game.__module__` must stay `paddleslap` (Task 7, `test_paddleslap_game_keeps_its_logical_name`).

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

- [ ] **Step 1: Write the failing tests** — update the existing ones to `member_packages=('mr_muncher',)`; add `test_a_game_depending_on_a_member_ships_both_archives` (a specification with `member_packages=('brave_adventurer_core', 'brave_adventurer_papyrus')` lists both zips in its pyscript config, the one depended on first, and `write_bundle` writes both).
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

### Brave Adventurer: one project, two games, one launcher (Tasks 4-6)

Brave Adventurer and its Egyptian edition, Papyrus, become one project built and published
together (the user, 2026-10-25): distribution `brave-adventurer`, directory
`src/games/brave-adventurer/`, in a src layout of layered import packages:

```
src/games/brave-adventurer/
  pyproject.toml               one distribution; console script brave-adventurer (the launcher)
  src/
    brave_adventurer_core/     the primitives both games share
    brave_adventurer/          Classic: its scene, player, enemies, drawn sprites, voice assistant
    brave_adventurer_papyrus/  Papyrus: its scene, TOML sprites, sprite_utils
    brave_adventurer_modes/    the launcher: a title screen, `--game classic|papyrus`
  tests/
    core/  classic/  papyrus/  each layer's own tests
    test_modes.py              the launcher, and both games started through it
    fixtures/replays/          golden-classic.jsonl.gz, golden-papyrus.jsonl.gz
```

The rules (the user's): only mechanical DRY moves, with no change to game state, timing,
randomness, physics, drawing output or recordings; the two games' different sprite behaviours
stay separate; `brave-adventurer-papyrus` and its `/play/` page go (the launcher is the one
entry). After every step, run only these games' tests, both golden replays and the Brave
Adventurer golden trace (never the full suite until Task 9):

```bash
uv run pytest --dummy-only --no-cov -q src/games/brave-adventurer/tests \
    tests/world/test_golden_traces.py -k "brave" \
    tests/replay/test_golden_replays.py -k "brave"
```

What can move (the audit, 2026-10-25): recordings and golden traces name sprites by class name
and creation order only (`glitchygames/tracing.py`: `type(sprite).__name__ + '#' + n`), and
scenes by logical name. So a class may move between modules, but no sprite class is renamed and
no sprite is created in a different order; each scene class stays in its game's `game.py`.

### Task 4: Move both games into one project, sharing their primitives

**Files:** the recipe (`docs/architecture/game_packages.md`, steps 1-7), for one member with
four import packages in a src layout (`WorkspaceMember.package_relative_paths`:
`src/brave_adventurer_core` and so on). Specifics:
- `brave_adventurer_core` takes what Papyrus already borrows from Classic, moved unchanged
  (about 950 lines): the shared constants (physics, camera, layers, parallax, scoring, pits,
  stone, sand, HUD, the player's speeds, lives, wall width, the death and game-over rumbles);
  `sounds.py`; `GroundSegment`, `StoneWall` and their drawers `draw_ground_segment`,
  `draw_stone_wall`; the parallax drawing (`_vertical_gradient` and its module-level cache,
  `draw_sky`, `draw_pyramids`, `_dune_top_y`, `draw_dunes_and_oasis`,
  `draw_near_ground_details`); `ScreenData`, `LEVEL_1`, `LevelManager`. Classic-only drawing
  constants (its sprite sizes and colours, arm and leg swing, rock and grass) stay in
  `brave_adventurer`.
- `LevelManager` gains a collectible-class hook beside `_get_enemy_class_map`; the core's
  imports no game's sprites, so each game gives its own (`GoldScarab`, `PapyrusGoldScarab`) and
  Papyrus's copied `_build` is deleted. Creation order is unchanged.
- Not shared (behaviour differs, or tangled with each sprite's animation): the players, the
  enemies' movement, the gold scarabs, the sprite drawers.
- Tests: `tests/examples/test_brave_adventurer_sounds.py` and `brave_adventurer_golden/*.npy` to
  `tests/core/`; `tests/examples/test_brave_adventurer_game.py` split into `tests/classic/`,
  `tests/papyrus/`, and tests parametrized over both editions in `tests/core/` (or kept
  parametrized in one place: one file per name, BUGS.md #31). Its package scans
  (`BRAVE_ADVENTURER_PACKAGE.glob`, `PAPYRUS_PACKAGE`) gain the core.
- Goldens: `tests/fixtures/replays/brave-adventurer/golden.jsonl.gz` and
  `.../brave-adventurer-papyrus/golden.jsonl.gz` to the member's `tests/fixtures/replays/`
  as `golden-classic.jsonl.gz` and `golden-papyrus.jsonl.gz` (bytes unchanged; two
  `RECORDING_PATH_RENAMES` lines). Until Task 5 the member keeps both console scripts, so each
  still replays through its own.
- `MEMBER_LAYERS` gains all four packages (`games`); `EXAMPLES_LAYERS` loses both games.
- Outside users: `tests/collision/test_collision.py`, `tests/animation/test_animation.py`,
  `tests/sprites/test_animated_sprite.py`, `tests/world/test_golden_traces.py`,
  `tests/benchmarks/test_benchmarks.py`, `tests/test_browser_touch_controls.py`,
  `scripts/audit_hitboxes.py`, `scripts/record_golden_traces.py`.
- Browser: both `GAMES` entries ship `member_packages=('brave_adventurer_core', 'brave_adventurer')`
  and `('brave_adventurer_core', 'brave_adventurer_papyrus')` (Task 2).

- [ ] **Step 1: Write the failing tests** — `test_both_games_keep_their_logical_names` (each
  scene class's logical name is unchanged), `test_the_old_example_packages_are_gone`,
  `test_both_goldens_keep_their_history`, `test_the_core_imports_neither_game` (no module of
  `brave_adventurer_core` imports `brave_adventurer` or `brave_adventurer_papyrus`),
  `test_each_level_manager_builds_its_own_gold_scarab`.
- [ ] **Step 2: Run** → FAIL. **Step 3:** move first (the recipe), then the core extraction,
  then the `LevelManager` hook, running the games' check above after each.
- [ ] **Step 4: Verify** — the check above passes, both goldens replaying strictly through their
  own console scripts; recipe step 8's configuration and lint commands; the `git grep` for
  `glitchygames.examples.brave_adventurer` prints nothing.
- [ ] **Step 5: Commit** — `"Workspace packages: Brave Adventurer and Papyrus as one project, sharing their primitives"`

### Task 5: The launcher

**Files:**
- Create: `src/games/brave-adventurer/src/brave_adventurer_modes/` (`__init__.py` with `main`,
  `title.py` with the title scene), `tests/test_modes.py`
- Modify: the member's `pyproject.toml` (one console script, `brave-adventurer =
  "brave_adventurer_modes:main"`), `scripts/build_browser_bundle.py` (one `GAMES` entry,
  `brave-adventurer`, shipping all four packages; Papyrus's entry and touch layout go),
  `scripts/record_scripted_session.py` and `scripts/record_golden_traces.py` (fixture paths),
  `docs/games/brave_adventurer.md`, the `/play/` pages (Papyrus's goes)

**Interfaces:**
- Produces: `brave_adventurer_modes.main() -> None`; `GAMES_BY_NAME: dict[str, Callable[[], None]]`
  (`'classic'` -> `brave_adventurer.main`, `'papyrus'` -> `brave_adventurer_papyrus.main`);
  `game_for_recording(*, path: Path) -> str | None` (the name of the game whose scene the
  recording's header names by logical name, or None when the recording is not one of these
  games'); `TitleScene` (its own `NAME`; choosing sets `next_scene` to the chosen game's scene).
- How it starts a game: `--game classic|papyrus` is read with `parse_known_args` and removed from
  `sys.argv`, then that game's own `main()` runs unchanged (each game's arguments, scene flow,
  header and recordings stay its own). With a recording to replay among the arguments, the
  launcher reads its header (`game_for_recording`) and starts that game, skipping the title
  screen: so a member with one console script replays both goldens
  (`glitchygames/testing/replays.py` `recording_console_script` is unchanged). With neither, the
  title screen offers both games, a line each on how they differ.

- [ ] **Step 1: Write the failing tests** — `test_the_game_flag_starts_that_game_without_its_flag`
  (`--game papyrus` runs Papyrus's `main` with `sys.argv` minus `--game papyrus`),
  `test_an_unknown_game_is_an_error` (exit status 2 and a message naming both),
  `test_a_recording_starts_its_own_game` (each golden starts its game, no title screen),
  `test_a_recording_of_another_game_is_an_error` (a Mr. Muncher recording: a clear error, not
  the title screen), `test_choosing_on_the_title_screen_starts_that_game`,
  `test_the_version_flag_still_works`, `test_both_goldens_replay_through_the_launcher`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**; remove `brave-adventurer-papyrus`.
- [ ] **Step 4: Verify** — the games' check above; `uv run nox -s browser -- brave-adventurer`
  builds one page whose bundle holds all four archives.
- [ ] **Step 5: Commit** — `"Brave Adventurer: one launcher for both games (the Papyrus command goes)"`

### Task 6: One scene base for both games

**Files:**
- Create: `src/games/brave-adventurer/src/brave_adventurer_core/scene.py` (`BraveAdventurerSceneBase`)
- Modify: `brave_adventurer/game.py`, `brave_adventurer_papyrus/game.py` (each keeps its
  concrete scene class, its name and module, and `main`)

**Interfaces:**
- Produces: `BraveAdventurerSceneBase(Scene)` holding the two scenes' identical code (about 750
  lines: terrain snapping, foot and support spans, wall entry, collision callbacks, death and
  respawn, high scores, pause, input, `render`, pits, HUD, `args`), with hooks for what differs
  (the audit): the player's foot line (Classic from its hitbox, a `float`; Papyrus from a fixed
  height, an `int`: each keeps its type), the player's starting y, the scarab class for terrain
  collisions, the save name, `NAME`, the setup log line, and Classic's voice assistant (a hook
  Papyrus leaves empty).
- `__init__` keeps its order exactly: the parallax layers, then the level, then the player.

- [ ] **Step 1: Write the failing test** — `test_both_scenes_share_one_base`; the two goldens and
  the trace are the behavioural test (they replay strictly).
- [ ] **Step 2: Implement** one hook at a time, running the games' check above after each.
- [ ] **Step 3: Verify** — the check above passes with both goldens unchanged, and
  `git diff --stat` shows the duplicate lines gone.
- [ ] **Step 4: Commit** — `"Brave Adventurer: one scene base for both games (no behaviour change)"`

### Task 7: Move PaddleSlap, and its bundled demo

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

- [ ] **Step 1: Write the failing tests** — in `src/games/paddleslap/tests/test_paddleslap_after_the_move.py` (a name of its own: Mr. Muncher has `test_logical_names_after_the_move.py`, and `tests/test_suite_collection.py` refuses a name used twice), `test_paddleslap_game_keeps_its_logical_name` (`logical_name(scene_class=Game) == 'games.paddleslap:Game'` and `Game.__module__ == 'paddleslap'`), `test_the_old_example_module_is_gone` (`find_spec('glitchygames.examples.paddleslap') is None`), `test_bundled_demos_are_found_in_member_packages` (`bundled_demo_paths()` returns `('paddleslap', <member>/paddleslap/demos/rally.jsonl.gz)`), `test_the_rally_demo_keeps_its_whole_history` (both old paths map to the new one), `test_paddleslaps_golden_keeps_its_history`.
- [ ] **Step 2: Run** → FAIL. **Step 3:** the recipe, steps 1-7, and the demo discovery above.
- [ ] **Step 4: Verify** — recipe step 8; `uv run python -m scripts.replay_metrics measure --only rally` (or the new `--only` name) measures the demo from its new place; the `git grep` for `glitchygames.examples.paddleslap`, `glitchygames/examples/paddleslap`, `paddleslap_demos`, `fixtures/replays/paddleslap` (`-- ':!plans' ':!quality' ':!BUGS.md'`) prints only what stays on purpose (recipe step 5): the `RECORDING_PATH_RENAMES` lines and their tests, and the member's after-the-move test; `plans/`, `quality/` and `BUGS.md` are history and are excluded. `tests/replay/test_record_scripted_session.py::test_every_game_has_a_fixture_location` uses PaddleSlap as its root-layout example since Task 3: point it at Drawing Fire, the one game not yet moved, and add PaddleSlap to `test_a_member_games_fixture_is_directly_in_the_members_replay_fixtures`.
- [ ] **Step 5: Commit** — `"Workspace packages: PaddleSlap as its own package, its demo inside it"`

### Task 8: Move Drawing Fire

**Files:** the recipe, for package `drawing_fire`, directory `src/games/drawing-fire/`. Specifics:
- Its sprite `drawing_fire/sprites/soldier.toml` ships as package data (read through `Path(__file__).parent`; its tests use `drawing_fire.__file__`).
- Tests: `tests/examples/drawing_fire/` → `src/games/drawing-fire/tests/` (drop its `__init__.py`; its `conftest.py`, the event-queue drain, becomes the member's `tests/conftest.py`). `test_simulation.py` imports `scripts.simulate_drawing_fire`, which imports `battle` and `drivers`: update the script's imports.
- `tests/replay/test_golden_replays.py`: `DRAWING_FIRE_CONTROLS` (built from `drawing_fire.players`' scancode lists), `_drawing_fire_snapshot_control`, its `GAMEPLAY_ACTION_MAPS`, `ENGINE_SCENE_CONTROLS`, `GAMES_WITHOUT_A_PAUSE` and `UNEXERCISED_CONTROLS` entries, and `test_the_drawing_fire_golden_replay_holds_a_death_and_a_takeover` follow the import. `scripts/record_scripted_session.py` `POLLED_INPUT_GAMES` keys by game, so it needs no change; `scripts/record_golden_traces.py` imports `DrawingFireScene`, `LEAVE_HOLD_SECONDS` and `Stage`.
- Browser: `GAMES['drawing-fire']` gets `member_packages=('drawing_fire',)`; it stays in `GAMES_WITHOUT_TOUCH_CONTROLS`.
- Golden: `tests/fixtures/replays/drawing-fire/golden.jsonl.gz`.

- [ ] **Step 1: Write the failing tests** — in `src/games/drawing-fire/tests/test_drawing_fire_after_the_move.py` (a name of its own, as Task 7's), `test_drawing_fire_keeps_its_logical_names` (`games.drawing_fire.game:DrawingFireScene`), `test_the_old_example_package_is_gone`, `test_drawing_fires_golden_keeps_its_history`, `test_the_soldier_sprite_ships_in_its_wheel` (`uv build --package drawing-fire`: the wheel holds `drawing_fire/sprites/soldier.toml`).
- [ ] **Step 2: Run** → FAIL. **Step 3:** the recipe, steps 1-7.
- [ ] **Step 4: Verify** — recipe step 8; `uv run python -m scripts.simulate_drawing_fire --seeds 2` runs; the `git grep` for its old paths (`glitchygames.examples.drawing_fire`, `glitchygames/examples/drawing_fire`, `fixtures/replays/drawing-fire`, `-- ':!plans' ':!quality' ':!BUGS.md'`) prints only what stays on purpose (recipe step 5): the `RECORDING_PATH_RENAMES` lines and their tests, and the member's after-the-move test; `plans/`, `quality/` and `BUGS.md` are history and are excluded. After this move no game is left in the root layout: `tests/replay/test_record_scripted_session.py::test_every_game_has_a_fixture_location` loses its root-layout example (it checks that every game's fixture is in its member), and Drawing Fire joins `test_a_member_games_fixture_is_directly_in_the_members_replay_fixtures`.
- [ ] **Step 5: Commit** — `"Workspace packages: Drawing Fire as its own package"`

### Task 9: Part 2's end state, docs and verification

**Files:**
- Modify: `src/glitchygames/logical_names.py` (`EXAMPLES_LAYERS` keeps only the three demos; its comment says Part 3 deletes it), `tests/test_logical_names.py`, `docs/glitchygames/examples/index.md` (only the demos), `docs/architecture/game_packages.md` (the layout's examples line; Part 2's lessons, if any changed the recipe), `README.md` and `CLAUDE.md` (every game is its own package), `plans/2026-10-24-workspace-packages.md` (Part 2 DONE, with its commits; Part 2's outline names Drawing Fire), `plans/future-features.md` (anything left over)
- Test: `tests/test_workspace_packages.py`

- [ ] **Step 1: Write the failing test** — `test_the_engines_examples_hold_only_the_demos_and_bitmappys_resources` (the entries of `src/glitchygames/examples/` other than `__init__.py`, `__pycache__` and `foo2.toml` are exactly `dt_demo.py`, `joystick_demo.py`, `text_input_demo.py`, `resources`); `test_the_root_goldens_are_the_engines_own` (`tests/fixtures/replays/` holds no game's directory).
- [ ] **Step 2: Run** → FAIL until the tables and docs follow; then make them follow.
- [ ] **Step 3: Verify the whole part** — `uv sync --all-extras --all-groups --all-packages`; `CI=true uv run nox -s test`; `uv run pytest` (both drivers, 100%); `uv run nox -s lint static-analysis lint-docs`; `uv run nox -s build-wheel` (the engine's wheel holds no game: its file list has no `clockwork_keep/`, `brave_adventurer*/`, `paddleslap`, `drawing_fire/`); `uv build --all-packages`; `uv run nox -s browser -- <each game>` builds; into a scratch venv, `pip install --find-links dist "glitchygames[games]"` from those built wheels (the games are not on PyPI) installs the engine and all six games, and each console script starts; `uv run nox -s docs-deploy -- --build-only`.
- [ ] **Step 4: Commit** — `"Workspace packages, Part 2: every game is its own package"`
