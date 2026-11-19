# Zombies Ain't My Neighbors, Feature 12: the intro and the title's idle loop

Master plan: [2026-11-14-zombies-aint-my-neighbors.md](2026-11-14-zombies-aint-my-neighbors.md)
(decisions 6 and 15; "What is left of level 1"). The intro's sprites are listed in the character
BOM, section 7 ([2026-11-14-zombies-aint-my-neighbors-2-character-bom.md](2026-11-14-zombies-aint-my-neighbors-2-character-bom.md)).
The attract demo is feature plan 13, which fills the loop's second slot.

Status: BUILT (2026-11-19), Tasks 1 to 5 committed; Task 6's browser rumble check waits for the
owner. The design was agreed in conversation on 2026-11-19; a builder check's eight questions were
settled as Claude's calls (marked below); the owner changed decision 2 the same day (every
launch, no saved flag).

## Intent

The game is pitched as a four-player arcade cabinet (the title's four blinking PRESS START
slots, decision 10). The intro tells its story: four kids at a sleepover, VR headsets on, and the
monsters come out of the TV. The owner wants it to behave as a cabinet's does: it plays by
itself when nobody is playing, a press always gets you straight back to the title, and it
opens every launch, skippable with any key or button. Rumble is for someone holding a pad, never
for pads lying on a table.

## Decisions (the owner, 2026-11-19)

| # | Decision | Why |
|---|----------|-----|
| 1 | **The intro plays in the title's idle loop**, arcade style: the game opens on the title; after the title has stood idle, the intro plays, then the attract demo (feature 13), then the title again, round and round. Any key or button returns to the title | The cabinet pitch; nobody waits at start-up; the intro and the demo share one home |
| 2 | **And at every launch**, before the title; any key or button skips it. First "once on the very first launch" (option 2 added to option 1: "With 2"), with a saved flag; changed the same day ("lets always run it then, but let the user skip with a button press"; "Yes, what you heard") once a side agent noted that a browser whose saves fail would never show it. No saved flag | Every player gets the story; a skip costs one press; nothing depends on saves working |
| 3 | **No rumble while unattended**: nothing in the idle loop rumbles, neither the intro nor the demo ("No rumble on the demo"). The launch showing rumbles every connected pad, in controller mode (decision 15) | Someone has just started the game; in the loop the pads may be on a table |
| 4 | **Built as a timeline in one scene** (approach A, Claude's recommendation, taken) | The whole intro reads top to bottom; retiming is editing numbers; tests can ask "at 6.0 s the TV bursts" |

## Approaches considered

- **A. A timeline in one scene (chosen).** `IntroScene` holds one table of timed cues (at a time,
  a sprite plays an animation; a shake; a rumble), fired on `Scene.game_time`. Deterministic,
  skippable at any moment, one place to retime, simple to test.
- **B. Sprites chain themselves.** Each animation's "Then" (the BOM's column) starts the next as
  it ends, and the scene reacts to animation ends. Follows the BOM literally, but the order is
  spread across many sprites and callbacks: hard to retime, hard to test as a whole.
- **C. A recording played back.** A replay drives a game from its input, and the intro has none;
  rumbling at launch only would be awkward. Rejected.

## Goals

- The idle loop: TITLE, idle for `IDLE_SECONDS`, then INTRO, then (feature 13) the ATTRACT DEMO,
  then TITLE; any key or button at any point returns to the title.
- The launch showing: CRT power-on, then INTRO, then TITLE, at every launch, skipped wherever
  the CRT power-on is skipped.
- The intro itself, as the master plan's "The intro" section describes: vignettes of the
  sleepover framed in a dark oval; the TV flickers, bulges and bursts; hands reach out; a Lawn
  Zombie climbs out; the screen shakes; at launch every connected pad rumbles; cut to the
  title.
- The intro's 9 sprites, 46 frames (BOM section 7), drawn the way this game draws its art (rigs in
  `zombies_aint_my_neighbors/art/` writing TOML), checked against the sprite schema like every
  shipped sprite.

## Non-goals

