# Game Host (outer game) and Browser Runner — Plan

- **Date:** 2026-10-23
- **Status:** Approved 2026-10-23 ("Host wraps the doors"; "minimal implementation"). Branch
  `wasm/pygame-ce-fork` (worktree `../glitchygames-wasm`), on top of `cleanup/post-replay`.
  Steps 1-7 implemented 2026-10-23 (uncommitted; see Done below).
- **Why:**
  - **Browser:** the engine should run in a browser (PyScript/Pyodide; feasibility study in
    `../pygame-ce-wasm/`). Browsers must get control back between frames, but
    `SceneManager.start` is a blocking loop paced by `time.sleep`. That works only where Pyodide
    can suspend `time.sleep` (JS Promise Integration: Chrome, Firefox and Safari on macOS). It
    freezes iOS Safari.
  - **Outer game:** the user (2026-10-23): "I want to graft an outer game on top of the inner
    game even in normal non-replay scenarios. That outer layer should currently just forward all
    events to the inner game and should be transparent to the user. This will eventually allow
    us to do some interesting things with AI and event/call injection that the game will be
    unaware of."
- **Constraint:** minimal. Desktop behaviour, recordings and replays stay exactly as they are
  (golden traces, driver comparison).

## Today

- **The doors** (`glitchygames/sources.py`) are the only way input, frame time, devices, saves,
  clocks and the seed reach the engine. A live run installs `LiveSources`. `--record-trace`
  wraps them in `RecordingSources` (`recording.py`), which serves everything from `inner` and
  writes what passes through. Replays install `ReplaySources`.
- **A game inside a game already exists:** a watched replay (`replay/viewer.py`). The outer
  viewer ticks at a fixed rate, and an accumulator decides how many inner frames run per tick.
  The contract is asked through `EngineSources.hold_frame` and `paced_frame_seconds` inside
  `SceneManager.start`'s loop. The viewer's docstring names "an inner replay under a live outer
  game" as a later user of the same contract.
- **The frame loop is `SceneManager.start`:**
  - a prologue (frame clock, first dt, `mark_frames_started`);
  - a `while` over `hold_frame`, `timer.start_frame`, `_run_frame` and `_finish_frame`, which
    paces with `time.sleep` (`timing.py`);
  - an epilogue (`_log_quit_info`, `terminate`).
- **`GameEngine.start`** wraps `_run_game` in a crash boundary that turns every ending into an
  exit code, after the teardown.

## Proposal

1. **`HostSources`** (new, `glitchygames/host.py`): forwarding doors installed around the live
   doors, beneath the recorder.
   - A live run's doors become `HostSources(inner=LiveSources)`; with `--record-trace`,
     `RecordingSources(inner=HostSources(inner=LiveSources))`.
   - Every member forwards to `inner` unchanged today.
   - Being beneath the recorder, whatever the host later adds, hides or rewrites is what the
     recording holds, so a recording replays exactly without the host or its AI.
   - Replays keep their doors as they are: there the replay viewer is the outer game.
2. **`GameHost`** (new, `glitchygames/host.py`): the outer game object the engine creates for
   every live run (`GameEngine.host`). It owns the host doors and drives frames.
   - `run(scene_manager=...)` (blocking) is today's loop, unchanged: it calls
     `SceneManager.start`.
   - `async run_async(scene_manager=..., wait_for_tick=...)` runs one outer tick per awaited
     `wait_for_tick()` (a browser animation frame).
3. **Frame-loop steps on `SceneManager`**, so both drivers run the same code:
   - `begin_frames()` returns the first frame's start reading;
   - `frames_should_continue()`;
   - `run_frame_step(frame_start_seconds=..., paced=...)` runs one iteration of today's loop
     body and returns the next frame's start;
   - `end_frames()`.
   - `start()` becomes those four, with identical behaviour.
   - With `paced=False` (the async driver), the frame runs its own work but never sleeps. The
     outer tick is the wait.
