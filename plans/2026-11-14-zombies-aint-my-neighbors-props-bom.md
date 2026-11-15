# Zombies Ain't My Neighbors: The Props BOM

**Status (2026-11-14):** STARTED with the TV (feature plan 5). The rest of the props (weapons and
their streams, pickups, the decoy, doors and keys, hedges, fences and walls with their damage,
the exit, radar icons, title cards) are listed for it in the character BOM, section 9, and are
added here as the features that need them arrive.

**Master plan:** [2026-11-14-zombies-aint-my-neighbors.md](2026-11-14-zombies-aint-my-neighbors.md).
**The character BOM**, whose rules (section 1) every prop follows unless its entry says otherwise:
[2026-11-14-zombies-aint-my-neighbors-2-character-bom.md](2026-11-14-zombies-aint-my-neighbors-2-character-bom.md).

## Rules props add

| Rule | Decision | Why |
|---|---|---|
| Facings | A prop has one facing (it is seen the same from every angle the camera allows) unless its entry says otherwise | Props don't turn |
| Collision | Each entry says whether a prop is hit (by attacks), solid (blocks walking) or neither | Props differ |
| Names | As the character BOM's: `<state>` or `<state>_<facing>`, multi-word states hyphenated | One rule |

## The TV (master plan decision 19; feature plan 5)

A boxy, wood-cased TV on short splayed legs, rabbit-ear antenna on top, its screen showing
static. Monsters come out of it (Lawn Zombies now; Rabbit-Ears later). 48x48, anchor `bottom`,
palette 15 (wood 3 tones, the screen's static 4 greys and its glow, the antenna's metal, the knobs,
the outline). Hitbox (for attacks, from Feature 6) `offset_x=4, offset_y=12, width=40, height=32`;
not solid yet (feature plan 5, Collisions). Large shadow.

| Animation | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|
| `static` | 3 | 0.08 | yes | — | The screen's static changes each frame; a faint scanline glow |
| `spawn` | 4 | 0.08 | no | `static` (a transition) | The screen bulges outward, bulges further, pops in a flash, settles back to static as the monster stands in front |

Damage stages (cracked, smashed and sparking, destroyed and smoking: master plan decision 19)
are drawn with Feature 6, when an attack can cause them; each stage's `static` and `spawn` will be
added then.

Total so far: **7 frames**.

## Audit

Run on each prop entry before its art, with the character BOM's checklist (section 10) where it
applies. The TV's (Claude, 2026-11-14): every state the TV has in feature plan 5 (flickering,
spawning) has an animation (A1); one facing, stated (A2); the non-looping `spawn` names its
Then (A3); size, palette, anchor, hitbox and collision given, the hitbox inside the frame
(4 + 40 = 44 ≤ 48, 12 + 32 = 44 ≤ 48) (A4); timings follow the effects' class, 0.08 s (A5);
symmetric (the antenna is centred) (A8); names follow the rule (A9); 3 + 4 = 7 (A10). No
original design copied (A7): the original game's monsters do not come out of television sets.
