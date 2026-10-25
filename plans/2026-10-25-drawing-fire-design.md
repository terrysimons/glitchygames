# Drawing Fire: Design

- **Date:** 2026-10-25
- **Status:** Design, from a brainstorm with the user. Not yet approved for building.
- **Pictures** (the brainstorm's sketches, in the session's scratchpad; to be copied into
  `docs/` with the first build): `army-scene.png` (the original idea), `army-scene-2.png`
  (tunnels, supply drop, debug seats), `army-scene-3.png` (joining by parachute),
  `camera-battle.png` (the shared screen sliding and zooming), `drawing-fire-vignette.png` (one
  moment of the full vision).

Marking: **(user)** the user decided it; **(my call)** proposed by me and approved, or a
default the builder may revisit; unmarked text explains or connects them.

## 1. Intent

**Names (user):** the game is **Drawing Fire**. The two armies are the **Pencil Platoon** and
the **Graphite Brigade**. **Eraser Front** may be one of the levels (so there are levels:
different battlefields).

The user's childhood drawings, made real: landscape paper covered in a stick-figure war.
Paratroopers drift down while a machine gunner behind sandbags shoots holes in their chutes,
someone shoots back at the gunner, someone else tunnels toward the enemy. **(user)**

What makes it special is **joining**. With the game running, anyone can press START and
become one of the stick men, or parachute in as a new one. Every soldier is a seat, and the
computer, a real AI (a language model driving through the engine's game host), or a person
can sit in it, changing hands mid-battle. That moment of dropping in "keeps us entranced"
**(user)**. It is also why the engine's game host exists: an outer layer that drives the game
without the game knowing (`glitchygames/host.py`).

The user wants to keep designing and adding features over time **(user)**, so the design is a
long vision built in steps, starting with a small MVP (section 4).

## 2. Goals, non-goals, anti-goals

**Goals**
- A battle that is fun to watch and easy to drop into, any time, on any side.
- Seats that change hands without the rules changing: a soldier plays the same whoever drives
  him (my call), so the computer, an AI or a person are interchangeable.
- Exact replays, like every GlitchyGames game: every driver's input reaches the game through
  the engine's doors, and all randomness comes from the engine's seeded streams.

**Non-goals (for now)**
- Realism. These are stick men on paper.
- Any particular real-world army, nation or conflict.

**Anti-goals** (what would make it a failure even if it worked)
- Red against blue, or anything politically charged. **(user)**
- A join that is hard to notice or understand: the drop-in must be obvious and delightful.
- Seats that behave differently for humans and computers (it breaks the hiding, section 3.4).

## 3. The full vision

### 3.1 The battlefield
- Side view, landscape: a ground line across the paper, sky above, and the underground drawn
  cut away beneath it, the way kids draw it. **(user's drawings; cut-away my call)**
- Two armies: the **Pencil Platoon** in pencil yellow and the **Graphite Brigade** in graphite
  grey, both straight off a school pencil and neither politically loaded. **(user)**
- Look: pencil on printer paper, hand-wobbled lines, a little crayon colour (helmets, muzzle
  flashes, explosions), hand-lettered sound effects ("RAT-A-TAT!", "POW!", "BOOM!", "uh oh").
  (my call)
- Each army has a radio tower near its edge (section 3.5).

### 3.2 Seats and drivers
- Every soldier is a seat with one driver: the computer AI, a real AI, or a player. **(user)**
- The debug view shows the "assimilation" first: a tag over every soldier naming his driver
  (CPU, AI, P1...), a seats panel per army, and joins and takeovers as they happen. It may
  move into play mode later. **(user)**

### 3.3 Joining
- With the game running, a new person presses START on a controller. **(user)**
- They choose a side: Random (the default), the Pencil Platoon or the Graphite Brigade. **(user)**
- They take over a soldier on the field, or parachute in from the next plane (section 3.5).
  **(user)**
- The prompt "Press START to join" is always visible, in the game or on the fourth wall.
  **(user)** Drawn as a sticky note on the paper with an arrow at the plane's glowing door, and
  a three-panel how-to strip in a corner: press START, you jump, you're in. (my call)
- Joining must visibly cause the parachute-in. Computer soldiers parachute in too. **(user)**
- A player's chute is striped, with a pennant; computer chutes are plain. (my call)

### 3.4 Roles, death and hiding
- A soldier's job comes with him: take over a digger and you dig, the gunner and you're on the
  gun. Choosing which soldier to take is strategy. **(user, "for now")**
- When your soldier dies you take over another soldier of your army, picked at random (from
  the engine's seed). You do his job, like it or not, "just like the real army". If none is
  available you come in on the next air drop. **(user)**
- Player markings (striped chutes, pennants, tags) show only to your own side, so the enemy
  can't tell players from computer soldiers. **(user)** Exceptions: local play on one screen
  shows both sides **(user)**; a Twitch stream shows both sides **(user)**, accepting that an
  opponent watching it can see who's a player.

### 3.5 Reinforcements, planes and the radio
- Planes bring paratroopers: joining players and computer soldiers. **(user)**
- A randomized back-off (from the engine's seed, so replays match) "calls" each plane, with
  an on-screen countdown. **(user)** Each army's radio tower calls its planes; drawn with a
  little clock beside it. (my call)
- The radio tower can be destroyed, and must be repaired before planes come again. **(user)**
- A radar-jamming soldier speeds up his army's support. **(user)** Read as: he jams the enemy's
  radar so his planes arrive sooner. (my call)
- Open: whether the back-off grows with each call.

### 3.6 Supplies, crates and weapons
- Air drops bring supplies in crates on parachutes: ammo, guns, timber props. **(user)**
- Smashing a crate reveals what's in it. **(user)**
- Shooting a crate's parachute drops it, once the chute has taken enough damage. **(user)**
- The weapon ladder: everyone starts with pistols and upgrades as the battle goes on, so it
  gets harder the further you get. **(user)** Proposed order: pistol, rifle, machine gun, then
  grenades, mortar, bazooka; each step unlocks for both armies on the clock and arrives in
  crates, so catching and smashing crates gets the new guns first. (my call)

### 3.7 Parachute damage (my call, approved: "I love it")
One rule for every chute, crate or soldier:
- Every hit leaves a visible hole; the chute falls a little faster and drifts more.
- Enough holes and it tears: the crate drops like a stone, the paratrooper plummets.
- A crate that lands hard smashes open and spills its contents for whoever gets there first;
  a shot-down paratrooper lands hurt or dies.
- Bigger guns tear faster. When you shoot matters: early, it lands nearer the enemy; late,
  it drifts toward you.

### 3.8 Tunnels
- Diggers tunnel underground toward the enemy (not trenches). **(user)**
- A tunnel needs timber props to go on; past the last prop the roof cracks and can collapse.
  Props come from air drops. **(user)**
- When a tunnel breaks through under the enemy, it calls in a wall of reinforcements: a sky
  full of the tunnelling army's planes. They keep the enemy occupied so more soldiers can
  breach up out of the tunnel. **(user)**
- Open: collapse rules; what a prop costs.

### 3.9 The shared screen
- One shared screen: everybody sees everything. **(user)**
- The battlefield is wider than the screen; the view slides left or right with the armies'
  sizes (a tug of war), and zooms out a little only when both sides have grown and sliding is
  not enough. **(user)** The bigger army pushes the view toward the enemy; an off-screen radio
  tower gets an arrow at the screen's edge; zooming stops while a stick man is still readable
  on a TV. (my call)
- Hard caps: players per side and how big the screen can reasonably get. **(user)** Measured in
  simulations (headless battles with every seat driven by the computer or the host) to tune
  the game. **(user)** Placeholder until then: 8 players per side, about 40 soldiers per army.
  (my call)

### 3.10 Winning
An army wins when the other is fully destroyed with no on-screen support coming. **(user)** Read
as: no soldiers left anywhere, and no plane on its way (a destroyed radio calls none). (my call)

### 3.11 Online and Twitch
- Players join over the internet, if there's room, and via Twitch: streamers can join in and
  help. **(user)** Local play too. **(user)**
- Fifteen chat interactions are kept as TODOs, to decide later **(user)**: enlist (`!join
  platoon`, a chat-ordered soldier), adopt a soldier, vote the next crate, hurry the plane, pick
  where a drop lands, wind, jam the radio, spotter (reveal a tunnel), bounty, cheer meter,
  predictions, doodles drawn onto the paper as cover, medic, instant replay, name the battle.
  Each reaches the game the way a controller does (through the host's doors), so recordings
  include chat's actions.

## 4. The MVP (the first build)

**Scope (user):** computer against computer, then one player against the computer, then two
players. Pistols each. No supply drops, no support (no planes, reinforcements or radio). No
Twitch, no network: local only, two players means two controllers on one screen. Digging comes
later. **(user)**

### 4.1 What it is
- One battlefield that fits the screen (no sliding or zooming yet: my call), with hills and
  sandbags (section 4.2), drawn in the pencil look: the Pencil Platoon on the left, the
  Graphite Brigade on the right.
- Each army starts with a fixed number of soldiers, every one armed with a pistol and driven
  by the computer.
- Soldiers move along the ground and shoot at the enemy. A soldier hit enough times dies.
- An army with no soldiers left has lost (there is no support in the MVP).
- **Between battles** (my call): the winner is announced on the paper for a few seconds, then a
  new battle starts on its own, so there is always something to drop into. Joined players keep
  their side and choose a soldier again. The engine's shared game-over scene is not used: its
  Space/Start restarts and B/Back quits would clash with joining and leaving.

### 4.2 The battlefield in the MVP
- **Hills (user):** the ground is not flat: hills give height, cover and angles, which free aim
  makes matter.
- **Sandbags (user):** walls of sandbags to fight from. A shot bag loses sand (it visibly
  sags, a little stream of sand trickling out), and enough shots flatten it. **(user)**
- **Holes wait for tunnels** (my call, as the user asked me to judge): in the MVP nothing
  digs or explodes, so nothing would make a hole. Holes arrive with the things that make them:
  digging, and later grenades and mortars. A battlefield that changes shape is then built once,
  for all of them.

### 4.3 Controls
- **Dual stick (user):** the left stick moves, the right stick aims at any angle, and a trigger
  fires. "A bit of a hard mode vibe." **(user)** Free aim also serves the later vision: shooting
  up at parachutes and crates.
- The keyboard player (section 4.4, Keyboard) moves with the arrows/WASD and aims with the mouse.
  (my call)

### 4.4 Seats in the MVP
- **Drivers:** the computer, and players. A soldier is driven by exactly one at a time; the
  game asks his driver for his intent each frame (move, aim, fire) and plays it the same way
  whoever the driver is.
- **Computer driver:** simple and readable: advance toward the enemy, keep some spacing,
  shoot the nearest enemy in range, with seeded aim error and reaction delay so battles vary
  with the seed but replay exactly. Mr. Muncher's autopilot
  (`glitchygames/examples/mr_muncher/autopilot.py`) is prior art: it reads the scene as a
  person reads the screen.
- **Where drivers live** (my call): the computer driver is game logic inside the scene,
  deterministic from the engine's seeded streams, with **one random stream per soldier** so a
  seat changing hands never shifts anyone else's randomness. Players' input comes through the
  doors as usual, so recordings hold players' input and replay the computer exactly. A later
  outside driver (a language model through the game host) sends a soldier's intent through
  the doors as a control event addressed to that soldier; that addressing is built when the
  first outside driver is, not in the MVP.
- **"Plays the same whoever drives him"** means the rules: movement, aim, fire rate and damage
  are the same for every driver. (my call)
- **Joining:** pressing START on a controller that has no soldier opens a side choice (Random
  by default, Platoon, Brigade) and then takes over a soldier on that side. With no planes in the
  MVP, joining is always a takeover. **(user-approved call)**
- **Which soldier:** the joining player chooses: a highlight cycles through that side's
  computer-driven soldiers (left/right), starting on the one nearest the middle, and START
  confirms. Choosing is the strategy the user described. A player can't take a soldier another
  player is driving. (my call, from the user's approval of "you choose which soldier" at join)
- **Keyboard** (my call): the keyboard counts as one controller, with Enter as its START, so
  development, the golden replay script and a one-keyboard player all work. Touch joins in the
  browser build come with the touch layout, later.
- **Leaving** (my call): a player leaves by holding Back/Select (or Esc on the keyboard) for a
  second, or by unplugging their controller; their soldier goes back to the computer at once,
  their slot (P1/P2) is freed, and the seats panel logs the leave. Plugging back in is a new
  join.
- **Death:** the player takes over another soldier of their side, picked at random from a
  seeded stream. If their side has none, the battle is over anyway.
- **Markings:** local play shows every player's marking on the one screen.
- **Debug seats view** (the user wants it from the start): with the debug overlay on (F3), a
  tag over every soldier names his driver (CPU, P1, P2), and a panel lists each army's seats
  and the last joins and takeovers with their times.

### 4.5 Milestones, in the user's order
1. **Computer against computer:** a full battle plays itself to a winner. This is also the
   first simulation: headless battles report how long they last and who wins, across seeds.
2. **One player against the computer:** START takes over a soldier; death moves you to
   another; the debug seats view shows it all.
3. **Two players:** a second controller joins, on either side (both against the computer, or
   against each other).

### 4.6 Engine fit and quality bar (as for every GlitchyGames game)
- A `Scene` in `glitchygames/examples/`, controls in an `ActionMap` bound by scancode and
  controller button, all randomness from `glitchygames.randomness` streams, clocks from
  `glitchygames.clock`, every input through the doors (`glitchygames/sources.py`).
- A golden replay (a recorded scripted battle that must replay exactly), tests at the repo's
  100% coverage, the dummy/native driver comparison.
- It should run in the browser build too (`nox -s browser`), with a touch layout
  (`scripts/build_browser_bundle.py` `TOUCH_LAYOUTS`) once its controls settle.

### 4.7 Tuning record (milestone 1)
`uv run python scripts/simulate_drawing_fire.py --seeds 20` (8 soldiers per side, 800x480):
- **Before** (health 3, pistol cooldown 0.6 s): battles ended in 7 to 21 s, with the winner
  keeping 2 to 7 soldiers. Too fast to watch.
- **After** (`SOLDIER_HEALTH = 6`, `PISTOL_COOLDOWN = 1.5`; other battle constants unchanged):
  Pencil Platoon 9 wins, Graphite Brigade 11; mean 45.1 s, shortest 21.4 s, longest 272.7 s
  (with the aim error held per shot and soldiers spaced, see below; it was 12 and 8, mean
  50.3 s, shortest 23.5 s, longest 102.5 s when the error was redrawn every frame and armies
  piled onto one spot). A further 200 seeds: Platoon 101, Brigade 99, mean 46.4 s, longest
  348.0 s, all ended (the long ones are queues behind sandbags that nobody can see over).
  No stalemates.
- **After the crowding fix** (Task 9, ruling R20: a crowded soldier never walks past the
  enemy's front): 20 seeds, Platoon 13, Brigade 7; mean 46.7 s, shortest 20.6 s, longest
  272.7 s. 200 seeds: Platoon 112, Brigade 88; mean 47.1 s, shortest 18.2 s, longest 348.0 s,
  all ended. 1,000 seeds: Platoon 539, Brigade 461, mean 52.5 s, longest 437.4 s (before the
  fix, the same 1,000 seeds: Platoon 521, Brigade 479, mean 51.5 s, longest 437.4 s). The
  Platoon's lean was there before the fix and grows a little with it; worth watching, not yet
  a reason to retune.
- **Driver rules the simulation forced** (my call):
  - Hills block bullets, so a soldier neither stands nor fires until the ground leaves a clear
    line to his target (otherwise whole armies stood on either side of a hill, firing into it).
  - A standing sandbag blocks walking, so a soldier stopped at one with the enemy hidden behind a
    hill shoots the sandbag's middle until it is low enough to walk over.
  - A soldier stops at a sandbag only when the enemy is in range and in sight; cover is for
    fighting, not for waiting.
  - He keeps his target unless another enemy is nearer by `TARGET_SWITCH_MARGIN` (30 px), so near
    ties cannot restart his reaction delay every frame.
  - A soldier blocked by a sandbag with the enemy in sight but out of range shoots the sandbag.
- **Spread:** each soldier draws his stand-off once, from his own stream, as a fraction of the
  pistol range in `STAND_OFF_FRACTION_RANGE` (0.6 to 0.9), so an army does not stand on one x.
- **Spacing** (my call): an army piled onto one x because every soldier stopped at the first x
  with a clear line over a hill (or at one sandbag edge), so eight soldiers drew as one. A
  soldier now walks on when a friend of higher priority is within `SOLDIER_SPACING` (16 px;
  the front soldier of each army has priority), steps back instead when the enemy is within
  `MELEE_PIXELS`, and queues 16 px behind a friend ahead on the way to a covering sandbag.
  Walking on never takes him past the enemy's front: within `MELEE_PIXELS` of it he steps back
  toward his own side (otherwise a friend he can never get clear of, a player walking on at
  the same speed, led him through the enemy's line to the field's edge).
  Sandbags are laid on level ground (`SANDBAG_MAX_GROUND_VARIATION`, 12 px).
- **Held aim** (my call): the aim error is drawn once per shot from the soldier's own stream (and
  again for a new target), then held, so the arm drawn along the aim does not shake at 60 Hz.

## 5. Constraints
- GlitchyGames engine on pygame-ce, Python 3.14; desktop and browser (PyScript/Pyodide).
- Deterministic and replayable: no wall-clock or unseeded randomness in game logic.
- The rules never depend on who drives a soldier, and a seat changing hands never shifts
  anyone else's randomness (section 4.4).

## 6. Left to the builder
- Numbers: army sizes, health, pistol range, damage, fire rate, bullet speed, movement speed.
  Start sensible; the computer-against-computer simulations tune them.
- The computer driver's exact behaviour beyond section 4.4.
- How the debug seats view is drawn: the engine's overlay panels are a fixed list
  (`glitchygames/debug/overlay.py` `DebugPanel`), so either add a hook for a game's own panel
  or draw it in the game behind the overlay's toggle.
- The side-choice screen after START, as long as Random is the default and it takes a moment
  at most.
- How the pencil look is rendered (procedural wobbly lines or sprites).
- The internal shape of drivers and seats, within section 5's constraints.

## 7. The engine mechanic this game proves: swatches

The user's rule: every new game adds a new game mechanic; once proven, it is considered for the
engine. **(user)** Drawing Fire proves **swatches**: recolouring sprites in memory by palette
swap, ergonomically. **(user)** It is built inside the game first, shaped so it can move into the
engine unchanged.

- **In the sprite file (user-approved):** next to `[colors]`, a generic `swatches` group holds
  named sets of swappable colours. The artist names each set for what it means in their game
  (here `livery`), and each part of a set lists the palette characters it covers and the role
  colour it takes:

  ```toml
  [colors]
  "h" = { red = 90, green = 110, blue = 60 }   # helmet
  "H" = { red = 60, green = 80, blue = 40 }    # helmet, in shadow
  "u" = { red = 120, green = 120, blue = 90 }  # uniform

  [swatches.livery.helmet]
  colors = ["h", "H"]
  role = "primary"

  [swatches.livery.uniform]
  colors = ["u"]
  role = "secondary"
  ```

- **In the game:** a scheme gives the role colours (`primary`, `secondary`) and, optionally, a
  colour for one named part; the game applies it to a set by name, e.g.
  `soldier.recolored(livery=Scheme(primary=PENCIL_YELLOW, secondary=...))`.
- **Shades follow:** every colour in a part keeps its brightness relative to the part's first
  colour, so the helmet's shadow comes out a darker yellow or a darker grey.
- **In memory:** the file never changes; each scheme's frames are built once and cached.
- **Names (user):** "swatches" (generic, engine) and "livery" (this game's set); the user
  wanted a less gruesome word than "skins".
- **Consequence for the MVP:** soldiers are sprite files (Bitmappy's TOML format, drawn to look
  pencilled), wearing the Pencil Platoon's or the Graphite Brigade's livery, instead of stick
  men drawn by code; aim (the arm and pistol) is still drawn at its angle over the sprite.

