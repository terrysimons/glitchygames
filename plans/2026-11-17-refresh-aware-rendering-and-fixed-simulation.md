# Refresh-aware rendering and fixed simulation: the owner's brief

Status: APPROVED by the owner (2026-11-20) as findings with the measurement first: sub-plan 1 (the Pi measurement) may proceed when a Pi is on; the choice between B and C waits for its numbers (question 1). TO-DO (2026-11-17), not started; findings and design options added 2026-11-20 (below the
brief), awaiting the owner's choice; audited the same day against main b7c2abd3 (see "Audit
2026-11-20" at the end: line numbers, counts and two ordering problems corrected). The owner's brief, kept verbatim below; the findings and
decisions from discussing it are in `plans/future-work.md`, "Refresh-aware rendering and fixed
simulation". Measure one thing at a time (the owner, 2026-11-17).

---

GlitchyGames: Refresh-Aware Rendering and Fixed Simulation

## Goal

Detect the refresh rate of the display containing the game window and use it to select a
rendering target, while keeping simulation timing independent and predictable. Improve motion
smoothness and diagnose hitching using frame-time measurements rather than average FPS alone.

The initial target is a Raspberry Pi 5 running at 1920 × 1080, with a 120 Hz display and a 60 Hz
simulation. These provide an 8.33 ms display interval and a 16.67 ms simulation interval. This is
an implementation brief, not a claim that the current engine already separates those loops.

## Intended behavior

| Component | Initial policy |
| --- | --- |
| Input | Poll every rendered frame; retain events until simulation consumes them |
| Simulation | Fixed 60 Hz, configurable per game |
| Rendering | Follow detected display refresh, subject to explicit user limits |
| Presentation | Prefer working VSync on a supported backend |
| Interpolation | Blend previous and current simulation transforms for rendering |
| Unknown refresh | Fall back to a configurable 60 FPS target |

Monitor changes must not change game speed, simulation timestep, or replay tick numbering.
Headless execution should not require a display query or presentation wait.

## 1. Audit the existing loop

Locate event polling, scene updates, physics steps, rendering, display presentation, and frame
limiting. Determine whether the current 60 Hz setting controls simulation, rendering, or both.
Check for multiple timing mechanisms, such as a sleep-based limiter combined with blocking VSync.

Instrument the current behavior before changing it. Preserve existing scene and replay contracts
where possible; document any changes to update semantics.

## 2. Detect the display refresh rate

pygame-ce provides these APIs, introduced in version 2.2.0:

```python
import pygame

pygame.init()
screen = pygame.display.set_mode((1920, 1080))
refresh_hz = pygame.display.get_current_refresh_rate()
render_target_hz = refresh_hz if refresh_hz > 0 else 60
```

Call the current-window query after creating the window. It returns zero when the refresh rate is
unknown. `pygame.display.get_desktop_refresh_rates()` provides desktop rates for all displays, but
a fullscreen window's actual mode may differ.

Re-query after relevant display/window changes, including movement between monitors and
fullscreen transitions. Debounce notifications rather than querying on every frame. Handle
unavailable display information in headless runs explicitly. Report both the detected rate and
the effective rendering target.

The API returns an integer: it does not provide exact fractional refresh timing or predict
individual variable-refresh intervals.

## 3. Separate simulation from rendering

Use a monotonic high-resolution clock, such as `time.perf_counter()`, and an accumulator:

1. Measure elapsed wall time since the previous iteration.
2. Collect input events into a queue or suitable persistent input state.
3. Add elapsed time to the simulation accumulator.
4. While the accumulator contains a full fixed timestep, advance simulation once and subtract
   that timestep.
5. Render using the fractional remainder as the interpolation factor.
6. Present and apply the selected pacing policy.

For each simulation step, retain previous renderable transforms before producing the current
transforms. Use `alpha = accumulator / fixed_dt` and interpolate from previous to current.
Interpolation must not mutate authoritative simulation state. Initialize both snapshots
identically, and reset them together for teleports, scene changes, and respawns.

Do not apply a one-shot input event twice during catch-up steps, or discard it on render frames
with no simulation step. Replay inputs should be associated with simulation ticks.

Bound catch-up work to prevent an overloaded simulation from starving rendering and input. Define
and log the overload policy explicitly: limiting catch-up and discarding accumulated time changes
the relationship between wall time and simulation time. On pause/resume, reset timing state
rather than simulating the entire pause. Offline deterministic replays should use an explicit
stepping policy without silently dropping ticks.

Interpolation normally introduces about one simulation tick of visual latency. Games needing
lower latency may choose 120 Hz simulation or carefully designed player/camera handling. Higher
physics rates are a per-game choice, not an automatic consequence of monitor detection.

## 4. Choose one primary pacing mechanism

### VSync

With the Surface display API, a possible supported path is:

```python
screen = pygame.display.set_mode(
    (1920, 1080),
    pygame.SCALED,
    vsync=1,
)
```

This is a request, not a guarantee. pygame documents VSync requests for SCALED or OPENGL modes;
do not add flags blindly to an existing renderer. OPENGL requires an appropriate rendering
implementation. Validate the selected backend on each target OS.

Use `pygame.display.is_vsync()` as a diagnostic, and measure presentation behavior as well. A
reported enabled state alone does not prove consistent visible presentation. Compositors and
buffering can affect timing.

When presentation genuinely paces the loop at the desired rate, avoid adding an independent
refresh-rate sleep limiter. If VSync does not pace it, use a fallback cap. Explicit lower user
caps need a coordinated policy rather than two competing timers.

### Software fallback

