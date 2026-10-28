# Future Work Backlog

Suggested during the `feature/debug-overlay`, `feature/engine-world-space` and
`feature/gameplay-replay` sessions (2026-10-17 to 2026-10-20) and not done yet. One line per item, with where it is detailed. Review, then promote items into
`plans/engine-audit.md`, a plan, or BUGS.md, or delete them.

## Gameplay replay wrap-up (done)

Merged 2026-10-22: `feature/engine-world-space` as PR #94 (`cd5e5f97`) and
`feature/gameplay-replay` as PR #95 (`bb51239d`), both with GitHub's "Squash and merge"; the
local branches are deleted. The decisions made on the way, for the record:

- ~~**Decide `--rebaseline`'s exit code when input was not delivered.**~~ **Done** 2026-10-20
  (the user chose a new code): `ExitCode.REBASELINE_INPUT_LOST` (7); NEW is still written, and
  differing frames alone still exit `SUCCESS` (`ReplayResult.has_lost_input`).
- ~~**Delete the stale `glitchygames.egg-info/`**~~ **Done** 2026-10-20 (BUGS.md #78).
  `game_entry_point`'s search of every installed distribution in
  `src/glitchygames/testing/replays.py` is kept as a guard against the next stray egg-info.
- **The final review fix round's behaviour decisions** (reviewed with the user 2026-10-20):
  - A game's own `sys.exit(0)` during `--rebaseline`: **changed**; it writes NEW and exits
    `REBASELINE_INPUT_LOST` (a plain replay still exits `REPLAY_DIVERGED`).
  - Held keys record their key codes, no format bump (BUGS.md #83): **kept**; `ActionMap`
    gained scancode bindings (see Input).
  - Saves snapshotted as first opened only for `--record-trace` runs: **kept**.
  - Unwritable outputs refused before the run with `CANNOT_WRITE_OUTPUT`: **kept**, and a
    mid-run write failure now exits `CANNOT_WRITE_OUTPUT` too (BUGS.md #82, fixed).
  - Rumble caching joystick handles per count, and playbacks never rumbling: **kept for now**;
    the user chose the rumble door (Gameplay replay, below), which replaces both.
  - A recorded run's wall clock is `recorded_at` plus the frame clock: **kept**; the
    processing-time comparison was built instead (below).
  - Live supervisors' posts made during a scope are re-posted after it, behind the events the
    scope held: **kept** (it is what lets a supervisor end a playback and then post).
- ~~**Push the branch, open the PR and merge it with GitHub's "Squash and merge"**~~ **Done**
  2026-10-22 (PR #95). The branch's commit hashes that BUGS.md, this file and the plans cite
  (`fead138`, `77ed933` and others) stay on PR #95's Commits tab (and on
  `origin/feature/gameplay-replay` until it is deleted).
- ~~**Delete the plan workspace**~~ **Done** 2026-10-20, after an audit put everything worth
  keeping into the plans, docs and module docstrings (the plans stay in `plans/`).
- ~~**Review and commit the close-out fixes**~~ **Done** 2026-10-21 (`34c99ff`): BUGS.md #79,
  #82 and #84, the scope's joystick rumble, `REBASELINE_INPUT_LOST` and
  `PROCESSING_SLOWER`, content hashes and measurement history, scancode bindings (the golden
  fixtures and bundled demo patched and rebaselined), and certifi 2026.10.19 for
  PYSEC-2026-4320.
- Bugs logged on the branch and still open: BUGS.md #83 (a documented limitation).

## Input

- ~~**Move the example games' positional keys to scancode bindings**~~ **Done** 2026-10-21:
  every control of PaddleSlap (paddles W/S and Up/Down, pause Space), Clockwork Keep and both
  Brave Adventurer editions (movement, jump, interact, run, pause Esc, quit Q) binds a physical
  position (`scancode=pygame.KSCAN_*`; pause and quit too, at the user's call: Q is then the key
  in QWERTY's Q place, A on AZERTY). Fabricated key events (the golden scripts' `press`/`release`, tests)
  take their key's US QWERTY position from `glitchygames.testing.keys.qwerty_scancode`
  (name-based, the same on every machine; it matched this machine's keymap for every key the
  scripts use). The golden replay fixtures and the bundled demo were patched in place (each
  recorded key event given its position; a one-off check proved nothing else changed), not
  re-recorded, and `ScriptedInputSupervisor` posts with `post_input_event`. Later: a rebind
  screen saving `ActionMap.to_dict()` (it already round-trips scancodes).

## Bugs found and not fixed yet

| Item | Where | Notes |
|---|---|---|
| Undoing an animation delete loses its per-frame hitboxes and rebuilds frames on surfaces without SRCALPHA (alpha lost); frame-add and animation-create undo captures still copy `frame.pixels`, which is fragile | `src/glitchygames/bitmappy/history/commands.py` | Found while fixing BUGS.md #53; same family as #51/#53. |
| `CollisionManager.check_overlap` computes each sprite's rect once per pass, so a callback that moves a sprite leaves later pairs using its old rect | `src/glitchygames/collision/layers.py` (documented in the docstring) | Harmless in PaddleSlap; matters for generic reuse. |
| Frame-anchor reference cache doesn't notice a frame hitbox edited in place (only frame add/remove/replace) | `src/glitchygames/sprites/animated.py` (documented) | Nothing edits in place today. |
| Frames loaded from TOML keep magenta (255, 0, 255) opaque (no colorkey, alpha 255), so the visible-pixel hitbox fallback of a magenta-keyed sprite is its whole frame (ghosty: `Rect(0, 0, 32, 32)`) | `src/glitchygames/sprites/animated.py` (loader), `src/glitchygames/collision/bounds.py` | Found while testing the viewport-save hitbox rule; confirm whether games rely on explicit hitboxes or set a colorkey themselves. |
| A real AI request has not been run in the packaged binary (needs an API key or network) | `dist/bitmappy` | Do once by hand to fully close BUGS.md #47. |
| `scripts/raw_sprite_loader.py` cannot start: `BitmappyLegacySprite` calls `Sprite.__init__` without x and y, and `inflate` draws zero-size rects (nothing) | `scripts/raw_sprite_loader.py:~41, ~84` | Found while deleting `legacy_sprite_loader.py` (BUGS.md #46). Tests use only its `deflate`; fix or fold into Galimore import (sub-plan E). |
| ~~`FrameAddCommand._add_frame` copies pixels through `PixelArray.flat` (pygame-ce has no `.flat`), so undoing a frame delete / redoing a frame add fails whenever the frame has pixels~~ | `src/glitchygames/bitmappy/history/commands.py` | Same bug fixed in `AnimationAddCommand` for BUGS.md #51 (use `SpriteFrame.set_pixel_data`). **Done** (#93, `606fa59b`): `FrameAddCommand._insert_frame` (the method's name now) uses `set_pixel_data` on an SRCALPHA frame and restores an explicit hitbox. |
| Undoing an animation delete restores the sprite data but only refreshes existing film strip widgets, so the restored animation appears to get no film strip until strips are rebuilt (`on_sprite_loaded`) | `src/glitchygames/bitmappy/history/commands.py` (`AnimationAddCommand._add_animation`) | Found while fixing BUGS.md #51; not checked in the running app. |
| The animation-delete undo capture keeps frame pixels and durations but not per-frame hitboxes | `src/glitchygames/bitmappy/film_strip_coordinator.py` (`_capture_animation_deletion_for_undo`) | Found while fixing BUGS.md #51. |
| PaddleSlap's `_separate_overlapping_balls` runs after wall and paddle handling, so a ball can sit 1–3 px inside a paddle or past a wall for one frame | `src/games/paddleslap/paddleslap/__init__.py` | Pre-existing, self-correcting next frame. |
| Papyrus sprites keep their unscaled native rect size | BUGS.md #59 | Latent; fixing it needs its own golden expected-difference class. |
| Brave Adventurer's ground and walls stay drawn only because the parallax layers dirty the whole screen | BUGS.md #60 | Fragile; make the terrain `dirty = 2` or document the dependency. |
| Brave Adventurer's and Papyrus's enemies (Cobra, Scarab, Scorpion) still draw in `update()` | `src/games/brave-adventurer/src/brave_adventurer/enemies.py`, `src/games/brave-adventurer/src/brave_adventurer_papyrus/enemies.py` | Harmless while their hitboxes do not depend on the pose (the scarab's bounds are the same at every roll angle); move drawing into `dt_tick` (the pose rule) if they ever do. |
| The memory guard counts about 290 MiB of reclaimable kernel slab (file metadata from the checkout and the installs), flat from before the first test; the kernel reclaims it before it kills, so the guard's figure overstates the run by that much | `tests/memory_guard.py` (`memory.current` less page cache) | Found 2026-10-28 by the test-memory-reduction work (BUGS.md #237: a serial run now peaks at 1409 MiB against the 1600 limit). The owner (2026-10-28): report it, change nothing yet; the guard's summary line and its stop message now name the slab (`memory guard: peak N MiB ... (S MiB of it reclaimable kernel slab)`). With CircleCI's real figures, choose: keep counting it, subtract it at 1600, or subtract it and lower the limit to about 1300. The `uvx` wrapper's 47 MiB is under Developer environment. |
| The multi-ball simulation tests write `ball.rect.x/y` for start positions and separations, which never took effect (the ball's position is `world_x`/`world_y`; rect was rebuilt from it, now by the engine), so every ball starts at its `reset()` serve position, not the drawn random one | `tests/game_objects/test_multi_ball_*.py` | Pre-existing test weakness found in feature/engine-world-space Task 9; set `world_x`/`world_y` instead and re-check the thresholds. |

## Engine roadmap (already in `plans/engine-audit.md`)

- ~~Engine world space (#6) with the `_finish_frame()` consolidation (#15)~~ **Done** on
  `feature/engine-world-space` (see `plans/engine-audit.md`).
- **Next: solid collision (#1) with the rest of balls on `CollisionManager` (#7).** Brave Adventurer
  and Papyrus now duplicate `_player_support_span` / `_entered_wall_from_left`; the solid-collision
  design should absorb them.
- **Level tools / Glitchy Studio (#11):** `plans/2026-10-18-level-tools.md` and sub-plans A–E
  (tilemap format with object layers, Mapsmith, Tilesmith, Bitmappy updates, Galimore import). Each
  needs a brainstormed spec before implementation.
- ~~BUGS.md #19 (ruff PLW0717, overly broad `try` blocks; rule temporarily disabled) is still active:
  62 sites left, all in Bitmappy (see Lint ignores cleanup below).~~ **Done** 2026-10-22
  (`8dc652f2`): every site narrowed, the ignore removed, BUGS.md #19 resolved.

## Sprite file-format detection (2026-10-26, workspace packages part 4)

- **Two `detect_file_format`s remain.** `src/glitchygames/sprites/file_format.py` (moved out of
  Bitmappy; case-insensitive; returns `'toml'` for a `.toml` extension or none and raises
  `ValueError` for any other) serves `AnimatedSprite` and Bitmappy's `AnimatedCanvasSprite`.
  `SpriteFactory.detect_file_format` (`src/glitchygames/sprites/factory.py`; case-sensitive;
  returns `'toml'`, `'yaml'` for `.yaml` or `.yml`, and `'unknown'` instead of raising) answers
  differently for the same file name, though only TOML is supported. Unify them (and their
  callers: `SpriteFactory.load_sprite` and `src/glitchygames/sprites/bitmappy_sprite.py`) in one
  slice.

## Engine tests after Part 3 (2026-10-26, workspace packages part 3)

Part 3 stopped the engine's tests borrowing members (decision 7) and measured the engine's
coverage from the root `tests/` alone before and after each of C2, C3 and C4 (decision 11): no
arc was lost. What follows is left.

- **Engine arcs reached only by root tests that run members.** The engine has no test of its own
  for these; the golden-trace test, the golden-script round trip and the power-on test reach them
  by running the games. They are not gaps (a full run covers them), but each deserves an engine
  stand-in test that reaches it directly. Line numbers are as of 273fa323 and re-checked
  2026-10-26 (none of these files changed since):
  - `game_objects/ball.py`: `dt_tick` (744), `_finish_wall_bounce` (820-821)
  - `animation/state_machine.py`: `evaluate` (291-292), `_switch_to` (342, 346)
  - `physics/body.py`: `get_animation_context` (133)
  - `input/action_map.py`: `handle_event` (401)
  - `audio/recipes.py`: `render` (116-117)
  - `audio/synth.py`: `concatenate` (437)
  - `camera.py`: `update_scroll` (144)
  - `transitions/elevator.py`: `_draw_shaft_walls` (208-209); the `ElevatorTransition` stand-in in
    `tests/world/test_transition_input.py` may reach it now: check before writing a test
  - `sprites/animated.py`: `SpriteAnimation.__init__` (575), `update_nested_sprites` (2663)
  - `engine/game_engine.py`: `_crash_boundary` (2577), `_run_game` (2596); only the power-on
    test reaches them
- **Root-only engine gaps that were there before Part 3.** The root `tests/` alone misses the
  same 5 lines and 7 branches before and after C2 (so they are not from the moves; a full run
  covers them through members' tests or not at all): `collision/layers.py` 72;
  `scenes/scene.py` 1270->1276; `sprites/animated.py` 1096, 1098, 2039-2040 and their branches.
  Give the engine its own tests for them.
- **Member tests import helpers from root test modules** (`tests.collision.test_ball_paddle_collision`,
  `tests.world.test_frame_integration`). Move the shared helpers into non-test helper modules
  both can import.
- **The import guard's blind spots.** `engine_test_imports_of_members` finds literal
  `importlib.import_module`/`__import__` strings but not `importlib.__import__`,
  `builtins.__import__`, `pytest.importorskip` or `importlib.util.find_spec`. The member-test
  naming check (`test_<distribution>*`) matches a prefix with no separator, so
  `test_bitmappyx.py` passes (the unique-name guard still catches clashes).

## Engine tools after Stage D (2026-10-27, workspace packages part 3)

Stage D moved every recording, replay and measurement tool into the engine
(`src/glitchygames/replay/tools/`, `plans/2026-10-26-workspace-packages-3-demos.md`). Left:

- **Paint `--compare-trace`'s ghost layer by layer** (decision 20 of
  `plans/2026-10-26-workspace-packages-3-demos.md`; the user, 2026-10-27, no half measures).
  OLD's items are blended over NEW's finished frame, so OLD's uneaten dot under NEW's Mr. Muncher
  draws over him. Interleave the games' draw layers in one frame (each layer: OLD's at the alpha,
  then NEW's), which needs OLD in the same process: do it when the engine context work makes an
  in-process OLD possible (`plans/2026-10-25-engine-context.md`, the Arcade spike's wrapper in
  `.superpowers/arcade-spike/`), replacing the child process and the per-pixel item rule
  (`replay/tools/compare.py` rule 10, `GhostCompositor`) rather than adding to them.
- **Logical-name collisions with outside packages.** `MEMBER_LAYERS`
  (`src/glitchygames/logical_names.py`) still names our members' packages, so an outside game
  whose package happens to be called `paddleslap` is labelled `games.paddleslap...` in its
  recordings. Kept because a frozen binary or a wheel install has no `pyproject.toml` to read
  the layers from; only `bundled_demos`' default stopped using it (Task D5). Fix: label a package
  by its layer only when it is the installed workspace member (its distribution's name).
- **`--profile` is ignored with a tool that runs in place of the game.** Since D4b, a game-flag
  tool with a game handler (`--record-golden-trace`, `--record-session`, `--measure`,
  `--report`, ...) runs from `GameEngine.__init__` (`registry.run_game_flag_tool`), before
  `GameEngine.start` starts the profiler, so `--profile` prints nothing; before D4b a profile
  was printed. Profile the handler too, or refuse `--profile` with such a tool.
- **Restarting a game through its console script on Windows is untested.** `--verify`,
  `--measure` and the onion skin start the running game again
  (`children.running_game_command`), which on Windows sees a launcher `.exe` in `sys.orig_argv`.
  Verify on Windows.
- **A launcher package's identity.** `console_script_identity`
  (`src/glitchygames/replay/tools/identity.py`, around lines 182-189) takes a console script's
  entry-point package as the game's. For a launcher (one package's script starting another
  package's game), `unmeasured` and the pre-commit hook then judge a different package's demos
  and revision than that game's own `--measure` does. Our nine console scripts are pinned by a
  test; resolve the launched game's package instead.
- **Tool option names are reserved in every game.** Every tool's flag and option is added to every
  game's parser (`registry.add_game_flags`), including generic names such as `report`'s
  `--threshold`, `--minimum-ms` and `--spans`, so a game defining one of them is refused at
  startup, on every run. Since the final Stage D review's fixes the refusal is clear
  (`GameEngine.initialize_arguments`, `reserved_flag_refusal`: exit 64, naming the flag and
  saying the engine reserves it, not an argparse traceback). Ours are pinned by
  `test_no_tool_option_clashes_with_any_of_our_games_arguments`, and the reserved names are
  documented (docs/architecture/gameplay_replay.md, "Tools for any game"). Still deferred: the
  rename to tool-prefixed names (`--report-threshold`) before outside games depend on these.
- **`tests/replay/tools/test_an_unseen_game.py` is slow:** about 94 s serial (20 s under
  `-n auto`), against a 60 s target. Share the built project and installed console script
  between cases, or run fewer `GAME` forms per tool.
- **The debug overlay draws under OLD in `--compare-trace`.** `ReplaySources.draw_overlay` draws
  the onion skin, and `SceneManager` draws the debug overlay before the doors' overlay, so OLD
  covers it. A correct fix is a new doors hook called before the debug overlay, say
  `EngineSources.draw_under_overlays(*, surface)`, implemented by the five `EngineSources`
  (`LiveSources` as a no-op; `HostSources`, `RecordingSources` and `PlaybackSources` forwarding;
  `ReplaySources` drawing the onion skin), with the onion skin moved from `draw_overlay` to it.
- **`--compare-trace` in the browser.** It is not refused up front under Pyodide, where there are
  no child processes; today a browser path has no options to give it. If one ever does, add
  `sys.platform == 'emscripten'` to `compare.compare_trace_refusal`.

From the final Stage D review (`.superpowers/sdd/2026-10-26-workspace-packages-3-demos/
final-review-stage-d.md`, Minors the controller deferred, 2026-10-27; I1-I4, M1, M3, M4, M6 and
the reserved-flag refusal were fixed):

- **M2: children find the project again for themselves.** `glitchygames verify|measure
  --project-root DIR` starts `GAME --verify|--measure` with `DIR` as its working directory
  (`traces.run_game_with_tool`), and the child runs `verify.verify_project_root` (through
  `settings.find_project_root`) again from there. If `DIR` has no `[tool.glitchygames]` and an
  ancestor has one, the parent reads `DIR`'s settings but the child works on the ancestor's
  (other goldens, another pending ledger). Fix: pass the resolved root to the child, through an
  environment variable `verify_project_root` honors (say `GLITCHYGAMES_PROJECT_ROOT`) or a
  hidden option (as `--replay-frame-stream` is hidden: `ToolOption(hidden=True)`).
- **M5: half of decision 17's seed rows run only through the game flag.** The command runs rows
  2, 4 and 6 and the audit refusal (`tests/replay/tools/test_an_unseen_game.py`, `SEED_ROWS`);
  rows 1, 3, 5 and 7 run only as flags, there and in `tests/replay/tools/test_random_seed.py`.
  The command forwards the seed verbatim (`Tool.child_arguments`), so the risk is low, but the
  "every tool, both front ends" constraint is not literally met for the seed table. Fix:
  parametrize `SEED_ROWS` over both front ends (mind the file's run time, above), or record
  there why one front end is enough.
- **M7: "no installed console script" misleads a pipx user.** `children.resolve_game` searches
  only this interpreter's distributions (`game_entry_point`), so a game installed with pipx (its
  console script on `PATH`, in another environment) is refused with "no installed console script
  or importable module has that name". Fix: say "in this Python environment" with
  `sys.executable`, and suggest the script-path or `MODULE:CALLABLE` form
  (`children.unknown_game_message`).
- **M8: game arguments without `--` get no hint.** `glitchygames record-trace mygame
  run.jsonl.gz --resolution 640x480` (no `--`) fails with argparse's "unrecognized arguments".
  Fix: in `command.main`, parse with `parse_known_args` and, for unknown arguments on a tool that
  runs the game, refuse with "(arguments for the game go after a bare --)" (exit 2, argparse's,
  or 64 to match the other usage refusals: decide with the user).
- **M9: `report` on a directory says "no such recording"** (exit 66, `MISSING_INPUT`), which is
  wrong about why (`src/glitchygames/replay/tools/report.py`). A path that exists but is not a
  file is unusable input (65; src/glitchygames/exit_codes.py says so), or say "is a directory".
- **M10a: `compare._accept`'s post-deadline race** (from the D10 review;
  `src/glitchygames/replay/tools/compare.py`, `_accept`, around lines 662-670). When a stranger's
  connection is refused after the connect deadline, the wait ends at once
  (`_never_connected`), though OLD's real child may already be in the listener's backlog. Fix:
  before giving up, accept once more without blocking and check that connection's token.
- **M10b: "behaviour" in `report`'s help** (`registry.TOOLS`, the `report` tool's `help`, from
  scripts/recording_report.py; accepted earlier). The project's prose is American: "behavior".
  Its help text is pinned by the tests that compare it with the script's old parser.

Found while fixing that review (2026-10-27):

- **The command's SIGTERM kills a recording child outright.** `glitchygames record-trace`,
  `record-session` and `replay-trace` wait on their game through `process.run_command`
  (`children.launch_game` with no timeout), so when the command is stopped by a signal,
  `subprocess.run` SIGKILLs the game: its recording is left unclosed (it still reads up to its
  last full frame). `verify` and `measure`'s games are stopped gently
  (`process.run_command_stopped_at_timeout`: SIGTERM, then the kill after the grace period),
  which lets the game's engine close what it writes. Consider the gentle stop for every launch.
- **`unmeasured`'s child has no timeout.** `measure.child_unmeasured` starts a game named
  otherwise than by its console script with `--unmeasured` and `timeout_seconds=None`; a script
  that is no game would hang it as `verify` and `measure` did before `game-timeout-seconds`
  (games from the settings are console scripts, read without starting them, so only `--game`
  names reach it). Give it the same timeout.
- **A rebaseline carries OLD's old absolute paths into NEW** (review m5 of D15, 2026-10-27).
  Every path the tools write into a file is stored relative to the project root
  (`src/glitchygames/replay/tools/settings.py` `stored_path`), but `rebaseline_header`
  (`src/glitchygames/replay/rebaseline.py`, near `header = dict(original_header)`) keeps OLD's
  header as it is: OLD's `options` (its `record_trace` and other path options) and its earlier
  `measurement_runs[*].rebaselined_from`. Rebaselining a recording made before D15 item 4, or
  one recorded elsewhere, so carries absolute paths into NEW; only
  `tests/test_our_stored_paths.py` catches them, and only in tracked files. Fix: pass the
  inherited `options` through `stored_options` and each earlier run's `rebaselined_from`
  through `stored_path`. `stored_options` lives in `src/glitchygames/engine/game_engine.py`,
  which imports `rebaseline.py`, so it must first move below the engine (beside `stored_path`,
  with `registry.path_option_destinations`, whose import would then have to stay light).
- **The startup options block is CRITICAL "for now"** (Part 3 Stage D, Task D18, 2026-10-28;
  the owner: "Log that at critical" ... "Do it for now").
  - Every engine start logs the run's whole options dictionary at CRITICAL
    (`GameEngine._log_the_startup_options`, `startup_options_block` in
    `src/glitchygames/engine/game_engine.py`), so it shows at every level. It prints on every
    launch, and in every engine the test suite starts: a serial `CI=true` run with the WARNING
    live log (as CircleCI's Linux job runs, `PYTEST_WORKERS=0`) printed 408 blocks, 29406 of its
    59466 lines (macOS, 2026-10-28). Under xdist (`nox -s test` locally, `-n 8`) the live log
    shows none; a failing test's captured log still holds its block.
  - Revisit: a direct startup line (stderr, not the log) that tests and the headless tools turn
    off, or CRITICAL only beside a crash (the options logged with the exit-70 traceback).

## World space follow-ups (feature/engine-world-space final review)

- **Clockwork Keep's start-of-scene camera swoop (game design decision):** at scene start the
  camera eases down from world y=0 to the tinker instead of starting on it. It was preserved on
  purpose during the migration so the golden traces match the baseline. A
  `self.camera.snap_to(...)` (or `snap_followed_axes_to`) at the end of `ClockworkKeepScene.setup()`
  would remove it; that changes every floor's opening frames, so it needs a golden
  expected-difference entry. Decide whether the swoop is wanted.
- **Review focus 3 gap:** no shipped game calls `snap_to` in `setup()`, so "a game that snaps in
  setup keeps doing so" is pinned only by `tests/world/test_camera_follow.py::TestSnapToThenAim`
  (function level) and, per game, by the golden traces. Add a frame-level test with a scene that
  snaps in `setup()` if a game starts doing it.
- **Review focus 4 gap:** int `world_x`/`world_y` and the missing-`world_y` `TypeError` are tested
  at function level (`tests/world/test_positioning.py`), not through `_run_scene_frame`
  (positioning calls the same function; acceptable, noted).
- ~~**Review focus 5 gap:** pacing re-anchor after a hitch proven only in the timer tests~~ Done:
  `tests/world/test_finish_frame.py::TestPacingAfterAHitch` runs `SceneManager.start()` with the
  real deadline policy and checks every frame after a 2 s hitch takes exactly one period.
- **WORLD shake, misuse ordering:** a game that calls `camera.update()` in the render phase
  (`update()`) while the engine also aims advances the shake twice that frame and gets no
  double-update warning (the aim ran first and saw no game update). Calls in `dt_tick` are
  handled (one advance, one warning). Remove such calls; consider warning from `update()` itself.

## Gameplay replay

- **Rumble door** (the user chose option c, 2026-10-20): rumble goes through the doors like
  events, saves and devices. Live sends to the real controllers; a recording also writes each
  send (`rumble_sent`: low/high levels, duration, target device) into its frame; a replay
  compares the sends with the recorded ones (a rumble regression is a divergence, as a sprite's
  is) and sends them to nothing or, in a watched replay, to the viewer's controller; a playback
  scope's policy decides per kind (instant replays may rumble, demos stay silent). The door
  owns the device mapping, which replaces the per-count joystick cache
  (`ConnectedRumbleDevices`) and the scope's asked-but-unused counts
  (`SceneManager._rumble_devices_for_scope`).
- **TODO (plan later): physical outputs as recorded events.** The user's direction
  (2026-10-20): an output such as rumble is both an event and a per-frame output record, so it
  can drive more than pygame/SDL (an Arduino over serial, other programmable devices) and leave
  a record of the physical behaviour for playbacks, devices and tools that post-process a
  session. Shape to plan:
  - Command events: a request to do something physical (rumble this controller at these
    levels for this long). Game code, or the game wrapper (the external control API), posts
    one; the engine intercepts the kinds it knows and translates them into the calls (the
    rumble door, a serial sink) instead of handing them to the scene. A wrapper's injected
    commands are input from outside the game, so they go through `post_input_event` and a
    replay serves them (BUGS.md #84's API).
  - Output record: what the engine actually did, per frame (`outputs`: kind, target, payload),
    written by the recorder, compared by a replay (an output regression is a divergence) and
    read by playbacks, devices and tools. A notification event of the same output lets game
    code or a wrapper react to it.
  - Sinks: pluggable per kind (SDL rumble, serial, MIDI out, OSC, DMX); a playback's policy
    picks which sinks it drives (rumble door, above).
  Other candidates worth recording the same way:
  - Haptics beyond rumble: trigger rumble and adaptive triggers (DualSense).
  - Controller lights: DualSense/DualShock light bar colour, player LEDs.
  - Audio cues: which sound or music started or stopped, on which channel, at what volume (audio
    regression checks; syncing lights or video to the game's sound).
  - Speech: text-to-speech lines and the DualSense speaker's audio.
  - Screen effects: shakes and flashes as they start (synced external lights; highlight reels).
  - Game milestones: score changes, lives lost, level start and end, achievements (`GAMEEVENT`
    today; analytics, highlight reels, the external control API's notifications).
  - Save writes: what was written and when (they are sandboxed in a replay; recorded, they could
    be compared).
  - Presentation changes: fullscreen, resolution and window changes.
  Input from such devices (an Arduino's buttons, MIDI in) would come back through the input
  door as device events, recorded as external input like a controller's.
- ~~**Content hashes and measurement history in recordings**~~ **Done** 2026-10-21 (design doc
  `plans/2026-10-20-recording-content-hash-and-history.md`, hashing option "Better"; plan
  `plans/2026-10-21-recording-content-hash-and-history-implementation.md`). The golden fixtures
  and bundled demo were rebaselined (the plan's Task 5, 2026-10-21) and carry one run each.
  Follow-ups: C12 through `recording_content_hash`; a git commit per run if the user decides
  for it; a CI processing-time check needs a baseline rebaselined on its runner (the fixtures'
  times are the developer machine's). A per-frame
  `content_hash` of everything the game did (times left out), and newest-first history lists
  across rebaselines (`processing_seconds`, `content_hash`, a header `measurement_runs`; depth
  constants starting at 10), so the baselines in the repo record behaviour and speed over time.
  The recording-level hash is derived from the frame hashes, not stored.
- ~~**Processing-time comparison**~~ **Done** 2026-10-20: `processing_seconds` per recorded
  frame, `--compare-processing` and `--max-processing-slowdown PERCENT` (exit
  `PROCESSING_SLOWER`, 8); contract in `src/glitchygames/replay/processing.py`, user docs in
  `docs/architecture/gameplay_replay.md`. Follow-ups: a CI job that keeps a baseline recording
  per runner and checks it; the golden fixtures and bundled demo hold no processing times until
  they are re-recorded (the scancode TODO's re-record would add them).
Design: `plans/2026-10-19-gameplay-replay.md`. Master plan:
`plans/2026-10-19-gameplay-replay-implementation.md`, with one sub-plan per part. User docs:
`docs/architecture/gameplay_replay.md`; engine summary in CLAUDE.md ("Clocks", "Gameplay Recording
and Replay").

- ~~**Part 1, replay core**~~ **Done** on `feature/gameplay-replay`
  (`plans/2026-10-19-gameplay-replay-core.md`): the doors (`src/glitchygames/sources.py`,
  `live_sources.py`, `RecordingSources`, `ReplaySources`), the clocks (`src/glitchygames/clock.py`,
  `Scene.game_time`), input snapshots, the devices and saves doors, the supervisor hook and
  control events, trace format 3, `--replay-trace`, `--replay-fps`, `--audit`, golden replay
  fixtures and the doors guard (`tests/test_engine_doors.py`). This replaces the old "Gameplay
  replay" entry; its items (wall-clock reads in gameplay, polled input, reference mapping) are all
  done.
- ~~**Part 2, replay tooling**~~ **Done** (`plans/2026-10-19-gameplay-replay-tooling.md`):
  `--headless` (Task 1: any run on SDL's dummy drivers; replays then run unpaced, print the
  divergence report and exit with `ExitCode` members; it replaced the private `--replay-unpaced`);
  watched replays (Task 2: the `ReplayViewer` outer loop at 60 Hz real time running the recorded
  game's frames from an accumulator, `ReplayControls` for Space pause / `.` step / `]` `[` speed /
  Esc quit with one action per press, the status bar, pausing at a divergence or the end with the
  debug overlay on, and the "Press Spacebar to Start Game Replay" start screen after frame 0 with
  the F3/F4 hint, drawn by the pause screen's `MessageScreen`; KEYDOWN/KEYUP stay unblocked at SDL
  and reach only the replay controls and the debug overlay); step back (Task 3: `,`, Home and D
  restart the replay process at a pause frame, `--replay-pause-at-frame N` rebuilding there
  unpresented and muted, the first process supervising later restarts through a handoff file).
  bookmarks (Task 4: B bookmarks the frame shown, S saves `x.bookmarked.jsonl.gz` with
  `breakpoint` control events that pause a watched replay of the copy; a restart with bookmarks
  saves and replays the copy); the pytest plugin for recordings (Task 5:
  `src/glitchygames/testing/replays.py`); `--rebaseline` (Task 6: `--replay-trace OLD --rebaseline NEW
  --headless` replays OLD's inputs on the current code without stopping at divergences, writes
  NEW atomically with OLD's inputs and the current sprites, prints a summary of the frames and
  sprites that changed and exits `SUCCESS`; `src/glitchygames/replay/rebaseline.py`).
- ~~**Part 3, in-game playback**~~ **Done** (`plans/2026-10-19-gameplay-replay-playback.md`):
  scene starts (`src/glitchygames/scene_start.py`, `replay_arguments`, `CAPTURES_SCENE_START`), the
  playback scope (`src/glitchygames/replay/playback.py`; does not block real input at SDL; real
  input reaches only its "exit playback" check), demos (`play_recording` and the bundled
  PaddleSlap demo, played by its game-over screen when idle, replay-tested by
  `tests/replay/test_bundled_demos.py`), instant replay (`src/glitchygames/instant_replay.py`,
  `INSTANT_REPLAY_SECONDS`, `end_playback` from a supervisor, repeated replays through the
  resume bridge) and ghosts (`src/glitchygames/replay/ghosts.py`).
- **Plain recording over a replay (`--record-trace` with `--replay-trace`) stays refused**
  (`ExitCode.OPTIONS_REFUSED`, 64; `GameEngine._refuse_an_unsound_recording_over_the_replay`),
  pointing at `--rebaseline NEW --headless`, which wires `ReplaySources.last_batch_origins()` and
  `ReplaySources.recording.recorded_frame_fields()` into `RecordingSources` (`replayed=`). A
  watched rebaseline (or `--record-trace` over a watched replay) would need the viewer's held
  frames and keys kept out of the recording; open it only if a use appears.

Follow-ups (not in any plan yet):

- **State snapshots:** serialize game state for fast step-back and instant replay of long
  scenes; today both re-simulate from the scene's start (spec, out of scope). A watched replay's
  step back restarts the process and rebuilds every frame up to the pause frame; an instant
  replay re-simulates the whole scene, so it is refused past
  `MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS` (60 s) and its journal (about 0.5-1.5 MB per minute)
  is dropped then. Snapshots every N seconds would bound both to N seconds of re-simulation and
  let the journal drop frames before the latest snapshot; rollback netcode needs the same.
- **Cheat device spec:** cheatable-field declarations, codes and UI. It plugs into the supervisor
  hook (`SceneManager.add_supervisor`: it runs after the frame's logic and events, so a change
  is drawn that frame and seen by collision on the next) and records each action as a control
  event (`record_control_event(kind='cheat', data=...)`), which a replay must re-apply on the
  same frame: add its kind to `REAPPLIED_CONTROL_EVENT_KINDS` (src/glitchygames/supervision.py),
  as `breakpoint` is, and apply it in a control event handler. Its reads should go through the
  same named fields the external control API would expose (spec section 2, out of scope).
- ~~**Supervisor posts outside a playback scope** (BUGS.md #84)~~ **Done:**
  `recording.post_input_event` (recorded as external input; every replay serves it). Left: a
  `--replay-trace` of a session whose live supervisor posted during a scope still needs that
  supervisor in the replay (`replay/playback.py` Limits): the scope's pump would have to use
  the installed replay's batch origins to tell a served input post from a scope post.
- ~~**Joystick-mode rumble inside a scope**~~ **Done:** each send asks the scope's devices door
  (a device cache of its own, so the live one is untouched) and rumbles no device. Left: the
  scope's rumble controller starts fresh, so its sends can fall on other frames than the
  recording's (documented in `replay/playback.py` Limits).
- **"Take over" handover:** let the player take control part way through a replay. It must end or
  suspend the SDL input block at the handover and switch the doors from recorded to live input.
- ~~**Audit test helper suppressions**~~ **Done:** every child process, the tests' included,
  starts through `glitchygames.process.run_command`, the one `subprocess` suppression.
- Deferred review notes still open: no test pins the first FPS log waiting one interval;
  `selection.get_state_summary` can return `-inf` for `last_update_time` (not strict JSON);
  `ControlEvent` is unhashable; `tests/test_tracing.py`'s `test_unknown_version_is_refused`
  duplicates `test_unknown_format_version_is_rejected_on_open`; `src/glitchygames/tracing.py` uses
  `cast('int', format_version)` where narrowing would do; `open_controller`'s
  `controller.quit()` inside its `except` (`src/glitchygames/input/devices.py`) could hide the
  original error if `quit` itself raises; a save's metadata `version` 1.9 is accepted as 1
  through `int()` (`src/glitchygames/state/manager.py` `_metadata_version`, pre-existing). Resolved by Part 3: `push_scoped_sources` refuses the installed
  sources (`SourcesAlreadyInstalledError`), so `reset_sources` never uninstalls one object
  twice; `start_trace_recording` can only run before the first frame (`install_sources` raises
  `SourcesAlreadyRunningError` after it), when no playback scope can be active, so it always
  wraps the installed doors.
- Bugs found during the replay core and not fixed (BUGS.md, Active): #67 (Bitmappy's
  joystick-event trigger conversion assumes pygame 1's integer axis scale), #68
  (`ControllerEventManager` keys controllers by device index but routes events by instance id;
  resolved 2026-10-22 with #181),
  #72 (`BitmappyMultiControllerEnhancements` stores a duration where a timestamp is expected), #73
  (PaddleSlap sets the `game` logger to INFO at import), #74 (`debug_events` is always False;
  resolved 2026-10-23: it is the `--debug-events` flag now),
  #75 (`pygame_needs_fastevents` compares major and minor separately).

## Headless capture to raw files and a frame/audio ready latch — groundwork for an external control API

User request (2026-10-19). Not planned yet; needs a brainstormed spec. Each part below is a
candidate ticket. The fuller design notes (lossless A/V streaming as its own API separate from the
event/state stream, the packet format, transports, and what to reuse from the replay engine) are in
[`plans/2026-10-20-av-capture-and-streaming.md`](2026-10-20-av-capture-and-streaming.md).

### Headless capture (`--headless DIR`)

- `video.raw`: every presented frame appended as raw RGBA, plus a small sidecar (for example
  `video.json`) giving width, height, pixel format and frame count, so it can be piped to
  `ffmpeg -f rawvideo -pixel_format rgba -video_size WxH -framerate N -i video.raw ...`.
- `audio.raw`: the mixer's final output as raw PCM, 44100 Hz, signed 16-bit, stereo (the engine's
  mixer format). The dummy audio driver plays nothing, so this needs a capture tap on the mix (see
  the latch section below for why a tap alone is not enough in lockstep mode).
- To consider: aligning the two streams by frame number; disk size (a 640×480 RGBA frame is
  about 1.2 MB, so about 74 MB per second at 60 FPS); frame-skip and downscale options.
- Builds on `--headless` (any run, not only replays; Part 2 Task 1 of the replay plans).

### One ready latch per frame (the frame is a packet)

Amended (user and controller decision): one latch tied to the frame, not separate "frame ready"
and "audio buffer ready" flags.

- Each frame is one packet: the presented picture plus exactly the audio that plays during that
  frame. The sample count comes from that frame's duration (about 735 stereo samples at 60 FPS;
  44100 / 60.01 = 734.9), with the fractional sample carried forward to the next frame so the
  stream never drifts.
- The engine sets the latch to 1 when the packet is written; the consumer reads the picture and
  the audio and writes 0.
- **Lockstep mode** (the engine waits for the 0 before the next frame; deterministic and complete,
  which is what an AI consumer needs) requires the engine to render each frame's audio slice
  itself: an offline, per-frame mixing path. pygame's mixer runs on its own real-time thread even
  with the dummy driver, so it cannot simply be tapped while the engine waits. The synth and
  live-voice code (`src/glitchygames/audio/synth.py`, `live.py`) already generates samples; sounds
  played through `pygame.mixer` (`SoundBank`, loaded sound files) would need the offline path too.
  **This is the main design question.**
- **Free-running mode** (the engine never waits): the latch covers frames only. Audio is a
  continuous stream in a ring buffer that the consumer reads at its own pace, with no audio latch.
- Transports to compare: shared memory or an mmap'd file, a local socket, the API. Exposing the
  latch through an API is a later ticket.

### External control API (brainstorm)

- **Observe:** raw pixels (full or downscaled); sprite state as data (the trace sample,
  `glitchygames.tracing.sample_scene_frame`); declared game state such as score, lives and level
  (shared with the future cheat device's named fields); the frame's audio packet and the sounds and
  voices started this frame; frame hashes (`src/glitchygames/replay/audit.py`'s `frame_digest`).
- **Act:** input injection through the doors, as an "external input" source alongside live and
  replay (`src/glitchygames/sources.py`); scripted supervisor actions at the existing hook
  (`src/glitchygames/supervision.py`); time control (pause, step, speed, reset with a seed); save and
  load state (needs state snapshots); scene control.
- **Output:** draw pixels, lines, rects, text and sprites to an overlay layer that is never in
  traces unless asked for; play a voice from a waveform equation or a preset, with duration, pitch
  curve and envelope, through the synth toolkit and live voices; speech through TTS; rumble and
  LEDs.
- **Recording:** start and stop `--record-trace`, fetch the recording, replay it, run `--audit`.
- **Shape:** a Gymnasium-style environment wrapper, `reset(seed)` and
  `step(actions) -> (observation, reward, done, info)`, built on lockstep mode and the seeded
  doors. Transports: shared memory locally, WebSocket or HTTP remotely. Check what
  `src/glitchygames/api/` already provides (today a FastAPI server and client for AI sprite
  generation, `glitchygames-server` / `glitchygames-client`). Security: authentication for remote
  input, rate limits, a read-only spectator mode.

### Where it leads (later epics)

- AI players and testers, whose runs are replayable and auditable.
- Twitch Plays: chat mapped to input, with voting or anarchy modes and per-viewer cooldowns,
  streamed from `video.raw` / `audio.raw` through ffmpeg.
- Remote multiplayer: lockstep input sync on the deterministic doors, checked with frame hashes.
  Rollback netcode needs state snapshots, the same prerequisite as fast step-back and long instant
  replays.
- Spectating by streaming recorded inputs.

### Prerequisites already built (replay Part 1)

The doors, deterministic simulation, recordings, the supervisor hook, the input-blocking helper
(`src/glitchygames/replay/input_blocking.py`), the golden fixtures and `--headless` (any run, not
only replays; Part 2 Task 1).

## Trace format ideas (pending a user decision)

- **A later trace format version (v4; v3 is the replay format):** record each world sprite's world position and snap mode, and the camera
  position and WORLD shake offset, in every frame. Today traces hold only rect and visibility, and
  the golden test samples world and camera positions from the live run (`WorldSampler` in
  `tests/world/test_golden_traces.py`), so a baseline cannot be checked against its own world
  state.
- **Camera-relative traces:** record world sprites in world coordinates (or relative to the
  camera) instead of screen rects, so a change to camera smoothing alone shows up as one camera
  difference rather than as a difference on every sprite.

## Bitmappy

- All Galibmap/GEDIT-derived features (hitbox editor, mirror/rotate, replace colour, colour wells,
  directional templates, tile mode, frame alignment, metadata panel, magenta-key decision):
  `plans/2026-10-18-level-tools-d-bitmappy-updates.md` (D1–D10).
- `plans/future-features.md` (the older feature roadmap, moved from the repo root on 2026-10-18):
  its item 38 (frame alignment command) duplicates plan D's D8.

## Performance and pacing

- Cull pickups by distance before `check_overlap` (Brave Adventurer checks all 46 collectibles per
  frame; each now measures visible pixels, ~0.15 ms/frame). Final review M5.
- Vsync-locked presentation to remove the remaining beat between 60.01 FPS and a 60 Hz display.
- Bitmappy frame cost (measured 2026-10-22, headless, mouse sweeping with the button held half
  the time, `time_bitmappy_drag`-style harness): median 0.88 -> 0.55 ms, mean 1.25 -> 0.70 ms per
  frame after caching the slider gradients (a dirty slider update 120-160 -> 3.3 us), cheaper
  canvas redraws (595 -> 124 us: per-pixel lookups hoisted, the grid as 1 px fills, no empty
  onion layer) and dropping per-frame debug logging. Next steps for the canvas: cache the
  background and grid and draw only pixels on top; then a changed-pixels-only redraw (needs real
  dirty tracking: BUGS.md #178 item 15, hover cells, onion layers, controller boxes wider than
  small cells). `_has_active_controllers_in_canvas_mode` in `canvas_interfaces.py` is now used only
  by its own tests (dead code to remove after a look). `_redraw_animated_sprite` and
  `_get_current_frame_pixels` still build debug-log arguments (`list(frames.keys())`,
  `frame_pixels[:3]`) on every redraw.
- Cache parsed sprite TOML by path: Brave Adventurer Papyrus parses `PapyrusGoldScarab`'s TOML
  once per collectible while building a level (46 times, 3 frames each; found counting log calls,
  2026-10-22). Load time only; every instance gets the same frames.
- **Audit defensive attribute lookups for CPU (user request, 2026-10-21), the engine first.**
  Look for `getattr(self, 'name', default)` / `hasattr` on the engine's own attributes, values
  computed when they may go unused, and conditional chains re-evaluated every frame. Declare
  each attribute once in `__init__` and read it directly: a direct read is cheaper than a
  `getattr` with a default, and it says which state really exists. `GameEngine.measurement_run`
  was one (the rebaseline names its run before `self.timer` was declared; `self.timer` is now
  declared first). Counts on 2026-10-21: `getattr(self` 17 times in `scenes/scene.py`
  (per-frame code), 3 in `engine/game_engine.py`, 4 in `sprites/animated.py`, 6 in
  `sprites/bitmappy_sprite.py`. Measure the per-frame paths (`SceneManager._run_frame_steps`,
  the event dispatch) before and after; keep a lookup only where an attribute really may not
  exist (a duck-typed game object), with a comment saying so.
  Done 2026-10-22: the engine's own state is declared and read directly (SceneManager's
  `_initialized`, jitter and pacing fields, the engine's `timer`, `controller_manager`,
  `live_voice_channels` and `game`; AnimatedSprite's `_animation_order` (None until a file is
  loaded; `has_own_animation_order`), `_color_order` and `_colors_with_per_pixel_alpha`;
  BitmappySprite's `pixels`, `pixels_across` and `pixels_tall`), which also fixed BUGS.md #167.
  Kept, with comments: lookups on game-optional attributes (`player`, `TARGET_FPS`, `args`,
  `icon`, `hidden`, `draw_offset`, `pixel_snap_mode`, `TRIM_TRANSPARENT_HITBOX`), on any sprite
  in a group. The scene lookups went too (the user's choice, 2026-10-22, "Require Scene"): the
  active scene must be a `Scene` (`switch_to_scene` and `request_transition` refuse anything else
  with a TypeError, `scenes.scene.required_scene`), so `scene_start_capture`, `debug_subject`,
  `camera`, `MAX_FRAME_SECONDS`, `PIXEL_SNAP_MODE`, `INSTANT_REPLAY_SECONDS` and the key-press
  journal (`record_key_press`/`forget_key_presses`, now public for the scene manager) are read
  directly, as are the recorder's scene start and `world.aim_camera`'s scene. The gain is a few tens of nanoseconds per frame (a `getattr` with a
  default costs ~16-25 ns, a direct read ~5-17 ns); the per-sprite helpers (`resolve_snap_mode`,
  `is_world_positioned`, `screen_position_for`, collision) make about 1,200 lookups per Brave
  Adventurer frame, ~20 us of ~2 ms, and need their defaults for foreign sprites.
- Deferred from the screen-shake spec (see its known follow-ups in
  `plans/2026-10-17-screen-shake-and-synth.md`): the audio probe capture mode and the spin-window
  power idea.

## Assets and art

- Ghosty sprite: frames 1–7 have inferred outer outlines; canvas screenshots of each frame would
  make them exact (`src/apps/bitmappy/bitmappy/resources/sprites/ghosty.toml`).
- Papyrus player art could be redrawn bottom-aligned, after which `frame_anchor` is unnecessary.

## Galimore

- Summary of the 1998–2001 Galimore code and tools: `docs/galimore.md`.
- Review the survey's read-only decoder (`galimore/tools/galimore_decode.py`) before reusing it in
  sub-plan E.
- Not extracted: the Mac sound resource forks, three nested 2000-04-17 editor zips, and a few files
  with non-ASCII names.
- Do not redistribute the FF3 reference tile rips or the third-party sound samples from the archives.

## Developer environment

- Dropbox syncing test artefacts made the suite run in 10 minutes instead of 46 s. If Dropbox stays
  on, mark `test-results/`, `.coverage*`, `.venv` and cache directories as ignored
  (`xattr -w com.dropbox.ignored 1 <path>`).
- Optional: lazy-import `speech_recognition` so the audio import chain doesn't load `aifc` (its
  deprecation warning is already filtered in `pyproject.toml`).
- ty reports 50 pre-existing `unused-ignore-comment` warnings (identical on main).
- **Bundle the dependencies' license texts into the Bitmappy binary** (found 2026-10-28 writing
  README.md's license obligations). `bitmappy.spec` freezes one executable and collects no
  license files, so a distributed build does not carry pygame-ce's LGPL-2.1, the MPL-2.0 and
  Apache-2.0 notices, or the permissive copyright notices the README lists. Collect them (each
  bundled distribution's `dist-info` license files, e.g. PyInstaller's `copy_metadata`) into the
  build, then remove README.md's "Not yet met" note.
- **Lift the `pytest<=9.1.1` cap** (the owner, 2026-10-28; `pyproject.toml`'s `dev` group). pytest
  9.2.0 removed the private `Node._nodeid`, which pytest-benchmark 5.3.0 (the newest) still reads
  (`pytest_benchmark/fixture.py:88`), so every `benchmark` test errored at setup. Lift it once a
  pytest-benchmark release works with 9.2, then re-run the benchmarks and the memory guard's
  check that pytest still keeps each test's class instance (`tests/garbage_collection.py`).
- **Decide the license-policy findings** (found 2026-10-28 when syft and grype replaced safety
  and pip-audit, `feature/test-memory-reduction`). `nox -s security-scan` fails on
  `scripts/check_licenses.py` until the owner decides each package it lists: an `EXCEPTIONS`
  entry (license, why, reviewer, date), an allowlist change, or removing the dependency.
  - Denied (GPL): `yamllint` (GPL-3.0-or-later, a lint tool).
  - Decided (the owner, 2026-10-28): `pygame-ce` (LGPL-2.1) is an exception, the source tree
    being public on GitHub; `psycopg` (LGPL-3.0-only) is gone with aisuite's `postgres` extra,
    which nothing used; `pyinstaller-hooks-contrib` is an exception, only its Apache-2.0 runtime
    hooks being bundled; MPL-2.0 is allowed (`certifi`, `tqdm`, `pathspec`, `hypothesis`);
    `text-unidecode` is an exception electing the Artistic License.
  - Unreviewed: `pyinstaller` (GPL-2.0-or-later with its bootloader exception).
  - The SBOM is the whole nox venv (dev and docs tools included), not what the binary bundles;
    a runtime-only SBOM for the policy is the other option (`nox -s security-scan`).
- **Run nox without the `uvx` wrapper in CI** (found 2026-10-28 by the test-memory-reduction
  work, `feature/test-memory-reduction`; the owner asked to look at it later).
  - Every CircleCI step runs `uvx --from "nox[uv]==<< pipeline.parameters.NOX_VERSION >>" nox
    -s ...` (`.circleci/config.yml`). The `uvx` process stays alive as nox's parent, holding about
    47 MiB of anonymous memory, which the Linux job's memory guard (`tests/memory_guard.py`,
    `GLITCHYGAMES_TEST_RSS_LIMIT_MB`) counts.
  - Option: install nox once per job (`uv tool install "nox[uv]==<pinned version>"`) and run
    `nox -s ...` directly, so no wrapper process waits on it.
  - It changes the test step of both the Linux and macOS jobs (and the shared commands), so check
    the Windows job and the cache keys too; measure the guard's peak before and after.
- **Stamp each game's build with its own revision** (found 2026-10-26, Part 3 Stage D, Task D3
  review).
  - Since D3, every recorded run names its game's source revision
    (`MeasurementRun.game_source_revision`). It is looked up in the game's package directory
    (`glitchygames.replay.tools.identity.game_source_revision` →
    `build_info.package_source_revision`), in this order: a git checkout that tracks it, then
    `_git_archival.txt`, then `_build_info.json`, else unknown. A ledger row's commit is that
    revision's, the engine's only when no game revision was recorded.
  - The builds stamp only the engine: `noxfile.py` `_build_stamp` (around line 1408) runs
    `scripts/write_build_stamp.py`, which writes `src/glitchygames/_build_info.json` alone.
  - So an installed member wheel (`nox -s build-wheel`, or nox's own non-editable test install)
    and the frozen Bitmappy binary (`build-binary`) have a game package with no checkout, archive
    or stamp. Their recordings now name an unknown game commit; before D3 they showed the engine
    stamp's commit.
  - No ledger row is affected today: every path that writes rows runs editable members from the
    checkout (`uv run`).
  - Fix: write a stamp into each game package as well, with `build_info.write_build_stamp` per
    package directory. Either `write_build_stamp.py` takes the members' package directories, or
    `_build_stamp` loops over them. Remove the stamps afterwards, as for the engine's, and ship
    `_build_info.json` in each member's wheel (hatch `artifacts`, as the engine's
    `pyproject.toml` does).
  - Then test that a built member wheel's recording names its game commit with source
    `build-stamp`.

## Upstream issues to file

`docs/quality/upstream_issues.md` holds each one with its evidence, reproduction, workaround and
drafted issue text. Not posted yet:

- griffe's `_dataclass_parameters` and mkdocstrings-python's `_test_existing_template` caches
  keep every `mkdocs serve` rebuild alive (BUGS.md #213; worked around in
  `scripts/mkdocs_hooks.py`'s `on_post_build`).

## Code quality

- **Lint caps shape the replay classes.** `GameEngine.__init__` and `ReplaySources.__init__`
  sit at the statement limit, `ReplaySources` and `PlaybackSources` at the public-method limit
  (PLR0904), and `GameEngine.start` at the complexity limit. Several shapes come from that:
  `decoded_replay_sources` is a module function, bookmarks save through a collaborator
  (`sources.bookmarks.save()`), `is_fast_forwarding` is a plain attribute, `record_frame`'s
  optional fields are `TypedDict`/`Unpack` keywords, and the processing collector rides on
  `ReplayResult`. The next change to these classes hits the same walls; split them (with the
  SceneManager extraction below) rather than squeezing more in.

- **Extract the playback scope's bookkeeping out of `SceneManager`** (final review of
  `feature/gameplay-replay`, item C6; deferred). `src/glitchygames/scenes/scene.py`'s `SceneManager`
  carries the scope's entry and exit (`_enter_playback`, `_exit_playback`, the stashed live rumble,
  scope-owned supervisors and handlers, discarded scope posts) and the instant-replay journal's
  begin/resume/journal steps. Split them into collaborators the scene manager calls at fixed
  points: a `PlaybackScopeController` (enter, exit, ownership of what the scope's code adds) and a
  `JournalKeeper` (the journal's lifecycle). The two-sources-of-truth bug the review found is
  fixed (`SceneManager.in_playback_scope` is the one answer); this is the structural follow-up,
  with no behaviour change (the replay, playback and golden tests must pass unchanged).
- **A content hash of the played recording in the `playback` marker** (final review, item C12;
  optional, not done). Adding `recording_sha256` (of a demo file's bytes) to the marker's data would
  make a session replay whose demo was re-recorded since diverge at the scope's first frame, naming
  the cause, instead of at a later sprite. Needs the marker's shape changed in
  `src/glitchygames/recording.py`'s docs and the tests that assert it; instant replays (in memory, same
  run) gain nothing from it.
- **Audit dataclasses for conversion to pydantic** (user request, 2026-10-20; lean yes unless there's
  a good reason not to). `src/glitchygames/` has ~49 `@dataclasses.dataclass` structures across ~30 files
  (`git grep -n "@dataclasses.dataclass\|@dataclass" -- glitchygames`). New data classes already use
  pydantic `BaseModel` (frozen where immutable, `extra='forbid'`; house style in
  `src/glitchygames/api/models/sprite_models.py` and `src/glitchygames/bitmappy/models.py`). For each existing
  one, decide convert or keep and record why:
  - Convert by default — validation at construction and JSON serialization for free; highest value
    first: replay and recording data (`src/glitchygames/replay/`, `recording.py`, `input/state.py`
    `InputSnapshot`, `input/devices.py` descriptors and enumeration answers, `supervision.py`
    `ControlEvent`), configuration (`services/config.py`), save data (`state/`).
  - Good reasons to keep a dataclass: a per-frame hot path where pydantic construction cost is
    measurable (benchmark first — `InputSnapshot` is built once per frame; `effects/shake.py` and
    `input/action_map.py` run per frame); identity/mutation semantics pydantic would change (custom
    `__eq__`/`__hash__`, `cached_property`, deliberately mutable state); trivial private helpers.
  - Keep behaviour identical: equality, hashing, ordering, defaults, immutability, and any JSON shapes
    already written to recordings or saves (golden traces and golden replay fixtures must stay
    unchanged).
  - Output: a short table (class, file, decision, reason, benchmark if any) in this file or the task
    report, then the conversions in reviewed commits.
- **Move the package to a `src/` layout** (user request, 2026-10-20) — DONE (#105, 2026-10-25):
  the engine package moved from the repository root into `src/glitchygames/`, and the games,
  demos and apps got `src/games/`, `src/demos/` and `src/apps/` beside it (design:
  `plans/2026-10-24-workspace-packages.md`). Why: tests and scripts then import the installed
  package (via `uv sync`), never a stray copy from the repository root, which catches packaging
  mistakes (missing package data, wrong includes) before release; it is the layout the Python
  Packaging Authority recommends. What moved or was updated together, in one reviewed change:
  - the build configuration in `pyproject.toml` (package discovery, package data such as fonts,
    sprites and TOML assets, console-script entry points) and the ruff/pyright/ty/vulture/bandit/
    coverage path settings, agreed with the user (the standing rule is not to change linter or
    type-checker config without asking);
  - `noxfile.py` session paths and every documented command (`ruff format src tests scripts
    noxfile.py`), CI configs (CircleCI, GitHub Actions);
  - path-based code and tests: the doors guard (`tests/test_engine_doors.py` scans the package
    directory), the randomness guard, the recording guard, `src/glitchygames/sprites` asset
    lookups, bundled demos, golden harness and fixture paths, `scripts/` that reference engine
    files;
  - the PyInstaller spec (`bitmappy.spec`, at the root), mkdocs/mkdocstrings source paths,
    CLAUDE.md, docs and plans that name `src/glitchygames/...` file paths (the docs scrub after
    #105 wrote them in full and added a guard, `tests/test_suite_collection.py`);
  - verified: `uv sync`, full suite, lint/type checks, mkdocs strict, `nox -s build`.
- **Lint ignores cleanup** (user request, 2026-10-20): planned in
  [`plans/2026-10-20-lint-ignores-cleanup.md`](2026-10-20-lint-ignores-cleanup.md). Phases 1-2
  done 2026-10-21 (the dead `EM101`/`EM102` ignores removed, the `COM812` comment corrected, the
  50 unused `ty: ignore` comments deleted so ty reports nothing, `S311` scoped to
  `src/glitchygames/randomness.py` and the tests). Phase 3 part 1 done 2026-10-21: the 36 broad try
  blocks outside Bitmappy narrowed. Left, carried forward by the user's choice (2026-10-21):
  Bitmappy's 62 `PLW0717` sites (`src/glitchygames/bitmappy/`, `src/glitchygames/sprites/bitmappy_sprite.py`,
  `tests/tools/`; BUGS.md #19), then removing the ignore; `ANN401`; and a decision on `G004`.
  Phase 3 done 2026-10-22 (ignore removed); phase 4: 151 of 152 typed, the last (`events/base.py`'s
  `__getattr__`) waiting on the typed events plan (see the plan); phase 5 done (all logging lazy,
  ignore removed). Phase 4 done 2026-10-22 too (`a8cbd953`): the global `ANN401` ignore is gone,
  and `HashableEvent.__getattr__` keeps a per-file ignore with its reason.
- ~~**Unified input devices**~~ **Done 2026-10-22:**
  [`plans/2026-10-22-unified-input-devices.md`](2026-10-22-unified-input-devices.md): one
  `InputDevice` per physical device so joysticks and controllers run together (BUGS.md #181
  resolved). Follow-ups in BUGS.md #184 (rumble through `InputDevice`, a playback scope's device
  events, a hardware check).
- ~~**Typed events** (proposed 2026-10-22, for review)~~ **Done 2026-10-22** (`a8cbd953`):
  [`plans/2026-10-22-typed-events.md`](2026-10-22-typed-events.md): per-family `HashableEvent`
  subclasses so handlers get real field types (`src/glitchygames/events/base.py`; events immutable).
- ~~**Tests that never run in CI**~~ **Done** by 2026-10-22 (`d1afcb9b`, `6861d0c5`, `80b1900f`,
  `1411160d`; no `pytest.skip` is left in those files): the placeholders were rewritten or removed, the voice and mixed-content tests run,
  `test_transparency_fix.py` is deleted, and the indicator update test runs on one thread (the
  collision manager's callers never call it off the main thread, so no BUGS.md entry); only the
  OS-specific skips in the last item remain, as intended. The audit as written
  (audited 2026-10-21 with `CI=true uv run pytest -rs`; documented
  only, nothing changed). Every collected test runs in CI, but these skip on every CI OS or are
  never collected:
  - 18 Bitmappy placeholders that skip as not implemented: frame insertion and spacing
    (`tests/tools/test_film_tab_functionality.py`, 9), selection state
    (`tests/tools/test_film_strip_navigation.py`, 2), AI strip integration
    (`tests/tools/test_bitmappy_ai_strip_integration.py`, 2), PNG conversion
    (`tests/tools/test_bitmappy_png_loading.py`, 1), `tests/tools/test_bitmappy.py` (2). Implement
    the features or delete the placeholders.
  - A real bug behind a skip: `VisualCollisionManager` is not thread-safe (concurrent updates raise
    `RuntimeError`; `tests/tools/test_multi_controller_edge_cases.py:249`). Log it in BUGS.md.
  - `tests/events/test_voice.py:1038` and `:1074` test the path without `speech_recognition`, which
    the dev extras install, so they always skip. Mock the import away so they run.
  - `tests/sprites/test_animated_sprite.py:288` and `:324` cover mixed content, which no longer
    exists since TOML-only sprites. Delete them.
  - `test_transparency_fix.py` (tracked, repo root) is outside `testpaths`, so never collected, and
    errors in its mock setup when run by hand (`'str' object has no attribute 'start'`);
    `tests/tools/` already covers transparency. Delete it.
  - Run on some CI OSes only, as intended: the `SIGBREAK` tests and the 1 ms timer test
    (`tests/timing/test_fast_timer_os.py`) only on Windows; one timing test is skipped only on
    Windows.
