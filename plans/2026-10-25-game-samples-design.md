# Game Samples: Every Game Plays Itself (design)

Status: DRAFT for the user's review (2026-10-25). Nothing is built from it until it is approved; a
plan follows. Decisions marked **(user)** are the user's, from the 2026-10-25 conversation; the rest
are proposals, marked **(proposal)**, for the user to accept or change.

## 1. Intent

Every GlitchyGames game gets, for free, recorded runs of itself that the engine can replay and
check exactly: so a change that alters how any game plays or draws is caught, on the developer's
machine before a push and on an end user's installed copy. The game developer writes nothing
**(user)**: the engine harnesses the game through what it already knows (its scenes, its declared
controls, its sprites). It is a new engine feature: running games inside the engine's own players
**(user)**.

Anti-goals: a developer having to write a script, register a hook or choose a folder to get it; a
check that passes because it looked at too little; a runner that leaks memory or state between
games.

## 2. The two kinds of file

| | What it is | ELI5 |
|---|---|---|
| **Recording** | Input: per-frame time, events, input changes, the random streams' states, each scene's logical name (today's "recording" format, version 3) | The tape of button presses |
| **Trace** | Expected output (the expected playback result): every sprite's world rect, visibility and animation state, per frame (today's "trace" format), produced by playing back exactly that recording | Where everything was on screen, frame by frame |

Today's golden replays and demos are both recordings (one type, two roles); today's golden traces
are traces, but recorded from a separate input script, so the two can drift. Here every trace is
made by playing back its own recording **(proposal)**, so they cannot. A trace is named for who
played its recording: a human trace, an ai trace, a cpu trace **(user)**.

## 3. Three kinds, named by who played **(user)**

| Kind | Played by | Rank | Notes |
|---|---|---|---|
| **human** | A human, playing normally in record mode | Highest | Precise and hand-tuned: every action is assumed deliberate |
| **ai** | A model that reads the game state and chooses actions ("dumb mode++") | Middle | Smarter than random; may be taught by human recordings (section 9) |
| **cpu** | The engine's explorer: seeded, curious, random within the game's controls | Baseline | Always available, needs nothing from the developer |

The three are one feature **(user)**: three players behind one runner, one recorder, one trace
format and one checker. A recording's header records who played it (`player: human | ai | cpu`),
so its kind is a fact, not a convention; its trace inherits it. It is fine that cpu does not play
well **(user)**: it finds controls and scenes; human recordings reach the deep states.

## 4. Names **(proposal)**

Nothing is unmarked: every file names its target and kind **(user: human, ai, cpu)**.

```
<package>/samples/
  <target>.human.recording.jsonl.gz      the inputs a person played
  <target>.human.trace.jsonl.gz          the expected result of playing them back
  <target>.ai.recording.jsonl.gz         (when a model has played it)
  <target>.ai.trace.jsonl.gz
  <target>.cpu.recording.jsonl.gz        (always: the engine's explorer)
  <target>.cpu.trace.jsonl.gz
  demos/<name>.recording.jsonl.gz        (a recording shown, not only checked)
```

A target is one thing a person can start: a game, or a game inside a wrapper. Brave Adventurer has
three: `brave-adventurer` (the launcher), `brave-adventurer-classic`, `brave-adventurer-papyrus`
**(user)**, each with its own samples; so will every game inside a future arcade **(user)**.

## 5. Who owns what (the layers)

From an adversarial pass over the first sketch (2026-10-25), which had the engine reading members'
build configuration, the samples stored as test data, the engine holding a table of this
repository's games, a scene owning game composition, and repository history inside the engine.

| Owner | Owns |
|---|---|
| **Each game package** | Its identity (a `Game` descriptor: target name, starting scene, the games it wraps) and its data: `<package>/samples/` is package data, read with `importlib.resources`, identical in an editable checkout and an installed wheel. Tests read samples; they own none. |
| **The engine** | The protocol and the mechanics, knowing no game by name: discovery of installed games through the `glitchygames.games` entry-point group (a game registers itself in its own `pyproject.toml`); the players (human recorder, model, explorer); the runner; the checker; the options; the seed rules. |
| **Quality tooling** (`scripts/`) | Measurement and history: the run ledger, keyed by sample identity (`<target>:<kind>:<role>`), not by file path, so moving a file needs no rename table. `RECORDING_PATH_RENAMES` leaves the engine. |

Discovery **(proposal)**:

```toml
# a game's own pyproject.toml
[project.entry-points."glitchygames.games"]
paddleslap = "paddleslap:GAME"
```

```python
GAME = Game(target='brave-adventurer', scene=TitleScene, wraps=(CLASSIC, PAPYRUS))
```

A wrapper's samples are its own plus every wrapped game's, walked recursively; asking the wrapper
runs all of them, asking one wrapped game runs only its own **(user)**. `MEMBER_LAYERS` stops being
the engine's game list (logical names derive from the registered games) **(proposal)**.

Committing samples is the developer's one action **(user)**: the engine writes them into the game's
`samples/`; a developer who does not want them can `.gitignore` it; users can still measure on their
own systems and report bugs **(user)**.

