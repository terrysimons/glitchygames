# Games, Demos and Apps as Their Own Packages (master plan)

Status: IN PROGRESS. Part 1 DONE on feature/workspace-packages-foundation (2026-10-25: the
src/ layout, Mr. Muncher as a member, logical names; commits e864215c..73a60265, 22 commits, verified
by Task 12; merged as #105, b29f85fc). Part 2 DONE on feature/workspace-packages-2-games
(2026-10-25: every game is its own package, five members under `src/games/`: mr-muncher (Part 1),
clockwork-keep, brave-adventurer (one project: core, Classic, Papyrus and a launcher), paddleslap
and drawing-fire; commits 46a6ca20 to "Workspace packages, Part 2: every game is its own
package", 26 commits, verified by Task 9; merged as #109, a97efbe9). Part 4 DONE on
feature/workspace-packages-4-bitmappy (2026-10-26: Bitmappy is its own package, `src/apps/bitmappy/`;
commits a97efbe9..through the final-review fix commits, first fix commit f0620b6d, hash pinned at
merge; the user's manual checks passed 2026-10-26, see
[its plan](2026-10-26-workspace-packages-4-bitmappy.md); not yet merged). Plan written 2026-10-24; amended 2026-10-25: everything under `src/`,
decision 7; logical names in recordings, decision 8; where recordings live, decision 9.
Part 1 has a full implementation plan; Parts 2-5 are outlined here and get theirs when each
starts, written against how Part 1 turned out.

Sub-plans:
- Part 1: [Foundation and the Mr. Muncher pilot](2026-10-24-workspace-packages-1-foundation.md)
- Part 2 (DONE): [The other five games](2026-10-25-workspace-packages-2-games.md) (Clockwork
  Keep, Brave Adventurer with Papyrus as one project, PaddleSlap and Drawing Fire, which postdates
  the outline; the move recipe is `docs/architecture/game_packages.md`)
- Part 3: The three demos (outline below)
- Part 4 (DONE): [Bitmappy as an app](2026-10-26-workspace-packages-4-bitmappy.md)
- Part 5: A browser IDE on each game's page (outline below)

## Why

The example games live inside the engine's package (`src/glitchygames/examples/`) and ship in its
wheel. Moving each into its own package beside the engine:

- **makes a game's code path easy to review**: a game change is one directory, its code, tests
  and golden replay together, read against the engine's public API;
- **makes the games prove the public API**: a game depends on `glitchygames` like any third-party
  game would, so reaching into engine internals becomes a visible decision (today only
  PaddleSlap does: `ball._debug_positions`);
- **slims the engine's wheel**: game code, sprites and demos stop shipping in `glitchygames`;
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
golden replay directly in `tests/fixtures/replays/` (`golden.jsonl.gz`; decision 9).

## Decisions (the user's, 2026-10-24)

1. **Names**: directory and distribution `mr-muncher`, import package `mr_muncher`, console
   script unchanged. Folders `src/games/`, `src/demos/` and `src/apps/` (Bitmappy is an
   application, not a game or demo; `src/apps/` also fits the API server and client should
   they move).
2. ~~**Recordings keep replaying unchanged** through `PREVIOUS_MODULES`~~: replaced by decision
   8 (2026-10-25). Part 1's Task 2 built it; Part 1's Task 5 removes it.
3. **Each package's tests and golden replay live inside it** (`src/games/mr-muncher/tests/`).
4. **100% coverage everywhere**: coverage measures the engine and every member, and the gate
   stays at 100% (a 100% total means every file is at 100%, so each package is).
5. **Bitmappy's sprites** (`src/glitchygames/examples/resources/sprites`: its AI training data, the
   `examples:` save/load prefix, the PyInstaller spec) **move with Bitmappy** to
   `src/apps/bitmappy/`. (2026-10-26: the user removed the `examples:` prefix instead of moving it:
   "We shouldn't treat examples specially anymore". The Load and Save dialogs use a file name as
   given, whitespace trimmed.)
6. **The browser IDE** (Part 5) is planned as MVP + Good; Better and Best are follow-ups.
7. **Everything under `src/`** (the user, 2026-10-25): four layers, `src/glitchygames/` (the
   engine), `src/games/<game>/`, `src/apps/<app>/`, `src/demos/<demo>/`. The engine moves too,
   "to avoid accidental package imports in the root": with `./glitchygames/` at the root, pytest
   (whose root `conftest.py` puts the root on `sys.path`) and anything else run from the root
   imported the source tree instead of the installed package, so nox's non-editable install was
   never what the tests ran. With the engine in `src/`, tests and tools run from the root must
   import the installed package. The import name stays `glitchygames`. (Replaces the
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
9. **Where recordings live** (the user, 2026-10-25): a game's bundled demos ship inside its
   import package, `<package>/demos/<name>.jsonl.gz` (PaddleSlap's in Part 2:
   `src/games/paddleslap/paddleslap/demos/rally.jsonl.gz`); its golden replays live with its
   tests, `<member>/tests/fixtures/replays/golden.jsonl.gz` (Mr. Muncher's in Part 1:
   `src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz`), and the golden plugin collects
   them across members, so the engine's suite still runs every one; the engine's root `tests/`
   keeps only recordings of its own (engine features without a real game).
   `RECORDING_PATH_RENAMES` keeps each moved recording's performance history connected (one
   line per moved recording) until logical recording ids replace it (Future work).

## What every part keeps true

- `main` works after each part: the whole suite passes on both drivers at 100% coverage, every
  golden replay matches, `nox -s lint` and `static-analysis` pass, the docs build strictly.
- The engine's guards (doors, randomness, the recording pump seam) scan every member package,
  not only `src/glitchygames/`, so moving a game never moves it out of their reach.
- A new member is caught if it is left out of any tool's configuration
  (`tests/test_workspace_config.py`, Part 1).
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

## Parts

### Part 1: Foundation and the Mr. Muncher pilot

Full plan: [2026-10-24-workspace-packages-1-foundation.md](2026-10-24-workspace-packages-1-foundation.md).
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
from the member). Task order: 1-4 (done), 5 logical names, 6 the conversion, 7 the engine to
`src/`, 8 the configuration checks, 9 Mr. Muncher, 10 the browser build, 11 docs, 12
verification.

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

