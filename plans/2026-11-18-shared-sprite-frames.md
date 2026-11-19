# Shared Sprite Frames Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A sprite file's text compiles once per process into read-only frames that every sprite loaded from the same text shares, as compiled sounds are shared through `ENGINE_SOUND_CACHE`.

**Architecture:** A new module, `glitchygames/sprites/compiled_sprites.py`, holds `CompiledSprite` (what one load of a text produces, frozen), `SharedSpriteCache` (by key, LRU past a byte limit) and the process's `ENGINE_SPRITE_CACHE`. `AnimatedSprite.load_text` takes the compile from the cache, compiling on a miss by running today's loader on a private sprite and capturing what it set. Each sprite gets its own small `SpriteFrame` objects that point at the compile's surfaces and pixels. A frame's public `image` and `pixels` copy those on first read (copy-on-write at the frame, the owner, 2026-11-18), so whatever a caller does with them reaches only its own copy. The engine's own reads use accessors that never copy, so a sprite that is only played stays shared.

**Tech Stack:** Python 3.14, pygame-ce, pydantic (frozen models, `extra='forbid'`), pytest with pytest-mock.

**Spec:** this plan's Decisions section. They were agreed in conversation on 2026-11-18: the owner asked for compile-once-and-reuse "like we did with sounds", accepted the design, and asked for this plan. During Task 3 the owner replaced read-only shared frames and the `shared_frames` flag with copy-on-write at the frame (Papyrus draws into its frames' surfaces, which a read-only guard cannot catch); Decisions 3 to 6 and Tasks 3 to 5 are that revision. The record that started it: `bugs/2026-11-18-sprite-frames-held-a-tuple-per-pixel.md`.

## Base: decided before Task 1

#220 (`feature/sprite-color-profiles`) rewrites the loader this plan changes: 928 lines of `animated.py`, a new `sprite_toml.py` and `sprite_text.py`, and changes to `pixel_utils.py`. It also gives the plan its seam: `load_text(*, text, source_name)` is the one path every load takes.

So the plan is written against #220's code. Two ways to get there:
- **(a) Recommended:** `fix/sprite-frame-memory` becomes stacked on #220. Its tuple fix (one commit plus its ledger rows, not pushed) is replayed onto `feature/sprite-color-profiles`, and the PR targets it with `--base`, as #221 does.
- **(b)** The tuple fix goes to main now as its own PR, and this plan becomes a new branch stacked on #220 later.

The owner picks one.

## Decisions

1. **The key is the text, where it came from, and the loading class:** `(sha256 of the text, source_name, the class's qualified name)`. The class was added after the final review (the owner, 2026-11-19: a subclass overriding a loader step was silently given a plain compile; "It is a bug.").
   - The text is all a compile reads, so an edited file is a new key and nothing goes stale.
   - `source_name` is in the key because the compile's repair warnings name it.
   - Scale is not in the key: frames compile at native size.
   - If Part 2 (color profiles) adds a runtime setting that changes compiled pixels, that setting joins the key.
2. **What a compile holds:** everything `load_text` sets on the sprite from the text.
   - `name`, `description`, `tags`, `_default_hitbox`, `frame_anchor`, `_animations` (the frames), `_animation_order`, `_animation_frame_intervals`, `_loop_flags`, `_animations_without_frame_index`, `_game_tables`, `transition_data`, `pixel_row_repairs`, `_pixel_rows_source`, `_color_map`, `_color_order`.
   - Plus each frame's drawn surface at scale 1, the one `_create_optimized_surface` makes.
   - Not held: anything holding the instance. `state_machine` is rebuilt per instance from `transition_data`, and the initial animation, frame manager and image are set per instance.
