# Zombies Ain't My Neighbors, Feature 2: The Character BOM

**Status (2026-11-14):** SIGNED OFF by the owner (draft 2.1). Audited twice; the owner answered audit 2's four questions
(section 9, decisions 6 to 9). Audit 1 (on draft 1, section 11) failed 8 of 10
checks; draft 2 applied the owner's four answers (section 9) and every audit-1 fix; audit 2
(section 12) passed A2, A6, A8, A9 and A10 and found the fixes now applied below, plus four
questions for the owner (section 12). Calls marked **default** are Claude's, taken from audit 1's
bracketed answers (section 11); the owner may overturn any. No art is drawn until the owner has seen the audit (master plan, decision 18).

**Master plan:** [2026-11-14-zombies-aint-my-neighbors.md](2026-11-14-zombies-aint-my-neighbors.md).

A character BOM (bill of materials) lists every sprite character in the game, each animation it
needs, the frames in each, their timing, loop rule and what plays next, and the character's
size, palette and hitbox, before any pixel is drawn. It answers three questions up front: is
every gameplay state covered, is the art consistent across the cast, and how much art is it.

Props and UI (weapons, pickups, projectiles, the decoy, tiles, doors, radar icons, title cards)
get their own BOM later. The shared effects characters rely on are listed here (section 6).

## 1. Rules every character follows

