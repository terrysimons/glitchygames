# Brave Adventurer Architecture

Brave Adventurer is a Pitfall-style side-scrolling platformer set in ancient Egypt: the
adventurer runs right across 20 screens of desert, jumps stone walls and pits, avoids cobras,
scarab beetles and scorpions, and picks up gold scarabs. Every picture is drawn from pygame
primitives and every sound is synthesized at startup, so the game ships no asset files.

The **Papyrus Edition** is the same game with hand-drawn TOML pixel art for the player, the
enemies and the collectibles (see [The Papyrus Edition](#the-papyrus-edition) below).

This page is for a developer who wants to understand the game or build one like it. It shows
which engine features the game uses and where its code puts each of them: world-space sprites,
camera follow and parallax layers, the pose rule, hitbox-based terrain collision, ActionMap
input, synthesized sounds, saves, recording and replay.

## Running it

```bash
uv run brave-adventurer            # the primitives edition
uv run brave-adventurer-papyrus    # the Papyrus Edition (TOML pixel art)
```

Both console scripts are declared in `pyproject.toml` and call `main()`, which runs
`GameEngine(game=BraveAdventurerScene).start()` (or `PapyrusBraveAdventurerScene`). The window
is 800 x 480 (`SCREEN_WIDTH`, `SCREEN_HEIGHT` in `constants.py`).

### Controls

The gameplay scene binds every control through one `ActionMap`
(`BraveAdventurerScene._create_action_map`). Keyboard controls are bound by **scancode**, a
physical key position, so they sit in the same place on every keyboard layout.

| Action | Keyboard (by position) | Gamepad | Read how |
|---|---|---|---|
| `move_right` | Right arrow | D-pad right | held: `is_held()` in `dt_tick` |
| `move_left` | Left arrow | D-pad left | held: `is_held()` in `dt_tick` |
| `jump` | Space or Up arrow | A | press: `get_action()` in the handler |
| `pause` | Esc | none | press |
| `quit` | Q | none | press: `scene_manager.quit()` posts QUIT |
| `mic_toggle` (primitives edition only) | none | DualSense mic button (controller button 15, joystick button 16) | press starts listening, release answers |

The built-in screens the game switches to have their own keys, by key code:

| Screen | Keys |
|---|---|
| Pause (`PauseScene`) | Space (on release) resumes, Esc quits, Q (on release) quits; regaining window focus more than 0.5 s after pausing resumes too |
| Game over (`GameOverScene`) | Space (on release) starts a new game, Esc quits, Q (on release) quits |

The analog sticks move nothing: no axis is bound (`TestButtonsAndAxesHoldMovement` pins it).

### Options

The scene's `args()` adds one option of its own; everything else is the engine's (see
[Argument System](../architecture/argument_system.md)).

| Option | Where | Effect in this game |
|---|---|---|
| `-v`, `--version` | `BraveAdventurerScene.args()` | Declared ("print the game version and exit"), but nothing reads it yet: the game starts normally (BUGS.md #178, item 25) |
| `--input-mode {auto,joystick,controller}` | engine | Passed to the `ActionMap`: which gamepad event family the D-pad, A and mic bindings answer |
| `--screen-shake-intensity` | engine | Passed to `Camera2D(shake_intensity=...)`; the game itself starts no shakes |
| `--rumble-intensity` | engine | Scales the death and game-over rumble pulses |
| `--target-fps` | engine | The scene sets no `TARGET_FPS`, so the default 60.01 applies |
| `--debug-overlay` (or F3, F4) | engine | Hitboxes by collision layer, physics, camera and performance panels |
| `--record-trace`, `--replay-trace`, `--headless` | engine | Record and replay a session (see [Recording, replay and golden tests](#recording-replay-and-golden-tests)) |

## Scenes and how they switch

The game is one gameplay scene plus the engine's built-in pause and game-over screens. Every
switch is a plain `next_scene` assignment or `switch_to_scene`; the game uses no transitions.

```mermaid
flowchart TB
    start(["main#40;#41;: GameEngine#40;game=BraveAdventurerScene#41;.start#40;#41;"])
    play["BraveAdventurerScene<br/>the gameplay scene"]
    pause["PauseScene<br/>the frozen game under a translucent overlay"]
    over["GameOverScene<br/>final score and the top 5 high scores"]
    fresh["a new BraveAdventurerScene<br/>type#40;previous_scene#41;#40;options=...#41;"]
    quit(["QUIT: the run ends"])

    start --> play
    play -->|"Esc: _pause_game#40;#41; sets next_scene"| pause
    pause -->|"Space released, or focus regained:<br/>resume#40;#41; switches back to the same scene"| play
    play -->|"last life lost: _player_die#40;#41;<br/>saves the high score, sets next_scene"| over
    over -->|"Space released: resume#40;#41;"| fresh
    play -->|"Q"| quit
    pause -->|"Esc, or Q released"| quit
    over -->|"Esc, or Q released"| quit
```

Resuming from the pause screen switches back to the *same* scene object, so the game picks up
where it stopped; its `setup()` runs again (it only rebuilds the HUD font and re-follows the
player; the sounds are generated once). The pause screen's `debug_subject` is the paused game,
so the debug overlay keeps showing the game's hitboxes over the frozen picture.

The game-over screen does not resume the old scene: `GameOverScene.resume()` builds a new
instance of the previous scene's class with the same options, so a restart is a clean game
(and the Papyrus Edition restarts as the Papyrus Edition).

## The world

### World-space sprites and the camera

Every game object is a world-space sprite: it declares
`COORDINATE_SPACE = CoordinateSpace.WORLD` and keeps float `world_x` / `world_y`. The game
never writes a sprite's `rect`; the engine places each world sprite from the camera every
frame, snapping with the scene's default `PIXEL_SNAP_MODE` (`NEAREST_HALF_UP`), and culls the
ones off screen. Only the HUD is drawn in screen space, straight onto the display in `render()`.

The camera is a `Camera2D` built in `__init__`:

| Setting | Value | Effect |
|---|---|---|
| `lead_x` | `CAMERA_LEAD` = 250 | The camera aims 250 px left of the player, so the player runs at about x = 250 on screen with the view ahead of it |
| `set_bounds(min_x=0.0)` | left bound only | The camera never shows the world left of x = 0; there is no right or vertical bound |
| `follow(target=self.player, axes=FollowAxes.X)` | in `setup()` | The engine aims the camera at the player on x only: the camera stays at the top of the world |
| smoothing | the default `smooth_factor` 0.1 | The camera eases toward its goal; with no `snap_to()` in `setup()` it eases in from the origin |
| `follow(target=None)` | at game over | The world and the camera stand still behind the game-over switch |

The scene never calls `camera.update()`: the engine aims the camera after logic and events, and
then positions the sprites (frame steps 5 and 6 in the next section).

### Parallax layers

Four background layers are added with `camera.add_background_layer(...)`, drawn by the
functions in `drawing.py`. Each draw function depends only on its arguments (the layer's
offset), so the engine redraws a layer only when its offset changes; none needs
`animated=True`.

| Depth | Layer | `scroll_factor` | Draw function | What it draws |
|---|---|---|---|---|
| 0 | sky | `PARALLAX_SKY` = 0.0 | `draw_sky` | A blue-to-haze vertical gradient (built once per surface size) |
| 1 | far | `PARALLAX_FAR` = 0.1 | `draw_pyramids` | A sand plane from y = 300 and three pyramids repeating every 2400 px |
| 2 | mid | `PARALLAX_MID` = 0.3 | `draw_dunes_and_oasis` | Dunes from three summed sine waves, oases repeating every 3000 px |
| 3 | near | `PARALLAX_NEAR` = 0.7 | `draw_near_ground_details` | Rocks and grass tufts every 60 px, placed by a hash of the world x (no randomness) |

The sprites sit above them on layers 4 to 7: terrain, collectibles, enemies, then the player
(`LAYER_*` in `constants.py`).

### Levels and screens

A level is a list of `ScreenData`, one per 800 px screen. Each screen lists its content in
screen-local x (and y for collectibles):

| `ScreenData` field | Entries | Becomes |
|---|---|---|
| `ground_segments` | `(local_x, width)` | `GroundSegment` at `GROUND_Y` = 400, 80 px tall |
| `walls` | `(local_x, height)` | `StoneWall`, 32 px wide, standing on the ground |
| `enemies` | `(type_name, local_x, kwargs)` | `Cobra`, `Scarab(speed=...)` or `Scorpion(patrol_range=...)` |
| `collectibles` | `(local_x, local_y)` | `GoldScarab` |

`LEVEL_1` ("The Path of the Pharaoh") has 20 screens of rising difficulty: flat ground with
scarabs to collect, a first short wall (screen 2), a first pit (screen 4), the first cobra
(5), scarab (7) and scorpion (10), then combinations, a triple pit (16), a gauntlet (18) and a
collectible run (19). `LevelManager` builds it once, in the scene's `__init__`:

```mermaid
flowchart TB
    level["LEVEL_1<br/>20 ScreenData, one per 800 px screen"]
    build["LevelManager._build#40;#41;<br/>world x = screen index × 800 + local x"]
    map["_get_enemy_class_map#40;#41;<br/>'cobra', 'scarab', 'scorpion' to classes<br/>#40;an unknown name is skipped#41;"]
    group["the scene's all_sprites<br/>#40;LayeredDirty, drawn by layer#41;"]
    lists["ground_sprites, wall_sprites,<br/>enemy_sprites, collectible_sprites"]
    layers["collision layers<br/>'player', 'enemies', 'collectibles'"]
    terrain["terrain collision code in the scene<br/>#40;ground and wall lists#41;"]

    level --> build
    map --> build
    build -->|"every sprite joins"| group
    build -->|"and one list per kind"| lists
    lists -->|"enemies, collectibles"| layers
    lists -->|"ground, walls"| terrain
```

The scene adds the player to the `'player'` layer and every enemy and collectible to theirs;
sprite-against-sprite contact goes through `self.collisions.check_overlap(...)`. Ground and
walls are not in collision layers: the scene resolves terrain itself (below).

There is no goal at the end of the level: past screen 19 there is no ground.

### Pits and walls

**Pits** are the gaps between consecutive ground segments. Nothing in the world represents a
pit; `render()` draws each one (`_draw_pits`) after the sprites, between the drawn rects of the
two segments either side, so the pit edges always meet the ground even at a half-pixel camera
position. The player is then blitted once more so it shows in front of the pit while falling.
Inside a pit the edges of the neighbouring segments act as walls, so the player cannot walk
out; falling more than `PIT_DEATH_THRESHOLD` (100 px) below the screen costs a life.

**Walls** (`StoneWall`) are both platform and obstacle: a player whose feet land within 16 px
of a wall's top stands on it; otherwise a player overlapping the wall's body is pushed out to
the side it came from (see [Collision](#collision)).

### Enemies and collectibles

| Sprite | Behaviour (in `dt_tick`) |
|---|---|
| `Cobra` | Stationary; strikes for 0.3 s every 2 s (`STRIKE_INTERVAL`, `STRIKE_DURATION`) |
| `Scarab` | Rolls at `roll_speed` (negative is left) under gravity; the scene lands it on ground segments or on a pit floor and reverses it at walls |
| `Scorpion` | Walks at 60 px/s between its origin and origin + `patrol_range`, turning at each end |
| `GoldScarab` | Bobs 4 px up and down (`sin(time × 3)`); worth `COLLECTIBLE_SCORE_BONUS` |

Touching any enemy costs a life. The primitives edition's enemies redraw their image in
`update()`, the render phase (the player does not: see the pose rule below).

## The player

### Movement and physics

`Player` composes a `PhysicsBody` (`glitchygames.physics`) instead of moving itself. Its
`world_x`, `world_y`, `velocity_x`, `velocity_y`, `on_ground` and `facing_right` are properties
that read and write the body.

| Part | Setting | Effect |
|---|---|---|
| `GravityBehavior` | `GRAVITY` = 1200 px/s², `MAX_FALL_SPEED` = 800 px/s | Falls, with a terminal speed |
| `AccelerationBehavior` | `PLAYER_ACCELERATION` = 1600, `PLAYER_DECELERATION` = 1200 px/s² | Ramps toward a target speed: `move_right()` / `move_left()` set ±`PLAYER_RUN_SPEED` (200 px/s), `stop_horizontal()` sets 0 |
| `BoundsConstraint(min_x=...)` | the world's left edge | Refitted to the hitbox every tick (`_fit_world_edge_to_hitbox`), so the hitbox, not the image's transparent margin, stops at x = 0 |
| `jump()` | `JUMP_VELOCITY` = -500 px/s | Only when `on_ground` |

There is no ground constraint in the body: the scene decides whether the player stands on
something. An `AnimationStateMachine` (rules written in code in the primitives edition) picks
the pose from the body's animation context: idle, running, jumping or falling.

### The pose rule

The player draws its pose, and so its hitbox, in `dt_tick`, after physics and the state
machine and before the scene's collision runs. Its hitbox is the image's visible pixels
(the engine trims transparent margins), so drawing the pose in `update()` would make collision
use the previous frame's pose: a player turning toward a wall would sit inside it for a frame
(BUGS.md, the pose fix). After drawing, the world-edge bound is refitted to the new hitbox and
applied again. `update()` does visual work only: the respawn fade
(`image.set_alpha(...)`).

### Collision

The scene resolves terrain in `dt_tick`, from the player's collision rect
(`get_sprite_collision_rect`) and offset (`collision_rect_offset`), never from its `rect` or its
drawn size:

| Check | Rule |
|---|---|
| Standing support | The player's support span is `common_hitbox_x_range()`: the columns **every** pose covers for the current facing, measured once by drawing every pose over two seconds of animation. A wider pose (falling is wider than idle) cannot catch a ledge the idle pose has left, so a player at an edge never falls, lands and falls again |
| Ground | The trailing foot (the back edge of the support span; the middle when still) must be over a segment, the hitbox bottom at or below `GROUND_Y`, and the player not rising. Then it is set so the hitbox bottom (the visible feet) rests on the ground |
| Pit edges | While below ground and not supported, moving into a segment's side puts the hitbox flush against it |
| Wall top | Feet within 16 px of the top, head above it, not rising, and the support span over the wall |
| Wall side | Pushed out on the side the hitbox was on before this frame's move (`velocity_x × dt` back), so a dt hitch cannot carry a fast player through; if it already overlapped (a wider pose), the side of the wall's centre decides (`_entered_wall_from_left`) |
| Snapping | Terrain edges are taken where the engine draws them (`snapped_world_position`), so collision agrees with the picture |
| Enemies | `check_overlap('player', 'enemies')`: one death per pass even when touching two enemies; none while respawning |
| Collectibles | `check_overlap('player', 'collectibles')`: score, sound, the scarab removed from the group, its list and its layer |

### Death and respawn

```mermaid
flowchart TB
    hit["an enemy hitbox overlaps,<br/>or the player fell 100 px below the screen"]
    die["_player_die#40;#41;: lives -= 1"]
    respawn["death sound, death rumble pulse<br/>_respawn_player#40;#41;: is_respawning = True, velocities 0"]
    fadeout["tween alpha to 0 over 0.2 s"]
    place["back 200 px #40;RESPAWN_OFFSET#41;, on the ground,<br/>is_respawning = False"]
    fadein["tween alpha to 255 over 0.3 s"]
    over["game_over_triggered = True, camera stops following<br/>game-over sound and rumble pulse<br/>_save_high_score#40;#41;, next_scene = GameOverScene"]

    hit --> die
    die -->|"lives left"| respawn
    respawn --> fadeout
    fadeout --> place
    place --> fadein
    die -->|"no lives left"| over
```

While `is_respawning` is set, movement input, enemy contact and the pit-death check are
skipped. The fades are scene tweens (`self.tweens`), which `Scene.dt_tick` advances by the
frame's dt. Once `game_over_triggered` is set, `dt_tick` returns at once, so nothing moves on
the last frame before the switch.

## One frame

The engine runs the frame (CLAUDE.md, SceneManager); the scene's `dt_tick` does all the game
logic in a fixed order, and its `render()` draws.

```mermaid
flowchart TB
    begin["1. begin the frame"]
    subgraph logic["2. logic: dt_tick#40;dt#41;"]
        direction TB
        input["movement input"]
        tick["every sprite's dt_tick"]
        collide["terrain collision"]
        contact["deaths and pickups"]
        score["distance score"]
        input --> tick --> collide --> contact --> score
    end
    events["3. event handlers"]
    aim["5. camera aim"]
    position["6. position and cull"]
    render["7. update#40;#41;, then render#40;#41;"]
    present["9-10. present and pace"]

    begin --> logic --> events --> aim --> position --> render --> present
```

| Step | Who | What happens in Brave Adventurer |
|---|---|---|
| 2, movement input | the scene | `Scene.dt_tick` (dt, tweens; the scene returns here once game over is set), then `actions.begin_frame()` and `is_held('move_right' / 'move_left')` set the player's target speed (skipped while respawning); the primitives edition also collects voice assistant responses |
| 2, every sprite's `dt_tick` | the sprites | Player physics, state machine and pose; enemy movement; collectible bobbing |
| 2, terrain collision | the scene | Ground (then the landing sound), walls, then scarabs against ground and walls |
| 2, deaths and pickups | the scene | The pit-death check and enemy contact (both skipped while respawning), then collectibles |
| 2, distance score | the scene | `max_distance`, then `score = round(max_distance / 10)` |
| 3 | the handlers | Jump, pause, quit and the mic button (`on_*_event`) |
| 5, 6 | the engine | Aims the camera at the player (x only), then positions and culls every world sprite |
| 7 | `Scene.update()`, `render()` | The player's fade and the primitive enemies' redraws; then sky fill, sprites, pits, the player again, the HUD |
| 9, 10 | the engine | Present the frame, pace it |

(Steps 4 and 8, shake and rumble and the still-camera shake, do nothing visible here: the game
starts no shakes, and its rumble pulses run on their own.)

Two things follow from this order:

- `dt_tick` runs before the frame's events, so movement uses the `ActionMap` state from the
  previous frame's events, and a jump pressed this frame takes effect in this frame's handler
  (its physics in the next `dt_tick`).
- Collision runs before the engine positions the sprites, so this frame's picture already
  shows the resolved positions. Game logic never reads a world sprite's `rect` (it holds where
  the sprite was last drawn); only `_draw_pits`, in the render phase, does.

`render()` replaces `Scene.render`: it fills the sky colour, draws the `LayeredDirty` group,
draws the pits and the player on top, then the HUD (score top left, lives top right, each with
a 1 px shadow), and sets `self.rects = None` so the whole screen is presented.

## Input

```mermaid
sequenceDiagram
    participant SDL as SDL queue
    participant Engine as GameEngine and SceneManager
    participant Scene as BraveAdventurerScene
    participant Actions as ActionMap
    participant Player

    Note over Scene,Player: dt_tick, before this frame's events
    Scene->>Actions: begin_frame()
    Scene->>Actions: is_held('move_right')
    Actions-->>Scene: True (held since an earlier KEYDOWN)
    Scene->>Player: move_right() sets the target speed
    Note over SDL,Engine: event processing
    SDL->>Engine: KEYDOWN (scancode of Space)
    Engine->>Scene: on_key_down_event(event)
    Scene->>Actions: handle_event(event) updates held state
    Scene->>Actions: get_action(event)
    Actions-->>Scene: 'jump'
    Scene->>Player: jump() (sound first when on the ground)
```

Held actions (`move_right`, `move_left`) are read once per frame in `dt_tick` with
`is_held()`; one-shot actions (`jump`, `pause`, `quit`, `mic_toggle`) are read from the event
in the handlers with `get_action()`. Every handler first calls `actions.handle_event(event)`,
key-up and button-up handlers included, so the held state follows the device. The handlers are
`on_key_down/up_event`, `on_controller_button_down/up_event`, `on_joy_button_down/up_event`
and `on_joy_axis_motion_event` (which only feeds the map). A key that maps to no action falls
through to `Scene.on_key_down_event`.

**Gamepads.** The D-pad and A are bound as `controller_button=...`; the `ActionMap` built with
the scene's `input_mode` turns that into controller events, joystick events or both. The scene
reads `self.options.get('input_mode', 'joystick')`; the engine's `--input-mode` default is
`auto`, so a normal run binds both families and the engine delivers each press once.

**Microphone (primitives edition).** `VoiceAssistant.discover()` (in `__init__`) looks for a
controller with both a microphone and a speaker (a DualSense) and returns `None` when there is
none. Pressing the mic button starts listening; releasing it sends the recording through
speech-to-text, an AI model and text-to-speech back to the controller's speaker, and
`dt_tick` collects finished responses (`voice_assistant.update()`). The DualSense reports its
mic button as 15 on the controller API and 16 on the raw joystick API, so both are bound
(`MIC_BUTTON_CONTROLLER`, `MIC_BUTTON_JOYSTICK`). The Papyrus Edition has no voice assistant.

## Sound

`sounds.py` generates five effects once, in `setup()` (`GameSounds.initialize()`), with the
engine's synthesizer toolkit (`glitchygames.audio.synth`: `oscillator`, `frequency_curve`,
`apply_envelope`, `concatenate`, `to_sound`), at the mixer's sample rate:

| Sound | Made of | Played when |
|---|---|---|
| jump | a 0.12 s sine sweep, 220 to 660 Hz | jump pressed while on the ground |
| land | a 0.06 s 80 Hz thud | airborne before this frame's physics, on the ground after collision |
| collect | C5, E5, G5, 0.06 s each | a gold scarab is picked up |
| death | a 0.3 s sweep, 500 to 80 Hz | a life is lost |
| game over | E4, C4, then a longer A3 | the last life is lost |

If audio is unavailable (`AudioUnavailableError`), no sound is set and the game plays silent
rather than with some of its sounds; every `play_*()` checks for `None`. The game uses plain
one-shot `pygame.mixer.Sound`s: no `SoundRecipe` files and no live voices.

## State, score and saves

| State | Where | Rule |
|---|---|---|
| Lives | `player.lives`, from `STARTING_LIVES` = 3 | One per death; game over at 0 |
| Score | `player.score` | `round(max_distance / DISTANCE_SCORE_DIVISOR)`: the furthest world x reached, over 10, set at the end of every `dt_tick`. A collected scarab adds `COLLECTIBLE_SCORE_BONUS` (100) to `score`, but the distance score replaces it later in the same tick |
| High scores | `open_saves(app_name='brave-adventurer')` (Papyrus: `'brave-adventurer-papyrus'`), save `'high_scores'` | `{'scores': [{'score': n}, ...]}`, the ten best, descending; written at game over and shown (top 5) on the game-over screen |

`open_saves` returns the door's `SaveManager`: a `DiskSaveManager` live, an in-memory one in a
replay, so a replayed game over never touches real saves.

## Engine features it uses

| Feature | How Brave Adventurer uses it |
|---|---|
| World space and culling | Every game sprite is `CoordinateSpace.WORLD`; the engine positions and culls them |
| Camera follow and parallax | `follow(target=player, axes=FollowAxes.X)`, a left bound, four parallax layers |
| Physics | `PhysicsBody` with `GravityBehavior`, `AccelerationBehavior`, `BoundsConstraint` |
| Collision layers and hitboxes | `'player'`, `'enemies'`, `'collectibles'` with `check_overlap`; visible-pixel hitboxes |
| Tweens | The respawn fade (`self.tweens.tween(target=player, property_name='alpha', ...)`) |
| Rumble | `scene_manager.rumble.pulse(...)` on death (0.7 / 0.4, 0.35 s) and game over (1.0 / 0.6, 0.8 s); the game-over pulse is finite, so it outlives the switch |
| Screen shake | Only the camera's `shake_intensity` setting; the game calls no `shake()` |
| Random streams | Not needed: nothing in the game is random (the near-ground details are a hash of the world x) |
| Saves | High scores through `open_saves` |
| Built-in scenes | `PauseScene`, `GameOverScene` |
| Debug overlay | F3 / F4: the collision layers' hitboxes, the player's velocities and ground state, the camera; no `debug_draw` of its own |
| Recording and replay | Every input comes through the engine's doors (ActionMap events, saves), so `--record-trace` and `--replay-trace` reproduce a session exactly |
| Transitions, instant replay, demos | Not used |

## Recording, replay and golden tests

Because the game takes input only from engine events, and has no randomness and no clock reads
of its own, a recording replays it exactly:

```bash
uv run brave-adventurer --record-trace /tmp/session.jsonl.gz
uv run brave-adventurer --replay-trace /tmp/session.jsonl.gz            # watch it
uv run brave-adventurer --replay-trace /tmp/session.jsonl.gz --headless # check it
```

Two kinds of golden test pin the game's behaviour frame by frame:

| Golden | File | Made by | What it checks |
|---|---|---|---|
| Golden replay | `tests/fixtures/replays/brave-adventurer/golden.jsonl.gz` (and `brave-adventurer-papyrus/`) | `scripts/record_scripted_session.py --game brave_adventurer --frames 400` through the real engine loop: the golden input script, then a controls tail (walk left, jump with Space, quit with Q): 472 frames | Replayed in a child process with `--replay-trace PATH --headless` by the replay pytest plugin; any divergence fails. `tests/replay/test_golden_replays.py` also checks that every bound control is exercised, or listed with the reason it is not (no gamepad on the dummy driver) |
| Golden trace | `tests/world/golden/brave_adventurer.jsonl.gz` (and `brave_adventurer_papyrus.jsonl.gz`) | `scripts/record_golden_traces.py`, before the world-space change | `tests/world/test_golden_traces.py` replays the script and compares every sprite's rect and visibility with that baseline; every difference must be explained by exactly one `ExpectedDifference` rule (engine culling, separate snapping, the pose fix, scarabs resting on their drawn underside) |

The golden script (`brave_adventurer_script()` in `scripts/record_golden_traces.py`) runs right
over screens 0 and 1 jumping for the higher scarabs, pauses and resumes, then places the
player at x = 2400 (a 900-frame run cannot reach the first pit from the start) and jumps the
two screen-3 walls and the screen-4 pit before walking back. Re-record either golden only
deliberately, after finding out why it changed (the scripts' docstrings give the commands).

## Tests

| Test file | What it pins |
|---|---|
| `tests/examples/test_brave_adventurer_game.py` | Both editions (most fixtures are parametrized over both scenes): rumble on death and game over; terrain from the hitbox (walls flush, wider frames pushed back out, fast players pushed back the way they came, ledges); the world left edge; feet on the ground; stable support at ledge and wall-top edges; Papyrus facing-left hitboxes and foot anchoring; one death per hit; Papyrus falling transitions in TOML; world space (every sprite class declares it, no module positions or culls sprites itself, the camera follows on x and stops at game over); the pose rule (`TestPoseBeforeCollision`); culled enemies keep animating; pits meet the ground at a half-pixel camera; scancode controls; parallax layer pixel digests; game over freezes the world; high scores; jump, quit, D-pad hold and mic buttons; the HUD; both `main()` entry points replaying their golden recordings |
| `tests/examples/test_brave_adventurer_sounds.py` | The synthesized sounds against stored goldens (`tests/examples/brave_adventurer_golden/*.npy`): length, envelope and pitch; silent play without a mixer |
| `tests/world/test_golden_traces.py` | The golden traces above |
| `tests/replay/test_golden_replays.py` and the golden replay items | The golden replays above, and which controls they exercise |
| `tests/collision/test_collision.py` | The Cobra's hitbox follows its drawing; Papyrus hitboxes scale with `SPRITE_SCALE` |
| `tests/examples/test_examples_sprites.py` | The Papyrus TOML sprites load, and their `[[transition]]` sections survive a save round trip |

## The Papyrus Edition

`brave_adventurer_papyrus` keeps the game and changes its characters. It imports the original
package's level data, terrain, drawing, sounds and constants, and replaces the sprites that
have pixel art.

| Shared with the original (imported, unchanged) | Changed in Papyrus |
|---|---|
| `LEVEL_1` and `ScreenData` (re-exported by its `levels.py`) | The player, the three enemies and the gold scarab are `AnimatedSprite`s loaded from TOML files in `sprites/` |
| `GroundSegment` and `StoneWall` (variable-width primitives, which do not suit fixed pixel art) | Sprites are scaled 2x (`SPRITE_SCALE`); TOML hitboxes are in native pixels, so `hitbox_scale` is set to 2 |
| The four parallax draw functions and the pits | The player stands on a fixed foot line, `PAPYRUS_PLAYER_HEIGHT` = 27 × 2 px below its snapped world y, instead of its hitbox bottom |
| `GameSounds` and every sound | Animation state machines come from the TOML `[[transition]]` sections (the player's, the cobra's timed strike) |
| Physics, camera, layer, parallax, scoring and colour constants (re-exported by its `constants.py`) | Its own save namespace (`brave-adventurer-papyrus`) and scene `NAME` |
| The controls (move, jump, pause, quit) | No voice assistant and no mic binding |

### How it is structured

The level manager is reused by subclassing; the scene is a parallel copy. Solid arrows are
inheritance; dotted arrows are runtime use (one class building or calling another). Both
scenes also import the original's `drawing.py`, `sounds.py` and constants (left out to keep
the diagram readable).

```mermaid
classDiagram
    direction TB
    class Scene
    class BraveAdventurerScene
    class PapyrusBraveAdventurerScene
    class LevelManager {
        _build()
        _get_enemy_class_map()
    }
    class PapyrusLevelManager {
        _build()
        _get_enemy_class_map()
    }
    class Sprite
    class AnimatedSprite
    class Player
    class PapyrusPlayer {
        frame_anchor BOTTOM
    }
    class TerrainSprites["GroundSegment, StoneWall"]
    class PrimitiveSprites["Cobra, Scarab, Scorpion, GoldScarab"]
    class PapyrusSprites["PapyrusCobra, PapyrusScarab,<br/>PapyrusScorpion, PapyrusGoldScarab"]

    Scene <|-- BraveAdventurerScene
    Scene <|-- PapyrusBraveAdventurerScene
    LevelManager <|-- PapyrusLevelManager
    Sprite <|-- Player
    Sprite <|-- TerrainSprites
    Sprite <|-- PrimitiveSprites
    AnimatedSprite <|-- PapyrusPlayer
    AnimatedSprite <|-- PapyrusSprites

    PapyrusLevelManager ..> TerrainSprites : builds
    PapyrusLevelManager ..> PapyrusSprites : builds
    LevelManager ..> TerrainSprites : builds
    LevelManager ..> PrimitiveSprites : builds
    BraveAdventurerScene ..> LevelManager : uses
    PapyrusBraveAdventurerScene ..> PapyrusLevelManager : uses
```

- **`PapyrusLevelManager`** overrides `_get_enemy_class_map()` to return the Papyrus enemy
  classes. It also overrides `_build()`, a copy of the original's loop that builds
  `PapyrusGoldScarab` instead of `GoldScarab`, because the base class has no hook for the
  collectible class.
- **`PapyrusBraveAdventurerScene`** is not a subclass of `BraveAdventurerScene`: it is a copy of
  the scene (about 960 lines against 1,010) with the Papyrus classes, the fixed foot line in
  the ground, wall and respawn code (`_snapped_player_top()` + `PAPYRUS_PLAYER_HEIGHT`), and no
  voice assistant. A change to the shared gameplay has to be made in both files; the tests run
  most cases against both scenes to keep them in step.
- **`PapyrusPlayer`** has the same `PhysicsBody` and move methods as `Player`. Each `dt_tick`
  ticks physics, evaluates the TOML state machine, advances the TOML animation
  (`AnimatedSprite.update(self, dt)`), rescales the frame (`apply_transparency_and_scale`), and
  mirrors image and hitbox when facing left (`hitbox_flip_x`), then refits the world-edge
  bound. That keeps the pose rule: the frame collision uses is the one drawn this frame.
  `frame_anchor = FrameAnchor.BOTTOM` draws each frame lower by its `draw_offset`, so frames
  whose feet end on rows 24 to 27 all stand on the 27-row foot line. Its standing support uses
  the engine's `AnimatedSprite.common_hitbox_x_range()` (the x-span every frame's hitbox
  shares) where the original measures its procedurally drawn poses.
- **The Papyrus enemies and gold scarab** do the same, animating in `dt_tick`, and make
  `update()` a no-op (`Scene.update()` would call it without a dt: BUGS.md #115).
- **`sprite_utils.py`**: `prepare_papyrus_sprite()` converts every loaded frame from the
  magenta colour key to per-pixel alpha (so transparency survives scaling and flipping) and sets
  `hitbox_scale`; `apply_transparency_and_scale()` scales the current frame's source surface
  each tick, never the already scaled image.

| Papyrus TOML sprite | Animations | Hitbox | State machine |
|---|---|---|---|
| `player.toml` (20 x 28) | idle, running, jumping, falling | per frame | 8 `[[transition]]`s on velocity and `on_ground` (falling last, mirroring `FALLING_VELOCITY_THRESHOLD`) |
| `cobra.toml` | idle (looping), strike (once) | per frame | idle to strike after 2 s, back after 0.3 s |
| `scarab.toml` | roll | sprite | none |
| `scorpion.toml` | walk | sprite | none |
| `gold_scarab.toml` | shimmer | sprite | none |

`scripts/audit_hitboxes.py` audits the Papyrus sprites' hitboxes against their pixels.

## Where things live

| File | What it holds |
|---|---|
| `glitchygames/examples/brave_adventurer/__init__.py` | Exports `main` (the `brave-adventurer` console script) |
| `glitchygames/examples/brave_adventurer/game.py` | `BraveAdventurerScene`: camera, parallax, level, controls, `dt_tick` order, terrain and enemy collision, death and respawn, high scores, input handlers, `render()`, pits, HUD; `main()` |
| `glitchygames/examples/brave_adventurer/player.py` | `Player`: physics body, state machine, the pose drawn in `dt_tick`, the common pose x-range |
| `glitchygames/examples/brave_adventurer/terrain.py` | `GroundSegment`, `StoneWall`, `GoldScarab` |
| `glitchygames/examples/brave_adventurer/enemies.py` | `Cobra`, `Scarab`, `Scorpion` |
| `glitchygames/examples/brave_adventurer/levels.py` | `ScreenData`, `LEVEL_1` (20 screens), `LevelManager` |
| `glitchygames/examples/brave_adventurer/drawing.py` | Every primitive drawing: the player, enemies, terrain, the four parallax layers |
| `glitchygames/examples/brave_adventurer/sounds.py` | The synthesized effects and `GameSounds` |
| `glitchygames/examples/brave_adventurer/constants.py` | Screen, physics, camera, parallax, layer, size, scoring, colour and rumble constants |
| `glitchygames/examples/brave_adventurer_papyrus/game.py` | `PapyrusBraveAdventurerScene` (the scene's parallel copy); `main()` |
| `glitchygames/examples/brave_adventurer_papyrus/player.py` | `PapyrusPlayer` |
| `glitchygames/examples/brave_adventurer_papyrus/enemies.py` | `PapyrusCobra`, `PapyrusScarab`, `PapyrusScorpion` |
| `glitchygames/examples/brave_adventurer_papyrus/terrain.py` | `PapyrusGoldScarab`; re-exports the shared `GroundSegment` and `StoneWall` |
| `glitchygames/examples/brave_adventurer_papyrus/levels.py` | `PapyrusLevelManager`; re-exports `LEVEL_1` |
| `glitchygames/examples/brave_adventurer_papyrus/sprite_utils.py` | Colour key to alpha, 2x scaling, `hitbox_scale` |
| `glitchygames/examples/brave_adventurer_papyrus/constants.py` | Re-exports the shared constants; `SPRITE_SCALE`, the Papyrus heights, `SPRITES_DIR` |
| `glitchygames/examples/brave_adventurer_papyrus/sprites/*.toml` | The pixel art, hitboxes and state machines |
| `glitchygames/scenes/builtin_scenes/pause_scene.py`, `game_over_scene.py` | The engine's pause and game-over screens |
| `tests/examples/test_brave_adventurer_game.py`, `test_brave_adventurer_sounds.py` | The game's tests |
| `tests/fixtures/replays/brave-adventurer*/golden.jsonl.gz` | The golden replays |
| `tests/world/golden/brave_adventurer*.jsonl.gz` | The golden traces |
| `scripts/record_scripted_session.py`, `scripts/record_golden_traces.py` | The scripts that record them, with the input scripts |
