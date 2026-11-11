# Arcade, Sub-plan 2: Demos for Every Tile — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task (execution is subagent-driven for every Arcade sub-plan: decision 4 of the engine context master plan). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every tile of the Arcade has a bundled demo recording: a `--script-only` session
shipped as package data in its member's package (`<package>/demos/<name>.jsonl.gz`), replayed
headless by `tests/replay/test_bundled_demos.py`, recorded by one reproducible command.

**Architecture:** One new repository script, `scripts/record_bundled_demos.py`, holds every
demo's recipe (scene, input script, frame count, flags, destination) and records it through the
engine's scripted-session recorder (`glitchygames.replay.tools.scripted_sessions`). The four new
input scripts (Bitmappy, the dt, text-input and joystick demos) go in `scripts/demo_inputs.py`;
the five games reuse their golden input scripts' frames. The engine gains one recorder option,
stand-in devices (a pad that exists only in the session, served through the real devices door,
so its recording replays like any other), plus posted joystick input in the session's snapshots.

**Tech Stack:** Python 3.14, pygame-ce, pydantic, pytest with pytest-mock, uv.

**Spec:** [2026-10-23-arcade-showcase.md](2026-10-23-arcade-showcase.md) (the master spec:
Sub-plans item 2, Architecture section 5, the ten tiles in Decisions and the mockup
https://claude.ai/artifact/3QKddtTADVqC1LVpvDSQSD).

## Rulings made while writing this plan (the owner may overturn any)

1. **Every tile needs its demo, not only the four the spec names.** The spec's Sub-plans item 2
   says "the games have theirs"; only PaddleSlap does (`paddleslap/demos/rally.jsonl.gz`). The
   others have golden replays, which end with the controls tail and the game's quit, not an
   attract reel. Section 5 asks one recording per game, so the five games get theirs here too.
   Cost if wrong: one task (Task 3) the owner did not want.
2. **The ten tiles are the mockup's:** PaddleSlap, Brave Adventurer (Classic), Brave Adventurer:
   Papyrus, Clockwork Keep, Mr. Muncher, Drawing Fire, Bitmappy, the dt, joystick and text-input
   demos. The Sound Board demo is not a tile in the mockup or the spec, so it gets no demo here
   (an open question in plans/future-work.md). The spec's other line, one Brave Adventurer tile
   for its launcher (2026-10-27), is sub-plan 6's to settle; both editions get a demo here, so
   either layout has what it needs. Cost if wrong: one Sound Board demo later, the same recipe.
3. **The games' demos reuse their golden scripts' frames,** `--script-only`, for as many frames
   as the golden session records before its controls tail: PaddleSlap's rally precedent. Clockwork
   Keep (330) and Brave Adventurer (400 each) are short because their scripts' first placement
   comes next (a session may not run a placement's frame). Longer attract scripts are future
   work. Cost if wrong: new scripts later; the recipe table stays.
4. **Brave Adventurer's demos live in its launcher's package** (`brave_adventurer_modes/demos/`):
   `bundled_demos` pairs a demo with the console script whose entry point is in the demo's own
   package, and only the launcher has one (`brave-adventurer = "brave_adventurer_modes:main"`);
   it replays the edition the recording's header names.
5. **PaddleSlap's rally is not re-recorded:** its recipe joins the table (450 frames, as
   recorded), so re-recording it later is one command.
6. **The dt and joystick demos are converted to sprites before their demos are recorded**
   (the owner, 2026-11-11; Task 4). They drew straight onto the screen, and a replay compares
   sprites and events only, so their demos' tests would have checked almost nothing. The values
   that matter (the square's position, the pad's axes, buttons and hat) are carried by sprite
   geometry and visibility, since a sprite's text is not compared either.

## Global Constraints

- Every demo is a `--script-only` session (`controls_tail=None`): no controls tail, no quit.
- Every demo is recorded under `glitchygames.replay.tools.golden_traces.RANDOM_SEED` (20261018),
  at the recorder's `SCREEN_RESOLUTION` ('800x480').
- Each bundled demo is at most 256 KB (`MAXIMUM_DEMO_BYTES = 256 * 1024`, enforced by a test);
  Drawing Fire's first frame alone is about 125 KB (CLAUDE.md, golden replays).
- A demo is replayed headless by its member's console script and exits `ExitCode.SUCCESS`.
- `EXPECTED_BUNDLED_DEMOS` (`tests/workspace_expectations.py`) is edited by hand with each demo.
- Golden replays are never re-recorded by this plan.
- New data classes: pydantic `BaseModel`, `frozen=True`, `extra='forbid'`.
- No abbreviated names; keyword arguments; pytest-mock only where something cannot run in a test.
- `ContextSlot` rules, the doors guard (`tests/test_engine_doors.py`) and every existing guard
  keep passing; never suppress a lint error or edit a linter configuration.
- The full suite passes on both drivers with 100% coverage after every task.
- Commits by path, each message ending with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **The AI service installed on the recording machine:** a demo session must never connect to
   it (it is not headless, so `create_link` would). Task 2 records every session with
   `GLITCHYGAMES_AI_INSTALL_ROOT` pointed at an empty temporary directory, and tests it.
2. **A demo ends with input still held:** the Arcade loops each demo, so a key, mouse button or
   pad button down at the end would be stuck into the loop. Task 2's test checks every recipe's
   script releases everything it presses before its last recorded frame.
3. **Bitmappy at 800x480:** the editor's canvas must fit, and every click the script makes must
   land on it. Task 6 tests the script's points against the canvas built at that size.
4. **A stand-in pad replayed on a machine with a real pad:** the replay must use the recorded
   pad only. Task 1's test replays its stand-in recording headless (real devices are blocked
   in a replay) and checks the device column shows the recorded name.
