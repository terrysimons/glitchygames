# Games as Their Own Packages

A GlitchyGames game, demo or app can live in its own package beside the engine: a
[uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) member under `src/`,
depending on `glitchygames` like any third-party game would. This page explains what a member
is, how to work with one, and how to move a game out of the engine into one. The why and the
order of the moves are in the plan, `plans/2026-10-24-workspace-packages.md`.

## The layout

Four layers, all under `src/`:

```
src/
  glitchygames/        the engine (distribution glitchygames); it has no examples package:
                       every game and demo is a member, and its resources/ holds only what the
                       engine itself ships
  games/<game>/        one member per game: every game (mr-muncher, clockwork-keep,
                       brave-adventurer, paddleslap, drawing-fire)
  demos/<demo>/        one member per demo (dt-demo, joystick-demo, text-input-demo): a small
                       program that shows one engine feature (console scripts `dt-demo`,
                       `joystick-demo`, `text-input-demo`; no browser build)
  apps/<app>/          one member per application (Bitmappy)
tests/                 the engine's own tests
scripts/               tools
```

Nothing at the repository root is importable as one of our packages. Tests and tools run from
the root import the installed engine and members (`uv sync` installs them editable, nox
non-editable), and `tests/test_suite_collection.py` checks that `import glitchygames` resolves to
the installed package. Coverage maps the installed copies back to `src/`
(`[tool.coverage.paths]`), so its report names the files in the repository.

### Two meanings of "demo"

- A **demo** (a demos-layer member): a program under `src/demos/<demo>/`, run with its console
  script or `python -m <package>`. It is code.
