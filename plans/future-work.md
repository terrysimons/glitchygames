# Future Work Backlog

Suggested during the `feature/debug-overlay` sessions (2026-10-17 to 2026-10-18) and not done yet.
One line per item, with where it is detailed. Review, then promote items into
`plans/engine-audit.md`, a plan, or BUGS.md, or delete them.

## Bugs found and not fixed yet

| Item | Where | Notes |
|---|---|---|
| After loading a multi-animation sprite, `is_looping` follows the first animation, not the last one loaded | `glitchygames/sprites/animated.py` | Side effect of the per-animation loop fix (BUGS.md #38); single-animation sprites unaffected. Confirm it's the intended default. |
| Brave Adventurer and Clockwork Keep draw their poses in `update()`, after wall resolution, so after turning the hitbox can sit past a wall (up to 4 px) for one frame | `examples/brave_adventurer/player.py`, `examples/clockwork_keep/player.py` | Needs pose drawing earlier in the frame; fits engine world space (#6). |
| `CollisionManager.check_overlap` computes each sprite's rect once per pass, so a callback that moves a sprite leaves later pairs using its old rect | `glitchygames/collision/layers.py` (documented in the docstring) | Harmless in PaddleSlap; matters for generic reuse. |
| Frame-anchor reference cache doesn't notice a frame hitbox edited in place (only frame add/remove/replace) | `glitchygames/sprites/animated.py` (documented) | Nothing edits in place today. |
| Bitmappy's panned-viewport save drops a hitbox that lies entirely outside the viewport | `glitchygames/bitmappy/animated_canvas.py` | Decide: drop, clamp, or warn. |
| Undoing an animation delete in Bitmappy restores its frames but not the `[[transition]]` entries dropped with it | `glitchygames/bitmappy/` (delete-animation command and its undo) | Found while fixing BUGS.md #44; the transitions should be captured by the delete command. |
| Renaming an animation in Bitmappy drops its timing and loop flag | `glitchygames/bitmappy/film_strip_coordinator.py:~1352` | BUGS.md #45 (active). |
| On SIGINT/SIGTERM Bitmappy's signal handler exits without the AI worker's queue cleanup, so the worker is killed as a daemon instead of receiving its shutdown message | Bitmappy signal handling / `ai_manager.py` | Found while verifying BUGS.md #47 in the binary; no leak or traceback observed, but shutdown isn't graceful for the worker. |
| A real AI request has not been run in the packaged binary (needs an API key or network) | `dist/bitmappy` | Do once by hand to fully close BUGS.md #47. |
| `scripts/legacy_sprite_loader.py` cannot start (`Sprite.__init__()` missing x and y) | `scripts/legacy_sprite_loader.py:~50` | BUGS.md #46 (active); fix or delete. |
| Bitmappy's editor canvas now honours `loop = false` (a one-shot animation plays once on SPACE and stays stopped) | `glitchygames/bitmappy/animated_canvas.py:~589` (`show_frame`) | Side effect of BUGS.md #38. Decide: keep, or force looping in the editor canvas as `film_strip.py:218` does for previews. |
| PaddleSlap's `_separate_overlapping_balls` runs after wall and paddle handling, so a ball can sit 1–3 px inside a paddle or past a wall for one frame | `glitchygames/examples/paddleslap.py` | Pre-existing, self-correcting next frame. |

## Engine roadmap (already in `plans/engine-audit.md`)

- **Next branch: engine world space (#6)**, folding in the frame loop `_finish_frame()` consolidation (#15).
- **Then solid collision (#1) with the rest of balls on `CollisionManager` (#7).** Brave Adventurer
  and Papyrus now duplicate `_player_support_span` / `_entered_wall_from_left`; the solid-collision
  design should absorb them.
- **Level tools / Glitchy Studio (#11):** `plans/2026-10-18-level-tools.md` and sub-plans A–E
  (tilemap format with object layers, Mapsmith, Tilesmith, Bitmappy updates, Galimore import). Each
  needs a brainstormed spec before implementation.
- BUGS.md #19 (ruff PLW0717, 102 overly broad `try` blocks; rule temporarily disabled) is still active.

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
- Debug-overlay graph: optional tolerance before a bar turns red (at 60.01 FPS many frames land a
  hair over target). Not decided.
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
