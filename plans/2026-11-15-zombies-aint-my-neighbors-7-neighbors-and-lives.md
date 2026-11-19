# Zombies Ain't My Neighbors, Feature 7: Neighbors, Lives and Stages — Plan

**Status (2026-11-15):** BUILT, uncommitted, awaiting the owner's review. The owner chose the run
carrying on across stages with only the neighbors saved ("Go ahead" to Claude's pick) and
approved this plan ("Go ahead"). The rulings made while building are listed below.

**Master plan:** [2026-11-14-zombies-aint-my-neighbors.md](2026-11-14-zombies-aint-my-neighbors.md)
(mechanic 1: a shrinking victim pool with a pass or fail rule per stage).
**Spec:** the character BOM (signed off): section 6 (neighbors, `saved`, `lost`), section 3
(`knocked-out` with lives, `cheer`, a player out of lives), section 9's decisions 5 (game over,
rejoining) and 9's "exit at stage clear"; the props BOM, which gains the exit door first.

## Goal

The yard has neighbors to save. A kid who touches one saves them; a zombie that reaches one
first loses them. Each kid has lives. When every neighbor is saved or lost and at least one was
saved, an exit door opens; a kid through it clears the stage, and the next stage brings back only
the neighbors saved. Lose every life, or end a stage with nobody saved, and the TV switches off:
game over.

## Scope

In: two neighbor types, saving and losing, lives, the stage's end, the next stage, game over, a
heads-up display (HUD), the props and art these need. Not in: score and extra lives, rejoining
mid-stage with a spare life, the TV Watcher and the Static Wraith, the radar, the villain (his
laugh joins game over when he is drawn), harder stages, sound, saves.

## Decisions (Claude's calls; the owner may overturn them)

| Decision | Value | Why |
|---|---|---|
| Neighbors | The BOM's first-playable two: the **Pizza Delivery Teen** (idle: checking the order slip; panic: the pizza box held up as a shield) and the **Lawn-Chair Reader** (idle: turning a newspaper page; panic: the newspaper over the head). 32x48, the BOM's hitbox; they never move | BOM section 6 and its first-playable stage |
| Stage 1's neighbors | 8, alternating the two types, at 8 of 12 fixed places spread round the yard (away from the TVs and the starting huddle), the 8 drawn from the named stream `zombies_aint_my_neighbors.neighbor-places` | Variety that replays repeat; at most 10 a stage (the genre) |
| Panic | A neighbor with a zombie within 96 px plays `panic`; otherwise `idle` | Tells players who needs help |
| Saving | A kid's hitbox meeting a neighbor's (the 4 px margin, as touching zombies) saves them: `saved` plays (pixels stream up, 0.3 s) and they leave | BOM section 6 |
| Losing | A zombie's hitbox meeting a neighbor's first loses them: the zombie grabs, `lost` plays (0.4 s) and they leave. Zombies chase the nearest kid **or** neighbor | BOM section 6; zombies must threaten neighbors |
| Lives | 3 per player. A knockout costs one. With lives left the kid gets back up as now; with none, it lies on its last `knocked-out` frame, fades out over 1 s and is out for the stage (zombies ignore it, the camera and the group span leave it out) | BOM section 3's transition rule |
| A player out of lives | Out until the stage ends; the next stage brings them back with 1 life. Their HUD slot reads OUT | The BOM's rejoin needs spare lives, which need score: a later feature |
| The stage's end | When no neighbor is left standing and at least one was saved, an **exit door** opens in the top hedge's middle; zombies keep coming. The first kid to touch it clears the stage: the kids `cheer` for 1.5 s, then the feature card shows STAGE n with who is playing, then the next stage | BOM: the exit and `cheer`; an arcade-simple exit |
| The next stage | The same yard: fresh, intact TVs, no zombies, the kids in the starting huddle, and only the neighbors saved, placed as stage 1's are (drawn again from the stream) | The shrinking pool, cheaply (the owner's choice) |
| Game over | When every joined player is out of lives, or a stage ends with nobody saved: the TV switches off (the picture collapses to a bright line, then a dot, then dark: a screen-space sprite drawn in code, 0.6 s), GAME OVER shows, and after 4 s, or a start press, the title returns with everyone still joined | BOM decision 5, less the villain's laugh until he is drawn |
| The run's state | One frozen pydantic model, `RunState`: the stage, the neighbors left (types), each slot's lives. Passed between scenes in its JSON form, as the roster is, so a replay rebuilds any scene | Replays (CLAUDE.md) |
| HUD | Screen-space text sprites along the top: each joined slot's `P1 ♥♥♥` (or `OUT`) in its colour, and `NEIGHBORS saved / total` and `STAGE n` in the middle. Redrawn only when a value changes | Every object is a sprite (CLAUDE.md) |
| Pools | Neighbors and the exit come from the scene's pools and are built before play, as zombies and zaps are (feature plan 6) | No sprite loads mid-game |
| The golden | The neighborhood golden is re-recorded on purpose: neighbors stand in the yard and the scripted kid saves one. A second golden, `golden-stage-clear`, is considered in Task 9 if a script can clear a stage within about 100 KB | The game changed |

