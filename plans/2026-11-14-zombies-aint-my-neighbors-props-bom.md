# Zombies Ain't My Neighbors: The Props BOM

**Status (2026-11-15):** the TV (feature plan 5), its damage stages, the Channel Changer and its
zap (feature plan 6), the exit door (feature plan 7), and the laser pointer and its dot
(feature plan 8). The rest of the props (weapons and
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

### The TV's damage stages (feature plan 6)

Three zaps a stage (feature plan 6). The case, legs and antenna are the intact TV's, damaged;
size, palette, anchor and hitbox unchanged. Hittable until destroyed; never solid yet.

| Animation | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|
| `cracked-static` | 3 | 0.08 | yes | — | The static, with a white crack running corner to corner across the screen |
| `cracked-spawn` | 4 | 0.08 | no | `cracked-static` (a transition) | `spawn`'s bulge and pop, the crack across it |
| `smashed-static` | 3 | 0.08 | yes | — | The screen half gone: dark glass shards round a black hole, static only in the corners; one antenna arm bent flat; a spark at the hole's edge, a different place each frame |
| `smashed-spawn` | 4 | 0.08 | no | `smashed-static` (a transition) | The hole flashes white on the pop |
| `destroyed` | 3 | 0.1 | yes | — | The screen black, the case scorched (its darkest wood), both antenna arms down; a curl of smoke rising from the top, higher each frame |

A destroyed TV spawns nothing, so it has no `spawn`. 3 + 4 + 3 + 4 + 3 = **17 frames**.

## The Channel Changer (feature plan 6)

The kids' first weapon: a chunky black TV remote with a red power button and a lit green LED
at its tip. Drawn only while a kid shoots (character BOM decision 9), centred on the frame's
hand point and mirrored with the frame; behind the kid when it faces up. One 12x12 canvas for
every facing, so one file holds them all and the hand point is always its centre (6, 6). Anchor
`bottom`, as every sprite in the game; the game places the canvas's centre on the hand. Palette: the outline, three greys of the case, the button's red, the LED's
green and its glow (white). Hitbox: the whole canvas (a TOML animated sprite needs one), never
collided: it is in a hand. One facing per drawn view.

| Animation | Facings | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|---|
| `held_<f>` | down, up, left | 1 | 0.08 | yes | — | Down: seen end-on, the LED toward the viewer below the hand (6 wide, 10 tall). Up: its back, LED away, above the hand. Left: side-on, 12 long and 6 tall, the LED at the left end, the red button on top |

The tip, where a zap leaves (game code, as hand points are, `weapon_rig.REMOTE_TIPS`): the
LED's cell, down (6, 10), up (6, 1), left (1, 6), the outline around it; right mirrors left,
`x' = 11 - x`. **3 frames.**

## The zap (feature plan 6)

What the Channel Changer fires: a small ring of TV static with a bright core. 12x12, anchor
`bottom` (the game places its centre), palette: the outline, the static's four greys, the
LED's green and white. Hitbox `offset_x=2, offset_y=2, width=8, height=8`: hit (it strikes a
zombie or a TV), not solid. One facing (a ring looks the same every way).

| Animation | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|
| `fly` | 3 | 0.06 | yes | — | The ring's static shifts each frame; the core flickers green and white |
| `fizzle` | 2 | 0.06 | no | removed | The ring breaks into a few specks, then fewer |

**5 frames.**

## The exit door (feature plan 7)

A garden gate set into the top hedge's middle, where the kids leave a cleared stage. Closed it is
a white picket gate on two posts; opening, it swings in; open, the gap glows the VR safe room's
blue (the same blue as `saved`), pulsing. 48x48, anchor `bottom`, palette: the outline, the
gate's white wood (3 tones), the posts' darker wood (2), the hedge's greens (2), the glow's blues
(3) and white. Hitbox `offset_x=8, offset_y=16, width=32, height=32`: a kid's touching it while
open clears the stage; not solid. One facing.

| Animation | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|
| `closed` | 1 | 0.08 | yes | — | The gate shut, hedge either side |
| `opening` | 3 | 0.08 | no | `open` (a transition) | The gate swings in a third, two thirds, all the way; the glow grows behind it |
| `open` | 2 | 0.2 | yes | — | The glow's pulse: brighter, dimmer |

**6 frames.**

## The laser pointer (feature plan 8)

The kids' second weapon, a lure: a slim silver pen with a red tip. Drawn only while a kid shines
it, centred on the frame's hand point and mirrored with the frame; behind the kid when it faces
up, as the Channel Changer. One 12x12 canvas for every facing; the grip is its centre (6, 6).
Anchor `bottom`. Palette: the outline, the pen's silver (3 tones), its clip's dark grey, the
tip's reds (2) and white. Hitbox: the whole canvas, never collided (it is in a hand).

