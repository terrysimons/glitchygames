# Solid collision (engine audit #1, with #7)

Part of the 2026-11-02 backlog run (the owner's explicit permission to plan, fix, commit, test
and push each item on its own branch).

## Where things stand

The audit's evidence is out of date. Its "7 `_resolve_*_collision` methods" and the duplicated
`_player_support_span` / `_entered_wall_from_left` were merged on 2026-10-26 (workspace packages,
part 2): Brave Adventurer's classic and Papyrus editions share one terrain base class
(`brave_adventurer_core/scene.py`), with three hooks for their differences (the foot line, a
float or int standing y, the scarab class). Today there are:

| | Brave Adventurer (both editions) | Clockwork Keep |
|---|---|---|
| Resolvers | ground (+ pit edges as walls), wall tops and sides, scarab terrain | one-way platforms, elevators, moving gears |
| Horizontal support | a stable support span (trailing foot for ground) | the hitbox now |
| Vertical test | overlap, falling or still | swept fall (BUGS.md #205) |
| Terrain positions | snapped | raw |
| Walls | sides and tops | the playfield bounds only |
| Ceilings | none | none |

PaddleSlap's ball resolves paddles with the same side rule as Brave Adventurer's walls
(`_entered_paddle_from_left`). The engine detects (`CollisionManager`) but resolves nothing;
`compute_push_out` and `GroundConstraint` exist and nothing uses them.

## Design

**Two layers: shared rules in the engine, policy in the games.** The games' differences above
are game design (Brave Adventurer's stable stance on ledges, Clockwork Keep's jump-through
platforms), and every one of them is pinned by golden traces and replays. A single generic
resolver would have to pick one policy and change the other game's play; instead the engine
holds the rules every resolver is built from, and each game keeps its policy.

**Phase 1 (this branch): the primitives, with no behavior change.**
`glitchygames/collision/solids.py`:

- `entered_from_left(...)`: the previous-position side rule (Brave Adventurer's walls, the
  ball's paddles). Each caller passes its own centre measure (Brave Adventurer an integer
  `rect.centerx`, the ball a float), so ties fall as before.
- `world_x_flush_left_of(...)` / `world_x_flush_right_of(...)`: flush placement against a solid's
  side from `collision_rect_offset` (pit edges, walls, a turning scarab: six sites).
- `feet_land_on_surface(...)`: Clockwork Keep's swept landing, available to any game.

Proof of no change: every golden trace and replay byte-identical, the games' own tests unchanged.

**Phase 2 (next, needs the level format): solids as data.** The level tools' tilemap format
(`plans/2026-10-18-level-tools-a-tilemap-format.md`) already names tile properties (`solid`,
`one_way`, `hazard`, ...) merged into `CollisionManager` layers by property. A `SolidLayer` resolver
on those layers, configured by a policy object (support: hitbox or stable span; vertical test:
overlap or swept; positions: snapped or raw), would let a new game get ground, walls and one-way
platforms without writing resolvers, and let the existing games move onto it one policy at a
time, each move checked against its goldens.

**Phase 3: what no game has yet.** Ceilings (a jump into a wall's underside), slopes, and
moving-platform carry generalized from Clockwork Keep's gears. Each needs a game that uses it, per
the "new game, new mechanic" rule.

**#7 (balls on `CollisionManager`):** ball-paddle detection already uses it; the paddle side
rule now comes from the engine. Ball-ball resolution stays PaddleSlap's own (BUGS.md #174's swept
pass), since elastic exchange is ball physics, not solid collision.

## Plan (phase 1)

1. `collision/solids.py` with tests (each rule's branches).
2. Brave Adventurer (walls, pits, scarabs), the ball (paddles) and Clockwork Keep (swept landing)
   call the primitives; their methods stay as the games' policy.
3. The full suite: golden traces and replays unchanged.
4. Update `plans/engine-audit.md` #1/#7 and `plans/future-work.md` (the stale duplication note).
5. Commit, push, PR.
