# Future Work Backlog

Suggested during the `feature/debug-overlay` sessions (2026-10-17 to 2026-10-18) and not done yet.
One line per item, with where it is detailed. Review, then promote items into
`plans/engine-audit.md`, a plan, or BUGS.md, or delete them.

## Bugs found and not fixed yet

| Item | Where | Notes |
|---|---|---|
| Built-in font fallback path is wrong: `Path(__file__).parent / 'fonts' / 'bitstream_vera'` resolves to `glitchygames/fonts/fonts/…`, so the fallback for packaged games raises `FileNotFoundError` | `glitchygames/fonts/font_manager.py:282` | BUGS.md #40 (active). One-line fix plus a test. |
| `InputConfirmationDialogScene.on_key_down_event` passes key-down events to `super().on_key_up_event` | `glitchygames/ui/dialogs.py:~305-317` | BUGS.md #41 (active). Pre-existing (identical on main). |
| TOML writers don't escape sprite names and descriptions (a `"""` in a description makes an unloadable file) | `glitchygames/sprites/animated.py` (both writers) | BUGS.md #42 (active). Pre-existing. |
| After loading a multi-animation sprite, `is_looping` follows the first animation, not the last one loaded | `glitchygames/sprites/animated.py` | Side effect of the per-animation loop fix (BUGS.md #38); single-animation sprites unaffected. Confirm it's the intended default. |
| Brave Adventurer and Clockwork Keep draw their poses in `update()`, after wall resolution, so after turning the hitbox can sit past a wall (up to 4 px) for one frame | `examples/brave_adventurer/player.py`, `examples/clockwork_keep/player.py` | Needs pose drawing earlier in the frame; fits engine world space (#6). |
| `CollisionManager.check_overlap` computes each sprite's rect once per pass, so a callback that moves a sprite leaves later pairs using its old rect | `glitchygames/collision/layers.py` (documented in the docstring) | Harmless in PaddleSlap; matters for generic reuse. |
| Frame-anchor reference cache doesn't notice a frame hitbox edited in place (only frame add/remove/replace) | `glitchygames/sprites/animated.py` (documented) | Nothing edits in place today. |
| Bitmappy's panned-viewport save drops a hitbox that lies entirely outside the viewport | `glitchygames/bitmappy/animated_canvas.py` | Decide: drop, clamp, or warn. |

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
- `FUTURE_FEATURES.md` item 38 (frame alignment command) duplicates D8. `FUTURE_FEATURES.md` is not
  tracked in git: decide whether to track it or fold its open items into `plans/`.

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

- Summary of the 1998–2001 Galimore code and tools: session scratchpad `galimore/SUMMARY.md` (not in
  the repo; copy it into `plans/` or docs if it should be kept).
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