3. **How it compiles: today's loader, captured.**
   - Today's `load_text` body becomes `_load_text_uncached` (no other change).
   - The compile runs it on the sprite being loaded (`compile_text_by_loading`), so its class's loader overrides run, and captures those fields into a `CompiledSprite`; that sprite then takes sharing frames like every later load. (First written as a private `AnimatedSprite(groups=None)`, which skipped a subclass's overrides; a subclass's constructor arguments rule out building a private instance of it.) Each frame's pixels become a tuple, and that private sprite's frames are the compile's template frames.
   - The loader is not rewritten, so a cached load and an uncached one cannot drift apart. The conservation test in Task 3 holds them equal for every shipped sprite.
4. **Each sprite owns its frames; the frames share their surfaces and pixels.**
   - A load from the cache builds a new `SpriteFrame` per template frame (`SpriteFrame.sharing(template)`): the same surface, the same pixel tuple, the same `loaded_pixel_rows`; its own `rect` and hitbox (copies) and its own `duration`.
   - It copies the other mutable state too: dicts and lists, `_game_tables` deep-copied, the default hitbox `Rect`.
   - So an assignment changes one sprite only. `frame.image = converted` (Papyrus), `frame.rect = ...`, `frame.hitbox = ...`, `set_pixel_data` and `frame.pixels = [...]` (Bitmappy) need no guard.
5. **Copy-on-write at the frame: the public `image` and `pixels` copy on first read.**
   - `SpriteFrame.image`: while the frame still points at a compile's surface, the first read copies it (`surface.copy()`), keeps the copy as the frame's own and returns it. Later reads return that copy.
   - `SpriteFrame.pixels` becomes a property: while it is the compile's tuple, the first read makes a private `list` and returns it. Its setter takes a new list, as today's attribute does.
   - The copy happens before the caller can write, so every kind of write reaches only the copy: methods (`set_colorkey`, `fill`, `blit`), C writes (`pygame.draw`, `PixelArray`, `surfarray`), and Bitmappy's `pixels[i] = ...`.
   - A surface cannot catch its own writes (C functions write its memory directly, and one surface cannot swap itself out of the sprites that share it); the frame is the one place every write can be caught.
6. **The engine's own reads never copy.**
   - `SpriteFrame.read_only_image` and `SpriteFrame.read_only_pixels` return the frame's current surface and pixels, shared or private, without copying. Callers must not change them.
   - The engine reads through these and through `SpriteFrame`'s own methods (`get_size`, `opaque_bounds`, `hitbox`, which use `_image`). The known reads to move are `animated.py` lines 702, 2596 and 2623 (`frame.image`), `_create_optimized_surface` and `_debug_frame_pixel_data` (`frame.pixels`), and `get_pixel_data` (it copies anyway, from `read_only_pixels`). Lines are as on this branch after Task 2.
   - `testing/sprite_files.py:153` reads through `get_pixel_data`, so it copies; that's fine for a test helper.
   - An engine read missed copies once per frame per sprite: still correct, but it loses the sharing. Task 3's played-sprite test is the check.
   - `SpriteFrame.is_sharing` is True while both the surface and the pixels are still the compile's.
7. **The cache follows `SharedSoundCache`'s shape.**
   - It is one per process, shared by every engine context (an Arcade tile reuses what another compiled).
   - Reads look up under one `threading.Lock`. A compile runs outside the lock, and two concurrent compiles of one key keep the first stored; they are equal.
   - Past `limit_bytes` (default `DEFAULT_SPRITE_CACHE_LIMIT_BYTES = 64 * 1024 * 1024`), the least recently used entries go. A sprite already loaded keeps its frames, because it holds them.
   - An entry's bytes are its surfaces' `width * height * bytesize`, plus 8 per pixel reference.
   - `clear()` exists for the test harness.
8. **Repair warnings are logged by the compile only.** A load from the cache logs none, but still gets the compile's `pixel_row_repairs`, so Bitmappy's notice and the tests see the same list.
9. **A text that fails to compile is not cached.** The next load of it compiles again and raises again.
10. **Out of scope:**
    - the DEBUG logging of large data, a separate item in the bug record;
    - the zombies `pool.py`, the game's call once this lands;
    - a disk layer: a compile is cheap, unlike rendering a sound;
    - per-pixel editor paths in Bitmappy;
    - Papyrus's `prepare_papyrus_sprite`, which now copies on read and so keeps private frames. Compiling its conversion once per file would let Papyrus sprites share too; that is a later decision.

