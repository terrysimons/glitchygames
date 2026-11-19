# Zombies Ain't My Neighbors, Feature 1: Registration and the 4-Player Title — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the game a registered workspace member whose title screen shows four player
slots, each blinking "PRESS START" in its own colour, that players join from the keyboard or any
of up to four gamepads, with a golden replay, a browser build and a docs page.

**Architecture:** One import package, `zombies_aint_my_neighbors`, in
`src/games/zombies-aint-my-neighbors/src/`. A pure, immutable join roster (`roster.py`) decides
which device holds which slot. The title scene (`title.py`) turns device presses into roster
changes and draws the roster as text sprites, pre-rendered once in `setup()`. A placeholder
"Feature presentation" scene (`feature_card.py`) shows who joined. Until gameplay exists, the
title scene is the game class, so the golden replay stays in one scene, as
`tests/replay/test_golden_replays.py` requires (header game == the class given to
`GameEngine`; the recording ends in it).

**Tech Stack:** Python 3.14, pygame-ce, pydantic (frozen, `extra='forbid'`), pytest +
pytest-mock, ruff, basedpyright, ty, uv.

**Spec:** [2026-11-14-zombies-aint-my-neighbors.md](2026-11-14-zombies-aint-my-neighbors.md)
(the master plan): decisions 4, 5, 10, 11, 16 and 17, and the owner's approval of this feature's
scope (2026-11-14: registration plus the title screen, no gameplay).

## Global Constraints

- Nothing under `src/glitchygames/` changes **except one line**: `'zombies_aint_my_neighbors':
  'games'` in `MEMBER_LAYERS` (`src/glitchygames/logical_names.py:21`). The owner approved
  exactly that line (2026-11-14: "register it if it's just that one").
- All game code lives in `src/games/zombies-aint-my-neighbors/`. Registration edits outside it
  are allowed: root config, test tables, `scripts/`, the browser build, docs (decision 17).
- Names: distribution `zombies-aint-my-neighbors`, import package `zombies_aint_my_neighbors`,
  console script `zombies-aint-my-neighbors`, title text "Zombies Ain't My Neighbors".
