# Zombies Ain't My Neighbors, Feature 10: The First Sounds — Plan

**Status (2026-11-16):** BUILT, uncommitted, awaiting the owner's ears (approved: "Yes").

**Master plan:** [2026-11-14-zombies-aint-my-neighbors.md](2026-11-14-zombies-aint-my-neighbors.md)
(decisions 3 and 11; the Game TODO "Sound and music", which this begins).

## The owner's ask (2026-11-15)

"I want the sound from the remote firing to sound like warbly thermamin radio waves and the laser
pointer should make a wheeeee kind of oscillation noise. Zombies should make a zombie sound
sometimes when they see something new to chase." The approach, chosen from two ("Yes 1 sounds
good"): baked sounds, the warble built from short pitch swoops.

## Why swoops

A theremin's warble is vibrato: the pitch wobbling several times a second. The engine has none
in a baked sound yet (`vibrato`, `lfos` and `glide` arrive in milestone M4; a sound file using one
is refused). A live sound could wobble its pitch for real, but the engine has four live voices
in all, which four players' lasers would fill. So each warble is a chain of short tones, each
sweeping its pitch with `ease_in_out_sine`, which turns smoothly at each end: the chain traces a
near-vibrato. When M4 lands, the sound files change and the code does not.

## Decisions (Claude's calls inside the owner's; the values are to tune by ear)

| Decision | Value | Why |
|---|---|---|
| Where the sounds live | One sound file, `sounds/sounds.toml` in the game's package (TOML version 1, `[effects.*]`), found by short name (the scenes' default `SOUND_DIRECTORY`) | Decision 3: engine-native files, written by Claude |
| Compiled before play | Every sound is declared in `SOUNDS` on `RosterScene` (the title and the neighborhood, the two scenes the launcher hands the engine, inherit it), so the engine compiles them while the game starts | Decision 11 |
| The remote's zap (`zap`) | About 0.22 s, under the 0.25 s firing rhythm: five swoops of a triangle wave between about 620 and 700 Hz (620, 700, 600, 690, 640, 50 ms each, the last fading out), a quiet noise layer for a radio's hiss, and a fast tremolo (about 18 Hz, depth 0.2) for the waver | "Warbly theremin radio waves"; each shot is its own short sound, so rapid fire never piles up |
| The laser's warm-up (`laser-rise`) | 0.4 s, the warm-up's length: four rising swoops of a sine, each overshooting a little and settling back (about 500 to 1400 Hz in all) | The "wheeee" rising as the laser warms |
| The laser shining (`laser-shine`) | A short wobbling high sine (about 1300 to 1500 Hz, four swoops in 0.5 s), played looping while the dot shines and faded out (60 ms) when it goes out: let go, switched, knocked out, or the battery dead | The "wheeee" holding while it shines |
| Which laser sounds play | The rise starts when a kid starts aiming the laser, and stops (60 ms fade) if it never lights; the shine starts when the dot lights and stops when it goes out. Each kid has its own | Four lasers sound like four lasers |
| A zombie's groan (`groan-1` to `groan-3`) | Three low moans (a sawtooth about 80 to 130 Hz, 0.6 to 0.9 s, low-passed, a little distortion, a slow tremolo), each a different shape: falling, rising then falling, wavering | "A zombie sound" that does not repeat exactly |
| When a zombie groans | When it picks a new target (a kid, a neighbor or a laser dot it was not chasing; its first target counts), it groans one time in three, never within 3 s of its own last groan, and never within 0.5 s of any zombie's groan starting; the moan is picked at random. Chances and picks come from a named stream (`zombies_aint_my_neighbors.zombie-groans`) | "Sometimes"; a crowd must not moan in chorus; replays repeat it |
| What the zombie knows | `Zombie.chase` remembers what it is chasing (the target itself, not only where it heads) and says when that changed this frame (`new_target`) | Its goal was only a place |
| Where sounds sit | Every sound on the `effects` bus, panned by the source's place across the screen (left edge -0.6, right edge 0.6) | Four players can tell whose zap is whose |
| Volumes | The zap 0.35, the laser 0.3, a groan 0.5 (zaps are many; groans rare) | Starting balance, to tune |
| The audio disk proof | Both goldens now compile the game's sounds, so their `SOUND_FOLDERS` entries become `zombies_aint_my_neighbors` (the test's comment says so) | It fails by design until then |

## Tasks

1. **The sound file and its checks** (`sounds/sounds.toml`, a new test file for the sounds): every
   sound compiles; each is the length above; rendered offline, the zap's pitch rises and falls at
   least four times within about 590 to 710 Hz, the rise's pitch ends at least twice where it
   began, the shine wobbles within about 1250 to 1550 Hz, and every groan stays under about
   150 Hz. `SOUNDS` on `RosterScene`.
2. **The zap** (`neighborhood.py`): a kid's shot plays `zap`, panned by the kid's place; one per
   shot, none from a dead battery or a knocked-out kid.
