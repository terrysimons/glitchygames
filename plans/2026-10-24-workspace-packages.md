# Games, Demos and Apps as Their Own Packages (master plan)

Status: IN PROGRESS. Part 1 DONE on feature/workspace-packages-foundation (2026-10-25: the
src/ layout, Mr. Muncher as a member, logical names; commits e864215c..73a60265, 22 commits,
verified by Task 12; merged as #105, b29f85fc). Part 2 DONE on
feature/workspace-packages-2-games (2026-10-25: every game is its own package, five members
under `src/games/`: mr-muncher (Part 1), clockwork-keep, brave-adventurer (one project: core,
Classic, Papyrus and a launcher), paddleslap and drawing-fire; commits 46a6ca20 to "Workspace
packages, Part 2: every game is its own package", 26 commits, verified by Task 9; merged as
#109, a97efbe9). Part 4 DONE on feature/workspace-packages-4-bitmappy (2026-10-26: Bitmappy is
its own package, `src/apps/bitmappy/`; commits a97efbe9..1d0994a0 at present, the last hash
pinned at merge; verified by its Task 7 and the user's manual checks, 2026-10-26, then a
final-review fix pass; see [its plan](2026-10-26-workspace-packages-4-bitmappy.md); not yet
merged). Part 3 (the demos) DONE on feature/workspace-packages-3a-src-layout (2026-10-26: Stage A,
every member in a `src/` layout; Stage B, the three demos are members of the `demos` layer and
`src/glitchygames/examples/` and `EXAMPLES_LAYERS` are gone; Stage C, engine tests stop borrowing
members and the guards cover every member; commits 832c76e6..abbbba09 and the C6 commits on top, the
last hash pinned at merge; awaiting the final review; see [its
plan](2026-10-26-workspace-packages-3-demos.md)); Part 5 (the browser IDE) NOT STARTED.
Plan written 2026-10-24; amended 2026-10-25: everything under `src/`, decision 7; logical names
in recordings, decision 8; where recordings live, decision 9; amended 2026-10-26: Part 4 runs
before Part 3 (the user: "bitmappy should move first"), so deleting `src/glitchygames/examples/`
moves to Part 3; the `examples:` file-name prefix is removed, not moved (decision 5); every
member declares what it imports (decision 10); the four WAVs are kept as engine resources and
the shared sprite-file checks became an engine testing helper (Part 3, done 2026-10-26).
Parts 1, 2 and 4 have full implementation plans; Parts 3 and 5 are outlined here and get theirs
when each starts, written against how Parts 2 and 4 turned out.

Sub-plans:
- Part 1 (DONE): [Foundation and the Mr. Muncher
  pilot](2026-10-24-workspace-packages-1-foundation.md)
- Part 2 (DONE): [The other five games](2026-10-25-workspace-packages-2-games.md) (Clockwork
  Keep, Brave Adventurer with Papyrus as one project, PaddleSlap and Drawing Fire, which postdates
  the outline; the move recipe is `docs/architecture/game_packages.md`)
- Part 3 (DONE): [The demos](2026-10-26-workspace-packages-3-demos.md) (outline below). Its plan
  starts from the untracked
  draft `plans/2026-10-25-workspace-packages-2-games-demos-apps.md` (Tasks 10-12 and 18),
  corrected against #109 and Part 4 (the outline lists what is stale in it); the draft is
  deleted once Part 3 has its plan (the user, 2026-10-26)
- Part 4 (DONE): [Bitmappy as an app](2026-10-26-workspace-packages-4-bitmappy.md)
- Part 5: A browser IDE on each game's page (outline below)

## Why

The example games live inside the engine's package (`src/glitchygames/examples/`) and ship in its
wheel. Moving each into its own package beside the engine:

- **makes a game's code path easy to review**: a game change is one directory, its code, tests
  and golden replay together, read against the engine's public API;
- **makes the games prove the public API**: a game depends on `glitchygames` like any third-party
  game would, so reaching into engine internals becomes a visible decision (before Part 2 only
  PaddleSlap did, through `ball._debug_positions`; Part 2 gave `BallSprite` a public
  `trajectory` and `record_trajectory_point`);
- **slims the engine's wheel**: game code, sprites and demos stop shipping in `glitchygames`
  (games since Part 2, Bitmappy and its sprite library since Part 4; the demos and `foo2.toml`
  shipped until Part 3, which moved them out on 2026-10-26 and put the four WAVs in the engine's
  own resources);
- **gives one package per playable thing**, as the browser bundles and `play/` pages already
  are, and a template a new game copies.

## The layout

Four layers, all under `src/` (decision 7):

```
src/
  glitchygames/                the engine (the root project, distribution glitchygames; moved
                               from ./glitchygames/ in Part 1, first; loses examples/ part by part)
  games/
    mr-muncher/                pyproject.toml (distribution mr-muncher), mr_muncher/, tests/
    paddleslap/
    clockwork-keep/
    brave-adventurer/          one project (Part 2): brave_adventurer_core, brave_adventurer
                               (Classic), brave_adventurer_papyrus and the launcher
                               brave_adventurer_modes, its one console script
    drawing-fire/              added in Part 2 (it postdates this outline)
  demos/
    dt-demo/  joystick-demo/  text-input-demo/
  apps/
    bitmappy/                  the pixel art editor, with its sprites
tests/                         the engine's tests (stay at the root)
scripts/                       tools (stay at the root)
```

The engine's import name stays `glitchygames`; its wheel holds the top-level package `glitchygames`
(hatch `packages = ["src/glitchygames"]`), so nothing that imports it changes. The repository
root holds no importable engine: tests and tools run from the root import the installed package
(nox installs it non-editable; `uv sync` installs it editable, through a `.pth` naming `src/`).
This plan names engine files by their repository path (`src/glitchygames/ui/dialogs.py`), as they
are now that Part 1 has moved the engine.

Each member is a uv workspace member (root `pyproject.toml` `[tool.uv.workspace]`): its own
`pyproject.toml` (hatchling, like the engine), its import package (`mr_muncher`: a hyphen
cannot be imported), its console script (`mr-muncher`, unchanged), and its own `tests/` with its
golden replay directly in `tests/fixtures/replays/` (`golden.jsonl.gz`; decision 9). A member's
`tests/` is rootless (no `__init__.py`): pytest imports each test module by its bare file name,
so each is named `test_<package>_<area>.py` and no name repeats across test roots (decision 3).

## Decisions (the user's, 2026-10-24)

1. **Names**: directory and distribution `mr-muncher`, import package `mr_muncher`, console
   script unchanged. Folders `src/games/`, `src/demos/` and `src/apps/` (Bitmappy is an
   application, not a game or demo; `src/apps/` also fits the API server and client should
   they move).
   (Since then: Part 2 removed one console script, `brave-adventurer-papyrus`, when Brave
   Adventurer and Papyrus became one project with the `brave-adventurer` launcher; Part 3 added
   console scripts to the demos (`dt-demo`, `joystick-demo`, `text-input-demo`, 2026-10-26). The
   Arcade is an app too, `src/apps/arcade/`,
   the user, 2026-10-25: `plans/2026-10-23-arcade-showcase.md`.)
2. ~~**Recordings keep replaying unchanged** through `PREVIOUS_MODULES`~~: replaced by decision
   8 (2026-10-25). Part 1's Task 2 built it; Part 1's Task 5 removes it.
3. **Each package's tests and golden replay live inside it** (`src/games/mr-muncher/tests/`).
   As built in Part 2 (#109) and kept by Part 4: the tests directory is rootless (no
   `__init__.py`, never a package named `tests`), each test module is named for its package,
   `test_<package>_<area>.py` (the user, 2026-10-26, for Bitmappy: "Explicit is better than
   implicit"), test file names are unique across every test root
   (`tests/test_suite_collection.py::test_test_file_names_are_unique_across_packages`), and a
   member `conftest.py` is allowed (`docs/architecture/game_packages.md`, step 1).
4. **100% coverage everywhere**: coverage measures the engine and every member, and the gate
   stays at 100% (a 100% total means every file is at 100%, so each package is).
5. **Bitmappy's sprites** (`src/glitchygames/examples/resources/sprites`: its AI training data, the
   `examples:` save/load prefix, the PyInstaller spec) **move with Bitmappy** to
   `src/apps/bitmappy/`. (2026-10-26, Part 4: the library is package data at
   `src/apps/bitmappy/bitmappy/resources/sprites/`, read through `bitmappy.SPRITE_CONFIG_DIR`.
   The user removed the `examples:` prefix instead of moving it: "We shouldn't treat examples
   specially anymore". The Load and Save dialogs use a file name as given, whitespace trimmed,
   and Save refuses a ':' where the platform gives it a meaning: refused on macOS; on Windows
   allowed only in a letter-drive designator (`C:\`, `C:/`, `C:a`, `\\?\C:\`, `\\.\C:\`),
   so a UNC name may not contain one; allowed on Linux and in the browser
   (`src/glitchygames/ui/dialogs.py` `_file_name_problem`).)
6. **The browser IDE** (Part 5) is planned as MVP + Good; Better and Best are follow-ups.
7. **Everything under `src/`** (the user, 2026-10-25): four layers, `src/glitchygames/` (the
   engine), `src/games/<game>/`, `src/apps/<app>/`, `src/demos/<demo>/`. The engine moves too,
   "to avoid accidental package imports in the root": with `./glitchygames/` at the root, pytest
   (whose root `conftest.py` puts the root on `sys.path`) and anything else run from the root
   imported the source tree instead of the installed package, so nox's non-editable install was
   never what the tests ran. With the engine in `src/`, tests and tools run from the root must
   import the installed package (since Part 4 no test edits `sys.path`:
   `tests/test_suite_collection.py::test_no_test_edits_sys_path`). The import name stays
   `glitchygames`. (Replaces the
   2026-10-24 layout: `games/`, `demos/`, `apps/` at the root and the engine at
   `./glitchygames/`.)
8. **Recordings name games by logical names** (the user, 2026-10-25; replaces decision 2): a
   logical name mirrors the four layers, `<layer>.<module path inside the package, starting
   with the package name>:<qualified name>` (`games.mr_muncher.game:MrMuncherScene`,
   `games.paddleslap:Game`, `demos.joystick_demo:Game`, `apps.bitmappy...`); engine modules
   (and any module in no layer) keep their own path (`glitchygames.scenes...`). The layer comes
   from the workspace member that owns the class's top-level import package
   (`src/<layer>/<member>/`). Because the engine needs it at run time and an installed engine
   has no workspace to read (nor may it import `scripts/`), the layers are data in the engine,
   `src/glitchygames/logical_names.py`: `MEMBER_LAYERS` (kept equal to what
   `scripts/workspace_packages.py` reads by a test) and `EXAMPLES_LAYERS` for the games and
   demos still in `src/glitchygames/examples/` (paddleslap, brave_adventurer,
   brave_adventurer_papyrus, clockwork_keep, mr_muncher -> games; dt_demo, joystick_demo,
   text_input_demo -> demos), deleted when the last one leaves. One function maps a class to
   its logical name; the header (`game`) and every scene start (`scene`) record it; the header
   check and the scene lookup compare logical names; a recording without `game` (the old
   format) is compared by its exact recorded module; a rebaseline writes the current game's
   logical name into NEW. A test checks every committed recording's logical names resolve to a
   real module and class. The six committed recordings are converted once, by rebaseline on
   the current code, before anything moves, each NEW replayed strictly (Part 1, Task 6): the
   recordings change only by that conversion. A game's move then needs nothing for its
   recordings: its logical name does not change.
   (Since then: after Part 2, `EXAMPLES_LAYERS` named only the three demos, and Part 3 deleted
   it (2026-10-26). Part 4 met the one exception to "a move needs nothing": a package that was in no
   layer.
   Bitmappy's logical name changed from `glitchygames.bitmappy.editor:BitmapEditorScene` to
   `apps.bitmappy.editor:BitmapEditorScene`, so a plain replay refuses a recording made before
   its move, naming the remedy, and `--replay-trace OLD --rebaseline NEW --headless` converts it:
   a rebaseline compares the game and scenes by qualified name and writes the current logical
   names; `docs/architecture/game_packages.md`, "A member that was never in a layer".)
9. **Where recordings live** (the user, 2026-10-25): a game's bundled demos ship inside its
   import package, `<package>/demos/<name>.jsonl.gz` (PaddleSlap's in Part 2:
   `src/games/paddleslap/paddleslap/demos/rally.jsonl.gz`); its golden replays live with its
   tests, `<member>/tests/fixtures/replays/golden.jsonl.gz` (Mr. Muncher's in Part 1:
   `src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz`), and the golden plugin collects
   them across members, so the engine's suite still runs every one; the engine's root `tests/`
   keeps only recordings of its own (engine features without a real game).
   `RECORDING_PATH_RENAMES` keeps each moved recording's performance history connected (one
   line per moved recording) until logical recording ids replace it (Future work).
10. **A member declares what it imports** (the user, 2026-10-26, for Bitmappy; the user
    confirmed it for the demos the same day): its `pyproject.toml` lists every distribution its
    package imports (Bitmappy's: `glitchygames`, `aisuite` with the root's extras, `numpy`,
    `pydantic`, `pygame-ce`, `tenacity`), and a dependency only a member imports moves out of
    the root (`tenacity`). The demos follow this rule (Part 3, 2026-10-26). The five games, moved
    earlier,
    still list only `glitchygames`; backfilling them is a small follow-up (Future work).

## What every part keeps true

- `main` works after each part: the whole suite passes on both drivers at 100% coverage, every
  golden replay matches, `nox -s lint` and `static-analysis` pass, the docs build strictly, and
  `nox -s build-wheel` builds every package's wheel (Part 4): the engine's holds only
  `glitchygames/` at its top level, and each member's holds its package with its package data.
- The engine's guards (doors, randomness, the recording pump seam) scan every member package,
  not only `src/glitchygames/`, so moving a game never moves it out of their reach.
- A new member is caught if it is left out of any tool's configuration
  (`tests/test_workspace_config.py`, Part 1), and each layer's extra (`games`, `demos`, `apps`)
  names exactly its members.
- Nothing under the repository root is importable as a package of ours: the engine and every
  member live under `src/`, and `tests/test_suite_collection.py` checks that `import
  glitchygames` resolves to the installed package (Part 1). Coverage maps the installed copies
  back to `src/` (`[tool.coverage.paths]`), so the report names the files in the repository.
- A moved recording keeps its run-ledger history (`RECORDING_PATH_RENAMES`,
  `src/glitchygames/recording_metrics.py`, Part 1): the engine's move already moves PaddleSlap's
  bundled demo, and every later move adds one line per moved recording (old and new path).
- Every committed recording names its game and scenes by logical names that resolve
  (`tests/replay/test_recording_logical_names.py`, Part 1), and the engine's `MEMBER_LAYERS`
  equals the workspace (`tests/test_workspace_config.py`). Recordings change only by Part 1's
  one conversion; a move changes no recording's bytes.
- Recordings live where decision 9 puts them: a member's goldens in
  `<member>/tests/fixtures/replays/`, its demos in `<package>/demos/`, the root `tests/` only
  the engine's own (since Part 2: none; `tests/test_workspace_packages.py` checks that no
  game's is there).
- Tests import the installed packages: no test file, the engine's or a member's, edits
  `sys.path` (`tests/test_suite_collection.py::test_no_test_edits_sys_path`, Part 4).
- Member test modules are named for their package and never repeat a name across test roots
  (decision 3). Part 4 guards Bitmappy's at any depth
  (`tests/test_suite_collection.py::test_bitmappys_test_modules_are_named_for_it`); Part 3
  (2026-10-26) extended the guard to every member.
- Each moved package's move tests are one file per subject (logical_names, install_location,
  wheel, package_data, entry_points, recording_history), named for the member; the install-location
  one asserts its old module is gone (`importlib.util.find_spec(...) is None`), so a leftover
  ignored `__pycache__` fails a test instead of shadowing the member.
- The engine points nowhere into a member: Part 4 guards Bitmappy
  (`tests/test_workspace_config.py::test_the_engine_outside_bitmappy_points_nowhere_into_it`,
  `tests/test_suite_collection.py::test_no_engine_test_imports_bitmappy`); Part 3 (2026-10-26)
  extended the guards to every member package (see the next items).
- Every member's packages are under `<member>/src/` (`tests/test_workspace_config.py::
  test_every_member_keeps_its_packages_under_src`).
- No engine code and no root test imports a member, apart from the listed exemptions
  (`MEMBER_IMPORT_EXEMPT_MODULES`, `MEMBER_IMPORT_EXEMPT_NAMES`: the golden-replay control tables
  and the per-game world rules in `tests/world/test_golden_traces.py`). Engine tests use
  stand-ins or discover members through the workspace and assert hand-written expectations
  (`tests/workspace_expectations.py`); `docs/architecture/game_packages.md`, step 5.
- Member tests are named for their member (`test_<distribution with - as _>*.py`, at any depth),
  and their move tests are split by subject, never one `_after_the_move` file.
- The engine's own wheel is tested (`tests/test_engine_wheel.py`): its package, four sounds and
  two sprites, no member.
- Browser bundles leave out ignored files: the engine archive is built from the files git does not
  ignore (an ignored file never ships; a new, not-yet-added file still does).
- Wall-clock timings live in benchmarks, never in the normal suite.
- A check fed by a glob or a list asserts that its input is not empty, since an empty
  parametrize only skips (for example
  `tests/examples/test_examples_sprites.py::test_the_animated_sprite_checks_have_sprites_to_run_on`,
  which Part 3 moved into `glitchygames.testing.sprite_files`, 2026-10-26).
- A check of a directory's contents reads the names git tracks, never the file system, so an
  ignored file (`.DS_Store`) cannot fail it, and runs git without the ambient `GIT_*` variables,
  so it also works inside a hook (`tests/test_workspace_packages.py` `tracked_entry_names`).

## Parts

### Part 1: Foundation and the Mr. Muncher pilot (DONE)

Full plan:
[2026-10-24-workspace-packages-1-foundation.md](2026-10-24-workspace-packages-1-foundation.md).
The shared, risky work, proven on one game: the workspace, the test harness as a plugin every
package's tests get, logical names in recordings (replacing Task 2's `PREVIOUS_MODULES`) and the
one conversion of the six committed recordings, the engine moved to `src/glitchygames/` (after
the conversion, before any member: every tool, script and test path follows it, and the root
stops being importable),
guards and tool configuration over every member, the replay plugin and session recorder finding
games by an explicit map instead of the `glitchygames.examples` prefix, the browser build
shipping each game's package as its own archive, the run ledger following a moved recording's
history, and Mr. Muncher moved to `src/games/mr-muncher/` (its golden replay to
`src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz`, collected by the golden plugin
from the member). Done 2026-10-25 in twelve tasks: 1-4 the workspace and harness, 5 logical
names, 6 the conversion, 7 the engine to `src/`, 8 the configuration checks, 9 Mr. Muncher, 10
the browser build, 11 docs, 12 verification; merged as #105.

### Part 2: The other five games (DONE)

Full plan: [2026-10-25-workspace-packages-2-games.md](2026-10-25-workspace-packages-2-games.md).
Done 2026-10-25 (commits 46a6ca20 to "Workspace packages, Part 2: every game is its own
package"). The games are mr-muncher (Part 1), clockwork-keep, brave-adventurer, paddleslap and
drawing-fire. As built, Brave Adventurer and Papyrus became one project, not two members: one
member, `src/games/brave-adventurer/`, with four import packages (`brave_adventurer_core`,
`brave_adventurer`, `brave_adventurer_papyrus`, `brave_adventurer_modes`) and one console script,
the launcher `brave-adventurer` (`--game classic|papyrus`); `brave-adventurer-papyrus` is gone.
The outline as written:

- Clockwork Keep, then Brave Adventurer, then Brave Adventurer Papyrus (depends on
  `brave-adventurer`: a member depending on a member; its sprite TOMLs ship as package data),
  then PaddleSlap, then Drawing Fire (added 2026-10-25: it was written after this outline), each
  to `src/games/<game>/`.
- PaddleSlap stays importable as `paddleslap` (logical name `games.paddleslap:Game`, the same
  before and after). Its bundled demo moves into its package
  (`src/games/paddleslap/paddleslap/demos/rally.jsonl.gz`, decision 9); bundled-demo discovery
  (`src/glitchygames/testing/replays.py` `bundled_demo_paths`, which today builds
  `glitchygames.examples.<game>` from the `<game>_demos` folder name) finds demos through each
  member's package (`<package>/demos/`), and the demo's ledger history follows it (one more
  `RECORDING_PATH_RENAMES` line). `ball._debug_positions` gets a public read-only API on
  `BallSprite`, so PaddleSlap uses no engine-private name.
- Each game: its entry moves from `EXAMPLES_LAYERS` to `MEMBER_LAYERS` (its recordings need
  nothing else: logical names do not change), its tests move, its golden replay moves to
  `<member>/tests/fixtures/replays/golden.jsonl.gz` (one `RECORDING_PATH_RENAMES` line), the
  golden-trace harness (`scripts/record_golden_traces.py`) and browser specification updated.
- Ends with `src/glitchygames/examples/` holding only the demos and Bitmappy's resources, and
  the root `tests/fixtures/replays/` holding only the engine's own recordings.

### Part 3: The three demos (outline; DONE 2026-10-26, Stages A, B and C)

Starts from the untracked draft `plans/2026-10-25-workspace-packages-2-games-demos-apps.md`
(Tasks 10-12, the demos, and 18, `examples/` deleted), corrected against #109 and Part 4. Its
`tests/<package>_tests/` packages, its `test_logical_names_after_the_move.py` per demo, its
`tests.moved_games` helper, its "member declares imports" guard and its Task 12 `MEMBER_LAYERS`
(six games) are stale; its per-demo `pyproject.toml`, root configuration checklist, `perl`
rewrites and Task 18's references guard are still useful. Part 3 is the mechanical move only
(the user, 2026-10-26): the demos experience, `plans/future-features.md` #57, is planned
afterward, on top of these members.

**Every member in a `src/` layout** (the user, 2026-10-26: "make each game be
<game>/src/<game>, and each app be <app>/src/<app>, same with demo. This follows best practices
for package design"; folded into Part 3 at the user's choice). A member's import package lives at
`<member>/src/<package>/`, never at the member's root, so nothing in the member directory can be
imported by accident in place of the installed package.
- **The demos** are created this way: `src/demos/<demo>/src/<package>/`.
- **The existing members are converted:** Bitmappy (`src/apps/bitmappy/src/bitmappy/`),
  Clockwork Keep, Drawing Fire, Mr. Muncher and PaddleSlap (`src/games/<game>/src/<package>/`).
  Brave Adventurer is already laid out this way (`src/games/brave-adventurer/src/`) and is the
  precedent; `WorkspaceMember.import_roots` (`scripts/workspace_packages.py`) already handles it.
- **Per member:**
  - `git mv <member>/<package> <member>/src/<package>`, then `rm -rf` the old directory, since
    ignored `__pycache__` left behind is importable.
  - In the member's `pyproject.toml`, hatch `packages = ["src/<package>"]`.
  - Root configuration:
    - coverage `[tool.coverage.paths]`
    - ruff `src`, ty `root` and `src.include`
    - the pyright environments' `root` and `extraPaths`
    - `noxfile.py` `_SOURCE_PACKAGE_DIRS`
    - `wily.cfg` `path`
    - mkdocstrings `paths`
  - The checks in `tests/test_workspace_config.py` are written per import root, so they cover
    every member.
- **PaddleSlap's bundled demo moves a third time**
  (`src/games/paddleslap/paddleslap/demos/rally.jsonl.gz` → `.../src/paddleslap/demos/...`), with
  its bytes unchanged. It needs a `RECORDING_PATH_RENAMES` line from each old path, so its
  run-ledger history stays one series. Package names don't change, so no logical name or
  recording changes.
- **Bitmappy:**
  - `bitmappy.spec` takes its `datas` from `src/apps/bitmappy/src/bitmappy/resources`.
  - `scripts/audit_hitboxes.py` `PRIORITY_TIERS` follows.
  - So do the browser bundle's member package directory (`scripts/build_browser_bundle.py`) and
    the packaging tests (`test_bitmappy_packaging.py`, `test_bitmappy_after_the_move.py`).
- **A guard:** every workspace member keeps its import packages under `<member>/src/`, and none
  at the member's root (`tests/test_workspace_config.py`, read from the workspace), so a future
  member can't slip back.
- **Docs:** the recipe's "What a member is" layout and its `pyproject.toml` template
  (`docs/architecture/game_packages.md`), its flat-layout notes, `CLAUDE.md`, `README.md`, and
  each `docs/games/<game>.md` file table.

- `src/demos/dt-demo/`, `src/demos/joystick-demo/`, `src/demos/text-input-demo/`, the first
  members of the `demos` layer (its extra, ruff and ty test globs, deptry exclude, and a "Demos
  API Reference" nav section come with the first), each with a console script (`dt-demo`,
  `joystick-demo`, `text-input-demo`; today they have none). Each module becomes its package's
  `__init__.py`, so its classes keep their logical names (`demos.<package>:<class>`), and its
  `if __name__ == '__main__'` block moves to `<package>/__main__.py`, as PaddleSlap's did
  (`docs/architecture/game_packages.md`, "A game that is one module"), so `python -m
  <package>` runs it; docstrings that say `python -m glitchygames.examples.<demo>` follow. Each
  demo declares everything it imports (decision 10), `glitchygames` and `pygame-ce` at least.
- Tests are rootless, `src/demos/<demo>/tests/` (`test_dt_demo.py` and its siblings already fit
  `test_<package>*`), each with a `test_<package>_after_the_move.py`. Their shared run helper,
  `tests/examples/demo_runs.py`, imports `scripts.record_golden_traces`, so it stays a root test
  helper (`tests/demo_runs.py`) that the demos' tests import.
- The joystick demo's `Game` deliberately shares its name with PaddleSlap's
  (`tests/replay/test_playback_scope.py`, `tests/replay/test_bundled_demos.py`): both stay loaded,
  told apart by `demos.joystick_demo:Game` and `games.paddleslap:Game`.
- With the demos out, `EXAMPLES_LAYERS` and `EXAMPLES_PACKAGE` are deleted, with the examples
  branches of `logical_module_name` and `module_for_logical_module`
  (`src/glitchygames/logical_names.py`) and the tests pinning them (`tests/test_logical_names.py`);
  `MEMBER_LAYERS` gains the three demos (12 entries). No committed recording is of a demo, so no
  `RECORDING_PATH_RENAMES` line; an old-format recording of one is refused by a plain replay and
  converted by `--rebaseline` (Part 4).
- The shared sprite-file checks move into an engine testing helper,
  `src/glitchygames/testing/sprite_files.py`, importable by any member (the user, 2026-10-26).
  `tests/examples/test_examples_sprites.py` checks the engine's own sprites (`assets/`,
  `tests/fixtures/sprites/`), not the examples, and two members import it today: Papyrus
  (`src/games/brave-adventurer/tests/papyrus/test_brave_adventurer_papyrus_sprite_files.py`)
  and Bitmappy (`src/apps/bitmappy/tests/test_bitmappy_sprite_library.py`); both switch to the
  helper. The engine's own run of the checks becomes `tests/sprites/test_engine_sprite_files.py`.
  The dead `ENGINE_PACKAGE_DIRECTORY` branch in `_animated_sprite_file_test_id` goes (the engine
  bundles no animated sprite).
- `foo2.toml` moves to `tests/fixtures/sprites/foo2.toml`, beside the engine's other sprite
  fixtures, for the one test that reads it (`tests/sprites/test_animated_sprite.py`
  `test_bundled_foo2_example_keeps_its_alpha`). It is animated, so the animated-sprite checks
  that glob that directory gain it as a case.
- The four WAVs in `src/glitchygames/examples/resources/snd/` (nothing references them) are
  kept as engine resources (the user, 2026-10-26): they move to
  `src/glitchygames/resources/sounds/`, engine package data shipped in the engine's wheel and
  the browser engine archive.
- Ends with `src/glitchygames/examples/` gone (moved here from Part 4's outline): out of the
  engine's wheel and its browser archive (`scripts/build_browser_bundle.py`), and out of
  `docs/glitchygames/examples/index.md`, `mkdocs.yml`, `docs/glitchygames/index.md` and the
  `norecursedirs` comment in `pyproject.toml`. The engine wheel check gains a
  check that `src/glitchygames/examples/` is absent.
  `tests/test_workspace_packages.py::test_the_engines_examples_hold_only_the_demos_and_their_resources`
  becomes a check that the directory is gone, and a guard (the draft's
  `former_examples_references`) keeps code and living docs from naming it. This plan names it
  on purpose, so the guard must exempt this plan.
- Part 4's Bitmappy-only guards become every member's (the user, 2026-10-26): test modules named
  for their package (every member's `*_after_the_move.py` is split by subject: logical_names,
  install_location, wheel, package_data, entry_points, recording_history), and no engine source or
  test configuration pointing into
  a member package. Their Bitmappy leftovers go: the vestigial `'bitmappy/'` skip in
  `tests/test_workspace_config.py` `engine_files_pointing_into_bitmappy` (and the self-test case
  that plants `bitmappy/inside.py`), and its `'examples', 'resources', 'sprites'` path check
  once `examples/` is gone.

### Part 4: Bitmappy as an app (DONE)

Full plan:
[2026-10-26-workspace-packages-4-bitmappy.md](2026-10-26-workspace-packages-4-bitmappy.md).
Done 2026-10-26 (commits a97efbe9..1d0994a0 at present, the last hash pinned at merge; the
user's manual checks passed the same day, then a final-review fix pass). As built, beyond the
outline: `--rebaseline` converts a recording whose classes moved to another logical module
(Bitmappy's logical name changed, decision 8); the engine's tests import the installed packages
with no `sys.path` edits, and a guard; `nox -s build-wheel` builds every package's wheel;
Bitmappy's tests are named `test_bitmappy_*.py`, guarded at any depth; the member declares
everything it imports (`tenacity` left the root, decision 10); the `examples:` prefix is removed,
not moved (decision 5). Part 3 then did what was left (2026-10-26): `src/glitchygames/examples/`,
`EXAMPLES_LAYERS`
and the shared sprite checks in `tests/examples/test_examples_sprites.py` are gone or moved. The
outline as written:

- `src/apps/bitmappy/` (distribution `bitmappy`, import package `bitmappy`, console script
  `bitmappy` unchanged) with its sprites. Engine code that points into Bitmappy or its sprites
  (`src/glitchygames/ui/dialogs.py` `examples:` prefix, `src/glitchygames/bitmappy/utils.py`
  `SPRITE_CONFIG_DIR`, the API routes, services) is separated: what is generic stays in the
  engine, what is Bitmappy's moves. `bitmappy.spec`, its PyInstaller hooks, the browser build's
  `included_subpackages` and the Bitmappy docs follow. The biggest part: a survey of the
  engine's references into `src/glitchygames/bitmappy/` comes first.
- (Its "Ends with `src/glitchygames/examples/` gone" moved to Part 3: Part 4 ran first, so the
  demos were still there. Part 3 then moved them and deleted `examples/`.)

### Part 5: A browser IDE on each game's page (outline)

On each game's browser page, `play/<game>/` (built by `scripts/build_browser_bundle.py` from
`browser/index.html`; the user, 2026-10-26: the IDE lives there, and the game's docs page,
`docs/games/<game>.md`, links to it), beside the running game: the game's package files, an
editor, and save to rerun. The game's code comes from its member packages: the browser build
ships each as its own archive (`<package>.zip`), and a game may ship several
(`GameSpecification.member_packages`, dependencies first: Brave Adventurer's games ship
`brave_adventurer_core` too). The file tree shows the game's own package as editable and the
packages it depends on as read-only. Where edits live is `plans/future-features.md` #58 (game
project workspaces): the MVP keeps them per game in the browser, and #58's workspace is where
they go later.

- **MVP**: a file tree of every file in the game's package and a code editor (CodeMirror, a
  pinned CDN version); edits kept per game in the browser (IndexedDB); Save starts a fresh
  Pyodide with the engine archive plus the edited package files written into its filesystem,
  then the game (a clean interpreter each save: no stale module or pygame state); a console
  pane with output and tracebacks; Reset returns to the published package.
- **Good**: a syntax check before restarting (errors shown inline), a diff against the published
  package and per-file revert, download the edited package as a zip.
- **Better** (follow-up): hot reload in a warm Pyodide (unload the game's modules, reimport,
  restart the scene; fall back to a fresh start; it needs the engine's per-run state held per
  context, `plans/2026-10-25-engine-context.md`), ruff in WebAssembly, and a replay check: run
  the game's golden replay against the edits and show the first divergent frame.
- **Best** (follow-up): add, rename and delete files; edit sprite TOMLs in an embedded Bitmappy (its
  own archive, `bitmappy.zip`, loaded beside
  the game's; the files in a #58 workspace);
  run the package's tests in the browser; autocomplete; shareable links carrying edits.

## Future work

- Recording naming convention and logical ids (future-features #55): standard recording names
  and a logical recording id (`games.mr_muncher:golden`, `games.paddleslap:demo/rally`) derived
  from a recording's location and checked by a test; the performance ledger re-keyed by id, so
  moves need no `RECORDING_PATH_RENAMES`.
- Game project workspaces (future-features #58): a workspace holding a game's own files, which
  the tools open instead of reaching into the engine or an app; a new workspace bundles starter
  material such as Bitmappy's sprite library. Part 5's IDE stores its edits there once it exists.
- The demos experience (future-features #57): the demos as browsable, pygame-examples-like
  examples, planned after Part 3's mechanical move (the user, 2026-10-26).
- Bitmappy's tests organized by input API and by module (future-features #59), under the
  member naming guard.
- Part 2's leftovers (future-features #56): a public testing helper in
  `src/glitchygames/testing/` for the engine seams member tests use (`SceneManager._reset`,
  `FontManager._font_cache`), ending the exemption in `docs/architecture/game_packages.md`.
- Backfill the five games' `pyproject.toml` with everything each imports, `pygame-ce` at least
  (decision 10; a small follow-up).
- The two `detect_file_format` functions (`plans/future-work.md`, "Sprite file-format detection",
  Part 4).
