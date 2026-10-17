# Bug Tracking for GlitchyGames

This document tracks bugs reported during development. Bugs are listed in order of discovery and will be investigated and fixed as time allows.

## Active Bugs

### 19. Ruff PLW0717: 102 Try Blocks Too Broad
- **Description**: ruff 0.17's `too-many-statements-in-try-clause` (PLW0717, max 5) flags 102 existing try blocks across `glitchygames/`, `scripts/`, and `tests/`
- **Status**: Active (rule temporarily disabled in `pyproject.toml`; remove that ignore when done)
- **Priority**: Low
- **Reporter**: Found while fixing the pre-push hooks
- **Date Reported**: 2026-10-15
- **Details**: Broad try blocks can catch exceptions from statements that were never expected to raise, hiding bugs. Each needs the try narrowed to the statements that can raise, with tests run per file. Re-enable with `uv run ruff check --select PLW0717 glitchygames tests scripts` to list them.

### 21. Parallax Backgrounds Never Scroll During Gameplay
- **Description**: `Camera2D.update()` no longer updates parallax layers, so backgrounds stay frozen at their `snap_to()` position in Brave Adventurer, Papyrus, and Clockwork Keep
- **Status**: Active (fix planned in `plans/2026-10-17-screen-shake-and-synth.md`)
- **Priority**: Medium
- **Reporter**: Found by the adversarial audit of the screen shake spec
- **Date Reported**: 2026-10-17
- **Root Cause**: Commit `df21435` inserted `snap_to()` between `update()`'s `_clamp_to_bounds()` call and its parallax loop, so the loop became the tail of `snap_to()` (which now updates layers twice) and `update()` lost it. Nothing else calls `ParallaxLayer.update_scroll()`.
- **Files**: `glitchygames/camera.py`

### 22. Mixer Pre-Init Settings Never Take Effect
- **Description**: `AudioEventManager` calls `pygame.mixer.pre_init(22050, -16, 2, 1024)` after `pygame.init()` has already started the mixer at (44100, -16, 2) with a 512-sample buffer, so the settings are ignored
- **Status**: Active (fix planned: delete the `pre_init`, document 44100/512)
- **Priority**: Medium
- **Reporter**: Found by the adversarial audit of the screen shake spec
- **Date Reported**: 2026-10-17
- **Impact**: Brave Adventurer generates its sounds for 22050 Hz, so they have always played an octave high at half length. Decided: restore them as written when they move to the engine synthesizer.
- **Files**: `glitchygames/events/audio.py:75`, `glitchygames/engine/game_engine.py:358`, `glitchygames/examples/brave_adventurer/sounds.py`

### 23. Engine Crashes Without an Audio Device
- **Description**: `pygame.mixer.init()` in `AudioEventManager.__init__` raises an uncaught `pygame.error` when no audio device is available
- **Status**: Active (fix planned: catch, log once, run silently)
- **Priority**: Low
- **Reporter**: Found by the adversarial audit of the screen shake spec
- **Date Reported**: 2026-10-17
- **Files**: `glitchygames/events/audio.py:76`

### 24. Jumping on a Clockwork Keep Elevator Never Rides It
- **Description**: `_check_elevator()` accepts `jump` as well as `interact`, but the jump handler clears `on_ground` during event processing and `_check_elevator()` requires `on_ground` on the next frame, so jump only ever jumps
- **Status**: Active (fix planned: interact only; jump always jumps)
- **Priority**: Low
- **Reporter**: Found by the adversarial audit of the screen shake spec
- **Date Reported**: 2026-10-17
- **Files**: `glitchygames/examples/clockwork_keep/game.py:467`

## Resolved Bugs