`Clock.tick(target_hz)` can provide a simple cap, but it does not synchronize to scanout and its
timing precision varies. For tighter pacing, use monotonic absolute deadlines and measure sleep
overshoot. Avoid accumulating drift by scheduling each deadline from the previous deadline rather
than from the end of work. Resynchronize after large overruns instead of issuing bursts of
overdue frames.

Do not default to busy waiting on the Pi: it consumes CPU and power. Consider it only as a
measured, optional tradeoff.

If 120 FPS cannot be sustained on a fixed 120 Hz display, an explicitly paced 60 FPS mode may be
smoother than an unstable 120 FPS target. Avoid rapidly oscillating automatic targets.

## 5. Configuration and diagnostics

Suggested configuration fields:

```toml
[timing]
simulation_hz = 60
render_rate = "display"
fallback_render_hz = 60
vsync = "auto"
interpolation = true
max_catchup_steps = 5
```

These are proposed engine settings, not existing pygame options. Also support an explicit
rendering cap and an uncapped benchmark mode.

Log OS, kernel, pygame/SDL versions, display backend, resolution, detected refresh rate,
requested/reported VSync state, effective cap, and simulation rate. Measure event handling,
update time, render time, presentation-call duration, limiter wait, catch-up count, and dropped
simulation time separately. Keep instrumentation buffered to avoid per-frame disk writes.

Report median, p95, p99, and p99.9 frame intervals plus counts above the selected frame budget.
Presentation-call return times are CPU-side proxies, not proof of physical scanout timing. Use
compositor instrumentation or external observation if those measurements disagree with visible
hitching.

## 6. Validation

| Scenario | Expected result |
| --- | --- |
| 120 Hz display, 60 Hz simulation | Approximately 120 renders and 60 simulation steps per second when sustainable |
| 60 Hz display | Rendering adapts; simulation speed is unchanged |
| Unknown refresh rate | Configured fallback, no crash |
| Move to another display | Rendering policy updates without resetting game state |
| VSync unavailable | Bounded fallback rendering rate |
| Temporary overload | Bounded catch-up work and explicit diagnostic counters |
| Pause/resume or teleport | No large catch-up burst or interpolation smear |
| Replay at different rendering rates | Same tick-indexed simulation outcomes when the simulation is deterministic |
| Headless run | No display dependency; explicit simulation stepping |

Use a repeatable scene or replay and compare before/after frame-time distributions under
identical display and power settings. Verify input edges are consumed once and movement speed is
independent of rendering frequency.

## Relationship to the kernel page-size experiment

Keep frame-pacing changes separate from the 4 KB versus 16 KB kernel comparison. Change one
variable at a time. If testing page size, ideally build both kernels from the same source with
equivalent settings apart from page-size-dependent changes.

Larger pages may help translation-heavy workloads, but they do not directly synchronize
presentation or guarantee fewer hitches. Neither abundant RAM nor high clock speeds rules out
compositor or timing problems. Investigate 64 KB pages only as a separate compatibility and
performance experiment.

## Completion criteria

The engine detects the current display rate, separates fixed simulation from rendering, handles
unknown rates and display changes, supports a verified VSync path and fallback cap, and exposes
enough timing data to distinguish simulation/render work from presentation waits. Measurements
must demonstrate whether visible hitching improves; do not treat a high average FPS as sufficient
evidence.

## References

- pygame-ce display documentation: refresh-rate queries and VSync diagnostics.
- pygame display documentation: VSync request limitations.
- pygame-ce time documentation: Clock timing and frame limiting.

The configuration policy, architecture, and validation plan above are proposed design decisions
for GlitchyGames.

---

# Findings and design (added 2026-11-20, investigation only; no engine code changed)

Everything below was read from `origin/main` at 4e6c7144 (line numbers re-checked on b7c2abd3 in the audit) and measured on one machine: an Apple
silicon Mac (macOS 27.2.1, arm64, 16 CPUs, Python 3.15.1, pygame-ce 2.5.8, SDL 2.32.10, cocoa
driver) whose built-in display reports 120 Hz. Not measured: any Raspberry Pi, any 60 Hz display,
Linux or Windows, and visible hitching (scanout phase), which no tool here reaches. The Mac was
busy with other work (`timer_report`: cpu share of a busy loop 0.27), so the CPU numbers are
upper bounds. The measuring scripts were scratch files outside the repository.

## Findings: what the engine does today

### The loop: one iteration is one frame is one step

`SceneManager.start` (`src/glitchygames/scenes/scene.py:1867`) runs `begin_frames` (1884), then
`run_frame_step` (1912) while `should_run_frames` (1899). One `run_frame_step` runs one
`_run_frame_steps` (2110) and closes in `_finish_frame` (1986). There is no accumulator, no
fixed timestep, no interpolation, and no second loop. A scene frame (`_run_scene_frame`, 2572)
runs in this order: `camera.begin_frame`, `_update_scene` (2872: `advance_game_time`, then
`Scene.dt_tick(scene_dt)`), `_process_events` (events pumped and dispatched), the supervisor slot,
`_update_frame_services` (shake, rumble), the camera aim, `_position_active_world_sprites` (2690),
`_render_scene` (2908: `Scene.update()` then `Scene.render`), `_present_frame` (1538).

Consequences of that order that matter here:

- **Logic runs before the event pump**, so `dt_tick` reads the previous frame's input snapshot
  (`docs/architecture/playback/how-a-frame-runs.md`). A "step" in any new design must keep
  `dt_tick`, then the frame's event batch, as one unit, or every recording changes meaning.
- **`dt` is start to start**, set in one place (`_set_frame_time`, 2047, through the
  `frame_seconds` door: `live_sources.py:112` returns the measurement, `recording.py:1636`
  records it, replay rule 4 in `replay/driver.py` returns the recorded value). Logic in frame N
  gets the time frame N-1 took.
