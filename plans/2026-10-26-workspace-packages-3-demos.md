# Workspace Packages, Part 3: The Demos, the `src/` Layout, and Members Kept Apart — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Tasks A1-C6 done (+B5b, user-added), 2026-10-26; final review passed (fixes 016c53ba, nits 6a8df329). Stage D (the engine owns every recording tool) PLANNED 2026-10-26; D1-D11 DONE 2026-10-27 (D10: docs, cleanups and the stage's verification); final Stage D review fixes DONE 2026-10-27 (I1-I4, M1, M3, M4, M6 and the reserved-flag refusal; M2, M5, M7-M10 in `plans/future-work.md`), awaiting the user's review and look at `--compare-trace` (D11 Step 3).
Stage A DONE; Stage B DONE (B1-B7, automated verification green; the user runs each demo by
hand); Stage C DONE (C1-C6). (Originally PLANNED 2026-10-26.)
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
- **Stage D:** the engine owns every recording, replay and measurement tool, as game flags and
  as the `glitchygames` command (added 2026-10-26; see "Stage D" below).

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
9. **The browser engine archive** leaves out git-ignored files: ignored files never ship (a new,
   not-yet-added file still does). This fixes the bug where ignored files such as `.DS_Store` ship
   in local builds.
   - *Note, 2026-10-26 (the controller's B2 ruling, refining this decision):* the code lists
     `git ls-files --cached --others --exclude-standard`, not tracked files alone. Reason: a
     developer building before `git add` should get the new file, and the bug is ignored files
     shipping, not untracked ones.
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
| `scripts/build_browser_bundle.py` | the engine archive without git-ignored files (Stage B) |
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

### Task B2: The browser engine archive leaves out git-ignored files (the bug fix)

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
- [ ] **Step 3:** commit — "Browser bundles leave out ignored files".

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

**Written 2026-10-26 (Task C1). Revised twice the same day after review**, with the user's
decisions and the controller's rulings applied, including the narrowed exemptions of the second
round. Branch `feature/workspace-packages-3a-src-layout`, from
273fa323. Stages C2-C5 work from this table.

**Test count at the base (273fa323):** `uv run pytest --collect-only -q -n0 --no-cov` collects
21032 tests over every test root, and the root `tests/` alone collects 15343. Each move must
keep these counts, apart from new tests (Review Focus 5).

**Decisions applied (2026-10-26):**
- **The user:** a "pick one member" test uses a stand-in game. The test writes a tiny game to
  `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern in `tests/world/test_gameplay_replay.py`) and
  installs it as a stand-in distribution (`write_stand_in_distribution`,
  `tests/replay/test_replay_plugin.py`). Each such row says which facts its stand-in must make
  explicit.
- **The user, narrowed by the controller:** in `tests/world/test_golden_traces.py`, only the
  per-game world rules' imports of member internals are exempt. That covers `TestWorldRules`, the
  `EXPECTED_DIFFERENCES` rule helpers, and the imports they need. `test_game_matches_golden_trace`
  and `test_expected_differences_cover_every_game` stay (c), with an independent expected set.
- **The controller:** the per-game control tables of `tests/replay/test_golden_replays.py` move
  unchanged into their own helper module, `tests/replay/golden_replay_controls.py` (C4 owns the
  move). Only that module is exempt; `test_golden_replays.py` stays guarded.
- **The controller:** two missing files are added (`tests/replay/test_recording_logical_names.py`
  and `tests/test_measure_staged_replays.py`).
- **The controller:** `tests/test_recording_report.py` is split. PaddleSlap's history goes to
  its member, and the root keeps a stand-in end-to-end test.
- **The controller:** the touch-control checks become per-member tests, and the root keeps only
  the generic check.
- **The controller:** the transition-input stand-in uses `ElevatorTransition`.
- **The controller:** the playback-scope stand-in keeps the Review Focus 4 check.
- **The controller:** expected sets are independent of the discovery they check.
- **The controller:** tool keys map to logical names through
  `logical_name(scene_class=GAME_SCENES[key])`.
- **The controller:** bundled demos compare by `(package, name)`.
- **The controller:** `test_build_browser_bundle` compares distributions.

**What counts as a borrow.** A root test borrows a member when it does any of these:
- imports a member package (`scripts.workspace_packages.workspace_members`), at module level or
  inside a function;
- runs member code in this process;
- starts a member in a child process (a console script, `python -m <package>`, or
  `replay_recording_headless`/`rebaseline_recording_headless`/`measure`);
- loads a member by string or entry point (`__import__`, `game_entry_point(...).load()`,
  `find_spec`, a game key in a tool's registry);
- needs a member installed to resolve its console script.

These are not borrows, because the member's name is only data:
- a stand-in class whose `__module__` is a member's name;
- a logical name in a hand-written header;
- a ledger or fixture path string;
- a pyproject read;
- reading a member's golden file by path without running the game.

**How the list was made:**
1. An AST scan of every file under `tests/`, helpers included, for imports of the 12 member
   packages. Function-local imports count.
2. A string scan for every package, distribution and console-script name.
3. A per-test AST pass that follows module-level helpers, fixtures (autouse too) and helper
   classes.
4. A run of the root suite with per-test coverage contexts:
   `COVERAGE_CORE=ctrace uv run pytest --dummy-only tests --cov-context=test --cov-branch`. The
   default `sysmon` core records no dynamic contexts, so `ctrace` is needed. This gives the
   member code each test runs in this process, and the root tests that reach each engine arc.
5. A reading of every candidate. Child processes are not measured, so those tests were found
   by reading.
6. A check of the files the review found missing.

**Differences from the list above (Task C1):**
- The brief's "21 files" are 19. Its two `joystick_demo` files, `test_bundled_demos.py` and
  `test_playback_scope.py`, are already among them.
- Nine more files borrow:
  - `tests/engine/test_engine_lifecycle.py`
  - `tests/test_build_browser_bundle.py`
  - `tests/replay/test_instant_replay.py`
  - `tests/replay/test_record_scripted_session.py`
  - `tests/replay/test_rebaseline_across_logical_modules.py`
  - `tests/test_recording_report.py`
  - `tests/world/test_gameplay_replay.py`
  - `tests/replay/test_recording_logical_names.py` (it imports members through
    `importlib.import_module` from the recordings' logical names)
  - `tests/test_measure_staged_replays.py` (it needs installed `paddleslap`/`clockwork-keep`
    console scripts, and every member's bundled demos)
- In all: 28 files and 123 tests, in 124 rows, because the recording-report test is split in
  two. The other tests in these files do not borrow and stay as they are.

**Not borrows, left as they are.** These files name a member only as data:
- `tests/world/test_gameplay_replay.py`: `TestRecordedGameCheck` and
  `test_a_rebaseline_writes_the_current_games_logical_name`.
- `tests/test_recording_metrics.py`.
- `tests/replay/test_replay_plugin.py`: the misplaced and nested collection errors, and the
  `mr_muncher` header strings.
- `tests/replay/test_record_scripted_session.py`: the supervisor unit tests that pass
  `game_key='paddleslap'`, and the fixture-table checks.
- `tests/test_browser_touch_controls.py`: the layout and boot-config tests.
- `tests/scenes/test_scene.py`.
- `tests/test_logical_names.py`, `tests/test_workspace_packages.py`,
  `tests/test_workspace_config.py`, `tests/test_suite_collection.py`,
  `tests/test_generate_performance_graphs.py`, `tests/test_mkdocs_hooks_browser_games.py`,
  `tests/test_gen_ref_pages.py`, `tests/test_ci_config.py`, `tests/test_engine_doors.py`,
  `tests/state/test_paths.py`, `tests/benchmarks/test_benchmarks.py`,
  `tests/sprites/test_sprite_animation.py`, `tests/demo_runs.py`.

**Exemptions.** C5's guard lists exactly these:
- **`tests/world/test_golden_traces.py`, by imported name (the user, 2026-10-26, narrowed by the
  controller).** Only these nine imports are exempt; any other member import in the file fails
  the guard:
  - `from brave_adventurer import constants`
  - `from brave_adventurer.drawing import draw_player, draw_scarab`
  - `from brave_adventurer.player import Player`
  - `from brave_adventurer_core import constants`
  - `from brave_adventurer_papyrus.player import PapyrusPlayer`
  - `from brave_adventurer_papyrus.sprite_utils import apply_transparency_and_scale`
  - `from clockwork_keep.constants import PLAYER_HEIGHT, PLAYER_WIDTH`
  - `from clockwork_keep.drawing import draw_tinker`
  - `from clockwork_keep.player import Tinker`

  They serve the 8 `TestWorldRules` rows, the `EXPECTED_DIFFERENCES` rule helpers and the
  `*_OLD_FALL_POSES` constants.
- **`tests/replay/golden_replay_controls.py`, the whole module (the controller, 2026-10-26).**
  This new helper holds, unchanged:
  - `GAMEPLAY_ACTION_MAPS`, `ENGINE_SCENE_CONTROLS`, `UNEXERCISED_CONTROLS` and
    `DRAWING_FIRE_CONTROLS`;
  - the helpers and constants that build them;
  - the six scene-class imports and `drawing_fire.players`.

  The 4 control-table tests stay in `tests/replay/test_golden_replays.py` and import from it.

**Out of scope: the tools.** These five scripts import games:
- `scripts/record_golden_traces.py`
- `scripts/audio_glitch_probe.py`
- `scripts/bitmappy_entry.py`
- `scripts/simulate_drawing_fire.py`
- `scripts/ai_query_inspector.py`

They are tools, not tests. One matters to C5: `scripts/record_golden_traces.py` imports every
game at module level (`GAME_SCENES`). Nineteen root test files and helpers import it for harness
pieces (`GoldenTraceEngine`, `GoldenTraceSceneManager`, `command_line`). So every member is
loaded whenever those tests run, and C5's AST guard does not see it. C6 records this in
`plans/future-work.md`.

**Decision 11 (engine-only coverage from the root `tests/` alone).** Engine coverage from the
root tests alone is compared before and after each of C2, C3 and C4: C3's stand-ins and C4's
rewrites can drop arcs as surely as C2's moves can. From the coverage-context run:
- **`scenes/scene.py` `SceneManager._process_transition_events` (2632)** is reached only by
  `test_recording_matches_the_golden_harness_frames`, which is (b). Its stand-in must queue at
  least 2 events in one transition frame, or the engine gets a new test that does.
- **Every other engine arc that only borrowing tests reach** stays reached after C2 and C3, but
  only by root tests that run members (the (c) and exempt rows). The future-work note below
  lists them.

**Notes for the tasks:**
- **Shared helpers.** Move `write_stand_in_distribution` and `member_recording_path`/
  `write_header_only_recording` (`tests/replay/test_replay_plugin.py`), `write_stand_in_package`
  (`tests/test_bundled_demo_discovery.py`), and a stand-in game source with its recorder, into
  one shared `tests/` helper (C3's "stand-in that more than one file needs").
- **Children need the stand-in.** A child process must find the stand-in distribution and its
  module, so their directory goes on the child's `PYTHONPATH` as well as on `sys.path`.
- **The touch-control helpers** (`SCANCODE_BY_CODE`, `SHARED_SCREEN_CODES`, `bound_scancodes`,
  `layout_buttons`) move to a shared `tests/` helper that the member tests import.
- **Independent expected sets** come from the workspace's shape, not from the discovery under
  test:
  - every `games`-layer member holds at least one golden: 5 games, 6 goldens;
  - the game console scripts equal the union of each member's `console_scripts`;
  - the bundled demos are `{('paddleslap', 'rally.jsonl.gz')}`;
  - the browser `GAMES` keys are the `games`-layer distributions plus `bitmappy`.
- **No row is (d).**

**Counts:**

| Category | Rows |
|---|---|
| (a) | 21 |
| (b) | 76: 21 stand-ins in this process, 55 stand-in games or distributions |
| (c) | 15 |
| Exempt | 12: 8 by name (the user, `TestWorldRules`), 4 through the helper module (the controller) |
| (d) | 0 |
| **Total** | **124 rows (123 tests) in 28 files** |

Parametrized tests count once each.

| File | Test | Category | Target, stand-in or discovery | Decision 11 (root-only engine coverage) |
|---|---|---|---|---|
| `tests/animation/test_animation.py` | `TestFallingConditionEquivalence::test_matches_old_logic_around_threshold` | (b) stand-in, in process | Two threshold floats instead of the imports: 10.0 (`brave_adventurer_core/constants.py` `FALLING_VELOCITY_THRESHOLD`) and 50.0 (`clockwork_keep/constants.py`), each with a comment naming its source. Engine: the animation `parse(...).evaluate` expression. | none: no engine arc only it reaches |
| `tests/collision/test_ball_paddle_collision.py` | `TestBallPairDistance::test_collision_distance_is_the_sum_of_visible_radii` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collisions.py`. Subject is `Game._calculate_ball_distance`, `_handle_ball_collisions` and `_keep_ball_playable`. `make_ball` (engine `BallSprite`) stays in `tests/` and is imported. | none: no engine arc only it reaches |
| `tests/collision/test_ball_paddle_collision.py` | `TestBallPairPlayability::test_head_on_hit_on_a_still_ball_leaves_neither_ball_stalled_or_flat` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collisions.py`. Subject is `Game._calculate_ball_distance`, `_handle_ball_collisions` and `_keep_ball_playable`. `make_ball` (engine `BallSprite`) stays in `tests/` and is imported. | none: no engine arc only it reaches |
| `tests/collision/test_ball_paddle_collision.py` | `TestBallPairPlayability::test_near_vertical_ball_is_turned_to_the_steepest_serve_angle` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collisions.py`. Subject is `Game._calculate_ball_distance`, `_handle_ball_collisions` and `_keep_ball_playable`. `make_ball` (engine `BallSprite`) stays in `tests/` and is imported. | none: no engine arc only it reaches |
| `tests/collision/test_ball_paddle_collision.py` | `TestBallPairPlayability::test_flat_ball_is_turned_to_the_shallowest_serve_angle` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collisions.py`. Subject is `Game._calculate_ball_distance`, `_handle_ball_collisions` and `_keep_ball_playable`. `make_ball` (engine `BallSprite`) stays in `tests/` and is imported. | none: no engine arc only it reaches |
| `tests/collision/test_ball_paddle_collision.py` | `TestBallPairPlayability::test_ball_already_moving_like_a_serve_is_unchanged` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collisions.py`. Subject is `Game._calculate_ball_distance`, `_handle_ball_collisions` and `_keep_ball_playable`. `make_ball` (engine `BallSprite`) stays in `tests/` and is imported. | none: no engine arc only it reaches |
| `tests/collision/test_collision.py` | `TestRedrawnGameSprites::test_cobra_hitbox_follows_first_draw_and_strike` | (a) | brave-adventurer: `src/games/brave-adventurer/tests/test_brave_adventurer_hitboxes.py` (the Cobra `brave_adventurer.enemies`). | none: no engine arc only it reaches |
| `tests/collision/test_collision.py` | `TestPapyrusHitboxScale::test_scaled_papyrus_player_collides_at_twice_the_toml_hitbox` | (a) | brave-adventurer: `test_brave_adventurer_hitboxes.py` (Papyrus `SPRITE_SCALE` hitboxes). | Shared, not alone: `sprites/animated.py` `SpriteAnimation.__init__` (575), `animation/state_machine.py` `evaluate` (291-292) and `physics/body.py` `get_animation_context` (133) are also reached by golden-trace and golden-replay rows (c), which stay |
| `tests/collision/test_collision.py` | `TestPapyrusHitboxScale::test_freshly_constructed_sprites_have_scaled_hitboxes_before_any_tick` | (a) | brave-adventurer: `test_brave_adventurer_hitboxes.py` (Papyrus `SPRITE_SCALE` hitboxes). | Shared, not alone: `sprites/animated.py` `SpriteAnimation.__init__` (575), `animation/state_machine.py` `evaluate` (291-292) and `physics/body.py` `get_animation_context` (133) are also reached by golden-trace and golden-replay rows (c), which stay |
| `tests/collision/test_collision.py` | `TestPapyrusHitboxScale::test_scale_one_keeps_native_hitbox` | (a) | brave-adventurer: `test_brave_adventurer_hitboxes.py` (Papyrus `SPRITE_SCALE` hitboxes). | Shared, not alone: `sprites/animated.py` `SpriteAnimation.__init__` (575), `animation/state_machine.py` `evaluate` (291-292) and `physics/body.py` `get_animation_context` (133) are also reached by golden-trace and golden-replay rows (c), which stay |
| `tests/engine/test_engine_lifecycle.py` | `test_every_game_powers_on_through_its_own_main` (9 console scripts x 2 backgrounds) | (c) | It loads each `main` by entry point (`game_entry_point(...).load()`). Parametrize from `declared_console_scripts(project_root=...)` minus `NOT_GAME_CONSOLE_SCRIPTS`. Independent expected set, asserted in `test_every_game_console_script_is_covered`: (1) those scripts equal the union of every member's `console_scripts`; (2) **there are exactly 9 of them**: 5 games, 3 demos and Bitmappy. | The only root test reaching `engine/game_engine.py` `_crash_boundary` (2577->2584) and `_run_game` (2596 exit). It stays in the root (Review Focus 4), so the engine keeps that coverage |
| `tests/game_objects/test_ball_collision_physics.py` | `TestBallCollisionSweepStationaryTarget::test_mover_stops_and_target_takes_its_velocity` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collision_physics.py`, with the sweep helper class built on `Game.__new__` (`_handle_ball_collisions`). `drawn_position`/`place_ball_center` stay in `tests/game_objects/ball_helpers.py`. | none: no engine arc only it reaches |
| `tests/game_objects/test_ball_collision_physics.py` | `TestBallCollisionSweepMovingPair::test_balls_swap_velocities` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collision_physics.py`, with the sweep helper class built on `Game.__new__` (`_handle_ball_collisions`). `drawn_position`/`place_ball_center` stay in `tests/game_objects/ball_helpers.py`. | none: no engine arc only it reaches |
| `tests/game_objects/test_ball_collision_physics.py` | `TestBallCollisionSweepFrameAlignedMeeting::test_head_on_balls_meeting_on_a_frame_collide` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_ball_collision_physics.py`, with the sweep helper class built on `Game.__new__` (`_handle_ball_collisions`). `drawn_position`/`place_ball_center` stay in `tests/game_objects/ball_helpers.py`. | none: no engine arc only it reaches |
| `tests/game_objects/test_collision_scenarios.py` | `TestPaddleCollisions::test_ball_bounces_off_left_paddle` | (b) stand-in, in process | A stand-in `SpeedUpSettings` instead of `PADDLESLAP_SPEED_UP`: `triggers=PADDLE_BOUNCE`, `curve=LOGARITHMIC`, `axes=BOTH`, `multiplier=1.15`, `max_speed=500.0` (from `paddleslap/__init__.py`). Engine: `BallSprite.speed_up`, `_do_bounce`. | none: no engine arc only it reaches |
| `tests/game_objects/test_collision_scenarios.py` | `TestPaddleCollisions::test_ball_bounces_off_right_paddle` | (b) stand-in, in process | A stand-in `SpeedUpSettings` instead of `PADDLESLAP_SPEED_UP`: `triggers=PADDLE_BOUNCE`, `curve=LOGARITHMIC`, `axes=BOTH`, `multiplier=1.15`, `max_speed=500.0` (from `paddleslap/__init__.py`). Engine: `BallSprite.speed_up`, `_do_bounce`. | none: no engine arc only it reaches |
| `tests/game_objects/test_collision_scenarios.py` | `TestPaddleCollisions::test_paddle_collision_spawns_new_ball` | (b) stand-in, in process | A stand-in `SpeedUpSettings` instead of `PADDLESLAP_SPEED_UP`: `triggers=PADDLE_BOUNCE`, `curve=LOGARITHMIC`, `axes=BOTH`, `multiplier=1.15`, `max_speed=500.0` (from `paddleslap/__init__.py`). Engine: `BallSprite.speed_up`, `_do_bounce`. | none: no engine arc only it reaches |
| `tests/game_objects/test_collision_scenarios.py` | `TestPaddleCollisions::test_paddle_collision_reverses_horizontal_direction` | (b) stand-in, in process | A stand-in `SpeedUpSettings` instead of `PADDLESLAP_SPEED_UP`: `triggers=PADDLE_BOUNCE`, `curve=LOGARITHMIC`, `axes=BOTH`, `multiplier=1.15`, `max_speed=500.0` (from `paddleslap/__init__.py`). Engine: `BallSprite.speed_up`, `_do_bounce`. | none: no engine arc only it reaches |
| `tests/game_objects/test_collision_scenarios.py` | `TestIntegrationCollisions::test_mixed_collision_scenarios` | (b) stand-in, in process | A stand-in `SpeedUpSettings` instead of `PADDLESLAP_SPEED_UP`: `triggers=PADDLE_BOUNCE`, `curve=LOGARITHMIC`, `axes=BOTH`, `multiplier=1.15`, `max_speed=500.0` (from `paddleslap/__init__.py`). Engine: `BallSprite.speed_up`, `_do_bounce`. | none: no engine arc only it reaches |
| `tests/game_objects/test_collision_scenarios.py` | `TestIntegrationCollisions::test_multiple_balls_collision_behavior` | (b) stand-in, in process | A stand-in `SpeedUpSettings` instead of `PADDLESLAP_SPEED_UP`: `triggers=PADDLE_BOUNCE`, `curve=LOGARITHMIC`, `axes=BOTH`, `multiplier=1.15`, `max_speed=500.0` (from `paddleslap/__init__.py`). Engine: `BallSprite.speed_up`, `_do_bounce`. | none: no engine arc only it reaches |
| `tests/game_objects/test_collision_scenarios.py` | `TestBallToBallCollisions::test_ball_to_ball_collision_cooldown` | (a) | paddleslap: `test_paddleslap_ball_collisions.py`. The cooldown is the game's own (`Game._ball_collision_cooldowns`, `_on_ball_ball_collision`). | none: no engine arc only it reaches |
| `tests/game_objects/test_game_over_scene.py` | `TestGameOverIntegration::test_game_over_triggered_when_all_balls_dead` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_game_over.py`. Covers PaddleSlap's `dt_tick`, `PaddleSlapGameOverScene` and its high-score save. | none: no engine arc only it reaches |
| `tests/replay/test_bundled_demos.py` | `test_paddleslap_ships_a_demo` | (c) | Independent expected set, by `(package, name)` and not by path (nox installs non-editable copies): `{('paddleslap', 'rally.jsonl.gz')}` today, and every entry's console script is the member's own (`console_scripts` of the member holding that package). | none: no engine arc only it reaches |
| `tests/replay/test_bundled_demos.py` | `test_bundled_demo_replays_without_divergence` (one per demo) | (c) | It already discovers demos (`bundled_demo_paths()`) and replays each in a child through its console script; the row above is its expected set (an empty parametrize list would skip, not fail). | none: no engine arc only it reaches |
| `tests/replay/test_bundled_demos.py` | `test_the_paddleslap_demo_plays_in_game` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_demo_plays_in_game.py`. Drop the `joystick_demo` import: the row for `test_playback_scope.py` below gives the same-name scene case its own stand-in. `running_scene` and `step_finishing` stay in `tests/` and are imported. | Shared, not alone: `game_objects/ball.py` `dt_tick` (744) and `_finish_wall_bounce` (820-821) are also reached by (c) rows that stay |
| `tests/replay/test_golden_replays.py` | `test_every_fixture_directory_is_a_game_console_script` | (c) | It already discovers fixtures (`workspace_members(...)` replay fixtures). Independent expected set: the console scripts the goldens resolve to (`recording_console_script`) equal the union of the `console_scripts` of the `games`-layer members, which is 5 scripts. | none: no engine arc only it reaches |
| `tests/replay/test_golden_replays.py` | `test_every_golden_replay_is_replayed_by_its_games_console_script` (per game) | (c) | Parametrize over the goldens in the members' `replay_fixtures_directory`. Map the tool's keys to logical names explicitly with `logical_name(scene_class=GAME_SCENES[key])` and compare with each golden header's `game`. Independent expected set: every `games`-layer member holds at least one golden (5 games, 6 goldens). | none: no engine arc only it reaches |
| `tests/replay/test_golden_replays.py` | `test_a_members_golden_replay_is_replayed_by_the_members_console_script` | (b) stand-in game or distribution | Stand-in distribution, no child: `write_stand_in_distribution` with one console script, and a header-only recording at `<tmp>/<distribution>/tests/fixtures/replays/golden.jsonl.gz` (`member_recording_path`, `write_header_only_recording`, `test_replay_plugin.py`; `test_a_member_with_several_console_scripts_replays_through_the_recorded_games_script` is the pattern). Must make explicit: exactly one console script, so the member's script is chosen without reading the header. The `drawing-fire` root-layout path becomes a stand-in console script in the same dist-info. | none: no engine arc only it reaches |
| `tests/replay/test_golden_replays.py` | `test_a_tampered_golden_replay_is_reported_at_its_frame` | (b) stand-in game or distribution | Stand-in game, in this process: a stand-in scene's session recorded in `tmp_path` (`record_session`/`DepartureRecordedScene`, `tests/world/test_gameplay_replay.py`, or a stand-in like it) and replayed through the engine (`replay_through_engine` under a stand-in key, or `replay_session`). Must make explicit: a sprite on frame 10 (`TAMPERED_FRAME`) and every frame after it, so the 1 px move diverges at frame 10 as a `SPRITE_DIVERGENCE` (Drawing Fire's golden has none on frame 10, so 'any golden' would not do). | Shared: `ball.py` 744, 820-821; see the future-work note below the table |
| `tests/replay/test_golden_replays.py` | `test_a_rebaselined_golden_replay_names_the_tampered_frames_and_replays_clean` | (b) stand-in game or distribution | The same stand-in session as the row above. Must make explicit: a sprite on frame 10 and later, deterministic replay, so `--rebaseline` counts exactly the tampered frames that have a sprite and its output replays with no divergence. | Shared: `ball.py` 744, 820-821; see the future-work note below the table |
| `tests/replay/test_golden_replays.py` | `test_every_game_with_a_golden_replay_has_its_controls_listed` | exempt via helper (controller) | The test stays in `tests/replay/test_golden_replays.py`, which stays guarded. The per-game tables move unchanged, with no mapping change, into a helper module of their own, `tests/replay/golden_replay_controls.py`. They are `GAMEPLAY_ACTION_MAPS`, `ENGINE_SCENE_CONTROLS`, `UNEXERCISED_CONTROLS`, `DRAWING_FIRE_CONTROLS` and the helpers that build them (`Control`, `InputKind`, `_key_control`, `_scancode_control`, `_drawing_fire_snapshot_control`, `_controls_from_action_maps`, `_paddleslap_action_maps`, `PAUSE_SCENE_CONTROLS`, `GAMES_WITHOUT_A_PAUSE`, `PAUSING_GAMES`, `NO_GAMEPAD_IN_THE_SESSION`, `QUITS_ONCE`), with their imports of the six scene classes (`paddleslap.Game`, `BraveAdventurerScene`, `PapyrusBraveAdventurerScene`, `ClockworkKeepScene`, `DrawingFireScene`, `MrMuncherScene`) and `drawing_fire.players`. The test imports the tables from the helper. C5's guard exempts only `tests/replay/golden_replay_controls.py`. **C4 owns the move**: these tests are cross-member infrastructure, and C4 rewrites the file's other (c) rows. | none: no engine arc only it reaches |
| `tests/replay/test_golden_replays.py` | `test_each_golden_is_its_own_games_recording` | exempt via helper (controller) | The test stays in `tests/replay/test_golden_replays.py`, which stays guarded. The per-game tables move unchanged, with no mapping change, into a helper module of their own, `tests/replay/golden_replay_controls.py`. They are `GAMEPLAY_ACTION_MAPS`, `ENGINE_SCENE_CONTROLS`, `UNEXERCISED_CONTROLS`, `DRAWING_FIRE_CONTROLS` and the helpers that build them (`Control`, `InputKind`, `_key_control`, `_scancode_control`, `_drawing_fire_snapshot_control`, `_controls_from_action_maps`, `_paddleslap_action_maps`, `PAUSE_SCENE_CONTROLS`, `GAMES_WITHOUT_A_PAUSE`, `PAUSING_GAMES`, `NO_GAMEPAD_IN_THE_SESSION`, `QUITS_ONCE`), with their imports of the six scene classes (`paddleslap.Game`, `BraveAdventurerScene`, `PapyrusBraveAdventurerScene`, `ClockworkKeepScene`, `DrawingFireScene`, `MrMuncherScene`) and `drawing_fire.players`. The test imports the tables from the helper. C5's guard exempts only `tests/replay/golden_replay_controls.py`. **C4 owns the move**: these tests are cross-member infrastructure, and C4 rewrites the file's other (c) rows. | none: no engine arc only it reaches |
| `tests/replay/test_golden_replays.py` | `test_every_golden_replay_exercises_every_control (per game)` | exempt via helper (controller) | The test stays in `tests/replay/test_golden_replays.py`, which stays guarded. The per-game tables move unchanged, with no mapping change, into a helper module of their own, `tests/replay/golden_replay_controls.py`. They are `GAMEPLAY_ACTION_MAPS`, `ENGINE_SCENE_CONTROLS`, `UNEXERCISED_CONTROLS`, `DRAWING_FIRE_CONTROLS` and the helpers that build them (`Control`, `InputKind`, `_key_control`, `_scancode_control`, `_drawing_fire_snapshot_control`, `_controls_from_action_maps`, `_paddleslap_action_maps`, `PAUSE_SCENE_CONTROLS`, `GAMES_WITHOUT_A_PAUSE`, `PAUSING_GAMES`, `NO_GAMEPAD_IN_THE_SESSION`, `QUITS_ONCE`), with their imports of the six scene classes (`paddleslap.Game`, `BraveAdventurerScene`, `PapyrusBraveAdventurerScene`, `ClockworkKeepScene`, `DrawingFireScene`, `MrMuncherScene`) and `drawing_fire.players`. The test imports the tables from the helper. C5's guard exempts only `tests/replay/golden_replay_controls.py`. **C4 owns the move**: these tests are cross-member infrastructure, and C4 rewrites the file's other (c) rows. | none: no engine arc only it reaches |
| `tests/replay/test_golden_replays.py` | `test_every_golden_replay_pauses_resumes_and_ends_with_the_games_own_quit (per game)` | exempt via helper (controller) | The test stays in `tests/replay/test_golden_replays.py`, which stays guarded. The per-game tables move unchanged, with no mapping change, into a helper module of their own, `tests/replay/golden_replay_controls.py`. They are `GAMEPLAY_ACTION_MAPS`, `ENGINE_SCENE_CONTROLS`, `UNEXERCISED_CONTROLS`, `DRAWING_FIRE_CONTROLS` and the helpers that build them (`Control`, `InputKind`, `_key_control`, `_scancode_control`, `_drawing_fire_snapshot_control`, `_controls_from_action_maps`, `_paddleslap_action_maps`, `PAUSE_SCENE_CONTROLS`, `GAMES_WITHOUT_A_PAUSE`, `PAUSING_GAMES`, `NO_GAMEPAD_IN_THE_SESSION`, `QUITS_ONCE`), with their imports of the six scene classes (`paddleslap.Game`, `BraveAdventurerScene`, `PapyrusBraveAdventurerScene`, `ClockworkKeepScene`, `DrawingFireScene`, `MrMuncherScene`) and `drawing_fire.players`. The test imports the tables from the helper. C5's guard exempts only `tests/replay/golden_replay_controls.py`. **C4 owns the move**: these tests are cross-member infrastructure, and C4 rewrites the file's other (c) rows. | none: no engine arc only it reaches |
| `tests/replay/test_golden_replays.py` | `test_the_drawing_fire_golden_replay_holds_a_death_and_a_takeover` | (a) | drawing-fire: `src/games/drawing-fire/tests/test_drawing_fire_golden_replay.py`. It checks Drawing Fire's own golden for its own game events (`SOLDIER_KILLED_SUBTYPE`, `SEAT_CHANGED_SUBTYPE`, `SeatChange`). | none: no engine arc only it reaches |
| `tests/replay/test_instant_replay.py` | `TestAnExampleGame::test_paddleslaps_journal_plays_back_exactly` | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_instant_replay.py`. It runs the golden script of PaddleSlap's `INSTANT_REPLAY_SECONDS` through `record_trace('paddleslap')`. The engine's instant replay keeps the stand-in tests in this file (`InstantCountingScene`). | Shared, not alone: `ball.py` 820-821 and `input/action_map.py` `handle_event` (401) are also reached by (c) rows that stay |
| `tests/replay/test_playback_scope.py` | `TestPlaybackErrors::test_the_module_picks_one_of_two_loaded_scenes_named_alike` | (b) stand-in, in process | Stand-in scenes, in this process: two stand-in `Scene` subclasses, both named `Game`, at different logical modules: one stand-in module per class (`type('Game', (Scene,), {'__module__': ...})`), with each package added to `logical_names.MEMBER_LAYERS` by `mocker.patch.dict`, one under `games` and one under `demos`. Assert that `find_scene_class(name='Game', module=...)` and `find_scene_class(..., logical=...)` each resolve to their own class while both are loaded together. This keeps Review Focus 4's check (`demos.joystick_demo:Game` and `games.paddleslap:Game` both resolve while loaded together); it must not be dropped. Afterwards delete them and run `gc.collect()` (as `test_two_loaded_classes_of_that_name_are_still_refused` does). | none: no engine arc only it reaches |
| `tests/replay/test_rebaseline_across_logical_modules.py` | `TestThroughTheRealGame::test_a_plain_replay_refuses_and_names_the_remedy` | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. Must make explicit: a single scene (the rename rewrites only the header's `game` and each `scene_start`'s `scene`, so a second scene would keep its old name), and one console script. The stand-in source, written by the test, registers its package in a layer when it is imported, in the child process as in this one: `logical_names.MEMBER_LAYERS['<stand_in_package>'] = 'games'` (a plain mutable dict, `src/glitchygames/logical_names.py`). `CURRENT_NAME` is then layered, `games.<stand_in_package>...:<Scene>`, exactly as Mr. Muncher's `games.mr_muncher.game:MrMuncherScene` was, and `NAME_IN_ANOTHER_LAYER` is `apps.<stand_in_package>...:<Scene>`. This is the default. The fallback, only if registering at import fails, is a layerless current name (`<module>:<Scene>`); C3 then checks that the plain replay still refuses with `REBASELINE_REMEDY` and that the rebaseline still converts. (C3 owns this.) | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_rebaseline_across_logical_modules.py` | `TestThroughTheRealGame::test_a_rebaseline_converts_it_and_the_new_recording_replays_strictly` | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. Must make explicit: a single scene (the rename rewrites only the header's `game` and each `scene_start`'s `scene`, so a second scene would keep its old name), and one console script. The stand-in source, written by the test, registers its package in a layer when it is imported, in the child process as in this one: `logical_names.MEMBER_LAYERS['<stand_in_package>'] = 'games'` (a plain mutable dict, `src/glitchygames/logical_names.py`). `CURRENT_NAME` is then layered, `games.<stand_in_package>...:<Scene>`, exactly as Mr. Muncher's `games.mr_muncher.game:MrMuncherScene` was, and `NAME_IN_ANOTHER_LAYER` is `apps.<stand_in_package>...:<Scene>`. This is the default. The fallback, only if registering at import fails, is a layerless current name (`<module>:<Scene>`); C3 then checks that the plain replay still refuses with `REBASELINE_REMEDY` and that the rebaseline still converts. (C3 owns this.) | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_rebaseline_across_logical_modules.py` | `TestThroughTheRealGame::test_a_different_qualified_name_is_refused_and_writes_nothing` | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. Must make explicit: a single scene (the rename rewrites only the header's `game` and each `scene_start`'s `scene`, so a second scene would keep its old name), and one console script. The stand-in source, written by the test, registers its package in a layer when it is imported, in the child process as in this one: `logical_names.MEMBER_LAYERS['<stand_in_package>'] = 'games'` (a plain mutable dict, `src/glitchygames/logical_names.py`). `CURRENT_NAME` is then layered, `games.<stand_in_package>...:<Scene>`, exactly as Mr. Muncher's `games.mr_muncher.game:MrMuncherScene` was, and `NAME_IN_ANOTHER_LAYER` is `apps.<stand_in_package>...:<Scene>`. This is the default. The fallback, only if registering at import fails, is a layerless current name (`<module>:<Scene>`); C3 then checks that the plain replay still refuses with `REBASELINE_REMEDY` and that the rebaseline still converts. (C3 owns this.) | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_record_scripted_session.py` | `test_scripted_session_records_and_replays` | (b) stand-in game or distribution | Stand-in game, in this process: a stand-in scene registered for the test under a stand-in key in the tool's tables (`mocker.patch.dict` on `GAME_SCENES`, `GAME_CONSOLE_SCRIPTS`, `SCRIPT_BUILDERS`/`CONTROLS_TAIL_BUILDERS` as needed), replayed with `replay_through_engine` under the same key. Must make explicit: no polled input (the key is not in `POLLED_INPUT_GAMES`, so snapshots never show posted keys held); no sprite placements in the session; it reads key events, so external key events are recorded; deterministic, 120 frames (`RECORDED_FRAME_COUNT`) replay with `end_of_recording`. | Shared: `ball.py` 744, 820-821, with other rows that stay |
| `tests/replay/test_record_scripted_session.py` | `test_a_session_drops_events_left_queued_before_it` | (b) stand-in game or distribution | Stand-in game, in this process: a stand-in scene registered for the test under a stand-in key in the tool's tables (`mocker.patch.dict` on `GAME_SCENES`, `GAME_CONSOLE_SCRIPTS`, `SCRIPT_BUILDERS`/`CONTROLS_TAIL_BUILDERS` as needed), replayed with `replay_through_engine` under the same key. Must make explicit: no polled input (the key is not in `POLLED_INPUT_GAMES`, so snapshots never show posted keys held); no sprite placements in the session; it reads key events, so external key events are recorded; it never posts a `GAMEEVENT` of subtype 9999 (`STALE_EVENT_SUBTYPE`) itself. | Shared: `ball.py` 744, 820-821, with other rows that stay |
| `tests/replay/test_record_scripted_session.py` | `test_a_tail_whose_quit_does_not_quit_fails_the_recording` | (b) stand-in game or distribution | Stand-in game, in this process: a stand-in scene registered for the test under a stand-in key in the tool's tables (`mocker.patch.dict` on `GAME_SCENES`, `GAME_CONSOLE_SCRIPTS`, `SCRIPT_BUILDERS`/`CONTROLS_TAIL_BUILDERS` as needed), replayed with `replay_through_engine` under the same key. Must make explicit: no polled input (the key is not in `POLLED_INPUT_GAMES`, so snapshots never show posted keys held); no sprite placements in the session; it reads key events, so external key events are recorded; the tail's X key (`pygame.K_x`) is no control of the stand-in, so it never quits and `GameDidNotQuitError` is raised. | Shared: `ball.py` 744, 820-821, with other rows that stay |
| `tests/replay/test_recording_logical_names.py` | `test_every_logical_name_in_the_recording_resolves` (per committed recording) | (c) | It already discovers recordings (`workspace_members(...)` replay fixtures, `bundled_demo_paths()`) and imports members by `importlib.import_module` from the logical names. Keep that. | none: no engine arc only it reaches |
| `tests/replay/test_recording_logical_names.py` | `test_the_committed_recordings_are_all_checked` | (c) | Replace `>= 6` with an independent expected set. Every `games`-layer member holds at least one golden (5 games, 6 goldens). The bundled demos, compared by `(package, name)`, are `{('paddleslap', 'rally.jsonl.gz')}`. `COMMITTED_RECORDINGS` holds exactly the goldens plus the demos the workspace reader finds, and every member golden's and demo's header `game` resolves. | none: no engine arc only it reaches |
| `tests/replay/test_replay_plugin.py` | `test_game_entry_point_reads_the_console_script` | (b) stand-in game or distribution | The file's own `write_stand_in_distribution` (a dist-info with `console_scripts`) on `monkeypatch.syspath_prepend`, with `stand-in-game = stand_in_game:main`. Engine: `testing/replays.py` `game_entry_point`. | none: no engine arc only it reaches |
| `tests/replay/test_replay_plugin.py` | `test_matching_recording_passes` | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. Its game directory is named for the stand-in console script, not `paddleslap`. Must make explicit: replays without divergence (deterministic, seeded). | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_replay_plugin.py` | `test_a_recording_can_be_skipped_from_a_marker` | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. Its game directory is named for the stand-in console script, not `paddleslap`. Must make explicit: only a console script and one recording file; the item is skipped, no child runs. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_replay_plugin.py` | `test_other_files_are_not_collected` | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. Its game directory is named for the stand-in console script, not `paddleslap`. Must make explicit: one deterministic recording that replays clean; the stray copies are the same file. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_replay_plugin.py` | `test_a_bookmarked_copy_is_not_collected` | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. Its game directory is named for the stand-in console script, not `paddleslap`. Must make explicit: a recording with at least 2 frames (`bookmarks` names frame 1 or 2). | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_replay_plugin.py` | `test_tampered_recording_fails_with_the_report` | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. Its game directory is named for the stand-in console script, not `paddleslap`. Must make explicit: a sprite in every frame from frame 10 on (`TAMPERED_FRAME`), so moving the first sprite 1 px diverges there. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_replay_plugin.py` | `test_unusable_recording_fails_with_the_exit_code` | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. Its game directory is named for the stand-in console script, not `paddleslap`. Must make explicit: only the console script: the child refuses the garbage file (UNUSABLE_INPUT, 65). | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_replay_plugin.py` | `test_missing_recording_fails_as_unusable` | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. Its game directory is named for the stand-in console script, not `paddleslap`. Must make explicit: only the console script and a recording deleted after collection (MISSING_INPUT, 66). | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_replay_plugin.py` | `test_replay_recording_headless_returns_the_finished_replay` | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. Its game directory is named for the stand-in console script, not `paddleslap`. Must make explicit: a sprite on frame 10 (`TAMPERED_FRAME`); the child prints `Replay diverged at frame 10`. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_replay_plugin.py` | `test_rebaseline_recording_headless_writes_the_new_recording` | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. Its game directory is named for the stand-in console script, not `paddleslap`. Must make explicit: deterministic, so the rebaseline reports `no frames differ`. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_replay_plugin.py` | `TestPluginInProcess::test_a_bookmarked_copy_is_not_collected` | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. Its game directory is named for the stand-in console script, not `paddleslap`. Must make explicit: a recording with frames to bookmark; collection only. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_replay_plugin.py` | `TestPluginInProcess::test_a_failed_replay_fails_the_item_with_its_exit_code_and_output` | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. Its game directory is named for the stand-in console script, not `paddleslap`. Must make explicit: only its console script (the child is mocked; the test asserts `console_script` is the stand-in's). | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_replay_plugin.py` | `TestPluginInProcess::test_a_successful_replay_passes_the_item` | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. Its game directory is named for the stand-in console script, not `paddleslap`. Must make explicit: only its console script (the child is mocked). | none: no engine arc only it reaches (child processes are not measured) |
| `tests/replay/test_replay_plugin.py` | `test_bundled_demo_paths_pairs_each_demo_with_its_games_console_script` | (b) stand-in game or distribution | `write_stand_in_package` (`tests/test_bundled_demo_discovery.py`) plus `write_stand_in_distribution`, whose console-script entry point is in the stand-in package. Engine: `bundled_demo_paths`. | none: no engine arc only it reaches |
| `tests/scenes/builtin_scenes/test_game_over.py` | `test_game_over_condition` | (a) | paddleslap: `test_paddleslap_game_over.py`, next to the row above (it is nearly the same test). This is the file's only test, so the file goes. | none: no engine arc only it reaches |
| `tests/scenes/builtin_scenes/test_pause_screen.py` | `TestPauseScreen::test_pause_screen_triggered_on_spacebar` | (b) stand-in, in process | A stand-in `Scene` that calls `self.pause()` (engine `Scene.pause`, `scene.py`) on the release of SPACE. PaddleSlap binds `pause` to `KSCAN_SPACE`. The stand-in draws something, so the overlay and display comparison mean something. This file's `_engine_for` and `TestPauseSceneBehaviour` already use stand-ins of this kind. Engine: `PauseScene`, `SceneManager._setup_new_scene`. | none: no engine arc only it reaches |
| `tests/scenes/builtin_scenes/test_pause_screen.py` | `TestPauseScreen::test_pause_screen_resume_on_spacebar` | (b) stand-in, in process | A stand-in `Scene` that calls `self.pause()` (engine `Scene.pause`, `scene.py`) on the release of SPACE. PaddleSlap binds `pause` to `KSCAN_SPACE`. The stand-in draws something, so the overlay and display comparison mean something. This file's `_engine_for` and `TestPauseSceneBehaviour` already use stand-ins of this kind. Engine: `PauseScene`, `SceneManager._setup_new_scene`. | none: no engine arc only it reaches |
| `tests/scenes/builtin_scenes/test_pause_screen.py` | `TestPauseScreen::test_pause_screen_gets_game_engine_reference` | (b) stand-in, in process | A stand-in `Scene` that calls `self.pause()` (engine `Scene.pause`, `scene.py`) on the release of SPACE. PaddleSlap binds `pause` to `KSCAN_SPACE`. The stand-in draws something, so the overlay and display comparison mean something. This file's `_engine_for` and `TestPauseSceneBehaviour` already use stand-ins of this kind. Engine: `PauseScene`, `SceneManager._setup_new_scene`. | none: no engine arc only it reaches |
| `tests/scenes/builtin_scenes/test_pause_screen.py` | `TestPauseScreenIntegration::test_pause_resume_cycle` | (b) stand-in, in process | A stand-in `Scene` that calls `self.pause()` (engine `Scene.pause`, `scene.py`) on the release of SPACE. PaddleSlap binds `pause` to `KSCAN_SPACE`. The stand-in draws something, so the overlay and display comparison mean something. This file's `_engine_for` and `TestPauseSceneBehaviour` already use stand-ins of this kind. Engine: `PauseScene`, `SceneManager._setup_new_scene`. | none: no engine arc only it reaches |
| `tests/test_browser_touch_controls.py` | `test_every_button_presses_a_key_its_game_reads` (per game) | (a) | Per member: each game with a browser build and a touch layout checks that its own buttons press keys its own scenes bind (`GAMES` names only Brave Adventurer's title scene, so a root lookup would lose the per-scene checks). New files: `test_paddleslap_touch_controls.py`, `test_brave_adventurer_touch_controls.py` (title screen, Classic, Papyrus), `test_clockwork_keep_touch_controls.py`, `test_mr_muncher_touch_controls.py`. `SCANCODE_BY_CODE`, `SHARED_SCREEN_CODES`, `bound_scancodes` and `layout_buttons` move to a shared `tests/` helper. The root keeps the generic check (`test_every_game_has_touch_controls_or_a_reason_not`, not a borrow), compared with an independent set: the `TOUCH_LAYOUTS` keys equal the `games`-layer members' distributions minus `drawing-fire`. | none: no engine arc only it reaches |
| `tests/test_browser_touch_controls.py` | `test_the_brave_adventurer_title_screen_takes_the_games_buttons` | (a) | brave-adventurer: `src/games/brave-adventurer/tests/test_brave_adventurer_touch_controls.py`, beside its per-scene check from the row above. It imports `scripts.build_browser_bundle` (member tests already import `scripts`/`tests` helpers). | none: no engine arc only it reaches |
| `tests/test_build_browser_bundle.py` | `TestGeneratedFiles::test_every_game_module_has_its_scene_class` | (c) | It imports each `GAMES` module by string (`__import__`); keep that. Independent expected set, by distribution: the `GAMES` keys equal the distributions of the `games`-layer members plus `bitmappy` (5 games plus Bitmappy; the `demos` layer has no browser build, decision 6). | none: no engine arc only it reaches |
| `tests/test_bundled_demo_discovery.py` | `test_paddleslaps_demo_is_found_with_its_console_script_and_install_name` | (b) stand-in game or distribution | `write_stand_in_package` plus `write_stand_in_distribution` (move it from `tests/replay/test_replay_plugin.py` into a shared `tests/` helper). Engine: `bundled_demos.bundled_demos` (console script, path, `install_name`). The real demo is checked by the (c) row in `test_bundled_demos.py`. | none: no engine arc only it reaches |
| `tests/test_bundled_demo_discovery.py` | `test_a_bundled_demo_is_a_frozen_record` | (b) stand-in, in process | Build a `BundledDemo` directly from stand-in values (no scene needed). Engine: the frozen dataclass. | none: no engine arc only it reaches |
| `tests/test_bundled_demo_discovery.py` | `test_package_demo_paths_lists_only_recordings_and_leaves_out_bookmarked_copies` | (b) stand-in, in process | Write a small stand-in recording in `tmp_path` with `glitchygames.tracing.write_trace`, with at least 3 frames because `bookmarks=[2]`. It replaces `PADDLESLAP_DEMO_PATH` as the source of `write_bookmarked_copy`. Engine: `package_demo_paths`, `tracing.is_bookmarked_copy`. | none: no engine arc only it reaches |
| `tests/test_bundled_demo_discovery.py` | `test_every_member_package_is_searched_by_default` | (c) | It already searches every member by default (`MEMBER_LAYERS`). Independent expected set, by `(package, name)` and not by a path re-derived from the package directories (nox installs non-editable copies): `{(demo.package, demo.path.name) for demo in bundled_demos()} == {('paddleslap', 'rally.jsonl.gz')}`, which is non-empty. Keep the `demos/` parent and sorted-path checks. | none: no engine arc only it reaches |
| `tests/test_bundled_demo_discovery.py` | `test_a_console_script_is_found_by_the_module_of_its_entry_point` | (b) stand-in game or distribution | `write_stand_in_distribution` on `sys.path`, whose entry point is in the stand-in module. Engine: `console_script_in_module`. | none: no engine arc only it reaches |
| `tests/test_measure_staged_replays.py` | `test_a_code_commit_is_measured_and_its_rows_staged_with_it` | (b) stand-in game or distribution | Stand-in distributions, no child (the measurement is mocked by `stand_in_measurement`): `write_stand_in_distribution` with console scripts named for the folders (`RECORDING_NAMES` becomes two stand-in names, not `paddleslap`/`clockwork-keep`), on `sys.path`, and explicit `demo_packages`. Must make explicit: the hook itself calls `replay_metrics.metric_recordings(project_root=repository)` with the default (every member's) demo packages (`scripts/measure_staged_replays.py` line 104), so `MEASURED_RECORDING_COUNT` (`len(bundled_demos())`) counts the real members' demos. C3 passes `demo_packages=()` there too, or patches the default, so the count is 2. | none: no engine arc only it reaches |
| `tests/test_measure_staged_replays.py` | `test_history_rows_the_measurement_wrote_are_staged_with_the_commit` | (b) stand-in game or distribution | Stand-in distributions, no child (the measurement is mocked by `stand_in_measurement`): `write_stand_in_distribution` with console scripts named for the folders (`RECORDING_NAMES` becomes two stand-in names, not `paddleslap`/`clockwork-keep`), on `sys.path`, and explicit `demo_packages`. Must make explicit: the hook itself calls `replay_metrics.metric_recordings(project_root=repository)` with the default (every member's) demo packages (`scripts/measure_staged_replays.py` line 104), so `MEASURED_RECORDING_COUNT` (`len(bundled_demos())`) counts the real members' demos. C3 passes `demo_packages=()` there too, or patches the default, so the count is 2. | none: no engine arc only it reaches |
| `tests/test_measure_staged_replays.py` | `test_an_unrelated_untracked_file_in_the_rows_directory_is_not_staged` | (b) stand-in game or distribution | Stand-in distributions, no child (the measurement is mocked by `stand_in_measurement`): `write_stand_in_distribution` with console scripts named for the folders (`RECORDING_NAMES` becomes two stand-in names, not `paddleslap`/`clockwork-keep`), on `sys.path`, and explicit `demo_packages`. Must make explicit: the hook itself calls `replay_metrics.metric_recordings(project_root=repository)` with the default (every member's) demo packages (`scripts/measure_staged_replays.py` line 104), so `MEASURED_RECORDING_COUNT` (`len(bundled_demos())`) counts the real members' demos. C3 passes `demo_packages=()` there too, or patches the default, so the count is 2. | none: no engine arc only it reaches |
| `tests/test_measure_staged_replays.py` | `test_code_that_arrived_without_the_hook_is_measured_by_the_next_commit` | (b) stand-in game or distribution | Stand-in distributions, no child (the measurement is mocked by `stand_in_measurement`): `write_stand_in_distribution` with console scripts named for the folders (`RECORDING_NAMES` becomes two stand-in names, not `paddleslap`/`clockwork-keep`), on `sys.path`, and explicit `demo_packages`. Must make explicit: the hook itself calls `replay_metrics.metric_recordings(project_root=repository)` with the default (every member's) demo packages (`scripts/measure_staged_replays.py` line 104), so `MEASURED_RECORDING_COUNT` (`len(bundled_demos())`) counts the real members' demos. C3 passes `demo_packages=()` there too, or patches the default, so the count is 2. | none: no engine arc only it reaches |
| `tests/test_measure_staged_replays.py` | `test_a_measured_code_tree_is_not_measured_again` | (b) stand-in game or distribution | Stand-in distributions, no child (the measurement is mocked by `stand_in_measurement`): `write_stand_in_distribution` with console scripts named for the folders (`RECORDING_NAMES` becomes two stand-in names, not `paddleslap`/`clockwork-keep`), on `sys.path`, and explicit `demo_packages`. Must make explicit: the hook itself calls `replay_metrics.metric_recordings(project_root=repository)` with the default (every member's) demo packages (`scripts/measure_staged_replays.py` line 104), so `MEASURED_RECORDING_COUNT` (`len(bundled_demos())`) counts the real members' demos. C3 passes `demo_packages=()` there too, or patches the default, so the count is 2. | none: no engine arc only it reaches |
| `tests/test_measure_staged_replays.py` | `test_a_retry_measures_the_recordings_a_failed_attempt_left_and_stages_everything` | (b) stand-in game or distribution | Stand-in distributions, no child (the measurement is mocked by `stand_in_measurement`): `write_stand_in_distribution` with console scripts named for the folders (`RECORDING_NAMES` becomes two stand-in names, not `paddleslap`/`clockwork-keep`), on `sys.path`, and explicit `demo_packages`. Must make explicit: the hook itself calls `replay_metrics.metric_recordings(project_root=repository)` with the default (every member's) demo packages (`scripts/measure_staged_replays.py` line 104), so `MEASURED_RECORDING_COUNT` (`len(bundled_demos())`) counts the real members' demos. C3 passes `demo_packages=()` there too, or patches the default, so the count is 2. | none: no engine arc only it reaches |
| `tests/test_measure_staged_replays.py` | `test_a_retry_where_every_recording_is_measured_does_not_measure_again` | (b) stand-in game or distribution | Stand-in distributions, no child (the measurement is mocked by `stand_in_measurement`): `write_stand_in_distribution` with console scripts named for the folders (`RECORDING_NAMES` becomes two stand-in names, not `paddleslap`/`clockwork-keep`), on `sys.path`, and explicit `demo_packages`. Must make explicit: the hook itself calls `replay_metrics.metric_recordings(project_root=repository)` with the default (every member's) demo packages (`scripts/measure_staged_replays.py` line 104), so `MEASURED_RECORDING_COUNT` (`len(bundled_demos())`) counts the real members' demos. C3 passes `demo_packages=()` there too, or patches the default, so the count is 2. | none: no engine arc only it reaches |
| `tests/test_measure_staged_replays.py` | `test_untracked_files_under_the_measured_paths_refuse_the_commit` | (b) stand-in game or distribution | Stand-in distributions, no child (the measurement is mocked by `stand_in_measurement`): `write_stand_in_distribution` with console scripts named for the folders (`RECORDING_NAMES` becomes two stand-in names, not `paddleslap`/`clockwork-keep`), on `sys.path`, and explicit `demo_packages`. Must make explicit: the hook itself calls `replay_metrics.metric_recordings(project_root=repository)` with the default (every member's) demo packages (`scripts/measure_staged_replays.py` line 104), so `MEASURED_RECORDING_COUNT` (`len(bundled_demos())`) counts the real members' demos. C3 passes `demo_packages=()` there too, or patches the default, so the count is 2. | none: no engine arc only it reaches |
| `tests/test_measure_staged_replays.py` | `test_an_untracked_member_test_does_not_refuse_the_commit` | (b) stand-in game or distribution | Stand-in distributions, no child (the measurement is mocked by `stand_in_measurement`): `write_stand_in_distribution` with console scripts named for the folders (`RECORDING_NAMES` becomes two stand-in names, not `paddleslap`/`clockwork-keep`), on `sys.path`, and explicit `demo_packages`. Must make explicit: the hook itself calls `replay_metrics.metric_recordings(project_root=repository)` with the default (every member's) demo packages (`scripts/measure_staged_replays.py` line 104), so `MEASURED_RECORDING_COUNT` (`len(bundled_demos())`) counts the real members' demos. C3 passes `demo_packages=()` there too, or patches the default, so the count is 2. | none: no engine arc only it reaches |
| `tests/test_measure_staged_replays.py` | `test_an_untracked_member_recording_refuses_the_commit` | (b) stand-in game or distribution | Stand-in distributions, no child (the measurement is mocked by `stand_in_measurement`): `write_stand_in_distribution` with console scripts named for the folders (`RECORDING_NAMES` becomes two stand-in names, not `paddleslap`/`clockwork-keep`), on `sys.path`, and explicit `demo_packages`. Must make explicit: the hook itself calls `replay_metrics.metric_recordings(project_root=repository)` with the default (every member's) demo packages (`scripts/measure_staged_replays.py` line 104), so `MEASURED_RECORDING_COUNT` (`len(bundled_demos())`) counts the real members' demos. C3 passes `demo_packages=()` there too, or patches the default, so the count is 2. | none: no engine arc only it reaches |
| `tests/test_measure_staged_replays.py` | `test_a_partial_commit_that_needs_measuring_is_refused` | (b) stand-in game or distribution | Stand-in distributions, no child (the measurement is mocked by `stand_in_measurement`): `write_stand_in_distribution` with console scripts named for the folders (`RECORDING_NAMES` becomes two stand-in names, not `paddleslap`/`clockwork-keep`), on `sys.path`, and explicit `demo_packages`. Must make explicit: the hook itself calls `replay_metrics.metric_recordings(project_root=repository)` with the default (every member's) demo packages (`scripts/measure_staged_replays.py` line 104), so `MEASURED_RECORDING_COUNT` (`len(bundled_demos())`) counts the real members' demos. C3 passes `demo_packages=()` there too, or patches the default, so the count is 2. | none: no engine arc only it reaches |
| `tests/test_recording_report.py` | `test_a_real_recording_reports_every_run_and_no_behaviour_change` (part 1 of a split) | (a) | paddleslap: `src/games/paddleslap/tests/test_paddleslap_recording_history.py`. Only PaddleSlap's own history: its golden's frame-0 `scene_start` names `scene_module` `glitchygames.examples.paddleslap` and a rebaseline names `paddleslap`, both under `games.paddleslap:Game`; and the behavior change "in frame 0 (scene Game), 1 span, 1 frame" between the golden's newest run and the first rebaseline. | none: no engine arc only it reaches |
| `tests/test_recording_report.py` | `test_a_real_recording_reports_every_run_and_no_behaviour_change` (part 2 of a split) | (b) stand-in game or distribution | Stand-in game: a tiny game source written to `tmp_path` (the `UNSEEDED_GAME_SOURCE` pattern, `tests/world/test_gameplay_replay.py`, but seeded and deterministic), installed with `write_stand_in_distribution` (a dist-info with its console script) on a directory the child also gets on `PYTHONPATH`, and its recording made in `tmp_path` by a child `--record-trace` run. The root keeps an end-to-end test of `scripts/recording_report.py` on a stand-in recording rebaselined twice through the stand-in's console script. Must make explicit: a deterministic game, so the two new runs did the same work (`no behaviour change` between them); the recording's own earlier runs (one live, paced run), so `paced live run` and `frame time p50` appear; and no frame-0 history change, unlike PaddleSlap's. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestTheRecordings::test_this_projects_recordings` | (c) | Independent expected set: every `games`-layer member holds at least one golden (5 games, 6 goldens), and the demos are compared by `(package, name)` (`demo.package`, `path.name`), not by path, because nox installs non-editable copies. `metric_recordings(...).replayable` holds exactly those, each with a console script. | none: no engine arc only it reaches |
| `tests/test_replay_metrics.py` | `TestTheRecordings::test_each_game_of_a_member_with_several_is_measured` (per golden) | (c) | Parametrize over the members holding more than one golden, read from the workspace. Independent expected set: Brave Adventurer is the one such member today, with `golden-classic` and `golden-papyrus` (the member's two game packages). | none: no engine arc only it reaches |
| `tests/test_replay_metrics.py` | `TestTheRecordings::test_a_bookmarked_copy_beside_a_members_golden_is_not_measured` | (b) stand-in game or distribution | Stand-in distribution, no child: a stand-in member in the `tmp_path` project with `write_stand_in_distribution` for its console script, and a stand-in recording with at least 2 frames (`bookmarks=[1]`). Must make explicit: the golden is named `golden-<game>` so the `golden*` glob takes it and the bookmarked copy is skipped. | none: no engine arc only it reaches |
| `tests/test_replay_metrics.py` | `TestTheRecordings::test_the_root_layout_finds_each_games_golden_and_skips_a_bookmarked_copy` | (b) stand-in game or distribution | Stand-in distribution, no child: the root-layout folder is named for a stand-in console script from `write_stand_in_distribution`; a stand-in recording with at least 2 frames for the bookmarked copy. | none: no engine arc only it reaches |
| `tests/test_replay_metrics.py` | `TestTheRecordings::test_a_demo_no_console_script_replays_is_reported_not_raised` | (b) stand-in game or distribution | `write_stand_in_package` plus `write_stand_in_distribution` (a demo package that has a console script) in place of `paddleslap`/`PADDLESLAP_DEMO_PATH`. Engine/tool: `metric_recordings` with `demo_packages`. | none: no engine arc only it reaches |
| `tests/test_replay_metrics.py` | `TestTheRecordings::test_the_measured_demos_are_exactly_the_engines_bundled_demos` | (c) | It already compares two discoveries. Compare by `(package, name)`, not by path (nox installs non-editable copies), and add an independent expected set: PaddleSlap's `rally.jsonl.gz` is the one bundled demo today (`(paddleslap, rally.jsonl.gz)`), and the set is non-empty. | none: no engine arc only it reaches |
| `tests/test_replay_metrics.py` | `TestMeasuringIntoRowFiles::test_a_measurement_writes_row_files_naming_the_code_tree` | (b) stand-in game or distribution | Stand-in game: `copied_golden` becomes a stand-in member in the `tmp_path` project (`src/games/<stand-in>/...` with its pyproject), its recording made by the stand-in game, its distribution installed with `write_stand_in_distribution` on a path the child gets. Must make explicit: the child rebaseline exits SUCCESS (deterministic); the rows name the stand-in's ledger path and console script. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuringIntoRowFiles::test_a_missing_origin_main_is_said_once` | (b) stand-in game or distribution | Stand-in game: `copied_golden` becomes a stand-in member in the `tmp_path` project (`src/games/<stand-in>/...` with its pyproject), its recording made by the stand-in game, its distribution installed with `write_stand_in_distribution` on a path the child gets. Must make explicit: the child rebaseline exits SUCCESS (deterministic); the rows name the stand-in's ledger path and console script. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuringIntoRowFiles::test_the_same_code_tree_is_measured_once_per_machine` | (b) stand-in game or distribution | Stand-in game: `copied_golden` becomes a stand-in member in the `tmp_path` project (`src/games/<stand-in>/...` with its pyproject), its recording made by the stand-in game, its distribution installed with `write_stand_in_distribution` on a path the child gets. Must make explicit: the child rebaseline exits SUCCESS (deterministic); the rows name the stand-in's ledger path and console script. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuringIntoRowFiles::test_the_summary_names_the_rows_directory` | (b) stand-in game or distribution | Stand-in game: `copied_golden` becomes a stand-in member in the `tmp_path` project (`src/games/<stand-in>/...` with its pyproject), its recording made by the stand-in game, its distribution installed with `write_stand_in_distribution` on a path the child gets. Must make explicit: the child rebaseline exits SUCCESS (deterministic); the rows name the stand-in's ledger path and console script. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestHistoryRunsInThePendingFile::test_a_history_run_on_a_commit_not_on_origin_main_is_not_appended` | (b) stand-in game or distribution | Stand-in game: `copied_golden` becomes a stand-in member in the `tmp_path` project (`src/games/<stand-in>/...` with its pyproject), its recording made by the stand-in game, its distribution installed with `write_stand_in_distribution` on a path the child gets. Must make explicit: the recording holds at least one history run with a commit, so a landed history run is appended (`LedgerOrigin.RECORDING`). | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestHistoryRunsInThePendingFile::test_a_history_run_on_a_commit_on_origin_main_is_appended` | (b) stand-in game or distribution | Stand-in game: `copied_golden` becomes a stand-in member in the `tmp_path` project (`src/games/<stand-in>/...` with its pyproject), its recording made by the stand-in game, its distribution installed with `write_stand_in_distribution` on a path the child gets. Must make explicit: the recording holds at least one history run with a commit, so a landed history run is appended (`LedgerOrigin.RECORDING`). | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuring::test_a_measurement_appends_rows_and_a_second_one_skips` | (b) stand-in game or distribution | Stand-in game: `copied_golden` becomes a stand-in member in the `tmp_path` project (`src/games/<stand-in>/...` with its pyproject), its recording made by the stand-in game, its distribution installed with `write_stand_in_distribution` on a path the child gets. Must make explicit: the counts the asserts read from the golden (`golden_runs_with_a_commit`, its runs, its recording path) are read from the stand-in recording; one older live run; for the failure rows, a second stand-in recording that fails. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuring::test_a_published_measurement_counts_as_measured` | (b) stand-in game or distribution | Stand-in game: `copied_golden` becomes a stand-in member in the `tmp_path` project (`src/games/<stand-in>/...` with its pyproject), its recording made by the stand-in game, its distribution installed with `write_stand_in_distribution` on a path the child gets. Must make explicit: the counts the asserts read from the golden (`golden_runs_with_a_commit`, its runs, its recording path) are read from the stand-in recording; one older live run; for the failure rows, a second stand-in recording that fails. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuring::test_uncommitted_changes_are_refused_unless_allowed` | (b) stand-in game or distribution | Stand-in game: `copied_golden` becomes a stand-in member in the `tmp_path` project (`src/games/<stand-in>/...` with its pyproject), its recording made by the stand-in game, its distribution installed with `write_stand_in_distribution` on a path the child gets. Must make explicit: the counts the asserts read from the golden (`golden_runs_with_a_commit`, its runs, its recording path) are read from the stand-in recording; one older live run; for the failure rows, a second stand-in recording that fails. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuring::test_failures_are_reported_and_measured_rows_kept` | (b) stand-in game or distribution | Stand-in game: `copied_golden` becomes a stand-in member in the `tmp_path` project (`src/games/<stand-in>/...` with its pyproject), its recording made by the stand-in game, its distribution installed with `write_stand_in_distribution` on a path the child gets. Must make explicit: the counts the asserts read from the golden (`golden_runs_with_a_commit`, its runs, its recording path) are read from the stand-in recording; one older live run; for the failure rows, a second stand-in recording that fails. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuring::test_an_unreplayable_recording_is_one_line_and_the_others_are_measured` | (b) stand-in game or distribution | Stand-in game: `copied_golden` becomes a stand-in member in the `tmp_path` project (`src/games/<stand-in>/...` with its pyproject), its recording made by the stand-in game, its distribution installed with `write_stand_in_distribution` on a path the child gets. Must make explicit: the counts the asserts read from the golden (`golden_runs_with_a_commit`, its runs, its recording path) are read from the stand-in recording; one older live run; for the failure rows, a second stand-in recording that fails. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestMeasuring::test_a_replay_of_another_commit_is_a_failure` | (b) stand-in game or distribution | Stand-in game: `copied_golden` becomes a stand-in member in the `tmp_path` project (`src/games/<stand-in>/...` with its pyproject), its recording made by the stand-in game, its distribution installed with `write_stand_in_distribution` on a path the child gets. Must make explicit: the counts the asserts read from the golden (`golden_runs_with_a_commit`, its runs, its recording path) are read from the stand-in recording; one older live run; for the failure rows, a second stand-in recording that fails. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestTheCommandLine::test_measure_one_recording_then_clear` | (b) stand-in game or distribution | Stand-in game: a stand-in package with a `demos/rally.jsonl.gz` made by the stand-in game (`write_stand_in_package` plus `write_stand_in_distribution`, on the import path and the child's `PYTHONPATH`), measured with `--only '<stand-in>/demos'`. Must make explicit: the command line's demo lookup must see the stand-in package (`metric_recordings(demo_packages=...)` takes members by default), so C3 passes it explicitly or patches the default; the row's ledger name is the stand-in demo's. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/test_replay_metrics.py` | `TestTheCommandLine::test_the_hooks_command_line_writes_row_files_naming_the_tree` | (b) stand-in game or distribution | Stand-in game: a stand-in package with a `demos/rally.jsonl.gz` made by the stand-in game (`write_stand_in_package` plus `write_stand_in_distribution`, on the import path and the child's `PYTHONPATH`), measured with `--only '<stand-in>/demos'`. Must make explicit: the command line's demo lookup must see the stand-in package (`metric_recordings(demo_packages=...)` takes members by default), so C3 passes it explicitly or patches the default; the row's ledger name is the stand-in demo's. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/world/test_frame_integration.py` | `TestPaddleSlapInTheFrame::test_paddle_hit_and_spawned_ball_are_drawn_at_their_world_positions` | (b) stand-in, in process | A stand-in world scene, run under this file's `running_scene`/`step` (stand-ins such as `CameraFreeScene` are already here). In its `dt_tick` it reverses one world sprite's speed and spawns a second world sprite. Reproduce: a ball 1 px right of a paddle's right edge, at speed x -300.0, y 0.0, giving two balls after one spawn (`PADDLESLAP_BALLS_AFTER_ONE_SPAWN = 2`). Assert both are drawn at `snapped_world_position` in the same frame, and the new one never at (0, 0). | none: no engine arc only it reaches |
| `tests/world/test_gameplay_recording.py` | `TestRecordingThroughTheEngine::test_saves_opened_before_recording_are_in_the_header` | (b) stand-in, in process | A stand-in scene that opens its save store in `__init__` (as PaddleSlap's `self.saves` does), recorded through the golden-trace engine (`GoldenTraceEngine`, `command_line`, `GoldenTraceEngine.start_trace_recording`) because `record_trace` takes only `GAME_SCENES` keys. The header's `SAVES_HEADER_FIELD` is keyed by the stand-in's app name, not `'paddleslap'`. | none: no engine arc only it reaches |
| `tests/world/test_gameplay_recording.py` | `test_recording_matches_the_golden_harness_frames` | (b) stand-in, in process | The stand-in departure/arrival session (`record_session`/`DepartureRecordedScene` in `tests/world/test_gameplay_replay.py`), or a stand-in like it. It needs a transition ride, a pause through `PauseScene`, key taps on known frames, and a fixed `FRAME_SECONDS` dt. It compares the engine's recording with the harness's own frames. Clockwork Keep supplied 900 frames, an elevator ride, a pause, K_UP before frame 10 and K_RIGHT before frame 70. | RISK: the only root test reaching `scenes/scene.py` `SceneManager._process_transition_events` (2632, the drain loop running more than once). The stand-in must queue at least 2 events in one transition frame. It also shares `transitions/elevator.py` `_draw_shaft_walls` (208-209), `animation/state_machine.py` `_switch_to` (342/346), `audio/recipes.py` `render` (116-117) and `camera.py` `update_scroll` (144) with golden-trace rows (c), which stay |
| `tests/world/test_gameplay_replay.py` | `TestRoundTrip::test_golden_script_recording_replays_without_divergence` (per `GAME_SCENES` key) | (c) | It is parametrized over the tool's `GAME_SCENES` keys. Map each key to its logical name explicitly, with `logical_name(scene_class=GAME_SCENES[key])`. Independent expected set: those logical names equal the `game` of every golden the workspace's members hold (every `games`-layer member holds at least one: 5 games, 6 goldens), and the set is non-empty. | Shared: `audio/synth.py` `concatenate` (437) and `sprites/animated.py` `update_nested_sprites` (2663), with `test_game_matches_golden_trace` (c); both stay |
| `tests/world/test_gameplay_replay.py` | `TestRoundTrip::test_golden_harness_stopped_early_reports_a_length_divergence` | (b) stand-in, in process | This file's `record_session`/`replay_session` stand-in, with a frame limit like `replay_golden_recording(frame_limit=...)`: 30 frames recorded, 10 replayed (`EARLY_STOP_RECORDED_FRAMES`/`EARLY_STOP_FRAME_LIMIT`). Engine: the replay's `LENGTH_DIVERGENCE`. | none: no engine arc only it reaches |
| `tests/world/test_gameplay_replay.py` | `TestRecordedDisplaySize::test_a_recording_on_a_window_of_another_size_replays_at_that_size` | (b) stand-in, in process | A stand-in scene that places a sprite from the display height (as PaddleSlap places its paddles), recorded asking for 800x480 on a window `window_manager_choosing_size` makes 800x600 (`WINDOW_MANAGER_SIZE`), for `DISPLAY_SIZE_FRAME_COUNT` (10) frames, then replayed. `record_session` and `window_manager_choosing_size` already exist here. | none: no engine arc only it reaches |
| `tests/world/test_gameplay_replay.py` | `TestAuditOption::test_a_golden_recording_passes_the_real_audit` | (b) stand-in game or distribution | A seeded stand-in game source, written to `tmp_path`, recorded and then replayed with `--audit` as children. `test_unseeded_randomness_makes_the_real_audit_fail` already does this with `UNSEEDED_GAME_SOURCE`. This replaces `python -m paddleslap` with PaddleSlap's golden. | none: no engine arc only it reaches (child processes are not measured) |
| `tests/world/test_golden_traces.py` | `test_expected_differences_cover_every_game` | (c) | Stays in the engine's tests. Independent, non-empty expected set: the baselines in `tests/world/golden/` (one file per game, frozen since the world-space change: `clockwork_keep`, `brave_adventurer`, `brave_adventurer_papyrus`, `paddleslap`) equal `GOLDEN_TRACE_GAMES` and the `EXPECTED_DIFFERENCES` keys, and are non-empty. It imports no member itself. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `test_game_matches_golden_trace` (per golden-trace game) | (c) | Stays in the engine's tests and still runs each game by key through the harness. Its expected set is the row above's, asserted (the baselines in `tests/world/golden/` vs `GOLDEN_TRACE_GAMES`, non-empty). The member imports its `EXPECTED_DIFFERENCES` rule helpers need fall under the exemption on the `TestWorldRules` rows; the test itself adds none. | It stays and runs members: see the future-work note below the table |
| `tests/world/test_golden_traces.py` | `test_same_random_seed_gives_identical_paddleslap_traces` | (b) stand-in, in process | Stand-in scene, in this process. It is outside the exemption, which covers only the per-game rules. The scene draws from the engine's seeded random streams (`glitchygames.randomness`). It runs twice under the golden-trace engine with `--random-seed` 123 and once with 124 (`SEEDED_TRACE_SEED`), each run `SEEDED_TRACE_FRAME_COUNT` (120) frames. Must make explicit: the scene draws random values that change its sprites in the first 120 frames, so that a different seed gives a different trace. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_settling_finds_one_old_camera_for_the_whole_frame` | exempt by name (user) | Stays as it is. Only the per-game world rules' imports of member internals are exempt, by name, in this file: `from brave_adventurer import constants`; `from brave_adventurer.drawing import draw_player, draw_scarab`; `from brave_adventurer.player import Player`; `from brave_adventurer_core import constants`; `from brave_adventurer_papyrus.player import PapyrusPlayer`; `from brave_adventurer_papyrus.sprite_utils import apply_transparency_and_scale`; `from clockwork_keep.constants import PLAYER_HEIGHT, PLAYER_WIDTH`; `from clockwork_keep.drawing import draw_tinker`; `from clockwork_keep.player import Tinker`. They serve `TestWorldRules`, the `EXPECTED_DIFFERENCES` rule helpers (`tinker_feet_margin_pixels`, `adventurer_feet_margin_pixels`, `scarab_feet_margin_pixels`, `adventurer_falling_pose_shift_pixels`, `papyrus_running_and_falling_poses`, and the rules built on them) and the `ADVENTURER_OLD_FALL_POSES`/`PAPYRUS_OLD_FALL_POSES` constants. C5's guard exempts exactly these imported modules and names in `tests/world/test_golden_traces.py`, not the whole file: any other member import there fails the guard. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_settling_rejects_a_tinker_no_old_position_explains` | exempt by name (user) | Stays as it is. Only the per-game world rules' imports of member internals are exempt, by name, in this file: `from brave_adventurer import constants`; `from brave_adventurer.drawing import draw_player, draw_scarab`; `from brave_adventurer.player import Player`; `from brave_adventurer_core import constants`; `from brave_adventurer_papyrus.player import PapyrusPlayer`; `from brave_adventurer_papyrus.sprite_utils import apply_transparency_and_scale`; `from clockwork_keep.constants import PLAYER_HEIGHT, PLAYER_WIDTH`; `from clockwork_keep.drawing import draw_tinker`; `from clockwork_keep.player import Tinker`. They serve `TestWorldRules`, the `EXPECTED_DIFFERENCES` rule helpers (`tinker_feet_margin_pixels`, `adventurer_feet_margin_pixels`, `scarab_feet_margin_pixels`, `adventurer_falling_pose_shift_pixels`, `papyrus_running_and_falling_poses`, and the rules built on them) and the `ADVENTURER_OLD_FALL_POSES`/`PAPYRUS_OLD_FALL_POSES` constants. C5's guard exempts exactly these imported modules and names in `tests/world/test_golden_traces.py`, not the whole file: any other member import there fails the guard. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_settling_rejects_sprites_no_single_old_camera_explains` | exempt by name (user) | Stays as it is. Only the per-game world rules' imports of member internals are exempt, by name, in this file: `from brave_adventurer import constants`; `from brave_adventurer.drawing import draw_player, draw_scarab`; `from brave_adventurer.player import Player`; `from brave_adventurer_core import constants`; `from brave_adventurer_papyrus.player import PapyrusPlayer`; `from brave_adventurer_papyrus.sprite_utils import apply_transparency_and_scale`; `from clockwork_keep.constants import PLAYER_HEIGHT, PLAYER_WIDTH`; `from clockwork_keep.drawing import draw_tinker`; `from clockwork_keep.player import Tinker`. They serve `TestWorldRules`, the `EXPECTED_DIFFERENCES` rule helpers (`tinker_feet_margin_pixels`, `adventurer_feet_margin_pixels`, `scarab_feet_margin_pixels`, `adventurer_falling_pose_shift_pixels`, `papyrus_running_and_falling_poses`, and the rules built on them) and the `ADVENTURER_OLD_FALL_POSES`/`PAPYRUS_OLD_FALL_POSES` constants. C5's guard exempts exactly these imported modules and names in `tests/world/test_golden_traces.py`, not the whole file: any other member import there fails the guard. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_blank_image_margins_are_measured_from_the_drawings` | exempt by name (user) | Stays as it is. Only the per-game world rules' imports of member internals are exempt, by name, in this file: `from brave_adventurer import constants`; `from brave_adventurer.drawing import draw_player, draw_scarab`; `from brave_adventurer.player import Player`; `from brave_adventurer_core import constants`; `from brave_adventurer_papyrus.player import PapyrusPlayer`; `from brave_adventurer_papyrus.sprite_utils import apply_transparency_and_scale`; `from clockwork_keep.constants import PLAYER_HEIGHT, PLAYER_WIDTH`; `from clockwork_keep.drawing import draw_tinker`; `from clockwork_keep.player import Tinker`. They serve `TestWorldRules`, the `EXPECTED_DIFFERENCES` rule helpers (`tinker_feet_margin_pixels`, `adventurer_feet_margin_pixels`, `scarab_feet_margin_pixels`, `adventurer_falling_pose_shift_pixels`, `papyrus_running_and_falling_poses`, and the rules built on them) and the `ADVENTURER_OLD_FALL_POSES`/`PAPYRUS_OLD_FALL_POSES` constants. C5's guard exempts exactly these imported modules and names in `tests/world/test_golden_traces.py`, not the whole file: any other member import there fails the guard. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_scarab_on_its_blank_image_stood_the_margin_higher (per case)` | exempt by name (user) | Stays as it is. Only the per-game world rules' imports of member internals are exempt, by name, in this file: `from brave_adventurer import constants`; `from brave_adventurer.drawing import draw_player, draw_scarab`; `from brave_adventurer.player import Player`; `from brave_adventurer_core import constants`; `from brave_adventurer_papyrus.player import PapyrusPlayer`; `from brave_adventurer_papyrus.sprite_utils import apply_transparency_and_scale`; `from clockwork_keep.constants import PLAYER_HEIGHT, PLAYER_WIDTH`; `from clockwork_keep.drawing import draw_tinker`; `from clockwork_keep.player import Tinker`. They serve `TestWorldRules`, the `EXPECTED_DIFFERENCES` rule helpers (`tinker_feet_margin_pixels`, `adventurer_feet_margin_pixels`, `scarab_feet_margin_pixels`, `adventurer_falling_pose_shift_pixels`, `papyrus_running_and_falling_poses`, and the rules built on them) and the `ADVENTURER_OLD_FALL_POSES`/`PAPYRUS_OLD_FALL_POSES` constants. C5's guard exempts exactly these imported modules and names in `tests/world/test_golden_traces.py`, not the whole file: any other member import there fails the guard. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_scarab_raised_rule_rejects_a_scarab_still_dropping_from_its_spawn` | exempt by name (user) | Stays as it is. Only the per-game world rules' imports of member internals are exempt, by name, in this file: `from brave_adventurer import constants`; `from brave_adventurer.drawing import draw_player, draw_scarab`; `from brave_adventurer.player import Player`; `from brave_adventurer_core import constants`; `from brave_adventurer_papyrus.player import PapyrusPlayer`; `from brave_adventurer_papyrus.sprite_utils import apply_transparency_and_scale`; `from clockwork_keep.constants import PLAYER_HEIGHT, PLAYER_WIDTH`; `from clockwork_keep.drawing import draw_tinker`; `from clockwork_keep.player import Tinker`. They serve `TestWorldRules`, the `EXPECTED_DIFFERENCES` rule helpers (`tinker_feet_margin_pixels`, `adventurer_feet_margin_pixels`, `scarab_feet_margin_pixels`, `adventurer_falling_pose_shift_pixels`, `papyrus_running_and_falling_poses`, and the rules built on them) and the `ADVENTURER_OLD_FALL_POSES`/`PAPYRUS_OLD_FALL_POSES` constants. C5's guard exempts exactly these imported modules and names in `tests/world/test_golden_traces.py`, not the whole file: any other member import there fails the guard. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_scarab_drop_rule_needs_the_old_scarab_at_its_spawn_height` | exempt by name (user) | Stays as it is. Only the per-game world rules' imports of member internals are exempt, by name, in this file: `from brave_adventurer import constants`; `from brave_adventurer.drawing import draw_player, draw_scarab`; `from brave_adventurer.player import Player`; `from brave_adventurer_core import constants`; `from brave_adventurer_papyrus.player import PapyrusPlayer`; `from brave_adventurer_papyrus.sprite_utils import apply_transparency_and_scale`; `from clockwork_keep.constants import PLAYER_HEIGHT, PLAYER_WIDTH`; `from clockwork_keep.drawing import draw_tinker`; `from clockwork_keep.player import Tinker`. They serve `TestWorldRules`, the `EXPECTED_DIFFERENCES` rule helpers (`tinker_feet_margin_pixels`, `adventurer_feet_margin_pixels`, `scarab_feet_margin_pixels`, `adventurer_falling_pose_shift_pixels`, `papyrus_running_and_falling_poses`, and the rules built on them) and the `ADVENTURER_OLD_FALL_POSES`/`PAPYRUS_OLD_FALL_POSES` constants. C5's guard exempts exactly these imported modules and names in `tests/world/test_golden_traces.py`, not the whole file: any other member import there fails the guard. | none: no engine arc only it reaches |
| `tests/world/test_golden_traces.py` | `TestWorldRules::test_scarab_drop_rule_rejects_a_scarab_that_has_landed` | exempt by name (user) | Stays as it is. Only the per-game world rules' imports of member internals are exempt, by name, in this file: `from brave_adventurer import constants`; `from brave_adventurer.drawing import draw_player, draw_scarab`; `from brave_adventurer.player import Player`; `from brave_adventurer_core import constants`; `from brave_adventurer_papyrus.player import PapyrusPlayer`; `from brave_adventurer_papyrus.sprite_utils import apply_transparency_and_scale`; `from clockwork_keep.constants import PLAYER_HEIGHT, PLAYER_WIDTH`; `from clockwork_keep.drawing import draw_tinker`; `from clockwork_keep.player import Tinker`. They serve `TestWorldRules`, the `EXPECTED_DIFFERENCES` rule helpers (`tinker_feet_margin_pixels`, `adventurer_feet_margin_pixels`, `scarab_feet_margin_pixels`, `adventurer_falling_pose_shift_pixels`, `papyrus_running_and_falling_poses`, and the rules built on them) and the `ADVENTURER_OLD_FALL_POSES`/`PAPYRUS_OLD_FALL_POSES` constants. C5's guard exempts exactly these imported modules and names in `tests/world/test_golden_traces.py`, not the whole file: any other member import there fails the guard. | none: no engine arc only it reaches |
| `tests/world/test_transition_input.py` | `test_jump_pressed_during_elevator_ride_does_not_jump_on_arrival` | (b) stand-in, in process | Stand-in scenes, in this process: this file's `DepartureScene`/`ArrivalScene` (with their shared `ActionMap`), changed so the departure takes the engine's `ElevatorTransition` (`glitchygames/transitions/elevator.py`). A jump pressed and released during the ride must not be `just_pressed`, and must not move the arrival scene's sprite up. Clockwork Keep supplied `SPAWN_SETTLE_FRAMES`, `ELEVATOR_SETTLE_FRAMES`, `ARRIVAL_WATCH_FRAMES` and the order K_w then K_UP. Engine: `SceneManager._process_transition_events`, `TRANSITION_DISCARDED_EVENT_TYPES`. | Using `ElevatorTransition` keeps `transitions/elevator.py` `_draw_shaft_walls` (208-209) reached by a stand-in |

**Future work (decision 11), for C6 to copy into `plans/future-work.md`.** After C2 and C3,
these engine arcs are reached only by root tests that run members. That means
`test_game_matches_golden_trace` (c),
`TestRoundTrip::test_golden_script_recording_replays_without_divergence` (c) and
`test_every_game_powers_on_through_its_own_main` (c). They are not gaps, but the engine's own
tests should reach each with a stand-in:
- `game_objects/ball.py`: `dt_tick` (744); `_finish_wall_bounce` (820-821)
- `animation/state_machine.py`: `evaluate` (291-292); `_switch_to` (342, 346)
- `physics/body.py`: `get_animation_context` (133)
- `input/action_map.py`: `handle_event` (401); only the golden traces reach it
- `audio/recipes.py`: `render` (116-117)
- `audio/synth.py`: `concatenate` (437)
- `camera.py`: `update_scroll` (144)
- `transitions/elevator.py`: `_draw_shaft_walls` (208-209); only the golden traces reach it,
  until the `ElevatorTransition` stand-in for
  `test_jump_pressed_during_elevator_ride_does_not_jump_on_arrival` reaches it too
- `sprites/animated.py`: `SpriteAnimation.__init__` (575); `update_nested_sprites` (2663)
- `engine/game_engine.py`: `_crash_boundary` (2577); `_run_game` (2596); only the power-on test
  reaches them

These were re-checked on 2026-10-26 against the per-test coverage contexts, with the revised
categories; the list is the reviewer's, unchanged. Line numbers are as of 273fa323.

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
  - browser bundles never ship ignored files (a new, not-yet-added file still does)
- This plan's Status.

- [ ] **Step 1:** write the docs; run `lint-docs` and the living-docs guard.
- [ ] **Step 2:** verify:
  - `nox -s lint static-analysis`, `CI=true nox -s test`, `uv run pytest` and
    `nox -s build-wheel`
  - one golden replay per game, through its console script
- [ ] **Step 3:** commit, then stop for the user's review.

---

## Stage D: the engine owns every recording, replay and measurement tool

**Status:** DONE 2026-10-27 (D1-D9, D11, then D10: the docs, the deferred cleanups and the stage's
verification), apart from D11 Step 3 (the user's look at a watched `--compare-trace`). The final
Stage D review's fixes are DONE 2026-10-27: the command runs inside the engine's crash boundary
(I1), `verify` fails unclaimed goldens and a project claims its own (I2), `game-timeout-seconds`
(I3), a rolled golden-trace seed is recorded (I4), `--project-root`'s per-tool default (M1),
unreadable pending ledgers (M3), missing required options exit 64 on both front ends (M4), git
variables (M6), and a clear refusal for a game argument named as an engine flag; the other
Minors are in `plans/future-work.md`. Planned 2026-10-26, after Stage C's final review, on the same branch and PR
(the user, 2026-10-26: "Let's do it here"). Where this section and the code differ, the code's
`registry.TOOLS` is the reference (the tools table was brought in line in D10).

**Goal.** A game the engine has never seen can record, replay, verify, rebaseline, measure, report
on and graph its recordings with only the installed `glitchygames` wheel. One set of tools serves
three users: the engine's own tests, our bundled games' goldens and demos, and a player recording
and replaying their own local runs (the user, 2026-10-26: "good tools for testing the engine and
bundled games, as well as user-centric tooling to reuse the same tools for their own local plays").

**Architecture.** A new engine subpackage, `glitchygames.replay.tools`, holds every tool, described
once in one table (`TOOLS`). Two front ends are built from that table, so their names can't drift:
- **On the game.** `GameEngine.args` adds every tool as a `--<name>` flag to the game's own
  command line. A flag that doesn't run the game (`--measure`, `--report`, …) runs *instead of*
  the game, in `_begin_run`, as `--list-input-devices` already does.
- **The `glitchygames` command.** A console script in the engine wheel, with the same names as
  subcommands. It reads recordings and the ledger itself, and starts the game as a child process
  (`<console script> --<name> …`) whenever the game has to run.

The game passes itself to the engine (`GameEngine(game=Game)`, as today) and declares nothing
else. Its package, package directory, console script and git revision all come from that object.
The project's settings live in `[tool.glitchygames]` in its `pyproject.toml`, with defaults that
fit a standard layout. `scripts/` keeps only this repository's policy: the five games' input
scripts, staging rows in the pre-commit hook, and the docs snippet text.

### Stage D decisions (the user's, 2026-10-26)

12. **Anything the engine can own, it owns.** That covers recording, scripted sessions, golden
    traces, replay, verification, rebaselining, measurement, the ledger, reports and performance
    pages (the user: "Anything the engine can own, it should. A game we've never seen should be
    able to be recorded, replayed, etc..."; "all of those tools need to be in the engine").
13. **The game passes itself into the engine; the engine injects the flags** (the user: "the
    engine should be able to inject all of the recording arguments into the game's argument
    section … The game never needs to know anything about it otherwise").
14. **Both front ends: flags on the game and a `glitchygames` command, with synced names, and
    tests for all of it** (the user: "we should do both. And tests for all. And keep the command
    and flags name sync'd"). The script aliases are registered console scripts that call the
    engine (the user: "the script aliases should be registered to hook the engine calls").
15. **The golden-replay pytest plugin auto-registers** through a `pytest11` entry point.
16. **Project settings live in `[tool.glitchygames]`** in `pyproject.toml`.
17. **`--random-seed` defaults to `None` everywhere** (the user, 2026-10-26: "If none, we roll
    random, if something, we use the something. If something on a replay, we use something, if
    it's None on a replay, we use the game seed from the replay"; "That allows us to test all
    combinations without changing much"). A recording or run with `None` rolls a random seed,
    logged in the recording. A replay with `None` uses the recorded seed. Refined the same day (the
    user: "I don't think we should force a replay that has a new seed - that would cause issues
    for the golden samples ... maybe we need to set a flag to have it update the replay?"): a
    replay given a different seed replays OLD's inputs under it without comparing and records
    nothing (the user: "we can replay the game but just not record a new version"; `--audit`
    still refuses it). With `--rebaseline NEW` it replays OLD's inputs under that seed into NEW
    (OLD untouched), confirmed by the user: "if you rebaseline then
    we will replace the seed if and only if provided". The harness tools lose their fixed default;
    our scripts pass `20261018`.
18. **`--compare-trace OLD` onion-skins two runs** (the user, 2026-10-26: "consider adding a
    --compare-trace that is able to be run to do the onion skinning"; placed as Task D11). An
    option of `replay-trace`: NEW replays watched and solid, OLD's same-numbered frame is drawn
    over it at `--compare-alpha` (default 50%). OLD is replayed by a headless child process in
    lockstep, streaming its frames, so NEW's replay is untouched.

**Calls made while planning** (the controller's; the user may overturn any):
- **Rebaseline and audit stay options of `replay-trace`** (the controller's recommendation; the
  user agreed, 2026-10-26). They already are; they take the same recording, find the game the same way and
  share replay-trace's other options. As separate tools they would either copy those options or
  change the game flag's shape (`--rebaseline OLD NEW`), breaking every existing use.
  `glitchygames --help` lists them under `replay-trace` so they stay discoverable. That leaves 10
  tools.
- **The package is `glitchygames.replay.tools`** (the user, 2026-10-26). Importing it loads pygame
  (through `glitchygames.replay`'s `__init__`), which is fine: pygame-ce is a required dependency
  (the user: "Anything importing anything glitchygames would need pygame"). What matters is that a
  tool that doesn't run the game builds no scene and opens no window, and that the command's
  output carries no pygame banner (`PYGAME_HIDE_SUPPORT_PROMPT` is set before any import).
- **Aliases: only `glitchygames` and `python -m glitchygames` for now** (the user, 2026-10-26:
  "Enough for now").
- **The existing names stay:** `record-trace`, `replay-trace` and `rebaseline`. They are already
  in every recording's docs, the recipe and CI, and synced names only need one name per tool, not
  a new one. Cost if wrong: a rename task with aliases.
- **A ledger row's commit is the game's.** The game's source revision is recorded beside the
  engine's (`MeasurementRun.game_source_revision`). The row's commit and uncommitted-changes flag
  come from the game, falling back to the engine's for a recording that predates the field. In
  this repository both are the same checkout, so our rows don't change (Task D3 pins that).
- **`MEMBER_LAYERS` stays for logical names for now.** A frozen binary or a wheel install has no
  `pyproject.toml` to read, and an unseen game already gets plain module names. Only
  `bundled_demos`' default stops using it (Task D5). The name-collision risk (an outside package
  named `paddleslap` would be labelled `games.paddleslap`) goes in `plans/future-work.md`.
- **Our five games' input scripts stay in `scripts/`.** The tools reach them as `MODULE:NAME`
  references (`--input-script scripts.golden_inputs:paddleslap_script`, run from the repository
  root).
  They are test data, not engine code.

### Stage D Global Constraints

Part 3's Global Constraints all apply, and in addition:
- **Every tool is registered once, in `TOOLS`,** and the game flag `--<name>` and the subcommand
  `glitchygames <name>` are generated from it. Nothing adds a tool flag or subcommand by hand.
- **No engine module imports `scripts.*`,** and no engine test does (the Stage C guard already
  forbids members; Task D1 extends it to `scripts`, apart from the test files that test a
  script).
- **Importing `glitchygames.replay.tools` never imports pytest** (it stays in the `dev` extra).
  Importing pygame is fine (a required dependency); opening a display is not, for any tool that
  doesn't run the game, and the command prints no pygame banner.
- **Every tool has tests through both front ends:** the game flag (on a stand-in game) and the
  command.
- **A move keeps behavior:** each script function moved into the engine keeps its tests, which
  move with it (to `tests/replay/tools/`), and gain a stand-in in place of any of our games.
  Decision 11's before/after engine coverage applies to every task.
- **Recordings and ledger rows keep their format,** apart from the one added optional field
  (Task D3). Old recordings and old rows must still load; a test pins each.

### Stage D Review Focus

1. **The two front ends drifting apart:** a tool reachable as a flag but not as a command, or with
   different options or defaults. The sync test (Task D1) compares names *and* each tool's options.
2. **A flag that doesn't run the game still building the game:** `--report run.jsonl.gz` must not
   open a window or construct the scene. Tests assert that no scene is built and the exit code is
   right (Tasks D5-D7).
3. **The pytest plugin loading in projects that aren't games** once it is auto-registered: it must
   add no items and print nothing where there is no `fixtures/replays/`
   directory and no `[tool.glitchygames]` (Task D8, tested with pytester in a bare project).
4. **An unseen game's rows naming the engine's commit** (the provenance bug the audit found).
   Task D3 tests a stand-in game in its own temporary git repository.
5. **A project without `[tool.glitchygames]`** (a player's own local runs): every tool must work on
   the defaults alone, and a path from the defaults that doesn't exist (no ledger directory yet)
   is created or reported, never a traceback (Tasks D2 and D9).

### Stage D File Structure

| File | Responsibility |
|---|---|
| `src/glitchygames/replay/tools/registry.py` | `Tool`, `ToolOption`, `TOOLS`, `add_game_flags(parser)`, `build_command_parser()`, `run_game_flag_tool(options, game) -> ExitCode \| None` |
| `src/glitchygames/replay/tools/command.py` | the `glitchygames` console script: `main()` |
| `src/glitchygames/replay/tools/children.py` | games run as child processes (moved from `testing/replays.py`; no pytest) |
| `src/glitchygames/replay/tools/settings.py` | `ProjectSettings`, read from `[tool.glitchygames]` |
| `src/glitchygames/replay/tools/identity.py` | `GameIdentity`: a game object's package, directory, console script and revision |
| `src/glitchygames/replay/tools/golden_traces.py` | the sprite-trace harness (from `scripts/record_golden_traces.py`) |
| `src/glitchygames/replay/tools/scripted_sessions.py` | the scripted-session recorder (from `scripts/record_scripted_session.py`) |
| `src/glitchygames/replay/tools/recordings.py` | a game's goldens and bundled demos |
| `src/glitchygames/replay/tools/measure.py` | measurement, `unmeasured`, `clear-published` (from `scripts/replay_metrics.py`) |
| `src/glitchygames/replay/tools/report.py` | the recording report (from `scripts/recording_report.py`) |
| `src/glitchygames/replay/tools/performance_pages.py` | the performance pages (from `scripts/generate_performance_graphs.py`) |
| `src/glitchygames/replay/tools/traces.py` | record-trace's, replay-trace's, record-golden-trace's and record-session's handlers on both front ends (added in D1-D4b) |
| `src/glitchygames/replay/tools/verify.py` | the `verify` tool (Task D5) |
| `src/glitchygames/replay/tools/compare.py` | `--compare-trace`, the onion skin (Task D11) |
| `tests/replay/tools/` | the engine's tests for all of it, on stand-in games |
| `scripts/golden_inputs.py` (new) | our five games' input scripts and controls tails, as `MODULE:NAME` targets |
| root `pyproject.toml` | `glitchygames` console script, `pytest11` entry point, our `[tool.glitchygames]` |

### The tools (names identical as `--<name>` and `glitchygames <name>`)

| Tool | Runs the game? | As a game flag | As a command |
|---|---|---|---|
| `record-trace` | yes | exists, with `--random-seed` and `--headless` | `glitchygames record-trace GAME PATH [same options]` |
| `replay-trace` | yes | exists, with its options `--headless`, `--replay-fps`, `--replay-pause-at-frame`, `--audit`, `--rebaseline NEW`, `--compare-processing`, `--max-processing-slowdown`, `--replay-digest`, `--random-seed`, and (Task D11) `--compare-trace OLD`, `--compare-alpha PERCENT` (and the hidden `--replay-frame-stream PORT:TOKEN`) | `glitchygames replay-trace PATH [same options] [--game GAME]` (the game comes from the recording) |
| `record-session` | yes | `--record-session PATH --input-script M:N --frame-count N [--controls-tail M:N] [--polled-input] [--input-only-placements]` | `glitchygames record-session GAME PATH --input-script M:N --frame-count N [same options]` |
| `record-golden-trace` | yes | `--record-golden-trace PATH --input-script M:N --frame-count N` | `glitchygames record-golden-trace GAME PATH --input-script M:N --frame-count N` |
| `verify` | yes | `--verify [PATH …] [--only TEXT]` (default: the game's own) | `glitchygames verify [PATH …] [--only TEXT] [--game GAME …]` (`--game` repeatable, in the three `GAME` forms; default: `[tool.glitchygames] games`) |
| `measure` | yes | `--measure [PATH …] [--force] [--allow-dirty \| --skip-dirty] [--only TEXT] [--code-tree TREE] [--rows-directory DIRECTORY] [--pending PATH]` | `glitchygames measure [PATH …] [same options] [--game GAME …]` (runs `GAME --measure` per game) |
| `unmeasured` | no | `--unmeasured [--code-tree TREE] [--rows-directory DIRECTORY] [--pending PATH]` | `glitchygames unmeasured [same options] [--game GAME …]` |
| `clear-published` | no | `--clear-published [--pending PATH]` | `glitchygames clear-published [--pending PATH]` |
| `report` | no | `--report PATH [--threshold PERCENT] [--minimum-ms MS] [--spans N]` | `glitchygames report PATH [same options]` |
| `performance-pages` | no | `--performance-pages DIRECTORY [--published]` | `glitchygames performance-pages DIRECTORY [--published]` |

(Updated 2026-10-27, Task D10, to match `registry.TOOLS`, the reference: `--frame-count`, not
`--frames`; `verify`/`measure`/`unmeasured` take their games as `--game`, once per game, beside
the recordings' paths; every subcommand also takes `--project-root DIR`, and arguments after a
bare `--` go to the game.)

**How `GAME` is resolved** (the user, 2026-10-26, approving three forms so an uninstalled game
works too). The command resolves it in this order and prints which form it used:

| `GAME` looks like | Meaning | The child it runs |
|---|---|---|
| contains `/` or ends in `.py` | a script path | `python <path> --<tool> …` |
| contains `:` | an entry point `MODULE:CALLABLE` | `python -c` calling it, with the flags in `sys.argv` |
| a plain name | an installed console script (`game_entry_point`), else an importable module | `<script> --<tool> …`, else `python -m <module> --<tool> …` |

A plain name matching nothing is an error naming all three forms. Every form ends in the game's
`GameEngine(game=Game)`, which injects the flags, so the game never knows how it was started.
`replay-trace` takes the game from the recording's header (`console_script_for_game_module`); when
that module no longer imports (a moved script), it asks for `--game GAME`, in the same three forms.

`[tool.glitchygames]` keys, with defaults for an unseen project:

| Key | Default | Ours |
|---|---|---|
| `games` | the project's `[project.scripts]` | the nine console scripts |
| `golden-globs` | `["tests/fixtures/replays/**/*.jsonl.gz"]` | `["src/*/*/tests/fixtures/replays/golden*.jsonl.gz"]` |
| `ledger-directory` | `"replay-ledger"` | `"quality/replay-ledger"` |
| `pending-ledger` | `".glitchygames/pending-ledger.jsonl"` (the project's local directory, git-ignored; Task D2) | `"test-results/replay-metrics/pending.jsonl"` |
| `published-ledger` | none (nothing published) | `"origin/gh-pages:<PUBLISHED_LEDGER_PATH>"` |
| `landed-ref` | `"origin/main"` | `"origin/main"` |
| `measured-paths` | `["src", "tests/fixtures/replays", "pyproject.toml"]` | today's `MEASURED_PATHS` |
| `unmeasured-paths` | `[]` | today's member-test pathspecs |
| `recording-renames` | `{}` | today's `RECORDING_PATH_RENAMES` |
| `game-timeout-seconds` | `3600` (an hour; added by the final review's fixes, I3) | the default |

### Task D1: The tool table, both front ends, and the sync test

**Files:** `replay/tools/{__init__,registry,command}.py`;
`glitchygames/__main__.py` (`python -m glitchygames`); `engine/game_engine.py` (`args` adds
`add_game_flags`, and `_begin_run` dispatches `run_game_flag_tool`); root `pyproject.toml`
(`glitchygames = "glitchygames.replay.tools.command:main"`); `tests/replay/tools/test_registry.py`;
the Stage C import guard gains `scripts`.

**Interfaces:**
- `Tool(name: str, help: str, options: tuple[ToolOption, ...], runs_game: bool, game_handler, command_handler)`.
- `ToolOption(flag: str, help: str, kind: Literal['path', 'paths', 'int', 'reference', 'flag'], required: bool)`.
- `GameLaunch(form: Literal['script', 'entry-point', 'console-script', 'module'], command: list[str])`;
  `resolve_game(*, game: str) -> GameLaunch` (raises `UnknownGameError` naming the three forms);
  `launch_game(*, launch: GameLaunch, arguments: list[str]) -> CompletedProcess[str]`.
- `add_game_flags(parser) -> None`; `build_command_parser() -> argparse.ArgumentParser`;
  `run_game_flag_tool(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode | None`
  (None: no tool flag was given, so run the game).

The existing `--record-trace`, `--replay-trace` and `--rebaseline` definitions move into `TOOLS`
unchanged (help text, destinations and defaults), with `--rebaseline` and `--audit` as
`replay-trace` options. Their game handlers stay where they are; their command handlers start
the game as a child.

- [x] **Step 1: failing tests.**
  - `test_every_tool_is_a_game_flag_and_a_command`: the set of `--<name>` tool flags in a
    stand-in game's parser equals the set of `glitchygames` subcommands, which equals
    `{tool.name for tool in TOOLS}`.
  - `test_each_tools_options_match_on_both_front_ends`: per tool, the option flags, kinds,
    `required` and defaults agree.
  - `test_the_existing_trace_flags_are_unchanged`: `--record-trace`, `--replay-trace` and
    `--rebaseline` parse to the same `OPTIONS` keys and values as before.
  - `test_glitchygames_help_lists_every_tool`, and `test_a_game_help_lists_every_tool`.
  - `test_importing_the_replay_tools_imports_no_pytest` (in a subprocess).
  - `test_the_command_prints_no_pygame_banner`: `glitchygames --help`'s stdout starts with the usage.
  - `test_python_m_glitchygames_is_the_command`.
  - `test_no_tool_option_clashes_with_any_of_our_games_arguments`: every member's game parser
    builds with the tool flags added.
  - `test_game_resolves_each_form` (a script path, `MODULE:CALLABLE`, a console script, a module;
    each launch's command), `test_a_plain_name_prefers_the_console_script_over_the_module`, and
    `test_an_unknown_game_names_all_three_forms`.
  - `test_replay_trace_asks_for_game_when_the_recorded_module_is_gone`.
  - `test_glitchygames_record_trace_runs_the_game_as_a_child` and
    `test_glitchygames_replay_trace_finds_the_game_from_the_recording` (on a stand-in game).
- [x] **Step 2:** implement until they pass; lint; `CI=true nox -s test`; commit — "The engine
  describes its recording tools once, as game flags and as the glitchygames command".

### Task D2: Children without pytest, project settings, and the game's identity

**Files:** `replay/tools/{children,settings,identity}.py`; `testing/replays.py` (the plugin keeps
its pytest parts; every importer of the moved helpers is updated, with no re-export);
`code_tree.py` and `recording_metrics.py` (their repository constants become `ProjectSettings`
fields, read where they were used); root `pyproject.toml` (`[tool.glitchygames]` with today's
values); `tests/replay/tools/test_{children,settings,identity}.py`.

**Interfaces:**
- `ProjectSettings` (pydantic, `extra='forbid'`, kebab-case aliases, the keys in the table above);
  `load_project_settings(*, project_root: Path) -> ProjectSettings`.
- `GameIdentity(package: str, package_directory: Path, console_script: str | None, distribution: str | None)`;
  `game_identity(*, game: type[Scene] | Scene) -> GameIdentity`.
- `children.py` keeps today's names and signatures (`replay_command`,
  `replay_recording_headless`, `rebaseline_recording_headless`, `recording_console_script`, …).
  `recording_console_script`'s error text loses "`uv sync --all-packages`" and names the console
  script it looked for.

- [x] **Step 1: failing tests.**
  - `test_a_project_without_tool_glitchygames_gets_the_defaults`
  - `test_an_unknown_setting_is_refused_by_name`
  - `test_our_settings_equal_the_old_constants`: our `pyproject.toml` gives exactly today's
    `LEDGER_DIRECTORY`, `MEASURED_PATHS`, the member-test pathspecs, the pending path, the
    published path and ref, and `RECORDING_PATH_RENAMES`. Copy the values into the test by hand
    before deleting the constants.
  - `test_a_game_knows_its_package_and_console_script` (a stand-in distribution), and
    `test_a_game_with_no_console_script_still_has_an_identity`.
  - `test_children_import_without_pytest` (in a subprocess with pytest blocked).
- [x] **Step 2:** implement; every caller reads settings; `CI=true nox -s test`; commit.

### Task D3: Rows and recordings name the game's commit

**Files:** `recording_metrics.py` (`MeasurementRun.game_source_revision: SourceRevision | None =
None`; `ledger_rows_from_rebaseline` takes commit and dirty state from it, falling back to
`source_revision`); `engine/game_engine.py:~1647` (sets it from
`game_identity(game=…).package_directory`); `tests/replay/tools/test_provenance.py`.

- [x] **Step 1: failing tests.**
  - `test_a_stand_in_game_in_its_own_repository_records_its_own_commit`: write a stand-in game
    into a temporary `git init` repository with one commit. Rebaseline a recording through its
    console script. The header's `game_source_revision.commit` is that repository's commit, and
    the ledger row's commit equals it, not the engine's.
  - `test_a_dirty_game_checkout_marks_the_row_dirty`.
  - `test_a_recording_without_game_source_revision_still_loads_and_uses_the_engines`, using a
    committed golden from before this change.
  - `test_our_games_rows_are_unchanged`: one of our goldens produces the same commit as before.
- [x] **Step 2:** implement; `CI=true nox -s test`; commit.

### Task D4a: The golden-trace harness moves into the engine

**Files:** `replay/tools/golden_traces.py` gets the general parts listed in the audit:
- `GameSceneClasses`, `FrameObserver`, `RecordTraceHooks`, `press`/`release`, `InputScript`
- `deterministic_environment`, `command_line`, `GoldenTraceSceneManager`, `GoldenTraceEngine`
- `discard_environment_events`, `ENVIRONMENT_EVENT_TYPES`, `FRAME_SECONDS`, `RANDOM_SEED`,
  `SCREEN_RESOLUTION`
- `record_trace` and `replay_golden_recording`, re-keyed to `(*, scene_class, script: InputScript, …)`
  in place of `game_key`

`scripts/golden_inputs.py` (new) gets the per-game scripts, constants and helper classes
(`PaddleTracker`, `MuncherSteering`, `DrawingFireMouse`, …). `scripts/record_golden_traces.py`
shrinks to `GAME_SCENES`, `GAME_MODULES`, `SCRIPT_BUILDERS`, `GOLDEN_TRACE_GAMES`, `golden_path`
and `main`, calling the engine. The ~40 importing test modules are updated: engine tests import
the engine harness, and member tests may import `scripts.golden_inputs`. The `record-golden-trace`
tool is added to `TOOLS`.

- [x] **Step 1:** move the tests with the code (`tests/replay/tools/test_golden_traces.py`). Add
  `test_record_golden_trace_on_a_stand_in_game_as_a_flag_and_a_command`.
- [x] **Step 2:** move the code; save engine-only coverage before and after; close any gap;
  every golden trace still matches (`tests/world/test_golden_traces.py`); commit.

### Task D4b: The scripted-session recorder moves into the engine

**Files:** `replay/tools/scripted_sessions.py` gets `PostedPolledInput`, `polled_input_follows`,
`ScriptedInputSupervisor`, `GameDidNotQuitError`, `QUIT_WAIT_FRAMES`, and
`record_scripted_session(*, scene_class, script, frame_count, path, controls_tail=None,
polled_input=False, input_only_placements=False, random_seed=RANDOM_SEED)`. The supervisor's
game-key checks become those two flags. `scripts/record_scripted_session.py` shrinks to our games'
tables (`INPUT_ONLY_PLACEMENT_GAMES`, `POLLED_INPUT_GAMES`, `CONTROLS_TAIL_BUILDERS`,
`REPLAY_FIXTURE_DIRECTORIES`, `GOLDEN_FIXTURE_NAMES`, `fixture_path`) and a `--game` CLI calling
the engine. The per-game controls tails move to `scripts/golden_inputs.py`. The
`record-session` tool is added (`--controls-tail M:N`, `--polled-input` and
`--input-only-placements` as tool options).

- [x] **Step 1:** move the tests (`tests/replay/tools/test_scripted_sessions.py`). Add
  `test_record_session_on_a_stand_in_game_as_a_flag_and_a_command` (the recording replays SUCCESS
  through `--replay-trace --headless`).
- [x] **Step 2:** move the code; coverage before and after; re-record nothing; prove one golden
  per game is byte-identical when re-recorded by `scripts/record_scripted_session.py --game`, into
  a scratch path; commit.

### Task D5: A game's recordings, and `verify`

**Files:** `replay/tools/recordings.py`
(`game_recordings(*, identity, settings, project_root) -> list[Recording]`, where
`Recording(console_script: str, path: Path, kind: Literal['golden', 'demo'])`: the goldens that match
`golden-globs` and belong to this game's console script, plus the demos in
`<package>/demos/`); `bundled_demos.py` (`packages` becomes required, with no `MEMBER_LAYERS`
default; callers pass it; `testing/replays.py:~409` too); the `verify` tool (each recording
replayed headless in a child; one line per recording; exit `SUCCESS` only if all pass);
`tests/replay/tools/test_{recordings,verify}.py`.

- [x] **Step 1: failing tests.**
  - `test_a_game_finds_its_own_goldens_and_demos_and_no_other_games`
  - `test_verify_passes_and_fails_per_recording_as_a_flag_and_a_command` (one good and one
    tampered recording; exit code and lines)
  - `test_verify_with_no_recordings_says_so`
- [x] **Step 2:** implement; commit.

### Task D6: `measure`, `unmeasured` and `clear-published` move into the engine

**Files:** `replay/tools/measure.py` gets from `scripts/replay_metrics.py`:
- `MeasureResult`, `UnreplayableRecording`, `this_machine`, `MeasureSettings`
- `measure_recording`, `describe_measurement`, `_already_measured`, the `measure` loop
- `rows_to_write`, with its "landed" rule on `settings.landed_ref`
- `missing_measurements(*, rows, recordings, code_tree, machine)` (from
  `measure_staged_replays._fully_measured_here`)
- `clear_published`

The tools `measure` (`--force`, `--allow-dirty | --skip-dirty`, `--only`, `--rows-directory`,
`--code-tree`), `unmeasured` and `clear-published` are added. `glitchygames measure [--game GAME …]` runs
`GAME --measure` per game and sums the exit codes, as today's loop does.
`scripts/replay_metrics.py` is deleted: the nox sessions call `glitchygames measure` and
`glitchygames clear-published`. `scripts/measure_staged_replays.py` keeps only git staging and its
refusals, and calls `glitchygames unmeasured` and `glitchygames measure --rows-directory`.
`tests/test_replay_metrics.py` moves to `tests/replay/tools/test_measure.py`, on stand-ins.

- [x] **Step 1:** move the tests; add `test_measure_a_stand_in_game_as_a_flag_and_a_command` (rows
  written to its `[tool.glitchygames]` pending ledger), `test_unmeasured_lists_then_empties`, and
  `test_measure_in_a_project_without_settings_creates_the_ledger_directory`.
- [x] **Step 2:** move the code; the pre-commit hook still measures and stages (its own tests
  pass unchanged apart from imports); `nox -s replay-metrics` works; commit.

### Task D7: `report` and `performance-pages` move into the engine

**Files:**
- `replay/tools/report.py`: `scripts/recording_report.py` whole, with its tests. The script is
  deleted.
- `replay/tools/performance_pages.py`:
  - the rendering half of `scripts/generate_performance_graphs.py`
  - `write_performance_pages(*, rows, directory)`
  - the source merge (row files, landed trees, published ledger, pending), driven by
    `ProjectSettings`
- `scripts/generate_performance_graphs.py` keeps the docs paths and `performance_snippet`, and
  calls the engine. If rendering imports anything outside the engine's runtime dependencies, that
  import is lazy and the tool reports the missing package by name.

- [x] **Step 1:** move the tests. Add:
  - `test_report_never_builds_the_game`: a scene class whose constructor raises; `--report` exits
    `SUCCESS`
  - `test_report_and_performance_pages_as_a_flag_and_a_command`
- [x] **Step 2:** move the code; `nox -s docs` still builds the performance pages; commit.

### Task D8: The pytest plugin auto-registers

**Files:**
- root `pyproject.toml`: `[project.entry-points.pytest11] glitchygames =
  "glitchygames.testing.replays"`
- root `conftest.py`: drop the manual load (and its comment)
- `testing/replays.py`: loading it prints nothing (no pygame banner) in any project. It collects the configured games' bundled demos too, unless
  `tests/replay/test_bundled_demos.py` already covers them; pick one, never both, and record which
  in the task report.
- `tests/replay/test_replay_plugin.py`: it stops importing `scripts.record_scripted_session`, and
  uses a stand-in fixture.

- [x] **Step 1: failing tests (pytester).**
  - `test_the_plugin_loads_without_a_conftest_line`
  - `test_a_project_with_no_recordings_and_no_settings_gets_no_items_and_no_output`
- [x] **Step 2:** implement; the collected count of golden-replay items is unchanged; commit.

### Task D9: The unseen game, end to end

**Files:** `tests/replay/tools/test_an_unseen_game.py`.

Build a project in `tmp_path`: `git init`, a stand-in game distribution with a console script, a
`[tool.glitchygames]` (and a second run with none), an input script, and nothing from this
repository on `sys.path` (the children get an environment without the repository root).
The game is launched in **each of the three `GAME` forms** (the project's script path, its
`MODULE:main`, and its console script once installed). Then, **through both front ends, every tool
in `TOOLS`**: record-trace, replay-trace (with `--rebaseline` and `--audit`),
record-session, record-golden-trace, verify, measure, unmeasured, report, performance-pages and
clear-published (against a local bare repository as "published"). Assert:
- each tool's exit code
- the files it wrote
- the rows' commit is the stand-in repository's
- a test that walks `TOOLS` fails if a new tool has no case here

- [x] **Step 1:** write it; it passes on the finished stage. Prove it bites: break one front end's
  option (in a scratch edit) and watch it fail, then restore.
- [x] **Step 2:** commit.

### Task D11: `--compare-trace`, the onion skin (runs after D9, before D10)

**Files:** `replay/tools/compare.py` (new); `replay/tools/children.py` (the frame-streaming child);
`replay/tools/registry.py` (the two options on `replay-trace`); the replay viewer's step and
restart path (`replay/viewer.py`, `replay/driver.py`) to keep the child in step;
`tests/replay/tools/test_compare_trace.py`; D9's unseen-game test gains a `--compare-trace` case.

**Behavior** (decision 18):
- `--replay-trace NEW --compare-trace OLD [--compare-alpha PERCENT]`, on the game and as
  `glitchygames replay-trace NEW --compare-trace OLD …`. NEW replays watched, as normal and drawn
  solid; after each presented frame, OLD's frame of the same number is blended over it at
  `PERCENT` (default 50, range 0-100, refused outside it).
- OLD is replayed by a headless child (`<OLD's game> --replay-trace OLD --headless` plus a
  hidden frame-stream option) that writes each frame's pixels to a pipe; the parent reads one
  frame per NEW frame. Nothing in NEW's replay state changes; memory holds one frame.
- OLD shorter than NEW: its last frame stays, labelled "OLD ended at frame N". NEW shorter: the
  replay ends as usual and the child is stopped.
- Refused before anything runs: `--headless` (an onion skin is watched; the headless
  equivalent is row 5 or `--rebaseline`), different screen sizes, `--audit`, `--rebaseline`.
- Works with every seed row: `--replay-trace OLD --random-seed N --compare-trace OLD` shows OLD
  over its new-seed run (row 5).
- Pause and frame-step move both runs together. The viewer's step back restarts NEW at an
  earlier frame; the child restarts at the same frame (the same `--replay-pause-at-frame` path).
- The child is always stopped and reaped when the replay ends, fails or is interrupted.

- [x] **Step 1: failing tests** (stand-in game):
  - `test_one_blended_frame_has_the_expected_pixels`: two stand-in recordings with known
    colors at a known spot; the blended pixel equals the 50% mix (and a `--compare-alpha 25`
    case).
  - `test_the_child_streams_one_frame_per_frame_in_order`.
  - `test_a_shorter_old_holds_its_last_frame_with_the_label`.
  - `test_compare_trace_refuses_headless_audit_rebaseline_and_different_sizes`.
  - `test_compare_trace_through_both_front_ends`.
  - `test_the_child_is_reaped_when_the_replay_ends_or_fails`.
  - `test_a_step_back_restarts_the_child_at_the_same_frame`.
- [x] **Step 2:** implement; lint; `CI=true nox -s test`; commit. (Done 2026-10-27: the frame
  stream is a loopback socket, not a pipe, as the one child launcher passes no descriptors; the
  hidden option is `--replay-frame-stream PORT:TOKEN` (fix round 1: a per-child token checked on
  accept), `ToolOption.hidden`, no sync-test exemption.)
- [ ] **Step 3: the user's look.** Give the user one `!` command for a watched compare on a real
  game (for example a PaddleSlap golden against a row-5 replay of it under another seed), and
  record what they report in the task report.

### Task D10: Docs, then Stage D's verification

**Files:**
- `docs/architecture/gameplay_replay.md`: a "Tools for any game" section, with the tool table,
  `[tool.glitchygames]` and both front ends
- `docs/architecture/game_packages.md`: the recipe's steps name the tools and `golden_inputs.py`
- `docs/quality/performance.md`, and `CLAUDE.md` (Common Commands, the recording sections)
- the game docs that cite moved functions
- the engine module docstrings
- the master plan's "What every part keeps true": the engine owns every recording tool; game
  flags and commands share names
- `plans/future-work.md`: the logical-name collision risk
- this plan's Status

- [x] **Step 1:** write the docs; run `lint-docs` and the living-docs guard.
- [x] **Step 2:** verify:
  - `nox -s lint static-analysis`, `CI=true nox -s test`, `uv run pytest` and
    `nox -s build-wheel`; the engine wheel has the `glitchygames` script and the pytest11 entry
  - `nox -s replay-metrics` and `nox -s docs`
  - the pre-commit hook on a real commit
  - for one game by hand: `<game> --record-trace`, `--replay-trace`, and
    `glitchygames report` on the result
- [x] **Step 3:** commit, then stop for the user's review.
