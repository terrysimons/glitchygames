# Workspace Packages, Part 3: The Demos, the `src/` Layout, and Members Kept Apart — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** PLANNED (2026-10-26), awaiting the user's review; no code written. Written from a
read-only survey of `feature/workspace-packages-4-bitmappy` at fc4a93d5 (PR #110), which becomes
`main` when #110 merges. **Before any stage starts, check `main` against this plan** (the user,
2026-10-26: "verify that main is correct before actually doing the work"):
- `git diff fc4a93d5 origin/main --stat` must be empty apart from merge bookkeeping. If #110 was
  squashed, compare the trees.
- `uv run pytest` must pass on `main`.
- Spot-check every `path:line` this plan cites for the stage about to start.

If anything differs, correct the plan before branching.

**Goal:**
- **Stage A:** every workspace member keeps its import packages under `<member>/src/`.
- **Stage B:** the engine's three demos become members of the `demos` layer, and
  `src/glitchygames/examples/` is deleted.
- **Stage C:** the engine's tests stop importing members by name, and Part 4's Bitmappy-only
  guards cover every member.

**Architecture:** One plan in three stages, done in order on **one branch,
`feature/workspace-packages-3a-src-layout`, for one PR** (the user, 2026-10-26). Each stage
ends with its own verification before the next starts.
- **Stage A** is a mechanical relayout of the five flat members (Brave Adventurer is already
  laid out this way, and is the precedent).
- **Stage B** moves the demos, following the recipe (`docs/architecture/game_packages.md`), and
  rehomes what is left of `examples/`.
- **Stage C** rehomes the engine tests that "borrow" a game and generalizes the guards.

No recording is re-recorded and no logical name changes: package names stay the same.

**Tech Stack:** Python 3.14, uv workspaces (hatchling members), pygame-ce, pytest (100% branch
coverage; dummy and native drivers), ruff, basedpyright, ty, mkdocs strict + mkdocs-gen-files,
PyInstaller, Pyodide browser bundles.

**Spec:** `plans/2026-10-24-workspace-packages.md`: decisions 1-10, "What every part keeps true",
and the Part 3 outline, which records the user's decisions of 2026-10-26. The recipe is
`docs/architecture/game_packages.md`. `plans/2026-10-26-workspace-packages-4-bitmappy.md` is the
model for conventions. The untracked draft `plans/2026-10-25-workspace-packages-2-games-demos-apps.md`,
Tasks 10-12 and 18, is a starting point only. Where it disagrees with this plan, this plan wins:
its `<pkg>_tests/` packages, `tests/moved_games.py` and `tests/sprites/test_bundled_sprites.py`
don't exist.

## Decisions (the user's, 2026-10-26)

1. **Every member in a `src/` layout:** `<member>/src/<package>/`. The demos are created this
   way; Bitmappy and the four flat games are converted.
