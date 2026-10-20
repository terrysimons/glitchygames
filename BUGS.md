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

### 59. Papyrus Sprites Keep Their Unscaled Native Rect Size
- **Description**: Papyrus's TOML sprites are drawn at 2x (`SPRITE_SCALE`), but their `rect` keeps the native size: the player's rect is 20x28 while its image is 40x56, a scarab's 10x8 while its image is 20x16
- **Status**: Active (latent)
- **Priority**: Low
- **Reporter**: Found on feature/engine-world-space (Task 8)
- **Date Reported**: 2026-10-18
- **Details**: Predates the branch. Latent today: every Papyrus sprite is `dirty = 2`, the scene renders the full screen, the image overhangs the rect by at most 28 px (less than `CULL_MARGIN_PIXELS`, 32), and hitboxes and the debug overlay use collision rects. It would surface with mouse picking (`sprites_at_position`, `pygame.sprite.spritecollide`), a non-dirty Papyrus sprite, or `pygame.display.update(rects)`. Fixing it (sizing rect from the scaled image in `apply_transparency_and_scale` / `prepare_papyrus_sprite`) changes every Papyrus rect size in the golden trace, so it needs its own expected-difference class in `tests/world/test_golden_traces.py`
- **Files**: `glitchygames/examples/brave_adventurer_papyrus/sprite_utils.py`

### 60. Brave Adventurer Ground and Walls Stay Drawn Only Because the Parallax Layers Dirty the Screen
- **Description**: The shared `GroundSegment` and `StoneWall` (both editions) are `dirty = 1` and are dirtied again only when they move. With a still camera they stay on screen only because the full-screen `dirty = 2` ParallaxLayers make the whole screen dirty every frame
- **Status**: Active (fragile, works today)
- **Priority**: Low
- **Reporter**: Found by the Task 8 review on feature/engine-world-space
- **Date Reported**: 2026-10-18
- **Details**: If the parallax layers stop redrawing the full screen (made static, partially sized, or removed), a still camera would let other sprites' clearing erase the terrain. Either make the terrain `dirty = 2` or document the dependency where the layers are built
- **Files**: `glitchygames/examples/brave_adventurer/terrain.py`, `glitchygames/examples/brave_adventurer/game.py`, `glitchygames/examples/brave_adventurer_papyrus/game.py`

### 67. Bitmappy's Joystick-Event Trigger Conversion Assumes pygame 1's Integer Axis Scale
- **Description**: `ControllerEventHandler._read_joystick_trigger_values` converts trigger axes with `(raw + 32768) / 65535`, but pygame 2 reports joystick axes as -1.0..1.0, so both triggers always read about 0.5 whatever their position
- **Status**: Active (latent: only events without an `instance_id` take this path, and pygame-ce's joystick and controller events all carry one, so they go to `_read_controller_trigger_values`, which converts correctly)
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 6)
- **Date Reported**: 2026-10-19
- **Details**: Fix with the `(raw + 1.0) / 2.0` conversion the controller path uses (or drop the path if no event without an `instance_id` can reach it). `TestTriggerValuesFromSnapshot` in `tests/tools/test_bitmap_editor_scene.py` pins today's values
- **Files**: `glitchygames/bitmappy/controllers/event_handler.py`

### 68. ControllerEventManager Keys Controllers by Device Index but Routes Events by Instance Id
- **Description**: `ControllerEventManager.__init__` and `on_controller_device_added_event` store each proxy under its device index (`self.controllers[controller_id]`, `self.controllers[event.device_index]`), but the axis, button, touchpad, sensor and removal handlers look proxies up by `event.instance_id`. The two agree only while every controller's instance id equals its device index (the first controllers plugged in at startup); after a reconnect the lookup raises `KeyError` or reaches the wrong controller
- **Status**: Active
- **Priority**: Medium
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 6)
- **Date Reported**: 2026-10-19
- **Details**: Key the proxies by instance id (`ControllerEventProxy._instance_id`, set from the controller's joystick view since Task 6), as `JoystickEventManager` does. The joystick demo's controller-mode tab code treats the keys as device indexes, so it needs updating with it
- **Files**: `glitchygames/events/controller.py`, `glitchygames/examples/joystick_demo.py`

### 72. MultiControllerEnhancements Stores a Duration Where Its Next Call Expects a Timestamp
- **Description**: `MultiControllerEnhancements._update_performance_metrics` stores the first reading as `performance_metrics[operation]`, then on each later call replaces it with `timestamp - performance_metrics[operation]`. From the third call on it subtracts a duration from a timestamp, so `'visual_update'` alternates between a duration and a timestamp-sized number
- **Status**: Active (diagnostic only: the value is reported by `get_controller_performance_stats` and nothing acts on it)
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 9)
- **Date Reported**: 2026-10-19
- **Details**: Keep the last reading and the last duration under separate keys (or separate dicts), so each call subtracts the previous reading. The readings come from `measured_seconds()` (real time, diagnostics only) since Task 12b
- **Files**: `glitchygames/bitmappy/controllers/enhancements.py`

### 73. PaddleSlap Sets the `game` Logger to INFO at Import, Overriding `--log-level`
- **Description**: `glitchygames/examples/paddleslap.py:46-47` calls `logging.getLogger('game').setLevel(logging.INFO)` when the module is imported (and `glitchygames/game_objects/paddle.py:18-19` does the same for `game.paddle`). The level set on the `game` logger wins over the root level `--log-level` configures, so `--log-level warning` or `error` still prints every `game.*` INFO line when PaddleSlap runs
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 14: the `--audit` children of the PaddleSlap golden replay printed INFO lines under `--log-level error`)
- **Date Reported**: 2026-10-19
- **Details**: Not fixed here: removing the module-level `setLevel` calls changes what PaddleSlap logs by default for other `game.*` loggers if anything else lowers the root level, and needs checking against the other examples that may do the same. `--log-level` defaults to `info`, so only runs that ask for a quieter level are affected
- **Files**: `glitchygames/examples/paddleslap.py`, `glitchygames/game_objects/paddle.py`

### 74. `debug_events` Is Always False: `--log-level` Is Compared With Upper-Case Names
- **Description**: `GameEngine.initialize_arguments` (`glitchygames/engine/game_engine.py`, around line 634) sets `OPTIONS['debug_events']` from `OPTIONS['log_level'] in {'DEBUG', 'CRITICAL', 'ERROR'}`, but `--log-level` (`glitchygames/events/game.py`) is lower-cased by `type=str.lower` and its choices are lower case, so the test never matches and unhandled events are never logged through `debug_events`
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 14)
- **Date Reported**: 2026-10-19
- **Details**: Not fixed here: correcting the case would turn event debug logging on for `--log-level error` and `critical` runs too, which looks unintended (the set probably meant `debug` only); the intended levels need deciding first
- **Files**: `glitchygames/engine/game_engine.py`, `glitchygames/events/game.py`, `glitchygames/events/base.py`

## Resolved Bugs

### 69. The Live Device Registry Keeps Every Enumeration Answer and Opened Descriptor Until a Recorder Takes Them
- **Description**: `LiveDeviceRegistry` appends every enumeration answer and every opened device's descriptor to lists that only `take_enumeration_answers()` / `take_opened_descriptors()` empty, and nothing calls them yet (the recorder will). Without a recorder they grow for the whole run: the joystick demo counts devices every frame (one answer per frame), and Bitmappy's controller scan reopens every joystick once a second
- **Status**: Resolved
- **Priority**: Low (tens of bytes per answer)
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 6)
- **Date Reported**: 2026-10-19
- **Files**: `glitchygames/input/devices.py`, `glitchygames/live_sources.py`
- **Date Resolved**: 2026-10-19
- **Solution**: `LiveSources.end_frame` calls `LiveDeviceRegistry.discard_untaken()`, which drops the frame's answers and descriptors nobody took; a recorder (Task 11) takes them before `end_frame`. The registry also forgets a device when it is removed (the joystick and controller managers' removal handlers call `forget_device`) or when `poll()` finds it detached or raising, instead of logging a traceback every frame. The joystick demo looks joystick device indexes up once per frame instead of once per tracked device
- **Files Modified**: `glitchygames/input/devices.py`, `glitchygames/live_sources.py`, `glitchygames/events/joystick.py`, `glitchygames/events/controller.py`, `glitchygames/examples/joystick_demo.py`
- **Tests**: `test_live_frames_without_a_recorder_keep_no_enumeration_answers`, `test_answers_taken_before_the_end_of_a_live_frame_are_intact` and the forget tests in `tests/input/test_devices.py`; the removal tests in `tests/events/`; `test_joystick_device_index_lookup_opens_each_joystick_once_per_frame` in `tests/examples/test_joystick_demo.py`

### 71. The Joystick Demo Called `get_id` / `get_instance_id` on Game Controllers
- **Description**: In controller mode the demo's device panel called `get_id()` and `get_instance_id()` on the `pygame._sdl2.controller.Controller`, which has neither, so the `AttributeError` (not caught by `except pygame.error`) would have stopped the demo once #66 no longer did
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 6)
- **Date Reported**: 2026-10-19
- **Date Resolved**: 2026-10-19
- **Solution**: Both lookups also catch `AttributeError`; the controller-mode readout takes the instance id from the controller's joystick view
- **Files Modified**: `glitchygames/examples/joystick_demo.py`

### 70. Bitmappy Read Controller State From the Wrong Device
- **Description**: `ControllerEventHandler._read_controller_trigger_values` opened `pygame.joystick.Joystick(event.instance_id)` and `is_controller_button_held` opened `pygame.joystick.Joystick(controller_id)`, but pygame's joystick constructor takes a device index. An instance id differs from the device index after a reconnect, and `controller_id` is Bitmappy's slot number (0-3), so both read the wrong device or raised `pygame.error` (read as "not held" / 0.0)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the replay core pre-flight on feature/gameplay-replay (Task 6)
- **Date Reported**: 2026-10-19
- **Date Resolved**: 2026-10-19
- **Solution**: Both read the frame's input snapshot (`current_input()`) by instance id; `is_controller_button_held` finds the slot's instance id through `find_controller_info`
- **Files Modified**: `glitchygames/bitmappy/controllers/event_handler.py`
- **Tests**: `TestIsControllerButtonHeld` and `TestTriggerValuesFromSnapshot` in `tests/tools/test_bitmap_editor_scene.py`

