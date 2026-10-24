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
- Watched replays in the browser: the viewer's `hold_frame` sleeps between ticks and needs its
  own async tick.

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

- **Startup focus events:** right after the window is created, the first event batch in the
  browser holds WINDOWFOCUSGAINED, WINDOWFOCUSLOST, WINDOWFOCUSGAINED.
  - Mr. Muncher pauses on focus loss, so in the browser it starts paused (P or Esc resumes).
  - The dummy driver on desktop shows similar spurious show/hide/focus cycles after the one
    `set_mode`; a real macOS window has not been checked.
  - Candidate fix: the host's doors could drop a startup focus loss that is followed by a gain
    in the same batch. Pending a decision.
- **Timer calibration:** `start_async` still runs `_configure_timer_and_performance`, which
  calibrates the desktop sleep timer (about 0.1 s of sleeps) although the async driver never
  uses the timer.
- **Fixed 2026-10-23 (BUGS.md #212):** `ASSET_PATH` pointed into `glitchygames/engine/`, so the
  default window icon was never loaded.