### 20. ty Static Analysis Fails (36 Errors)
- **Description**: The `static-analysis` pre-push hook fails at its `ty` step with 36 errors (plus 57 `unused-ignore-comment` warnings) in `glitchygames/` and `scripts/`
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while fixing the pre-push hooks
- **Date Reported**: 2026-10-15
- **Date Resolved**: 2026-10-15
- **Details**: Already failing before the uv.lock re-lock (26 errors with ty 0.0.81 on the same code); the bump to ty 0.0.87 added 10 more. Main kinds: unresolved-attribute (10), invalid-property-type-override (9), invalid-argument-type (7), invalid-attribute-override (4). Worst files: `bitmappy/editor.py` (6), `events/voice.py` (5), `scripts/raw_sprite_loader.py` (4).
- **Solution**: Fixed every error without `cast`/`Any`; the only new suppressions are two commented, targeted ones for SpriteFrame's presence-based `_image_stale` flag. Mostly typing gaps: EditorContext protocol members made read-only properties to match Scene, `set_pixel_data` takes a `Sequence`, the `animations` interface type corrected, singleton `__instance__` declared as a ClassVar, scripts' `log` declared ClassVar and `image`/`rect` no longer pre-set to None, optional `speech_recognition`/`miniaudio` modules checked for None where used.
- **Real bugs found and fixed along the way**:
  - `voice_miniaudio.py`: without speech_recognition installed, defining `MiniaudioMicrophone(sr.AudioSource)` raised AttributeError at import, which the backend registry (catching only ImportError) would not handle; the import is now required so a missing package raises ImportError
  - `film_strip_coordinator.on_frame_removed()` copied `editor.selected_frame` (None after the last animation is removed) into the film strip widget's int `selected_frame`; it now falls back to 0
  - Singleton classes could hand a subclass an instance of a different class found on a base class's `__instance__`; instances are now matched with `isinstance(instance, cls)`
- **Dead code removed (follow-up)**: `AnimatedCanvasInterface.controller_indicators` and `ControllerEventHandler.canvas_controller_indicators` were write-only since they were added in `e117684` (2025-10-24); the canvas draws controller markers from live controller state. `VisualIndicators._update_canvas_indicators()` now only forces a canvas redraw while a controller is in canvas mode (`TestUpdateCanvasIndicators` in `tests/tools/test_bitmappy_event_handlers.py`)
- **Files Modified**: `glitchygames/bitmappy/{protocols,editor,animated_canvas,canvas_interfaces,film_strip_coordinator}.py`, `glitchygames/bitmappy/controllers/visual_indicators.py`, `glitchygames/sprites/{frame,animated,animated_interface,bitmappy_sprite}.py`, `glitchygames/ui/sliders.py`, `glitchygames/events/{voice,voice_miniaudio}.py`, `scripts/{ai_query_inspector,basic,legacy_sprite_loader,raw_sprite_loader,sprite_loader}.py`

### 18. Serve Directions Lopsided (Rightward Serves Never Go Downward)
- **Description**: `BallSprite.reset()` serves leftward balls up or down (90-269 degrees) but rightward balls only up (270-359 degrees)
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found while fixing bug #17
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-15
- **Related problems fixed with it**:
  - Serve angles spanned almost the full half-circle, so near-vertical serves crawled across the field at the 50 px/s minimum (~15 s for 800 px); the minimum-speed patch that compensated caused bug #17
  - The serve position was hardcoded for an 800x480 screen (`randbelow(700) + 50`, `randbelow(375) + 25`): off-screen on smaller windows, unused space on larger ones
  - PaddleSlap overwrote every opening serve with a fixed (250, 125), and its RANDOM_SPEED spawns had their own full-circle angle plus a copy of the #17 minimum-speed sign bug
  - `test_zero_speed_scenarios` passed or failed depending on the random spawn position (a wall bounce flipped Y)
