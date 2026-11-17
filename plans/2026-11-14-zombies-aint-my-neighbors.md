# Zombies Ain't My Neighbors — Master Plan

**Status (2026-11-14):** research done; design not started. Branch
`feature/zombies-aint-my-neighbors`, from `origin/main` at 333fcc0d (#208), worktree
`glitchygames-zombies-aint-my-neighbors`.

**Goal:** a new game member in `src/games/`: a top-down, four-player co-op horror-comedy
run-and-gun in the genre of LucasArts' *Zombies Ate My Neighbors* (1993), built on the
glitchygames engine. It follows the package recipe in docs/architecture/game_packages.md
(its own code, tests and golden replay).

This file is the master plan. It holds the research, the decisions and the priorities, and it
will point to one detailed plan for each feature as each one is designed.

## Why

The owner and a friend are competing. Each is making a game in this genre, without seeing the
other's, each with their own tools. The owner's own challenge: **every sprite, sound
effect and piece of music must be made in formats the engine already supports**. No imported
PNGs, WAVs or tracker files. The game must be its own thing, not a copy.

## Decisions

| # | Date | Decision | By |
|---|------|----------|----|
| 1 | 2026-11-14 | Build a game in this genre, on this engine, called "Zombies Ain't My Neighbors" | owner |
| 2 | 2026-11-14 | Not a copy: our own heroes, villain, sprites, music, stage layouts and stage names (see Originality) | owner |
| 3 | 2026-11-14 | All assets in engine-native formats only: sprite TOML (ANIMATION_README.md), sound files as TOML version 1 (docs/architecture/sound.md), instruments from the catalog. Claude writes the sprites, sounds and music | owner |
| 4 | 2026-11-14 | Keyboard and gamepad support | owner |
| 5 | 2026-11-14 | Co-op multiplayer from the start, extended to 4 players (the controller system already supports 4 controllers at once) | owner |
| 6 | 2026-11-14 | A title screen with a recorded attract-mode demo (bundled demos) | owner |
| 7 | 2026-11-14 | Saved high scores and progress instead of passwords | owner |
| 8 | 2026-11-14 | No deadline and no formal rules: a blind show-and-tell where the owner and the friend judge each other. Compete on new ideas, number of platforms, keyboard and controller support, and player count | owner |
| 9 | 2026-11-14 | The concept below is accepted ("Love the theme, let's do it"). The kids wear **VR headsets**, not 3D glasses | owner |
| 10 | 2026-11-14 | Title screen: **"Press Start" blinks for each of the 4 player slots, each slot in its own colour**, in the style of 4-player arcade cabinets, so it's obvious at once that 4 players are supported | owner |
| 11 | 2026-11-14 | Performance: do all heavy work before play. Compile sounds and load sprites in `setup()`, let the engine's caches work, and add game-level caches where the engine has none | owner |
| 12 | 2026-11-14 | **No engine code changes.** Engine bugs, features and refactors found along the way are tracked (see Engine wishlist), not fixed | owner |
| 13 | 2026-11-14 | The game's browser page gets a two-way flat toggle with icons: keyboard (or keyboard and mouse) on one side, gamepad on the other. Switching to gamepad brings up the browser's device dialog | owner |
| 14 | 2026-11-14 | Narration built from the engine's own synthesized waves: track the gaps as roadmap tasks (plans/future-features.md #90), don't build them yet | owner |
| 15 | 2026-11-14 | A cinematic intro: sprite vignettes of the sleepover, then monsters coming out of the TV screen. Controllers vibrate at that moment when playing in controller mode | owner |

| 16 | 2026-11-14 | The boundary: **all game code lives in `src/games/zombies-aint-my-neighbors/`**. It may use anything in the engine, and may hold any support code it needs, but must not refactor the engine for it; things that belong in the engine move there later. The owner's reasoning: the limit keeps workarounds from becoming convoluted. One exception, granted the same day: **the keyboard/gamepad toggle goes on the shared browser page** (`browser/index.html` and its scripts), so every game's page gets it | owner |

| 18 | 2026-11-14 | **A character BOM (bill of materials) before any art**: every sprite character gets its full frame and animation list written and audited before any art is drawn: each character's animations (idle, walk in each facing, attack, hurt, death, and anything special), the frames in each, their timing and loop rule, size, palette and hitbox. The art feature starts only after the owner has seen that audit | owner |
| 19 | 2026-11-14 | **TV spawners**: monsters (Lawn Zombies, Rabbit-Ears) come out of TV sets left on around the neighborhood, and players destroy the TVs to stop them, through stages of destruction (Claude's proposal: intact, cracked, smashed and sparking, destroyed and smoking; the spawn rate halves at each stage and stops when destroyed) | owner (stages: Claude's proposal) |
| 17 | 2026-11-14 | The registration files outside the game folder may be edited (root config, test tables, `scripts/`, the browser build). **`src/glitchygames/` is off-limits**, with two approved exceptions: the `MEMBER_LAYERS` line, and the small fix to `collision/detection.py`'s margin (Engine wishlist #11), both on this branch ("everything goes into this branch") | owner |

## Open questions (the owner's)

1. **Registering the game (partly answered by decision 17).** The one registration line inside
   `src/glitchygames/` is still unresolved: see the conflict below. A new game becomes a workspace member only through edits outside
   its folder (docs/architecture/game_packages.md, steps 2 to 5): the root `pyproject.toml`,
   `pyrightconfig.json`, `noxfile.py`, `wily.cfg`, `zensical.yml`, `uv.lock`, hand-written test
   tables (`tests/workspace_expectations.py`, `tests/test_logical_names.py`,
   `tests/replay/...`), the golden scripts in `scripts/`, the browser build's `GAMES` entry, and
   **one line of engine source**: the package in `MEMBER_LAYERS`
   (`src/glitchygames/logical_names.py`), which gives recordings their `games.` names and is
   checked against the workspace. Without them the game can't be run with `uv run`, tested,
   replayed or built for the browser. Claude proposes allowing exactly these registration lines,
   with no change to engine behaviour; every game added so far needed the same lines.
2. **The title.** "Zombies Ain't My Neighbors" is one word away from a title that is still owned.
   It doesn't matter for a private build, but it does for shipping, the website or a browser
   bundle. The owner decides whether to keep it or pick a name further from the original.

## Concept (accepted 2026-11-14)

A **late-night creature-feature marathon**. Four kids at a sleepover (one per player) are
watching a cancelled horror-host show when its monsters climb out of the TV and spread through
the neighborhood. Each stage is a "feature presentation" with a B-movie title card. Changing
stages is a channel change through CRT static, using the engine's CRT power-on sequence.
The villain is the show's washed-up host, original to this game.

Showcase features the engine already has that fit this theme:
- **Instant replay as a VHS rewind** of a stage's best moment (`instant_replay.py`).
- **Rumble and screen shake** on hits and explosions (`effects/shake.py`, `input/rumble.py`).
- **The CRT power-on** as the game's opening "TV switching on".
- **Exact replays**, so the attract demo is real recorded play.

Not suitable: `audio/tts.py` voices only on macOS (`say`) and writes audio at run time, which
breaks platform breadth and the native-formats rule. Narration from the engine's own waves is
tracked as roadmap #90 and not built for this game yet.

### The intro (decision 15)

1. Vignettes: shots of the sleepover framed in a dark oval, built from sprites. The four kids in
   sleeping bags in front of the TV, VR headsets on, snacks and a lamp, the horror host on screen.
2. The TV flickers. Monsters push out through the screen; the screen shakes, and in controller
   mode every connected controller rumbles.
3. Cut to the title, with four "Press Start" slots blinking.

Any key or button skips it, as the CRT power-on does.

### Controller mode on the browser page (decision 13): findings to verify in a spike

- Bitmappy has no gamepad or WebHID code. The browser HID work is in PyMasterHub
  (`PyMasterHub/examples/webhid/index.html`, `src/pymasterhub/transport/webhid_backend.py`),
  which talks to MasterHub modules, not gamepads. Use it as the reference.
- The device dialog is WebHID (`navigator.hid.requestDevice`), which only Chromium browsers
  have (Chrome, Edge). Firefox and Safari don't. Standard gamepads reach a page through the
  Gamepad API, which needs no dialog, only a button press.
- Unverified: whether SDL in the browser (pygame-ce under Pyodide) passes Gamepad API pads to
  the engine, and whether rumble works there (`input/rumble.py` drives SDL rumble; the
  browser's own route is the Gamepad API's `vibrationActuator`).
- Proposal: the gamepad side asks for a button press (works everywhere) and, on Chromium, also
  opens the WebHID dialog. A spike settles what the engine sees in each case.

**Platforms (owner, 2026-11-14):** it will certainly be played **in the browser**, and also on
other platforms, with **Raspberry Pi as the low end**. The targets are the browser
(`nox -s browser`), macOS, Linux, Windows and Raspberry Pi. Consequences:
- The Pi and the browser set the performance budget: frame time with four players and a stage
  full of monsters, and the time to compile synthesized sounds and music when a scene loads
  (every sound is built in `setup()`, so a long layered music loop costs load time). Measure on
  the Pi early, not at the end.
- Four gamepads in the browser need checking: browsers expose controllers through the Gamepad
  API, not SDL. On-screen touch buttons (`browser/touch_controls.js`) could give a phone a
  player slot.
- The browser's shared pause and game-over screens take Esc and Space, so the game's own
  controls must avoid those keys (CLAUDE.md, Browser).

## What the engine gives the assets today (recon, 2026-11-14)

- **Sprites:** TOML character-to-colour maps with magenta as the transparency key, and
  `[[animation]]` sections with per-frame `pixels`. House style (Brave Adventurer's
  `player.toml`): about 20x28 characters, scaled 2x at runtime, a 10 to 15 colour palette, and
  a hitbox in TOML. Bitmappy's library (`src/apps/bitmappy/src/bitmappy/resources/sprites/`, 71
  files) already has genre-useful pieces to use as style references: `hedge`, `grave`,
  `brick_wall*`, `dead_tree`, `key`, `cross`, `bomb`, `flame`, `ghosty`, `small_heart`, doors.