## Props and art (added to the BOMs' entries before any art)

| Sprite | Size | Animations | Notes |
|---|---|---|---|
| Pizza Delivery Teen | 32x48 | `idle` 2 at 0.5 s, `panic` 2 at 0.12 s | BOM section 6; a neighbor rig beside the zombie's |
| Lawn-Chair Reader | 32x48 | `idle` 2 at 0.5 s, `panic` 2 at 0.12 s | Sitting in a striped lawn chair |
| `saved` | 32x48 | 5 at 0.06 s, then removed | BOM shared effect |
| `lost` | 32x48 | 5 at 0.08 s, then removed | BOM shared effect |
| The exit door | 48x48 | `closed` 1, `opening` 3 at 0.08 s, `open` 2 at 0.2 s (looping glow) | Props BOM; a garden gate in the hedge, a VR-blue glow once open |

New frames: 4 + 4 + 5 + 5 + 6 = **24**.

## Tasks

1. **The BOM entries and their audit**: the exit door in the props BOM; the two neighbors and the
   effects confirmed against section 6.
2. **Art: the neighbors and the effects** (`art/neighbor_rig.py`; `sprites/pizza_teen.toml`,
   `lawn_chair_reader.toml`, `saved.toml`, `lost.toml`): the BOM conformance tests, the engine's
   checks, each file equal to its rig's output.
3. **Art: the exit door** (`art/door_rig.py`, `sprites/exit_door.toml`): the same tests.
4. **`RunState`** (`run_state.py`): the stage, the neighbors left, lives; its JSON round trip; the
   next stage's state from a cleared one (survivors kept, players out back with 1 life); game over
   when nobody was saved.
5. **`Neighbor`** (`neighbor.py`): idle and panic by zombie distance, being saved, being lost, then
   gone; the places drawn from the named stream.
6. **Lives** (`kid.py`): a knockout costs a life; with none left the kid stays down, fades and is
   out; zombies, the camera and the group span leave an out kid alone.
7. **The stage's end and the exit door** (`neighborhood.py`, `exit_door.py`): the door opens only
   when no neighbor stands and one was saved; a kid through it clears the stage; the cheer; the
   card shows STAGE n and leads to the next stage with the survivors.
8. **Game over** (`game_over.py`): when every player is out, or a stage ends with nobody saved;
   the switch-off, GAME OVER, back to the title after 4 s or start.
9. **The HUD, the neighborhood together, the goldens, and the docs**: lives, neighbors and stage
   shown and updated; zombies chase neighbors; the golden re-recorded; the docs page and the
   master plan updated.

Each task: tests first, then ruff, the type checkers and the game's tests. The engine's
member-scanning tests run on push.

## Review Focus