3. **The laser** (`neighborhood.py`, with what the kid already says: `laser_aiming`,
   `laser_lit`): the rise and the shine per kid, each stopped as above; nothing left playing
   after a stage ends, a pause's return, or the kid's knockout.
4. **The groans** (`zombie.py`, `neighborhood.py`): `chase` remembers its target and reports a new
   one; the scene groans under the rules above, with the stream's seed saved per the owner's
   seed rule (a fresh seed plus saved ones).
5. **The goldens, the docs, the master plan**: the disk proof's entries, the goldens replayed
   (re-recorded only if the new stream changes their recorded scene starts), the docs page.

Each task: tests first (sounds checked by what plays, and when, through spies on the compiled
sounds' `play`, and by rendering them offline; nobody can listen in a test), then ruff, the type
checkers and the game's tests with its coverage at 100%; before the commit, the engine's replay,
guard and audio golden tests.

## Review Focus

- A laser switched, let go or put out by a knockout on the very frame it lights: no shine left
  looping.
- Pausing and resuming with a laser shining (the scene's sounds pause with it, per the engine's
  owner rules).
- Four players firing at once: four zaps a quarter-second apart each, never a voice shortage that
  drops a groan.
- A zombie flickering between two targets at equal distance: one groan at most (its 3 s rest).
- A replay repeats every groan (the named stream).

## Rulings while building (Claude's, 2026-11-15; the owner may overturn them)

| Ruling | Why | If wrong |
|---|---|---|
| Swoops join end to end, each a whole number of its own cycles, with no overlap and no fade between them | Measured: overlapping swoops of near pitch beat (the zap's pitch spiked to 733 Hz at a join, a blip you would hear); a swoop that ends on a whole cycle ends where the next begins, so the warble is one unbroken wave | None |
| The zap is a sine, not a triangle | A triangle starts at -1, so even a one-sample gap at a join clicks; a sine starts at 0, and the catalog's theremin is nearly a sine | One field in the rig |
| No tremolo on a sound of several swoops (the zap, two of the groans) | Tremolo restarts with each tone, so it would click at every join; the warble comes from the pitch alone | The waver is pitch only until the engine has vibrato (M4) |
| The sound file is written by `sound_rig.py`, as the sprites' rigs write theirs, and a test keeps it equal | The whole-cycle arithmetic lives in reviewable code, not hand-typed numbers | None |
| Sounds are named by the file's absolute path (`sounds.sound_reference`), in `SOUNDS` and every play | A relative path resolves against the active scene's package and falls back to the working directory where none is active (tests, tools); one string for both keeps every play on the sound compiled at start | None |
| The zap plays where a player's shot fires (the scene's tick), not in `add_zap` | Tests call `add_zap` on scenes never set up | None |
| The groan rules are a pure `GroanTimer` (`groans.py`), checking the rests before rolling | A zombie that may not groan draws nothing from the stream, so the draws stay deterministic, and each rule is tested exactly | None |
| Two measurements in the sound tests corrected to their own descriptions after a first run: the rise compares its first and last windows, groans use 60 ms windows | Quarter medians blurred where the rise began; 20 ms holds under two cycles of an 80 Hz moan. The sounds did not change | None |

## Found while building

- The game's test suite ran over half an hour on 2026-11-15 to 16. Not a hang: no test passes
  60 s, and a profile puts a neighborhood test's time in sprite loading, as fast on the engine
  before feature 9's engine fix as after. The machine's load was 19 to 34 (another session's full
  suite, running two hours, and other services) against 16 workers. The sounds add little: each
  set-up neighborhood compiles its six, and the harness's fresh audio engine per test means once
  per test.

- **The engine's guards found two things before commit** (fixed at the owner's word, "Yes"):
  - A crumbling zombie kept the neighbor it had chased alive after the neighbor was rescued and
    left every group: its new `target` stopped updating while it crumbled
    (`tests/replay/test_removed_sprites_are_freed.py`, the neighborhood golden). Reproduced by a
    script; the zombie now holds its target weakly, so no state of a zombie keeps anything
    alive. `test_a_zombie_keeps_no_target_alive_after_it_leaves_the_yard` failed first in all
    three states (crumbling, grabbing, put away). The test gap: the game's routine skips the
    engine's guards, which caught it. The sweep found no other holder of a sprite that can
    leave its groups.
  - `tests/test_every_recording_replays_inside_an_inner_game.py` lists the games whose
    recordings sound when heard (`PLAYS_SOUNDS`), by game; this game's neighborhood golden
    sounds and its title golden does not, so the list is now by recording, with a check that
    every entry names a recording that exists. Planted: the silent title listed fails its case,
    and a stale entry fails the check.

## What only listening can judge

How it sounds. The tests prove the shape (the pitch wavers, rises, stays low); the owner hears
whether it is a theremin, a "wheeee" and a zombie, and the values above are where to tune.

## Not in this feature

The other sounds in the Game TODO (TV spawns and hits, rescues and losses, knockouts, the gate,
the stage clear, the game over) and the score; real vibrato (engine M4).