## Global Constraints

- Python 3.14 and 3.15. ruff (100-character lines), basedpyright and ty clean; coverage stays at 100%, with no new `pragma: no cover` without its reason.
- New data classes are pydantic `BaseModel`, `frozen=True`, `extra='forbid'`. pygame types need `arbitrary_types_allowed=True`.
- Module-level mutable state needs its row in `tests/test_process_state_guard.py`, in the read-only cache wording of `ENGINE_SOUND_CACHE`'s row (R17).
- A new autouse reset fixture joins `engine_service_resets` in `tests/harness.py`.
- Tests use real pygame, real files (`tmp_path`) and `mocker` only. They are added to the existing file of the module they test; the new module gets its own test file.
- Keyword arguments in calls. Full names, never abbreviations. American spelling.

## Review Focus

1. **An engine read missed in Decision 6** (`frame.image` or `frame.pixels` somewhere in the per-frame path): it silently copies every frame of every sprite and the sharing is lost, with nothing failing. Task 3's played-sprite test plays, draws and collides two shared sprites for many frames and asserts every frame `is_sharing`; the reviewer greps the engine for public `.image`/`.pixels` reads on frames.
2. **A game changes a frame's hitbox `Rect` in place** (`frame.hitbox.x += 1`): each sprite has its own hitbox copy (Decision 4), so only that sprite changes. Task 3 tests it.
3. **One file loaded at scale 1 and at scale 3 in the same scene:** the scaled drawn surfaces stay per sprite and the native ones shared. Task 4 tests that each draws its own size.
4. **Bitmappy opens a sprite a game already loaded:** its edits copy on read and the game's sprite stays unchanged. Task 5 tests the edit, and the game's frame afterwards.
5. **A sprite saved by Bitmappy, then loaded again by a game in the same process:** the new text is a new key and loads the new pixels. Task 4 tests this through two different texts at one path.

---

### Task 1: Base the branch (the owner's choice above)

- [ ] **Step 1:** For (a): `git rebase --onto origin/feature/sprite-color-profiles origin/main fix/sprite-frame-memory`. The branch is not pushed, so this rewrites nothing published. Resolve `pixel_utils.py` against #220's version, keeping `_one_tuple_per_color`.
- [ ] **Step 2:** Run `uv run pytest tests/sprites src/apps/bitmappy/tests -q --dummy-only`. Expected: all pass, including `TestConvertedPixelsShareOneTuplePerColor` and `TestLoadedFramesShareOneTuplePerColor`.

### Task 2: `CompiledSprite`, `SharedSpriteCache`, `ENGINE_SPRITE_CACHE`

**Files:**
- Create: `src/glitchygames/sprites/compiled_sprites.py`
- Test: `tests/sprites/test_compiled_sprites.py`
- Modify: `tests/harness.py` (the fixture and its group), `tests/test_process_state_guard.py` (the audit row)

**Interfaces:**
- Produces:
  - `class CompiledSprite(BaseModel)`, frozen, with the fields of Decision 2. Collections become tuples or `MappingProxyType`, and frames are `tuple[SpriteFrame, ...]` per animation.
    - `drawn_surfaces: Mapping[tuple[str, int], pygame.Surface]`;
    - `byte_count: int`.
  - `class SharedSpriteCache` with:
    - `compiled(*, key: SpriteKey) -> CompiledSprite | None`;
    - `keep(*, key: SpriteKey, compiled: CompiledSprite) -> CompiledSprite`, which returns the entry kept, the first one if two raced;
    - `clear() -> None`;
    - `__len__`;
    - `bytes_held: int`;
    - `limit_bytes: int`.
  - `SpriteKey = tuple[str, str]`, the sha256 hexdigest and `source_name`.
  - `def sprite_key(*, text: str, source_name: str) -> SpriteKey`.
  - `ENGINE_SPRITE_CACHE: Final[SharedSpriteCache]` and `DEFAULT_SPRITE_CACHE_LIMIT_BYTES`.