4. **`TickPacer`** (new, `glitchygames/host.py`): the async driver's accumulator, in the
   viewer's style.
   - Each tick it adds the real time since the last tick. It runs one inner frame when the
     accumulator holds at least the frame period minus half a tick, so a 60 FPS game on a 120 Hz
     display runs every second tick, and on 60 Hz every tick.
   - After falling more than one period behind, it re-anchors instead of bursting (the
     `next_frame_deadline_ns` rule).
   - The period follows the doors: `paced_frame_seconds()`, else the scene manager's
     `target_fps`. 0 means every tick.
   - It also keeps the median tick interval, the display's measured refresh, which the async
     runner logs.
5. **`GameEngine.start_async(*, wait_for_tick)`**: the same crash boundary as `start()` (moved
   into a shared context manager, so both use one copy) around `prepare_run()` (today's
   `_run_game` up to the loop) and `await host.run_async(...)`.
6. **Small browser-readiness fixes:**
   - **R1:** `events/midi.py` imports `pygame.midi` optionally (no PortMidi in WebAssembly
     builds), and `input/devices.py` and `events/controller.py` treat a missing
     `pygame._sdl2.controller` as no controllers (stock Pyodide's pygame-ce lacks it).
   - **R2:** log `str(display_info)` (pygame-ce's VidInfo breaks `isinstance` on CPython 3.14.2).
   - **R4:** `glitchygames.state` save observers (`observe_saves(observer=...)`), called after
     each completed save, so a browser can flush IndexedDB right away.

## Steps

1. R2, R1 (tests: module absent → no crash, zero devices).
2. Frame-loop steps on `SceneManager`; `start()` rebuilt on them (existing tests unchanged).
3. `HostSources` + `GameHost.run`; the engine installs them for live runs; the recorder sees
   through `HostSources` for `first_open_save_snapshots` (tests: a live run's doors, a recorded
   run's layering, replays without a host).
4. `TickPacer`, `GameHost.run_async`, `GameEngine.start_async` (tests drive the async runner with
   a fake tick source on the dummy driver).
5. R4 save observers.
6. Browser launcher (`nox -s browser`, `browser/` shell outside the package) on top of
   `start_async`.
7. Docs: CLAUDE.md (engine components, doors), `docs/architecture`.

## Not now

- Injection features (AI input, hiding input, call injection): the seams are in place
  (`HostSources` for input, supervisors for calls).
- Watched replays in the browser: done 2026-10-24 (below).

## Done (2026-10-23)

- **Steps 1-5 (engine):** R1 (`pygame.midi` and `pygame._sdl2.controller` optional:
  `events/midi.py` `MIDI_MODULE`, `input/devices.py` `sdl_controller_module()`), R2 (Display
  Info logged as text), the frame-loop steps, `glitchygames/host.py` (`HostSources`, `TickPacer`,
  `GameHost`), the engine's shared `_crash_boundary` with `start_async`, and R4
  (`observe_disk_save_changes`).
  - Full suite: 19,714+ passed, 100% coverage; ruff and basedpyright clean project-wide.
  - Changed tests: `tests/world/test_gameplay_recording.py` (the recording now wraps
    `HostSources`); `tests/test_engine_doors.py` (the clock allow-list names the new steps).
- **Step 6 (browser launcher):**
  - `browser/` (`index.html`, `boot.py`, `browser_storage.py`) and
    `scripts/build_browser_bundle.py`, with tests in `tests/test_build_browser_bundle.py`.
  - `nox -s browser -- <game>`. The engine archive is 1.16 MB (Bitmappy, the API, services,
    testing, templates and the asset PNGs left out).
  - All four games verified in headless Chromium 141 and Playwright WebKit 26: they load, take
    the click, run at the display's rate measured by the host (60.0/58.8 Hz) with no errors,
    and take keys (PaddleSlap: Space restarts after game over).
  - Saves persist across a reload through the save observer's flush (IndexedDB holds
    `paddleslap/high_scores.json`).
- **Step 7:** CLAUDE.md (Game Host, the frame-loop steps, the doors' providers, the clock
  allow-list, save observers).

## Open issues found on the way

- **Fixed 2026-10-24 (BUGS.md #213), startup focus events:** the first batch held a focus loss
  and regain, so Mr. Muncher started paused. Cause: `SCALED` makes SDL recreate the window for
  an OpenGL renderer (once in the browser, twice on the dummy driver, never on macOS). The
  host's doors drop a loss given back within the same batch.
- **Fixed 2026-10-24, timer calibration:** `start_async` no longer calibrates the sleep timer
  (about 0.1 s of sleeps) it never paces with (`_prepare_run(paced_by_timer=False)`); the timer
  is still made, uncalibrated, for a recording's provenance.
- **Fixed 2026-10-23 (BUGS.md #212):** `ASSET_PATH` pointed into `glitchygames/engine/`, so the
  default window icon was never loaded.

## Bitmappy in the browser (2026-10-23, follow-up)

- **Lazy import:** `tenacity` (not in Pyodide) is imported when an AI request is made, not with
  `ai_worker`, so `glitchygames.bitmappy` imports without it. Test: the editor imports in a
  fresh interpreter whose `import tenacity` fails.
- **Feature flag:** `bitmappy/constants.AI_FEATURES_ENABLED` is `sys.platform != 'emscripten'`
  (off for WebAssembly only, the user's choice for now). With it off, `AIManager.setup` starts
  no worker process, and a prompt shows "AI features are off in this build".
- **Launcher:** `nox -s browser -- bitmappy`. `GameSpecification.included_subpackages` lets that
  bundle alone include `bitmappy/`.
- **Verified** in Chromium and Playwright WebKit: the editor starts, renders, and a click
  draws on the canvas.
- **Save/Load and the clipboard (2026-10-24):**
  - `glitchygames/user_files.py`: Load opens the browser's file picker (the file is copied to
    ~/opened and loaded), Save downloads the saved file. On the desktop nothing changes.
  - `glitchygames/clipboard.py`: a clipboard factory (pyperclip, else in-process); the browser
    installs `BrowserClipboard` (the page's paste event; `navigator.clipboard.writeText`).
  - Verified in Chromium and Playwright WebKit: the picker opens from the game's frame and loads
    `scarab.toml` (four frames), Save downloads `my sprite.toml`, Cmd+V pastes the system
    clipboard into the prompt box. Copying out of the game reaches the system clipboard in
    Chromium only (Safari refuses `writeText` outside the key's handler).
  - The page sets `user-select: none`: Cmd+A in a text box also selected the page.
- **Not tried yet:** voice input and controller editing.
- **Fork CI:** the first run built the wheel on Linux, byte-identical to the macOS build (sha256
  `777cfa26…`).

## Replays, iOS and publishing (2026-10-24)

- **Watched replays:** `GameEngine.start_async` drives a watched `--replay-trace` with
  `run_watched_replay_async` (glitchygames/replay/viewer.py): each awaited tick is one viewer
  tick (`ticks_externally`: no sleeping), its inner frames run until the viewer holds
  (`SceneManager.last_step_was_held`). A headless replay is refused (it never gives control
  back). Restarts (step back, Home, D) need a new process: in a browser they show a message
  (`replay/controls.py` `RESTARTS_AVAILABLE`). Verified: `nox -s browser -- paddleslap --
  --replay-trace glitchygames/examples/paddleslap_demos/rally.jsonl.gz` replays exactly in
  Chromium and WebKit; PaddleSlap's attract-mode demo plays in the live game too.
- **Engine version in the browser:** the engine archive carries
  `glitchygames-<version>.dist-info/METADATA`, so a replay compares versions (it warned "this is
  None" before).
- **iOS Simulator (iOS 26.0, safaridriver):** no JSPI (`WebAssembly.Suspending` undefined); the
  page loads in about 5 s and PaddleSlap runs on animation frames. safaridriver's tap fires only
  pointerdown/touchstart (no click), so automation starts the game with a scripted click.
- **Publishing:** `scripts/build_browser_bundle.py all` builds every game plus an index;
  `nox -s docs-deploy` builds it first and the MkDocs hook copies it into the site as play/
  (https://terrysimons.github.io/glitchygames/play/ after the next deploy). Verified: a strict
  docs build, served under /glitchygames/ with wheels as application/octet-stream, starts Mr.
  Muncher from play/ in Chromium and WebKit.
