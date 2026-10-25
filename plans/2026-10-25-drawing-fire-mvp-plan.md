# Drawing Fire MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Drawing Fire MVP: a pencil-on-paper stick-figure battle between the Pencil Platoon and the Graphite Brigade, with pistols, hills and sandbags, that plays itself (computer against computer) and that one or two local players join at any time by pressing START, taking over soldiers, with dual-stick aim and a debug view of who drives each soldier.

**Architecture:** The game also proves a new engine mechanic, **swatches** (Task 4): sprites recoloured in memory by palette swap, from a `[swatches.<set>.<part>]` group in the sprite file. A pure battle model (`battle.py`: soldiers, bullets, sandbags, damage, the winner; no display) is stepped each frame with one `Intent` per living soldier. Every soldier has one driver: the computer (`drivers.py`, seeded game logic, one random stream per soldier) or a player (`players.py`, reading the engine's recorded per-frame `InputSnapshot`: controllers' sticks and buttons, keyboard and mouse). `seats.py` owns joining, choosing a soldier, death takeovers and leaving. The scene (`game.py`) wires them together and draws the pencil look (`drawing.py`); the debug seats view uses the scene's `debug_draw` hook. A simulation script steps the model alone, headless and fast.

**Tech Stack:** Python 3.14, pygame-ce, the GlitchyGames engine (`Scene`, `glitchygames.input.state.current_input`, `glitchygames.randomness.random_stream`), pytest at 100% coverage, ruff (ALL), basedpyright.

**Spec:** `plans/2026-10-25-drawing-fire-design.md` (section 4 is the MVP; sections 1-3 are the vision it must not block).

## Global Constraints