### 66. The Joystick Demo Calls `pygame._sdl2.controller.name_forindex`, Which pygame-ce Does Not Have
- **Description**: `joystick_demo.py` calls `pygame._sdl2.controller.name_forindex` in controller mode (building a proxy's name and validating a controller), but pygame-ce 2.5.8 has no such function, so the call raises `AttributeError`, which the surrounding `except pygame.error` does not catch
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 5)
- **Date Reported**: 2026-10-19
- **Details**: The `# type: ignore[attr-defined]` on both lines hid it from the type checkers. Only pygame-ce's legacy stub `pygame/_sdl2/controller_old.pyi` declares it; the live `pygame/_sdl2/controller.pyi` does not
- **Date Resolved**: 2026-10-19
- **Solution**: Both calls go through the devices door's `name_for_index` (glitchygames/input/devices.py, replay core Task 6), which answers None when pygame has no lookup; the device panel then shows 'Unknown Controller'. The `# type: ignore` comments are gone
- **Files Modified**: `glitchygames/examples/joystick_demo.py`

### 65. A Test Left GameEngine.USE_FASTEVENTS Set for Every Later Test on Its Worker
- **Description**: `test_use_fastevents_with_old_pygame` mocks pygame as version 1.1, so `GameEngine.__init__` sets the class attribute `GameEngine.USE_FASTEVENTS = True`; nothing undid it, so every later engine on that pytest worker chose the fastevent path (and, since the engine's doors, created fastevent `LiveSources`). Harmless only because `pygame.fastevent` no longer exists once the test's mock is undone
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 2 review)
- **Date Reported**: 2026-10-19
- **Date Resolved**: 2026-10-19
- **Root Cause**: The autouse `restore_game_engine_class_state` fixture restored only `game`, `icon` and `OPTIONS`, not the other class attribute engine code writes
- **Solution**: The fixture also restores `USE_FASTEVENTS`, and the test patches it with `mocker.patch.object` so it undoes its own write
- **Files Modified**: `tests/conftest.py`, `tests/engine/test_game_engine.py`
- **Tests**: `TestGameEngineFastEvents` in `tests/engine/test_game_engine.py`; the full suite

### 64. Collision Used the Previous Frame's Pose (Hitbox Up to 4 px Inside a Wall for One Frame)
- **Description**: In Brave Adventurer and Clockwork Keep, on the frame the player turned toward a wall or started to run while standing at it, the drawn hitbox sat 1-4 px inside the wall for one frame; the first ground check after a respawn also ran on the blank image, so the player stood 1-2 px high
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found on feature/debug-overlay (`plans/future-work.md`); fixed on feature/engine-world-space
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-18
- **Root Cause**: Both games drew the player's pose in `update()`, which runs in the render phase after collision, so wall and ground resolution in `dt_tick` used the previous frame's image and hitbox
- **Solution**: The pose rule (CLAUDE.md, World Space): each player draws its pose in `dt_tick` (`_draw_pose()`), after physics and the state machine and before collision, then refits its wall bounds to the new hitbox; `update()` keeps only visual work (the respawn fade). Papyrus already drew in `dt_tick`
- **Files Modified**: `glitchygames/examples/clockwork_keep/player.py` (51d4f08), `glitchygames/examples/brave_adventurer/player.py` (dc4d25f)
- **Tests**: `TestPoseBeforeCollision` in `tests/examples/test_clockwork_keep.py` and `tests/examples/test_brave_adventurer_game.py` (8 wall/facing/key cases each, hitbox checked after logic and after render, both Brave editions); the golden traces prove the changed frames exactly

### 63. Camera Stepped Ahead on the Frame a Scene Resumed From Pause
- **Description**: After the engine took over camera aiming, Brave Adventurer's camera moved one extra smoothing step on the frame it resumed from the pause screen, so every sprite was drawn a little off for the following frames (about 470 golden-trace rects on frames 373-386)
- **Status**: Resolved (found and fixed before it reached main)
- **Priority**: Medium
- **Reporter**: Found by the golden traces on feature/engine-world-space (Task 7)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `PauseScene` resumes with `switch_to_scene` during event processing, after the pause scene's `dt_tick`. The engine then aimed the resumed scene's camera that same frame although that scene ran no logic, an extra step the games' own `camera.update` in `dt_tick` had never taken
- **Solution**: `SceneManager._run_scene_frame` aims the camera only when the scene that ran `dt_tick` this frame is still active; its world sprites are still positioned for the frame's render
- **Files Modified**: `glitchygames/scenes/scene.py` (0823479)
- **Tests**: `test_camera_waits_for_the_resumed_scene_logic` in `tests/world/test_frame_integration.py`; the Brave Adventurer golden trace