- [ ] **Step 1: Write the failing tests** in `tests/sprites/test_compiled_sprites.py`:
  - `test_a_kept_sprite_is_found_by_its_key`;
  - `test_the_same_text_from_another_source_is_another_key`;
  - `test_another_text_is_another_key`;
  - `test_a_second_keep_of_a_key_returns_the_first`;
  - `test_past_the_limit_the_least_recently_used_go`: three entries of known `byte_count` against a limit of two. Reading the first keeps it, and the second goes;
  - `test_bytes_held_is_the_sum_of_its_entries`;
  - `test_clear_empties_it`.
  - `CompiledSprite`s for these come from a small helper building one from two one-color surfaces.
- [ ] **Step 2:** Run `uv run pytest tests/sprites/test_compiled_sprites.py -q --dummy-only`. Expected: FAIL (`ModuleNotFoundError: glitchygames.sprites.compiled_sprites`).
- [ ] **Step 3:** Implement the module, modeled on `audio/library.py` `SharedSoundCache`: an `OrderedDict`, one lock, `move_to_end` on read. Its docstring states the contract: read-only values computed only from their keys, never written after they are made.
- [ ] **Step 4:** Add the `empty_engine_sprite_cache` autouse fixture in `tests/harness.py`, beside `empty_engine_sound_cache`, with `clear()` before and after, and add it to `engine_service_resets`. Add the process-state row:

  ```
  'sprites/compiled_sprites.py': {
      'ENGINE_SPRITE_CACHE': ('R17: compiled, read-only sprite frames by text and source, one cache per process by design (the owner, 2026-11-18, "like we did with sounds"); CLAUDE.md.'),
  },
  ```

  Then add `test_every_test_starts_with_an_empty_engine_sprite_cache` in `tests/sprites/test_compiled_sprites.py`, modeled on the sound one.
- [ ] **Step 5:** Run `uv run pytest tests/sprites/test_compiled_sprites.py tests/test_process_state_guard.py tests/test_engine_context.py -q --dummy-only`. Expected: PASS.
- [ ] **Step 6:** Commit: "Sprites: a process cache of compiled sprite frames, shaped like the sound cache".

### Task 3: Sprites from one text share frames, copied on write

