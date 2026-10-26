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
  glitchygames/        the engine (distribution glitchygames); examples/ holds the demos and
                       Bitmappy's resources, which have not moved yet
  games/<game>/        one member per game: every game (mr-muncher, clockwork-keep,
                       brave-adventurer, paddleslap, drawing-fire)
  demos/<demo>/        one member per demo
  apps/<app>/          one member per application (Bitmappy)
tests/                 the engine's own tests
scripts/               tools
```

Nothing at the repository root is importable as one of our packages. Tests and tools run from
the root import the installed engine and members (`uv sync` installs them editable, nox
non-editable), and `tests/test_suite_collection.py` checks that `import glitchygames` resolves to
the installed package. Coverage maps the installed copies back to `src/`
(`[tool.coverage.paths]`), so its report names the files in the repository.

## What a member is

A member is a directory under its layer, named after its distribution (with hyphens), holding:

```
src/games/<game>/
  pyproject.toml       its metadata (below)
  README.md            one paragraph: what it is, how to play and test it
  <package>/           its import package (underscores: a hyphen cannot be imported)
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
packages = ["<package>"]

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
pip install glitchygames                # the engine
pip install "glitchygames[games]"       # the engine and every game
pip install "glitchygames[demos,apps]"  # the engine, the demos and the apps
```

(`uv sync --extra games` does the same in the repository.) A layer with no member yet is an empty
extra; `tests/test_workspace_config.py` keeps each extra equal to its layer's members.

- **Recordings name games by logical names**: `<layer>.<module path inside the package>:<class>`
  (`games.mr_muncher.game:MrMuncherScene`). A recording therefore does not depend on where the
  code lives, and moving a game changes no recording. The layers are data in the engine,
  `glitchygames/logical_names.py`: `MEMBER_LAYERS` for members (kept equal to the workspace by
  `tests/test_workspace_config.py`) and `EXAMPLES_LAYERS` for the demos still in
  `glitchygames/examples/` (every game has moved; Part 3 moves the demos).
- **Golden replays** live with the member's tests; the golden plugin collects them from every
  member, so the engine's `uv run pytest` replays each one.
- **The browser build** ships a member's package as its own archive (`<package>.zip`) beside the
  engine's `glitchygames.zip` (`scripts/build_browser_bundle.py`, `GameSpecification.member_packages`).
- **API reference**: `scripts/gen_ref_pages.py` writes a page per member package
  (`<package>/index.md`), listed under "Games API Reference" in `mkdocs.yml`.

## Moving a game out of the engine

The recipe Mr. Muncher's move followed (`plans/2026-10-24-workspace-packages-1-foundation.md`,
Task 9). Do one game per commit series, and verify each before the next. Every step names the
check that fails if it is skipped: `tests/test_workspace_config.py` catches a member left out of
any tool's configuration.

### 1. Move the code and tests

- `git mv src/glitchygames/examples/<package> src/games/<game>/<package>`, then delete what is
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
- A `tests/test_<package>_after_the_move.py` (Mr. Muncher's is `test_logical_names_after_the_move.py`,
  the first; every later member names its own, since `tests/test_suite_collection.py` refuses a
  test file name used twice): the game's classes keep the logical names its recordings hold, and
  `importlib.util.find_spec('glitchygames.examples.<package>')` is None.

### 3. Register it in the root configuration

| File | What to add or change |
|---|---|
| `pyproject.toml` | Remove its console script from `[project.scripts]` (the member's own `pyproject.toml` has it now). Add the member to its layer's extra (`games`, `demos` or `apps` in `[project.optional-dependencies]`), `[tool.uv.workspace] members`, `[tool.uv.sources]`, the `dev` dependency group, pytest `testpaths`, `addopts` (`--cov=<package>`), coverage `source` and `[tool.coverage.paths]`, ruff `src`, `include` and `namespace-packages` (its tests), isort `known-first-party`, ty `root` and `src.include`, deptry `known_first_party`. Re-key any per-file ruff ignore that names the old path. |
| `pyrightconfig.json` | Add it to `include`, a tests environment (before the member's own) and the member's environment, each with the `extraPaths` Mr. Muncher's have |
| `noxfile.py` | `_CODE_DIRS`, `_SOURCE_PACKAGE_DIRS`, `_MEMBER_DISTRIBUTIONS` |
| `wily.cfg` | The `path` list |
| `mkdocs.yml` | The mkdocstrings `paths`, and its API page under "Games API Reference" |
| `uv.lock` | Regenerate: `uv lock` |

### 4. Update the engine's tables

- `glitchygames/logical_names.py`: move its package from `EXAMPLES_LAYERS` to `MEMBER_LAYERS`.
  Its recordings need nothing else (their logical names do not change); `tests/test_logical_names.py`
  pins both tables.
- `glitchygames/recording_metrics.py` `RECORDING_PATH_RENAMES`: one line per moved recording, old
  path to new, so its run-ledger history stays connected. Each lookup is one step: a recording
  that has already moved once needs a line from each of its old paths.

### 5. Update the scripts and tests that name it

- `scripts/record_golden_traces.py`: its imports, `GAME_SCENES`, and `GAME_MODULES` (whose value
  is the bare package name). `scripts/record_scripted_session.py` derives its fixture
  directories from `GAME_MODULES` and the workspace (`REPLAY_FIXTURE_DIRECTORIES`), and refuses
  a game no member holds: only its docstring examples need editing.
- `tests/replay/test_golden_replays.py`: its imports, `GAMEPLAY_ACTION_MAPS`,
  `ENGINE_SCENE_CONTROLS`, `UNEXERCISED_CONTROLS` and any table naming the game.
- The engine tests that borrow a game, by import or by path. Clockwork Keep's move touched
  `tests/animation/test_animation.py`, `tests/world/test_golden_traces.py` (its trace stays; only
  imports change), `tests/world/test_transition_input.py`, `tests/test_browser_touch_controls.py`
  and `scripts/audio_glitch_probe.py`. Add the moved game to
  `tests/replay/test_record_scripted_session.py::test_a_member_games_fixture_is_directly_in_the_members_replay_fixtures`.
  `tests/engine/test_engine_lifecycle.py` `GAME_CONSOLE_SCRIPTS` lists every game's console script
  (unchanged by a move, which keeps the script's name).
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
      "glitchygames.examples.<package>\|glitchygames/examples/<package>\|fixtures/replays/<game>" \
      -- ':!plans' ':!quality' ':!BUGS.md'
  ```

  prints only the `RECORDING_PATH_RENAMES` line and its test in `tests/test_recording_metrics.py`
  (the old path is their point), and the member's after-the-move test (its old-package check and
  docstring). `plans/`, `quality/` (ledger rows) and `BUGS.md` are history and keep the old paths.

