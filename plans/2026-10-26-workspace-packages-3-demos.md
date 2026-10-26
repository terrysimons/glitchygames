# Workspace Packages, Part 3: The Demos, the `src/` Layout, and Members Kept Apart — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Stage A DONE; Stage B DONE (2026-10-26: B1-B7, automated verification green;
the user runs each demo by hand); Stage C not started. (Originally PLANNED 2026-10-26.)
Written from a read-only survey of `feature/workspace-packages-4-bitmappy` at fc4a93d5 (PR #110), which becomes
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

## Stage C borrow table

**Written 2026-10-26 (Task C1)** on `feature/workspace-packages-3a-src-layout` at 273fa323.
Stages C2-C5 work from this table.

**Test count at the base (273fa323):** `uv run pytest --collect-only -q -n0 --no-cov` collects
21032 tests over every test root. The root `tests/` alone collects 15343. Each move must keep
these counts, apart from new tests (Review Focus 5).

**What counts as a borrow.** A root test borrows a member when it does one of these:
- imports a member package (`scripts.workspace_packages.workspace_members`), at module level or
  inside a function;
- runs member code in this process, which the coverage contexts below record;
- starts a member in a child process (a console script, `python -m <package>`, or
  `replay_recording_headless`/`rebaseline_recording_headless`/`measure`);
- loads a member by string or entry point (`__import__`, `game_entry_point(...).load()`,
  `find_spec`, a game key looked up in a tool's registry);
- needs a member to be installed to resolve its console script.

A member's name used only as data does not count: a stand-in class's `__module__`, a logical
name in a hand-written header, a ledger or fixture path string, or a pyproject read. Neither does
reading a member's committed golden file by path, unless the test then runs the game.

**How the list was made:**
1. An AST scan of every file under `tests/` (helpers included) for imports of the 12 member
   packages. Function-local imports count.
2. A string scan for every package, distribution and console-script name.
3. A per-test AST pass that follows module-level helpers, fixtures (autouse ones too) and helper
   classes.
4. A run of the root suite with per-test coverage contexts:
   `COVERAGE_CORE=ctrace uv run pytest --dummy-only tests --cov-context=test --cov-branch`.
   `ctrace` is needed because the default `sysmon` core records no dynamic contexts. That run
   gave, for each test, the member code it executes. For each engine arc, it gave the root tests
   that reach it.
5. A reading of every candidate.

Child processes are not measured, so those tests were found by reading.

**Differences from the list above (Task C1):**
- The brief's "21 files" are 19. The "two that borrow `joystick_demo` after Stage B" are
  `tests/replay/test_bundled_demos.py` and `tests/replay/test_playback_scope.py`, which the
  list already names.
- Seven more files borrow without importing a member, so the import scan alone misses them:
  - `tests/engine/test_engine_lifecycle.py` (entry-point load of every game's `main`)
  - `tests/test_build_browser_bundle.py` (`__import__` of each browser game's module)
  - `tests/replay/test_instant_replay.py` (`GAME_SCENES['paddleslap']`)
  - `tests/replay/test_record_scripted_session.py` (it records PaddleSlap by key)
  - `tests/replay/test_rebaseline_across_logical_modules.py` (a child through `mr-muncher`)
  - `tests/test_recording_report.py` (a child through `paddleslap`)
  - `tests/world/test_gameplay_replay.py` (`GAME_SCENES` keys, and `python -m paddleslap`)
- In total, 26 files and 110 tests borrow. The tests in these files that are not listed do not
  borrow and stay as they are.

**Not borrows, left as they are.** These files name a member only as data:
- `tests/world/test_gameplay_replay.py`: `TestRecordedGameCheck` and
  `test_a_rebaseline_writes_the_current_games_logical_name` (stand-in classes whose module is
  `'paddleslap'`).
- `tests/test_recording_metrics.py` (ledger paths; `test_rows_from_a_real_golden_replay` reads
  PaddleSlap's golden by path).
- `tests/replay/test_replay_plugin.py`: the misplaced and nested collection errors, and the
  `mr_muncher` header strings.
- `tests/replay/test_record_scripted_session.py`: the supervisor unit tests with
  `game_key='paddleslap'`, and the fixture-table checks.
- `tests/test_browser_touch_controls.py`: the layout and boot-config tests.
- `tests/scenes/test_scene.py` (a docstring).
- `tests/test_logical_names.py`, `tests/test_workspace_packages.py`,
  `tests/test_workspace_config.py`, `tests/test_suite_collection.py`,
  `tests/test_generate_performance_graphs.py`, `tests/test_measure_staged_replays.py`,
  `tests/test_mkdocs_hooks_browser_games.py`, `tests/test_gen_ref_pages.py`,
  `tests/test_ci_config.py`, `tests/test_engine_doors.py`, `tests/state/test_paths.py`,
  `tests/benchmarks/test_benchmarks.py`, `tests/sprites/test_sprite_animation.py`,
  `tests/demo_runs.py`.

**Out of scope: the tools.** These five scripts import games:
- `scripts/record_golden_traces.py`
- `scripts/audio_glitch_probe.py`
- `scripts/bitmappy_entry.py`
- `scripts/simulate_drawing_fire.py`
- `scripts/ai_query_inspector.py`

They are tools, not tests. One consequence matters to C5. `scripts/record_golden_traces.py`
imports every game at module level for `GAME_SCENES`. Nineteen root test files and helpers
import it for engine harness pieces (`GoldenTraceEngine`, `GoldenTraceSceneManager`,
`command_line`), among them `tests/engine/test_engine_*.py`, `tests/events/test_*_events.py`,
`tests/replay/replay_helpers.py` and `tests/demo_runs.py`. So every member is still loaded when
those tests run. C5's AST guard on the root tests will not see this. Splitting the harness out
of the tool belongs in `plans/future-work.md`; it is not a C-task.

**Decision 11 (engine-only coverage from the root `tests/` alone).** These figures come from the
coverage-context run, over in-process engine arcs:
- Only two engine arcs are reached by a single borrowing test:
  - `engine/game_engine.py` `_crash_boundary`/`_run_game` (2577, 2596), reached only by
    `test_every_game_powers_on_through_its_own_main`. That row is (c) and stays.
  - `scenes/scene.py` `SceneManager._process_transition_events` (2632), reached only by
    `test_recording_matches_the_golden_harness_frames`. That row is (b), so its stand-in must
    keep that arc.
- Several engine arcs are reached only by borrowing tests as a group:
  - `game_objects/ball.py` 744, 820-821
  - `animation/state_machine.py` 291-292, 342, 346
  - `physics/body.py` 133
  - `input/action_map.py` 401
  - `audio/recipes.py` 116-117
  - `audio/synth.py` 437
  - `camera.py` 144
  - `transitions/elevator.py` 208-209
  - `sprites/animated.py` 575, 2663

  In every case at least one (c) row reaches the arc and stays in the root, so no (a) move
  opens a gap by itself.
- C3 should run the same before/after comparison: a stand-in can drop an arc the member reached
  (the elevator arcs, if `test_jump_pressed_during_elevator_ride_does_not_jump_on_arrival`'s
  stand-in uses another transition).

**Notes for the tasks:**
- (a) rows that share a member test file: PaddleSlap's ball-pair, cooldown and sweep tests
  (`test_paddleslap_ball_collisions.py`, `test_paddleslap_ball_collision_physics.py`); its two
  game-over tests (`test_paddleslap_game_over.py`); and Brave Adventurer's four hitbox tests
  (`test_brave_adventurer_hitboxes.py`). Helpers they need (`make_ball`, `running_scene`,
  `step_finishing`) stay in `tests/` and are imported.
- `tests/scenes/builtin_scenes/test_game_over.py` has only the one test, so the file goes.
- Several (b) rows need `write_stand_in_distribution` from `tests/replay/test_replay_plugin.py`.
  Moving it, with `write_stand_in_package` from `tests/test_bundled_demo_discovery.py`, into a
  shared `tests/` helper (C3's "stand-in that more than one file needs") avoids importing one
  test module from another.
- Many (c) rows use a golden picked by name today. C4's `members_in_layer` and "the goldens the
  workspace holds" (`member.replay_fixtures_directory`, each header's `game` logical name,
  resolved with `glitchygames.logical_names.module_for_logical_module` and
  `importlib.import_module`) serve all of them. The tampered-golden rows need a sprite on frame
  10, so the chosen golden must have one.
- No row is (d).

**Counts:** (a) 20, (b) 27, (c) 63, (d) 0, for 110 tests in 26 files. Parametrized tests count
once each.

| File | Test | Cat. | Target, stand-in or discovery | Decision 11 (root-only engine coverage) |
|---|---|---|---|---|
| `tests/animation/test_animation.py` | `TestFallingConditionEquivalence::test_matches_old_logic_around_threshold` | (b) | Two threshold floats instead of the imports: 10.0 (`brave_adventurer_core/constants.py` `FALLING_VELOCITY_THRESHOLD`) and 50.0 (`clockwork_keep/constants.py`), each with a comment naming its source. Engine: the animation `parse(...).evaluate` expression. | none: no engine arc only it reaches |
| `tests/collision/test_ball_paddle_collision.py` | `TestBallPairDistance::test_collision_distance_is_the_sum_of_visible_radii` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collisions.py`. Subject is `Game._calculate_ball_distance`, `_handle_ball_collisions` and `_keep_ball_playable`. `make_ball` (engine `BallSprite`) stays in `tests/` and is imported. | none: no engine arc only it reaches |
| `tests/collision/test_ball_paddle_collision.py` | `TestBallPairPlayability::test_head_on_hit_on_a_still_ball_leaves_neither_ball_stalled_or_flat` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collisions.py`. Subject is `Game._calculate_ball_distance`, `_handle_ball_collisions` and `_keep_ball_playable`. `make_ball` (engine `BallSprite`) stays in `tests/` and is imported. | none: no engine arc only it reaches |
| `tests/collision/test_ball_paddle_collision.py` | `TestBallPairPlayability::test_near_vertical_ball_is_turned_to_the_steepest_serve_angle` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collisions.py`. Subject is `Game._calculate_ball_distance`, `_handle_ball_collisions` and `_keep_ball_playable`. `make_ball` (engine `BallSprite`) stays in `tests/` and is imported. | none: no engine arc only it reaches |
| `tests/collision/test_ball_paddle_collision.py` | `TestBallPairPlayability::test_flat_ball_is_turned_to_the_shallowest_serve_angle` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collisions.py`. Subject is `Game._calculate_ball_distance`, `_handle_ball_collisions` and `_keep_ball_playable`. `make_ball` (engine `BallSprite`) stays in `tests/` and is imported. | none: no engine arc only it reaches |
| `tests/collision/test_ball_paddle_collision.py` | `TestBallPairPlayability::test_ball_already_moving_like_a_serve_is_unchanged` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collisions.py`. Subject is `Game._calculate_ball_distance`, `_handle_ball_collisions` and `_keep_ball_playable`. `make_ball` (engine `BallSprite`) stays in `tests/` and is imported. | none: no engine arc only it reaches |
| `tests/collision/test_collision.py` | `TestRedrawnGameSprites::test_cobra_hitbox_follows_first_draw_and_strike` | (a) | brave-adventurer: `src/games/brave-adventurer/tests/test_brave_adventurer_hitboxes.py` (the Cobra `brave_adventurer.enemies`). | none: no engine arc only it reaches |
| `tests/collision/test_collision.py` | `TestPapyrusHitboxScale::test_scaled_papyrus_player_collides_at_twice_the_toml_hitbox` | (a) | brave-adventurer: `test_brave_adventurer_hitboxes.py` (Papyrus `SPRITE_SCALE` hitboxes). | Shared, not alone: `sprites/animated.py` `SpriteAnimation.__init__` (575), `animation/state_machine.py` `evaluate` (291-292) and `physics/body.py` `get_animation_context` (133) are also reached by golden-trace and golden-replay rows (c), which stay |
| `tests/collision/test_collision.py` | `TestPapyrusHitboxScale::test_freshly_constructed_sprites_have_scaled_hitboxes_before_any_tick` | (a) | brave-adventurer: `test_brave_adventurer_hitboxes.py` (Papyrus `SPRITE_SCALE` hitboxes). | Shared, not alone: `sprites/animated.py` `SpriteAnimation.__init__` (575), `animation/state_machine.py` `evaluate` (291-292) and `physics/body.py` `get_animation_context` (133) are also reached by golden-trace and golden-replay rows (c), which stay |
| `tests/collision/test_collision.py` | `TestPapyrusHitboxScale::test_scale_one_keeps_native_hitbox` | (a) | brave-adventurer: `test_brave_adventurer_hitboxes.py` (Papyrus `SPRITE_SCALE` hitboxes). | Shared, not alone: `sprites/animated.py` `SpriteAnimation.__init__` (575), `animation/state_machine.py` `evaluate` (291-292) and `physics/body.py` `get_animation_context` (133) are also reached by golden-trace and golden-replay rows (c), which stay |
| `tests/game_objects/test_ball_collision_physics.py` | `TestBallCollisionSweepStationaryTarget::test_mover_stops_and_target_takes_its_velocity` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collision_physics.py`, with the sweep helper class built on `Game.__new__` (`_handle_ball_collisions`). `drawn_position`/`place_ball_center` stay in `tests/game_objects/ball_helpers.py`. | none: no engine arc only it reaches |
| `tests/game_objects/test_ball_collision_physics.py` | `TestBallCollisionSweepMovingPair::test_balls_swap_velocities` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collision_physics.py`, with the sweep helper class built on `Game.__new__` (`_handle_ball_collisions`). `drawn_position`/`place_ball_center` stay in `tests/game_objects/ball_helpers.py`. | none: no engine arc only it reaches |
| `tests/game_objects/test_ball_collision_physics.py` | `TestBallCollisionSweepFrameAlignedMeeting::test_head_on_balls_meeting_on_a_frame_collide` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collision_physics.py`, with the sweep helper class built on `Game.__new__` (`_handle_ball_collisions`). `drawn_position`/`place_ball_center` stay in `tests/game_objects/ball_helpers.py`. | none: no engine arc only it reaches |
| `tests/game_objects/test_collision_scenarios.py` | `TestPaddleCollisions::test_ball_bounces_off_left_paddle` | (b) | A stand-in `SpeedUpSettings` instead of `PADDLESLAP_SPEED_UP`: `triggers=PADDLE_BOUNCE`, `curve=LOGARITHMIC`, `axes=BOTH`, `multiplier=1.15`, `max_speed=500.0` (from `paddleslap/__init__.py`). Engine: `BallSprite.speed_up`, `_do_bounce`. | none: no engine arc only it reaches |
| `tests/game_objects/test_collision_scenarios.py` | `TestPaddleCollisions::test_ball_bounces_off_right_paddle` | (b) | A stand-in `SpeedUpSettings` instead of `PADDLESLAP_SPEED_UP`: `triggers=PADDLE_BOUNCE`, `curve=LOGARITHMIC`, `axes=BOTH`, `multiplier=1.15`, `max_speed=500.0` (from `paddleslap/__init__.py`). Engine: `BallSprite.speed_up`, `_do_bounce`. | none: no engine arc only it reaches |
| `tests/game_objects/test_collision_scenarios.py` | `TestPaddleCollisions::test_paddle_collision_spawns_new_ball` | (b) | A stand-in `SpeedUpSettings` instead of `PADDLESLAP_SPEED_UP`: `triggers=PADDLE_BOUNCE`, `curve=LOGARITHMIC`, `axes=BOTH`, `multiplier=1.15`, `max_speed=500.0` (from `paddleslap/__init__.py`). Engine: `BallSprite.speed_up`, `_do_bounce`. | none: no engine arc only it reaches |
| `tests/game_objects/test_collision_scenarios.py` | `TestPaddleCollisions::test_paddle_collision_reverses_horizontal_direction` | (b) | A stand-in `SpeedUpSettings` instead of `PADDLESLAP_SPEED_UP`: `triggers=PADDLE_BOUNCE`, `curve=LOGARITHMIC`, `axes=BOTH`, `multiplier=1.15`, `max_speed=500.0` (from `paddleslap/__init__.py`). Engine: `BallSprite.speed_up`, `_do_bounce`. | none: no engine arc only it reaches |
| `tests/game_objects/test_collision_scenarios.py` | `TestIntegrationCollisions::test_mixed_collision_scenarios` | (b) | A stand-in `SpeedUpSettings` instead of `PADDLESLAP_SPEED_UP`: `triggers=PADDLE_BOUNCE`, `curve=LOGARITHMIC`, `axes=BOTH`, `multiplier=1.15`, `max_speed=500.0` (from `paddleslap/__init__.py`). Engine: `BallSprite.speed_up`, `_do_bounce`. | none: no engine arc only it reaches |
| `tests/game_objects/test_collision_scenarios.py` | `TestIntegrationCollisions::test_multiple_balls_collision_behavior` | (b) | A stand-in `SpeedUpSettings` instead of `PADDLESLAP_SPEED_UP`: `triggers=PADDLE_BOUNCE`, `curve=LOGARITHMIC`, `axes=BOTH`, `multiplier=1.15`, `max_speed=500.0` (from `paddleslap/__init__.py`). Engine: `BallSprite.speed_up`, `_do_bounce`. | none: no engine arc only it reaches |
| `tests/game_objects/test_collision_scenarios.py` | `TestBallToBallCollisions::test_ball_to_ball_collision_cooldown` | (a) | paddleslap: `test_paddleslap_ball_collisions.py`. The cooldown is the game's own (`Game._ball_collision_cooldowns`, `_on_ball_ball_collision`). | none: no engine arc only it reaches |
| `tests/game_objects/test_game_over_scene.py` | `TestGameOverIntegration::test_game_over_triggered_when_all_balls_dead` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_game_over.py`. Covers PaddleSlap's `dt_tick`, `PaddleSlapGameOverScene` and its high-score save. | none: no engine arc only it reaches |
| `tests/scenes/builtin_scenes/test_game_over.py` | `test_game_over_condition` | (a) | paddleslap: `test_paddleslap_game_over.py`, next to the row above (it is nearly the same test). This is the file's only test, so the file goes. | none: no engine arc only it reaches |
| `tests/scenes/builtin_scenes/test_pause_screen.py` | `TestPauseScreen::test_pause_screen_triggered_on_spacebar` | (b) | A stand-in `Scene` that calls `self.pause()` (engine `Scene.pause`, `scene.py`) on the release of SPACE. PaddleSlap binds `pause` to `KSCAN_SPACE`. The stand-in draws something, so the overlay and display comparison mean something. This file's `_engine_for` and `TestPauseSceneBehaviour` already use stand-ins of this kind. Engine: `PauseScene`, `SceneManager._setup_new_scene`. | none: no engine arc only it reaches |
| `tests/scenes/builtin_scenes/test_pause_screen.py` | `TestPauseScreen::test_pause_screen_resume_on_spacebar` | (b) | A stand-in `Scene` that calls `self.pause()` (engine `Scene.pause`, `scene.py`) on the release of SPACE. PaddleSlap binds `pause` to `KSCAN_SPACE`. The stand-in draws something, so the overlay and display comparison mean something. This file's `_engine_for` and `TestPauseSceneBehaviour` already use stand-ins of this kind. Engine: `PauseScene`, `SceneManager._setup_new_scene`. | none: no engine arc only it reaches |
| `tests/scenes/builtin_scenes/test_pause_screen.py` | `TestPauseScreen::test_pause_screen_gets_game_engine_reference` | (b) | A stand-in `Scene` that calls `self.pause()` (engine `Scene.pause`, `scene.py`) on the release of SPACE. PaddleSlap binds `pause` to `KSCAN_SPACE`. The stand-in draws something, so the overlay and display comparison mean something. This file's `_engine_for` and `TestPauseSceneBehaviour` already use stand-ins of this kind. Engine: `PauseScene`, `SceneManager._setup_new_scene`. | none: no engine arc only it reaches |
| `tests/scenes/builtin_scenes/test_pause_screen.py` | `TestPauseScreenIntegration::test_pause_resume_cycle` | (b) | A stand-in `Scene` that calls `self.pause()` (engine `Scene.pause`, `scene.py`) on the release of SPACE. PaddleSlap binds `pause` to `KSCAN_SPACE`. The stand-in draws something, so the overlay and display comparison mean something. This file's `_engine_for` and `TestPauseSceneBehaviour` already use stand-ins of this kind. Engine: `PauseScene`, `SceneManager._setup_new_scene`. | none: no engine arc only it reaches |
| `tests/engine/test_engine_lifecycle.py` | `test_every_game_powers_on_through_its_own_main` (9 console scripts x 2 backgrounds) | (c) | It loads each `main` by entry point (`game_entry_point(...).load()`). It is parametrized from the hard-coded `GAME_CONSOLE_SCRIPTS`; it should read `declared_console_scripts(project_root=...)` minus `NOT_GAME_CONSOLE_SCRIPTS` instead. Expected set: `test_every_game_console_script_is_covered` already asserts the list equals the declared scripts. Make that assertion read the same source and assert that it is non-empty. | The only root test reaching `engine/game_engine.py` `_crash_boundary` (2577->2584) and `_run_game` (2596 exit). It stays in the root (Review Focus 4), so the engine keeps that coverage |
| `tests/replay/test_bundled_demos.py` | `test_paddleslap_ships_a_demo` | (c) | Expected set from the workspace: for each `workspace_members` import package, the files in `<package directory>/demos/*.jsonl.gz`. Assert that `bundled_demo_paths()` equals it (PaddleSlap's rally demo is one entry) and is non-empty. | none: no engine arc only it reaches |
| `tests/replay/test_bundled_demos.py` | `test_bundled_demo_replays_without_divergence` (one per demo) | (c) | It already discovers demos (`bundled_demo_paths()`) and replays each in a child process through its console script. Add the expected-set test above: an empty parametrize list would skip, not fail. | none: no engine arc only it reaches |
| `tests/replay/test_bundled_demos.py` | `test_the_paddleslap_demo_plays_in_game` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_demo_plays_in_game.py`. Drop the `joystick_demo` import: the row for `test_playback_scope.py` below gives the same-name scene case its own stand-in. `running_scene` and `step_finishing` stay in `tests/` and are imported. | Shared, not alone: `game_objects/ball.py` `dt_tick` (744) and `_finish_wall_bounce` (820-821) are also reached by (c) rows that stay |
| `tests/replay/test_golden_replays.py` | `test_every_fixture_directory_is_a_game_console_script` | (c) | It already discovers fixtures (`workspace_members(...)` replay fixtures). `GAME_CONSOLE_SCRIPTS` is a tool's table, and console scripts are resolved from installed metadata. Expected set: the console scripts found equal the declared scripts of the members holding goldens. | none: no engine arc only it reaches |
| `tests/replay/test_golden_replays.py` | `test_every_golden_replay_is_replayed_by_its_games_console_script` (per game) | (c) | Parametrize over the goldens found in the members' `replay_fixtures_directory`, not the tool's `GAME_CONSOLE_SCRIPTS`. Expected set: the games found equal the tool's game keys, and are non-empty. | none: no engine arc only it reaches |
| `tests/replay/test_golden_replays.py` | `test_a_members_golden_replay_is_replayed_by_the_members_console_script` | (c) | It already picks Mr. Muncher through `workspace_members`. Pick any member with a golden instead, and read the expected console script from that member's `console_scripts`. The `drawing-fire` root-layout path is only a string. | none: no engine arc only it reaches |
| `tests/replay/test_golden_replays.py` | `test_a_tampered_golden_replay_is_reported_at_its_frame` | (c) | A golden found in the workspace (`member.replay_fixtures_directory`, not `fixture_path(game_key='paddleslap')`). Resolve its scene from the header's `game` logical name (`glitchygames.logical_names.module_for_logical_module` + `importlib.import_module`), not `GAME_SCENES`. The golden must have a sprite on `TAMPERED_FRAME` (10). Expected set: the goldens found equal the members holding goldens, and are non-empty. | Shared: `ball.py` 744, 820-821, with other rows that stay |
| `tests/replay/test_golden_replays.py` | `test_a_rebaselined_golden_replay_names_the_tampered_frames_and_replays_clean` | (c) | A golden found in the workspace (`member.replay_fixtures_directory`, not `fixture_path(game_key='paddleslap')`). Resolve its scene from the header's `game` logical name (`glitchygames.logical_names.module_for_logical_module` + `importlib.import_module`), not `GAME_SCENES`. The golden must have a sprite on `TAMPERED_FRAME` (10). Expected set: the goldens found equal the members holding goldens, and are non-empty. | Shared: `ball.py` 744, 820-821, with other rows that stay |
| `tests/replay/test_golden_replays.py` | `test_every_game_with_a_golden_replay_has_its_controls_listed` | (c) | `GAMEPLAY_ACTION_MAPS`, `ENGINE_SCENE_CONTROLS`, `UNEXERCISED_CONTROLS` and `DRAWING_FIRE_CONTROLS` import the six scene classes and `drawing_fire.players` by name. Key them by each golden's logical name and import the classes with `importlib.import_module`. The per-game tables stay, as data. Expected set: `GOLDEN_GAMES` equals the games of the goldens the workspace holds (from their headers), and is non-empty. | none: no engine arc only it reaches |
| `tests/replay/test_golden_replays.py` | `test_each_golden_is_its_own_games_recording` | (c) | `GAMEPLAY_ACTION_MAPS`, `ENGINE_SCENE_CONTROLS`, `UNEXERCISED_CONTROLS` and `DRAWING_FIRE_CONTROLS` import the six scene classes and `drawing_fire.players` by name. Key them by each golden's logical name and import the classes with `importlib.import_module`. The per-game tables stay, as data. Expected set: `GOLDEN_GAMES` equals the games of the goldens the workspace holds (from their headers), and is non-empty. | none: no engine arc only it reaches |
| `tests/replay/test_golden_replays.py` | `test_every_golden_replay_exercises_every_control (per game)` | (c) | `GAMEPLAY_ACTION_MAPS`, `ENGINE_SCENE_CONTROLS`, `UNEXERCISED_CONTROLS` and `DRAWING_FIRE_CONTROLS` import the six scene classes and `drawing_fire.players` by name. Key them by each golden's logical name and import the classes with `importlib.import_module`. The per-game tables stay, as data. Expected set: `GOLDEN_GAMES` equals the games of the goldens the workspace holds (from their headers), and is non-empty. | none: no engine arc only it reaches |
| `tests/replay/test_golden_replays.py` | `test_every_golden_replay_pauses_resumes_and_ends_with_the_games_own_quit (per game)` | (c) | `GAMEPLAY_ACTION_MAPS`, `ENGINE_SCENE_CONTROLS`, `UNEXERCISED_CONTROLS` and `DRAWING_FIRE_CONTROLS` import the six scene classes and `drawing_fire.players` by name. Key them by each golden's logical name and import the classes with `importlib.import_module`. The per-game tables stay, as data. Expected set: `GOLDEN_GAMES` equals the games of the goldens the workspace holds (from their headers), and is non-empty. | none: no engine arc only it reaches |
| `tests/replay/test_golden_replays.py` | `test_the_drawing_fire_golden_replay_holds_a_death_and_a_takeover` | (a) | drawing-fire: `src/games/drawing-fire/tests/test_drawing_fire_golden_replay.py`. It checks Drawing Fire's own golden for its own game events (`SOLDIER_KILLED_SUBTYPE`, `SEAT_CHANGED_SUBTYPE`, `SeatChange`). | none: no engine arc only it reaches |
| `tests/replay/test_instant_replay.py` | `TestAnExampleGame::test_paddleslaps_journal_plays_back_exactly` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_instant_replay.py`. It runs the golden script of PaddleSlap's `INSTANT_REPLAY_SECONDS` through `record_trace('paddleslap')`. The engine's instant replay keeps the stand-in tests in this file (`InstantCountingScene`). | Shared, not alone: `ball.py` 820-821 and `input/action_map.py` `handle_event` (401) are also reached by (c) rows that stay |
| `tests/replay/test_playback_scope.py` | `TestPlaybackErrors::test_the_module_picks_one_of_two_loaded_scenes_named_alike` | (b) | Two stand-in `Scene` subclasses, both named `Game`, in two stand-in modules (`type('Game', (Scene,), {'__module__': ...})`). Delete them and run `gc.collect()` afterwards, as `test_two_loaded_classes_of_that_name_are_still_refused` (`test_rebaseline_across_logical_modules.py`) does. Engine: `replay/playback.py` `find_scene_class` walking subclasses by module. | none: no engine arc only it reaches |
| `tests/replay/test_record_scripted_session.py` | `test_scripted_session_records_and_replays` | (c) | These test the golden-replay recorder (`scripts/record_scripted_session.py`), which runs a real game by game key. Choose the game from the goldens the workspace holds (the tool's key for that member), not the literal `'paddleslap'`. Expected set: the tool's `GAME_CONSOLE_SCRIPTS` keys equal the games of the workspace's goldens, and are non-empty. | Shared: `ball.py` 744, 820-821, with other rows that stay |
| `tests/replay/test_record_scripted_session.py` | `test_a_session_drops_events_left_queued_before_it` | (c) | These test the golden-replay recorder (`scripts/record_scripted_session.py`), which runs a real game by game key. Choose the game from the goldens the workspace holds (the tool's key for that member), not the literal `'paddleslap'`. Expected set: the tool's `GAME_CONSOLE_SCRIPTS` keys equal the games of the workspace's goldens, and are non-empty. | Shared: `ball.py` 744, 820-821, with other rows that stay |
| `tests/replay/test_record_scripted_session.py` | `test_a_tail_whose_quit_does_not_quit_fails_the_recording` | (c) | These test the golden-replay recorder (`scripts/record_scripted_session.py`), which runs a real game by game key. Choose the game from the goldens the workspace holds (the tool's key for that member), not the literal `'paddleslap'`. Expected set: the tool's `GAME_CONSOLE_SCRIPTS` keys equal the games of the workspace's goldens, and are non-empty. | Shared: `ball.py` 744, 820-821, with other rows that stay |
| `tests/replay/test_rebaseline_across_logical_modules.py` | `TestThroughTheRealGame::test_a_plain_replay_refuses_and_names_the_remedy` | (c) | A child replays through `CONSOLE_SCRIPT = 'mr-muncher'`; the file says Mr. Muncher's golden "stands in for any game". Use a golden found in the workspace, with `CURRENT_NAME` read from its header's `game` and the console script from `recording_console_script(path=...)`. Expected set: as for the golden-replay rows. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_rebaseline_across_logical_modules.py` | `TestThroughTheRealGame::test_a_rebaseline_converts_it_and_the_new_recording_replays_strictly` | (c) | A child replays through `CONSOLE_SCRIPT = 'mr-muncher'`; the file says Mr. Muncher's golden "stands in for any game". Use a golden found in the workspace, with `CURRENT_NAME` read from its header's `game` and the console script from `recording_console_script(path=...)`. Expected set: as for the golden-replay rows. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_rebaseline_across_logical_modules.py` | `TestThroughTheRealGame::test_a_different_qualified_name_is_refused_and_writes_nothing` | (c) | A child replays through `CONSOLE_SCRIPT = 'mr-muncher'`; the file says Mr. Muncher's golden "stands in for any game". Use a golden found in the workspace, with `CURRENT_NAME` read from its header's `game` and the console script from `recording_console_script(path=...)`. Expected set: as for the golden-replay rows. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_replay_plugin.py` | `test_game_entry_point_reads_the_console_script` | (b) | The file's own `write_stand_in_distribution` (a dist-info with `console_scripts`) on `monkeypatch.syspath_prepend`, with `stand-in-game = stand_in_game:main`. Engine: `testing/replays.py` `game_entry_point`. | none: no engine arc only it reaches |
| `tests/replay/test_replay_plugin.py` | `test_matching_recording_passes` | (c) | The plugin resolves the `paddleslap` game directory to the installed console script, and most of these runs start it in a child. Use one member found in the workspace: its golden replaces `REPO_FIXTURE` and its console script replaces `'paddleslap'`. Expected set: the members with a golden and a console script equal those the workspace declares, and are non-empty. The tampered cases need a sprite on frame 10. | none: no engine arc only it reaches (the child replays are not measured; `TestPluginInProcess` measures the plugin in this process) |
| `tests/replay/test_replay_plugin.py` | `test_a_recording_can_be_skipped_from_a_marker` | (c) | The plugin resolves the `paddleslap` game directory to the installed console script, and most of these runs start it in a child. Use one member found in the workspace: its golden replaces `REPO_FIXTURE` and its console script replaces `'paddleslap'`. Expected set: the members with a golden and a console script equal those the workspace declares, and are non-empty. The tampered cases need a sprite on frame 10. | none: no engine arc only it reaches (the child replays are not measured; `TestPluginInProcess` measures the plugin in this process) |
| `tests/replay/test_replay_plugin.py` | `test_other_files_are_not_collected` | (c) | The plugin resolves the `paddleslap` game directory to the installed console script, and most of these runs start it in a child. Use one member found in the workspace: its golden replaces `REPO_FIXTURE` and its console script replaces `'paddleslap'`. Expected set: the members with a golden and a console script equal those the workspace declares, and are non-empty. The tampered cases need a sprite on frame 10. | none: no engine arc only it reaches (the child replays are not measured; `TestPluginInProcess` measures the plugin in this process) |
| `tests/replay/test_replay_plugin.py` | `test_a_bookmarked_copy_is_not_collected` | (c) | The plugin resolves the `paddleslap` game directory to the installed console script, and most of these runs start it in a child. Use one member found in the workspace: its golden replaces `REPO_FIXTURE` and its console script replaces `'paddleslap'`. Expected set: the members with a golden and a console script equal those the workspace declares, and are non-empty. The tampered cases need a sprite on frame 10. | none: no engine arc only it reaches (the child replays are not measured; `TestPluginInProcess` measures the plugin in this process) |
| `tests/replay/test_replay_plugin.py` | `test_tampered_recording_fails_with_the_report` | (c) | The plugin resolves the `paddleslap` game directory to the installed console script, and most of these runs start it in a child. Use one member found in the workspace: its golden replaces `REPO_FIXTURE` and its console script replaces `'paddleslap'`. Expected set: the members with a golden and a console script equal those the workspace declares, and are non-empty. The tampered cases need a sprite on frame 10. | none: no engine arc only it reaches (the child replays are not measured; `TestPluginInProcess` measures the plugin in this process) |
| `tests/replay/test_replay_plugin.py` | `test_unusable_recording_fails_with_the_exit_code` | (c) | The plugin resolves the `paddleslap` game directory to the installed console script, and most of these runs start it in a child. Use one member found in the workspace: its golden replaces `REPO_FIXTURE` and its console script replaces `'paddleslap'`. Expected set: the members with a golden and a console script equal those the workspace declares, and are non-empty. The tampered cases need a sprite on frame 10. | none: no engine arc only it reaches (the child replays are not measured; `TestPluginInProcess` measures the plugin in this process) |
| `tests/replay/test_replay_plugin.py` | `test_missing_recording_fails_as_unusable` | (c) | The plugin resolves the `paddleslap` game directory to the installed console script, and most of these runs start it in a child. Use one member found in the workspace: its golden replaces `REPO_FIXTURE` and its console script replaces `'paddleslap'`. Expected set: the members with a golden and a console script equal those the workspace declares, and are non-empty. The tampered cases need a sprite on frame 10. | none: no engine arc only it reaches (the child replays are not measured; `TestPluginInProcess` measures the plugin in this process) |
| `tests/replay/test_replay_plugin.py` | `test_replay_recording_headless_returns_the_finished_replay` | (c) | The plugin resolves the `paddleslap` game directory to the installed console script, and most of these runs start it in a child. Use one member found in the workspace: its golden replaces `REPO_FIXTURE` and its console script replaces `'paddleslap'`. Expected set: the members with a golden and a console script equal those the workspace declares, and are non-empty. The tampered cases need a sprite on frame 10. | none: no engine arc only it reaches (the child replays are not measured; `TestPluginInProcess` measures the plugin in this process) |
| `tests/replay/test_replay_plugin.py` | `test_rebaseline_recording_headless_writes_the_new_recording` | (c) | The plugin resolves the `paddleslap` game directory to the installed console script, and most of these runs start it in a child. Use one member found in the workspace: its golden replaces `REPO_FIXTURE` and its console script replaces `'paddleslap'`. Expected set: the members with a golden and a console script equal those the workspace declares, and are non-empty. The tampered cases need a sprite on frame 10. | none: no engine arc only it reaches (the child replays are not measured; `TestPluginInProcess` measures the plugin in this process) |
| `tests/replay/test_replay_plugin.py` | `TestPluginInProcess::test_a_bookmarked_copy_is_not_collected` | (c) | The plugin resolves the `paddleslap` game directory to the installed console script, and most of these runs start it in a child. Use one member found in the workspace: its golden replaces `REPO_FIXTURE` and its console script replaces `'paddleslap'`. Expected set: the members with a golden and a console script equal those the workspace declares, and are non-empty. The tampered cases need a sprite on frame 10. | none: no engine arc only it reaches (the child replays are not measured; `TestPluginInProcess` measures the plugin in this process) |
| `tests/replay/test_replay_plugin.py` | `TestPluginInProcess::test_a_failed_replay_fails_the_item_with_its_exit_code_and_output` | (c) | The plugin resolves the `paddleslap` game directory to the installed console script, and most of these runs start it in a child. Use one member found in the workspace: its golden replaces `REPO_FIXTURE` and its console script replaces `'paddleslap'`. Expected set: the members with a golden and a console script equal those the workspace declares, and are non-empty. The tampered cases need a sprite on frame 10. | none: no engine arc only it reaches (the child replays are not measured; `TestPluginInProcess` measures the plugin in this process) |
| `tests/replay/test_replay_plugin.py` | `TestPluginInProcess::test_a_successful_replay_passes_the_item` | (c) | The plugin resolves the `paddleslap` game directory to the installed console script, and most of these runs start it in a child. Use one member found in the workspace: its golden replaces `REPO_FIXTURE` and its console script replaces `'paddleslap'`. Expected set: the members with a golden and a console script equal those the workspace declares, and are non-empty. The tampered cases need a sprite on frame 10. | none: no engine arc only it reaches (the child replays are not measured; `TestPluginInProcess` measures the plugin in this process) |
| `tests/replay/test_replay_plugin.py` | `test_bundled_demo_paths_pairs_each_demo_with_its_games_console_script` | (b) | `write_stand_in_package` (`tests/test_bundled_demo_discovery.py`) plus `write_stand_in_distribution`, whose console-script entry point is in the stand-in package. Engine: `bundled_demo_paths`. | none: no engine arc only it reaches |
| `tests/test_browser_touch_controls.py` | `test_every_button_presses_a_key_its_game_reads` (per game) | (c) | `GAME_SCANCODES` imports five scene classes by name. Import each page's scenes with `importlib.import_module`, from the `module`/`scene_class` in `scripts/build_browser_bundle.py` `GAMES` (the browser bundle's own table). Expected set: the games with a `TOUCH_LAYOUTS` entry equal the `games`-layer members that have a browser build, minus `GAMES_WITHOUT_TOUCH_CONTROLS`, and are non-empty. | none: no engine arc only it reaches |
| `tests/test_browser_touch_controls.py` | `test_the_brave_adventurer_title_screen_takes_the_games_buttons` | (a) | brave-adventurer: `src/games/brave-adventurer/tests/test_brave_adventurer_touch_controls.py`. It checks Brave Adventurer's title-screen bindings against its touch layout, and imports `scripts.build_browser_bundle` (member tests already import `scripts`/`tests` helpers). | none: no engine arc only it reaches |
| `tests/test_build_browser_bundle.py` | `TestGeneratedFiles::test_every_game_module_has_its_scene_class` | (c) | It imports each `GAMES` module by string (`__import__`). Keep the import. The expected set is already pinned by the `GAMES` key assertions in `test_build_browser_bundle.py`; also assert that `GAMES`' member packages equal those of the workspace's non-`demos` members (decision 6). | none: no engine arc only it reaches |
| `tests/test_bundled_demo_discovery.py` | `test_paddleslaps_demo_is_found_with_its_console_script_and_install_name` | (b) | `write_stand_in_package` plus `write_stand_in_distribution` (move it from `tests/replay/test_replay_plugin.py` into a shared `tests/` helper). Engine: `bundled_demos.bundled_demos` (console script, path, `install_name`). The real demo is checked by the (c) row in `test_bundled_demos.py`. | none: no engine arc only it reaches |
| `tests/test_bundled_demo_discovery.py` | `test_a_bundled_demo_is_a_frozen_record` | (b) | Build a `BundledDemo` directly from stand-in values (no scene needed). Engine: the frozen dataclass. | none: no engine arc only it reaches |
| `tests/test_bundled_demo_discovery.py` | `test_package_demo_paths_lists_only_recordings_and_leaves_out_bookmarked_copies` | (b) | Write a small stand-in recording in `tmp_path` with `glitchygames.tracing.write_trace`, with at least 3 frames because `bookmarks=[2]`. It replaces `PADDLESLAP_DEMO_PATH` as the source of `write_bookmarked_copy`. Engine: `package_demo_paths`, `tracing.is_bookmarked_copy`. | none: no engine arc only it reaches |
| `tests/test_bundled_demo_discovery.py` | `test_every_member_package_is_searched_by_default` | (c) | It already searches every member by default (`MEMBER_LAYERS`). Compare the result with the expected set from the workspace (each member package's `demos/*.jsonl.gz`), not with `'paddleslap'`, and assert that it is non-empty. | none: no engine arc only it reaches |
| `tests/test_bundled_demo_discovery.py` | `test_a_console_script_is_found_by_the_module_of_its_entry_point` | (b) | `write_stand_in_distribution` on `sys.path`, whose entry point is in the stand-in module. Engine: `console_script_in_module`. | none: no engine arc only it reaches |
| `tests/test_recording_report.py` | `test_a_real_recording_reports_every_run_and_no_behaviour_change` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_recording_report.py`. It rebaselines PaddleSlap's golden twice through its console script and checks that golden's own history (its move from `glitchygames.examples.paddleslap` to `paddleslap`). `rebaselined_twice` moves with it. `REPO_FIXTURE` comes from `fixture_path`, not from `tests.replay.test_replay_plugin`. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestTheRecordings::test_this_projects_recordings` | (c) | Expected set from the workspace: every member golden (`replay_fixtures_directory`) and every bundled demo (`bundled_demos()`), by ledger name, equal `metric_recordings(...).replayable`, and are non-empty. This replaces the `PADDLESLAP_DEMO_PATH` import and the `mr-muncher` literal. | none: no engine arc only it reaches |
| `tests/test_replay_metrics.py` | `TestTheRecordings::test_each_game_of_a_member_with_several_is_measured` (per golden) | (c) | Parametrize over the members with more than one golden, found in the workspace (today, Brave Adventurer's `golden-classic`/`golden-papyrus`). Expected set: that list is non-empty. | none: no engine arc only it reaches |
| `tests/test_replay_metrics.py` | `TestTheRecordings::test_a_bookmarked_copy_beside_a_members_golden_is_not_measured` | (c) | It copies Brave Adventurer's golden into a `tmp_path` project and resolves the installed `brave-adventurer` console script. Use a member found in the workspace (its distribution, package path and golden). Expected set: as for the first row of this class. | none: no engine arc only it reaches |
| `tests/test_replay_metrics.py` | `TestTheRecordings::test_the_root_layout_finds_each_games_golden_and_skips_a_bookmarked_copy` | (c) | The root layout's directory names the installed `paddleslap` console script. Use a member console script found in the workspace, and its golden. | none: no engine arc only it reaches |
| `tests/test_replay_metrics.py` | `TestTheRecordings::test_a_demo_no_console_script_replays_is_reported_not_raised` | (b) | `write_stand_in_package` plus `write_stand_in_distribution` (a demo package that has a console script) in place of `paddleslap`/`PADDLESLAP_DEMO_PATH`. Engine/tool: `metric_recordings` with `demo_packages`. | none: no engine arc only it reaches |
| `tests/test_replay_metrics.py` | `TestTheRecordings::test_the_measured_demos_are_exactly_the_engines_bundled_demos` | (c) | It already compares two discoveries. Replace the `('paddleslap', 'paddleslap/demos/rally.jsonl.gz')` literal with the workspace's expected demo set, and assert that it is non-empty: today two empty sets would pass. | none: no engine arc only it reaches |
| `tests/test_replay_metrics.py` | `TestMeasuringIntoRowFiles::test_a_measurement_writes_row_files_naming_the_code_tree` | (c) | `copied_golden` copies PaddleSlap's golden and `measure` rebaselines it in a child process through the `paddleslap` console script. `copied_golden` should take one member found in the workspace (its golden, its console script, and its member path in the `tmp_path` project). Expected set: as for `test_this_projects_recordings`. `TestMeasuring` reads the run count from that golden, so the asserted numbers follow it. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuringIntoRowFiles::test_a_missing_origin_main_is_said_once` | (c) | `copied_golden` copies PaddleSlap's golden and `measure` rebaselines it in a child process through the `paddleslap` console script. `copied_golden` should take one member found in the workspace (its golden, its console script, and its member path in the `tmp_path` project). Expected set: as for `test_this_projects_recordings`. `TestMeasuring` reads the run count from that golden, so the asserted numbers follow it. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuringIntoRowFiles::test_the_same_code_tree_is_measured_once_per_machine` | (c) | `copied_golden` copies PaddleSlap's golden and `measure` rebaselines it in a child process through the `paddleslap` console script. `copied_golden` should take one member found in the workspace (its golden, its console script, and its member path in the `tmp_path` project). Expected set: as for `test_this_projects_recordings`. `TestMeasuring` reads the run count from that golden, so the asserted numbers follow it. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuringIntoRowFiles::test_the_summary_names_the_rows_directory` | (c) | `copied_golden` copies PaddleSlap's golden and `measure` rebaselines it in a child process through the `paddleslap` console script. `copied_golden` should take one member found in the workspace (its golden, its console script, and its member path in the `tmp_path` project). Expected set: as for `test_this_projects_recordings`. `TestMeasuring` reads the run count from that golden, so the asserted numbers follow it. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestHistoryRunsInThePendingFile::test_a_history_run_on_a_commit_not_on_origin_main_is_not_appended` | (c) | `copied_golden` copies PaddleSlap's golden and `measure` rebaselines it in a child process through the `paddleslap` console script. `copied_golden` should take one member found in the workspace (its golden, its console script, and its member path in the `tmp_path` project). Expected set: as for `test_this_projects_recordings`. `TestMeasuring` reads the run count from that golden, so the asserted numbers follow it. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestHistoryRunsInThePendingFile::test_a_history_run_on_a_commit_on_origin_main_is_appended` | (c) | `copied_golden` copies PaddleSlap's golden and `measure` rebaselines it in a child process through the `paddleslap` console script. `copied_golden` should take one member found in the workspace (its golden, its console script, and its member path in the `tmp_path` project). Expected set: as for `test_this_projects_recordings`. `TestMeasuring` reads the run count from that golden, so the asserted numbers follow it. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuring::test_a_measurement_appends_rows_and_a_second_one_skips` | (c) | `copied_golden` copies PaddleSlap's golden and `measure` rebaselines it in a child process through the `paddleslap` console script. `copied_golden` should take one member found in the workspace (its golden, its console script, and its member path in the `tmp_path` project). Expected set: as for `test_this_projects_recordings`. `TestMeasuring` reads the run count from that golden, so the asserted numbers follow it. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuring::test_a_published_measurement_counts_as_measured` | (c) | `copied_golden` copies PaddleSlap's golden and `measure` rebaselines it in a child process through the `paddleslap` console script. `copied_golden` should take one member found in the workspace (its golden, its console script, and its member path in the `tmp_path` project). Expected set: as for `test_this_projects_recordings`. `TestMeasuring` reads the run count from that golden, so the asserted numbers follow it. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuring::test_uncommitted_changes_are_refused_unless_allowed` | (c) | `copied_golden` copies PaddleSlap's golden and `measure` rebaselines it in a child process through the `paddleslap` console script. `copied_golden` should take one member found in the workspace (its golden, its console script, and its member path in the `tmp_path` project). Expected set: as for `test_this_projects_recordings`. `TestMeasuring` reads the run count from that golden, so the asserted numbers follow it. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuring::test_failures_are_reported_and_measured_rows_kept` | (c) | `copied_golden` copies PaddleSlap's golden and `measure` rebaselines it in a child process through the `paddleslap` console script. `copied_golden` should take one member found in the workspace (its golden, its console script, and its member path in the `tmp_path` project). Expected set: as for `test_this_projects_recordings`. `TestMeasuring` reads the run count from that golden, so the asserted numbers follow it. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuring::test_an_unreplayable_recording_is_one_line_and_the_others_are_measured` | (c) | `copied_golden` copies PaddleSlap's golden and `measure` rebaselines it in a child process through the `paddleslap` console script. `copied_golden` should take one member found in the workspace (its golden, its console script, and its member path in the `tmp_path` project). Expected set: as for `test_this_projects_recordings`. `TestMeasuring` reads the run count from that golden, so the asserted numbers follow it. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuring::test_a_replay_of_another_commit_is_a_failure` | (c) | `copied_golden` copies PaddleSlap's golden and `measure` rebaselines it in a child process through the `paddleslap` console script. `copied_golden` should take one member found in the workspace (its golden, its console script, and its member path in the `tmp_path` project). Expected set: as for `test_this_projects_recordings`. `TestMeasuring` reads the run count from that golden, so the asserted numbers follow it. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestTheCommandLine::test_measure_one_recording_then_clear` | (c) | `--only 'paddleslap/demos'` measures PaddleSlap's bundled demo in a child process. Choose `--only` from a demo found by `bundled_demos()` (asserted non-empty), and compare the row with that demo's ledger name. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestTheCommandLine::test_the_hooks_command_line_writes_row_files_naming_the_tree` | (c) | `--only 'paddleslap/demos'` measures PaddleSlap's bundled demo in a child process. Choose `--only` from a demo found by `bundled_demos()` (asserted non-empty), and compare the row with that demo's ledger name. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/world/test_frame_integration.py` | `TestPaddleSlapInTheFrame::test_paddle_hit_and_spawned_ball_are_drawn_at_their_world_positions` | (b) | A stand-in world scene, run under this file's `running_scene`/`step` (stand-ins such as `CameraFreeScene` are already here). In its `dt_tick` it reverses one world sprite's speed and spawns a second world sprite. Reproduce: a ball 1 px right of a paddle's right edge, at speed x -300.0, y 0.0, giving two balls after one spawn (`PADDLESLAP_BALLS_AFTER_ONE_SPAWN = 2`). Assert both are drawn at `snapped_world_position` in the same frame, and the new one never at (0, 0). | none: no engine arc only it reaches |
| `tests/world/test_gameplay_recording.py` | `TestRecordingThroughTheEngine::test_saves_opened_before_recording_are_in_the_header` | (b) | A stand-in scene that opens its save store in `__init__` (as PaddleSlap's `self.saves` does), recorded through the golden-trace engine (`GoldenTraceEngine`, `command_line`, `GoldenTraceEngine.start_trace_recording`) because `record_trace` takes only `GAME_SCENES` keys. The header's `SAVES_HEADER_FIELD` is keyed by the stand-in's app name, not `'paddleslap'`. | none: no engine arc only it reaches |
| `tests/world/test_gameplay_recording.py` | `test_recording_matches_the_golden_harness_frames` | (b) | The stand-in departure/arrival session (`record_session`/`DepartureRecordedScene` in `tests/world/test_gameplay_replay.py`), or a stand-in like it. It needs a transition ride, a pause through `PauseScene`, key taps on known frames, and a fixed `FRAME_SECONDS` dt. It compares the engine's recording with the harness's own frames. Clockwork Keep supplied 900 frames, an elevator ride, a pause, K_UP before frame 10 and K_RIGHT before frame 70. | RISK: the only root test reaching `scenes/scene.py` `SceneManager._process_transition_events` (2632, the drain loop running more than once). The stand-in must queue at least 2 events in one transition frame. It also shares `transitions/elevator.py` `_draw_shaft_walls` (208-209), `animation/state_machine.py` `_switch_to` (342/346), `audio/recipes.py` `render` (116-117) and `camera.py` `update_scroll` (144) with golden-trace rows (c), which stay |
| `tests/world/test_gameplay_replay.py` | `TestRoundTrip::test_golden_script_recording_replays_without_divergence` (per `GAME_SCENES` key) | (c) | It is parametrized over the tool's `GAME_SCENES`. Expected set: those keys equal the games of the goldens the workspace holds (from their headers' logical names), and are non-empty. | Shared: `audio/synth.py` `concatenate` (437) and `sprites/animated.py` `update_nested_sprites` (2663), with `test_game_matches_golden_trace` (c); both stay |
| `tests/world/test_gameplay_replay.py` | `TestRoundTrip::test_golden_harness_stopped_early_reports_a_length_divergence` | (b) | This file's `record_session`/`replay_session` stand-in, with a frame limit like `replay_golden_recording(frame_limit=...)`: 30 frames recorded, 10 replayed (`EARLY_STOP_RECORDED_FRAMES`/`EARLY_STOP_FRAME_LIMIT`). Engine: the replay's `LENGTH_DIVERGENCE`. | none: no engine arc only it reaches |
| `tests/world/test_gameplay_replay.py` | `TestRecordedDisplaySize::test_a_recording_on_a_window_of_another_size_replays_at_that_size` | (b) | A stand-in scene that places a sprite from the display height (as PaddleSlap places its paddles), recorded asking for 800x480 on a window `window_manager_choosing_size` makes 800x600 (`WINDOW_MANAGER_SIZE`), for `DISPLAY_SIZE_FRAME_COUNT` (10) frames, then replayed. `record_session` and `window_manager_choosing_size` already exist here. | none: no engine arc only it reaches |
| `tests/world/test_gameplay_replay.py` | `TestAuditOption::test_a_golden_recording_passes_the_real_audit` | (b) | A seeded stand-in game source, written to `tmp_path`, recorded and then replayed with `--audit` as children. `test_unseeded_randomness_makes_the_real_audit_fail` already does this with `UNSEEDED_GAME_SOURCE`. This replaces `python -m paddleslap` with PaddleSlap's golden. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/world/test_golden_traces.py` | `test_expected_differences_cover_every_game` | (c) | Expected set: the baselines in `tests/world/golden/` equal `GOLDEN_TRACE_GAMES`, and are non-empty. They are frozen since the world-space change, and four games have them. The rule helpers (`tinker_feet_margin_pixels`, `scarab_feet_margin_pixels`, the falling-pose rules) import member modules with `importlib.import_module`, from each game's package as the workspace names it. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `test_game_matches_golden_trace` (per golden-trace game) | (c) | It runs each game in the harness by key. Same expected set as the row above. The member internals that `EXPECTED_DIFFERENCES` reads (`Tinker`, `PapyrusPlayer`, the scarab drawing) come in through `importlib.import_module` from the workspace's package names. | Shared: the transition, animation, audio and camera arcs listed under `test_recording_matches_the_golden_harness_frames`. This row stays in the root, so it keeps them covered |
| `tests/world/test_golden_traces.py` | `test_same_random_seed_gives_identical_paddleslap_traces` | (b) | A stand-in scene that draws from the engine's seeded random streams (`glitchygames.randomness`), run twice under the golden-trace engine with `--random-seed` 123 and once with 124 (`SEEDED_TRACE_SEED`, `SEEDED_TRACE_FRAME_COUNT` = 120 frames). Same seed, same sprites; another seed, different sprites. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_settling_finds_one_old_camera_for_the_whole_frame` | (c) | Unit tests of the golden-trace world rules, which measure Clockwork Keep's and Brave Adventurer's drawings. They go wherever the rules go and use the same `importlib.import_module` discovery. Expected set: as for `test_expected_differences_cover_every_game`. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_settling_rejects_a_tinker_no_old_position_explains` | (c) | Unit tests of the golden-trace world rules, which measure Clockwork Keep's and Brave Adventurer's drawings. They go wherever the rules go and use the same `importlib.import_module` discovery. Expected set: as for `test_expected_differences_cover_every_game`. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_settling_rejects_sprites_no_single_old_camera_explains` | (c) | Unit tests of the golden-trace world rules, which measure Clockwork Keep's and Brave Adventurer's drawings. They go wherever the rules go and use the same `importlib.import_module` discovery. Expected set: as for `test_expected_differences_cover_every_game`. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_blank_image_margins_are_measured_from_the_drawings` | (c) | Unit tests of the golden-trace world rules, which measure Clockwork Keep's and Brave Adventurer's drawings. They go wherever the rules go and use the same `importlib.import_module` discovery. Expected set: as for `test_expected_differences_cover_every_game`. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_scarab_on_its_blank_image_stood_the_margin_higher (per case)` | (c) | Unit tests of the golden-trace world rules, which measure Clockwork Keep's and Brave Adventurer's drawings. They go wherever the rules go and use the same `importlib.import_module` discovery. Expected set: as for `test_expected_differences_cover_every_game`. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_scarab_raised_rule_rejects_a_scarab_still_dropping_from_its_spawn` | (c) | Unit tests of the golden-trace world rules, which measure Clockwork Keep's and Brave Adventurer's drawings. They go wherever the rules go and use the same `importlib.import_module` discovery. Expected set: as for `test_expected_differences_cover_every_game`. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_scarab_drop_rule_needs_the_old_scarab_at_its_spawn_height` | (c) | Unit tests of the golden-trace world rules, which measure Clockwork Keep's and Brave Adventurer's drawings. They go wherever the rules go and use the same `importlib.import_module` discovery. Expected set: as for `test_expected_differences_cover_every_game`. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_scarab_drop_rule_rejects_a_scarab_that_has_landed` | (c) | Unit tests of the golden-trace world rules, which measure Clockwork Keep's and Brave Adventurer's drawings. They go wherever the rules go and use the same `importlib.import_module` discovery. Expected set: as for `test_expected_differences_cover_every_game`. | none: no engine arc only it reaches |
| `tests/world/test_transition_input.py` | `test_jump_pressed_during_elevator_ride_does_not_jump_on_arrival` | (b) | This file's `DepartureScene`/`ArrivalScene` (shared `ActionMap`). A jump pressed and released during the ride must not be `just_pressed`, and must not move the arrival scene's sprite up. Clockwork Keep supplied `SPAWN_SETTLE_FRAMES`, `ELEVATOR_SETTLE_FRAMES`, `ARRIVAL_WATCH_FRAMES` and K_w then K_UP. Engine: `SceneManager._process_transition_events`, `TRANSITION_DISCARDED_EVENT_TYPES`. | Shared: `transitions/elevator.py` 208-209 and the other transition arcs, with `test_game_matches_golden_trace` (c), which stays. A stand-in using another transition no longer reaches the elevator arcs |

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
