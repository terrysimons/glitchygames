# Games as Their Own Packages

A GlitchyGames game, demo or app lives in its own package beside the engine: a
[uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) member under `src/`,
depending on `glitchygames` like any third-party game would. This page explains what a member
is, how to work with one, and how to add one. The why is in the plan,
`plans/2026-10-24-workspace-packages.md`; how the games got here is under "History" below.

## The layout

Four layers, all under `src/`:

```
src/
  glitchygames/        the engine (distribution glitchygames); it has no examples package:
                       every game and demo is a member, and its resources/ holds only what the
                       engine itself ships
  games/<game>/        one member per game: every game (mr-muncher, clockwork-keep,
                       brave-adventurer, paddleslap, drawing-fire)
  demos/<demo>/        one member per demo (dt-demo, joystick-demo, sound-board-demo,
                       text-input-demo): a small
                       program that shows one engine feature (console scripts `dt-demo`,
                       `joystick-demo`, `sound-board-demo`, `text-input-demo`; no browser build)
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
src/<layer>/<member>/
  pyproject.toml       its metadata (below)
  README.md            one paragraph: what it is, how to play and test it
  src/<package>/       its import package (underscores: a hyphen cannot be imported), never at
                       the member's root, so nothing in the member directory can be imported by
                       accident in place of the installed package
  tests/               its tests (no __init__.py); a game's golden replay is in
                       tests/fixtures/replays/golden.jsonl.gz
```

Its `pyproject.toml` follows Mr. Muncher's (`src/games/mr-muncher/pyproject.toml`):

```toml
[project]
name = "<distribution>"
version = "1.0.0"
description = "<one line>"
requires-python = ">=3.14,<4.0"
# What it imports (decision 10: a member declares every distribution it imports)
dependencies = ["glitchygames>=1.0.0", "pygame-ce"]

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

A member declares every distribution its code imports, and the engine with a version floor
(`tests/test_workspace_config.py`: `test_every_member_declares_what_it_imports`,
`test_every_member_depends_on_the_engine_with_a_floor`): Mr. Muncher's list is
`["glitchygames>=1.0.0", "pydantic", "pygame-ce"]`. A member that reuses another member's code
depends on it too (`"<other>"` in `dependencies`, `<other> = { workspace = true }`). Files inside
the import package (a sprite TOML, a bundled demo) ship as package data: read them through the
module's own path (`Path(__file__).parent / 'sprites'`), never through the repository.

## Working with a member

From the repository root:

```bash
uv sync --all-extras --all-groups --all-packages   # the engine and every member, with the dev tools
uv run <console-script>                            # play it
uv run pytest --no-cov src/<layer>/<member>/tests  # its tests alone (no coverage gate on a subset)
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
  code lives. The layers are data in the engine, `src/glitchygames/logical_names.py`:
  `MEMBER_LAYERS` (kept equal to the workspace by `tests/test_workspace_config.py`).
- **Golden replays** live with the member's tests; the golden plugin collects them from every
  member, so the engine's `uv run pytest` replays each one.
- **The browser build** ships a member's package as its own archive (`<package>.zip`) beside the
  engine's `glitchygames.zip` (`scripts/build_browser_bundle.py`, `GameSpecification.member_packages`).
- **API reference**: `scripts/gen_ref_pages.py` writes a page per member package
  (`<package>/index.md`), listed in `zensical.yml` under "Games API Reference", "Demos API
  Reference" or "Apps API Reference" by its layer.
- **Wheels**: `nox -s build-wheel` builds the wheel of the engine and of every member
  (`uv build --all-packages`).

## Adding a member

A new game, demo or app starts as a member. The Sound Board demo (`src/demos/sound-board-demo/`,
added with the sound engine) is the newest and the smallest to copy; Mr. Muncher is the game to
copy. The workspace is the list of members in the root `pyproject.toml` (`[tool.uv.workspace]
members`): once a member is listed there, `tests/test_workspace_config.py` finds it and fails,
naming the file and key, for every tool's configuration below that leaves it out. The steps say
which entries no test checks.

### 1. Create the member

- `src/<layer>/<member>/pyproject.toml` (above), `README.md`, and `src/<package>/` whose
  `__init__.py` defines or re-exports `main` (and `__main__.py`, for `python -m <package>`).
- `tests/`, with no `__init__.py`, holding test files named for the member:
  `test_<distribution with - as _>.py` or `test_<distribution with - as _>_<subject>.py`
  (`tests/test_suite_collection.py::test_every_members_test_modules_are_named_for_it`). Every
  member has these subjects where they apply:
  - `_logical_names.py` (every member, required by the same test): its scene classes have the
    logical names its recordings will hold (`demos.sound_board_demo:Game`);
  - `_install_location.py`: the package imports from `<member>/src/`, or `site-packages` in a
    wheel install;
  - `_entry_points.py`: the console script and `python -m <package>` resolve to `main`;
  - `_package_data.py` and `_wheel.py`, for a member that ships data (a sprite library, a bundled
    demo): the data is inside the package, checked without building a wheel, and the wheel
    holds only the package and its data.