### 6. The browser build

In `scripts/build_browser_bundle.py`, its `GAMES` entry's `module` becomes `<package>.game` and
`member_packages` names its package (a tuple, dependencies first); its `TOUCH_LAYOUTS` entry is
unchanged. `tests/test_build_browser_bundle.py` pins which games ship member packages. A game that depends
on another member lists both, the one depended on first: each ships as its own archive.

### 7. The docs

- `docs/games/<game>.md`: its file table and every path (`src/games/<game>/<package>/...`), and an
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
# The member, its golden replay and golden trace
uv run pytest --dummy-only --no-cov -q src/games/<game>/tests \
    tests/replay/test_golden_replays.py tests/world/test_golden_traces.py -k <package>
# The configuration guards, and every engine test that borrows the game (step 5's git grep)
uv run pytest --dummy-only --no-cov -q tests/test_suite_collection.py \
    tests/test_workspace_config.py tests/test_workspace_packages.py tests/test_logical_names.py \
    tests/test_browser_touch_controls.py tests/test_build_browser_bundle.py \
    tests/engine/test_engine_lifecycle.py tests/test_recording_metrics.py \
    tests/test_replay_metrics.py tests/test_measure_staged_replays.py \
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
`scripts/recording_report.py` shows that this is the only difference.

### 9. Commit

