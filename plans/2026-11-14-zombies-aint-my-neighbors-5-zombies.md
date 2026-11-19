# Zombies Ain't My Neighbors, Feature 5: Zombies Come Out of the TVs — Plan

**Status (2026-11-14):** BUILT, uncommitted, awaiting the owner's review. The owner said
"proceed" to Claude's suggestion: the Lawn Zombie with its TV spawner. All seven tasks are done;
the rulings made while building are listed under "Rulings while building" below.

**Master plan:** [2026-11-14-zombies-aint-my-neighbors.md](2026-11-14-zombies-aint-my-neighbors.md).
**Spec:** the character BOM, section 5.1 (the Lawn Zombie) and its rules (section 1); master plan
decision 19 (TV spawners).

## Goal

TV sets in the yard flicker with static and push Lawn Zombies out through their screens; the
zombies shamble toward the nearest kid, and a zombie that reaches a kid knocks it out. The kid
plays its knockout, loads back in, and blinks for a moment, untouchable. The smallest version
that plays: dodging.

## Scope (Claude's call; the owner may overturn it)

Destroying zombies and TVs needs an attack, and the kids have no weapons yet; both come with the
first weapon (Feature 6). Lives, game over and neighbors come later. Until then a knocked-out kid
always comes back.

## Decisions (Claude's calls; the owner may overturn them)