- **Sound effects:** sound files with instruments (wave, envelope, profile such as `chip`) and
  `notes = "B5:0.06 E6:0.18"` sequences. Mr. Muncher's `sounds.py` is a model of a themed effects
  set.
- **Music:** the catalog has the B-movie kit: `theremin`, `ondes martenot`, `harpsichord`,
  `timpani`, `tubular bells`, `celesta`, `glass harmonica`, `saw`. There is **no sequencer yet**
  (roadmap #64, `[sequences]` in sound files, is design only). Music must be layered looping
  sounds (bass, lead, drums started together on the `music` bus) or a single mixed recipe.
  Check before the music plan: the `music` bus reserves only two channels, so more than two
  layers can be stolen by a storm of effects, and separately looping layers can drift apart.
- **Input:** `Scene.input_devices` and the controller system (CONTROLLER_CONTROLS_README.md)
  cover keyboard and gamepads; not yet checked for two players in one game.

## Research: the original game

*Zombies Ate My Neighbors*, LucasArts, published by Konami, 1993, SNES and Genesis. Credits:
designer Mike Ebert, programmer Dean Sharpe, artists Collette Michaud, Leonard Robel and
Sean Turner, music by Joe McDermott and George Sanger. It was built on the SNES first and ported
to the Genesis about halfway through development. Its engine was reused for *Ghoul Patrol*,
*Metal Warriors* and *Big Sky Trooper*. It sold modestly and became a cult classic; reviewers
praised the humour, the two-player mode, the graphics and the music.

### Core loop

- Top-down run-and-gun, played by one player or by two in co-op on a shared screen.
- Each stage has up to **10 victims** ("neighbors"). You save one by touching it. A monster that
  touches one first kills it.
- The stage ends when every victim is either saved or dead, and an exit door then opens.
  **At least one victim must be saved** to go on.
- **Dead victims are gone for the rest of the run**, unless you earn a bonus victim by scoring
  points. Points also earn extra lives.
- **Game over** comes when every life is lost, or when every victim is dead.
- So the real thing you manage is a pool of victims that only shrinks over the whole run.

### Victims

Each type is worth different points: barbecue dad, cheerleaders, babies, a teacher, tourists,
archaeologists, soldiers and a dog. Some victims change during a stage: on night stages,
tourists turn into werewolves and count as killed.

### Weapons are matched to enemies

You carry many weapons, each with limited ammo, and switch between them. Each one is strong
against certain enemies:

- a squirt gun as the basic weapon
- an Uzi water gun, a bazooka, a weed-whacker, soda-can grenades, ice pops, tomatoes, plates,
  silverware, crucifixes, a fire extinguisher and a Martian bubble gun
- a flamethrower, in the SNES version only

Examples: silverware kills a werewolf in one hit, and crucifixes work best on vampires. Learning
which weapon beats which monster is a large part of the skill.

### Items

These include keys for locked doors, medkits, a speed potion, a decoy, and a monster potion that
turns the player into a strong monster for a while. You find them lying around, in trash cans
and cupboards, and behind locked doors. The bazooka breaks through some walls, which opens
shortcuts.

### Enemies

They parody 1950s B-movies and slasher films (*Friday the 13th*, *The Texas Chain Saw
Massacre*): zombies, mummies, werewolves, vampires, chainsaw maniacs, giant ants, spiders, a
giant baby, evil dolls, Martians with UFOs, pod people, blobs, giant worms and squidmen. Many of
them break hedges and walls, so the map changes as you play.

### Structure

- 48 stages, 7 of them optional bonus stages (Wikipedia's count; other sources give other
  numbers, not checked). Settings include suburbs, malls, pyramids and castles.
- Password progress instead of a battery save. The team wanted a battery save but couldn't
  afford one.
- A **victim radar** shows where the remaining victims are.
- Stage titles pun on horror-movie titles, and there are secret stages.

### Art and audio

- Bright, readable cartoon pixel art on a darker, slightly sickly palette, which reviewers
  called "colorful and detailed" and "creepy".
- A three-quarter top-down view, small player sprites with exaggerated animation, and a campy
  horror tone.
- On SNES, Nintendo of America had the blood changed to purple ooze. In Europe the game was
  renamed *Zombies*, and lumberjacks with axes replaced the chainsaw maniacs.
- The music parodies over-the-top horror-film scores.

Not checked against a primary source: the speed potion, the decoy and the radar come from memory
and the sources below, not from the manual. Check them before a feature plan depends on them.

## Mechanics to build, in proposed priority order

The order is a proposal and depends on open question 1.

1. **A shrinking victim pool across the run**, with a pass or fail rule per stage. This is the
   genre's main hook.
2. **Weapons strong or weak against specific enemy types**, with ammo and weapon switching.
3. **Destructible terrain:** hedges and walls that monsters break, and bazooka shortcuts; and
   **TV spawners** players destroy through stages of destruction (decision 19).
4. **The victim radar**, plus victims who change during a stage (like the tourist turning into
   a werewolf).
5. **Co-op for up to four players on one screen** (decision 5), with a shared camera.
6. **Stages that each introduce one new monster or idea**, plus bonus and secret stages.
7. **Progress across sessions:** saves through `glitchygames.state.open_saves` rather than
   passwords (the original's password system was a cost limit, not a design goal).

## Engine notes to check during design

Not yet investigated. The first design step is to read `src/games/brave-adventurer` and
docs/architecture/game_packages.md to find:

- whether a top-down tile map and collision exist, or must be built (and whether that work
  belongs in the engine, which must stay genre-neutral, or in the game)
- whether the camera can follow up to four players at once (`Scene.camera_target()`)
- how four players' input reaches a game (`Scene.input_devices`, CONTROLLER_CONTROLS_README.md;
  answered for the title by feature plan 1)
- the replay rules a new game must meet: named random streams for spawns and AI, golden replay,
  controls listed in `tests/replay/golden_replay_controls.py`, workspace expectations in
  `tests/workspace_expectations.py`
- whether the sound engine and instrument catalog cover the B-movie score and effects

## Originality

The genre and these mechanics are ours to use. Everything recognisable from the original is not.
That covers its heroes, its villain, its sprites, its music, its stage layouts and its stage
names. Our cast, villain, monster designs, art and stage names will be new. Monster types common
to the genre (zombies, mummies, werewolves) are fine; the original's specific characters and
designs are not.

## Game TODOs

- [x] **Hide the 0.32 s hitch when a stage is built** (found 2026-11-15, feature plan 7): done
  by feature plan 9: the card builds the stage's sprites ahead, a sprite a frame, and the stage
  is built in 2 ms (was 349 ms).
- [x] **The pointer over a kid ended the game** (the owner, 2026-11-15:
  `'Kid' object has no attribute 'on_mouse_focus_event'`): fixed in the engine, as the owner
  directed. `AnimatedSprite` stood outside `RootSprite`, so it had no mouse or keyboard handlers;
  every game's animated sprites (Brave Adventurer's player too) crashed under the pointer.
  `RootSprite` now carries both protocols' silent handlers (moved up from `Sprite`),
  `AnimatedSprite` stands on it, and the mouse manager calls only handlers a sprite has (a
  replay's ghost has none). Tests: `test_moving_the_mouse_over_a_kid_does_not_crash` (the game),
  the engine's mouse and animated-sprite tests, and `tests/test_sprite_classes_are_root_sprites.py`
  (no sprite class stands on pygame's sprites but `RootSprite` and `GhostSprite`). The test gap:
  BUGS.md #225 met this error in 2026-10 but only hid the test windows, so no test moved a
  pointer over a sprite in a live scene.
- [x] **The game's coverage back to 100%** (found 2026-11-15 by the full suite: 99.96%, a push
  blocker): Features 6 to 8 were tested with `--no-cov`. Eight tests cover the reachable gaps
  (game over before setup, set up twice and a stranger's start; START on the joystick layer; a TV
  destroyed by a pad that has gone; a TV broken mid-spawn; a dying zombie's animation; a gone
  zap); dead or duplicate code behind the unreachable ones was removed at the owner's word (no
  pragmas): the door's glow of strength 0, the kid's and the neighbor's redundant guards, a
  duplicate touchable check, an always-true zap check, and the game over's and the effect
  order's None checks, now properties that fail loudly (`GameOverScene.screen_picture`,
  `Neighbor.playing_effect`). The game's test routine now measures its coverage (memory).