- Two things on one frame: a kid and a zombie reaching a neighbor together (the kid wins: kids
  are checked first), the last neighbor saved as the last life is lost (game over wins: a stage
  can't clear with nobody to walk out).
- A pad unplugged mid-stage: its kid and lives leave; with nobody left, the title.
- Pausing during the cheer, the door or the switch-off.
- A replay started on stage 2 or the game over: rebuilt from `RunState`'s JSON.
- Every neighbor lost: the stage ends with nobody saved, so game over, never an exit.

## Rulings while building (Claude's, 2026-11-15; the owner may overturn them)

| Ruling | Why | If wrong |
|---|---|---|
| Lives show as `P1` and a multiplication sign (`P1 x3`), not hearts | The bundled font covers Latin-1; a heart could draw as a missing-glyph box | Hearts as a small sprite instead |
| Saving a neighbor is `rescue`, not `save` (the scene's `rescued`, `next_stage(rescued=...)`, the test names: the owner asked for the names to follow) | `save` overrode the engine's `AnimatedSprite.save`, which writes a sprite file; both type checkers caught it | None found |
| A kid out of lives leaves the camera and the group's span only once it has faded (state `OUT`), not while it lies fading | The fading kid still shows for its second; the camera stays on it | A camera a little slower to follow the others |
| The door and the game over wait for the last neighbor's effect to end (all gone), not just for nobody standing | The last rescue or loss plays out before the stage ends | 0.4 s later at most |
| A kid and a zombie touching a neighbor on one frame: a rescue (kids are checked first) | The plan's Review Focus | None |
| The stage clear is in the neighborhood golden, not a second golden (the owner asked for the replay, 2026-11-15) | The engine's golden tests take one golden per scene class (a game key maps to its scene's logical name), and both would start on `NeighborhoodScene`; one golden covering both keeps every table as it was | A larger fixture: 1970 script frames (2122 with its tail), 179 KB, over the repository's usual 100 KB and under Drawing Fire's 185 KB |
| The route is planned by `scripts/plan_neighborhood_route.py`, kept in the repository (the owner, 2026-11-15) | A fixed list of keys would quietly stop clearing the stage after a gameplay change; the planner re-makes it, and `test_zombies_aint_my_neighbors_golden_route.py` fails when the golden no longer reaches stage 2 or the committed route is no longer the plan (both proven to fail with a defect planted: zombies 50% faster; the title's golden) | Re-planning and re-recording after gameplay changes |
| Back on a STAGE n card keeps the run (the owner: "Ok" to Claude's recommendation): the title holds it and its next start brings back the same card; before stage 1 the title holds none | A new run there would dodge the shrinking pool | None |
| The stage and neighbors line sits at the bottom of the screen, not the top the plan named (found by the final review) | The four players' lives fill the top row, one per column; a centred line there would run over P2's and P3's | Moving it costs nothing |
| Neighbors and the exit door are built with the scene, not taken from pools as the plan said (found by the final review) | They are made once per stage, before play, and never respawn, so a pool would only hold them | None: nothing loads mid-game (`test_no_sprite_file_loads_during_play`) |

## Found while building

- **The Lawn-Chair Reader's originality check had been skipped** (a side agent's note, the
  owner's word to check): done from the original's victim list and descriptions, and she is
  cleared. The sprite art itself could not be fetched. Recorded in the character BOM, section 9.
- **A flaky test, and the bug behind it:** `test_the_group_always_fits_on_the_screen[4]`
  failed in some runs. The harness gives each test fresh, unseeded streams, so whether a
  zombie knocked a kid out of its last life varied from run to run. When one did, the scene
  rightly left that kid out of the group's span, but the test still measured it. The fix:
  the span leaves out only a kid fully gone (`OUT`), and the test measures the same group.
  Probed across 12 stream seeds for 2, 3 and 4 players: all pass.
- **The final review (a fresh reviewer, 2026-11-15)** found no Critical or Important bugs. It
  confirmed the lives bookkeeping, the order of operations, replay determinism and the stage
  transitions with probes, and replayed the golden. Two of its Minor findings were raised to
  Important by what a player sees, and fixed with tests that failed first:
  - A rescue's or loss's effect was drawn on layer 0, behind the kid or zombie standing on it.
    It now draws a frame's height in front of the neighbor's feet
    (`test_a_rescue_or_loss_plays_in_front_of_whoever_caused_it`).
  - A kid waiting at the gate cleared the stage while it was still drawn shut, so the gate was
    never seen to open. Now it must have swung all the way open (`ExitDoor.is_passable`;
    `test_a_kid_waiting_at_the_gate_leaves_only_once_it_has_swung_open`).
  - **Deferred (Minor):** a kid knocked out when the stage clears doesn't cheer, and gets back up
    during the cheer. Harmless, because the next stage builds new kids. Fixed 2026-11-19: it
    cheers as it gets up (the master plan's "What is left of level 1").
  - **For the owner:** Back on a STAGE n card returns to the title, and the next start begins
    a new run. Stage 1, 8 neighbors and full lives dodge the shrinking pool. The plan didn't say;
    Claude recommends Back keep the run (the title then leads to the same STAGE n card).
  - The reviewer would reconsider skipping a stage-clear golden: the hand-over from the stage
    clear through the card to stage 2 is covered by unit tests, not by an end-to-end replay.
- **The pools broke an engine guard, from Feature 6's commit on (3b6fb8ed).**
  `tests/replay/test_removed_sprites_are_freed.py` fails when anything holds a sprite removed
  from every group, and the pools held removed zombies and zaps. It went unseen because the
  game-only test runs (the owner's rule for this game) skip the engine's tests; the push gate
  runs them. Fixed: a zombie or zap that has gone is hidden and kept in the scene's group
  (`put_away`), and the pools build theirs there, hidden. The guard now passes for the golden.
  The scene's tracking test checks that every zombie or zap shown is one the scene tracks.
- **A 0.32 s hitch when stage 2 is built** (the golden records that frame at 3 fps): the card
  builds the next neighborhood (8 neighbors with 16 effects, the kids, the pools) on one frame.
  The frame cap keeps the game from jumping ahead, but the pause shows. Building the stage
  while the card shows would hide it. Not built; it is in the master plan's Game TODOs.
- The busy tests' yard now has its one neighbor rescued first: zombies chase the nearest
  neighbor, so without that they never walked into the kids' fire.

## Not in this feature

Score and extra lives, rejoining mid-stage, the TV Watcher, the Static Wraith, the radar, the
villain, harder stages, sound, saves.
