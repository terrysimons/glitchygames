# Bug Tracking for GlitchyGames

This document tracks bugs reported during development. Bugs are listed in order of discovery and will be investigated and fixed as time allows.

## Active Bugs

### 224. Smaller Findings From the Workspace Packages Part 1 Reviews
- **Description**: The task reviews and the final whole-branch review of workspace packages Part 1 (plans/2026-10-24-workspace-packages-1-foundation.md, 2026-10-25) recorded these minor findings; the final reviewer triaged them and none blocks the merge. The critical and important findings were fixed on the branch. Before Part 2 adds more members, item 31 (members' test helper modules colliding by basename) should be settled
- **Status**: Active
- **Priority**: Low
- **Reporter**: The task reviews and the final review of workspace packages Part 1
- **Date Reported**: 2026-10-25
- **Details** (task numbers are Part 1's):
  1. Task 1: BUGS.md:409 still names tests/conftest.py in a present-tense sentence (other BUGS.md mentions are history)
  2. Task 1: tests/collision/test_ball_visible_walls.py:4-5 comment says the harness mocks drawing for game_objects paths (BUGS.md:523 says that mocking is gone)
  3. Task 1: tests/display_canvas.py:1 docstring says "a helper for conftest and tests"
  4. Task 1: tests/test_suite_collection.py:523 imports the root conftest as `conftest` inside the test (works under the current import mode)
  5. Task 2: tests/scenes/test_scene.py:118 comparison operands reversed from the brief (cosmetic)
  6. Task 3: bare KeyError when a member's pyproject lacks [project] or name (no member named)
  7. Task 3: test_the_real_repository_is_readable only checks index 0 (passes with no members)
  8. Task 3: "has no pyproject.toml" message also covers a missing member directory
  9. Task 3: WorkspaceMember's before-validator assumes dict input (model_validate of an existing member would raise AttributeError; unused today)
  10. Task 3: `packages` itself is not validated as a list of strings (a bare string fails later as FileNotFoundError, not silently)
  11. Task 4: test_every_pump_seam_still_reads_the_queue walks only the engine package (correct: seams are engine files) without a comment saying so
  12. Task 4: the member test's tmp `glitchygames` directory is uncommented
  13. Task 4: scanned_source_files keys engine files by comparing to `project_root / ENGINE_PACKAGE` verbatim (a differently resolved path would give glitchygames/... keys; allowlists would fail loudly)
  14. Task 4: the randomness member test calls unseeded_randomness twice per file (filter, then value)
  15. Task 5: class-or-instance normalisation written two ways in game_engine.py (:855/:1271 vs :980/:1236)
  16. Task 5: instant_replay.py:208 writes the literal 'game' instead of a shared constant
  17. Task 5: game_class annotated type[Scene] while tests pass plain type stand-ins
  18. Task 6: test_recording_report asserts the oldest run's commit is unknown (true for the committed fixtures, implicit); it reads REPO_FIXTURE twice
  19. Task 7: 11 test modules repeat ENGINE_PACKAGE_DIRECTORY = imported_engine_directory()
  20. Task 7: generate_complexity_graphs crashes with a raw FileNotFoundError when the ranked package and HEAD disagree
  21. Task 7b: _git_succeeds repeats run_git's run_command call
  22. Task 7b: one merge-base per history row per recording (no per-commit cache)
  23. Task 7b: "no history rows written" line printed even when no recording has history runs
  24. Task 7b: the staging list can hold a path twice (harmless for git add)
  25. Task 8: bare asserts do not name the tool; a KeyError/ValueError says nothing of which tool is wrong
  26. Task 8: test_lint_and_type_checks_cover_every_member covers six tools in one test (first miss hides the rest)
  27. Task 8: roots.index('tests') assumes the tests environment exists
  28. Task 8: nox _install_from_lockfile and .envrc --all-packages have no check here (Task 9's test_ci_config covers the reinstall)
  29. Task 8: parse_jsonc annotated -> dict[str, Any] though json.loads may return any JSON type
  30. Task 9: ruff namespace-packages for src/games/mr-muncher/tests also covers its subdirectories (fits the design; judged acceptable)
  31. Task 9: member test roots import by basename, so two members' non-test helper modules (helpers.py) would collide unnoticed; the uniqueness check covers only test_*.py; consider per-member test package names or --import-mode=importlib
  32. Task 9: noxfile._SOURCE_PACKAGE_DIRS check is a subset check (a stale extra entry passes); the noxfile could read members with tomllib instead of static lists
  33. Task 9: member goldens enumerated in three places (REPLAY_FIXTURES, golden_replay_globs, REPLAY_FIXTURE_DIRECTORIES)
  34. Task 9: ReplayItem.runtest recomputes the console script collect already has
  35. Task 9: nothing checks mr_muncher is imported from its installed distribution (defensive only)
  36. Task 9: the unique-names check matches only test_*.py, not *_test.py (python_files allows both)
  37. Task 10: member_package_directory's LookupError path untested
  38. Task 10: test_the_engine_archive_no_longer_holds_the_moved_game checks only examples/mr_muncher
  39. Task 10: write_bundle's report line counts only engine files
  40. Task 11: CLAUDE.md:164-165 wrote the games' directory without the leading src/ where README wrote it with it (package-relative convention); resolved by the src-layout docs scrub, which writes every repository path in full
  41. Task 11: browser/index.html:3 and browser/touch_controls.js:3 comments start with a bare command
  42. Task 11: CLAUDE.md:920 phrasing of TOUCH_LAYOUTS
  43. Task 11: browser/boot.py:3-4 says the page unpacks the engine only
  44. Task 11: docs/games/mr_muncher.md:763 "Both test files" without noting they are in the member
  45. Final: src/games/mr-muncher/pyproject.toml depends on glitchygames with no version floor
  46. Final: find_scene_class's "no scene class named X is loaded" warning misleads when the class is loaded but its module or logical name differs
  47. Final: nox test session writes src/glitchygames/_build_info.json for its duration (race with concurrent build sessions)
  48. Browser test (the owner): every page requests /favicon.ico and gets a 404 (no tab icon in the bundle)
- **Files**: see each item

### 222. Scripts and Tests Insert the Repository Root Into sys.path, Which Does Nothing Since the Engine Moved
- **Description**: Many scripts and tests start with `sys.path.insert(0, str(Path(__file__).parent.parent))` (or `.parent.parent.parent`) "so direct imports work". Since the engine moved to `src/glitchygames`, the repository root holds no importable `glitchygames`: the imports resolve to the installed package either way, so the lines do nothing (the root still serves `scripts.*`, but a script reaches that as `python -m scripts.<name>`). They also hide a mistake: a test that needed the root would pass here and fail elsewhere
- **Status**: Active
- **Priority**: Low
- **Reporter**: The documentation task of plans/2026-10-24-workspace-packages-1-foundation.md
- **Date Reported**: 2026-10-25
- **Files**: `scripts/ai_query_inspector.py`, `scripts/animation_demo.py`, `scripts/animation_scene_demo.py`, `scripts/animation_scene_full_demo.py`, `scripts/show_ai_query.py`, and under `tests/` `animation/`, `canvas/`, `engine/`, `events/` and others (`git grep -n 'sys.path.insert' -- scripts tests`)
- **Solution**: Remove the lines (and their comments), then run the suite; where a script needs `scripts.*`, run it as a module

### 221. tests/test_logging.py Inserts a Path That Never Existed Into sys.path
- **Description**: `tests/test_logging.py:13` runs `sys.path.insert(0, str(Path(__file__).parent / 'glitchygames'))`, which is `tests/glitchygames`, a directory that has never existed. Dead code (and, were a `tests/glitchygames` ever created, it would shadow the engine)
- **Status**: Active
- **Priority**: Low
- **Reporter**: The documentation task of plans/2026-10-24-workspace-packages-1-foundation.md
- **Date Reported**: 2026-10-25
- **Files**: `tests/test_logging.py`
- **Solution**: Delete the line and the `sys`/`Path` imports if nothing else uses them

### 220. Smaller Findings From the Measured-Rows Review
- **Description**: A fresh review of the measured-rows-in-the-repository branch (2026-10-25) found these; none breaks publishing on main as merges are made today (squash, up to date, the hook installed). Its critical and important findings were fixed on the branch: code that arrived by a merge is measured by the next commit, rows of a refused commit are staged on the retry, partial commits and untracked measured files are refused, deploys only from main, the hooks installed by `.envrc`
- **Status**: Active
- **Priority**: Low
- **Reporter**: The final review of plans/2026-10-25-measured-rows-in-the-repository.md
- **Date Reported**: 2026-10-25
- **Details**:
  1. `src/glitchygames/code_tree.py` `landed_code_trees` runs three git commands over a full temporary index per row-adding commit on every docs build (each `mkdocs serve` rebuild too), uncached: 0.36 s now, seconds after hundreds of merges. A cache keyed by commit (the answer never changes) would fix it
  2. A local build plots a branch's unlanded rows under their parent commit (their `source_revision`), next to the parent's own rows, not labelled as unlanded
  3. Code reverted to an earlier tree takes the earliest commit that tree landed in, with that commit's old date
  4. Merge commits instead of squash merges would publish a branch's intermediate commits' rows (`git log --diff-filter=A` follows one parent): squash-only merging is assumed, not documented as required
  5. `MEASURED_PATHS` misses inputs outside it (a Python version pinned elsewhere; `scripts/replay_metrics.py`'s own measuring logic)
  6. Fixed 2026-10-25 (Task 7b): the hook wrote a recording's earlier header runs as `history-…` row files (no code tree, so always published, even a run of code that never landed) and left them untracked, and a moved recording's earlier runs were written again under its new path. Now only runs measured on a commit on `origin/main` without uncommitted changes are written (none without an `origin/main`), the hook stages every file its measurement wrote, and "already held" resolves `RECORDING_PATH_RENAMES`
  7. `uv run` inside the hook may rewrite a stale `uv.lock`, and the framework then fails the hook for modifying files
  8. CircleCI's checkout is a full clone today; a shallow checkout would silently publish fewer landed rows (`git log` sees fewer commits)
- **Files**: `src/glitchygames/code_tree.py`, `src/glitchygames/recording_metrics.py`, `scripts/measure_staged_replays.py`

### 110. Smaller Findings From the Coverage Push
- **Description**: Small inconsistencies the coverage tests found, none breaking a feature on its own
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests; not fixed)
- **Date Reported**: 2026-10-21
- **Details**: Fixed 2026-10-21: items 3 (typed text on the hex tab is read as hex), 4 (one loop refreshes R, G, B and alpha), 5 (`tts.say` runs through `run_command` with a 30 s timeout), 6 (preset SDL drivers kept, pygame re-initialized after `pygame.quit()`, the frame manager always restored), 7 (pixel blocks written without their trailing newline, so a rewrite is identical), 9 (the animation tests render to a real display and check its pixels), 1 (load errors go to `parent_scene.debug_text`, where a successful load writes, and are shown) and 2 (the class-wide `WIDTH`/`HEIGHT` writes are gone: nothing read them). Kept for the record: (3) `slider_manager.py:807` and `ui/sliders.py:322` read typed text as hex only when it contains a-f, even on the hex tab ("10" is 10, not 16). (4) `slider_manager.py:701-735` refreshes only the R, G and B text formats on a tab change, not alpha. (5) `audio/tts.py:92` calls `subprocess.run` directly instead of `glitchygames.process.run_command`, the engine's one launcher. (6) `services/renderer_service.py:101-102` always overwrites `SDL_VIDEODRIVER`/`SDL_AUDIODRIVER`; its `pygame_initialized` class flag never resets after `pygame.quit()`; `:415-418` leaves the frame manager on the last rendered frame when its starting animation is None. (7) `ai_manager.py:588-590`/`616-620`: each TOML rewrite adds a blank line to every pixel block (tomllib keeps the trailing newline; loading ignores it). (8) No production callers: `visual_indicators._update_slider_indicator` and `_draw_visual_indicator`, the `animated_canvas` panning helpers, `_convert_static_to_animated`, `_mark_film_strips_dirty`, `_clear_existing_film_strips`, `adaptive_clamping.get_statistical_aggregates`. (9) `tests/animation/test_animation_hardware.py`'s 9 "hardware" tests read the shared mocked display, whose `get_at` answers black for every pixel: they check no real rendering, whatever their names say. (10) Unreachable code the tests could not reach is listed in each agent's notes: e.g. `film_strip_operations.py:324-328`/`388-391`, `modes.py:146`/`367`/`373`, `sprite_generation_service.py:176-181`. Also: a joystick in film strip mode always reads R2 as pressed because of #67, so its triggers never switch modes
- **Files**: see Details

### 111. The Default Palette's Names Do Not Match Their Colors
- **Description**: In the `Default` palette (`color/palette.py:200-210`, exported by `color/constants.py`), YELLOW is (128, 128, 0) (olive), GREEN is (0, 255, 255) (cyan) and BLACK has alpha 0
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found fixing #102
- **Date Reported**: 2026-10-21
- **Details**: Deferred by choice: fixing the names or the values changes colours the games draw, so it needs its own review of every user of these constants
- **Files**: `src/glitchygames/color/palette.py:200-210`, `src/glitchygames/color/constants.py`

### 113. The Health Route Reports a Stale "pygame initialized" Flag
- **Description**: `api/routes/health.py:26` reports `RendererService.pygame_initialized`, which stays True after `pygame.quit()` until the next `RendererService()` is made
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found fixing #110 item 6
- **Date Reported**: 2026-10-21
- **Files**: `src/glitchygames/api/routes/health.py:26`, `src/glitchygames/services/renderer_service.py`

### 115. A Scene's AnimatedSprites Advance a Fixed 16 ms per Rendered Frame (Suspected)
- **Description**: `Scene.update()` (`scenes/scene.py:2968-2978`) calls `sprite.update()` without a dt, and `AnimatedSprite.update(dt=0.016)` defaults it, so a plain `AnimatedSprite` in a scene's group animates by frames rendered, not by time: slower than real time below 62.5 FPS, faster above it
- **Status**: Active
- **Priority**: Medium
- **Reporter**: Found rewriting the animation hardware tests
- **Date Reported**: 2026-10-21
- **Details**: The example games avoid it by animating in `dt_tick` and making `update()` a no-op (`src/glitchygames/examples/brave_adventurer_papyrus/enemies.py:86`). A fix changes animation timing in games and recordings, so it needs the golden replays checked
- **Files**: `src/glitchygames/scenes/scene.py:2968-2978`, `src/glitchygames/sprites/animated.py:2520`

### 119. Frames Inserted or Removed Through the Film Strip Never Reach the Coordinator
- **Description**: `film_strip_events.py:746`, `:993` and `film_strip_sprite.py:806` check `hasattr(parent_scene, 'on_frame_inserted' / 'on_frame_removed')`, which only `FilmStripCoordinator` has, so the editor's `selected_frame` is never adjusted after frames are inserted or removed through the film strip
- **Status**: Active
- **Priority**: Medium
- **Reporter**: Found fixing #90 (same pattern)
- **Date Reported**: 2026-10-21
- **Files**: `src/glitchygames/bitmappy/film_strip_events.py:746`, `:993`, `src/glitchygames/bitmappy/film_strip_sprite.py:806`

### 120. A Canvas Drag Released Outside the Canvas Is Never Finished
- **Description**: `editor.py:701-704` sends the left-button-up only to sprites under the mouse, so a drag released outside the canvas never flushes or submits its stroke to undo, and `_drag_active` stays True
- **Status**: Active
- **Priority**: Medium
- **Reporter**: Found fixing #101
- **Date Reported**: 2026-10-21
- **Files**: `src/glitchygames/bitmappy/editor.py:701-704`, `src/glitchygames/bitmappy/animated_canvas.py`

### 134. A HashableEvent's Own Hash Shows Up as One of Its Attributes
- **Description**: `HashableEvent` stores its hash in `__dict__` (`_HashableEvent__hash`), so `len()`, iteration, `keys()` and `repr` include it: `len(HashableEvent(KEYDOWN, key=1)) == 3`
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found by the 100% coverage audit
- **Date Reported**: 2026-10-22
- **Files**: `src/glitchygames/events/base.py:339`

### 135. Dialog Scenes Ignore Their `groups` Argument
- **Description**: `NewCanvasDialogScene`, `LoadDialogScene` and `SaveDialogScene` always pass a new `LayeredDirty()`
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found by the 100% coverage audit
- **Date Reported**: 2026-10-22
- **Files**: `src/glitchygames/ui/dialogs.py` 344-346, 394-397, 446-449

### 137. Frame Extraction Reports Non-PNG Data as a Success With 0 Frames
- **Description**: `/sprites/extract-frames` returns `success=True` with no frames for arbitrary bytes, because `APNG.from_bytes` accepts garbage
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found by the 100% coverage audit
- **Date Reported**: 2026-10-22
- **Files**: `src/glitchygames/api/routes/sprites.py`

### 138. Smaller Findings From the 100% Coverage Audit
- **Description**: Inconsistencies none of which breaks a feature
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found by the 100% coverage audit
- **Date Reported**: 2026-10-22
- **Details**: (1) `replay/driver.py` `_recorded_start` (958-966): a bad or missing `recorded_at` is refused with the right exit code but without the "The recording is malformed" prefix other header refusals use. (2) `scenes/scene.py` ~2593-2597: a scene with a `VERSION` but no `NAME` gets the caption `' v2.1'`. (3) `scenes/scene.py` 1930-1935: an exception between `push_scoped_sources` and setting `_playback_session` would leave the scoped doors pushed (only `take_redelivered_events()` runs there today). (4) `SlideTransition` with an unknown direction draws nothing while `WipeTransition` reveals the new scene; neither validates `direction` (tests pin current behaviour). (5) Resolved: the unreachable freetype fallbacks in `fonts/font_manager.py` were removed. (6) `AnimatedCanvasSprite.previous_animation` into an animation with no frames leaves the canvas but switches the film strip to it. (7) Resolved 2026-10-22: the dead code the audit found was deleted (#146, #147, #148, `animated.py` and `editor.deflate`), apart from `_create_surface_from_toml_pixels`, now the live frame builder (#133)
- **Files**: see Details

### 141. A Third Controller on a Cached Indicator Position Lands on the First
- **Description**: `VisualCollisionManager.position_cache` is keyed by position only, so a third controller at a position cached for two gets the fallback offset (0, 0), on top of the first controller
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found by the coverage audit follow-ups
- **Date Reported**: 2026-10-22
- **Details**: Pinned by the strict xfail `tests/tools/test_visual_collision.py::TestCachedOffsetsForAGrowingGroup`
- **Files**: `src/glitchygames/bitmappy/indicators/collision.py`

### 144. An AnimatedSprite's Rect Comes From the Unscaled Frame Surface
- **Description**: `_update_surface_and_mark_dirty` sets `rect` from the 1x cached frame surface; a game that scales `sprite.image` itself (Papyrus) gets the right size back only because `apply_transparency_and_scale` runs straight after. Latent
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found by the coverage audit follow-ups
- **Date Reported**: 2026-10-22
- **Files**: `src/glitchygames/sprites/animated.py`

### 151. Frame Paste Undoes Out of Order With Paint
- **Description**: Frame paste goes on the global undo stack while paint goes on per-frame stacks; `handle_undo` tries the frame stack first, so after paint then paste, Ctrl+Z undoes the paint before the paste
- **Status**: Active
- **Priority**: Medium
- **Reporter**: Found by the dead-code audit follow-ups
- **Date Reported**: 2026-10-22
- **Files**: `src/glitchygames/bitmappy/history/undo_redo.py`

### 152. Redo Pressed Mid-Pan Applies Inside the Gesture
- **Description**: Ctrl+Shift+Z while an arrow is still held applies the redo inside a pan gesture; undoing the gesture still restores its starting pixels, but the redo stack is not cleared until the gesture ends
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found by the dead-code audit follow-ups
- **Date Reported**: 2026-10-22
- **Files**: `src/glitchygames/bitmappy/editor.py` (`handle_undo`/`handle_redo`)

### 153. Controllers Cannot Adjust Alpha
- **Description**: There is no alpha slider mode: `is_any_controller_in_slider_mode`, slider navigation and the indicators know only R, G and B
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found by the dead-code audit follow-ups
- **Date Reported**: 2026-10-22
- **Files**: `src/glitchygames/bitmappy/controllers/`

### 154. Film Strip Triangles May Lag a Moving Controller
- **Description**: A film strip sprite re-renders only when dirty; `render_visual_indicators` updates selections every frame, but nothing confirms a controller moving between frames always marks the strip dirty (unchecked)
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found by the dead-code audit follow-ups
- **Date Reported**: 2026-10-22
- **Details**: Suspected; needs a real-editor test
- **Files**: `src/glitchygames/bitmappy/film_strip_rendering.py`

### 155. Smaller Slider Findings
- **Description**: Deferred improvements and minor findings from the slider work
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found by the dead-code audit follow-ups
- **Date Reported**: 2026-10-22
- **Details**: (1) Slider gradients are redrawn every frame (dirty 2, ~1024 line draws): pre-render once. (2) TabControlSprite rebuilds its font every update after its first click. (3) A channel enum instead of strings. (4) Tidy-ups: `trigger.value` mutation in `on_slider_event`, the try/except and hasattr in `get_current_color`, DEBUG f-strings, `MIN/MAX_COLOR_VALUE` vs `MAX_COLOR_CHANNEL_VALUE`. (5) Controller line painting leaves the cursor one past the last painted pixel (maybe intended; pinned). (6) `AnimatedCanvasSprite.active_color` is inferred as a literal tuple (an `assignment` ignore remains in `apply_color`)
- **Files**: see Details

### 161. Middle and Right Mouse Drags Never Reach a Scene
- **Description**: The mouse event proxy calls the game's `on_middle_mouse_drag_down_event` / `on_right_mouse_drag_down_event`, which a Scene does not have (it has `on_middle_mouse_drag_event` / `on_right_mouse_drag_event`), so through the engine these drags become missing events and never reach a scene or its sprites
- **Status**: Active
- **Priority**: Medium
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Details**: Pinned: `tests/events/test_mouse_events.py::TestMouseEventProxyDragEvent::test_middle_and_right_drags_reach_a_plain_scenes_drag_handler`. Related, latent: the proxy's drop handlers call `on_*_mouse_drag_up_event` instead of `on_*_mouse_drop_event` (pinned: `TestMouseEventProxyDropEvent`). Possibly intended: buttons 4/5 map to scroll down/up
- **Files**: `src/glitchygames/events/mouse.py`

### 162. Editing Text Shows a Box in the Inactive Colour
- **Description**: `TextSprite.update_text` renders the text with `background_color` but fills the image with the editing grey (50, 50, 50), so an inactive-colour box surrounds the text while editing (the black box in a slider's value field)
- **Status**: Active
- **Priority**: Medium
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Details**: Pinned: `tests/ui/test_ui_text_cursor.py::test_active_text_is_drawn_on_the_editing_background`
- **Files**: `src/glitchygames/ui/text_widgets.py`

### 163. MultiLineTextBox Puts the Cursor in the Wrong Place After a Wrap
- **Description**: `_map_cursor_pos_to_wrapped_text` finds the Nth occurrence of the character under the cursor, but wrapping turned some spaces into newlines, so a cursor on a space after the first wrap maps to a later space or the end (19 wrong positions in the test text); affects where the cursor is drawn and up/down
- **Status**: Active
- **Priority**: Medium
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Details**: Pinned: `tests/ui/test_ui_text_cursor_wrapping.py::test_cursor_on_a_space_after_a_wrap_is_on_its_own_line_and_column`
- **Files**: `src/glitchygames/ui/text_widgets.py`

### 164. Widgets Away From the Origin Draw at Their Screen Position on Their Own Image
- **Description**: MenuBar draws its background, border and focus outline at `self.rect` (screen coordinates) on its own image, leaving a transparent strip when it is not at (0, 0); TextBoxSprite draws its text the same way, so a text box away from (0, 0) shows no text and keeps stale pixels (the InputDialog prompt)
- **Status**: Active
- **Priority**: Medium
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Details**: Pinned: `test_ui_menubar.py::test_menubar_not_at_the_origin_draws_its_whole_background`, `test_widgets.py::test_menubar_away_from_the_origin_draws_its_background_on_all_of_itself`, `test_widgets.py::test_text_box_away_from_the_origin_shows_its_text`
- **Files**: `src/glitchygames/ui/menus.py`, `src/glitchygames/ui/text_widgets.py`

### 165. Smaller UI Bugs the Real Display Found
- **Description**: Bugs pinned by strict xfails in tests/ui
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Details**: (1) A pressed ButtonSprite looks like a released one (its `background_color` is never drawn): `test_pressed_button_is_drawn_in_its_active_color`. (2) CheckboxSprite never runs its click callback (no user in the code base): `test_checkbox_click_runs_its_callback`. (3) `MenuItem.add_menu` puts the first sub-item at y=40, below the dropped-down image, not y=20: `test_add_menu_puts_the_first_sub_item_right_below_the_item`. (4) After a paste the MultiLineTextBox cursor is past the end of the text: `test_handle_paste_leaves_the_cursor_after_the_pasted_text`. (5) Click-to-cursor measures characters by ink width, not advance, drifting 1-2 px per character: `test_mouse_down_in_the_middle_of_a_character_puts_the_cursor_before_it`. (6) InputBox types Escape's character into Save/Load/New file names (unconfirmed against a real key press): `test_dialogs.py::TestInputConfirmationDialogScene::test_escape_key_down_types_nothing`. Not pinned: MenuBar mouse-up calls items' down handlers; a focused MenuBar's outline equals its border; constructor text is never wrapped; freetype line height 14 vs a 20 px cursor; `_render_with_pygame_font` renders twice; InputBox parent-offset code is dead and its initial text colour differs from render()'s
- **Files**: see Details

### 166. Changing a Scene's Background Colour Leaves Stale Pixels
- **Description**: Setting `Scene.background_color` after the scene has rendered repaints only the areas sprites dirty; the rest of the display keeps the old colour
- **Status**: Active
- **Priority**: Medium
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Details**: Pinned: `tests/scenes/test_scene_rendering.py::TestSceneRenderingEdgeCases::test_scene_rendering_with_render_state_changes_manager`. (The screenshot half, black on displays with per-pixel alpha, was #142, resolved)
- **Files**: `src/glitchygames/scenes/scene.py`

### 168. Clicking a Film Strip's Empty Area Does Nothing in the Editor
- **Description**: `FilmStripEventHandler.handle_click` (the parent-strip path) tests the strip-local click position against the widget's screen rect; strips sit right of the canvas (x=350), so the click never matches
- **Status**: Active
- **Priority**: Medium
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Details**: Pinned: `test_film_strip_selection.py::test_parent_strip_click_selects_itself`, `test_clicking_a_strips_empty_area_on_screen_selects_that_strip`
- **Files**: `src/glitchygames/bitmappy/film_strip_events.py`

### 170. The Film Strip Scroll Offset Goes Stale After Deleting an Animation
- **Description**: The recomputation lives in `_handle_no_remaining_animations`, which `_delete_animation` never calls; deleting strip_3 of 3 leaves offset 1 with strip_1 selected but scrolled out of view (the old tests passed only because `on_sprite_loaded` was a Mock)
- **Status**: Active
- **Priority**: Medium
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Details**: Pinned: `test_delete_animation_scroll_offset_calculation`, `..._last_strip`, `..._many_strips`. Not pinned: `switch_to_film_strip` sets the strip's `current_frame` but not `selected_frame`; the `is_right_click` onion-skinning branch of `handle_click` cannot be reached from FilmStripSprite (right-clicks sample colour first), although CLAUDE.md says right-clicking frames toggles onion skinning
- **Files**: `src/glitchygames/bitmappy/film_strip_coordinator.py`

### 171. Frame TOML With More Than 64 Colours Is Invalid
- **Description**: `AIManager._generate_frame_toml_content(force_single_char_glyphs=False)` with more than 64 colours makes several colours share a glyph and writes one `[colors."<glyph>"]` table per colour, declaring the same table twice. Latent: the only production caller passes True
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Details**: Pinned: `test_bitmappy_png_loading.py::TestColorQuantization::test_generate_frame_toml_without_quantization_many_colours_is_valid_toml`. Also: integer-packed pixels make it log an exception and return '' (pinned as current behaviour; decide whether packed pixels should be supported)
- **Files**: `src/glitchygames/bitmappy/ai_manager.py`

### 172. The Ball Draws a Fixed 10 px Circle Whatever Its Size
- **Description**: `BallSprite.color` draws `pygame.draw.circle(..., 5, 0)`: a radius-5 circle centred in the image whatever the ball's width and height (20x20 by default), so the visible ball and its visible-pixel hitbox are 10x10 inside a 20x20 rect
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Details**: Unchanged since the ball was written (4d1863ea); every recording and golden trace was made with it, so changing it changes PaddleSlap's physics and needs reviewed new baselines. The ball physics tests had assumed the whole 20x20 image was visible, which was true only under the mocks
- **Files**: `src/glitchygames/game_objects/ball.py:514`

### 173. Smaller Findings From the Real-Display Migration
- **Description**: Minor findings, none breaking a feature
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Details**: (1) `FontManager` stores `font_bold`/`font_italic` but never uses them. (2) `src/glitchygames/examples/paddleslap.py` TextSprite/TextBox (~157-196) are never constructed and broken (`FontManager()` without a game raises; a bound method passed as a font name). (3) `src/glitchygames/examples/dt_demo.py` asks for Calibri (SysFont). (4) `--windowed` defaults to True with no way to turn it off, and `args()` compares `platform.system()` with 'MacOS' (it is 'Darwin'); see #76. (5) `BitmappySprite.__init__` discards its `convert()` result (as #143). (6) Tests that test nothing in production, kept and listed for review: inline-logic tests in `test_pixel_saving.py`, mock-only scroll tests in `test_multi_controller_color_assignment.py`, `test_description_loading_from_toml`, protocol/`hasattr` tests in `test_canvas.py`, `test_clipboard_persistence`, `test_film_strip_sprite_methods`, four ball-to-ball swap tests in `test_collision_scenarios.py`, `test_bitmappy_sprite_save_method`, five creation-only tests in `test_sprite_animation.py`, `test_animation_timing_performance`
- **Files**: see Details

### 174. Fast Balls Can Pass Through Each Other in PaddleSlap
- **Description**: Ball-to-ball collisions are checked once per frame with no check along the path between frames. Two balls closing at 10 px or more per frame (the circle's full collision distance) can go from just touching, to centres on the same pixel (where no contact direction exists and the pair is skipped), to touching on the far side, passing straight through each other. A head-on pair at 300 px/s each does it; the 500 px/s speed cap allows faster
- **Status**: Active
- **Priority**: Medium
- **Reporter**: Found moving the ball physics tests onto real pygame
- **Date Reported**: 2026-10-22
- **Details**: Pinned: `tests/game_objects/test_ball_collision_physics.py::TestBallCollisionSweepFrameAlignedMeeting::test_head_on_balls_meeting_on_a_frame_collide` (4 angles). A fix (swept collision or sub-stepping) changes PaddleSlap physics and so its golden trace and replay. Note: the moving-pair sweep's 10% velocity-swap tolerance holds only with its 2 px contact phase (the game computes contact directions from whole-pixel centres, so on a 10 px circle a pixel of rounding turns the direction by about 10 degrees)
- **Files**: `src/glitchygames/examples/paddleslap.py`, `src/glitchygames/game_objects/ball.py`

### 59. Papyrus Sprites Keep Their Unscaled Native Rect Size
- **Description**: Papyrus's TOML sprites are drawn at 2x (`SPRITE_SCALE`), but their `rect` keeps the native size: the player's rect is 20x28 while its image is 40x56, a scarab's 10x8 while its image is 20x16
- **Status**: Active (latent)
- **Priority**: Low
- **Reporter**: Found on feature/engine-world-space (Task 8)
- **Date Reported**: 2026-10-18
- **Details**: Predates the branch. Latent today: every Papyrus sprite is `dirty = 2`, the scene renders the full screen, the image overhangs the rect by at most 28 px (less than `CULL_MARGIN_PIXELS`, 32), and hitboxes and the debug overlay use collision rects. It would surface with mouse picking (`sprites_at_position`, `pygame.sprite.spritecollide`), a non-dirty Papyrus sprite, or `pygame.display.update(rects)`. Fixing it (sizing rect from the scaled image in `apply_transparency_and_scale` / `prepare_papyrus_sprite`) changes every Papyrus rect size in the golden trace, so it needs its own expected-difference class in `tests/world/test_golden_traces.py`
- **Files**: `src/glitchygames/examples/brave_adventurer_papyrus/sprite_utils.py`

### 60. Brave Adventurer Ground and Walls Stay Drawn Only Because the Parallax Layers Dirty the Screen
- **Description**: The shared `GroundSegment` and `StoneWall` (both editions) are `dirty = 1` and are dirtied again only when they move. With a still camera they stay on screen only because the full-screen `dirty = 2` ParallaxLayers make the whole screen dirty every frame
- **Status**: Active (fragile, works today)
- **Priority**: Low
- **Reporter**: Found by the Task 8 review on feature/engine-world-space
- **Date Reported**: 2026-10-18
- **Details**: If the parallax layers stop redrawing the full screen (made static, partially sized, or removed), a still camera would let other sprites' clearing erase the terrain. Either make the terrain `dirty = 2` or document the dependency where the layers are built
- **Files**: `src/glitchygames/examples/brave_adventurer/terrain.py`, `src/glitchygames/examples/brave_adventurer/game.py`, `src/glitchygames/examples/brave_adventurer_papyrus/game.py`

### 67. Bitmappy's Joystick-Event Trigger Conversion Assumes pygame 1's Integer Axis Scale
- **Description**: `ControllerEventHandler._read_joystick_trigger_values` converts trigger axes with `(raw + 32768) / 65535`, but pygame 2 reports joystick axes as -1.0..1.0, so both triggers always read about 0.5 whatever their position
- **Status**: Active (latent: only events without an `instance_id` take this path, and pygame-ce's joystick and controller events all carry one, so they go to `_read_controller_trigger_values`, which converts correctly)
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 6)
- **Date Reported**: 2026-10-19
- **Details**: Fix with the `(raw + 1.0) / 2.0` conversion the controller path uses (or drop the path if no event without an `instance_id` can reach it). `TestTriggerValuesFromSnapshot` in `tests/tools/test_bitmap_editor_scene.py` pins today's values
- **Files**: `src/glitchygames/bitmappy/controllers/event_handler.py`

### 72. MultiControllerEnhancements Stores a Duration Where Its Next Call Expects a Timestamp
- **Description**: `MultiControllerEnhancements._update_performance_metrics` stores the first reading as `performance_metrics[operation]`, then on each later call replaces it with `timestamp - performance_metrics[operation]`. From the third call on it subtracts a duration from a timestamp, so `'visual_update'` alternates between a duration and a timestamp-sized number
- **Status**: Active (diagnostic only: the value is reported by `get_controller_performance_stats` and nothing acts on it)
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 9)
- **Date Reported**: 2026-10-19
- **Details**: Keep the last reading and the last duration under separate keys (or separate dicts), so each call subtracts the previous reading. The readings come from `measured_seconds()` (real time, diagnostics only) since Task 12b
- **Files**: `src/glitchygames/bitmappy/controllers/enhancements.py`

### 73. PaddleSlap Sets the `game` Logger to INFO at Import, Overriding `--log-level`
- **Description**: `src/glitchygames/examples/paddleslap.py:46-47` calls `logging.getLogger('game').setLevel(logging.INFO)` when the module is imported (and `src/glitchygames/game_objects/paddle.py:18-19` does the same for `game.paddle`). The level set on the `game` logger wins over the root level `--log-level` configures, so `--log-level warning` or `error` still prints every `game.*` INFO line when PaddleSlap runs
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 14: the `--audit` children of the PaddleSlap golden replay printed INFO lines under `--log-level error`)
- **Date Reported**: 2026-10-19
- **Details**: Not fixed here: removing the module-level `setLevel` calls changes what PaddleSlap logs by default for other `game.*` loggers if anything else lowers the root level, and needs checking against the other examples that may do the same. `--log-level` defaults to `info`, so only runs that ask for a quieter level are affected
- **Files**: `src/glitchygames/examples/paddleslap.py`, `src/glitchygames/game_objects/paddle.py`

### 75. `pygame_needs_fastevents` Compares the Major and Minor Versions Separately
- **Description**: `pygame_needs_fastevents()` (`src/glitchygames/engine/game_engine.py`, around line 107) returns `vernum[0] < 2 and vernum[1] < 2`, so it is True only when both the major and the minor version are below 2. pygame 1.9 (major 1, minor 9) gets False and would not read events with `pygame.fastevent`, although its docstring says "True for pygame < 2.2". The intended test is `(vernum[0], vernum[1]) < (PYGAME_MIN_MAJOR_VERSION, PYGAME_MIN_MINOR_VERSION)`
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 12 review)
- **Date Reported**: 2026-10-19
- **Details**: Harmless today: the project runs on pygame-ce 2.x, where both forms give False. The existing `test_use_fastevents_with_old_pygame` mocks pygame 1.1, which both forms treat as old, so it does not catch the bug; a fix should add a 1.9 case
- **Files**: `src/glitchygames/engine/game_engine.py`

### 83. Keys a Layout Adds Without a pygame `K_*` Constant Are Not Replayed on Another Layout
- **Description**: Recordings now hold the key codes the held keys had (`held_key_codes`), so a replay on another keyboard layout answers `key_pressed(K_*)` as recorded. Only pygame's named `K_*` codes are recorded (`glitchygames.input.state.NAMED_KEY_CODES`): a key code a layout adds that pygame names no constant for (say a Unicode letter key) is never reported held in a replay, even on the recording machine
- **Status**: Active (documented limitation)
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (final review fixes, item A4)
- **Date Reported**: 2026-10-20
- **Details**: pygame exposes key code to scancode (through a ScancodeWrapper) but not scancode to key code, so the held keys can only be named by trying every known key code. Documented for game authors in `docs/architecture/gameplay_replay.md` (Polled input): handle such keys through events or by position (`scancode_pressed`, `ActionMap.bind(scancode=...)`), not by polling their key code
- **Files**: `src/glitchygames/input/state.py`

### 176. Bitmappy Accepts Canvas Widths That Leave No Room for a Pixel
- **Description**: The new-canvas dialog's width is never capped: a width over 350, or one too large for the screen, makes `new_pixel_size` 0, and the editor builds a zero-size canvas surface that can't be seen or drawn on
- **Status**: Active
- **Priority**: Medium
- **Reporter**: Found narrowing the broad try blocks (BUGS.md #19)
- **Date Reported**: 2026-10-22
- **Details**: Non-positive sizes (`0x16`, `-4x4`) are refused since #175; very large ones are not. Refuse (or cap) a size whose pixel size would be 0, with the same "Invalid dimensions" log
- **Files**: `src/glitchygames/bitmappy/editor.py:402`

### 177. The Fallback TOML Parser Crashes on Some Malformed Files
- **Description**: `parse_toml_robustly`, the regex fallback for TOML that `tomllib` rejects, raises instead of recovering: a section header under a key already holding a non-table value raises `TypeError: argument of type 'int' is not a container` (`'a = 1\na = 2\n[a.b]\nc = 1\n'`), and a section header with an unterminated quote raises `ValueError: substring not found` from `remaining.index('"', 1)` (`'x = 1\nx = 2\n["unterminated]\n'`)
- **Status**: Active
- **Priority**: Medium
- **Reporter**: Found narrowing the broad try blocks (BUGS.md #19)
- **Date Reported**: 2026-10-22
- **Details**: The fallback exists to load damaged files; it should skip a line it cannot place and log it. Related: `normalize_toml_data` copies only the top level, so it changes the caller's nested `sprite`/`animation` tables in place, and an error part way returns them half-normalized
- **Files**: `src/glitchygames/bitmappy/toml_processing.py:215`, `:219`, `:360`, `:634`

### 178. Smaller Findings From Narrowing the Try Blocks
- **Description**: Minor findings, none breaking a feature
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found narrowing the broad try blocks (BUGS.md #19)
- **Date Reported**: 2026-10-22
- **Details**: (1) `BitmappySprite.inflate` discards `image.convert()`'s result (as #143/#173.5), builds a `raw_pixels` list it never uses, and its docstring says "Raises: None" though an unknown pixel character raises KeyError. (2) The two static loaders disagree: an unknown pixel character raises KeyError through `_load_static_toml` but becomes magenta through `_inflate_toml`. (3) A static sprite's width comes from its first row: longer rows are clipped, shorter ones leave black pixels. (4) `_process_pixel_rows` writes a colour missing from the map as '.', which could collide with a real '.' glyph (unreachable today: too many colours is refused first). (5) `animated_canvas.py:1316-1332` logs one load failure three times with `log.exception`, the third adding `traceback.format_exc()` to a traceback already printed. (6) `film_strip_rendering.py:129`, `:949` create a `pygame.font.Font(None, size)` per thumbnail per draw: slow, and pygame's default font, not the bundled Vera (#156). (7) The AI worker spins logging exceptions forever if its request queue is permanently broken (`get()` always raising). (8) `_make_ai_api_call` logs every failure's traceback twice (two `log.exception` calls). (9) `_load_ai_sprite` keeps every AI response's temp file (deliberate, per its comment, for debugging): one file leaks per response. (10) `AIManager.setup` drops its two queues without `close()` when `Process.start()` fails. (11) `undo_frame`/`redo_frame` drop a command that raises from the history but put back one that returns False. (12) `InputBox` calls its parent's `on_input_box_submit_event(event=self)`, but `ui/dialogs.py:256` and `src/glitchygames/examples/text_input_demo.py:86` name the parameter `control`, so either would raise TypeError if called (latent: no InputBox has those as its parent today). (13) `src/glitchygames/examples/joystick_demo.py` (~319) built its TextSprite with `game=self`, the scene, which has no `controller_manager`, so the demo always made its own `ControllerEventManager` instead of using the engine's for hotplug events as its comment intended (fixed 2026-10-22: the demo was rewritten on `Scene.input_devices`, #185). (14) The key chord handlers are declared `keys: list[int]` (`events/input_event_interfaces.py`, `sprites/sprite.py`, `events/keyboard.py`) but receive a tuple of the held keys' KEYDOWN events (fixed 2026-10-22: they are `keys: tuple[KeyEvent, ...]`, `plans/2026-10-22-typed-events.md`). (15) The canvas's `dirty_pixels` list is set in many places but never read or cleared, and panning, frame switches, hover and onion changes don't mark it, so it can't drive a changed-pixels-only redraw (`src/glitchygames/bitmappy/`). (16) `src/glitchygames/examples/paddleslap.py` (~421) checks `hasattr(ball, '_debug_positions')` and carries `# type: ignore[attr-defined]` though `BallSprite` declares it (`ball.py:438`), typed `tuple[float, ...]` while PaddleSlap stores snapped ints. (17) `SliderSprite.update_slider_appearance` draws each column down to `self.height`, one row past the image (clipped, harmless; kept for identical pixels). (18) `Sprite.__init__` falls back to `self.name = type(self)` when no name is given, so `name` is not always a string. (19) `sprites/animated.py` (~1585) sorts a TOML animation's frames by `getattr(frame, 'frame_index', 0)`, but `SpriteFrame` has no `frame_index`, so the sort never reorders: a file's `frame_index` values are ignored and frames stay in file order. (20) `sprites/animated.py` (~2564): the frame-dump debug log's `hasattr(frame, 'surface')` is always False (`SpriteFrame` has no `surface`). (21) `bitmappy/film_strip_coordinator.py` (~1423-1428): a rename updates the strip sprite's `current_animation` only when the sprite has its own animation order, and sets the order to `[new_name]`, dropping its other animations. (22) `bitmappy/controllers/event_handler.py` (~774) and `controllers/canvas_operations.py` (~470) read `applying_undo_redo` from the controller handler, which never sets it, so those guards are always False (no visible effect today: controller undo/redo goes through `mode_switcher`). (23) `bitmappy/ai_worker.py` `_set_ollama_env_timeout` sets `OLLAMA_TIMEOUT`, which neither aisuite 0.2.0 nor openai reads, and queries the local ollama server's model status a second time. (24) `FilmStripWidget.refresh(recalculate_layout=True)` computes the layout twice (`update_layout` already calls `calculate_layout`). (25) `-v/--version` does nothing in any game (Brave editions, PaddleSlap, dt demo, Bitmappy; the joystick demo's is gone, #185): nothing reads `options['version']`. (26) Brave Adventurer binds `mic_toggle` with `controller_button=15, joystick_button=16`; in joystick mode `controller_button` maps to JOYBUTTON events, so raw joystick button 15 may open the mic too (unverified on hardware). (27) The engine logs its placeholder `NAME` at startup ("Game Title: Boilerplate Adventures", `engine/game_engine.py` ~364, 1272, 1389) before the scene sets the real caption. (28) `Scene._handle_scene_key_events` sets the scene's `quit_requested` on K_q, which nothing reads (only the SceneManager's is read). (29) PaddleSlap's `Game.__init__(groups=...)` replaces the given groups with its own `LayeredDirty`. (30) `ui/inputs.py`: InputBox draws its first text in the box colour (~105) but `render()` redraws it white (~179). (31) `src/glitchygames/examples/dt_demo.py` parses `-v/--version` and `-b/--balls` but never uses them; `text_input_demo` blits its box in `update()` though its group draws it, and puts it in two groups. (32) A `--headless` run still opens a SCALED window under the dummy driver ("no fast renderer available" warning, an error under pytest)
- **Files**: see Details
- **Progress** (2026-10-23): item 25 is fixed for PaddleSlap and both Brave Adventurer editions (`-v/--version` is argparse's version action); the dt demo and Bitmappy still declare a `--version` that does nothing

### 184. Smaller Findings From the Unified Input Devices
- **Description**: Findings from `plans/2026-10-22-unified-input-devices.md`, none breaking a feature on its own
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found implementing the unified input devices
- **Date Reported**: 2026-10-22
- **Details**: (1) Rumble still picks its devices by input mode, not through `InputDevices`: with a controller manager (now `auto` too) `ConnectedRumbleDevices.find` rumbles only the controller manager's controllers, so an unmapped joystick that can rumble no longer rumbles in the default mode (it did when `auto` meant joystick mode); moving rumble to `InputDevice.rumble` (one send per device) would fix it, but changes the devices door calls a joystick-mode recording holds for rumble (`input/rumble.py:68`, `scenes/scene.py` `_update_frame_services`). (2) A playback scope's rumble asks the door as the *live* engine's mode would (`_rumble_devices_for_scope(controller_manager=...)` uses the live controller manager): a joystick-mode recording with rumble, played in an `auto` game, leaves its recorded `joystick_count` answers unasked, which the played scene's own next enumeration would read (no bundled demo or golden recording has per-frame device answers today). (3) A playback scope's recorded device events (JOYDEVICEADDED, ...) go through the live engine's joystick and controller managers, so a played device is added to the live game's managers and `input_devices` and announced to the scope's scene, and stays after the scope (pre-existing for the managers; the registry follows them). (4) `JoystickEventProxy` writes axis, hat and ball events into its caches without a bounds check (buttons have one): an event for an index past the opened device's counts raises IndexError (SDL never sends one; a replay against other stand-ins could) (`events/joystick.py` `on_joy_axis_motion_event`, `on_joy_hat_motion_event`, `on_joy_ball_motion_event`); nothing reads those caches any more (`InputDevice` reads the snapshot). (5) The removed `auto` detection said the controller API "has compatibility issues with pygame-ce 2.5+" without saying which; the known ones (#181, the remapped-event lookup) are fixed, but `auto` now runs both managers on real pads: check on hardware (a DualSense, an Xbox pad, an unmapped stick, hot-plugging each). (6) `ActionMap.from_dict` always builds a map in the default input mode (`auto` now), whatever mode the saved map was made in
- **Files**: `src/glitchygames/input/rumble.py`, `src/glitchygames/scenes/scene.py`, `src/glitchygames/events/joystick.py`, `src/glitchygames/input/action_map.py`

### 186. Smaller Findings From the Typed Events
- **Description**: Findings from `plans/2026-10-22-typed-events.md` (typed, immutable events), none breaking a feature on its own
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found implementing the typed events
- **Date Reported**: 2026-10-22
- **Details**: Fixed 2026-10-22: items 1-4. (1) Bitmappy's joystick hat handler (`bitmappy/controllers/event_handler.py` `on_joy_hat_motion_event`) compared the hat's value with integer bitmasks (1, 2, 4, 8), but pygame always reports a hat as an `(x, y)` tuple, so no direction was ever recognised (each is disabled anyway, so only its debug log changes); the `JOYSTICK_HAT_*` constants are now tuples, `JOYSTICK_HAT_UP` added. (2) `HashableEvent | mapping` (and `mapping | event`) raised AttributeError: UserDict's `|` read `self.data`, which the class never sets; it now builds a changed copy. (3) `MultiLineTextBox`'s click handler computed its line height itself, falling back to `self.font.size` unrounded (a freetype font's float size; the bound `size()` method for a pygame font without `get_linesize`); it uses `_get_line_height()`. (4) `SliderManager.on_slider_event` wrote the clamped value back into its trigger event, which nothing read (removed: events are immutable). Kept for the record: (5) pygame-ce gives `CONTROLLERSENSORUPDATE` no fields at all (its `dict_from_event` has no case for it), so a real sensor event has no `instance_id`: `InputDevices.dispatches` drops it (an input event naming no device), so sensor updates never reach a game, and the interfaces' comments promise `instance_id, sensor, data` (`events/input_event_interfaces.py`; the engine never enables sensors today). (6) Sprite rects are typed `FRect | Rect` (pygame's `DirtySprite` stubs), so a click's position minus `self.rect.x` is `float | int` to the type checker; the widgets' rects are Rects, and `int()` now says so (`film_strip_sprite.py`, `animated_canvas.py`, `ui/text_widgets.py`, `ui/sliders.py`; type-only). (7) A typed class's undeclared names still read as `Any` through `HashableEvent.__getattr__` (kept on the base for custom events), so a typo such as `event.poss` is not caught; a base without `__getattr__` for the typed classes would catch it but needs every generic `HashableEvent` reader typed. (8) pygame-ce's documentation lists `which` for MOUSEWHEEL and `clicks` for MOUSEBUTTONDOWN/UP, but its `dict_from_event` (2.5.6) sets neither, so they are not declared. (9) `HashableEvent.__setstate__` with another type's state keeps the event's class (only pickling calls it, always with its own class's state)
- **Files**: see Details

### 190. LayeredDirty Chooses How to Draw the Next Frame From Wall-Clock Time (Suspected)
- **Description**: pygame's `LayeredDirty.draw` times itself with `pygame.time.get_ticks()` and draws the next frame in full-screen mode (the background over the whole surface, then every visible sprite) when a draw took longer than its threshold (1000/80 ms by default), and in dirty-rect mode (only the dirty areas cleared and redrawn) otherwise. Which mode a frame is drawn in therefore depends on the machine's speed and load, not on the game. Where the two modes draw different pixels (anything drawn on the surface before `draw()` outside the dirty areas, a non-dirty sprite outside them after the surface was filled) a slow machine presents different frames from a fast one
- **Status**: Active
- **Priority**: Low (not observed: no frame differed between two dummy runs or between dummy and cocoa for this reason in the driver comparison, `nox -s compare-drivers`)
- **Reporter**: Found investigating the dummy/cocoa driver comparison
- **Date Reported**: 2026-10-23
- **Details**: Replays compare sprite rects, not pixels, so they are unaffected; the clock read is inside pygame, so `tests/test_engine_doors.py` cannot see it. A fix would pin the mode (`LayeredDirty.set_timing_threshold` with a huge threshold keeps dirty-rect mode; `_use_update = False` keeps full-screen mode) wherever the engine makes its groups, after checking which mode each game relies on
- **Files**: pygame-ce `sprite.py` (`LayeredDirty.draw`); the groups made in `src/glitchygames/scenes/scene.py` and the games

### 200. Smaller Findings From the Docs Audit
- **Description**: Minor findings, none breaking a common path
- **Status**: Active
- **Priority**: Low
- **Reporter**: Found by the docs audit (2026-10-23)
- **Date Reported**: 2026-10-23
- **Details**: (1) TEXTINPUT/TEXTEDITING go to `process_unimplemented_event`; MULTIGESTURE, CLIPBOARDUPDATE, LOCALECHANGED, RENDER_* and some WINDOW* events are never routed. (2) Engine options (as #76): `--resolution` help says 1024x768 but the default is 800x480; `-w` can never change anything; the macOS video-driver check compares with 'MacOS' (it is 'Darwin'); the video-driver lists use SDL 1 names. (3) `api/routes/sprites.py`: an HTTP 400 for a bad `output_path` is caught by `except Exception` and returned as 500. (4) `AnimatedSprite._save_toml_single_frame` writes `alpha = 255` for opaque colours, magenta included. (5) `src/glitchygames/scenes/builtins` is a tracked symlink to `builtin_scenes` (packaging tools and griffe see two copies). (6) Two PyInstaller specs: `bitmappy.spec` and the engine package's `bitmappy.spec` (the second ships in the wheel; maybe stale). (7) #72's title uses the old name `MultiControllerEnhancements`; `ControllerSelection.set_fill_direction` can't be reached from a controller; `GameEngine.process_window_focus_event` and probably `handle_event` are called only by tests. (8) Inaccurate docstrings: `SpriteFactory.save_sprite` lists INI/YAML; references to nonexistent `_detect_file_format()` and `AnimatedSprite._load()`; `EditorSetup.setup_voice_recognition` cites a stale line; `AIManager._is_ai_error_message` claims apology detection; `extract_apng_frames` says failures raise 400 (they return 200 with success=False); `FpsEvent` says Scene posts it (SceneManager does); `ResourceManager`'s singleton claim. Item 8 done (2026-10-23): each docstring now says what the code does (`save_sprite`: TOML only; the real detectors `SpriteFactory.detect_file_format()` and `glitchygames.bitmappy.utils.detect_file_format()`, and `AnimatedSprite.load()`; the voice setup names where `BitmapEditorScene.__init__` leaves it out; `_is_ai_error_message`: any validation failure; `extract_apng_frames`: 200 with success=False, 500 for unexpected errors; `FpsEvent`: SceneManager; `ResourceManager`: one shared instance per class, but `__init__` re-runs, #198), and the `JoystickEventManager` comments name `instance_id` (which the code reads; `joy` is only its fallback)
- **Progress** (2026-10-23): (1) TEXTINPUT/TEXTEDITING now reach the active scene's text handlers and WINDOWTAKEFOCUS is routed; MULTIGESTURE, CLIPBOARDUPDATE, LOCALECHANGED and RENDER_* stay unrouted (no engine handler exists: new features). (2) Fixed with #76. (3) Fixed: `/generate` and `/refine` pass an HTTPException through, so a bad `output_path` is a 400 (`tests/api/test_sprite_routes.py::test_a_bad_output_path_is_a_400`). Still open, each needing a decision: (4) `alpha = 255` round-trips (writer and loader agree); changing it changes every saved file. (5) The `scenes/builtins` symlink needs removing through git. (6) Fixed 2026-10-24: the engine package's `bitmappy.spec` was PyInstaller's generated stub (`collect_all`, no hooks, hidden imports or icon), referenced by nothing and shipped in the wheel; removed, leaving `bitmappy.spec` (the one `nox -s build-binary` uses). (7) `set_fill_direction` and the unused `process_window_focus_event` (its own `set_grab` behaviour) are removal decisions
- **Files**: see Details

### 210. Five Options Do Nothing
- **Description**: Found writing their help text (#74/#76 round): `--video-driver` is parsed and recorded but never applied (nothing sets `SDL_VIDEODRIVER` from it); `--use-gfxdraw` reaches `GameEngine.use_gfxdraw`, which nothing reads (Ball and Paddle set their own unread `use_gfxdraw`); `--font-bold`, `--font-italic` and `--font-antialias` are copied into `FontManager.OPTIONS`, but `font()` and `pygame_font()` read only the name and size; `--font-size` sizes only the default font, and `--font-dpi` sets `pygame.freetype`'s default resolution, which `pygame.font` ignores. The font cache key ignores DPI, so a later DPI change would reuse fonts made at the old one
- **Status**: Active
- **Priority**: Low (the help text now says which are not used or not applied)
- **Reporter**: Found by the engine-options fixes, 2026-10-23
- **Date Reported**: 2026-10-23
- **Details**: Each needs a decision: wire it (`--video-driver` like `--headless`: set the variable before `pygame.init()`, restore it at teardown) or remove it. `--use-gfxdraw`: to be made real (plans/future-features.md #48). Not the tests' driver choice: they set `SDL_VIDEODRIVER` themselves (`tests/conftest.py`, `tests/driver_comparison.py`)
- **Files**: `src/glitchygames/engine/game_engine.py`, `src/glitchygames/fonts/font_manager.py`

### 211. Smaller Findings From the Bug-Fix Round
- **Description**: Found while fixing #74-#209 (2026-10-23); none fixed
- **Status**: Active
- **Priority**: Low
- **Reporter**: The bug-fix round, 2026-10-23
- **Date Reported**: 2026-10-23
- **Details**:
  1. Recordings store raw custom event ids (#197): code that calls `pygame.event.custom_type()` before glitchygames is imported shifts FPSEVENT/GAMEEVENT/MENUEVENT, and a recording made that way replays only in a process that imports the same way. A follow-up could record the ids in the header and remap them on read
  2. `Sprite.on_*_mouse_drag_down/up_event` are no longer called by the mouse proxy (#199): dead handlers
  3. The engine's game-over subtitle still reads "Press SPACE to restart or ESC to quit" though a gamepad now works there too (#209 item 10)
  4. Bitmappy: `FilmStripOperationTracker.add_frame_selection` (`history/operations.py`) falls back to a hard-coded `('strip_1', 0)` when no current frame is known; undoing that first selection on a sprite without `strip_1` targets an animation that does not exist (latent now that #150 keeps the current frame)
  5. Bitmappy: every load records a "Selected frame" step before #150's reset clears it (harmless now; wasted work)
  6. Fixed 2026-10-23: Clockwork Keep's victory played the elevator clank; it now plays its own `victory` chime (`sounds.py`; test `TestClockFaceVictory::test_the_victory_plays_its_own_fanfare`)
  7. `tests/examples/test_brave_adventurer_game.py`'s `_start_display()` keeps whatever display exists (not always 800x480 under pytest); the scenes size the pit floor from it, so pit tests set the display themselves
- **Files**: see each item

## Resolved Bugs

### 223. Importing scripts/gen_ref_pages.py Rewrote docs/
- **Description**: `scripts/gen_ref_pages.py` did all its work at module level, through
  `mkdocs_gen_files.open`, which outside a docs build writes real files into `docs/`. It had not
  been wired into mkdocs.yml since 2024, so the only way it ever ran was by being imported: a
  test importing it rewrote 24 hand-written reference pages under `docs/glitchygames/` (dropping
  their options and module blocks) and added 241 generated files (`docs/SUMMARY.md` and a page
  per module)
- **Status**: Resolved
- **Priority**: Medium (silently rewrote committed docs)
- **Reporter**: Found fixing the members' API reference pages, 2026-10-25
- **Date Reported**: 2026-10-25
- **Details**: The script now generates only the workspace members' pages, inside the build
  (mkdocs-gen-files runs it with `runpy.run_path`; it writes only when `__name__` is
  `RUN_PATH_NAME`). `test_importing_the_script_writes_nothing` and
  `test_run_as_gen_files_runs_it_the_script_writes_each_page_into_the_build` cover both ways in
- **Date Resolved**: 2026-10-25
- **Files**: `scripts/gen_ref_pages.py`, `tests/test_gen_ref_pages.py`, `mkdocs.yml`

### 212. Collecting Garbage Between Tests Stalls the Native Run's coreaudio
- **Description**: With `tests/garbage_collection.py`'s collections on in every run, a local `uv run pytest -n 4` (the dummy run plus its native cocoa/coreaudio child, side by side) took over an hour: in the native run many tests waited almost exactly 30 s, and 20 failed with `pygame.error: mixer not initialized` (sound loading, paddles with collision sounds, the mixer pool, the pause screen)
- **Status**: Resolved (no longer reproduces; the workaround is removed)
- **Priority**: Medium (may be a real hazard in how sounds or audio devices are freed)
- **Reporter**: Found verifying #85's fix, 2026-10-24
- **Date Reported**: 2026-10-24
- **Details**: Reproduced twice in the dual run; it did not happen with the collections off (the dual run passed in 219 s) or in the native run alone with them on (serial 706 s, three workers 175 s, and three workers as a background app recording frame fingerprints, as the child runs, 196 s). Each failing test passes alone. Suspected: a collection frees an old pygame object (a `Sound`, a channel, an audio device, a controller: the DualSense attached to the machine is also an audio device) whose C cleanup locks the audio device while the mixer's callback thread waits for the interpreter lock, or tears down coreaudio state the next mixer start needs; the 30 s waits fit an audio-device timeout. Not narrowed to an object: it shows only with both runs side by side, an hour per try. Next step: log every freed pygame mixer object (type, test) in the native run of a dual run and find the free before the first 30 s stall
- **Investigation 2026-10-24** (on main after #97, collections forced in every process by a scratchpad pytest plugin, the same 16 MB-step collector): no stall, no `mixer not initialized`, no test over 20 s in any of five configurations: the native run alone with the child's 11 workers (77 s, 157 collections); the default side-by-side run (89 s, 163 native collections); the same with the joystick drivers on and a DualSense and a Logitech Dual Action attached (97 s); the original command `uv run pytest -n 4` (native 3 workers: 236 s, 75 collections; it took over an hour when found); and `-n 4` with the pads visible (244 s). The earlier comparison had a confound (the failing run's native child had 11 workers, the clean "alone" runs 3 or serial), but 11 workers alone was clean too. The change that removed the cause is not isolated; candidates landed between finding and now: #97 (the game host, pygame-ce 2.5.8, an in-process clipboard for every test instead of the machine's) and this branch's hidden real pads (ruled out: clean with them visible)
- **Fix**: the workaround is removed: `process_peak_memory_collector()` collects on every audio driver again (`test_every_run_gets_a_collector_reading_its_real_peak`), so the native run's memory is bounded like the dummy run's. Should it return, it shows as a native run far slower than the dummy one (about 90 s side by side on this machine)
- **Date Resolved**: 2026-10-24
- **Files**: `tests/garbage_collection.py`, `tests/conftest.py`, `tests/test_garbage_collection.py`

### 219. A Pad Connected at Startup Got a Second Controller Proxy
- **Description**: SDL reports a pad that is already connected twice: in the startup count (the managers open it in `__init__`) and as a device-added event on the first pump (`--list-input-devices`: one device counted before pumping, then added events at 0.05 s). `ControllerEventManager.on_controller_device_added_event` opened it again and replaced the tracked proxy without checking, so anything the game set on that controller's proxy before the event was lost. `JoystickEventManager` already kept its tracked proxy
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found checking the input-devices work with a DualSense and a Logitech Dual Action, 2026-10-24
- **Date Reported**: 2026-10-24
- **Details**: Measured in a real engine run: `open_controller` and `open_joystick` each ran twice for the pad counted at startup (instance 0), once for the pad reported only by event (instance 1). The second open shares SDL's reference-counted handle, so no handle leaks; the door still records both opens (a replay makes the same calls). Fixed: the controller manager keeps the proxy it tracks for that instance and forwards the event to it (`test_a_device_added_that_is_already_tracked_keeps_its_proxy`, failed before). Seen on the way, not a bug: on SDL's dummy video driver (a `--headless` run, the tests) the Logitech never arrives; SDL finds it on macOS only through the joystick drivers that need the Cocoa event loop, so a dummy-driver run sees only the DualSense, while cocoa sees both
- **Date Resolved**: 2026-10-24
- **Files**: `glitchygames/events/controller.py`, `tests/events/test_controller_events.py`

### 157. A Hypothesis Property Test Fails Its Deadline on a Busy Machine
- **Description**: `TestPaletteRoundtrip::test_double_roundtrip_is_stable` took 277 ms against hypothesis's default 200 ms deadline while another suite ran (DeadlineExceeded); it passes on a quiet machine
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found running two full suites at once
- **Date Reported**: 2026-10-22
- **Details**: The deadline is a speed heuristic, not a correctness check; CI machines can be as loaded. Options: a hypothesis settings profile without a deadline for the suite, or per-test `deadline=None` where the work is file I/O
- **Date Resolved**: 2026-10-24 (`tests/conftest.py` registers and loads a `glitchygames` Hypothesis profile with `deadline=None` for the whole suite; `test_the_suite_runs_hypothesis_without_its_deadline` failed before it)
- **Files**: `tests/test_hypothesis_properties.py`, `tests/conftest.py`

### 214. Two Docs Builds at Once Break Each Other's Complexity Graphs
- **Description**: When two docs builds generate the complexity graphs at the same time (a running `mkdocs serve` and the pre-push hook's `mkdocs build --strict`, both seeing a new HEAD), one fails: `Could not generate the complexity graphs: The graph page loads no plotly.js from cdn.plot.ly: plotly changed its output`, and the push is refused
- **Status**: Resolved
- **Priority**: Medium (refuses pushes while a docs server runs; likely the "transient" pre-push lint failures seen before)
- **Reporter**: Found pushing PR #96, 2026-10-24
- **Date Reported**: 2026-10-24
- **Details**: `scripts/generate_complexity_graphs.py`'s `graph_metric` has wily write each page straight into `docs/quality/graphs/`, then reads it back and rewrites it in place with jsDelivr's plotly.js (`load_plotly_from_jsdelivr`). Both builds write the same paths, so one reads a page the other already rewrote: no cdn.plot.ly URL left, so it raises. The server's log showed its 102 s regeneration (15:12:21-15:14:04) overlapping the push; with the server stopped the push passed. Plotly (5.24.1) and wily (1.25.0) were the same in both environments. The generation also began by deleting the whole graphs directory, pulling pages out from under the other build. Fixed 2026-10-24: everything is made in a staging directory inside the graphs directory (`.staging-*`, hidden from mkdocs) and each finished file replaces its published one in one step (`publish_staged_graphs`; files no longer generated are removed after), and `generate_if_stale` (and `main`) hold a `filelock` lock (`.generation.lock`, released when its process ends) around the check and the generation, so the second build waits and then finds the graphs current. Tests: `test_two_generations_at_once_both_succeed_and_only_one_generates` (failed before with this bug's exact error), `test_the_published_graphs_stay_whole_while_new_ones_are_made`, `test_a_generation_cleans_up_after_one_that_crashed`. Two strict `mkdocs build`s at once on stale graphs both passed (88 s and 85 s)
- **Date Resolved**: 2026-10-24
- **Files**: `scripts/generate_complexity_graphs.py`, `tests/test_generate_complexity_graphs.py`, `pyproject.toml` (`filelock` in the `dev` extra)

### 218. A replay-metrics Test Fails Once a Docs Deploy Measured This Commit on This Machine
- **Description**: `tests/test_replay_metrics.py` `test_measure_one_recording_then_clear` read the
  real published run ledger (gh-pages) while measuring: after `nox -s docs-deploy` measured the
  checked-out commit on this machine, the bundled demo counted as "already measured", nothing
  was measured and the test failed. CI never saw it (no measurements from its machines)
- **Status**: Resolved 2026-10-25: the test stubs the published ledger as empty from the start
  (it already did before its `clear-published` step)
- **Priority**: Low (local runs only, after a deploy)
- **Reporter**: Found running the suite after the first docs deploy with play/, 2026-10-25
- **Date Reported**: 2026-10-25
- **Files**: `tests/test_replay_metrics.py`

### 213. `mkdocs serve` Keeps Every Rebuild Alive, Growing to 14.5 GB
- **Description**: A local `mkdocs serve` (`nox -s docs-serve`) grew by about 330 MB with every rebuild (each saved docs or source file) and was at 14.5 GB when found
- **Status**: Resolved
- **Priority**: Medium (local docs server only; the published build runs once)
- **Reporter**: Found by the docs server's size, 2026-10-24
- **Date Reported**: 2026-10-24
- **Details**: Four builds in one process, as `serve` builds, ended at 694, 1016, 1375 and 1532 MB though the inputs were the same. Every build's griffe API tree and mkdocstrings Python handler stayed alive, held by two unbounded `functools.cache`s keyed by one build's objects: griffe's `_dataclass_parameters` (`griffe/_internal/extensions/dataclasses.py`, keyed by the build's classes; about 430 MB per build kept) and mkdocstrings-python's `_test_existing_template` (`mkdocstrings_handlers/python/_internal/rendering.py`, keyed by the build's Jinja environment). Both are upstream (griffe 2.4.1 and mkdocstrings-python 2.0.10, the latest releases). Not ours: the graph scripts load once and the history they graph is a few kilobytes. Fixed: `scripts/mkdocs_hooks.py`'s `on_post_build` empties every module cache of the loaded griffe and mkdocstrings modules after each build (found by scanning, not by name, so a renamed cache is still found); the same four builds stay at 647-718 MB. The caches only speed up work within one build. Upstream reports (drafted, not posted), evidence and reproduction: `docs/quality/upstream_issues.md`
- **Date Resolved**: 2026-10-24
- **Files**: `scripts/mkdocs_hooks.py`, `tests/test_generate_complexity_graphs.py`, `docs/quality/upstream_issues.md`

### 85. One Process Running the Whole Test Suite Grows to 5.2 GB
- **Description**: `pytest -n 1` (one xdist worker, coverage on) peaked at 5,188 MB resident (macOS `/usr/bin/time -l`, 2026-10-21, 16,339 tests in 13 min). CircleCI's Linux job (`resource_class: small`, 1 vCPU, 2 GB) runs one worker since the worker count follows its CPU quota, so the out-of-memory killer ends that worker part way (`worker 'gw0' crashed`, then a coverage failure from its lost data)
- **Status**: Resolved
- **Priority**: High (the Linux CI job cannot pass)
- **Reporter**: Found investigating PR #95's Linux failure
- **Date Reported**: 2026-10-21
- **Details**: Run serially (`PYTEST_WORKERS=0`) on the small class, the process was killed (signal 9) 16% of the way through. Not a slow leak but spikes: a serial run recording the peak after each test (coverage off) climbed 322 MB -> 3.5 GB in steps, and three tests raised it by 2 GB, each through a recording mock kept millions of calls: `tests/timing/test_timing.py::TestDeadlineReanchorsAfterHitch::test_average_rate_over_jittery_frames_equals_target_exactly[fast]` (+870 MB; the fake clock patched in with `side_effect` mocks, read every fake microsecond of FastTimer's spin over 1,000 frames) and `tests/animation/test_animation_hardware.py::test_hardware_display_buffer_access` / `test_hardware_buffer_integrity` (+590 / +555 MB; the mocked display's recording `get_at`, 480,000 calls per 800x600 capture). Fixed 2026-10-21 with plain functions in place of the mocks: alone, the timing test peaked 2.09 GB -> 123 MB and the hardware file 1.35 GB -> 246 MB. The Linux job is back on the 2 GB small class, serial; whether the whole suite now fits is the open question (the next spikes: Brave Adventurer's game tests, about 300 MB together). Pattern to avoid: a recording mock (`side_effect=`, a `Mock` method) on anything a test calls in a tight loop. Second round 2026-10-24 (PR #96's Linux job killed, signal 9, during the golden replays): a serial CI-style run (coverage on, `--log-cli-level=WARNING`) peaked at 2.6 GB, mostly garbage the cycle collector had not reached yet, not live objects. Each finished scene, its sprites and their groups are reference cycles holding megabytes of SDL surfaces in few Python objects, and the collector runs by object counts, so Brave Adventurer's 319 tests piled up 1.4 GB of them. Fixed: (1) `Scene.next_scene` is None for "stay" (it was the scene itself, a cycle in every scene), and the scene manager resets a scene naming itself to None (about 12% of Brave Adventurer's peak); (2) `tests/replay/test_golden_replays.py`'s `golden_recording` is no longer `functools.cache`d (the five decoded recordings, 1.3 million objects and about 209 MB, were kept for the rest of the run); (3) `tests/garbage_collection.py`: after a test, `gc.collect()` when the process's peak grew 16 MB since the last collection (44 collections, about 6 s per serial run; collecting after every test took 27 minutes), on the dummy audio driver only (#212). Serial peak 2.6 GB -> 1.49 GB (macOS `/usr/bin/time -l`), suite time unchanged. The Linux job passed on the 2 GB small class (PR #96, CircleCI build 2144, 2026-10-24). Ruled out on the way: captured logs (0.2 MB over 20,000 tests), pytest's reports (about 5 KB per test), the coverage cores (`sysmon` and `ctrace` alike) and the per-test fixtures
- **Date Resolved**: 2026-10-24
- **Files**: `tests/`, `noxfile.py`, `.circleci/config.yml`, `tests/garbage_collection.py`, `glitchygames/scenes/scene.py`, `tests/replay/test_golden_replays.py`

### 209. Smaller Findings From the Game Architecture Pages
- **Description**: Found reading every premier game's code for docs/games/ (2026-10-23); none fixed
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found writing the game architecture pages (docs/games/), 2026-10-23
- **Date Reported**: 2026-10-23
- **Details**:
  1. PaddleSlap declares `-v/--version` ("print the game version and exit") but nothing reads it (Brave Adventurer's is #178 item 25)
  2. PaddleSlap: `VerticalPaddle.update()` clamps the paddle to the screen in the render phase (the pose rule reserves `update()` for visual work), so collision sees a paddle past the edge for a frame
  3. PaddleSlap: `Game.setup()` calls `pygame.key.set_repeat(1)` (a KEYDOWN repeat about every 1 ms while a key is held), never undone; movement reads held state, so the repeats only bloat event batches and recordings
  4. PaddleSlap: dead state: `self.ball_spawn_cooldown` (never read; `_get_spawn_cooldown()` is used) and `ball.collision_cooldowns` (only a test touches it)
  5. Brave Adventurer: a scarab that rolls into a pit is probably hidden (the pit fill is drawn after the sprites; only the player is re-blitted). From the code, not checked visually
  6. Brave Adventurer (primitives): Cobra, Scarab and Scorpion redraw their image in `update()`, so their visible-pixel hitboxes are a frame behind in collision (and the whole image before the first draw)
  7. Brave Adventurer: neither edition's player has a running to falling transition: running off a ledge keeps the running pose
  8. Clockwork Keep: no victory: `levels.py` says reaching the top of the Clock Face is victory, but nothing detects it
  9. Clockwork Keep: unused data: `FloorData.enemies` (never filled or read) and the constants `STEAM_SPRITE_*`, `GEAR_GOLEM_*`, `MIC_BUTTON_*`, `PARALLAX_MID`, `PARALLAX_NEAR`, `LAYER_WALLS`, `LAYER_ENEMIES`, `LAYER_HUD`, `INVINCIBILITY_DURATION`, `PLATFORM_GAP_*`
  10. The pause and game-over screens answer only the keyboard: a gamepad cannot unpause or restart any game
  11. `ActionMap.begin_frame`'s docstring says to call it at the start of `dt_tick` before querying `just_pressed`; events are processed after `dt_tick`, so doing that makes `just_pressed` always False in `dt_tick` (Clockwork Keep reads first, correctly)
  12. The games' `_create_action_map(s)` docstrings list `input_mode` as 'joystick' or 'controller' only; 'auto' is the engine default, and the games fall back to 'joystick' when the option is missing
  13. Stale or wrong comments: `ball.py` (~691) says paddle hits are resolved in PaddleSlap's `update()` (they are in `Game.dt_tick`); Clockwork Keep's `_go_to_next_floor` says it uses the wall colours (it passes the platform colours) and unpacks three unused locals; `CAMERA_LEAD_Y`'s "look ahead upward" (it leaves slightly less view above the player); `MovingGear`'s "gear diameter" (it is a size by size/4 bar); Brave Adventurer's repeated `dt_tick` step numbers, "Phase 3" parallax comment, "used in PhysicsBody.platformer()" (built by hand), Scarab "wrap or continue off-screen" (they reverse), and a duplicated voice-assistant comment; `pause_scene.py`'s "Pause scene for paddleslap game" (every game uses it); Mr. Muncher's `drawing.py` docstring says per-pixel-alpha drawing never leaves transparent pixels on the background, which contradicts `game.py` and #142 (why it calls `make_opaque`); `tests/collision/test_ball_paddle_collision.py` says `tests/conftest.py` mocks pygame (it no longer does)
  14. Fixed 2026-10-23: `--resolution`'s help said "(default: 1024x768)"; it now prints the real default (800x480), as #76's details say
- **Files**: see each item
- **Date Resolved**: 2026-10-23
- **Solution**: Every item: (1) `-v/--version` is argparse's version action in PaddleSlap and both Brave editions (prints `<NAME> <VERSION>`, exits 0). (2) `VerticalPaddle` and `HorizontalPaddle` clamp in `dt_tick`. (3) PaddleSlap's `set_repeat(1)` removed. (4) The dead cooldown state removed. (5) Confirmed visually, then fixed: enemies overlapping a pit are redrawn after the pit fill. (6) Cobra, Scarab and Scorpion draw their pose in `dt_tick`. (7) running to falling added (code and Papyrus `player.toml`); the golden traces' new differences are explained by `adventurer_fell_in_its_falling_pose` / `papyrus_fell_in_its_falling_pose`. (8) Clockwork Keep's Clock Face victory: standing on the highest platform fades to `ClockworkKeepVictoryScene` (a `GameOverScene` titled VICTORY!). (9) The unused data and constants removed. (10) `PauseScene` and `GameOverScene` answer a gamepad on both layers (`scenes/builtin_scenes/gamepad_choice.py`): Start or A resumes/restarts on its release after a press there, B or Back quits on its press. (11) `ActionMap.begin_frame`'s docstring: read `just_pressed` first, then call it. (12) Every `input_mode` docstring lists 'auto'; the games' fallbacks are 'auto'. (13) Every stale comment listed. (14) `--resolution`'s help (with #76). Tests in each game's and module's test file; no golden replay re-recorded

### 208. Replaying a Brave Adventurer Recording Can Start the Real Voice Assistant
- **Description**: `VoiceAssistant.discover()` (the primitives edition, its `__init__`) enumerates audio devices through miniaudio, outside the engine's doors, and the microphone toggle starts real listening and AI calls. A replay of a recording that pressed the microphone button would do the same on the replaying machine: nothing it draws differs, but it is outside the replay contract (a replay never touches real devices)
- **Status**: Resolved
- **Priority**: Low (only recordings with a microphone press; no visible divergence)
- **Reporter**: Found writing the game architecture pages (docs/games/), 2026-10-23
- **Date Reported**: 2026-10-23
- **Details**: Likely fix: route device enumeration through the devices door, and skip (or serve recorded results of) the voice assistant while replaying
- **Files**: `glitchygames/examples/brave_adventurer/__init__.py`, `glitchygames/examples/brave_adventurer/game.py`
- **Date Resolved**: 2026-10-23
- **Solution**: `BraveAdventurerScene._discover_voice_assistant()` calls `VoiceAssistant.discover()` only when the active doors serve the real device registry (`LiveDeviceRegistry`: live play or a recording). In a replay, rebaseline or playback the assistant is None: no device enumeration, and a recorded microphone press does nothing. Test: `TestVoiceAssistantNeverStartsInAReplay` (including a golden replay with `discover` asserted not called)

### 206. The Papyrus Edition's Player Keeps Walking While It Respawns
- **Description**: The Papyrus edition's `_respawn_player` lacks the original's `self.player.stop_horizontal()`. While `is_respawning` is set, movement input is skipped, so the acceleration target stays at the last direction (±200 px/s) and the player walks on (about 27 px) during the 0.2 s fade before it is repositioned
- **Status**: Resolved
- **Priority**: Low (cosmetic, during a fade)
- **Reporter**: Found writing the game architecture pages (docs/games/), 2026-10-23
- **Date Reported**: 2026-10-23
- **Files**: `glitchygames/examples/brave_adventurer_papyrus/game.py` (`_respawn_player`)
- **Date Resolved**: 2026-10-23
- **Solution**: The Papyrus edition's `_respawn_player` calls `stop_horizontal()`, as the original does. Test: `TestRespawnStopsWalking`

### 205. Clockwork Keep's Tinker Can Fall Through a Platform After a Slow Frame
- **Description**: `_resolve_ground_collision` finds support only when the feet end a tick within 20 px below a support's top. At the 800 px/s terminal speed a tick longer than 25 ms (below 40 FPS) moves more than 20 px, and the 50 ms `MAX_FRAME_SECONDS` cap allows 40 px, so a hitch while falling fast can drop the Tinker through a platform, or through the ground (costing a life). The cap's comment says it prevents tunneling; at 50 ms it does not
- **Status**: Resolved
- **Priority**: Medium (a hitch can cost a life; rare on a fast machine)
- **Reporter**: Found writing the game architecture pages (docs/games/), 2026-10-23
- **Date Reported**: 2026-10-23
- **Details**: Likely fix: sweep the fall (test the segment from the previous to the new feet position against each support's top), or sub-step physics as Mr. Muncher does (at most 1/120 s per step). Platform and elevator support also use a literal 20 where the gear check uses `GROUND_SNAP_TOLERANCE`
- **Files**: `glitchygames/examples/clockwork_keep/game.py` (`_resolve_ground_collision`, `MAX_FRAME_SECONDS`)
- **Date Resolved**: 2026-10-23
- **Solution**: `_resolve_ground_collision` sweeps the fall: a platform, elevator or gear catches feet that end the tick at or below its top and started it (the world y before the tick, plus any gear ride) within `GROUND_SNAP_TOLERANCE` (`_feet_before_tick`, `_feet_reach_surface`), so a 50 ms tick at 800 px/s lands on the support it crossed. The literal 20s are gone; the `MAX_FRAME_SECONDS` comment no longer claims the cap prevents tunneling. Tests: `tests/examples/test_clockwork_keep.py::TestNoFallThroughAfterASlowFrame`

### 204. Brave Adventurer Never Keeps a Gold Scarab's Bonus
- **Description**: Collecting a gold scarab adds `COLLECTIBLE_SCORE_BONUS` (100) to the score (`_on_player_collect`), but the last step of the same `dt_tick` sets `player.score = round(player.max_distance / DISTANCE_SCORE_DIVISOR)`, so the bonus is overwritten in the frame it is earned: the score is always the distance score. Both editions (`brave_adventurer/game.py:321`, `brave_adventurer_papyrus/game.py:314`). Reproduced by placing the player on a collectible: it was collected and the score stayed 29
- **Status**: Resolved
- **Priority**: Medium (a visible scoring rule that never works)
- **Reporter**: Found writing the game architecture pages (docs/games/), 2026-10-23
- **Date Reported**: 2026-10-23
- **Details**: Likely fix: keep the bonus points separately (score = distance score + bonus points). The golden replay and golden traces include collecting scarabs, so the fix changes the score sprite: check what they compare before changing it
- **Files**: `glitchygames/examples/brave_adventurer/game.py`, `glitchygames/examples/brave_adventurer_papyrus/game.py`
- **Date Resolved**: 2026-10-23
- **Solution**: The players keep `bonus_points` (each gold scarab adds `COLLECTIBLE_SCORE_BONUS`), and `dt_tick` sets `score = round(max_distance / DISTANCE_SCORE_DIVISOR) + bonus_points` in both editions. Tests: `tests/examples/test_brave_adventurer_game.py::TestCollectibleBonusIsKept`. No golden recording changed

### 203. A Scene's Q Key-Down Sets a Quit Flag Nothing Reads
- **Description**: `Scene._handle_scene_key_events` (`glitchygames/scenes/scene.py`, reached from `Scene.on_key_down_event` for a key no focused sprite takes) logs "Quit requested" and sets the scene's own `quit_requested` on Q, but the frame loop reads only `SceneManager.quit_requested`, and nothing reads `Scene.quit_requested`. The press does nothing; a base scene quits on Q's (or ESC's) release instead (`Scene.on_key_up_event` posts QUIT), which is why PaddleSlap and the pause screen still quit. The same dead-flag shape as #202's `next_scene = None`, one level down: the log line claims a quit that never happens
- **Status**: Resolved
- **Priority**: Low (misleading log line and dead state; the release path quits)
- **Reporter**: Found auditing every game's controls for the golden replays (plans/future-features.md #44)
- **Date Reported**: 2026-10-23
- **Details**: Likely fix: drop the flag and the Q branch (the release path is the quit), or post QUIT there as `_handle_quit_key_press` does (then Q would quit on its press and its release would post a second QUIT)
- **Files**: `glitchygames/scenes/scene.py` (`Scene._handle_scene_key_events`, `Scene.__init__`'s `quit_requested`)
- **Date Resolved**: 2026-10-23
- **Solution**: The Q branch and `Scene.quit_requested` are gone; `_handle_scene_key_events` stays as a hook that does nothing (Bitmappy overrides it), and Q quits once, on its release. Test: `tests/scenes/test_scene_focus.py::test_q_quits_once_on_its_release_and_its_press_claims_nothing`; the tests that asserted the flag now assert the press posts no QUIT

### 201. The Sprite Count Report Always Says 0
- **Description**: `Sprite.__init__` does `self.SPRITE_COUNT += 1` (`glitchygames/sprites/sprite.py` ~154), which creates an attribute on each instance instead of incrementing the class counter, so `Sprite.SPRITE_COUNT` stays 0 and the engine's teardown report says `Sprite Count: 0`; the first sprite of each type also records `pixels = 0` instead of its width times height, so per-type pixel totals leave one sprite out
- **Status**: Resolved
- **Priority**: Low (diagnostics only)
- **Reporter**: Found fixing #188 (moving the report from `GameEngine.__del__` to teardown)
- **Date Reported**: 2026-10-23
- **Files**: `glitchygames/sprites/sprite.py`
- **Date Resolved**: 2026-10-23
- **Solution**: `Sprite.__init__` increments `Sprite.SPRITE_COUNT` on the class, and a type's first sprite records width x height pixels. Tests: `tests/sprites/test_sprite_core.py::TestSpriteCounters`

### 199. Mouse Events: Wheel Directions Swapped, Some Handlers Never Called
- **Description**: In `events/mouse.py`, wheel buttons 4 and 5 are swapped (scrolling up calls the scroll-down handler); the button-specific drop handlers and the focus/unfocus handlers are never called (found by reading; verify with tests)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the docs audit (2026-10-23)
- **Date Reported**: 2026-10-23
- **Files**: `glitchygames/events/mouse.py`
- **Date Resolved**: 2026-10-23
- **Solution**: Wheel button 4 scrolls up and 5 down. The mouse proxy calls the handlers `Scene` defines (`on_*_mouse_drop_event`, `on_middle/right_mouse_drag_event`); a release after a drag also calls the released button's drop handler; focus and unfocus follow the topmost sprite under the mouse. Scene's middle/right drag and drop logs are at DEBUG. Tests: `tests/events/test_mouse_events.py` (two strict xfails removed)

### 198. Event Manager Proxies: Lookup Stops at the First Proxy; Re-instantiation Resets a Manager
- **Description**: `ResourceManager.__getattr__` returns from the first proxy and never tries later ones, so e.g. `MouseEventManager().get_pos()` (on `pygame.mouse`, the second proxy) raises AttributeError; and constructing a manager again re-runs `__init__` with `game=None`, resetting the singleton's state (both reproduced)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the docs audit (2026-10-23)
- **Date Reported**: 2026-10-23
- **Files**: `glitchygames/events/base.py` (`ResourceManager`)
- **Date Resolved**: 2026-10-23
- **Solution**: `ResourceManager.__getattr__` tries every proxy in turn and raises AttributeError (not recursion) before `__init__` set the proxies. Shared instances (`SHARES_INSTANCE`: the event managers) are initialized once (`__init_subclass__` wraps `__init__`), so constructing one again returns it unchanged; proxies and `EventManager` (GameEngine, SceneManager) are not shared, which also fixes `ControllerEventProxy` being one object for every controller. `GameEngine._initialize_event_managers` calls `ResourceManager.release_shared_instances()`, so each run builds its own managers. Tests: `tests/events/test_events_core.py::TestResourceManager`, `tests/events/test_controller_events.py::...::test_two_controllers_have_a_proxy_each`

### 197. Custom Event Ids Collide With pygame.event.custom_type()
- **Description**: `FPSEVENT`, `GAMEEVENT` and `MENUEVENT` are hard-coded as `USEREVENT + 1..3` (`events/base.py` ~114-116) instead of being allocated with `pygame.event.custom_type()`; a game or library that calls `custom_type()` gets an id equal to `FPSEVENT` (confirmed: 32866)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the docs audit (2026-10-23)
- **Date Reported**: 2026-10-23
- **Details**: Allocating them with `custom_type()` changes their values, which recordings store: check the golden recordings and the recording format before changing (a remap on read may be needed)
- **Files**: `glitchygames/events/base.py`
- **Date Resolved**: 2026-10-23
- **Solution**: FPSEVENT, GAMEEVENT and MENUEVENT are allocated with `pygame.event.custom_type()` at import (`events/base.py`), keeping USEREVENT+1..3 (the values recordings hold, since glitchygames is imported before game code allocates any); a later `custom_type()` never returns one of them. Tests: `tests/events/test_events_core.py::TestCustomEventTypes` (fresh interpreters). Caveat in #211

### 169. Adding an Animation After a Delete Can Replace an Existing One
- **Description**: `FilmStripCoordinator._add_new_animation` names the new animation `strip_{count+1}`; after a delete that name can still be in use, and that animation's frames are silently replaced
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Details**: Pinned: `test_bitmappy_film_strips.py::test_adding_after_a_delete_does_not_replace_an_existing_animation`
- **Files**: `glitchygames/bitmappy/film_strip_coordinator.py`
- **Date Resolved**: 2026-10-23
- **Solution**: `FilmStripCoordinator._add_new_animation` names the new animation with `_unused_animation_name`: `strip_<count + 1>`, counting up until no animation uses it, so adding (at the end or after a tab) never replaces an existing animation. Tests: `tests/tools/test_bitmappy_film_strips.py` (the strict xfail removed; insert-after and loaded-sprite cases added)

### 150. Undo History Survives Loading Another Sprite
- **Description**: Nothing clears undo history on load: paint on sprite A, load sprite B with the same animation name, press Ctrl+Z, and A's stroke is written into B
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Found by the dead-code audit follow-ups
- **Date Reported**: 2026-10-22
- **Details**: Related: `UndoRedoManager.clear_history` never clears the per-frame stacks (`frame_undo_stacks`/`frame_redo_stacks`) and has no callers. Confirmed by script
- **Files**: `glitchygames/bitmappy/history/undo_redo.py`, `editor.py`
- **Date Resolved**: 2026-10-23
- **Solution**: `UndoRedoManager.clear_history` also clears the per-frame stacks (it keeps `current_frame`, which is where the editor is, not a step). `BitmapEditorScene.start_new_undo_history()` clears it and the paint not yet submitted; `AnimatedCanvasSprite._load_file_into_canvas` calls it in a `finally` once the sprite has been replaced (every load: dialog, drop, PNG, AI result), and `on_new_file_event` after a new canvas. A load that fails before replacing the sprite keeps the history. Loading still cannot be undone, as before. Tests: `tests/tools/test_bitmappy_editor_scene.py::TestUndoHistoryStartsOverInTheRealEditor`, `tests/tools/test_undo_redo_manager.py::test_clear_history_clears_every_frames_stacks`

### 76. Graphics Options: `--resolution` Help, `--windowed` and the macOS Video-Driver Check Disagree With the Code
- **Description**: In `GameEngine.args()` (`glitchygames/engine/game_engine.py`): `--resolution`'s help says "default: 1024x768" while its default is `800x480`; `-w`/`--windowed` is `store_true` with `default=True`, so the flag can never change anything (there is no way to ask for fullscreen); and the video-driver block checks `platform.system() == 'MacOS'`, which never matches (`platform.system()` returns `'Darwin'`), so the macOS branch is dead (harmless today, since it would also give no choices)
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 15: correcting `docs/architecture/argument_system.md` against the argparse definitions)
- **Date Reported**: 2026-10-19
- **Details**: The help text is fixed (2026-10-23: `%(default)s`, so it names the real default; `tests/engine/test_game_engine.py::TestResolutionArgument`). Still open: `--windowed` needs a decision (a `--fullscreen` flag, or `BooleanOptionalAction`); the macOS check should compare with `'Darwin'`
- **Files**: `glitchygames/engine/game_engine.py`, `docs/architecture/argument_system.md`
- **Date Resolved**: 2026-10-23
- **Solution**: All three parts: `--resolution`'s help prints `%(default)s` (800x480). `-w/--windowed` is `argparse.BooleanOptionalAction` (default windowed): `--no-windowed` asks for fullscreen, `-w`/`--windowed` keep working. `--video-driver` offers SDL 2's names per platform (`PLATFORM_VIDEO_DRIVERS`: Darwin cocoa, Windows windows, Linux x11/wayland/kmsdrm; plus offscreen and dummy everywhere), replacing the SDL 1 names and the 'MacOS' comparison; cocoa, offscreen and dummy checked to start on macOS. The option is still not applied (#210). Tests: `TestResolutionArgument`, `TestGameEngineFullscreen`, `TestVideoDriverArgument` (tests/engine/test_game_engine.py)

### 74. `debug_events` Is Always False: `--log-level` Is Compared With Upper-Case Names
- **Description**: `GameEngine.initialize_arguments` (`glitchygames/engine/game_engine.py`, around line 634) sets `OPTIONS['debug_events']` from `OPTIONS['log_level'] in {'DEBUG', 'CRITICAL', 'ERROR'}`, but `--log-level` (`glitchygames/events/game.py`) is lower-cased by `type=str.lower` and its choices are lower case, so the test never matches and unhandled events are never logged through `debug_events`
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 14)
- **Date Reported**: 2026-10-19
- **Details**: Not fixed here: correcting the case would turn event debug logging on for `--log-level error` and `critical` runs too, which looks unintended (the set probably meant `debug` only); the intended levels need deciding first
- **Files**: `glitchygames/engine/game_engine.py`, `glitchygames/events/game.py`, `glitchygames/events/base.py`
- **Date Resolved**: 2026-10-23
- **Solution**: `debug_events` is an explicit opt-in flag, `--debug-events` (Diagnostics Options, off by default): "log a warning the first time each unhandled event type arrives (--no-unhandled-events raises on one instead)" (the user's decision). The derivation from `--log-level` (lower-cased, compared with upper-case names, so always False) is removed. It stays in `REPLAY_LOCAL_OPTIONS`, so a replay uses its own run's flag and old recordings replay unchanged. Side effect: `--debug` is no longer an accepted abbreviation of `--debug-overlay` (argparse: ambiguous with `--debug-events`); `--debug-o` is. Tests: `tests/engine/test_game_engine.py::TestGameEngineInitializeArguments`, `TestDebugEventsArgument`; the restart test's abbreviation case uses `--debug-o`

### 217. A Failed Bitmappy Save Ended the Editor (Unsaved Work Lost)
- **Description**: `AnimatedCanvasSprite.on_save_file_event` logs a save failure (OSError,
  ValueError, KeyError) and re-raises it "for the caller to report", but its caller,
  `SaveDialogScene.on_confirm_event` (`glitchygames/ui/dialogs.py`), does not catch it, and
  neither does `InputBox` (`glitchygames/ui/inputs.py`), which calls `on_confirm_event`. The
  error reaches the engine's crash boundary, so the editor exits `INTERNAL_ERROR` with the
  canvas unsaved, where a load failure is shown in the editor instead (`_show_load_message`)
- **Status**: Resolved 2026-10-24 (branch `wasm/pygame-ce-fork`): `SaveDialogScene.on_confirm_event`
  catches the canvas's OSError, ValueError and KeyError, shows `Error saving <path>: <error>` in
  the editor's debug text box (where load errors show), hands nothing to the player (no browser
  download) and closes the dialog; the drawing stays. The canvas still logs and re-raises.
  Tests: `tests/ui/test_dialogs.py` `test_a_failed_save_returns_to_the_editor_and_is_not_handed_over`
  and `tests/tools/test_bitmappy_failed_save.py` (a real editor saving into a missing folder)
- **Priority**: Medium (a full disk or unwritable folder loses the drawing)
- **Reporter**: Found adding browser Save/Load (plans/2026-10-23-game-host-and-browser-runner.md),
  2026-10-24
- **Date Reported**: 2026-10-24
- **Files**: `glitchygames/ui/dialogs.py`, `glitchygames/bitmappy/animated_canvas.py`

### 216. Games Saw a Focus Loss Before Their First Frame (SDL Recreating a SCALED Window)
- **Description**: `GameEngine` opens its window with `SCALED`, so pygame-ce asks SDL for a
  renderer. When that renderer needs an OpenGL window, SDL recreates the window (SDL 2.32.10
  `GLES2_CreateRenderer` calls `SDL_RecreateWindow`, which hides, destroys and recreates it), and
  each recreation queues the mouse leaving, focus lost and the window hidden, then all three given
  back. The first batch therefore held a focus loss, and Mr. Muncher (which pauses on focus loss)
  started paused in the browser. Measured 2026-10-24: one recreation in Chromium 141 and WebKit 26
  (WebGL), two on the dummy driver (it tries two OpenGL renderers before software), none on
  macOS (cocoa). `RESIZABLE` and `DOUBLEBUF` alone queue nothing
- **Status**: Resolved 2026-10-24 (branch `wasm/pygame-ce-fork`): the host's doors
  (`HostSources.pump_events`, `glitchygames/host.py` `without_window_recreation_bursts`) drop
  each loss a window gets back later in the same batch, with the event giving it back (focus,
  shown, entered, and the matching ACTIVEEVENTs). Beneath the recorder, so recordings hold the
  cleaned batch. Mr. Muncher now starts playing in both browsers. Tests: `tests/test_host.py`
  `TestWindowRecreationBursts` (including a real SCALED window on the dummy driver)
- **Priority**: Medium (a game started paused in the browser)
- **Reporter**: Found running Mr. Muncher in the browser, 2026-10-23
- **Date Reported**: 2026-10-23
- **Files**: `glitchygames/host.py`

### 215. The Default Window Icon Was Never Loaded (ASSET_PATH Pointed Into glitchygames/engine/)
- **Description**: `ASSET_PATH` (and `PACKAGE_PATH`) in `glitchygames/engine/game_engine.py` were
  `Path(__file__).parent`-based. That was right when the engine was `glitchygames/engine.py`
  (`89093de8`, 2023-09); once it became the `glitchygames/engine/` package they pointed at
  `glitchygames/engine/assets`, which does not exist. `GameEngine._icon_path.exists()` was False,
  so every game without its own icon got a blank 32x32 surface instead of
  `glitchygames/assets/glitch.png`
- **Status**: Resolved 2026-10-23 (branch `wasm/pygame-ce-fork`): `PACKAGE_PATH` is the
  `glitchygames` package directory and `ASSET_PATH` is `PACKAGE_PATH / 'assets'`; the default icon
  loads (1024x1024). Tests: `tests/engine/test_engine_initialization.py`
  `TestPackageAndAssetPaths` (they fail on the old paths)
- **Priority**: Low
- **Reporter**: Found building the browser bundle (plans/2026-10-23-game-host-and-browser-runner.md),
  2026-10-23
- **Date Reported**: 2026-10-23
- **Files**: `glitchygames/engine/game_engine.py`

### 207. Unhandled-Event Warnings Turn On at Log Level ERROR and CRITICAL (Not a Bug: Duplicate of #74)
- **Description**: Filed on the reading that `debug_events` is on for `--log-level` DEBUG, ERROR and CRITICAL. It never is: `--log-level` is lower-cased (`type=str.lower`) and compared with upper-case names, so `debug_events` is always False, which #74 already records
- **Status**: Resolved (duplicate)
- **Priority**: Low
- **Reporter**: Found documenting the unhandled-event options, 2026-10-23
- **Date Reported**: 2026-10-23
- **Date Resolved**: 2026-10-23
- **Solution**: Folded into #74, whose fix should also settle the intent (which levels turn the warnings on; DEBUG alone looks likely, since a WARNING record is filtered out at ERROR and CRITICAL anyway). The docs that stated the wrong rule are corrected

### 202. Q Did Not Quit Clockwork Keep, Brave Adventurer, the Papyrus Edition or Mr. Muncher
- **Description**: Each game's quit action set `self.next_scene = None`, but `SceneManager._switch_to_requested_scene` reads a `None` next scene as "no switch pending", so pressing Q did nothing; a comment in `SceneManager.__init__` ("Scene manager terminates on self.next_scene = None") stated the old, wrong rule. The tests only checked that `next_scene` became `None`
- **Status**: Resolved
- **Priority**: Medium (a documented control did nothing in four example games)
- **Reporter**: The user (Mr. Muncher's Q), 2026-10-23
- **Date Reported**: 2026-10-23
- **Date Resolved**: 2026-10-23
- **Solution**: Quit calls `self.scene_manager.quit()` (posts QUIT, as the game-over screen's ESC does) in all four games; the wrong comment is gone and `docs/architecture/event_system.md` states the rule. Tests press and release Q through the engine's frame loop and assert the run ends: `tests/examples/test_mr_muncher.py::test_q_quits`, `tests/examples/test_clockwork_keep.py::...::test_the_quit_key_ends_the_run`, `tests/examples/test_brave_adventurer_game.py::TestQuitKey` (both editions). Since then every golden replay ends with its game's quit control, so a game that stops quitting diverges (plans/future-features.md #44)
- **Files**: `glitchygames/examples/{clockwork_keep,brave_adventurer,brave_adventurer_papyrus,mr_muncher}/game.py`, `glitchygames/scenes/scene.py`, `docs/architecture/event_system.md`

### 188. GameEngine.__del__ Logs, Which Can Fail When Garbage Collection Runs Mid-Write
- **Description**: `GameEngine.__del__` logs the sprite counts (`self.log.info(...)`). When the garbage collector finalises an engine while the process is inside a write to the same stream (pytest's live logging, `--log-cli-level=DEBUG`, writes log records to stdout), the nested write raises `RuntimeError: reentrant call inside <_io.BufferedWriter name=1>`; Python reports it as an unraisable exception and pytest turns that into a failure of whichever test is running (seen once in a cocoa run on a loaded machine: `tests/world/test_gameplay_replay.py::TestProcessingComparison::test_without_a_replay_the_options_are_ignored_with_a_warning[arguments1]`, nine such exceptions; it passed on rerun)
- **Status**: Resolved
- **Priority**: Low (flaky test failures; a real program could print the same unraisable warning at exit)
- **Reporter**: Found re-auditing the test drivers on cocoa
- **Date Reported**: 2026-10-23
- **Details**: Logging (or any I/O) from a finaliser is unsafe: it runs at whatever point the collector triggers. Likely fix: report the sprite counts from the run's teardown (`_shutdown`) instead of `__del__`, or drop `__del__`
- **Date Resolved**: 2026-10-23
- **Solution**: No finaliser does I/O now. `GameEngine.__del__` is gone: the teardown (`_shutdown`, beside the unhandled event table) logs the sprite counts (`_log_sprite_count_report`). The only other finaliser in the package, `FastTimer.__del__`, logged when giving back the 1 ms Windows timer resolution failed; the timers now have an explicit `close()` (FastTimer's ends the period once and logs a failure; PygameTimer's does nothing), which `_shutdown` calls, and `FastTimer.__del__` stays as a silent backstop for a timer never closed. No `weakref.finalize` or `atexit` hooks exist. Tests: `tests/engine/test_game_engine.py::TestGameEngineTeardownReports` (the counts logged at teardown, no `GameEngine.__del__`, the timer closed); `tests/timing/test_timing.py` (close releases once, the finaliser releases an unclosed timer and logs nothing, and `test_a_finaliser_run_mid_write_does_not_write` reproduces the reentrancy deterministically: a timer's last reference is dropped from inside the raw write of the stream its logger writes to, which with the old finaliser raised `RuntimeError: reentrant call inside <_io.BufferedWriter>` as an unraisable exception)
- **Files**: `glitchygames/engine/game_engine.py` (`_shutdown`, `_log_sprite_count_report`), `glitchygames/timing.py` (`FastTimer.close`, `FastTimer.__del__`, `PygameTimer.close`)

### 112. The Palette README's Example Cannot Load
- **Description**: `glitchygames/color/resources/README.md` documents a `[palette]` section, but the loader reads `[default]`
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found fixing #104
- **Date Reported**: 2026-10-21
- **Files**: `glitchygames/color/resources/README.md`
- **Date Resolved**: 2026-10-23
- **Solution**: The README example uses the loader's `[default]` section and `description` key; it loads now (docs audit, 67605eef)

### 196. A PaddleSlap Session Recorded on x11 Under Load Can Diverge on Replay
- **Description**: `tests/replay/test_record_scripted_session.py::test_scripted_session_records_and_replays` records 120 PaddleSlap frames live (in the test process, on the run's display) and replays them headless. On x11-linux (the Docker container drawing on XQuartz), with other tests running beside it, the replay switched to `PaddleSlapGameOverScene` where the recording stayed in `Game` (frame 100, 105 and 115 in three failures); every sprite rect matched until then. It passes alone and under CPU load alone, and never failed on dummy, cocoa or x11-macos
- **Status**: Resolved
- **Priority**: Medium (if it is a determinism bug in the engine or PaddleSlap, any live recording can fail to replay)
- **Reporter**: Found by the driver comparison (x11-linux), 2026-10-23
- **Date Reported**: 2026-10-23
- **Date Resolved**: 2026-10-23
- **Root Cause**: Not the window-size race (#193): it still failed after that fix, with no warning, and the recording's frames were all 800x480. Not key repeat, X window events or sub-pixel state. Investigated 2026-10-23 by keeping the failing recordings (a scratch copy of the test writing them to a fixed path, run with the three files at `-n 4 --dist loadscope` in the container: 2 of 4 failed; they then failed the same way replayed headless on the Mac, so the replay is deterministic and the recordings hold the difference). Under that load the container's frames take 0.1-0.7 s, so the ball passes the paddle within the first 15 frames: game over, and `PaddleSlapGameOverScene` plays the bundled demo after `GAME_OVER_IDLE_SECONDS` (10) of game time, around frame 85-120. The `Game` the recording "stayed in" is the demo's (its sprite ids `VerticalPaddle#2`/`#3`, `BallSprite#1`). Two causes, both in replaying a session that played a scope:
  1. A scope's first frame recorded the played recording's dt, but that frame's time was read on the live doors as the frame before it ended, where it advanced the live frame clock and could post an FPS event (a long frame does). The replay of the session was served the played dt there, so it missed that FPS event (`missing internal event` FPS, frames 98 and 119 in two failures) and its frame clock fell behind the session's for good (it is restored after the scope). Now the installed doors' `end_frame` always gets the installed doors' own frame time (`PlaybackSources.installed_frame_seconds`, `SceneManager._installed_doors_frame_seconds`): the scope's frames still run with the played recording's dt, which a replay of the session serves again. Test: `tests/replay/test_playback_scope.py::TestRecordingDuringAPlayback::test_a_session_whose_scope_began_after_a_long_frame_replays_exactly` (fails without the fix on dummy and cocoa with the same divergence)
  2. The recording's scripted supervisor (`scripts/record_scripted_session.py`'s `ScriptedInputSupervisor`) posts its keys with `post_input_event` while the demo plays. Live, the scope held a live supervisor's posts for the live game (`held_live_game_posts`), so the press did not end the demo; the replay (which, as designed for `post_input_event`, runs without the supervisor) served the recorded press as external input, the scope's exit check saw it and the demo ended (`The demo playback ended: exit_input`): scene `Game` expected, `PaddleSlapGameOverScene` got, at frames 87 and 107 in two failures after fix 1
- **Solution**: (1) as above: the installed doors' `end_frame` always gets their own frame time; every recorded scope frame's dt is the live measured frame time (the user's decision). (2) The user's decision, 2026-10-23, "supervisor posts = player": the live game's `post_input_event` posts of an SDL type (below `USEREVENT`), made during a scope or pending as it begins, are the player's input there (`PlaybackSources._sort_live_post`, `_sort_player_event`, `_is_sdl_event_type`; rule 5 of `glitchygames/replay/playback.py`): a press reaches the exit check (it ends an exit-on-input demo, live too), releases, device and window events are held with the player's (`held_live_events`, external) and redelivered after the scope, the rest reach nothing. A replay of the session without the supervisor serves the same recorded events to the same branches, so the two agree. Input posts of a type SDL never generates (no player makes one) stay the live game's, held and posted again as input after the scope. Follow-up, 2026-10-23 (the user's requirement: "I do want the supervisor to be able to generate all game events though. Not just ones the player can generate."): a replay of the session without the supervisor served such a post (recorded external) to the scope, whose sorting classified unmatched events by type, so a custom-type event (`GAMEEVENT`) was taken for the playback scene's own internal event (`demo diverged: ... unexpected internal event`, the live game never got it) or, pending as the scope began, held as internal (the replay delivered it, but a `--rebaseline` recorded its `redelivered_events` origin as internal). Now the scope takes each served event's recorded origin from the installed doors (`replayed_batch_origins`, moved from `glitchygames/engine/game_engine.py` to `glitchygames/replay/driver.py`: `ReplaySources.last_batch_origins()`, through a `--rebaseline`'s `RecordingSources`), and holds a recorded external event of a non-SDL type that matches no post exactly as the live run did (`_is_served_live_input_post`; pending as the scope began: `held_live_events`, external; during it: `held_live_game_posts`, posted again as input after it). Live sorting is unchanged. The rule (rule 5 of `playback.py`): a supervisor may post any event (`post_input_event`); input of an SDL type during a scope counts as the player's; everything else reaches the game (after the scope if one is playing), live and replayed alike. The Limits paragraph keeps only a supervisor's `post_event` posts (the game's own, which a replay expects the replayed code to make again). Recordings made before the change under the old rule (such as the two failing x11 recordings) cannot match: live, the press did not end the demo, and a replay now (as before) ends it. Reproduced deterministically on dummy by recording PaddleSlap's scripted session with each live frame slowed (0.3 s): the old rule diverged at frame 39, the new one matches (with 0.12, 0.3 and 0.5 s frames; the supervisor's presses ended the demo up to three times). With the new rule the scripted supervisor ends the game-over demo whenever it presses during it; the test records and replays reliably (10 local runs; 3 runs of it with `test_processing_comparison.py`, `test_rebuild.py` and `test_playback_scope.py` at `-n 4 --dist loadscope` in the x11-linux container)
- **Tests**: `tests/replay/test_playback_scope.py::TestRecordingDuringAPlayback::test_a_session_whose_scope_began_after_a_long_frame_replays_exactly` (cause 1); `tests/replay/test_playback_scope.py::TestALiveSupervisorsInputIsThePlayers` (cause 2: a supervisor's press ends a demo; reaches nothing without exit on input; a session whose supervisor pressed during a demo, and one whose supervisor released during a scope, replay without it; an input press pending as a demo begins ends it; all but the second fail without the fix); follow-up: `tests/replay/test_playback_scope.py::TestASupervisorPostsAnyEvent` (a supervisor's `GAMEEVENT` reaches the game once, at the same frame live and in a replay without it, and every frame matches: outside a scope, during a demo, during a scope without exit on input, pending as a demo begins; a `--rebaseline` of the session keeps its origins and replays; the demo, scope and both rebaseline cases fail without the fix)
- **Files**: `glitchygames/replay/playback.py`, `glitchygames/scenes/scene.py`, `glitchygames/recording.py`, `tests/replay/test_playback_scope.py`; follow-up: `glitchygames/replay/driver.py`, `glitchygames/engine/game_engine.py`, `docs/architecture/gameplay_replay.md`, `CLAUDE.md`

### 191. A Replay Never Checks the Recorded Display Size
- **Description**: Games read the real display size: scenes and sprites take `screen.get_width()`/`get_height()` when built (`Scene` and `Sprite.__init__`), and PaddleSlap places its paddles at half the screen height and bounces its balls off the screen's edges. A recording's header holds the size the window had (`screen_size`), but a replay opened its window at the recorded `--resolution` and never compared. When the window a recording was made on had another size than requested (a window manager that widened it, a tiling window manager, an x11 resize that landed late, #193), the replay diverged
- **Status**: Resolved
- **Priority**: Medium (a recording that cannot replay; not seen in a golden fixture, all recorded on dummy)
- **Reporter**: Found investigating the x11 driver comparison (`test_scripted_session_records_and_replays` diverged at frame 105 on x11-linux)
- **Date Reported**: 2026-10-23
- **Date Resolved**: 2026-10-23
- **Root Cause**: `start_replay` applied the recorded options, `--resolution` among them, and nothing read the header's `screen_size`. Shown on dummy: PaddleSlap recorded asking for 800x480 on a window forced to 800x600 (header `screen_size [800, 600]`) replayed with `Replay diverged at frame 0: sprite VerticalPaddle#0 rect expected [0, 250, 20, 100], got [0, 190, 20, 100]`
- **Solution**: No format change. The replay opens its window at the recorded size: `start_replay` sets the `resolution` option to the header's `screen_size` (`apply_recorded_screen_size`, glitchygames/replay/driver.py rule 1), so the engine's normal display set-up (`GameEngine.initialize_display`, headless or watched) asks for it. When the window still opens at another size, the engine logs `Cannot replay PATH: it was recorded on a 800x600 display, but the window opened at 800x480 (the window manager chose another size); refusing to replay it` and exits `UNUSABLE_INPUT` (`display_size_refusal`, `GameEngine._refuse_a_replay_display_of_another_size`). A `screen_size` that is not two positive integers is a malformed header (`UNUSABLE_INPUT`). A header without one (the engine's recorder has always written it, format 2 included; only a hand-made header lacks it) keeps the recorded `--resolution`, with a warning. Still open: a size that changes during a recording (a window resized mid-game) is not recorded, so a game that reads the live size every frame would need the size served through the doors (a format addition, for the user to decide). The in-game playback scope (demos, instant replay) plays in the live game's window and does not apply the size
- **Tests**: `tests/world/test_gameplay_replay.py::TestRecordedDisplaySize` (the repro above now matches; it fails without the fix with the same divergence; the refusal; recordings without a size, formats 2 and 3; malformed sizes)
- **Files**: `glitchygames/replay/driver.py`, `glitchygames/engine/game_engine.py`

### 192. compare-drivers Reports Agreement When No Test Ran
- **Description**: `nox -s compare-drivers -- --help` hands `--help` to every pytest run, which prints its help and exits 0 recording no test; the session then reported "Every configuration agrees on every compared test" and overwrote the previous report with zero-test runs
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by accident investigating the x11 failures (the previous report was overwritten)
- **Date Reported**: 2026-10-23
- **Date Resolved**: 2026-10-23
- **Root Cause**: `scripts/driver_frame_matrix.py` compared whatever the runs recorded, zero tests included, and the session deleted its output folder (the last report) before the first run
- **Solution**: The matrix refuses runs that recorded no test before writing anything (no report, no image request): it names each run on stderr (`No report written: run dummy-1 (dummy, DIR) recorded no test (did pytest run the suite? --help or --collect-only run no test), so nothing could be compared`) and exits `UNUSABLE_INPUT`, which fails the session. The session no longer deletes the last comparison first: it waits in `test-results/driver-comparison/nox-previous/` while a comparison runs, goes back to `nox/` when the comparison fails (any failure, or Ctrl-C), and the failed comparison's runs are kept in `nox-failed/`
- **Tests**: `tests/test_driver_frame_matrix.py::TestCommandLine::test_runs_that_recorded_no_test_write_nothing_and_are_named`, `::test_an_earlier_report_is_kept_when_a_run_recorded_no_test`, `::TestComparisonFolders`
- **Files**: `scripts/driver_frame_matrix.py`, `noxfile.py`, `docs/quality/driver_comparison.md`

### 193. Resizing an Existing Window Left the Game on the Old Size (x11)
- **Description**: On SDL's x11 driver a window's new size arrives after `set_mode` returns when the window manager takes longer than SDL's 100 ms wait (`X11_SetWindowSize`): pygame warns "Requested window was forcibly resized by the OS" and returns a display surface of the old size, which changes to the requested size on a later pump. A game set up then (an engine started on an existing window, a test's display) built its scenes and sprites on the old size. In the driver comparison, 86 x11-linux tests failed with the warning (800x600 and 800x480 swapped)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the driver comparison (`nox -s compare-drivers`, x11-linux)
- **Date Reported**: 2026-10-23
- **Date Resolved**: 2026-10-23
- **Root Cause**: SDL's x11 resize gives up after 100 ms; over TCP from the Linux container to XQuartz under load, every resize took 0.8-3.4 s (8 processes resizing at once)
- **Solution**: `glitchygames.display_mode.set_display_mode` sets the mode and, when pygame warns and the display still has its old size, pumps until the size changes (at most about 10 s), warning only if the window ends at another size than the requested one. `GameEngine.initialize_display` and the tests (the conftest's display reset, every `set_mode` call) use it
- **Tests**: `tests/test_display_mode.py`, `tests/engine/test_game_engine.py::TestGameEngineDisplayMethods::test_initialize_display_waits_for_a_late_resize` (a stand-in window manager answers late: `tests/slow_window_manager.py`)
- **Files**: `glitchygames/display_mode.py`, `glitchygames/engine/game_engine.py`, `tests/display_canvas.py`

### 194. The Engine Enabled SYSWMEVENT, Which SDL Leaves Disabled
- **Description**: `GameEngine.initialize_event_handlers` called `pygame.event.set_allowed(None)`, which enables every SDL event type, `SYSWMEVENT` (the window system's raw messages) included. On a real X server every X event the window got then reached the queue: tests that assumed a quiet queue failed on x11, and `tests/replay/test_instant_replay.py::TestTheJournal::test_journal_memory_per_minute_stays_bounded` exceeded its bound (518,753 and 585,910 bytes against 500,000) because the journal kept them
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the driver comparison (x11-macos and x11-linux)
- **Date Reported**: 2026-10-23
- **Date Resolved**: 2026-10-23
- **Root Cause**: The allow-all, since commit 869c8ade (2025-11-02, "Stale code cleanups"). Test fixtures that snapshot and restore the blocked types made it worse: pygame-ce 2.5.8 reports `SYSWMEVENT` as allowed while SDL ignores it (until it is blocked through pygame), so restoring the snapshot enabled it
- **Solution**: `events.allow_every_event_type(native_window_messages=...)` allows every type and blocks `SYSWMEVENT` through pygame unless the game's scene class sets `NATIVE_WINDOW_MESSAGES = True` (then they reach `on_sys_wm_event`); the conftest blocks it before each test
- **Tests**: `tests/engine/test_engine_event_system.py::TestNativeWindowMessages`, `tests/world/test_gameplay_replay.py::TestRealInputBlocking::test_native_window_messages_stay_blocked_after_the_replay`, the SYSWMEVENT case of `tests/test_recording.py`'s round trip
- **Files**: `glitchygames/events/base.py`, `glitchygames/engine/game_engine.py`, `glitchygames/scenes/scene.py`, `tests/conftest.py`

### 195. x11-macos Workers Died in XQuartz's OpenGL
- **Description**: Pytest workers on x11-macos (SDL built with x11, drawing on XQuartz) ended with no Python traceback (`worker 'gw2' crashed`). Reproduced twice: `X Error of failed request: GLXBadContext` (`X_GLXMakeCurrent`), and a segmentation fault in SkyLight (`CGSWindowFinalize`) on a thread of Apple's Xplugin (faulthandler's C stack)
- **Status**: Resolved
- **Priority**: Low (test configuration only)
- **Reporter**: Found by the driver comparison (x11-macos)
- **Date Reported**: 2026-10-23
- **Date Resolved**: 2026-10-23
- **Root Cause**: The build had OpenGL (GLX). SDL on macOS marks every window OpenGL by default (`SDL_DefaultGraphicsBackends`), so creating any window loaded XQuartz's libGL and Apple's Xplugin into the process, and SDL drew window surfaces through an OpenGL texture (the window had an `opengl` renderer). XQuartz's GLX failed under load (its log is full of `DRISurfaceNotify: xp_destroy_surface failed`); an X error exits through Xlib's default error handler. The Linux container has no libGL, so it always drew in software
- **Solution**: `scripts/build_sdl_x11.py` configures SDL with `--disable-video-opengl`: no libGL or Xplugin in the process, window surfaces drawn in software (XShm)
- **Tests**: `tests/test_build_sdl_x11.py` (the configure options)
- **Files**: `scripts/build_sdl_x11.py`

### 189. The Elevator Ride Drew a Black Box Around the Player on macOS
- **Description**: During Clockwork Keep's elevator ride (`ElevatorTransition`), the player, pinned on the platform, was drawn inside a black rectangle on cocoa: its transparent pixels showed black instead of the floor behind it. The dummy and x11 drivers drew it correctly
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the driver comparison (`nox -s compare-drivers`): `tests/world/test_golden_traces.py::test_game_matches_golden_trace[clockwork_keep]`, `tests/world/test_gameplay_recording.py::test_recording_matches_the_golden_harness_frames` and `tests/world/test_transition_input.py::test_jump_pressed_during_elevator_ride_does_not_jump_on_arrival` presented 761 differing pixels from the ride's first frame
- **Date Reported**: 2026-10-23
- **Date Resolved**: 2026-10-23
- **Root Cause**: The ride's composite (new floor, shaft, old floor) was a plain `pygame.Surface(size)`, which on cocoa takes the display's format (an alpha mask without SRCALPHA). Blending the floor screenshots onto it left alpha 0 there (the effect behind #142); each frame copied that alpha 0 into the display, and pygame-ce's alpha blitter copies a source pixel outright onto a destination pixel with alpha 0, so the player's transparent pixels (0, 0, 0, 0) replaced the floor and `make_opaque` then showed them black
- **Solution**: The composite and the shaft are made in the screenshots' format (`pygame.Surface(size, 0, old_surface)`) and the finished composite is made opaque (`make_opaque`), so the display keeps alpha 255 under the player. The driver comparison then finds no difference in those tests
- **Tests**: `tests/transitions/test_transitions.py::TestElevatorTransitionOnPerPixelAlphaDisplays` (screenshots in cocoa's format, so it fails without the fix on dummy too; it failed on cocoa before the fix)
- **Files**: `glitchygames/transitions/elevator.py`

### 187. Tests After a Headless Engine Ran on the Dummy Drivers
- **Description**: In a full-suite run on real drivers (`SDL_VIDEODRIVER=cocoa SDL_AUDIODRIVER=coreaudio`), 2,186 of 19,025 tests started on the dummy video driver and 4,686 on the dummy audio driver (99 more with no mixer at all): a test that constructs an engine with `--headless` sets `SDL_VIDEODRIVER`/`SDL_AUDIODRIVER` to `dummy` and restarts a display and mixer on another driver on the dummy one, and nothing switched back, so every later test on that xdist worker ran without a window or sound
- **Status**: Resolved
- **Priority**: Medium (the real-driver runs tested the dummy drivers for part of the suite)
- **Reporter**: Found by a per-test display audit on cocoa
- **Date Reported**: 2026-10-22
- **Date Resolved**: 2026-10-23
- **Root Cause**: `GameEngine._enter_headless_mode` changes the process's environment and restarts the display and mixer, but never put the variables back, even when the run ended. Two leak shapes: (1) the variables stayed `dummy` (a test running a headless replay without restoring the environment), so even a display reopened later came up on dummy; (2) the test restored the variables itself (`monkeypatch`, `mocker.patch.dict(os.environ)`, `engine_run_environment`) but the display and mixer it had moved stayed on dummy, and the harness reopens a display only when none is running. A test that quit the mixer (`tests/audio/test_synth.py`) likewise left later tests without one
- **Solution**: The engine keeps the variables' earlier values in `_enter_headless_mode` and puts them back (an unset one removed) in `_tear_down_run`, after `_shutdown` has quit pygame, even when the teardown fails: a program that runs a headless replay and goes on starts pygame on its own drivers again. The test harness is the safety net for tests that never end a run: `tests/sdl_defaults.py` keeps the run's variables (`SDL_DRIVER_ENVIRONMENT_FOR_RUN`), the session fixture `run_sdl_driver_state` reads the drivers the run's display and mixer start on, and `ensure_pygame_graceful_quit`'s teardown calls `restore_run_sdl_drivers` (`tests/sdl_driver_isolation.py`): it sets back changed variables, restarts a display on another driver (shown with the canvas at 800x600, never black) and a mixer on another driver or stopped (with the run's format and channel count), through pygame functions captured at import (a test's mocks may still be in place at that teardown). Nothing changed costs about 4 microseconds; a restart about 0.2 s on cocoa/coreaudio (more on a loaded machine; 128 restarts in a cocoa run). After: 0 of 19,037 tests started on a dummy driver in the cocoa run
- **Tests**: `tests/test_sdl_driver_defaults.py` (the run's variables and state; nothing restored when nothing changed; variables put back; a display on another driver reopened showing the canvas; a mixer on another driver or stopped restarted with the run's format; with pygame quit only the variables), each moving things off the run's drivers by naming other drivers so it means something on a dummy run; `tests/world/test_gameplay_replay.py::TestHeadlessDriverRestore` (a headless run puts the variables back, also after a failed teardown; a non-headless run leaves them alone; a constructed headless engine is put back on the run's drivers by the harness)
- **Files**: `glitchygames/engine/game_engine.py`, `tests/conftest.py`, `tests/sdl_defaults.py`, `tests/sdl_driver_isolation.py`, `CLAUDE.md`, `docs/architecture/gameplay_replay.md`

### 142. On Displays With Per-Pixel Alpha, Translucent Sprites Over a Bare Scene Background Do Not Blend
- **Description**: The `Scene.background_color` setter added alpha 0 to an RGB colour. On displays with an alpha channel (cocoa) the restored background pixels had alpha 0, and pygame-ce's alpha blitter copied the source colour onto them instead of blending: foo2 in a Scene showed corner (255, 0, 255, 0) and an unblended body (80, 220, 120, 137) on cocoa, (20, 20, 40) and a blended (52, 127, 83) on dummy. The cocoa window shows a pixel with alpha 0 as black whatever its colour, so every scene with a background colour (PaddleSlap, Clockwork Keep, the text input demo, game over, pause, dialogs) presented black frames or black holes on macOS, and `Scene.screenshot` came out transparent, so the pause screen showed black where the frozen game should be
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the coverage audit follow-ups
- **Date Reported**: 2026-10-22
- **Date Resolved**: 2026-10-22
- **Root Cause**: Alpha 0 came in by the PR #87 "normalize to RGBA" change (nothing relied on a transparent scene background: no scene sets a four-component one). Underneath it, on a display with per-pixel alpha a plain `pygame.Surface(size)` (and `convert()`'s result) takes the display's format, alpha mask included, without the SRCALPHA flag: blitting such a surface copies its alpha unblended, and alpha-blending anything (text, a SRCALPHA copy) onto it leaves alpha 0 there. The dummy and x11 displays have no alpha channel, so none of this shows off macOS
- **Solution**: A scene background is opaque: an RGB colour becomes RGBA with alpha 255, and a translucent colour (alpha below 255) raises `ValueError` (the background is the frame's bottom layer: nothing is under it to show through, and the drivers would disagree about how to show it). `glitchygames/opacity.py` (`has_per_pixel_alpha`, `make_opaque`: a `BLEND_RGBA_MAX` fill with opaque black, which raises alpha to 255 and keeps the colours, about 0.04 ms at 800x600) makes every presented frame opaque (`SceneManager._show_frame`), so the window shows the colours the dummy driver shows; the background patterns are made opaque (their text is blended); `Scene.screenshot` is opaque (opaque black, then a `BLEND_RGBA_MAX` blit of the screen: the screen's colours, unblended, as the presented frame shows them); `SliderSprite` copies its kept gradient back unblended (`set_alpha(None)`), and `TabControlSprite` and `InputBox` make their images opaque after drawing their text. The test display guard judges what the window shows (`display_looks_entirely_black`: on a display with per-pixel alpha a pixel looks black when its colour or its alpha is 0), and the conftest teardown that sets the display back to 800x600 presents the canvas, so no window is left black (under the last scene's caption, e.g. "Arrival v1.0") while a worker waits. A cocoa run (`SDL_VIDEODRIVER=cocoa`) of the whole suite went from 15 tests whose last frame looked entirely black (all alpha 0), 50 more with alpha-0 regions and 4 that presented black-looking frames, to none
- **Tests**: `tests/test_opacity.py`; `tests/scenes/test_scene.py` (`TestSceneBackgroundColor`: opaque RGB and RGBA, translucent refused, non-RGB(A) refused, opaque on a per-pixel-alpha target; `TestSceneScreenshot`); `tests/scenes/test_scene_rendering.py::TestSceneBackgroundOpacity` (foo2's blend); `tests/test_display_canvas.py` (`TestTheBlackFrameCheck`, per-pixel-alpha surfaces built explicitly so it runs on dummy); `tests/effects/test_shake.py` and `tests/world/test_gameplay_replay.py::TestWatched` (presented frames opaque); `tests/ui/test_ui_sliders.py`, `test_ui_tab_control.py`, `test_ui_input.py` (images opaque in cocoa's format). The cocoa-only strict xfail `tests/scenes/test_scene_rendering.py::TestSceneRendering::test_scene_rendering_with_surface_management_manager` passes now (marker removed)
- **Files**: `glitchygames/opacity.py`, `glitchygames/scenes/scene.py`, `glitchygames/backgrounds.py`, `glitchygames/ui/sliders.py`, `glitchygames/ui/inputs.py`, `glitchygames/scenes/builtin_scenes/pause_scene.py` (comment), `tests/conftest.py`, `tests/display_canvas.py`

### 143. `Scene` Discards Its Converted Background
- **Description**: `Scene.__init__` called `self.background.convert()` and threw the result away; `Scene.screenshot` did the same with `screenshot.convert()`
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the coverage audit follow-ups
- **Date Reported**: 2026-10-22
- **Date Resolved**: 2026-10-22
- **Solution**: Both keep `convert()`'s result (`pygame.Surface(size).convert()`); the screenshot is also made opaque (#142). The same discarded `convert()` remains in `ui/inputs.py` (`InputBox.__init__`), `BitmappySprite.__init__` (#173.5) and `BitmappySprite.inflate`
- **Tests**: `tests/scenes/test_scene.py` (background and screenshot tests), run on dummy and cocoa
- **Files**: `glitchygames/scenes/scene.py`

### 181. Controller Mode Crashes After a Controller Is Replugged
- **Description**: `ControllerEventManager` stored each controller under its device index (`self.controllers[controller_id]` at startup, `self.controllers[event.device_index]` on CONTROLLERDEVICEADDED) but looked it up by the event's instance id (`self.controllers[event.instance_id]` in every axis/button/touchpad handler). They are equal only until a device is replugged (SDL gives it a new instance id) or devices are opened out of order; then the first axis or button event raised KeyError
- **Status**: Resolved
- **Priority**: High (a crash), in controller mode only then (`--input-mode controller`; joystick mode, the pygame-ce default then, blocked controller events); `auto` runs the controller manager now
- **Reporter**: Found planning the unified input devices (`plans/2026-10-22-unified-input-devices.md`)
- **Date Reported**: 2026-10-22
- **Date Resolved**: 2026-10-22
- **Root Cause**: The manager keyed proxies by the device index the added event names, but every later event names the instance id. Also: `on_controller_device_remapped_event` read `event.device_index`, which a CONTROLLERDEVICEREMAPPED event does not have (pygame's event docs: it carries `instance_id`), so every real remap raised AttributeError; and a controller unplugged again before CONTROLLERDEVICEADDED could open it raised `pygame.error` out of the engine
- **Solution**: Proxies are keyed by the instance id they open with (`ControllerEventProxy.instance_id`, from the controller's joystick view), at startup and on CONTROLLERDEVICEADDED, as the joystick manager does; a remap is looked up by its instance id (an untracked one is ignored); a controller that vanished before it opened is logged and skipped. `JoystickEventManager.joysticks` and `ControllerEventManager.controllers` are typed (`dict[int, JoystickEventProxy]` / `dict[int, ControllerEventProxy]`, the proxies' devices `OpenedJoystick` / `OpenedController`), with public `instance_id` and `device_index` on both proxies. Duplicate of #68 (also resolved)
- **Tests**: `tests/events/test_controller_events.py` (`TestControllersKeyedByInstanceId`: stand-ins whose instance id differs from their device index, at startup, hot-plugged, remapped, replugged, vanished); `tests/events/test_events_integration.py::TestEventIntegration::test_reconnected_controller_event_through_engine` (the strict xfail of #68, now a passing test); the engine-level dispatch tests in `tests/engine/test_game_engine.py`
- **Files**: `glitchygames/events/controller.py`, `glitchygames/events/joystick.py`

### 68. ControllerEventManager Keys Controllers by Device Index but Routes Events by Instance Id
- **Description**: `ControllerEventManager.__init__` and `on_controller_device_added_event` stored each proxy under its device index but the axis, button, touchpad, sensor and removal handlers looked proxies up by `event.instance_id`; after a reconnect the lookup raised `KeyError` or reached the wrong controller
- **Status**: Resolved (duplicate of #181, resolved there)
- **Priority**: Medium
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 6)
- **Date Reported**: 2026-10-19
- **Date Resolved**: 2026-10-22
- **Details**: Was pinned by `tests/events/test_events_integration.py::TestEventIntegration::test_reconnected_controller_event_through_engine` (a strict xfail, now a passing test). The joystick demo's controller-mode tab code went away with the demo's rewrite (#185)
- **Files**: `glitchygames/events/controller.py`, `glitchygames/examples/joystick_demo.py`

### 185. The Joystick Demo Branched on an Input Mode, Built Its Own Managers and Had Dead Code
- **Description**: `examples/joystick_demo.py` (1,422 lines) re-checked an `input_mode` string in about ten methods, read the managers' dicts as `Any` (12 ANN401 sites), used `hasattr` and private reads (`_buttons`, `_device_id`), and built its own joystick and controller managers, so it never got hotplug events
- **Status**: Resolved
- **Priority**: Low (a demo)
- **Reporter**: Found auditing the demo for the unified input devices plan
- **Date Reported**: 2026-10-22
- **Date Resolved**: 2026-10-22
- **Root Cause**: The demo predated the engine's devices: `Scene` has no `game`, so `_get_device_manager`'s engine branches never ran, and its `TextSprite` got `game=self` (the scene, #178 item 13), so it made its own managers (hence `_cleanup_stale_joysticks`, `_add_new_controllers` and a per-frame device-count fallback); `on_controller_device_added/removed_event` set the controller count from `joystick_count()`; its `input_mode` defaults disagreed (`'controller'`, `'joystick'`, `'Not Found'`); `on_left_mouse_button_up/down` lacked the `_event` suffix (never called) and called a `post_game_event` scenes do not have, so `on_pew_pew_event` / `on_recharge_event` were dead; `--time` and `-v/--version` were never read; `_draw_text` was an empty stub; `ShapesSprite.use_gfxdraw` was always False (dead gfxdraw branches); `render()` wrapped its tiles at `i % 20 == 0` (a new row after the first tile) and `load_resources` read `Path('resources')` relative to the working directory (no tiles in the package); `Game.__init__` blocked CONTROLLER_EVENTS itself; the header's FPS was the class attribute `Game.FPS` (always 0)
- **Solution**: Rewritten on `Scene.input_devices` (about 310 lines): one column per device (name, GUID, instance id, device index, event layer, then that layer's axes, held buttons and hats), drawn every frame from the snapshot, a header with the input mode, the last device change (`on_input_device_added/removed`) and the last input event with the handler it reached. No mode branches, no `Any`, no `hasattr`, no private reads, no managers of its own; the shapes, tiles, tabs, arguments and dead handlers are gone
- **Tests**: `tests/examples/test_joystick_demo.py` (the drawn readout checked pixel by pixel on stand-in devices, hot-plugging, each handler, `main()` run headless): 100% line and branch coverage
- **Files**: `glitchygames/examples/joystick_demo.py`

### 183. Bitmappy's AI Timeout Setup Did Nothing, and Its Ollama Config Broke Every Ollama Request
- **Description**: After building its aisuite client, the AI worker set provider timeouts through `client._providers` and `provider.client._client` (`_configure_ollama_provider`, `_configure_client_timeouts`, `_apply_client_timeouts`, `_configure_provider_client_timeout` in `glitchygames/bitmappy/ai_worker.py`). aisuite 0.2.0's `Client` has no `_providers` (its public dict is `providers`), so the setup only logged `Client does not have _providers attribute` (seen in #47's verification) and set nothing. Separately, the ollama provider config held `request_timeout` and `read_timeout` next to `timeout`; aisuite's `OllamaProvider` passes its config to `openai.OpenAI`, which raised `TypeError: OpenAI.__init__() got an unexpected keyword argument 'request_timeout'` when the first request created the provider, so every request to an `ollama:` model failed
- **Status**: Resolved
- **Priority**: Medium (High for `ollama:` models; the default Anthropic model already got its timeout through the client's config, #6)
- **Reporter**: Found typing the last Bitmappy `typing.Any` parameters (ANN401, `plans/2026-10-20-lint-ignores-cleanup.md` Phase 4)
- **Date Reported**: 2026-10-22
- **Date Resolved**: 2026-10-22
- **Root Cause**: aisuite creates each provider lazily, on the first request that names it, from the client's `provider_configs` entry, so `Client.providers` is empty after construction: no step after it can reach a provider, under either name. Only the configuration passed to `Client` (or `Client.configure`) can carry a timeout, and its keys go straight to the vendor SDK's client constructor
- **Solution**: The post-construction timeout functions are removed. `_create_ollama_config` returns `{'ollama': {'timeout': seconds}}` only (the download timeout when the model must be downloaded first, from `_get_provider_timeout_value`), merged with `{'anthropic': {'timeout': AI_TIMEOUT}}` in the config `_initialize_ai_client` passes to `aisuite.Client`
- **Tests**: `tests/tools/test_ai_worker.py` (`TestProviderTimeouts`: a real `aisuite.Client` from `_initialize_ai_client`, no providers before a request, and the Anthropic and ollama providers created offline from its config have SDK clients with the expected timeouts; the ollama one raised `TypeError` before the fix), `tests/tools/test_bitmappy.py` (`TestProviderConfigTimeouts`), `tests/tools/test_bitmappy_state.py` (`TestClientProviderTimeouts`)
- **Files**: `glitchygames/bitmappy/ai_worker.py`

### 167. Crash Logs Name the Wrong Scene
- **Description**: `GameEngine._resolve_scene_name_for_error` reads `scene_manager.current_scene`, which SceneManager does not have (it has `active_scene`): a crash in the first scene is logged as 'None', and one after a switch names the old scene
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Details**: Was pinned by `tests/engine/test_engine_lifecycle.py::test_start_method_error_message_with_current_scene`, `..._with_previous_scene` (strict xfails, now passing tests). Also pinned then: #74 (`test_command_line_debug_levels_enable_debug_events`)
- **Files**: `glitchygames/engine/game_engine.py`
- **Date Resolved**: 2026-10-22
- **Solution**: Found by the defensive-lookup audit (`getattr` with a default hid the missing attribute): the scene manager's `active_scene` and `previous_scene` are read directly, so the log names the scene that was running, else the one before it

### 182. A Drag Handler That Changed the Mouse State Crashed the Drag
- **Description**: `MouseEventProxy.on_mouse_motion_event` walked `mouse_state.values()` while calling the drag handlers, so a handler that led to a button press or release (a new `mouse_state` entry) raised `RuntimeError: dictionary changed size during iteration`. Next to it, every motion computed an unused `_has_down` (a generator over the mouse state, in a try/except for that same RuntimeError) and bumped two counters nothing read
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found removing per-frame work from the drag path (2026-10-22)
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/events/mouse.py`
- **Date Resolved**: 2026-10-22
- **Solution**: The drag loop walks a snapshot (`tuple(self.mouse_state.values())`); the unused diagnostics are gone (their test, which only exercised the dead try/except, now tests the real case: `TestMouseEventProxyMotionWithCollision::test_a_drag_handler_that_presses_another_button_does_not_break_the_drag`)

### 179. `HashableEvent` Stored Its Hash as an Event Field
- **Description**: `HashableEvent.__init__` stored `self.__hash`, which lives in `__dict__` as `_HashableEvent__hash`, so every event showed a junk field: in iteration, `len()` (5 for a 3-field event), `dict(event)` and JSON. The hash covered only the type and attribute names, and the engine (`GameEngine` dispatch) built events as `HashableEvent(type)` and filled them in afterwards, so its events all hashed alike per type, and an engine-built event compared unequal to the same event built whole (the stored hashes differed)
- **Status**: Resolved
- **Priority**: Medium (events exist to be hashed and serialized: API mechanics, replays)
- **Reporter**: Found reviewing `HashableEvent` for the ANN401 typing work
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/events/base.py`, `glitchygames/engine/game_engine.py`
- **Date Resolved**: 2026-10-22
- **Solution**: Nothing but the type and fields is stored; `__hash__` hashes the current content (unhashable values, such as a game event's lists and dicts, by their contents; recursion guarded as `__eq__` is), so equal events hash alike however they were built or changed. The engine builds events with the constructor. Tests: `tests/events/test_events_core.py::TestHashableEventIdentity`

### 180. Key Chords Never Forgot Released Keys
- **Description**: `KeyboardEventProxy` tracked keys by the whole event's items, so a KEYUP (a different type) never replaced its KEYDOWN: once pressed, a key stayed "down" in every later chord (press and release A, press B: the chord said A and B). The chord handler also wrote `keys_down` into the event it was handed, so stored events held tuples containing themselves (why `HashableEvent.__eq__` needed a recursion guard)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found fixing #179
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/events/keyboard.py`
- **Date Resolved**: 2026-10-22
- **Solution**: Keys are tracked by key code (each key's latest event, in last-pressed order); the keys down are the held keys' KEYDOWN events. A chord up lists the keys still held (the released key is the event itself); two tests that expected the released key among them were changed to that. The event is no longer changed (nothing read `keys_down`; the keys reach the game as the chord's argument). Tests: `TestKeyboardEventProxyChords::test_a_released_key_is_not_in_a_later_chord`, `test_a_released_key_is_not_down_in_its_own_chord_up`, `test_a_key_pressed_again_is_last_in_the_chord`

### 19. Ruff PLW0717: 102 Try Blocks Too Broad
- **Description**: ruff 0.17's `too-many-statements-in-try-clause` (PLW0717, max 5) flags 102 existing try blocks across `glitchygames/`, `scripts/`, and `tests/`
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found while fixing the pre-push hooks
- **Date Reported**: 2026-10-15
- **Details**: Broad try blocks can catch exceptions from statements that were never expected to raise, hiding bugs. Each needs the try narrowed to the statements that can raise, with tests run per file. Re-enable with `uv run ruff check --select PLW0717 glitchygames tests scripts` to list them.
- **Date Resolved**: 2026-10-22
- **Solution**: Every site narrowed (36 outside Bitmappy on 2026-10-21, the last 60 in Bitmappy on 2026-10-22) and the ignore removed from `pyproject.toml`. Each `try` holds only what can raise what it catches; deliberate boundaries (the engine's `start()`, thread and HTTP/AI-client boundaries, file loads, undo/redo, draw paths that must never crash the editor) keep their broad catch around one helper call. No suppressions. Narrowing found the bugs in #175 (fixed) and #176-#178

### 175. Bugs Fixed While Narrowing the Try Blocks
- **Description**: Bugs the broad try blocks hid or sat next to: (1) Bitmappy's new-canvas dialog accepted `0x16`/`16x0` (`ZeroDivisionError`, crashing the editor) and `-4x4` (`pygame.error: Invalid resolution for Surface`); (2) a `ValueError` while building the new canvas was logged as "Invalid dimensions format"; (3) a slider failure after sampling a frame's colour was reported as a sampling error; (4) the AI manager left temp files behind when saving or reading the sprite, the frame or the strip failed, and when an example file was unreadable; (5) the AI worker answered an earlier request a second time (with an error) when the queue's `get()` failed after it; (6) a `ValueError` after `BitmappySprite.load`'s factory call silently re-read the file the old static way
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found narrowing the broad try blocks (BUGS.md #19)
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/bitmappy/editor.py`, `film_strip_sprite.py`, `ai_manager.py`, `ai_worker.py`, `glitchygames/sprites/bitmappy_sprite.py`
- **Date Resolved**: 2026-10-22
- **Solution**: (1) the size parser refuses non-positive sizes (logged as invalid input); (2), (3), (6) the try holds only the parse/sample/factory call, so other errors propagate; (4) temp files are removed in `finally` (or by `_write_temporary_toml_file` on a failed write); (5) the request is reset every iteration. Tests: `TestCanvasRedrawInTheRealEditor::test_non_positive_dimensions_keep_the_canvas`, `test_a_failure_building_the_canvas_is_not_reported_as_bad_dimensions`, `TestFilmStripSpriteColorSampling::test_a_slider_failure_is_not_reported_as_a_sampling_error`, the `test_save_failure_leaves_no_temporary_file` pair, `TestLoadTempTomlAsExample`, `TestRunAiWorker::test_queue_error_after_a_request_does_not_answer_it_again`, `TestBitmappySpriteLoadWithFactory::test_load_does_not_fall_back_when_converting_the_loaded_sprite_fails`

### 158. `BitmappySprite.load` Had a Branch Only a Mock Could Reach
- **Description**: `if current_frame and hasattr(current_frame, 'surface')`: `SpriteFrame` has no `surface`, so only the mocked factory's Mock frames reached it; real loads always copied the AnimatedSprite's image
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/sprites/bitmappy_sprite.py`
- **Date Resolved**: 2026-10-22
- **Solution**: The branch is removed; the load copies the image

### 159. A PaddleSlap Test Wrote High Scores to the Real Save Directory
- **Description**: `test_game_over_triggered_when_all_balls_dead` saved through the real save path
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Files**: `tests/game_objects/`
- **Date Resolved**: 2026-10-22
- **Solution**: It saves under tmp_path

### 160. 14 Tests Were Never Collected
- **Description**: `tests/sprites/test_rgba_auto_detection.py` named them `testneeds_alpha_channel_*` and `testconvert_pixels_*`, which pytest does not collect
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found moving the tests off the shared pygame mocks onto the real display
- **Date Reported**: 2026-10-22
- **Files**: `tests/sprites/test_rgba_auto_detection.py`
- **Date Resolved**: 2026-10-22
- **Solution**: Renamed `test_...`; all 14 pass

### 156. The Default Font Is Looked Up Among the Machine's System Fonts
- **Description**: `FontManager` (and `ui/inputs.py`, two examples) load `SysFont('arial')` and friends, so pygame scans the system's fonts with fontconfig (`/usr/X11/bin/fc-list` on a Mac with XQuartz) under a short timeout. Under load the scan times out with a UserWarning ("System fonts cannot be loaded"), which the suite turns into a failure (`TestClearWithoutStrips::test_new_strips_are_made`, 2026-10-22, during a concurrent serial run), and text renders in whatever "arial" each machine has although the project bundles Bitstream Vera
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found running two full suites at once
- **Date Reported**: 2026-10-22
- **Details**: Text width depends on the font, so text sprites' rects (and any trace or test that measures them) can differ between machines. A fix: load the bundled Vera by default and use system fonts only when a game names one
- **Files**: `glitchygames/fonts/font_manager.py:261`, `:317`, `glitchygames/ui/inputs.py:96`
- **Date Resolved**: 2026-10-22
- **Solution**: The default font is the bundled Bitstream Vera (`DEFAULT_FONT_NAME = 'Vera'`, `bundled_font_path`), loaded from its file with no system font scan, for FontManager, `--font-name`, `ui/inputs.py` and Bitmappy (its options and slider labels had named 'arial' and 'Courier'); a game naming another font still gets SysFont. Also fixed: the PyInstaller fallback always loaded size 12, and `compare_font_systems` crashed on a real pygame.font font. Tests: `tests/fonts/test_font_manager.py` (with fontconfig made unavailable), `TestBitmappyFonts`. No golden trace or replay changed

### 146. Canvas Panning Showed Nothing While Held, Lost Paint and Leaked Between Sprites
- **Description**: Ctrl+Shift+Arrow panning: the renderer showed the pan only after key-up (it checked a flag only a dead first draft set); releasing Ctrl or Shift before the arrow never committed (canvas and frame out of step); each pan shifted the pixels captured before the frame's first pan, so paint made after it vanished; loading another sprite kept the panning state, carrying the old sprite's pixels into the next pan; a pan was not undoable; the fill was RGB magenta inside RGBA pixel data
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the dead-code audit follow-ups
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/bitmappy/panning.py` (new), `animated_canvas.py`, `frame_operations.py`, `canvas_interfaces.py`, `editor.py`, `history/commands.py`
- **Date Resolved**: 2026-10-22
- **Solution**: Each pan step writes the moved pixels into the frame (canvas, frame, film strip and saves always agree); a gesture runs from the first press until an arrow, Ctrl or Shift key comes up and becomes one undo step (`CanvasPanCommand`); loading or a new canvas ends it; the fill matches the pixel data. The dead first draft (shadowed since the 2025-10-25 panning commit) and `BitmapEditorScene.deflate` are deleted. Tests: `tests/tools/test_canvas_panning.py::TestPanningInTheRealEditor` (real editor and key events). Behaviour change: pixels pushed off the edge come back only through undo once a gesture ends. README documents Ctrl+Shift+Arrow

### 147. Controller Triangles Over Film Strip Frames Never Drew
- **Description**: `draw_multi_controller_indicators_new` read `parent_scene.film_strip_controller_selections`, which moved to `editor.controller_handler`, and the data had changed from a list per animation to a dict by controller id; its test faked the old shape
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the dead-code audit follow-ups
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/bitmappy/film_strip_rendering.py`
- **Date Resolved**: 2026-10-22
- **Solution**: It reads `controller_handler.film_strip_controller_selections`. Tests: `TestControllerIndicatorsInTheEditor` (real editor and controllers, real pixels). The superseded triforce indicator and uncalled film strip wrappers are deleted

### 148. Slider Click-Away Commits Moved the Slider but Not the Colour, and Skipped Alpha
- **Description**: Clicking away to commit typed slider text set only the slider value (the colour well and canvas kept the old colour), and the alpha text box was left out of click-away commits, so it stayed active and kept taking keystrokes
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the dead-code audit follow-ups
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/ui/sliders.py`, `glitchygames/bitmappy/slider_manager.py`, `editor.py`
- **Date Resolved**: 2026-10-22
- **Solution**: Enter and click-away share `SliderSprite.commit_text`, driven over all four channel sliders. Tests: `TestClickAwayCommitInTheRealEditor`

### 149. Controller Painting Ignored the Alpha Slider
- **Description**: `SliderManager.get_current_color` returned RGB only, so controller painting dropped the alpha slider while mouse painting used RGBA; its "already this colour" check compared RGBA with RGB, never matched, and recorded every repeat paint for undo
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the dead-code audit follow-ups
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/bitmappy/slider_manager.py`
- **Date Resolved**: 2026-10-22
- **Solution**: It returns RGBA. Tests: `TestControllerPaintColorInTheRealEditor`. Also: one `apply_color` for every colour change, one channel formatter and parser, the sliders' duplicate indicator drawing (at each slider's top-left) removed, dead slider code deleted

### 145. A Serial Run of the World and Replay Tests Segfaults in a Live-Voice Test
- **Description**: `uv run pytest tests/world tests/replay -n 0 -p no:randomly` segfaults in `tests/replay/test_playback_scope.py::TestLiveVoicesThroughAPlayback::test_a_live_scenes_voice_survives_the_scope` while the SDL audio thread runs (Python frame `randomness.stream_seed`), then hangs in the signal path (`quit_game`); the test and its file pass alone
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Found by the guards agent and the serial memory run
- **Date Reported**: 2026-10-22
- **Details**: A serial memory run hung at the same place for 3 hours. Cause: `reserve_live_voice_pool` grew the mixer by the pool size for every `GameEngine` made; once pygame stayed initialized across tests, the run's mixer reached ~1,500 channels, and each `set_num_channels` reallocated pygame's channel table while SDL's audio thread was still finishing an earlier test's live voice on it (heap corruption, crashing in unrelated code: `stream_seed`, `json` decoding)
- **Files**: `tests/conftest.py`, `glitchygames/audio/live.py`
- **Date Resolved**: 2026-10-22
- **Solution**: `reserve_live_voice_pool` remembers the channel count it grew the mixer to and reuses the pool when the mixer still has it (a restarted mixer grows again); the test conftest stops every mixer channel after each test, so no sound plays into the next. Tests: `TestPoolReservation::test_reserving_again_on_the_same_mixer_reuses_the_pool`, `test_a_restarted_mixer_gets_its_pool_again`. The serial world and replay run passes (941), the mixer ending at 12 channels instead of 1,492

### 139. Switching Animation on Frame 0 Kept the Old Image
- **Description**: `_update_surface_and_mark_dirty` compared only the frame index; FrameManager resets the frame to 0 on an animation change, so `set_animation('walk')` then `set_animation('jump')` kept walk's image (and did not mark the sprite dirty)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the coverage audit follow-ups
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/sprites/animated.py`
- **Date Resolved**: 2026-10-22
- **Solution**: It tracks `(animation, frame)` (`_last_drawn_frame`). Tests: `TestAnimationSwitchUpdatesImage`

### 140. AnimatedSprite Hashed Every Frame's Pixels on Each Frame Advance
- **Description**: `update()` ran `_debug_frame_info` (str(frame.pixels) and a SHA-256, or `surfarray.array3d`) on every frame advance with debug logging off
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the coverage audit follow-ups
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/sprites/animated.py`
- **Date Resolved**: 2026-10-22
- **Solution**: It runs only when the logger is enabled for DEBUG. Tests: `TestFrameDumpOnlyWithDebugLogging`

### 133. An AnimatedSprite's Image Loses Per-Pixel Alpha and Magenta Transparency
- **Description**: `_update_surface_and_mark_dirty` -> `_get_current_surface` -> `_create_optimized_surface` (`sprites/animated.py` ~706-733) rebuilds the image of any frame with a `pixels` list (every TOML frame) as a plain Surface with no SRCALPHA and no colorkey; its "RGBA pixel" branch equals the RGB one. With `examples/foo2.toml`, the frame image has alpha 137 but `sprite.image` has 255 and no colorkey
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the 100% coverage audit
- **Date Reported**: 2026-10-22
- **Details**: Very likely the cause of the CLAUDE.md caveat that TOML AnimatedSprites keep magenta opaque. A fix changes visible-pixel hitboxes and so the golden traces and replays; needs a decision
- **Files**: `glitchygames/sprites/animated.py:706-733`
- **Date Resolved**: 2026-10-22
- **Solution**: `_create_optimized_surface` builds frames with pixels through `_create_surface_from_toml_pixels`, rewritten: a frame with translucent pixels gets an SRCALPHA surface (transparent pixels stored as `TRANSPARENT_MAGENTA`, alpha 0); every other frame a plain surface with magenta as its colorkey (fast blits; keyed pixels never written, whatever the destination's alpha). Tests: `TestAnimatedSpriteImageTransparency` (7, real TOML loading; dummy and cocoa). No golden trace or replay changed: traces record rect sizes and hitboxes come from `frame.image`. The CLAUDE.md caveat has another cause: the loader's `frame.image` (`pixel_utils.create_alpha_surface` keeps magenta at alpha 255; `plans/future-work.md`)

### 136. A Menu With No Item Rects Raises ValueError
- **Description**: `max()` over the items' rects raises when none has one (`menus.py:527`), which also makes 531->539 unreachable
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the 100% coverage audit
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/ui/menus.py:527`
- **Date Resolved**: 2026-10-22
- **Solution**: Items without a rect are skipped for width, heights and layout; with none the menu keeps the item's own size. Test: `TestMenuItemAddMenu::test_add_menu_whose_items_have_no_rect_keeps_the_item_size`

### 125. A Truncated APNG Upload Gave a Server Error
- **Description**: `_extract_apng_frames` caught only ValueError; APNG data cut off inside a chunk header raises `struct.error`, so `/sprites/extract-frames` answered HTTP 500 instead of `success=False, "Invalid APNG file: ..."`
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the 100% coverage audit
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/api/routes/sprites.py:513`
- **Date Resolved**: 2026-10-22
- **Solution**: `struct.error` is caught too. Test: `TestExtractFramesErrors::test_truncated_apng_is_an_unsuccessful_response`

### 126. Clearing Controller Indicators Left Them Pushing New Ones Aside
- **Description**: `VisualCollisionManager.clear_all_indicators` cleared only the main `indicators` dict; the film strip, canvas and slider dicts and their collision groups kept the cleared indicators, so a new indicator placed where one stood was still offset (15, -15)
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the 100% coverage audit
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/bitmappy/indicators/collision.py`
- **Date Resolved**: 2026-10-22
- **Solution**: Every location's dicts and groups are cleared. Tests: `TestClearAllIndicatorsClearsEveryLocation`

### 127. The Indicator Collision Summary Always Reported 0
- **Description**: `get_collision_summary` counted the legacy `collision_groups` dict, which nothing fills
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the 100% coverage audit
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/bitmappy/indicators/collision.py`
- **Date Resolved**: 2026-10-22
- **Solution**: It counts the three per-location group dicts. Tests: `TestCollisionSummaryCountsLocationGroups`

### 128. `bitmappy --font-system pygame` Crashed the Film Strip
- **Description**: The film strip's label rendering called `font.render(text, fgcolor=..., size=12)`, the freetype form; a `pygame.font.Font` raised TypeError (missing `antialias`), and the `pygame.font` branches after it could never run
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the 100% coverage audit
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/bitmappy/film_strip_layout.py`, `glitchygames/bitmappy/film_strip_rendering.py`
- **Date Resolved**: 2026-10-22
- **Solution**: One helper, `render_label_text(*, text, color)` in `film_strip_layout.py`, tells freetype fonts apart by `render_to` (as `ui/text_widgets.py` does). Tests: `TestCalculateAnimationLayouts::test_label_width_follows_the_name_with_the_pygame_font_system`, `TestLabelsWithThePygameFontSystem`

### 129. Comparing an Event With a Non-Event Raised TypeError
- **Description**: `HashableEvent.__ne__` negated `__eq__`'s NotImplemented, and Python 3.14 raises on `bool(NotImplemented)`, so `event != "x"` raised
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the 100% coverage audit
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/events/base.py`
- **Date Resolved**: 2026-10-22
- **Solution**: `__ne__` returns NotImplemented. Test: `TestHashableEventEquality::test_comparison_with_a_non_event_is_not_implemented`

### 130. Saved Action Maps Lost Every Gamepad Button in Joystick Mode
- **Description**: In joystick mode (the default) `ActionMap.to_dict()` dropped JOYBUTTONDOWN bindings, from both `controller_button=` and `joystick_button=`, so after a save and load those actions had no gamepad button
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the 100% coverage audit
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/input/action_map.py`
- **Date Resolved**: 2026-10-22
- **Solution**: They are saved as `'JoyButtonDown'` and restored with `joystick_button=`. Test: `TestPersistence::test_joystick_mode_gamepad_buttons_survive_a_round_trip`

### 131. Nested Menus Crashed on Mouse Motion, and Leaving a Menu Entered Its Submenus
- **Description**: `MenuItem.on_mouse_motion_event`, `on_mouse_enter_event` and `on_mouse_exit_event` iterated the `menu_items` dict's keys (names), calling handlers on strings (AttributeError for any nested submenu); the exit handler also sent submenus an enter event
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the 100% coverage audit
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/ui/menus.py` (~679, 712, 744)
- **Date Resolved**: 2026-10-22
- **Solution**: They iterate `.values()`, and exit sends exit. Tests: `tests/ui/test_menubar_events.py::TestMenuItemNestedSubMenus`; the widget tests that worked around it with mock dict keys were rewritten

### 132. `Sprite.break_when` Registered the Wrong Type and Broke on Every Sprite
- **Description**: `break_when(sprite_type=X)` registered the class it was called on instead of X; with any type registered, `Sprite.__init__` called `breakpoint()` for every sprite (and again on a match), and logged `<any>`
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the 100% coverage audit
- **Date Reported**: 2026-10-22
- **Files**: `glitchygames/sprites/sprite.py`
- **Date Resolved**: 2026-10-22
- **Solution**: It registers `str(sprite_type)`, breaks only on a match and logs the matched type. Tests: `TestSpriteBreakWhen`

### 114. Clearing the Voice Assistant's Conversation Mid-Request Leaves a History Starting With an Answer
- **Description**: `_ask_ai` runs on a background thread; a `clear_conversation()` on the main thread while it waits empties the history, and the answer is then appended to the empty history, which starts with an assistant message
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found fixing #105 (by reading)
- **Date Reported**: 2026-10-21
- **Files**: `glitchygames/audio/voice_assistant.py`
- **Date Resolved**: 2026-10-22
- **Solution**: Every change to the history holds `self._lock` (never across the network call); an answer is added only while its question is still the last entry, and trimming deletes in place. Test: `TestPipeline::test_clearing_mid_request_leaves_no_answer_without_its_question` (a successful and a failed reply)

### 121. Unpickling a HashableEvent Fails
- **Description**: `HashableEvent.__setstate__` (`events/base.py`, about line 551) calls `hash((self.type, self.__dict__))`, and a dict cannot be hashed
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found fixing #88 (by reading, not run)
- **Date Reported**: 2026-10-21
- **Files**: `glitchygames/events/base.py`
- **Date Resolved**: 2026-10-22
- **Solution**: Confirmed: `__reduce__` rebuilt the event without its `type` and `__setstate__` hashed a dict. Both now rebuild it as `__init__` does, so a restored event equals the original and hashes the same. Test: `TestHashableEventCopyAndPickle::test_pickle_round_trip_keeps_attributes_equality_and_hash`

### 122. After a `--headless` Restart, the Scene Manager Drew on the Closed Display
- **Description**: A scene manager made before the engine (pygame started first) kept the surface of the display it saw then. When `--headless` restarted a display on a real video driver, the engine opened a new one but never handed it over, so the first scene's background blit failed with "Surface is not initialized"
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found running the suite with `SDL_VIDEODRIVER=cocoa` (the dummy driver never restarts, and reuses its display surface)
- **Date Reported**: 2026-10-21
- **Files**: `glitchygames/engine/game_engine.py` (`initialize_display`)
- **Date Resolved**: 2026-10-21
- **Solution**: `initialize_display` gives the scene manager the display it opens. Test: `TestHeadless::test_the_scene_manager_draws_on_the_display_the_engine_opens` (closes the display first, as the restart does, on any driver)

### 123. The Status Bar and Debug Overlay Stayed in the Frame on Displays With Per-Pixel Alpha
- **Description**: `SceneManager._show_frame` draws a shaken or overlaid frame on the display, flips, then blits its clean copy back. On real video drivers (cocoa) the display has per-pixel alpha, so the copy blended instead of copying: pixels below alpha 255 kept the replay status bar or debug overlay in the frame screenshots and dirty-rect updates use, and a SCREEN shake blended such pixels into the border fill
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found running the suite with `SDL_VIDEODRIVER=cocoa` (the dummy display has no alpha channel, so the blit copied)
- **Date Reported**: 2026-10-21
- **Files**: `glitchygames/scenes/scene.py` (`_show_frame`)
- **Date Resolved**: 2026-10-21
- **Solution**: The clean copy's blending is turned off (`set_alpha(None)`), so it is copied back and shifted exactly. Tests: `TestWatched::test_the_clean_frame_comes_back_exactly_on_a_display_with_per_pixel_alpha`, `TestScreenShakePresentation::test_shaken_frame_on_a_display_with_per_pixel_alpha_is_copied_not_blended` (per-pixel alpha screens, any driver)

### 124. An Opaque RGBA PNG Was Treated as Transparent
- **Description**: `FileIOManager._detect_png_transparency` took an alpha channel to mean transparency, so an RGBA PNG whose pixels are all opaque (as paint programs often export) was handled as transparent
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found running the suite with `SDL_VIDEODRIVER=cocoa` (a test's "opaque" PNG took the display's alpha format there)
- **Date Reported**: 2026-10-21
- **Files**: `glitchygames/bitmappy/file_io.py`
- **Date Resolved**: 2026-10-21
- **Solution**: Transparent means a pixel below `ALPHA_TRANSPARENCY_THRESHOLD`, the test the colour sampler uses. Test: `test_alpha_channel_with_only_opaque_pixels_has_no_transparency`; the test helper writes PNGs at explicit depths

### 116. AI Strip Examples Held Only the Strip's First Frame
- **Description**: `AIManager._load_temp_toml_as_example` extracted only the first `pixels` block of the saved strip and labelled it static, so the `selected_strip` example sent to the AI had frame 0's pixels with every frame's colours
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found rewriting the skipped AI strip integration tests
- **Date Reported**: 2026-10-21
- **Files**: `glitchygames/bitmappy/ai_manager.py`, `glitchygames/ai/sprite_generator.py`
- **Date Resolved**: 2026-10-21
- **Solution**: The example is parsed with tomllib: an animated strip becomes `sprite_type 'animated'` with every frame in `animations` and the raw TOML in `raw_content`; the formatter checks `animations` before `pixels`, so an animated example is never rebuilt as one static sprite. Test: `test_ai_strip_context_includes_every_frame` (was a strict xfail)

### 117. "Loading Sprite Anyway" After the Last AI Retry Loaded Nothing
- **Description**: After the last retry the log and text box said the sprite was being loaded anyway, but `_load_ai_sprite` rejects the same content, so nothing loaded
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found fixing #93
- **Date Reported**: 2026-10-21
- **Files**: `glitchygames/bitmappy/ai_manager.py:486-500`
- **Date Resolved**: 2026-10-21
- **Solution**: It no longer tries; the log and text box say the sprite was not loaded. Test: `test_invalid_response_after_the_last_retry_says_it_was_not_loaded`

### 118. Restoring a Slider's Value on the Hex Tab Wrote It in Decimal
- **Description**: Cancelling a slider edit on the hex tab wrote the original value back as decimal text (255 as "255", not "FF")
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found fixing #110 item 3
- **Date Reported**: 2026-10-21
- **Files**: `glitchygames/bitmappy/slider_manager.py`, `glitchygames/ui/sliders.py`
- **Date Resolved**: 2026-10-21
- **Solution**: Restored values are written in the active format. Tests: `test_restoring_on_the_hex_tab_writes_hex`, `test_slider_restore_original_value_uses_the_active_format`

### 87. Images Dropped onto the Film Strip Never Become Frames
- **Description**: `FilmStripSprite._convert_image_to_sprite_frame` calls `pygame.surfarray.array4d`, which pygame-ce does not have; the AttributeError is caught at line 698, so every image dropped on the film strip converts to None and the drop silently does nothing
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: The existing drop tests mock `_convert_image_to_sprite_frame`, which hid it. Pinned by the strict xfail `tests/tools/test_film_strip_sprite.py::TestFilmStripSpriteImageDrops::test_png_converts_to_a_frame_of_the_canvas_size`. Lines 666, 678-696 and 702 are reachable only once this is fixed
- **Files**: `glitchygames/bitmappy/film_strip_sprite.py:677`
- **Date Resolved**: 2026-10-21
- **Solution**: The pixels are read with `surfarray.array3d` plus `array_alpha` (pygame-ce has no `array4d`), row-major; the strict xfail passes, and `test_png_with_alpha_keeps_its_alpha_and_pixel_order` and `test_dropped_png_replaces_the_frame` cover the real conversion

### 88. `HashableEvent.get` and `in` Raise, So Film Strip C and V Keys Crash
- **Description**: `HashableEvent` subclasses `UserDict` but never sets `self.data`, so its `get` and `in` raise AttributeError (a pygame Event has no `get` at all). `FilmStripSprite.on_key_down_event` reads `event.get('mod', 0)`, so any C or V key reaching it raises
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Pinned by the strict xfail `tests/tools/test_film_strip_sprite.py::TestFilmStripSpriteCopyPasteKeys::test_real_hashable_ctrl_c_event_copies_the_frame`. Other code calling `.get` or `in` on a HashableEvent fails the same way; fix `HashableEvent` (set `self.data` or read attributes) rather than each caller
- **Files**: `glitchygames/events/base.py`, `glitchygames/bitmappy/film_strip_sprite.py:443`, `:453`
- **Date Resolved**: 2026-10-21
- **Solution**: `HashableEvent` overrides `__contains__`, `__iter__` and `get` to read its attributes (`__dict__`), so `items()` follows; its hash, `keys()` and what recordings hold are unchanged. Tests: `TestHashableEventMappingAccess` in `tests/events/test_events_core.py`; the copy/paste key tests use real HashableEvents and the strict xfail passes

### 89. Loading a PNG Through the Load Dialog Fails
- **Description**: `AnimatedCanvasSprite` calls `self._convert_png_to_bitmappy`, which only exists on the file I/O delegate (`file_io.py:151`), so loading a PNG through the Load dialog ends in "Error loading sprite"
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Found by the canvas tests; not pinned by an xfail
- **Files**: `glitchygames/bitmappy/animated_canvas.py:1398`, `glitchygames/bitmappy/file_io.py:151`
- **Date Resolved**: 2026-10-21
- **Solution**: The canvas converts through the editor's file I/O delegate (`parent_scene._file_io._convert_png_to_bitmappy`) and refuses with a clear ValueError without an editor. Tests: `test_png_loads_through_the_load_dialog` (a real PNG through a real FileIOManager), `test_png_without_an_editor_is_refused`

### 90. Unconfirmed Deletes Crash Instead of Opening the Confirmation Dialog
- **Description**: `FilmStripCoordinator._show_delete_animation_confirmation` and `_show_delete_frame_confirmation` call `self.game_engine.scene_manager.switch_to_scene(...)`, but `FilmStripCoordinator` never sets `game_engine`, so every unconfirmed delete raises AttributeError and no dialog opens. `film_strip_events.py:830` also calls `parent_scene._show_delete_frame_confirmation(...)`, which `BitmapEditorScene` does not have (only the coordinator does), so the frame-removal button would raise too (found by reading, not run)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Pinned by the strict xfail `tests/tools/test_film_strip_coordinator.py::test_delete_animation_dialog_opens_from_a_new_coordinator`; the dialog-callback tests give the coordinator a `game_engine` explicitly
- **Files**: `glitchygames/bitmappy/film_strip_coordinator.py:1007`, `:1077`, `glitchygames/bitmappy/film_strip_events.py:830`
- **Date Resolved**: 2026-10-21
- **Solution**: Both confirmation dialogs open by setting `editor.next_scene`, as the Save/Load/New dialogs do (the switch happens at the frame's end, so the rest of the event batch does not land on the dialog); the film strip's removal button calls the coordinator's `_show_delete_frame_confirmation`. The strict xfail passes; `test_delete_frame_dialog_opens_from_a_new_coordinator` added

### 91. Events the Delete Confirmation Dialog Does Not Take Crash the Editor
- **Description**: `BitmapEditorScene.handle_event` calls `super().handle_event`, which no parent class defines, so any event the confirmation dialog does not consume raises AttributeError (lines 1406-1410 can never run)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Found by the editor tests
- **Files**: `glitchygames/bitmappy/editor.py:1404`
- **Date Resolved**: 2026-10-21
- **Solution**: The `super().handle_event` call (no parent defines it) is removed. Tests in `test_bitmappy_editor_scene.py`. Note: nothing calls `BitmapEditorScene.handle_event` or sets `confirmation_dialog`, so the method looks dead

### 94. Deleting a Frame Before the Shown Frame Moves the Canvas Back Two Frames
- **Description**: When a frame before the shown frame is deleted, `current_frame` is decremented twice: in `_stop_animation_and_adjust_frame_before_deletion` and again in `_adjust_canvas_frame_after_deletion`. `FrameDeleteCommand.execute()` and `FrameAddCommand.undo()` both take this path. In a 3-frame animation showing frame 2, deleting frame 0 shows index 0 instead of 1
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Pinned by the strict xfail `tests/tools/test_history_commands.py::TestFrameDeleteCommand::test_deleting_frame_before_shown_frame_keeps_showing_it`
- **Files**: `glitchygames/bitmappy/history/commands.py:1309-1314`, `:1329-1333`
- **Date Resolved**: 2026-10-21
- **Solution**: `_adjust_canvas_frame_after_deletion` only clamps and shows the frame; the one step back happens before the deletion. The strict xfail passes, with tests for deleting the shown middle frame and undoing an add before the shown frame

### 96. Controller Lookups Pass a Controller Id Where an Instance Id Is Expected
- **Description**: `MultiControllerManager.get_controller_info` is keyed by SDL instance id (`self.controllers.get(instance_id)`), but `visual_indicators.py:53` and `:102` (and the callers `event_handler.py:187`, `:191`, `:588`, `canvas_operations.py:482`, `history/commands.py:1125`, `:1210`) pass a controller id. When the two differ (after a reconnect, say), no canvas or mode indicator is placed, or another controller's info is used
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Pinned by the strict xfail `tests/tools/test_visual_indicators.py::TestUpdateControllerCanvasVisualIndicator::test_controller_whose_instance_id_differs_gets_indicator`. A fix: look up by controller id (`ControllerEventHandler.find_controller_info`). 2026-10-21: `visual_indicators.py` now looks up by controller id (`handler.find_controller_info`), which fixes every caller listed (the xfail passes, and `test_controllers_with_swapped_instance_ids_get_their_own_colors` guards the mode colours); one more instance remains, `canvas_interfaces.py:1136`
- **Files**: `glitchygames/bitmappy/controllers/visual_indicators.py:53`, `:102`, `glitchygames/bitmappy/controllers/manager.py:283`
- **Date Resolved**: 2026-10-21
- **Solution**: `visual_indicators.py` and `canvas_interfaces.py:1133-1138` look controllers up by controller id (`find_controller_info`); every caller passing a controller id is covered, and the two remaining `get_controller_info` callers pass instance ids. Tests with swapped instance ids check each controller gets its own indicator and colour

### 98. Film Strips Are Never Refreshed After an Undo or Redo Sync
- **Description**: `BitmapEditorScene` checks `hasattr(self, 'update_film_strips_for_frame')`, which is always False (only `FilmStripCoordinator` has that method), so the refresh after an undo/redo sync never runs
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Found by the editor tests
- **Files**: `glitchygames/bitmappy/editor.py:1291`
- **Date Resolved**: 2026-10-21
- **Solution**: The editor always calls `film_strip_coordinator.update_film_strips_for_frame`. `test_valid_state_forces_redraw` checks the call

### 99. Deleting an Animation Loses the Frame Selection It Computes
- **Description**: `_select_animation_after_deletion` computes and shows a clamped target frame, then calls `on_sprite_loaded`, which resets `selected_frame` and the canvas to frame 0, so the computed selection is always lost
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: A test showed frame 0 where 1 was expected
- **Files**: `glitchygames/bitmappy/film_strip_coordinator.py:870-905`, `:1252-1284`
- **Date Resolved**: 2026-10-21
- **Solution**: The strips are rebuilt first, then the computed frame is shown and selected. The delete tests check the final selection and canvas frame (they had ended on 0, expecting 1)

### 101. Drag Strokes May Never Reach Undo Through the Canvas Drag Path (Suspected)
- **Description**: `_submit_drag_pixel_changes_to_undo` runs only when `_drag_pixels` is empty, so drag strokes do not reach undo through this path
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Suspected from reading; whether drags record undo elsewhere was not checked
- **Files**: `glitchygames/bitmappy/animated_canvas.py:1229-1240`
- **Date Resolved**: 2026-10-21
- **Solution**: Confirmed real: a click-drag recorded only the click's pixel. The release submitted drag pixels only when there were none, and submitted ones went to the list the editor ignores whenever its dict holds anything. The release now merges the drag pixels into `current_pixel_changes_dict`, keeping each pixel's first old colour, so click and drag are one undo stroke; the editor's type hints now match the `(x, y) -> (x, y, old, new)` shape. Test: `test_drag_stroke_reaches_undo` (real canvas and FrameOperationManager, real event order)

### 92. Transparent Pixels of a Dropped PNG Come Out White
- **Description**: `_load_and_resize_png` flattens any image with alpha onto a white RGB surface, then `_convert_png_to_bitmappy` checks that flattened surface for `SRCALPHA` (`_detect_png_transparency`), which is always false: transparent pixels map to white, never to the magenta transparency key
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Confirmed with a 4x4 PNG whose pixel (0, 0) is transparent: the TOML maps it to (255, 255, 255). Line 176 is unreachable until fixed
- **Files**: `glitchygames/bitmappy/file_io.py:249-255`, `:274-275`
- **Date Resolved**: 2026-10-21
- **Solution**: `_detect_png_transparency` reads the alpha from the original file (scaled to the converted size so pixels line up) instead of the image already flattened onto white, so transparent pixels become magenta; `_sample_png_colors` no longer drops the flattened colour (white) from the palette, which had turned opaque white pixels transparent too. Tests in `tests/tools/test_file_io.py` (`TestConvertPngToBitmappy`, `TestDetectPngTransparency`) and `tests/tools/test_bitmappy_png_loading.py`

### 93. AI Answers Wrapped in Markdown Fences Never Load
- **Description**: `validate_ai_response` runs before `_clean_ai_response` and rejects any answer starting with ``` or containing ```toml, so a fenced answer is retried and, after the last retry, treated as an error; the cleaning step that would strip the fences never runs
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Found by the AI manager tests
- **Files**: `glitchygames/bitmappy/ai_manager.py:436`, `:537`
- **Date Resolved**: 2026-10-21
- **Solution**: `AIManager._validate_ai_content` validates the raw answer, then the fence-stripped one, and accepts either (cleaning alone can drop real content); `_process_ai_response` and `_is_ai_error_message` both use it. Test: `TestProcessAiResponse::test_fenced_valid_response_loads_without_a_retry`

### 95. Undoing a Trigger Mode Switch Does Nothing
- **Description**: `handle_trigger_input` has already switched the mode when `_track_controller_mode_change` reads the old mode, so the undo record holds the new mode twice (`('canvas', 'canvas')` instead of `('film_strip', 'canvas')`)
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Pinned by the strict xfail `tests/tools/test_controller_event_handler.py::TestControllerTriggerAxisMotion::test_a_trigger_mode_switch_records_the_old_and_new_mode_for_undo`
- **Files**: `glitchygames/bitmappy/controllers/event_handler.py:578-587`, `:748`
- **Date Resolved**: 2026-10-21
- **Solution**: `_handle_trigger_axis_motion` reads the old mode before `handle_trigger_input` switches it and passes it as `_track_controller_mode_change(old_mode=...)`; the strict xfail now passes

### 97. The Canvas Cursor Is Clamped to the Canvas's Screen Size, Not Its Pixels
- **Description**: `_canvas_move_cursor` clamps to `canvas.width` / `canvas.height`, the on-screen size, so on an 8x8 canvas drawn at 16x the D-pad can move the cursor up to x=127; the line, jump and paint code all use `pixels_across` / `pixels_tall`
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Seen with a real `AnimatedCanvasSprite` (8x8, `pixel_width=16`: `pixels_across` 8, `width` 128). The tests use a fake canvas whose two sizes agree, so they do not pin today's behaviour
- **Files**: `glitchygames/bitmappy/controllers/canvas_operations.py:437-438`
- **Date Resolved**: 2026-10-21
- **Solution**: The cursor is clamped to `pixels_across`/`pixels_tall`. Test: `TestCanvasMoveCursor::test_clamps_to_the_pixel_count_not_the_screen_size` (8x8 canvas at 16x: the cursor had reached (56, 51))

### 100. Slider Hover Crashes Before the Sliders Are Set Up
- **Description**: `_update_slider_bbox_hover` guards with `hasattr(self, bbox_attr)`, but `__init__` always sets those attributes to None, so `update_slider_hover_effects` before `setup_sliders_and_color_well` raises `AttributeError: 'NoneType' object has no attribute 'visible'` (the alpha path at line 601 checks `is not None` correctly; line 535 is unreachable)
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Reproduced by a script and by the slider manager tests
- **Files**: `glitchygames/bitmappy/slider_manager.py:532-535`
- **Date Resolved**: 2026-10-21
- **Solution**: `_update_slider_bbox_hover` checks for sliders not yet set up (`getattr(..., None)`). Test: `TestHoverEffects::test_hover_before_the_sliders_are_set_up_does_nothing`

### 102. The System Palette's Color Names Do Not Match Its File
- **Description**: The names in `palette.py:217-233` are in a different order from `color/resources/system.palette`: loading `System()` gives MAROON=(255, 255, 255), GREEN=(255, 0, 0), RED=(128, 128, 128), WHITE=(0, 0, 128); only BLACK is right
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Seen by printing every named color
- **Files**: `glitchygames/color/palette.py:217-233`
- **Date Resolved**: 2026-10-21
- **Solution**: The `System` class names are reordered to match `resources/system.palette` (the file is unchanged, so palette indexes do not move). Test: `TestBuiltinPalettes::test_system_color_names_match_their_colors`

### 103. `ColorPalette` Size Is Off by One
- **Description**: `_size` is `len - 1`, so `set_color(last_index, ...)` appends instead of replacing, `_size` is never updated after `set_color` (`get_color` cannot see appended colors), and a one-color palette has `_size == 0` (`get_color` returns magenta for every index)
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Found by the palette tests
- **Files**: `glitchygames/color/palette.py:55`, `:67`, `:87`
- **Date Resolved**: 2026-10-21
- **Solution**: `_size` is gone; `get_color`/`set_color` use `len(self._colors)`, so the last entry can be read and replaced and appended colours read back. Tests in `tests/color/test_palette.py`; the hypothesis property now checks every index reads back

### 104. Palette Files Cannot Round-Trip
- **Description**: `PaletteUtility.write_palette_to_file` writes JSON, but `load_palette_from_file` reads ConfigParser format, so a written palette cannot be loaded back
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Found by the palette tests
- **Files**: `glitchygames/color/palette.py:147-148`
- **Date Resolved**: 2026-10-21
- **Solution**: `write_palette_to_file` writes ConfigParser format (what every bundled `.palette` file and the loader use), from a ConfigParser or a dict of sections. Tests: `test_written_palette_data_loads_back`, `test_written_palette_dictionary_loads_back`

### 105. The Voice Assistant's History Breaks After 10 Questions
- **Description**: History trimming keeps the last 20 of 21 entries, so from the 11th question on the history sent starts with an `assistant` message, which providers requiring a user message first reject ("No response from AI"). A failed request also leaves the question in the history unanswered, so the next request sends two user messages in a row
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Both confirmed by tests on the messages sent; not checked against a live API
- **Files**: `glitchygames/audio/voice_assistant.py:295`, `:298-299`, `:314-316`
- **Date Resolved**: 2026-10-21
- **Solution**: Trimming drops whole user/assistant pairs from the front before the question is added, so the history always starts with a user message; a failed request removes its own question (by identity, so an earlier identical question stays). Tests in `tests/audio/test_voice_assistant.py`

### 106. The `backoff` Retry Decorator Triggers a Python 3.14 Deprecation Warning
- **Description**: `backoff`'s decorator calls `asyncio.iscoroutinefunction`, deprecated in Python 3.14 and due for removal in 3.16; applying it in the AI worker emits a DeprecationWarning (an error under the test suite's `filterwarnings=error`)
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: The AI worker tests patch `ai_worker.backoff` to None and use the no-retry path. Fix by upgrading or replacing `backoff` before 3.16
- **Files**: `glitchygames/bitmappy/ai_worker.py:549`
- **Date Resolved**: 2026-10-21
- **Solution**: `tenacity` replaces `backoff` (`ai_worker._create_ai_retry_decorator`: `stop_after_attempt(AI_MAX_RETRIES)`, `wait_exponential(multiplier=AI_BASE_DELAY, max=AI_MAX_DELAY)`, non-retryable errors raised at once, the last error re-raised). It also fixes the waits: `backoff`'s `base=AI_BASE_DELAY` (1.0) was the exponent's base, so every retry waited about 1 s; they now wait 1, 2, 4... s up to 60 s. The tests exercise real retries with the sleep recorded instead of patching the decorator away

### 107. Remote Templates Get a Trailing Newline in Their URL
- **Description**: `build()` reads the `.repo` file with `fh.readline()`, which keeps the newline, so cookiecutter receives `'url\n'` from a normal `.repo` file
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: The new test writes the file without a newline so it does not lock in the bug
- **Files**: `glitchygames/templates/game.py:26`
- **Date Resolved**: 2026-10-21
- **Solution**: `build()` strips the line it reads. The on-disk test writes `.repo` with its newline

### 108. A DualSense HID Write Error Disables the Controller's Whole Audio
- **Description**: If `device.write` raises (hidapi can, on a disconnected device), `close()` is skipped and the exception escapes `ControllerAudio.__init__`, so `for_controller` returns None for the whole controller instead of only losing the speaker
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Found by reading, not tested
- **Files**: `glitchygames/audio/controller_audio.py:134-135`
- **Date Resolved**: 2026-10-21
- **Solution**: The HID write is wrapped (`OSError`, `ValueError`: logged, returns False) with `close()` in a `finally`, so a failed speaker enable keeps the controller's audio. Tests in `tests/audio/test_controller_audio.py`

### 109. `quantize_colors_if_needed` Crashes When There Is No Room for Colors
- **Description**: When `max_colors` is no more than the slot reserved for transparency (`has_transparency=True, max_colors=1`), it raises `KeyError: None`
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the coverage push (2026-10-21, helper agents writing tests)
- **Date Reported**: 2026-10-21
- **Details**: Confirmed by running it; reachable only through direct calls with a tiny `max_colors`
- **Files**: `glitchygames/bitmappy/toml_processing.py:714`
- **Date Resolved**: 2026-10-21
- **Solution**: It raises `ValueError` naming `max_colors` and the reserved slots (the docstring documents it); production callers use 1000 and 64. Test: `TestQuantizeColorsIfNeeded::test_no_room_for_colors_raises_a_clear_error`

### 86. FastTimer Woke Most Frames 1-2 ms Late on macOS
- **Description**: FastTimer slept until 1 ms before each frame deadline, assuming a sleep wakes on time. macOS lets a normal-priority sleep run late by a quarter of its length (4 ms wakes 1.01 ms late, 16 ms 4.01 ms; measured 2026-10-21), so an ~11 ms frame sleep woke ~2.75 ms late and frames finished 1.5 ms past their deadline (60 FPS, 4 ms of work: median 1.54 ms, p90 1.85 ms). The average rate held (deadlines do not accumulate lateness); every frame's present jittered. Where sleeps wake much later (a virtual machine, a background process: a flat 85-100 ms), frames fell to about 10 FPS
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while calibrating timers for the CircleCI macOS timing failure
- **Date Reported**: 2026-10-21
- **Files**: `glitchygames/timing.py`, `glitchygames/engine/game_engine.py`, `glitchygames/recording_history.py`
- **Date Resolved**: 2026-10-21
- **Solution**: `--timer-backend auto`, the new default: the engine measures the machine's sleep delay as a constant plus a fraction of the sleep's length (`SleepModel`, `measure_sleep_model`) when it starts a paced live game, and FastTimer sizes each sleep so its predicted wake lands `sleep_granularity_ns` before the deadline, spinning the whole wait when no sleep could. Same measurement: frames on time (median 0.000 ms) at 30% CPU instead of 24%; at background priority on time at 92% CPU. A paced recording names its timer (`MeasurementRun.pacing_timer`). `--timer-backend fast` keeps the old behaviour

### 82. A Recording That Cannot Be Written Part Way Ends the Run as an Internal Error
- **Description**: An unwritable `--record-trace` (or `--rebaseline` partial, `--replay-digest`) file is refused before the run with one line and `CANNOT_WRITE_OUTPUT` (73), and a digest file that fails at the end exits 73 after the report. But a recording whose writes start failing part way (the disk fills, the file system goes away) raises `OSError` from `GameplayRecorder.record_frame` inside the frame loop, so the run exits `INTERNAL_ERROR` (70) with a traceback
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (final review fixes, item A5)
- **Date Reported**: 2026-10-20
- **Details**: Catching `OSError` around the recorder's writes and ending the run with `CANNOT_WRITE_OUTPUT` (after closing what was written) would match the up-front refusal; not done here, as the review asked for the path checks only
- **Files**: `glitchygames/recording.py`, `glitchygames/engine/game_engine.py`
- **Date Resolved**: 2026-10-20
- **Solution**: `GameplayRecorder` turns a failed write into `RecordingWriteError` (an `OSError`): it logs one line (`<path> could not be written: No space left on device`, no traceback), closes the file as far as it can (the frames before stay readable) and writes nothing more; `GameEngine.start` ends the run with `CANNOT_WRITE_OUTPUT` (73). A failure as the file is closed in the teardown (the gzip trailer) is logged, not raised, so the teardown finishes, and the run exits 73 too (`GameEngine.recording_write_failed`). A rebaseline's NEW goes through the same recorder

### 78. A Stale `glitchygames.egg-info` in the Checkout Root Hides the Installed Package Metadata
- **Description**: The checkout root holds an untracked, git-ignored `glitchygames.egg-info/` from April 2025 (version 0.1.0, no entry points). Whenever the checkout root comes before `site-packages` on `sys.path` (pytest's rootdir insertion, `python -c` or `python -m` run from the root), `importlib.metadata` finds it first: `importlib.metadata.version('glitchygames')` returns `0.1.0` instead of `1.0.0`, so `--replay-trace` logs "The recording was made with engine version 1.0.0; this is 0.1.0" and recordings made that way would record `engine_version` 0.1.0; `importlib.metadata.entry_points()` (which keeps only the first distribution of each name) lists none of the project's console scripts
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (replay tooling, Task 5: the replay plugin's console-script lookup failed under pytest)
- **Date Reported**: 2026-10-20
- **Details**: Not a code bug and not removed here (it is the user's file). Deleting the directory fixes it; `glitchygames/testing/replays.py` (`game_entry_point`) searches every distribution so the plugin works either way. `replay/driver.py` (`_installed_engine_version`) and `state/manager.py` still read the first one
- **Files**: `glitchygames.egg-info/` (untracked), `glitchygames/replay/driver.py`, `glitchygames/state/manager.py`
- **Date Resolved**: 2026-10-20
- **Solution**: Deleted the stale directory (with the user's go-ahead); `importlib.metadata.version('glitchygames')` run from the checkout root now gives 1.0.0 and the console scripts are listed. `game_entry_point`'s search of every distribution (`glitchygames/testing/replays.py`) is left as it is: harmless, and it guards against the next stray egg-info (the src/ layout move would remove the cause)

### 84. A Live Supervisor's `post_event` Is Recorded as the Scene's Own Internal Event
- **Description**: When a live supervisor (or control-event handler) calls `glitchygames.recording.post_event` in an ordinary live frame, the post is journaled and recorded as one of the scene's internal events. A later `instant_replay()` across that frame diverges (`event UserEvent missing internal event expected {...}, got None`), because nothing in the played scene makes that post; a post made in the frame just before `instant_replay()` plays the first time, but a second replay across that scope diverges. A `--replay-trace` replay of a `--record-trace` session diverges the same way unless the replay adds the same supervisor
- **Status**: Resolved
- **Priority**: Low (supervisors are an engine hook; no shipped game posts from one)
- **Reporter**: Found by reading during the gameplay-replay final review fixes; confirmed by the re-review's probe
- **Date Reported**: 2026-10-20
- **Details**: Predates 77ed933 (present at 00b795d). Inside a playback scope, 77ed933 already keeps live supervisors' posts apart (`recording.live_game_posts`) and re-posts them after the scope; outside a scope they are not marked. Golden replays avoid it because `ScriptedInputSupervisor` (`scripts/record_scripted_session.py`) posts SDL input types with raw `pygame.event.post`, which are recorded as external input. A fix could mark supervisor-slot posts outside scopes too and record them as external (or as control events), so a replay serves them instead of expecting the game to make them
- **Files**: `glitchygames/recording.py`, `glitchygames/scenes/scene.py`, `glitchygames/replay/playback.py`, `glitchygames/replay/driver.py`, `glitchygames/engine/game_engine.py`
- **Date Resolved**: 2026-10-20
- **Solution**: An explicit API instead of guessing whose supervisor it is: `recording.post_input_event` posts an event as input to the game (a supervisor driving it, a harness, a tool). Recordings and the instant-replay journal record it as `external`, whatever its type, so every replay serves it whether or not it runs the poster again; a copy the replayed code posts (a supervisor the played scene's setup() added) is dropped (`ReplaySources._sort_live_events`; inside a scope `PlaybackSources._sort_base_events`, which notes the input posts before the installed doors pump, since a replay's pump forgets them). The live game's input posts held by a scope are redelivered as external or re-posted as input; scene starts and resume bridges count only the game's own posts as earlier events (`pending_code_post_count`). `post_event` keeps meaning "the game posted it", so a supervisor that posts with it still gets the old behaviour (documented in the module docstring). Remaining limit: a `--replay-trace` of a session whose live supervisor posted during an instant replay diverges if the replay lacks that supervisor (the scope's pump cannot tell the served event from a scope post; `replay/playback.py` Limits)

### 79. Clockwork Keep's `--floor` Option Is Parsed but Never Read
- **Description**: `ClockworkKeepScene.args` adds `--floor` ("Starting floor (0=Boiler Room, 1=Gear Works, 2=Clock Face)"), but nothing reads `options['floor']`: the game always starts on floor 0 (`ClockworkKeepScene()` with its default `floor_index`)
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (in-game playback, Task 1: Clockwork Keep's `replay_arguments`)
- **Date Reported**: 2026-10-20
- **Details**: Either read the option where the first floor is built (`floor_index=options.get('floor', 0)`, which would make `--floor` a recorded option a replay applies) or drop the argument. Not fixed here: it changes the game's behaviour, outside this task
- **Files**: `glitchygames/examples/clockwork_keep/game.py`
- **Date Resolved**: 2026-10-20
- **Solution**: Read it where the first floor is built: `ClockworkKeepScene(floor_index=None)` (the default, which is how the engine builds the first scene from options alone) takes `options['floor']` (`_starting_floor_index`); the elevator and a playback's rebuild still name their floor. `--floor` now refuses a floor that does not exist (`choices=range(len(ALL_FLOORS))`), and as a recorded option a replay applies it; recordings without it start on floor 0 as before

### 80. Playbacks Found a Scene Class by Its Bare Name, So Two Loaded Scenes Named Alike Refused It
- **Description**: A scene start recorded only the class name (`SceneStart.scene_class`, e.g. `Game`), and `find_scene_class` refused a playback when several loaded `Scene` subclasses shared it ("Several scene classes are named Game"). Ten example and script scenes are named `Game` (PaddleSlap, the joystick, dt and text-input demos, six in `scripts/`), and the full suite loads more than one
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found on feature/gameplay-replay (in-game playback, Task 4: PaddleSlap's bundled demo)
- **Date Reported**: 2026-10-20
- **Files**: `glitchygames/scene_start.py`, `glitchygames/replay/playback.py`, `glitchygames/replay/driver.py`, `glitchygames/engine/game_engine.py`
- **Date Resolved**: 2026-10-20
- **Solution**: A start records `scene_module` and the class's `__qualname__`; `find_scene_class` takes the one loaded class with that module and qualified name, else (no module recorded, a game run as `__main__`) a qualified name no other loaded scene shares, and still refuses an ambiguous one; nothing is imported from recording data. The trace header holds `game_module` too, and `check_recorded_game` refuses a same-named game from another module (name only for headers without it, or when either side is `__main__`). PaddleSlap's bundled demo was re-recorded; the golden replay fixtures (no module) still replay

### 81. A Playback Scope Left `SceneManager.previous_scene` Pointing at Its Own Scenes
- **Description**: A demo whose recording switches scenes (to the pause screen, to game over) set `SceneManager.previous_scene` through `switch_to_scene`; `_exit_playback` restored the live scene but not `previous_scene`, so `GameOverScene.resume` (which restarts `type(previous_scene)`) or the default `Scene.resume` could restart or resume a playback scene
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (in-game playback, Task 4)
- **Date Reported**: 2026-10-20
- **Files**: `glitchygames/scenes/scene.py`, `glitchygames/replay/playback.py`
- **Date Resolved**: 2026-10-20
- **Solution**: `PlaybackRequest.begin_session` saves `previous_scene` (`PlaybackSession.saved_previous_scene`) as the scope begins and `_exit_playback` restores it

### 77. Multi-Controller Stress Tests Time Themselves With the Wall Clock
- **Description**: `tests/tools/test_multi_controller_stress.py` asserts elapsed `time.time()` differences (e.g. `test_concurrent_operations_stress`: `< 10.0` seconds), so a wall-clock jump fails it: one full-suite run measured 732 s inside a 68 s run
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (replay tooling, Task 4: full-suite run)
- **Date Reported**: 2026-10-20
- **Files**: `tests/tools/test_multi_controller_stress.py`
- **Date Resolved**: 2026-10-20
- **Solution**: Every duration in the file is measured with `time.perf_counter()` (monotonic, never stepped by sleep or NTP) instead of `time.time()`

### 69. The Live Device Registry Keeps Every Enumeration Answer and Opened Descriptor Until a Recorder Takes Them
- **Description**: `LiveDeviceRegistry` appends every enumeration answer and every opened device's descriptor to lists that only `take_enumeration_answers()` / `take_opened_descriptors()` empty, and nothing calls them yet (the recorder will). Without a recorder they grow for the whole run: the joystick demo counts devices every frame (one answer per frame), and Bitmappy's controller scan reopens every joystick once a second
- **Status**: Resolved
- **Priority**: Low (tens of bytes per answer)
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 6)
- **Date Reported**: 2026-10-19
- **Files**: `glitchygames/input/devices.py`, `glitchygames/live_sources.py`
- **Date Resolved**: 2026-10-19
- **Solution**: `LiveSources.end_frame` calls `LiveDeviceRegistry.discard_untaken()`, which drops the frame's answers and descriptors nobody took; a recorder (Task 11) takes them before `end_frame`. The registry also forgets a device when it is removed (the joystick and controller managers' removal handlers call `forget_device`) or when `poll()` finds it detached or raising, instead of logging a traceback every frame. The joystick demo looks joystick device indexes up once per frame instead of once per tracked device
- **Files Modified**: `glitchygames/input/devices.py`, `glitchygames/live_sources.py`, `glitchygames/events/joystick.py`, `glitchygames/events/controller.py`, `glitchygames/examples/joystick_demo.py`
- **Tests**: `test_live_frames_without_a_recorder_keep_no_enumeration_answers`, `test_answers_taken_before_the_end_of_a_live_frame_are_intact` and the forget tests in `tests/input/test_devices.py`; the removal tests in `tests/events/`; `test_joystick_device_index_lookup_opens_each_joystick_once_per_frame` in `tests/examples/test_joystick_demo.py`

### 71. The Joystick Demo Called `get_id` / `get_instance_id` on Game Controllers
- **Description**: In controller mode the demo's device panel called `get_id()` and `get_instance_id()` on the `pygame._sdl2.controller.Controller`, which has neither, so the `AttributeError` (not caught by `except pygame.error`) would have stopped the demo once #66 no longer did
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 6)
- **Date Reported**: 2026-10-19
- **Date Resolved**: 2026-10-19
- **Solution**: Both lookups also catch `AttributeError`; the controller-mode readout takes the instance id from the controller's joystick view
- **Files Modified**: `glitchygames/examples/joystick_demo.py`

### 70. Bitmappy Read Controller State From the Wrong Device
- **Description**: `ControllerEventHandler._read_controller_trigger_values` opened `pygame.joystick.Joystick(event.instance_id)` and `is_controller_button_held` opened `pygame.joystick.Joystick(controller_id)`, but pygame's joystick constructor takes a device index. An instance id differs from the device index after a reconnect, and `controller_id` is Bitmappy's slot number (0-3), so both read the wrong device or raised `pygame.error` (read as "not held" / 0.0)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the replay core pre-flight on feature/gameplay-replay (Task 6)
- **Date Reported**: 2026-10-19
- **Date Resolved**: 2026-10-19
- **Solution**: Both read the frame's input snapshot (`current_input()`) by instance id; `is_controller_button_held` finds the slot's instance id through `find_controller_info`
- **Files Modified**: `glitchygames/bitmappy/controllers/event_handler.py`
- **Tests**: `TestIsControllerButtonHeld` and `TestTriggerValuesFromSnapshot` in `tests/tools/test_bitmap_editor_scene.py`

### 66. The Joystick Demo Calls `pygame._sdl2.controller.name_forindex`, Which pygame-ce Does Not Have
- **Description**: `joystick_demo.py` calls `pygame._sdl2.controller.name_forindex` in controller mode (building a proxy's name and validating a controller), but pygame-ce 2.5.8 has no such function, so the call raises `AttributeError`, which the surrounding `except pygame.error` does not catch
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 5)
- **Date Reported**: 2026-10-19
- **Details**: The `# type: ignore[attr-defined]` on both lines hid it from the type checkers. Only pygame-ce's legacy stub `pygame/_sdl2/controller_old.pyi` declares it; the live `pygame/_sdl2/controller.pyi` does not
- **Date Resolved**: 2026-10-19
- **Solution**: Both calls go through the devices door's `name_for_index` (glitchygames/input/devices.py, replay core Task 6), which answers None when pygame has no lookup; the device panel then shows 'Unknown Controller'. The `# type: ignore` comments are gone
- **Files Modified**: `glitchygames/examples/joystick_demo.py`

### 65. A Test Left GameEngine.USE_FASTEVENTS Set for Every Later Test on Its Worker
- **Description**: `test_use_fastevents_with_old_pygame` mocks pygame as version 1.1, so `GameEngine.__init__` sets the class attribute `GameEngine.USE_FASTEVENTS = True`; nothing undid it, so every later engine on that pytest worker chose the fastevent path (and, since the engine's doors, created fastevent `LiveSources`). Harmless only because `pygame.fastevent` no longer exists once the test's mock is undone
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found on feature/gameplay-replay (replay core, Task 2 review)
- **Date Reported**: 2026-10-19
- **Date Resolved**: 2026-10-19
- **Root Cause**: The autouse `restore_game_engine_class_state` fixture restored only `game`, `icon` and `OPTIONS`, not the other class attribute engine code writes
- **Solution**: The fixture also restores `USE_FASTEVENTS`, and the test patches it with `mocker.patch.object` so it undoes its own write
- **Files Modified**: `tests/conftest.py`, `tests/engine/test_game_engine.py`
- **Tests**: `TestGameEngineFastEvents` in `tests/engine/test_game_engine.py`; the full suite

### 64. Collision Used the Previous Frame's Pose (Hitbox Up to 4 px Inside a Wall for One Frame)
- **Description**: In Brave Adventurer and Clockwork Keep, on the frame the player turned toward a wall or started to run while standing at it, the drawn hitbox sat 1-4 px inside the wall for one frame; the first ground check after a respawn also ran on the blank image, so the player stood 1-2 px high
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found on feature/debug-overlay (`plans/future-work.md`); fixed on feature/engine-world-space
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-18
- **Root Cause**: Both games drew the player's pose in `update()`, which runs in the render phase after collision, so wall and ground resolution in `dt_tick` used the previous frame's image and hitbox
- **Solution**: The pose rule (CLAUDE.md, World Space): each player draws its pose in `dt_tick` (`_draw_pose()`), after physics and the state machine and before collision, then refits its wall bounds to the new hitbox; `update()` keeps only visual work (the respawn fade). Papyrus already drew in `dt_tick`
- **Files Modified**: `glitchygames/examples/clockwork_keep/player.py` (51d4f08), `glitchygames/examples/brave_adventurer/player.py` (dc4d25f)
- **Tests**: `TestPoseBeforeCollision` in `tests/examples/test_clockwork_keep.py` and `tests/examples/test_brave_adventurer_game.py` (8 wall/facing/key cases each, hitbox checked after logic and after render, both Brave editions); the golden traces prove the changed frames exactly

### 63. Camera Stepped Ahead on the Frame a Scene Resumed From Pause
- **Description**: After the engine took over camera aiming, Brave Adventurer's camera moved one extra smoothing step on the frame it resumed from the pause screen, so every sprite was drawn a little off for the following frames (about 470 golden-trace rects on frames 373-386)
- **Status**: Resolved (found and fixed before it reached main)
- **Priority**: Medium
- **Reporter**: Found by the golden traces on feature/engine-world-space (Task 7)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `PauseScene` resumes with `switch_to_scene` during event processing, after the pause scene's `dt_tick`. The engine then aimed the resumed scene's camera that same frame although that scene ran no logic, an extra step the games' own `camera.update` in `dt_tick` had never taken
- **Solution**: `SceneManager._run_scene_frame` aims the camera only when the scene that ran `dt_tick` this frame is still active; its world sprites are still positioned for the frame's render
- **Files Modified**: `glitchygames/scenes/scene.py` (0823479)
- **Tests**: `test_camera_waits_for_the_resumed_scene_logic` in `tests/world/test_frame_integration.py`; the Brave Adventurer golden trace

### 62. Frame Processing Time Included the Pacing Sleep
- **Description**: The per-frame processing time handed to the performance manager was measured after `_handle_frame_pacing`, so it included the sleep; `AdaptiveClamping.get_spare_time_stats` reported about zero spare capacity whenever a timer backend paced the loop
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found on feature/engine-world-space (Task 5)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `actual_processing_time` was taken from the frame start to after pacing, not to the end of the frame's work
- **Solution**: `SceneManager.start()` measures `processing_seconds` from the frame start to the end of `_run_frame()`, before pacing, and passes it to `_finish_frame`, which records it (engine audit #15)
- **Files Modified**: `glitchygames/scenes/scene.py` (733ebb4)
- **Tests**: `test_processing_time_excludes_the_pacing_sleep` in `tests/world/test_finish_frame.py` (on a fake clock; before the fix the sample was 0.0234 s for 0.0059 s of work)

### 61. Brave Adventurer Sprites That Had Been Off Screen Stopped Being Drawn
- **Description**: Brave Adventurer's per-sprite culling set `dirty = 0` on sprites outside the screen. `Scene.update()` calls `update()` only on dirty sprites, so an off-screen scarab never drew its image: collision then used the blank image (the whole image as the hitbox) and the scarabs rolled 2 px above the ground. Enemies that draw in `update()` (Cobra, Scarab, Scorpion) were drawn once when they came back on screen (the `visible` setter dirtied them) and then froze on that frame
- **Status**: Resolved
- **Priority**: Low (the scripted runs never show an enemy returning on screen; worked out from the code and proven on the scarabs)
- **Reporter**: Found by the golden traces on feature/engine-world-space (Task 7)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: Culling and redraw scheduling shared one flag: `dirty = 0` meant both "nothing changed" and "do not run `update()`"
- **Solution**: The games' `is_visible` culling was removed; the engine's positioning step culls with `visible` only and never lowers `dirty = 2` (spec 2.4). The scarabs now rest their visible underside on the ground (3384 golden rects, each proven by an exact rule; a scratch emulation restoring only the old culling reproduced the baseline with 0 differences)
- **Files Modified**: `glitchygames/examples/brave_adventurer/terrain.py`, `glitchygames/examples/brave_adventurer/enemies.py` (dc4d25f); Papyrus's copies in d5144ce
- **Tests**: `test_scarab_rolls_with_its_visible_bottom_on_the_ground`; the off-screen Papyrus scarab keeps `dirty = 2` (`TestPapyrusEngineWorldSpace` in `tests/examples/test_brave_adventurer_game.py`); `test_dirty_two_sprite_stays_two` in `tests/world/test_positioning.py`

### 58. Frame Pacing Bursts to Catch Up After a Hitch
- **Description**: After a long stall (a 2 s hitch, a window drag, a debugger pause) the main loop ran about 120-150 frames back to back without sleeping: a CPU spike, skewed FPS, frame-time and 1%-low statistics, uneven presentation, and anything counted per frame ran fast until the deadlines caught up
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found on feature/engine-world-space
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: Both timer backends' `compute_deadline` returned `previous_deadline + period` unconditionally, so after a stall every missed deadline was already in the past and `sleep_until_next` returned immediately for each of them
- **Solution**: A shared `next_frame_deadline_ns` in `glitchygames/timing.py` (used by `FastTimer` and `PygameTimer`) re-anchors to `now + period` when the loop is more than one full period behind (`now - (previous + period) > period`), dropping the backlog. Exactly one period behind still catches up, as does any normal jitter, so the long-run rate stays exactly at the target. The first frame and the uncapped (period 0) result are unchanged. PygameTimer's clock is whole milliseconds, so its lateness is measured to within 1 ms
- **Files Modified**: `glitchygames/timing.py`, `tests/timing/test_timing.py`, `CLAUDE.md`
- **Tests**: `TestDeadlineReanchorsAfterHitch` and `TestDeadlineReanchorBoundary` in `tests/timing/test_timing.py` (both backends on a fake clock: a 2 s hitch re-anchors and leaves no unslept frames (157 before the fix), a 2 ms late frame still catches up, both sides of the boundary, an exact average rate over 1,000 jittery frames, uncapped unchanged); existing `compute_deadline` tests now use an on-time previous deadline instead of a fixed 1 s one

### 57. PaddleSlap Reseeds Python's Global random Module at Startup
- **Description**: Creating PaddleSlap's `Game` called `random.seed()` with a value from `time.perf_counter()`, under the comment "Set random seed for reproducible randomness". The seed was neither reproducible (it came from the clock) nor used by PaddleSlap (its randomness comes from `secrets` and the ball's `_SERVE_RANDOM`), but it reset the process-wide `random` module for every other user in the process (for example `glitchygames/audio/controller_audio.py`'s noise), and the golden-trace harness had to save and restore the global state around each run
- **Status**: Resolved
- **Priority**: Low (no visible effect; a hidden global side effect)
- **Reporter**: Found on feature/engine-world-space (Task 1)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: A leftover reseed from the coverage branch (a029a67); nothing in PaddleSlap reads the global `random` module
- **Solution**: Removed the reseed, its log line and the `random` import. The golden-trace harness no longer fakes `time.perf_counter` for PaddleSlap or saves/restores the global random state; the PaddleSlap golden trace is unchanged (the harness never depended on the reseed)
- **Files Modified**: `glitchygames/examples/paddleslap.py`, `scripts/record_golden_traces.py`
- **Tests**: `test_game_initialization_leaves_global_random_state_alone` in `tests/examples/test_paddleslap.py`; `tests/world/test_golden_traces.py` (PaddleSlap trace still matches)

### 56. isinstance/issubclass Against Scene, Sprite and Every Concrete Event Class Is False for Subclasses
- **Description**: `issubclass(SubScene, Scene)` and `isinstance(sub_scene, Scene)` were False for every real subclass; the same held for every concrete class deriving from `EventInterface` (`Sprite`, `BitmappySprite`, `Scene`, the `*EventStubs`, the example game scenes, UI widgets and dialogs). Only an object whose exact type is the checked class passed (Python's exact-type fast path)
- **Status**: Resolved
- **Priority**: Low (no engine code path depended on the wrong answer; it blocked using isinstance)
- **Reporter**: Found on feature/engine-world-space (Task 1b)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `EventInterface.__subclasshook__` returned `False` when its structural check failed. To `abc`, False means "definitely not a subclass", so normal inheritance was never consulted. Concrete classes have no abstract methods, so the structural check always failed for them
- **Solution**: The hook returns True when the class implements every abstract method of the interface and `NotImplemented` otherwise, so `abc` falls back to inheritance. Audit (every `isinstance`/`issubclass` against an `EventInterface` subclass in `glitchygames/`, `scripts/` and `tests/`, plus a full-suite run with an instrumented hook): no check on a real object changes outcome (the checked objects are exact types or classes without subclasses); the 615 changed class pairs are subclass-vs-concrete-ancestor pairs and interface pairs involving abstract classes, which no code checks. `SceneManager.on_key_down_event` keeps its by-name `_record_key_press` lookup: `active_scene` is annotated `Scene`, so an isinstance check is flagged as unnecessary by basedpyright
- **Files Modified**: `glitchygames/events/base.py`, `glitchygames/scenes/scene.py` (comment only)
- **Tests**: `TestEventInterface` in `tests/events/test_events_core.py`: a real Scene subclass passes issubclass/isinstance; an unrelated class does not; a class implementing every abstract method of `KeyboardEvents` without inheriting passes; a partial implementation does not; the hook returns NotImplemented for a non-matching class. The existing hook tests now expect NotImplemented instead of False

### 55. Input Pressed During a Scene Transition Is Delivered When It Ends
- **Description**: Keys, buttons and clicks pressed during a transition (about 4 s for Clockwork Keep's elevator ride) were all delivered at once to the new scene when it ended: a jump pressed mid-ride jumped on arrival. A key held before the ride and released during it still read as held on the arrival scene's first frame, and quit or a controller disconnect during a ride waited for it to end
- **Status**: Resolved
- **Priority**: Medium (stale input acted on arrival)
- **Reporter**: Found while planning the engine world space (`plans/2026-10-18-engine-world-space.md`)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `SceneManager.start()`'s transition branch never processed events, so they queued in SDL for the whole transition
- **Solution**: Each transition frame calls the new `SceneManager._process_transition_events()`, which runs `GameEngine.process_events(discarded_event_types=TRANSITION_DISCARDED_EVENT_TYPES)`: presses and motion (`KEYDOWN`, `TEXTINPUT`, `MOUSEBUTTONDOWN`, `MOUSEMOTION`, `MOUSEWHEEL`, `JOYBUTTONDOWN`, `JOYAXISMOTION`, `JOYHATMOTION`, `JOYBALLMOTION`, `CONTROLLERBUTTONDOWN`, `CONTROLLERAXISMOTION`, `FINGERDOWN`, `FINGERMOTION`, `TEXTEDITING`, `CONTROLLERTOUCHPADDOWN`, `CONTROLLERTOUCHPADMOTION`, `MULTIGESTURE`) are dropped, except motion back to neutral, which is a release (`is_discarded_during_transition`: an axis inside ActionMap's `DEFAULT_DEADZONE`, or a hat at (0, 0)); releases (including `CONTROLLERTOUCHPADUP`), quit, window, focus, device and drop events (`DROPFILE`/`DROPTEXT`: a drop during a ride should land) go through the normal dispatch. They reach the incoming scene, which `_start_transition` has already made active (the outgoing scene is cleaned up). The golden-trace harness's copy of the transition branch (`GoldenTraceSceneManager.run_frame`) does the same. The base `Scene.on_key_up_event` quit keys (Q, ESC) now quit only on the release of a key whose key-down reached that scene: `SceneManager.on_key_down_event` calls `Scene._record_key_press` before dispatch (so overriding handlers are covered) and each release consumes its press. A Q pressed during a transition, or pressed in the departing scene and released after it was left, no longer quits (nor does an ESC held from gameplay into the pause screen)
- **Files Modified**: `glitchygames/scenes/scene.py`, `glitchygames/engine/game_engine.py`, `glitchygames/input/action_map.py`, `scripts/record_golden_traces.py`
- **Tests**: `tests/world/test_transition_input.py` (real engine and scenes through the harness): a jump pressed and released mid-ride does not jump on arrival; a key held before a transition and released during it is not held after (shared `ActionMap`); a press during a transition is never delivered; quit during a transition quits; a joystick removal during a transition reaches the joystick manager; the discard set holds no release; a stick pushed before a transition and centred during it is not held after, a stick pushed during it is discarded, a centred hat is delivered and a pushed one discarded; a file dropped during a transition reaches the arriving scene. Q pressed and released during a transition does not quit; Q pressed before it and released during it does not quit; Q pressed and released in one scene quits (`TestSceneKeyUpEvent` in `tests/scenes/test_scene.py` covers the release-without-press and one-quit-per-press cases). The golden traces did not change: the only scripted input inside a transition is Clockwork Keep's interact release at frame 354 (ride: frames 352-592), which the arrival floor's fresh `ActionMap` ignores whether it arrives during or after the ride

### 54. GameEngine.process_events Drops Events
- **Description**: Events queued in the same frame as an unhandled event were lost, scenes that take raw pygame events (`process_event`) only ever received the first event of each frame, and an event type missing from `EVENT_HANDLERS` was reported with the previous event's result
- **Status**: Resolved
- **Priority**: Medium (lost input whenever an unhandled event shared a frame with it)
- **Reporter**: Found while planning the engine world space (`plans/2026-10-18-engine-world-space.md`)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `pygame.event.get()` removes the whole batch from SDL's queue, but the loop returned `False` right after `process_unimplemented_event`, returned `True` after the first raw event, and never reset `event_was_handled` per event
- **Solution**: Every event of the batch is handled; handled/unhandled is decided per event (a type with no handler is unhandled and goes to `process_unimplemented_event`); the loop never returns early; raw-event scenes get every event in order. The return value is True only when every event was handled (False for an empty batch, as before)
- **Files Modified**: `glitchygames/engine/game_engine.py`
- **Tests**: `TestProcessEvents` in `tests/engine/test_game_engine.py`: an unhandled event followed by a key-down in one batch (both processed); a raw-event scene receives all events in order; an unmapped type after a handled event is unhandled; True only when every event was handled. The golden traces did not change (the scripts never mix an unhandled event into a batch)

### 53. Undoing a Bitmappy Frame Delete Fails
- **Description**: Deleting a frame from an animation in the film strip and then undoing the delete restored nothing: the undo failed with `AttributeError: 'PixelArray' object has no attribute 'flat'` and the frame stayed deleted. A frame known only by its surface came back black, and a restored frame lost its explicit hitbox and per-pixel alpha
- **Status**: Resolved
- **Priority**: Medium (undo of a frame delete was broken)
- **Reporter**: Found while fixing BUGS.md #51 (`plans/future-work.md`)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `FrameAddCommand._add_frame` (which `FrameDeleteCommand.undo` uses) copied pixels through `PixelArray.flat`, which pygame-ce's `PixelArray` does not have, so the undo raised, logged and returned False (the same bug as #51 in `AnimationAddCommand`). The delete capture (`FilmStripEventHandler.track_frame_deletion_for_undo`) recorded `frame.pixels`, which is empty for a frame that has only a surface, and did not record the frame's hitbox; the restore built a surface without `SRCALPHA`
- **Solution**: The delete capture reads pixels with `SpriteFrame.get_pixel_data()` and records an explicit frame hitbox as an `(x, y, width, height)` tuple (None when the frame uses the hitbox fallback). `FrameAddCommand._add_frame` builds an `SRCALPHA` surface like the editor's own frames, passes the hitbox to `SpriteFrame` and copies pixels with `SpriteFrame.set_pixel_data` (which also keeps `frame.pixels`, which saves read). A grep of the package found no other `.flat` or `PixelArray` use
- **Files Modified**: `glitchygames/bitmappy/history/commands.py`, `glitchygames/bitmappy/film_strip_events.py`
- **Tests**: `TestFilmStripFrameDeleteUndo` in `tests/tools/test_bitmappy_film_strips.py` (real `AnimatedSprite` and `FilmStripWidget`): delete the middle frame, undo (pixels, alpha, duration and hitbox back at index 1, and saved), redo deletes it again, undo again; a frame with no pixel list is restored from its surface; the editor's `handle_undo`/`handle_redo` undo and redo the delete

### 52. Bitmappy's Signal Handler Skips the AI Worker's Graceful Shutdown (and Can Lose the Signal)
- **Description**: On SIGINT/SIGTERM Bitmappy exited without the AI worker's shutdown (`AIManager.cleanup`), so the worker (a daemon `multiprocessing.Process`) was killed at exit instead of receiving its shutdown message. A terminal Ctrl-C also killed the worker directly with KeyboardInterrupt. Verifying the fix showed a worse problem: a signal arriving while the editor was writing a log line was lost and the editor kept running
- **Status**: Resolved
- **Priority**: Low (no leak or traceback observed in normal runs), but the lost signal meant `kill` sometimes needed sending twice
- **Reporter**: Found while verifying BUGS.md #47 in the binary (`plans/future-work.md`)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `editor.main`'s handler called `sys.exit(0)`; the SystemExit ends `GameEngine.start` without the scene manager's loop exit, so no scene `cleanup()` (and so no `AIManager.cleanup`) ran. The terminal sends SIGINT to the whole process group, and the spawned worker kept Python's default SIGINT handler. The handler also logged; when the signal interrupted a write to stderr, logging raised `RuntimeError: reentrant call inside <_io.BufferedWriter name='<stderr>'>`, which escaped the handler in place of SystemExit and was swallowed by the frame loop
- **Solution**: The handler now only records the signal and raises SystemExit. `main` wraps `engine.start()` in `try/finally`; the finally logs the signal and calls `shut_down_running_ai_workers()`, which runs `AIManager.cleanup` (shutdown message, join for `AI_WORKER_JOIN_TIMEOUT_SECONDS` = 2 s, terminate and then kill only if still alive, close queues) for each manager whose worker is running (a `WeakSet` filled by `AIManager.setup`). It runs after SystemExit has unwound the engine, so it cannot block on a lock the interrupted code held, and it does nothing after a normal quit (cleanup unregisters the manager and clears its process and queues, so it is safe to call twice). The worker now starts through `run_ai_worker_process`, which ignores SIGINT so Ctrl-C leaves it to exit on its shutdown message (`terminate()` still stops it)
- **Verification**: Ran `uv run bitmappy` headless (`SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`), waited for the worker, then sent SIGTERM to the editor process and, in a second run, SIGINT to the whole process group (as Ctrl-C does). Both exited in under 0.3 s with code 0, logged the shutdown message being sent and `AI process cleanup completed` without terminating the worker, printed no traceback, and left no processes
- **Files Modified**: `glitchygames/bitmappy/editor.py`, `glitchygames/bitmappy/ai_manager.py`, `glitchygames/bitmappy/ai_worker.py`
- **Tests**: `TestAiWorkerShutdown` in `tests/tools/test_bitmappy.py`: a signal while the engine runs exits 0 through `shut_down_running_ai_workers` without logging inside the handler; cleanup sends the message then joins with the timeout and does not terminate a worker that exits; terminates one that does not; started managers are shut down once; the worker process ignores SIGINT

### 51. Undoing a Bitmappy Animation Delete Fails and Loses Its Transitions and Settings
- **Description**: Deleting an animation drops the `[[transition]]` entries from or to it (BUGS.md #44), and undoing the delete did not bring them back. Fixing that showed the undo had never worked: it failed with `AttributeError: 'PixelArray' object has no attribute 'flat'` and restored nothing
- **Status**: Resolved
- **Priority**: Medium (undo of an animation delete was broken; transitions silently lost)
- **Reporter**: Found while fixing BUGS.md #44 (`plans/future-work.md`)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `_capture_animation_deletion_for_undo` saved only the frames. `AnimationAddCommand._add_animation` (which `AnimationDeleteCommand.undo` uses) copied pixels through `PixelArray.flat`, which pygame-ce's `PixelArray` does not have, so the undo raised, logged, and returned False. The delete also left the animation's loop flag, frame interval and `_animation_order` entry behind, and its redo (`AnimationAddCommand._delete_animation`) did not drop the transitions again
- **Solution**: The delete capture also records the animation's position, loop flag, frame interval and the transitions it drops with their indices (`AnimatedSprite.transitions_for_animation`); frames are captured with `get_pixel_data()`. The delete (and `AnimatedSprite.remove_animation`) now drops the settings and order entry (`forget_animation_settings`). `AnimationDeleteCommand.undo` re-adds the frames (now via `SpriteFrame.set_pixel_data`), puts the animation back in its place with its settings (`restore_animation_settings`) and the transitions back at their original positions (`restore_transitions`); its redo drops the transitions and settings again
- **Files Modified**: `glitchygames/sprites/animated.py`, `glitchygames/bitmappy/film_strip_coordinator.py`, `glitchygames/bitmappy/history/commands.py`
- **Tests**: `test_undoing_an_animation_delete_restores_its_transitions_and_settings` in `TestFilmStripAnimationTransitions` (`tests/tools/test_bitmappy_film_strips.py`, real `AnimatedSprite`: delete, undo, save, redo, undo); `test_removed_transitions_restore_to_their_original_positions` and `test_remove_animation_forgets_its_settings` in `tests/sprites/test_animated_sprite.py`

### 50. Packaged Bitmappy AI Requests Fail With "Supported providers: set()"
- **Description**: In the PyInstaller binary every AI sprite request failed with `ValueError: Invalid provider key 'anthropic'. Supported providers: set()`
- **Status**: Resolved
- **Priority**: High (AI generation unusable in the packaged app)
- **Reporter**: User, testing the binary after BUGS.md #47
- **Date Reported**: 2026-10-18
- **Root Cause**: aisuite discovers providers by globbing `aisuite/providers/*_provider.py` on disk (`ProviderFactory.get_supported_providers`) and imports them by a constructed name. PyInstaller stores modules compiled inside its archive, so the glob found no files and the dynamic import was invisible to its analysis.
- **Solution**: A project PyInstaller hook, `packaging/pyinstaller_hooks/hook-aisuite.py` (enabled via `hookspath` in `bitmappy.spec`), bundles the anthropic, openai and ollama provider modules as hidden imports and their source files as data, so both the glob and the import work. Only these providers are bundled, to keep vendor SDKs out of the binary; others fail with aisuite's clear "not supported" error.
- **Files Modified**: `packaging/pyinstaller_hooks/hook-aisuite.py` (new), `bitmappy.spec`
- **Tests**: `tests/tools/test_bitmappy_packaging.py` checks the spec uses the hook directory and that the hook bundles the default `AI_MODEL`'s provider and only real provider modules. Verified by rebuilding and listing the binary's archive (the three provider files are present); a real request in the binary still needs a manual run with an API key.

### 49. bitmappy.spec Lists a Hidden Import That No Longer Exists
- **Description**: The PyInstaller build logged `ERROR: Hidden import 'glitchygames.events.voice_portaudio' not found`
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found while verifying BUGS.md #40 with `nox -s build-binary`
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: The PortAudio voice backend moved to `glitchygames.events.voice_backends.voice_portaudio`, and the spec was not updated. The spec had also never been committed: the PyInstaller section of `.gitignore` ignores `*.spec`, so a fresh clone could not run `nox -s build-binary` at all
- **Solution**: The hidden import now names `glitchygames.events.voice_backends.voice_portaudio`. `.gitignore` makes an exception for `bitmappy.spec`, and the spec is now tracked
- **Verification**: The rebuild logs no hidden-import errors for `glitchygames` modules. Its remaining `Hidden import … not found` warnings (`pycparser.lextab`, `pycparser.yacctab`, `scipy.special._cdflib`) come from third-party PyInstaller hooks, not from the spec
- **Tests**: `test_every_spec_hidden_import_exists` (each hidden import must exist) and `test_spec_script_and_data_sources_exist` (the Analysis script and every `datas` source must exist) in `tests/tools/test_bitmappy_packaging.py`
- **Files**: `bitmappy.spec`, `.gitignore`

### 48. Packaged Bitmappy Is Missing `pygame._sdl2.audio`
- **Description**: A background process in the PyInstaller build crashed with `ModuleNotFoundError: No module named 'pygame._sdl2.audio'`
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while verifying BUGS.md #40 with `nox -s build-binary`
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: The module was not missing: both builds contain `pygame/_sdl2/audio.cpython-314-darwin.so` (checked with `pyi-archive_viewer --list`), and the main process imported it. The crashing process was one of the children that, without `freeze_support()` (#47), re-ran the whole entry point and imported Bitmappy. It crashed while the parent was being stopped, most likely because the one-file build's extracted files were already being removed
- **Solution**: Fixed by #47 (children no longer import Bitmappy). `pygame._sdl2.audio` is now also listed in `bitmappy.spec`'s `hiddenimports`, so the binary cannot lose it if PyInstaller's analysis changes
- **Verification**: Rebuilt binary ran headless and was stopped with SIGTERM and with SIGINT; neither run printed a `ModuleNotFoundError` or traceback
- **Tests**: `test_spec_lists_the_audio_module_pygame_sdl2_imports` in `tests/tools/test_bitmappy_packaging.py`
- **Files**: `bitmappy.spec`

### 47. Packaged Bitmappy Re-Launches Itself for Background Processes (No freeze_support)
- **Description**: In the PyInstaller build (`dist/bitmappy`), background processes (the AI worker and multiprocessing's resource tracker) started the bundled app again with multiprocessing's own arguments (`--multiprocessing-fork …`, `-B -S -I -c …`), which the app's argument parser rejected, so those processes failed
- **Status**: Resolved
- **Priority**: High for the packaged build; no effect when running from source
- **Reporter**: Found while verifying BUGS.md #40 with `nox -s build-binary` (2026-10-18)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: Bitmappy uses the `spawn` start method (`editor.main` calls `multiprocessing.set_start_method('spawn', force=True)`; `AIManager.setup` starts the worker with `multiprocessing.Process`), and a frozen app spawns children by re-running its own executable. No `multiprocessing.freeze_support()` call existed, so each child ran the app's entry point instead of its task
- **Solution**: `scripts/bitmappy_entry.py` (the script `bitmappy.spec` builds) calls `multiprocessing.freeze_support()` first, and imports and starts Bitmappy only afterwards, so a child never imports Bitmappy or reaches its argument parser
- **Verification**: Rebuilt with `nox -s build-binary` and ran `dist/bitmappy` headless (`SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`). While it ran, the resource tracker (`-B -S -I -c …`) and the AI worker (`--multiprocessing-fork …`) were alive as child processes. The worker initialized its AI client (it logged `game.ai - WARNING - Client does not have _providers attribute`, which was #183). After SIGINT, every process had exited within 5 s. There were no argparse usage errors, tracebacks or `ModuleNotFoundError`. A real AI request was not tried (it needs an API key or network access)
- **Tests**: `test_entry_point_calls_freeze_support_before_starting_bitmappy` in `tests/tools/test_bitmappy_packaging.py`
- **Files**: `scripts/bitmappy_entry.py`

### 46. scripts/legacy_sprite_loader.py Cannot Start
- **Description**: The script raised `TypeError: Sprite.__init__() missing 'x' and 'y'` while building its scene
- **Status**: Resolved (script deleted)
- **Priority**: Low
- **Reporter**: Found by the re-review of `feature/debug-overlay`
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `Sprite.__init__` gained required `x` and `y` arguments in 4bdc966 (Refactor/bitmappy editor, #87); the script still called it with only `width` and `height`. Beyond that, the script was obsolete: since it was added (f20bca6) its history is only lint clean-ups; nothing references it (docs, noxfile, tests, other scripts); its `inflate` draws each pixel as a zero-size rect, which pygame-ce draws as nothing, so even a fixed call would show a solid green square whatever the file held; it wrote the loaded sprite back as an INI `.cfg` file, a format the engine no longer loads (TOML only); and its input (headerless 32×32, one VGA palette index per byte) matches none of the Galimore formats surveyed in `docs/galimore.md` (RGB565 `.bg/.fg/.get/.spr`, 24-bit `.raw`), which Galimore import (sub-plan E) will convert to TOML instead
- **Solution**: Deleted `scripts/legacy_sprite_loader.py` rather than fixing a script that cannot do its job. `scripts/sprite_loader.py` covers loading sprites (TOML). `scripts/raw_sprite_loader.py` is kept because tests use its `BitmappyLegacySprite.deflate`, though it has the same broken `Sprite` call and zero-size-rect `inflate` (noted in `plans/future-work.md`)
- **Files Modified**: `scripts/legacy_sprite_loader.py` (deleted)
- **Tests**: None (nothing to test; `uv run python -c "import pygame; ..."` confirmed a zero-size `pygame.draw.rect` leaves the surface unchanged)

### 45. Renaming an Animation in Bitmappy Drops Its Timing and Loop Flag
- **Description**: `_rename_animation_in_sprite` moved the animation's frames but not its loop flag or frame interval, so a renamed one-shot animation stopped honouring `loop = false` at runtime and saved as `loop = true` with the most common frame duration as its interval
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the re-review of `feature/debug-overlay`
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: The coordinator renamed the sprite's per-animation data by hand (frames, `_animation_order`, and since #44 the transitions) and missed `_loop_flags` and `_animation_frame_intervals`. It also moved the frames to the end of `_animations` (the save order), left the sprite's `frame_manager.current_animation` on the old name when the renamed animation was the current one, and overwrote an existing animation when renamed onto its name. Renames had no undo command at all
- **Solution**: New `AnimatedSprite.rename_animation(old_name=, new_name=)` moves everything stored under the name: frames (in place), `_animation_order`, loop flag, frame interval, transitions, cached surfaces for either name, and the current animation (keeping the current frame); it raises `ValueError` for a missing name or one already in use. `_rename_animation_in_sprite` calls it; `on_animation_rename` refuses (with a warning) a rename onto an existing animation and records an `AnimationRenameCommand` (`FilmStripOperationTracker.add_animation_renamed`, `OperationType.FILM_STRIP_ANIMATION_RENAME`), whose undo renames back through `on_animation_rename` and so restores the old name with its data, and whose redo renames again. The live `AnimationStateMachine` (built at load) is not renamed; Bitmappy does not run it, and saves use `transition_data`
- **Files Modified**: `glitchygames/sprites/animated.py`, `glitchygames/bitmappy/film_strip_coordinator.py`, `glitchygames/bitmappy/history/commands.py`, `glitchygames/bitmappy/history/operations.py`, `glitchygames/bitmappy/history/undo_redo.py`, `glitchygames/bitmappy/history/__init__.py`
- **Tests**: `test_renaming_an_animation_moves_its_loop_flag_and_frame_interval` (flag and interval follow, the one-shot animation stops on its last frame, the save writes them under the new name), `test_renaming_the_current_animation_keeps_it_current`, `test_renaming_onto_an_existing_animation_is_refused` and `test_undoing_an_animation_rename_restores_the_old_name_and_its_data` in `TestFilmStripAnimationTransitions` (`tests/tools/test_bitmappy_film_strips.py`, real `AnimatedSprite`); `test_rename_animation_moves_transitions_and_keeps_the_order` and `test_rename_animation_rejects_a_missing_or_existing_name` in `tests/sprites/test_animated_sprite.py`

### 44. TOML Save Drops Animation State Machine Transitions
- **Description**: The TOML writers never wrote `[[transition]]` sections, so loading and saving a sprite lost its animation state machine (cobra: 2 transitions → 0; Papyrus player: 6 → 0). Saving a sprite in Bitmappy silently broke the game's animation logic
- **Status**: Resolved
- **Priority**: High (silent data loss in game assets)
- **Reporter**: Found by the re-review of `feature/debug-overlay`
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `_load_toml` handed the `[[transition]]` tables straight to `AnimationStateMachine.load_from_toml` (which keeps only parsed `Transition` objects) and kept no copy, so neither `_save_toml` nor `_save_toml_single_frame` had anything to write. Bitmappy's derived sprites (viewport save, single-frame canvas save) had nothing to copy either
- **Solution**: The loader keeps each table verbatim, in file order, in `AnimatedSprite.transition_data`; both writers append them as `[[transition]]` sections with the same keys, values and order (`_write_toml_transitions`). Strings are escaped as TOML basic strings (`toml_basic_string`: backslash, quote and control characters; also `toml_key` and `toml_scalar`), so `when` expressions with quotes or backslashes round-trip. Transitions that games add in code (the Papyrus player's compound falling transitions) are not part of the data and are not written. Bitmappy's viewport and single-frame canvas saves copy the transitions (`copy_transitions_from`); renaming an animation renames it in its transitions (`rename_animation_in_transitions`, called by `FilmStripCoordinator._rename_animation_in_sprite`); deleting one drops the transitions from or to it with a logged warning (`remove_transitions_for_animation`, called by `_delete_animation` and `AnimatedSprite.remove_animation`). Undoing a Bitmappy animation delete now restores the dropped transitions (BUGS.md #51)
- **Tests**: `test_bundled_transitions_survive_a_save_round_trip` (every bundled sprite) and `test_state_machine_transitions_reload_in_order` (Papyrus player, cobra) in `tests/examples/test_examples_sprites.py`; `TestTransitionData` in `tests/sprites/test_animated_sprite.py`; `test_viewport_save_keeps_transitions` and `test_static_save_keeps_transitions` in `tests/tools/test_canvas_panning.py`; `TestFilmStripAnimationTransitions` in `tests/tools/test_bitmappy_film_strips.py`
- **Files**: `glitchygames/sprites/animated.py`, `glitchygames/bitmappy/animated_canvas.py`, `glitchygames/bitmappy/film_strip_coordinator.py`

### 43. Bitmappy Single-Frame Save Drops the Sprite Name, Frame Anchor and Sprite Hitbox
- **Description**: Bitmappy's normal save of a single-frame sprite (`on_save_file_event` → `_save_as_static_sprite`) built a new `AnimatedSprite` and copied only `description`, so the saved file's `name` became `"animated_sprite"` (battle_axe: `bttlaxe.get` → `animated_sprite`) and `frame_anchor` and a sprite-level hitbox not stored on the frame were lost
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the re-review of `feature/debug-overlay`
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `AnimatedCanvasSprite._save_as_static_sprite` copied sprite-level fields one at a time and only `description` (and, since #44, the transitions) was ever added; the new sprite also lacked the loaded color glyphs, so a save could pick different characters
- **Solution**: New `AnimatedSprite.copy_sprite_metadata_from` copies every sprite-level field the writers save (name, description, frame_anchor, the default hitbox, transitions) plus the loaded color glyphs and their order; `_save_as_static_sprite` uses it
- **Tests**: `test_static_save_keeps_the_sprite_name` (battle_axe: name and pixel glyphs) and `test_static_save_keeps_frame_anchor_and_sprite_hitbox` in `tests/tools/test_canvas_panning.py`
- **Files**: `glitchygames/sprites/animated.py`, `glitchygames/bitmappy/animated_canvas.py`

### 42. TOML Writers Don't Escape Sprite Names and Descriptions
- **Description**: Both TOML writers wrote `name = "{name}"` and `description = """{description}"""` without escaping, so a description containing `"""` or a name containing `"` or a backslash produced an invalid TOML file that could not be loaded again
- **Status**: Resolved
- **Priority**: Medium (AI-generated descriptions in Bitmappy can contain quotes)
- **Reporter**: Found while fixing the single-frame writer (BUGS.md #39)
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: The values were interpolated into f-strings verbatim in `_save_toml_single_frame` and `_write_toml_sprite_section`
- **Solution**: Names are written with `toml_basic_string` (the escaping added for BUGS.md #44) and descriptions with `toml_multiline_basic_string`, which keeps real line breaks but escapes backslashes, quotes, other control characters and a leading newline (which TOML would otherwise drop)
- **Tests**: `test_names_and_descriptions_needing_escapes_round_trip` (both writers) in `tests/examples/test_examples_sprites.py`
- **Files**: `glitchygames/sprites/animated.py`

### 41. Input Confirmation Dialog Sends Key-Down Events to the Key-Up Handler
- **Description**: `InputConfirmationDialogScene.on_key_down_event` passed unhandled key-down events to `super().on_key_up_event(event)` instead of `super().on_key_down_event(event)`
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the final whole-branch review of `feature/debug-overlay`
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: A copy-paste slip in `glitchygames/ui/dialogs.py` (identical on main): the inactive-input branch of `on_key_down_event` called the base key-up handler, so base key-down handling never ran for the dialog (and its subclasses: New Canvas, Load, Save) and key-up handling ran twice per key press. No other key-down/key-up mix-up exists in `dialogs.py` (the delete-animation and delete-frame dialogs route correctly)
- **Solution**: The branch now calls `super().on_key_down_event(event)`
- **Files Modified**: `glitchygames/ui/dialogs.py`
- **Tests**: `test_input_confirmation_dialog_key_down_inactive_input` in `tests/ui/test_dialogs.py` checks an unhandled key-down reaches `Scene.on_key_down_event` and not `Scene.on_key_up_event`

### 40. Built-In Font Fallback Points at a Missing Path
- **Description**: When no system font can be loaded (PyInstaller-packaged games), `FontManager` fell back to the bundled Vera.ttf via `Path(__file__).parent / 'fonts' / 'bitstream_vera' / 'Vera.ttf'`, which resolves to `glitchygames/fonts/fonts/bitstream_vera/Vera.ttf` (does not exist), so the fallback raised `FileNotFoundError` instead of loading the font
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while choosing the debug overlay's font
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-18
- **Root Cause**: `font_manager.py` already lives in `glitchygames/fonts/`, so the extra `'fonts'` path segment pointed one directory too deep. The existing fallback test mocked `pygame.freetype.Font`, so the bad path was never opened
- **Solution**: The fallback uses `Path(__file__).parent / 'bitstream_vera' / 'Vera.ttf'`, the path `bitmappy.spec`'s comment documents and bundles. No other copy of the wrong path exists (`glitchygames/debug/overlay.py`'s `DEBUG_FONT_PATH` was already correct)
- **Tests**: `TestFontManagerBuiltInFallback` in `tests/fonts/test_font_manager.py` (with `SysFont` raising `TypeError` or `FileNotFoundError`, a real freetype font is loaded from a file that exists)
- **Files**: `glitchygames/fonts/font_manager.py`

### 39. Single-Frame TOML Save Drops the Description
- **Description**: Saving a single-frame (static) sprite lost its `[sprite] description`
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found while fixing BUGS.md #36
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `_save_toml_single_frame` writes its own `[sprite]` table (it needs `pixels` inside it) and wrote only `name`, `frame_anchor`, `pixels` and the hitbox, while the animated writer (`_write_toml_sprite_section`) also writes `description`. These are the only `[sprite]` keys the loader reads
- **Solution**: The single-frame writer writes `description` in the same format as the animated writer
- **Tests**: `test_static_sprite_metadata_survives_a_save_round_trip` and `test_bundled_sprite_metadata_survives_a_save_round_trip` (name, description, frame_anchor and effective hitbox for every bundled sprite) in `tests/examples/test_examples_sprites.py`
- **Files**: `glitchygames/sprites/animated.py`

### 38. Only One Loop Flag Per Sprite Honoured at Runtime
- **Description**: An AnimatedSprite with a looping and a non-looping animation (cobra: idle loops, strike does not; Papyrus player: jumping/falling do not) used a single `is_looping` for all of them: after loading it was the last animation's `loop`, whichever animation played
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while fixing BUGS.md #34
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `_process_toml_animation` assigned each animation's `loop` to the one sprite-wide `_is_looping`, so the last one won, and `set_animation` never changed it. Only `AnimationStateMachine` applied per-animation flags (from `_loop_flags`), so sprites without a state machine, and direct `play()`/`set_animation()` calls, ignored them. `get_animation_metadata`/`set_animation_metadata` likewise read and wrote the sprite-wide flag whatever animation was named
- **Solution**: `_loop_flags` (filled at load, reset on each load) is the single per-animation store, also used by save (it replaces `_animation_loops` from #34). `set_animation` and the initial animation apply the animation's own flag through `_apply_animation_loop_flag`; setting `is_looping` still overrides it until the next animation is set, and animations without a loaded flag leave `is_looping` unchanged. The metadata methods read and write that animation's flag
- **Tests**: `TestPerAnimationLoop` in `tests/sprites/test_animated_sprite.py`
- **Files**: `glitchygames/sprites/animated.py`

### 37. PaddleSlap Ball-Ball Collisions Leave Stalled, Vertical or Flat Balls
- **Description**: After ball-ball collisions PaddleSlap balls could end up nearly stopped (e.g. (13, 1) px/s), nearly vertical (e.g. (14, 218) px/s, bouncing between the top and bottom walls for 1000+ frames without reaching a paddle in a headless paddle-AI run), or flat (vy = 0, sliding along a wall)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: Not an error in the physics: `_apply_elastic_collision` is an exact equal-mass elastic exchange (the recorded (96, 136) + (-160, 43) -> (-78, -38) + (14, 218) collision conserves momentum and kinetic energy to rounding, with the contact normal from the balls' centres). Exact physics legitimately produces these outcomes: a head-on hit on a slower ball hands over nearly all its speed, and the exchange can leave any heading. PaddleSlap had no rule keeping a ball playable after a ball-ball collision, unlike its serves, which `ServeSettings` keeps between 15 and 60 degrees from horizontal
- **Solution**: A deliberate game-design rule (kept by user decision): it is not momentum-conserving, and it exists to prevent stalled, vertical and flat balls. The physics step is unchanged (the 2328-case collision sweeps still check swapped velocities, a mover that stops dead and conserved momentum and energy). `Game.update()` then runs `_keep_collided_balls_playable()`: each ball that collided this frame gets its velocity's angle from horizontal moved into its own `ServeSettings` band (keeping each component's sign; a zero component points away from the partner) and its speed raised to at least its serve speed (`_keep_ball_playable`). The rule conserves each ball's speed when it only turns it, adds energy only when it raises a slow ball's speed, and does not conserve momentum; balls already serve-like are untouched. A 3000-frame paddle-AI harness run had no stalled, vertical or flat balls afterwards (the same check found 1052 samples before)
- **Tests**: `TestBallPairPlayability` in `tests/collision/test_ball_paddle_collision.py`; `test_update_keeps_collided_balls_playable_after_ball_collisions` in `tests/examples/test_paddleslap.py`; the existing sweeps in `tests/game_objects/test_ball_collision_physics.py`
- **Files**: `glitchygames/examples/paddleslap.py`

### 36. Saving a Static Sprite With an RGBA Color Blanks Its Pixels
- **Description**: `toadstool.toml` came back from load -> save -> reload as a blank 16x18 grid: every pixel was written as `.`
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: The file is valid; the static (single-frame) writer was wrong. toadstool declares one color with an `alpha` field (the unused magenta `"█" = { ..., alpha = 255 }`), so the loader gives the frame RGBA pixel tuples such as `(0, 0, 0, 255)`. `_build_toml_color_map` keys opaque colors as RGB (`(0, 0, 0)`) when no pixel has partial alpha, and `_save_toml_single_frame` looked pixels up by exact tuple equality, found nothing and silently wrote its default character `.` (which toadstool maps to black). The animated writer was unaffected because it uses `lookup_pixel_char`, which matches RGBA pixels against RGB keys
- **Solution**: `_save_toml_single_frame` converts pixels with the same `_convert_pixels_to_toml_chars` as animated saves (which raises `KeyError` for a color missing from the map instead of writing a default character). Note: colors that no pixel uses are not written back, so toadstool's reloaded pixels are RGB tuples rather than RGBA; the colors are identical
- **Tests**: `test_bundled_sprite_pixels_survive_a_save_round_trip` (every bundled sprite TOML, static and animated, compared as RGBA) in `tests/examples/test_examples_sprites.py`
- **Files**: `glitchygames/sprites/animated.py`

### 35. TOML Save Turns the Visible-Pixel Fallback Into Explicit Hitboxes
- **Description**: Saving a sprite without hitboxes wrote a `[sprite.hitbox]` (the union of all frames' visible bounds) and an `[animation.frame.hitbox]` for every frame, so a load -> save added hitboxes the author never defined (colors, glimmer, scarab, gold_scarab) and froze them: later edits to the art no longer changed the collision shape, and the sprite-level default no longer reached frames
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `_build_toml_data_structure` fell back to `_auto_compute_envelope_hitbox()` when `default_hitbox` was None, and `_create_toml_frame_data` fell back to `compute_bounding_box_from_pixels()` when a frame had no explicit hitbox. Both date from before the visible-pixel default existed, when a written hitbox was the only way to get a tight one
- **Solution**: Save writes `[sprite.hitbox]` only when `default_hitbox` is set (loaded or set in code/Bitmappy) and a per-frame hitbox only when `SpriteFrame.has_explicit_hitbox`; `_auto_compute_envelope_hitbox` was removed. Nothing in Bitmappy or the tests relied on the synthesised sections (Bitmappy only carries explicit hitboxes, in its viewport save). Note: a magenta-keyed (non-alpha) `AnimatedSprite` saved without a hitbox now collides as its full frame, like one loaded without a hitbox (see the CLAUDE.md caveat)
- **Tests**: `test_bundled_hitboxes_survive_a_save_round_trip_unchanged` (every bundled sprite, with and without hitboxes) in `tests/examples/test_examples_sprites.py`
- **Files**: `glitchygames/sprites/animated.py`

### 34. TOML Save Loses Animation Timings and Loop Settings
- **Description**: Loading an animated sprite and saving it (as Bitmappy does) wrote `frame_interval = 0.5` and `loop = true` for every animation and dropped per-frame `frame_interval` overrides, so every bundled animation (cobra, gold_scarab, the Papyrus player, scarab, scorpion, colors, slime-jump, ghosty) came back at 0.5 s per frame and the cobra's strike and the player's jump/fall animations started looping
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: `AnimatedSprite._build_toml_data_structure` hard-coded `'frame_interval': 0.5` and `'loop': True` in every `[[animation]]` entry, and `_write_toml_animations` never wrote a per-frame `frame_interval`. The loader kept the timing only as each `SpriteFrame.duration` (and the last animation's loop in `_is_looping`)
- **Solution**: The loader records each animation's `frame_interval` and `loop` (`_animation_frame_intervals`, `_animation_loops`). Save writes them back (`_build_toml_animation_entry`); animations without a loaded value (built in code or Bitmappy) use their most common frame duration. A frame gets a per-frame `frame_interval` only when its duration differs from its animation's, so the file's structure is reproduced. Bitmappy's viewport save copies the settings with `AnimatedSprite.copy_animation_timing_from`; the full save already saves the loaded sprite
- **Tests**: `test_bundled_animation_timings_survive_a_save_round_trip` (parametrized over every bundled animated sprite) in `tests/examples/test_examples_sprites.py`; `test_viewport_save_keeps_animation_timing` in `tests/tools/test_canvas_panning.py`
- **Files**: `glitchygames/sprites/animated.py`, `glitchygames/bitmappy/animated_canvas.py`
- **Note (2026-10-18)**: Bitmappy's panned-viewport save (`save_animated_sprite` / `_save_viewport_sprite`), mentioned in the entries above, was unreachable from the editor and was later removed; planned item D11 (`plans/2026-10-18-level-tools-d-bitmappy-updates.md`) replaces its purpose.

### 33. PaddleSlap Balls Collided as Their 20x20 Image; Half-Pixel Collision Rects 1 px Off
- **Description**: PaddleSlap balls bounced off paddles and walls, and were killed off-screen, by their full 20x20 image instead of the radius-5 circle players see (turning around 5 px before a wall, killed 5 px late). A ball at x = 10.5 was drawn at 11 but collided at 10
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: (1) Collision rects were the sprite's whole image rect, transparent margin included, and `BallSprite.dt_tick` found paddles by scanning its groups with an image-rect test. (2) `get_collision_rect` placed rects at `round(world_x)` (Python's round-half-even: 10.5 -> 10) while the ball draws at its `pixel_snap_mode` (NEAREST_HALF_UP: 10.5 -> 11)
- **Solution**: Hitboxes default to the image's visible pixels (`glitchygames/collision/bounds.py`; `TRIM_TRANSPARENT_HITBOX = False` opts out) and collision rects start at the sprite's own snapped position (`glitchygames/pixel_snap.py`). PaddleSlap pairs balls with paddles through `CollisionManager.check_overlap('balls', 'paddles')`, and `BallSprite.handle_paddle_collision` does an exact circle-vs-rect check, placing the visible edge flush on the face the ball came in through. Wall bounces, overshoot mirroring, the off-screen kill and the serve margin use the visible rect (`BallSprite._visible_rect`)
- **Tests**: `tests/collision/test_ball_paddle_collision.py`; `tests/collision/test_ball_visible_walls.py`; `TestOpaqueBounds`, `TestVisiblePixelCollisionRect` and `test_snap_mode_sprite_rounds_half_up` in `tests/collision/test_collision.py`; `tests/examples/test_paddleslap.py`
- **Files**: `glitchygames/collision/bounds.py`, `glitchygames/collision/detection.py`, `glitchygames/collision/layers.py`, `glitchygames/pixel_snap.py`, `glitchygames/game_objects/ball.py`, `glitchygames/examples/paddleslap.py`

### 32. Gold Scarab Frame Drawn With a Notch
- **Description**: The gold scarab's third frame had a notch in its right edge
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: Frame 2, row 2 of `gold_scarab.toml` was 9 characters wide instead of 10; the loader pads short rows with their last (transparent) character
- **Solution**: Restored the missing pixel; a test checks that every bundled sprite's rows are equal width
- **Tests**: `test_bundled_sprite_rows_have_equal_lengths` in `tests/examples/test_examples_sprites.py`
- **Files**: `glitchygames/examples/brave_adventurer_papyrus/sprites/gold_scarab.toml`

### 31. Two Simultaneous Enemy Contacts Cost Two Lives
- **Description**: In Brave Adventurer and Papyrus, touching two enemies in the same frame lost two lives and respawned twice
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: The collision manager calls the player-enemy callback once per overlapping pair, and each call ran `_player_die`
- **Solution**: The enemy callback kills the player at most once per collision pass and never while the player is respawning
- **Tests**: `TestOneDeathPerHit` in `tests/examples/test_brave_adventurer_game.py`
- **Files**: `glitchygames/examples/brave_adventurer/game.py`, `glitchygames/examples/brave_adventurer_papyrus/game.py`

### 30. Ledge Land/Fall Oscillation; Feet Off the Ground
- **Description**: A player standing at a ledge or wall-top edge landed, fell and landed again forever (20 landings in 40 frames). Brave Adventurer's figure floated 1 px above the ground; Papyrus feet sank into or floated above the ground as the animation changed frames; players stopped short of walls (Papyrus about 12 px) and of the world's left edge, and a dt hitch could push a fast player through a wall
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: (1) Ground support used the current frame's hitbox, and falling frames and poses are wider than idle ones (Papyrus idle 6..28 vs falling 0..40), so an idle player off an edge fell, was caught by the wider falling hitbox and landed again. (2) Terrain used the drawn image size (Brave's feet end 1 px above its 48 px image; `PAPYRUS_PLAYER_WIDTH` was the full 40 px drawn width while the hitbox is 22 px at offset 6; the world-edge constraint stopped the image, not the hitbox). (3) Papyrus frames are top-aligned with visible bottoms from 24 to 27 rows, so a fixed foot line could not match every frame. (4) Walls pushed out on the side of the hitbox centre, which a long frame can carry past the wall's centre
- **Solution**: Support uses a stable x-span shared by every frame and pose (`AnimatedSprite.common_hitbox_x_range()`, Brave's per-facing pose intersection, `_player_support_span`). Terrain, walls, world edges, scarab ground and Clockwork Keep platforms work from `get_sprite_collision_rect` and `collision_rect_offset`. Opt-in `AnimatedSprite.frame_anchor` (`FrameAnchor`) moves each frame so its hitbox bottom lands on the reference hitbox's; the Papyrus player uses BOTTOM on the 27-row foot line. Walls push out on the side the hitbox was on before this frame's move (`_entered_wall_from_left`)
- **Tests**: `TestTerrainUsesHitbox`, `TestHitboxLooseEnds`, `TestStableSupportAtEdges`, `TestPapyrusFeetAnchoring` and `test_fast_player_*` in `tests/examples/test_brave_adventurer_game.py`; `TestPlatformSupportUsesHitbox` in `tests/examples/test_clockwork_keep.py`; `TestAnimatedSpriteFrameAnchor` and `test_common_hitbox_x_range_is_the_intersection_of_all_frames` in `tests/sprites/test_animated_sprite.py`
- **Files**: `glitchygames/sprites/animated.py`, `glitchygames/collision/layers.py`, `glitchygames/examples/brave_adventurer/game.py`, `glitchygames/examples/brave_adventurer/player.py`, `glitchygames/examples/brave_adventurer_papyrus/game.py`, `glitchygames/examples/brave_adventurer_papyrus/player.py`, `glitchygames/examples/brave_adventurer_papyrus/constants.py`, `glitchygames/examples/clockwork_keep/game.py`, `glitchygames/debug/panels.py`

### 29. Papyrus Hitboxes Not Scaled 2x Nor Mirrored When Facing Left
- **Description**: Papyrus player and enemy hitboxes covered only the top-left quarter of the drawn sprite, and facing left they kept the unflipped offset (an 8 px gap walking left into a wall, and wrong world-edge, ledge and enemy contact)
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-18
- **Date Resolved**: 2026-10-18
- **Root Cause**: TOML hitboxes are in native pixels, but Papyrus draws every sprite at `SPRITE_SCALE = 2` and flips the image when facing left; `AnimatedSprite.hitbox` applied neither
- **Solution**: `AnimatedSprite.hitbox_scale` multiplies explicit, default and trimmed hitboxes (set by `prepare_papyrus_sprite` right after loading, so hitboxes are scaled before the first tick), and `AnimatedSprite.hitbox_flip_x` mirrors them within the drawn frame width; Papyrus sets it wherever it flips the image
- **Tests**: `TestPapyrusHitboxScale` and `test_freshly_constructed_sprites_have_scaled_hitboxes_before_any_tick` in `tests/collision/test_collision.py`; `TestPapyrusFacingLeftHitbox` in `tests/examples/test_brave_adventurer_game.py`; `test_hitbox_scale_*` and `test_hitbox_flip_x_*` in `tests/sprites/test_animated_sprite.py`
- **Files**: `glitchygames/sprites/animated.py`, `glitchygames/examples/brave_adventurer_papyrus/sprite_utils.py`, `glitchygames/examples/brave_adventurer_papyrus/player.py`, `glitchygames/examples/brave_adventurer_papyrus/enemies.py`, `glitchygames/examples/brave_adventurer_papyrus/constants.py`

### 28. Resume Paused Again Immediately; Pause Screenshot One Frame Behind
- **Description**: Clockwork Keep and Brave Adventurer paused again one frame after resuming. PaddleSlap's pause screenshot showed the previous frame while the game state was one frame ahead (the ball sat off its hitbox and jumped a frame on resume)
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Debug overlay review
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-18
- **Root Cause**: (1) Games that paused by setting `next_scene` never cleared it, so after resuming, the loop's end-of-frame check switched to the old pause scene again. (2) `Scene.pause()` switched mid-frame, during event processing, after sprites had already moved but before they were rendered. The first fix for (1) reset `next_scene` on the scene becoming active, which wiped the `next_scene` that bootstrap scenes (`joystick_demo`, `scripts/cached_fonts.py`) set in `__init__`, so they never left their first scene
- **Solution**: `Scene.pause()` requests the switch via `next_scene`, which the loop performs after rendering. `SceneManager.switch_to_scene` clears the outgoing scene's pending switch (`outgoing.next_scene = outgoing`) and leaves the incoming scene's alone (`_clear_outgoing_scene_pending_switch`, also called by `_start_transition`, so a scene left through a transition cannot bounce back to a stale `next_scene` when it is returned to); the end-of-frame check is `SceneManager._switch_to_requested_scene`
- **Tests**: `test_pause_requests_a_pause_scene_after_this_frame`, `test_bootstrap_scene_reaches_the_scene_its_init_requests` and `test_resumed_scene_does_not_switch_back_to_the_old_pause_scene`, `test_scene_left_through_a_transition_does_not_switch_back_on_return` and `test_bootstrap_scene_reached_through_a_transition_still_hands_over` in `tests/scenes/test_scene.py`; `tests/scenes/builtin_scenes/test_pause_screen.py`
- **Files**: `glitchygames/scenes/scene.py`

### 27. Live Voice Clicks at Chunk Boundaries
- **Description**: A steady "click click click" was audible at the 100 ms live-voice chunk boundaries during the Clockwork Keep elevator ascent (the cut at arrival is accepted)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: User
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-17
- **Root Cause**: The synthesized samples are clean (an SDL disk-driver capture of the motor, 3.9 s, had no gaps, no discontinuities and a smooth onset). pygame-ce's mixer imports `PyGILState_Ensure`, `Mix_ChannelFinished` and `Mix_PlayChannelTimed`: its channel-finished callback takes the GIL to start the queued Sound. While the main thread holds the GIL (Python's default switch interval is 5 ms) the next chunk starts late, leaving a short silence, heard as a click at every boundary. The mixer buffer is 512 samples at 44100 Hz = 11.6 ms. The first probe missed this because it slept between frames (GIL free) and the disk driver is not real-time
- **Measurements**: 2 ms-period thread under game-like load (6 ms of Python work per frame at 60.5 FPS, FastTimer coarse sleep and pure-Python spin). Before: default 5 ms interval, pure spin: median 0.51 ms, p99 6.44 ms, max 6.81 ms; spin yielding with `time.sleep(0)`: p99 6.09 ms, max 6.46 ms. After: 0.5 ms interval and yielding spin: p99 1.16 ms, max 1.18 ms (on a quiet machine; on a heavily loaded one OS scheduling noise dominates the maximum, so the probe's risk check uses the p99 wait against half the mixer buffer: about 2 ms with the fix vs about 6.4 ms with the old interval; see `scripts/audio_glitch_probe.py`)
- **Solution**: (1) `GIL_SWITCH_INTERVAL_SECONDS = 0.0005` in `glitchygames/timing.py`; `GameEngine` calls `sys.setswitchinterval()` with it before `pygame.init()`. (2) `FastTimer.sleep_until_next`'s final spin calls `time.sleep(0)` each iteration so audio callbacks can take the GIL mid-spin. (3) New `glitchygames/audio/diagnostics.py` (gap, discontinuity and edge analysis; `measure_lock_wait`; `dropout_risk`) and `scripts/audio_glitch_probe.py` (`--mode dsp|realtime|both`), which records and measures under game-like main-thread load
- **Tests**: `TestGilSwitchInterval` in `tests/engine/test_engine_initialization.py`; `test_final_spin_yields_the_gil_each_iteration` in `tests/timing/test_timing.py`; `tests/audio/test_diagnostics.py`
- **Files**: `glitchygames/timing.py`, `glitchygames/engine/game_engine.py`, `glitchygames/audio/diagnostics.py`, `scripts/audio_glitch_probe.py`, `CLAUDE.md`

### 26. Paced Frames Measured in Whole Milliseconds; Fractional Target FPS Truncated
- **Description**: In Clockwork Keep (target 60, default pygame timer) the target-relative FPS histogram showed 68.5% of frames in "90-99% (54-59)" and 31.5% in ">=100%", although the game ran at a steady 60 FPS
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: User
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-17
- **Root Cause**: (1) With the `pygame` timer backend, `PygameTimer.ns_now()` is `pygame.time.get_ticks() * 1_000_000` (whole milliseconds), and `SceneManager._handle_frame_pacing` overwrote `self.dt` from those timestamps. A 16.67 ms cadence was measured as 17, 17, 16 ms (58.8, 58.8, 62.5 FPS, the reported 2:1 split), and `_track_performance` records `1 / self.dt`, so paced frames were quantized again (the uncapped path was fixed in #25, this path was not). (2) `SceneManager.start` called `timer.start_frame(int(self.target_fps))`, truncating fractional targets (60.5 became 60), and both timers computed `1_000_000_000 // target_fps`
- **Solution**: (1) Paced `dt` is measured with `time.perf_counter()` from a frame start recorded in the main loop; deadlines still use the timer's own clock. (2) The `int(...)` truncation was removed; `start_frame(target_fps: float)` in both timers returns `round(1_000_000_000 / target_fps)` (0 when not positive), and `target_fps` attributes are annotated `float`. For integer targets the period is now rounded rather than floored (60 FPS: 16_666_667 ns instead of 16_666_666). (3) `--timer-backend` now defaults to `fast` (`pygame` remains a choice); CLAUDE.md updated
- **Tests**: `TestHandleFramePacing` in `tests/scenes/test_scene.py`; `test_scene_manager_passes_fractional_target_fps_to_timer` in `tests/scenes/test_scene_timer_pacing.py`; `TestFractionalTargetFps` in `tests/timing/test_timing.py`; `test_timer_backend_*` in `tests/engine/test_timer_args.py`
- **Files**: `glitchygames/scenes/scene.py`, `glitchygames/timing.py`, `glitchygames/engine/game_engine.py`, `CLAUDE.md`

### 25. FPS Statistics Sampled pygame's 10-Frame Counter
- **Description**: Per-frame FPS statistics held repeated, quantized and stale values. A PauseScene run had 10 frames, 9 at 243.9 (10000/41) and 1 stale 526.3, so the median equalled the minimum. The report also said `dropped top/bottom 5.0%` when no frames were dropped (fewer than 20 frames at 5% drops none)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: User
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-17
- **Root Cause**: With unlimited FPS, `SceneManager._track_performance` recorded `clock.get_fps()` every frame. pygame-ce's `Clock.get_fps()` (1) recomputes only every 10 `tick()` calls, so each value repeats for 10 frames, (2) is `10000 / (milliseconds for the last 10 ticks)`, so values are quantized (357 = 10000/28, 385 = /26, 500 = /20), and (3) carries over from the previous scene because the clock is shared, so a new scene's first samples are stale. The trim label was printed whenever trim_percent > 0 regardless of the frames actually dropped
- **Solution**: `_track_performance` records `1.0 / self.dt` (measured with `time.perf_counter()` in the main loop) on every path, and its unused `timer`/`period_ns` parameters were removed. The trim label is built from the actual `total_frames`/`trimmed_frames` (`no trimming`, `dropped 0 of N frames; the P% setting needs at least M`, or `dropped K frame(s) from each end (P%)`, singular only for exactly 1). The dead `SceneManager._tick_clock()` (same `get_fps()` sampling, never called by the main loop) was removed; its idea is engine audit item #15
- **Related changes**: (a) histogram buckets are ordered numerically instead of lexicographically by string key; (b) the median is the true median (mean of the two middle values for an even count) instead of the upper-middle element; (c) min/max come from all valid frames in both the global and per-scene stats (previously global used untrimmed and per-scene used trimmed data) and the printed lines are labelled `(all frames)` / `(analyzed frames)`; (d) new `one_percent_low_fps` (mean of the slowest 1% of all valid frames) printed after the minimum; (e) selectable histogram mode via `--fps-histogram equal-range|target-relative` (`FpsHistogramMode`, `AdaptiveClamping.set_histogram_mode`): `equal-range` (default) uses exactly 10 equal-width buckets spanning the analyzed min to max, reported as `fps_bucket_width`, with integer range labels such as `450-469`; `target-relative` uses 10% steps of the target FPS (`>=100% (60+ FPS)` down to `<10% (<6)`, non-empty buckets only) and falls back to equal range, saying so in the header, when no target FPS is set; the stats report the mode actually used as `fps_histogram_mode`; (f) the printed histogram lists buckets in ascending numeric order of their lower bound (the bell-curve rearrangement was removed); (g) FPS and frame-time histories use `deque(maxlen=...)` instead of `list.pop(0)` (12.5 us per frame per full 100k list)
- **Tests**: `TestTrackPerformance` in `tests/scenes/test_scene.py`; `TestShutdownStatistics`, `TestHistogramBucketing` and `test_trim_label_*` in `tests/performance/test_adaptive_clamping.py`
- **Files**: `glitchygames/scenes/scene.py`, `glitchygames/performance/adaptive_clamping.py`

### 24. Jumping on a Clockwork Keep Elevator Never Rides It
- **Description**: `_check_elevator()` accepted `jump` as well as `interact`, but the jump handler clears `on_ground` during event processing and `_check_elevator()` requires `on_ground` on the next frame, so jump only ever jumped
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the adversarial audit of the screen shake spec
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-17
- **Solution**: Elevator activation uses interact only; jump always jumps (commit `2850d4f`)
- **Tests**: `TestElevatorActivation` in `tests/examples/test_clockwork_keep.py`
- **Files**: `glitchygames/examples/clockwork_keep/game.py`

### 23. Engine Crashes Without an Audio Device
- **Description**: `pygame.mixer.init()` in `AudioEventManager.__init__` raised an uncaught `pygame.error` when no audio device was available
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found by the adversarial audit of the screen shake spec
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-17
- **Solution**: The error is caught and logged once, and the engine runs silently (commit `ebc2b48`)
- **Tests**: `test_init_survives_missing_audio_device` in `tests/events/test_audio_events.py`
- **Files**: `glitchygames/events/audio.py`

### 22. Mixer Pre-Init Settings Never Take Effect
- **Description**: `AudioEventManager` called `pygame.mixer.pre_init(22050, -16, 2, 1024)` after `pygame.init()` had already started the mixer at (44100, -16, 2) with a 512-sample buffer, so the settings were ignored
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the adversarial audit of the screen shake spec
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-17
- **Impact**: Brave Adventurer generated its sounds for 22050 Hz, so they had always played an octave high at half length
- **Solution**: Deleted the `pre_init` call and documented the real mixer settings (44100 Hz, 512-sample buffer) (commit `ebc2b48`). The Brave Adventurer sounds were restored as written when they moved to the engine synthesizer (commit `bb4b352`), so they now play an octave lower and longer than before
- **Tests**: `test_init_does_not_call_pre_init` in `tests/events/test_audio_events.py`; `tests/examples/test_brave_adventurer_sounds.py`
- **Files**: `glitchygames/events/audio.py`, `glitchygames/engine/game_engine.py`, `glitchygames/examples/brave_adventurer/sounds.py`

### 21. Parallax Backgrounds Never Scroll During Gameplay
- **Description**: `Camera2D.update()` no longer updated parallax layers, so backgrounds stayed frozen at their `snap_to()` position in Brave Adventurer, Papyrus, and Clockwork Keep
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found by the adversarial audit of the screen shake spec
- **Date Reported**: 2026-10-17
- **Date Resolved**: 2026-10-17
- **Root Cause**: Commit `df21435` inserted `snap_to()` between `update()`'s `_clamp_to_bounds()` call and its parallax loop, so the loop became the tail of `snap_to()` (which updated layers twice) and `update()` lost it. Nothing else called `ParallaxLayer.update_scroll()`.
- **Solution**: Parallax layers are updated from `Camera2D.update()` again (commit `afab532`, "Fix parallax layers not following the camera")
- **Tests**: `TestCamera2DParallax` in `tests/test_camera.py`
- **Files**: `glitchygames/camera.py`

### 20. ty Static Analysis Fails (36 Errors)
- **Description**: The `static-analysis` pre-push hook fails at its `ty` step with 36 errors (plus 57 `unused-ignore-comment` warnings) in `glitchygames/` and `scripts/`
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while fixing the pre-push hooks
- **Date Reported**: 2026-10-15
- **Date Resolved**: 2026-10-15
- **Details**: Already failing before the uv.lock re-lock (26 errors with ty 0.0.81 on the same code); the bump to ty 0.0.87 added 10 more. Main kinds: unresolved-attribute (10), invalid-property-type-override (9), invalid-argument-type (7), invalid-attribute-override (4). Worst files: `bitmappy/editor.py` (6), `events/voice.py` (5), `scripts/raw_sprite_loader.py` (4).
- **Solution**: Fixed every error without `cast`/`Any`; the only new suppressions are two commented, targeted ones for SpriteFrame's presence-based `_image_stale` flag. Mostly typing gaps: EditorContext protocol members made read-only properties to match Scene, `set_pixel_data` takes a `Sequence`, the `animations` interface type corrected, singleton `__instance__` declared as a ClassVar, scripts' `log` declared ClassVar and `image`/`rect` no longer pre-set to None, optional `speech_recognition`/`miniaudio` modules checked for None where used.
- **Real bugs found and fixed along the way**:
  - `voice_miniaudio.py`: without speech_recognition installed, defining `MiniaudioMicrophone(sr.AudioSource)` raised AttributeError at import, which the backend registry (catching only ImportError) would not handle; the import is now required so a missing package raises ImportError
  - `film_strip_coordinator.on_frame_removed()` copied `editor.selected_frame` (None after the last animation is removed) into the film strip widget's int `selected_frame`; it now falls back to 0
  - Singleton classes could hand a subclass an instance of a different class found on a base class's `__instance__`; instances are now matched with `isinstance(instance, cls)`
- **Dead code removed (follow-up)**: `AnimatedCanvasInterface.controller_indicators` and `ControllerEventHandler.canvas_controller_indicators` were write-only since they were added in `e117684` (2025-10-24); the canvas draws controller markers from live controller state. `VisualIndicators._update_canvas_indicators()` now only forces a canvas redraw while a controller is in canvas mode (`TestUpdateCanvasIndicators` in `tests/tools/test_bitmappy_event_handlers.py`)
- **Files Modified**: `glitchygames/bitmappy/{protocols,editor,animated_canvas,canvas_interfaces,film_strip_coordinator}.py`, `glitchygames/bitmappy/controllers/visual_indicators.py`, `glitchygames/sprites/{frame,animated,animated_interface,bitmappy_sprite}.py`, `glitchygames/ui/sliders.py`, `glitchygames/events/{voice,voice_miniaudio}.py`, `scripts/{ai_query_inspector,basic,legacy_sprite_loader,raw_sprite_loader,sprite_loader}.py`

### 18. Serve Directions Lopsided (Rightward Serves Never Go Downward)
- **Description**: `BallSprite.reset()` serves leftward balls up or down (90-269 degrees) but rightward balls only up (270-359 degrees)
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found while fixing bug #17
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-15
- **Related problems fixed with it**:
  - Serve angles spanned almost the full half-circle, so near-vertical serves crawled across the field at the 50 px/s minimum (~15 s for 800 px); the minimum-speed patch that compensated caused bug #17
  - The serve position was hardcoded for an 800x480 screen (`randbelow(700) + 50`, `randbelow(375) + 25`): off-screen on smaller windows, unused space on larger ones
  - PaddleSlap overwrote every opening serve with a fixed (250, 125), and its RANDOM_SPEED spawns had their own full-circle angle plus a copy of the #17 minimum-speed sign bug
  - `test_zero_speed_scenarios` passed or failed depending on the random spawn position (a wall bounce flipped Y)
- **Solution**: New `ServeSettings(minimum_angle_degrees=15, maximum_angle_degrees=60, horizontal=EITHER, vertical=EITHER, speed=250, spawn_margin=50)` with validation, `ServeHorizontalDirection`/`ServeVerticalDirection` enums, `BallSprite(serve_settings=...)`, a public `serve(serve_toward=None)` that sets only the velocity, and `reset(serve_toward=None)` that picks a position within `spawn_margin` of the actual screen (centered if there's no room) and then serves. All serve randomness uses one `secrets.SystemRandom()` source. The minimum-speed patch is gone. PaddleSlap's opening balls use `PADDLESLAP_SERVE` (the defaults) and RANDOM_SPEED spawns use `PADDLESLAP_SPAWN_SERVE` (150 px/s); fixed-speed spawns keep (250, 125).
- **Files Modified**:
  - `glitchygames/game_objects/ball.py`
  - `glitchygames/examples/paddleslap.py`
- **Tests**: `TestServeSettings` in `tests/game_objects/test_ball.py`: every horizontal x vertical setting x band-edge/middle angle x coin outcome x `serve_toward` override (324 cases), real-randomness band and four-diagonal coverage, 0°/90° extremes, spawn position at several screen sizes including too-small screens, and validation. PaddleSlap serve tests in `tests/examples/test_paddleslap.py`. The whole suite was also run with serve randomness pinned to both extremes to confirm no test depends on chance.

### 7. Ball Collision Trajectory Bug
- **Description**: A horizontally moving ball doesn't update its trajectory after a diagonal collision
- **Status**: Closed (cannot reproduce; reopen as a new bug if seen again)
- **Date Closed**: 2026-10-15
- **Priority**: High
- **Reporter**: User
- **Date Reported**: Not recorded
- **Files**: `glitchygames/game_objects/ball.py`
- **Notes**: Distinct from resolved bug #4 (perpendicular collisions being skipped entirely). Not reproduced on 2026-10-14: the collision sweep tests (every 15° heading, stationary and moving targets, several speeds) show velocities exchanging correctly in all 2328 cases. Likely superseded by the physics rewrites; candidate to close.

### 17. Serves at 90 and 270 Degrees Go the Wrong Way
- **Description**: About 1 serve in 270 from `BallSprite.reset()` moved opposite to its serve side
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while fixing bug #14
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: The 50 px/s minimum-speed rule took its sign from `speed_x`, but `cos(270°)` is -1.8e-16 and `cos(90°)` is +6e-17 in floating point, so the left-side (rightward) 270° serve became -50 px/s and the right-side (leftward) 90° serve became +50 px/s.
- **Solution**: The minimum speed takes its sign from the chosen serve side.
- **Also fixed**: `test_ball_reset_direction` and `test_ball_reset_position` asserted reset() picked a different value than before, which fails by chance (~1 in 270 for direction); they now pin the random source. `test_boundary_bounce_sound_effects` relied on reset()'s random direction pointing into the wall (failed ~half the time once moving-away balls stopped bouncing); it now sets its velocity.
- **Files Modified**:
  - `glitchygames/game_objects/ball.py` (`reset`)
  - `tests/game_objects/test_ball.py`, `tests/game_objects/test_ball_boundary_physics.py`
- **Tests**: `test_every_possible_serve` checks all 270 possible random serves aim toward their side with both components >= 50 px/s. The ball test suites were also run with reset()'s randomness pinned both up and down to confirm no test depends on the random direction.

### 14. Corner Collision Un-Reflects the Ball
- **Description**: A ball hitting a corner is sent back into the corner, bounces off both walls again the next frame, and (with WALL_BOUNCE speed-ups) gets 4 speed-ups for one corner hit
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Found during the speed-up redesign (bug #13); reproduced 2026-10-14
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: The top/bottom and left/right handlers already reflect the ball, then `_handle_corner_collision()` negates both speed components again, undoing the reflection. Reproduction (speed-ups off): world (5, 5), speed (-300, -300), `bounce_left_right=True`, one `dt_tick(1/60)` leaves the ball at (1, 1) still moving (-300, -300) into the corner.
- **Related problems fixed with it** (all in the wall-bounce path):
  - Contact is detected on the snapped rect but reflection used the float position, so a ball at `world_y = 0.3` (rect.y == 0) was "mirrored" to -0.3, outside the playfield (same on every wall)
  - A ball still within half a pixel of a wall after bouncing (moving away) was bounced again the next frame: another sound and another WALL_BOUNCE speed-up
  - A corner hit applied two WALL_BOUNCE speed-ups and played the sound twice
  - The corner handler teleported the ball to 1 px inside the corner, discarding its sub-pixel position
- **Solution**: `_handle_boundary_collisions()` bounces only off walls the ball touches while moving toward them, records which walls were hit, and plays one sound and applies at most one WALL_BOUNCE speed-up per frame. Edge handlers only reflect velocity. New `_keep_inside_playfield()` mirrors any real overshoot back inside on every frame, bounce or not (a ball found past a wall while moving away is moved back without bouncing). The corner handler now only gives visual feedback.
- **Files Modified**:
  - `glitchygames/game_objects/ball.py`
- **Tests**: `TestBallSpriteWallBounceSpeed` in `tests/game_objects/test_ball.py`: every wall and corner x every 15° heading into it x overshoots (2.0, 0.0, -0.3) x 3 speeds x speed-ups on/off must reflect exactly the hit components, keep speed (or apply one step), end at the mirrored position inside the field, and not bounce again over the next 10 frames; plus balls past a wall moving away or stationary must be moved inside with no bounce, sound, or speed-up. `TestCornerCollisions` now asserts correct corner behavior instead of the teleport.

### 16. BallSprite.bounce() Ignores Speed-Up Settings
- **Description**: `BallSprite.bounce()` hardcodes `self.speed *= 1.1`, bypassing `speed_up_settings` entirely
- **Status**: Resolved
- **Priority**: Low
- **Reporter**: Found during the speed-up redesign (bug #13)
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Details**: Nothing in `glitchygames/` calls `bounce()`; only its own test does
- **Solution**: Removed `bounce()`. It was left over from 2022 angle-based movement: the `direction` it updated no longer affects motion, so its only effect was the hidden speed-up. Real bounces go through the wall handlers and the WALL_BOUNCE trigger.
- **Files Modified**:
  - `glitchygames/game_objects/ball.py`
- **Tests**: `TestBallSpriteWallBounceSpeed` in `tests/game_objects/test_ball.py` replaces the `bounce()` tests: with speed-ups off, bounces off every wall from every 15° heading at 3 speeds must mirror the velocity and keep its magnitude, so any hidden speed change in a bounce path fails; with WALL_BOUNCE, three real bounces give exactly three curve steps

### 15. Continuous Speed-Up Timer Drifts and Drops Intervals
- **Description**: CONTINUOUS speed-ups happen less often than `interval` implies whenever frames don't line up with it
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found during the speed-up redesign (bug #13)
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Details**:
  - `_check_continuous_speed_up()` sets `_last_speed_up_time = current_time` instead of advancing by `interval`, so the remainder of each interval is lost: with interval 1.0, checks at 1.5, 2.4, 3.0, 10.0 give 3 speed-ups instead of 10
  - A long frame or pause applies at most one speed-up (no catch-up)
  - The `>=` comparison on floats can miss by one frame: 0.4 - 0.30000000000000004 < 0.1
  - The timer used the wall clock (`time.time()`), so time spent paused counted toward speed-ups
- **Solution**: The timer now accumulates game time (the `dt` passed to `dt_tick`) and is reset by `reset()`. New `SpeedUpSettings.schedule` (`SpeedUpSchedule`): `FIXED_RATE` (default; leftover time carries over so the rate is frame-rate independent, and a long frame yields one speed-up, not a burst), `CATCH_UP` (every elapsed interval, bursting after a long frame; for deterministic simulations), `MINIMUM_GAP` (the previous behavior: the interval restarts when a speed-up fires). A 1e-9 s tolerance stops float accumulation from delaying a speed-up.
- **Files Modified**:
  - `glitchygames/game_objects/ball.py`
- **Tests**: `TestContinuousSpeedUpSchedule` in `tests/game_objects/test_ball_speed_up.py` checks every schedule x 3 intervals x 5 frame patterns (30/60/144 fps, jittery, long hitches) against a reference model, plus frame-rate independence, burst/no-burst behavior, pause (wall clock) independence, reset, and float accumulation

### 13. Speed-Up Mode Names Don't Match Their Behavior
- **Description**: `SpeedUpMode` names promise growth curves and axes the code doesn't deliver
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while resolving bug #12
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Details**:
  - `LINEAR` multiplies speed by `speed_up_multiplier` each time, which compounds: over n speed-ups speed grows as m**n (exponential growth, not linear)
  - `LOGARITHMIC_*` is identical to `LINEAR`; nothing tapers off
  - `EXPONENTIAL_*` raises the multiplier to a power based on current speed (capped at 2), which accelerates faster than exponential
  - `_X`/`_Y` suffixes don't restrict the speed-up to that axis (all modes preserve the angle)
  - `speed_up()` silently ignores an unrecognized `speed_up_type`
- **Solution**: Replaced the `SpeedUpMode` bit flags with `SpeedUpSettings(triggers, curve, axes, multiplier, interval, max_speed)`. `SpeedUpCurve` LINEAR/EXPONENTIAL/LOGARITHMIC follow their textbook formulas; `SpeedUpAxes` BOTH/X_ONLY/Y_ONLY scale only what they say; `SpeedUpTrigger` CONTINUOUS/PADDLE_BOUNCE/WALL_BOUNCE share one curve per ball. Each speed-up multiplies the current speed by the curve's step ratio f(n+1)/f(n), so collisions between steps are preserved. Settings are validated. The paddle collision's hardcoded 500 px/s cap became `max_speed`. PaddleSlap now uses a true LOGARITHMIC curve (multiplier 1.15, max 500).
- **Files Modified**:
  - `glitchygames/game_objects/ball.py`
  - `glitchygames/examples/paddleslap.py`
  - 14 test files migrated to the new API (no tests removed)
- **Tests**: `tests/game_objects/test_ball_speed_up.py`: exact curve values, settings validation, axes, caps, triggers, reset, and a sweep of every trigger x curve x axes x 24 headings x 3 speeds; deeper per-curve tests in `test_ball_linear_speedup.py`, `test_ball_exponential_speedup.py`, `test_ball_logarithmic_speedup.py`

### 12. Paddle-Bounce Speed-Up Scales Both Axes, Test Expects X Only
- **Description**: `test_paddleslap_speed_up_logic` expects an `ON_BOUNCE_LOGARITHMIC_X` paddle bounce to speed up only `speed.x`; the ball now scales both components (`speed.y` 200 -> 230)
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while restoring a clean test suite
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: `1a9a7fe` (2026-03-31) deliberately changed `BallSprite.speed_up()` to scale both components to preserve the trajectory angle, so `_X`/`_Y` speed-up flags now only choose which component drives the multiplier. The test predates that change and was never re-run because of bug #11.
- **Solution**: Kept the deliberate angle-preserving behavior; updated the test to expect it and documented in `SpeedUpMode`/`speed_up()` that `_X`/`_Y` don't mean single-axis. Naming problems tracked as bug #13.
- **Files Modified**:
  - `glitchygames/game_objects/ball.py` (docstrings only)
  - `tests/examples/test_paddleslap.py`
- **Tests**: `TestBallSpeedUpSweep` in `tests/game_objects/test_ball_speed_up.py`: every paddle/wall flag combination x every 15° heading x 3 speeds checks the heading is preserved and the speed factor matches

### 11. tests/examples/ Silently Never Collected
- **Description**: The 11 tests in `tests/examples/` never ran in the default suite
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Found while restoring a clean test suite
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: `norecursedirs = ["examples", ...]` in `pyproject.toml` (added in `e7ecce6`, 2025-10-05) was meant for the top-level `examples/` directory, but pytest matches these patterns against directory names at any depth, so it also excluded `tests/examples/`. The top-level directory was already outside `testpaths = ["tests"]`.
- **Solution**: Removed `"examples"` from `norecursedirs`, with a comment explaining the trap
- **Files Modified**:
  - `pyproject.toml`
- **Tests**: `tests/test_suite_collection.py` fails if any test file under `tests/` sits in a directory matching `norecursedirs` or has a name `python_files` will not collect

### 10. API Route Test Broken by FastAPI 0.143
- **Description**: `test_app_has_routes` failed with `'_IncludedRouter' object has no attribute 'path'`
- **Status**: Resolved
- **Priority**: Medium
- **Reporter**: Found while restoring a clean test suite
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: The uv.lock re-lock bumped FastAPI 0.141.1 -> 0.143.1, which stores each `include_router()` as an `_IncludedRouter` entry in `app.routes` with no `.path`. The API itself was unaffected (all endpoints still respond); the test inspected framework internals.
- **Solution**: Replaced with tests of the public contract: the OpenAPI schema lists exactly the expected paths, and every documented path/method reaches a handler (no 404/405)
- **Files Modified**:
  - `tests/api/test_api_main.py`

### 9. Logging Mock Leak Broke ~3,300 Tests
- **Description**: The full suite reported roughly 3,300-3,800 setup errors (`'Mock' object is not iterable`, `KeyError: StashKey`); counts varied with test order
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Found while verifying bug #8
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: Eight tests in `tests/events/test_voice.py` patched `'glitchygames.events.voice.logging.getLogger'`, which is the global `logging.getLogger`. pytest's logging plugin calls `logging.getLogger()` at the start of teardown, before mocker undoes patches; it crashed on the Mock, the patch was never undone, and every later test in that worker errored.
- **Solution**: The tests now inject a `voice_logger` fixture (`mocker.Mock(spec=logging.Logger)`) through `VoiceEventManager(logger=...)` instead of patching. A `pytest_runtest_call` wrapper in `tests/conftest.py` fails any test that leaves `logging.getLogger` or `logging.Logger.manager` replaced, restoring the real objects first so the failure cannot cascade.
- **Files Modified**:
  - `tests/events/test_voice.py`
  - `tests/conftest.py`

### 8. Ball-to-Ball Separation Undone on the Next Frame
- **Description**: After two balls collide, the push that separates them is thrown away one frame later, so overlapping balls stay overlapped and can re-collide or stick
- **Status**: Resolved
- **Priority**: High
- **Reporter**: Found while investigating bug #7
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: `Game._separate_overlapping_balls()` (`glitchygames/examples/paddleslap.py`) moves only `rect`. `BallSprite.dt_tick()` rebuilds `rect` from `world_x`/`world_y` every frame, so the separation is discarded. Every other ball movement path updates `world_x`/`world_y` first. Regressed when `1a9a7fe` (2026-03-31) introduced sub-pixel world positions.
- **Solution**: `_separate_overlapping_balls()` now moves `world_x`/`world_y` by the (sub-pixel) separation, then sets `rect` from `round(world)` as `dt_tick` does. (Adding whole-pixel rect deltas to `.5` world values instead disagrees with Python's banker's rounding.)
- **Files Modified**:
  - `glitchygames/examples/paddleslap.py`
- **Tests**: `tests/game_objects/test_ball_collision_physics.py` (`TestBallCollisionSweepStationaryTarget`, `TestBallCollisionSweepMovingPair`): all 2328 sweep cases failed before the fix and pass after

### 6. Anthropic SDK Rejects Bitmappy's Non-Streaming 64k-Token Requests
- **Description**: Every Bitmappy AI request fails client-side with `ValueError: Streaming is required for operations that may take longer than 10 minutes`
- **Status**: Resolved (end-to-end sprite generation pending a funded API key)
- **Priority**: High
- **Reporter**: Found while verifying bug #5
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: The uncommitted `uv.lock` re-lock bumped `anthropic` from 0.30.1 to 0.125.0. Newer SDKs refuse non-streaming requests whose `max_tokens` implies more than 10 minutes, unless a custom timeout is set. Bitmappy sends `max_tokens=AI_MAX_OUTPUT_TOKENS` (64000). `_configure_client_timeouts()` never reaches the Anthropic client because aisuite creates providers lazily on the first request, so `client._providers` is empty at init time. (aisuite 0.2.0 calls it `providers`; the post-construction timeout step was removed by #183.)
- **Solution**: `_initialize_ai_client()` always passes `{'anthropic': {'timeout': AI_TIMEOUT}}` (merged with any ollama config) to `ai.Client()`. Verified a full 64k-token request now reaches the API. Switching to streaming remains a possible future improvement.
- **Files Modified**:
  - `glitchygames/bitmappy/ai_worker.py` (`_initialize_ai_client`)
- **Tests**: `tests/tools/test_bitmappy.py` (`TestInitializeAiClient`)

### 5. AI Errors Never Reach the Bitmappy UI
- **Description**: When an AI request failed (e.g. Anthropic "credit balance is too low"), Bitmappy showed nothing or "AI response was empty"
- **Status**: Resolved
- **Priority**: High
- **Reporter**: User
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: Three compounding problems: (1) the retry decorator retried every exception, including permanent 4xx errors, for up to 5 attempts with backoff; (2) `_process_ai_request()` then re-raised provider SDK exceptions (e.g. `anthropic.BadRequestError`), which are not in `run_ai_worker()`'s caught exception types, so the worker process died and no response was ever queued; (3) `AIManager._process_ai_response()` ignored `AIResponse.error` and always displayed "AI response was empty"
- **Solution**: `_process_ai_request()` returns `AIResponse(content=None, error='<Type>: <message>')` instead of raising; new `_is_non_retryable_ai_error()` gives up immediately on 4xx except 408/409/429 (`RETRYABLE_CLIENT_ERROR_STATUS_CODES`); new `AIManager._handle_empty_ai_response()` shows "AI request failed: <error>" in the AI text box
- **Files Modified**:
  - `glitchygames/bitmappy/ai_worker.py`
  - `glitchygames/bitmappy/ai_manager.py`
  - `glitchygames/bitmappy/constants.py`
- **Tests**: `tests/tools/test_bitmappy_additional.py` (`TestProcessAiRequest`, `TestCreateAiRetryDecorator`), `tests/tools/test_bitmappy_editor_scene.py` (`TestProcessAiResponseErrors`)

### 4. Vertical vs Horizontal Ball Collision Detection Bug
- **Description**: Perpendicular ball collisions (vertical ball hitting horizontal ball) were incorrectly skipped based on relative velocity calculation
- **Status**: Resolved
- **Priority**: High
- **Reporter**: User
- **Date Reported**: Not recorded
- **Date Resolved**: 2026-03-21 (commit c9b9f5f)
- **Root Cause**: Collision detection checked if `dvn > 0` (relative velocity along normal), which can be positive for perpendicular collisions depending on geometry. Complex speed ratio logic then incorrectly skipped valid collisions when speeds were similar (speed_ratio < 1.2).
- **Solution**: Simplified collision detection to only skip when balls are BOTH moving away (dvn > 0) AND not overlapping (distance >= collision_distance). Removed faulty speed ratio check that prevented perpendicular collisions.
- **Impact**: Vertical vs horizontal collisions now processed correctly, no more missed collisions
- **Files Modified**:
  - `glitchygames/examples/paddleslap.py` - Simplified collision detection logic in `_handle_ball_collisions()`
- **Tests**: `tests/game_objects/test_ball_collision_physics.py` (21/21 passing)

### 3. First Pasted Frame Alpha Loss
- **Description**: First frame pasted into a newly created film strip on a per-pixel alpha sprite lost transparency
- **Status**: Resolved
- **Priority**: High
- **Reporter**: User
- **Date Reported**: Not recorded
- **Date Resolved**: 2026-03-21 (commit c9b9f5f)
- **Root Cause**: Code duplication - `_add_new_animation()` created surfaces without `pygame.SRCALPHA` flag, while `_insert_frame_at_tab()` had it
- **Solution**: Created canonical `_create_blank_frame()` helper method with proper SRCALPHA support, eliminated 24 lines of duplicated code
- **Impact**: All new frames (first and subsequent) now properly preserve per-pixel alpha transparency
- **Files Modified**:
  - `glitchygames/tools/bitmappy.py` - Created `_create_blank_frame()` helper, refactored `_add_new_animation()` and `_create_animated_sprite()`
  - `glitchygames/tools/film_strip.py` - Refactored `_insert_frame_at_tab()` to use shared helper
- **Current Locations** (after the bitmappy editor refactor, #87): `_create_blank_frame()` and `_add_new_animation()` in `glitchygames/bitmappy/film_strip_coordinator.py`, `_create_animated_sprite()` in `glitchygames/bitmappy/editor_setup.py`, `_insert_frame_at_tab()` in `glitchygames/bitmappy/film_strip.py`

### 2. Ball-to-Ball Collision Clipping Bug
- **Description**: Balls moving perpendicular (horizontal vs vertical) would clip through each other, getting stuck in repeated collision loops
- **Status**: Resolved
- **Priority**: High
- **Reporter**: User
- **Date Reported**: Not recorded
- **Date Resolved**: 2025-10-24 (commit e117684)
- **Root Cause**: Float separation values (< 1.0) rounded to 0 when assigned to integer rect.x/rect.y positions, leaving balls overlapped after collision
- **Solution**: Ensure minimum 1-pixel separation in each direction where collision normal has significant component, use round() for integer conversion
- **Impact**: Balls can now collide cleanly without clipping, especially in horizontal vs vertical scenarios
- **Files Modified**:
  - `glitchygames/examples/paddleslap.py` - Fixed ball separation logic in `_handle_ball_collisions()`
- **Tests**: `tests/game_objects/test_multi_ball_ball_collision_bounce.py` - No more "(clipping through)" messages

### 1. Ball Movement Speed Inconsistency
- **Description**: Balls sometimes travel faster going left than right and faster going up than down
- **Status**: Resolved
- **Priority**: High
- **Reporter**: User
- **Date Reported**: Not recorded
- **Date Resolved**: 2025-10-24 (commit e117684)
- **Root Cause**: The `speed_up()` method in `BallSprite` was using a flawed logarithmic scaling formula that capped speed increases at 5% instead of the expected 15%, causing inconsistent speed changes over time.
- **Solution**: Replaced the complex logarithmic scaling with simple linear scaling that applies the multiplier directly to both speed components.
- **Files Modified**:
  - `glitchygames/game_objects/ball.py` - Fixed `speed_up()` method
  - `glitchygames/game_objects/ball.py` - Added `round()` calls in `dt_tick()` for precision
  - `glitchygames/game_objects/paddle.py` - Added `round()` calls in `dt_tick()` for precision

## Notes

- All bugs are tracked with discovery date and priority level
- High priority bugs affect core gameplay and should be addressed first
- Medium priority bugs affect user experience but don't break core functionality
- Low priority bugs are minor issues or edge cases
