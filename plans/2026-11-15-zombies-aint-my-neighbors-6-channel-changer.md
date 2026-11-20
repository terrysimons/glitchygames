# Zombies Ain't My Neighbors, Feature 6: The Channel Changer — Plan

**Status (2026-11-15):** BUILT, uncommitted, awaiting the owner's review. The owner chose the
weapon ("Yes that sounds good", 2026-11-15) and approved this plan ("Sounds good"). All nine tasks
are done; the rulings made while building are under "Rulings while building".

**Master plan:** [2026-11-14-zombies-aint-my-neighbors.md](2026-11-14-zombies-aint-my-neighbors.md).
**Spec:** the character BOM, section 3 (the kids' `shoot` and `walk-shoot` poses, hand points,
"the weapon is drawn only while attacking") and 5.1 (the zombie's `crumble`); master plan
decision 19 (TV damage stages); the props BOM, which gains this feature's props first
(decision 18's discipline).

## Goal

The kids fight back. A kid points a TV remote and fires a zap; a zombie it hits "changes
channel" and crumbles; a TV it hits cracks, then smashes and sparks, then dies smoking, spawning
more slowly at each stage and not at all once destroyed. Dodging becomes a game.

## Scope

In: one weapon, firing on the keyboard and on pads, zaps, zombies dying, TV damage stages, the
props they need, the golden. Not in: ammo and weapon switching (with the second weapon), score,
lives, game over, neighbors (Feature 7), sound (no sound exists in the game yet: a sound feature
covers every effect at once), weapon diagonals (deferred in the BOM, decision 11).

## Decisions (Claude's calls; the owner may overturn them)

| Decision | Value | Why |
|---|---|---|
| The weapon | The **Channel Changer**: a chunky black TV remote with a red power button and a little lit LED at its tip | The owner's choice; the monsters came out of a TV |
| Ammo | Unlimited | The basic weapon; ammo arrives with the second weapon (owner, 2026-11-15) |
| Fire controls | Keyboard: **J** (for a WASD hand) and **Right Shift** (for an arrows hand), by scancode. Pads: **A** (the south face button) on the controller layer; button 0 on the joystick layer | Never Space, Esc, Enter, P, Q, backtick, F3 or F4 (taken: `roster_scene.py`); one key under each hand that can steer |
| Firing rhythm | A press fires at once; holding fires again every 0.25 s (4 a second) | Hold-to-fire is kind to four players on one screen; a cap keeps the screen readable |
| Pose | Standing: `shoot_<f>` (2 frames, 0.08 s). Moving: `walk-shoot_<f>` while the button is held or a shot is under 0.25 s old. Both kids' poses already exist | BOM section 3 |
| Aim | The kid's eight-way facing. The pose uses the nearest straight facing (BOM decision 11); at exactly 45° the side pose wins (down-left shoots with `shoot_left`) | The remote reads best side-on; the shot still flies diagonally |
| The remote | A prop sprite drawn at the frame's hand point only while shooting, mirrored with the frame; behind the kid when facing up | BOM rules (hand points, mirroring) |
| The zap | A small ring of TV static, 12x12, 3 frames looping at 0.06 s; flies at 320 px/s from the remote's tip for at most 0.6 s (192 px), then fizzles out in 2 frames. Hits the first zombie or TV it touches and is gone. Passes through kids, other zaps and the hedges' insides; stops at the yard's edge | A short range keeps it a dodging game; no friendly fire in co-op |
| Zombies | One zap kills a Lawn Zombie. It plays `crumble` (5 frames, 0.1 s), touches no one while crumbling, then its last frame (the slippers) fades out over 0.5 s and it is removed | The basic monster dies to the basic weapon; BOM 5.1's "slippers fade in code" |
| TVs | Hittable (the props BOM's hitbox). **3 hits per stage**: intact, cracked, smashed and sparking, destroyed and smoking. Each stage doubles the wait between spawns (so the rate halves: 6–9 s, 12–18 s, 24–36 s); destroyed spawns nothing. A spawn already started finishes | Master plan decision 19; 9 zaps (just over 2 s of holding fire) take one down |
| A hit's feedback | The struck TV or zombie flashes white for one frame (0.05 s). A destroyed TV shakes the world briefly and rumbles the destroying kid's pad | The engine's shake and rumble (master plan concept) |
| Caps and the stream | The caps (3 per TV, 10 in all) count living zombies, so killing frees room; spawn waits still draw from `zombies_aint_my_neighbors.tv-spawns` (one draw per wait; the stage multiplies it) | Replays repeat it |
| Draw order | Zaps and the remote sort with everything else by their feet | One depth rule |
| The golden | Re-recorded on purpose: the scripted kid now fires at the nearest TV and some zombies. The controls tail gains the fire keys and buttons (`tests/replay/golden_replay_controls.py`, a shared file) | The game changed |

## Props (added to the props BOM before any art)

| Prop | Size | Animations | Hitbox / collision |
|---|---|---|---|
| The Channel Changer | 12x8 side-on; 6x10 front and back | `held_<f>` for down, up, left (1 frame each; right mirrored) | None (it is in a hand) |
| The zap | 12x12 | `fly` 3 frames, 0.06 s, loop; `fizzle` 2 frames, 0.06 s, then removed | Hit, `offset 2,2, 8x8`; not solid |
| The TV's damage stages | 48x48 (the TV's) | `cracked-static`, `cracked-spawn`, `smashed-static`, `smashed-spawn` (3 and 4 frames, as the intact ones); `destroyed` 3 frames, 0.1 s, loop (smoke curling up, a last spark) | As the intact TV; hittable until destroyed |

New frames: 3 + 5 + 17 = **25**. The audit (character BOM section 10) runs on these entries
before their art and is recorded in the props BOM.

## Tasks

1. **The props BOM entries and their audit** (the table above, in full).
2. **Art: the remote and the zap** (`art/weapon_rig.py`, `sprites/channel_changer.toml`,
   `sprites/zap.toml`): conformance to the props BOM, the engine's sprite checks, each committed
   file equal to its rig's output.
3. **Art: the TV's damage stages** (`art/tv_rig.py`, `sprites/tv.toml`): the same tests; the
   intact frames unchanged.
4. **Fire controls** (`controls.py`, the scene's action map): a press and a hold for each device
   kind and each layer, reported per player; the reserved keys stay unbound.
5. **The kid shoots** (`kid.py`): the firing rhythm, the pose for standing, walking and diagonal
   facings, the remote at the hand point (mirrored, behind when facing up), no firing while
   knocked out.
6. **`Zap`** (`zap.py`): its flight, range, fizzle, the yard's edge, hitting the first zombie or
   TV, passing through kids.
7. **Zombies die** (`zombie.py`): crumble, untouchable while crumbling, the slippers' fade,
   removal, the caps freed.
8. **TVs take damage** (`tv.py`): hits per stage, the stage animations, the waits doubling, no
   spawns when destroyed, a started spawn finishing, the flash, shake and rumble.
9. **The neighborhood brings it together**, the golden re-recorded and verified, and the master
   plan's feature list updated.

Each task: tests first, then ruff, the type checkers and the game's tests. The engine's
member-scanning tests (process-state guard and the like) run on push.

## Rulings while building (Claude's, 2026-11-15; the owner may overturn them)

| Ruling | Why | If wrong |
|---|---|---|
| The remote is one 12x12 canvas for every facing (the plan said 12x8 side-on and 6x10 end-on); the drawing inside keeps those proportions | One file, and the hand point is always the canvas's centre | A resized canvas; no game change |
| The remote's tips are its LED cells, (6, 10), (6, 1) and (1, 6), not the canvas's edges | The outline needs the edge cell | None |
| A hit's flash lasts 0.05 s (white on the 2 frames before it runs out at 60 fps), where the plan said "one frame (0.05 s)" | At 60 fps those disagree; every other timing in the game is in seconds | A flash a frame longer than meant |
| The wait running when a TV breaks doubles too, not only the waits drawn after | "The rate halves at each stage" takes effect at once; still one draw per wait, so replays repeat it | A TV that spawns a little later than a stricter reading |
| `tests/replay/golden_replay_controls.py` is unchanged | The neighborhood's polled keys (WASD, the arrows) are covered by the golden's main script, not its controls tail; fire is polled too, so `J` and right `Shift` are in the main script | Two entries in a shared file |
| The golden runs 720 script frames (872 with its tail; 46 KB), not 660 | So it holds a zapped zombie (frame 509; 524 since feature plan 7 added neighbors), a destroyed TV (frame 658: the world shakes) and zaps passing through it | A larger fixture |

## Found while building

- **Fixed:** the scene re-layered a zombie whose fade had just ended, and a zap that had just
  fizzled, after each had left its groups: pygame raised `ValueError`. Regression tests
  `test_a_crumbled_zombie_leaves_the_yard` and `test_a_zap_that_fizzles_out_leaves_the_yard`
  failed before the fix. The class, as a property: everything the scene tracks is in its sprites,
  and nothing it drops stays there. `test_everything_the_scene_tracks_is_in_its_sprites_through_a_busy_game`
  checks it over 20 s of four kids firing, and fails with the defect planted. Swept: kids leave
  with their remotes through `_device_left`, and TVs never leave, so neither re-layers a sprite
  that has gone.
- **The final review (a fresh reviewer, 2026-11-15) found two bugs, both fixed with regression
  tests that failed first:**
  - A standing shot on a slow frame (0.16 s or more, a hitch) skipped its pose. The remote was
    never placed, so the zap left from wherever the remote last was, or the yard's corner before
    any shot. The frame a shot fires now always shows it
    (`test_a_standing_shot_on_a_slow_frame_still_poses_and_places_the_remote`).
  - A zap couldn't strike on the step that ended its range or stopped it at the yard's edge, so
    a target reachable only in that step was never hit. A zap now strikes on the frame its
    flight ends (`test_a_zap_strikes_what_it_meets_on_its_last_step`, `..._at_the_yards_edge`).
- **Sprite files loaded mid-game (the owner asked about a first-shot hitch, 2026-11-15).** Every
  zombie spawn read and parsed its sprite file (27 to 41 ms: two or three dropped frames at
  60 fps) and every zap its own (about 2 ms). The engine keeps no cache of loaded files. 327 loads
  happened in 20 busy seconds. Present since Feature 5 for zombies. No other game loads sprite
  files during play: Drawing Fire loads its soldier once and shares the frames, Brave Adventurer
  builds every level sprite with its scene, and the rest draw in code. **Fixed:** the
  neighborhood builds pools of 16 zombies and 12 zaps (4 kids x 3 in the air) before play
  (`pool.py`; master plan decision 11). `test_no_sprite_file_loads_during_play` failed before
  (327 loads) and passes now; the golden was re-recorded for the pooled sprites (872 frames,
  45 KB). The engine-side cache is Engine wishlist #12.
- **The review's four Minor findings, fixed at the owner's word ("Fix the 4 minors", 2026-11-15),
  each with a test that failed first:**
  - Zaps could step over targets when a frame was longer than about 0.09 s. The neighborhood now
    caps a frame at 0.05 s (`MAX_FRAME_SECONDS`, as Clockwork Keep does), so a zap's step stays
    under 16 px, shorter than its hitbox and a zombie's together
    (`test_the_neighborhoods_frame_cap_keeps_a_zap_from_stepping_over_a_zombie`, and a sweep of
    40 starts at the capped frame).
  - The remote and the zap's start sat 1 px off a true mirror when facing right. The grip now
    flips with the frame, column 6 to column 5
    (`test_facing_right_the_remote_mirrors_facing_left_exactly`).
  - A TV destroyed mid-spawn showed its smoke while its zombie popped out. It now plays the spawn
    out, as a smashed TV's, then smokes
    (`test_a_tv_destroyed_mid_spawn_plays_the_spawn_out_then_smokes`).
  - Held fire drifted at frame rates that don't divide 0.25 s. Held fire now carries the part of
    a frame past each 0.25 s, so 50 and 40 fps keep four a second; a fresh press starts the rhythm
    from zero, so a release banks nothing (`test_held_fire_keeps_four_a_second_at_any_frame_rate`,
    `test_a_long_release_does_not_bank_shots`).
  The golden was re-recorded for the carried rhythm (its second zap one frame sooner; the TV now
  destroyed at frame 658).
- **Built after (the owner, 2026-11-15: "continue with the next item"):** on-screen touch
  controls for the neighborhood: a D-pad (the arrows) and **Fire** (`J`) beside Start and Pause
  (`TOUCH_LAYOUTS` in `scripts/build_browser_bundle.py`, `KeyJ` added to the touch keys). The
  D-pad walks four ways, since a button presses one key. Tests: the game's
  `test_zombies_aint_my_neighbors_touch_controls.py`.
- **Was not built:** the browser page has no on-screen walk or fire buttons (its touch layout has
  only Start and Pause), so the neighborhood needs a keyboard or a pad there. It predates this
  feature. Touch walking and firing belong together, in a feature of their own.

## Not in this feature

Ammo, weapon switching and other weapons, score, lives, game over, neighbors, sound, solid props
and walls, the other monsters, weapon diagonals.
