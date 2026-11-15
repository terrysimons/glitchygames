# Zombies Ain't My Neighbors, Feature 8: The Laser Pointer — Plan

**Status (2026-11-15):** BUILT, uncommitted, awaiting the owner's review (the plan approved:
"Yes"). The owner asked for it ("when you
shine the laser pointer somewhere, the zombies chase the laser pointer, but its batteries run out
quickly") and chose Claude's suggestion, a battery that recharges by itself ("Yes").

**Master plan:** [2026-11-14-zombies-aint-my-neighbors.md](2026-11-14-zombies-aint-my-neighbors.md)
(mechanic 2: weapons with strengths and switching; the Game TODO this replaces).
**Spec:** the owner's request above; the character BOM's `shoot_<f>` and `walk-shoot_<f>` poses
and hand points (section 3); the props BOM, which gains the laser pointer and its dot first.

## Goal

A second weapon, the laser pointer, a lure. Holding fire shines a red dot on the lawn ahead of
the kid, and zombies near it chase the dot instead of kids and neighbors. Its battery is short:
3 seconds of shine, then a wait while it recharges. Each kid switches between it and the
Channel Changer.

## Decisions (Claude's calls; the owner may overturn them)

| Decision | Value | Why |
|---|---|---|
| Switching | **K** on the keyboard (by scancode), **Y** on a pad (button 3 on the joystick layer, Y's number), toggling the kid's weapon between the Channel Changer and the laser pointer. A switch takes effect at once; each kid starts with the Channel Changer | One button beside the fire key's hand; never a reserved key (Space, Esc, Enter, P, Q, backtick, F3, F4) |
| Shining | While fire is held and the battery has charge, the kid poses `shoot_<f>` standing (its first frame held, the arm out) or `walk-shoot_<f>` moving, the laser pointer in the hand, and a red dot sits on the lawn **160 px** ahead in the kid's eight-way facing (clamped to the yard), moving with the kid | The BOM's existing poses; no beam: real laser beams don't show |
| The lure | Each zombie within **240 px** of a dot (frame to frame) chases the nearest dot instead of a kid or neighbor, and stands on it once there. Touching still counts: a zombie that meets a kid or neighbor on its way knocks out or loses as before | The owner's "zombies chase the laser pointer"; touching unchanged keeps it a risk |
| The battery | **3.0 s** of shine when full. Shining drains 1 s a second; not shining refills it at **0.3 s a second** (10 s from empty). Run flat, it is dead until refilled to **1.0 s**, so it can't flicker on and off at empty. It refills whichever weapon is held | "Batteries run out quickly"; a rhythm players learn |
| The warm-up (the owner, 2026-11-15: "a delay before the laser shows... and power draws normally during the delay") | **0.4 s** (Claude's value): holding fire with the laser pointer, the kid aims, the pointer in hand, and the battery draws from the first frame; the dot appears after 0.4 s of unbroken drawing. Releasing starts the warm-up again (the charge spent stays spent), so tapped fire never lights the dot | Against rapid fire, and for tension |
| A visible beam (the owner, 2026-11-15, after the feature was committed: "a beam shining to the laser point but the beam is fading in and out with alpha"; this overrides "no beam") | A red line, 2 px, from the laser pointer's tip to the dot, while the dot shines; its opacity pulses smoothly from 64 to 192 and back twice a second (Claude's values), timed by the frames it has shone so replays repeat it; drawn in code each frame (`laser.LaserBeam`), over the dot and under everything standing | The owner's ask |
| Several lasers | Each kid's laser has its own dot and battery; a zombie goes for the nearest dot | Co-op |
| The heads-up display | Under each player's lives: a small battery bar (a sprite, redrawn when its tenth of a second of charge changes), and the held weapon (`ZAP` or `LASER`) | Players must see the charge and the weapon |
| New props (props BOM, audited before art) | The laser pointer in the hand: 12x12, `held_<f>` for down, up and left (one frame each; right mirrored), a slim silver pen with a red tip, its tip where the dot's light leaves; the dot: 8x8, `glow` 2 frames at 0.06 s, looping, a red point with a halo, no hitbox use (not collided) | The remote's pattern (feature plan 6) |
| Not in it | Battery pickups (with items), sound, a visible beam | Scope |
| The golden | The neighborhood golden's opening gains a weapon switch (K), a laser burst that pulls a zombie, and a switch back; its stage-clear route is re-planned with `scripts/plan_neighborhood_route.py` and the golden re-recorded. The switch's key and button join the controls tables (`tests/replay/golden_replay_controls.py`, a shared file), since switching is an action, not a polled key | The golden must exercise every bound control |

## Tasks

1. **The props BOM entries and their audit**: the laser pointer and the dot.
2. **Art** (`art/weapon_rig.py`, `sprites/laser_pointer.toml`, `sprites/laser_dot.toml`): the
   props BOM's conformance tests, the engine's checks, each file equal to its rig's output.
3. **Switching** (`roster_scene.py` or the neighborhood's action map; `kid.py`): K and Y switch the
   kid's weapon, on every device kind and layer; reserved keys stay unbound; the touch layout gains
   a Switch button (K).
4. **The battery** (`laser.py`): drain, recharge, the dead state until 1.0 s, its exact frames.
5. **Shining** (`kid.py`, `laser.py`): the pose, the laser pointer in the hand (mirrored, behind
   when facing up), the dot 160 px ahead along the aim, clamped to the yard, gone when the
   battery dies or fire is released.
6. **The lure** (`zombie.py`, `neighborhood.py`): zombies within 240 px chase the nearest dot,
   gather on it, and still touch kids and neighbors on the way; several dots.
7. **The HUD** (`hud.py`): the battery bar and the weapon, per joined player.
8. **The golden, the planner, the docs**: the opening's switch and burst, the route re-planned,
   the golden re-recorded and its route test green; the docs page and the master plan.

Each task: tests first, then ruff, the type checkers and the game's tests; before the commit,
the engine's replay and guard tests too (`tests/replay`, the process-state guard): the push gate
runs them, and feature plan 7 found what skipping them costs.

## Review Focus

- The battery at its edges: exactly 3 s of shine from full, refill to 1.0 s before a dead laser
  shines again, a switch mid-shine (the dot goes, the battery keeps its charge).
- A zombie torn between a dot and a kid it is already touching (the touch wins).
- A dot clamped at the yard's edge, and two dots at the same distance (the first kid's wins).
- A kid knocked out or out of lives while shining: the dot goes at once.
- Pause and resume while shining.

## Rulings while building (Claude's, 2026-11-15; the owner may overturn them)

| Ruling | Why | If wrong |
|---|---|---|
| The warm-up is 0.4 s (the owner asked for a warm-up, the value is Claude's) | Long enough to stop a tapped trigger and to be felt; short enough to answer a zombie closing in | One constant (`WARM_UP_SECONDS`) |
| The remote and the laser pointer share one class (`HandProp`), told apart by sprite and tips | One path for placing, mirroring and the tip; parallel copies drift | None |
| `TIME_TOLERANCE` moved to `tolerances.py` (`kid.py` re-exports it) | `laser.py` needs it, and `kid.py` now imports `laser.py`: a cycle otherwise | None |
| The scene sets a kid's `bounds` after building it, not through the constructor | A sixth constructor argument broke the project's argument limit; a suppression needs the owner's yes | None |
| The dot lands 160 px ahead of the kid's feet, the lure measured feet to dot | The lawn is where both stand | Numbers to tune by playing |
| The golden's opening gains K, a held J (warm-up into a lit dot), and K again, before the re-planned route | Every bound control exercised; the route test keeps the clear | A longer golden (2139 frames, 181 KB) |

## Found while building

- **A seed-dependent flake, and the owner's rule for them:** `test_a_laser_pulls_a_zombie_off_a_neighbor`
  failed in some runs: the neighbor's drawn place could put Dex at the yard's edge, so his dot
  missed. The neighbor is pinned now. The owner then set the rule: save a failing seed to a
  fixture for its test vector, and run a fresh seed plus every saved one, parametrized
  (`tests/regressed_seeds.py`, `tests/fixtures/regressed_seeds/`). That test's seed was never
  captured, so its fixture is empty. The group-span test of feature plan 7 now keeps seeds 1,
  3 and 5 for four players: 1 and 5 fail with feature plan 7's old span rule planted back, and
  3 failed the test's earlier form.
- Two tests passed before their code existed, so they were rewritten to fail first: the
  neighbor lure test (the zombie chased Dex anyway) and the lured-knockout test (Dex was the
  nearest prey without any lure).

- **The final review (a fresh reviewer, 2026-11-15)** found 3 Important and 7 Minor issues. Fixed
  with tests that failed first:
  - Switching from the laser to the remote with fire held fired two zaps on consecutive frames:
    the laser's held time was banked into the remote's rhythm. A switch now lets go of the
    trigger (`test_switching_to_the_remote_with_fire_held_fires_on_the_fresh_press_rhythm`).
  - A dot clamped at the yard's top edge pulled zombies above the yard, out of the camera's
    reach. The dot now stays far enough in that a zombie standing on it fits in the yard (half a
    frame from the sides, a frame's height from the top;
    `test_a_zombie_lured_toward_the_yards_edge_stays_in_the_yard`).
  - The golden's laser burst lured no zombie: it shone where none could reach. Dex now turns
    toward the zombie coming along the top before shining (a zombie in reach for 125 frames),
    and `test_the_golden_lures_a_zombie_with_the_laser` checks it. The golden is now 2161 script
    frames (2313 with its tail), 197 KB: the largest in the repository.
  - Raised from Minor, since it defeats the owner's seed rule: a fresh seed was reported only in
    assertion messages, so a failure by exception lost it. `resolve_seed` records the seed on the
    running test and the game's conftest adds it to every failed report (proven with the old
    span bug planted).
  - **The five Minor findings, fixed at the owner's word ("fix those 5 small issues"), each with
    a test that failed first where one could be written:** a knockout puts the laser out within
    the frame, and each zombie reads the lit dots afresh, so no later zombie is lured by it; a
    dead battery shows no pointer, walking or standing (fire held on the move keeps only the
    remote's pose); a switch ends the remote's last shot pose; the planner delivers K after the
    frame's logic, as the engine does (the route came out the same, since K and J never
    overlap); and the laser-pull test no longer pins the neighbor: Dex stands on whichever side
    has room, so its seeds vary the scene (checked on 30 seeds).
  - **The owner's decision (2026-11-15): each kid keeps its weapon into the next stage**, the
    battery refilled. `RunState.weapons` carries each slot's weapon (a run saved before loads
    with the remote), the stage clear stores what each kid holds, and the next stage's kids
    start with it.

## Not in this feature

Battery pickups, sound, a visible beam, other weapons, weapon strengths per monster.
