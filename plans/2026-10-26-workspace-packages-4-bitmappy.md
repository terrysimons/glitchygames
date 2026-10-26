# Workspace Packages, Part 4: Bitmappy as an App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Tasks 1-6 done (2026-10-26); Task 7 (verification, with the user's manual checks)
pending. Open questions 1-9 were answered by the user on 2026-10-26; 10 (the branch name) was
assumed.

**Goal:** Move Bitmappy out of the engine into its own workspace member,
`src/apps/bitmappy/` (distribution `bitmappy`, import package `bitmappy`, console script `bitmappy`
unchanged, logical layer `apps`). Its sprite library moves with it as package data, and its tests
move into the member.

**Architecture:** This follows the recipe #109 used for the games (`docs/architecture/game_packages.md`,
steps 1-9) and the master plan's Part 4 outline. The order:
1. Make `--rebaseline` able to convert a recording whose class moved into a layer, so a user's
   pre-move Bitmappy recording can be converted.
2. Make the engine stop pointing into Bitmappy or its sprites.
3. Gather every Bitmappy test in `tests/tools/`.
4. Move Bitmappy in one commit.
5. Make `nox -s build-wheel` build every workspace package.
6. Docs, then whole-branch verification.

Part 3 (the three demos) is **not** done first (the user, 2026-10-26: "bitmappy should move
first"), so `src/glitchygames/examples/` keeps the demos, `EXAMPLES_LAYERS` stays, and deleting
`examples/` stays in Part 3.

**Tech Stack:** Python 3.14, uv workspaces (hatchling members), pygame-ce, pytest (100% coverage,
dummy and native drivers), ruff, basedpyright, ty, mkdocs strict + mkdocs-gen-files, PyInstaller,
Pyodide browser bundles.

**Spec:** `plans/2026-10-24-workspace-packages.md` (decisions 1, 3, 4, 5, 7, 8; Part 4's outline;
"What every part keeps true"). The move recipe is `docs/architecture/game_packages.md`.
`plans/2026-10-25-workspace-packages-2-games-demos-apps.md` is a superseded, untracked draft
written before #109. Its Tasks 13-17 are the starting point here, corrected against `main` at
a97efbe9 by a read-only survey (2026-10-26). Where they disagree, this plan wins.

## Open questions for the user (answer before Task 1)

Each item says what this plan currently assumes.

1. **`src/glitchygames/assets/bitmappy.png`: DECIDED (the user, 2026-10-26: move it to
   Bitmappy).**
   - It is byte-for-byte the same file as `bitmappy/resources/bitmappy.png` (both SHA-1
     `5699d5ec0c3a23c3420e5320f2d30cb4c5e05d86`, 1024×1024 RGB), which the editor loads
     (`editor.py:1561`).
   - So the move is: Bitmappy keeps its copy, which moves with the package in Task 4, and Task 2
     `git rm`s the engine's duplicate.
   - Task 2 checks the hashes again before removing it. If they differ, stop and ask.
2. **What the member declares: DECIDED (the user, 2026-10-26: everything it imports).** Bitmappy
   declares:
   - `glitchygames`
   - `aisuite` with the root's exact extras pin (no google extra; not the draft's `aisuite[all]`)
   - `numpy`, `pydantic`, `pygame-ce`
   - `tenacity>=9.1`, which moves out of the root: after the move only `bitmappy/ai_worker.py`
     imports it, so the root's deptry would flag it as unused (DEP002)