- **`Scene.update()` is not visual only for animation.** `Scene.update` (`scene.py` near 3573)
  hands each dirty `AnimatedSprite` `self.dt`, so an animation frame index (state a recording
  samples) advances in the render phase. In a split loop that call must move into the step, or a
  120 Hz render would advance animations twice as fast. Games that animate in `dt_tick` already
  override `update()` as a no-op, which is the shape to generalise.
- Time inside a frame comes from `Scene.game_time` (`scene.py:3344`: the sum of the capped `dt`s
  `dt_tick` received, paused while the scene is not running) and the frame clock (the sum of
  closed frames' `dt`, `advance_frame_clock`, `sources.py:499`; 18 reads in the engine). Both
  count frames' `dt`, so both would count steps if a frame were not a step.
- `MAX_FRAME_SECONDS` (`scene.py:3145`, used by `_scene_frame_seconds`, 2643; set by clockwork
  keep and the zombies scene to 0.05 s) is today's overload policy: after a hitch the scene
  advances at most the cap and the rest of the wall time is silently dropped, so game time and
  wall time already diverge. The brief's `max_catchup_steps` is the same decision made explicitly.
- `Scene.dt_tick` is overridden 39 times outside tests; each mixes per-step and per-frame work.

### Pacing: one cap, no presentation awareness

- `--target-fps` defaults to 60.01 (`timing.py:43`, `DEFAULT_TARGET_FPS`; a scene may set
  `TARGET_FPS`, `resolve_target_fps`, `engine/game_engine.py:1314`; 0 is uncapped). Pacing is
  `_handle_frame_pacing` (`scene.py:1793`): `FastTimer.start_frame` rounds the period to the
  nearest nanosecond (`timing.py:466`; 16,664,000 ns for 60.01), deadlines advance from the
  previous deadline (no drift from work time), and `sleep_until_next` (493) sleeps to a measured
  distance before the deadline and then spins (`sleep(0)`) the rest. The pygame clock is the
  fallback. `dt` is measured separately with `raw_counter_seconds` (BUGS.md #26).
- No refresh-rate query and no VSync request exist anywhere in `src/glitchygames`
  (`get_current_refresh_rate`, `vsync=`, `is_vsync` have no hits). The display mode is
  `DOUBLEBUF | SCALED | RESIZABLE` (`game_engine.py:1696-1699`), through `set_display_mode`
  (`display_mode.py:67`, which calls `pygame.display.set_mode(size, flags)` with no `vsync`).
  SCALED is already there, which pygame requires for a VSync request, so asking for VSync is a
  keyword in one function, not a new display mode.
- Presenting is three flips and one `update` call in `_show_frame`/`_update_display`
  (`scene.py:1627-1640`, 2917-2927; `--update-type update` is the default and updates dirty rects).
- **Two timers can already compete.** Uncapped (`--target-fps 0`) on this Mac the loop runs at
  the display rate because the present call blocks (measured below); capped at 60.01 the present
  returns at once and the engine's own deadline paces.

### The game host and the browser: a second pacer

`GameHost.run_async` (`host.py:432`) takes one outer tick per `await wait_for_tick()`, which in
the browser is one `requestAnimationFrame` (`browser/boot.py`, `AnimationFrameTicks`), so the tick
rate is the display's (60, 120, 144, 240 Hz; Safari caps at 60). `TickPacer` (`host.py:342`)
decides which ticks run an inner frame, and frames run unpaced (`run_frame_step(paced=False)`), so
the wait for the tick is their pacing. `dt` is still measured start to start, so it is 8.3 ms,
25 ms or 16.7 ms depending on which ticks ran a frame. This is already a "simulation rate versus
display rate" decoupling, done at the whole-frame level with no interpolation, and it has just had
a real bug: `bugs/2026-11-20-browser-frames-juddered-at-120-hz.md` (in the working tree of
`fix/browser-pacer-judder`, not on main yet) measured frames running after 1, then 3 ticks (8 and
25 ms) on a 120 Hz Chrome because 60.01 FPS is not exactly two ticks. The same arithmetic applies
to the native pacer (see the measurements). Whatever this tentpole builds, the host's pacer
should become a consumer of it, not stay a parallel mechanism.

### Recording and replay: the frame is the unit and `dt` is recorded

- A recording is a list of frames. Each holds the frame's `dt`, its event batch (pump N serves
  batch N), `input_changes`, and the sampled scene and sprites (`replay/driver.py` rules 2-5, 8).
  A replay serves the recorded `dt` through the `frame_seconds` door (rule 4), is unpaced
  (`paced_frame_seconds` 0.0, rule 13), counts its own `end_frame` calls (rule 3) and compares
  the sprites at each `end_frame` (rule 8). A watched replay's viewer ticks at 60 Hz and the
  inner frames are not presented by the scene manager (`presents_frames`).
- Because a replay serves each frame's recorded `dt` exactly, replays are already independent of
  the machine's refresh rate and of any pacing change: pacing only decides when a frame starts,
  never what it computes. The danger is only a change to what a frame computes or in what order.
- Recordings today (`git ls-tree` on b7c2abd3): 8 golden replays
  (`src/games/*/tests/fixtures/replays`), 11 bundled demos (`*/demos`; 10 before #235 added the
  zombies attract demo), 4 golden-trace files (`tests/world/golden`), plus 2 AI-behaviour
  recordings and a provenance fixture. (`plans/future-work.md` says 25 and 5; the 19 under `src/`
  plus 4 is what the repository holds. Worth reconciling.) Of the 19 under `src/`, 18 have a
  median `dt` of 16.664 ms (60.01 FPS) over their first 400 frames; PaddleSlap's rally demo has
  16.586 ms, so "every committed recording is at 1/60.01" below is almost, not exactly, true.
- The doors guard (`tests/test_engine_doors.py`) allows time only through `clock.py`. A refresh
  rate is a platform read that does not change what a frame computes, but it changes what a
  recording's drawn output would be on a given machine, so it belongs behind a door (live: the
  display; replay: the recorded header value or none).

