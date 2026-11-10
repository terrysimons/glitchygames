# Pin LayeredDirty's drawing mode (BUGS.md #190)

Part of the 2026-11-02 backlog run (the owner's explicit permission to plan, fix, commit, test
and push each item on its own branch).

## Investigation

pygame-ce's `LayeredDirty.draw` times itself with `pygame.time.get_ticks()`. A new group draws
its first frame full-screen (`_use_update = False`); after every draw it switches to dirty-rect
mode if that draw took 1000/80 ms or less and to full-screen mode otherwise. The two modes can
draw different pixels, so a slow machine (the browser builds' WASM draws are the likeliest)
could show different frames from a fast one.

Proven with three dummy runs of the whole suite, each fingerprinting every presented frame
(`glitchygames.testing.frame_fingerprints`, seed 190), with a probe plugin forcing the mode:

| Run | Mode | Compared with the normal run |
|---|---|---|
| normal | pygame's timing | — |
| full | every draw full-screen (a slow machine) | **184 tests present different frames** |
| dirty | dirty-rect after the first draw (the candidate fix) | **0 differences** |

The full-screen run also failed 4 tests the others pass (`tests/scenes/test_scene_rendering.py`'s
dirty-rect expectations, the dt demo): the engine already assumes dirty-rect mode
(`Scene.render` returns only the dirty rects).

While running it, `scripts/compare_driver_frames.py` reported "0 differences" for runs that had
recorded no test (filed and fixed as BUGS.md #256).

## Design

Pin dirty-rect mode on the group every scene draws. `Scene.all_sprites` becomes a property whose
setter calls `pin_dirty_rect_drawing(group)` (`group.set_timing_threshold(math.inf)` for a
`LayeredDirty`; anything else left alone), so the default group, a group a game passes in, and one
assigned later (PaddleSlap replaces its `all_sprites`) are all pinned. The first draw stays
full-screen (nothing is drawn yet), as on a fast machine. Bitmappy's `EditorContext` protocol
declares `all_sprites` as a property to match.

Rejected: pinning full-screen mode (changes 184 tests' frames and breaks the engine's dirty-rect
expectations); pinning each `LayeredDirty()` the games create (40 call sites, most of them groups
that are never drawn).

## Plan

1. `pin_dirty_rect_drawing` and the `all_sprites` property; the protocol.
2. Tests: pygame's own switch (the mechanism), a pinned group staying in dirty-rect mode after slow
   draws, every way a scene gets its group, a non-`LayeredDirty` left alone.
3. The full suite (dummy and native); BUGS.md #190 and #256; commit, push, PR.