- [ ] **Sound and music** (begun by feature plan 10: the zap, the laser, the groans; the rest
  below still to come) (the owner, 2026-11-15: "We do need sounds in the game though, we
  just haven't gotten there yet"): effects for the game's actions (zaps, TV spawns and hits,
  rescues and losses, knockouts, the laser, the gate, the stage clear, the game over) and a
  B-movie score as layered loops, all engine-native (decisions 3 and 11: sound files version 1,
  the instrument catalog, compiled in `setup()`); every game moved onto the sound library with
  live instruments in #213, so build on that. (Feature plan 10 set this game's two
  `SOUND_FOLDERS` entries in `tests/audio/test_audio_engine_goldens.py` to its folder.)
- [ ] **A game cannot declare an engine context slot yet** (found 2026-11-15, feature plan 9):
  `tests/test_engine_context_source_guards.py` requires an isolation check for every slot,
  members' included, in the engine's `ISOLATION_CHECKS`, but engine tests may never import a
  member (`tests/test_workspace_config.py`). Any game wanting per-game state that outlives a
  scene meets this. Fix in the shared guards (members keep their checks in their own tests,
  collected by the guard) when a game needs a slot; feature plan 9 passes its kit from scene to
  scene instead. The owner's call.
- [x] **A laser pointer weapon (the owner, 2026-11-15):** planned as feature plan 8.
  Asked: "when you shine the laser pointer
  somewhere, the zombies chase the laser pointer, but its batteries run out quickly." A lure
  weapon beside the Channel Changer: a dot that zombies chase instead of kids and neighbors,
  on a battery that drains fast. Needs its own feature plan (weapon switching and the battery
  come with it). Asked while Feature 7 was being built; taken up after it.