| Decision | Value | Why |
|---|---|---|
| The zombie's look | A shambling neighbor in a faded blue bathrobe and pink fuzzy slippers, grey-blue skin (no green near P1's), holding a soggy newspaper out in front with both hands (centred: arms out, as zombies walk, and mirroring keeps it) | BOM 5.1; it said both "arms out" and "clutched to the chest"; holding it out in front satisfies both |
| The zombie's frames | BOM 5.1 less `rise` (decision 6): `walk_<f>` 4 frames at 0.18 s, `grab_<f>` 2 at 0.1 s, `crumble` 5 at 0.1 s; idle is walk frame 0 held; facings down, up, left (right mirrored); no diagonals (decision 11 gave them to the kids); 32x48, hitbox as a kid's | The signed-off BOM |
| The art | A zombie rig beside the kids' (`art/zombie_rig.py`), using the same canvas, shading and outline | One look across the cast |
| `crumble` | Drawn now (the BOM lists it) though nothing kills a zombie until Feature 6 | The file holds the whole BOM entry, as the kids' do |
| The TV | A prop: a boxy wood-cased TV on short legs, 48x48, antenna on top. Its frames: `static` (3, 0.08 s, loop) and `spawn` (4, 0.08 s: the screen bulges and pops, then `static`). Its damage stages wait for Feature 6 | Master plan decision 19; the BOM's tv-spawn effect, folded into the TV so it plays where the TV is |
| The props BOM | Started here, with the TV's entry; the rest of the props BOM later | Decision 18's discipline for characters, applied to the prop this feature needs |
| Spawning | Four TVs at fixed places, one in each quarter of the yard. Each spawns every 6 to 9 s (drawn from the named random stream `zombies_aint_my_neighbors.tv-spawns`, so replays repeat it), at most 3 zombies alive per TV and 10 in all | Variety without breaking replays (CLAUDE.md, randomness) |
| Zombie movement | Toward the nearest kid who is not knocked out, at 40 px/s (a third of a kid's walk), facing the nearest of four ways; standing still when every kid is knocked out | The BOM's "slower than a kid" |
| Touching | When a zombie's hitbox meets a kid's (a 4 px forgiveness margin, the engine's `get_collision_rect_with_margin`), the zombie plays `grab` and the kid is knocked out | The core threat |
| Knocked out | The kid plays `knocked-out` (5 frames), lies still for 1.0 s more, plays `respawn`, then blinks for 2.0 s, untouchable, walking again. Its player cannot move it until `respawn` ends | BOM section 3; a fair recovery |
| Blinking | The kid hides and shows every 0.1 s while untouchable (`hidden`, the engine's world-sprite rule) | No hurt frames (BOM section 1) |
| Collisions | TVs block neither kids nor zombies yet; zombies may overlap each other | Walls and solid props come with the props BOM's tiles |
| Draw order | Zombies and TVs sort by their feet, with the kids | One depth rule |
| The golden | The neighborhood golden is re-recorded on purpose: zombies now appear and move in it | The game changed; a replay compares sprite rects |

## Tasks

1. **The props BOM** (a new `plans/2026-11-14-zombies-aint-my-neighbors-props-bom.md`), with
   the TV's entry: size, palette,
   frames, timings, loop rules, what follows, anchor, collision.
2. **The zombie rig and file** (`art/zombie_rig.py`, `sprites/lawn_zombie.toml`): tests for BOM
   conformance (names, frames, timings, loops, transitions, hitbox, anchor, 32x48, 15 colours),
   the engine's sprite checks, the committed file equal to the rig's output.
3. **The TV rig and file** (`art/tv_rig.py`, `sprites/tv.toml`): the same tests against the props
   BOM.
4. **`Zombie`** (`zombie.py`): an animated world sprite (mirroring through the scene's cache),
   chasing, facing, grabbing. Tests: chases the nearest standing kid, ignores knocked-out kids,
   stands when none are left, grabs on touch.
5. **`Tv`** (`tv.py`) and spawning: the static loop, the spawn animation, the timing from the named
   stream, the caps. Tests: spawn timing within 6 to 9 s, the caps, a zombie appears in front of
   its TV after the pop, replays repeat the timings (the same seed gives the same spawns).
6. **Knocked-out kids** (`kid.py`): the knockout, the lie-still, the respawn, the blinking and
   untouchability, no movement meanwhile. Tests for each.
7. **The neighborhood brings it together**, and the golden is re-recorded and verified.

## Rulings while building (Claude's, 2026-11-14; the owner may overturn them)

| Ruling | Why | If wrong |
|---|---|---|
| The random stream is `zombies_aint_my_neighbors.tv-spawns`, not `tv-spawns` | The engine's convention for stream names is `<game>.<purpose>` (`glitchygames.randomness.random_stream`) | A rename and a re-recorded golden |
| A TV counts a zombie when its spawn starts, not when the zombie pops out | Two TVs starting together can't pass the cap of 10 | None found |
| A TV whose wait ends while a cap is reached skips that spawn and waits again (a new 6 to 9 s draw) | No zombie bursts out the moment a cap frees; the stream's draws stay one per wait | Zombies return a little later after Feature 6 starts killing them |
| Touching shrinks both hitboxes by the 4 px margin (the engine's function shrinks one sprite's rect) | The plan named the engine's function; applying it to each sprite is its use | A touch that feels a few pixels too forgiving |
| The neighborhood golden is recorded at 660 script frames (11 s; 812 with its tail), not 330 | At 330 (5.5 s) no TV has spawned (the first wait is at least 6 s), so the golden would not cover spawning; at 660 every TV's first zombie is in it (41.6 KB) | A larger fixture |
| Knockout timers end within `TIME_TOLERANCE` (1e-9 s) of their time | Thirty frame times of 1/60 s add up to 0.49999..., so each 0.5 s step ran one frame long; regression tests pin each step to its exact frames | None |
| Kid and zombie share one frame-showing path (`MirrorCache.show_frame`) | Mirroring and the hitbox's flip must agree; parallel copies drift | None |

## Found while building

- The process-state guard (`tests/test_process_state_guard.py`) failed since bfa4544c on the
  module-level `KID_HAND_POINTS` dict, and would have on the zombie's and TV's palettes; all three
  are now read-only `MappingProxyType` views. The game-only test runs (the owner's rule for this
  game) skip the engine tests that scan every member, which is how it went unseen: run those too
  before committing (the list is in the execution ledger).
- `feature_card.py` ends its card when `game_time >= CARD_SECONDS`, the same float-sum boundary:
  the card probably shows one frame longer than 2.0 s. Not fixed: it would change the title golden
  for a frame nobody sees.

## Not in this feature

Weapons, killing zombies, damaging TVs, lives, game over, neighbors, solid props and walls, the
other monsters.
