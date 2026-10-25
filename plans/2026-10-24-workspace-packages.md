# Games, Demos and Apps as Their Own Packages (master plan)

Status: PLANNED (2026-10-24). Part 1 has a full implementation plan; Parts 2-5 are outlined here
and get theirs when each starts, written against how Part 1 turned out.

Sub-plans:
- Part 1: [Foundation and the Mr. Muncher pilot](2026-10-24-workspace-packages-1-foundation.md)
- Part 2: The other four games (outline below)
- Part 3: The three demos (outline below)
- Part 4: Bitmappy as an app (outline below)
- Part 5: A browser IDE on each game's page (outline below)

## Why

The example games live inside the engine's package (`glitchygames/examples/`) and ship in its
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

```
glitchygames/                  the engine (unchanged place; loses examples/)
games/
  mr-muncher/                  pyproject.toml (distribution mr-muncher), mr_muncher/, tests/
  paddleslap/
  clockwork-keep/
  brave-adventurer/
  brave-adventurer-papyrus/    depends on brave-adventurer (it reuses its code)
demos/
  dt-demo/  joystick-demo/  text-input-demo/
apps/
  bitmappy/                    the pixel art editor, with its sprites
```

Each member is a uv workspace member (root `pyproject.toml` `[tool.uv.workspace]`): its own
`pyproject.toml` (hatchling, like the engine), its import package (`mr_muncher`: a hyphen
cannot be imported), its console script (`mr-muncher`, unchanged), and its own `tests/` with its
golden replay under `tests/fixtures/replays/<console-script>/`.

## Decisions (the user's, 2026-10-24)

1. **Names**: directory and distribution `mr-muncher`, import package `mr_muncher`, console
   script unchanged. Folders `games/`, `demos/` and `apps/` (Bitmappy is an application, not a
   game or demo; `apps/` also fits the API server and client should they move).
2. **Recordings keep replaying unchanged**: a scene class declares the modules it used to live
   in (`PREVIOUS_MODULES`), and a replay accepts a recording naming one of them. The committed
   recordings stay byte-for-byte as they are, so no content hash or measurement history
   changes. (Rejected: re-recording them, which replaces reviewed fixtures and restarts their
   history; rewriting their module names, which changes frame 0's content hash.)
3. **Each package's tests and golden replay live inside it** (`games/mr-muncher/tests/`).
4. **100% coverage everywhere**: coverage measures the engine and every member, and the gate
   stays at 100% (a 100% total means every file is at 100%, so each package is).
5. **Bitmappy's sprites** (`glitchygames/examples/resources/sprites`: its AI training data, the
   `examples:` save/load prefix, the PyInstaller spec) **move with Bitmappy** to `apps/bitmappy/`.
6. **The browser IDE** (Part 5) is planned as MVP + Good; Better and Best are follow-ups.

## What every part keeps true

- `main` works after each part: the whole suite passes on both drivers at 100% coverage, every
  golden replay matches, `nox -s lint` and `static-analysis` pass, the docs build strictly.
- The engine's guards (doors, randomness, the recording pump seam) scan every member package,
  not only `glitchygames/`, so moving a game never moves it out of their reach.
- A new member is caught if it is left out of any tool's configuration
  (`tests/test_workspace_config.py`, Part 1).

## Parts

### Part 1: Foundation and the Mr. Muncher pilot

Full plan: [2026-10-24-workspace-packages-1-foundation.md](2026-10-24-workspace-packages-1-foundation.md).
The shared, risky work, proven on one game: the workspace, `PREVIOUS_MODULES`, the test harness
as a plugin every package's tests get, guards and tool configuration over every member, the
replay plugin and session recorder finding games by an explicit map instead of the
`glitchygames.examples` prefix, the browser build shipping each game's package as its own
archive, the run ledger following a moved recording's history, and Mr. Muncher moved.

### Part 2: The other four games (outline)

- Clockwork Keep, then Brave Adventurer, then Brave Adventurer Papyrus (depends on
  `brave-adventurer`: a member depending on a member; its sprite TOMLs ship as package data),
  then PaddleSlap.
- PaddleSlap: its bundled demo moves with it (`paddleslap/demos/rally.jsonl.gz`); bundled-demo
  discovery (`glitchygames/testing/replays.py` `bundled_demo_paths`) changes from
  `glitchygames/examples/<game>_demos/` to each member's demos folder, and the demo's ledger
  history follows it (Part 1's rename map). `ball._debug_positions` gets a public read-only API
  on `BallSprite`, so PaddleSlap uses no engine-private name.
- Each game: `PREVIOUS_MODULES` on every scene class, tests and golden replay moved, the
  golden-trace harness (`scripts/record_golden_traces.py`) and browser specification updated.
- Ends with `glitchygames/examples/` holding only the demos and Bitmappy's resources.

### Part 3: The three demos (outline)

- `demos/dt-demo/`, `demos/joystick-demo/`, `demos/text-input-demo/` (console scripts added:
  today they have none). The joystick demo's `Game` deliberately shares its name with
  PaddleSlap's (`tests/replay/test_playback_scope.py`): that test keeps both loaded.
- `foo2.toml` moves to the one test that uses it; the four unused `examples/resources/snd/*.wav`
  are listed for the user to keep or delete (nothing references them).

### Part 4: Bitmappy as an app (outline)

- `apps/bitmappy/` (distribution `bitmappy`, import package `bitmappy`, console script
  `bitmappy` unchanged) with its sprites. Engine code that points into Bitmappy or its sprites
  (`glitchygames/ui/dialogs.py` `examples:` prefix, `glitchygames/bitmappy/utils.py`
  `SPRITE_CONFIG_DIR`, the API routes, services) is separated: what is generic stays in the
  engine, what is Bitmappy's moves. `bitmappy.spec`, its PyInstaller hooks, the browser build's
  `included_subpackages` and the Bitmappy docs follow. The biggest part: a survey of the
  engine's references into `glitchygames/bitmappy/` comes first.
- Ends with `glitchygames/examples/` gone.

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