- The attract demo (feature 13). Until it lands the loop is TITLE, INTRO, TITLE.
- A menu entry or key to replay the intro: waiting on the title replays it (Claude's call; the
  owner may ask for one).
- Narration (decision 14, roadmap #90).
- Any engine change (decision 12). Engine gaps go in the master plan's wishlist.

## Anti-goals (a failure even if it works)

- A pad rumbling when nobody touched the game since it was last idle.
- A press that wakes the game also joining a player, or starting a stage.
- The intro playing again when a title is rebuilt (after the intro, Back from a STAGE n card,
  quitting a stage, the game over): it opens a launch only.
- A golden replay or bundled demo that crosses into the loop without meaning to. The loop is
  deterministic game logic (it runs on `Scene.game_time`), so a recording that idles past
  `IDLE_SECONDS` records the intro and replays it faithfully; the goldens must simply stay
  shorter than that (the title's is 240 frames), and a test holds them to it.
- The loop playing over a player who has joined on the title.

## How it behaves

### The idle loop

```
CRT power-on → TITLE ──(idle IDLE_SECONDS)──► INTRO ──► ATTRACT DEMO (feature 13) ──► TITLE …
                 ▲                              │               │
                 └────────── any key or button ─┴───────────────┘
```

- `IDLE_SECONDS = 20.0` (Claude's call: long enough to read the title and pick up a pad, short
  enough to start while someone's still looking; one constant).
- The loop runs in every mode, live, recorded, replayed and on the dummy driver (Claude's call,
  after the builder check: it is ordinary deterministic game logic, so replays reproduce it, and
  gating it would need the engine-private reasons the CRT power-on uses). This replaces the
  first playback's "only on a live title".
- "Idle" is the title's own `Scene.game_time` since its last activity. It freezes while the game
  is paused (the pause scene is the active scene then) and starts from zero on a rebuilt title.
  Activity is a key going down, a pad button going down, or a join; stick and trigger movement
  is not (a resting stick drifts). The title needs an event hook for these beside
  `_press_start`.
- Only an idle title with **no slot joined and no run** loops: a joined slot or a run held (Back
  from a STAGE n card) means someone is playing.
- From the loop's intro (and the demo), the press that returns to the title is consumed: the
  new title ignores the keys and pad buttons held as it opens (read from the frame's
  `current_input()`), each until it is seen up, so the key-up, a held button or a key repeat
  can't join anyone, while every other key and button counts at once (Claude's call: the arcade
  feel; no stray join. First written "until every key and pad button is up"; the final review's
  I1 found that one input held for good, a latched toggle, then locked every device out). The intro itself handles every event it can be sent:
  key down and up, pad buttons, axes, devices added and removed.
- The intro returns to a fresh title whose idle count starts at zero, with an empty roster and
  no run (the only title that loops).

### The launch showing

```
Every launch:  CRT power-on → INTRO (rumble; any key or button skips) → TITLE
```

- No saved flag (decision 2, as changed): nothing depends on saves working, so the browser,
  whose saves may fail, shows it like every other platform.
- It plays only where the CRT power-on would. The game asks the engine's public functions the
  same question the engine asks:
  `crt_power_on.should_play(mode=crt_power_on.resolve_mode(option=options.get('crt_power_on'),
  environment=os.environ), video_driver=<the SDL video driver>, options=options)` (not on the
  dummy video driver, not with `replay_trace`, `record_trace`, `audit` or `rebaseline`, not with
  `--crt-power-on off`). That repeats one engine call in the game (no engine change, decision
  12); a public "would the power-on play" answer goes in the master plan's wishlist.
- The launcher's `first_scene` stays the title (or the neighborhood for a recording made
  there); the title, on its first frame, hands over to the intro when it is the **opening**
  title and the showing is allowed (Claude's call: keeps `first_scene` and the goldens' starting
  scene as they are).
- The opening title is the one the engine builds at launch: `TitleScene` gains
  `opening: bool = True`, and every other place that builds a title passes `opening=False` (the
  intro's hand-back, the STAGE n card's Back, quitting a stage, the game over), so a rebuilt
  title never plays the intro again. A test checks each of those hand-offs.

### The intro, as a timeline

One table, in `intro.py`, read top to bottom. The times are a first cut (about 8 s; the BOM's
frame timings fix each animation's own length); tuning them is editing the table:

| At (s) | Cue |
|---|---|
| 0.0 | the oval fades in; the four kids `sit` in their bags, the TV plays `show` (the host), the lamp and the snack bowl `still` |
| 4.0 | TV `static`; lamp `flicker` |
| 5.5 | TV `bulge` |
| 6.0 | TV `burst`; kids `startled`; screen shake; **rumble every connected pad, launch showing only** |
| 6.3 | hands `reach` |
| 6.8 | Lawn Zombie `climb-out` |
| 8.0 | to the title (the loop: the demo, once feature 13 lands); the zombie's `climb-out` ends near 7.3 s, and the beat it holds before the cut is meant |

- Cues fire on `Scene.game_time` crossing their time, each exactly once, on the frame it is
  crossed (a long frame fires every cue it crosses, in order).
- Every object is a sprite in the scene's groups (CLAUDE.md), the dark oval included (one
  full-screen sprite with an oval hole, drawn once in `setup()`).
- Intro sprites are not collidable, palette 15, anchored `bottom`, no shadows (BOM section 7).
- Sounds: effects only, no score (Claude's call): the TV's static, the bulge, the burst, and the
  zombie's groan from the game's existing sounds where one fits; any new one is a TOML version 1
  sound requested in `setup()` (decision 11). The intro is silent of the stage loop.
- Shake: `Scene.shake(Shake(...), targets=ShakeTarget.SCREEN)` at the burst.
- Rumble: in the launch showing only, every pad `Scene.input_devices` holds then, through the
  same `rumble(low_frequency=, high_frequency=, duration_milliseconds=)` call the neighborhood's
  `_tv_destroyed` makes, with the intro's own strength and length constants. "Controller mode"
  (decision 15) means a pad is connected: nobody has joined at launch, so no joined
  device can be asked, and the engine has no keyboard-only mode (`InputMode` is auto, joystick,
  controller). No pad, no rumble. In the loop the rumble cue does nothing.
- Skipping: any key or button on any frame ends the intro at once, to the title; the press is
  consumed (above).

## Constraints

- No engine changes (decision 12); all code in `src/games/zombies-aint-my-neighbors/`
  (decision 16).
- Heavy work before play (decision 11): the intro's sprites load and its sounds compile in
  `setup()`. The Pi and the browser set the frame budget.
- Clocks and randomness by the engine's rules: `Scene.game_time` for the cues and the idle
  count; any randomness (the static's noise) from a named stream.
- Unhandled events raise in every test (`--no-unhandled-events`): the intro handles every event
  it can receive (keys, pad buttons, device added and removed).
- The title's golden (`golden.jsonl.gz`, 240 frames) and the neighborhood's golden must replay
  unchanged.
- Rumble in the browser build is unverified (master plan: "Test controller rumble in the
  browser build"). The intro must work without it: a rumble that does nothing there is fine.
  Check it during this feature and record the answer in the master plan and the wishlist (#4).

## Tests (behaviours)

- The timeline: each cue fires once, at its time, in order, including across a long frame; the
  scene hands over at its end.
- Skipping: a key, a pad button, at the start, mid-way and on the last frame, ends it on that
  frame, and the press neither joins nor starts a stage.
- The idle loop: the title hands over to the intro after exactly `IDLE_SECONDS` idle; any press
  or join restarts the count; a joined title never hands over; the intro returns to a title
  whose count starts at zero.
- The launch: the opening title, with the showing allowed, hands over to the intro on its first
  frame, at every launch; on the dummy driver, under each of `replay_trace`, `record_trace`,
  `audit`, `rebaseline`, and with `--crt-power-on off`, it never does; a title built with
  `opening=False` never does, and each place that builds one (the intro, the card's Back,
  quitting a stage, the game over) passes it.
- Rumble: the launch showing rumbles every connected pad, once, at the burst; the loop's
  intro rumbles nothing; with no pad connected nothing rumbles and nothing raises (stand-in
  devices, `tests/input/stand_in_devices.py`).
- The shake is asked for at the burst (screen target).
- Every intro sprite loads, matches the schema (`glitchygames.testing.sprite_files`), and has
  each BOM animation with its frame count and timing.
- The two goldens replay unchanged, and every golden or bundled demo that starts on the title
  is shorter than `IDLE_SECONDS` of frames.
- A title holding a run, or with a slot joined, never loops; the new title after a skip ignores
  a key still held, and a key-up, until everything is up.
- Pixels, not calls: the oval's corners are dark and its centre shows the scene.

## Left to the builder

- The rigs' drawing of the 9 sprites within the BOM's sizes, palettes and timings; a contact
  sheet for the owner to look at before they ship (as the other features did).
- The oval's exact shape and fade time.
- Which existing sounds fit; any new ones' design.
- The intro's code layout beyond `intro.py`, and how the title passes "launch" or "loop" to
  the intro.

---

# Implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** the title's idle loop, the launch showing and the intro scene above, with the
intro's 9 sprites drawn.

**Architecture:** a pure timeline (`intro_timeline.py`: cues and which ones a frame crosses), an
`IntroScene` that owns the sprites and acts on crossed cues (`intro.py`), the "may we show it"
question (`launch_showing.py`), and the title gaining `opening`, an idle count, a first-frame
hand-over and a wait for released input. The art follows the
game's rigs: `art/intro_rig.py` draws, `art/build.py` writes TOML.

**Tech stack:** Python 3.15 (parses as 3.14), pygame-ce, the GlitchyGames engine (scenes, sprites,
`Shake`, `InputDevices`, `crt_power_on`), pydantic, pytest with `mocker`.

**Spec:** this file's design above (the sections from "Intent" to "Left to the builder").

Paths below are relative to `src/games/zombies-aint-my-neighbors/` unless they start with
`src/glitchygames/`, `tests/` (the engine's) or `plans/`. `Z` is
`src/zombies_aint_my_neighbors/`; `T` is `tests/`.

## Global constraints

- No engine changes (decision 12); all code in `src/games/zombies-aint-my-neighbors/`.
- `IDLE_SECONDS = 20.0`; timeline first cut: 0.0, 4.0, 5.5, 6.0, 6.3, 6.8, 8.0 (the table above).
- Intro sprites: not collidable, palette 15 (the climbing zombie 14), anchor `bottom`, no shadows,
  the BOM section 7 sizes, animations, frame counts, intervals and loop flags exactly.
- Every object is a sprite in the scene's groups; heavy work in `setup()`.
- Time from `Scene.game_time` only; randomness only from named streams.
- `--no-unhandled-events` holds in every test: each scene handles every event it can be sent.
- Data classes are pydantic `BaseModel` (`frozen=True`, `extra='forbid'`); keyword arguments;
  no `assert` outside tests; `mocker`, never `unittest.mock`.
- Ruff, then basedpyright and ty, then tests, per task; the whole gate after the last task.
- Commits only when the owner says so (they asked for this feature's commits by task when they
  approve execution); pushes need `SKIP=raspberry-pi-replay-metrics` while the Pi is down.

## Review focus

1. A key held down through the skip (or a key repeat) reaching the new title as a press: no join.
   Task 5 pins it (`test_a_key_still_held_after_a_skip_never_joins`).
2. A pad unplugged or plugged in during the intro: handled, no raise, the intro goes on. Task 3
   pins it (`test_a_pad_plugged_in_or_out_during_the_intro_changes_nothing`).
3. A very long frame (a hitch of several seconds) mid-intro: every cue it crosses fires once, in
   order, and the hand-over still happens once. Task 2 and Task 3 pin it.
4. A title rebuilt anywhere (the intro, a card's Back, quitting a stage, the game over) playing
   the intro again. Task 4 pins each hand-off
   (`test_every_title_built_after_the_launch_is_not_the_opening_one`).
5. Pause during the title's idle count, or during the intro: the count and the timeline freeze
   with `game_time`. Task 5 pins the title's; Task 3 the intro's
   (`test_pausing_the_intro_holds_its_timeline`).

---

### Task 1: The intro's sprites

**Files:**
- Create: `Z/art/intro_rig.py` (draws every intro frame as a `rig.Grid`, on the kids' canvas,
  shading and outline as `tv_rig.py` does; the static from a seeded generator so builds never
  change).
- Modify: `Z/art/build.py` (one `*_sprite_text()` per intro sprite through
  `character_sprite_text`, tags `('intro',)` plus the sprite's kind; `build()` writes them).
- Create (generated): `Z/sprites/intro_bag_dex.toml`, `intro_bag_marisol.toml`,
  `intro_bag_theo.toml`, `intro_bag_june.toml`, `intro_tv.toml`, `intro_hands.toml`,
  `intro_zombie.toml`, `intro_lamp.toml`, `intro_snacks.toml`.
- Modify: `Z/art/contact_sheet.py` (an `intro` sheet beside the kids').
- Test: `T/test_zombies_aint_my_neighbors_art.py`.

**Interfaces:**
- Produces: `intro_rig.INTRO_ANIMATIONS: Mapping[str, tuple[AnimationSpec, ...]]` keyed by
  sprite file stem; `intro_rig.intro_frames(*, sprite: str) -> dict[str, tuple[Grid, ...]]`;
  the sprite file stems above, and these animation names: bags `sit`, `startled`; TV `show`,
  `static`, `bulge`, `burst`, `switch-off`; hands `reach`; zombie `climb-out`; lamp `still`,
  `flicker`; snacks `still`.

- [ ] **Step 1: Write the failing tests**
  - `test_the_intro_bom_totals_46_frames`: summing frames over `INTRO_ANIMATIONS` gives 46
    (4 x (2 + 2) + 18 + 4 + 4 + 3 + 1).
  - `test_each_intro_file_holds_every_bom_animation_with_its_timing_and_loop` (parametrized
    over the 9 stems): each loaded `AnimatedSprite` has exactly the BOM's animations, frame
    counts, intervals and loop flags (table above, BOM section 7).
  - `test_every_intro_frame_has_its_bom_size_and_keeps_to_its_palette`: bags 48x32; TV, hands,
    zombie 64x64; lamp, snacks 32x32; at most 15 colours besides magenta (the zombie 14).
  - `test_every_shipped_intro_sprite_matches_the_schema`: through
    `glitchygames.testing.sprite_files.check_values_match_the_schema`.
  - `test_building_twice_writes_the_same_files`: two builds into `tmp_path` give equal bytes.
- [ ] **Step 2: Run them; expect failures** (`uv run pytest --dummy-only -n0 T/test_zombies_aint_my_neighbors_art.py -k intro`: no `intro_rig`).
- [ ] **Step 3: Implement `intro_rig.py` and the `build.py` entries; run
  `uv run python -m zombies_aint_my_neighbors.art.build`.**
- [ ] **Step 4: Run the tests; expect them to pass.**
- [ ] **Step 5: Render the intro contact sheet to a PNG and show it to the owner; stop for
  their review** (the art gate the other features used). Rework until approved.
- [ ] **Step 6: Commit** (rig, build, generated TOML, contact sheet, tests).

### Task 2: The timeline

**Files:**
- Create: `Z/intro_timeline.py`.
- Test: `T/test_zombies_aint_my_neighbors_intro.py` (new: a distinct subject).

**Interfaces:**
- Consumes: Task 1's stems and animation names.
- Produces:
  - `class CueKind(StrEnum)`: `ANIMATE`, `OVAL_FADE_IN`, `SHAKE`, `RUMBLE`, `END`.
  - `class IntroCue(BaseModel)` (frozen, `extra='forbid'`): `at_seconds: float`,
    `kind: CueKind`, `actor: str | None = None`, `animation: str | None = None`; a validator
    refuses `ANIMATE` without both, and any other kind with either.
  - `INTRO_TIMELINE: Final[tuple[IntroCue, ...]]`, sorted by `at_seconds`, the design's table:
    0.0 oval fade-in and every actor's first animation; 4.0 TV `static`, lamp `flicker`;
    5.5 TV `bulge`; 6.0 TV `burst`, the four bags `startled`, `SHAKE`, `RUMBLE`; 6.3 hands
    `reach`; 6.8 zombie `climb-out`; 8.0 `END`.
  - `cues_crossed(*, timeline: Sequence[IntroCue], before_seconds: float, now_seconds: float) -> tuple[IntroCue, ...]`:
    the cues with `before_seconds <= at_seconds < now_seconds`, in timeline order.
  - `INTRO_SECONDS: Final = 8.0` (the `END` cue's time).

- [ ] **Step 1: Write the failing tests**
  - `test_the_timeline_is_in_order_and_ends_once`: sorted; exactly one `END`, last.
  - `test_each_cue_fires_once_frame_by_frame`: stepping 0 to 9 s by 1/60 and collecting
    `cues_crossed` gives `INTRO_TIMELINE` exactly once each, in order.
  - `test_a_long_frame_fires_every_cue_it_crosses_in_order`: `before=3.9, now=6.5` gives the
    4.0, 5.5, 6.0 and 6.3 cues in order.
  - `test_a_cue_on_a_frame_boundary_fires_on_the_frame_that_starts_at_it`: `before=6.0` fires the
    6.0 cues; `now=6.0` does not.
  - `test_a_cue_needs_an_actor_and_animation_exactly_when_it_animates`: `IntroCue` raises
    `ValidationError` for each wrong combination.
  - `test_every_animate_cue_names_a_sprite_and_an_animation_it_has`: against
    `intro_rig.INTRO_ANIMATIONS`.
- [ ] **Step 2: Run; expect failures.**
- [ ] **Step 3: Implement `intro_timeline.py`.**
- [ ] **Step 4: Run; expect passes.**
- [ ] **Step 5: Commit.**

### Task 3: The intro scene

**Files:**
- Create: `Z/intro.py`.
- Modify: `Z/sounds.py` only if a new sound is needed (prefer the existing `TV_SPAWN`,
  `TV_BREAK`, `TV_DESTROYED`, `GROANS`); a new one goes in `Z/sounds/sounds.toml` (version 1)
  and `EVERY_SOUND`.
- Test: `T/test_zombies_aint_my_neighbors_intro.py`.

**Interfaces:**
- Consumes: `INTRO_TIMELINE`, `cues_crossed`, `CueKind` (Task 2); the stems (Task 1);
  `TitleScene` (`Z/title.py`, gaining `awaiting_release` in Task 5: until then pass nothing).
- Produces:
  - `class IntroShowing(StrEnum)`: `LAUNCH`, `LOOP`.
  - `class IntroScene(PadTolerantScene)`: `__init__(self, options: dict[str, Any] | None = None, groups: pygame.sprite.LayeredDirty[Any] | None = None, showing: IntroShowing | str = IntroShowing.LOOP)`;
    `replay_arguments() -> dict[str, Any]` returns `{'showing': <value>}`; `actors: Mapping[str, AnimatedSprite]`;
    `fired: tuple[IntroCue, ...]` (the cues fired so far, for tests and the debug overlay).
  - `INTRO_BURST_SHAKE: Final = Shake(style=ShakeStyle.NOISE, strength=6.0, duration=0.5, frequency=24.0)`;
    `INTRO_RUMBLE_LOW: Final = 1.0`, `INTRO_RUMBLE_HIGH: Final = 0.7`,
    `INTRO_RUMBLE_MILLISECONDS: Final = 600` (Claude's first cut, the TV-destroyed rumble's
    shape, stronger and longer).
  - On `END` or a skip: `next_scene = TitleScene(options=..., awaiting_release=True)` (plan 13
    will send `LOOP` to the demo instead).
- Behaviour: `setup()` loads every actor (placed as a staged scene: the bags in a row in front of
  the TV, lamp and snacks beside them, hands and zombie over the TV, hidden until their cue), the
  oval (a full-screen sprite with a transparent oval hole, alpha fading in over the first 0.5 s),
  and requests its sounds. `dt_tick` fires `cues_crossed(before=previous game_time, now=game_time)`.
  `RUMBLE` rumbles every device in `self.input_devices` only when `showing` is `LAUNCH`.
  `SHAKE` calls `self.shake(INTRO_BURST_SHAKE, targets=ShakeTarget.SCREEN)`. Key down, controller
  and joystick button down skip; key up, button up, axes, hats and device added or removed are
  handled and do nothing (pad events through `PadTolerantScene`).

- [ ] **Step 1: Write the failing tests**
  - `test_the_intro_fires_its_timeline_and_hands_over_to_the_title`: ticking to 8.1 s fires every
    cue once and `next_scene` is a `TitleScene`.
  - `test_at_six_seconds_the_tv_bursts_the_kids_start_and_the_screen_shakes`: actors' current
    animations, and `scene.shake` called once with `INTRO_BURST_SHAKE` and the screen target
    (`mocker.spy`).
  - `test_the_launch_showing_rumbles_every_pad_once_at_the_burst` and
    `test_the_loop_rumbles_nothing`: two stand-in pads (`tests/input/stand_in_devices.py`); spy
    on each device's `rumble`; called once with the three constants, or never.
  - `test_no_pad_no_rumble_and_nothing_raises`.
  - `test_a_key_or_button_skips_at_any_moment` (parametrized: key, controller START, joystick
    button; at 0.0, 4.5 and 7.9 s): `next_scene` is a `TitleScene` on that frame.
  - `test_a_hitch_across_the_burst_fires_each_cue_once_and_hands_over_once` (one 7 s frame).
  - `test_a_pad_plugged_in_or_out_during_the_intro_changes_nothing` (Review focus 2).
  - `test_pausing_the_intro_holds_its_timeline` (Review focus 5): `game_time` frozen while
    paused, no cue fires.
  - `test_the_oval_darkens_the_corners_and_shows_the_middle`: rendered pixels (after the
    fade-in): a corner is the oval's dark colour, the TV's centre is not.
  - `test_the_intro_replays_as_it_began`: `IntroScene(**scene.replay_arguments())` has the same
    `showing`.
- [ ] **Step 2: Run; expect failures.**
- [ ] **Step 3: Implement `intro.py` (and a sound, only if none fits).**
- [ ] **Step 4: Run; expect passes.**
- [ ] **Step 5: Commit.**

### Task 4: The launch showing

**Files:**
- Create: `Z/launch_showing.py`.
- Modify: `Z/title.py` (`opening: bool = True`, in `replay_arguments` only when False; on the
  opening title's first frame, hand over to `IntroScene(showing=IntroShowing.LAUNCH)` when
  allowed), and every place that builds a title, to pass `opening=False`: `Z/intro.py`,
  `Z/feature_card.py:244`, `Z/neighborhood.py:956`, `Z/game_over.py:232`.
- Test: `T/test_zombies_aint_my_neighbors_title.py` (and the hand-off tests beside each scene's
  own: `..._intro.py`, `..._feature_card.py`, `..._neighborhood.py`, `..._game_over.py`).

**Interfaces:**
- Produces:
  - `launch_showing_allowed(*, options: Mapping[str, Any], video_driver: str) -> bool`: returns
    `crt_power_on.should_play(mode=crt_power_on.resolve_mode(option=options.get('crt_power_on'), environment=os.environ), video_driver=video_driver, options=options)`.
  - `current_video_driver() -> str` (`pygame.display.get_driver()`; the one place tests patch).
  - `TitleScene(..., opening: bool = True)`.

- [ ] **Step 1: Write the failing tests** (the driver by patching
  `launch_showing.current_video_driver`):
  - `test_the_opening_title_hands_over_to_the_intro_at_launch`: driver `'cocoa'`: the title's
    first tick sets `next_scene` to an `IntroScene` with `LAUNCH`.
  - `test_the_launch_showing_plays_at_every_launch`: two fresh opening titles in turn (two
    launches) both hand over.
  - `test_the_launch_showing_is_skipped_where_the_power_on_is` (parametrized: driver `'dummy'`;
    `replay_trace`, `record_trace`, `audit`, `rebaseline` each set; `crt_power_on='off'`): no
    hand-over.
  - `test_a_title_that_is_not_the_opening_one_never_plays_the_intro`: `opening=False`, driver
    `'cocoa'`: no hand-over; `replay_arguments` carries `opening: False`.
  - `test_every_title_built_after_the_launch_is_not_the_opening_one` (Review focus 4;
    parametrized: the intro's end, the intro's skip, the STAGE n card's Back, quitting a stage,
    the game over's return): the `TitleScene` each hands to has `opening` False.
- [ ] **Step 2: Run; expect failures.**
- [ ] **Step 3: Implement `launch_showing.py`, `opening`, and the four `opening=False` sites.**
- [ ] **Step 4: Run; expect passes; the title's golden still replays** (run its replay item).
- [ ] **Step 5: Commit.**

### Task 5: The title's idle loop

**Files:**
- Modify: `Z/title.py`.
- Test: `T/test_zombies_aint_my_neighbors_title.py`.

**Interfaces:**
- Consumes: `IntroScene`, `IntroShowing` (Task 3).
- Produces:
  - `IDLE_SECONDS: Final = 20.0` in `Z/title.py`.
  - `TitleScene.__init__` gains `awaiting_release: bool = False` (in `replay_arguments` only when
    True); `TitleScene.idle_seconds -> float` (property).
  - Activity (resets the count to the current `game_time`): key down, controller or joystick
    button down, a join. Axes and hats are not.
  - Hand-over: `idle_seconds >= IDLE_SECONDS - TIME_TOLERANCE`, no slot joined, `run is None`:
    `next_scene = IntroScene(options=..., showing=IntroShowing.LOOP)`.
  - `awaiting_release`: start presses are ignored until a frame whose `current_input()` has no key
    and no pad button down; then it clears.

- [ ] **Step 1: Write the failing tests**
  - `test_an_idle_title_hands_over_to_the_intro_after_twenty_seconds`: not at 19.98 s; at the
    frame reaching 20.0 s, an `IntroScene` with `LOOP`.
  - `test_any_press_or_join_starts_the_count_again` (parametrized: a non-start key, a pad button,
    a join then the player leaving).
  - `test_stick_movement_is_not_activity`.
  - `test_a_title_with_a_joined_slot_or_a_run_never_loops` (parametrized).
  - `test_pausing_the_title_holds_its_idle_count` (Review focus 5).
  - `test_a_key_still_held_after_a_skip_never_joins` (Review focus 1): a title made with
    `awaiting_release=True` and Enter held in the input snapshot ignores a start press; after a
    frame with nothing held, a press joins.
  - `test_every_title_recording_ends_before_the_idle_loop`: each golden and bundled demo of this
    game whose first scene is the title holds fewer frames than `IDLE_SECONDS` at its recorded
    frame times (sum of `dt`).
- [ ] **Step 2: Run; expect failures.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run; expect passes; both goldens replay unchanged** (their replay items, and
  `tests/replay/test_golden_replays.py`).
- [ ] **Step 5: Commit.**

### Task 6: Browser rumble, the records, the gate

**Files:**
- Modify: `plans/2026-11-14-zombies-aint-my-neighbors.md` (feature 12 BUILT; the "Test controller
  rumble in the browser build" item answered; wishlist #4 updated; a new wishlist row: a public
  "would the power-on play" answer, `launch_showing.launch_showing_allowed` repeating the engine's
  call), this file's Status.
- Check the game's docs page (`docs/`, generated member pages: `scripts/gen_ref_pages.py`)
  lists the new modules.

- [ ] **Step 1: Build the browser bundle (`nox -s browser -- zombies-aint-my-neighbors`), plug in a
  pad, let the launch intro play, and record whether it
  rumbled.** This needs the owner at a browser with a pad: ask them, and record their answer.
- [ ] **Step 2: Update the plans above.**
- [ ] **Step 3: Run the whole gate** (ruff format and check over `src tests scripts noxfile.py`,
  basedpyright, ty, `pytest`); 100% coverage; fix findings first.
- [ ] **Step 4: Commit.**