### 62. Frame Processing Time Included the Pacing Sleep
- **Description**: The per-frame processing time handed to the performance manager was measured after `_handle_frame_pacing`, so it included the sleep; `AdaptiveClamping.get_spare_time_stats` reported about zero spare capacity whenever a timer backend paced the loop
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found on feature/engine-world-space (Task 5)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `actual_processing_time` was taken from the frame start to after pacing, not to the end of the frame's work
- **Solution**: `SceneManager.start()` measures `processing_seconds` from the frame start to the end of `_run_frame()`, before pacing, and passes it to `_finish_frame`, which records it (engine audit #15)
- **Files Modified**: `glitchygames/scenes/scene.py` (733ebb4)
- **Tests**: `test_processing_time_excludes_the_pacing_sleep` in `tests/world/test_finish_frame.py` (on a fake clock; before the fix the sample was 0.0234 s for 0.0059 s of work)

### 61. Brave Adventurer Sprites That Had Been Off Screen Stopped Being Drawn
- **Description**: Brave Adventurer's per-sprite culling set `dirty = 0` on sprites outside the screen. `Scene.update()` calls `update()` only on dirty sprites, so an off-screen scarab never drew its image: collision then used the blank image (the whole image as the hitbox) and the scarabs rolled 2 px above the ground. Enemies that draw in `update()` (Cobra, Scarab, Scorpion) were drawn once when they came back on screen (the `visible` setter dirtied them) and then froze on that frame
- **Status**: Resolved
- **Priority**: Low (the scripted runs never show an enemy returning on screen; worked out from the code and proven on the scarabs)
- **Reporter**: Found by the golden traces on feature/engine-world-space (Task 7)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: Culling and redraw scheduling shared one flag: `dirty = 0` meant both "nothing changed" and "do not run `update()`"
- **Solution**: The games' `is_visible` culling was removed; the engine's positioning step culls with `visible` only and never lowers `dirty = 2` (spec 2.4). The scarabs now rest their visible underside on the ground (3384 golden rects, each proven by an exact rule; a scratch emulation restoring only the old culling reproduced the baseline with 0 differences)
- **Files Modified**: `glitchygames/examples/brave_adventurer/terrain.py`, `glitchygames/examples/brave_adventurer/enemies.py` (dc4d25f); Papyrus's copies in d5144ce
- **Tests**: `test_scarab_rolls_with_its_visible_bottom_on_the_ground`; the off-screen Papyrus scarab keeps `dirty = 2` (`TestPapyrusEngineWorldSpace` in `tests/examples/test_brave_adventurer_game.py`); `test_dirty_two_sprite_stays_two` in `tests/world/test_positioning.py`

### 58. Frame Pacing Bursts to Catch Up After a Hitch
- **Description**: After a long stall (a 2 s hitch, a window drag, a debugger pause) the main loop ran about 120-150 frames back to back without sleeping: a CPU spike, skewed FPS, frame-time and 1%-low statistics, uneven presentation, and anything counted per frame ran fast until the deadlines caught up
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found on feature/engine-world-space
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: Both timer backends' `compute_deadline` returned `previous_deadline + period` unconditionally, so after a stall every missed deadline was already in the past and `sleep_until_next` returned immediately for each of them
- **Solution**: A shared `next_frame_deadline_ns` in `glitchygames/timing.py` (used by `FastTimer` and `PygameTimer`) re-anchors to `now + period` when the loop is more than one full period behind (`now - (previous + period) > period`), dropping the backlog. Exactly one period behind still catches up, as does any normal jitter, so the long-run rate stays exactly at the target. The first frame and the uncapped (period 0) result are unchanged. PygameTimer's clock is whole milliseconds, so its lateness is measured to within 1 ms
- **Files Modified**: `glitchygames/timing.py`, `tests/timing/test_timing.py`, `CLAUDE.md`
- **Tests**: `TestDeadlineReanchorsAfterHitch` and `TestDeadlineReanchorBoundary` in `tests/timing/test_timing.py` (both backends on a fake clock: a 2 s hitch re-anchors and leaves no unslept frames (157 before the fix), a 2 ms late frame still catches up, both sides of the boundary, an exact average rate over 1,000 jittery frames, uncapped unchanged); existing `compute_deadline` tests now use an on-time previous deadline instead of a fixed 1 s one

### 57. PaddleSlap Reseeds Python's Global random Module at Startup
- **Description**: Creating PaddleSlap's `Game` called `random.seed()` with a value from `time.perf_counter()`, under the comment "Set random seed for reproducible randomness". The seed was neither reproducible (it came from the clock) nor used by PaddleSlap (its randomness comes from `secrets` and the ball's `_SERVE_RANDOM`), but it reset the process-wide `random` module for every other user in the process (for example `glitchygames/audio/controller_audio.py`'s noise), and the golden-trace harness had to save and restore the global state around each run
- **Status**: Resolved
- **Priority**: Low (no visible effect; a hidden global side effect)
- **Reporter**: Found on feature/engine-world-space (Task 1)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: A leftover reseed from the coverage branch (a029a67); nothing in PaddleSlap reads the global `random` module
- **Solution**: Removed the reseed, its log line and the `random` import. The golden-trace harness no longer fakes `time.perf_counter` for PaddleSlap or saves/restores the global random state; the PaddleSlap golden trace is unchanged (the harness never depended on the reseed)
- **Files Modified**: `glitchygames/examples/paddleslap.py`, `scripts/record_golden_traces.py`
- **Tests**: `test_game_initialization_leaves_global_random_state_alone` in `tests/examples/test_paddleslap.py`; `tests/world/test_golden_traces.py` (PaddleSlap trace still matches)

### 56. isinstance/issubclass Against Scene, Sprite and Every Concrete Event Class Is False for Subclasses
- **Description**: `issubclass(SubScene, Scene)` and `isinstance(sub_scene, Scene)` were False for every real subclass; the same held for every concrete class deriving from `EventInterface` (`Sprite`, `BitmappySprite`, `Scene`, the `*EventStubs`, the example game scenes, UI widgets and dialogs). Only an object whose exact type is the checked class passed (Python's exact-type fast path)
- **Status**: Resolved
- **Priority**: Low (no engine code path depended on the wrong answer; it blocked using isinstance)
- **Reporter**: Found on feature/engine-world-space (Task 1b)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `EventInterface.__subclasshook__` returned `False` when its structural check failed. To `abc`, False means "definitely not a subclass", so normal inheritance was never consulted. Concrete classes have no abstract methods, so the structural check always failed for them
- **Solution**: The hook returns True when the class implements every abstract method of the interface and `NotImplemented` otherwise, so `abc` falls back to inheritance. Audit (every `isinstance`/`issubclass` against an `EventInterface` subclass in `glitchygames/`, `scripts/` and `tests/`, plus a full-suite run with an instrumented hook): no check on a real object changes outcome (the checked objects are exact types or classes without subclasses); the 615 changed class pairs are subclass-vs-concrete-ancestor pairs and interface pairs involving abstract classes, which no code checks. `SceneManager.on_key_down_event` keeps its by-name `_record_key_press` lookup: `active_scene` is annotated `Scene`, so an isinstance check is flagged as unnecessary by basedpyright
- **Files Modified**: `glitchygames/events/base.py`, `glitchygames/scenes/scene.py` (comment only)
- **Tests**: `TestEventInterface` in `tests/events/test_events_core.py`: a real Scene subclass passes issubclass/isinstance; an unrelated class does not; a class implementing every abstract method of `KeyboardEvents` without inheriting passes; a partial implementation does not; the hook returns NotImplemented for a non-matching class. The existing hook tests now expect NotImplemented instead of False

### 55. Input Pressed During a Scene Transition Is Delivered When It Ends
- **Description**: Keys, buttons and clicks pressed during a transition (about 4 s for Clockwork Keep's elevator ride) were all delivered at once to the new scene when it ended: a jump pressed mid-ride jumped on arrival. A key held before the ride and released during it still read as held on the arrival scene's first frame, and quit or a controller disconnect during a ride waited for it to end
- **Status**: Resolved
- **Priority**: Medium (stale input acted on arrival)
- **Reporter**: Found while planning the engine world space (`plans/2026-10-18-engine-world-space.md`)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `SceneManager.start()`'s transition branch never processed events, so they queued in SDL for the whole transition
- **Solution**: Each transition frame calls the new `SceneManager._process_transition_events()`, which runs `GameEngine.process_events(discarded_event_types=TRANSITION_DISCARDED_EVENT_TYPES)`: presses and motion (`KEYDOWN`, `TEXTINPUT`, `MOUSEBUTTONDOWN`, `MOUSEMOTION`, `MOUSEWHEEL`, `JOYBUTTONDOWN`, `JOYAXISMOTION`, `JOYHATMOTION`, `JOYBALLMOTION`, `CONTROLLERBUTTONDOWN`, `CONTROLLERAXISMOTION`, `FINGERDOWN`, `FINGERMOTION`, `TEXTEDITING`, `CONTROLLERTOUCHPADDOWN`, `CONTROLLERTOUCHPADMOTION`, `MULTIGESTURE`) are dropped, except motion back to neutral, which is a release (`is_discarded_during_transition`: an axis inside ActionMap's `DEFAULT_DEADZONE`, or a hat at (0, 0)); releases (including `CONTROLLERTOUCHPADUP`), quit, window, focus, device and drop events (`DROPFILE`/`DROPTEXT`: a drop during a ride should land) go through the normal dispatch. They reach the incoming scene, which `_start_transition` has already made active (the outgoing scene is cleaned up). The golden-trace harness's copy of the transition branch (`GoldenTraceSceneManager.run_frame`) does the same. The base `Scene.on_key_up_event` quit keys (Q, ESC) now quit only on the release of a key whose key-down reached that scene: `SceneManager.on_key_down_event` calls `Scene._record_key_press` before dispatch (so overriding handlers are covered) and each release consumes its press. A Q pressed during a transition, or pressed in the departing scene and released after it was left, no longer quits (nor does an ESC held from gameplay into the pause screen)
- **Files Modified**: `glitchygames/scenes/scene.py`, `glitchygames/engine/game_engine.py`, `glitchygames/input/action_map.py`, `scripts/record_golden_traces.py`
- **Tests**: `tests/world/test_transition_input.py` (real engine and scenes through the harness): a jump pressed and released mid-ride does not jump on arrival; a key held before a transition and released during it is not held after (shared `ActionMap`); a press during a transition is never delivered; quit during a transition quits; a joystick removal during a transition reaches the joystick manager; the discard set holds no release; a stick pushed before a transition and centred during it is not held after, a stick pushed during it is discarded, a centred hat is delivered and a pushed one discarded; a file dropped during a transition reaches the arriving scene. Q pressed and released during a transition does not quit; Q pressed before it and released during it does not quit; Q pressed and released in one scene quits (`TestSceneKeyUpEvent` in `tests/scenes/test_scene.py` covers the release-without-press and one-quit-per-press cases). The golden traces did not change: the only scripted input inside a transition is Clockwork Keep's interact release at frame 354 (ride: frames 352-592), which the arrival floor's fresh `ActionMap` ignores whether it arrives during or after the ride

### 54. GameEngine.process_events Drops Events
- **Description**: Events queued in the same frame as an unhandled event were lost, scenes that take raw pygame events (`process_event`) only ever received the first event of each frame, and an event type missing from `EVENT_HANDLERS` was reported with the previous event's result
- **Status**: Resolved
- **Priority**: Medium (lost input whenever an unhandled event shared a frame with it)
- **Reporter**: Found while planning the engine world space (`plans/2026-10-18-engine-world-space.md`)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `pygame.event.get()` removes the whole batch from SDL's queue, but the loop returned `False` right after `process_unimplemented_event`, returned `True` after the first raw event, and never reset `event_was_handled` per event
- **Solution**: Every event of the batch is handled; handled/unhandled is decided per event (a type with no handler is unhandled and goes to `process_unimplemented_event`); the loop never returns early; raw-event scenes get every event in order. The return value is True only when every event was handled (False for an empty batch, as before)
- **Files Modified**: `glitchygames/engine/game_engine.py`
- **Tests**: `TestProcessEvents` in `tests/engine/test_game_engine.py`: an unhandled event followed by a key-down in one batch (both processed); a raw-event scene receives all events in order; an unmapped type after a handled event is unhandled; True only when every event was handled. The golden traces did not change (the scripts never mix an unhandled event into a batch)

### 53. Undoing a Bitmappy Frame Delete Fails
- **Description**: Deleting a frame from an animation in the film strip and then undoing the delete restored nothing: the undo failed with `AttributeError: 'PixelArray' object has no attribute 'flat'` and the frame stayed deleted. A frame known only by its surface came back black, and a restored frame lost its explicit hitbox and per-pixel alpha
- **Status**: Resolved
- **Priority**: Medium (undo of a frame delete was broken)
- **Reporter**: Found while fixing BUGS.md #51 (`plans/future-work.md`)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `FrameAddCommand._add_frame` (which `FrameDeleteCommand.undo` uses) copied pixels through `PixelArray.flat`, which pygame-ce's `PixelArray` does not have, so the undo raised, logged and returned False (the same bug as #51 in `AnimationAddCommand`). The delete capture (`FilmStripEventHandler.track_frame_deletion_for_undo`) recorded `frame.pixels`, which is empty for a frame that has only a surface, and did not record the frame's hitbox; the restore built a surface without `SRCALPHA`
- **Solution**: The delete capture reads pixels with `SpriteFrame.get_pixel_data()` and records an explicit frame hitbox as an `(x, y, width, height)` tuple (None when the frame uses the hitbox fallback). `FrameAddCommand._add_frame` builds an `SRCALPHA` surface like the editor's own frames, passes the hitbox to `SpriteFrame` and copies pixels with `SpriteFrame.set_pixel_data` (which also keeps `frame.pixels`, which saves read). A grep of the package found no other `.flat` or `PixelArray` use
- **Files Modified**: `glitchygames/bitmappy/history/commands.py`, `glitchygames/bitmappy/film_strip_events.py`
- **Tests**: `TestFilmStripFrameDeleteUndo` in `tests/tools/test_bitmappy_film_strips.py` (real `AnimatedSprite` and `FilmStripWidget`): delete the middle frame, undo (pixels, alpha, duration and hitbox back at index 1, and saved), redo deletes it again, undo again; a frame with no pixel list is restored from its surface; the editor's `handle_undo`/`handle_redo` undo and redo the delete

### 52. Bitmappy's Signal Handler Skips the AI Worker's Graceful Shutdown (and Can Lose the Signal)
- **Description**: On SIGINT/SIGTERM Bitmappy exited without the AI worker's shutdown (`AIManager.cleanup`), so the worker (a daemon `multiprocessing.Process`) was killed at exit instead of receiving its shutdown message. A terminal Ctrl-C also killed the worker directly with KeyboardInterrupt. Verifying the fix showed a worse problem: a signal arriving while the editor was writing a log line was lost and the editor kept running
- **Status**: Resolved
- **Priority**: Low (no leak or traceback observed in normal runs), but the lost signal meant `kill` sometimes needed sending twice
- **Reporter**: Found while verifying BUGS.md #47 in the binary (`plans/future-work.md`)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `editor.main`'s handler called `sys.exit(0)`; the SystemExit ends `GameEngine.start` without the scene manager's loop exit, so no scene `cleanup()` (and so no `AIManager.cleanup`) ran. The terminal sends SIGINT to the whole process group, and the spawned worker kept Python's default SIGINT handler. The handler also logged; when the signal interrupted a write to stderr, logging raised `RuntimeError: reentrant call inside <_io.BufferedWriter name='<stderr>'>`, which escaped the handler in place of SystemExit and was swallowed by the frame loop
- **Solution**: The handler now only records the signal and raises SystemExit. `main` wraps `engine.start()` in `try/finally`; the finally logs the signal and calls `shut_down_running_ai_workers()`, which runs `AIManager.cleanup` (shutdown message, join for `AI_WORKER_JOIN_TIMEOUT_SECONDS` = 2 s, terminate and then kill only if still alive, close queues) for each manager whose worker is running (a `WeakSet` filled by `AIManager.setup`). It runs after SystemExit has unwound the engine, so it cannot block on a lock the interrupted code held, and it does nothing after a normal quit (cleanup unregisters the manager and clears its process and queues, so it is safe to call twice). The worker now starts through `run_ai_worker_process`, which ignores SIGINT so Ctrl-C leaves it to exit on its shutdown message (`terminate()` still stops it)
- **Verification**: Ran `uv run bitmappy` headless (`SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`), waited for the worker, then sent SIGTERM to the editor process and, in a second run, SIGINT to the whole process group (as Ctrl-C does). Both exited in under 0.3 s with code 0, logged the shutdown message being sent and `AI process cleanup completed` without terminating the worker, printed no traceback, and left no processes
- **Files Modified**: `glitchygames/bitmappy/editor.py`, `glitchygames/bitmappy/ai_manager.py`, `glitchygames/bitmappy/ai_worker.py`
- **Tests**: `TestAiWorkerShutdown` in `tests/tools/test_bitmappy.py`: a signal while the engine runs exits 0 through `shut_down_running_ai_workers` without logging inside the handler; cleanup sends the message then joins with the timeout and does not terminate a worker that exits; terminates one that does not; started managers are shut down once; the worker process ignores SIGINT

### 51. Undoing a Bitmappy Animation Delete Fails and Loses Its Transitions and Settings
- **Description**: Deleting an animation drops the `[[transition]]` entries from or to it (BUGS.md #44), and undoing the delete did not bring them back. Fixing that showed the undo had never worked: it failed with `AttributeError: 'PixelArray' object has no attribute 'flat'` and restored nothing
- **Status**: Resolved
- **Priority**: Medium (undo of an animation delete was broken; transitions silently lost)
- **Reporter**: Found while fixing BUGS.md #44 (`plans/future-work.md`)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `_capture_animation_deletion_for_undo` saved only the frames. `AnimationAddCommand._add_animation` (which `AnimationDeleteCommand.undo` uses) copied pixels through `PixelArray.flat`, which pygame-ce's `PixelArray` does not have, so the undo raised, logged, and returned False. The delete also left the animation's loop flag, frame interval and `_animation_order` entry behind, and its redo (`AnimationAddCommand._delete_animation`) did not drop the transitions again
- **Solution**: The delete capture also records the animation's position, loop flag, frame interval and the transitions it drops with their indices (`AnimatedSprite.transitions_for_animation`); frames are captured with `get_pixel_data()`. The delete (and `AnimatedSprite.remove_animation`) now drops the settings and order entry (`forget_animation_settings`). `AnimationDeleteCommand.undo` re-adds the frames (now via `SpriteFrame.set_pixel_data`), puts the animation back in its place with its settings (`restore_animation_settings`) and the transitions back at their original positions (`restore_transitions`); its redo drops the transitions and settings again
- **Files Modified**: `glitchygames/sprites/animated.py`, `glitchygames/bitmappy/film_strip_coordinator.py`, `glitchygames/bitmappy/history/commands.py`
- **Tests**: `test_undoing_an_animation_delete_restores_its_transitions_and_settings` in `TestFilmStripAnimationTransitions` (`tests/tools/test_bitmappy_film_strips.py`, real `AnimatedSprite`: delete, undo, save, redo, undo); `test_removed_transitions_restore_to_their_original_positions` and `test_remove_animation_forgets_its_settings` in `tests/sprites/test_animated_sprite.py`

### 50. Packaged Bitmappy AI Requests Fail With "Supported providers: set()"
- **Description**: In the PyInstaller binary every AI sprite request failed with `ValueError: Invalid provider key 'anthropic'. Supported providers: set()`
- **Status**: Resolved
- **Priority**: High (AI generation unusable in the packaged app)
- **Reporter**: User, testing the binary after BUGS.md #47
- **Date Reported**: 2026-10-18
- **Root Cause**: aisuite discovers providers by globbing `aisuite/providers/*_provider.py` on disk (`ProviderFactory.get_supported_providers`) and imports them by a constructed name. PyInstaller stores modules compiled inside its archive, so the glob found no files and the dynamic import was invisible to its analysis.
- **Solution**: A project PyInstaller hook, `packaging/pyinstaller_hooks/hook-aisuite.py` (enabled via `hookspath` in `bitmappy.spec`), bundles the anthropic, openai and ollama provider modules as hidden imports and their source files as data, so both the glob and the import work. Only these providers are bundled, to keep vendor SDKs out of the binary; others fail with aisuite's clear "not supported" error.
- **Files Modified**: `packaging/pyinstaller_hooks/hook-aisuite.py` (new), `bitmappy.spec`
- **Tests**: `tests/tools/test_bitmappy_packaging.py` checks the spec uses the hook directory and that the hook bundles the default `AI_MODEL`'s provider and only real provider modules. Verified by rebuilding and listing the binary's archive (the three provider files are present); a real request in the binary still needs a manual run with an API key.

### 49. bitmappy.spec Lists a Hidden Import That No Longer Exists
- **Description**: The PyInstaller build logged `ERROR: Hidden import 'glitchygames.events.voice_portaudio' not found`
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found while verifying BUGS.md #40 with `nox -s build-binary`
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: The PortAudio voice backend moved to `glitchygames.events.voice_backends.voice_portaudio`, and the spec was not updated. The spec had also never been committed: the PyInstaller section of `.gitignore` ignores `*.spec`, so a fresh clone could not run `nox -s build-binary` at all
- **Solution**: The hidden import now names `glitchygames.events.voice_backends.voice_portaudio`. `.gitignore` makes an exception for `bitmappy.spec`, and the spec is now tracked
- **Verification**: The rebuild logs no hidden-import errors for `glitchygames` modules. Its remaining `Hidden import … not found` warnings (`pycparser.lextab`, `pycparser.yacctab`, `scipy.special._cdflib`) come from third-party PyInstaller hooks, not from the spec
- **Tests**: `test_every_spec_hidden_import_exists` (each hidden import must exist) and `test_spec_script_and_data_sources_exist` (the Analysis script and every `datas` source must exist) in `tests/tools/test_bitmappy_packaging.py`
- **Files**: `bitmappy.spec`, `.gitignore`

### 48. Packaged Bitmappy Is Missing `pygame._sdl2.audio`
- **Description**: A background process in the PyInstaller build crashed with `ModuleNotFoundError: No module named 'pygame._sdl2.audio'`
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while verifying BUGS.md #40 with `nox -s build-binary`
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: The module was not missing: both builds contain `pygame/_sdl2/audio.cpython-314-darwin.so` (checked with `pyi-archive_viewer --list`), and the main process imported it. The crashing process was one of the children that, without `freeze_support()` (#47), re-ran the whole entry point and imported Bitmappy. It crashed while the parent was being stopped, most likely because the one-file build's extracted files were already being removed
- **Solution**: Fixed by #47 (children no longer import Bitmappy). `pygame._sdl2.audio` is now also listed in `bitmappy.spec`'s `hiddenimports`, so the binary cannot lose it if PyInstaller's analysis changes
- **Verification**: Rebuilt binary ran headless and was stopped with SIGTERM and with SIGINT; neither run printed a `ModuleNotFoundError` or traceback
- **Tests**: `test_spec_lists_the_audio_module_pygame_sdl2_imports` in `tests/tools/test_bitmappy_packaging.py`
- **Files**: `bitmappy.spec`

### 47. Packaged Bitmappy Re-Launches Itself for Background Processes (No freeze_support)
- **Description**: In the PyInstaller build (`dist/bitmappy`), background processes (the AI worker and multiprocessing's resource tracker) started the bundled app again with multiprocessing's own arguments (`--multiprocessing-fork …`, `-B -S -I -c …`), which the app's argument parser rejected, so those processes failed
- **Status**: Resolved
- **Priority**: High for the packaged build; no effect when running from source
- **Reporter**: Found while verifying BUGS.md #40 with `nox -s build-binary` (2026-10-18)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: Bitmappy uses the `spawn` start method (`editor.main` calls `multiprocessing.set_start_method('spawn', force=True)`; `AIManager.setup` starts the worker with `multiprocessing.Process`), and a frozen app spawns children by re-running its own executable. No `multiprocessing.freeze_support()` call existed, so each child ran the app's entry point instead of its task
- **Solution**: `scripts/bitmappy_entry.py` (the script `bitmappy.spec` builds) calls `multiprocessing.freeze_support()` first, and imports and starts Bitmappy only afterwards, so a child never imports Bitmappy or reaches its argument parser
- **Verification**: Rebuilt with `nox -s build-binary` and ran `dist/bitmappy` headless (`SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`). While it ran, the resource tracker (`-B -S -I -c …`) and the AI worker (`--multiprocessing-fork …`) were alive as child processes. The worker initialized its AI client (it logged `game.ai - WARNING - Client does not have _providers attribute`). After SIGINT, every process had exited within 5 s. There were no argparse usage errors, tracebacks or `ModuleNotFoundError`. A real AI request was not tried (it needs an API key or network access)
- **Tests**: `test_entry_point_calls_freeze_support_before_starting_bitmappy` in `tests/tools/test_bitmappy_packaging.py`
- **Files**: `scripts/bitmappy_entry.py`

### 46. scripts/legacy_sprite_loader.py Cannot Start
- **Description**: The script raised `TypeError: Sprite.__init__() missing 'x' and 'y'` while building its scene
- **Status**: Resolved (script deleted)
- **Priority**: Low
- **Reporter**: Found by the re-review of `feature/debug-overlay`
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `Sprite.__init__` gained required `x` and `y` arguments in 4bdc966 (Refactor/bitmappy editor, #87); the script still called it with only `width` and `height`. Beyond that, the script was obsolete: since it was added (f20bca6) its history is only lint clean-ups; nothing references it (docs, noxfile, tests, other scripts); its `inflate` draws each pixel as a zero-size rect, which pygame-ce draws as nothing, so even a fixed call would show a solid green square whatever the file held; it wrote the loaded sprite back as an INI `.cfg` file, a format the engine no longer loads (TOML only); and its input (headerless 32×32, one VGA palette index per byte) matches none of the Galimore formats surveyed in `docs/galimore.md` (RGB565 `.bg/.fg/.get/.spr`, 24-bit `.raw`), which Galimore import (sub-plan E) will convert to TOML instead
- **Solution**: Deleted `scripts/legacy_sprite_loader.py` rather than fixing a script that cannot do its job. `scripts/sprite_loader.py` covers loading sprites (TOML). `scripts/raw_sprite_loader.py` is kept because tests use its `BitmappyLegacySprite.deflate`, though it has the same broken `Sprite` call and zero-size-rect `inflate` (noted in `plans/future-work.md`)
- **Files Modified**: `scripts/legacy_sprite_loader.py` (deleted)
- **Tests**: None (nothing to test; `uv run python -c "import pygame; ..."` confirmed a zero-size `pygame.draw.rect` leaves the surface unchanged)

### 45. Renaming an Animation in Bitmappy Drops Its Timing and Loop Flag
- **Description**: `_rename_animation_in_sprite` moved the animation's frames but not its loop flag or frame interval, so a renamed one-shot animation stopped honouring `loop = false` at runtime and saved as `loop = true` with the most common frame duration as its interval
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the re-review of `feature/debug-overlay`
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: The coordinator renamed the sprite's per-animation data by hand (frames, `_animation_order`, and since #44 the transitions) and missed `_loop_flags` and `_animation_frame_intervals`. It also moved the frames to the end of `_animations` (the save order), left the sprite's `frame_manager.current_animation` on the old name when the renamed animation was the current one, and overwrote an existing animation when renamed onto its name. Renames had no undo command at all
- **Solution**: New `AnimatedSprite.rename_animation(old_name=, new_name=)` moves everything stored under the name: frames (in place), `_animation_order`, loop flag, frame interval, transitions, cached surfaces for either name, and the current animation (keeping the current frame); it raises `ValueError` for a missing name or one already in use. `_rename_animation_in_sprite` calls it; `on_animation_rename` refuses (with a warning) a rename onto an existing animation and records an `AnimationRenameCommand` (`FilmStripOperationTracker.add_animation_renamed`, `OperationType.FILM_STRIP_ANIMATION_RENAME`), whose undo renames back through `on_animation_rename` and so restores the old name with its data, and whose redo renames again. The live `AnimationStateMachine` (built at load) is not renamed; Bitmappy does not run it, and saves use `transition_data`
- **Files Modified**: `glitchygames/sprites/animated.py`, `glitchygames/bitmappy/film_strip_coordinator.py`, `glitchygames/bitmappy/history/commands.py`, `glitchygames/bitmappy/history/operations.py`, `glitchygames/bitmappy/history/undo_redo.py`, `glitchygames/bitmappy/history/__init__.py`
- **Tests**: `test_renaming_an_animation_moves_its_loop_flag_and_frame_interval` (flag and interval follow, the one-shot animation stops on its last frame, the save writes them under the new name), `test_renaming_the_current_animation_keeps_it_current`, `test_renaming_onto_an_existing_animation_is_refused` and `test_undoing_an_animation_rename_restores_the_old_name_and_its_data` in `TestFilmStripAnimationTransitions` (`tests/tools/test_bitmappy_film_strips.py`, real `AnimatedSprite`); `test_rename_animation_moves_transitions_and_keeps_the_order` and `test_rename_animation_rejects_a_missing_or_existing_name` in `tests/sprites/test_animated_sprite.py`

### 44. TOML Save Drops Animation State Machine Transitions
- **Description**: The TOML writers never wrote `[[transition]]` sections, so loading and saving a sprite lost its animation state machine (cobra: 2 transitions → 0; Papyrus player: 6 → 0). Saving a sprite in Bitmappy silently broke the game's animation logic
- **Status**: Resolved
- **Priority**: High (silent data loss in game assets)
- **Reporter**: Found by the re-review of `feature/debug-overlay`
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `_load_toml` handed the `[[transition]]` tables straight to `AnimationStateMachine.load_from_toml` (which keeps only parsed `Transition` objects) and kept no copy, so neither `_save_toml` nor `_save_toml_single_frame` had anything to write. Bitmappy's derived sprites (viewport save, single-frame canvas save) had nothing to copy either
- **Solution**: The loader keeps each table verbatim, in file order, in `AnimatedSprite.transition_data`; both writers append them as `[[transition]]` sections with the same keys, values and order (`_write_toml_transitions`). Strings are escaped as TOML basic strings (`toml_basic_string`: backslash, quote and control characters; also `toml_key` and `toml_scalar`), so `when` expressions with quotes or backslashes round-trip. Transitions that games add in code (the Papyrus player's compound falling transitions) are not part of the data and are not written. Bitmappy's viewport and single-frame canvas saves copy the transitions (`copy_transitions_from`); renaming an animation renames it in its transitions (`rename_animation_in_transitions`, called by `FilmStripCoordinator._rename_animation_in_sprite`); deleting one drops the transitions from or to it with a logged warning (`remove_transitions_for_animation`, called by `_delete_animation` and `AnimatedSprite.remove_animation`). Undoing a Bitmappy animation delete now restores the dropped transitions (BUGS.md #51)
- **Tests**: `test_bundled_transitions_survive_a_save_round_trip` (every bundled sprite) and `test_state_machine_transitions_reload_in_order` (Papyrus player, cobra) in `tests/examples/test_examples_sprites.py`; `TestTransitionData` in `tests/sprites/test_animated_sprite.py`; `test_viewport_save_keeps_transitions` and `test_static_save_keeps_transitions` in `tests/tools/test_canvas_panning.py`; `TestFilmStripAnimationTransitions` in `tests/tools/test_bitmappy_film_strips.py`
- **Files**: `glitchygames/sprites/animated.py`, `glitchygames/bitmappy/animated_canvas.py`, `glitchygames/bitmappy/film_strip_coordinator.py`

### 43. Bitmappy Single-Frame Save Drops the Sprite Name, Frame Anchor and Sprite Hitbox
- **Description**: Bitmappy's normal save of a single-frame sprite (`on_save_file_event` → `_save_as_static_sprite`) built a new `AnimatedSprite` and copied only `description`, so the saved file's `name` became `"animated_sprite"` (battle_axe: `bttlaxe.get` → `animated_sprite`) and `frame_anchor` and a sprite-level hitbox not stored on the frame were lost
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the re-review of `feature/debug-overlay`
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `AnimatedCanvasSprite._save_as_static_sprite` copied sprite-level fields one at a time and only `description` (and, since #44, the transitions) was ever added; the new sprite also lacked the loaded color glyphs, so a save could pick different characters
- **Solution**: New `AnimatedSprite.copy_sprite_metadata_from` copies every sprite-level field the writers save (name, description, frame_anchor, the default hitbox, transitions) plus the loaded color glyphs and their order; `_save_as_static_sprite` uses it
- **Tests**: `test_static_save_keeps_the_sprite_name` (battle_axe: name and pixel glyphs) and `test_static_save_keeps_frame_anchor_and_sprite_hitbox` in `tests/tools/test_canvas_panning.py`
- **Files**: `glitchygames/sprites/animated.py`, `glitchygames/bitmappy/animated_canvas.py`

### 42. TOML Writers Don't Escape Sprite Names and Descriptions
- **Description**: Both TOML writers wrote `name = "{name}"` and `description = """{description}"""` without escaping, so a description containing `"""` or a name containing `"` or a backslash produced an invalid TOML file that could not be loaded again
- **Status**: Resolved
- **Priority**: Medium (AI-generated descriptions in Bitmappy can contain quotes)
- **Reporter**: Found while fixing the single-frame writer (BUGS.md #39)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: The values were interpolated into f-strings verbatim in `_save_toml_single_frame` and `_write_toml_sprite_section`
- **Solution**: Names are written with `toml_basic_string` (the escaping added for BUGS.md #44) and descriptions with `toml_multiline_basic_string`, which keeps real line breaks but escapes backslashes, quotes, other control characters and a leading newline (which TOML would otherwise drop)
- **Tests**: `test_names_and_descriptions_needing_escapes_round_trip` (both writers) in `tests/examples/test_examples_sprites.py`
- **Files**: `glitchygames/sprites/animated.py`

### 41. Input Confirmation Dialog Sends Key-Down Events to the Key-Up Handler
- **Description**: `InputConfirmationDialogScene.on_key_down_event` passed unhandled key-down events to `super().on_key_up_event(event)` instead of `super().on_key_down_event(event)`
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the final whole-branch review of `feature/debug-overlay`
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: A copy-paste slip in `glitchygames/ui/dialogs.py` (identical on main): the inactive-input branch of `on_key_down_event` called the base key-up handler, so base key-down handling never ran for the dialog (and its subclasses: New Canvas, Load, Save) and key-up handling ran twice per key press. No other key-down/key-up mix-up exists in `dialogs.py` (the delete-animation and delete-frame dialogs route correctly)
- **Solution**: The branch now calls `super().on_key_down_event(event)`
- **Files Modified**: `glitchygames/ui/dialogs.py`
- **Tests**: `test_input_confirmation_dialog_key_down_inactive_input` in `tests/ui/test_dialogs.py` checks an unhandled key-down reaches `Scene.on_key_down_event` and not `Scene.on_key_up_event`

### 40. Built-In Font Fallback Points at a Missing Path
- **Description**: When no system font can be loaded (PyInstaller-packaged games), `FontManager` fell back to the bundled Vera.ttf via `Path(__file__).parent / 'fonts' / 'bitstream_vera' / 'Vera.ttf'`, which resolves to `glitchygames/fonts/fonts/bitstream_vera/Vera.ttf` (does not exist), so the fallback raised `FileNotFoundError` instead of loading the font
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while choosing the debug overlay's font
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-18
- **Root Cause**: `font_manager.py` already lives in `glitchygames/fonts/`, so the extra `'fonts'` path segment pointed one directory too deep. The existing fallback test mocked `pygame.freetype.Font`, so the bad path was never opened
- **Solution**: The fallback uses `Path(__file__).parent / 'bitstream_vera' / 'Vera.ttf'`, the path `bitmappy.spec`'s comment documents and bundles. No other copy of the wrong path exists (`glitchygames/debug/overlay.py`'s `DEBUG_FONT_PATH` was already correct)
- **Tests**: `TestFontManagerBuiltInFallback` in `tests/fonts/test_font_manager.py` (with `SysFont` raising `TypeError` or `FileNotFoundError`, a real freetype font is loaded from a file that exists)
- **Files**: `glitchygames/fonts/font_manager.py`

### 39. Single-Frame TOML Save Drops the Description
- **Description**: Saving a single-frame (static) sprite lost its `[sprite] description`
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found while fixing BUGS.md #36
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `_save_toml_single_frame` writes its own `[sprite]` table (it needs `pixels` inside it) and wrote only `name`, `frame_anchor`, `pixels` and the hitbox, while the animated writer (`_write_toml_sprite_section`) also writes `description`. These are the only `[sprite]` keys the loader reads
- **Solution**: The single-frame writer writes `description` in the same format as the animated writer
- **Tests**: `test_static_sprite_metadata_survives_a_save_round_trip` and `test_bundled_sprite_metadata_survives_a_save_round_trip` (name, description, frame_anchor and effective hitbox for every bundled sprite) in `tests/examples/test_examples_sprites.py`
- **Files**: `glitchygames/sprites/animated.py`

### 38. Only One Loop Flag Per Sprite Honoured at Runtime
- **Description**: An AnimatedSprite with a looping and a non-looping animation (cobra: idle loops, strike does not; Papyrus player: jumping/falling do not) used a single `is_looping` for all of them: after loading it was the last animation's `loop`, whichever animation played
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while fixing BUGS.md #34
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `_process_toml_animation` assigned each animation's `loop` to the one sprite-wide `_is_looping`, so the last one won, and `set_animation` never changed it. Only `AnimationStateMachine` applied per-animation flags (from `_loop_flags`), so sprites without a state machine, and direct `play()`/`set_animation()` calls, ignored them. `get_animation_metadata`/`set_animation_metadata` likewise read and wrote the sprite-wide flag whatever animation was named
- **Solution**: `_loop_flags` (filled at load, reset on each load) is the single per-animation store, also used by save (it replaces `_animation_loops` from #34). `set_animation` and the initial animation apply the animation's own flag through `_apply_animation_loop_flag`; setting `is_looping` still overrides it until the next animation is set, and animations without a loaded flag leave `is_looping` unchanged. The metadata methods read and write that animation's flag
- **Tests**: `TestPerAnimationLoop` in `tests/sprites/test_animated_sprite.py`
- **Files**: `glitchygames/sprites/animated.py`

### 37. PaddleSlap Ball-Ball Collisions Leave Stalled, Vertical or Flat Balls
- **Description**: After ball-ball collisions PaddleSlap balls could end up nearly stopped (e.g. (13, 1) px/s), nearly vertical (e.g. (14, 218) px/s, bouncing between the top and bottom walls for 1000+ frames without reaching a paddle in a headless paddle-AI run), or flat (vy = 0, sliding along a wall)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: Not an error in the physics: `_apply_elastic_collision` is an exact equal-mass elastic exchange (the recorded (96, 136) + (-160, 43) -> (-78, -38) + (14, 218) collision conserves momentum and kinetic energy to rounding, with the contact normal from the balls' centres). Exact physics legitimately produces these outcomes: a head-on hit on a slower ball hands over nearly all its speed, and the exchange can leave any heading. PaddleSlap had no rule keeping a ball playable after a ball-ball collision, unlike its serves, which `ServeSettings` keeps between 15 and 60 degrees from horizontal
- **Solution**: A deliberate game-design rule (kept by user decision): it is not momentum-conserving, and it exists to prevent stalled, vertical and flat balls. The physics step is unchanged (the 2328-case collision sweeps still check swapped velocities, a mover that stops dead and conserved momentum and energy). `Game.update()` then runs `_keep_collided_balls_playable()`: each ball that collided this frame gets its velocity's angle from horizontal moved into its own `ServeSettings` band (keeping each component's sign; a zero component points away from the partner) and its speed raised to at least its serve speed (`_keep_ball_playable`). The rule conserves each ball's speed when it only turns it, adds energy only when it raises a slow ball's speed, and does not conserve momentum; balls already serve-like are untouched. A 3000-frame paddle-AI harness run had no stalled, vertical or flat balls afterwards (the same check found 1052 samples before)
- **Tests**: `TestBallPairPlayability` in `tests/collision/test_ball_paddle_collision.py`; `test_update_keeps_collided_balls_playable_after_ball_collisions` in `tests/examples/test_paddleslap.py`; the existing sweeps in `tests/game_objects/test_ball_collision_physics.py`
- **Files**: `glitchygames/examples/paddleslap.py`

### 36. Saving a Static Sprite With an RGBA Color Blanks Its Pixels
- **Description**: `toadstool.toml` came back from load -> save -> reload as a blank 16x18 grid: every pixel was written as `.`
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: The file is valid; the static (single-frame) writer was wrong. toadstool declares one color with an `alpha` field (the unused magenta `"█" = { ..., alpha = 255 }`), so the loader gives the frame RGBA pixel tuples such as `(0, 0, 0, 255)`. `_build_toml_color_map` keys opaque colors as RGB (`(0, 0, 0)`) when no pixel has partial alpha, and `_save_toml_single_frame` looked pixels up by exact tuple equality, found nothing and silently wrote its default character `.` (which toadstool maps to black). The animated writer was unaffected because it uses `lookup_pixel_char`, which matches RGBA pixels against RGB keys
- **Solution**: `_save_toml_single_frame` converts pixels with the same `_convert_pixels_to_toml_chars` as animated saves (which raises `KeyError` for a color missing from the map instead of writing a default character). Note: colors that no pixel uses are not written back, so toadstool's reloaded pixels are RGB tuples rather than RGBA; the colors are identical
- **Tests**: `test_bundled_sprite_pixels_survive_a_save_round_trip` (every bundled sprite TOML, static and animated, compared as RGBA) in `tests/examples/test_examples_sprites.py`
- **Files**: `glitchygames/sprites/animated.py`

### 35. TOML Save Turns the Visible-Pixel Fallback Into Explicit Hitboxes
- **Description**: Saving a sprite without hitboxes wrote a `[sprite.hitbox]` (the union of all frames' visible bounds) and an `[animation.frame.hitbox]` for every frame, so a load -> save added hitboxes the author never defined (colors, glimmer, scarab, gold_scarab) and froze them: later edits to the art no longer changed the collision shape, and the sprite-level default no longer reached frames
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `_build_toml_data_structure` fell back to `_auto_compute_envelope_hitbox()` when `default_hitbox` was None, and `_create_toml_frame_data` fell back to `compute_bounding_box_from_pixels()` when a frame had no explicit hitbox. Both date from before the visible-pixel default existed, when a written hitbox was the only way to get a tight one
- **Solution**: Save writes `[sprite.hitbox]` only when `default_hitbox` is set (loaded or set in code/Bitmappy) and a per-frame hitbox only when `SpriteFrame.has_explicit_hitbox`; `_auto_compute_envelope_hitbox` was removed. Nothing in Bitmappy or the tests relied on the synthesised sections (Bitmappy only carries explicit hitboxes, in its viewport save). Note: a magenta-keyed (non-alpha) `AnimatedSprite` saved without a hitbox now collides as its full frame, like one loaded without a hitbox (see the CLAUDE.md caveat)
- **Tests**: `test_bundled_hitboxes_survive_a_save_round_trip_unchanged` (every bundled sprite, with and without hitboxes) in `tests/examples/test_examples_sprites.py`
- **Files**: `glitchygames/sprites/animated.py`

### 34. TOML Save Loses Animation Timings and Loop Settings
- **Description**: Loading an animated sprite and saving it (as Bitmappy does) wrote `frame_interval = 0.5` and `loop = true` for every animation and dropped per-frame `frame_interval` overrides, so every bundled animation (cobra, gold_scarab, the Papyrus player, scarab, scorpion, colors, slime-jump, ghosty) came back at 0.5 s per frame and the cobra's strike and the player's jump/fall animations started looping
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `AnimatedSprite._build_toml_data_structure` hard-coded `'frame_interval': 0.5` and `'loop': True` in every `[[animation]]` entry, and `_write_toml_animations` never wrote a per-frame `frame_interval`. The loader kept the timing only as each `SpriteFrame.duration` (and the last animation's loop in `_is_looping`)
- **Solution**: The loader records each animation's `frame_interval` and `loop` (`_animation_frame_intervals`, `_animation_loops`). Save writes them back (`_build_toml_animation_entry`); animations without a loaded value (built in code or Bitmappy) use their most common frame duration. A frame gets a per-frame `frame_interval` only when its duration differs from its animation's, so the file's structure is reproduced. Bitmappy's viewport save copies the settings with `AnimatedSprite.copy_animation_timing_from`; the full save already saves the loaded sprite
- **Tests**: `test_bundled_animation_timings_survive_a_save_round_trip` (parametrized over every bundled animated sprite) in `tests/examples/test_examples_sprites.py`; `test_viewport_save_keeps_animation_timing` in `tests/tools/test_canvas_panning.py`
- **Files**: `glitchygames/sprites/animated.py`, `glitchygames/bitmappy/animated_canvas.py`
- **Note (2026-10-18)**: Bitmappy's panned-viewport save (`save_animated_sprite` / `_save_viewport_sprite`), mentioned in the entries above, was unreachable from the editor and was later removed; planned item D11 (`plans/2026-10-18-level-tools-d-bitmappy-updates.md`) replaces its purpose.

### 33. PaddleSlap Balls Collided as Their 20x20 Image; Half-Pixel Collision Rects 1 px Off
- **Description**: PaddleSlap balls bounced off paddles and walls, and were killed off-screen, by their full 20x20 image instead of the radius-5 circle players see (turning around 5 px before a wall, killed 5 px late). A ball at x = 10.5 was drawn at 11 but collided at 10
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: (1) Collision rects were the sprite's whole image rect, transparent margin included, and `BallSprite.dt_tick` found paddles by scanning its groups with an image-rect test. (2) `get_collision_rect` placed rects at `round(world_x)` (Python's round-half-even: 10.5 -> 10) while the ball draws at its `pixel_snap_mode` (NEAREST_HALF_UP: 10.5 -> 11)
- **Solution**: Hitboxes default to the image's visible pixels (`glitchygames/collision/bounds.py`; `TRIM_TRANSPARENT_HITBOX = False` opts out) and collision rects start at the sprite's own snapped position (`glitchygames/pixel_snap.py`). PaddleSlap pairs balls with paddles through `CollisionManager.check_overlap('balls', 'paddles')`, and `BallSprite.handle_paddle_collision` does an exact circle-vs-rect check, placing the visible edge flush on the face the ball came in through. Wall bounces, overshoot mirroring, the off-screen kill and the serve margin use the visible rect (`BallSprite._visible_rect`)
- **Tests**: `tests/collision/test_ball_paddle_collision.py`; `tests/collision/test_ball_visible_walls.py`; `TestOpaqueBounds`, `TestVisiblePixelCollisionRect` and `test_snap_mode_sprite_rounds_half_up` in `tests/collision/test_collision.py`; `tests/examples/test_paddleslap.py`
- **Files**: `glitchygames/collision/bounds.py`, `glitchygames/collision/detection.py`, `glitchygames/collision/layers.py`, `glitchygames/pixel_snap.py`, `glitchygames/game_objects/ball.py`, `glitchygames/examples/paddleslap.py`

### 32. Gold Scarab Frame Drawn With a Notch
- **Description**: The gold scarab's third frame had a notch in its right edge
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: Frame 2, row 2 of `gold_scarab.toml` was 9 characters wide instead of 10; the loader pads short rows with their last (transparent) character
- **Solution**: Restored the missing pixel; a test checks that every bundled sprite's rows are equal width
- **Tests**: `test_bundled_sprite_rows_have_equal_lengths` in `tests/examples/test_examples_sprites.py`
- **Files**: `glitchygames/examples/brave_adventurer_papyrus/sprites/gold_scarab.toml`

### 31. Two Simultaneous Enemy Contacts Cost Two Lives
- **Description**: In Brave Adventurer and Papyrus, touching two enemies in the same frame lost two lives and respawned twice
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: The collision manager calls the player-enemy callback once per overlapping pair, and each call ran `_player_die`
- **Solution**: The enemy callback kills the player at most once per collision pass and never while the player is respawning
- **Tests**: `TestOneDeathPerHit` in `tests/examples/test_brave_adventurer_game.py`
- **Files**: `glitchygames/examples/brave_adventurer/game.py`, `glitchygames/examples/brave_adventurer_papyrus/game.py`

### 30. Ledge Land/Fall Oscillation; Feet Off the Ground
- **Description**: A player standing at a ledge or wall-top edge landed, fell and landed again forever (20 landings in 40 frames). Brave Adventurer's figure floated 1 px above the ground; Papyrus feet sank into or floated above the ground as the animation changed frames; players stopped short of walls (Papyrus about 12 px) and of the world's left edge, and a dt hitch could push a fast player through a wall
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: (1) Ground support used the current frame's hitbox, and falling frames and poses are wider than idle ones (Papyrus idle 6..28 vs falling 0..40), so an idle player off an edge fell, was caught by the wider falling hitbox and landed again. (2) Terrain used the drawn image size (Brave's feet end 1 px above its 48 px image; `PAPYRUS_PLAYER_WIDTH` was the full 40 px drawn width while the hitbox is 22 px at offset 6; the world-edge constraint stopped the image, not the hitbox). (3) Papyrus frames are top-aligned with visible bottoms from 24 to 27 rows, so a fixed foot line could not match every frame. (4) Walls pushed out on the side of the hitbox centre, which a long frame can carry past the wall's centre
- **Solution**: Support uses a stable x-span shared by every frame and pose (`AnimatedSprite.common_hitbox_x_range()`, Brave's per-facing pose intersection, `_player_support_span`). Terrain, walls, world edges, scarab ground and Clockwork Keep platforms work from `get_sprite_collision_rect` and `collision_rect_offset`. Opt-in `AnimatedSprite.frame_anchor` (`FrameAnchor`) moves each frame so its hitbox bottom lands on the reference hitbox's; the Papyrus player uses BOTTOM on the 27-row foot line. Walls push out on the side the hitbox was on before this frame's move (`_entered_wall_from_left`)
- **Tests**: `TestTerrainUsesHitbox`, `TestHitboxLooseEnds`, `TestStableSupportAtEdges`, `TestPapyrusFeetAnchoring` and `test_fast_player_*` in `tests/examples/test_brave_adventurer_game.py`; `TestPlatformSupportUsesHitbox` in `tests/examples/test_clockwork_keep.py`; `TestAnimatedSpriteFrameAnchor` and `test_common_hitbox_x_range_is_the_intersection_of_all_frames` in `tests/sprites/test_animated_sprite.py`
- **Files**: `glitchygames/sprites/animated.py`, `glitchygames/collision/layers.py`, `glitchygames/examples/brave_adventurer/game.py`, `glitchygames/examples/brave_adventurer/player.py`, `glitchygames/examples/brave_adventurer_papyrus/game.py`, `glitchygames/examples/brave_adventurer_papyrus/player.py`, `glitchygames/examples/brave_adventurer_papyrus/constants.py`, `glitchygames/examples/clockwork_keep/game.py`, `glitchygames/debug/panels.py`

### 29. Papyrus Hitboxes Not Scaled 2x Nor Mirrored When Facing Left
- **Description**: Papyrus player and enemy hitboxes covered only the top-left quarter of the drawn sprite, and facing left they kept the unflipped offset (an 8 px gap walking left into a wall, and wrong world-edge, ledge and enemy contact)
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: TOML hitboxes are in native pixels, but Papyrus draws every sprite at `SPRITE_SCALE = 2` and flips the image when facing left; `AnimatedSprite.hitbox` applied neither
- **Solution**: `AnimatedSprite.hitbox_scale` multiplies explicit, default and trimmed hitboxes (set by `prepare_papyrus_sprite` right after loading, so hitboxes are scaled before the first tick), and `AnimatedSprite.hitbox_flip_x` mirrors them within the drawn frame width; Papyrus sets it wherever it flips the image
- **Tests**: `TestPapyrusHitboxScale` and `test_freshly_constructed_sprites_have_scaled_hitboxes_before_any_tick` in `tests/collision/test_collision.py`; `TestPapyrusFacingLeftHitbox` in `tests/examples/test_brave_adventurer_game.py`; `test_hitbox_scale_*` and `test_hitbox_flip_x_*` in `tests/sprites/test_animated_sprite.py`
- **Files**: `glitchygames/sprites/animated.py`, `glitchygames/examples/brave_adventurer_papyrus/sprite_utils.py`, `glitchygames/examples/brave_adventurer_papyrus/player.py`, `glitchygames/examples/brave_adventurer_papyrus/enemies.py`, `glitchygames/examples/brave_adventurer_papyrus/constants.py`

### 28. Resume Paused Again Immediately; Pause Screenshot One Frame Behind
- **Description**: Clockwork Keep and Brave Adventurer paused again one frame after resuming. PaddleSlap's pause screenshot showed the previous frame while the game state was one frame ahead (the ball sat off its hitbox and jumped a frame on resume)
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-18
- **Root Cause**: (1) Games that paused by setting `next_scene` never cleared it, so after resuming, the loop's end-of-frame check switched to the old pause scene again. (2) `Scene.pause()` switched mid-frame, during event processing, after sprites had already moved but before they were rendered. The first fix for (1) reset `next_scene` on the scene becoming active, which wiped the `next_scene` that bootstrap scenes (`joystick_demo`, `scripts/cached_fonts.py`) set in `__init__`, so they never left their first scene
- **Solution**: `Scene.pause()` requests the switch via `next_scene`, which the loop performs after rendering. `SceneManager.switch_to_scene` clears the outgoing scene's pending switch (`outgoing.next_scene = outgoing`) and leaves the incoming scene's alone (`_clear_outgoing_scene_pending_switch`, also called by `_start_transition`, so a scene left through a transition cannot bounce back to a stale `next_scene` when it is returned to); the end-of-frame check is `SceneManager._switch_to_requested_scene`
- **Tests**: `test_pause_requests_a_pause_scene_after_this_frame`, `test_bootstrap_scene_reaches_the_scene_its_init_requests` and `test_resumed_scene_does_not_switch_back_to_the_old_pause_scene`, `test_scene_left_through_a_transition_does_not_switch_back_on_return` and `test_bootstrap_scene_reached_through_a_transition_still_hands_over` in `tests/scenes/test_scene.py`; `tests/scenes/builtin_scenes/test_pause_screen.py`
- **Files**: `glitchygames/scenes/scene.py`

### 27. Live Voice Clicks at Chunk Boundaries
- **Description**: A steady "click click click" was audible at the 100 ms live-voice chunk boundaries during the Clockwork Keep elevator ascent (the cut at arrival is accepted)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: User
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-17
- **Root Cause**: The synthesized samples are clean (an SDL disk-driver capture of the motor, 3.9 s, had no gaps, no discontinuities and a smooth onset). pygame-ce's mixer imports `PyGILState_Ensure`, `Mix_ChannelFinished` and `Mix_PlayChannelTimed`: its channel-finished callback takes the GIL to start the queued Sound. While the main thread holds the GIL (Python's default switch interval is 5 ms) the next chunk starts late, leaving a short silence, heard as a click at every boundary. The mixer buffer is 512 samples at 44100 Hz = 11.6 ms. The first probe missed this because it slept between frames (GIL free) and the disk driver is not real-time
- **Measurements**: 2 ms-period thread under game-like load (6 ms of Python work per frame at 60.5 FPS, FastTimer coarse sleep and pure-Python spin). Before: default 5 ms interval, pure spin: median 0.51 ms, p99 6.44 ms, max 6.81 ms; spin yielding with `time.sleep(0)`: p99 6.09 ms, max 6.46 ms. After: 0.5 ms interval and yielding spin: p99 1.16 ms, max 1.18 ms (on a quiet machine; on a heavily loaded one OS scheduling noise dominates the maximum, so the probe's risk check uses the p99 wait against half the mixer buffer: about 2 ms with the fix vs about 6.4 ms with the old interval; see `scripts/audio_glitch_probe.py`)
- **Solution**: (1) `GIL_SWITCH_INTERVAL_SECONDS = 0.0005` in `glitchygames/timing.py`; `GameEngine` calls `sys.setswitchinterval()` with it before `pygame.init()`. (2) `FastTimer.sleep_until_next`'s final spin calls `time.sleep(0)` each iteration so audio callbacks can take the GIL mid-spin. (3) New `glitchygames/audio/diagnostics.py` (gap, discontinuity and edge analysis; `measure_lock_wait`; `dropout_risk`) and `scripts/audio_glitch_probe.py` (`--mode dsp|realtime|both`), which records and measures under game-like main-thread load
- **Tests**: `TestGilSwitchInterval` in `tests/engine/test_engine_initialization.py`; `test_final_spin_yields_the_gil_each_iteration` in `tests/timing/test_timing.py`; `tests/audio/test_diagnostics.py`
- **Files**: `glitchygames/timing.py`, `glitchygames/engine/game_engine.py`, `glitchygames/audio/diagnostics.py`, `scripts/audio_glitch_probe.py`, `CLAUDE.md`

### 26. Paced Frames Measured in Whole Milliseconds; Fractional Target FPS Truncated
- **Description**: In Clockwork Keep (target 60, default pygame timer) the target-relative FPS histogram showed 68.5% of frames in "90-99% (54-59)" and 31.5% in ">=100%", although the game ran at a steady 60 FPS
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: User
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-17
- **Root Cause**: (1) With the `pygame` timer backend, `PygameTimer.ns_now()` is `pygame.time.get_ticks() * 1_000_000` (whole milliseconds), and `SceneManager._handle_frame_pacing` overwrote `self.dt` from those timestamps. A 16.67 ms cadence was measured as 17, 17, 16 ms (58.8, 58.8, 62.5 FPS, the reported 2:1 split), and `_track_performance` records `1 / self.dt`, so paced frames were quantized again (the uncapped path was fixed in #25, this path was not). (2) `SceneManager.start` called `timer.start_frame(int(self.target_fps))`, truncating fractional targets (60.5 became 60), and both timers computed `1_000_000_000 // target_fps`
- **Solution**: (1) Paced `dt` is measured with `time.perf_counter()` from a frame start recorded in the main loop; deadlines still use the timer's own clock. (2) The `int(...)` truncation was removed; `start_frame(target_fps: float)` in both timers returns `round(1_000_000_000 / target_fps)` (0 when not positive), and `target_fps` attributes are annotated `float`. For integer targets the period is now rounded rather than floored (60 FPS: 16_666_667 ns instead of 16_666_666). (3) `--timer-backend` now defaults to `fast` (`pygame` remains a choice); CLAUDE.md updated
- **Tests**: `TestHandleFramePacing` in `tests/scenes/test_scene.py`; `test_scene_manager_passes_fractional_target_fps_to_timer` in `tests/scenes/test_scene_timer_pacing.py`; `TestFractionalTargetFps` in `tests/timing/test_timing.py`; `test_timer_backend_*` in `tests/engine/test_timer_args.py`
- **Files**: `glitchygames/scenes/scene.py`, `glitchygames/timing.py`, `glitchygames/engine/game_engine.py`, `CLAUDE.md`

### 25. FPS Statistics Sampled pygame's 10-Frame Counter
- **Description**: Per-frame FPS statistics held repeated, quantized and stale values. A PauseScene run had 10 frames, 9 at 243.9 (10000/41) and 1 stale 526.3, so the median equalled the minimum. The report also said `dropped top/bottom 5.0%` when no frames were dropped (fewer than 20 frames at 5% drops none)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: User
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-17
- **Root Cause**: With unlimited FPS, `SceneManager._track_performance` recorded `clock.get_fps()` every frame. pygame-ce's `Clock.get_fps()` (1) recomputes only every 10 `tick()` calls, so each value repeats for 10 frames, (2) is `10000 / (milliseconds for the last 10 ticks)`, so values are quantized (357 = 10000/28, 385 = /26, 500 = /20), and (3) carries over from the previous scene because the clock is shared, so a new scene's first samples are stale. The trim label was printed whenever trim_percent > 0 regardless of the frames actually dropped
- **Solution**: `_track_performance` records `1.0 / self.dt` (measured with `time.perf_counter()` in the main loop) on every path, and its unused `timer`/`period_ns` parameters were removed. The trim label is built from the actual `total_frames`/`trimmed_frames` (`no trimming`, `dropped 0 of N frames; the P% setting needs at least M`, or `dropped K frame(s) from each end (P%)`, singular only for exactly 1). The dead `SceneManager._tick_clock()` (same `get_fps()` sampling, never called by the main loop) was removed; its idea is engine audit item #15
- **Related changes**: (a) histogram buckets are ordered numerically instead of lexicographically by string key; (b) the median is the true median (mean of the two middle values for an even count) instead of the upper-middle element; (c) min/max come from all valid frames in both the global and per-scene stats (previously global used untrimmed and per-scene used trimmed data) and the printed lines are labelled `(all frames)` / `(analyzed frames)`; (d) new `one_percent_low_fps` (mean of the slowest 1% of all valid frames) printed after the minimum; (e) selectable histogram mode via `--fps-histogram equal-range|target-relative` (`FpsHistogramMode`, `AdaptiveClamping.set_histogram_mode`): `equal-range` (default) uses exactly 10 equal-width buckets spanning the analyzed min to max, reported as `fps_bucket_width`, with integer range labels such as `450-469`; `target-relative` uses 10% steps of the target FPS (`>=100% (60+ FPS)` down to `<10% (<6)`, non-empty buckets only) and falls back to equal range, saying so in the header, when no target FPS is set; the stats report the mode actually used as `fps_histogram_mode`; (f) the printed histogram lists buckets in ascending numeric order of their lower bound (the bell-curve rearrangement was removed); (g) FPS and frame-time histories use `deque(maxlen=...)` instead of `list.pop(0)` (12.5 us per frame per full 100k list)
- **Tests**: `TestTrackPerformance` in `tests/scenes/test_scene.py`; `TestShutdownStatistics`, `TestHistogramBucketing` and `test_trim_label_*` in `tests/performance/test_adaptive_clamping.py`
- **Files**: `glitchygames/scenes/scene.py`, `glitchygames/performance/adaptive_clamping.py`

### 24. Jumping on a Clockwork Keep Elevator Never Rides It
- **Description**: `_check_elevator()` accepted `jump` as well as `interact`, but the jump handler clears `on_ground` during event processing and `_check_elevator()` requires `on_ground` on the next frame, so jump only ever jumped
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the adversarial audit of the screen shake spec
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-17
- **Solution**: Elevator activation uses interact only; jump always jumps (commit `2850d4f`)
- **Tests**: `TestElevatorActivation` in `tests/examples/test_clockwork_keep.py`
- **Files**: `glitchygames/examples/clockwork_keep/game.py`

### 23. Engine Crashes Without an Audio Device
- **Description**: `pygame.mixer.init()` in `AudioEventManager.__init__` raised an uncaught `pygame.error` when no audio device was available
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the adversarial audit of the screen shake spec
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-17
- **Solution**: The error is caught and logged once, and the engine runs silently (commit `ebc2b48`)
- **Tests**: `test_init_survives_missing_audio_device` in `tests/events/test_audio_events.py`
- **Files**: `glitchygames/events/audio.py`

### 22. Mixer Pre-Init Settings Never Take Effect
- **Description**: `AudioEventManager` called `pygame.mixer.pre_init(22050, -16, 2, 1024)` after `pygame.init()` had already started the mixer at (44100, -16, 2) with a 512-sample buffer, so the settings were ignored
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the adversarial audit of the screen shake spec
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-17
- **Impact**: Brave Adventurer generated its sounds for 22050 Hz, so they had always played an octave high at half length
- **Solution**: Deleted the `pre_init` call and documented the real mixer settings (44100 Hz, 512-sample buffer) (commit `ebc2b48`). The Brave Adventurer sounds were restored as written when they moved to the engine synthesizer (commit `bb4b352`), so they now play an octave lower and longer than before
- **Tests**: `test_init_does_not_call_pre_init` in `tests/events/test_audio_events.py`; `tests/examples/test_brave_adventurer_sounds.py`
- **Files**: `glitchygames/events/audio.py`, `glitchygames/engine/game_engine.py`, `glitchygames/examples/brave_adventurer/sounds.py`

### 21. Parallax Backgrounds Never Scroll During Gameplay
- **Description**: `Camera2D.update()` no longer updated parallax layers, so backgrounds stayed frozen at their `snap_to()` position in Brave Adventurer, Papyrus, and Clockwork Keep
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the adversarial audit of the screen shake spec
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-17
- **Root Cause**: Commit `df21435` inserted `snap_to()` between `update()`'s `_clamp_to_bounds()` call and its parallax loop, so the loop became the tail of `snap_to()` (which updated layers twice) and `update()` lost it. Nothing else called `ParallaxLayer.update_scroll()`.
- **Solution**: Parallax layers are updated from `Camera2D.update()` again (commit `afab532`, "Fix parallax layers not following the camera")
- **Tests**: `TestCamera2DParallax` in `tests/test_camera.py`
- **Files**: `glitchygames/camera.py`

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