- [ ] **Test controller rumble in the browser build** once the game works locally (the owner,
  2026-11-14). The engine's rumble (`input/rumble.py`) goes through SDL, and nobody has checked
  whether SDL under Pyodide can rumble a pad. If it can't, record that here and in Engine
  wishlist #4, and fix it later. The likely fix is browser-only code in the game folder that
  calls the Gamepad API's `vibrationActuator`, since `src/glitchygames/` is off-limits. The
  intro's rumble (decision 15) depends on the answer, so check it before the intro is built.

## Engine wishlist (decision 12)

Engine bugs, features and refactors found while building the game. Nothing here is changed in
the engine on this branch. Bugs also go into BUGS.md and features into plans/future-features.md
when filed; this table links to them.

| # | Found | Kind | What | Filed |
|---|-------|------|------|-------|
| 1 | 2026-11-14 | feature | Narration from the engine's own waves (speech synthesis, text to phonemes, a sound-file form) | future-features #90 |
| 2 | 2026-11-14 | feature | A per-game hook for the browser page (extra page content and scripts). Less pressing now that the input toggle is allowed on the shared page (decision 16) | not yet |
| 3 | 2026-11-14 | feature | A music sequencer (already roadmap #64, design only); this game works around it with layered looping sounds | future-features #64 |
| 4 | 2026-11-14 | to verify | Gamepads and rumble in the browser build (SDL under Pyodide) | not yet |
| 5 | 2026-11-14 | refactor | `MEMBER_LAYERS` in `src/glitchygames/logical_names.py` is a hand-kept copy of the workspace, so adding any game means editing engine source. The engine could derive a package's layer from the installed member's location or its distribution metadata, so new games never touch the engine | not yet |
| 6 | 2026-11-14 | feature | Scripted sessions (goldens, bundled demos) can't plug a device in mid-session: `ScriptedSessionOptions` has no `plugged_in_at_start=False` (only `install_stand_in_devices` does, `src/glitchygames/input/stand_in_devices.py:251`). Hot-plug joins are tested in unit tests only | not yet |
| 9 | 2026-11-14 | feature | In `--input-mode joystick` a pad's START is bound as raw joystick button `CONTROLLER_BUTTON_START` (6), which is another button on many pads (Back or View on Xbox layouts); the engine's `gamepad_choice.py` does the same (`action_map.py` documents it; BUGS.md #178.26). A per-device lookup of START's raw index would fix every game | not yet |
| 11 | 2026-11-14 | bug (engine) | `collision.detection.get_collision_rect_with_margin` shrinks a rect by twice the margin and pygame-ce normalises the negative size, so a box narrower than twice the margin becomes a hittable box (`Rect(10, 10, 0, 0).inflate(-4, -4)` gives `Rect(12, 12, -4, -4)`). Found by the character BOM's audit 2 | **FIXED on this branch** (owner's permission, 2026-11-14: "as long as it remains a small fix"): each side shrinks to zero at most, keeping the centre; regression tests in `tests/collision/test_collision.py` |
| 10 | 2026-11-14 | bug (engine) | The engine's `PauseScene` leaves raw device events (JOYDEVICEREMOVED and the like) unhandled, so unplugging a pad while any game is paused raises under `--no-unhandled-events` (off by default, so players only see a log line at most). Found by this game's pause-unplug test, which runs that path without the flag | not yet |
| 8 | 2026-11-14 | bug (repo tooling) | `scripts/build_browser_bundle.py` `render_page` puts a game's title into the page's `<title>` unescaped (the index page escapes it). Harmless for this title, but a title with `&` or `<` would make invalid HTML | not yet |
| 12 | 2026-11-15 | feature | The engine keeps no cache of loaded sprite files: every `AnimatedSprite(filename=...)` reads and parses its TOML and rebuilds its frame surfaces, so a game that creates sprites mid-play drops frames (a Lawn Zombie: 27 to 41 ms). A shared, read-only cache of parsed files (frames and surfaces), keyed by path, would let every game spawn freely. This game works around it with pools (feature plan 6) | not yet |
| 7 | 2026-11-14 | to consider | `tests/replay/test_golden_replays.py` assumes a game is one scene (header game == gameplay scene; the recording ends in it). A title in front of gameplay has to be left out of the golden. The tests could accept a start scene that differs from the gameplay scene | not yet |

## Feature plans

Each feature gets its own plan in `plans/`, linked here and linking back to this file.

1. [Registration and the 4-player title](2026-11-14-zombies-aint-my-neighbors-1-title-and-registration.md):
   BUILT (2026-11-14), committed. The title with four blinking
   slots, joining from the keyboard or pads, the feature card, the golden replay, the browser
   bundle and the docs page (`docs/games/zombies_aint_my_neighbors.md`).
2. [Character BOM](2026-11-14-zombies-aint-my-neighbors-2-character-bom.md) (decision 18): every
   sprite character's frames and animations, audited before any art. SIGNED OFF by the owner
   (2026-11-14, draft 2.1).
3. [Dex, the first kid on the shared rig](2026-11-14-zombies-aint-my-neighbors-3-dex.md): BUILT
   at 32x48 SNES-era detail: Dex approved by the owner, then all four kids written.
4. [The kids walk the neighborhood](2026-11-14-zombies-aint-my-neighbors-4-walking.md): BUILT,
   committed locally (bfa4544c).
5. [Zombies come out of the TVs](2026-11-14-zombies-aint-my-neighbors-5-zombies.md): BUILT,
   committed. Four TVs spawn Lawn Zombies (6 to 9 s waits, 3 per
   TV, 10 in all); zombies chase and knock kids out; kids recover and blink. The props BOM is
   started ([2026-11-14-zombies-aint-my-neighbors-props-bom.md](2026-11-14-zombies-aint-my-neighbors-props-bom.md)).
6. [The Channel Changer](2026-11-15-zombies-aint-my-neighbors-6-channel-changer.md): BUILT,
   committed. The first weapon, a TV remote with unlimited zaps (owner,
   2026-11-15); zombies crumble in one zap; TVs crack, smash and die in 3 zaps a stage.
7. [Neighbors, lives and stages](2026-11-15-zombies-aint-my-neighbors-7-neighbors-and-lives.md):
   BUILT, committed. Neighbors to save, 3 lives each, an exit door at a
   stage's end, the next stage with only the neighbors saved (owner, 2026-11-15), and game over.
8. [The laser pointer](2026-11-15-zombies-aint-my-neighbors-8-laser-pointer.md): BUILT,
   committed. A second weapon, a lure: zombies chase its dot; its battery
   gives 3 s of shine and recharges by itself (owner, 2026-11-15). K or Y switches weapons.
9. [A sprite kit built ahead](2026-11-15-zombies-aint-my-neighbors-9-sprite-kit.md): BUILT,
   committed (82074978). The stage card builds the coming stage's sprites into a kit, a sprite a frame,
   and hands it to the stage, so no stage pauses to load (the owner's option 2, 2026-11-15).
10. [The first sounds](2026-11-15-zombies-aint-my-neighbors-10-first-sounds.md): BUILT,
   uncommitted. The remote's warbly theremin zap, the laser's "wheeee", and
   zombies groaning sometimes at a new target (the owner's ask, 2026-11-15), as baked sounds.

## Sources

- [Wikipedia: Zombies Ate My Neighbors](https://en.wikipedia.org/wiki/Zombies_Ate_My_Neighbors)
- [MobyGames](https://www.mobygames.com/game/6966/)
- [The Cutting Room Floor (SNES)](https://new.tcrf.net/Zombies_Ate_My_Neighbors_(SNES))
- [Hardcore Gaming 101](https://www.hardcoregaming101.net/zombies/)
- [Giant Bomb](https://www.giantbomb.com/wd/3030-16116)
