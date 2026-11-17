# Refresh-aware rendering and fixed simulation: the owner's brief

Status: TO-DO (2026-11-17), not started. The owner's brief, kept verbatim below; the findings and
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