- Start control: **Enter** on the keyboard (`pygame.KSCAN_RETURN` and `pygame.KSCAN_KP_ENTER`),
  **START** on a gamepad (`pygame.CONTROLLER_BUTTON_START`). Never Space, Esc, Q, P, backtick,
  F3 or F4 for joining (the engine's pause, quit, AI console and debug overlay use them).
- Pause on the title: **P** (keyboard). The shared PauseScene resumes with Space.
- Every pad press is handled on **both** layers: `on_controller_button_down_event` (a mapped
  pad) and `on_joy_button_down_event` (unmapped pads, and every pad in `--input-mode joystick`,
  which scripted sessions force). Both carry `instance_id` and `button`.
- Every on-screen thing is a sprite. Text images are rendered once in `setup()` and swapped,
  never rendered per frame (decision 11).
- New data classes are pydantic `BaseModel`, frozen, `extra='forbid'`.
- Tests: pytest style, `mocker` only, real pygame and real display, assertions on pixels, test
  files named `test_zombies_aint_my_neighbors*.py`.
- Never commit unless the owner says so (global instructions). "Checkpoint" steps below mean:
  run the gate, then stop for the owner's word before committing.

## Decisions this plan makes (Claude's calls; the owner may overturn them)

| Decision | Value | Why |
|---|---|---|
| Player colours | P1 `(92, 230, 92)` ghoul green, P2 `(255, 140, 26)` pumpkin orange, P3 `(176, 97, 255)` séance violet, P4 `(51, 214, 255)` TV-glow cyan | Four hues far apart on the colour wheel, readable on black, on-theme |
| Blink | 0.5 s shown, 0.5 s hidden, all four slots in step, from `Scene.game_time` | Arcade attract rhythm; `game_time` replays exactly |
| Keyboard players | One (the whole keyboard is one device) | Two players sharing one keyboard is a later feature |
| Join | A start press from a device that holds no slot takes the lowest free slot; a fifth device is ignored | Arcade convention; predictable for 4 players |
| Begin | Once at least one player has joined, a start press from a **joined** device switches to the feature card | An unjoined device's first press joins it; it never also starts the game |
| Unplugging | A removed device gives up its slot | Hot-plug is part of the controller story |
| Feature card | Shows "FEATURE PRESENTATION" and each joined player's slot label in its colour; a start press from a joined device returns to the title with the roster kept | Placeholder until gameplay; keeps the loop testable |
| Text | Bundled `VeraBd` through `glitchygames.fonts.font_manager.bundled_font_path` | A font is an engine-native format; a pixel font can replace it in the sprite feature |
| Golden | Keyboard only, title scene only | Gamepad controls can't count as exercised (`Control.is_triggered_by` counts keyboard and mouse); scripted sessions can't hot-plug (Engine wishlist #6) |

## Review Focus

1. **The same device pressing start twice.** Expect: it keeps its one slot; it never fills two.
2. **A pad and the keyboard pressing on the same frame.** Expect: both join, in event order, in
   slots 1 and 2.
3. **A device unplugged on the feature card.** Expect: the card keeps working and drops that
   player; when the roster empties it returns to the title.
4. **Pads already plugged in when the game starts.** Expect: they can join. `on_input_device_added`
   is not called for them, so joining must not depend on that hook having run.
5. **Raw device events (added, removed, remapped) under `--no-unhandled-events`.** Expect: no
   exception. Each is overridden as a no-op on both scenes.

Each has its test in the task that owns the code (marked "Review Focus").

---

### Task 1: Register the member with a minimal title scene

**Files:**
- Modify: `src/games/zombies-aint-my-neighbors/pyproject.toml` (uncomment the console script; add
  `pydantic` to `dependencies`)
- Modify: `src/games/zombies-aint-my-neighbors/src/zombies_aint_my_neighbors/__init__.py`
  (re-export `main`)
- Create: `src/games/zombies-aint-my-neighbors/src/zombies_aint_my_neighbors/__main__.py`
- Create: `src/games/zombies-aint-my-neighbors/src/zombies_aint_my_neighbors/title.py`
- Create: tests `test_zombies_aint_my_neighbors_logical_names.py`, `_install_location.py` and
  `_entry_points.py`, modelled on Mr. Muncher's and PaddleSlap's
- Modify (registration, docs/architecture/game_packages.md steps 2 and 3): root
  `pyproject.toml`, `pyrightconfig.json`, `noxfile.py`, `wily.cfg`, `zensical.yml` (mkdocstrings
  path), `uv.lock`, `src/glitchygames/logical_names.py` (the one line),
  `tests/test_logical_names.py`, `tests/workspace_expectations.py`
  (`EXPECTED_ALL_CONSOLE_SCRIPTS`), `tests/replay/tools/test_settings.py` (`OUR_GAMES`), and
  whatever other hand-written table the guard tests below name

**Interfaces:**
- Produces: `zombies_aint_my_neighbors.main() -> None` (`GameEngine(game=TitleScene).start()`);
  `zombies_aint_my_neighbors.title.TitleScene(Scene)` with `NAME = "Zombies Ain't My Neighbors"`,
  `VERSION = '1.0'`, `__init__(self, options=None, groups=None)`, and a black
  `background_color`. Its logical name is `games.zombies_aint_my_neighbors.title:TitleScene`.

- [ ] **Step 1: Write the member's three standard tests.** The logical-names test asserts that
  every `Scene` subclass defined in `zombies_aint_my_neighbors.title` has the logical name
  `games.zombies_aint_my_neighbors.title:<qualname>`, and that at least one exists. The
  entry-points test asserts `importlib.import_module('zombies_aint_my_neighbors.__main__').main
  is zombies_aint_my_neighbors.main`, and that the console script resolves to it. The
  install-location test copies Mr. Muncher's.
- [ ] **Step 2: Run them and the guards, and watch them fail.**
  `uv run pytest --dummy-only --no-cov -q src/games/zombies-aint-my-neighbors/tests
  tests/test_workspace_config.py tests/test_suite_collection.py tests/test_logical_names.py`.
  Expected: import errors, because the member isn't in the workspace.
- [ ] **Step 3: Add the member to `[tool.uv.workspace] members`, then each registration entry**
  in the files listed above, run `uv lock` and read its diff (only the new member), and run
  `uv sync --all-extras --all-groups --all-packages`. Write `title.py`'s `TitleScene` and
  `main()`. Rerun the guards after each file and add the member to every further table they name.
- [ ] **Step 4: Run Step 2's command.** Expected: all pass. Also run `uv run
  zombies-aint-my-neighbors --help` and expect the engine's usage text.
- [ ] **Step 5: Lint and type-check.** `uv run --extra dev nox -s format-code lint-code
  lint-dependencies`, then `uv run basedpyright && uv run nox -s static-analysis-ty`. Expected:
  clean.
- [ ] **Step 6: Checkpoint.** Show the owner `git status` and the registration diff outside the
  member folder. Commit only on the owner's word.

### Task 2: The join roster

**Files:**
- Create: `src/games/zombies-aint-my-neighbors/src/zombies_aint_my_neighbors/roster.py`
- Test: `src/games/zombies-aint-my-neighbors/tests/test_zombies_aint_my_neighbors_roster.py`

**Interfaces:**
- Produces:
  - `MAXIMUM_PLAYERS: Final = 4`
  - `class DeviceKind(StrEnum)` with `KEYBOARD = 'keyboard'` and `GAMEPAD = 'gamepad'`
  - `class DeviceIdentity(BaseModel)` (frozen): `kind: DeviceKind`, `instance_id: int | None`
    (None for the keyboard; a gamepad's SDL instance id otherwise)
  - `class JoinedPlayer(BaseModel)` (frozen): `slot_index: int` (0 to 3), `device: DeviceIdentity`
  - `class JoinRoster(BaseModel)` (frozen), with field `slots: tuple[JoinedPlayer | None, ...]`
    (length `MAXIMUM_PLAYERS`) and these members:
    - `empty() -> JoinRoster` (classmethod)
    - `join(*, device) -> JoinRoster`
    - `leave(*, device) -> JoinRoster`
    - `holds(*, device) -> bool`
    - `joined_players` (property): `tuple[JoinedPlayer, ...]`, in slot order
    - `is_full` (property): `bool`
  - `PLAYER_COLOURS: Final[tuple[tuple[int, int, int], ...]]`, the four colours from the
    decisions table, indexed by slot

- [ ] **Step 1: Write the failing tests** (invariants first):
  - `test_a_slot_is_never_held_by_two_devices_and_a_device_never_holds_two_slots`: apply any
    sequence of joins and leaves over keyboard and gamepads 0 to 5 (a fixed table of sequences),
    and the devices in `slots` are always unique.
  - `test_the_first_device_takes_slot_one`: `empty().join(device=keyboard).slots[0].device ==
    keyboard`.
  - `test_joining_twice_keeps_one_slot` (Review Focus 1): joining the same device twice gives the
    same roster.
  - `test_a_fifth_device_is_ignored`: with four joined, `join` returns the roster unchanged and
    `is_full` is true.
  - `test_leaving_frees_the_slot_and_the_next_join_takes_the_lowest_free_slot`: with pads A, B and
    C joined, after B leaves, D lands in slot 1.
  - `test_the_keyboard_and_a_pad_with_instance_id_zero_are_different_devices`.
  - `test_the_roster_is_immutable`: assigning to `slots` raises `ValidationError`.
- [ ] **Step 2: Run them** (`uv run pytest --dummy-only --no-cov -q
  src/games/zombies-aint-my-neighbors/tests/test_zombies_aint_my_neighbors_roster.py`).
  Expected: FAIL, because `roster` doesn't exist.
- [ ] **Step 3: Implement `roster.py`** to the interfaces above. The models use
  `model_config = ConfigDict(frozen=True, extra='forbid')`, and `join` and `leave` return
  `self.model_copy(update=...)`.
- [ ] **Step 4: Run them.** Expected: PASS. Then run ruff, basedpyright and ty on the member.

### Task 3: Title slots, drawn and blinking

**Files:**
- Create: `src/games/zombies-aint-my-neighbors/src/zombies_aint_my_neighbors/text.py`
- Modify: `title.py`
- Test: `src/games/zombies-aint-my-neighbors/tests/test_zombies_aint_my_neighbors_title.py`

**Interfaces:**
- Consumes: `JoinRoster`, `PLAYER_COLOURS` and `MAXIMUM_PLAYERS` (Task 2).
- Produces:
  - In `text.py`: `title_font(*, size: int) -> pygame.font.Font` (bundled `VeraBd`, uncached:
    the scene calls it once per size in `setup()` and keeps the fonts, so there is no
    module-level state for `tests/test_process_state_guard.py` to flag),
    `render_text(*, font, text: str, colour) -> pygame.Surface` (antialiased with
    `FontManager.antialias()`), and `class TextPicture(Sprite)`, which centres an image on a
    point and has `show_image(*, image: pygame.Surface)` and `set_shown(*, shown: bool)`. It
    writes `visible` only when it changes, and marks itself dirty.
  - In `title.py`: `BLINK_SECONDS: Final = 0.5`. `TitleScene.slot_pictures: tuple[TextPicture,
    ...]`, one per slot, laid out left to right across the bottom quarter of the screen.
    `TitleScene.roster: JoinRoster` (starts at `JoinRoster.empty()`, or at a roster passed as
    `__init__(..., roster=None)`). `TitleScene.replay_arguments()` returns the roster.
  - The text in each slot: unjoined, `"P{n}"` over `"PRESS START"`, blinking. Joined,
    `"P{n} READY"` over `"KEYBOARD"` or `"GAMEPAD"`, steady. Always in the slot's colour. The
    game's title sits in the upper half.
  - Every image (four slots in two states, plus the title) is rendered once in `setup()` and
    swapped by `show_image`.

- [ ] **Step 1: Write the failing tests:**
  - `test_each_unjoined_slot_shows_press_start_in_its_players_colour`: after `setup()` and one
    drawn frame, each slot's area holds pixels of exactly `PLAYER_COLOURS[slot]` (counted, more
    than zero), and no other slot's colour.
  - `test_unjoined_slots_blink_together_every_half_second`: with `game_time` at 0.25 s every slot
    is shown; at 0.75 s every slot is hidden; at 1.25 s every slot is shown again. Drive it
    through `dt_tick`.
  - `test_a_joined_slot_is_steady`: a roster with P2 joined, passed to `__init__`, keeps slot 2
    shown at 0.75 s while slots 1, 3 and 4 are hidden.
  - `test_the_title_scene_renders_no_text_after_setup`: patch `render_text` with
    `mocker.spy` after `setup()`, run 120 `dt_tick` frames, and expect zero calls (decision 11).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement `text.py` and the slot drawing in `title.py`.** Set the pose
  (`set_shown`) in `dt_tick`, never in `update()` (CLAUDE.md, World Space).
- [ ] **Step 4: Run them.** Expected: PASS. Then lint and type-check.

### Task 4: Joining from the keyboard and gamepads

**Files:**
- Modify: `title.py`
- Test: `test_zombies_aint_my_neighbors_title.py`

**Interfaces:**
- Consumes: `JoinRoster.join`, `leave` and `holds`, plus `DeviceIdentity` (Task 2).
- Produces, on `TitleScene`:
  - `KEYBOARD_START_SCANCODES: Final = frozenset({pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER})`
  - `GAMEPAD_START_BUTTON: Final = pygame.CONTROLLER_BUTTON_START`. In joystick mode an unmapped
    pad's START is the same number; the engine's `gamepad_choice.py` reads both layers by the
    same numbers.
  - `on_key_down_event`: a start scancode presses start for the keyboard identity; **P** calls
    `self.pause()`; anything else goes to `super()`.
  - `on_controller_button_down_event` and `on_joy_button_down_event`: `GAMEPAD_START_BUTTON`
    presses start for `DeviceIdentity(kind=GAMEPAD, instance_id=event.instance_id)`.
  - `_press_start(*, device: DeviceIdentity) -> None`: joins if unjoined; if joined, begins
    (Task 5).
  - `on_input_device_removed(self, *, device)`: leaves for that pad.
  - No-op overrides for `on_joy_device_added_event`, `on_joy_device_removed_event`,
    `on_controller_device_added_event`, `on_controller_device_removed_event` and
    `on_controller_device_remapped_event`.
  - Every other pad button and key-up the scene doesn't use is handled as a no-op or passed to
    `super()`, so `--no-unhandled-events` never raises.

- [ ] **Step 1: Write the failing tests.** Use the harness's stand-in devices
  (`tests/input/stand_in_devices.py`; unit tests may hot-plug with
  `install_stand_in_devices(..., plugged_in_at_start=False)` and
  `engine.process_joystick_event(...)`, as `src/demos/joystick-demo/tests/test_joystick_demo.py`
  does):
  - `test_enter_joins_the_keyboard_in_slot_one`
  - `test_keypad_enter_also_joins_the_keyboard`
  - `test_a_controller_start_joins_that_pad`: a controller event, instance 9, lands in the next
    free slot.
  - `test_a_joystick_start_joins_that_pad_in_joystick_mode`: the same with a JOYBUTTONDOWN event.
  - `test_space_escape_and_other_buttons_never_join`
  - `test_a_pad_and_the_keyboard_on_the_same_frame_both_join_in_event_order` (Review Focus 2)
  - `test_a_pad_plugged_in_before_the_game_starts_can_join` (Review Focus 4)
  - `test_unplugging_a_pad_frees_its_slot_and_its_slot_blinks_again`
  - `test_raw_device_events_are_handled_under_no_unhandled_events` (Review Focus 5)
  - `test_p_pauses`: `next_scene` is a `PauseScene`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the handlers** to the interfaces above.
- [ ] **Step 4: Run them.** Expected: PASS. Then lint and type-check.

### Task 5: The feature card

**Files:**
- Create: `src/games/zombies-aint-my-neighbors/src/zombies_aint_my_neighbors/feature_card.py`
- Modify: `title.py` (begin), the logical-names test (now covers both modules)
- Test: `src/games/zombies-aint-my-neighbors/tests/test_zombies_aint_my_neighbors_feature_card.py`

**Interfaces:**
- Consumes: `JoinRoster`, `TextPicture`, `render_text` and `title_font`.
- Produces: `FeatureCardScene(Scene)`, with `__init__(self, options=None, groups=None, *,
  roster: JoinRoster)` and `replay_arguments()` returning the roster. It shows "FEATURE
  PRESENTATION" and one `"P{n}"` label per joined player in its colour. A start press from a
  joined device sets `next_scene = TitleScene(options=..., roster=self.roster)`. A removed
  device leaves; an emptied roster returns to the title. It has the same no-op device-event
  overrides as the title. `TitleScene._press_start` sets `next_scene =
  FeatureCardScene(options=self.options, roster=self.roster)` when the device is already joined.

- [ ] **Step 1: Write the failing tests:**
  - `test_a_joined_players_second_start_begins_the_feature`
  - `test_an_unjoined_devices_first_start_only_joins`
  - `test_the_card_shows_each_joined_player_in_their_colour` (pixels)
  - `test_start_on_the_card_returns_to_the_title_with_the_roster_kept`
  - `test_unplugging_the_last_player_on_the_card_returns_to_the_title` (Review Focus 3)
  - `test_the_card_handles_raw_device_events`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement `feature_card.py` and the begin path.** `feature_card` imports
  `TitleScene` inside the method that builds it, so the two modules don't import each other at
  load time.
- [ ] **Step 4: Run them.** Expected: PASS. Then lint and type-check.

### Task 6: Golden replay, golden trace and controls

**Files:**
- Modify: `scripts/golden_inputs.py` (`zombies_aint_my_neighbors_script`,
  `zombies_aint_my_neighbors_controls`), `scripts/record_golden_traces.py` (`GAME_SCENES`
  `'zombies_aint_my_neighbors.title:TitleScene'`, `GAME_MODULES`, `SCRIPT_BUILDERS`),
  `scripts/record_scripted_session.py` (`CONTROLS_TAIL_BUILDERS`, and the docstring's command
  list), `tests/replay/golden_replay_controls.py` (`GAMEPLAY_ACTION_MAPS`,
  `ENGINE_SCENE_CONTROLS`, `UNEXERCISED_CONTROLS`),
  `tests/replay/test_record_scripted_session.py`, `tests/workspace_expectations.py`
  (`EXPECTED_GOLDENS`, `EXPECTED_GAME_CONSOLE_SCRIPTS`), root `pyproject.toml`
  `[tool.glitchygames] games`
- Create: `src/games/zombies-aint-my-neighbors/tests/fixtures/replays/golden.jsonl.gz`
  (recorded), plus the golden trace the recorder writes
- Modify: `title.py`, adding `TitleScene._create_action_map(*, options) -> ActionMap` (static),
  which binds `start` (Enter, keypad Enter, controller START) and `pause` (P), and routing the
  handlers through it. Its behaviour is unchanged, so Task 4's tests are the regression check.

**Interfaces:**
- Consumes: `TitleScene` (Tasks 1 to 4).
- Produces:
  - The golden script, keyboard only, 60 frames per second. Frame 30: tap Enter (P1 joins). Then
    run long enough to see two full blink cycles of slots 2 to 4.
  - The controls tail: `_pause_with(tail, key=pygame.K_p, ...)`, resume with Space, then tap
    Enter (the begin press goes to the card) and Enter again (back to the title), then
    `tail.at(<last frame>, press(pygame.K_q))`. The recording ends in `TitleScene`, as
    `test_golden_replays.py` requires.
  - `ENGINE_SCENE_CONTROLS`: `PAUSE_SCENE_CONTROLS`. `UNEXERCISED_CONTROLS`: the controller START
    with `NO_GAMEPAD_IN_THE_SESSION`, plus the PauseScene keyboard-quit and gamepad entries,
    copied from Mr. Muncher's.

- [ ] **Step 1: Add the expectations first** (`EXPECTED_GOLDENS`,
  `EXPECTED_GAME_CONSOLE_SCRIPTS`, the controls tables), and run
  `uv run pytest --dummy-only --no-cov -q tests/replay/test_golden_replays.py
  tests/world/test_golden_traces.py tests/test_workspace_packages.py -k zombies`. Expected: FAIL
  (no golden).
- [ ] **Step 2: Write the two builders and record.** `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
  uv run python -m scripts.record_scripted_session --game zombies_aint_my_neighbors --frames N`,
  then the golden trace through `scripts/record_golden_traces.py`. Read the recording's scenes:
  Title, Pause, Title, FeatureCard, Title.
- [ ] **Step 3: Rerun Step 1's command.** Expected: PASS. Then run `uv run
  zombies-aint-my-neighbors --verify` (expected: golden replays with no differences) and the
  member's tests (Task 4's still pass with the action map).
- [ ] **Step 4: Checkpoint.** Commit only on the owner's word. The `replay-metrics` hook refuses
  untracked files under `src/`, so stage the whole member and its registration.

### Task 7: Browser build, docs and the whole gate

**Files:**
- Modify: `scripts/build_browser_bundle.py` (`GAMES['zombies-aint-my-neighbors'] =
  GameSpecification(module='zombies_aint_my_neighbors.title', scene_class='TitleScene',
  title="Zombies Ain't My Neighbors", member_packages=('zombies_aint_my_neighbors',))`, and a
  `TOUCH_LAYOUTS` entry: centre `TouchButton('Start', 'Enter')` and `TouchButton('Pause',
  'KeyP')`), `tests/test_build_browser_bundle.py`, `tests/test_browser_touch_controls.py` if it
  lists games
- Create: `src/games/zombies-aint-my-neighbors/tests/test_zombies_aint_my_neighbors_touch_controls.py`
  (as Mr. Muncher's: the layout's keys are ones the game handles)
- Create: `docs/games/zombies_aint_my_neighbors.md` (what it is, how to play, controls, an "Its
  package" line), and add it to `zensical.yml` `nav` and the Games API Reference
- Modify: `README.md` and `CLAUDE.md` (the game lists and `uv run` lines),
  `plans/2026-11-14-zombies-aint-my-neighbors.md` (Feature plans: this plan built; Engine
  wishlist entries filed)

- [ ] **Step 1: Write the touch-controls test, and add the bundle test's expectation.** Run them;
  expected: FAIL.
- [ ] **Step 2: Add the `GAMES` and `TOUCH_LAYOUTS` entries, the docs page and its nav, and the
  README and CLAUDE.md lines.**
- [ ] **Step 3: Build and serve the bundle.** Run `uv run python -m scripts.build_browser_bundle
  zombies-aint-my-neighbors --output <scratchpad>/bundle` and expect `zombies_aint_my_neighbors.zip`
  in its `pyscript.toml`. Then run `uv run nox -s browser -- zombies-aint-my-neighbors` and check
  the title by eye in Chrome: four blinking slots, Enter joins. Say what was not checked (pads in
  the browser are Engine wishlist #4).
- [ ] **Step 4: Run the whole gate after the last edit:** ruff (format and lint), basedpyright,
  ty, the full `uv run pytest` (both drivers, 100% coverage), `uv build --package
  zombies-aint-my-neighbors`, and `uv run nox -s lint-docs`. Expected: all green. Name each
  tool's scope in the report.
- [ ] **Step 5: Grep every `.md` for stale statements** ("five games", game lists) and fix them.
- [ ] **Step 6: Checkpoint.** Report to the owner. Commit and open the PR only on their word.