- A game's **bundled demo recording**: `<package>/demos/<name>.jsonl.gz`, package data inside a
  game (PaddleSlap's `rally.jsonl.gz`), replayed by that game's console script. It is data, and
  `glitchygames.bundled_demos` finds it (see "Bundled demos" below).

A `demos` directory inside a package is therefore never a demos-layer member, and a demos-layer
member's recordings (it has none today) would still be that member's own package data.

## What a member is

A member is a directory under its layer, named after its distribution (with hyphens), holding:

```
src/games/<game>/
  pyproject.toml       its metadata (below)
  README.md            one paragraph: what it is, how to play and test it
  src/<package>/       its import package (underscores: a hyphen cannot be imported), never at
                       the member's root, so nothing in the member directory can be imported by
                       accident in place of the installed package
  tests/               its tests (no __init__.py), with its golden replay in
                       tests/fixtures/replays/golden.jsonl.gz
```

Its `pyproject.toml` follows Mr. Muncher's (`src/games/mr-muncher/pyproject.toml`):

```toml
[project]
name = "<distribution>"
version = "1.0.0"
description = "<one line>"
requires-python = ">=3.14,<4.0"
dependencies = ["glitchygames"]

[project.scripts]
<console-script> = "<package>:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/<package>"]

[tool.uv.sources]
glitchygames = { workspace = true }
```

A member that reuses another member's code depends on it too
(`dependencies = ["glitchygames", "<other>"]`, `<other> = { workspace = true }`). Files inside
the import package (a sprite TOML, a bundled demo) ship as package data: read them through the
module's own path (`Path(__file__).parent / 'sprites'`), never through the repository.

## Working with a member

From the repository root:

```bash
uv sync --all-extras --all-groups --all-packages   # the engine and every member, with the dev tools
uv run <console-script>                            # play it
uv run pytest --no-cov src/games/<game>/tests      # its tests alone (no coverage gate on a subset)
uv run pytest                                      # everything: the engine's and every member's tests
```

A plain `uv sync` keeps every member installed (each is in the root's `dev` dependency group),
but drops the dev tools: use the full command above. The 100% coverage gate covers the engine
and every member together, so it is met only by the whole run.

Each layer is also an extra of the engine, naming that layer's members, so an installer picks
the engine alone or with them:

```bash
uv build --all-packages                                    # every wheel, into dist/
                                                           # (nox -s build-wheel does the same)
pip install --find-links dist glitchygames                 # the engine
pip install --find-links dist "glitchygames[games]"        # the engine and every game
pip install --find-links dist "glitchygames[demos,apps]"   # the engine, the demos and the apps
```

The names are not yet on PyPI (neither `glitchygames` nor any game's), so install from the built
wheels as above: a plain `pip install glitchygames` would fetch whatever package someone else
published under that name.

(`uv sync --extra games` does the same in the repository.) A layer with no member yet is an empty
extra; `tests/test_workspace_config.py` keeps each extra equal to its layer's members.

- **Recordings name games by logical names**: `<layer>.<module path inside the package>:<class>`
  (`games.mr_muncher.game:MrMuncherScene`). A recording therefore does not depend on where the
  code lives, and moving a game changes no recording. The layers are data in the engine,
  `src/glitchygames/logical_names.py`: `MEMBER_LAYERS` for members (kept equal to the workspace by
  `tests/test_workspace_config.py`). Every game, demo and Bitmappy is a member; the engine has no
  examples package.
- **Golden replays** live with the member's tests; the golden plugin collects them from every
  member, so the engine's `uv run pytest` replays each one.
- **The browser build** ships a member's package as its own archive (`<package>.zip`) beside the
  engine's `glitchygames.zip` (`scripts/build_browser_bundle.py`, `GameSpecification.member_packages`).
- **API reference**: `scripts/gen_ref_pages.py` writes a page per member package
  (`<package>/index.md`), listed under "Games API Reference" in `mkdocs.yml`, or under "Apps API
  Reference" for an app (Bitmappy's `bitmappy/index.md`).
- **Wheels**: `nox -s build-wheel` builds the wheel of the engine and of every member
  (`uv build --all-packages`).

## Moving a game out of the engine

Historical: every game and demo has moved out and `src/glitchygames/examples/` is gone (Part 3,
2026-10-26). A new game or demo starts as a fresh member. These steps record how the moves were
done.

The recipe Mr. Muncher's move followed (`plans/2026-10-24-workspace-packages-1-foundation.md`,
Task 9). Do one game per commit series, and verify each before the next. Every step names the
check that fails if it is skipped: `tests/test_workspace_config.py` catches a member left out of
any tool's configuration.

### 1. Move the code and tests

- `git mv src/glitchygames/examples/<package> src/games/<game>/src/<package>`, then delete what is
  left of the old directory: its git-ignored `__pycache__` would otherwise keep an importable
  namespace package there. `git mv` of a directory carries its untracked `__pycache__` along
  too: delete it in the member as well (its `.pyc` files name the old module).
- Move its tests to `src/games/<game>/tests/` with no `__init__.py` (a tests directory must not be
  a package named `tests`: `tests/test_suite_collection.py`). A member's tests directory is
  rootless, so pytest imports each test file under its bare file name: name every test file
  after the package, `test_<package>_<area>.py` (Drawing Fire's `test_drawing_fire_battle.py`, not
  `test_battle.py`), so no two test directories share a name.
  `tests/test_suite_collection.py::test_test_file_names_are_unique_across_packages` fails on a
  name used twice, naming both files; a shared helper module name can collide too (BUGS.md #31).
- A member may have a `tests/conftest.py` (Drawing Fire's drains the event queue). It is imported
  under the bare name `conftest`, replacing the root conftest in `sys.modules`, so nothing may
  `import conftest` by name: look a conftest up as pytest registered it, by its path
  (`pytestconfig.pluginmanager.get_plugin(str(pytestconfig.rootpath / 'conftest.py'))`).
- Move its golden replay to `src/games/<game>/tests/fixtures/replays/golden.jsonl.gz`, its bytes
  unchanged. Data its tests read beside them (golden sounds, for instance) moves with them.
  Delete the emptied `tests/fixtures/replays/<console-script>/` (and any parent it leaves empty:
  Drawing Fire's move emptied the root's `tests/fixtures/`).
- Rewrite `glitchygames.examples.<package>` imports to `<package>` (`git grep -l` across the
  repository, excluding `plans/`), then read the whole diff: a docstring or a path string can
  match too.

### 2. Create the member

- `src/games/<game>/pyproject.toml` (above) and `README.md`. The package's `__init__.py`
  re-exports `main`.
- The move's tests, one file per subject, each named `test_<distribution with - as _>_<subject>.py`
  (`tests/test_suite_collection.py` refuses a test file named for anything else, or a name used
  twice). A member has only the subjects it has tests for:
  - `_logical_names.py`: the game's classes keep the logical names its recordings hold (every
    member has this one);
  - `_install_location.py`: the package imports from `<member>/src/` (or `site-packages` in a
    wheel install), and (for a member that was once an example)
    `importlib.util.find_spec('glitchygames.examples')` is None, so a leftover ignored directory
    fails a test. A brand-new member, never an example, has no "old example module is gone"
    test;
  - `_wheel.py`: the member's wheel holds only its package, plus its data (sprites, demos,
    resources);
  - `_package_data.py`: the member's shipped data (a sprite library, a bundled demo) is inside the
    package, checked without building a wheel (`_wheel.py` is for the tests that build one);
  - `_entry_points.py`: the console script and `python -m <package>` resolve to `main`;
  - `_recording_history.py`: the golden's old path maps to its new one in the root
    `pyproject.toml`'s `[tool.glitchygames]` `recording-renames` (its history follows it), and so
    does every other moved recording.

  That is six subjects: logical_names, install_location, wheel, package_data, entry_points,
  recording_history. A move test outside them goes beside the member's other tests, named for its
  subject (Brave Adventurer's `tests/core/test_brave_adventurer_shared_core.py`, for example).

### 3. Register it in the root configuration

| File | What to add or change |
|---|---|
| `pyproject.toml` | Remove its console script from `[project.scripts]` (the member's own `pyproject.toml` has it now). Add the member to its layer's extra (`games`, `demos` or `apps` in `[project.optional-dependencies]`), `[tool.uv.workspace] members`, `[tool.uv.sources]`, the `dev` dependency group, pytest `testpaths`, `addopts` (`--cov=<package>`), coverage `source` and `[tool.coverage.paths]`, ruff `src`, `include` and `namespace-packages` (its tests), isort `known-first-party`, ty `root` and `src.include`, deptry `known_first_party`. Re-key any per-file ruff ignore that names the old path. |
| `pyrightconfig.json` | Add it to `include`, a tests environment (before the member's own) and the member's environment, each with the `extraPaths` Mr. Muncher's have. Every member is a src layout, so the environments name the member's `src/` (`WorkspaceMember.import_roots` in `scripts/workspace_packages.py`), as Brave Adventurer's do: that is the one form. `tests/test_workspace_config.py::test_every_member_keeps_its_packages_under_src` enforces the layout, and no configuration entry may name a member path the workspace does not derive |
| `noxfile.py` | `_CODE_DIRS`, `_SOURCE_PACKAGE_DIRS`, `_MEMBER_DISTRIBUTIONS` |
| `wily.cfg` | The `path` list |
| `mkdocs.yml` | The mkdocstrings `paths`, and its API page under "Games API Reference" |
| `uv.lock` | Regenerate: `uv lock` |

### 4. Update the engine's tables

- `src/glitchygames/logical_names.py`: add its package to `MEMBER_LAYERS`.
  Its recordings need nothing else (their logical names do not change); `tests/test_logical_names.py`
  pins both tables.
- The root `pyproject.toml`'s `[tool.glitchygames.recording-renames]`: one line per moved
  recording, old path to new, so its run-ledger history stays connected. Each lookup is one
  step: a recording that has already moved once needs a line from each of its old paths.

### 5. Update the scripts and tests that name it

- `scripts/record_golden_traces.py`: add a `'<module>:<class>'` reference to `GAME_SCENES`
  (never a module-level import of a member: the subprocess import test fails on one),
  `GAME_MODULES` (whose value is the bare package name) and its input script's builder to
  `SCRIPT_BUILDERS` (the script itself goes in `scripts/golden_inputs.py`, importing what it reads
  of its game inside the functions that read it). `scripts/record_scripted_session.py`
  derives its fixture directories from `GAME_MODULES` and the workspace
  (`REPLAY_FIXTURE_DIRECTORIES`), and refuses
  a game no member holds: only its docstring examples need editing.
- `tests/replay/test_golden_replays.py`: its imports, `GAMEPLAY_ACTION_MAPS`,
  `ENGINE_SCENE_CONTROLS`, `UNEXERCISED_CONTROLS` and any table naming the game.
- Engine tests no longer borrow a game, by import or by path: `tests/test_suite_collection.py`
  (`engine_test_imports_of_members`) fails on any root test that imports a member. Each kind of
  test lives in one place:
  - **The game's own tests** are in the member (`src/games/<game>/tests/`): its rules, sprites,
    touch controls, replays and the move's tests above. A test that only the game's code can
    answer goes there, not in `tests/`.
  - **Engine tests use stand-ins**: `tests/stand_in_harness_games.py` (games for the replay and
    harness tests) and `tests/stand_in_games.py` (games and distributions for the discovery,
    replay-plugin and playback tests). A test that needs a game, a root-layout example or several
    console scripts writes or imports a stand-in; it never imports a member.
  - **Cross-member tests discover through the workspace** (`scripts/workspace_packages.py`) and
    assert hand-written expectations in `tests/workspace_expectations.py`
    (`EXPECTED_GOLDENS`, `EXPECTED_GAME_CONSOLE_SCRIPTS`, `EXPECTED_ALL_CONSOLE_SCRIPTS`,
    `EXPECTED_BUNDLED_DEMOS`). They are
    written out on purpose, because an expectation derived from the thing it checks checks
    nothing. **Edit them when a game, golden, bundled demo or console script is added or
    removed.** Also add the game to the control tables in
    `tests/replay/golden_replay_controls.py`, and to
    `tests/replay/test_record_scripted_session.py::test_a_member_games_fixture_is_directly_in_the_members_replay_fixtures`.
  - **The exemptions** (`MEMBER_IMPORT_EXEMPT_MODULES` and `MEMBER_IMPORT_EXEMPT_NAMES` in
    `tests/test_suite_collection.py`, each with its reason; a stale one fails): the module
    `tests/replay/golden_replay_controls.py`, whose per-game control tables are cross-member
    infrastructure moved there unchanged, and the eleven named imports in
    `tests/world/test_golden_traces.py`, whose per-game world rules measure the games' own
    drawings and players. Nothing else in `tests/` may import a member.
- Every game is a member now (Drawing Fire, the last in the engine's examples, moved), so no
  game is a root-layout example any more. The root's `fixtures/replays/<console-script>/` layout
  stays only as the replay plugin's layout for other projects; the tests of it
  (`tests/replay/test_replay_plugin.py`, `tests/replay/test_golden_replays.py`,
  `tests/test_code_tree.py`, `tests/test_measure_staged_replays.py`) use stand-ins: a `tmp_path`
  path, a stand-in installed distribution, a pytester copy. A new game or demo starts as a
  member; a test that needs a root-layout or several-console-script example writes one.
- Paths built with `/` (`... / 'fixtures' / 'replays' / '<game>' / ...`) escape the grep below:
  also grep for `'<console-script>' /` and `/ '<console-script>'`.
- `git grep` for the old package path and the old golden path across the repository: engine tests
  that borrow a game (a collision test using its sprites), benchmarks reading its golden, scripts
  importing it. Point each at the member, or move the test into the member when it is really the
  game's. Once done, the only matches left are on purpose:

  ```bash
  git grep -n \
      "glitchygames.examples.<package>\|fixtures/replays/<game>" \
      -- ':!plans' ':!quality' ':!BUGS.md'
  ```

  (grep's `.` matches any character, so the dotted pattern finds the slashed path too) prints
  only the `recording-renames` line (the old path is its point) and the member's move tests
  (the history check on that line in `_recording_history.py`, the old-package check and docstring
  in `_install_location.py`).
  `plans/`, `quality/` (ledger rows) and `BUGS.md` are history and keep the old paths.

### 6. The browser build

In `scripts/build_browser_bundle.py`, its `GAMES` entry's `module` becomes `<package>.game` and
`member_packages` names its package (a tuple, dependencies first); its `TOUCH_LAYOUTS` entry is
unchanged. `tests/test_build_browser_bundle.py` pins which games ship member packages. A game that depends
on another member lists both, the one depended on first: each ships as its own archive.

### 7. The docs

- `docs/games/<game>.md`: its file table and every path (`src/games/<game>/src/<package>/...`), and an
  "Its package" line linking here.
- `docs/glitchygames/examples/index.md`: remove its `:::` block, if it has one (its API page is now
  generated from the member).
- `README.md` and `CLAUDE.md`: where the game lives.

### 8. Verify

```bash
uv lock                                     # then read its diff: only the new member
uv sync --all-extras --all-groups --all-packages
uv run --extra dev nox -s format-code lint-code lint-dependencies
uv run basedpyright && uv run nox -s static-analysis-ty
# The member's tests, its golden replay among them (no -k: a golden's id is
# <console-script>/golden, hyphenated, so -k <package> would deselect it)
uv run pytest --dummy-only --no-cov -q src/games/<game>/tests
# The engine's checks on its golden replay, and its golden trace
uv run pytest --dummy-only --no-cov -q \
    tests/replay/test_golden_replays.py tests/world/test_golden_traces.py -k <package>
# The configuration guards, and every engine test that borrows the game (step 5's git grep)
uv run pytest --dummy-only --no-cov -q tests/test_suite_collection.py \
    tests/test_workspace_config.py tests/test_workspace_packages.py tests/test_logical_names.py \
    tests/test_browser_touch_controls.py tests/test_build_browser_bundle.py \
    tests/engine/test_engine_lifecycle.py tests/test_recording_metrics.py \
    tests/test_our_measured_recordings.py tests/test_measure_staged_replays.py \
    tests/test_generate_performance_graphs.py tests/replay tests/world <borrowing tests>
uv run pytest                               # the whole suite, both drivers, 100% coverage
uv build --package <distribution>           # the member builds on its own
uv run python -m scripts.build_browser_bundle <console-script> --output <scratch directory>
uv run nox -s browser -- <console-script>   # its browser bundle, served and opened
uv run nox -s lint-docs                     # the docs build strictly
```

The bundle built without serving must list `<package>.zip` in its `pyscript.toml`, and the
member's wheel hold only its package. Before the whole suite, a coverage run of the member's
tests and its borrowing tests (`--cov=<package> --cov-fail-under=0`) shows its code still at
100% from where it now is.

The golden replay is not re-recorded: its bytes are unchanged, and it replays strictly from its
new place. Its first frame records the scene's module, so its content hash changes:
`glitchygames report` shows that this is the only difference.

### 9. Commit

The `replay-metrics` pre-commit hook measures every recording on the new code and stages the
rows (about 12 s). It refuses a commit with untracked files under `src/` or a partial commit, so
stage the whole move (`git add -A src tests scripts docs`) before committing.

## Special cases

- **A member that was never in a layer** (Bitmappy, an app that lived in the engine as
  `glitchygames.bitmappy`, outside `examples/`, so no layer table named it): its logical name
  changes when it moves, from its module path (`glitchygames.bitmappy.editor:BitmapEditorScene`)
  to `apps.bitmappy.editor:BitmapEditorScene`, so a recording made before the move no longer
  matches. A plain replay refuses such a recording, naming the remedy, and
  `--replay-trace OLD --rebaseline NEW --headless` converts it (a rebaseline compares the game
  and each scene by qualified name alone and writes the current logical names:
  [gameplay replay](gameplay_replay.md)). A game that was already in a layer keeps its logical
  name when it moves, as the recipe above says. Bitmappy has no golden replay, so its move
  converted none; it keeps its tests named `test_bitmappy_*.py`, its sprite library as package
  data (`bitmappy.SPRITE_CONFIG_DIR`), and its member declares everything it imports itself (the
  engine's `pyproject.toml` no longer lists tenacity, for instance).
- **Several games in one project** (Brave Adventurer and its Egyptian edition, Papyrus): one
  member, built and published together, with layered import packages in its own src layout
  (`src/games/brave-adventurer/src/`): the primitives both games share
  (`brave_adventurer_core`), each game on top of them (`brave_adventurer`,
  `brave_adventurer_papyrus`), and a launcher (`brave_adventurer_modes`) as the member's one
  console script. The launcher starts the game a recording's header names, so the golden-replay
  plugin's one console script per member replays every game's golden; the goldens are named
  apart (`golden-<game>.jsonl.gz`). A member that keeps several console scripts instead has each
  recording replayed through the one whose entry point's module holds the game its header names
  (`src/glitchygames/replay/tools/children.py`, `recorded_games_console_script`).
  `scripts/record_scripted_session.py` names each such game's golden (`GOLDEN_FIXTURE_NAMES`)
  and keys its console scripts by game (`GAME_CONSOLE_SCRIPTS`), as
  tests/replay/test_golden_replays.py keys each golden's controls: one script can replay
  several games' goldens. Share only by mechanical moves: recordings and golden traces
  name sprites by class name and creation order, so a class may change module but not name, and
  nothing may be created in a different order. Its browser bundle lists every archive a game
  needs, the shared ones first.
- **A game that is one module** (PaddleSlap's `paddleslap.py`): its recordings name
  `games.paddleslap:Game`, so `Game` must stay defined in the package itself (`src/paddleslap/__init__.py`),
  not in a `paddleslap/game.py` it re-exports: a re-export does not change `Game.__module__`, and
  the logical name would become `games.paddleslap.game:Game`. Ruff's `non-empty-init-module`
  (RUF067) is ignored for that file in `pyproject.toml`. A package's `__init__` never runs as
  `__main__`, so the module's `if __name__ == '__main__'` moves to `src/<package>/__main__.py`
  (`python -m paddleslap`, as it was when the game lived in the engine's examples package).
- **Bundled demos** ship inside the package as package data, `<package>/demos/<name>.jsonl.gz`
  (PaddleSlap's `paddleslap/demos/rally.jsonl.gz`, read through `Path(__file__).parent`). The
  engine finds them in the installed packages: `glitchygames.bundled_demos.bundled_demos()`
  (`find_spec` over the packages its caller names, with no default; bookmarked copies left out)
  returns `BundledDemo` records
  (console script, installed path, install name). It is the one lookup: the replay plugin's
  `bundled_demo_paths` (which raises for a demo no console script replays) and
  `glitchygames.replay.tools.recordings.game_recordings` (a game's own demos, which `--verify`
  and `--measure` take) both call it. Development installs
  are editable (`uv sync`, and the `replay-metrics` nox session's `uv run --all-packages`), so
  the demos are found in the repository and the ledger names them by repository path; under a
  built install (`site-packages`, as nox's test sessions install on purpose) a recording outside
  the repository is named by its install name
  (`glitchygames.replay.tools.measure.recording_ledger_name`). A demo moved twice needs a `recording-renames` line from each
  old path.
- **Engine-private names**: a member uses only the engine's public API. Where a game reaches
  into the engine, give the engine a public read-only API first, then move the game. PaddleSlap
  needed no private name once the engine offered `BallSprite.trajectory` and
  `record_trajectory_point`.
- **A known exemption, member tests**: a member's tests may use the engine's test seams (for
  example `SceneManager._reset` and `FontManager._font_cache`, which reset engine state between
  tests); the member's game code may not. A public testing helper for them is a follow-up
  (`plans/future-features.md`, item #56).

## Pitfalls

- A plain `uv sync` drops the dev tools (pytest among them): use
  `uv sync --all-extras --all-groups --all-packages`.
- A member-only test run fails the coverage gate: add `--no-cov`, and let the whole run check
  coverage.
- An old example directory left on disk (its ignored `__pycache__`) is importable and shadows
  the member, and `tests/test_suite_collection.py` rejects a `glitchygames/` directory at the
  root. Delete leftovers after moving. The same trap applies to Bitmappy's old directory:
  a leftover `src/glitchygames/bitmappy/` (ignored `__pycache__`) resolves as a namespace
  package and fails `test_the_old_engine_package_is_gone`; `rm -rf src/glitchygames/bitmappy`.
- The same applies to `src/glitchygames/examples` and `tests/examples`: ignored leftovers of the
  move (`__pycache__`) make `glitchygames.examples` resolve as a namespace package in an
  editable install, and `test_the_old_example_module_is_gone` (in each moved member) and
  `test_the_engines_examples_directory_is_gone` fail. Their messages name the leftover
  locations; the remedy is `rm -rf src/glitchygames/examples tests/examples`.
- A member's console script resolves through its installed distribution: the golden plugin
  cannot find it unless `--all-packages` installed the member.
