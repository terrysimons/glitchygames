# Layer Audit: What Crosses Between the Engine and the Games (2026-10-26)

Read-only audit of branch feature/workspace-packages-2-games, after Part 2 moved every game into its
own workspace member. It drives phase 0 of the game samples feature
(plans/2026-10-25-game-samples-design.md, section 0): the engine-owned samples machinery cannot be
built cleanly on top of these leaks. Underscored names were found with an AST scan and checked
against where the engine and the games define them; names a game uses on its own classes are left
out. Line numbers are from the audited tree and drift as code changes.

The rules (the user's): game code uses only the engine's public API; the engine's runtime knows no
game by name; tests belong to their layer (a game's tests import no engine test module; the engine's
tests depend on games only through a deliberate, named seam); tooling holds no per-game knowledge
that belongs in the game; data belongs to its owner.

## 1. Game code to engine private names

- `src/games/drawing-fire/drawing_fire/game.py:473` calls `self._keys_pressed_in_scene.discard`, the
  engine Scene's private set (`src/glitchygames/scenes/scene.py:2919`). Blocks the goal. Fix: a
  public `Scene.forget_key_press(key)`, the counterpart of `record_key_press` (`scene.py:3362`).
- `src/games/brave-adventurer/src/brave_adventurer_modes/launcher.py:37-40, 69-70, 136` parses the
  recording header itself (`replay.driver.GAME_HEADER_FIELD`, `replay.rebuild.REPLAY_TRACE_OPTION`,
  `TraceReader`) to choose which game to replay. Public names, but replay plumbing. Should fix: under
  the samples design the engine dispatches to a wrapped game; the launcher only declares what it
  wraps.
- No `# type: ignore` reaches into an engine object (the four in `paddleslap/__init__.py:126-665`
  are pygame typing).

## 2. Game tests to engine private names, and to engine test or tool modules

Engine private names (16 uses, all should fix; `docs/architecture/game_packages.md:319-323` allows
them for now, but a third-party game cannot rely on them):

- `SceneManager._reset` (8): `brave-adventurer/tests/classic/test_brave_adventurer_classic.py:236,251`,
  `tests/core/test_brave_adventurer_both_editions.py:1167,1182`,
  `tests/test_brave_adventurer_modes.py:82,87`.
- `FontManager._font_cache`: `drawing-fire/tests/test_drawing_fire_drawing.py:442,498`.
- `state_machine._transitions`: `brave-adventurer/tests/papyrus/test_brave_adventurer_papyrus.py:288`,
  `test_brave_adventurer_papyrus_sprite_files.py:136`.
- `scene._keys_pressed_in_scene`: `drawing-fire/tests/test_drawing_fire_game.py:694`.
- `scene_manager._live_audio`: `mr-muncher/tests/test_mr_muncher.py:275,283,688`.

Imports of engine tests or scripts (all block the goal):

- `scripts.record_golden_traces` (the golden harness, `press`/`release`, `command_line`, the private
  `_golden_game`): `paddleslap/tests/test_paddleslap.py:16`, `mr-muncher/tests/test_mr_muncher.py:16-24`,
  `clockwork-keep/tests/test_clockwork_keep.py:12-19`,
  `brave-adventurer/tests/test_brave_adventurer_modes.py:19`, `core/...both_editions.py:15-21`,
  `classic/...classic.py:8`.
- `scripts.simulate_drawing_fire`: `drawing-fire/tests/test_drawing_fire_simulation.py:5-6`.
- `tests.examples.test_examples_sprites` (its test functions called):
  `brave-adventurer/tests/papyrus/test_brave_adventurer_papyrus_sprite_files.py:14,57-98`.
- Hidden: the root `conftest.py:16-22` loads `tests.harness` and `tests.driver_comparison` for every
  member; member tests silently rely on its autouse resets (`tests/harness.py:256-283, 403`, which
  themselves call `SceneManager._reset` and `FontManager._font_cache`).

Acceptable for now: the after-the-move tests in four members import the engine's
`RECORDING_PATH_RENAMES` (history checks; they go when the rename table leaves the engine).

## 3. Engine runtime to game names

- `src/glitchygames/logical_names.py:31-38` `MEMBER_LAYERS` lists every game package; it is also the
  default package list at `bundled_demos.py:24,92` and `testing/replays.py:66,409`. Blocks the goal.
  Fix: derive it from the registered games.
- `src/glitchygames/recording_metrics.py:85-110` `RECORDING_PATH_RENAMES` holds game paths (used at
  `:781`, `:1182`). Blocks the goal. Fix: move it to the quality tooling and key history by sample
  identity.
- `src/glitchygames/transitions/elevator.py:1`: described as "for Clockwork Keep", used only by
  `clockwork_keep/game.py:837`. Should fix: describe it generically, or move it into the member.
- `logical_names.py:23-27` `EXAMPLES_LAYERS` names the demos: an acceptable stopgap until Part 3.
- Prose only, low priority: `randomness.py:33-35` (paddleslap stream names that will go stale),
  `state/manager.py:11`, `host.py:101`, `instant_replay.py:153`, `camera.py:7`, `bundled_demos.py:4-59`,
  `pixel_snap.py:19`, `game_objects/ball.py:354-729`, `input/action_map.py:215`, `sprites/frame.py:217`,
  `sprites/animated.py:185,346`, `replay/controls.py:34`, `replay/processing.py:26`,
  `replay/driver.py:417,2781`, `physics/behaviors.py:92`, `collision/bounds.py:8`, `debug/panels.py:230`.

## 4. glitchygames/testing to game names

Docstring examples only (`testing/replays.py:10,109,131-132,200-205,237-238,359`); the code is
generic apart from the inherited `MEMBER_LAYERS` default (`:409`). Acceptable.

## 5. Engine tests to games (31 files; 23 uses of game private names, mostly `_create_action_map(s)`)

(a) Really about the game: move to the member.
`tests/collision/test_collision.py:624-742` (Cobra; Papyrus hitbox scale) to brave-adventurer;
`tests/game_objects/test_game_over_scene.py:14,154-182`, `tests/collision/test_ball_paddle_collision.py:296-404`,
`tests/game_objects/test_ball_collision_physics.py:529-886`, `tests/game_objects/test_collision_scenarios.py:272-274`
to paddleslap; `tests/animation/test_animation.py:9-13,391-402` (the games' falling thresholds);
`tests/replay/test_golden_replays.py:690` (Drawing Fire's death and takeover).

(b) The game is a convenient real fixture: a stand-in is cleaner (one small synthetic member game, or
`tmp_path`).
`tests/scenes/builtin_scenes/test_pause_screen.py:20,125`, `test_game_over.py:14`;
`tests/world/test_transition_input.py:31,312-330`; `tests/world/test_frame_integration.py:34,1307`;
`tests/world/test_gameplay_recording.py:36,122,890-901,1021-1028`; `tests/world/test_gameplay_replay.py:1013-1018,1451`;
`tests/replay/test_playback_scope.py:18,472`; `tests/replay/test_replay_plugin.py:35,43,133-141`;
`tests/replay/test_bundled_demos.py:23-32`; `tests/test_bundled_demo_discovery.py:18,39`;
`tests/replay/test_instant_replay.py:92,829`; `tests/replay/test_record_scripted_session.py:41-82`;
`tests/test_replay_metrics.py:48-85`; `tests/test_recording_metrics.py:58-89`;
`tests/benchmarks/test_benchmarks.py:37-42,325`; `tests/test_generate_performance_graphs.py:49-50`;
`tests/test_recording_report.py:32-42`; `tests/test_code_tree.py:79-86`; `tests/test_gen_ref_pages.py:23-28`.
Harmless string-only uses: `debug/test_manager_overlay.py:58`, `state/test_paths.py:21`,
`test_mkdocs_hooks_browser_games.py:15`.

(c) Cross-cutting guards over all games: the data should come from the games.
`tests/replay/test_golden_replays.py:44-64,346-374` (`GAMEPLAY_ACTION_MAPS` via private
`_create_action_map(s)`; `DRAWING_FIRE_CONTROLS`, `ENGINE_SCENE_CONTROLS`, `GAMES_WITHOUT_A_PAUSE`,
`UNEXERCISED_CONTROLS` become each game's declared controls, pause flag and excused controls);
`tests/test_browser_touch_controls.py:22-27,66-75,130` (`TOUCH_LAYOUTS` via private action maps:
games declare their touch layout); `tests/world/test_golden_traces.py:31,986` (`EXPECTED_DIFFERENCES`)
and its game-specific world rules (`:1917-2009`), with baselines in `tests/world/golden/*.jsonl.gz`:
the comparator stays in the engine, each game's baseline and expected differences belong to the
game; `tests/engine/test_engine_lifecycle.py:733-743` (`GAME_CONSOLE_SCRIPTS`: derive from the
registry); `tests/test_logical_names.py:23-57` (pins `MEMBER_LAYERS`).
Acceptable (repository-level workspace guards, not engine guards): `test_workspace_packages.py:199-238`,
`test_workspace_config.py:96`, `test_suite_collection.py:260-264`, `test_ci_config.py:214`,
`replay/test_recording_logical_names.py:76`.

## 6. Tooling to per-game knowledge

- `scripts/record_golden_traces.py`, blocks the goal: imports (57-73); `GAME_SCENES:107`,
  `GAME_MODULES:121`, `GOLDEN_TRACE_GAMES:134`; per-game constants (142-181); per-game input scripts
  and robot players (313-734: `clockwork_keep_script`, `brave_adventurer_script`, `PaddleTracker`,
  `paddleslap_script`, `MuncherSteering`, `mr_muncher_script`, `DrawingFireMouse`,
  `drawing_fire_script`); `SCRIPT_BUILDERS:735`; its harness uses engine private names
  (`SceneManager._reset` 810-822, `_run_frame` 826, `_initialize_event_managers` 856). Owners: each
  script belongs to its game (its scripted cpu stimuli); the harness belongs to the engine's public
  testing and samples runner.
- `scripts/record_scripted_session.py`, should fix: `INPUT_ONLY_PLACEMENT_GAMES:139`,
  `POLLED_INPUT_GAMES:144`, `GOLDEN_FIXTURE_NAMES:162`, the controls tails (282-376),
  `CONTROLS_TAIL_BUILDERS:378`. Owner: each game declares its polled input, controls tail and quit,
  and sample names; the recorder belongs to the engine.
- `scripts/build_browser_bundle.py`, blocks the goal: `TOUCH_LAYOUTS:194-218`, `GAMES:252-298`.
  Owner: the game's descriptor (Bitmappy's entry goes with the app).
- `scripts/simulate_drawing_fire.py:19-20`, should fix: move it and its test into drawing-fire.
- `scripts/audit_hitboxes.py:56-75`, should fix: `PRIORITY_TIERS` hard-codes Papyrus's sprite
  directory; discover sprite directories from the registered games.
- `scripts/audio_glitch_probe.py:5,100-108`, should fix: imports `clockwork_keep.constants`; use a
  stand-in voice configuration or move it to the member.
- Docstring examples only, acceptable: `replay_metrics.py:95-103`, `recording_report.py:24`,
  `generate_performance_graphs.py:145`, `gen_ref_pages.py:69`, `workspace_packages.py:29-34`.

## 7. Members to other members

None: every member depends only on `glitchygames`, and no member imports another's package (Brave
Adventurer's four packages are internal to its member). Mr. Muncher's autopilot is game-owned: the
right direction.

## 8. Docs and config that teach a violation

- `docs/architecture/game_packages.md:319-323` allows member tests to use `SceneManager._reset` and
  `FontManager._font_cache`; `:106-111, 171-187, 221-224` make each move edit engine tables
  (`MEMBER_LAYERS`, `RECORDING_PATH_RENAMES`) and engine-test or tool tables.
- `docs/architecture/engine_context.md:40` lists `SceneManager._reset` as API.
- The game docs present `_create_action_map(s)` as the controls contract (`docs/games/paddleslap.md:500`,
  `clockwork_keep.md:663`, `brave_adventurer.md:55,72`) and name `scripts/record_golden_traces.py` as
  owning each game's script (`paddleslap.md:593,629`, `drawing_fire.md:126`, `clockwork_keep.md:699`,
  `brave_adventurer.md:568,802`); `drawing_fire.md:300` describes `POLLED_INPUT_GAMES`.
- `CLAUDE.md:648-662` codifies the same workflow.
- Config: the root `pyproject.toml` is both the engine's distribution and the workspace root, so the
  engine's `games` extra and per-member testpaths and coverage live in the engine's file: an
  acceptable seam, though a third-party engine install still advertises these games.

## Summary

| Direction | Instances | Blocks / should fix / acceptable |
|---|---|---|
| Game code to engine private | 2 | 1 / 1 / 0 |
| Game tests to engine private names | 16 uses in 7 files | 0 / 16 / 0 |
| Game tests to engine tests or scripts | 9 files, plus the root conftest | 9 / 1 / 0 |
| Engine runtime to games | 3 tables or features, plus ~20 prose mentions | 2 / 1 / ~20 |
| Testing to games | prose only | 0 / 0 / 1 |
| Engine tests to games | 31 files (8 move, ~18 stand-in, 5 guards) | 5 / 26 / 5 workspace guards |
| Tooling to game knowledge | 6 scripts | 2 / 4 / 5 |
| Member to member | 0 | 0 / 0 / 0 |
| Docs and config | 9 places | 0 / 8 / 1 |

## The smallest set of public engine APIs that removes most of it

1. A public test-isolation plugin, `glitchygames.testing.isolation`, with `reset_engine_state()`:
   the autouse resets move out of `tests/harness.py`. Ends the `_reset` and `_font_cache` uses, the
   root-conftest dependency and the scripts' private calls.
2. Public controls: `_create_action_map(s)` becomes a public `Scene.action_maps(input_mode)`, plus a
   `Controls` record (pause, quit, polled inputs, excused controls, touch layout). Ends 23 private
   uses, the guard tables in `test_golden_replays` and `test_browser_touch_controls`,
   `CONTROLS_TAIL_BUILDERS`, `POLLED_INPUT_GAMES` and `TOUCH_LAYOUTS`. The samples explorer needs it.
3. A `Game` descriptor registered by composition (target, scene, title, packages, wraps, controls,
   stimuli): replaces `MEMBER_LAYERS`, `GAMES`, `GAME_SCENES`/`GAME_MODULES`, `SCRIPT_BUILDERS`,
   `GOLDEN_FIXTURE_NAMES`, the lifecycle test's `GAME_CONSOLE_SCRIPTS` and the launcher's dispatch.
4. A public stimulus harness in the engine (the scripted-input engine, `press`/`release`,
   `command_line`, `golden_game`), with each game's robot-player script moved into the game. Ends the
   game tests' imports of `scripts.*`.
5. A public sprite-file validator, `glitchygames.testing.sprites.check_sprite_file(path)`. Ends the
   `tests.examples` import.
6. Small accessors: `Scene.forget_key_press`, a read-only `StateMachine.transitions`, and a public
   way to inject `SceneManager.live_audio`.

## For the game samples feature

Its section 5 already takes `MEMBER_LAYERS` (as a game list) and `RECORDING_PATH_RENAMES` out of the
engine. The explorer's declared controls need API 2 first. The existing robot players are the
scripted cpu stimuli the design assigns to the games; moving them is the first concrete step. The
Brave launcher's header parsing is the wrapper dispatch the design gives the engine. The golden-trace
baselines in `tests/world/golden/` are engine-owned game data, against the design's rule that tests
own no samples: they move to the games too.