3. **Test file names: DECIDED (the user, 2026-10-26: "Let's call them test_bitmappy_*.
   Explicit is better than implicit.").** Every moved test module is named `test_bitmappy_<rest>.py`:
   - `test_canvas.py` becomes `test_bitmappy_canvas.py`, and the helper `test_film_strip_base.py`
     becomes `test_bitmappy_film_strip_base.py`, with its 12 importers rewritten.
   - A name that already starts with `test_bitmappy_` keeps it.
   - `test_bitmappy.py` stays as it is.
   - `conftest.py` stays.
   - Task 4 adds a guard: every test module in `src/apps/bitmappy/tests/` is named
     `test_bitmappy*.py`.
4. **Task 1 (`--rebaseline` across logical modules): DECIDED (the user, 2026-10-26: include it).**
   No committed recording is of Bitmappy, but a user's pre-move Bitmappy recording must be
   convertible.
5. **`nox -s build-wheel`: DECIDED (the user, 2026-10-26: fix it here).** Task 5 makes it build
   every workspace package's wheel (`uv build --all-packages`), not just the engine's.
6. **Local leftovers: DECIDED (the user, 2026-10-26: delete them).** Before Task 1, `rm -rf`
   these untracked leftover directories (`game_packages.md`, Pitfalls); nothing tracked is in them:
   - `src/glitchygames/examples/brave_adventurer/`, `brave_adventurer_papyrus/`,
     `clockwork_keep/` and `drawing_fire/` (ignored `__pycache__` and `.DS_Store`)
   - `tests/examples/drawing_fire/`

   Check each with `git ls-files <dir>` (it must print nothing) before deleting.
7. **The superseded draft: DECIDED (the user, 2026-10-26: keep it untracked for Part 3).**
   `plans/2026-10-25-workspace-packages-2-games-demos-apps.md` stays untracked, and is never
   staged on this branch. Its demos tasks (10-12) may help Part 3; delete it once Part 3 has its
   plan.
8. **The `examples:` prefix: DECIDED (the user, 2026-10-26: "We shouldn't treat examples
   specially anymore").** The prefix is removed from the engine's Load/Save dialogs, with no
   replacement. Task 2, item 2.
9. **Execution: DECIDED (the user, 2026-10-26: subagent-driven).** One fresh agent per task with
   a review gate after each, then a whole-branch review (superpowers:subagent-driven-development).
10. **The branch:** `feature/workspace-packages-4-bitmappy` from the latest `main`, one PR (not yet
    confirmed by the user).

## Global Constraints

- Branch from the latest `main`. Never push or open a PR without the user's go-ahead. Never
  restore files from git.
- Layers: `src/glitchygames` (engine), `src/games`, `src/demos`, `src/apps`. Bitmappy is the first
  `apps` member.
- Names: directory and distribution `bitmappy`, import package `bitmappy`, console script `bitmappy`.
  Logical name `apps.bitmappy.<module>:<class>` (it was `glitchygames.bitmappy...`, in no layer).
- **Member tests are rootless, as #109 built them:**
  - They live in `src/apps/bitmappy/tests/`, with no `__init__.py`.
  - Test file names are unique across every test root
    (`tests/test_suite_collection.py::test_test_file_names_are_unique_across_packages`).
  - A member `conftest.py` is allowed.
  - Not the draft's `bitmappy_tests/` package.
- Coverage stays at 100% (branch) over the engine and every member.
- No `# noqa`, `# ruff: ignore` or type-ignore additions; no lint or type configuration loosened.
  Configuration only grows to name the new member and the `apps` layer.
- pytest-mock `mocker` only. Keyword arguments; full names, no abbreviations; Google docstrings;
  100 columns.
- Lint (`ruff`, `basedpyright`, `ty`) before tests. TDD: see each new test fail before the change.
- Path rewrites use `perl -pi -e` with `\b` over `git grep -l ... -- ':!plans' ':!quality' ':!BUGS.md'`.
  Never `sed`. `glitchygames.bitmappy\b` must not touch `glitchygames.sprites.bitmappy_sprite`,
  `BitmappySprite` or `BitmappyLegacySprite`: read the diff.
- After `git mv` of a package, `rm -rf` its old directory: an ignored `__pycache__` left behind is
  importable and shadows the member.
- Run `uv lock`, then `uv sync --all-extras --all-groups --all-packages`, before committing the
  member.
- The pre-commit `replay-metrics` hook measures commits touching `src/`, `uv.lock` or
  `pyproject.toml`, and refuses untracked files under `src/` and partial commits. Never
  `--no-verify` or `SKIP=`.
- Stage explicitly (`git add <paths>`, `git add -u -- <paths>`), never `git add -A`/`.`. Each commit
  message ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Review Focus

1. **Data the source tree has but an installed copy does not.**
   - The risk: the sprite library, `bitmappy.cfg` and `bitmappy.png` load from `src/` (editable
     install) but not from the wheel (nox) or the frozen binary (PyInstaller `datas`).
   - Pinned by: Task 4's `test_the_sprite_library_ships_in_its_wheel` and
     `test_the_spec_bundles_the_resources_where_bitmappy_reads_them`, `CI=true nox -s test`, and
     Task 7's binary check.
2. **A stale `bitmappy` that shadows the member.**
   - The risk: `src/glitchygames/bitmappy/__pycache__`, or the four test files that do
     `sys.path.insert(0, <three directories up>)`, which after the move would put `src/apps` on
     the path and expose a `bitmappy` namespace directory.
   - Pinned by: Task 4's `test_the_old_engine_package_is_gone` (`find_spec('glitchygames.bitmappy') is None`)
     and `test_bitmappy_is_imported_from_its_member` (`bitmappy.__file__` is under
     `src/apps/bitmappy/bitmappy/` or `site-packages`). Task 3 deletes the `sys.path.insert` lines.
3. **A user's Bitmappy recording made before the move.**
   - Expected: a plain replay refuses it and names the remedy; `--rebaseline` converts it.
   - Pinned by: Task 1's tests.
4. **Someone who still types `examples:heart.toml` into the Load dialog.**
   - Expected: it is an ordinary file name now. It isn't found, and the dialog reports that the way
     it reports any missing file: no crash and no traceback.
   - Pinned by: Task 2's `test_an_examples_prefix_is_not_special`, plus a load-dialog test that a
     missing file is reported (check how the dialog reports a missing file today, and pin that).
5. **The AI worker after the move.**
   - The risk: `multiprocessing` starts `run_ai_worker_process` from `bitmappy.ai_worker`, and
     under the spawn start method the child must import `bitmappy` by name, in the editable
     install, the wheel, and the frozen binary (`freeze_support` in `scripts/bitmappy_entry.py`).
   - Pinned by: Task 4's `test_the_ai_worker_target_is_importable_by_name`
     (`run_ai_worker_process.__module__ == 'bitmappy.ai_worker'`, and `importlib.import_module` of
     it succeeds), and Task 7's binary check with AI features on.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/glitchygames/replay/driver.py`, `replay/playback.py`, `replay/rebaseline.py` | one `modules_not_compared` rule for both record formats (Task 1) |
| `src/glitchygames/sprites/file_format.py` (new) | `detect_file_format`, moved from Bitmappy (Task 2) |
| `src/glitchygames/ui/dialogs.py` | the `examples:` prefix removed; names used as given (Task 2) |
| `tests/fixtures/sprites/` (new) | the engine's own sprite test data: `colors.toml`, `static.toml`, `girl.toml` (Task 2) |
| `tests/tools/` | every Bitmappy test gathered (Task 3), then moved out (Task 4) |
| `src/apps/bitmappy/` (new) | `pyproject.toml`, `README.md`, `bitmappy/` (with `resources/sprites/`), `tests/` (Task 4) |
| `src/glitchygames/logical_names.py` | `MEMBER_LAYERS['bitmappy'] = 'apps'` (Task 4) |
| `scripts/build_browser_bundle.py` | Bitmappy as a member archive; `included_subpackages` deleted (Task 4) |
| `bitmappy.spec`, `scripts/bitmappy_entry.py` | the binary built from `src/apps/bitmappy` (Task 4) |
| `pyproject.toml`, `pyrightconfig.json`, `noxfile.py`, `wily.cfg`, `mkdocs.yml`, `uv.lock` | the member and the `apps` layer named everywhere (Task 4) |
| `noxfile.py` `_build_wheel`, `tests/test_ci_config.py` | `build-wheel` builds every workspace package (Task 5) |
| docs (Task 6) | `docs/architecture/bitmappy.md`, `game_packages.md`, `gameplay_replay.md`, `CLAUDE.md`, `README.md`, the root `*_README.md` files, `ai/README.md`, `ai/INTEGRATION.md`, the master plan |

---

### Task 1: `--rebaseline` converts a recording whose class moved to another logical module

**Why:** today a recording naming `glitchygames.bitmappy.editor:BitmapEditorScene` is refused even
under `--rebaseline`:
- `check_recorded_game` (`replay/driver.py:2774-2832`) compares full logical names in its
  logical-name branch (:2800-2807), ignores `is_rebaseline`, and does not name
  `REBASELINE_REMEDY` when it refuses.
- `find_scene_class` (`replay/playback.py:1033-1105`), in its logical branch, matches by name only
  for `__main__` (:1084-1088).
- `modules_not_compared` (`driver.py:2744-2771`) already returns True under `is_rebaseline`, but
  is only consulted for old-format records.

**The rule:** `modules_not_compared` becomes the one rule for both formats, compared on logical
modules.
- Under `--rebaseline` only, a recorded logical name with the same qualified name at another
  logical module is accepted, and NEW records the current names.
- Two loaded classes matching by qualified name are still refused (ambiguity).
- A different qualified name is still refused.
- A plain replay refuses and names `REBASELINE_REMEDY`.

**Files:**
- Modify: `src/glitchygames/replay/driver.py` (`modules_not_compared`'s docstring,
  `check_recorded_game`, rule 17 of the module docstring at :161),
  `src/glitchygames/replay/playback.py` (`find_scene_class`), `src/glitchygames/replay/rebaseline.py`
  (its docstring's rule list)
- Create: `tests/replay/test_rebaseline_across_logical_modules.py`

**Interfaces:**
- Consumes: `modules_not_compared(*, recorded_module, loaded_module, is_rebaseline)`,
  `REBASELINE_REMEDY`, `ReplayRefusedError`, `logical_module_name(module=...)`,
  `fixture_path(*, game_key, name=None)` (`scripts/record_scripted_session.py:388`),
  `replay_recording_headless` / `rebaseline_recording_headless` (`src/glitchygames/testing/replays.py:350,377`).
- Produces: `check_recorded_game(*, header, game_class, is_rebaseline=False)` and
  `find_scene_class(*, name, module, logical, is_rebaseline)`, both with the rule above (the
  signatures don't change).

- [ ] **Step 1: Write the failing tests.**
  - A module-level helper `write_recording_naming_logical_names(*, golden_path: Path, path: Path, renames: dict[str, str]) -> None`
    lives in the test file; it is the only user, and there is no root `tests/moved_games.py`. It
    rewrites the header's `game` and each `scene_start.scene` through `renames`, gzip in and out.
  - Mr. Muncher's golden stands in for any moved game:
    `CURRENT_NAME = 'games.mr_muncher.game:MrMuncherScene'`,
    `NAME_IN_ANOTHER_LAYER = 'apps.mr_muncher.game:MrMuncherScene'`.
  - A local `LayerMovedScene(Scene)` with `FORMER_LAYER_MOVED_NAME = 'apps.space_game.game:LayerMovedScene'`.
  - Tests:
    - `TestTheHeaderCheck`:
      - `test_a_rebaseline_accepts_the_same_class_at_another_logical_module`
      - `test_a_plain_replay_refuses_it_naming_the_remedy` (the message contains `REBASELINE_REMEDY`)
      - `test_a_different_qualified_name_is_refused_even_by_a_rebaseline`
    - `TestTheSceneLookup`:
      - `test_a_rebaseline_finds_the_moved_scene` (`is LayerMovedScene`)
      - `test_a_plain_replay_does_not` (`is None`)
      - `test_two_loaded_classes_of_that_name_are_still_refused`: a `type('LayerMovedScene', (Scene,), {...})`
        twin is kept referenced, and the result `is None`
    - `TestThroughTheRealGame` (`console_script='mr-muncher'`):
      - a plain replay of the renamed golden exits `ExitCode.UNUSABLE_INPUT` with
        `REBASELINE_REMEDY` in stdout
      - a rebaseline exits `SUCCESS` with `'no frames differ'`, every name in NEW is
        `CURRENT_NAME`, and NEW then replays strictly with `SUCCESS`
      - a different qualified name exits `UNUSABLE_INPUT` and NEW is not written
- [ ] **Step 2: Run them; they fail.** Run `uv run pytest --dummy-only --no-cov -q tests/replay/test_rebaseline_across_logical_modules.py`.
  Expected:
  - The "accepts/finds/converts" tests fail (refused, or `None`).
  - The plain replay's message lacks the remedy ("refusing to replay it").
  - The ambiguity and different-name tests already pass.
- [ ] **Step 3: Implement.**
  - `check_recorded_game`'s logical-name branch splits each logical name into module and
    qualified name. When the qualified names are equal and the modules differ, it raises
    `ReplayRefusedError` naming `REBASELINE_REMEDY`, unless
    `modules_not_compared(recorded_module=..., loaded_module=..., is_rebaseline=...)`. A
    different qualified name keeps today's refusal.
  - `find_scene_class`'s logical `matches_by_name` filters `named_alike` by
    `modules_not_compared(recorded_module=logical_module, loaded_module=logical_module_name(module=scene_class.__module__), is_rebaseline=is_rebaseline)`.
  - Docstrings:
    - `modules_not_compared`: "the one rule for every record a game or scene is found by: an
      old-format record gives its module, a newer one its logical module".
    - Rule 17 in `driver.py` and the rule list in `rebaseline.py` gain: "a recording whose
      classes moved to another logical module is converted the same way; a plain replay refuses
      it, naming the rebaseline".
- [ ] **Step 4: Lint, then run every replay test.**
  - Lint: `uv run --extra dev nox -s format-code lint-code`, `uv run basedpyright`,
    `uv run --extra dev nox -s static-analysis-ty`.
  - Tests: `uv run pytest --dummy-only -q tests/replay tests/world src/games`.
  - Expected: PASS. Every golden replay passes, and Mr. Muncher's `TestRecordingsMadeBeforeLogicalNames`
    (`src/games/mr-muncher/tests/test_logical_names_after_the_move.py:68`) is unchanged.
- [ ] **Step 5: Commit** — "--rebaseline converts a recording whose classes moved to another
  logical module". The hook measures this commit, because `src/` changed.

### Task 2: The engine stops pointing into Bitmappy or its sprites

**The survey (2026-10-26):**
- `api/`, `services/` and `ai/*.py` import nothing from Bitmappy; they stay in the engine. The
  only mention is a comment at `ai/sprite_generator.py:192`.
- Bitmappy imports no engine-private name and uses no `..` relative import.

**What points into Bitmappy, all fixed here before anything moves:**
1. `sprites/animated.py:256-277` imports `detect_file_format` from `glitchygames.bitmappy`, with
   an ImportError fallback; after the move the fallback would run silently. Its docstrings at
   :1278, :1807 and :1955 name `glitchygames.bitmappy.utils.detect_file_format()`.
   - Bitmappy's function (`bitmappy/utils.py:9-28`: `'toml'` for `.toml` or no extension,
     `ValueError` otherwise) moves to `glitchygames/sprites/file_format.py`, and Bitmappy imports
     it from there.
   - The engine's different `SpriteFactory.detect_file_format` (`sprites/factory.py:74-88`) stays
     as it is. Unifying the two is out of scope; note it in `plans/future-work.md`.
2. **The `example:`/`examples:` file-name prefix is removed** (the user, 2026-10-26: "We
   shouldn't treat examples specially anymore"; open question 8). Today `ui/dialogs.py` has:
   - `_process_example_filename` (:31-66), which strips the prefix
   - `_get_examples_dir` (:69-87), which builds `examples/resources/sprites` plus a `_MEIPASS` twin
   - `_get_save_path` (:90) and `_get_load_path` (:113), which send a prefixed name there

   Both helpers are deleted. `_get_save_path(filename: str) -> Path` and
   `_get_load_path(filename: str) -> Path` return `Path(filename.strip())`: surrounding whitespace
   is still trimmed, as today; that is not about examples. A name such as `examples:heart.toml` is
   an ordinary file name, used as given. The dialogs gain no new parameter, and Bitmappy passes
   nothing. Bitmappy's sprite library stays its AI training data (`SPRITE_CONFIG_DIR`,
   `sprite_inspection.py`), opened like any other file.
3. `bitmappy/editor_setup.py:91` finds the engine's `raspberry.toml` through
   `resource_path('glitchygames', 'assets', ...)`, which resolves from Bitmappy's own file. It
   becomes `ASSET_PATH / 'raspberry.toml'` (`from glitchygames.engine import ASSET_PATH`).
   `scripts/compound_sprite.py:14,71` does the same.
4. Engine tests read sprite data from `src/glitchygames/examples/resources/sprites/`:
   - `colors.toml`: `tests/animation/test_animation_hardware.py:45`,
     `test_animation_system_audit.py:36`, `test_animation_timing.py:32`
   - `static.toml`: `tests/benchmarks/test_benchmarks.py:34`, `tests/sprites/test_sprite_animation.py:31`
   - `girl.toml`: `tests/sprites/test_animated_sprite.py:3165`

   Copies go to `tests/fixtures/sprites/`, the engine's own test data; Bitmappy keeps its whole
   library. Check first that no layout guard forbids a root `tests/fixtures/` (Drawing Fire's
   move emptied it).
5. `src/glitchygames/assets/bitmappy.png` is unreferenced and a byte-for-byte duplicate of
   Bitmappy's own `resources/bitmappy.png`. After `shasum` confirms they are still equal, it is
   `git rm`'d (open question 1). Bitmappy's copy moves with it in Task 4. Also fix the comment in
   `scripts/build_browser_bundle.py:87`, which calls it Bitmappy's.
6. Comments: `sprites/frame.py:143` names `glitchygames/bitmappy/animated_canvas.py`. Say what it
   means without the engine path.

**Files:**
- Create: `src/glitchygames/sprites/file_format.py`, `tests/sprites/test_file_format.py`,
  `tests/fixtures/sprites/{colors,static,girl}.toml`
- Modify: `src/glitchygames/sprites/animated.py`, `src/glitchygames/sprites/frame.py`,
  `src/glitchygames/ui/dialogs.py`, `src/glitchygames/bitmappy/{utils,editor_setup}.py`,
  `scripts/compound_sprite.py`, `tests/ui/test_dialogs.py` (`TestGetExamplesDir` :440, the
  save/load tests :460-500, the load-dialog test :905-919), and the six sprite-reading tests above
- Delete: `src/glitchygames/assets/bitmappy.png` (the duplicate; open question 1)
- Test: `tests/sprites/test_file_format.py`, `tests/ui/test_dialogs.py`, a guard in
  `tests/test_workspace_config.py`

**Interfaces:**
- Produces:
  - `glitchygames.sprites.file_format.detect_file_format(filename: str) -> str`
  - `_get_save_path(filename: str) -> Path` and `_get_load_path(filename: str) -> Path`
    (no prefix handling). `_process_example_filename` and `_get_examples_dir` are deleted.
    `LoadDialogScene`/`SaveDialogScene` signatures don't change.
  - the guard `engine_files_pointing_into_bitmappy(*, project_root: Path) -> list[str]`, built on
    `tests/ast_scanning.py` (`import_bindings`, `scanned_source_files`)

- [ ] **Step 1: Write the failing tests.**
  - In `test_file_format.py`:
    - `test_toml_and_bare_names_are_toml` (parametrized over `ball.toml`, `BALL.TOML`, `ball`)
    - `test_another_format_is_refused_by_name` (`ValueError` matching `Unsupported file format: \.yaml`)
    - `test_the_engine_reaches_no_bitmappy_module` (`animated.detect_file_format is detect_file_format`)
  - In `test_dialogs.py`, the `_process_example_filename` tests (:407-440), `TestGetExamplesDir`
    (:440) and the example-path tests (:460-500) are replaced by `TestFileNames`:
    - `test_a_plain_name_is_used_as_it_is`
    - `test_surrounding_whitespace_is_trimmed`
    - `test_an_examples_prefix_is_not_special`: `_get_load_path('examples:heart.toml') == Path('examples:heart.toml')`,
      and the same for save
  - The load-dialog test (:905-919) loads a sprite copied into `tmp_path` by its path.
  - In `test_workspace_config.py`, `test_the_engine_outside_bitmappy_points_nowhere_into_it`:
    no engine `.py` file outside `bitmappy/` imports `glitchygames.bitmappy` or contains
    `'examples', 'resources', 'sprites'`.
- [ ] **Step 2: Run them; they fail.** The failures name `file_format`; the prefix test finds the
  prefix stripped; the guard lists `animated.py` and `dialogs.py`.
- [ ] **Step 3: Implement** items 1-6. Use `cp` for the fixtures. Drop each sprite test's
  `ENGINE_PACKAGE_DIRECTORY` import where nothing else in the file uses it.
- [ ] **Step 4: Lint, then run**
  `uv run pytest --dummy-only -q tests/sprites tests/ui tests/tools tests/animation tests/benchmarks tests/test_workspace_config.py`.
- [ ] **Step 5: Commit** — "The engine stops pointing into Bitmappy: its format check, no
  examples: prefix in the dialogs, raspberry through ASSET_PATH".

### Task 3: Every Bitmappy test gathered in `tests/tools/`

Seven engine test files outside `tests/tools/` test Bitmappy (survey, 2026-10-26, verified). After
this task, `tests/tools/` holds Bitmappy's tests plus three of the engine's (`test_charmap.py`,
`test_terminal_utils.py`, `test_ascii_renderer.py`), so Task 4 moves one directory's worth.

| File | What moves | To |
|---|---|---|
| `tests/test_film_strip_frame_addition.py` | all | `tests/tools/test_film_strip_frame_addition.py` |
| `tests/canvas/test_animated_canvas.py` | all | `tests/tools/test_animated_canvas.py` |
| `tests/events/test_on_load_file_event.py` | all | `tests/tools/test_on_load_file_event.py` |
| `tests/events/test_voice.py` | the editor-scene fixture (:1447-1456), `TestBitmapEditorSceneVoiceIntegrationNegative` (:1484), `...Positive` (:1523) | `tests/tools/test_bitmappy_voice.py` |
| `tests/fonts/test_font_manager.py` | `TestBitmappyFonts` (:526) | `tests/tools/test_bitmappy_fonts.py` |
| `tests/engine/test_engine_initialization.py` | `test_bitmappy_gets_engine_default` (:373) and its import (:23) | `tests/tools/test_bitmappy_engine_defaults.py` |
| `tests/benchmarks/test_benchmarks.py` | `TestControllerSelectionBenchmarks` (:199), `TestVisualCollisionBenchmarks` (:260) | `tests/tools/test_bitmappy_benchmarks.py` |

Also in this task:
- **Delete the `sys.path.insert(...)` lines** (Review Focus 2) in:
  - `tests/tools/test_animated_canvas_sprite.py:16`
  - `test_bitmappy_multi_controller_enhancements.py:12`
  - `test_frame_copy_paste.py:16`
  - `test_pixel_saving.py:7`

  Nothing needs them, since the tests import the installed packages.
- **`performance-test` runs every testpath.** `noxfile.py:1290-1307` passes `'tests/'`, so
  Bitmappy's benchmarks would stop running once they move. Drop that argument.

**Files:** the table's files; `noxfile.py` (`performance_test`); `tests/test_ci_config.py`;
a guard in `tests/test_suite_collection.py`.

**Interfaces:**
- Produces: `bitmappy_test_imports_outside_tools(*, project_root: Path) -> list[str]`. Task 4
  replaces it with "no engine test imports `bitmappy`".

- [ ] **Step 1: Write the failing tests.**
  - `test_bitmappys_tests_are_all_in_tests_tools`: the helper returns `[]`.
  - `test_the_performance_session_benchmarks_every_testpath`: call `noxfile.performance_test(session)`
    directly, as `tests/test_ci_config.py` already calls `docs_deploy`/`replay_metrics`
    (:112, :129), not through `.func`. Assert the pytest call names no directory.
- [ ] **Step 2: Run them; they fail** (the seven files are listed, and the session passes `'tests/'`).
- [ ] **Step 3: Move.**
  - `git mv` the three whole files.
  - Cut the four partial files into their new files. Each gets the docstring "Bitmappy's
    <subject> (split from tests/<file>; they move with Bitmappy)." and copies the imports and
    fixtures it uses.
  - Remove imports the engine files no longer use.
  - Delete the four `sys.path.insert` lines.
  - Edit `performance_test`.
- [ ] **Step 4: Lint, then run.**
  - First save `uv run pytest --collect-only -q | tail -1` on `HEAD` to the scratchpad.
  - Run the suite: `uv run pytest --dummy-only -q tests/tools tests/events tests/fonts tests/engine tests/benchmarks tests/canvas tests/test_suite_collection.py tests/test_ci_config.py`.
  - Collect again and compare: expected PASS with the same number of test ids as before.
- [ ] **Step 5: Commit** — "Bitmappy's tests gathered in tests/tools; performance-test
  benchmarks every testpath". There's no measured path, so no measurement.

### Task 4: Move Bitmappy into `src/apps/bitmappy/`

Bitmappy moves whole:

| What | From | To | Size |
|---|---|---|---|
| The package | `src/glitchygames/bitmappy/` | `src/apps/bitmappy/bitmappy/` | 48 modules, 31,497 lines, plus `resources/bitmappy.cfg` and `resources/bitmappy.png` |
| The sprite library (AI training data and the `examples:` files; master plan decision 5) | `src/glitchygames/examples/resources/sprites/` | `src/apps/bitmappy/bitmappy/resources/sprites/` | 71 TOMLs |
| The tests | `tests/tools/` (all but `__init__.py` and the three engine files) | `src/apps/bitmappy/tests/` | about 62,300 lines, rootless |

Code and imports:
- **The sprite library path:** `SPRITE_CONFIG_DIR = Path(__file__).parent / 'resources' / 'sprites'`.
  `resource_path` and its `_MEIPASS` branch go. That works because PyInstaller sets a bundled
  module's `__file__` under `_MEIPASS`, which `fonts/font_manager.py:80` already relies on.
- **AI worker:** it starts by import (`ai_manager.py:167-168`), so no module string changes.
- **Imports into the moved test helper:** `from tests.tools.test_film_strip_base import ...` (12
  files) becomes `from test_bitmappy_film_strip_base import ...`. Rootless tests put their own
  directory on `sys.path`, and the name is unique.

Recordings: none of the 11 committed `*.jsonl.gz` is of Bitmappy, so there is no
`RECORDING_PATH_RENAMES` line. The logical name becomes `apps.bitmappy.editor:BitmapEditorScene`.

**Files:**
- Move:
  - the package, the sprite library, and `tests/tools/conftest.py` with every Bitmappy test (above)
  - `TestExamplesSprites` and `_load_example_sprite`, cut from `tests/examples/test_examples_sprites.py`
    into `src/apps/bitmappy/tests/test_bitmappy_sprite_library.py`, reading
    `bitmappy.SPRITE_CONFIG_DIR`, with the missing-directory `pytest.skip` branches gone

  `tests/examples/test_examples_sprites.py` itself **stays**: Papyrus imports it
  (`src/games/brave-adventurer/tests/papyrus/test_brave_adventurer_papyrus_sprite_files.py:14`),
  and Part 3 owns `tests/examples/`.
- Create: `src/apps/bitmappy/pyproject.toml`, `src/apps/bitmappy/README.md`,
  `src/apps/bitmappy/tests/test_bitmappy_after_the_move.py`
- Modify:
  - `src/apps/bitmappy/bitmappy/{utils,__init__,sprite_inspection,editor_setup}.py`, and the
    tests of `resource_path` (`test_bitmappy.py:35,349`, `test_bitmappy_additional.py:56,1480-1496`,
    `test_bitmappy_state.py:22-48`); the `SPRITE_CONFIG_DIR` patches at `test_bitmappy.py:608-636`
    keep working
  - `test_bitmappy_packaging.py`: `SPEC_PATH`/`ENTRY_POINT_PATH` from
    `PROJECT_ROOT = Path(__file__).resolve().parents[4]`, no longer relative to the working
    directory
  - `bitmappy.spec` `datas` (:45, :47): one entry,
    `('src/apps/bitmappy/bitmappy/resources', 'bitmappy/resources')`; its docstring paths follow
  - `scripts/bitmappy_entry.py:19` (`from bitmappy import main`); `scripts/ai_query_inspector.py:19-28`
    (import `bitmappy`, and drop its `sys.path.insert`); `scripts/compound_sprite.py`;
    `scripts/audit_hitboxes.py:66` (`PRIORITY_TIERS[2]`)
  - `scripts/build_browser_bundle.py`:
    - `EXCLUDED_SUBPACKAGES` (:86) loses `'bitmappy'`
    - `GameSpecification.included_subpackages` (:113, :127) and its use at :561 are deleted
    - `GAMES['bitmappy']` (:290-297) becomes `module='bitmappy.editor'`,
      `member_packages=('bitmappy',)`; its comment names `bitmappy.constants.AI_FEATURES_ENABLED`
  - `tests/test_build_browser_bundle.py`:
    - the `is_bundled` cases (:65, :88) use another excluded subpackage (`api/main.py`)
    - :124 and :382 follow
    - `test_only_the_bitmappy_bundle_holds_the_editor` (:409) asserts `bitmappy/editor.py` is in
      `bitmappy.zip`, and that no `glitchygames.zip` holds `bitmappy/`
    - :440-446 expects Bitmappy to ship `glitchygames.zip` **and** `bitmappy.zip`
  - `tests/test_logical_names.py:68-75`: the expected dict gains `'bitmappy': 'apps'`
  - `tests/test_workspace_packages.py:202-224`: the `ENGINE_EXAMPLES_AFTER_PART_2` comment and
    docstring no longer say "Bitmappy's resources"; `'resources'` stays (it still holds `snd/`)
  - `tests/test_suite_collection.py`: Task 3's guard becomes `test_no_engine_test_imports_bitmappy`
  - `src/glitchygames/logical_names.py:30-39`: `MEMBER_LAYERS` gains `'bitmappy': 'apps'`
  - `src/glitchygames/examples/__init__.py:1` (its docstring stops naming Bitmappy's resources)
  - `.gitignore:193-194`
  - Every root configuration file (Step 3)

**Interfaces:**
- Consumes: Task 1 (a pre-move recording converts), Task 2 (no engine module points into
  Bitmappy), Task 3 (its tests are in one place).
- Produces:
  - `import bitmappy`, with `bitmappy = "bitmappy:main"` in the member's `pyproject.toml`
  - `MEMBER_LAYERS['bitmappy'] == 'apps'`
  - `bitmappy.SPRITE_CONFIG_DIR == Path(bitmappy.utils.__file__).parent / 'resources' / 'sprites'`
  - `GAMES['bitmappy'].member_packages == ('bitmappy',)`
  - `GameSpecification` with no `included_subpackages` field

- [ ] **Step 1: Write the failing tests.** These are written after Step 2 creates the directory,
  and must fail before Step 3 wires the member.
  - `test_bitmappy_after_the_move.py`:
    - `test_the_editor_is_named_in_the_apps_layer`:
      `logical_name(scene_class=BitmapEditorScene) == 'apps.bitmappy.editor:BitmapEditorScene'`
      and `BitmapEditorScene.__module__ == 'bitmappy.editor'`
    - `test_the_old_engine_package_is_gone`: `find_spec('glitchygames.bitmappy') is None`
    - `test_bitmappy_is_imported_from_its_member`
    - `test_the_sprite_library_is_package_data`: 71 TOMLs under `SPRITE_CONFIG_DIR`, which is
      under the package
    - `test_the_sprite_library_ships_in_its_wheel`:
      `uv build --package bitmappy --wheel --out-dir tmp_path`, as Drawing Fire's
      `test_the_soldier_sprite_ships_in_its_wheel` does; the wheel lists
      `bitmappy/resources/sprites/` (71 files), `bitmappy/resources/bitmappy.cfg` and
      `bitmappy.png`, and only the `bitmappy` package
    - `test_the_ai_worker_target_is_importable_by_name`
  - In `test_bitmappy_packaging.py`: `test_the_spec_bundles_the_resources_where_bitmappy_reads_them`.
    The `datas` destination covers `SPRITE_CONFIG_DIR` relative to the package's parent; read the
    spec with `ast`.
  - In `tests/test_suite_collection.py`: `test_no_engine_test_imports_bitmappy`. No file under
    the root `tests/` imports a module whose top level is `bitmappy`.
  - In `tests/test_suite_collection.py`: `test_bitmappys_test_modules_are_named_for_it`. Every
    `*.py` in `src/apps/bitmappy/tests/` other than `conftest.py` matches `test_bitmappy*.py`.
- [ ] **Step 2: Move and rewrite references.**
  ```bash
  mkdir -p src/apps/bitmappy/tests
  git mv src/glitchygames/bitmappy src/apps/bitmappy/bitmappy && rm -rf src/glitchygames/bitmappy
  git mv src/glitchygames/examples/resources/sprites src/apps/bitmappy/bitmappy/resources/sprites
  git mv tests/tools/conftest.py src/apps/bitmappy/tests/conftest.py
  # every tests/tools/test_*.py but test_charmap.py, test_terminal_utils.py, test_ascii_renderer.py
  ```
  Then name every moved test module explicitly (decided, open question 3), with `git mv` so
  history follows:
  - `test_<rest>.py` becomes `test_bitmappy_<rest>.py`, unless it already starts with
    `test_bitmappy` (`test_bitmappy.py` and `test_bitmappy_*.py` keep their names).
  - Print the old and new names, and check that no new name collides with an existing one.

  Then rewrite references with `perl -pi -e`, over `git grep -l` excluding history:
  - `\bfrom glitchygames import bitmappy\b` becomes `import bitmappy`
  - `\bglitchygames\.bitmappy\b` becomes `bitmappy`; this covers about 100 `mocker.patch`
    strings and about 90 self-imports
  - `src/glitchygames/bitmappy/` becomes `src/apps/bitmappy/bitmappy/`
  - `\btests\.tools\.test_film_strip_base\b` becomes `test_bitmappy_film_strip_base`
  - `(src/)?glitchygames/examples/resources/sprites\b` becomes `src/apps/bitmappy/bitmappy/resources/sprites`

  Read the whole diff. `bitmappy_sprite`, `BitmappySprite` and `BitmappyLegacySprite` must be
  untouched. `tests/tools/__init__.py` stays, for the engine's three tests.
- [ ] **Step 3: Wire the member and the `apps` layer.**
  - **`src/apps/bitmappy/pyproject.toml`:** Drawing Fire's shape (`version = "1.0.0"`,
    `requires-python = ">=3.14,<4.0"`, hatchling, `packages = ["bitmappy"]`,
    `[tool.uv.sources] glitchygames = { workspace = true }`, `[project.scripts] bitmappy = "bitmappy:main"`).
    `dependencies` per open question 2.
  - **`README.md`:** one paragraph, as the recipe says (what it is; `uv run bitmappy`;
    `uv run pytest --no-cov src/apps/bitmappy/tests`; `nox -s build-binary`;
    `nox -s browser -- bitmappy`; `docs/architecture/bitmappy.md`).
  - **Root `pyproject.toml`:**
    - delete `bitmappy = "glitchygames.bitmappy:main"` (:53)
    - `apps = ["bitmappy"]` (:110)
    - `members`, `[tool.uv.sources]` and the dev group gain the member
    - `testpaths` gains `src/apps/bitmappy/tests`; `addopts` gains `--cov=bitmappy`
    - coverage `source` gains `"bitmappy"`; `paths` gains `bitmappy = ["src/apps/bitmappy/bitmappy", "*/site-packages/bitmappy"]`
    - ruff `src` gains the member and its tests; `include` gains `src/apps/bitmappy/**/*.py`;
      `namespace-packages` gains its tests
    - a new per-file-ignores key `"src/apps/*/tests/**/*.py"`, exactly equal to `tests/**/*.py`'s
    - isort `known-first-party` gains `bitmappy`
    - ty `root`, `src.include` and `src.exclude` (`src/apps/*/tests`)
    - deptry `known_first_party` gains `bitmappy`; `extend_exclude` gains `"src/apps"`
    - `tenacity` per open question 2
  - **`pyrightconfig.json`:**
    - `include` gains `src/apps/bitmappy`
    - every tests environment's `extraPaths` gains `src/apps/bitmappy`
    - a `src/apps/bitmappy/tests` environment (a copy of `tests` minus `root`), placed **before**
      `{"root": "src/apps/bitmappy", "extraPaths": ["src"]}`
  - **`noxfile.py`:** `_CODE_DIRS`, `_SOURCE_PACKAGE_DIRS`, and `_MEMBER_DISTRIBUTIONS` (in
    workspace order; it is what makes the binary's venv reinstall Bitmappy).
  - **`wily.cfg`:** `path` gains it.
  - **`mkdocs.yml`:** mkdocstrings `paths` gains `src/apps/bitmappy`, and a nav section
    "Apps API Reference" with `bitmappy: "bitmappy/index.md"`.
  - Then `uv lock` (read its diff: only the new member, and `tenacity` moving) and
    `uv sync --all-extras --all-groups --all-packages`.
- [ ] **Step 4: Lint, run, run as nox does.**
  - `uv run --extra dev nox -s format-code lint-code lint-dependencies lint-dead-code`
  - `uv run basedpyright`
  - `uv run --extra dev nox -s static-analysis-ty`
  - `uv run pytest --dummy-only --no-cov -q src/apps/bitmappy/tests tests/tools tests/sprites tests/ui tests/examples tests/test_build_browser_bundle.py tests/test_suite_collection.py tests/test_workspace_config.py tests/test_workspace_packages.py tests/test_logical_names.py tests/test_engine_doors.py tests/test_code_tree.py tests/engine src/games/brave-adventurer/tests/papyrus`
  - `uv run --extra dev nox -s lint-docs`. The new generated page renders all 48 modules under
    `--strict` for the first time; fix any docstring warning in the module itself, never by
    configuration.
  - `CI=true uv run --extra dev nox -s test`

  Expected: PASS at 100% coverage.
- [ ] **Step 5: Commit** — "Bitmappy is its own app: src/apps/bitmappy, its sprite library as
  package data". Before committing, `git status --short | grep '^??'` must print nothing under
  `src/`.

### Task 5: `nox -s build-wheel` builds every workspace package

`_build_wheel` (`noxfile.py:1425-1427`) runs `uv build --wheel --out-dir dist`, which builds the
root project only, so no member has a wheel from the documented command. The user decided to fix
it here (open question 5).

**Files:**
- Modify: `noxfile.py` (`_build_wheel`), `tests/test_ci_config.py`

**Interfaces:**
- Produces: `_build_wheel` runs `uv build --all-packages --wheel --out-dir dist`. Its docstring:
  "Build the engine's wheel and every workspace member's with uv build".

- [ ] **Step 1: Write the failing test.** `test_the_wheel_build_builds_every_workspace_package`:
  `noxfile._build_wheel(session)` with a `mocker.Mock()` session.
  `session.run.assert_called_once_with('uv', 'build', '--all-packages', '--wheel', '--out-dir', 'dist', external=True)`.
  Check how `_build_wheel` calls `session.run` today, and match its `external` argument.
- [ ] **Step 2: Run it; it fails** (no `--all-packages`).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the test, then the real build.** `rm -rf dist && uv run --extra dev nox -s build-wheel`,
  then list each wheel's top-level entries:
  `for wheel in dist/*.whl; do echo "$wheel"; unzip -l "$wheel" | awk 'NR>3 {print $4}' | cut -d/ -f1 | sort -u; done`.
  Expected:
  - one wheel per workspace package: the engine plus each member in the workspace's `members`
    (today five games and Bitmappy)
  - the engine's wheel has only `glitchygames` and its dist-info at the top level: no `bitmappy`,
    no game package
  - Bitmappy's wheel has `bitmappy/` with `resources/sprites/`
  - Drawing Fire's has `sprites/soldier.toml`; PaddleSlap's has `demos/rally.jsonl.gz`
- [ ] **Step 5: Commit** — "nox -s build-wheel builds every workspace package's wheel". There's
  no measured path, so no measurement.

### Task 6: Docs

**Files:**
- `docs/architecture/bitmappy.md`: its package, its sprite library (AI training data, package
  data), that the `examples:` prefix is gone (files are opened by their path), and its logical
  name.
- `plans/2026-10-24-workspace-packages.md` decision 5 mentions the `examples:` prefix: add a dated
  note that the user removed it on 2026-10-26. A pre-move recording is refused by a plain replay, which names the remedy, and
  converted by `--replay-trace OLD --rebaseline NEW --headless`.
- `docs/architecture/gameplay_replay.md`: Task 1's rule, for any class that moved to another
  logical module.
- `docs/architecture/game_packages.md`:
  - :16-20, the layout: `examples/` now holds only the demos
  - a special case for a member that was never in a layer (its logical name changes; Task 1)
  - "Apps API Reference"
- `docs/architecture/argument_system.md:266`, `docs/multi_controller_system.md:20-24,42-43`
- `CLAUDE.md`: the Bitmappy section's paths (:966-980), :136, :154-177, and `performance-test`
  over every testpath
- `README.md`, `BITMAPPY_ARCHITECTURE.md`, `LOADER_README.md:43,66,434`, `CONTROLLER_CONTROLS_README.md:22`
- `src/glitchygames/ai/README.md:257-258`, `src/glitchygames/ai/INTEGRATION.md:153-154,175`
- `plans/2026-10-24-workspace-packages.md`:
  - Part 4 DONE, with its commit range and this plan's link
  - Part 2's stale "not yet merged" corrected (it merged as #109)
  - the Part 4 outline's "Ends with `src/glitchygames/examples/` gone" moved to Part 3
- `plans/future-work.md`: the two `detect_file_format` functions
- `CLAUDE.md` and `docs/architecture/game_packages.md`: `nox -s build-wheel` builds every
  package's wheel (Task 5)
- BUGS.md stays history. Don't rewrite its paths.

- [ ] **Step 1: Write the docs.**
- [ ] **Step 2: Build strictly.** Run `uv run --extra dev nox -s lint-docs`, then
  `uv run pytest --dummy-only --no-cov -q tests/test_suite_collection.py`; the living-docs path
  guard scans CLAUDE.md, README.md, `*_README.md`, BITMAPPY_ARCHITECTURE.md, `docs/**` and the
  living plans.
- [ ] **Step 3: Commit** — "Docs: Bitmappy is an app".

### Task 7: Whole-branch verification

- [ ] **Step 1:** `uv run --extra dev nox -s lint static-analysis` passes.
- [ ] **Step 2:** `CI=true uv run --extra dev nox -s test`, then `uv run pytest` (both drivers).
  Expected: 100% coverage, with `src/apps/bitmappy/bitmappy/` in the report and no driver
  differences.
- [ ] **Step 3:** `uv build --package bitmappy --wheel --out-dir <scratch>`. The wheel holds only
  `bitmappy/`, with `resources/`. The engine's wheel (`uv build --wheel`) holds no `bitmappy/` and
  no sprite library.
- [ ] **Step 4:** `uv run python -m scripts.build_browser_bundle bitmappy --output <scratch>`. Its
  `pyscript.toml` lists `glitchygames.zip` and `bitmappy.zip`. Then `nox -s browser -- bitmappy`
  serves it; the user opens it, and Bitmappy starts with AI features off.
- [ ] **Step 5:** `nox -s build-binary`. The user starts `dist/bitmappy`, loads a sprite by its
  path (for example `src/apps/bitmappy/bitmappy/resources/sprites/heart.toml`), starts one AI
  request (if a key is configured; it reads the sprite library as training data), and quits; it
  exits cleanly.
- [ ] **Step 6:** `uv run bitmappy` from the editable install: load, draw, save, quit.
- [ ] **Step 7:** Update this plan's Status (DONE, with its commit range) and write any finding
  into BUGS.md. Stop for the user's review before pushing or opening the PR.