5. **Members installed from wheels** (nox's sessions): the demos must ship as package data.
   `EXPECTED_BUNDLED_DEMOS` compares by `(package, name)`, never by path, so the nox run of
   `tests/replay/test_bundled_demos.py` proves it.

## File Structure

- Create `src/glitchygames/input/stand_in_devices.py`: `StandInDeviceSources`, `stand_in_registry`,
  `install_stand_in_devices`, moved from `tests/input/stand_in_devices.py` (which keeps its
  descriptors and imports these).
- Modify `src/glitchygames/engine/game_engine.py:1595-1601`: the live doors are built by
  `GameEngine.build_live_sources`.
- Modify `src/glitchygames/replay/tools/golden_traces.py` (`GoldenTraceEngine`) and
  `src/glitchygames/replay/tools/scripted_sessions.py` (`ScriptedSessionOptions`,
  `PostedPolledInput`, `record_scripted_session`).
- Modify `src/demos/dt-demo/src/dt_demo/__init__.py` and
  `src/demos/joystick-demo/src/joystick_demo/__init__.py`: drawn with sprites (Task 4).
- Create `scripts/record_bundled_demos.py` (the recipes and the command) and
  `scripts/demo_inputs.py` (the four new input scripts).
- Create the demos: `clockwork_keep/demos/climb.jsonl.gz`,
  `brave_adventurer_modes/demos/classic.jsonl.gz`, `brave_adventurer_modes/demos/papyrus.jsonl.gz`,
  `mr_muncher/demos/chase.jsonl.gz`, `drawing_fire/demos/battle.jsonl.gz`,
  `dt_demo/demos/timing.jsonl.gz`, `text_input_demo/demos/typing.jsonl.gz`,
  `bitmappy/demos/drawing.jsonl.gz`, `joystick_demo/demos/pad.jsonl.gz` (each under its member's
  `src/<package>/`).
- Tests: `tests/replay/tools/test_scripted_sessions.py`, `tests/test_record_bundled_demos.py`
  (new; a `SCRIPT_TEST_FILES` entry in `tests/test_suite_collection.py`),
  `tests/replay/test_bundled_demos.py`, `src/apps/bitmappy/tests/test_bitmappy_demo_script.py`.

---

### Task 1: Stand-in devices in a recorded session (engine)

**Files:**
- Create: `src/glitchygames/input/stand_in_devices.py`
- Modify: `tests/input/stand_in_devices.py` (imports the moved names, keeps `STAND_IN_STICK` and
  its other descriptors)
- Modify: `src/glitchygames/engine/game_engine.py:1595-1601`
- Modify: `src/glitchygames/replay/tools/golden_traces.py` (`GoldenTraceEngine`)
- Modify: `src/glitchygames/replay/tools/scripted_sessions.py`
- Test: `tests/replay/tools/test_scripted_sessions.py`, `tests/engine/` (the file holding the
  engine's live-doors tests)

**Interfaces:**
- Produces:
  - `glitchygames.input.stand_in_devices.stand_in_registry(*, descriptors: Sequence[DeviceDescriptor], plugged_in_at_start: bool = True) -> ReplayDeviceRegistry`
  - `StandInDeviceSources(LiveSources)`, `__init__(self, *, registry: ReplayDeviceRegistry, **live_options: Any)` (passes `live_options` to `LiveSources`), `devices()` returns the registry
  - `install_stand_in_devices(*, descriptors, plugged_in_at_start=True) -> ReplayDeviceRegistry`
  - `GameEngine.build_live_sources(self, *, random_seed: int, captures_scene_starts: bool) -> LiveSources`
  - `GoldenTraceEngine.__init__(self, *, game, stand_in_devices: Sequence[DeviceDescriptor] | None = None)`: its `build_live_sources` returns `StandInDeviceSources` around `stand_in_registry(descriptors=stand_in_devices)` when given
  - `ScriptedSessionOptions.stand_in_devices: Sequence[DeviceDescriptor] | None` (default None)
  - `PostedPolledInput` follows `JOYAXISMOTION`, `JOYBUTTONDOWN`/`UP` and `JOYHATMOTION` by `instance_id` and `overlay` lays them into `device_axes`, `device_buttons`, `device_hats`

- [ ] **Step 1: Write the failing tests** in `tests/replay/tools/test_scripted_sessions.py`:

```python
def test_a_session_with_a_stand_in_pad_records_and_replays_it(tmp_path):
    """The pad exists only in the session; its recording replays headless (Review Focus 4)."""
    script = InputScript()
    script.at(5, joystick_axis(instance_id=STAND_IN_STICK.instance_id, axis=0, value=0.5))
    script.at(8, joystick_button(instance_id=STAND_IN_STICK.instance_id, button=1, pressed=True))
    script.at(11, joystick_button(instance_id=STAND_IN_STICK.instance_id, button=1, pressed=False))
    path = tmp_path / 'pad.jsonl.gz'

    record_scripted_session(
        scene_class=PadReadoutScene, script=script, frame_count=20, path=path,
        polled_input=True, stand_in_devices=[STAND_IN_STICK], random_seed=RANDOM_SEED,
    )

    header, frames = read_recording(path=path)
    assert [device['name'] for device in header['devices']] == [STAND_IN_STICK.name]
    assert snapshot_axis(frames=frames, frame_number=6, instance_id=5, axis=0) == 0.5
    assert replay_headless(path=path).returncode == ExitCode.SUCCESS
```

`PadReadoutScene` is a stand-in scene (in `tests/stand_in_games.py`) holding one sprite whose
rect's x is `100 + round(100 * current_input().axis(device_id=..., axis=0))`, so a replay compares
the pad's effect. `joystick_axis`/`joystick_button`/`joystick_hat` build the pygame events;
`read_recording`, `snapshot_axis` and `replay_headless` are this file's helpers over the
existing readers. A second test: `test_posted_polled_input_follows_the_pads_axes_buttons_and_hat`
on `PostedPolledInput` alone (an axis, a button down then up, a hat; `overlay` of an empty
snapshot shows each, a button released reads False). A third, in the engine's live-doors test
file: `GameEngine.build_live_sources` returns `LiveSources` with the given seed and
`captures_scene_starts`.

- [ ] **Step 2: Run** `uv run pytest --dummy-only tests/replay/tools/test_scripted_sessions.py -k "stand_in_pad or follows_the_pad"`. Expected: fail (`unexpected keyword argument 'stand_in_devices'`).
- [ ] **Step 3: Implement.** Move the three names into the engine module (the test module
  imports them; no copy is left); extract `build_live_sources` from `game_engine.py:1595-1601`
  unchanged in behaviour; `record_scripted_session` passes `stand_in_devices` to
  `GoldenTraceEngine`; extend `PostedPolledInput.follow`/`overlay`. Axes and buttons tuples are
  sized from the descriptor (`axis_count`, `button_count`, `hat_count`), so `PostedPolledInput`
  takes `descriptors` (empty by default) at construction.
- [ ] **Step 4: Run** the three tests, then `uv run pytest --dummy-only tests/input tests/replay tests/engine -n auto`, then lint (`nox -s lint-code`, `nox -s static-analysis`). Expected: all pass; `tests/test_engine_doors.py` passes (no new device bypass).
- [ ] **Step 5: Run the suite** (`uv run pytest -n auto`): every test passes, 100% coverage, 0 driver differences. **Commit:** `Engine: stand-in devices in a recorded scripted session`.

---

### Task 2: The demo recipes and their command

**Files:**
- Create: `scripts/record_bundled_demos.py`
- Modify: `scripts/record_scripted_session.py` (its docstring's rally command points to the new script)
- Test: `tests/test_record_bundled_demos.py`; `tests/test_suite_collection.py` (`SCRIPT_TEST_FILES` entry)

**Interfaces:**
- Consumes: Task 1's `stand_in_devices` option; `scripts.record_golden_traces.GAME_SCENES`, `SCRIPT_BUILDERS`; `record_scripted_session`.
- Produces:
  - `DemoRecipe(BaseModel)` (frozen, extra='forbid'): `scene: str` (`'module:Qualname'`), `script: str` (`'module:callable'`, loaded with `golden_traces.load_input_script`), `frame_count: int`, `package: str`, `name: str`, `polled_input: bool = False`, `input_only_placements: bool = False`, `stand_in_devices: tuple[DeviceDescriptor, ...] = ()`
  - `DEMO_RECIPES: dict[str, DemoRecipe]`, today `{'paddleslap_rally': DemoRecipe(scene='paddleslap:Game', script='scripts.golden_inputs:paddleslap_script', frame_count=450, package='paddleslap', name='rally.jsonl.gz', input_only_placements=True)}`
  - `demo_path(*, recipe: DemoRecipe) -> Path`: the package's installed directory (`importlib.util.find_spec`) / `demos` / `name`
  - `record_demo(*, recipe: DemoRecipe) -> Path`: records with `controls_tail=None`, `random_seed=RANDOM_SEED`, with `GLITCHYGAMES_AI_INSTALL_ROOT` set to an empty temporary directory for the session
  - `main()`: `--demo KEY` (choices: `DEMO_RECIPES`) or `--all`

- [ ] **Step 1: Write the failing tests:**

```python
def test_the_recipes_are_the_expected_bundled_demos():
    assert {(recipe.package, recipe.name) for recipe in DEMO_RECIPES.values()} == (
        EXPECTED_BUNDLED_DEMOS
    )

def test_every_recipe_releases_what_it_presses():  # Review Focus 2
    for key, recipe in DEMO_RECIPES.items():
        assert held_at_end(recipe=recipe) == set(), key

def test_a_demo_session_never_reaches_the_ai_service(mocker, tmp_path):  # Review Focus 1
    recorded = mocker.patch('scripts.record_bundled_demos.record_scripted_session')
    seen = {}
    recorded.side_effect = lambda **_: seen.update(root=os.environ[AI_INSTALL_ROOT_VARIABLE])
    record_demo(recipe=DEMO_RECIPES['paddleslap_rally'].model_copy(update={'name': 'x.jsonl.gz'}))
    assert not any(Path(seen['root']).iterdir())
```

`held_at_end(*, recipe)` walks the script's events for frames below `frame_count` and returns the
keys, mouse buttons and `(instance_id, button)` pad buttons pressed and not released. Also:
`test_every_demo_is_in_a_package_with_its_console_script` (each recipe's `package` has
`console_script_in_module(module=package)`), and `test_main_records_one_demo_or_all` (patched
`record_demo`: `--demo paddleslap_rally` records one, `--all` every key). The recording test
itself is `tests/replay/test_bundled_demos.py`, which replays the committed files.

- [ ] **Step 2: Run** `uv run pytest --dummy-only tests/test_record_bundled_demos.py`. Expected: ImportError.
- [ ] **Step 3: Implement** the module (docstring: the rules above, the command per demo, why each frame count). Add its `SCRIPT_TEST_FILES` entry.
- [ ] **Step 4: Run** the file, `tests/test_suite_collection.py`, lint. Expected: pass.
- [ ] **Step 5: Commit:** `Scripts: one recipe and one command for every bundled demo`.

---

### Task 3: The five games' demos

**Files:**
- Modify: `scripts/record_bundled_demos.py` (`DEMO_RECIPES`)
- Create: the five recordings: `clockwork_keep/demos/climb.jsonl.gz` (330 frames,
  `clockwork_keep_script`), `brave_adventurer_modes/demos/classic.jsonl.gz` and `papyrus.jsonl.gz`
  (400 each, `brave_adventurer_script`, scenes `brave_adventurer.game:BraveAdventurerScene` and
  `brave_adventurer_papyrus.game:PapyrusBraveAdventurerScene`), `mr_muncher/demos/chase.jsonl.gz`
  (1950, `mr_muncher_script`), `drawing_fire/demos/battle.jsonl.gz` (1600, `drawing_fire_script`,
  `polled_input=True`)
- Modify: `tests/workspace_expectations.py` (`EXPECTED_BUNDLED_DEMOS`), `tests/replay/test_bundled_demos.py`

**Interfaces:**
- Consumes: Task 2's `DEMO_RECIPES`, `record_demo`, `main`.

- [ ] **Step 1: Write the failing test** in `tests/replay/test_bundled_demos.py`: rename `test_paddleslap_ships_a_demo` to `test_the_bundled_demos_are_the_expected_ones`; add

```python
def test_every_bundled_demo_is_small_enough_to_ship():
    for demo in bundled_demos(packages=MEMBER_PACKAGES):
        assert demo.path.stat().st_size <= MAXIMUM_DEMO_BYTES, demo.install_name
```

and add the five `(package, name)` pairs to `EXPECTED_BUNDLED_DEMOS` (its comment names each).

- [ ] **Step 2: Run** `uv run pytest --dummy-only tests/replay/test_bundled_demos.py tests/test_record_bundled_demos.py`. Expected: the expected-set tests fail (five demos missing).
- [ ] **Step 3: Add the five recipes, then record:** `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_bundled_demos --demo <key>` for each new key. Check each file's size.
- [ ] **Step 4: Run** the two files (the five replays exit SUCCESS; the Brave Adventurer demos through `brave-adventurer`), then `uv run glitchygames verify --game brave-adventurer` and `--game mr-muncher` (a game's own recordings now include its demos). Expected: pass.
- [ ] **Step 5: Suite, then commit:** `Demos: Clockwork Keep, both Brave Adventurer editions, Mr. Muncher and Drawing Fire`.

---

### Task 4: The dt and joystick demos draw with sprites

A replay compares each sprite's rect, visibility and draw order, and the recorded events; never
pixels, and never a sprite's text. Both demos draw straight onto `self.screen` (the joystick
demo's `_draw_line`; the dt demo's `font.render` blits and `pygame.draw.rect`), so their demos
would replay clean whatever they showed (plans/future-work.md, Games, 2026-11-11). Text alone in
a sprite would still compare nothing but its width, so the values that matter are carried by
sprite geometry. The demos must look as they do today, except for the joystick demo's new gauges.

**Files:**
- Modify: `src/demos/dt-demo/src/dt_demo/__init__.py`, `src/demos/dt-demo/tests/test_dt_demo.py`
- Modify: `src/demos/joystick-demo/src/joystick_demo/__init__.py`, `src/demos/joystick-demo/tests/test_joystick_demo.py`
- Modify: `plans/future-work.md` (remove the "Convert the joystick demo to sprites" entry: done here)

**Interfaces:**
- Produces: both scenes draw only through their sprite groups (`update()` no longer blits or
  draws on `self.screen`, beyond the background). Tasks 5 and 7 record the demos after this.
- dt demo: the square is a screen-space sprite whose `rect.x` is `int(rect_pos)`; the time, FPS
  and record lines are `glitchygames.ui.TextSprite`s; the record line is `visible = False` until
  the square crosses the screen (screen-space, so `visible` is the demo's to set).
- joystick demo: the header and each device line are `TextSprite`s whose text is replaced when
  it changes. Below each device's text, gauges: per axis a marker sprite on a track
  `AXIS_TRACK_WIDTH` (100) pixels wide, its `rect.centerx` the track's left plus
  `round((value + 1) / 2 * AXIS_TRACK_WIDTH)`; per button a lamp sprite, visible only while
  held; per hat a dot sprite offset from its centre by `HAT_STEP` (8) pixels times the hat's
  (x, -y). A device's sprites are made in `on_input_device_added` (or for the devices present
  in `setup()`) and killed in `on_input_device_removed`. `device_lines` stays.

- [ ] **Step 1: Write the failing tests.** dt demo: `test_the_square_is_a_sprite_that_follows_its_position` (after Space and some frames, the square sprite's `rect.x == int(scene.rect_pos)`), `test_the_record_line_is_hidden_until_the_square_crosses`. Joystick demo, with the existing stand-in devices: `test_an_axis_marker_moves_with_its_axis` (values -1.0, 0.0, 1.0 put its `centerx` at the track's left, middle and right), `test_a_button_lamp_is_visible_only_while_held`, `test_the_hat_dot_moves_with_the_hat` (each of the four directions and centre), `test_a_removed_devices_sprites_are_gone`, and for both demos `test_update_draws_only_sprites` (patch `pygame.Surface.blit` on the scene's screen with `mocker.spy` and assert `update()` makes no call; the sprite group's draw is separate).
- [ ] **Step 2: Run them.** `uv run pytest --dummy-only src/demos/dt-demo/tests src/demos/joystick-demo/tests`. Expected: the new tests fail.
- [ ] **Step 3: Convert both demos** to the sprites above. Keep the existing tests' assertions on what is drawn (pixels) passing: they are the check that the demos look as before.
- [ ] **Step 4: Run** both test directories, then look once at each demo live (`uv run dt-demo`, `uv run joystick-demo` with a pad if one is to hand, else its tests' stand-in). Expected: pass; the dt demo looks unchanged, the joystick demo shows its gauges.
- [ ] **Step 5: Suite, then commit:** `Demos: the dt and joystick demos draw with sprites, so their replays compare what they show`.

---

### Task 5: The dt and text-input demos

**Files:**
- Create: `scripts/demo_inputs.py` (`dt_demo_script() -> InputScript`, `text_input_demo_script() -> InputScript`)
- Modify: `scripts/record_bundled_demos.py`, `tests/workspace_expectations.py`, `tests/test_record_bundled_demos.py`
- Create: `dt_demo/demos/timing.jsonl.gz` (600 frames, `polled_input=True`: the demo reads Space from `current_input()`), `text_input_demo/demos/typing.jsonl.gz` (600 frames)

**Interfaces:**
- Consumes: Task 4's sprite-drawn dt demo.

- [ ] **Step 1: Write the failing tests** in `tests/test_record_bundled_demos.py`: `test_the_dt_demo_script_presses_every_dt_demo_control` (every key the demo's `on_key_down_event` and `dt_tick` read, from the demo's module, is pressed at least once) and `test_the_text_input_script_types_and_submits` (the script's events type `GLITCHYGAMES` into the input box and submit it: KEYDOWN/KEYUP with each letter's `unicode`, plus `TEXTINPUT` events if the box reads them: read `InputBox` first). Add both pairs to `EXPECTED_BUNDLED_DEMOS`.
- [ ] **Step 2: Run them.** Expected: ImportError, then the expected-set test fails.
- [ ] **Step 3: Write the two scripts** (each releases everything it presses: Task 2's test), add the recipes, record both.
- [ ] **Step 4: Run** `tests/test_record_bundled_demos.py` and `tests/replay/test_bundled_demos.py`. Expected: pass, both replays SUCCESS.
- [ ] **Step 5: Suite, then commit:** `Demos: the dt and text-input demos`.

---

### Task 6: Bitmappy's demo: a sprite being drawn

**Files:**
- Modify: `scripts/demo_inputs.py` (`bitmappy_demo_script() -> InputScript`, its click points as `BITMAPPY_DEMO_POINTS: tuple[tuple[int, int], ...]`)
- Modify: `scripts/record_bundled_demos.py`, `tests/workspace_expectations.py`
- Create: `bitmappy/demos/drawing.jsonl.gz` (900 frames; `polled_input=True` if the canvas reads the polled mouse: read `bitmappy`'s canvas first)
- Test: `src/apps/bitmappy/tests/test_bitmappy_demo_script.py`

- [ ] **Step 1: Write the failing test** (Review Focus 3):

```python
def test_every_demo_click_lands_on_the_canvas_at_the_recorders_resolution():
    scene = build_editor(resolution=SCREEN_RESOLUTION)
    canvas = scene.canvas.rect
    assert all(canvas.collidepoint(point) for point in BITMAPPY_DEMO_POINTS)
```

`build_editor` is the Bitmappy tests' existing way to build `BitmapEditorScene` (use the helper the
other Bitmappy tests use; name the canvas attribute as the scene does). The script picks a
colour, then draws a small figure (a smiley: at least 20 pixels, two colours) with clicks and
drags. Add the pair to `EXPECTED_BUNDLED_DEMOS`.
- [ ] **Step 2: Run it.** Expected: ImportError.
- [ ] **Step 3: Write the script, add the recipe, record.** If the editor does not fit 800x480 (Review Focus 3), stop and report: the recorder's resolution is shared with every golden.
- [ ] **Step 4: Run** the test, `tests/replay/test_bundled_demos.py`, `tests/test_record_bundled_demos.py`. Expected: pass.
- [ ] **Step 5: Suite, then commit:** `Demos: Bitmappy drawing a sprite`.

---

### Task 7: The joystick demo, answering a recorded pad

**Files:**
- Modify: `scripts/demo_inputs.py` (`DEMO_PAD: DeviceDescriptor`: `JOYSTICK_KIND`, device index 0, instance id 0, name `'GlitchyGames Demo Pad'`, 6 axes, 12 buttons, 1 hat, 0 balls; `joystick_demo_script() -> InputScript`)
- Modify: `scripts/record_bundled_demos.py` (recipe with `stand_in_devices=(DEMO_PAD,)`, `polled_input=True`), `tests/workspace_expectations.py`, `tests/test_record_bundled_demos.py`
- Create: `joystick_demo/demos/pad.jsonl.gz` (600 frames)

**Interfaces:**
- Consumes: Task 1's stand-in devices and posted pad input; Task 4's gauge sprites (what the replay compares).

- [ ] **Step 1: Write the failing test** `test_the_joystick_script_moves_every_axis_presses_every_button_and_the_hat`: every axis of `DEMO_PAD` gets a JOYAXISMOTION, every button a down and an up, the hat each of its four directions and back to centre. Add the pair to `EXPECTED_BUNDLED_DEMOS`.
- [ ] **Step 2: Run it.** Expected: ImportError.
- [ ] **Step 3: Write the script** (axes swept smoothly over several frames each, so the readout visibly moves), add the recipe, record.
- [ ] **Step 4: Run** the tests and `tests/replay/test_bundled_demos.py`; replay the demo watched once (`uv run joystick-demo --replay-trace <path>`) and check the pad's column appears with moving values and gauges. Then prove the replay checks the readout: in a scratch copy of the demo, offset the axis marker by one pixel and replay `pad.jsonl.gz` headless (expected: a `sprite` divergence), then discard the copy. Expected: pass.
- [ ] **Step 5: Suite, then commit:** `Demos: the joystick demo answering a recorded pad`.

---

### Task 8: Docs, plans, verification

**Files:**
- Modify: `CLAUDE.md` (Bundled demos: every tile's demo, the recipe script, the stand-in devices option; remove "PaddleSlap's is ..." as the only one), `docs/architecture/game_packages.md` (where it describes a member's bundled demos), `docs/architecture/gameplay_replay.md` (the scripted-session recorder's options)
- Modify: `plans/2026-10-23-arcade-showcase.md` (status: sub-plan 2 done; Sub-plans item 2 links this plan; section 5 "Demos for all ten" lists the ten demos and their paths), `plans/future-features.md` #43, `plans/future-work.md` (longer attract scripts for Clockwork Keep and Brave Adventurer; the Sound Board's tile and demo, the owner's question; Task 4 removed the joystick demo's sprite entry)

- [ ] **Step 1:** Update the docs and plans as listed; this plan's status line says done with the commits.
- [ ] **Step 2: Verify:** `uv run pytest` (both drivers: every test passes, 0 driver differences, 100% coverage), `CI=true nox -s test`, `nox -s lint`, `nox -s static-analysis`, `uv run glitchygames verify` (every game's goldens and demos pass), `uv run glitchygames unmeasured` (lists the nine new demos for this machine: the run ledger measures them from now on, so they are in the benchmarks with the goldens).
- [ ] **Step 3: Commit:** `Docs: every Arcade tile has its bundled demo`.