The `replay-metrics` pre-commit hook measures every recording on the new code and stages the
rows (about 12 s). It refuses a commit with untracked files under `src/` or a partial commit, so
stage the whole move (`git add -A src tests scripts docs`) before committing.

## Special cases

- **Several games in one project** (Brave Adventurer and its Egyptian edition, Papyrus): one
  member, built and published together, with layered import packages in its own src layout
  (`src/games/brave-adventurer/src/`): the primitives both games share
  (`brave_adventurer_core`), each game on top of them (`brave_adventurer`,
  `brave_adventurer_papyrus`), and a launcher (`brave_adventurer_modes`) as the member's one
  console script. The launcher starts the game a recording's header names, so the golden-replay
  plugin's one console script per member replays every game's golden; the goldens are named
  apart (`golden-<game>.jsonl.gz`). A member that keeps several console scripts instead has each
  recording replayed through the one whose entry point's module holds the game its header names
  (`glitchygames/testing/replays.py`, `recorded_games_console_script`).
  `scripts/record_scripted_session.py` names each such game's golden (`GOLDEN_FIXTURE_NAMES`)
  and keys its console scripts by game (`GAME_CONSOLE_SCRIPTS`), as
  tests/replay/test_golden_replays.py keys each golden's controls: one script can replay
  several games' goldens. Share only by mechanical moves: recordings and golden traces
  name sprites by class name and creation order, so a class may change module but not name, and
  nothing may be created in a different order. Its browser bundle lists every archive a game
  needs, the shared ones first.
- **A game that is one module** (PaddleSlap's `paddleslap.py`): its recordings name
  `games.paddleslap:Game`, so `Game` must stay defined in the package itself (`paddleslap/__init__.py`),
  not in a `paddleslap/game.py` it re-exports: a re-export does not change `Game.__module__`, and
  the logical name would become `games.paddleslap.game:Game`. Ruff's `non-empty-init-module`
  (RUF067) is ignored for that file in `pyproject.toml`. A package's `__init__` never runs as
  `__main__`, so the module's `if __name__ == '__main__'` moves to `<package>/__main__.py`
  (`python -m paddleslap`, as `python -m glitchygames.examples.paddleslap` was).
- **Bundled demos** ship inside the package as package data, `<package>/demos/<name>.jsonl.gz`
  (PaddleSlap's `paddleslap/demos/rally.jsonl.gz`, read through `Path(__file__).parent`). The
  engine finds them in the installed packages: `glitchygames.bundled_demos.bundled_demos()`
  (`find_spec` over `MEMBER_LAYERS`; bookmarked copies left out) returns `BundledDemo` records
  (console script, installed path, install name). It is the one lookup: the replay plugin's
  `bundled_demo_paths` (which raises for a demo no console script replays) and
  `scripts/replay_metrics.py` (which reports it unreplayable) both call it. Development installs
  are editable (`uv sync`, and the `replay-metrics` nox session's `uv run --all-packages`), so
  the demos are found in the repository and the ledger names them by repository path; under a
  built install (`site-packages`, as nox's test sessions install on purpose) a recording outside
  the repository is named by its install name (`scripts/replay_metrics.py`
  `recording_ledger_name`). A demo moved twice needs a `RECORDING_PATH_RENAMES` line from each
  old path.
- **Engine-private names**: a member uses only the engine's public API. Where a game reaches
  into the engine, give the engine a public read-only API first, then move the game. PaddleSlap
  needed no private name once the engine offered `BallSprite.trajectory` and
  `record_trajectory_point`.

## Pitfalls

- A plain `uv sync` drops the dev tools (pytest among them): use
  `uv sync --all-extras --all-groups --all-packages`.
- A member-only test run fails the coverage gate: add `--no-cov`, and let the whole run check
  coverage.
- An old example directory left on disk (its ignored `__pycache__`) is importable and shadows
  the member, and `tests/test_suite_collection.py` rejects a `glitchygames/` directory at the
  root. Delete leftovers after moving.
- A member's console script resolves through its installed distribution: the golden plugin
  cannot find it unless `--all-packages` installed the member.