### World space and the camera

World sprites keep float `world_x`/`world_y`, and only the engine writes their `rect`
(`world.py`; `position_world_sprites` once per frame after the camera aim). That is exactly the
hook interpolation needs: the engine already derives every world sprite's screen position from
(`world_x`, `world_y`, camera) at the end of the frame, so blending previous and current
`world_x`/`world_y` and the camera position there needs no game change for world sprites.
Screen-space sprites set their own `rect` and are not interpolable without a game's opt-in.
Pixel snapping (`pixel_snap.py`) must apply after the blend. `LayeredDirty` redraws only dirty
sprites, so a blended sprite is dirty every render frame (more rect traffic than today's
once-per-step motion at 60 Hz, none for a still scene).

### Headless

The dummy driver does not report an unknown rate: measured with `SDL_VIDEODRIVER=dummy`,
`get_desktop_refresh_rates()` is `[60]` and `get_current_refresh_rate()` is `60`, and
`is_vsync()` is True after a `vsync=1` request. So "unknown refresh, fall back to 60" is never
exercised by the dummy driver, and its `60` is a made-up answer. A headless run should skip the
query by rule (the brief says so), not rely on a 0.

## Measurements (this Mac, cocoa, 120 Hz; 8 s runs after 180 warm-up frames)

Method: a scratch script that runs Paddle Slap through `GameEngine(game=Game).start()` with
`SceneManager._set_frame_time` and `_present_frame` wrapped to collect the measured frame time
and the present call's duration, quitting after the interval. `refresh` from pygame-ce 2.5.8:
`get_desktop_refresh_rates()` `[120]`, `get_current_refresh_rate()` 120, `is_vsync()` True for a
`SCALED, vsync=1` window (the engine does not request it).

| Run | Frames | Median | p95 | p99 | p99.9 | Max | stdev | Present call median / max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `--target-fps 60.01` (8 s) | 481 | 16.664 ms | 16.665 | 16.669 | 16.69-16.81 | 16.81 | 0.003-0.011 | 0.31 / 0.46 ms |
| `--target-fps 60.01` (75 s) | 4505 | 16.664 | 16.665 | 16.669 | 16.700 | 17.466 | 0.017 | 0.34 / 2.60 ms |
| `--target-fps 120` (8 s, two runs) | 961 | 8.333 | 8.335 | 8.336-8.365 | 8.365-11.26 | 11.26 | 0.002-0.135 | not measured |
| `--target-fps 0`, uncapped (8 s, two runs) | 960 | 8.43-8.53 | 8.51-8.64 | 8.56-8.71 | 9.37-9.47 | 9.47 | 0.33-0.44 | 8.22 / 9.27 ms |

What they show:

1. **The CPU-side frame interval is already tight at 60.01 and 120.** Median 16.664 ms, p99.9
   16.69-16.81 ms in 8 s and 16.70 ms in 75 s, one 17.47 ms outlier in 75 s. A frame-interval
   histogram cannot see the hitching the owner describes on the Pi: the brief is right that
   averages and even tail percentiles of `dt` do not prove smoothness. (The browser bug was the
   same: every frame cost under 2 ms and every tick was on time, and it still juddered.)