**Files:**
- Modify: `src/glitchygames/sprites/frame.py` (`SpriteFrame`: `sharing`, `image` and `pixels` copy on first read, `read_only_image`, `read_only_pixels`, `is_sharing`), `src/glitchygames/sprites/animated.py` (`load_text` cached, `_load_text_uncached`, the engine reads of Decision 6), `src/glitchygames/sprites/compiled_sprites.py` (`compile_sprite_text`)
- Test: `tests/sprites/test_animated_sprite.py` (`TestSharedFrames`, and `TestSpriteFrame`, where `SpriteFrame`'s tests are today), `tests/sprites/test_compiled_sprites.py`

**Interfaces:**
- Consumes: Task 2's cache and key.
- Produces:
  - `compile_sprite_text(*, text: str, source_name: str) -> CompiledSprite`;
  - `SpriteFrame.sharing(template: SpriteFrame) -> SpriteFrame` (classmethod);
  - `SpriteFrame.read_only_image: pygame.Surface` and `SpriteFrame.read_only_pixels: Sequence[tuple[int, ...]]` (properties);
  - `SpriteFrame.is_sharing: bool` (property).
  - `AnimatedSprite.load_text(self, *, text, source_name)` keeps its signature, and so do `__init__` and `load`.

- [ ] **Step 1: Write the failing tests.**
  - In `TestSpriteFrame`:
    - `test_a_sharing_frame_copies_its_surface_on_first_read`: two frames sharing one template; reading `image` on one returns a surface that is not the template's, equal in pixels; the other still `is_sharing`; a second read returns the same copy.
    - `test_drawing_on_a_read_image_reaches_only_that_frame`, parametrized over `set_colorkey`, `fill`, `pygame.draw.rect` and `PixelArray`: the template's surface bytes are unchanged afterwards.
    - `test_a_sharing_frame_copies_its_pixels_on_first_read`: `pixels` returns a `list` equal to the tuple; `pixels[0] = (1, 2, 3)` leaves the template unchanged.
    - `test_read_only_accessors_never_copy`: after reading them, the frame still `is_sharing`.
    - `test_assigning_a_sharing_frames_image_changes_only_it`.
  - In `test_animated_sprite.py`, class `TestSharedFrames`:
    - `test_two_sprites_from_one_file_share_their_surfaces_and_pixels`: each sprite's frames are its own objects, and their `read_only_image` and `read_only_pixels` are the same objects across both.
    - `test_a_second_load_compiles_nothing`: `mocker.spy` on `compile_sprite_text`; one call for two loads, and one cache entry.
    - `test_cached_and_uncached_loads_agree_for_every_shipped_sprite`: the conservation property, parametrized over every `.toml` under `src/**/resources/sprites/`. Every field of Decision 2 is compared by value, plus each frame's pixels and surface bytes, between a cached load and `_load_text_uncached` on a fresh sprite.
    - `test_a_played_sprite_stays_shared`: two sprites from one animated file, in a `LayeredDirty` group, each `update(dt=...)` for 60 frames through every animation, drawn to a surface each frame, `hitbox` read each frame. Afterwards every frame of both still `is_sharing` (Review Focus 1).
    - `test_a_sprite_changing_its_hitbox_changes_no_other` (Review Focus 2).
    - `test_each_sprite_keeps_its_own_playback`: two sprites set to different animations draw different frames.
    - `test_a_cached_load_logs_no_repair_warning_but_keeps_the_repairs`: `caplog` at WARNING, with the repaired TOML of `test_repairs_are_logged_once_per_block`.
    - `test_a_text_that_fails_is_not_kept`: an invalid sprite raises on both loads, and the cache stays empty.
    - `test_papyrus_style_preparation_leaves_other_sprites_unchanged`: one sprite runs `prepare_papyrus_sprite`'s steps (`set_colorkey` on `frame.image`, then assigns a converted surface) on every frame; a second sprite from the same file still `is_sharing`, and its surfaces' bytes are unchanged. Written with the steps inline: an engine test must not import a member.
- [ ] **Step 2:** Run `uv run pytest tests/sprites -q --dummy-only --no-cov -k "Shared or sharing or read_only or papyrus"`. Expected: FAIL (`sharing`, `is_sharing` and `compile_sprite_text` don't exist).
- [ ] **Step 3:** Implement `SpriteFrame` per Decisions 4 to 6. The frame keeps its compile's surface and pixels until the first public read. `opaque_bounds`, `get_size`, `get_alpha`, `get_colorkey` and `hitbox` keep using the current surface without copying.
- [ ] **Step 4:** Implement `compile_sprite_text` (Decision 3) and the cached `load_text`:
  1. `key = sprite_key(...)`;
  2. `compiled = ENGINE_SPRITE_CACHE.compiled(key=key) or ENGINE_SPRITE_CACHE.keep(key=key, compiled=compile_sprite_text(...))`;
  3. apply it per Decision 4;
  4. rebuild `state_machine` from `transition_data` as `_load_text_uncached` does;
  5. then the same initial-animation and first-surface steps.
- [ ] **Step 5:** Move the engine reads of Decision 6 to the read-only accessors.
- [ ] **Step 6:** Run `uv run pytest tests/sprites -q --dummy-only --no-cov`. Expected: PASS. Then the whole suite, `uv run pytest --dummy-only -q --no-cov`. A failure is either a test relying on loads not sharing (fix the test to the new contract, saying why) or a real finding (report it before changing anything).
- [ ] **Step 7:** Commit: "Sprites: sprites loaded from one text share its frames, copied on write".

### Task 4: Drawn surfaces come from the compile

**Files:**
- Modify: `src/glitchygames/sprites/animated.py` (`_get_current_surface`)
- Test: `tests/sprites/test_animated_sprite.py` `TestSharedFrames`

- [ ] **Step 1: Write the failing tests:**
  - `test_shared_sprites_draw_the_same_native_surface`: at scale 1, `drawn_frame_surface()` is the same object for two sprites.
  - `test_a_scaled_sprite_draws_its_own_size_beside_a_native_one` (Review Focus 3).
  - `test_a_sprite_whose_pixels_were_edited_draws_its_own`: after `frame.pixels[0] = ...` and `clear_surface_cache()`, its drawn surface differs from the other sprite's, which is unchanged.
  - `test_new_text_at_the_same_path_loads_the_new_pixels` (Review Focus 5).
- [ ] **Step 2:** Run them. Expected: FAIL on the identity assertion.
- [ ] **Step 3:** In `_get_current_surface`, a frame that `is_sharing`, at scale 1, returns the compile's `drawn_surfaces[(animation, frame)]`. Above scale 1, that surface is scaled into the sprite's own `_surface_cache`. A frame no longer sharing is drawn as today.
- [ ] **Step 4:** Run `uv run pytest tests/sprites tests/world -q --dummy-only --no-cov`. Expected: PASS. Golden replays are unchanged, so their tests pass with no re-recording.
- [ ] **Step 5:** Commit: "Sprites: shared sprites draw the compile's surfaces".

### Task 5: Bitmappy edits copies, and nothing else changes

**Files:**
- Test: `src/apps/bitmappy/tests/` (the canvas's existing load test file)
- Modify: nothing, unless the tests find otherwise

- [ ] **Step 1: Write the test** `test_the_editor_edits_a_copy_of_a_sprite_a_game_loaded` (Review Focus 4): load a shipped sprite as a game would, open the same file in the canvas, change a pixel through the canvas's edit path, and assert that the game sprite's frames still `is_sharing` with unchanged bytes.
- [ ] **Step 2:** Run it, along with Bitmappy's whole suite: `uv run pytest src/apps/bitmappy/tests -q --dummy-only --no-cov`. Expected: PASS without changes. A failure is a Bitmappy path writing through something other than `image`/`pixels`; report it and fix it at the frame, not in Bitmappy.
- [ ] **Step 3:** Commit: "Tests: Bitmappy edits copies of frames a game shares".

### Task 6: Measure, document, gate

**Files:**
- Modify: `CLAUDE.md` (Sprites, animation and collision: one line on shared frames, copied on first read of `image`/`pixels`, and the engine's `read_only_*` accessors), `docs/architecture/` (the sprite page that describes loading, found with `grep -rl "load_sprite" docs/architecture`), `bugs/2026-11-18-sprite-frames-held-a-tuple-per-pixel.md` (the sprite-file-cache sibling marked fixed, with the measurement)

- [ ] **Step 1:** Measure the zombies pair case on the stacked code. Bring the zombies game in the same way as before, by applying the branch's diff in a worktree carrying #215, and run `uv run python -m scripts.memory_triage per-test "<the case>"`. Expected: a peak below the 683 MiB measured after the tuple fix. Record the number.
- [ ] **Step 2:** Write the docs lines and the bug record update.
- [ ] **Step 3:** Run the whole gate: `uv run nox -s lint static-analysis`, then `uv run pytest`, which includes the native-driver comparison. Expected: all pass, coverage 100%.
- [ ] **Step 4:** Commit: "Docs: shared sprite frames", and add the execution record to this plan.