### Part 3: The three demos (outline)

- `src/demos/dt-demo/`, `src/demos/joystick-demo/`, `src/demos/text-input-demo/` (console scripts added:
  today they have none). The joystick demo's `Game` deliberately shares its name with
  PaddleSlap's (`tests/replay/test_playback_scope.py`): that test keeps both loaded (their
  logical names, `demos.joystick_demo:Game` and `games.paddleslap:Game`, tell them apart).
- With the demos out, nothing is left in `src/glitchygames/examples/` that `EXAMPLES_LAYERS` names:
  the table is deleted (decision 8) along with its `glitchygames.examples` prefix handling.
- Ends with `src/glitchygames/examples/` gone (moved here from Part 4's outline).
- `foo2.toml` moves to the one test that uses it; the four unused `src/glitchygames/examples/resources/snd/*.wav`
  are listed for the user to keep or delete (nothing references them).

### Part 4: Bitmappy as an app (DONE)

Full plan: [2026-10-26-workspace-packages-4-bitmappy.md](2026-10-26-workspace-packages-4-bitmappy.md).
Done 2026-10-26 (commits a97efbe9..through the final-review fix commits, first fix commit
f0620b6d; the hash is pinned at merge; the user's manual checks passed the same day). The outline as written:

- `src/apps/bitmappy/` (distribution `bitmappy`, import package `bitmappy`, console script
  `bitmappy` unchanged) with its sprites. Engine code that points into Bitmappy or its sprites
  (`src/glitchygames/ui/dialogs.py` `examples:` prefix, `src/glitchygames/bitmappy/utils.py`
  `SPRITE_CONFIG_DIR`, the API routes, services) is separated: what is generic stays in the
  engine, what is Bitmappy's moves. `bitmappy.spec`, its PyInstaller hooks, the browser build's
  `included_subpackages` and the Bitmappy docs follow. The biggest part: a survey of the
  engine's references into `src/glitchygames/bitmappy/` comes first.
- (Its "Ends with `src/glitchygames/examples/` gone" moved to Part 3: Part 4 ran first, so the
  demos were still there. After Part 4, `examples/` holds the three demos and their resources.)

### Part 5: A browser IDE on each game's page (outline)

On `/games/<game>/` (docs/games/<game>.md), beside the running game: the game's package files,
an editor, and save to rerun. The game's code comes from its member package (Part 1 ships each
as its own archive in the browser build).

- **MVP**: a file tree of every file in the game's package and a code editor (CodeMirror, a
  pinned CDN version); edits kept per game in the browser (IndexedDB); Save starts a fresh
  Pyodide with the engine archive plus the edited package files written into its filesystem,
  then the game (a clean interpreter each save: no stale module or pygame state); a console
  pane with output and tracebacks; Reset returns to the published package.
- **Good**: a syntax check before restarting (errors shown inline), a diff against the published
  package and per-file revert, download the edited package as a zip.
- **Better** (follow-up): hot reload in a warm Pyodide (unload the game's modules, reimport,
  restart the scene; fall back to a fresh start), ruff in WebAssembly, and a replay check: run
  the game's golden replay against the edits and show the first divergent frame.
- **Best** (follow-up): add, rename and delete files; edit sprite TOMLs in an embedded Bitmappy;
  run the package's tests in the browser; autocomplete; shareable links carrying edits.

## Future work

- Recording naming convention and logical ids (future-features #55): standard recording names
  and a logical recording id (`games.mr_muncher:golden`, `games.paddleslap:demo/rally`) derived
  from a recording's location and checked by a test; the performance ledger re-keyed by id, so
  moves need no `RECORDING_PATH_RENAMES`.