2. **Uncapped, the present call is the pacer.** The present call blocks 8.2 ms (a whole 120 Hz
   refresh) and the loop runs at exactly 120 FPS with `dt` spread 7.2-9.5 ms (the display's
   phase, not the engine's). Capped at 60.01 the same call returns in 0.3 ms. So on cocoa the
   display is paced by the present call whenever nothing else paces, and by the engine's
   sleep-and-spin when something does. I did not establish why the capped call does not block
   (compositor queueing is a guess, not a finding).
3. **60.01 is not a whole number of 120 Hz refreshes.** By arithmetic (not measured): 60.01 FPS
   is 16.6639 ms, two refreshes are 16.6667 ms, so the frame's phase against the display moves
   about 2.8 microseconds a frame, one whole 8.33 ms refresh in about 3,000 frames, roughly every
   50 s. On a 120 Hz display a frame that was presented in the first half of a refresh slides
   through the second half and crosses a vblank. This is the same mechanism the browser fix
   found. Whether it is visible on the Pi was not measured: it needs scanout-phase observation
   (`scripts/frame_phase_probe.py` in the `fix/browser-pacer-judder` working tree is the nearest
   tool; it is not on main).
4. **Pacing cost.** `timer_report` here: with `--timer-backend auto` calibrated "fast, final spin
   1.0 ms (sleeps wake 3.07 ms + 38% of their length late)"; waits of 12 ms wake with median
   0.00 ms, p90 2.57, max 4.21 ms late; plain `time.sleep(16 ms)` wakes a median 4.02 ms late
   (p90 7.0). Process CPU time over wall time during the runs: 0.12-0.13 at 60.01, 0.25 at 120
   (including the game's own work, on a busy Mac). The brief's concern that the default spins is
   true in kind (1.0 ms of final spin per frame, plus `sleep(0)` polling) but on this Mac it
   costs 6% of a 60 FPS period; the Pi's sleep delays (which `auto` measures) decide whether
   whole waits spin. Not measured on the Pi.
5. **Replays are unaffected by all of the above** (by design; see Constraints). No replay was
   re-recorded or run differently for this investigation.

## Constraints

1. **Goldens are never re-recorded for this change.** An existing recording must replay as it
   is: each recorded frame is one step of its recorded `dt`, with its recorded event batch, in
   the recorded order, with the same samples compared at the same `end_frame`. So the step
   (today's `dt_tick` plus the event batch) must remain one unit that the replay driver can run
   per recorded frame, and drawing must be separable from it.
2. **Draw-only frames must never reach the doors' `end_frame`** (a recorder samples and writes a
   frame there; a replay counts and compares there, rules 3 and 8), and must not pump events,
   call `frame_seconds`, advance the frame clock, draw random numbers or call `dt_tick`.
3. **The replay of a recording is always at its recorded steps.** Re-stepping the game at another
   rate changes outcomes (collisions land at other points, the zap's 0.25 s cooldown crosses on
   other steps, random streams draw per step). So only drawing may be resampled to the display
   rate; this is the owner's 2026-11-17 idea, and the evidence for it is the engine's own
   replay contract.
4. **New live recordings** would record the fixed step, not the measurement, as the step's `dt`
   (each step is exactly `1 / simulation_hz`). Their `dt` would stop jittering, which makes them
   more reproducible across machines than today's; a header field must name the simulation rate
   so a replay knows the recording is fixed-step (and the format version moves).
5. **Existing 60.01-FPS recordings are not fixed 60 Hz recordings**: their `dt` is 16.664 ms
   with jitter. A step of recorded `dt` is a variable step. So the engine needs two stepping
   policies for as long as old recordings exist: recorded (the recording says when and by how
   much) and fixed (the accumulator says). The brief's "explicit stepping policy for offline
   deterministic replays" is this, and it is what the owner already decided on 2026-11-17.
6. **Clocks:** time only through `clock.py` and `Scene.game_time` (never `time.perf_counter`
   in scene code). Game time, the frame clock, tweens, shake, rumble, sound voices (which end by
   played time, the served `dt`) and FPS events advance per step; any UI timing that should look
   smooth at the render rate (a blink phase) needs a draw clock that is not recorded and never
   affects state.
7. **World space rules:** only the engine writes a world sprite's `rect`; game logic never reads
   it; interpolation is engine-side in `position_world_sprites` from retained previous values; the
   pose rule (draw the pose in `dt_tick`, before collision) is unchanged because a step is
   unchanged.
8. **The doors:** a display refresh query is a new platform read. It needs a door
   (`EngineSources`), a recorded header field for provenance, and an entry in the engine-doors
   guard; and the inner-game/Arcade case (private render target, no window) must not query it.
   The same rule the owner gave the cursor and key-repeat to-dos on 2026-11-20
   (`plans/future-work.md`, Arcade follow-ups) applies to everything here that touches SDL's
   one window: the VSync request, the refresh query, the re-query on a window move and the
   present policy belong to the context that owns the window; an inner game (a tile, the
   viewer's later inner game) never requests, queries or paces the display, and keeps no state
   of it. Per-context state of the new loop (the accumulator, the snapshots) is a `ContextSlot`
   with an isolation check (`tests/test_engine_context.py`).
9. **Transitions and pause:** transition frames (`_start_transition`, raw `dt` to the
   transition's update) and the held frame (`_present_held_frame`, `hold_frame` door) are
   presentation paths today; each needs an explicit rule (a transition is presented per frame;
   pause resets the accumulator).
10. **Lint caps:** `GameEngine.__init__`, `ReplaySources`, `PlaybackSources` and
    `GameEngine.start` sit at their lint limits (`plans/future-work.md`, "Lint caps shape the
    replay classes"), and `SceneManager` is already the file the playback extraction targets. The
    new loop belongs in its own collaborator (a frame driver), not more methods on those classes.
11. One change at a time, measured under identical display and power settings (the owner);
    kernel page size is a separate experiment.
12. Existing known debt (not new): 24 `assert` statements remain in `scenes/scene.py` (for
    example 2595, 2669, 2700, 2879; the owner remembered about ten), against the global rule
    "never assert outside tests".
    Bandit's B101 is filtered out by `[tool.bandit]` severity, with a TODO to remove them.

## Mapping the brief to the engine

| The brief asks for | Exists | Missing | Touches |
| --- | --- | --- | --- |
| Poll input every rendered frame, keep it until simulation consumes it | One pump per frame; events dispatched that frame (`GameEngine.process_events`); polled `InputSnapshot` set after the pump | A queue between pump and step; per-step delivery so a one-shot event acts exactly once; at least a rule for edge-triggered snapshot fields | `engine/game_engine.py`, `input/state.py`, `sources.py` doors, replay pump rules 2 and 5 |
| Fixed 60 Hz simulation, per game | `TARGET_FPS`, `--target-fps`; `MAX_FRAME_SECONDS` | `SIMULATION_HZ` (or timing option), accumulator, catch-up bound, overload counters | `scenes/scene.py` loop, `timing.py`, `Scene` attributes |
| Render at the detected refresh, subject to limits | Pacing to a fixed target | The query, a door for it, re-query on window moves and fullscreen (SDL display events), debounce, effective-target reporting | new `display_refresh` module, `display_mode.py`, window-event handling |
| Prefer VSync where supported | SCALED mode (`game_engine.py:1696`), a flip/update present | `vsync=` in `set_display_mode`, `is_vsync()` check, whole-ratio skipping (SDL has no swap interval above 1), "present paces, so do not also sleep" policy | `display_mode.py`, `_handle_frame_pacing`, `timing.py` |
| Interpolate previous and current transforms | `world_x/world_y`, `position_world_sprites`, camera | Previous-state snapshot per world sprite and camera, reset on teleport, spawn, scene change, respawn; `alpha` | `world.py`, `camera.py`, `sprites/`, `pixel_snap.py` |
| Unknown refresh falls back to 60 | `DEFAULT_TARGET_FPS` | The 0 handling; the dummy driver answers 60 (finding above) | the new module |
| Pause/resume and overload policy | Held frame, `MAX_FRAME_SECONDS` cap | Accumulator reset on resume; counters and a log line for dropped simulation time | `scene.py` |
| Diagnostics and percentiles | `timer-report`, performance manager FPS, `--log-timer-jitter`, replay-metrics ledger | Event, update, render, present and limiter-wait split per frame; median/p95/p99/p99.9 and over-budget counts; buffered output; environment header | `performance/`, `scene.py` timing points |
| Headless: no display query | Dummy driver, unpaced replays | An explicit "headless" branch before the query | the new module |

## Design options

The worked example throughout is Paddle Slap on the 120 Hz Mac measured above (a ball crossing the
playfield at some speed in pixels per second), and its golden replay
(`src/games/paddleslap/tests/fixtures/replays`, recorded at about 60 FPS with `dt` near 16.664 ms).

### Option A: pace to the display, keep one variable step per frame

The engine asks for the display's rate and sets the target FPS to it (120). Nothing else changes.
In the example: the ball's `dt_tick` runs 120 times a second with `dt` of about 8.33 ms and moves
half as far each time, the 0.25 s cooldown crosses on a different step than at 60, and
collisions are tested twice as often (so a ball that tunnelled at 60 may not at 120, and one that
clipped a paddle corner now may not). The golden replay is untouched: it serves its recorded
`dt`, ignores the display, and replays the same 60 FPS frames headless. Cost: double the game
work per second for every game, no smoothing of uneven frames (a late frame still gives a long
`dt`), and games tuned at 60 behave subtly differently live at 120. The brief's "monitor changes
must not change game speed, timestep or replay tick numbering" is not met: the timestep follows
the monitor. This is the "cheaper first change" of `plans/future-work.md`.

### Option B: whole-ratio presentation at the game's own rate (phase-locked, no interpolation)

Keep one step per frame, at the game's rate (60). Detect the display rate R and pick the whole
ratio N = round(R / game rate) when R is within about 2% of a multiple; request VSync
(`vsync=1`); present on every Nth refresh by counting presents (the browser's fix does the same
with animation frames: `whole_ticks_per_frame`, found by `bugs/2026-11-20-...`). In the example
on the 120 Hz display: the ball steps at 60 Hz with a constant 16.667 ms `dt`, and every step's
frame is shown for exactly two refreshes, so the 2.8 microsecond phase slide of 60.01 against
120 Hz disappears (the frame is paced by the display, not by a 60.01 deadline), and a late frame
is a visible repeat of one frame, not a phase shift. Render frames equal steps, so no part of
the replay or world-space contracts changes, and the golden replay is untouched. What it does
not give: 120 distinct images a second. Motion is exactly as smooth as 60 FPS on a 60 Hz
display, which is the "60 Hz simulation on a 120 Hz screen" the brief calls a baseline, not a
goal. A 144 Hz display (ratio 2.4) has no whole ratio and falls back to a deadline cap.

### Option C: fixed step, interpolated rendering (the brief's design; steps are the recorded unit)

Split the frame into step (`dt_tick` plus the event batch, exactly as today, with a fixed
`dt`) and draw (positioning, `update`, render, present). An accumulator decides, each loop
iteration, how many steps run (0, 1, or up to `max_catchup_steps`), then draws once with
`alpha = remainder / step`, blending the previous and current `world_x`/`world_y` and camera.
In the example at 120 Hz: half of the iterations run no step (they only draw the ball a half-step
past its previous position), the others run one; the ball is drawn at 120 distinct positions a
second, with a latency of about one step (16.7 ms) more than option B; a spawned ball appears
from the first draw after its step, not mid-blend; a respawn teleports it with both snapshots
reset so it does not smear across the playfield. At 30 Hz display (a slow Pi) the iteration
runs two steps per draw and the sprites a step skipped are drawn once at their last state (the
owner's "nothing vanishes" rule in `plans/future-work.md`). In the golden replay: the driver runs
each recorded frame as one step with its recorded `dt` and event batch and compares at that step's
`end_frame`, then draws at whatever rate the viewer wants by blending; the file bytes and the
comparison are identical to today. Live and new recordings record the fixed step. Cost: the
largest change: a loop split, per-sprite previous state, the move of animation advance out of
`Scene.update`, 39 `dt_tick` overrides audited for per-frame work, the host and Arcade drivers
rewired, and one step of visual latency.

### Option D (variation of C, proposed as its first stage): C without blending

Do C's loop split and accumulator and fixed step, but draw each step's state as it is (no
`alpha`), so a 120 Hz display shows each step twice. In the example it looks like B (60 distinct
positions) but with the loop, replay and door changes done and tested, and with the fixed step's
`dt` and catch-up bound already live. Blending then becomes a drawing-only change behind a flag,
which cannot alter a recording. This is how C is staged so each stage is measured on its own.

## Recommendation

Build C, staged as D then blending, and put B's measurement first.

- Why C: it is the only option that meets the brief's own validation table (120 renders and 60
  steps a second; monitor changes do not change speed or tick numbering; temporary overload is
  bounded with counters; replays at different render rates give tick-indexed outcomes), and it
  keeps the one property the replay contract demands (a step is the recorded unit; drawing is
  resampled). Option A fails the "monitor changes must not change simulation" requirement and
  doubles every game's work.
- Why not C directly: the owner's rule is one change at a time, and the measurements here show the
  CPU-side `dt` is already tight, so the evidence that hitching exists is a phase effect
  (60.01 against 120) that B already removes at a fraction of the risk. So sub-plan 1 measures on
  the Pi with `vsync=1` and whole-ratio presentation first. If that removes visible hitching, C's
  motivation shrinks to "more than 60 distinct images", which the owner can then weigh against
  the cost.
- The host's `TickPacer` and the native pacer should end up as the same component (a
  presentation scheduler fed by display ticks), so the browser bug class cannot return.

## Open questions for the owner

### Decided by the owner (2026-11-20)

- **Question 1 (the goal) waits for the measurement.** Measure first, then choose between B
  alone and C staged as D.
- **Question 2: the default simulation rate becomes exactly 60** (not 60.01). Committed
  recordings are untouched: a replay serves its recorded `dt`.
- **Question 8: the measurement baseline.** A Raspberry Pi 5 on its display at 1920x1080 and
  120 Hz, CPU governor `performance`. The second case is the same display forced to 60 Hz
  (same panel, cable and Pi, so only the refresh rate changes); it exercises B's ratio of 1
  where 120 Hz exercises a ratio of 2. A Pi 4 is an optional extra only if `kmsprint` (or
  `wlr-randr`) lists 1920x1080 at 120 Hz on it. The session also runs B at 60 Hz and at 120 Hz
  and compares the engine's per-frame cost, to measure what 120 Hz scanout costs in memory
  bandwidth (estimated at about 1 GB/s against 0.5 GB/s for 1080p, not measured). Measured with
  `scripts/frame_phase_probe.py` once it is on main. The owner runs it later.
- Questions 3 to 7, 9 and 10 gate only sub-plan 4 and later, and stay open.

### The questions as asked

1. Is the goal smoother motion at the display rate (120 distinct images), or removing hitching at
   60 Hz? B solves the second cheaply; only C does the first.
2. Do you want the default simulation rate to stay 60.01 (today's) or become exactly 60? Exactly
   60 is a whole ratio of 60, 120 and 240 Hz displays and removes the beat. `git log -S` finds
   60.01 in `timing.py` as far back as #93 and #94 with no reason recorded in the code, the
   argument docs or the plans I grepped. Changing it changes every new live recording's `dt`
   (all committed recordings are at P = 1/60.01), not old ones.
3. May a recording's format version move, so new recordings are fixed-step and name their rate in
   the header? (Old ones must still replay as variable-step.)
4. Per-game simulation rate: a class attribute like `TARGET_FPS`, a `[timing]` table in
   `pyproject.toml` (the brief's), or both? Which wins?
5. Interpolation scope: world sprites and the camera only (engine-side, no game changes), or also
   an opt-in for screen-space sprites?
6. Input: first step after the frame's pump (one frame of extra latency below the step rate) is
   proposed. Is that acceptable for Paddle Slap and the zombies' zap, or do you want a game to
   be able to ask for a faster step?
7. Overload: `max_catchup_steps` of 5 with dropped time counted and logged, or keep
   `MAX_FRAME_SECONDS`-style capping per scene? Both can coexist only while old recordings do.
8. Where may the Pi measurement run, and which display (the 120 Hz one in the brief) and power
   settings are the fixed baseline?
9. The recordings count: `future-work.md` says 25 goldens and demos plus 5 baselines; `find` shows
   8 goldens, 10 demos and 4 golden-trace files here. Is something outside the repository, or is
   the note stale?
10. Should `--ai-stepping idle` (serving the AI during the pacer's wait, already designed in
    `plans/2026-11-17-sprite-color-profiles.md`) land with this work, as `future-work.md` says?

## Proposed split into sub-plans

Each is its own plan file linked back to this one; each ends with a measurement under the same
display and power settings before the next starts.

1. **Measure and diagnose (no behaviour change).** A buffered frame-timing recorder (event,
   update, render, present, limiter wait, steps run, dropped time) with median, p95, p99, p99.9
   and over-budget counts and an environment header; a presentation-phase probe; baseline on the
   Pi at 60.01 and at 60. Tests: a recorder given a known sequence of timings reports exactly
   those percentiles; the recorder writes nothing per frame; a replay run with the recorder
   produces the same frame hashes as without it.
2. **Display refresh door.** The query behind an `EngineSources` door (live: pygame-ce's
   `get_current_refresh_rate`; headless, inner game, replay: no query, recorded header value or
   none), re-query on window moves and fullscreen changes with a debounce, and effective-target
   reporting. Tests: a rate of 0 gives the configured fallback and no crash; a headless run makes
   no display call; moving to another display re-targets without resetting game time or the
   frame number; the dummy driver's 60 is not reported as a detected rate; the doors guard
   fails if the query is read outside the door.
3. **VSync request and whole-ratio presentation (option B)** (the audit recommends two sub-plans,
   3a native and 3b the host's `TickPacer`). `vsync` in `set_display_mode`,
   `is_vsync` diagnostic, whole-ratio skipping, no second sleeper when present paces, a fallback
   cap when it does not. Tests: at 120 Hz and a 60 game rate every second refresh presents and
   every present is a whole ratio apart despite 0.8 ms jitter (the browser pacer's jittered
   test is the model); an unsupported VSync falls back to the cap and says so; 144 Hz keeps the
   cap; an explicit lower user cap is never exceeded; existing goldens replay byte-identically.
   This sub-plan also folds `TickPacer` into the same scheduler (browser, native, one decision).
4. **Fixed step with the loop split (option D).** A frame driver collaborator owning the
   accumulator; step and draw separated; animation advance moved into the step; per-step clocks;
   input queue delivering each event to exactly one step; `max_catchup_steps` with counters;
   pause and scene switch reset the accumulator; the recorded stepping policy for replays. Tests:
   movement per second is the same at 30, 60, 120 and 240 Hz render rates; a one-shot key event
   acts once with two steps in one frame and with none; a long stall runs at most
   `max_catchup_steps` and counts the rest as dropped; every golden and demo replays unchanged
   (the golden-trace baselines need no new `ExpectedDifference`); a draw-only frame calls no
   door's `end_frame`, pumps no events and draws no random number; a recording made live carries
   the fixed rate and replays at another render rate with identical per-tick samples.
5. **Interpolation.** Previous and current world transforms and camera, `alpha`, reset on
   teleport, respawn, spawn and scene change, pixel snapping after the blend, an opt-in for
   screen-space sprites, the below-step-rate "nothing vanishes" list. Tests: a ball at half
   alpha is drawn midway; a teleport draws as a jump; blending never changes `world_x`/`world_y`
   or any recorded sample; a sprite spawned and removed within one draw is drawn once; a
   recording is identical with interpolation on and off.
6. **Per-game rates and the audit** (the read-only audit of the 39 `dt_tick` overrides moves
   before sub-plan 4: see the Audit section). `SIMULATION_HZ` per game and the `[timing]` table, the 39
   `dt_tick` overrides audited for per-frame work, Paddle Slap's and the zombies' feel checked at
   120 Hz, the Arcade's inner games and the replay viewer moved onto the driver. Tests: every
   game runs a step count independent of its render rate on the same input; the Arcade's inner
   game draws only on its render target at any outer rate.

## Audit 2026-11-20

Checked against origin/main b7c2abd3 (after #235, #237, #238, #239). The owner's brief at the top
is unchanged (the only line this audit edited above the findings is the Status line, which is
not part of the brief). Verified: every `scene.py` line cited (1538, 1793, 1867, 1884, 1899,
1912, 1986, 2047, 2110, 2572, 2643, 2690, 2872, 2908, 2917, 3145, 3344), `timing.py` 43, 466 and
493, `display_mode.py` 67, `host.py` 342 and 432, `live_sources.py` 112, `recording.py` 1636,
`sources.py` 499, the 39 `dt_tick` overrides outside `scene.py`, no refresh-rate or VSync call in
`src/glitchygames` or `browser/`, and the browser bug still unmerged (its file is in the
`fix/browser-pacer-judder` working tree only). The arithmetic in measurement 3 (2.8
microseconds a frame, one refresh in about 3,000 frames, about 50 s) checks out.

Corrected in place: `game_engine.py` line numbers (shifted 1693-1697 to 1696-1699), the `assert`
count in `scene.py` (24, not ten), the recording counts (11 demos now), and the
"every recording is at 1/60.01" statement (18 of 19; the rally demo is 16.586 ms). Added to
Constraint 8: the window-owner rule from the owner's cursor and key-repeat to-dos, and the
`ContextSlot` requirement. Not verified: "Safari caps at 60" (browser claim, not tested here),
anything on a Raspberry Pi, anything on a 60 Hz display.

What I would reconsider, with my recommendation (the plan's design is unchanged):

1. **The audit of the 39 `dt_tick` overrides comes too late.** It is in sub-plan 6, but
   sub-plan 4 (the fixed step) cannot be designed without knowing which overrides mix per-step
   and per-frame work, and moves animation advance out of `Scene.update`. Worked case: Paddle
   Slap's `dt_tick` and a zombies animation both advance state; at a 120 Hz render rate each
   must run per step or per draw, and that is only known from the audit. Recommend a read-only
   report (a list, no code changes) before sub-plan 4, in sub-plan 1's period; sub-plan 6 keeps
   the fixes.
2. **Sub-plan 3 does two things.** The native VSync request with whole-ratio presentation, and
   folding the browser's `TickPacer` into the same scheduler. The second changes a browser path
   that was only just fixed and that has not been merged yet, so it has a dependency
   (`fix/browser-pacer-judder` on main) and its own risk. Recommend 3a (native) and 3b (the
   host), 3b after the browser fix is on main, each measured alone (the owner's one-change rule).
3. **Sub-plan 4 is the largest in the series.** Extracting a frame driver, the accumulator, the
   input queue, per-step clocks and the stepping policy for replays in one plan cannot land
   green in pieces. Recommend 4a: the frame driver extracted with step equal to frame (no
   behaviour change, every golden and demo unchanged, the lint caps relieved), then 4b: the
   accumulator and fixed step. 4a is also where the Arcade and viewer drivers can be pointed at
   it, which is cheap while nothing else has changed.
4. **Which questions block what.** Questions 1, 2 and 8 (goal, 60.01 versus 60, where the Pi
   measurement runs) gate sub-plans 1 to 3; 3 to 7 gate only 4 and later. Recommend the owner
   answer 1, 2 and 8 first; the plan should not wait on the rest.
5. **Coverage and the browser.** The new modules (`display_refresh`, the frame driver, the
   recorder) need tests with a fake display door and an injected clock, not the real display, so
   they run on the dummy driver at 100% coverage; the dummy driver answers 60, so tests must
   not treat that as a detected rate (the plan's own finding). In the browser the display tick
   is `requestAnimationFrame`, so the refresh query there is the tick spacing, not pygame's
   call: sub-plan 2 must say so.
6. **Owner's decisions.** The "Recommendation" is stated as a build order but depends on
   question 1; it is a recommendation, not a decision, and nothing in the plan is built until the
   owner answers. No other decision was found that belongs to the owner and was made for them.
