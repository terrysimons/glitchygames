# Zombies Ain't My Neighbors, Feature 9: A Sprite Kit Built Ahead — Plan

**Status (2026-11-15):** APPROVED, then REVISED: the approved design reused sprites across stages;
building found that breaks partway playback (below), and the owner chose option 2 ("Option 2"):
the kit holds the next stage's fresh sprites, built ahead, each used once. BUILT, uncommitted.

**Master plan:** [2026-11-14-zombies-aint-my-neighbors.md](2026-11-14-zombies-aint-my-neighbors.md)
(decision 11: heavy work before play; the Game TODO "hide the 0.32 s hitch when a stage is built").

## Why

Building a stage takes about 340 ms (measured 2026-11-15, one player): the zombie pool 168 ms (16
at 10.5 ms), the TVs 63 ms, the neighbors with their effects 59 ms, a kid 42 ms (168 ms with four
players), the rest 11 ms. Nearly all of it is parsing sprite files again for sprites every stage
rebuilds alike. The engine can only build an animated sprite by reading its file (cloning parsed
frames would reach into engine internals: Engine wishlist #12), but the game may keep its own
built sprites. The owner, 2026-11-15: keep the game's sprites in a cache on the engine's context,
built on first use, not on the scene.

## Decisions (option 2; Claude's calls inside it, the owner may overturn them)

| Decision | Value | Why |
|---|---|---|
| Where the kit lives | `SpriteKit` (`sprite_kit.py`), handed from scene to scene: the card makes one (or is given the last stage's) and gives it to its stage; a cleared stage gives it to the next card; a scene given none makes its own. It keeps waiting sprites in a storage group of its own and a `MirrorCache` its sprites share | Ruling below: a game cannot declare a context slot yet. The removed-sprites guard allows sprites held in a group |
| Used once | A stage takes each sprite it needs out of the kit; nothing goes back. A sprite no stage takes (a kid built for a player who unplugged on the card: at most 3 kids, 15 sprites, a run) stays in the kit, never sampled, until the title or the game's end drops the kit; no later stage can take it, since players join only on the title, which starts a new kit (the final review) | A sprite first seen in its own stage gets its replay id as today (finding below) |
| What building ahead does | Loads sprite files only: no positions, no random draws. A stage still places everything and draws every random number in its constructor, in today's order | A playback rebuilds a stage from the streams as its constructor began (`scene_start.py` rule 4): a draw made on the card would be lost |
| What a stage needs | One kid per joined slot (its look), 4 TVs, 16 zombies, 12 zaps, one neighbor per entry of the run's neighbors (by kind), the exit door | Today's build |
| When it is built | The stage card builds one sprite a frame toward the coming stage's needs (a kid, the costliest, about 42 ms); a stage takes what is ready and builds the rest at once (the card skipped early, a player joining mid-stage) | The card's 2 s are idle; a pause only where there was no wait |
| Inside a playback scope | A rebuilt scene is given no kit, so it makes its own: nothing is shared with the waiting live game | A playback builds a stage beside the live game (`replay/playback.py` rule 2) |
| The TV | Its constructor only loads; `Tv.place(world_x=, world_y=, stream=)` places it and draws its first wait | The one constructor that drew a random number |
| Proving it | A stage built after a full card loads no sprite file (counted at `AnimatedSprite`'s load); the golden plays back from stage 2's start, leaving the live stage's kit as it was; building ahead draws no random number; the golden replays unchanged | Each risk named above, checked |

## Found while building (2026-11-15): reused sprites and partway playback

Blocks the plan as approved; put to the owner with options before any code.

- A sprite's id comes from the draw order (its layer, the feet's row) when it is first seen
  (`LayeredDirty.sprites()` in `tracing.sample_scene_frame`). The recorder first sees a stage's
  sprites at the end of the frame that switched to it, before its first logic frame; a playback
  starting at that stage first sees its rebuilt sprites only at the end of its start frame. A
  reused sprite keeps the id stage 1's positions gave it, while a playback numbers the rebuilt
  ones by stage 2's positions. A probe with the engine's own `StableSpriteIds` and
  `_ids_given_before_start` (two neighbors trading places between stages): DIVERGES; with every
  kit sprite on one layer, in creation order, until the start frame is sampled: MATCH.
- Playback sets the live scene aside without `cleanup()` and builds a `NeighborhoodScene` beside
  it (`replay/playback.py` rule 2): a shared kit taken there would strip the live game's sprites.

## Rulings while building (Claude's, 2026-11-15; the owner may overturn them)

| Ruling | Why | If wrong |
|---|---|---|
| The kit is passed from scene to scene, not kept in an engine context slot | The shared guards require every slot's isolation check in the engine's tests, which may never import a member: no game can declare a slot today without changing those guards (Game TODO). Passing it is explicit, and makes playback and Arcade safety structural: nothing is shared | Fix the guards, then move the kit into a slot |
| The card builds nothing once its stage has begun | Building after hand-over left sprites no stage asked for (found by the no-load test, ticking past the switch) | None |
| `Part` hashes explicitly (`__hash__` over kind and variant) | basedpyright does not see a frozen pydantic model as hashable; the engine's `InputSnapshot` does the same | None |
| Stage 1 is built ahead too: the card before it is "FEATURE PRESENTATION"; the title builds nothing | One place builds ahead, before every stage | A start pressed at once on the card still builds the rest then |

## The final review (a fresh reviewer, 2026-11-15)

No Critical findings; one Important, fixed with a test proven to fail:
- **The property the design rests on had no test** (the golden covers one player and a full
  card): `test_a_stage_built_from_any_kit_is_the_stage_built_without_one` builds stage 2 from the
  card's kit and with none, from the same seed, and compares every sprite's replay id, layer,
  place, hidden and TV wait, and every stream: the card at 0, 0.3, 1.0 and 1.95 s, with 1 and 4
  players and with leftovers (4 on the card, 2 left), each on a fresh seed plus saved ones (the
  owner's rule; fixture `test_a_stage_built_from_any_kit_is_the_stage_built_without_one.json`).
  Planted: a builder drawing a random number, and built-ahead sprites entering the group
  reversed: 9 of 12 fail each (the 3 at 0 s built nothing ahead, so they rightly pass).

Two Minor findings fixed too, since each was a test promising more than it checked: the TV test
now checks the engine's streams across the constructor (proven with a planted draw), and the kid
hand-over test asserts the order `Kid.__init__` makes its props in rather than the storage
group's. A wrong claim corrected: leftovers wait for no later stage (decisions table).

Deferred minors: the no-draw test sees only the engine's named streams (a draw from the global
`random` module is the unseeded-randomness guard's to catch); one test exercises the private
type check `_as` (a guard on a defensive line).

## Results (measured 2026-11-15, one player)

The stage built after the whole card: 2 ms (was 349 ms; a card skipped at once still takes about
that). The card builds 42 sprites over its 120 frames; its longest frame of building is 57 ms (a
kid and its props), on a still card. The golden replays unchanged: same random numbers, same
sprite ids.

## Tasks

1. `SpriteKit`: its slot, building one item, building toward a stage's needs, taking (moving an
   item's sprites, companions included, into the scene's group in their creation order), the
   private kit for a playback; tests for each, and for separate kits in two engine contexts.
2. `Tv.place`, and the neighborhood taking every sprite from the kit (`neighborhood.py`); the card
   building ahead (`feature_card.py`); the load-count, playback and kit-untouched checks.
3. The gates, the golden (replayed; re-recorded only if the order of the sprites changed it), the
   docs page, the master plan and the Game TODO.

## Not in this feature

The engine-side parsed-sprite cache (wishlist #12); sound.
