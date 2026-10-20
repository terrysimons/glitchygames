# Future Work Backlog

Suggested during the `feature/debug-overlay` and `feature/engine-world-space` sessions (2026-10-17
to 2026-10-18) and not done yet. One line per item, with where it is detailed. Review, then promote items into
`plans/engine-audit.md`, a plan, or BUGS.md, or delete them.

## Bugs found and not fixed yet

| Item | Where | Notes |
|---|---|---|
| Undoing an animation delete loses its per-frame hitboxes and rebuilds frames on surfaces without SRCALPHA (alpha lost); frame-add and animation-create undo captures still copy `frame.pixels`, which is fragile | `glitchygames/bitmappy/history/commands.py` | Found while fixing BUGS.md #53; same family as #51/#53. |
| `CollisionManager.check_overlap` computes each sprite's rect once per pass, so a callback that moves a sprite leaves later pairs using its old rect | `glitchygames/collision/layers.py` (documented in the docstring) | Harmless in PaddleSlap; matters for generic reuse. |
| Frame-anchor reference cache doesn't notice a frame hitbox edited in place (only frame add/remove/replace) | `glitchygames/sprites/animated.py` (documented) | Nothing edits in place today. |
| Frames loaded from TOML keep magenta (255, 0, 255) opaque (no colorkey, alpha 255), so the visible-pixel hitbox fallback of a magenta-keyed sprite is its whole frame (ghosty: `Rect(0, 0, 32, 32)`) | `glitchygames/sprites/animated.py` (loader), `glitchygames/collision/bounds.py` | Found while testing the viewport-save hitbox rule; confirm whether games rely on explicit hitboxes or set a colorkey themselves. |
| A real AI request has not been run in the packaged binary (needs an API key or network) | `dist/bitmappy` | Do once by hand to fully close BUGS.md #47. |
| `scripts/raw_sprite_loader.py` cannot start: `BitmappyLegacySprite` calls `Sprite.__init__` without x and y, and `inflate` draws zero-size rects (nothing) | `scripts/raw_sprite_loader.py:~41, ~84` | Found while deleting `legacy_sprite_loader.py` (BUGS.md #46). Tests use only its `deflate`; fix or fold into Galimore import (sub-plan E). |
| `FrameAddCommand._add_frame` copies pixels through `PixelArray.flat` (pygame-ce has no `.flat`), so undoing a frame delete / redoing a frame add fails whenever the frame has pixels | `glitchygames/bitmappy/history/commands.py:~512` | Same bug fixed in `AnimationAddCommand` for BUGS.md #51 (use `SpriteFrame.set_pixel_data`). |
| Undoing an animation delete restores the sprite data but only refreshes existing film strip widgets, so the restored animation appears to get no film strip until strips are rebuilt (`on_sprite_loaded`) | `glitchygames/bitmappy/history/commands.py` (`AnimationAddCommand._add_animation`) | Found while fixing BUGS.md #51; not checked in the running app. |
| The animation-delete undo capture keeps frame pixels and durations but not per-frame hitboxes | `glitchygames/bitmappy/film_strip_coordinator.py` (`_capture_animation_deletion_for_undo`) | Found while fixing BUGS.md #51. |
| PaddleSlap's `_separate_overlapping_balls` runs after wall and paddle handling, so a ball can sit 1–3 px inside a paddle or past a wall for one frame | `glitchygames/examples/paddleslap.py` | Pre-existing, self-correcting next frame. |
| Papyrus sprites keep their unscaled native rect size | BUGS.md #59 | Latent; fixing it needs its own golden expected-difference class. |
| Brave Adventurer's ground and walls stay drawn only because the parallax layers dirty the whole screen | BUGS.md #60 | Fragile; make the terrain `dirty = 2` or document the dependency. |
| Brave Adventurer's and Papyrus's enemies (Cobra, Scarab, Scorpion) still draw in `update()` | `examples/brave_adventurer/enemies.py` | Harmless while their hitboxes do not depend on the pose (the scarab's bounds are the same at every roll angle); move drawing into `dt_tick` (the pose rule) if they ever do. |
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
- BUGS.md #19 (ruff PLW0717, 102 overly broad `try` blocks; rule temporarily disabled) is still active.

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

Design: `plans/2026-10-19-gameplay-replay.md`. Master plan:
`plans/2026-10-19-gameplay-replay-implementation.md`, with one sub-plan per part. User docs:
`docs/architecture/gameplay_replay.md`; engine summary in CLAUDE.md ("Clocks", "Gameplay Recording
and Replay").

- ~~**Part 1, replay core**~~ **Done** on `feature/gameplay-replay`
  (`plans/2026-10-19-gameplay-replay-core.md`): the doors (`glitchygames/sources.py`,
  `live_sources.py`, `RecordingSources`, `ReplaySources`), the clocks (`glitchygames/clock.py`,
  `Scene.game_time`), input snapshots, the devices and saves doors, the supervisor hook and
  control events, trace format 3, `--replay-trace`, `--replay-fps`, `--audit`, golden replay
  fixtures and the doors guard (`tests/test_engine_doors.py`). This replaces the old "Gameplay
  replay" entry; its items (wall-clock reads in gameplay, polled input, reference mapping) are all
  done.
- **Part 2, replay tooling** (pending, `plans/2026-10-19-gameplay-replay-tooling.md`): watched
  replay controls (starts paused with a "Press Spacebar to Start Game Replay" overlay that also
  shows how to turn on the debug overlay), `--headless` (replaces the private `--replay-unpaced`),
  `--rebaseline`, and the pytest plugin for recordings. While watched controls are active,
  KEYDOWN/KEYUP stay unblocked at SDL and reach only the replay controls.
- **Part 3, in-game playback** (pending, `plans/2026-10-19-gameplay-replay-playback.md`): scene
  starts, the playback scope (does not block real input at SDL; real input reaches only its "exit
  playback" check), demos (the bundled PaddleSlap demo), instant replay and ghosts.
- **Recording over a replay (`--record-trace` with `--replay-trace`) is refused** (exit 2,
  `GameEngine._start_requested_replay`): the recorder would classify the replay's batches with the
  internal-post tracker, whose pending posts the replay's pump already consumed, and would not
  copy the source recording's saves and device fields. Part 2 Task 6 (`--rebaseline`) lifts the
  refusal by wiring `ReplaySources.last_batch_origins()` and `recorded_frame_fields()` into
  `RecordingSources`.

Follow-ups (not in any plan yet):

- **State snapshots:** serialize game state for fast step-back and instant replay of long
  scenes; today both re-simulate from the scene's start (spec, out of scope).
- **Cheat device spec:** cheatable-field declarations, codes and UI; it plugs into the supervisor
  hook and records its actions as control events (spec section 2, out of scope).
- **"Take over" handover:** let the player take control part way through a replay. It must end or
  suspend the SDL input block at the handover and switch the doors from recorded to live input.
- **Divergence exit status:** a diverged `--replay-trace` run logs the divergence but still exits
  0; Part 2's `--headless` exits 1 on a divergence (spec 3.3).
- **Audit test helper suppressions:** the end-to-end audit test helper should start its children
  through `glitchygames/replay/audit.py`'s launcher, so the only `subprocess` suppression pair is
  the one in engine code (user decision, queued after the core documentation task).
- Deferred review notes: `reset_sources` would call `on_uninstalled` twice for an object that is
  both scoped and installed (`push_scoped_sources` should refuse it; Part 3);
  `start_trace_recording` wraps `active_sources()`, which returns scoped sources first, so
  recording inside a playback scope must wrap the installed doors (Part 3); no test pins the first
  FPS log waiting one interval; `selection.get_state_summary` can return `-inf` for
  `last_update_time` (not strict JSON); `ControlEvent` is unhashable.
- Bugs found during the replay core and not fixed (BUGS.md, Active): #67 (Bitmappy's
  joystick-event trigger conversion assumes pygame 1's integer axis scale), #68
  (`ControllerEventManager` keys controllers by device index but routes events by instance id),
  #72 (`MultiControllerEnhancements` stores a duration where a timestamp is expected), #73
  (PaddleSlap sets the `game` logger to INFO at import), #74 (`debug_events` is always False),
  #75 (`pygame_needs_fastevents` compares major and minor separately).

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
- Deferred from the screen-shake spec (see its known follow-ups in
  `plans/2026-10-17-screen-shake-and-synth.md`): the audio probe capture mode and the spin-window
  power idea.

## Assets and art

- Ghosty sprite: frames 1–7 have inferred outer outlines; canvas screenshots of each frame would
  make them exact (`examples/resources/sprites/ghosty.toml`).
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