| Animation | Facings | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|---|
| `held_<f>` | down, up, left | 1 | 0.08 | yes | — | Down: end-on, the red tip toward the viewer below the hand (4 wide, 9 tall). Up: its back, the clip showing, the tip above the hand. Left: side-on, 10 long and 4 tall, the red tip at the left end, the clip on top |

The tip (game code): its red cell on each facing, the outline around it; right mirrors left,
`x' = 11 - x`. **3 frames.**

## The laser dot (feature plan 8)

Where a shining laser pointer's light lands: a red point with a soft halo, on the lawn 160 px
ahead of the kid. 8x8, anchor `bottom` (the game places its centre). Palette: the reds (3), a
pale pink and white; no outline, since a dot of light has no edge. Hitbox: the whole canvas,
never collided (zombies chase it by distance, feature plan 8). One facing.

| Animation | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|
| `glow` | 2 | 0.06 | yes | — | The point and its halo; the halo a pixel wider on frame 1, so it flickers as a laser does |

**2 frames.**

Total so far: 7 + 17 + 3 + 5 + 6 + 3 + 2 = **43 frames**.

## Audit

Run on each prop entry before its art, with the character BOM's checklist (section 10) where it
applies. The TV's (Claude, 2026-11-14): every state the TV has in feature plan 5 (flickering,
spawning) has an animation (A1); one facing, stated (A2); the non-looping `spawn` names its
Then (A3); size, palette, anchor, hitbox and collision given, the hitbox inside the frame
(4 + 40 = 44 ≤ 48, 12 + 32 = 44 ≤ 48) (A4); timings follow the effects' class, 0.08 s (A5);
symmetric (the antenna is centred) (A8); names follow the rule (A9); 3 + 4 = 7 (A10). No
original design copied (A7): the original game's monsters do not come out of television sets.

The damage stages, the Channel Changer and the zap (Claude, 2026-11-15, before their art):
- **A1:** every state feature plan 6 gives them has an animation: each damaged TV flickers and
  spawns, a destroyed TV only smokes (it spawns nothing, so it needs no `spawn`); the remote is
  held while shooting (it is drawn at no other time); the zap flies and fizzles.
- **A2:** the TV and the zap have one facing, stated; the remote has down, up and left, as the
  kid's shooting poses do (right mirrored).
- **A3:** each non-looping animation names its Then: `cracked-spawn` and `smashed-spawn` go to
  their stage's static, and `fizzle` ends in removal.
- **A4:** each has a size, palette, anchor and hitbox, and says whether it collides. The TV's
  hitbox is unchanged (44 ≤ 48 both ways). The zap's is 2 + 8 = 10 ≤ 12 both ways. The remote's
  is its whole canvas and never collided.
- **A5:** the static, spawns and zap are effects, at 0.06 to 0.08 s. `destroyed` is a death, at
  0.1 s. The remote is one frame, its interval unused.
- **A6:** not applicable: no shared rig.
- **A7:** no original design copied. The original's TVs and remotes are not weapons, and its
  basic weapon is a squirt gun; our zap is static from a remote.
- **A8:** the TV is never mirrored, so its bent antenna may be one-sided. The remote's mirrored
  side view keeps the LED at the front end, and the zap is round.
- **A9:** the names follow the rule (`<state>`, `<state>_<facing>`, multi-word states hyphenated).
- **A10:** 17 + 3 + 5 = 25, as feature plan 6 says; 32 in all with the intact TV's 7.

The exit door (Claude, 2026-11-15, before its art): every state feature plan 7 gives it has an
animation (closed, opening, open) (A1); one facing, stated (A2); the non-looping `opening` names
its Then (A3); size, palette, anchor and hitbox given, and whether it collides (8 + 32 = 40 ≤ 48,
16 + 32 = 48 ≤ 48) (A4); the opening is an effect at 0.08 s, the pulse a slow glow at 0.2 s,
slower than an effect because it is a resting loop (A5); symmetric (A8); names follow the rule
(A9); 1 + 3 + 2 = 6 (A10). No original design copied (A7): the original's exits are doors; ours
is a garden gate glowing as the VR safe room does.

The laser pointer and the dot (Claude, 2026-11-15, before their art): every state feature plan
8 gives them has an animation (the pointer held while shining; the dot glowing) (A1); the pointer
has down, up and left as the shooting poses do, the dot one facing (A2); both loop, so no Then
is owed (A3); size, palette, anchor and hitbox given, neither collided (A4); the dot's flicker is
an effect at 0.06 s (A5); the pointer's mirrored side view keeps its tip at the front, and the
dot is round (A8); names follow the rule (A9); 3 + 2 = 5 (A10). No original design copied (A7):
the original game has no laser pointer and no lure that monsters chase.
