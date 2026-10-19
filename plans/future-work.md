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

## Gameplay replay (follow-up to `--record-trace`, feature/engine-world-space Task 1d)

- **`--replay-trace PATH`:** load a recording (`glitchygames/recording.py`, read with
  `TraceReader`), `reset_streams(seed=...)` from its `random_seed` and apply its recorded options
  (screen size, input mode); each frame, set `dt` from the frame's `dt` instead of reading the
  clock, and at `GameEngine._pump_events` (the single seam) return recorded batch N for pump call
  N: the frame's external events, merged with the internal events (FPS, game, menu events, code
  QUITs) the live queue holds, which the replayed code posts again and which the recording's
  internal entries verify. Sample the sprites as the recorder does, compare them with the
  recording's frames and report the first divergence (frame, sprite, field). Nothing pauses for
  wall-clock time.
- ~~Move the games' randomness onto the seeded engine~~ **Done** (feature/engine-world-space
  Task 1f): every random draw in the package comes from a named stream of the run's master seed
  (`random_stream` / `numpy_stream` in `glitchygames/randomness.py`), the golden harness passes
  `--random-seed` instead of patching, and `tests/test_randomness.py` rejects unseeded sources.
- **Wall-clock reads in gameplay:** PaddleSlap's ball spawn cooldown reads `time.time`, which a
  replay cannot reproduce (the golden harness's `deterministic_environment` still patches it with
  a fake clock). Move it onto game time (accumulated `dt`).
- **Polled input:** input read outside the event queue is not recorded (`pygame.key.get_pressed`,
  `pygame.key.get_mods`, `pygame.mouse.get_pos`, joystick and controller `get_axis`; the sites are
  listed in `glitchygames/recording.py`'s module docstring). Replay of code that polls needs a
  per-frame snapshot of the polled state, recorded next to the frame's event batches. The debug
  overlay's mouse poll only draws the overlay. Pumps after the final recorded frame (during
  terminate) are not recorded either.
- Recorded attributes come back as `RecordedReference` (a window or joystick, by id) or
  `UnrepresentableValue` (any other object); replay must map references to live objects and
  decide what an unrepresentable external value becomes. Games that post SDL-type events with raw
  `pygame.event.post` are recorded as external and would be delivered twice: move them to
  `post_event`.

## Trace format ideas (pending a user decision)

- **Trace format v3:** record each world sprite's world position and snap mode, and the camera
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
