# Game code that belongs in the engine — Master Plan and Sub-plan Order

> **Status: APPROVED by the owner (2026-11-20), with the decisions at the end; nothing is built.**
> Each sub-plan below becomes its own detailed plan, one branch and one PR, when the owner picks
> it. Open questions are at the end, and each decision marked "recommended" waits for the owner.

**Goal:** Move the code the games copied from one another into the engine, one small piece at a
time, with every golden replay and golden trace passing **unchanged** at each step, and with each
piece shaped for other genres (a top-down RPG, a shooter, a puzzle game, a fighting game), not
only for today's six games.

**Source:** the audit's Part 1 (`.superpowers/overnight-2026-11-20/engine-and-performance.md`,
a scratch file in the main checkout, measured at origin/main `b7c2abd3`) and the critique of the
game-ideas proposals (`game-ideas-critique.md`, same folder). Every file:line below was
re-checked against origin/main `6f929051` on 2026-11-20. Four numbers in the audit had drifted
(Brave Adventurer's `player.py` properties are at 162-212, not 160-215, and `_draw_pose` at 275,
not 285-308's start); the sites below are the current ones.

## What a golden compares (the rule every step is judged by)

Read from the code, not assumed:

- A golden **trace** (`tests/world/golden/*.jsonl.gz`, `tests/world/test_golden_traces.py`) and a
  golden **replay** (`<member>/tests/fixtures/replays/*.jsonl.gz`) compare, frame by frame, the
  active scene's class name and **every sprite in `scene.all_sprites`**: its stable id
  (`ClassName#index`, counted per class), `rect` and `visible`
  (`src/glitchygames/tracing.py:215`, `sample_scene_frame`). Internal events a game posts are
  matched record by record (`replay/driver.py`, rule 2), the save snapshot is part of the
  header, and `--audit` / `compare-drivers` also compare a content digest of every frame.
- Audio is played, not compared (`docs/architecture/gameplay_replay.md`), but compiles are
  counted and logged, so the **order of sound requests** stays.
- So a change is invisible to a golden if it adds, removes or reorders no sprite in the group,
  moves no `rect`, posts no new internal event, changes no float accumulation order, calls
  `saves.load`/`saves.save` in the same sequence, and draws the same pixels.
- Consequence for the audit's candidate 3 (HUD text): a HUD label that is a sprite in the scene's
  group **adds an entry to every frame of every golden**, so it fails them all. It cannot land
  in an existing game without re-recording, which the rules forbid ("never re-record the
  baselines to make a change pass"). That is why it is last and optional below.

**How each step proves exactness** (the same four proofs, named once; each sub-plan says which
of them can fail on its change):

1. *Characterization first.* Before the code moves, write the test that pins today's behaviour
   (the old output for a table of inputs), run it green on the old code, then keep it green on the
   new. Plant one defect in the new code and watch it go red, so the gate is known to be able to
   fail (the global rule on absent measurements).
2. *The goldens, untouched.* `uv run pytest` (full: the golden traces, every member's golden
   replay, `tests/replay/test_bundled_demos.py`) plus `git diff --stat origin/main -- '*.jsonl.gz'`
   must show **no recording changed**. No `scripts/record_*` command is run in any sub-plan.
3. *`uv run glitchygames verify`* (every golden and bundled demo, headless) and
   `nox -s compare-drivers -- --drivers native --fail-on-difference --workers auto` (pixels).
4. *A spy on the doors the change touches* (saves calls, sound requests, posted events, sprite
   group contents per frame): recorded on old code from a golden's replay, compared to new.

## Where this starts: the candidates, verified

| # | Candidate | Where it lives today (origin/main `6f929051`) | Golden risk |
| --- | --- | --- | --- |
| 5 | Font helpers, same algorithm twice | Mr. Muncher `scenery.py:30-79` (`bundled_font`, `fitted_font`, `render_text`); Zombies `text.py:34-81` (`title_font`, `fitted_title_font`, `render_text`; `render_lines` at 84 is Zombies-only); the engine already has `bundled_font_path` (`fonts/font_manager.py:192`) and `FontManager.antialias()` | none (no gameplay state) |
| 2 | High-score table, four copies | PaddleSlap `__init__.py:496-514`; Brave `brave_adventurer_core/scene.py:742-762`; Clockwork `game.py:1008-1039` (adds `floor`; its `_load_high_scores` reads the same slot); Mr. Muncher `game.py:1003-1033` (adds `level`; `HIGH_SCORES_SAVE_NAME`, `HIGH_SCORE_ENTRIES` at 214-215). The engine's `GameOverScene` (`scenes/builtin_scenes/game_over_scene.py:26-48`) draws a `high_scores` list nothing in the engine produces | none to low (save call order) |
| 3 | Shadowed HUD text | Brave `scene.py:1062-1089` and Clockwork `game.py:1157-1190` (same code: shadow at +1,+1, score left, lives right at `screen_width - 110`; Clockwork adds the floor name); Zombies `hud.py:91` (`Hud`, sprites), Drawing Fire `drawing.py:498` (`draw_hud`), Mr. Muncher `scenery.py:197` (`SidePanel`) each their own way | none for the immediate-mode half; **high** for sprites |
| 4 | Idle to bundled demo | PaddleSlap's game-over screen only: `__init__.py:81-93` (`GAME_OVER_IDLE_SECONDS`) and `1294-1352`; Zombies' title scene has its own (`title.py:40`, `IDLE_SECONDS`, `attract.py`). Brave, Clockwork, Drawing Fire and Mr. Muncher ship bundled demos and have no idle trigger | none for goldens (off by default); medium for PaddleSlap's own conversion |
| 1 | Platformer kit | Properties `world_x/world_y/velocity_x/velocity_y/on_ground/facing_right` delegated to `self.physics`: Brave `player.py:162-212`, Clockwork `player.py:130-180`; `jump/move_right/move_left/stop_horizontal`: Brave 285-304, Clockwork 235-272 (Clockwork adds `running`); `_create_action_map`: Brave `scene.py:209-242`, Clockwork `game.py:540-584`; `_process_movement_input`: Brave 820-830, Clockwork 586-599; the five input handlers: Brave 852-957, Clockwork 1053-1140; `_respawn_player`: Brave 764-802, Clockwork 972-1006; hand-built `PauseScene(options=self.options)`: Brave 813, Clockwork 1050 and 1065, Mr. Muncher 1262, though `Scene.pause()` exists (`scenes/scene.py:4527`) | low to high by part |

Two findings that shape the design, from reading the sites:

- **The two games' input handlers are not identical.** Brave plays its jump sound only when the
  player is on the ground, then jumps (`scene.py:852-876`); Clockwork calls `_try_jump()`; Clockwork
  adds run and interact. So a shared piece cannot own the *reaction* to an action, only the
  *routing* of an event to an action name.
- **Nobody calls `super()` consistently**, so an engine hook placed in the base `Scene` key
  handlers (the audit's `Scene.note_activity()`) would silently not fire in a scene whose
  override omits `super()`. The idle design below is placed where every event passes instead.

## Decisions (recommended; the owner reviews them with the plan)

1. **Kits are helper modules and small objects, never a `Scene` base class** (CLAUDE.md: patterns
   must work for other genres). A top-down RPG scene wants `HighScoreTable` and the font helpers
   but not a platformer base. New code lives in `src/glitchygames/` next to `movement/`,
   `physics/`, `state/`, `fonts/`; the games import it, the engine imports no game.
2. **Delegation by descriptor, not by mixin.** The twelve one-line property accessors become
   `world_x = physics_field(name='world_x')` style declarations (a small descriptor in
   `glitchygames/physics/`), because the owner prefers composition to mixins and a descriptor
   keeps the sprite class's own base (`Sprite`) and its MRO untouched. The attribute names stay
   exactly (the world-space engine and the tracer read them by name).
3. **Routing helper over installed handlers, first.** An `ActionRouter` the game's existing five
   handlers call (one line each) rather than `Scene.bind_actions` installing handlers. Why: the
   scene still owns its handlers, so handler resolution, `super()` order and what the scene
   consumes are byte-identical, and the replay is the proof. Installing handlers on `Scene`
   can follow later as a separate step if the owner wants it (question 3).
4. **Idle detection at the `SceneManager`, in game time.** It sees every key, button and
   configured event before any scene override, so a scene cannot defeat it by forgetting
   `super()`; it counts `Scene.game_time`, so replays serve the same value (CLAUDE.md, Clocks).
5. **Order by golden risk, safest first, each landing green alone** (below). The two optional
   high-risk items (HUD sprites; timers) are listed last or out of scope.
6. **New data classes are pydantic** (`frozen=True`, `extra='forbid'`): table settings, router
   bindings, idle settings. A list a table mutates, a sprite and an object holding a Surface or a
   `SaveManager` stay plain classes (the arcade-3 plan's rule).
7. **Existing save files keep loading.** A table keeps the slot name and shape
   (`{'scores': [{'score': ..., 'floor': ...}]}`): players' saves on disk and recorded save
   snapshots in the goldens' headers are exactly that.

## Sub-plan order

Each is one branch and one PR, each green alone (ruff, basedpyright, ty, `pytest` at 100%
coverage, `verify`), none edits a recording.

### Sub-plan 1: Shared font helpers (candidate 5)

**Files:** create `src/glitchygames/fonts/bundled.py` (or functions in `font_manager.py`: question
2); modify Mr. Muncher `scenery.py` and its users (`game.py`), Zombies `text.py` and its users
(`game_over.py`, `feature_card.py`, `hud.py`, `attract.py`, `title.py`, `art/contact_sheet.py`);
tests in `tests/fonts/` and the two games' own test files.

**Interface:** `bundled(*, bold: bool, size: int) -> pygame.font.Font`;
`fitted(*, texts: Sequence[str], width: int, largest: int, bold: bool = True) -> pygame.font.Font`
(the loop `range(largest, SMALLEST_FONT_SIZE, -1)` and the floor of 8 exactly as both copies);
`render_line(*, font, text: str, color: Color) -> pygame.Surface`. Uncached on purpose, as both
files say, so the process-state guard has no module state to flag. The Zombies spelling `colour`
becomes `color` at the call (the engine's spelling); Zombies' `render_lines` stays in Zombies.

**Worked example:** Mr. Muncher's title asks `fitted_font(bold=True, texts=(...), width=640,
largest=48)` and gets the first size from 48 down in which every text is at most 640 pixels
wide; Zombies' `fitted_title_font(texts=..., width=640, largest=48)` is the same call with
`bold=True` fixed. One function serves both, and a third game's body text asks `bold=False`.

**Exactness:** proof 1 (render the same strings through old and new at every size 8 to 64 and
assert equal pixels and equal chosen size, both fonts), then 2 and 3. No sprite, event or save is
touched, so no golden can move; the proof exists to catch a typo, not a design risk.

### Sub-plan 2: `HighScoreTable` (candidate 2)

**Files:** create `src/glitchygames/state/high_scores.py`; modify the four games' `_save_high_score`
(and Clockwork's `_load_high_scores`, Mr. Muncher's `_saved_high_scores` and
`_best_saved_score`); tests in `tests/state/`.

**Interface:** `HighScoreTableSettings` (pydantic: `slot_name: str = 'high_scores'`,
`limit: int = 10`, `score_key: str = 'score'`, `best: BestScore = BestScore.HIGHEST`);
`HighScoreTable(saves: SaveManager, settings=...)` with `.entries() -> list[dict[str, int]]`,
`.record(*, score: int, **extra: int) -> list[dict[str, int]]` (returns the sorted, cut list a
`GameOverScene(high_scores=...)` takes), `.best() -> int`. `BestScore` is a `StrEnum` with
`HIGHEST` and `LOWEST` (a racing or time-trial game sorts ascending: an explicit flag, both
branches tested).

**Behaviours to keep exactly** (the characterization table): one `saves.load(slot)`, a
`SaveNotFoundError` means an empty list, one `saves.save(slot, {'scores': ...})` and nothing else;
the sort is `list.sort(key=..., reverse=True)` on the appended list, so a **new entry that ties an
old one stays below it** (the sort is stable and `reverse=True` keeps the original order of equal
elements). A tidy-looking replacement (insertion before the first lower-or-equal entry) would
put the new tie above the old one and change which entry a full table drops; the test pins the tie. The cut is
`[:limit]`. Mr. Muncher loads once in `_best_saved_score` and once in `_save_high_score`
(two loads); the table must not change that count, as the save door's calls are recorded.

**Worked example:** Clockwork ends a climb with score 900 on floor 3. Today
`_save_high_score` loads, appends `{'score': 900, 'floor': 3}`, sorts, cuts to 10 and saves;
afterwards `GameOver` shows the top 5. With the table: `table.record(score=900, floor=3)`, the
same one load and one save, the same dictionary order inside the saved entry.

**Exactness:** proofs 1 (save-door spy: the sequence of `(call, slot, payload)` from each game's
golden replay is equal before and after) and 2. Risk: none to low (the in-memory replay sandbox
sees the same calls).

### Sub-plan 3: Cached shadowed text, and `Scene.pause()` (candidate 3, immediate-mode half)

**Files:** create `src/glitchygames/fonts/shadowed_text.py`; modify Brave `_draw_hud`, Clockwork
`_draw_hud`; and replace the hand-built `PauseScene(options=self.options)` at Brave 813, Clockwork
1050 and 1065 and Mr. Muncher 1262 with `self.pause()` (the same `next_scene` assignment: it is
what `Scene.pause` does, `scenes/scene.py:4540`).

**Interface:** `ShadowedText(font, color, shadow_color, offset=(1, 1))` with
`.render(text) -> pygame.Surface` holding the last text's surfaces and rebuilding only when the
text changes, and `.blit(surface, text, position, anchor)` for the left, centred and right
anchors the three HUD labels use. It stays **immediate mode**: the games' `render()` still blits
it, no sprite is added to any group (the golden constraint above).

**Exactness:** the surfaces come from the same `font.render(text, antialias, color)` calls with
the same arguments, so the pixels are the same: proof 1 compares a frame's HUD region pixel for
pixel, proof 3 over the goldens. Whether any scene overrides `pause()` is checked first (none
under `src/games` does today: `grep -rn "def pause" src/games` is empty). Gain: removes the
per-frame `Font.render` (Clockwork 5.4 and Brave 3.6 calls per frame in the audit's profile),
worth most on a Pi, unmeasured.

### Sub-plan 4: The idle-to-demo loop (candidate 4)

**Files:** `src/glitchygames/scenes/__init__.py` (SceneManager) and `scenes/scene.py`; PaddleSlap
`__init__.py` (its game-over screen becomes the first user); then, one at a time and only if the
owner wants them, Brave's, Clockwork's, Drawing Fire's and Mr. Muncher's title or game-over scenes.

**Interface:** a scene class constant `IDLE_DEMO: IdleDemo | None = None` where `IdleDemo` is a
pydantic model: `recording: Path`, `seconds: float = 10.0`, `ends_on: frozenset[int]` (the event
types that count as activity; default key down, joy button down, controller button down, which
is the set PaddleSlap resets on today). The `SceneManager` records `scene.game_time` when it
dispatches such an event to the active scene (before the scene's handler runs, so no override
can skip it), and in its logic step calls `scene_manager.play_recording(path=..., then=scene)`
when `game_time - last_activity >= seconds` (`Scene.play_recording` at `scenes/scene.py:805`
already exists; PaddleSlap calls it today).

**Worked example:** PaddleSlap's game-over screen: 10 s of game time with no press starts
`rally.jsonl.gz`; a press while it plays ends it and is consumed. Today three handlers reset
`idle_since_game_time` and `dt_tick` compares. With the constant,
`IDLE_DEMO = IdleDemo(recording=PADDLESLAP_DEMO_PATH)` replaces about 70 lines, and Brave's title
gets attract mode with one more constant.

**Risk and proof:** existing goldens: none for scenes that set nothing (the constant is `None`).
PaddleSlap's conversion is the risk: the timer must restart at the same frames. Proof 4: first
measure, on old code, the frame at which `play_recording` starts in every PaddleSlap test that
idles (the game-over test, the demo test); the new code must start it at the same frames, and
the golden (which ends with a quit, never idle 10 s: verify with the spy) must be unaffected.
Gap to confirm in the detailed plan: a scene's `game_time` does not advance while a demo plays
(PaddleSlap's docstring says so), and the manager's counter must follow the same rule.

### Sub-plan 5: The platformer kit (candidate 1), in four steps by risk

A genre-neutral helper set (`glitchygames/physics/` delegation, `glitchygames/input/` routing,
`glitchygames/effects/` respawn), named for what each does, not for "platformer"; Brave and
Clockwork are the first users, and a top-down game uses the router and the delegation as is.

- **5a, the property delegation** (low). `physics_field` declarations replace the twelve
  accessors in both players. Tracer reads `world_x` by name; keep names. Proof 1 (every field
  read and written through the new declaration equals the physics body's, incl. `world_x` set
  from the world-space engine) and 2, 3.
- **5b, the action map** (medium: the controls rule). `ActionMap` construction for the common
  controls: `bind_standard_controls(actions, move=..., jump=..., pause=..., quit=...)` taking the
  game's extras (Clockwork's run and interact stay Clockwork's). Each game's static
  `_create_action_map(*, options)` **stays**, because `tests/replay/golden_replay_controls.py`
  builds the game's maps through it. Proof 1: snapshot the full binding table (action to
  scancode, controller button, axis) of both games before the change and assert equal after,
  and the controls tail of the goldens (`tests/replay/test_golden_replays.py`) is untouched.
- **5c, the router** (the riskiest: medium to high). `ActionRouter(actions, reactions:
  Mapping[str, Callable[[], None]])` with `on_key_down/on_key_up/on_joy_button/
  on_controller_button/on_axis(event) -> bool` (True when an action consumed it), which each
  game's own five handlers call and then fall to `super()` when False, exactly the current
  `elif action is None: super()...` shape. Reactions stay the game's own (Brave's sound and
  jump, Clockwork's `_try_jump`). Task 0 of its detailed plan reads the ten handler pairs and
  lists every difference before any code moves (axis deadzones, which release events call
  `handle_event`). Proof 1 (a table of events to the old handler's observable result, then the
  new), 2, 3, and proof 4 on the posted and consumed events.
- **5d, `respawn_with_fade`** (low to medium: tween order). Same two tweens, same properties,
  durations 0.2 and 0.3, easing `ease_out_quad` and `ease_in_quad`, same callback order, and the
  inert `_restore_input_after_respawn` callbacks (both games carry a docstring-only one, Brave
  `scene.py:803`) go away or become `on_done=None`. Proof 4: the tween creation sequence per
  frame, from a golden's replay, equal before and after. Note `max(0.0, ...)` (BUGS.md #230):
  the float type of the respawn position is recorded, so the helper takes the already-computed
  point.

Together the audit estimated 250 to 300 lines removed across the two games.

## Out of scope, and where it would fit

- **Timers and cooldowns** (`Countdown`, `PhaseClock`; about 25 `x -= dt` sites): high golden
  risk (float accumulation order changes the last bit and a golden compares exact states).
  Only for new games, or for a game the owner is willing to re-verify bit by bit, as its own plan.
  It is also where a `BeatClock` lands (below).
- **HUD labels as sprites** (candidate 3, the full form): see question 1.
- **Sound effect sets, lives and score state** (audit candidates 7 and 8): small, list only.
- **The game-ideas critique's top three engine features**, not planned here, with the place each
  fits so these sub-plans do not block them:
  - *A solid kinematic echo sprite* (`Echo`; not a flag on `GhostSprite`, whose docstring forbids
    collision groups): a new module beside `replay/ghosts.py`, its track part of the recording.
    It would use the physics delegation of 5a as a consumer, not a dependency.
  - *A `BeatClock`* (the same work as plans/future-features.md #64's `Sequence`, which is a
    design, not built): `Scene.game_time`-driven, so it belongs with the timers item above and
    `audio/`; do the small half of #64 with it.
  - *Spatial audio / resonance helpers*: `audio/` (`live_controls.py` routes), after Arcade
    sub-plan 7 for any cross-tile use.
- **Performance candidates** of the same audit (parallax, `position_world_sprites`, LayeredDirty
  cost): a separate subject.

## Review focus (for the detailed plans)

1. No sub-plan changes a recording: the diff of `*.jsonl.gz` against origin/main is empty at every
   PR.
2. No sub-plan adds a sprite to a scene group, posts an event, or reorders a save or sound call.
3. A kit used by one game only is not worth landing: each of 1 to 5 has at least two users today
   (5d's helper, 5a to 5c: Brave and Clockwork; the router also fits Mr. Muncher's pause).
4. The engine imports no game; the games import the engine (`tests/test_workspace_config.py`).
5. Docs: each new engine module gets its `docs/glitchygames/` page, `docs/architecture/` mention
   where it changes a flow (idle demo, saves), and the game packages' README lines that name the
   copied helpers; grep every .md for the old paths.

## Open questions for the owner

### Decided by the owner (2026-11-20)

These answers win over the question text below wherever they differ.

1. **HUD labels become sprites in Brave and Clockwork, option (c).** Re-record the six
   recordings that compare their sprites (goldens: Brave's `golden-classic` and
   `golden-papyrus`, Clockwork's `golden`; demos: Brave's `classic` and `papyrus`, Clockwork's
   `climb`) as one reviewed step, gated by a check that replays each old and new recording side
   by side and fails unless every difference is one of the new HUD label sprites: every other
   sprite matches frame for frame and the pixels are identical. Zombies' HUD (already sprites,
   pre-rendered) is the model; title, pause and game-over text already render once. The
   measured gain from no longer re-rendering text each frame: Clockwork 2.3 %, Brave 0.6 % of
   the frame on the M4 Max (more on a Pi, unmeasured).
2. **Names and homes as proposed:** the font helpers are functions in `font_manager.py`;
   `HighScoreTable` in `state/`; `HudLabel` in `sprites/`, and it absorbs `ShadowedText` (one
   text mechanism, now that HUDs are sprites); `IdleDemo` in `scenes/`; `ActionRouter` in
   `input/`; `physics_field` and `respawn_with_fade` in a `platformer/` package.
3. **Stop at `ActionRouter`;** no `Scene.bind_actions`.
4. **`IdleDemo`: PaddleSlap first,** then Brave, Clockwork, Drawing Fire and Mr. Muncher as
   separate small pull requests the owner approves.
5. **High-score entries are strict pydantic models:** a frozen base (`name`, `score`,
   `extra='forbid'`) that each game subclasses for its own fields, with `model_dump` and
   `model_validate` at the disk and `GameOverScene` boundaries.
6. **Per-player tables wait for the player roster** (`plans/2026-10-28-player-roster-design.md`);
   no `player_slot` field now.
7. **Sequencing, in risk order:** Sub-plans 1 and 2 at any time; the HUD re-record lands between
   Arcade sub-plans 5 and 6, together with the `drawing` and `typing` demo re-records of
   `plans/2026-11-20-window-owner-events.md` (its question 5); `IdleDemo` and the platformer kit
   after, at any gap.

### The questions as asked

1. **Do HUD labels become sprites?** Worked example: Brave's HUD is three `Font.render` and six
   blits per frame in `render()`. As three `HudLabel` sprites it would redraw only when the score
   or lives change and would show in the AI's introspection and the debug overlay (the "every
   game object is a sprite" rule, 2026-11-07), but the 3 extra entries in `all_sprites` fail
   every Brave and Clockwork golden. Options: (a) never in existing games, only new ones (the
   recommendation: exact, and Sub-plan 3 already removes the per-frame cost); (b) exclude HUD
   labels from `sample_scene_frame` by a marker, which changes what the goldens mean; (c)
   re-record Brave's and Clockwork's goldens as a reviewed step, the one thing the rules call
   deliberate, and worth it only if the owner wants the sprite rule applied there.
2. **Names and homes:** `fonts.bundled/fitted/render_line` as functions in `font_manager.py` or a
   new module; `HighScoreTable` in `state/` (recommended) or `scenes/builtin_scenes/`;
   `ActionRouter`, `physics_field`, `ShadowedText`, `IdleDemo`, `respawn_with_fade` are working
   names (the owner names things; no abbreviations).
3. **Stop at the router, or install handlers on `Scene`** (`Scene.bind_actions`)? Recommended:
   stop at the router (5c) until a third game uses it; `bind_actions` would make the scene's
   handler set implicit, against "explicit is better than implicit".
4. **Idle demo scope:** only PaddleSlap converts, or should Brave, Clockwork, Drawing Fire and
   Mr. Muncher gain attract mode now (their demos exist and are replayed in tests)? Each is a
   visible behaviour change in a shipped game, so it is the owner's call; recommended: PaddleSlap
   first, the others as separate small PRs the owner approves.
5. **`HighScoreTable` entries:** keep plain dicts (recommended: the disk format and
   `GameOverScene(high_scores=...)` are dicts, so a model would convert at both ends for no gain)
   or pydantic entry models with `extra='allow'` (against the project's `extra='forbid'` rule).
6. **A 4-player scoreboard or per-player tables** (the four controller slots): should the table
   key its slot by player now (`slot_name` already allows it), or wait for the roster plan
   (`plans/2026-10-28-player-roster-design.md`)?
7. **Sequencing against the Arcade and the Zombies finish**: these touch Brave, Clockwork, Mr.
   Muncher and PaddleSlap, which the Arcade wraps unchanged (no game changes to wrap one); the
   golden recordings are shared with the Arcade's tile tests. Land between Arcade sub-plans, or
   after?

Related: plans/future-work.md (Games), plans/future-features.md #64 (BeatClock),
plans/2026-11-20-window-owner-events.md (the other overnight plan; independent).
