# Future Features for GlitchyGames

> Moved from the repository root (`FUTURE_FEATURES.md`, previously untracked) into `plans/` on
> 2026-10-18. Newer plans: `plans/engine-audit.md` (engine roadmap), `plans/future-work.md`
> (backlog) and `plans/2026-10-18-level-tools.md` (Glitchy Studio).
>
> Paths: `glitchygames/tools/bitmappy.py` and the other editor modules named below were moved into
> the `glitchygames/bitmappy/` package by the Bitmappy refactor (#87, `4bdc966c`): the editor scene
> is `bitmappy/editor.py`, the film strip `bitmappy/film_strip*.py`, `canvas_interfaces.py` and
> `onion_skinning.py` keep their names, the undo/redo manager and operation trackers are
> `bitmappy/history/undo_redo.py` and `history/operations.py`, the multi-controller manager and
> controller selection `bitmappy/controllers/manager.py` and `controllers/selection.py`, and the
> visual collision manager `bitmappy/indicators/collision.py`. `glitchygames/tools/` now holds only
> the ASCII renderer (`ascii_renderer.py`, `charmap.py`, `terminal_utils.py`). Other
> `glitchygames/tools/...` files listed under planned features were never created.

This document tracks planned future features for the GlitchyGames project. Features are listed in priority order and will be implemented as time and priorities allow.

## High Priority Features

### 1. Memory Optimization
- **Description**: Implement configurable buffer sizes and automatic cleanup for long-running games
- **Use Case**: Reduced memory footprint for extended gameplay sessions, 5 9s reliability (100,000+ data points)
- **Status**: Planned
- **Priority**: High
- **Implementation**:
  - Increase FPS history buffer to 100,000 frames
  - Add configurable buffer sizes
  - Implement automatic cleanup for memory management

### 2. Real-time Performance Monitoring
- **Description**: Add live performance dashboard during gameplay with FPS overlay and performance warnings
- **Use Case**: Essential for debugging and performance monitoring during development
- **Status**: Planned
- **Priority**: High
- **Implementation**:
  - Refactor existing FPS blit functionality
  - Add live FPS counter overlay
  - Implement performance warnings (FPS drops, memory usage)
  - Track sprite count and memory usage
  - Estimate CPU usage from frame times
- **Progress**: the FPS overlay is done: the debug overlay's performance panel
  (`glitchygames/debug/`, `--debug-overlay` / F3) shows FPS, frame time, the 1% low and a
  frame-time graph. Warnings, sprite count and memory usage are still open.

### 3. Enhanced Metrics Collection
- **Description**: Comprehensive performance metrics beyond basic FPS tracking
- **Use Case**: Better performance insights and bottleneck identification
- **Status**: Planned
- **Priority**: High
- **Implementation**:
  - Frame time variance (jitter analysis)
  - Input lag measurement
  - Audio latency tracking
  - Network performance (for multiplayer)
  - GPU utilization (if available)

## Medium Priority Features

### 4. Performance Profiling Integration
- **Description**: Detailed profiling capabilities for per-scene performance breakdown
- **Use Case**: Better development tools and performance optimization
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - Per-scene performance breakdown (update vs render time)
  - Sprite/object performance impact analysis
  - Event processing time tracking
  - Memory allocation tracking

### 5. Adaptive Quality Settings
- **Description**: Dynamic quality scaling based on performance
- **Use Case**: Improves user experience on lower-end hardware
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - Automatic resolution scaling
  - Dynamic sprite detail reduction
  - Adaptive particle system density
  - Smart LOD (Level of Detail) for complex scenes

## Low Priority Features

### 6. Performance Benchmarking
- **Description**: Built-in performance test suite and automated testing
- **Use Case**: Performance regression testing and optimization
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - Automated performance regression testing
  - Hardware-specific performance profiles
  - Performance comparison tools
  - Bottleneck identification

### 7. Debug Performance Tools
- **Description**: Advanced debugging capabilities for performance analysis
- **Use Case**: Advanced debugging features for developers
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - Performance bottleneck visualization
  - Frame time graph overlay (done: the debug overlay's performance panel, `glitchygames/debug/panels.py`)
  - Performance hotspot identification
  - Memory leak detection

### 8. Performance Configuration System
- **Description**: User-configurable performance profiles and settings
- **Use Case**: Customizable performance for different hardware capabilities
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - Performance presets (High/Medium/Low)
  - Custom performance profiles
  - Automatic performance optimization
  - Performance-based settings recommendations

### 9. Platform-Specific Optimizations
- **Description**: Platform-aware performance optimizations and tuning
- **Use Case**: Optimized performance for different platforms
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - Mobile-specific performance tuning
  - Desktop vs console optimizations
  - Platform-specific frame rate targets
  - Hardware capability detection
  - Per-platform super accurate timers

### 10. Performance Data Export
- **Description**: Data export and analysis tools for performance data
- **Use Case**: Performance analysis and historical tracking
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - CSV/JSON performance data export
  - Performance visualization tools
  - Historical performance tracking
  - Performance trend analysis

## Code Architecture Features

### 11. Event Manager Naming Convention Refactor
- **Description**: Refactor all event managers to use consistent `FooEventManager` naming convention instead of `FooManager`
- **Use Case**: Improves code clarity and consistency by making it explicit that these classes manage events
- **Status**: Planned. The rename is done: every manager in `glitchygames/events/` is a
  `*EventManager` (voice: `VoiceEventManager`; no `VoiceRecognitionManager` remains). The Vosk
  backend item below is still open
- **Priority**: Medium
- **Implementation**:
  - Renamed to EventManagers:
- Voice recognition:
  - Add optional Vosk backend using miniaudio capture for fully offline STT
    - Capture via MiniaudioMicrophone, segment/buffer, feed Vosk model
    - Expose backend selection flag and graceful fallback to speech_recognition
    - `GameEventManager`
    - `ControllerEventManager`
    - `AppEventManager`
    - `MouseEventManager`
    - `JoystickEventManager`
    - `MidiEventManager`
    - `WindowEventManager`
  - Rename `VoiceRecognitionManager` → `VoiceRecognitionEventManager`
  - Update all imports and references throughout the codebase
  - Update documentation and comments
  - Ensure backward compatibility during transition period

## Game Mechanics Features

### 12. Stuck Ball Recovery System
- **Description**: Game mechanic for handling balls that get stuck at zero speed (0, 0), turning it into a strategic gameplay element rather than a bug
- **Use Case**: Creates strategic depth where players must manage stuck balls, adds recovery mechanics, and prevents game-breaking scenarios
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Stuck Detection**: Detect when ball speed magnitude falls below threshold (e.g., < 1.0 pixels/second)
  - **Stuck State Tracking**: Track how long ball has been stuck and position where it became stuck
  - **Visual Indicators**: Clear UI feedback showing stuck state (color change, pulsing, special effects)
  - **Recovery Mechanisms**:
    - Limited "kick" attempts to free stuck balls (e.g., 3 kicks per ball)
    - Directional kicks (left, right, up, down, random)
    - Automatic recovery after paddle contact
  - **Strategic Elements**:
    - Stuck balls could count differently in scoring
    - Time limits for stuck balls before special events
    - Risk/reward of intentionally creating stuck balls
  - **Game Events**: Special events triggered by critically stuck balls (stuck too long)
  - **UI Features**: 
    - Stuck ball counter/indicator
    - Recovery kick counter
    - Stuck time display
    - Recovery attempt feedback

### 13. Air Brake Paddle Movement System
- **Description**: Paddles that continuously move with air resistance, requiring constant input to maintain position
- **Use Case**: Creates more dynamic and challenging paddle control where paddles naturally drift and require active management
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - **Continuous Movement**: Paddles always have some movement unless actively controlled
  - **Air Resistance**: Natural deceleration when not actively moving
  - **Momentum System**: Paddles build up momentum and require counter-input to stop
  - **Drift Mechanics**: Paddles naturally drift in one direction unless actively opposed
  - **Control Feedback**: Visual/audio feedback for momentum and drift direction
  - **Difficulty Scaling**: Adjustable drift speed and resistance for different skill levels

### 14. Enhanced Ball Boundary Physics ✅ COMPLETED
- **Description**: Improved ball collision and boundary behavior with proper physics
- **Use Case**: More realistic ball behavior, better collision detection, and smoother gameplay
- **Status**: ✅ COMPLETED
- **Priority**: Medium
- **Implementation**:
  - ✅ **Proper Boundary Checking**: Ball should not clip through screen edges
  - ✅ **Collision Response**: Realistic bounce angles and energy conservation
  - ✅ **Edge Case Handling**: Better behavior when ball hits corners or edges
  - ✅ **Physics Accuracy**: Proper momentum transfer and angle calculations
  - ✅ **Visual Feedback**: Clear indication of collision points and bounce directions
- **Files Modified**:
  - `glitchygames/game_objects/ball.py` - Enhanced physics with realistic collision response
  - `tests/game_objects/test_ball_boundary_physics.py` - Comprehensive test suite

### 15. Momentum Dampening System
- **Description**: Gradual deceleration system for movement objects to create more natural motion
- **Use Case**: Smoother, more realistic movement that feels more natural and controllable
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - **Gradual Deceleration**: Objects slow down over time instead of instant stops
  - **Configurable Damping**: Adjustable deceleration rates for different objects
  - **Momentum Preservation**: Maintains some momentum for more realistic physics
  - **Input Response**: Responsive to input while maintaining natural deceleration
  - **Performance Optimization**: Efficient calculation of dampening effects

## Recently Completed Features

### 42. Mr. Muncher Remade: A Maze Chase at the Movies ✅ COMPLETED
- **Description**: The converted toy was not fun (12 px/s movement, an open field with two
  wall pieces, munchers wandering at random, discs overlapping walls, a catch resetting only the
  player, no end to a won game; a perfect bot cleared 87 of 211 dots in 10 minutes). It is now a
  complete, original maze-chase game with a cinema theme (2026-10-23)
- **Status**: ✅ COMPLETED (2026-10-23)
- **Implementation** (`glitchygames/examples/mr_muncher/`):
  - `maze.py`: a hand-designed 27x24 maze (symmetric, corridors one tile wide, no dead ends,
    connected; tests check all four), tunnels at the top and bottom, a house with a door
  - `actors.py`: tile-to-tile movement (turns on tile centres only; a direction pressed early is
    taken at the first open junction; reversing is immediate); four munchers with their own
    targets (chaser, ambusher, flanker, shy), scatter/chase phases, a frightened random walk on
    the seeded stream, eyes going home and back out
  - `levels.py`: speeds, fright length, mode schedule and bonus per reel, ramping to reel 8
  - `game.py`: the scene (countdown 3-2-1-ACTION!, TAKE n after a death, REEL n, CUT!, THE END),
    sprockets (10), snacks (50, a sugar rush), munchers 200/400/800/1600, the bonus reel twice a
    reel, an extra life at 10,000, high scores through `open_saves`, the engine's pause and a
    game-over screen, a screen shake and rumble on a catch, a projector-flutter live voice,
    `debug_draw` marks muncher targets; `drawing.py` (velvet-and-gold maze, popcorn-bucket
    player, fuzzball munchers, candy snacks), `scenery.py`, `sounds.py` (all original sounds)
  - `autopilot.py`: a player bot (territory-safe BFS) used by the golden script and the tests;
    golden replay re-recorded (2250 frames: countdown, pause, a snack, two munchers and the
    bonus eaten, a death, take 2); tests `tests/examples/test_mr_muncher.py` and
    `tests/examples/test_mr_muncher_maze_and_actors.py` (100% lines and branches)

### 41. Mr. Muncher Example Game and Microphone Capture Check ✅ COMPLETED
- **Description**: Two untracked toys brought up to the project's standards (2026-10-23): the
  plain-pygame Pac-Man toy `scripts/mr_muncher.py` became the example game
  `glitchygames/examples/mr_muncher/` (`uv run mr-muncher`), and `scripts/audio_test.py` became
  `scripts/microphone_capture_check.py`
- **Status**: ✅ COMPLETED (2026-10-23)
- **Implementation**:
  - Mr. Muncher: a `Scene` run by `GameEngine`; scancode `ActionMap` controls; the maze, its
    sprockets and the munchers' turns from seeded random streams; frame-rate independent speeds;
    sprites (compared by replays) instead of direct drawing; golden replay
    `tests/fixtures/replays/mr-muncher/golden.jsonl.gz` (600 frames,
    `scripts/record_golden_traces.py: mr_muncher_script`); `tests/examples/test_mr_muncher.py`
  - Microphone check: capture `--duration` seconds (default 3) from the default or a named
    (`--device`) capture device with miniaudio, report bytes, frames and peak/RMS levels, exit
    with an `ExitCode`; `tests/test_microphone_capture_check.py`

### 40. Gameplay Replay ✅ COMPLETED (Parts 1-3)
- **Description**: Replay a `--record-trace` recording exactly through the real engine
  (`--replay-trace PATH`), comparing every frame's sprites with the recording and reporting the
  first divergence; audit determinism in two fresh processes (`--audit`); replay tooling (Part 2)
  and in-game playback (Part 3)
- **Use Case**: Bug reproduction from a recording, regression tests from real play, finding
  nondeterminism; watching and stepping through recordings; attract-mode demos, instant replays
  and ghosts in games
- **Status**: ✅ COMPLETED (branch `feature/gameplay-replay`: Part 1 2026-10-19, Parts 2 and 3
  2026-10-20; final whole-branch review clean 2026-10-20; merged 2026-10-22 as PR #95, `bb51239d`)
- **Priority**: High
- **Implementation**:
  - The doors: `glitchygames/sources.py` (leaf registry), `LiveSources`, `RecordingSources`,
    `ReplaySources`; `tests/test_engine_doors.py` guards them
  - Clocks (`glitchygames/clock.py`, `Scene.game_time`), input snapshots (`current_input()`),
    the devices door with replay stand-ins, saves through `open_saves` (`DiskSaveManager` /
    `MemorySaveManager`), the supervisor hook and control events
  - Trace format 3, `--replay-fps {recorded,real}`, real input blocked at SDL during a replay,
    golden replay fixtures (`tests/fixtures/replays/`, `scripts/record_scripted_session.py`),
    run as pytest items by the replay plugin (`glitchygames/testing/replays.py`)
  - Part 2, tooling: `--headless`, the watched-replay viewer (pause, step, speed, step back
    through a restarted process, bookmarks saved to `*.bookmarked.jsonl.gz`), recordings as
    pytest items, `--rebaseline`
  - Part 3, playback: scene starts (`glitchygames/scene_start.py`), the playback scope
    (`glitchygames/replay/playback.py`), demos (`play_recording`; PaddleSlap's bundled demo on
    its game-over screen), instant replay (`glitchygames/instant_replay.py`), ghosts
    (`glitchygames/replay/ghosts.py`)
- **Docs**: CLAUDE.md (Clocks, Gameplay Recording and Replay),
  `docs/architecture/gameplay_replay.md`, `plans/2026-10-19-gameplay-replay.md`

### 39. Engine World Space and One End-of-Frame Call ✅ COMPLETED
- **Description**: Sprites declare `CoordinateSpace.WORLD` and the engine positions, snaps and
  culls them from the scene's camera every frame; the camera follows a target on chosen axes;
  every frame ends in one `_finish_frame` that paces and measures the frame once (engine audit
  #6 and #15)
- **Use Case**: Games no longer write per-sprite camera loops or culling; shake, snapping,
  culling and follow have one place in the engine; frame statistics match what the loop did
- **Status**: ✅ COMPLETED (branch `feature/engine-world-space`, 2026-10-18; merged 2026-10-22 as PR #94, `cd5e5f97`)
- **Priority**: High
- **Implementation**:
  - `glitchygames/world.py`: `CoordinateSpace`, `WorldPositioned`, `hidden`,
    `position_world_sprites` (`CULL_MARGIN_PIXELS` culling that never lowers `dirty = 2`,
    `draw_offset` added), `aim_camera`
  - `Camera2D.follow(target=, axes=FollowAxes)`, `aim_at`, `begin_frame`; `Scene.camera_target()`,
    `Scene.PIXEL_SNAP_MODE`, `Scene.MAX_FRAME_SECONDS`
  - `SceneManager._finish_frame`: one start-to-start `dt`; pacing re-anchors after a hitch
  - Brave Adventurer, Papyrus, Clockwork Keep and PaddleSlap migrated; the pose rule (draw the
    pose in `dt_tick` before collision) fixes the one-frame wall lag
  - Golden traces of every game (`tests/world/test_golden_traces.py`), each difference proven by
    exactly one rule; gameplay recording (`--record-trace`) and seeded random streams
    (`--random-seed`)
- **Docs**: CLAUDE.md (World Space, Frame Pacing), `plans/2026-10-18-engine-world-space.md`

### 16. ASCII Transparency Contrast Enhancement ✅ COMPLETED
- **Description**: Enhanced ASCII renderer to draw fully transparent pixels as light grey for better contrast visibility
- **Use Case**: Improves visibility of transparent pixels in terminal output, making it easier to see sprite boundaries and structure
- **Status**: ✅ COMPLETED
- **Priority**: Medium
- **Implementation**:
  - Modified `_colorize_pixels` method in ASCII renderer
  - Added light grey (192, 192, 192) background for fully transparent pixels (alpha = 0)
  - Enhanced transparency detection for both RGBA and magenta transparency
  - Improved contrast for better terminal visibility
- **Files Modified**:
  - `glitchygames/tools/ascii_renderer.py` - Enhanced transparency handling

### 17. TOML Drag-n-Drop Support ✅ COMPLETED
- **Description**: Added drag-n-drop support for .toml files to the canvas, complementing existing PNG drag-n-drop functionality
- **Use Case**: Allows users to directly load TOML sprite files by dragging them onto the canvas, streamlining the workflow
- **Status**: ✅ COMPLETED
- **Priority**: Medium
- **Implementation**:
  - Extended `on_drop_file_event` method to detect .toml file extensions
  - Added direct loading of TOML files without conversion
  - Maintained existing PNG conversion workflow
  - Updated error messages to reflect support for both file types
- **Files Modified**:
  - `glitchygames/tools/bitmappy.py` - Enhanced drag-n-drop handling

### 18. Flood-Fill Tool ✅ COMPLETED
- **Description**: Implemented flood-fill functionality for the canvas using control-click to fill connected regions of the same color
- **Use Case**: Efficiently fill large areas or backgrounds with a single click, improving productivity for sprite editing
- **Status**: ✅ COMPLETED
- **Priority**: High
- **Implementation**:
  - Added control-click detection using `pygame.key.get_pressed()`
  - Implemented iterative flood-fill algorithm using stack-based approach
  - Added 4-connected neighbor checking (up, down, left, right)
  - Integrated with existing canvas interface and color system
  - Added comprehensive logging for debugging
- **Files Modified**:
  - `glitchygames/tools/bitmappy.py` - Added flood-fill algorithm and control-click handling

### 19. Onion Skinning Initialization Fix ✅ COMPLETED
- **Description**: Fixed onion skinning initialization when loading sprites to ensure proper alpha blending and transparency handling
- **Use Case**: Ensures onion skinning works correctly after loading sprites, with proper semi-transparent overlays
- **Status**: ✅ COMPLETED
- **Priority**: High
- **Implementation**:
  - Restored `_initialize_onion_skinning_for_sprite` method
  - Added automatic initialization after successful sprite loading
  - Proper frame state management for all animations
  - Global onion skinning toggle support
  - Enhanced alpha blending with transparent pixels
- **Files Modified**:
  - `glitchygames/tools/bitmappy.py` - Fixed onion skinning initialization

### 20. Debug Logging Cleanup ✅ COMPLETED
- **Description**: Removed verbose debug logging statements that were cluttering console output
- **Use Case**: Cleaner console output for better development experience and reduced log noise
- **Status**: ✅ COMPLETED
- **Priority**: Low
- **Implementation**:
  - Removed animation update debug logs
  - Removed film strip update debug logs
  - Maintained functionality while reducing console verbosity
- **Files Modified**:
  - `glitchygames/tools/bitmappy.py` - Cleaned up debug logging

### 21. Controller Position Undo/Redo System ✅ COMPLETED
- **Description**: Integrated controller position and mode changes into the undo/redo system, allowing users to undo controller movements and mode switches
- **Use Case**: Essential for collaborative editing workflows where controller positions and modes need to be tracked and reversible, improving user experience and workflow efficiency
- **Status**: ✅ COMPLETED
- **Priority**: High
- **Implementation**:
  - **Controller Position Tracking**: Track controller position changes for undo/redo operations
  - **Controller Mode Tracking**: Track controller mode changes (canvas, film_strip, slider modes)
  - **Smart Continuous Movement Handling**: Skip tracking during continuous movement to prevent undo stack overflow
  - **Final Position Tracking**: Track final positions when continuous movement stops
  - **Undo/Redo Integration**: Full integration with existing undo/redo system
  - **Controller-Specific History**: Each controller maintains its own position and mode history
  - **Performance Optimization**: Efficient tracking that doesn't interfere with continuous movement
- **Technical Requirements**:
  - Controller position operation tracking system
  - Controller mode change operation tracking
  - Continuous movement detection and handling
  - Integration with existing undo/redo manager
  - Performance optimization for real-time tracking
  - Smart operation batching for continuous movements
- **Key Features**:
  - **Position Undo/Redo**: Undo/redo controller position changes
  - **Mode Undo/Redo**: Undo/redo controller mode switches
  - **Continuous Movement Handling**: Smart tracking that doesn't overwhelm undo system
  - **Final Position Tracking**: Track complete movements as single operations
  - **Controller Context**: Maintain controller-specific undo/redo history
  - **Performance Optimized**: Minimal impact on continuous movement performance
- **Files Created/Modified**:
  - `glitchygames/tools/undo_redo_manager.py` - Added controller position operation types and callbacks
  - `glitchygames/tools/operation_history.py` - Added ControllerPositionOperationTracker
  - `glitchygames/tools/bitmappy.py` - Integrated controller position tracking with movement system
  - `tests/tools/test_controller_position_undo_redo.py` - Comprehensive test suite
  - `tests/tools/test_slider_continuous_movement_fix.py` - Continuous movement fix tests
- **Known Issues**:
  - Some minor bugs with slider continuous movement stopping (livable but annoying)
  - Controller position tracking may occasionally miss rapid movements
  - Mode switching undo/redo may have edge cases with complex controller interactions
- **Future Improvements**:
  - Enhanced continuous movement detection
  - Improved slider button release handling
  - Better integration with existing undo/redo visualization
  - Performance optimizations for high-frequency controller movements

### 22. Per-Pixel Alpha Support for AI-Generated Sprites ✅ COMPLETED
- **Description**: Enhanced sprite loading and rendering pipeline to support per-pixel alpha transparency in AI-generated sprites, with automatic detection and proper handling
- **Use Case**: Enables AI-generated sprites to use sophisticated transparency effects with per-pixel alpha values, improving visual quality and artistic possibilities
- **Status**: ✅ COMPLETED
- **Priority**: High
- **Implementation**:
  - **Automatic Alpha Detection**: Detects whether sprites use per-pixel alpha or indexed transparency based on color data
  - **RGBA Surface Creation**: Creates pygame surfaces with SRCALPHA flag when per-pixel alpha is detected
  - **Transparency Key Handling**: Maintains proper handling of magenta (255, 0, 255) transparency key
  - **Canvas Rendering**: Ensures transparency key pixels are skipped during canvas rendering to show background
  - **Film Strip Display**: Converts transparency key to transparent pixels for proper film strip visualization
  - **ASCII Output Enhancement**: Updated ASCII renderer to show all animation frames with dimensions and properties
- **Technical Requirements**:
  - Enhanced sprite loading pipeline with alpha detection
  - Proper RGBA surface creation and pixel conversion
  - Canvas renderer updates to handle transparency correctly
  - Film strip transparency handling
  - ASCII renderer improvements for animation display
- **Key Features**:
  - **Per-Pixel Alpha Support**: Full RGBA color support with alpha channel
  - **Indexed Transparency Fallback**: Maintains compatibility with existing indexed transparency
  - **Automatic Detection**: No manual configuration required - automatically detects alpha usage
  - **Proper Canvas Rendering**: Transparency key pixels show background instead of drawing transparently
  - **Enhanced ASCII Output**: Shows all animation frames with dimensions (e.g., "dimensions: 2x2")
  - **Film Strip Compatibility**: Proper transparency handling in film strip display
- **Files Modified**:
  - `glitchygames/sprites/animated.py` - Enhanced RGBA support and transparency key handling
  - `glitchygames/tools/bitmappy.py` - Updated canvas rendering and sprite loading
  - `glitchygames/tools/canvas_interfaces.py` - Fixed transparency key pixel rendering
  - `glitchygames/tools/film_strip.py` - Proper transparency handling for film strip
  - `glitchygames/tools/ascii_renderer.py` - Enhanced animation frame display with dimensions
- **Future Improvements**:
  - Update AI sprite generation instructions to include per-pixel alpha examples
  - Add documentation for alpha transparency best practices
  - Consider adding alpha blending modes for advanced effects

## Animation Features

### 21. Onion Skinning ✅ COMPLETED
- **Description**: Animation feature that allows users to see previous/future frames as semi-transparent overlays while editing current frame
- **Use Case**: Helps with smooth animation creation by providing visual reference of motion
- **Status**: ✅ COMPLETED
- **Priority**: TBD
- **Implementation**:
  - **Onion Skinning Manager**: Core data structure to track enabled frames per animation
  - **Visual Indicators**: Film strip shows yellow overlay for frames with onion skinning enabled
  - **Canvas Rendering**: Onion frames rendered first with 50% transparency, then active frame with full opacity
  - **Toggle Controls**: Right-click or Shift+click on film strip frames to toggle onion skinning
  - **Keyboard Shortcuts**: 'O' key toggles global onion skinning on/off
  - **Transparency Control**: Configurable transparency level (default 50%)
- **Files Created/Modified**:
  - `glitchygames/tools/onion_skinning.py` - Core onion skinning management
  - `glitchygames/tools/onion_skinning_renderer.py` - Canvas rendering with transparency
  - `glitchygames/tools/film_strip.py` - Visual indicators and click handling
  - `glitchygames/tools/canvas_interfaces.py` - Integration with canvas rendering
  - `glitchygames/tools/bitmappy.py` - Keyboard shortcuts
  - `tests/tools/test_onion_skinning.py` - Comprehensive test suite


### 22. Multi-Controller Navigation System (BETTER) ✅ COMPLETED
- **Description**: Multi-controller support system for bitmappy tool allowing up to 4 simultaneous controllers with independent navigation and visual distinction
- **Use Case**: Enables multiple users to navigate and select different frames/animations simultaneously using separate controllers
- **Status**: ✅ COMPLETED
- **Priority**: High
- **Implementation**:
  - **Controller Assignment**: Automatic detection and assignment of controllers on first button press
  - **Independent Navigation**: Each controller navigates film strips and frames independently
  - **Visual Distinction**: Unique colored triangles for each controller (Red, Green, Blue, Yellow)
  - **Smart Positioning**: Automatic collision avoidance when multiple controllers select same frame
  - **Controller Management**: 
    - Automatic assignment on first button press
    - Controller reconnection handling
    - Status tracking and display
  - **Navigation Features**:
    - Independent frame/animation selection per controller
    - Controller-specific scrolling and navigation
    - Frame preservation when switching between controllers
    - Individual controller selection state management
- **Technical Requirements**:
  - Multi-controller event handling system
  - Visual collision detection and positioning
  - Independent state tracking per controller
  - Efficient rendering of multiple indicators
  - Controller connection/disconnection handling
- **Controller Color Scheme**:
  - Controller 0: Red (255, 0, 0)
  - Controller 1: Green (0, 255, 0)  
  - Controller 2: Blue (0, 0, 255)
  - Controller 3: Yellow (255, 255, 0)
- **User Experience**:
  - **Intuitive Assignment**: Controllers automatically assigned on first use
  - **Clear Visual Feedback**: Distinct colors and indicators for each controller
  - **Smooth Navigation**: Independent scrolling and frame selection
  - **No Conflicts**: Smart positioning prevents visual overlap
- **Files to Create/Modify**:
  - `glitchygames/tools/multi_controller_manager.py` - Core multi-controller system
  - `glitchygames/tools/controller_selection.py` - Individual controller state management
  - `glitchygames/tools/visual_collision_manager.py` - Visual indicator positioning
  - `glitchygames/tools/bitmappy.py` - Enhanced with multi-controller support
  - `glitchygames/tools/film_strip.py` - Enhanced visual system for multiple indicators
  - `tests/tools/test_multi_controller.py` - Multi-controller system tests
  - `tests/tools/test_visual_collision.py` - Visual system tests
- **Configuration Options**:
  - Maximum controller count (default: 4, easily configurable)
  - Controller color customization
  - Navigation speed per controller
  - Visual indicator styles
- **Future Extensibility**:
  - Easy to increase controller limit (change MAX_CONTROLLERS constant)
  - Modular design allows adding new controller features
  - Foundation for collaborative editing features

### 23. Collaborative Multi-Controller Editing System (BEST) ✅ COMPLETED
- **Description**: Advanced collaborative editing system building on multi-controller navigation, enabling real-time simultaneous editing by multiple users
- **Use Case**: Enables teams to collaboratively edit sprites and animations in real-time, with conflict resolution and advanced workflow management
- **Status**: ✅ COMPLETED
- **Priority**: High
- **Prerequisites**: Multi-Controller Navigation System (Feature #18)
- **Implementation**:
  - **Real-time Collaborative Editing**: Multiple controllers can edit pixels simultaneously
  - **Conflict Resolution**: Intelligent handling of simultaneous pixel editing with priority-based resolution
  - **Advanced Visual Management**:
    - Controller-specific settings and preferences
    - Customizable visual indicators and styles
    - Advanced positioning algorithms for complex scenarios
  - **Collaborative Features**:
    - Shared editing sessions with real-time synchronization
    - Permission management (master/slave controller relationships)
    - Edit history and undo/redo per controller
    - Collaborative session management
  - **Advanced Controller Features**:
    - Controller-specific shortcuts and button mappings
    - Speed control and navigation preferences per controller
    - Focus management and controller switching
    - Performance monitoring per controller
  - **Session Management**:
    - Start/stop collaborative sessions
    - Controller permission levels
    - Edit conflict notifications
    - Session history and playback
- **Technical Requirements**:
  - Real-time synchronization system
  - Conflict detection and resolution algorithms
  - Advanced visual management for complex scenarios
  - Performance optimization for simultaneous editing
  - Session state management
  - Edit history tracking per controller
- **Collaborative Workflow**:
  - **Session Initiation**: Master controller starts collaborative session
  - **Controller Joining**: Additional controllers join with assigned permissions
  - **Real-time Editing**: All controllers can edit simultaneously
  - **Conflict Handling**: Automatic resolution of edit conflicts
  - **Session Management**: Save/load collaborative sessions
- **Permission Levels**:
  - **Master Controller**: Full control, can manage session
  - **Editor Controllers**: Can edit pixels, limited session control
  - **Viewer Controllers**: Can navigate, cannot edit
  - **Guest Controllers**: Limited navigation, no editing
- **Conflict Resolution Strategies**:
  - **First-Come-First-Served**: First controller to edit pixel wins
  - **Priority-Based**: Master controller has priority
  - **Time-Based**: Most recent edit wins
  - **Area-Based**: Controllers assigned to different sprite areas
- **Files to Create/Modify**:
  - `glitchygames/tools/collaborative_editing.py` - Collaborative editing system
  - `glitchygames/tools/session_manager.py` - Session management
  - `glitchygames/tools/conflict_resolver.py` - Conflict resolution
  - `glitchygames/tools/permission_manager.py` - Permission system
  - `glitchygames/tools/edit_history.py` - Edit history tracking
  - `glitchygames/tools/bitmappy.py` - Enhanced with collaborative features
  - `tests/tools/test_collaborative_editing.py` - Collaborative editing tests
  - `tests/tools/test_session_manager.py` - Session management tests
  - `tests/tools/test_conflict_resolver.py` - Conflict resolution tests
- **Advanced Features**:
  - **Edit Broadcasting**: Real-time edit notifications to all controllers
  - **Undo/Redo Per Controller**: Individual edit history for each controller
  - **Edit Locks**: Temporary locks on pixels being edited
  - **Collaborative Cursors**: Show other controllers' cursor positions
  - **Edit Previews**: Show pending edits before confirmation
  - **Session Recording**: Record collaborative sessions for playback
- **Performance Considerations**:
  - **Edit Batching**: Group rapid edits to reduce network overhead
  - **Area-Based Updates**: Only sync relevant sprite areas
  - **Controller Throttling**: Limit edit frequency per controller
  - **Memory Management**: Efficient storage of edit history
- **User Experience**:
  - **Seamless Collaboration**: Natural editing experience with multiple users
  - **Clear Conflict Indication**: Visual feedback for edit conflicts
  - **Session Awareness**: Always know who is editing what
  - **Flexible Permissions**: Adaptable to different workflow needs
- **Future Extensibility**:
  - Network support for remote controllers
  - Cloud-based collaborative sessions
  - Advanced conflict resolution algorithms
  - Integration with version control systems

### 24. Colorized ASCII Output for Bitmappy Sprites ✅ COMPLETED
- **Description**: Enhanced terminal output for bitmappy sprite objects that displays ASCII art with colors matching the sprite's color palette
- **Use Case**: Better visual representation of sprites in terminal/console output, improved debugging and development experience
- **Status**: ✅ COMPLETED
- **Priority**: Medium
- **Implementation**:
  - **Color Palette Integration**: Extract colors from sprite's color section and map to terminal colors
  - **ASCII Art Generation**: Convert sprite pixels to ASCII characters with appropriate color mapping
  - **Terminal Color Support**: Detect terminal color capabilities (8-color, 256-color, true color)
  - **Fallback Support**: Graceful degradation for terminals without color support
  - **Performance Optimization**: Efficient color mapping and ASCII conversion
  - **Customization Options**:
    - Configurable ASCII character sets (basic, extended, custom)
    - Color intensity scaling for better terminal visibility
    - Size scaling for different terminal sizes
    - Optional color reduction for compatibility
- **Technical Requirements**:
  - Terminal color detection and support
  - Color palette extraction from sprite data
  - ASCII character mapping algorithms
  - Terminal compatibility testing
  - Performance optimization for large sprites
- **Files to Create/Modify**:
  - `glitchygames/tools/ascii_renderer.py` - ASCII rendering system
  - `glitchygames/tools/color_mapper.py` - Color palette mapping
  - `glitchygames/tools/terminal_utils.py` - Terminal capability detection
  - `tests/tools/test_ascii_renderer.py` - ASCII rendering tests
  - `tests/tools/test_color_mapper.py` - Color mapping tests

## AI and Input Features

### 25. Speech-to-Text AI Sprite Generation
- **Description**: Use microphone input to generate sprites through AI using speech-to-text technology
- **Use Case**: Hands-free sprite creation, accessibility features, creative workflow enhancement
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Speech Recognition**: Real-time speech-to-text conversion for sprite descriptions
  - **AI Integration**: Connect speech input to AI sprite generation systems
  - **Controller Support**: PS5 controller microphone integration for portable sprite creation
  - **Voice Commands**: Natural language commands for sprite generation
  - **Real-time Processing**: Live speech recognition with immediate feedback
  - **Multi-language Support**: Support for multiple languages and accents
- **Technical Requirements**:
  - Speech recognition library integration (e.g., SpeechRecognition, Whisper)
  - AI sprite generation API integration
  - Microphone input handling
  - PS5 controller microphone support
  - Real-time audio processing
  - Voice command parsing and interpretation
- **Controller Integration**:
  - **PS5 Controller Support**: Utilize built-in microphone for portable sprite creation
  - **Voice Activation**: Push-to-talk or voice activation for hands-free operation
  - **Audio Quality**: Optimize for controller microphone limitations
  - **Noise Filtering**: Background noise reduction for better recognition
- **User Experience**:
  - **Natural Language**: "Create a red dragon sprite" or "Make a blue car"
  - **Voice Feedback**: Audio confirmation of recognized commands
  - **Visual Feedback**: Real-time display of recognized speech
  - **Error Handling**: Graceful handling of unclear or unrecognized speech
- **Advanced Features**:
  - **Voice Training**: Personalized voice recognition for better accuracy
  - **Command Shortcuts**: Custom voice shortcuts for common operations
  - **Batch Generation**: Voice commands for creating multiple sprites
  - **Style Transfer**: "Make it look like pixel art" or "Make it anime style"
- **Files to Create/Modify**:
  - `glitchygames/ai/speech_sprite_generator.py` - Core speech-to-sprite system
  - `glitchygames/ai/voice_processor.py` - Speech recognition and processing
  - `glitchygames/ai/controller_mic.py` - PS5 controller microphone support
  - `glitchygames/ai/voice_commands.py` - Voice command parsing
  - `glitchygames/tools/bitmappy.py` - Integration with bitmappy tool
  - `tests/ai/test_speech_sprite_generator.py` - Speech generation tests
  - `tests/ai/test_voice_processor.py` - Voice processing tests

## Gameplay Features

### 26. Water Physics Level System
- **Description**: Half-water, half-air level with realistic refraction physics and visual effects
- **Use Case**: Enhanced gameplay mechanics, visual variety, physics-based challenges
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Water Boundary Detection**: Detect when paddle/ball enters water zone
  - **Refraction Physics**: Change object velocity based on water entry angle and speed
  - **Visual Effects**:
    - Water surface animation (waves, ripples)
    - Light shimmer effects on water surface
    - Magnification effect (objects appear larger underwater)
    - Splash effects when objects enter water
  - **Audio Effects**:
    - Splash sounds for paddle/ball water entry
    - Different splash intensities based on entry velocity
    - Underwater audio filtering for submerged objects
  - **Physics Considerations**:
    - Reduced speed in water (drag effect)
    - Altered bounce angles due to refraction
    - Buoyancy effects for floating objects
    - Surface tension effects at water boundary
  - **Visual Polish**:
    - Water surface distortion effects
    - Caustic light patterns
    - Particle effects for splashes
    - Dynamic water level (waves affect gameplay)
- **Technical Requirements**:
  - Water zone collision detection
  - Velocity modification algorithms
  - Visual effect rendering system
  - Audio system integration
  - Performance optimization for real-time effects
- **Files to Create/Modify**:
  - `glitchygames/levels/water_level.py` - Water level implementation
  - `glitchygames/effects/water_effects.py` - Visual effects system
  - `glitchygames/physics/refraction.py` - Refraction physics
  - `glitchygames/audio/water_sounds.py` - Water audio effects
  - `tests/levels/test_water_level.py` - Water level tests
  - `tests/physics/test_refraction.py` - Refraction physics tests

### 27. Dynamic Audio Intensity System
- **Description**: Programmatic audio modification system for impact-based sound effects
- **Use Case**: Enhanced audio feedback, realistic sound scaling, immersive gameplay
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - **Audio Scaling**: Modify pitch, volume, and effects based on impact intensity
  - **Velocity-Based Audio**: Different sounds for different collision speeds
  - **Layered Audio**: Combine multiple sound effects for complex interactions
  - **Real-time Processing**: Dynamic audio modification during gameplay
- **Technical Requirements**:
  - Audio processing pipeline
  - Sound effect layering system
  - Performance optimization for real-time audio
  - Integration with existing sound system

## Editing and Workflow Features

### 28. Sprite Format Linter
- **Description**: Comprehensive validation and linting tool for TOML sprite files to ensure format compliance and catch common errors
- **Use Case**: Essential for maintaining sprite file quality, catching format errors early, and ensuring compatibility across different sprite formats
- **Status**: Planned
- **Priority**: High
- **Implementation**:
  - **Format Validation**: Validate TOML syntax and structure compliance
  - **Sprite Structure Validation**: Verify sprite sections, animation structure, and frame data
  - **Color Map Validation**: Validate color definitions and glyph mappings
  - **Transparency Validation**: Check transparency glyph usage and alpha value consistency
  - **Performance Validation**: Detect inefficient color usage and suggest optimizations
  - **Cross-Format Compatibility**: Ensure compatibility between compact and animated formats
- **Validation Rules**:
  - **TOML Syntax**: Valid TOML structure and syntax
  - **Sprite Section**: Required fields (name, pixels) and proper format
  - **Animation Section**: Valid animation structure with proper frame data
  - **Color Section**: Valid color definitions with proper RGB/RGBA values
  - **Transparency Glyph**: Proper usage of `█` glyph (implied constant, not defined in colors)
  - **Frame Consistency**: Consistent frame dimensions and pixel data
  - **Animation Timing**: Valid frame intervals and duration values
- **Linting Features**:
  - **Error Detection**: Identify syntax errors, missing fields, and invalid values
  - **Warning System**: Flag potential issues and suggest improvements
  - **Format Suggestions**: Recommend optimal format (compact vs animated) based on content
  - **Color Optimization**: Suggest color palette optimizations and unused color removal
  - **Performance Analysis**: Analyze sprite efficiency and suggest improvements
- **Output Formats**:
  - **Console Output**: Detailed error/warning messages with line numbers
  - **JSON Report**: Machine-readable validation results for CI/CD integration
  - **HTML Report**: Visual validation report with highlighted issues
  - **Fix Suggestions**: Automatic fix suggestions for common issues
- **Integration Features**:
  - **CLI Tool**: Command-line interface for batch validation
  - **IDE Integration**: Integration with development environments
  - **CI/CD Integration**: Automated validation in build pipelines
  - **Real-time Validation**: Live validation during sprite editing
- **Advanced Features**:
  - **Custom Rules**: User-defined validation rules and constraints
  - **Rule Sets**: Predefined rule sets for different sprite types
  - **Batch Processing**: Validate multiple sprite files simultaneously
  - **Format Migration**: Suggest and perform format migrations
- **Technical Requirements**:
  - TOML parsing and validation engine
  - Sprite format specification compliance checker
  - Color palette analysis and optimization
  - Performance analysis algorithms
  - Integration with existing sprite loading system
- **Files to Create/Modify**:
  - `glitchygames/tools/sprite_linter.py` - Core linting engine
  - `glitchygames/tools/format_validator.py` - Format validation system
  - `glitchygames/tools/color_analyzer.py` - Color palette analysis
  - `glitchygames/tools/sprite_optimizer.py` - Performance optimization suggestions
  - `glitchygames/tools/cli_linter.py` - Command-line interface
  - `tests/tools/test_sprite_linter.py` - Linter validation tests
  - `tests/tools/test_format_validator.py` - Format validation tests
- **Validation Categories**:
  - **Critical Errors**: Syntax errors, missing required fields, invalid data types
  - **Warnings**: Potential issues, inefficient usage, deprecated patterns
  - **Suggestions**: Optimization opportunities, format improvements, best practices
  - **Info**: Format information, statistics, and analysis results
- **Format Specifications**:
  - **Compact Format**: Single-frame sprites with `[sprite]` section and `pixels` field
    - Uses `[colors."█"]` format (legacy support)
    - Implied `█` glyph for magenta transparency (not defined in colors)
    - Target audience: developers who want simple, readable sprite files
  - **Animated Format**: Multi-frame sprites with `[[animation]]` sections
    - Uses `"█" = { red = 255, green = 0, blue = 255 }` format (legacy support)
    - Implied `█` glyph for magenta transparency (not defined in colors)
    - Target audience: complex animations with multiple frames
- **Future Extensibility**:
  - Support for additional sprite formats (JSON, XML, binary)
  - Custom validation rule engine
  - Integration with sprite generation tools
  - Automated sprite optimization suggestions

### 29. Universal Undo/Redo System
- **Description**: Comprehensive undo/redo system for all editing operations in bitmappy
- **Use Case**: Essential for non-destructive editing, mistake recovery, and professional workflow
- **Status**: Planned
- **Priority**: High
- **Implementation**:
  - **Operation History**: Track all editing operations (pixel changes, frame modifications, etc.)
  - **Multi-Level Undo**: Support for multiple undo levels (default: 50 operations)
  - **Keyboard Shortcuts**: Ctrl+Z for undo, Ctrl+Shift+Z for redo
  - **Controller Support**: Circle button (B) for undo, Square button (X) for redo
  - **Visual Feedback**: Clear indication of undo/redo availability
  - **Memory Management**: Efficient storage of operation history
  - **Cross-Frame Undo**: Undo operations across different frames and animations
  - **Canvas Undo/Redo**: Undo/redo pixel-level changes on the canvas
  - **Film Strip Undo/Redo**: Undo/redo frame-level operations (add, delete, reorder frames)
- **Technical Requirements**:
  - Operation serialization and storage
  - Efficient memory management for history
  - Integration with existing editing systems
  - Performance optimization for large histories
  - **Canvas Integration**: Track pixel-level changes, brush strokes, color changes
  - **Film Strip Integration**: Track frame operations, animation changes, frame reordering
  - **Unified History**: Single undo/redo system that works across both areas
  - **Context Awareness**: Undo/redo operations respect current editing context
- **Files to Create/Modify**:
  - `glitchygames/tools/undo_redo_manager.py` - Core undo/redo system
  - `glitchygames/tools/operation_history.py` - Operation tracking
  - `glitchygames/tools/bitmappy.py` - Integration with main editor
  - `tests/tools/test_undo_redo.py` - Undo/redo system tests

### 30. Pixel-Level Copy/Paste System
- **Description**: Advanced copy/paste functionality for pixel regions within frames
- **Use Case**: Efficient editing of sprite regions, pattern duplication, and detailed sprite work
- **Status**: Planned
- **Priority**: High
- **Implementation**:
  - **Selection Tools**: Rectangular selection, freehand selection, magic wand selection
  - **Copy Operations**: Copy selected regions to clipboard
  - **Paste Operations**: Paste with position control and blending options
  - **Multi-Selection**: Support for multiple selected regions
  - **Transform on Paste**: Rotate, flip, scale during paste operations
  - **Blending Modes**: Normal, overlay, multiply, screen blending options
- **Selection Features**:
  - **Rectangular Selection**: Click and drag to select rectangular areas
  - **Freehand Selection**: Lasso tool for irregular selections
  - **Magic Wand**: Select connected pixels of similar color
  - **Selection Modifiers**: Add to selection (Shift), subtract from selection (Ctrl)
- **Paste Features**:
  - **Position Control**: Precise positioning of pasted content
  - **Blending Options**: Various blend modes for natural integration
  - **Transform Tools**: Rotate, flip, scale pasted content
  - **Preview Mode**: See paste result before confirming
- **Files to Create/Modify**:
  - `glitchygames/tools/selection_tools.py` - Selection system
  - `glitchygames/tools/pixel_clipboard.py` - Pixel-level clipboard
  - `glitchygames/tools/transform_tools.py` - Transform operations
  - `glitchygames/tools/bitmappy.py` - Integration with main editor
  - `tests/tools/test_selection_tools.py` - Selection system tests

### 31. Multi-Frame Copy/Paste System
- **Description**: Copy and paste entire animations or frame sequences
- **Use Case**: Animation workflow efficiency, pattern reuse, and animation composition
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Frame Sequence Copy**: Copy multiple consecutive frames
  - **Animation Copy**: Copy entire animations with all frames
  - **Cross-Animation Paste**: Paste frames between different animations
  - **Frame Insertion**: Insert copied frames at specific positions
  - **Animation Merging**: Combine multiple animations
  - **Timing Preservation**: Maintain original frame timing and duration
- **Workflow Features**:
  - **Frame Range Selection**: Select start and end frames for copying
  - **Animation Browser**: Visual interface for selecting animations to copy
  - **Paste Options**: Insert, replace, or append frames
  - **Timing Control**: Adjust timing when pasting frames
- **Files to Create/Modify**:
  - `glitchygames/tools/animation_clipboard.py` - Animation clipboard system
  - `glitchygames/tools/frame_sequence_manager.py` - Frame sequence handling
  - `glitchygames/tools/bitmappy.py` - Integration with main editor
  - `tests/tools/test_animation_clipboard.py` - Animation clipboard tests

### 32. Advanced Clipboard Operations
- **Description**: Enhanced clipboard system with multiple slots and history
- **Use Case**: Professional workflow with multiple clipboard items and advanced operations
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Multiple Clipboard Slots**: Store multiple copied items (default: 10 slots)
  - **Clipboard History**: Access previously copied items
  - **Clipboard Browser**: Visual interface for managing clipboard items
  - **Format Support**: Support for different data formats (pixels, frames, animations)
  - **Clipboard Persistence**: Maintain clipboard across sessions
- **Advanced Features**:
  - **Clipboard Preview**: Thumbnail previews of clipboard items
  - **Clipboard Search**: Search through clipboard history
  - **Clipboard Export**: Save clipboard items to files
  - **Clipboard Import**: Load clipboard items from files
- **Files to Create/Modify**:
  - `glitchygames/tools/advanced_clipboard.py` - Advanced clipboard system
  - `glitchygames/tools/clipboard_browser.py` - Clipboard management UI
  - `glitchygames/tools/bitmappy.py` - Integration with main editor
  - `tests/tools/test_advanced_clipboard.py` - Advanced clipboard tests

### 33. Selection and Transform Tools
- **Description**: Comprehensive selection and transformation tools for sprite editing
- **Use Case**: Professional sprite editing with precise selection and transformation capabilities
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Selection Tools**:
    - Rectangular selection with precise positioning
    - Freehand/lasso selection for irregular shapes
    - Magic wand selection for color-based selection
    - Selection modification (add, subtract, intersect)
  - **Transform Tools**:
    - Rotate selected regions (90°, 180°, 270°, custom angles)
    - Flip selected regions (horizontal, vertical)
    - Scale selected regions (uniform and non-uniform scaling)
    - Skew and perspective transforms
  - **Selection Management**:
    - Save and load selections
    - Selection preview and confirmation
    - Selection constraints (aspect ratio, grid alignment)
- **Files to Create/Modify**:
  - `glitchygames/tools/selection_tools.py` - Selection system
  - `glitchygames/tools/transform_tools.py` - Transform operations
  - `glitchygames/tools/bitmappy.py` - Integration with main editor
  - `tests/tools/test_transform_tools.py` - Transform tools tests

### 34. System Clipboard Integration
- **Description**: Integration with system clipboard for external tool compatibility
- **Use Case**: Copy/paste between bitmappy and other applications, external tool workflow
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - **System Clipboard Support**: Copy/paste to/from system clipboard
  - **Format Conversion**: Convert between bitmappy formats and standard formats
  - **Image Export**: Export selections as standard image formats
  - **External Tool Integration**: Work with external image editors
- **Supported Formats**:
  - PNG export/import for image data
  - JSON export/import for animation data
  - Custom format for bitmappy-specific data
- **Files to Create/Modify**:
  - `glitchygames/tools/system_clipboard.py` - System clipboard integration
  - `glitchygames/tools/format_converter.py` - Format conversion utilities
  - `glitchygames/tools/bitmappy.py` - Integration with main editor
  - `tests/tools/test_system_clipboard.py` - System clipboard tests

### 35. Undo/Redo Visualization
- **Description**: Visual representation of undo/redo history for better workflow understanding
- **Use Case**: Advanced users who need to understand their editing history and navigate complex undo stacks
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - **History Timeline**: Visual timeline of all operations
  - **Operation Previews**: Thumbnail previews of each operation
  - **Branch Navigation**: Navigate different undo branches
  - **Operation Details**: Detailed information about each operation
  - **History Search**: Search through operation history
- **Visual Features**:
  - **Timeline View**: Horizontal timeline of operations
  - **Thumbnail Grid**: Grid view of operation snapshots
  - **Operation Tree**: Tree view of operation relationships
  - **Filter Options**: Filter operations by type, time, or scope
- **Files to Create/Modify**:
  - `glitchygames/tools/undo_visualization.py` - Undo/redo visualization
  - `glitchygames/tools/history_browser.py` - History management UI
  - `glitchygames/tools/bitmappy.py` - Integration with main editor
  - `tests/tools/test_undo_visualization.py` - Undo visualization tests

### 36. Batch Operations
- **Description**: Apply operations to multiple frames, animations, or sprites simultaneously
- **Use Case**: Efficient workflow for repetitive tasks and large-scale sprite operations
- **Status**: Planned
- **Priority**: Low
- **Implementation**:
  - **Multi-Frame Operations**: Apply changes to multiple frames at once
  - **Animation-Wide Changes**: Apply operations to entire animations
  - **Batch Processing**: Process multiple sprites or animations
  - **Operation Templates**: Save and reuse operation sequences
  - **Progress Tracking**: Visual progress indicators for long operations
- **Batch Features**:
  - **Frame Range Operations**: Apply operations to frame ranges
  - **Animation Operations**: Apply operations to multiple animations
  - **Sprite Operations**: Apply operations to multiple sprites
  - **Operation Queuing**: Queue multiple operations for batch execution
- **Files to Create/Modify**:
  - `glitchygames/tools/batch_operations.py` - Batch operation system
  - `glitchygames/tools/operation_templates.py` - Operation template system
  - `glitchygames/tools/bitmappy.py` - Integration with main editor
  - `tests/tools/test_batch_operations.py` - Batch operations tests

### 37. Enhanced Drag-n-Drop Frame Updates
- **Description**: Extend drag-n-drop support to update selected frames or film strips rather than replacing existing content
- **Use Case**: Efficient workflow for updating specific frames, adding frames to animations, and targeted sprite modifications
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Frame-Specific Updates**: Drop files onto specific frames to update them
  - **Film Strip Integration**: Drop files onto film strip positions to insert/update frames
  - **Animation Preservation**: Maintain existing animation structure while updating content
  - **Smart Insertion**: Automatically determine whether to replace, insert, or append frames
  - **Visual Feedback**: Clear indication of drop targets and update operations
- **Update Modes**:
  - **Replace Mode**: Replace selected frame with dropped content
  - **Insert Mode**: Insert new frame at drop position
  - **Append Mode**: Add frame to end of animation
  - **Merge Mode**: Blend dropped content with existing frame
- **Drop Target Detection**:
  - **Frame Drop Zones**: Detect when dropping on specific frames
  - **Film Strip Drop Zones**: Detect when dropping on film strip positions
  - **Animation Drop Zones**: Detect when dropping on animation headers
  - **Smart Positioning**: Automatically position content based on drop location
- **Content Integration**:
  - **Size Matching**: Automatically resize dropped content to match target frame
  - **Format Conversion**: Convert between different sprite formats
  - **Color Palette Integration**: Merge color palettes when combining content
  - **Timing Preservation**: Maintain original frame timing and duration
- **User Experience**:
  - **Visual Drop Indicators**: Show valid drop zones and expected behavior
  - **Preview Mode**: Preview how content will be integrated before confirming
  - **Undo Support**: Full undo/redo support for drag-n-drop operations
  - **Conflict Resolution**: Handle conflicts when dropping incompatible content
- **Advanced Features**:
  - **Batch Frame Updates**: Drop multiple files to update multiple frames
  - **Animation Sequence Import**: Import entire animation sequences
  - **Smart Frame Detection**: Automatically detect frame boundaries in dropped content
  - **Content Validation**: Validate dropped content before integration
- **Technical Requirements**:
  - Enhanced drop zone detection system
  - Content integration and conversion algorithms
  - Visual feedback and preview system
  - Integration with existing undo/redo system
- **Files to Create/Modify**:
  - `glitchygames/tools/enhanced_drag_drop.py` - Enhanced drag-n-drop system
  - `glitchygames/tools/frame_updater.py` - Frame update operations
  - `glitchygames/tools/content_integration.py` - Content integration utilities
  - `glitchygames/tools/bitmappy.py` - Integration with main editor
  - `glitchygames/tools/film_strip.py` - Enhanced film strip drop handling
  - `tests/tools/test_enhanced_drag_drop.py` - Enhanced drag-n-drop tests

### 38. Frame Alignment Command
- **Description**: A Bitmappy command that permanently re-aligns an animation's frames to a common anchor point, rewriting the pixel data
- **Use Case**: Art drawn top-aligned (like the Papyrus player, whose feet end on rows 24–27 depending on the frame) makes feet drift between frames. The engine can compensate at draw time with `AnimatedSprite.frame_anchor` (`FrameAnchor`), but fixing the art itself makes it correct everywhere, including Bitmappy's own preview, and removes the need for the setting
- **Status**: Planned
- **Priority**: Medium
- **Implementation**:
  - **Alignment modes**: The nine `FrameAnchor` points: top-left, top, top-right, left, center, right, bottom-left, bottom, bottom-right (e.g. bottom for walkers, center for spinners and floaters, top for hanging things)
  - **Reference**: Each frame's hitbox if defined, else its visible-pixel bounds; aligned to the sprite-level hitbox, else the union of all frames' hitboxes
  - **Rewrite**: Shift each frame's pixels within the fixed canvas and shift its per-frame hitbox by the same amount; refuse (with a message) when a shift would push visible pixels off the canvas
  - **Undo**: One undoable operation through the existing undo/redo system
  - **Preview**: Show the aligned animation before applying
  - **After applying**: Clear `frame_anchor` on the sprite if it was set, since the art no longer needs it
- **Files to Create/Modify**:
  - Bitmappy film strip / animation menu (new command)
  - `tests/tools/` - Alignment tests: every mode, hitbox shift, off-canvas refusal, undo

### 42. Sound Effects From a Description
- **Description**: Describe a sound effect in words ("a short wet pop, like a bubble bursting
  underwater", "a heavy mechanical clunk, then a slow hiss") and the engine works out how to make it:
  an LLM (or a rule-based process) plans one or more source sounds, and a chain of audio
  operations shapes them into the sound you asked for
- **Use Case**: Fast, reproducible sound design for games without a sound library or audio tools;
  iterate in plain language ("punchier", "an octave lower", "make the tail longer")
- **Status**: Planned (requested 2026-10-23)
- **Priority**: Medium
- **Implementation**:
  - **Plan from the description**: the LLM (through the existing AI client used for sprite
    generation, `glitchygames/ai/`) returns a structured plan (a pydantic model, validated): the
    source sounds and the operations to apply, in order. A rule-based fallback maps common words
    (pop, click, thud, whoosh, zap, chirp) to recipes when no model is available
  - **Source sounds**, any of:
    - synthesized: the existing toolkit (`glitchygames/audio/synth.py` oscillators, noise,
      envelopes, pitch curves) and `SoundRecipe`/`Tone` (`glitchygames/audio/recipes.py`)
    - spoken: words or syllables rendered with text-to-speech (`glitchygames/audio/tts.py`)
    - performed: the engine suggests sounds for you to make yourself ("say 'pop' with your lips
      closed", "click your tongue twice", "say 'tsss'") and records them from the microphone
      (the microphone capture script, `scripts/`), then trims the silence
  - **Operations** (the shaping chain, each with parameters the plan chooses):
    - pitch: shift by octaves or semitones, keeping the length (or resample to change both)
    - time: stretch or compress the length without changing the pitch (phase vocoder or a
      granular method), clip to a range, extend (loop with a crossfade, or a decaying tail)
    - dynamics: gain, compression, limiting, hard or soft clipping (distortion), envelope
      (attack, decay, sustain, release)
    - tone: low-, high- and band-pass filters (the existing FIR filters), EQ
    - layering: mix several sources with offsets (a click on top of a thud)
  - **Iterate**: preview the result, then refine with more words; the plan is updated, not
    regenerated from scratch, so a good result isn't lost
  - **Save it reproducibly**: store the plan (sources and operation chain) as a TOML recipe next to
    the rendered sound, so it can be regenerated and edited by hand; recorded sources are saved
    as files the recipe references. Rendering must be deterministic (seeded noise through the
    engine's random streams) so games and replays sound the same everywhere
- **Technical Requirements**:
  - DSP operations on numpy arrays at the mixer's format (44100 Hz, 16-bit, stereo), unit-tested
    against known signals (a sine's pitch after a shift, a length after a stretch)
  - A schema for the plan the LLM returns, with validation and clear errors for bad plans
  - Microphone capture with a device choice and silence trimming
  - An editor or command-line front end (e.g. a `glitchygames-sfx` console script, or a panel in
    Bitmappy or Glitchy Studio)

## Notes

- All features are currently in planning phase
- Implementation timeline will be determined based on project priorities
- Features may be refined or expanded upon during development
- This document will be updated as features are implemented or new features are added

---
*Moved into plans/ on 2026-10-18.*