- **Solution**: New `ServeSettings(minimum_angle_degrees=15, maximum_angle_degrees=60, horizontal=EITHER, vertical=EITHER, speed=250, spawn_margin=50)` with validation, `ServeHorizontalDirection`/`ServeVerticalDirection` enums, `BallSprite(serve_settings=...)`, a public `serve(serve_toward=None)` that sets only the velocity, and `reset(serve_toward=None)` that picks a position within `spawn_margin` of the actual screen (centered if there's no room) and then serves. All serve randomness uses one `secrets.SystemRandom()` source. The minimum-speed patch is gone. PaddleSlap's opening balls use `PADDLESLAP_SERVE` (the defaults) and RANDOM_SPEED spawns use `PADDLESLAP_SPAWN_SERVE` (150 px/s); fixed-speed spawns keep (250, 125).
- **Files Modified**:
  - `glitchygames/game_objects/ball.py`
  - `glitchygames/examples/paddleslap.py`
- **Tests**: `TestServeSettings` in `tests/game_objects/test_ball.py`: every horizontal x vertical setting x band-edge/middle angle x coin outcome x `serve_toward` override (324 cases), real-randomness band and four-diagonal coverage, 0°/90° extremes, spawn position at several screen sizes including too-small screens, and validation. PaddleSlap serve tests in `tests/examples/test_paddleslap.py`. The whole suite was also run with serve randomness pinned to both extremes to confirm no test depends on chance.

### 7. Ball Collision Trajectory Bug
- **Description**: A horizontally moving ball doesn't update its trajectory after a diagonal collision
- **Status**: Closed (cannot reproduce; reopen as a new bug if seen again)
- **Date Closed**: 2026-10-15
- **Priority**: High
- **Reporter**: User
- **Date Reported**: Not recorded
- **Files**: `glitchygames/game_objects/ball.py`
- **Notes**: Distinct from resolved bug #4 (perpendicular collisions being skipped entirely). Not reproduced on 2026-10-14: the collision sweep tests (every 15° heading, stationary and moving targets, several speeds) show velocities exchanging correctly in all 2328 cases. Likely superseded by the physics rewrites; candidate to close.

### 17. Serves at 90 and 270 Degrees Go the Wrong Way
- **Description**: About 1 serve in 270 from `BallSprite.reset()` moved opposite to its serve side
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while fixing bug #14
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: The 50 px/s minimum-speed rule took its sign from `speed_x`, but `cos(270°)` is -1.8e-16 and `cos(90°)` is +6e-17 in floating point, so the left-side (rightward) 270° serve became -50 px/s and the right-side (leftward) 90° serve became +50 px/s.
- **Solution**: The minimum speed takes its sign from the chosen serve side.
- **Also fixed**: `test_ball_reset_direction` and `test_ball_reset_position` asserted reset() picked a different value than before, which fails by chance (~1 in 270 for direction); they now pin the random source. `test_boundary_bounce_sound_effects` relied on reset()'s random direction pointing into the wall (failed ~half the time once moving-away balls stopped bouncing); it now sets its velocity.
- **Files Modified**:
  - `glitchygames/game_objects/ball.py` (`reset`)
  - `tests/game_objects/test_ball.py`, `tests/game_objects/test_ball_boundary_physics.py`
- **Tests**: `test_every_possible_serve` checks all 270 possible random serves aim toward their side with both components >= 50 px/s. The ball test suites were also run with reset()'s randomness pinned both up and down to confirm no test depends on the random direction.

### 14. Corner Collision Un-Reflects the Ball
- **Description**: A ball hitting a corner is sent back into the corner, bounces off both walls again the next frame, and (with WALL_BOUNCE speed-ups) gets 4 speed-ups for one corner hit
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Found during the speed-up redesign (bug #13); reproduced 2026-10-14
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: The top/bottom and left/right handlers already reflect the ball, then `_handle_corner_collision()` negates both speed components again, undoing the reflection. Reproduction (speed-ups off): world (5, 5), speed (-300, -300), `bounce_left_right=True`, one `dt_tick(1/60)` leaves the ball at (1, 1) still moving (-300, -300) into the corner.
- **Related problems fixed with it** (all in the wall-bounce path):
  - Contact is detected on the snapped rect but reflection used the float position, so a ball at `world_y = 0.3` (rect.y == 0) was "mirrored" to -0.3, outside the playfield (same on every wall)
  - A ball still within half a pixel of a wall after bouncing (moving away) was bounced again the next frame: another sound and another WALL_BOUNCE speed-up
  - A corner hit applied two WALL_BOUNCE speed-ups and played the sound twice
  - The corner handler teleported the ball to 1 px inside the corner, discarding its sub-pixel position
- **Solution**: `_handle_boundary_collisions()` bounces only off walls the ball touches while moving toward them, records which walls were hit, and plays one sound and applies at most one WALL_BOUNCE speed-up per frame. Edge handlers only reflect velocity. New `_keep_inside_playfield()` mirrors any real overshoot back inside on every frame, bounce or not (a ball found past a wall while moving away is moved back without bouncing). The corner handler now only gives visual feedback.
- **Files Modified**:
  - `glitchygames/game_objects/ball.py`
- **Tests**: `TestBallSpriteWallBounceSpeed` in `tests/game_objects/test_ball.py`: every wall and corner x every 15° heading into it x overshoots (2.0, 0.0, -0.3) x 3 speeds x speed-ups on/off must reflect exactly the hit components, keep speed (or apply one step), end at the mirrored position inside the field, and not bounce again over the next 10 frames; plus balls past a wall moving away or stationary must be moved inside with no bounce, sound, or speed-up. `TestCornerCollisions` now asserts correct corner behavior instead of the teleport.

### 16. BallSprite.bounce() Ignores Speed-Up Settings
- **Description**: `BallSprite.bounce()` hardcodes `self.speed *= 1.1`, bypassing `speed_up_settings` entirely
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found during the speed-up redesign (bug #13)
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Details**: Nothing in `glitchygames/` calls `bounce()`; only its own test does
- **Solution**: Removed `bounce()`. It was left over from 2022 angle-based movement: the `direction` it updated no longer affects motion, so its only effect was the hidden speed-up. Real bounces go through the wall handlers and the WALL_BOUNCE trigger.
- **Files Modified**:
  - `glitchygames/game_objects/ball.py`
- **Tests**: `TestBallSpriteWallBounceSpeed` in `tests/game_objects/test_ball.py` replaces the `bounce()` tests: with speed-ups off, bounces off every wall from every 15° heading at 3 speeds must mirror the velocity and keep its magnitude, so any hidden speed change in a bounce path fails; with WALL_BOUNCE, three real bounces give exactly three curve steps

### 15. Continuous Speed-Up Timer Drifts and Drops Intervals
- **Description**: CONTINUOUS speed-ups happen less often than `interval` implies whenever frames don't line up with it
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found during the speed-up redesign (bug #13)
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Details**:
  - `_check_continuous_speed_up()` sets `_last_speed_up_time = current_time` instead of advancing by `interval`, so the remainder of each interval is lost: with interval 1.0, checks at 1.5, 2.4, 3.0, 10.0 give 3 speed-ups instead of 10
  - A long frame or pause applies at most one speed-up (no catch-up)
  - The `>=` comparison on floats can miss by one frame: 0.4 - 0.30000000000000004 < 0.1
  - The timer used the wall clock (`time.time()`), so time spent paused counted toward speed-ups
- **Solution**: The timer now accumulates game time (the `dt` passed to `dt_tick`) and is reset by `reset()`. New `SpeedUpSettings.schedule` (`SpeedUpSchedule`): `FIXED_RATE` (default; leftover time carries over so the rate is frame-rate independent, and a long frame yields one speed-up, not a burst), `CATCH_UP` (every elapsed interval, bursting after a long frame; for deterministic simulations), `MINIMUM_GAP` (the previous behavior: the interval restarts when a speed-up fires). A 1e-9 s tolerance stops float accumulation from delaying a speed-up.
- **Files Modified**:
  - `glitchygames/game_objects/ball.py`
- **Tests**: `TestContinuousSpeedUpSchedule` in `tests/game_objects/test_ball_speed_up.py` checks every schedule x 3 intervals x 5 frame patterns (30/60/144 fps, jittery, long hitches) against a reference model, plus frame-rate independence, burst/no-burst behavior, pause (wall clock) independence, reset, and float accumulation

### 13. Speed-Up Mode Names Don't Match Their Behavior
- **Description**: `SpeedUpMode` names promise growth curves and axes the code doesn't deliver
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while resolving bug #12
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Details**:
  - `LINEAR` multiplies speed by `speed_up_multiplier` each time, which compounds: over n speed-ups speed grows as m**n (exponential growth, not linear)
  - `LOGARITHMIC_*` is identical to `LINEAR`; nothing tapers off
  - `EXPONENTIAL_*` raises the multiplier to a power based on current speed (capped at 2), which accelerates faster than exponential
  - `_X`/`_Y` suffixes don't restrict the speed-up to that axis (all modes preserve the angle)
  - `speed_up()` silently ignores an unrecognized `speed_up_type`
- **Solution**: Replaced the `SpeedUpMode` bit flags with `SpeedUpSettings(triggers, curve, axes, multiplier, interval, max_speed)`. `SpeedUpCurve` LINEAR/EXPONENTIAL/LOGARITHMIC follow their textbook formulas; `SpeedUpAxes` BOTH/X_ONLY/Y_ONLY scale only what they say; `SpeedUpTrigger` CONTINUOUS/PADDLE_BOUNCE/WALL_BOUNCE share one curve per ball. Each speed-up multiplies the current speed by the curve's step ratio f(n+1)/f(n), so collisions between steps are preserved. Settings are validated. The paddle collision's hardcoded 500 px/s cap became `max_speed`. PaddleSlap now uses a true LOGARITHMIC curve (multiplier 1.15, max 500).
- **Files Modified**:
  - `glitchygames/game_objects/ball.py`
  - `glitchygames/examples/paddleslap.py`
  - 14 test files migrated to the new API (no tests removed)
- **Tests**: `tests/game_objects/test_ball_speed_up.py`: exact curve values, settings validation, axes, caps, triggers, reset, and a sweep of every trigger x curve x axes x 24 headings x 3 speeds; deeper per-curve tests in `test_ball_linear_speedup.py`, `test_ball_exponential_speedup.py`, `test_ball_logarithmic_speedup.py`

### 12. Paddle-Bounce Speed-Up Scales Both Axes, Test Expects X Only
- **Description**: `test_paddleslap_speed_up_logic` expects an `ON_BOUNCE_LOGARITHMIC_X` paddle bounce to speed up only `speed.x`; the ball now scales both components (`speed.y` 200 -> 230)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while restoring a clean test suite
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: `1a9a7fe` (2026-03-31) deliberately changed `BallSprite.speed_up()` to scale both components to preserve the trajectory angle, so `_X`/`_Y` speed-up flags now only choose which component drives the multiplier. The test predates that change and was never re-run because of bug #11.
- **Solution**: Kept the deliberate angle-preserving behavior; updated the test to expect it and documented in `SpeedUpMode`/`speed_up()` that `_X`/`_Y` don't mean single-axis. Naming problems tracked as bug #13.
- **Files Modified**:
  - `glitchygames/game_objects/ball.py` (docstrings only)
  - `tests/examples/test_paddleslap.py`
- **Tests**: `TestBallSpeedUpSweep` in `tests/game_objects/test_ball_speed_up.py`: every paddle/wall flag combination x every 15° heading x 3 speeds checks the heading is preserved and the speed factor matches

### 11. tests/examples/ Silently Never Collected
- **Description**: The 11 tests in `tests/examples/` never ran in the default suite
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Found while restoring a clean test suite
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: `norecursedirs = ["examples", ...]` in `pyproject.toml` (added in `e7ecce6`, 2025-10-05) was meant for the top-level `examples/` directory, but pytest matches these patterns against directory names at any depth, so it also excluded `tests/examples/`. The top-level directory was already outside `testpaths = ["tests"]`.
- **Solution**: Removed `"examples"` from `norecursedirs`, with a comment explaining the trap
- **Files Modified**:
  - `pyproject.toml`
- **Tests**: `tests/test_suite_collection.py` fails if any test file under `tests/` sits in a directory matching `norecursedirs` or has a name `python_files` will not collect

### 10. API Route Test Broken by FastAPI 0.143
- **Description**: `test_app_has_routes` failed with `'_IncludedRouter' object has no attribute 'path'`
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while restoring a clean test suite
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: The uv.lock re-lock bumped FastAPI 0.141.1 -> 0.143.1, which stores each `include_router()` as an `_IncludedRouter` entry in `app.routes` with no `.path`. The API itself was unaffected (all endpoints still respond); the test inspected framework internals.
- **Solution**: Replaced with tests of the public contract: the OpenAPI schema lists exactly the expected paths, and every documented path/method reaches a handler (no 404/405)
- **Files Modified**:
  - `tests/api/test_api_main.py`

### 9. Logging Mock Leak Broke ~3,300 Tests
- **Description**: The full suite reported roughly 3,300-3,800 setup errors (`'Mock' object is not iterable`, `KeyError: StashKey`); counts varied with test order
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Found while verifying bug #8
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: Eight tests in `tests/events/test_voice.py` patched `'glitchygames.events.voice.logging.getLogger'`, which is the global `logging.getLogger`. pytest's logging plugin calls `logging.getLogger()` at the start of teardown, before mocker undoes patches; it crashed on the Mock, the patch was never undone, and every later test in that worker errored.
- **Solution**: The tests now inject a `voice_logger` fixture (`mocker.Mock(spec=logging.Logger)`) through `VoiceEventManager(logger=...)` instead of patching. A `pytest_runtest_call` wrapper in `tests/conftest.py` fails any test that leaves `logging.getLogger` or `logging.Logger.manager` replaced, restoring the real objects first so the failure cannot cascade.
- **Files Modified**:
  - `tests/events/test_voice.py`
  - `tests/conftest.py`

### 8. Ball-to-Ball Separation Undone on the Next Frame
- **Description**: After two balls collide, the push that separates them is thrown away one frame later, so overlapping balls stay overlapped and can re-collide or stick
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Found while investigating bug #7
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: `Game._separate_overlapping_balls()` (`glitchygames/examples/paddleslap.py`) moves only `rect`. `BallSprite.dt_tick()` rebuilds `rect` from `world_x`/`world_y` every frame, so the separation is discarded. Every other ball movement path updates `world_x`/`world_y` first. Regressed when `1a9a7fe` (2026-03-31) introduced sub-pixel world positions.
- **Solution**: `_separate_overlapping_balls()` now moves `world_x`/`world_y` by the (sub-pixel) separation, then sets `rect` from `round(world)` as `dt_tick` does. (Adding whole-pixel rect deltas to `.5` world values instead disagrees with Python's banker's rounding.)
- **Files Modified**:
  - `glitchygames/examples/paddleslap.py`
- **Tests**: `tests/game_objects/test_ball_collision_physics.py` (`TestBallCollisionSweepStationaryTarget`, `TestBallCollisionSweepMovingPair`): all 2328 sweep cases failed before the fix and pass after

### 6. Anthropic SDK Rejects Bitmappy's Non-Streaming 64k-Token Requests
- **Description**: Every Bitmappy AI request fails client-side with `ValueError: Streaming is required for operations that may take longer than 10 minutes`
- **Status**: Resolved (end-to-end sprite generation pending a funded API key)
- **Priority**: High
- **Reporter**: Found while verifying bug #5
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: The uncommitted `uv.lock` re-lock bumped `anthropic` from 0.30.1 to 0.125.0. Newer SDKs refuse non-streaming requests whose `max_tokens` implies more than 10 minutes, unless a custom timeout is set. Bitmappy sends `max_tokens=AI_MAX_OUTPUT_TOKENS` (64000). `_configure_client_timeouts()` never reaches the Anthropic client because aisuite creates providers lazily on the first request, so `client._providers` is empty at init time.
- **Solution**: `_initialize_ai_client()` always passes `{'anthropic': {'timeout': AI_TIMEOUT}}` (merged with any ollama config) to `ai.Client()`. Verified a full 64k-token request now reaches the API. Switching to streaming remains a possible future improvement.
- **Files Modified**:
  - `glitchygames/bitmappy/ai_worker.py` (`_initialize_ai_client`)
- **Tests**: `tests/tools/test_bitmappy.py` (`TestInitializeAiClient`)

### 5. AI Errors Never Reach the Bitmappy UI
- **Description**: When an AI request failed (e.g. Anthropic "credit balance is too low"), Bitmappy showed nothing or "AI response was empty"
- **Status**: Resolved
- **Priority**: High
- **Reporter**: User
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: Three compounding problems: (1) the retry decorator retried every exception, including permanent 4xx errors, for up to 5 attempts with backoff; (2) `_process_ai_request()` then re-raised provider SDK exceptions (e.g. `anthropic.BadRequestError`), which are not in `run_ai_worker()`'s caught exception types, so the worker process died and no response was ever queued; (3) `AIManager._process_ai_response()` ignored `AIResponse.error` and always displayed "AI response was empty"
- **Solution**: `_process_ai_request()` returns `AIResponse(content=None, error='<Type>: <message>')` instead of raising; new `_is_non_retryable_ai_error()` gives up immediately on 4xx except 408/409/429 (`RETRYABLE_CLIENT_ERROR_STATUS_CODES`); new `AIManager._handle_empty_ai_response()` shows "AI request failed: <error>" in the AI text box
- **Files Modified**:
  - `glitchygames/bitmappy/ai_worker.py`
  - `glitchygames/bitmappy/ai_manager.py`
  - `glitchygames/bitmappy/constants.py`
- **Tests**: `tests/tools/test_bitmappy_additional.py` (`TestProcessAiRequest`, `TestCreateAiRetryDecorator`), `tests/tools/test_bitmappy_editor_scene.py` (`TestProcessAiResponseErrors`)

### 4. Vertical vs Horizontal Ball Collision Detection Bug
- **Description**: Perpendicular ball collisions (vertical ball hitting horizontal ball) were incorrectly skipped based on relative velocity calculation
- **Status**: Resolved
- **Priority**: High
- **Reporter**: User
- **Date Reported**: Not recorded
- **Date Resolved**: 2026-03-21 (commit c9b9f5f)
- **Root Cause**: Collision detection checked if `dvn > 0` (relative velocity along normal), which can be positive for perpendicular collisions depending on geometry. Complex speed ratio logic then incorrectly skipped valid collisions when speeds were similar (speed_ratio < 1.2).
- **Solution**: Simplified collision detection to only skip when balls are BOTH moving away (dvn > 0) AND not overlapping (distance >= collision_distance). Removed faulty speed ratio check that prevented perpendicular collisions.
- **Impact**: Vertical vs horizontal collisions now processed correctly, no more missed collisions
- **Files Modified**:
  - `glitchygames/examples/paddleslap.py` - Simplified collision detection logic in `_handle_ball_collisions()`
- **Tests**: `tests/game_objects/test_ball_collision_physics.py` (21/21 passing)

### 3. First Pasted Frame Alpha Loss
- **Description**: First frame pasted into a newly created film strip on a per-pixel alpha sprite lost transparency
- **Status**: Resolved
- **Priority**: High
- **Reporter**: User
- **Date Reported**: Not recorded
- **Date Resolved**: 2026-03-21 (commit c9b9f5f)
- **Root Cause**: Code duplication - `_add_new_animation()` created surfaces without `pygame.SRCALPHA` flag, while `_insert_frame_at_tab()` had it
- **Solution**: Created canonical `_create_blank_frame()` helper method with proper SRCALPHA support, eliminated 24 lines of duplicated code
- **Impact**: All new frames (first and subsequent) now properly preserve per-pixel alpha transparency
- **Files Modified**:
  - `glitchygames/tools/bitmappy.py` - Created `_create_blank_frame()` helper, refactored `_add_new_animation()` and `_create_animated_sprite()`
  - `glitchygames/tools/film_strip.py` - Refactored `_insert_frame_at_tab()` to use shared helper
- **Current Locations** (after the bitmappy editor refactor, #87): `_create_blank_frame()` and `_add_new_animation()` in `glitchygames/bitmappy/film_strip_coordinator.py`, `_create_animated_sprite()` in `glitchygames/bitmappy/editor_setup.py`, `_insert_frame_at_tab()` in `glitchygames/bitmappy/film_strip.py`

### 2. Ball-to-Ball Collision Clipping Bug
- **Description**: Balls moving perpendicular (horizontal vs vertical) would clip through each other, getting stuck in repeated collision loops
- **Status**: Resolved
- **Priority**: High
- **Reporter**: User
- **Date Reported**: Not recorded
- **Date Resolved**: 2025-10-24 (commit e117684)
- **Root Cause**: Float separation values (< 1.0) rounded to 0 when assigned to integer rect.x/rect.y positions, leaving balls overlapped after collision
- **Solution**: Ensure minimum 1-pixel separation in each direction where collision normal has significant component, use round() for integer conversion
- **Impact**: Balls can now collide cleanly without clipping, especially in horizontal vs vertical scenarios
- **Files Modified**:
  - `glitchygames/examples/paddleslap.py` - Fixed ball separation logic in `_handle_ball_collisions()`
- **Tests**: `tests/game_objects/test_multi_ball_ball_collision_bounce.py` - No more "(clipping through)" messages

### 1. Ball Movement Speed Inconsistency
- **Description**: Balls sometimes travel faster going left than right and faster going up than down
- **Status**: Resolved
- **Priority**: High
- **Reporter**: User
- **Date Reported**: Not recorded
- **Date Resolved**: 2025-10-24 (commit e117684)
- **Root Cause**: The `speed_up()` method in `BallSprite` was using a flawed logarithmic scaling formula that capped speed increases at 5% instead of the expected 15%, causing inconsistent speed changes over time.
- **Solution**: Replaced the complex logarithmic scaling with simple linear scaling that applies the multiplier directly to both speed components.
- **Files Modified**:
  - `glitchygames/game_objects/ball.py` - Fixed `speed_up()` method
  - `glitchygames/game_objects/ball.py` - Added `round()` calls in `dt_tick()` for precision
  - `glitchygames/game_objects/paddle.py` - Added `round()` calls in `dt_tick()` for precision

## Notes

- All bugs are tracked with discovery date and priority level
- High priority bugs affect core gameplay and should be addressed first
- Medium priority bugs affect user experience but don't break core functionality
- Low priority bugs are minor issues or edge cases
