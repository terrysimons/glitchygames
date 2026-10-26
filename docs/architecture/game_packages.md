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
  glitchygames/        the engine (distribution glitchygames); examples/ holds what has not moved yet
  games/<game>/        one member per game (Mr. Muncher first: src/games/mr-muncher/)
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
  `tests/test_workspace_config.py`) and `EXAMPLES_LAYERS` for games and demos still in
  `glitchygames/examples/`.
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
  namespace package there.
- Move its tests to `src/games/<game>/tests/` with no `__init__.py` (a tests directory must not be
  a package named `tests`: `tests/test_suite_collection.py`). Test file names must stay unique
  across every test directory; a shared helper module name can collide too (BUGS.md #31).
- Move its golden replay to `src/games/<game>/tests/fixtures/replays/golden.jsonl.gz`, its bytes
  unchanged. Data its tests read beside them (golden sounds, for instance) moves with them.
- Rewrite `glitchygames.examples.<package>` imports to `<package>` (`git grep -l` across the
  repository, excluding `plans/`), then read the whole diff: a docstring or a path string can
  match too.

### 2. Create the member

- `src/games/<game>/pyproject.toml` (above) and `README.md`. The package's `__init__.py`
  re-exports `main`.
- A `tests/test_logical_names_after_the_move.py` like Mr. Muncher's: the game's classes keep the
  logical names its recordings hold.

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
  becomes the bare package name). `scripts/record_scripted_session.py` derives its fixture
  directories from `GAME_MODULES` and the workspace: only its docstring examples need editing.
- `tests/replay/test_golden_replays.py`: its imports, `GAMEPLAY_ACTION_MAPS`,
  `ENGINE_SCENE_CONTROLS`, `UNEXERCISED_CONTROLS` and any table naming the game.
- `git grep` for the old package path and the old golden path across `tests/` and `scripts/`:
  engine tests that borrow a game (a collision test using its sprites), benchmarks reading its
  golden, scripts importing it. Point each at the member, or move the test into the member when
  it is really the game's.

### 6. The browser build

In `scripts/build_browser_bundle.py`, its `GAMES` entry's `module` becomes `<package>.game` and
`member_packages` names its package (a tuple, dependencies first); its `TOUCH_LAYOUTS` entry is unchanged.
`tests/test_build_browser_bundle.py` pins which games ship member packages. A game that depends
on another member lists both, the one depended on first: each ships as its own archive.

### 7. The docs

- `docs/games/<game>.md`: its file table and every path (`src/games/<game>/<package>/...`), and an
  "Its package" line linking here.
- `docs/glitchygames/examples/index.md`: remove its `:::` block (its API page is now generated
  from the member).
- `README.md` and `CLAUDE.md`: where the game lives.

### 8. Verify

```bash
uv lock && uv sync --all-extras --all-groups --all-packages
uv run --extra dev nox -s format-code lint-code lint-dependencies
uv run basedpyright && uv run nox -s static-analysis-ty
uv run pytest --dummy-only --no-cov -q src/games/<game>/tests tests/test_suite_collection.py \
    tests/test_workspace_config.py tests/test_workspace_packages.py tests/test_logical_names.py \
    tests/replay tests/test_replay_metrics.py tests/test_generate_performance_graphs.py
uv run pytest                               # the whole suite, both drivers, 100% coverage
uv build --package <distribution>           # the member builds on its own
uv run nox -s browser -- <console-script>   # its browser bundle
uv run nox -s lint-docs                     # the docs build strictly
```

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
  apart (`golden-<game>.jsonl.gz`). Until the launcher, the member keeps each game's console
  script, and the plugin replays a recording through the one whose entry point's module holds
  the game its header names (`glitchygames/testing/replays.py`, `recorded_games_console_script`);
  `scripts/record_scripted_session.py` names each such game's golden
  (`GOLDEN_FIXTURE_NAMES`). Share only by mechanical moves: recordings and golden traces
  name sprites by class name and creation order, so a class may change module but not name, and
  nothing may be created in a different order. Its browser bundle lists every archive a game
  needs, the shared ones first.
- **A game that is one module** (PaddleSlap's `paddleslap.py`): its recordings name
  `games.paddleslap:Game`, so `Game` must stay defined in the package itself (`paddleslap/__init__.py`),
  not in a `paddleslap/game.py` it re-exports: a re-export does not change `Game.__module__`, and
  the logical name would become `games.paddleslap.game:Game`.
- **Bundled demos** ship inside the package, `<package>/demos/<name>.jsonl.gz`, found by
  `glitchygames/testing/replays.py` `bundled_demo_paths`.
- **Engine-private names**: a member uses only the engine's public API. Where a game reaches
  into the engine (PaddleSlap reads `ball._debug_positions`), give the engine a public read-only
  API first, then move the game.

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