- Package `glitchygames/examples/drawing_fire/`; console script `drawing-fire = "glitchygames.examples.drawing_fire:main"`; scene `DrawingFireScene`, `NAME = 'Drawing Fire'`.
- Armies: `Side.PLATOON` ("Pencil Platoon", pencil yellow `(242, 194, 48)`, left) and `Side.BRIGADE` ("Graphite Brigade", graphite grey `(125, 127, 133)`, right). Never red/blue, never green/tan.
- MVP scope only: pistols; hills; sandbags that lose sand when shot and flatten; no holes, digging, planes, drops, radio, network or Twitch.
- Deterministic: game logic reads time only from `dt` / `Scene.game_time` and randomness only from `glitchygames.randomness.random_stream(...)`; rendering never draws from a random stream. A seat changing hands never shifts another soldier's randomness: one stream per soldier.
- Every player input comes from `current_input()` (the doors' recorded snapshot), never from `pygame.event`, `pygame.key` or `pygame.mouse` directly.
- The rules never depend on who drives a soldier: every driver produces an `Intent`, and the battle applies every `Intent` the same way.
- Repo conventions: single quotes, Google docstrings, no abbreviated names, `# ruff: ignore[rule-name] - reason` (never noqa), no shared mocks (stand-ins defined per test file), tests use real pygame on the dummy driver, 100% coverage.
- Commits stay local; nothing is pushed without the user's say-so.

## Review Focus

1. **A controller unplugged mid-battle or mid-join:** its player leaves; a soldier it drove goes back to the computer that frame. Test in Task 7 (`test_an_unplugged_controller_leaves`).
2. **No computer soldier left to take** (both players on one side, or a death when every survivor is a player): the player waits, marked as waiting, and takes the next soldier that frees up or plays again next battle; nothing crashes. Test in Task 7 (`test_a_death_with_no_free_soldier_waits`).
3. **An aim stick resting in its dead zone:** the soldier keeps aiming where he last aimed (he never snaps to aim right). Test in Task 6 (`test_a_resting_aim_stick_keeps_the_last_aim`).
4. **The last soldier of an army dying while a player chooses a soldier:** the battle ends cleanly; the chooser waits for the next battle. Test in Task 7 (`test_choosing_when_the_battle_ends_waits_for_the_next`).
5. **A different window size** (`--resolution`): the battlefield, hills and sandbags are built for the screen's width and height, and soldiers stand on the ground at any size. Test in Task 1 (`test_terrain_spans_any_screen_width`).

---

### Task 1: Package, terrain with hills, and an empty battlefield on screen

**Files:**
- Create: `glitchygames/examples/drawing_fire/__init__.py` (re-exports `main`), `glitchygames/examples/drawing_fire/terrain.py`, `glitchygames/examples/drawing_fire/game.py`
- Modify: `pyproject.toml` (the console script, next to `mr-muncher`)
- Copy: the brainstorm's pictures (`army-scene*.png`, `camera-battle.png`, `drawing-fire-vignette.png` from the session scratchpad) into `docs/games/drawing_fire/`
- Test: `tests/examples/drawing_fire/test_terrain.py`, `tests/examples/drawing_fire/test_game.py` (with `tests/examples/drawing_fire/__init__.py`)

**Interfaces:**
- Produces: `Terrain` (frozen dataclass: `width: int`, `height: int`, `ground: tuple[float, ...]` one ground y per x pixel); `Terrain.ground_y(x: float) -> float` (clamped to the field, interpolated); `build_terrain(*, width: int, height: int, random: random.Random) -> Terrain`; `GROUND_BASELINE_FRACTION = 0.78` (the flat ground's y as a fraction of the height); `HILL_COUNT_RANGE = (2, 3)`; `HILL_HEIGHT_FRACTION_RANGE = (0.06, 0.14)` (of the height). `DrawingFireScene(Scene)`, `main() -> None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_terrain_has_hills_and_is_seeded():
    first = build_terrain(width=800, height=480, random=random.Random(5))
    again = build_terrain(width=800, height=480, random=random.Random(5))
    assert first == again
    baseline = 480 * GROUND_BASELINE_FRACTION
    assert min(first.ground) < baseline - 480 * HILL_HEIGHT_FRACTION_RANGE[0] / 2  # a hill rises
    assert max(first.ground) <= baseline

@pytest.mark.parametrize(('width', 'height'), [(800, 480), (1280, 720), (320, 240)])
def test_terrain_spans_any_screen_width(width, height):
    terrain = build_terrain(width=width, height=height, random=random.Random(1))
    assert len(terrain.ground) == width
    assert 0 < terrain.ground_y(-50) == terrain.ground[0]
    assert terrain.ground_y(width + 50) == terrain.ground[-1]

def test_the_scene_draws_paper_and_ground(scene):  # a real DrawingFireScene on the dummy display
    scene.render(scene.screen)
    assert scene.screen.get_at((5, 5))[:3] == PAPER_COLOR
```

- [ ] **Step 2: Run them to verify they fail** — `uv run pytest tests/examples/drawing_fire --dummy-only --no-cov -q` → ImportError.
- [ ] **Step 3: Implement** `terrain.py` (hills as smooth bumps, e.g. raised cosines, at seeded positions away from the edges), and a `DrawingFireScene` that builds `self.terrain` from `random_stream('drawing_fire.terrain')` for `(self.screen_width, self.screen_height)`, sets `PAPER_COLOR = (251, 248, 239)` as its background, and draws the ground line; `main()` runs `GameEngine(game=DrawingFireScene).start()`. Add the console script.
- [ ] **Step 4: Run** the tests → PASS; `uv run drawing-fire` opens a window with paper and hills.
- [ ] **Step 5: Commit** — `git commit -m "Drawing Fire: package, seeded hilly terrain, an empty battlefield"`

### Task 2: The battle model: soldiers, pistols, bullets, sandbags, the winner

**Files:**
- Create: `glitchygames/examples/drawing_fire/battle.py`
- Test: `tests/examples/drawing_fire/test_battle.py`

**Interfaces:**
- Consumes: `Terrain` (Task 1).
- Produces:
  - `class Side(enum.StrEnum)`: `PLATOON = 'platoon'`, `BRIGADE = 'brigade'`; `Side.opponent -> Side`; `ARMY_NAMES = {Side.PLATOON: 'Pencil Platoon', Side.BRIGADE: 'Graphite Brigade'}`.
  - `@dataclass(frozen=True) class Intent`: `move: float = 0.0` (-1 left .. 1 right), `aim_angle: float = 0.0` (radians; 0 points right, `math.pi / 2` points up), `fire: bool = False`.
  - `@dataclass class Soldier`: `soldier_id: int`, `side: Side`, `x: float`, `y: float` (feet, on the ground), `health: int`, `aim_angle: float`, `cooldown: float`; `alive -> bool` (`health > 0`); `muzzle -> tuple[float, float]`.
  - `@dataclass class Sandbag`: `x: float`, `width: float`, `sand: float` (1.0 full .. 0.0 flat); `height -> float` (`SANDBAG_HEIGHT * sand`); `flattened -> bool`.
  - `@dataclass class Bullet`: `x`, `y`, `velocity_x`, `velocity_y`, `side: Side`, `distance_left: float`.
  - `@dataclass(frozen=True) class SoldierKilled`: `soldier_id: int`; `@dataclass(frozen=True) class SandbagFlattened`: `index: int`; `type BattleEvent = SoldierKilled | SandbagFlattened`.
  - `class Battle`: `Battle(*, terrain: Terrain, soldiers_per_side: int, sandbag_xs: Sequence[float])`; attributes `terrain`, `soldiers: list[Soldier]` (ids 0.. per side, Platoon first; Platoon spawns in the left fifth, Brigade in the right fifth), `sandbags: list[Sandbag]`, `bullets: list[Bullet]`, `seconds: float`; `living(side: Side) -> list[Soldier]`; `soldier(soldier_id: int) -> Soldier`; `winner -> Side | None` (the side with soldiers left when the other has none); `step(*, dt: float, intents: Mapping[int, Intent]) -> list[BattleEvent]`.
  - Starting numbers (tuned later by the simulations, Task 3): `SOLDIERS_PER_SIDE = 8`, `SOLDIER_HEALTH = 3`, `WALK_SPEED = 60.0` px/s, `PISTOL_COOLDOWN = 0.6` s, `BULLET_SPEED = 600.0` px/s, `PISTOL_RANGE = 420.0` px, `PISTOL_DAMAGE = 1`, `SOLDIER_HIT_RADIUS = 9.0` px, `SANDBAG_HEIGHT = 26.0` px, `SANDBAG_WIDTH = 48.0` px, `SAND_PER_HIT = 0.25`; `sandbag_positions(*, terrain: Terrain, random: random.Random) -> tuple[float, ...]` (two or three per side, on that side's half, away from the spawn fifths).
  - Rules: `step` applies each living soldier's intent (move clamped to ±1 at `WALK_SPEED`, kept on the field; a standing sandbag at least half a soldier tall blocks walking through it; aim is stored; fire spawns a bullet from the muzzle if `cooldown <= 0`, then `cooldown = PISTOL_COOLDOWN`); then moves bullets, which stop at the ground, a sandbag (taking `SAND_PER_HIT`, emitting `SandbagFlattened` when it reaches 0) or an enemy soldier within `SOLDIER_HIT_RADIUS` (`PISTOL_DAMAGE`, emitting `SoldierKilled` at 0); bullets never hit their own side; soldiers missing from `intents` stand still.

- [ ] **Step 1: Write the failing tests** (a flat `Terrain` built in the test file for exact geometry):

```python
def test_armies_spawn_on_their_own_sides():
    battle = flat_battle(soldiers_per_side=4)
    assert all(s.x < battle.terrain.width / 5 for s in battle.living(Side.PLATOON))
    assert all(s.x > battle.terrain.width * 4 / 5 for s in battle.living(Side.BRIGADE))

def test_a_shot_hits_the_enemy_it_is_aimed_at():  # facing soldiers at the same height, no sandbag
    battle, shooter, target = duel(distance=200)
    run(battle, seconds=1.0, intents={shooter.soldier_id: Intent(aim_angle=0.0, fire=True)})
    assert target.health == SOLDIER_HEALTH - 2  # cooldown allows two shots in 1.0 s (0 and 0.6)

def test_three_hits_kill_and_report_it(): ...      # SoldierKilled(target.soldier_id) once; target.alive is False
def test_bullets_never_hit_their_own_side(): ...
def test_a_shot_sandbag_loses_sand_and_flattens(): ...   # four hits: sand 0.75 .. 0.0, SandbagFlattened once
def test_a_standing_sandbag_blocks_walking_and_a_flat_one_does_not(): ...
def test_bullets_stop_at_a_hill(): ...             # a hill between duellists: no damage
def test_out_of_range_shots_fall_away(): ...       # distance_left runs out at PISTOL_RANGE
def test_the_winner_is_the_army_left_standing(): ...  # winner None until one side has no living soldiers
```

- [ ] **Step 2: Run** → fail. **Step 3: Implement** `battle.py`. **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `"Drawing Fire: the battle model (pistols, bullets, sandbags, the winner)"`

### Task 3: The computer driver, and a battle that plays itself (milestone 1)

**Files:**
- Create: `glitchygames/examples/drawing_fire/drivers.py`, `scripts/simulate_drawing_fire.py`
- Modify: `glitchygames/examples/drawing_fire/game.py` (every soldier computer-driven; the battle stepped in `dt_tick`; phases)
- Test: `tests/examples/drawing_fire/test_drivers.py`, `tests/examples/drawing_fire/test_simulation.py`, `tests/examples/drawing_fire/test_game.py`

**Interfaces:**
- Consumes: `Battle`, `Soldier`, `Intent`, `Side` (Task 2).
- Produces:
  - `soldier_stream_name(*, battle_number: int, soldier_id: int) -> str` → `f'drawing_fire.soldier.{battle_number}.{soldier_id}'`.
  - `computer_intent(*, soldier: Soldier, battle: Battle, random: random.Random) -> Intent`: target the nearest living enemy; advance toward it until within `PISTOL_RANGE * 0.8`, stopping behind a standing sandbag on the way when one is near; aim at the target plus seeded error (`AIM_ERROR_RADIANS = 0.08`, normal); fire when the cooldown allows and a seeded reaction delay (`REACTION_SECONDS_RANGE = (0.15, 0.45)`, drawn per new target) has passed. It draws only from `random` (the caller passes that soldier's stream).
  - In `game.py`: `class Phase(enum.Enum)`: `BATTLE`, `VICTORY`; `VICTORY_SECONDS = 3.0`; `DrawingFireScene.battle_number: int` (1 first); `DrawingFireScene.start_battle() -> None` (new terrain, sandbags and soldiers from the streams `'drawing_fire.terrain'`, `'drawing_fire.sandbags'`); the victory message names the winning army's `ARMY_NAMES` value, then the next battle starts on its own.
  - `scripts/simulate_drawing_fire.py`: `simulate(*, seed: int, soldiers_per_side: int = SOLDIERS_PER_SIDE, frame_seconds: float = 1 / 60, max_seconds: float = 600.0) -> SimulationResult` (frozen dataclass: `seed`, `winner: Side | None`, `seconds: float`, `survivors: int`); `main(argv)` with `--seeds N` and `--soldiers-per-side N` prints one line per seed and a summary (wins per army, mean and longest battle). It seeds the engine (`seed_engine_random(seed=seed)`) and steps `Battle` with `computer_intent`, no window.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_soldier_draws_only_from_his_own_stream():
    battle = small_battle()
    mine, other = random.Random(1), random.Random(2)
    other_state = other.getstate()
    computer_intent(soldier=battle.soldiers[0], battle=battle, random=mine)
    assert other.getstate() == other_state

def test_the_computer_aims_at_the_nearest_enemy(): ...   # aim within AIM_ERROR_RADIANS * 4 of the true bearing
def test_the_computer_advances_until_in_range(): ...     # move sign toward the enemy, 0 once within range

def test_a_computer_battle_ends_with_a_winner():
    result = simulate(seed=3)
    assert result.winner is not None and result.seconds < 600.0

def test_the_same_seed_replays_the_same_battle():
    assert simulate(seed=8) == simulate(seed=8)

def test_the_scene_starts_the_next_battle_after_victory(scene): ...  # winner -> VICTORY -> after VICTORY_SECONDS, battle_number 2
def test_the_simulation_prints_a_summary(capsys): ...  # main(['--seeds', '2']) prints both seeds and 'wins'
```

- [ ] **Step 2: Run** → fail. **Step 3: Implement.** **Step 4: Run** → PASS; `uv run python scripts/simulate_drawing_fire.py --seeds 20` reports battles that end (tune the Task 2 numbers here if battles drag past a few minutes or end in seconds; record the chosen numbers and the summary in the design document's section 4).
- [ ] **Step 5: Commit** — `"Drawing Fire: the computer driver; computer-against-computer battles and the simulation"`

### Task 4: Swatches: recolouring sprites by palette swap (the mechanic this game proves)

**Files:**
- Create: `glitchygames/examples/drawing_fire/swatches.py`, `glitchygames/examples/drawing_fire/sprites/soldier.toml` (Bitmappy's TOML format: `stand`, `walk` (two frames) and `down` animations, pencil-looking, with a `[swatches.livery]` set: `helmet` (primary) and `uniform` (secondary), each with a shadow shade)
- Test: `tests/examples/drawing_fire/test_swatches.py`

**Interfaces:**
- Consumes: the sprite file format (`glitchygames/sprites/animated.py` loads `[colors]` and `[[animation]]`; `[swatches]` is read here, beside it).
- Produces (shaped to move into the engine later, so no Drawing Fire names in it):
  - `type Color = tuple[int, int, int]`
  - `@dataclass(frozen=True) class SwatchPart`: `name: str`, `colors: tuple[Color, ...]` (the RGB of each listed palette character, in the file's order), `role: str | None`.
  - `@dataclass(frozen=True) class SwatchSet`: `name: str`, `parts: tuple[SwatchPart, ...]`.
  - `load_swatch_sets(*, path: Path) -> dict[str, SwatchSet]` (reads `[colors]` and `[swatches]`; raises `SwatchError` naming the file and part for an unknown palette character, a part with no colours, or a character in two parts of one set).
  - `@dataclass(frozen=True) class Scheme`: `primary: Color | None = None`, `secondary: Color | None = None`, `parts: Mapping[str, Color] = {}` (a part's own colour wins over its role's); `Scheme.color_for(part: SwatchPart) -> Color | None`.
  - `shade_map(*, part: SwatchPart, color: Color) -> dict[Color, Color]`: the part's first colour becomes `color`; every other keeps its brightness ratio to the first (per channel, clamped to 0..255).
  - `recolor_surface(*, surface: pygame.Surface, swatch_set: SwatchSet, scheme: Scheme) -> pygame.Surface` (a new surface; exact RGB replacement, alpha and colorkey kept; parts the scheme gives no colour stay as drawn).
  - `class RecoloredFrames`: `RecoloredFrames(*, frames: Mapping[str, Sequence[pygame.Surface]], swatch_set: SwatchSet)`; `frames_for(scheme: Scheme) -> Mapping[str, tuple[pygame.Surface, ...]]` (built once per scheme and cached; `Scheme` is hashable).

- [ ] **Step 1: Write the failing tests**

```python
def test_a_scheme_recolors_each_part_by_its_role(): ...       # helmet pixels -> primary, uniform -> secondary
def test_shadows_keep_their_brightness_ratio(): ...           # 'H' at 2/3 of 'h' -> 2/3 of the new primary
def test_a_part_colour_wins_over_its_role(): ...
def test_unlisted_colours_and_transparency_are_untouched(): ...
def test_each_scheme_is_built_once(): ...                     # frames_for twice -> the same surfaces (identity)
def test_an_unknown_palette_character_is_an_error(): ...      # SwatchError names the file and part
def test_the_soldier_sprite_has_a_livery(): ...               # load_swatch_sets(soldier.toml)['livery'] has helmet and uniform
```

- [ ] **Step 2-4:** fail, implement, pass.
- [ ] **Step 5: Commit** — `"Drawing Fire: swatches, recolouring sprites by palette swap (the game's new mechanic)"`

### Task 5: The pencil look

**Files:**
- Create: `glitchygames/examples/drawing_fire/drawing.py`
- Modify: `glitchygames/examples/drawing_fire/game.py` (`render` draws through it)
- Test: `tests/examples/drawing_fire/test_drawing.py`

**Interfaces:**
- Consumes: `Terrain`, `Battle`, `Soldier`, `Sandbag`, `Bullet`, `Side`, `ARMY_NAMES`; `Scheme`, `RecoloredFrames`, `load_swatch_sets` (Task 4).
- Produces: `ARMY_COLORS = {Side.PLATOON: (242, 194, 48), Side.BRIGADE: (125, 127, 133)}`; `PENCIL_COLOR = (44, 44, 44)`; `wobble(*, x: float, y: float, salt: int) -> tuple[float, float]` (a deterministic hash of its inputs, at most `WOBBLE_PIXELS = 1.5` each way: hand-drawn lines with no random stream); `draw_terrain(surface, terrain)`, `draw_sandbag(surface, sandbag, terrain)` (sagging with its sand; a trickle of sand while not flat), `ARMY_LIVERIES = {Side.PLATOON: Scheme(primary=(242, 194, 48), secondary=(214, 168, 40)), Side.BRIGADE: Scheme(primary=(125, 127, 133), secondary=(98, 100, 106))}`; `draw_soldier(surface, soldier, *, frames: RecoloredFrames, marked: str | None)` (the soldier sprite's frame wearing his army's livery (Task 4), walking or standing, `down` when dead; the arm and pistol drawn as pencil lines along `aim_angle`; `marked` is a player's name drawn as a small pennant over him), `draw_bullet(surface, bullet)` (a short dash), `draw_hud(surface, battle)` (each army's name and living count in its corner), `draw_banner(surface, text)` (the victory message, hand-lettered).

- [ ] **Step 1: Write the failing tests** — pixel checks on a real `Surface`: a Platoon soldier's helmet pixel is pencil yellow and a Brigade soldier's graphite grey (the same sprite, two liveries); a full sandbag is taller than a half-empty one (topmost non-paper pixel); `wobble` is deterministic and bounded; `draw_hud` writes both army names (the HUD surface differs from a blank one in both corners).
- [ ] **Step 2-4:** fail, implement, pass. Look at it: `uv run drawing-fire`; the battle should read like the brainstorm's pictures.
- [ ] **Step 5: Commit** — `"Drawing Fire: the pencil look"`

### Task 6: Player input: devices, dual stick, keyboard and mouse

**Files:**
- Create: `glitchygames/examples/drawing_fire/players.py`
- Test: `tests/examples/drawing_fire/test_players.py`

**Interfaces:**
- Consumes: `Intent` (Task 2); `glitchygames.input.state.InputSnapshot`.
- Produces:
  - `@dataclass(frozen=True) class Device`: `controller_id: int | None` (None is the keyboard and mouse); `KEYBOARD = Device(controller_id=None)`; `connected_devices(snapshot: InputSnapshot) -> tuple[Device, ...]` (the keyboard, then every id in `snapshot.controller_axes`, sorted).
  - `device_intent(*, device: Device, snapshot: InputSnapshot, soldier_position: tuple[float, float], last_aim: float) -> Intent`. Controller: move = `CONTROLLER_AXIS_LEFTX` / 32767 (dead zone `STICK_DEAD_ZONE = 0.2` → 0); aim = `atan2(-RIGHTY, RIGHTX)` while the right stick is past `STICK_DEAD_ZONE`, else `last_aim`; fire = `CONTROLLER_AXIS_TRIGGERRIGHT > TRIGGER_THRESHOLD` (`0.5` of full) or `CONTROLLER_BUTTON_RIGHTSHOULDER` held. Keyboard: move from A/D and the left/right arrows (scancodes); aim at the mouse from `soldier_position` (screen y down: `atan2(soldier_y - mouse_y, mouse_x - soldier_x)`); fire = left mouse button.
  - `class ButtonEdges`: `update(snapshot: InputSnapshot) -> None`; `pressed(device: Device, button: Button) -> bool` (down this frame, up last frame); `held_frames(device: Device, button: Button) -> int` (frames held so far, 0 when up); `class Button(enum.Enum)`: `START` (controller `CONTROLLER_BUTTON_START`, keyboard Enter), `BACK` (`CONTROLLER_BUTTON_BACK`, keyboard Escape), `LEFT`, `RIGHT` (D-pad or stick past the dead zone; keyboard arrows/A/D).

- [ ] **Step 1: Write the failing tests** (snapshots built directly: `InputSnapshot(pressed_scancodes=..., modifiers=0, mouse_position=..., mouse_buttons=..., mouse_focused=True, controller_axes={7: axes}, controller_buttons={7: buttons})`):

```python
def test_dual_stick_moves_and_aims(): ...          # LEFTX 32767 -> move 1.0; RIGHTX 0, RIGHTY -32767 -> aim pi/2 (up)
def test_a_resting_aim_stick_keeps_the_last_aim(): ...  # right stick in the dead zone -> aim == last_aim
def test_the_trigger_fires(): ...
def test_the_keyboard_aims_at_the_mouse(): ...     # mouse up-left of the soldier -> aim in (pi/2, pi)
def test_start_is_pressed_once_per_press(): ...    # held two frames -> pressed only on the first
def test_connected_devices_list_the_keyboard_and_each_controller(): ...
```

- [ ] **Step 2-4:** fail, implement, pass. **Step 5: Commit** — `"Drawing Fire: player input (dual stick, keyboard and mouse)"`

### Task 7: Seats: joining, choosing a soldier, death takeovers, leaving (milestones 2 and 3)

**Files:**
- Create: `glitchygames/examples/drawing_fire/seats.py`
- Modify: `glitchygames/examples/drawing_fire/game.py` (seats in `dt_tick`: players' intents for their soldiers, the computer's for the rest; deaths to `Seats.soldier_killed`; the choosing screens and highlight drawn; `marked` names on players' soldiers), `glitchygames/examples/drawing_fire/drawing.py` (`draw_join_prompt(surface)`: the "Press START to join!" sticky note on the paper, always shown while a device is unseated, with "Enter" named for the keyboard)
- Test: `tests/examples/drawing_fire/test_seats.py`, `tests/examples/drawing_fire/test_game.py`

**Interfaces:**
- Consumes: `Battle`, `Side`, `Soldier` (Task 2); `Device`, `ButtonEdges`, `Button`, `connected_devices` (Task 6).
- Produces:
  - `class Stage(enum.Enum)`: `CHOOSING_SIDE`, `CHOOSING_SOLDIER`, `PLAYING`, `WAITING`.
  - `class SideChoice(enum.Enum)`: `RANDOM` (the default), `PLATOON`, `BRIGADE`.
  - `@dataclass class PlayerSeat`: `name: str` ('P1', 'P2', ...: the lowest free), `device: Device`, `stage: Stage`, `side: Side | None`, `soldier_id: int | None`, `highlight_index: int`, `side_choice: SideChoice` (`RANDOM` first, `PLATOON`, `BRIGADE`).
  - `@dataclass(frozen=True) class SeatLogEntry`: `seconds: float`, `text: str` (e.g. `'P2 START → random → PLATOON'`, `'P1 took soldier 5'`, `'P1 died → soldier 3'`, `'P2 left'`).
  - `class Seats`: `Seats(*, random: random.Random)` (the scene passes `random_stream('drawing_fire.seats')`); `players: dict[str, PlayerSeat]`; `log: collections.deque[SeatLogEntry]` (`maxlen=8`); `driver_of(soldier_id: int) -> str` (a player's name, else `'CPU'`); `update(*, edges: ButtonEdges, devices: Sequence[Device], battle: Battle, seconds: float) -> None` (START on an unseated device opens `CHOOSING_SIDE`; LEFT/RIGHT cycle; START confirms; RANDOM picks a side from the seats stream; `CHOOSING_SOLDIER` cycles a highlight over that side's computer-driven living soldiers, starting nearest the field's middle; BACK held `LEAVE_HOLD_FRAMES = 60` frames, or a controller no longer in `devices`, leaves); `soldier_killed(*, soldier_id: int, battle: Battle, seconds: float) -> None` (the player takes a random computer-driven living soldier of their side from the seats stream, else `WAITING`); `battle_started(*, battle: Battle) -> None` (every seated player goes back to `CHOOSING_SOLDIER` on their side).
  - The keyboard counts as one device; at most one seat per device.

- [ ] **Step 1: Write the failing tests**

```python
def test_start_then_confirm_joins_a_random_side_and_takes_a_soldier(): ...  # log holds 'P1 START → random → ...'
def test_a_player_cannot_take_another_players_soldier(): ...
def test_death_moves_the_player_to_a_random_soldier_of_their_side(): ...    # seeded: same seed, same soldier
def test_a_death_with_no_free_soldier_waits(): ...                           # stage WAITING; takes the next free one
def test_holding_back_leaves_and_returns_the_soldier_to_the_computer(): ...  # after LEAVE_HOLD_FRAMES, driver_of -> 'CPU'
def test_an_unplugged_controller_leaves(): ...
def test_choosing_when_the_battle_ends_waits_for_the_next(): ...
def test_two_players_on_opposite_sides(): ...       # milestone 3: P1 Platoon, P2 Brigade, both PLAYING
def test_two_players_on_the_same_side(): ...
def test_the_join_prompt_shows_while_a_device_is_unseated(scene): ...  # pixels in the note's corner; gone once every device is seated
def test_a_joined_player_plays_the_next_battle(scene): ...  # after VICTORY, battle_started -> CHOOSING_SOLDIER, same side
def test_the_scene_drives_a_players_soldier_from_their_device(scene): ...  # set_current_input(...) with LEFTX full: his x grows
```

- [ ] **Step 2-4:** fail, implement, pass. Play it: `uv run drawing-fire`, press Enter, choose, fight with WASD and the mouse; plug in a controller and press START.
- [ ] **Step 5: Commit** — `"Drawing Fire: seats (join, choose, take over on death, leave), one and two players"`

### Task 8: The debug seats view

**Files:**
- Modify: `glitchygames/examples/drawing_fire/game.py` (`debug_draw`), `glitchygames/examples/drawing_fire/drawing.py` (`draw_seat_tag`, `draw_seats_panel`)
- Test: `tests/examples/drawing_fire/test_game.py`, `tests/examples/drawing_fire/test_drawing.py`

**Interfaces:**
- Consumes: `Seats.driver_of`, `Seats.players`, `Seats.log` (Task 7).
- Produces: `DrawingFireScene.debug_draw(surface, camera)` (the engine calls it while the debug overlay is on: F3, or `--debug-overlay`): a tag over every living soldier with `Seats.driver_of(...)` (pink `DEBUG_COLOR = (212, 0, 106)` outline), and a panel in a bottom corner listing each army's players and computer count, then the last `Seats.log` lines with their `m:ss` times. `draw_seat_tag(surface, *, text: str, at: tuple[float, float])`, `draw_seats_panel(surface, *, lines: Sequence[str])`.

- [ ] **Step 1: Write the failing tests** — with one player seated, `debug_draw` changes pixels over that soldier and in the panel's corner; `seats_panel_lines(seats, battle) -> list[str]` (a pure helper in `game.py`) gives `['PLATOON  P1 · CPU ×7', 'BRIGADE  CPU ×8', '0:04  P1 START → random → PLATOON']` for that case.
- [ ] **Step 2-4:** fail, implement, pass. **Step 5: Commit** — `"Drawing Fire: the debug seats view"`

### Task 9: Golden replay, registration and docs

**Files:**
- Modify: `scripts/record_scripted_session.py` and `scripts/record_golden_traces.py` (a `drawing_fire` script: the keyboard presses Enter, confirms, plays a while aiming with the mouse and firing, dies at least once, holds Escape to leave), `tests/replay/test_golden_replays.py` (register `drawing-fire`; its controls are read from snapshots, not an `ActionMap`, so list them as hard-coded controls the way Mr. Muncher's hat is, and its gamepad controls as `NO_GAMEPAD_IN_THE_SESSION`), `tests/fixtures/replays/drawing-fire/golden.jsonl.gz` (recorded with the scripts, as the other games' are), `scripts/build_browser_bundle.py` (a `drawing-fire` entry in `GAMES`; no touch layout yet: if `TOUCH_LAYOUTS`' coverage test exists on `main`, exempt `drawing-fire` there with the reason "dual stick: touch controls once its controls settle"), `docs/games/drawing_fire.md` and `mkdocs.yml` (an architecture page like the other games', with the copied pictures), `CLAUDE.md` (Drawing Fire under the examples), `plans/future-features.md` (a "Drawing Fire" entry pointing at the design for everything after the MVP, and a "Swatches into the engine" entry: the mechanic Task 4 proved, its API as built, and what moving it into `glitchygames/sprites/` would take).
- Test: `tests/replay/test_golden_replays.py` (the new golden replay replays exactly and exercises every keyboard control).

- [ ] **Step 1:** Add the session script and registration; record the golden replay with the same commands the other games use (see `CLAUDE.md`, "Golden traces" and `nox -s replay-metrics`).
- [ ] **Step 2: Run** `uv run pytest tests/replay -q --dummy-only` → the drawing-fire replay passes; then the full `uv run pytest` (dummy and cocoa) → 100% coverage, no driver differences.
- [ ] **Step 3:** `uv run nox -s lint` and `uv run nox -s static-analysis` clean; `nox -s browser -- drawing-fire` runs the game in a browser (keyboard and mouse).
- [ ] **Step 4: Commit** — `"Drawing Fire: golden replay, registration, docs"`