| Rule | Decision | Why |
|---|---|---|
| Format | Sprite TOML (ANIMATION_README.md): one file per character, one `[[animation]]` per namespace, magenta `(255, 0, 255)` as the transparency key | The engine's native format (decision 3) |
| View | Three-quarter top-down: the top of the head and the front of the body | The genre's camera |
| Grid | Tiles 32x32 native; people 32x48; large monsters 48x48 or 64x64; nothing larger in this BOM (owner, 2026-11-14: "32x48 native and much much more detail", decision 10) | People fit a one-tile corridor; Bitmappy's 32x32 tiles fit the grid as they are |
| Scale | Drawn at 1x: people are 32x48 on screen, as before, with four times the pixels | 800x480 shows 25x15 tiles; the surfaces are the same size as before, so the Pi's memory is unchanged |
| Style | SNES-era pixel art, not Atari (owner, 2026-11-14): volumes shaded with ramps from a light at the top left (skin 3 tones, clothes 4, trousers 3), hand-drawn details on top (faces, goggles, drawstrings, laces), the shared outline round the silhouette. The approved sample: one standing Dex (feature plan 3) | The owner's bar |
| Facings | The closed set {down, up, left}. Right is left mirrored: the game flips each left frame once in `setup()` and caches it (scaled frames and white copies too), sets `AnimatedSprite.hitbox_flip_x` so the hitbox and the anchor's draw offset mirror with it, and puts the cached flipped image back after every `AnimatedSprite.update`, since a frame change redraws the image (BUGS.md #144). Brave Adventurer sets `hitbox_flip_x` too but flips its image every tick, uncached; the cache is new game code | 130 frames fewer (section 8); the engine's own mirroring support |
| Diagonals | Standing and walking have diagonal facings, down-left and up-left, drawn as the front and back turned a quarter (decision 11); a kid faces the nearest of eight directions; the weapon poses use the nearest straight facing until weapons bring their own diagonals | The owner asked for a diagonal pose |
| Asymmetry | Nothing that matters may sit on one side only, since right is left mirrored: held items are carried in front or centred, and lettering only on front faces (it would read backwards mirrored) | Audits 1 and 2, A8 |
| Hand points | Each kid `shoot`, `walk-shoot`, `spray`, `swing`, `launch` and `throw` frame has a hand point, kept in game code (never in the TOML, which has no point fields), shared by all four kids (one rig). A mirrored frame's hand point is `x' = width - 1 - x` (31 - x for a kid), and the weapon sprite is mirrored with the frame | Weapons sit in the hand on every facing |
| Hurt and knockback | Being hit is never a pose: a white flash in code (below), and, when a hit knocks a character back (the Blow-Up Mascot's `belly-bump`), a slide in code with `idle_<f>` held for the slide. A zombie's `grab` is contact damage only; the kid is not held | Audit 2, A1 |
| Hit flash | A hit flashes the sprite white for 0.1 s. White copies are made in code once, in `setup()`, cut from the magenta key (TOML animated frames keep magenta opaque), for drawn and mirrored frames alike. **No hurt frames are drawn** | About 32 frames fewer |
| Player colours | Each kid's clothes carry their player's colour: P1 ghoul green `(92, 230, 92)`, P2 pumpkin orange `(255, 140, 26)`, P3 seance violet `(176, 97, 255)`, P4 TV-glow cyan `(51, 214, 255)`. A kid is fixed to their slot (**default**: P1 is always Dex). The night palette swap leaves the player colours unchanged, and no monster uses a green near P1's (the Lawn Zombie's skin is a grey-blue) | Matches the title's slots; players always find themselves |
| Palettes | 15 colours besides magenta for every character (the SNES sprite budget): kids, neighbors, monsters, the villain and the Glitch Beast (one of its 15 the reserved accent, character `A`, swapped to the player's colour in code); effects 8; intro sprites 15. One shared outline colour `(24, 16, 32)` across the cast | The SNES look needs shading ramps |
| Shadows | Separate shared sprites under every character in play, never drawn into frames: small 16x6 (24-wide characters), person 24x8, large 40x10 (48- and 64-wide, Vesper included), floating 20x6 drawn 8 px lower than the feet for floaters (the Wraith). None in the intro, and none for the Pool Creature while it lurks in its pool | One shadow per size class |
| Anchor | `frame_anchor = "bottom"` for grounded characters, `"center"` for floaters. It aligns frames by their hitboxes, so it matters only where frames carry their own hitboxes; no character in this BOM has per-frame hitboxes. Effects are placed by the game: bottom-anchored and centred on the target's hitbox (a 64x64 cloud or storm over a 32x48 kid or neighbor) | The engine's FrameAnchor; audit 2, A4 |
| Hitboxes | One `[sprite.hitbox]` per character for **being hit** (the body, not hair or raised arms), inside every frame. Walls use a **foot box**, the bottom 12 rows at the hit box's width, kept in game code. Characters wider than 32 (the beast, the mower, the mascot, the pool creature) cannot pass one-tile corridors; that is intended: they smash or go round | The engine has one hitbox per frame; walls need the feet |
| Timing | Walk 0.12 s a frame; idle 0.5 s; attacks 0.08 s; deaths 0.1 s; spawns, reveals and gestures (emerge, inflate, start-up, summon, respawn, rescue) 0.1 s; dissolves and teleports (phase, teleport, the shared effects) 0.06 to 0.08 s, quicker so they read as a flash; the intro's timings follow its pacing. Attacking on the move (`walk-shoot`) keeps the walk's 0.12 s, so the legs match `walk`. A row that differs from its class says why | One rhythm across the cast (audit 2, A5) |
| Names | A namespace is `<state>` or `<state>_<facing>`, where facing is one of `down`, `up`, `left`. A state of several words joins them with hyphens (`walk-shoot`, `knocked-out`, `phase-in`), so splitting on the last underscore always finds the facing. Section 2 maps the game's shared states to each character's namespaces | Audit 1, A9 |
| Then | What plays after a non-looping animation is in each table's "Then" column. A Then that names a namespace in the same file is a `[[transition]] from=... to=... when="animation_complete"` (`src/glitchygames/animation/state_machine.py`, one per facing; a condition such as `and lives_left > 0` works when the game puts the value in the machine's context). Every other Then (removed, holds, hidden, another sprite, a trigger such as "when a kid comes near") is game code. A non-looping animation holds its last frame by default | Audits 1 and 2, A3 |

## 2. Shared states to namespaces

Code asks for a shared state; this table says which namespace each character plays for it.
Facing `<f>` is down, up or left (right mirrors left). A dash means the character never enters
that state.

Hurt is the same for everyone: a white flash in code, and a knockback slide in code where a hit
knocks back (section 1); it has no namespace.

| Character | spawn | idle | move | attack | die | Special |
|---|---|---|---|---|---|---|
| Kid | `respawn` | `idle_<f>` | `walk_<f>` | `shoot_<f>`, `walk-shoot_<f>`, `spray_<f>`, `swing_<f>`, `launch_<f>`, `throw_<f>` (launch roots the kid; swing and throw stop the kid for their 0.24 s) | `knocked-out` | `cheer`, `rescue` |
| Glitch Beast | glitch-cloud effect | `idle_<f>` | `walk_<f>` | `smash_<f>` | glitch-cloud effect | `rescue` |
| Vincent Vesper | `teleport-in` | `idle` | — | `summon` | `defeated` | `laugh`, `teleport-out`; never hittable outside the boss fight |
| Lawn Zombie | tv-spawn effect | `walk_<f>` frame 0 held | `walk_<f>` | `grab_<f>` | `crumble` | — |
| Static Wraith | `phase-in` | `drift` | `drift` | `lunge` | `burst` | `phase-out` |
| Rabbit-Ears | tv-spawn effect | `idle` before it first moves; then `hop_<f>` frame 0 held | `hop_<f>` | `zap_<f>` | `fizzle` | — |
| Kiddie Pool Creature | `emerge` | `lurk` (in the pool); `idle` out of it before it first moves; then `slither_<f>` frame 0 held | `slither_<f>` | `splash_<f>` | `melt` | — |
| Haunted Mower | `start-up` | `idle` before it first moves; then `drive_<f>` frame 0 held | `drive_<f>` | `charge_<f>` | `wreck` | — |
| Blow-Up Mascot | `inflate` | `idle` before it first moves; then `bounce_<f>` frame 0 held | `bounce_<f>` | `belly-bump_<f>` | `deflate` | — |
| Neighbor | — | `idle` | — | — | lost effect | `panic`; saved effect |
| TV Watcher (neighbor) | — | `idle` | — | — | lost effect | `panic`, `staticify` |

## 3. Players: the four kids

The kids share one body rig: the same frame counts, timing, poses, hitbox and hand points. Each
has their own head, hair, clothes and colours. One kid is drawn first and checked; the other
three redraw the head and clothes on the same poses. Every kid wears a VR headset, pushed up on
the forehead in play and over the eyes in the intro.

| Kid | Player | Look (redesigned in draft 2 where audit 1 flagged it) |
|---|---|---|
| Dex | P1, ghoul green | Green hoodie, knit beanie with a pom-pom over the headset strap, sneakers |
| Marisol | P2, pumpkin orange | Denim overalls with matching orange knee patches (symmetric) over a striped shirt, two puff buns, high-tops |
| Theo | P3, seance violet | Violet sweater vest, round glasses under the headset, loafers |
| June | P4, TV-glow cyan | Cyan windbreaker, headphones around her neck, rain boots |

Size 32x48, anchor `bottom`, hitbox `offset_x=6, offset_y=12, width=20, height=36`, palette 15.

Moving while attacking (owner, 2026-11-14): shooting and spraying on the move play `walk-shoot`;
`launch` roots the kid while it plays (it is heavy); `swing` and `throw` stop the kid only for
their 0.24 s. The weapon is drawn only while attacking (owner, 2026-11-14), so idle and walk
frames carry no hand points and nothing is drawn behind the body when facing up.

| Animation | Facings | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|---|
| `idle_<f>` | down, up, left | 2 | 0.5 | yes | — | Breathing bob: body 1 px down on frame 2 |
| `walk_<f>` | down, up, left | 4 | 0.12 | yes | — | Contact, pass, contact, pass; arms swing opposite to legs |
| `shoot_<f>` | down, up, left | 2 | 0.08 | no | `idle_<f>` | Standing shot with a one-handed weapon; frame 2 a 1 px recoil |
| `walk-shoot_<f>` | down, up, left | 4 | 0.12 | yes, while firing on the move | `walk_<f>` | `walk_<f>`'s legs with both arms forward; also used for spraying on the move (Claude's call: the arms are the same) |
| `spray_<f>` | down, up, left | 2 | 0.08 | yes, while the button is held | `idle_<f>` | Both hands braced on a hose-style weapon; frame 2 a shudder. The stream is the weapon's effect |
| `swing_<f>` | down, up, left | 3 | 0.08 | yes, while held | `idle_<f>` | Melee sweep: back, across, through |
| `launch_<f>` | down, up, left | 3 | 0.08 | no | `idle_<f>` | Launcher on the shoulder, the kick, recovery |
| `throw_<f>` | down, up, left | 3 | 0.08 | no | `idle_<f>` | Wind-up, release, follow-through |
| `knocked-out` | down | 5 | 0.1 | no | `respawn` when lives are left (a transition with `when="animation_complete and lives_left > 0"`); otherwise holds its last frame | Stagger, spin (2 frames), fall, flat with stars |
| `respawn` | down | 4 | 0.1 | no | `idle_down` | Headset flashes; pixels resolve from the top down ("loading in") |
| `cheer` | down | 2 | 0.25 (a bouncier beat than idle) | yes | — | Fists up, jump: stage clear, and the ending |
| `rescue` | down | 2 | 0.1 | no | `idle_down` | High-five pose |

Per kid: 6 + 12 + 6 + 12 + 6 + 9 + 9 + 9 + 5 + 4 + 2 + 2 = **82 frames**. Four kids: **328**
(82 drawn fully, 246 as head-and-clothes redraws).

A player out of lives (**default**): their slot shows PRESS START to rejoin with the next spare
life, as arcades do; their kid's last `knocked-out` frame stays until it fades.

### 3.1 The Glitch Beast (the monster-form power-up)

A pixel-glitched VR avatar, all blocks and scan lines, drawn once; its accent colour (palette
character `A`) is swapped to the player's colour in code, so four tints come from one drawing.
Changing in and out is the shared glitch-cloud effect (section 6) over the swap: no per-kid
transform frames (owner, 2026-11-14). The beast can rescue neighbors, and a hit ends the form
(glitch cloud, then the kid's hit flash) without costing a life (owner, 2026-11-14). Where the
beast does not fit (a one-tile corridor), the game places it at the nearest spot where it does,
under the glitch cloud.

Size 64x64, anchor `bottom`, hitbox `offset_x=12, offset_y=16, width=40, height=48`, palette 15.

| Animation | Facings | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|---|
| `idle_<f>` | down, up, left | 2 | 0.5 | yes | — | Glitch flicker on frame 2 |
| `walk_<f>` | down, up, left | 4 | 0.12 | yes | — | Heavy stomps |
| `smash_<f>` | down, up, left | 3 | 0.08 | no | `idle_<f>` | Raise, slam, rebound; breaks hedges and walls |
| `rescue` | down | 2 | 0.1 | no | `idle_down` | A careful pat on the head |

Total: 6 + 12 + 9 + 2 = **29 frames**.

## 4. The villain

**Vincent Vesper**, host of the cancelled *Midnight Spook-tacular*: a lanky late-night horror host
in a moth-eaten tuxedo and cape, with a TV-static aura. He taunts from the edges of stages, laughs
over the game-over screen, and fights at the end of a run (the boss design is a later feature).
Size 48x64, anchor `bottom`, hitbox `offset_x=12, offset_y=12, width=24, height=52`, palette 15.

| Animation | Facings | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|---|
| `idle` | down | 3 | 0.5 | yes | — | Cape sway |
| `laugh` | down | 3 | 0.12 (a cackle reads faster than idle) | yes | — | Head back, shoulders shake |
| `summon` | down | 4 | 0.1 (slower than an attack: it is a gesture) | no | `idle` | Arms raised, static sparks |
| `teleport-out` | down | 4 | 0.08 | no | gone | Dissolves into horizontal static bands |
| `teleport-in` | down | 4 | 0.08 | no | `idle` | The bands resolve |
| `defeated` | down | 6 | 0.1 | no | holds, then fades in code | Clutches chest, cape droops, collapses into a puddle of static |

Total: **24 frames**.

## 5. Monsters

All original designs; each comes out of the show's old episodes. Tier 1 is needed for the first
playable stage; Tier 2 arrives as stages add it. Terrain breaking: the Lawn Zombie pushes
through hedges by walking into them (**default**); the Haunted Mower flattens fences and
flowerbeds by driving (owner); the Kiddie Pool Creature smashes fences with `splash` (**default**);
the Blow-Up Mascot knocks down walls with `belly-bump` (**default**).

**TV spawners** (owner, 2026-11-14): Lawn Zombies and Rabbit-Ears come out of TV sets left on in
yards and houses (the tv-spawn effect). Players stop a TV by destroying it, through damage
stages (**default**: intact, cracked screen, smashed and sparking, destroyed and smoking; the
spawn rate halves at each stage and stops when destroyed). The TV is a prop: its stages are in the
props BOM (section 9). Breaking needs no extra frames: the hedge or wall shows the damage (props BOM).

### 5.1 Lawn Zombie (Tier 1): the basic monster

A shambling neighbor in a bathrobe and fuzzy slippers, clutching a soggy newspaper to his chest
with both arms (centred, so mirroring keeps it). He comes out of TV sets left on around the
neighborhood (the tv-spawn effect), not out of lawns (owner, 2026-11-14: the lawn rise echoed the
original's first enemy). 32x48, anchor `bottom`, hitbox `offset_x=6, offset_y=12, width=20, height=36`, palette 15. Idle: `walk_<f>` frame 0 held (a shuffler stands
like it walks).

| Animation | Facings | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|---|
| `walk_<f>` | down, up, left | 4 | 0.18 (slower than a kid) | yes | — | Shuffle |
| `grab_<f>` | down, up, left | 2 | 0.1 (a lunge, slower than a shot) | no | `walk_<f>` | Lunge, arms clamp: contact damage, the kid is not held (the newspaper drops for the lunge, back in frame 1 of the walk) |
| `crumble` | down | 5 | 0.1 | no | removed; the slippers fade in code | Robe sags, falls apart, slippers left |

Total: 12 + 6 + 5 = **23 frames**.

### 5.2 Static Wraith (Tier 1): passes through walls

A floating figure of TV static and scan lines, with two bright eye dots. The same from every side,
so no facings. 32x48, anchor `center`, hitbox `offset_x=4, offset_y=4, width=24, height=36`,
palette 8 (static is a few greys and two eye colours, within the 15 budget), floating shadow.

| Animation | Facings | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|---|
| `drift` | none | 4 | 0.1 (static must crawl faster than idle) | yes | — | Idle and moving: the static changes each frame, the outline holds |
| `phase-out` | none | 3 | 0.08 | no | hidden inside the wall | Breaks into horizontal bands |
| `phase-in` | none | 3 | 0.08 | no | `drift` | The bands resolve; also its spawn |
| `lunge` | none | 2 | 0.08 | no | `drift` | Stretches toward its target: contact damage to a kid, or takes a neighbor |
| `burst` | none | 4 | 0.08 (a pop, faster than a death) | no | removed | Collapses to a bright dot, then a "TV off" line |

Total: **16 frames**.

### 5.3 Rabbit-Ears (Tier 2): small, fast, in swarms (replaces Puppet Pal)

Little creatures shaped like old TV antennas: a round set-top body, two telescoping antenna ears,
spring legs. They hop out of TV sets left on in houses (the tv-spawn effect) and zap with sparks
between their ears. 24x24, anchor `bottom`, hitbox `offset_x=4, offset_y=6, width=16, height=18`,
palette 15, small shadow.

| Animation | Facings | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|---|
| `idle` | down | 2 | 0.25 (twitchy) | yes | — | Ears twitch |
| `hop_<f>` | down, up, left | 3 | 0.08 (faster than a kid) | yes | — | Squash, leap, land |
| `zap_<f>` | down, up, left | 2 | 0.08 | no | `hop_<f>` | Spark arcs between the ears |
| `fizzle` | down | 3 | 0.1 | no | removed | Ears droop, a puff of smoke |

Total: 2 + 9 + 6 + 3 = **20 frames**.

### 5.4 Kiddie Pool Creature (Tier 2): ambushes from backyard pools

A swamp blob with a pool noodle stuck through its middle (centred). 64x64, anchor `bottom`,
hitbox `offset_x=8, offset_y=24, width=48, height=36`, palette 15, large shadow. While it lurks
it cannot be hit: the game ignores hits during `lurk` (no per-frame hitbox: audit 2 found that an
empty one shifts the frames 60 px down under the bottom anchor, and that the engine's collision
margin turned it into a hittable 4x4 box: Engine wishlist #11, since fixed on this branch).

| Animation | Facings | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|---|
| `lurk` | none | 2 | 0.5 | yes | `emerge` when a kid comes near | Bubbles only |
| `emerge` | down | 4 | 0.1 (a reveal, held a beat) | no | `slither_<f>` toward the kid | Surface bulges, rises dripping |
| `idle` | down | 2 | 0.5 | yes | — | Out of the pool, waiting: ooze sags |
| `slither_<f>` | down, up, left | 3 | 0.15 (heavier than a walk) | yes | — | Ooze pulses |
| `splash_<f>` | down, up, left | 3 | 0.08 | no | `slither_<f>` | Rears up, slams; breaks fences |
| `melt` | down | 4 | 0.1 | no | removed | Puddles, the noodle left floating |

Total: 2 + 4 + 2 + 9 + 9 + 4 = **30 frames**.

### 5.5 Haunted Mower (Tier 2): tears through hedges (replaces the Werepoodle)

A ride-on lawn mower with nobody in the seat, headlight eyes, its grass bag flapping like a jaw.
It flattens fences and flowerbeds; hedges are left to the beast and the zombie (owner,
2026-11-14: shredding hedges echoed the original's chainsaw maniacs).
48x48, anchor `bottom`, hitbox `offset_x=4, offset_y=16, width=40, height=28`, palette 15, large
shadow.

| Animation | Facings | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|---|
| `start-up` | down | 3 | 0.12 (the cough of an engine) | no | `drive_down` | Pull cord yanks itself, smoke, headlights on; its spawn, in a garage or shed |
| `idle` | down | 2 | 0.25 (an engine idles fast) | yes | — | Sputter, shaking |
| `drive_<f>` | down, up, left | 3 | 0.1 (faster than a walk) | yes | — | Wheels turn, grass sprays (flattens fences and flowerbeds) |
| `charge_<f>` | down, up, left | 3 | 0.08 | no | `drive_<f>` | Rears, revs, lunges forward |
| `wreck` | down | 5 | 0.1 | no | removed; a smoking wreck fades in code | Blade flies off, it tips, sputters out |

Total: 3 + 2 + 9 + 9 + 5 = **28 frames**.

### 5.6 Blow-Up Mascot (Tier 2): knocks down walls (replaces the Rerun Saucer)

An inflatable snack-commercial mascot (a grinning cereal box with flailing tube arms), escaped
from the show's ad breaks. Its lettering is on the front face only (mirroring). It bounces, and bumps kids and walls. 64x64, anchor `bottom`, hitbox
`offset_x=8, offset_y=8, width=48, height=52`, palette 15, large shadow.

| Animation | Facings | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|---|
| `inflate` | down | 4 | 0.1 (a reveal) | no | `idle` | Fills from a flat heap; its spawn |
| `idle` | down | 2 | 0.5 | yes | — | Arms flail slowly |
| `bounce_<f>` | down, up, left | 3 | 0.12 | yes | — | Squash, rise, land |
| `belly-bump_<f>` | down, up, left | 3 | 0.08 | no | `bounce_<f>` | Leans back, bumps, wobbles; knocks walls down and kids back |
| `deflate` | down | 5 | 0.1 | no | removed | Hisses, crumples, flat |

Total: 4 + 2 + 9 + 9 + 5 = **29 frames**.

## 6. Neighbors and shared effects

Seven original neighbor types, redesigned where audit 1 flagged them. Each has its own idle
activity and panic; being saved and being lost are shared effects. All are 32x48, anchor
`bottom`, hitbox `offset_x=4, offset_y=8, width=24, height=40`, palette 15. `idle` loops at 0.5
s; `panic` loops at 0.12 s (panic must read frantic). Neighbors never move.

| Neighbor | `idle` | `panic` | Points (proposal) |
|---|---|---|---|
| Street Chalk Artist | 3 frames: drawing on the driveway | 2 frames: chalk thrown, arms over head | 100 |
| Pizza Delivery Teen | 2 frames: checking the order slip | 2 frames: pizza box held up as a shield | 100 |
| Yoga Neighbor | 3 frames: slow pose changes on a mat | 2 frames: frozen in a pose, wobbling | 200 |
| Garage Drummer | 3 frames: drumming on a practice pad | 2 frames: hiding behind the drum | 200 |
| Mail Carrier | 2 frames: sorting letters | 2 frames: letters flying | 200 |
| Lawn-Chair Reader | 2 frames: turning a newspaper page | 2 frames: newspaper over the head | 100 |
| TV Watcher | 2 frames: lit by a portable TV on an extension cord | 2 frames: the TV crackles, he can't look away | 500 |

**The TV Watcher changes mid-stage** (owner, 2026-11-14): when a static storm reaches his TV (the
static-storm effect over him), he has a few seconds to be saved; then he plays `staticify` and
becomes a Static Wraith, and counts as lost.

| Animation | Frames | Interval | Loop | Then | Frame notes |
|---|---|---|---|---|---|
| `staticify` | 5 | 0.1 | no | replaced by a Static Wraith playing `drift` | Static climbs up his body from the TV; the outline breaks into scan lines |

Neighbors: 17 idle + 14 panic + 5 staticify = **36 frames**.

### Shared effects

| Effect | Size | Frames | Interval | Loop | Then | Used by |
|---|---|---|---|---|---|---|
| `saved` | 32x48 | 5 | 0.06 | no | removed | A neighbor touched by a kid or the beast: pixels stream up into a VR "safe room" portal |
| `lost` | 32x48 | 5 | 0.08 | no | removed | A neighbor caught by a monster: flickers and fades to a TV-static silhouette |
| `glitch-cloud` | 64x64 | 6 | 0.06 | no | the beast's `idle_<f>`, or the kid's, in the same facing | The kid turning into the beast and back |
| `tv-spawn` | 64x64 | 4 | 0.08 | no | the monster's move in facing down (Lawn Zombie `walk_down`, Rabbit-Ears `hop_down`) | Monsters that come out of TV sets: the screen bulges and pops |
| `static-storm` | 64x64 | 3 | 0.08 | yes, while the storm lasts | — | The storm over the TV Watcher |
| `shadow` | 4 sizes | 1 each | — | — | — | Every character (section 1) |

Effects are not collidable; the game places each one bottom-anchored and centred on its target's
hitbox. Total: 5 + 5 + 6 + 4 + 3 + 4 = **27 frames**.

## 7. Intro vignette sprites (decision 15)

The headsets are on from the first shot (decision 9), so there is no headset-on animation.
After the hands come through the screen, a Lawn Zombie climbs out (**default**). Intro sprites
are not collidable; palette 15 (the climbing zombie 14, as in play); anchor `bottom`; no shadows.
The TV's `switch-off` is also the game-over screen (decision 5).

| Sprite | Size | Animation | Frames | Interval | Loop | Then |
|---|---|---|---|---|---|---|
| Kid in a sleeping bag (one per kid) | 48x32 | `sit` | 2 | 0.5 | yes | `startled` when the TV bursts |
| | | `startled` | 2 | 0.12 | no | holds |
| The TV | 64x64 | `show` | 4 | 0.25 (the host's show flickers) | yes | `static` |
| | | `static` | 3 | 0.08 | yes | `bulge` |
| | | `bulge` | 4 | 0.12 | no | `burst` |
| | | `burst` | 4 | 0.08 | no | holds, broken |
| | | `switch-off` | 3 | 0.08 | no | holds, dark: the game over (the picture collapses to a line, then a dot) |
| Monster hands | 64x64 | `reach` | 4 | 0.12 | no | the zombie's `climb-out` |
| Lawn Zombie climbing out | 64x64 | `climb-out` | 4 | 0.12 | no | the intro cuts to the title |
| Lamp | 32x32 | `still` | 1 | — | — | `flicker` with the TV's static |
| | | `flicker` | 2 | 0.08 | yes | — |
| Snack bowl | 32x32 | `still` | 1 | — | — | — |

Total: 4 x (2 + 2) + (4 + 3 + 4 + 4 + 3) + 4 + 4 + (1 + 2) + 1 = 16 + 18 + 4 + 4 + 3 + 1 =
**46 frames**, in 9 sprites.

## 8. Totals

| Group | Characters | Frames |
|---|---|---|
| Kids | 4 (one rig) | 328 (82 full, 246 redraws) |
| Glitch Beast | 1 (four tints in code) | 29 |
| Villain | 1 | 24 |
| Monsters, Tier 1 | 2 (Lawn Zombie, Static Wraith) | 39 |
| Monsters, Tier 2 | 4 (Rabbit-Ears, Pool Creature, Haunted Mower, Blow-Up Mascot) | 107 |
| Neighbors | 7 | 36 |
| Shared effects | 6 (shadow in 4 sizes) | 27 |
| Intro | 9 sprites | 46 |
| **Everything** | | **636** |
| **First playable stage**: kids, Lawn Zombie, Static Wraith, two neighbors (Pizza Delivery Teen, Lawn-Chair Reader), the TV Watcher, saved, lost, static-storm, tv-spawn, shadows, and the TV's `switch-off` for the game over (plus the TV spawner prop, in the props BOM) | | **408** |

The first stage: 328 + 23 + 16 + 4 + 4 + 9 + 5 + 5 + 3 + 4 + 4 + 3 = 408 (the zombie lost its 4
`rise` frames and the stage gained the 4-frame tv-spawn effect).

**Mirroring saves 130 frames**: kids 92 (each kid's left sets: 2 + 4 + 2 + 4 + 2 + 3 + 3 + 3 = 23),
beast 9, Lawn Zombie 6, Rabbit-Ears 5, Pool Creature 6, Haunted Mower 6, Blow-Up Mascot 6.
**Code-made hit flashes save about 32**: one hurt frame per drawn facing for each character that
takes hits: ten with three facings (four kids, the beast, the zombie, Rabbit-Ears, the Pool
Creature, the mower, the mascot) is 30, plus the Wraith and the villain.

**Memory, for the Raspberry Pi** (corrected by audit 2): drawn frames plus mirrors (636 + 130 =
766); white copies only for characters that can be hit (636 less 27 effects, 46 intro and 36
neighbor frames is 527, plus the 130 mirrors: 657); the beast's extra tints (three more, each
29 + 9 frames, 114; their white copies are the same as the first's) is 1,537 surfaces. If the
drawn accent matches no player colour, a fourth tint adds 38. At this BOM's largest frame, 64x64
at 1x (16 KB), that is at most about 25 MB (no separate scaled copies now that sprites draw at
1x); most frames are 32x48 (6 KB at 1x), so the real figure is
far smaller. The engine's own surface cache is extra. To be measured, not assumed, when the art
loads.

## 9. Decisions

| # | Date | Decision | By |
|---|---|---|---|
| 1 | 2026-11-14 | Weapon poses: walk-and-shoot, continuous spray, melee swing and shoulder-fired, looping while held | owner |
| 2 | 2026-11-14 | Redesign everything audit 1 flagged: the Wagon Twins (now the Garage Drummer), the Werepoodle (now the Haunted Mower), Puppet Pal (now Rabbit-Ears), the Rerun Saucer (now the Blow-Up Mascot), Dex's backwards cap (now a beanie), Marisol's bomber jacket (now overalls), and Hose Grandpa (now the Street Chalk Artist) | owner |
| 3 | 2026-11-14 | The neighbor who changes mid-stage: the TV Watcher, caught in a static storm, becomes a Static Wraith if not saved in time | owner |
| 4 | 2026-11-14 | Monster form: one glitch-cloud effect for every kid; the beast can rescue; a hit ends the form without costing a life | owner |
| 5 | 2026-11-14 | Defaults from audit 1's questions 4 and 6 to 12 (question 5 was the owner's, decision 4), each overturnable: terrain breaking as in section 5 (the mower's part since decided by the owner, decision 7); game over is the TV switching off with Vesper's `laugh` on screen; the ending is the kids' `cheer` and Vesper's `defeated`; bonus and secret stages get characters only with their stage design; the intro's headsets are on from the first shot and a zombie climbs out after the hands; a kid is fixed to their slot; night stages are a palette swap in code, measured on the Pi first; a player out of lives rejoins with PRESS START; the decoy is a prop | Claude (defaults) |
| 6 | 2026-11-14 | Zombies come out of TV sets, not lawns (`rise` dropped, 4 frames). TVs are spawners players destroy, through damage stages | owner |
| 7 | 2026-11-14 | The Haunted Mower flattens fences and flowerbeds; hedges stay the beast's and the zombie's | owner |
| 8 | 2026-11-14 | `launch` roots the kid; `swing` and `throw` stop the kid only for their 0.24 s | owner |
| 9 | 2026-11-14 | Weapons are drawn only while attacking: no hand points on idle or walk frames | owner |
| 10 | 2026-11-14 | Sprites are 32x48 native for people (every size and hitbox in sections 3 to 7 doubled), drawn at 1x, in SNES-era detail with 15-colour palettes; the style was approved on a sample Dex ("Much better") | owner |
| 11 | 2026-11-14 | **Diagonal facings** (owner: "I want a diagonal pose"): standing and walking also face down-left (three-quarter front) and up-left (three-quarter back); down-right and up-right are those mirrored, as right is left. A kid faces the nearest of eight directions. The weapon poses get diagonals with weapons (Claude's call). Each kid gains 12 frames (2 idle + 4 walk, in two facings): 94 a kid, 376 for the four | owner (scope: Claude) |

The speed potion is the walk at a shorter interval plus an afterimage effect, and the medkit has
no pose (both in the props BOM). The exit at stage clear is `walk_up` and a fade. The TV
Watcher's change echoes the original's tourists turning into werewolves; the master plan allows
mechanics, and the design (a static storm, a TV, a Wraith) is ours.

**For the props and UI BOM**, so nothing is lost: the TV spawner (on, spawning, and its damage
stages: intact, cracked, smashed and sparking, destroyed and smoking), weapons and their streams
and projectiles, the decoy (idle wobble, hit, pop), keys and locked doors, trash cans and cupboards, breakable hedges,
fences and walls with their damage states, the exit door, radar icons per neighbor type, title
cards, an off-screen marker per player, the speed afterimage, the smoking mower wreck and the
zombie's slippers fading.

**Before any art**: compare the cast against reference art of the 1993 game (audit 2 could not
clear the Kiddie Pool Creature and the Lawn-Chair Reader from memory), and record the result here.

## 10. The audit (run on every draft before any art)

Each line passes or fails; a failure is fixed in this document before drawing starts.

| # | Check |
|---|---|
| A1 | Every gameplay state in the master plan has an animation for every character it applies to (or a written reason it needs none) |
| A2 | Every character that moves has the facings {down, up, left}, or says why it has none |
| A3 | Every non-looping animation names what plays after it |
| A4 | Every sprite has a size, a palette budget, an anchor and a hitbox (or "not collidable"), and every hitbox fits inside every frame |
| A5 | Timing follows section 1, or the row says why not |
| A6 | Characters that share a rig share frame counts, timing, hitbox and hand points exactly |
| A7 | No design copies the original game: no Zeke, Julie or Dr. Tongue lookalikes; none of its victim types (cheerleaders, barbecue dad, tourists, teacher, archaeologist, soldier, babies, the dog); none of its enemy designs |
| A8 | Nothing that matters is on one side only, since right mirrors left |
| A9 | Every namespace follows section 1's naming rule, and section 2 maps every shared state |
| A10 | The totals add up: section 8 against sections 3 to 7 |

## 11. Audit 1, on draft 1 (2026-11-14)

Kept as the record. Its section numbers refer to draft 1 (whose sections 7, 8 and 9 were the
totals, the audit and the questions); draft 2 answers every finding below.

A fresh reviewer, who had not written the draft, ran section 8 against the master plan, the
sprite format (ANIMATION_README.md) and the engine source. **A2 and A6 passed; A1, A3, A4, A5,
A7, A8, A9 and A10 failed.** Every frame total was right; the counts around them were not (fixed
in draft 1's totals section).

### Format facts the draft must use (verified in engine source)

- **Flipping:** the engine has `AnimatedSprite.hitbox_flip_x` (`src/glitchygames/sprites/
  animated.py`), which mirrors the hitbox and the anchor's draw offset for a game that draws a
  mirrored image (Brave Adventurer uses it). Mirrored frames must use it. Caching the flipped
  images once is the game's work, and must cover the scaled frames and the white copies too.
- **Scale:** `AnimatedSprite.scale` (an integer) does the 2x; section 1 should name it.
- **Anchor:** `frame_anchor` aligns frames by their **hitboxes**, not their edges. With one
  sprite-level hitbox it does nothing; it matters only where frames carry their own hitboxes (the
  Werepoodle's 16x16 and 24x24 frames). Floaters (Wraith, Saucer) should use `center`.
- **White flash:** TOML animated frames keep magenta opaque, so a white silhouette must be cut
  from the magenta key, not from alpha.
- **Then:** what plays after a non-looping animation can be written as `[[transition]] from=...
  to=... when="animation_complete"` (`src/glitchygames/animation/state_machine.py`), one per
  facing; there are no `_right` namespaces in a file, so the game maps right to left plus a flip.

### Fixes Claude will make in draft 2 (no owner decision needed)

| Check | Fix |
|---|---|
| A3 | A "Then" column on every table, including effects and the intro; written as transitions where the game will use them |
| A4 | Per-frame hitboxes for the Werepoodle's poodle frames; a palette budget for every sprite class (villain, beast, effects, intro); "not collidable" for effects and intro props; `center` anchor for floaters; shadow sizes per class; a foot-box width per size class, and whether the beast fits a one-tile corridor; a hitbox rule for the Pool Creature's `lurk` |
| A5 | Every timing that differs from section 1 gets its reason, or the section 1 value; the intro gets timings |
| A6 | Hand points shared by all four kids, stated; drop the claim that the intro reuses the kids' rig |
| A8 | The zombie clutches the newspaper in front with both arms; the Pool Creature's noodle is centred; hand points and weapon sprites mirror with the frame (x' = width - 1 - x); white copies cover mirrored frames |
| A9 | Section 1's "one lookup rule" replaced by a per-character table from shared states (spawn, idle, move, attack, die) to namespaces; facings are the closed set {down, up, left}, right being left plus a flip; states with underscores are named so a parser never splits them |
| A10 | Done above |
| Format | The facts above written into section 1 |
| Consistency | Puppet Pal is a ventriloquist dummy: `collapse` loses the strings (it slumps, jaw dropping); the intro's `headset_on` goes, since the headsets are on from the first shot (decision 9), unless the owner wants the kids to put them on; the beast's tint uses one reserved palette character |

### Gaps found (A1): states with no animation

Most important first. Items marked **owner** need a decision (section 9 and below); the rest
Claude fills in draft 2.

1. **Shooting while walking (owner).** A run-and-gun fires on the move, but `shoot` is a standing
   pose. Options: `walk_shoot_<facing>` (4 frames x 3 facings: 12 a kid, 48 in all), or a split
   upper and lower body (fewer frames, more code).
2. **Weapon poses (owner).** The master plan's genre includes continuous spray, a shoulder-fired
   launcher and a melee sweep; a 2-frame `shoot` shows none. Add `spray_<facing>` and
   `swing_<facing>`, or keep our weapon roster to gun and throw poses.
3. **A neighbor who changes mid-stage (owner).** No neighbor changes. If the Werepoodle is that
   mechanic it must be rescuable before nightfall (needs `panic`, and saved/lost effects that fit
   16x16).
4. **Monsters breaking hedges and walls (owner).** Only the player's beast smashes. Which monsters
   break terrain, and do they use their attack animation?
5. **The decoy (owner).** A lure monsters attack: idle wobble, hit, pop. Character or prop?
6. **Static Wraith attack.** Draft 2: contact damage with a 2-frame `lunge`.
7. **Monster-form handover for each kid (owner).** The beast is drawn once, so "the kid's pixels
   scatter" needs four variants (40 frames) or a generic glitch cloud plus each kid's `respawn` wipe.
8. **Game over (owner).** What plays: the villain's `laugh` over the kids' last `knocked_out` frame,
   or a TV-switching-off vignette?
9. **Spawns.** Draft 2: the Wraith reuses `phase_in`; the Puppet and the Saucer get spawn frames, or
   come from in-stage TVs (a spawner effect).
10. **Saucer abduction.** Draft 2: the neighbor plays `lost` inside the beam; `damaged` overlays
    hover and beam rather than replacing them.
11. **Werepoodle after `yelp`.** A `dazed` loop; a beast `idle` after nightfall.
12. **Monster idles.** Draft 2: an idle for every monster that can be blocked or waiting, or "walk
    frame 0 held", stated per monster.
13. **Speed potion, medkit, drinking.** Draft 2: speed is the walk at a shorter interval plus an
    afterimage effect (props BOM); no drink or heal poses.
14. **Monster form edge cases (owner).** Can the beast rescue neighbors? When it is hit, does it
    `transform_out` and then `knocked_out`?
15. **Bonus and secret stages, and the end of a run (owner).** Their own characters? An ending
    vignette (reuse `cheer`)?
16. **The intro's monsters (owner).** Only hands come through the screen; should a whole monster
    climb out (reusing the zombie's `rise`)? A lamp `flicker` to match the TV.
17. **The exit at stage clear.** Draft 2: `walk_up` and a fade; the door is a prop.
18. **For the props and UI BOM, so nothing is lost:** radar icons per neighbor type, title cards,
    keys and locked doors, trash cans and cupboards, breakable walls, an off-screen marker per
    player.

### Originality concerns (A7)

Checked from memory of the 1993 game; to check against reference art before the art starts. The
A7 list also misses two of its victim types the master plan names: **babies** and **the dog**.

| Item | Concern | Risk |
|---|---|---|
| Wagon Twins | Two toddlers are the original's babies victim | High |
| Werepoodle | A dog (an original victim) that turns into a werewolf at nightfall echoes its tourists turning into werewolves on night stages | High |
| Puppet Pal | A small, fast, grinning doll fills the role of its evil dolls | Medium |
| Rerun Saucer | Its Martians with UFOs; the cardboard-and-fishing-line take is ours, the role is not | Medium |
| Dex's backwards cap, Marisol's bomber jacket | Signature costume elements of the original heroes, as recalled | Medium |
| Lawn Zombie's `rise` | A zombie climbing out of a suburban lawn is the original's iconic first enemy; the bathrobe design is ours | Low to medium |
| Hose Grandpa | An older man doing a backyard chore is close in role to its barbecue dad | Low |
| Kiddie Pool Creature, Vincent Vesper | Genre-generic; Vesper is no Dr. Tongue lookalike | Low |

### Questions only the owner can answer

The ones that change the most are asked first; the rest have Claude's default in brackets.

1. Weapon poses: walk-and-shoot, continuous spray, melee swing, shoulder-fired? (all four, as
   loops where held)
2. The originality redesigns: replace the Wagon Twins, the Werepoodle's night-werewolf twist and
   the two costume elements? (yes)
3. The mid-stage-changing neighbor: which one, and what does it change into? (a neighbor caught
   in a TV-static storm turns into a Static Wraith)
4. Which monsters break terrain? (the zombie pushes through hedges; the Pool Creature smashes
   fences; both with their attack animation)
5. Monster form: per-kid transforms or a generic glitch cloud; rescue as the beast; hit as the
   beast? (glitch cloud; yes, it can rescue; a hit ends the form without costing a life)
6. Game over and the ending? (game over: the TV switching off, the villain's laugh on screen;
   ending: the four kids `cheer`, then Vesper `defeated`)
7. Bonus and secret stages: their own characters? (not yet; decided with the stage design)
8. The intro: headsets on from the first shot; only hands through the screen, or a whole monster?
   (headsets on; a zombie climbs out after the hands)
9. Is a kid fixed to a player slot and its colour? (yes: P1 is always Dex)
10. Night stages: a palette swap in code or night art? (palette swap, measured on the Pi first)
11. A player out of lives while others play on: what do they see? (their slot shows PRESS START
    to rejoin, as in arcades, with the next spare life)
12. The decoy: a character here, or a prop? (a prop with three animations, in the props BOM)

## 12. Audit 2, on draft 2 (2026-11-14)

A fresh reviewer ran section 10 on draft 2, checked every audit-1 finding and the owner's four
decisions, and probed the format with a test sprite loaded through `SpriteFactory` (hyphens in
namespaces load, play, transition and save; a per-frame `width=0, height=0` hitbox is kept and
never collides under plain `colliderect`; conditional transitions such as
`animation_complete and lives_left > 0` parse).

**Result:** A2, A6, A8, A9 and A10 passed; A1, A3, A4, A5 and A7 failed. Every total was right.
The owner's four decisions were applied everywhere they reach. Fixed in place above (no owner
decision needed): knockback and grab (section 1, Hurt and knockback); swapping into the beast in
a corridor (section 3.1); the TV's `switch-off` for the game over (section 7, +3 frames: 640 in
all, 408 for the first stage); effects placement and the two unnamed Thens (section 6); which
Thens are transitions and which are game code (section 1, Then); timing classes for spawns,
gestures, dissolves and the intro (section 1, Timing); hurt in the state table (section 2);
monster idles that would snap the facing (section 2); the Pool Creature's `lurk`, which an empty
per-frame hitbox would have drawn 60 px low (section 5.4); lettering and patches that mirroring
would reverse (section 1, Asymmetry; Marisol); Vesper's shadow and hittability; shadows in the
intro and the pool; player colours against the night swap and green zombies; the memory model,
which overcounted (section 8: about 25 MB, not 29); the props list carried forward and a reference
check scheduled before art (section 9); stale section references.

Found in the engine (Engine wishlist #11, not fixed): the collision margin
(`collision.detection.get_collision_rect_with_margin`) shrinks a rect by twice the margin, and
pygame-ce normalises the negative size, so a box narrower than twice the margin grows into a
hittable one (`Rect(10, 10, 0, 0).inflate(-4, -4)` gives `Rect(12, 12, -4, -4)`, which collides).

### Questions for the owner (all answered 2026-11-14: decisions 6 to 9, each as recommended,
with TV spawners added to the first)

1. **The Lawn Zombie's rise from lawns** echoes the original's signature first enemy (audit 1
   flagged it; decision 2 covers it). Recommended: zombies come out of TV sets, as the intro shows
   (the tv-spawn effect), and `rise` goes (4 frames fewer).
2. **The Haunted Mower's hedge-shredding** fills the original's chainsaw maniacs' role. Recommended:
   it flattens fences and flowerbeds instead, and hedges stay the beast's and the zombie's.
3. **Swing, launch and throw on the move.** Recommended: launch roots the kid while it plays
   (heavy); throw and swing stop the kid only for their 0.24 s. No new frames.
4. **Weapons while idle or walking.** Recommended: the weapon shows only while attacking (no hand
   points on idle and walk frames). Showing it always adds hand points to 18 more frames a kid
   (shared by the rig), and a draw-behind rule for `up`.