## 6. The explorer (cpu)

**What it presses**: the game's declared controls (its ActionMaps' actions, with their keys and
buttons) and the engine's own keys, holding some, waiting between, in seeded sequences. Quit is held
back until the end. A game that reads raw input without declaring controls gets a weaker explorer:
a known, documented limitation, not worked around **(user)**.

**What steers it** is separate from **what is checked** (an adversarial audit, 2026-10-25):

- *Checked*: everything the trace records, every frame: positions, visibility, animation
  state. Idle animations, walk cycles and blinking are all verified.
- *Steering*: a coarse per-frame state signature: the scene, which sprites exist, each sprite's
  world position rounded, its animation state *name* (not frame index), visibility, and any score
  or lives a scene exposes. From it:
  - idle = the signature cycling with a short period (an idle animation is not progress);
  - stuck = a walk animation playing while the world position holds (that action is blocked here:
    try another);
  - progress = a signature not seen before; the explorer steers toward unseen signatures.
- Doing nothing is one of its moves: in many games waiting is progress (spawns, timers).
- Signals rejected and why: raw x/y (misses animation in place, camera scroll, HUD text), any
  sprite change (idle animations never look still), pixels (particles and timers make every frame
  new; costly).

**How long** **(user)**: about 60 seconds of game time per target, stopping early once nothing new
has appeared for a while.

**Coverage report**: which controls it pressed and which scenes it reached, so the gaps show.

## 7. The human recorder (human)

Play the game normally with recording on (`--record-sample`); the engine saves a human recording
and makes its trace by playing it back. High fidelity: the human reaches what cpu cannot
**(user)**. The existing hand-authored scripted runs (Brave Adventurer's, Drawing Fire's, Clockwork
Keep's input scripts, Mr. Muncher's autopilot) are precise authored input: they are kept as human,
recorded once more under the new names **(proposal; user to confirm)**.

## 8. The options (every game, from the engine) **(proposal)**

| Option | Does |
|---|---|
| `--list-games` | This target and every game it wraps (recursively); a single game lists itself **(user)** |
| `--list-samples` | Its samples, by kind (human, ai, cpu) and role |
| `--run-samples` | Plays back every recording strictly and checks its trace; exit status is pass/fail |
| `--run-demos` | Plays the demos, watched |
| `--demo NAME` | One demo |
| `--record-sample` | Human recording mode |
| `--explore` | Runs the explorer and writes the cpu recording and trace |
| `--random-seed N` / `--random-seed random` | The engine owns the seed **(user)**; each target's default is a fixed seed the engine derives from its target name, so runs repeat with nothing set **(user)** |
| `--no-samples` (and a project setting) | The disable switch: on by default, off for developers who want it off **(user)** |

## 9. Human recordings teach the ai player (a note for later) **(user)**

Human recordings are rated highest. A model can compare a human run with the game state frame by
frame and ask why: "an event happened here in the human game: the player jumped with a scarab two tiles
ahead; why?". Because human recordings are precise and tuned by hand, every action is assumed to have a
reason (no double-jumps by accident). The answers teach the ai player what matters in the game.

## 10. Running many samples in one process

A wrapper runs several targets, an arcade dozens: no process per sample, no state between them.

1. Once per process: pygame and the display are initialised.
2. Per sample, setup: the engine's random streams, input state and clock reset; a fresh engine and
   scene from the recording's header.
3. Run: the recording is streamed, never decoded whole (today's are about 200 MB decoded); each
   frame is compared as it goes.
4. Teardown, in a `finally` (a failing sample cannot poison the next): the scene ends, sprite groups
   empty, audio channels stop, scene-owned surfaces and fonts are released, the event queue is
   cleared, references dropped, a garbage collection runs.
5. Leak guard: weak references to each sample's engine and scene must be dead after teardown; a
   test runs one sample several times and checks the weak references and that memory (tracemalloc)
   stays flat.

## 11. On every push **(user)**

A pre-push hook runs every installed target's samples through the runner, in process; any
difference blocks the push and names the target, kind and frame. The commit-time measurement
(`replay-metrics`) stays: it records performance; this verifies behaviour. Expected time: well under
a minute (today's replays measure in about 12 s); measured when built.

A guard test walks `--list-games` and fails if any target lacks a cpu recording and trace (always
possible) or if any recording lacks its trace. Today's gaps (no trace for Mr. Muncher, Drawing Fire, the
Brave Adventurer launcher) are filled.

## 12. Known limits

- cpu plays badly by design; deep states need a human (or ai) recording.
- Raw-input games get a weaker explorer (documented per game in its samples).
- Committed samples grow the repository and each wheel (today about 1 MB compressed in all).

## 13. Open questions for the user

1. Names: settled (the user, 2026-10-25): recording and trace; human, ai, cpu.
2. The existing hand-authored scripted runs: human (section 7)?
3. The ai player's model: which model and where it runs (local, an API), and is ai in the first plan
   or after human and cpu?
4. The order: build cpu and human (with the runner, the options, discovery and the layout) first,
   ai after?