2. **Part 3 is the mechanical move only.** The demos experience (#57) is planned afterward.
3. **The four WAVs are kept** as engine resources, in `src/glitchygames/resources/sounds/`.
4. **The shared sprite-file checks** move into an engine testing helper,
   `src/glitchygames/testing/sprite_files.py`.
5. **Decision 10:** a member declares what it imports. The demos declare `glitchygames` and
   `pygame-ce`.
6. **The demos get no browser build.** The guard "every game has a browser build" exempts the
   `demos` layer.
7. **Engine tests stop borrowing members.** The engine tests that import a game or demo by name are
   rehomed: into the member, onto a stand-in, or onto workspace discovery. A guard then forbids
   any root test from importing a member package.
8. **An automated engine-wheel test** is added.
9. **The browser engine archive** is built from git-tracked files only. This fixes the bug where
   ignored files such as `.DS_Store` ship in local builds.
10. **Part 4's guards cover every member:**
    - test modules are named for the member, `test_<distribution with - as _>*.py`, so Mr.
      Muncher's `test_logical_names_after_the_move.py` becomes `test_mr_muncher_after_the_move.py`;
    - the engine source imports no member.
11. **The engine keeps its own tests for whatever a relocated test covered** (the user,
    2026-10-26: "For anything we relocate into the games, we should make sure the engine has tests
    for any gapped functionality that the migrated tests were covering").
    - A full run counts members' tests toward the engine's coverage, so the 100% gate can't see
      this gap.
    - It is measured instead: **engine coverage from the root `tests/` alone**, before and after
      every relocation. Any engine line or branch that the relocation leaves covered only by a
      member's test gets a new engine test in `tests/`. That test uses an engine stand-in, never
      the member.
    - See Global Constraints, "Engine-only coverage".

**Calls made while planning** (the controller's, from the survey; the user may overturn any):
- **The test prefix is the distribution name with `-` as `_`.** Brave Adventurer's four packages
  share `test_brave_adventurer_*`, which all eight of its files already use.
- **A demo's `__init__.py` drops the shebang and the executable bit.** It is no longer a script:
  `python -m <package>` and the console script are the entry points. Without the shebang, ruff's
  EXE002 would flag a file left executable.
- **The sprite-file helper is engine code.** It is rewritten to engine standards (typed, 100%
  covered, functions named `check_*` so pytest never collects them), and it imports pytest at
  module level, as `glitchygames.testing.replays` does. `glitchygames.testing.__init__` never
  imports it, so the engine's runtime never needs pytest.

## Open questions (answered by the user, 2026-10-26)

1. **Local leftovers: DECIDED, delete them.** Check each with `git ls-files` (it must print
   nothing), then `rm -rf`:
   - `src/glitchygames/examples/**/__pycache__` and `tests/examples/__pycache__` (Stage B)
   - `src/glitchygames/scenes/builtin/` (only `__pycache__`; it resolves as a namespace package)
   - the empty `src/glitchygames/build/bitmappy`, `src/glitchygames/dist` and
     `src/glitchygames/.benchmarks`
   - `.DS_Store` files under `src/glitchygames`
   The ones outside `examples/` go before Stage A.
2. **One PR: DECIDED.** Stages A, B and C on one branch.
3. **The branch: DECIDED,** `feature/workspace-packages-3a-src-layout`, from `main` after #110
   merges and after the check of `main` above.

## Global Constraints

- The branch starts from the latest `main` after #110 merged, after the check above. Never push or open a PR without the user's go-ahead. Never restore files from git.
- Layers: `src/glitchygames` (engine), `src/games`, `src/demos`, `src/apps`. Each member's import
  packages live under `<member>/src/`.
- Names:
  - directories and distributions are kebab-case (`dt-demo`)
  - import packages are snake_case (`dt_demo`)
  - console scripts: `dt-demo = "dt_demo:main"`, `joystick-demo = "joystick_demo:main"`,
    `text-input-demo = "text_input_demo:main"`
  - logical names: `demos.<package>:<class>`
- Member tests are rootless (`<member>/tests/`, no `__init__.py`) and named
  `test_<distribution with - as _>*.py`. Test-file names are unique across every test root.
- Coverage stays at 100% (branch) over the engine and every member.
- **Engine-only coverage (decision 11).** Applies to any task that relocates a test out of the
  root `tests/`: B1, B3 and B4 (the demos' tests), and C2.
  - **Before the relocation:** save the engine's coverage from the root tests alone:
    `uv run pytest --dummy-only -q tests --cov=glitchygames --cov-branch --cov-report=json:<scratch>/engine-before.json --cov-fail-under=0`.
  - **After it:** save the same report as `engine-after.json`.
  - **Compare them:** any engine line or branch covered before and not after is a gap that the
    task closes. The fix is a new engine test in `tests/`, named for the behavior and using an
    engine stand-in (never the member), until the after-report covers it.
  - **The task report** lists each gap and the test that closes it, or "no gaps".
  - **Don't count a fresh gap as a pre-existing one.** Today's baseline may not be 100% from the
    root tests alone. Engine code that only member tests reach is outside this plan; record it in
    `plans/future-work.md` as found. A gap the relocation creates must be closed.
  - A helper script is optional. If one is written, it goes in `scripts/`, with tests, as
    `scripts/engine_only_coverage.py` with
    `newly_uncovered(*, before: Path, after: Path) -> list[str]`.
- No `# noqa`, `# ruff: ignore` or type-ignore additions; no lint or type configuration loosened.
  Configuration only grows to name members and layers. Moving an existing per-file ignore key
  with its file is allowed.
- pytest-mock `mocker` only; keyword arguments; full names, no abbreviations; Google docstrings;
  100 columns; American spelling.
- Lint (ruff, basedpyright, `uv run ty check`) before tests. TDD: see each new test fail first.
- Path rewrites use `perl -pi -e` with `\b` over `git grep -l ... -- ':!plans' ':!quality' ':!BUGS.md'`;
  read the whole diff.
- After `git mv` of a package, `rm -rf` its old directory, since ignored `__pycache__` left
  behind is importable.
- After changing a member's hatch `packages`, run `uv lock` and then
  `uv sync --all-extras --all-groups --all-packages`. Check that the member's editable `.pth`
  now points at `<member>/src`.
- The pre-commit `replay-metrics` hook measures commits touching `src/`, `uv.lock` or
  `pyproject.toml`, and stages its rows. Never `--no-verify` or `SKIP=`. It refuses untracked
  files under `src/`.
- Recordings move only by `git mv`, with their bytes unchanged, plus `RECORDING_PATH_RENAMES`
  lines: one from each old path to the final path.
- Stage explicitly; never `git add -A` or `.`. Each commit message ends with
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Review Focus

1. **A stale configuration entry that still names the old flat path.** For example,
   `src/games/clockwork-keep` left in ruff `src` beside the new `src/games/clockwork-keep/src`.
   No guard catches this today. Stage A's guard asserts every root configuration entry naming a
   member path is one the workspace derives (Task A1).
2. **An editable install still pointing at the member root after the relayout.** The package
   would then still import from the old place in a stale `.venv`. Each member's
   `test_<package>_after_the_move.py` asserts `<package>.__file__` lies under `<member>/src/`, or
   under `site-packages` in a wheel install (Tasks A2-A4).
3. **PaddleSlap's rally demo history** after its third move: every old path must resolve to the
   committed file (`test_every_rename_ends_at_a_committed_recording`, Task A3).
4. **A demo that no longer runs as it used to:**
   - `python -m <package>` and the console script both start it (Tasks B3-B4, with
     `__main__.py` covered)
   - its power-on test in `tests/engine/test_engine_lifecycle.py` passes
   - `demos.joystick_demo:Game` and `games.paddleslap:Game` both still resolve while loaded
     together
5. **An engine test silently losing its subject when borrows move (Stage C).** The test count
   before and after each move must match, apart from new tests. A cross-member infrastructure
   test that discovers members must assert it found each one it expects, so it can't pass on
   zero.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/{apps,games}/<member>/src/<package>/` | each member's import packages (Stage A) |
| `src/demos/{dt-demo,joystick-demo,text-input-demo}/` | the three demo members, each `pyproject.toml`, `README.md`, `src/<package>/{__init__,__main__}.py`, `tests/` (Stage B) |
| `src/glitchygames/testing/sprite_files.py` (new) | the shared sprite-file checks, importable by any member (Stage B) |
| `tests/sprites/test_engine_sprite_files.py` (new) | the engine's own run of those checks (Stage B) |
| `src/glitchygames/resources/sounds/` (new) | the four WAVs, engine package data (Stage B) |
| `scripts/build_browser_bundle.py` | the engine archive from tracked files (Stage B) |
| `tests/test_engine_wheel.py` (new) | the engine wheel's contents (Stage B) |
| `src/glitchygames/logical_names.py` | `EXAMPLES_*` deleted; `MEMBER_LAYERS` gains the demos (Stage B) |
| `tests/test_workspace_config.py`, `tests/test_suite_collection.py` | the `src/` layout guard and the stale-entry guard (A); the guards generalized (C) |
| root `pyproject.toml`, `pyrightconfig.json`, `noxfile.py`, `wily.cfg`, `mkdocs.yml`, `uv.lock` | every member and layer named |
| `docs/architecture/game_packages.md`, `CLAUDE.md`, `README.md`, `docs/games/*.md` | the recipe and layout |

---

## Stage A: every member in a `src/` layout

### Task A1: The guards fail first: packages under `<member>/src/`, no stale entries

**Files:** `tests/test_workspace_config.py` (test), and nothing else yet.

**Interfaces:**
- Produces:
  - `members_with_packages_outside_src(*, members: Sequence[WorkspaceMember]) -> list[str]`
  - `stale_member_paths_in_configuration(*, project_root: Path, members: Sequence[WorkspaceMember]) -> list[str]`

  Both are in `tests/test_workspace_config.py`.
  - The first reads `WorkspaceMember.package_directories` from the **real** workspace, so the
    synthetic flat projects in other tests keep working.
  - The second reads the root configuration lists that name member paths: ruff `src`, ty
    `environment.root`, the pyright environments' `root` and `extraPaths`, `noxfile`
    `_SOURCE_PACKAGE_DIRS`, mkdocstrings `paths`, and `[tool.coverage.paths]`. It reports any
    entry under a member directory that isn't an import root, a package directory, the member's
    tests directory, or the member directory itself in the lists that take it (`include`,
    `_CODE_DIRS`, `wily.cfg`).

- [ ] **Step 1:** write `test_every_member_keeps_its_packages_under_src` and
  `test_no_configuration_entry_names_a_member_path_the_workspace_does_not_derive`. Give each a
  self-test that uses a synthetic member and configuration in `tmp_path`.
- [ ] **Step 2:** run them. The first fails, listing bitmappy, clockwork-keep, drawing-fire,
  mr-muncher and paddleslap. The second passes today; its self-test proves it catches a planted
  stale entry.
- [ ] **Step 3:** commit — "Guards: every member's packages under src/, and no stale member paths
  in configuration" (the first test is marked `xfail(strict=True)` with the reason "Stage A converts
  the flat members", and that marker comes off in Task A4).

### Task A2: Clockwork Keep, Drawing Fire and Mr. Muncher move into `src/`

These are pure moves: no recording, no data path in code.

**Files, per member:**
- Move: `<member>/<package>` to `<member>/src/<package>`. Drawing Fire's `sprites/soldier.toml`
  moves with its package.
- Modify:
  - `<member>/pyproject.toml` hatch: `packages = ["src/<package>"]`
  - root `pyproject.toml`: `[tool.coverage.paths]` (`src/games/<game>/src/<package>`), ruff
    `src` (`<member>/src`), ty `environment.root` (`<member>/src`)
  - `pyrightconfig.json`: every tests environment's `extraPaths` (all seven copies) and the
    member environment `{"root": "<member>", "extraPaths": ["src", "<member>/src"]}`, Brave
    Adventurer's form
  - `noxfile.py` `_SOURCE_PACKAGE_DIRS`
  - `mkdocs.yml` mkdocstrings `paths`
  - `scripts/record_golden_traces.py:508,603` (docstrings)
  - `tests/test_gen_ref_pages.py:28` (Mr. Muncher's hard-coded package directory)
  - `tests/ast_scanning.py:102` (docstring)
  - `tests/replay/test_golden_replays.py:391` (comment)
  - `tests/test_code_tree.py:123-125,153` (synthetic flat paths, kept consistent)
  - each member's `test_<package>_after_the_move.py` gains
    `test_<package>_is_imported_from_its_src_directory`. Mr. Muncher's file is still named
    `test_logical_names_after_the_move.py` until Stage C.
- Unchanged: `wily.cfg`, ruff `include` and `namespace-packages`, ty `src.include`, pyright
  `include`, `_CODE_DIRS` (they name the member directory).

- [ ] **Step 1:** write the three `..._is_imported_from_its_src_directory` tests and run them.
  They fail, because the package is under the member root.
- [ ] **Step 2:** `git mv` each package, `rm -rf` its old directory, then do the configuration
  edits, then `uv lock` and `uv sync --all-extras --all-groups --all-packages`. Check each
  `.venv/**/_editable_impl_<package>.pth`.
- [ ] **Step 3:** lint, then run each member's tests, `tests/test_workspace_config.py`,
  `tests/test_workspace_packages.py`, `tests/test_gen_ref_pages.py`,
  `tests/replay/test_golden_replays.py` and `tests/world/test_golden_traces.py`, then
  `uv run --extra dev nox -s lint-docs`.
- [ ] **Step 4:** commit — "Clockwork Keep, Drawing Fire and Mr. Muncher keep their packages under
  src/".

### Task A3: PaddleSlap moves into `src/`, and its rally demo's history follows

**Files:**
- Move: `src/games/paddleslap/paddleslap` to `src/games/paddleslap/src/paddleslap`, including
  `demos/rally.jsonl.gz`, whose bytes don't change.
- Modify:
  - the same configuration as Task A2
  - the ruff per-file ignore key `"src/games/paddleslap/paddleslap/__init__.py"`
    (`pyproject.toml:460-466`) becomes `.../src/paddleslap/__init__.py`
  - `src/glitchygames/recording_metrics.py:85-92` `RECORDING_PATH_RENAMES`: both existing keys
    are re-pointed, and a new key from `src/games/paddleslap/paddleslap/demos/rally.jsonl.gz` is
    added, all to `src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz`
  - `src/games/paddleslap/tests/test_paddleslap_after_the_move.py:18-22` (the repository path,
    plus `RALLY_DEMO_FORMER_PATHS` gaining its third entry)
  - the tests that use the path as data: `tests/test_code_tree.py:84`,
    `tests/test_generate_performance_graphs.py:50`, `tests/test_recording_metrics.py:526,533`,
    `tests/test_replay_metrics.py:601`
  - docstrings at `src/glitchygames/randomness.py:34` and `scripts/replay_metrics.py:246`

- [ ] **Step 1:** write `test_paddleslap_is_imported_from_its_src_directory` and extend the rally
  demo's former-paths test to the third path. Both fail.
- [ ] **Step 2:** move, `rm -rf` the old directory, configure, `uv lock`, sync.
- [ ] **Step 3:** lint, then run `src/games/paddleslap/tests`, `tests/replay`,
  `tests/test_recording_metrics.py`, `tests/test_replay_metrics.py`,
  `tests/test_bundled_demo_discovery.py`, `tests/test_code_tree.py` and
  `tests/test_generate_performance_graphs.py`. Run `uv run python -m scripts.replay_metrics`
  only in a dry form if one exists; otherwise rely on `test_every_rename_ends_at_a_committed_recording`.
- [ ] **Step 4:** commit — "PaddleSlap keeps its package under src/; its rally demo's history
  follows".

### Task A4: Bitmappy moves into `src/`

**Files:**
- Move: `src/apps/bitmappy/bitmappy` to `src/apps/bitmappy/src/bitmappy`, with its resources.
- Modify:
  - the same configuration as Task A2. Ruff `src` keeps its extra `src/apps/bitmappy/tests`
    entry.
  - `bitmappy.spec:47` `datas`: `('src/apps/bitmappy/src/bitmappy/resources', 'bitmappy/resources')`
  - `scripts/audit_hitboxes.py:67` `PRIORITY_TIERS[2]`
  - `src/apps/bitmappy/tests/test_bitmappy_after_the_move.py:23` `MEMBER_PACKAGE_DIRECTORY`,
    plus `test_bitmappy_is_imported_from_its_src_directory`. The existing
    `test_bitmappy_is_imported_from_its_member` is tightened to `src/`.
  - `.gitignore:194` (comment)
  - docstrings: `animated_canvas.py:208`, `editor_setup.py:418`, `frame_operations.py:47`, and
    the first line of ten test modules (the survey's list), plus
    `test_bitmappy_canvas_panning.py:749`
  - remove `xfail(strict=True)` from Task A1's layout test

- [ ] **Step 1:** write `test_bitmappy_is_imported_from_its_src_directory`; it fails.
- [ ] **Step 2:** move, `rm -rf` the old directory, configure, `uv lock`, sync. The
  `test_bitmappy_packaging.py` spec test derives the package parent from `bitmappy.__file__`, so
  it follows without changes; confirm it.
- [ ] **Step 3:** lint, then run `src/apps/bitmappy/tests`, `tests/test_workspace_config.py`,
  `tests/test_build_browser_bundle.py` and `tests/test_suite_collection.py`, then
  `CI=true uv run --extra dev nox -s test`. Task A1's layout test now passes with no `xfail`.
- [ ] **Step 4:** commit — "Bitmappy keeps its package under src/; every member does now".

### Task A5: Docs, then Stage A's verification

**Files:**
- `docs/architecture/game_packages.md`:
  - the layout tree (:35-42)
  - the template `packages = ["src/<package>"]` (:61-62)
  - the move command (:131)
  - the flat-layout pyright note (:169), now "every member"
  - the docs path (:233)
  - "A game that is one module" (:312-320): `src/paddleslap/__init__.py`
- `docs/games/{mr_muncher,clockwork_keep,drawing_fire,paddleslap}.md`: the file tables and paths
- `CLAUDE.md`, `README.md`, `CONTROLLER_CONTROLS_README.md`, `docs/architecture/bitmappy.md`,
  `docs/architecture/argument_system.md`, `docs/multi_controller_system.md`,
  `src/glitchygames/ai/{INTEGRATION,README}.md`: every member path (the survey's list)
- The master plan: Part 3, Stage A done.

- [ ] **Step 1:** write the docs, then run `lint-docs` and `tests/test_suite_collection.py` (the
  living-docs path guard).
- [ ] **Step 2:** verify the whole stage:
  - `uv run --extra dev nox -s lint static-analysis`
  - `CI=true uv run --extra dev nox -s test`
  - `uv run pytest` (both drivers)
  - `uv run --extra dev nox -s build-wheel`; each member wheel holds only its packages
  - `nox -s build-binary`; the user starts `dist/bitmappy` and loads a sprite
  - the PaddleSlap browser bundle builds
- [ ] **Step 3:** commit — "Docs: every member in a src/ layout". Report Stage A's results, then
  continue with Stage B (one PR: no stop between stages).

---

## Stage B: the demos layer, and `examples/` gone

### Task B1: The shared sprite-file checks become `glitchygames.testing.sprite_files`

**Files:**
- Create:
  - `src/glitchygames/testing/sprite_files.py`
  - `tests/sprites/test_engine_sprite_files.py` (the engine's run)
  - `tests/testing/test_sprite_files.py`, which tests the helper itself, including the skip
    branches at :148 and :195. Use the existing `tests/testing/` directory, or the closest
    existing home for `glitchygames.testing` tests.
- Modify:
  - `src/games/brave-adventurer/tests/papyrus/test_brave_adventurer_papyrus_sprite_files.py`
    (:3, :14, :57-98)
  - `src/apps/bitmappy/tests/test_bitmappy_sprite_library.py` (:5, :19, :280-321)
  - `docs/games/brave_adventurer.md:588`
- Delete: `tests/examples/test_examples_sprites.py`.

**Interfaces:** each in `glitchygames.testing.sprite_files`, typed, with a Google docstring. Each
raises `AssertionError` with the sprite file and the difference, or calls `pytest.skip` where the
old test did:
- `check_rows_have_equal_lengths(*, sprite_file: Path) -> None`
- `check_animation_timings_survive_a_save_round_trip(*, sprite_file: Path, directory: Path) -> None`
- `check_hitboxes_survive_a_save_round_trip_unchanged(*, sprite_file: Path, directory: Path) -> None`
- `check_pixels_survive_a_save_round_trip(*, sprite_file: Path, directory: Path) -> None`
- `check_metadata_survives_a_save_round_trip(*, sprite_file: Path, directory: Path) -> None`
- `check_transitions_survive_a_save_round_trip(*, sprite_file: Path, directory: Path) -> None`
- `animated_sprite_files(*, directories: Iterable[Path]) -> list[Path]`

The engine's run in `test_engine_sprite_files.py` keeps today's test names, cases and the
non-empty guard. Its inputs are `assets/*.toml` and `tests/fixtures/sprites/`. The dead
`ENGINE_PACKAGE_DIRECTORY` branch of `_animated_sprite_file_test_id` (:93-94) is not carried over.
The `real_display` fixture stays in the test module.

- [ ] **Step 1:** write `tests/testing/test_sprite_files.py`, covering each `check_*` on a good
  and a bad synthetic sprite in `tmp_path`, both skip branches, and
  `animated_sprite_files`. Run it; it fails on the import.
- [ ] **Step 2:** write `sprite_files.py` to engine standards, then
  `test_engine_sprite_files.py`. Switch Papyrus and Bitmappy to `from glitchygames.testing import
  sprite_files` and the new names. `git rm tests/examples/test_examples_sprites.py`.
- [ ] **Step 3:** lint (engine rules apply to the helper: pyright strict, ty, vulture, bandit),
  then run `tests/testing`, `tests/sprites`, `src/games/brave-adventurer/tests/papyrus` and
  `src/apps/bitmappy/tests/test_bitmappy_sprite_library.py`. Collect the test count before and
  after; it must be the same, plus the helper's own tests. Run with coverage, and
  `sprite_files.py` must be at 100%.
- [ ] **Step 4:** commit — "Sprite-file checks are an engine testing helper members import".

### Task B2: The browser engine archive holds only git-tracked files (the bug fix)

**Files:** `scripts/build_browser_bundle.py` (`bundled_package_files`, :316-330), and
`tests/test_build_browser_bundle.py`.

**Interfaces:**
- Produces: `bundled_package_files(*, package_directory: Path, excluded_subpackages: frozenset[str]) -> list[Path]`.
  The signature is unchanged; it now lists files with `git ls-files` (run with `GIT_*` stripped
  from the environment, as `tests/test_workspace_packages.py`'s `run_git` does), and still
  filters with `is_bundled`.
- Outside a git checkout, it raises a clear error naming the directory. Bundles are always built
  from a checkout.

- [ ] **Step 1:** write `test_an_ignored_file_is_not_bundled`, which plants an ignored
  `.DS_Store` and an untracked file in a `tmp_path` git repository, and
  `test_outside_a_checkout_is_an_error`. Both fail.
- [ ] **Step 2:** implement, then run `tests/test_build_browser_bundle.py`, and build the Mr.
  Muncher bundle into the scratchpad. Its `glitchygames.zip` holds no `.DS_Store`.
- [ ] **Step 3:** commit — "Browser bundles ship only tracked files".

### Task B3: The `demos` layer, with the dt demo first

**Files:**
- Create `src/demos/dt-demo/`:
  - `pyproject.toml`: `name = "dt-demo"`, `dependencies = ["glitchygames", "pygame-ce"]` with
    the root's specifiers, `[project.scripts] dt-demo = "dt_demo:main"`, hatch
    `packages = ["src/dt_demo"]`, `[tool.uv.sources] glitchygames = { workspace = true }`
  - `README.md`
  - `src/dt_demo/__init__.py`: the old module moved by `git mv`, with its shebang and executable
    bit removed, and its `if __name__ == '__main__'` block moved out
  - `src/dt_demo/__main__.py`: `from dt_demo import main` and the `__main__` call, as PaddleSlap's
    does
  - `tests/test_dt_demo.py`, moved from `tests/examples/` with its docstrings updated (no longer
    "has no console script"; `python -m dt_demo`)
  - `tests/test_dt_demo_after_the_move.py`
- Modify:
  - `src/glitchygames/logical_names.py` `MEMBER_LAYERS`: `'dt_demo': 'demos'`. `EXAMPLES_LAYERS`
    keeps the other two until Task B5.
  - root `pyproject.toml`:
    - `demos = ["dt-demo"]`
    - members, `[tool.uv.sources]`, the dev group
    - `testpaths`, `--cov=dt_demo`, coverage `source` and `paths`
    - ruff `src`, `include` and `namespace-packages`
    - the first `"src/demos/*/tests/**/*.py"` per-file-ignores key, exactly equal to the
      `tests/**/*.py` list
    - a `RUF067` per-file ignore for `src/demos/dt-demo/src/dt_demo/__init__.py`, as PaddleSlap's
    - isort and deptry `known_first_party`; deptry `extend_exclude` `src/demos`
    - ty `root`, `include` and `exclude` (`src/demos/*/tests`)
  - `pyrightconfig.json`: `include`, the tests environments' `extraPaths`, a
    `src/demos/dt-demo/tests` environment (a copy of `tests` minus `root`, keeping `"."` because
    it imports `tests.*` helpers), and the member environment
  - `noxfile.py` `_CODE_DIRS`, `_SOURCE_PACKAGE_DIRS`, `_MEMBER_DISTRIBUTIONS`; `wily.cfg`
  - `mkdocs.yml`: mkdocstrings `paths` and a "Demos API Reference" nav section
  - `tests/engine/test_engine_lifecycle.py` `GAME_CONSOLE_SCRIPTS` (:732-739)
  - the browser-build guard (`tests/test_build_browser_bundle.py:618-631`,
    `test_every_game_has_a_browser_build`): exempt every console script whose member is in the
    `demos` layer, read from the workspace and not a hand list
  - `tests/test_browser_touch_controls.py` if it enumerates console scripts
  - `tests/examples/demo_runs.py` moves to `tests/demo_runs.py` (a root helper, since it imports
    `scripts.record_golden_traces`), and its docstring is updated

**`test_dt_demo_after_the_move.py`:**
- `logical_name(scene_class=Game) == 'demos.dt_demo:Game'`
- `Game.__module__ == 'dt_demo'`
- `find_spec('glitchygames.examples.dt_demo') is None`
- `dt_demo.__file__` is under `src/demos/dt-demo/src/`
- `python -m dt_demo` and the `dt-demo` console script both resolve to `main`: check the entry
  point, and import `dt_demo.__main__` with `main` patched, as `test_paddleslap_after_the_move.py:38-42`
  does

- [ ] **Step 1:** write the after-the-move tests. Add `'dt_demo': 'demos'` to
  `tests/test_logical_names.py`'s expected tables. Both fail.
- [ ] **Step 2:** move, `rm -rf`, create the member, configure, `uv lock`, sync.
- [ ] **Step 3:** lint, then run `src/demos/dt-demo/tests`, `tests/test_workspace_config.py`,
  `tests/test_workspace_packages.py`, `tests/test_logical_names.py`,
  `tests/test_build_browser_bundle.py`, `tests/engine/test_engine_lifecycle.py` and
  `tests/test_suite_collection.py`. Then run `uv run dt-demo --help` and
  `uv run python -m dt_demo --help`, if the engine supports `--help` headless.
- [ ] **Step 4:** commit — "The dt demo is the first member of the demos layer".

### Task B4: The joystick and text-input demos

The same as Task B3, for each demo, plus:
- **joystick:**
  - its docstring at :4 becomes `python -m joystick_demo`
  - the vestigial `PLR0913` per-file ignore for `src/glitchygames/examples/joystick_demo.py`
    (`pyproject.toml:457-459`) is dropped, after confirming ruff passes without it
  - its tests import `tests.input.stand_in_devices` and `scripts.record_golden_traces` (keep
    them; Stage C doesn't touch member tests)
  - update `tests/replay/test_bundled_demos.py:16-18,56` and
    `tests/replay/test_playback_scope.py:22,471-478` to `joystick_demo` (Stage C rehomes them)
  - `tests/world/test_gameplay_replay.py:1456-1458` keeps its old-format string on purpose
- **text-input:** its tests import `tests.display_canvas`.

- [ ] **Step 1:** write the after-the-move tests; they fail.
- [ ] **Step 2:** move both, configure, `uv lock`, sync.
- [ ] **Step 3:** lint, then run as in Task B3, plus `tests/replay`.
- [ ] **Step 4:** commit — "The joystick and text-input demos join the demos layer".

### Task B5: `src/glitchygames/examples/` is gone

**Files:**
- Move:
  - `foo2.toml` to `tests/fixtures/sprites/foo2.toml`. It is animated, so the engine's
    animated-sprite checks gain it.
  - the four WAVs to `src/glitchygames/resources/sounds/`, as package data with no
    `__init__.py`, like `color/resources/`
- Delete:
  - the rest of `src/glitchygames/examples/` and `tests/examples/`, then `rm -rf` their leftovers
  - `docs/glitchygames/examples/index.md`
- Modify:
  - `src/glitchygames/logical_names.py`: delete `EXAMPLES_PACKAGE`, `EXAMPLES_LAYERS`, the
    docstring sentence at :11-13, and the examples branches at :54-58 and :93-94
  - `tests/test_logical_names.py:26,42-50,53-65,68-85`: the examples cases go; the "moved into
    a member keeps its logical name" test is rewritten for `MEMBER_LAYERS` alone
  - `tests/sprites/test_animated_sprite.py:2803-2814`: foo2 from `SPRITE_FIXTURES_DIRECTORY`;
    drop the now-dead `ENGINE_PACKAGE_DIRECTORY` and its import (:41, :44)
  - `tests/test_build_browser_bundle.py:179-202`: the moved-game archive checks become
    `test_the_engine_archive_holds_no_examples`, and the synthetic `'examples/paddleslap.py'`
    cases at :62, :80 and :99 become another excluded subpackage
  - `tests/test_workspace_packages.py:205-217,282-286`: the examples constants go, and the
    check becomes `test_the_engines_examples_directory_is_gone`. Use `git ls-files` with a
    pathspec from `PROJECT_ROOT`, because `tracked_entry_names` can't run in a deleted directory.
  - `mkdocs.yml:39`, `docs/glitchygames/index.md:302-308`, the `norecursedirs` comment
    (`pyproject.toml:170-172`) and `tests/test_suite_collection.py:5-6`
- Create:
  - `tests/test_engine_resources.py`: each WAV is in `importlib.resources.files('glitchygames') /
    'resources' / 'sounds'` and starts with `RIFF`
  - the guard `former_examples_references(*, project_root: Path) -> list[str]` and
    `test_nothing_names_the_deleted_examples_package` in `tests/test_suite_collection.py`

  The guard uses the regex `glitchygames[./]examples\b` over tracked code, configuration and
  living docs. It **exempts** history on purpose:
  - `RECORDING_PATH_RENAMES` keys
  - every `*_after_the_move.py`
  - the old-format stand-ins (`tests/world/test_gameplay_replay.py`,
    `tests/replay/test_replay_plugin.py:472`, `tests/test_recording_report.py:80,84`,
    `tests/test_replay_metrics.py:600,701`)
  - `src/games/paddleslap/src/paddleslap/__main__.py:4`
  - the guard's own text
  - the recipe's history lines
  - the master plan

  Each exemption is a listed path, with a reason comment.

- [ ] **Step 1:** write the guard, the resources test and the gone-check. Run them; they fail,
  listing the references.
- [ ] **Step 2:** move, delete, rewrite. With the user's go-ahead (open question 1), `rm -rf`
  the ignored leftovers, including `src/glitchygames/scenes/builtin/`.
- [ ] **Step 3:** lint, then run the whole suite once (`uv run pytest --dummy-only -q`), then
  `lint-docs`.
- [ ] **Step 4:** commit — "src/glitchygames/examples/ is gone: the demos are members, foo2 a
  fixture, the sounds engine resources".

### Task B6: The engine wheel's contents are tested

**Files:** create `tests/test_engine_wheel.py`.

`test_the_engine_wheel_holds_the_engine_alone`:
- run `uv build --wheel --out-dir tmp_path`, as the members' wheel tests do, with the same timeout
  allowance
- assert its top level is only `glitchygames` plus its dist-info
- assert it has no `glitchygames/examples/`, no member package and no `*.toml` sprite library
  beyond `assets/`
- assert it holds `glitchygames/resources/sounds/` with the four WAVs

- [ ] **Step 1:** write it; run it; it passes, since Task B5 already ran. To see it fail first,
  run it against the commit before B5 in a scratch worktree, and record that.
- [ ] **Step 2:** commit — "The engine wheel's contents are tested".

### Task B7: Docs, then Stage B's verification

**Files:**
- `docs/architecture/game_packages.md`: `EXAMPLES_LAYERS` gone, the `demos` layer, and two
  meanings of "demo" kept apart: a demos-layer member versus a game's bundled demo recording,
  `<package>/demos/*.jsonl.gz`
- `CLAUDE.md:177-186` (Example Games, plus the demos' console scripts) and `:1055-1058`
- `README.md:188`
- `docs/architecture/argument_system.md:279,283`, `docs/architecture/event_system.md:2270`
- the master plan: Stage B done

- [ ] **Step 1:** write the docs; run `lint-docs` and the living-docs guard.
- [ ] **Step 2:** verify:
  - `nox -s lint static-analysis`, `CI=true nox -s test` and `uv run pytest`
  - the user runs each demo by hand: `uv run dt-demo`, `uv run joystick-demo` (with a pad),
    `uv run text-input-demo`, and one `python -m <package>`
- [ ] **Step 3:** commit. Report Stage B's results, then continue with Stage C.

---

## Stage C: the engine's tests stop borrowing members, and the guards cover every member

### Task C1: Classify every borrowing test (a written table, then a checkpoint)

These 21 files import a member package by name:
- `tests/animation/test_animation.py`
- `tests/collision/test_ball_paddle_collision.py`, `tests/collision/test_collision.py`
- `tests/game_objects/test_ball_collision_physics.py`, `test_collision_scenarios.py`,
  `test_game_over_scene.py`
- `tests/replay/test_bundled_demos.py`, `test_golden_replays.py`, `test_playback_scope.py`,
  `test_replay_plugin.py`
- `tests/scenes/builtin_scenes/test_game_over.py`, `test_pause_screen.py`
- `tests/test_browser_touch_controls.py`, `tests/test_bundled_demo_discovery.py`,
  `tests/test_replay_metrics.py`
- `tests/world/test_frame_integration.py`, `test_gameplay_recording.py`, `test_golden_traces.py`,
  `test_transition_input.py`
- the two that borrow `joystick_demo` after Stage B

For each test (not each file), record in this plan which category it is:
- **(a) The member's own test:** it tests the game's behavior. It moves into the member as
  `test_<package>_<subject>.py`.
- **(b) An engine test that needs any scene or sprite:** the borrowed game is replaced by a
  stand-in defined in the test, or a shared engine test fixture.
- **(c) A cross-member infrastructure test** (golden replays, golden traces, touch controls,
  bundled-demo discovery, replay metrics): it finds members through the workspace
  (`scripts.workspace_packages`, entry points, `bundled_demos()`) instead of importing them by
  name. It also asserts the set of members it found, so it can't pass on zero.
- **(d) None of these:** stop and ask the user.

The 5 scripts that import games (`scripts/record_golden_traces.py` and the others) are tools,
not tests, and are out of scope. Say so in the table.

- [ ] **Step 1:** write the table into this plan (a new "Borrow table" section). Collect the
  suite's test count on the branch's base and save it.
- [ ] **Step 2:** if any row is (d), stop for the user. Otherwise commit the table — "Plan: every
  borrowing test classified".

### Task C2: Category (a): the members' own tests move into the members

**Files:** per the table.
- Moved tests keep their bodies.
- Engine-only helpers or fixtures they use stay in `tests/` and are imported. A member test may
  import `tests.*` helpers, as the Papyrus precedent shows.
- New member test files are named `test_<distribution with - as _>_<subject>.py`.

- [ ] **Step 1:** save `engine-before.json` (Global Constraints, "Engine-only coverage"), then
  move the tests. The test count stays equal.
- [ ] **Step 2:** save `engine-after.json` and compare.
  - **The comparison:** for every engine line or branch the moved tests were the only root tests
    to reach, write an engine test in `tests/` that exercises the same behavior with a stand-in
    (decision 11).
  - **Example:** if `test_ball_paddle_collision.py` was the engine's only test of a collision
    branch, the engine gets its own collision test with a stand-in ball and paddle.
  - Repeat until the comparison is empty, and list each gap and its new test in the task report.
- [ ] **Step 3:** lint, then run the touched members' tests and the files the tests left, then
  `CI=true nox -s test` (100% overall).
- [ ] **Step 4:** commit — "Tests that were really the games' own move into the games".

### Task C3: Category (b): stand-ins replace borrowed games

**Files:** per the table. A stand-in that more than one file needs goes into an engine test
helper in `tests/`, named for what it stands in for (for example `tests/stand_in_scenes.py`).

- [ ] **Step 1:** replace each borrow with a stand-in, and check that each assertion still
  exercises the same engine path. Where a borrowed game supplied specific geometry or timing,
  copy the values into the stand-in, with a comment naming their source.
- [ ] **Step 2:** lint, then run, keeping the count equal and coverage at 100%.
- [ ] **Step 3:** commit — "Engine tests use stand-ins instead of borrowing games".

### Task C4: Category (c): cross-member tests discover members

**Files:** per the table.

**Interfaces:**
- If several tests need it, add `members_in_layer(*, layer: str) -> list[WorkspaceMember]` (or
  reuse an existing reader in `scripts/workspace_packages.py`), and import game classes with
  `importlib.import_module` from the discovered package names.
- Each such test asserts the discovered set equals the expected members, read from the
  workspace, and is never empty.

- [ ] **Step 1:** rewrite each test, then run it, then plant a missing member in a `tmp_path`
  workspace to prove the non-empty assertion fails.
- [ ] **Step 2:** lint, then run the whole suite once.
- [ ] **Step 3:** commit — "Cross-member tests find members through the workspace".

### Task C5: The guards cover every member

**Files:**
- `tests/test_suite_collection.py`:
  - `misnamed_bitmappy_test_modules` becomes `misnamed_member_test_modules(*, members)`, over
    every member's tests directory. It still uses `rglob`, still exempts `conftest.py` and
    `TEST_DATA_DIRECTORY_NAMES`, and uses the prefix `test_<distribution with - as _>`.
  - `engine_test_imports_of_bitmappy` becomes `engine_test_imports_of_members(*, project_root,
    members)`, flagging any root test that imports any member import package.
- `tests/test_workspace_config.py`:
  - `engine_files_pointing_into_bitmappy` becomes `engine_files_importing_a_member(*,
    project_root, members)`
  - drop the vestigial `'bitmappy/'` skip (:358) and its self-test plant (:417-418)
  - keep the Bitmappy sprite-path check (:382-383), as a separate named check
- Rename `src/games/mr-muncher/tests/test_logical_names_after_the_move.py` to
  `test_mr_muncher_after_the_move.py`, and update its references (the recipe at
  `docs/architecture/game_packages.md`, and `CLAUDE.md`).

**Self-tests:** each guard gets a planted offender in a second, synthetic member in `tmp_path`,
proving it isn't Bitmappy-specific.

- [ ] **Step 1:** generalize the guards and their self-tests. Run them; the naming guard lists
  only Mr. Muncher's file.
- [ ] **Step 2:** `git mv` the Mr. Muncher file, then run again; everything passes.
- [ ] **Step 3:** lint, then run, then commit — "Every member's tests are named for it, and no
  engine code or test imports a member".

### Task C6: Docs, then Stage C's verification, then Part 3 is done

**Files:**
- `docs/architecture/game_packages.md` step 5: engine tests no longer borrow games. Say where
  each kind of test lives now: the game's own tests, stand-ins, and discovery.
- `CLAUDE.md` Testing Guidelines: the guards cover every member.
- The master plan: Part 3 DONE, with each stage's commit range pinned at merge, and "What every
  part keeps true" gains:
  - every member's packages are under `src/`
  - no engine code or test imports a member
  - member tests are named for their member
  - the engine wheel is tested
  - browser bundles ship tracked files only
- This plan's Status.

- [ ] **Step 1:** write the docs; run `lint-docs` and the living-docs guard.
- [ ] **Step 2:** verify:
  - `nox -s lint static-analysis`, `CI=true nox -s test`, `uv run pytest` and
    `nox -s build-wheel`
  - one golden replay per game, through its console script
- [ ] **Step 3:** commit, then stop for the user's review.
