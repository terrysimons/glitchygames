# `/sprite <description>` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** typing `/sprite a blue dragon` in the AI console generates a sprite through the local AI service, saves it under the game's package, and adds it to the running scene at the center of the camera's view, in a recorded event that replays exactly.

**Architecture:** the console's worker generates and saves; the main thread posts one recorded input event carrying the sprite's TOML text and world position; an engine-level handler builds a world-space sprite from the text and adds it to the game's scene. A replay serves the recorded event, so it needs neither the AI service nor the saved file.

**Tech Stack:** Python 3.14, pygame-ce, pydantic, pytest with pytest-mock.

**Spec:** `plans/2026-11-16-console-sprite-generation.md` on main (sections "Part 2: `/sprite <description>`" and "Settled after the builder check"; approved 2026-11-17). This branch does not contain that file: see "Where this branch sits".

## Where this branch sits

- `feat/sprite-command` is stacked on `feature/sprite-color-profiles` (the peer session's branch, at `e216633e`), which is stacked on `feature/zombies-aint-my-neighbors` (#215). The owner put `/sprite` there (2026-11-17), because that branch built the shared text loader this needs (`SpriteFactory.load_sprite_from_text`, `sprites/sprite_text.py`).
- Neither base contains #216 (`4f53b448`, Part 1 of the spec). This plan uses only what this branch has: `SpriteGenerationService` (unchanged by #216) and `api/client.find_available_path` (#216 may have moved it into `api/sprite_requests.py`; when a base merges main, this branch follows it to wherever it lives, and keeps one copy).
- Its PR opens with `--base feature/sprite-color-profiles` once that branch is pushed, saying it is stacked.

## The thread question (the owner, 2026-11-17: "Yes go ahead")

The color profiles plan (decision 6) says the game uses no threads: its Part 3 turns the console's request into an async task the frame loop steps. That isn't built. `/sprite` uses the console's existing worker, exactly as `/ask` does, so Part 3 converts both commands together. Nothing in this plan adds a thread or a second worker.

## Global Constraints

- The console exists only with AI on: never with `--headless`, in a replay or in the browser (`ai_host.py`). `/sprite` therefore never runs in a replay; the replay only serves its event.
- The frame never waits: generating and saving run on the worker; the main thread only posts and prints.
- Code driving the game from outside its logic posts with `recording.post_input_event` (recorded as `origin: external`; a replay serves it whether or not the poster runs).
- Custom event types are registered by name at import (`events.base.named_custom_event_type`).
- World-space sprites: the engine owns `rect`; position with `world_x`/`world_y`.
- Every game object is a sprite in the scene's groups, never drawn straight to the screen.
- Unhandled events raise under `--no-unhandled-events` (on in every test): the spawn event is handled by the engine and never reaches a game's handlers.
- Engine changes are shared by every game: the whole suite runs, not only the console's tests.
- Pydantic models (`frozen=True`, `extra='forbid'`) for new data classes; full names; keyword arguments; mocker, never unittest.mock.
- New module- or class-level mutable state fails `tests/test_process_state_guard.py`: the event type is an `int` constant registered at import, which is allowed.

## Review Focus

1. **A model-chosen sprite name that is a path** (`../../evil`, `/etc/x`, `con`, an empty name): the file must land inside `<package>/sprites/` under a safe name, or not at all. Test in Task 3.
2. **A scene that takes raw events** (`process_event`, which bypasses the engine's handler table): the spawn must still be handled by the engine, not handed to that scene. Test in Task 2.
3. **`/cancel`, then the late result arrives** while a second `/sprite` or `/ask` runs: the late result must spawn nothing and must not touch the new request. Test in Task 3.
4. **Arcade inner games** replaying a recording that holds a spawn: the handler runs in the inner game's own context and adds the sprite to the inner scene, not the outer one. Test in Task 4.
5. **The generated text fails to build** after a successful generation (the factory refuses mixed content, say): the console says so, nothing spawns, and nothing is posted, so the recording carries no event that cannot build. Test in Task 3.

---

### Task 1: a world-space sprite built from text

**Files:**
- Create: `src/glitchygames/sprites/spawned.py`
- Modify: `src/glitchygames/sprites/factory.py` (`load_sprite_from_text` gains a sprite class)
- Test: `tests/sprites/test_spawned_sprite.py` (a new subject: the spawned sprite), `tests/sprites/test_sprite_text.py` (the factory's new keyword)

**Interfaces:**
- Produces: `SpriteFactory.load_sprite_from_text(*, text: str, source_name: str, sprite_class: type[AnimatedSprite] = AnimatedSprite) -> AnimatedSprite`. The default keeps today's behavior.
- Produces: `class SpawnedSprite(AnimatedSprite)` with `COORDINATE_SPACE = CoordinateSpace.WORLD`, `world_x: float`, `world_y: float`, and `@classmethod from_text(cls, *, text: str, source_name: str, center_x: float, center_y: float) -> SpawnedSprite`, which places the sprite's center (its native image size) at the point.

- [ ] **Step 1: Write the failing tests.**
  - `test_a_spawned_sprite_is_centered_on_its_point`: a 4x2 static sprite from text at (100.0, 50.0) has `world_x == 98.0`, `world_y == 49.0`, and is world-positioned (`world.is_world_positioned(sprite)`).
  - `test_a_spawned_sprite_animates_as_a_loaded_one`: an animated text's frames and frame intervals equal `SpriteFactory.load_sprite_from_text`'s for the same text.
  - `test_text_that_cannot_build_a_sprite_is_refused`: the factory's `ValueError`, with `source_name` in its message.
  - In `test_sprite_text.py`: `test_the_text_loader_builds_the_class_it_is_given`, and the default still returns a plain `AnimatedSprite`.
- [ ] **Step 2: Run them; they fail** (`spawned` doesn't exist; the keyword is unknown).
  Run: `uv run pytest tests/sprites/test_spawned_sprite.py tests/sprites/test_sprite_text.py --dummy-only -q --no-cov`
- [ ] **Step 3: Implement.** The factory builds `sprite_class(groups=None)` and calls `load_text`, the one path. `from_text` sets the position from the loaded image's size.
- [ ] **Step 4: Run them; they pass.** Then all of `tests/sprites/`.
- [ ] **Step 5: Lint, type-check, commit.**

### Task 2: the spawn event and its engine handler

**Files:**
- Create: `src/glitchygames/events/sprite_spawn.py`
- Modify: `src/glitchygames/engine/game_engine.py` (`process_events`, the handler table)
- Test: `tests/events/test_sprite_spawn.py`

**Interfaces:**
- Consumes: `SpawnedSprite.from_text` (Task 1).
- Produces: `SPRITE_SPAWN_EVENT: int = named_custom_event_type('glitchygames.sprite_spawn')`.
- Produces: `class SpriteSpawn(BaseModel)` (frozen, `extra='forbid'`) with `toml_text: str`, `sprite_name: str`, `world_x: float`, `world_y: float`, plus `to_event() -> pygame.event.Event` and `from_event(event) -> SpriteSpawn`.
- Produces: `def post_sprite_spawn(*, spawn: SpriteSpawn) -> bool`, which calls `recording.post_input_event`.
- Produces: `def add_spawned_sprite(*, spawn: SpriteSpawn, scene: Scene) -> SpawnedSprite | None`. It adds the sprite to `scene.debug_subject.all_sprites` (the game's own scene under a pause screen, settled point 1). Text that cannot build is logged at warning, one line naming the sprite, and returns None.
- The engine handles `SPRITE_SPAWN_EVENT` before the raw-event bypass in `process_events`, so a `process_event` scene never sees it. The handler returns True even when the text cannot build: the event was the engine's, and the game goes on.

- [ ] **Step 1: Write the failing tests.**
  - `test_a_spawn_adds_a_world_sprite_centered_on_its_point`: on a still camera and on a moved one (`camera.world_x = 300`), the sprite's `world_x`/`world_y` are the point less half its size, and after one frame its `rect.center` is the point less the camera's position.
  - `test_a_spawn_under_the_pause_screen_goes_to_the_paused_game`.
  - `test_a_spawn_that_cannot_build_adds_nothing_and_logs_once` (`caplog`, one warning line, no traceback).
  - `test_a_spawn_never_reaches_the_games_handlers`: it runs under `--no-unhandled-events` with a scene whose `on_*` handlers would raise.
  - `test_a_raw_event_scene_still_gets_the_spawn_added`.
  - `test_a_spawn_round_trips_through_its_event` (`from_event(to_event())` gives an equal model).
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them; they pass.** Then `tests/events/`, `tests/engine/` and `tests/test_engine_doors.py`.
- [ ] **Step 5: Lint, type-check, commit.** Name the engine tests that ran in the message.

### Task 3: the `/sprite` command

**Files:**
- Modify: `src/glitchygames/ai_console.py` (the command, the worker's job, the main-thread spawn, the docstring's rules 1, 2 and 5)
- Create: `src/glitchygames/sprites/saved_sprites.py` (choosing and writing the file)
- Test: `tests/test_ai_console.py` (the command), `tests/sprites/test_saved_sprites.py` (a new subject: the file)

**Interfaces:**
- Consumes: `SpriteSpawn`, `post_sprite_spawn` (Task 2), and `SpriteFactory.load_sprite_from_text` for the pre-post check.
- Produces: `def sprite_file_name(*, sprite_name: str | None, description: str) -> str`: a lowercase file stem of letters, digits, `-` and `_` only, from the sprite's name, else the description, else `sprite`; never empty and never a path.
- Produces: `def save_sprite(*, toml_text: str, file_stem: str, sprites_folder: Path) -> Path`. It creates the folder, never overwrites (a numbered name, through the existing `find_available_path`), and writes through `output_files.write_aside_then_replace`. `OSError` propagates to the caller.
- `AiConsole.__init__` gains `sprite_service: SpriteGenerationService | None = None` (None: built when first used), so tests pass one whose `_client` is a stand-in, as `tests/services/test_sprite_generation_service.py` does.
- Flow:
  1. `/sprite <description>` refuses an empty description (usage), a request already running ("#N is still running: /cancel to stop it", shared with `/ask`), the link states `/ask` refuses, and no scene ("No scene yet", as `/inspect`). Otherwise it prints "#N generating <description>...".
  2. The worker calls `generate_sprite(prompt=description)`. On success it checks that the text builds (the factory, off-screen, no groups), then saves to `<package directory>/sprites/` (`identity.game_package` of the scene's `debug_subject`, `identity.package_directory_of`).
  3. The worker hands the main thread the outcome: the TOML text, the sprite's name, and the saved path or the reason it wasn't saved. The worker never posts.
  4. The main thread drops the outcome if its request is no longer `self.running` (cancelled). Otherwise it reads the camera's center from `scene.debug_subject.camera` (`world_x + screen_width / 2`, `world_y + screen_height / 2`), posts the spawn and prints the path or "not saved: <reason>".
  5. A failed generation, or text that does not build, prints the service's error and posts nothing. `AIProviderError` (the service unreachable) prints that the AI service at its address can't be reached.
- `/help` lists `/sprite <description>`.

- [ ] **Step 1: Write the failing tests.**
  - In `test_saved_sprites.py`:
    - `test_a_file_name_is_never_a_path`, parametrized over `../../evil`, `/etc/passwd`, `a/b`, `   `, `CON`, `..`, `dragon!!` and None with an empty description. Each gives a stem matching `[a-z0-9_-]+`, and the saved file's parent is the sprites folder.
    - `test_a_second_sprite_of_the_same_name_gets_a_new_file` (both files exist; the first is unchanged).
    - `test_a_folder_that_cannot_be_written_raises` (read-only `tmp_path` folder; skipped on Windows, where a read-only folder is not refused).
  - In `test_ai_console.py`, with a stand-in sprite service and a scene:
    - `test_sprite_saves_under_the_games_package_and_posts_the_spawn`: the file exists under the stand-in game's package `sprites/`, one `SPRITE_SPAWN_EVENT` is posted with the TOML text and the camera's center, and the transcript names the path.
    - `test_sprite_never_waits_on_the_frame`: the stand-in holds its reply; `filter_events` returns at once and the transcript shows "generating".
    - `test_sprite_refuses_an_empty_description`, `test_sprite_refuses_while_a_request_runs`, `test_sprite_refuses_with_no_scene`.
    - `test_a_cancelled_sprite_spawns_nothing`: the late result after `/cancel`, with a second request running, posts nothing and leaves `running` alone.
    - `test_a_sprite_that_cannot_be_saved_still_appears` (the folder unwritable: "not saved", the spawn still posted).
    - `test_a_failed_generation_posts_nothing`, and the same when the text does not build.
    - `test_an_unreachable_service_is_named`.
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Implement.** Reword the docstring's rule 1 (read-only, except `/sprite`, which adds one sprite through a recorded event), rule 2 (the spawn event goes above the recorder on purpose) and rule 5 (generating and saving are worker work).
- [ ] **Step 4: Run them; they pass.** Then `tests/test_ai_console.py` and `tests/test_ai_host.py` whole.
- [ ] **Step 5: Lint, type-check, commit.**

### Task 4: replay

**Files:**
- Test: `tests/world/test_gameplay_replay.py` (beside `TestInputPosts`), and the Arcade's inner-game tests (`tests/engine/test_inner_game.py`)

**Interfaces:**
- Consumes: `post_sprite_spawn` (Task 2), `record_session` and `replay_session` (that test file's helpers).

- [ ] **Step 1: Write the failing tests.** They pass only once Tasks 1-2's handler is in the recorded game's path. If they pass at once, check that they would fail with the handler removed (plant the removal).
  - `test_a_spawn_replays_at_its_frame_and_place`: record with a spawn posted at `ACTION_FRAME`, delete the sprite file, replay with no AI; `divergence is None`, and the replayed scene holds the spawned sprite at the same `world_x`/`world_y` from the same frame.
  - `test_an_inner_game_replays_a_spawn_into_its_own_scene`: the outer scene's sprites are unchanged.
- [ ] **Step 2: Run them; plant the defect; see them fail; restore.**
- [ ] **Step 3: Commit.**

### Task 5: docs and the whole gate

**Files:** `docs/architecture/` (the AI console page: `/sprite`, the spawn event and its replay), `CLAUDE.md` ("the read-only AI console" becomes read-only except `/sprite`), the spec's status line on main when the base carries it (until then, this plan's).

- [ ] Grep every `.md` for "read-only AI console" and `/help`'s command lists; fix stale lines (finished plans keep theirs).
- [ ] Run the whole gate: `uv run ruff format --check src tests scripts noxfile.py && uv run ruff check src tests scripts noxfile.py && uv run basedpyright && uv run ty check && uv run pytest -q -p no:cacheprovider`, then `uv run nox -s lint-docs`.
- [ ] Try it in a running game with the AI service up (`uv run paddleslap`, backtick, `/sprite a blue dragon`). Record a run, then replay it headless with the saved file moved away.
- [ ] Commit; push and open the PR on the owner's word.

## Left open (the builder's calls, recorded as rulings when made)

- The command's exact wording in `/help` and the console's lines.
- Where in `process_events` the check sits, as long as it comes before the raw-event bypass.

## Execution record

The executor's ledger, kept as written: the rulings made while building, the whole-branch review's fixes and the minors it deferred, and the merges of the base.

- Spec: plans/2026-11-16-console-sprite-generation.md on origin/main (read with git show; not in this branch's base), Part 2 and "Settled after the builder check".
- Pre-flight: T2 consumes T1's SpawnedSprite.from_text(*, text, source_name, center_x, center_y) — consistent. T3 consumes T2's SpriteSpawn, post_sprite_spawn and T1's load_sprite_from_text(sprite_class=...) for the pre-post check — consistent. T4 consumes T2's post_sprite_spawn and the replay test helpers — consistent.
- Task 1: complete (commits d506293..b832a91, tests: uv run pytest tests/sprites --dummy-only -q --no-cov → ============================= 1078 passed in 7.74s =============================)
- Task 1: Ruling: the factory's sprite_class is typed with overloads (no keyword: AnimatedSprite; a class: that class) instead of a defaulted type parameter, which ty refuses (invalid-parameter-default) — cost if wrong: none (same calls, same types).
- Task 1: Ruling: factory.py imports AnimatedSprite at module level (it was type-checking only, with an import inside load_sprite); checked: no import cycle (animated imports nothing that imports the factory) — cost if wrong: an import-order failure the suite would show.
- Task 2: complete (commits b832a91..60ef5ff, tests: uv run pytest tests/events tests/engine tests/test_engine_doors.py tests/test_process_state_guard.py tests/sprites --dummy-only -q --no-cov → ============================= 2850 passed in 7.97s =============================)
- Task 2: Ruling: the engine handles a spawn with no active scene by logging one warning and dropping it (the plan named no case) — cost if wrong: a spawn posted before the first scene is lost, which the console cannot do (it refuses with no scene).
- Task 2: Ruling: SPRITE_SPAWN_EVENT joins the process-state audit as EVENT_TYPE_TABLE, as the engine's other named event ids are — cost if wrong: none.
- Task 3: complete (commits 60ef5ff..8f1dac4, tests: uv run pytest tests/test_ai_console.py tests/sprites tests/events tests/test_process_state_guard.py tests/test_engine_doors.py --dummy-only -q --no-cov → ============================= 2450 passed in 8.95s =============================)
- Task 3: Ruling: the text-builds check runs on the main thread just before posting, not on the worker as the plan said (building a sprite makes pygame surfaces, which belong on the main thread); saving follows only once it builds, so an unbuildable sprite is neither posted nor saved — cost if wrong: a millisecond-scale build on the frame that posts.
- Task 3: Ruling: the console takes sprites_folder (None: the game's package's sprites folder) beside sprite_service, so tests never write into a source package — cost if wrong: one more constructor keyword.
- Task 3: Ruling: save_sprite imports find_available_path from api/client.py lazily instead of moving it (main's #216 reworked that file; a move would conflict) — cost if wrong: the sprites module reaches into the client module, to tidy when this branch takes main.
- Task 3: Ruling: the banner drops "read-only" ("AI console. /help lists commands..."), since /sprite changes the game — cost if wrong: none.
- Task 3: Ruling: unwritable-folder tests put the folder under a regular file instead of chmod 0o500, so they hold on Windows and as root — cost if wrong: none.
- Task 4: complete (commits 8f1dac4..44dd2ed, tests: uv run pytest tests/engine/test_inner_game.py tests/world/test_gameplay_replay.py tests/events --dummy-only -q --no-cov → ============================ 1607 passed in 13.18s =============================)
- Task 4: Ruling: fixed a Task 2 defect Task 4's replay test found — the handler read GameEngine._active_scene, which no run ever assigns, so every live spawn was dropped; it now reads scene_manager.active_scene (separate commit, tests corrected to set the scene where a run keeps it) — cost if wrong: none; the defect was real (probe: posted, recorded, never handled).
- Task 4: Ruling: the stand-in writer's StandInSounds becomes StandInFrameActions (gaining spawn_on_frame) instead of a sixth parameter, which ruff's argument limit refuses — cost if wrong: a rename inside tests/stand_in_games.py only.
- Task 4: Finding (reported, not fixed): GameEngine.process_events' raw-event bypass reads the same never-assigned _active_scene, so a scene's process_event is never called in a real run; its tests set the field by hand.
- Final review: opus, whole branch e216633e..ee9c3689 — "merge after fixing Important 1 and 2; item 3 needs honest wording".
- Final: fixed 1 a non-text model name (name = 5) raised in SpriteSpawn on the main thread — the service returns None for a name that is not non-empty text — test_a_name_that_is_not_text_is_no_name (5 cases), test_a_sprite_whose_name_is_not_text_still_spawns_under_the_description RED→GREEN.
- Final: fixed 2 a worker exception other than AIProviderError left the request running — caught, the request fails with it — test_an_unexpected_worker_failure_ends_the_sprite_request RED→GREEN.
- Final: fixed 3 (by wording, re-graded Important) /cancel cannot stop the service's blocking call; it now says the service finishes it and the sprite is dropped — test_cancelling_a_sprite_says_the_generation_runs_on RED→GREEN.
- Final: added test_a_sprite_named_like_a_path_is_saved_in_the_sprites_folder (Review Focus 1 at console level).
- Final: minor (deferred): 4 post_sprite_spawn's False return is ignored ("added" printed anyway); only a blocked type returns False, and the spawn type is never blocked.
- Final: minor (deferred): 5 the build check runs uncapped on the main thread (a huge sprite costs two hitches); consider a pixel or frame cap.
- Final: minor (deferred): 6 find_available_path then replace can overwrite if two processes save the same name at once; an exclusive create would close it.
- Final: minor (deferred): 7 tests/stand_in_games.py's sound_constants / sound_lines / live_voice_import now also hold the spawn's lines; rename them.
- Final: minor (deferred): 8 the file lands in debug_subject's class's package (a scene defined in glitchygames would write into the engine's source package), as the spec says.
- Final: gate on a7c4d95d — ruff, basedpyright, ty clean; 28631 passed, 100.00% coverage, driver differences 0 (gate-final.log).
- Merge: Ruling: after merging the base (main's #217 schema now checks text at load), a non-text sprite name fails the request naming the field, instead of spawning under the description; test updated to that contract — cost if wrong: a model's numbered name refuses the sprite rather than renaming it.
- Merge: gate on bf5f6a8c (base cc6f8761 merged) — ruff, basedpyright, ty clean; 29195 passed, 100.00% coverage, driver differences 0.
