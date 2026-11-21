# Game code that belongs in the engine — Master Plan and Sub-plan Order

> **Status: APPROVED by the owner (2026-11-20); nothing is built.** The owner's decisions are in
> the body below and recorded in one line each under "Decided" at the end. Each sub-plan becomes
> its own detailed plan, one branch and one PR, in the order under "Sub-plan order".

**Goal:** Move the code the games copied from one another into the engine, one small piece at a
time, with each piece shaped for other genres (a top-down RPG, a shooter, a puzzle game, a
fighting game), not only for today's six games. Every step keeps every golden replay, golden
trace and bundled demo **unchanged**, except one: Sub-plan 3's HUD step, which re-records the
recordings its new HUD label sprites appear in as one deliberate, reviewed step, gated by a
check that fails on any difference other than the ones it names.

**Source:** the audit's Part 1 (`.superpowers/overnight-2026-11-20/engine-and-performance.md`,
a scratch file in the main checkout, measured at origin/main `b7c2abd3`) and the critique of the
game-ideas proposals (`game-ideas-critique.md`, same folder). Every file:line below was
re-checked against origin/main `60f6207a` on 2026-11-20. Four numbers in the audit had drifted
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
  header, and `--audit` / `compare-drivers` also compare a digest of every frame. Bundled demos
  (`<package>/demos/*.jsonl.gz`) are replayed the same way (`tests/replay/test_bundled_demos.py`,
  and the Arcade's tiles).
- Audio is played, not compared (`docs/architecture/gameplay_replay.md`), but compiles are
  counted and logged, so the **order of sound requests** stays.
- So a change is invisible to a golden if it adds, removes or reorders no sprite in the group,
  moves no `rect`, posts no new internal event, changes no float accumulation order, calls
  `saves.load`/`saves.save` in the same sequence, and draws the same pixels.
- Consequence for the audit's candidate 3 (HUD text): a HUD label that is a sprite in the scene's
  group **adds entries to every frame** of every recording of that scene, so no existing
  recording of Brave Adventurer or Clockwork Keep can pass with it. The project rule is "never
  re-record the baselines to make a change pass"; it forbids re-recording to hide a difference
  nobody reviewed, not a deliberate re-record whose every difference is named in advance and
  checked. The owner chose the HUD sprites (the "every game object is a sprite" rule,
  2026-11-07) with exactly that kind of re-record: Sub-plan 3 holds it, and it is the only step
  in this plan that changes a recording.

**How each step proves exactness** (the same four proofs, named once; each sub-plan says which
of them can fail on its change):

1. *Characterization first.* Before the code moves, write the test that pins today's behaviour
   (the old output for a table of inputs), run it green on the old code, then keep it green on the
   new. Plant one defect in the new code and watch it go red, so the gate is known to be able to
   fail (the global rule on absent measurements).
2. *The goldens, untouched.* `uv run pytest` (full: the golden traces, every member's golden
   replay, `tests/replay/test_bundled_demos.py`) plus `git diff --stat origin/main -- '*.jsonl.gz'`
   must show **no recording changed**. No `scripts/record_*` command and no `--rebaseline` is
   run in any sub-plan except Sub-plan 3's re-record step, which replaces this proof with its
   own check (below).
3. *`uv run glitchygames verify`* (every golden and bundled demo, headless) and
   `nox -s compare-drivers -- --drivers native --fail-on-difference --workers auto` (pixels).
4. *A spy on the doors the change touches* (saves calls, sound requests, posted events, sprite
   group contents per frame): recorded on old code from a golden's replay, compared to new.

## Where this starts: the candidates, verified

| # | Candidate | Where it lives today (origin/main `60f6207a`) | Golden risk |
| --- | --- | --- | --- |
| 5 | Font helpers, same algorithm twice | Mr. Muncher `scenery.py:30-79` (`bundled_font`, `fitted_font`, `render_text`); Zombies `text.py:34-81` (`title_font`, `fitted_title_font`, `render_text`; `render_lines` at 84 is Zombies-only); the engine already has `bundled_font_path` (`fonts/font_manager.py:192`) and `FontManager.antialias()` (`font_manager.py:536`) | none (no gameplay state) |
| 2 | High-score table, four copies | PaddleSlap `__init__.py:496-514`; Brave `brave_adventurer_core/scene.py:742-762`; Clockwork `game.py:1008-1039` (adds `floor`; its `_load_high_scores` reads the same slot); Mr. Muncher `game.py:1003-1033` (adds `level`; `HIGH_SCORES_SAVE_NAME`, `HIGH_SCORE_ENTRIES` at 214-215). The engine's `GameOverScene` (`scenes/builtin_scenes/game_over_scene.py:22-48`) draws a `high_scores` list nothing in the engine produces | none to low (save call order) |
| 3 | Shadowed HUD text | Brave `brave_adventurer_core/scene.py:1062-1085` and Clockwork `game.py:1157-1189` (same code: shadow at +1,+1, score left, lives right at `screen_width - 110`; Clockwork adds the floor name, centred); Zombies `hud.py:91` (`Hud`, sprites, every label rendered once), Drawing Fire `drawing.py:498` (`draw_hud`), Mr. Muncher `scenery.py:197` (`SidePanel`) each their own way | **high, accepted**: the labels become sprites, so the six Brave and Clockwork recordings are re-recorded in Sub-plan 3's one checked step |
| 4 | Idle to bundled demo | PaddleSlap's game-over screen only: `__init__.py:81-93` (`GAME_OVER_IDLE_SECONDS`) and `1294-1352`; Zombies' title scene has its own (`title.py:40`, `IDLE_SECONDS`, `attract.py`). Brave, Clockwork, Drawing Fire and Mr. Muncher ship bundled demos and have no idle trigger | none for goldens (off by default); medium for PaddleSlap's own conversion |
| 1 | Platformer kit | Properties `world_x/world_y/velocity_x/velocity_y/on_ground/facing_right` delegated to `self.physics`: Brave `brave_adventurer/player.py:162-212`, Clockwork `player.py:130-180`; `jump/move_right/move_left/stop_horizontal`: Brave 285-304, Clockwork 235-272 (Clockwork adds `running`); `_create_action_map`: Brave `scene.py:209-242`, Clockwork `game.py:540-584`; `_process_movement_input`: Brave 820-830, Clockwork 586-599; the input handlers: Brave 852-957, Clockwork 1053-1140; `_respawn_player`: Brave 764-802, Clockwork 972-1006; hand-built `PauseScene(options=self.options)`: Brave 813 (in `_pause_game`), Clockwork 1050 (focus loss) and 1065, Mr. Muncher `game.py:1262`, though `Scene.pause()` exists (`scenes/scene.py:4527`) | low to high by part |

Two findings that shape the design, from reading the sites:

- **The two games' input handlers are not identical.** Brave plays its jump sound only when the
  player is on the ground, then jumps (`scene.py:852-876`); Clockwork calls `_try_jump()`; Clockwork
  adds run and interact. So a shared piece cannot own the *reaction* to an action, only the
  *routing* of an event to an action name.
- **Nobody calls `super()` consistently**, so an engine hook placed in the base `Scene` key
  handlers (the audit's `Scene.note_activity()`) would silently not fire in a scene whose
  override omits `super()`. The idle design below is placed where every event passes instead.

## Decisions

1. **Kits are helper modules and small objects, never a `Scene` base class** (CLAUDE.md: patterns
   must work for other genres). A top-down RPG scene wants `HighScoreTable` and the font helpers
   but not a platformer base. New code lives in `src/glitchygames/`; the games import it, the
   engine imports no game.
2. **Names and homes** (the owner's): the font helpers are functions in
   `fonts/font_manager.py`; `HighScoreTable` in `state/`; `HudLabel` in `sprites/` (it absorbs
   the earlier `ShadowedText` idea: one text mechanism, now that HUDs are sprites); `IdleDemo` in
   `scenes/`; `ActionRouter` in `input/`; `physics_field` and `respawn_with_fade` in a new
   `platformer/` package.
3. **Delegation by descriptor, not by mixin.** The twelve one-line property accessors become
   `world_x = physics_field(name='world_x')` style declarations, because the owner prefers
   composition to mixins and a descriptor keeps the sprite class's own base (`Sprite`) and its MRO
   untouched. The attribute names stay exactly (the world-space engine and the tracer read them
   by name).
4. **A routing helper, and stop there.** An `ActionRouter` the game's existing handlers call (one
   line each). There is no `Scene.bind_actions` installing handlers: the scene keeps owning its
   handlers, so handler resolution, `super()` order and what the scene consumes stay
   byte-identical (the replay is the proof), and the scene's handler set stays explicit.
5. **Idle detection at the `SceneManager`, in game time.** It sees every key, button and
   configured event before any scene override, so a scene cannot defeat it by forgetting
   `super()`; it counts `Scene.game_time`, so replays serve the same value (CLAUDE.md, Clocks).
   PaddleSlap converts first; Brave, Clockwork, Drawing Fire and Mr. Muncher gain attract mode
   afterwards, each as its own small PR the owner approves (each is a visible behaviour change in
   a shipped game).
6. **Order by golden risk, safest first, each landing green alone** (below). The HUD sprites are
   in scope, with their one checked re-record; timers stay out of scope.
7. **New data classes are pydantic** (`frozen=True`, `extra='forbid'`): table settings,
   high-score entries, router bindings, idle settings. A list a table mutates, a sprite and an
   object holding a Surface or a `SaveManager` stay plain classes (the arcade-3 plan's rule).
8. **High-score entries are strict models, and existing save files keep loading.** A frozen
   base entry holds only `score`; Clockwork's subclass adds `floor`, Mr. Muncher's adds `level`;
   PaddleSlap and Brave use the base. The table keeps the slot name and shape
   (`{'scores': [{'score': ..., 'floor': ...}]}`), converting with `model_validate` on load and
   `model_dump` on save and at `GameOverScene`: players' saves on disk and the recorded save
   snapshots in the goldens' headers are exactly that shape, in that field order.
9. **One player per table, for now.** Per-player tables and player names on high scores wait for
   the player roster (`plans/2026-10-28-player-roster-design.md`); no `player_slot` or `name`
   field now (player names are a to-do in plans/future-work.md, Games).

## Sub-plan order

Each is one branch and one PR, each green alone (ruff, basedpyright, ty, `pytest` at 100%
coverage, `verify`). None edits a recording except Sub-plan 3's re-record step.

**Sequencing, in risk order** (these touch Brave, Clockwork, Mr. Muncher and PaddleSlap, which
the Arcade wraps unchanged, and whose recordings the Arcade's tiles play):

1. Sub-plans 1 and 2 land at any time.
2. Sub-plan 3 (HUD label sprites, `Scene.pause()`, the checked re-record) lands **between
   Arcade sub-plans 5 and 6**, and its re-record step also carries the re-records of Bitmappy's
   `drawing` and the text-input demo's `typing` demos (`plans/2026-11-20-window-owner-events.md`)
   and Zombies' `golden.jsonl.gz`, so every reviewed re-record happens once, under one check.
3. Sub-plan 4 (`IdleDemo`: PaddleSlap, then the other four games one PR each) and Sub-plan 5
   (the platformer kit) after Sub-plan 3, at any gap between Arcade sub-plans.

### Sub-plan 1: Shared font helpers (candidate 5)

**Files:** modify `src/glitchygames/fonts/font_manager.py` (new module-level functions beside
`bundled_font_path`); modify Mr. Muncher `scenery.py` and its users (`game.py`), Zombies `text.py`
and its users (`game_over.py`, `feature_card.py`, `hud.py`, `attract.py`, `title.py`,
`art/contact_sheet.py`); tests in `tests/fonts/` and the two games' own test files.

**Interface:** `bundled_font(*, bold: bool, size: int) -> pygame.font.Font`;
`fitted_font(*, texts: Sequence[str], width: int, largest: int, bold: bool = True) -> pygame.font.Font`
(the loop `range(largest, SMALLEST_FONT_SIZE, -1)` and the floor of 8 exactly as both copies);
`render_line(*, font, text: str, color: Color) -> pygame.Surface`. Uncached on purpose, as both
files say, so the process-state guard has no module state to flag. The Zombies spelling `colour`
becomes `color` at the call (the engine's spelling); Zombies' `render_lines` stays in Zombies.
`HudLabel` (Sub-plan 3) renders through `render_line`.

**Worked example:** Mr. Muncher's title asks `fitted_font(bold=True, texts=(...), width=640,
largest=48)` and gets the first size from 48 down in which every text is at most 640 pixels
wide; Zombies' `fitted_title_font(texts=..., width=640, largest=48)` is the same call with
`bold=True` fixed. One function serves both, and a third game's body text asks `bold=False`.

**Exactness:** proof 1 (render the same strings through old and new at every size 8 to 64 and
assert equal pixels and equal chosen size, both fonts), then 2 and 3. No sprite, event or save is
touched, so no golden can move; the proof exists to catch a typo, not a design risk.

### Sub-plan 2: `HighScoreTable` (candidate 2)

**Files:** create `src/glitchygames/state/high_scores.py`; modify the four games'
`_save_high_score` (and Clockwork's `_load_high_scores`, Mr. Muncher's `_saved_high_scores` and
`_best_saved_score`), and each game that adds a field gains its entry subclass; tests in
`tests/state/` and the four games' own test files.

**Interface:**

- `HighScoreEntry` (pydantic, `frozen=True`, `extra='forbid'`): `score: int`. Clockwork's
  `ClockworkHighScore(HighScoreEntry)` adds `floor: int`; Mr. Muncher's subclass adds
  `level: int`. Field order is declaration order (base first), so `model_dump()` gives
  `{'score': ..., 'floor': ...}`, the order today's code appends.
- `HighScoreTableSettings` (pydantic): `slot_name: str = 'high_scores'`, `limit: int = 10`,
  `best: BestScore = BestScore.HIGHEST`. `BestScore` is a `StrEnum` with `HIGHEST` and `LOWEST`
  (a racing or time-trial game sorts ascending: an explicit flag, both branches tested).
- `HighScoreTable(*, saves: SaveManager, entry_type: type[EntryT], settings=...)`, generic in
  the game's entry model: `.entries() -> list[EntryT]` (best first);
  `.record(entry: EntryT) -> list[EntryT]` (the sorted, cut list, which the game turns into
  `GameOverScene(high_scores=[entry.model_dump() for entry in ...])`); `.best() -> int` (0 when
  empty).
- Conversion happens only at the two boundaries: `entry_type.model_validate` on each loaded
  dictionary, `model_dump()` for the saved payload and for `GameOverScene`, whose
  `high_scores: list[dict[str, Any]]` parameter stays as it is.

**Behaviours to keep exactly** (the characterization table): one `saves.load(slot)` per record,
a `SaveNotFoundError` or a missing `'scores'` key means an empty list, one
`saves.save(slot, {'scores': ...})` and nothing else; the sort is `list.sort(key=...,
reverse=True)` on the appended list, so a **new entry that ties an old one stays below it** (the
sort is stable and `reverse=True` keeps the original order of equal elements). A tidy-looking
replacement (insertion before the first lower-or-equal entry) would put the new tie above the old
one and change which entry a full table drops; the test pins the tie. The cut is `[:limit]`.
Mr. Muncher loads once in `_best_saved_score` and once in `_save_high_score` (two loads); the
table must not change that count, as the save door's calls are recorded. Every save file the four
games write today validates against its game's model and is written back byte-identical (the
characterization table includes each game's real payload and each golden header's save
snapshot).

**Worked example:** Clockwork ends a climb with score 900 on floor 3. Today
`_save_high_score` loads, appends `{'score': 900, 'floor': 3}`, sorts, cuts to 10 and saves;
afterwards `GameOver` shows the top 5. With the table:
`table.record(ClockworkHighScore(score=900, floor=3))`, the same one load and one save, and the
saved entry dumps as `{'score': 900, 'floor': 3}`, the same dictionary order.

**An entry that fails validation: two policies, chosen by an option (the owner, 2026-11-20).**
Example: Clockwork's save holds `{"scores": [{"floor": 3}]}` (no `score`; today it is kept, sorts
as 0 and is written back every game). A new engine option, `--invalid-high-scores
{refuse,drop}` (default `refuse`; a command-line option, and an explicit
`HighScoreTableSettings.invalid_entries` field for code). It is not a `[tool.glitchygames]`
setting: only the repository's tools read that table, and a game installed from a wheel never
sees `pyproject.toml` (corrected while building it, 2026-11-20). It picks:
- **`refuse` (the default for now; the owner may switch it later):** the table raises the
  existing `SaveCorruptedError` naming the slot and the first bad entry. The game-over flow
  catches it, still shows the run's score, logs one error, and does not save, so the file stays
  exactly as found.
- **`drop`:** invalid entries are left out with one logged warning naming each, the table works,
  and the next save writes the file without them.
The option is one of the engine's Game Options (`GameEventManager.args`, listed in
docs/architecture/argument_system.md); it must not clash with any tool's or game's arguments.

**Tests for the policies (behaviours; both branches, the owner's rule that a reachable mode is
an explicit flag tested both ways):**
- With the default, a file holding an invalid entry: `record()` raises `SaveCorruptedError`
  naming the slot and entry; the save door saw one load and no save; the file's bytes are
  unchanged.
- With `drop`: the same file gives the valid entries in their order, one warning per dropped
  entry is logged, and the next `record()` saves the file without the invalid ones.
- Valid files behave identically under both policies (the characterization table runs under each).
- The option parses from the command line, defaults to `refuse`,
  rejects any other value naming the two choices, and the game-over flow under `refuse` shows the
  score, logs the error and does not save (a test through a stand-in game-over scene).
- An entry with an unknown extra field (refused by `extra='forbid'`) and one with a wrong type
  count as invalid under both policies.

**Exactness:** proofs 1 (save-door spy: the sequence of `(call, slot, payload)` from each game's
golden replay is equal before and after) and 2. Risk: none to low (the in-memory replay sandbox
sees the same calls).

### Sub-plan 3: HUD labels as sprites, `Scene.pause()`, and the one checked re-record (candidate 3)

Three parts, in two PRs (the coordinator's ruling, 2026-11-21, so the neutral half lands
sooner); only part C changes recordings:

- **First PR, from main** (`refactor/engine-scene-pause-and-recording-check`): part B and the
  check of part C (its comparison and command line, with their planted-defect tests). Neither
  changes a recording, needs Sub-plan 1 or waits for Arcade sub-plan 5.
- **Second PR** (`refactor/engine-hud-labels`, on Sub-plan 1 and the first PR): part A and the
  re-record itself, which land together (part A alone fails every Brave and Clockwork golden),
  between Arcade sub-plans 5 and 6.

**A. `HudLabel`.** Brave's and Clockwork's HUDs (score, lives, and Clockwork's floor name)
become sprites in the scene's group, rendered only when their text changes, as Zombies' HUD
already is (its labels are pre-rendered sprites; title, pause and game-over text already render
once). Measured gain from no longer calling `Font.render` six to nine times a frame: Clockwork
2.3 %, Brave 0.6 % of the frame on the M4 Max (more on a Pi, unmeasured).

- **Files:** create `src/glitchygames/sprites/hud_label.py`; modify Brave
  `brave_adventurer_core/scene.py` (`setup`, `render` at 958, `_draw_hud` at 1062-1085 goes; it
  serves both editions) and Clockwork `game.py` (`render` at 1142, `_draw_hud` at 1157-1189 goes);
  tests in `tests/sprites/` and both games' test files.
- **Interface:** `HudLabel(*, font, color, groups, position: tuple[int, int], anchor:
  HudAnchor = HudAnchor.TOP_LEFT, shadow_color: Color | None = None, shadow_offset:
  tuple[int, int] = (1, 1), layer: int = ...)`, a screen-space sprite standing on `RootSprite`
  (`tests/test_sprite_classes_are_root_sprites.py`); a `text` property whose setter re-renders
  (through Sub-plan 1's `render_line`, so antialiasing follows `FontManager.antialias()`) only
  when the text differs; `HudAnchor` a `StrEnum` (`TOP_LEFT`, `TOP_CENTER`, `TOP_RIGHT`: the
  three positions today's HUDs use, the centred one re-anchoring when its width changes, as
  Clockwork's floor name does). Redrawn every frame by the group like Zombies' `TextPicture`
  (`dirty = 2`), since both scenes fill the screen each frame.
- **The shadow is a second `HudLabel`** (no shadow of its own) that the owning label creates,
  adds to the group just before itself in the same layer, and keeps in step. Why not one image
  with the shadow composited in: antialiased text has per-pixel alpha, and blending shadow and
  text into an intermediate surface and then onto the screen rounds differently from blending
  each straight onto the screen, as today's code does, so the pixels would differ at the glyph
  edges. Two sprites blitted in today's order (score shadow, score, lives shadow, lives, floor
  shadow, floor) reproduce today's pixels; one class keeps one text mechanism. The detailed plan
  confirms this with proof 1 and keeps the single-image version only if it measures identical.
- **Draw order (found while verifying):** Clockwork draws the group and then the HUD
  (`game.py:1151-1154`), so labels in the top layer are drawn in the same order as today. Brave
  draws the group, then the pit fill, the enemies in a pit and an unconditional re-blit of the
  player (`scene.py:972-983`), and only then the HUD (986). A label in the group is drawn before
  those, so wherever the player's rect (or a pit) meets a label, today the label is on top and
  as a sprite it would be underneath. Task 0 of the detailed plan measures, over every frame of
  both Brave recordings, whether any post-draw blit meets a label's rect (the labels sit in the
  top 30 pixels; the pits at ground level); the check in part C fails on any such frame whatever
  the measurement says. **The HUD stays on top** (the owner, 2026-11-20): Brave's post-draw pass
  (the pit fill, the enemies in a pit, the player's re-blit) leaves the label rects alone, so a
  label is never drawn under anything, as today, and the check stays strict.

**B. `Scene.pause()` replaces the hand-built pause scenes** at Brave 813 (`_pause_game`),
Clockwork 1050 (focus loss) and 1065, and Mr. Muncher `game.py:1262`: the same `next_scene =
PauseScene(options=self.options)` assignment is what `Scene.pause` does (`scenes/scene.py:4540`),
plus one INFO log line (`Scene pause requested`), below the games' default WARNING level.
Whether any scene overrides `pause()` is checked first (none under `src/games` does today:
`git grep -n "def pause" -- src/games` is empty). Exactness: proofs 2 and 3 on their own commit,
before part A, since no sprite, event or save changes.

**C. The checked re-record**, the plan's one reviewed step that changes recordings (the owner's
decision; "re-record only deliberately, as a reviewed step").

- **Recordings, nine:** the six that show the new labels (goldens: Brave
  `golden-classic.jsonl.gz` and `golden-papyrus.jsonl.gz`, Clockwork `golden.jsonl.gz`; bundled
  demos: Brave `classic.jsonl.gz` and `papyrus.jsonl.gz`, Clockwork `climb.jsonl.gz`), and in the
  same step Bitmappy's `drawing.jsonl.gz` and the text-input demo's `typing.jsonl.gz`
  (`plans/2026-11-20-window-owner-events.md`, its decision 5: they predate its window-setting
  event, and its tolerance for older recordings goes once they are re-recorded) and Zombies'
  `golden.jsonl.gz`. That last one replays exactly today ("no frames differ"), but its content
  hash differs at two scene starts whose constructor arguments grew after it was recorded on
  2026-11-15: frame 291's `FeatureCardScene` gained `run` (#215) and frame 311's `TitleScene`
  gained `opening: false` (#227).
- **How they are re-recorded: by rebaseline, not by a fresh session.** A fresh recording never
  matches the one it replaces (each frame's dt is measured in real time, so sprites differ by a
  few pixels: `scripts/record_scripted_session.py`'s docstring), which would make a side-by-side
  check meaningless. `--replay-trace OLD --rebaseline NEW --headless` (`replay/driver.py` rule 17,
  `replay/rebaseline.py`) replays OLD's inputs and dt under the new code and records NEW from that
  run, so OLD and NEW are frame for frame the same session and every difference is the code's.
- **The check** (a reusable comparison in `src/glitchygames/replay/recording_differences.py`,
  its command line in `scripts/check_rebaselined_recordings.py`, kept in the tree for the next
  reviewed re-record; this step's allowances are a plan file the script reads, committed with
  the re-record, so the script names no step): for each OLD/NEW pair it fails unless
  - both hold the same frame count, scenes per frame, served inputs and dt, saves and device
    fields, and internal events, record by record;
  - every sprite record in every frame is identical (id, rect, visible, group order) once the
    pair's allowed sprite ids are set aside, and NEW's extra ids are exactly the allowed ones;
  - every header and `scene_start` field is identical except the measurement histories
    (`content_hash`, `processing_seconds`, `audio_*`) and the header fields a rebaseline
    rewrites whatever the code does (the measurement runs, which hold the source revision,
    `rebaselined_from`, the engine, pygame and Python versions, `custom_event_types`), plus the
    pair's named allowances. The recorded start time is compared: a rebaseline keeps OLD's.
    Custom events compare by their type's name: found while building the check, a rebaseline
    of an unchanged golden rewrites `custom_event_types` with this process's numbering (Brave's
    and Clockwork's goldens predate the field and gain it, with `glitchygames.sprite_spawn`
    added since), so numbers alone would report differences the code did not make;
  - the pixels are identical: the suite run under the frame fingerprints plugin
    (`glitchygames/testing/frame_fingerprints.py`) on the commit before the change and on the
    change commit, compared test by test as `compare_driver_frames.py` compares drivers: no
    test's frame sequence may differ, no test may be in one run only, and the report counts the
    frames compared.

  Allowances, per pair and nothing else: Brave's four recordings, the `HudLabel` ids of the score
  and lives labels and their shadows; Clockwork's two, those plus the floor label and its
  shadow; `drawing` and `typing`, the window-owner plan's window-setting internal events (by
  custom event type name); Zombies' `golden`, the `run` argument
  of frame 291's `FeatureCardScene` start and `opening: false` of frame 311's `TitleScene` start.
- **The check is proven able to fail** before it is trusted (the global rule): planted on a
  copy, each of these turns it red: a label one pixel off, a non-HUD sprite moved one pixel, an
  extra sprite of another class, one pixel changed outside the HUD, an internal event dropped, a
  third scene-argument change in Zombies' golden, a window-setting event in a HUD recording.
- **Prerequisite and what moves with it:** the window-owner plan's window-setting event has
  landed (otherwise `drawing` and `typing` have nothing to re-record and wait for the next
  reviewed re-record). The files that pin these recordings are updated in the same commit and
  listed in Task 0 (`git grep` for each name: the provenance fixtures in `tests/fixtures/provenance/`,
  `tests/replay/test_record_scripted_session.py`, Brave's recording-history test, the
  measurement ledger via `nox -s replay-metrics`, the benchmarks); the recording history carries
  over, as a rebaseline stacks its own hashes in front of OLD's.
- **The review:** the PR shows the check's report for all nine pairs (every allowed difference
  counted per recording, nothing else), the fingerprint comparison's empty result, and the
  measured gain. The re-record is its own commit, after parts A and B, so reverting it alone is
  possible.

**Tests, as behaviours:** a label renders once and not again while its text is unchanged; it
re-renders when the text changes and re-anchors (right and centre) by the new width; its pixels
over a scene's background equal today's two direct blits for the score, lives and floor texts;
the shadow label sits under its label in group order; the label is screen space and stands on
`RootSprite`; with the labels, Brave's and Clockwork's frames (part A's characterization, run
before the re-record against OLD's replay with the label ids set aside) match today's pixel for
pixel; each game's pause key and Clockwork's focus loss still lead to `PauseScene`; the check
passes on the nine real pairs and fails on each planted defect above.

### Sub-plan 4: The idle-to-demo loop (candidate 4)

**Files:** `src/glitchygames/scenes/idle_demo.py` (the model), `scenes/__init__.py`
(SceneManager) and `scenes/scene.py`; PaddleSlap `__init__.py` (its game-over screen becomes the
first user). Then Brave's, Clockwork's, Drawing Fire's and Mr. Muncher's title or game-over
scenes, each its own small PR the owner approves.

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
(PaddleSlap's docstring says so), and the manager's counter must follow the same rule. Each later
game's PR is a visible behaviour change and adds no recording change: its goldens never idle for
`seconds` (checked with the spy per game).

### Sub-plan 5: The platformer kit (candidate 1), in four steps by risk

A helper set named for what each piece does, in the owner's homes: `physics_field` and
`respawn_with_fade` in `src/glitchygames/platformer/`, `ActionRouter` and the standard controls
in `src/glitchygames/input/` beside `ActionMap` (`input/action_map.py:152`). Brave and Clockwork
are the first users, and a top-down game uses the router as is.

- **5a, first step: the access-cost benchmark** (the owner, 2026-11-20), before any game changes.
  The twelve accessors are read many times per sprite per frame, and Brave's profile already
  spends much of its frame on per-sprite lookups. A built-in `property` runs in C; a hand-written
  descriptor's `__get__` runs in Python and can cost several times more per access. A benchmark in
  `tests/benchmarks/` (collected by `noxfile.py`'s `_BENCHMARK_PATHS`) measures reads and writes of
  today's property forwarders against `physics_field`, at Brave's sprite count. If
  `physics_field` is measurably slower, it generates real `property` objects (the same
  declaration, C-speed access) instead of being a descriptor class; the choice and the numbers go
  in the PR.
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
  game's own handlers call and then fall to `super()` when False, exactly the current
  `elif action is None: super()...` shape. Reactions stay the game's own (Brave's sound and
  jump, Clockwork's `_try_jump`). This is where the kit stops: no `Scene.bind_actions`. Task 0
  of its detailed plan reads the handler pairs and lists every difference before any code moves
  (axis deadzones, which release events call `handle_event`, Brave's voice-assistant buttons).
  Proof 1 (a table of events to the old handler's observable result, then the new), 2, 3, and
  proof 4 on the posted and consumed events.
- **5d, `respawn_with_fade`** (low to medium: tween order). Same two tweens, same properties,
  durations 0.2 and 0.3, easing `ease_out_quad` and `ease_in_quad`, same callback order, and the
  inert `_restore_input_after_respawn` callbacks (both games carry a docstring-only one, Brave
  `scene.py:803`) go away or become `on_done=None`. Proof 4: the tween creation sequence per
  frame, from a golden's replay, equal before and after. Note `max(0.0, ...)` (BUGS.md #230):
  the float type of the respawn position is recorded, so the helper takes the already-computed
  point.

Together the audit estimated 250 to 300 lines removed across the two games. Sub-plan 5 runs on
the recordings Sub-plan 3 re-recorded; it changes none of them.

## Out of scope, and where it would fit

- **Timers and cooldowns** (`Countdown`, `PhaseClock`; about 25 `x -= dt` sites): high golden
  risk (float accumulation order changes the last bit and a golden compares exact states).
  Only for new games, or for a game the owner is willing to re-verify bit by bit, as its own plan.
  It is also where a `BeatClock` lands (below).
- **HUDs of the other games:** Zombies' is already sprites; Drawing Fire draws its HUD
  immediately (its sprite conversion is in plans/future-work.md); Mr. Muncher's `SidePanel` is a
  sprite. `HudLabel` is there for them and for new games; converting them would need its own
  checked re-record.
- **Per-player high-score tables and player names:** wait for the player roster (decision 9).
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

0. **Performance, per PR** (the owner, 2026-11-20): no separate benchmark branch; the replay
   ledger's rows (every golden and demo, per commit, on the Mac and the Pis) are the before and
   after. Each PR states the per-frame processing p50 and p99 change against main for the games it
   touches; a slowdown beyond the run-to-run noise blocks the merge. Expected: Sub-plans 1, 2 and
   4 neutral, Sub-plan 3 faster (measured), Sub-plan 5 the one risk (its benchmark first, above).
1. Only Sub-plan 3's re-record commit changes a recording: the diff of `*.jsonl.gz` against
   origin/main is empty at every other PR and commit, and that commit changes exactly the nine
   recordings, each with the check's report.
2. Outside that step, no sub-plan adds a sprite to a scene group, posts an event, or reorders a
   save or sound call; inside it, the only differences are the allowances it names.
3. The check is shown to fail on every planted defect before its pass is cited, and the pixel
   comparison is shown to have compared frames (a non-zero frame count per recording).
4. A kit used by one game only is not worth landing: each of 1 to 5 has at least two users today
   (5d's helper, 5a to 5c, `HudLabel`: Brave and Clockwork; the router also fits Mr. Muncher's
   pause).
5. High-score entries round-trip every real save and golden save snapshot byte for byte.
6. The engine imports no game; the games import the engine (`tests/test_workspace_config.py`).
7. Docs: each new engine module gets its `docs/glitchygames/` page, `docs/architecture/` mention
   where it changes a flow (idle demo, saves, the reviewed re-record procedure in
   `gameplay_replay.md`), and the game packages' README lines that name the copied helpers; grep
   every .md for the old paths.

## Decided (the owner, 2026-11-20)

1. HUD labels become sprites in Brave and Clockwork (`HudLabel`), with one checked re-record of
   their six recordings; `Scene.pause()` replaces the hand-built pause scenes in the same
   sub-plan.
2. Homes: font helpers in `font_manager.py`, `HighScoreTable` in `state/`, `HudLabel` in
   `sprites/` (absorbing `ShadowedText`), `IdleDemo` in `scenes/`, `ActionRouter` in `input/`,
   `physics_field` and `respawn_with_fade` in `platformer/`.
3. Stop at `ActionRouter`; no `Scene.bind_actions`.
4. `IdleDemo`: PaddleSlap first, then Brave, Clockwork, Drawing Fire and Mr. Muncher as separate
   small PRs the owner approves.
5. High-score entries are strict pydantic models: a frozen `score`-only base, `floor` and `level`
   subclasses, converted at the disk and `GameOverScene` boundaries, every existing save loading
   in the same field order. An invalid entry is refused (`SaveCorruptedError`, the file kept, the
   game-over flow catches it) by default, or dropped with a warning, chosen by
   `--invalid-high-scores {refuse,drop}`; both policies tested.
6. Per-player tables and player names wait for the player roster; no `player_slot` or `name`
   field now.
7. Sequencing: Sub-plans 1 and 2 any time; the re-record step (with `drawing`, `typing` and
   Zombies' golden) between Arcade sub-plans 5 and 6; `IdleDemo` and the platformer kit after.
8. Brave's HUD labels stay on top: its post-draw pass leaves the label rects alone (2026-11-20).
9. If the window-owner plan's API has not reached Bitmappy and the text-input demo by the
   re-record step, the step re-records the other seven and `drawing` and `typing` wait for the
   next reviewed re-record (2026-11-20).

Related: plans/future-work.md (Games), plans/future-features.md #64 (BeatClock),
plans/2026-11-20-window-owner-events.md (the other overnight plan; shares Sub-plan 3's
re-record step).