- pytest imports every test module by its path from the repository root, never by its bare file
  name (`--import-mode=importlib` in the root `pyproject.toml`), so two members may have test
  files or helpers of the same name (BUGS.md #224 item 31). To patch a test module's own names,
  use `__name__` (`mocker.patch(f'{__name__}.LOG')`). A helper module beside the tests is
  imported by that same path (`from src.apps.bitmappy.tests.film_strip_support import ...`),
  never by its bare name
  (`tests/test_suite_collection.py::test_no_member_test_imports_a_module_by_a_bare_name`). A
  member directory whose name holds a dash cannot be named in an `import` statement: give its
  tests their shared helpers as `conftest.py` fixtures (the simplest), or load one with
  `importlib.import_module('src.games.mr-muncher.tests.maze_support')`.
- A member may have a `tests/conftest.py` (Drawing Fire's drains the event queue). It is imported
  by its path too, so nothing may `import conftest` by name: look a conftest up as pytest
  registered it, by its path
  (`pytestconfig.pluginmanager.get_plugin(str(pytestconfig.rootpath / 'conftest.py'))`).

### 2. Register it in the root configuration

| File | What to add |
|---|---|
| `pyproject.toml` | `[tool.uv.workspace] members` (first: this is what makes it a member), `[tool.uv.sources]`, the `dev` dependency group, its layer's extra (`games`, `demos` or `apps` in `[project.optional-dependencies]`), pytest `testpaths` and `addopts` (`--cov=<package>`), coverage `source` and `[tool.coverage.paths]`, ruff `src`, `include` and `namespace-packages` (its tests), isort `known-first-party`, ty `environment.root` and `src.include`, deptry `package_module_name_map` (its distribution -> its import packages; not `known_first_party`, which would hide the extra's use). Not checked by a test: `[tool.glitchygames] games` (its console script, so `glitchygames verify` and `glitchygames measure` with no `--game` take its recordings; a golden or bundled demo no listed game claims fails `tests/test_our_measured_recordings.py`, a member with neither fails nothing), and, for a demo, deptry's `DEP002` list (nothing at the root imports a demo, so `nox -s lint-dependencies` reports its extra entry as unused) |
| `pyrightconfig.json` | `include`; its `src/` in the `extraPaths` of the `tests` environment and of every member's tests environment (each is a copy of `tests`'s); a tests environment for it (a copy of `tests`'s), before its own environment (`"extraPaths": ["src", "<member>/src"]`) |
| `noxfile.py` | `_CODE_DIRS`, `_SOURCE_PACKAGE_DIRS`, `_MEMBER_DISTRIBUTIONS` |
| `wily.cfg` | The `path` list |
| `zensical.yml` | The mkdocstrings `paths` (its `src/`; not checked by a test, but without it `nox -s lint-docs` fails to render its API page), and its API page under its layer's "API Reference" |
| `uv.lock` | Regenerate: `uv lock`, then read its diff: only the new member |

The per-layer entries need nothing: the ruff per-file ignores and ty's `src.exclude` name each
layer's tests by a glob (`src/demos/*/tests/**/*.py`). A game that is one module adds a per-file
ruff ignore (see "Special cases").

### 3. The tables written by hand

Some tests compare what they find with a list written out on purpose, because an expectation
derived from the thing it checks checks nothing. Every member:

- `src/glitchygames/logical_names.py`: its package in `MEMBER_LAYERS` (checked by
  `tests/test_workspace_config.py`); and the two tables in `tests/test_logical_names.py`.
- `tests/workspace_expectations.py`: its console script in `EXPECTED_ALL_CONSOLE_SCRIPTS`.
- `tests/replay/tools/test_settings.py`: its console script in `OUR_GAMES`.

A game also has a golden replay, recorded from a scripted session, and a golden trace:

- `tests/workspace_expectations.py`: `EXPECTED_GOLDENS` and `EXPECTED_GAME_CONSOLE_SCRIPTS` (and
  `EXPECTED_BUNDLED_DEMOS` for a bundled demo).
- `scripts/golden_inputs.py`: its golden input script (`<package>_script`) and controls tail
  (`<package>_controls`), each a callable taking no arguments that returns an `InputScript`,
  importing what it reads of its game inside the function. Any tool reaches them as
  `MODULE:NAME` from the repository root (`--input-script scripts.golden_inputs:<package>_script`,
  `--controls-tail scripts.golden_inputs:<package>_controls`).
- `scripts/record_golden_traces.py`: a `'<module>:<class>'` reference in `GAME_SCENES` (never a
  module-level import of a member: the subprocess import test fails on one), `GAME_MODULES`
  (whose value is the bare package name) and its input script's builder in `SCRIPT_BUILDERS`.
  It records on the engine's golden-trace harness (`glitchygames.replay.tools.golden_traces`).
- `scripts/record_scripted_session.py` records the golden replay on the engine's
  scripted-session recorder (`glitchygames.replay.tools.scripted_sessions`, the
  `record-session` tool): its controls tail in `CONTROLS_TAIL_BUILDERS`, and the game in
  `INPUT_ONLY_PLACEMENT_GAMES` or `POLLED_INPUT_GAMES` when its script needs it. It derives its
  fixture directories from `GAME_MODULES` and the workspace (`REPLAY_FIXTURE_DIRECTORIES`), and
  refuses a game no member holds; add its command to the docstring's list. Record with
  `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_scripted_session --game <package> --frames N`.
- `tests/replay/golden_replay_controls.py`: its control tables (`GAMEPLAY_ACTION_MAPS`,
  `ENGINE_SCENE_CONTROLS`, `UNEXERCISED_CONTROLS`), and
  `tests/replay/test_record_scripted_session.py::test_a_member_games_fixture_is_directly_in_the_members_replay_fixtures`.

The recording tools themselves are the engine's, and a member has them without declaring
anything (`--record-golden-trace`, `--record-session`, `--verify`, `--measure`, ..., or
`glitchygames <tool>`: [Tools for any game](gameplay_replay.md#tools-for-any-game)).

Engine tests never borrow a member, by import or by path: `tests/test_suite_collection.py`
(`engine_test_imports_of_members`) fails on any root test that imports one. A test only the
member's code can answer goes in the member's tests; an engine test that needs a game uses a
stand-in (`tests/stand_in_harness_games.py`, `tests/stand_in_games.py`). The exemptions are
listed with their reasons (`MEMBER_IMPORT_EXEMPT_MODULES` and `MEMBER_IMPORT_EXEMPT_NAMES` in
`tests/test_suite_collection.py`; a stale one fails): the per-game control tables in
`tests/replay/golden_replay_controls.py`, and the per-game world rules
`tests/world/test_golden_traces.py` imports.

### 4. The browser build (games and apps)

In `scripts/build_browser_bundle.py`, a `GAMES` entry: its `module` and `scene_class`, its
`title`, and `member_packages` (a tuple, dependencies first: each ships as its own archive), and
a `TOUCH_LAYOUTS` entry for its touch controls. `tests/test_build_browser_bundle.py` pins which
games ship member packages. Demos have no browser build.

### 5. The docs

- `docs/games/<game>.md` (a game) or a section of the page for the feature a demo shows (the
  Sound Board demo's is in [Sound](sound.md)), with an "Its package" line linking here; and its
  entry in `zensical.yml`'s `nav`.
- `README.md` and `CLAUDE.md`: where it lives and how to run it.

### 6. Verify

```bash
uv lock                                     # then read its diff: only the new member
uv sync --all-extras --all-groups --all-packages
uv run --extra dev nox -s format-code lint-code lint-dependencies
uv run basedpyright && uv run nox -s static-analysis-ty
uv run pytest --dummy-only --no-cov -q src/<layer>/<member>/tests
# The configuration guards and the hand-written tables
uv run pytest --dummy-only --no-cov -q tests/test_suite_collection.py \
    tests/test_workspace_config.py tests/test_workspace_packages.py tests/test_logical_names.py \
    tests/replay/tools/test_settings.py tests/engine/test_every_game_powers_on.py
uv run pytest                               # the whole suite, both drivers, 100% coverage
uv build --package <distribution>           # the member builds on its own
uv run nox -s lint-docs                     # the docs build strictly
```

A game also checks its golden and its browser build (no `-k <package>` on the member's own
tests: a golden's id is `<console-script>/golden`, hyphenated, so it would be deselected):

```bash
uv run pytest --dummy-only --no-cov -q \
    tests/replay/test_golden_replays.py tests/world/test_golden_traces.py -k <package>
uv run <console-script> --verify            # its golden replay and bundled demos, replayed headless
uv run glitchygames unmeasured --game <console-script>   # what --measure would measure of it
uv run python -m scripts.build_browser_bundle <console-script> --output <scratch directory>
uv run nox -s browser -- <console-script>   # its browser bundle, served and opened
```

The bundle built without serving must list `<package>.zip` in its `pyscript.toml`.

### 7. Commit

The `replay-metrics` pre-commit hook (`scripts/measure_staged_replays.py`, which runs
`glitchygames unmeasured`, then `glitchygames measure --code-tree TREE --rows-directory DIR`)
measures every recording on the new code and stages the rows (about 12 s). It refuses a commit
with untracked files under `src/` or a partial commit, so stage the whole member and its
registration (`git add -A src tests scripts docs`) before committing.

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
  (`src/glitchygames/replay/tools/children.py`, `recorded_games_console_script`).
  `scripts/record_scripted_session.py` names each such game's golden (`GOLDEN_FIXTURE_NAMES`)
  and keys its console scripts by game (`GAME_CONSOLE_SCRIPTS`), as
  `tests/replay/test_golden_replays.py` keys each golden's controls: one script can replay
  several games' goldens. Share only by mechanical moves: recordings and golden traces
  name sprites by class name and creation order, so a class may change module but not name, and
  nothing may be created in a different order. Its browser bundle lists every archive a game
  needs, the shared ones first.
- **A game that is one module** (PaddleSlap; the Sound Board demo is one too): its recordings
  name `games.paddleslap:Game`, so `Game` stays defined in the package itself
  (`src/games/paddleslap/src/paddleslap/__init__.py`), not in a `game.py` it re-exports: a
  re-export does not change the class's `__module__`, and the logical name would become
  `games.paddleslap.game:Game`. Ruff's `non-empty-init-module` (RUF067) is ignored for that
  `__init__.py` in the root `pyproject.toml`, with the reason. A package's `__init__` never runs
  as `__main__`, so its `if __name__ == '__main__'` is in `__main__.py` (`python -m paddleslap`).
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
  (`glitchygames.replay.tools.measure.recording_ledger_name`).
- **Engine-private names**: a member uses only the engine's public API. Where a member needs
  something the engine keeps private, give the engine a public read-only API first: PaddleSlap
  reads its ball's path through `BallSprite.trajectory` and `record_trajectory_point`.
- **A known exemption, member tests**: a member's tests may use the engine's test seams (for
  example `SceneManager._reset` and `FontManager._font_cache`, which reset engine state between
  tests); the member's code may not. A public testing helper for them is a follow-up
  (`plans/future-features.md`, item #56).

## Pitfalls

- A plain `uv sync` drops the dev tools (pytest among them): use
  `uv sync --all-extras --all-groups --all-packages`.
- A member-only test run fails the coverage gate: add `--no-cov`, and let the whole run check
  coverage.
- A member's console script resolves through its installed distribution: the golden plugin
  cannot find it unless `--all-packages` installed the member.
- A directory left on disk by a removed or renamed package (its git-ignored `__pycache__`) is
  importable as a namespace package and can shadow the member: delete it.

## History: the moves out of the engine

Every game and demo began in the engine's examples package, and Bitmappy in the engine itself;
all moved into members by 2026-10-26 (Part 3). The plans record each move step by step
(`plans/2026-10-24-workspace-packages.md` and its parts; Mr. Muncher's, the first, is
`plans/2026-10-24-workspace-packages-1-foundation.md`, Task 9). What still matters:

- **Logical names**: a game moved from the examples package kept its logical name, so no
  recording changed. Bitmappy, which was not in a layer, did not: its scene's logical name was
  its module path (glitchygames.bitmappy.editor:BitmapEditorScene) and is now
  `apps.bitmappy.editor:BitmapEditorScene`. A plain replay refuses a recording made before the
  move, naming the remedy, and `--replay-trace OLD --rebaseline NEW --headless` converts it (a
  rebaseline compares the game and each scene by qualified name alone and writes the current
  logical names: [gameplay replay](gameplay_replay.md)).
- **Moved recordings keep their history**: the root `pyproject.toml`'s
  `[tool.glitchygames.recording-renames]` maps each moved recording's old path to its new one,
  so its run-ledger rows stay connected (each moved member's `_recording_history.py` test
  checks its lines). Each lookup is one step: a recording moved twice needs a line from each of
  its old paths.
- **Old checkouts**: a checkout from before the moves can hold ignored leftovers (their
  `__pycache__`) in the old places, src/glitchygames/examples, src/glitchygames/bitmappy and
  tests/examples, which resolve as namespace packages in an editable install. The moved
  members' `test_the_old_example_module_is_gone` (PaddleSlap's and the demos'), Bitmappy's
  `test_the_old_engine_package_is_gone` and the engine's
  `test_the_engines_examples_directory_is_gone` fail on them, naming the leftover; the remedy is
  `rm -rf src/glitchygames/examples src/glitchygames/bitmappy tests/examples`.
