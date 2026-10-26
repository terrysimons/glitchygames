# Game Samples: Every Game Plays Itself (design)

Status: DRAFT for the user's review (2026-10-25); the four questions answered (2026-10-26). Nothing is built from it until it is approved; a
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
| **Stimulus** | Input (what goes in): per-frame time, events, input changes, the random streams' states, each scene's logical name (today's "recording" format, version 3) | The tape of button presses |
| **Response** | Expected output (what playing the stimulus back must produce): every sprite's world rect, visibility and animation state, per frame (today's "trace" format), produced by playing back exactly that stimulus | Where everything was on screen, frame by frame |

Today's golden replays and demos are both stimuli (one type, two roles: today's "recording"
format); today's golden traces are responses, but recorded from a separate input script, so the
two can drift. Here every response is made by playing back its own stimulus **(proposal)**, so they
cannot. A stimulus and its response are named for who played the stimulus: the human stimulus and
response, the ai ones, the cpu ones **(user)**. The names (the user, 2026-10-25): stimulus and
response, chosen over recording/trace, playthrough/sprites and acronyms (PIR/EPR) so that the type
is obvious in the file name and easy to say.

## 3. Three kinds, named by who played **(user)**

| Kind | Played by | Rank | Notes |
|---|---|---|---|
| **superhuman** | A human plus an ai: the ai's assessment of the human and cpu stimuli, corrected by a human | Highest | Built last (section 9) **(user)** |
| **human** | A human, playing normally in record mode | High | Precise and hand-tuned: every action is assumed deliberate |
| **ai** | A model that reads the game state and chooses actions ("dumb mode++") | Middle | Smarter than random; may be taught by human stimuli (section 9) |
| **cpu** | The engine's explorer: seeded, curious, random within the game's controls | Baseline | Always available, needs nothing from the developer |

The three are one feature **(user)**: three players behind one runner, one recorder, one response
format and one checker. A stimulus's header records who played it (`player: human | ai | cpu`),
so its kind is a fact, not a convention; its response inherits it. It is fine that cpu does not play
well **(user)**: it finds controls and scenes; human stimuli reach the deep states.

## 4. Names **(proposal)**

Nothing is unmarked: every file names its target and kind **(user: human, ai, cpu)**.

```
<package>/samples/
  <target>.human.stimulus.jsonl.gz       what a person pressed
  <target>.human.response.jsonl.gz       what playing it back must produce
  <target>.ai.stimulus.jsonl.gz          (when a model has played it)
  <target>.ai.response.jsonl.gz
  <target>.cpu.stimulus.jsonl.gz         (always: the engine's explorer)
  <target>.cpu.response.jsonl.gz
  demos/<name>.stimulus.jsonl.gz         (a stimulus shown, not only checked)
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

- *Checked*: everything the response records, every frame: positions, visibility, animation
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

Play the game normally with recording on (`--record-sample`); the engine saves a human stimulus
and makes its response by playing it back. High fidelity: the human reaches what cpu cannot
**(user)**. The existing hand-authored scripted runs (Brave Adventurer's, Drawing Fire's, Clockwork
Keep's input scripts, Mr. Muncher's autopilot) are cpu stimuli **(user, 2026-10-25)**: the CPU
generated them; nobody held the controls. A human stimulus is only one recorded with a person driving.

## 8. The options (every game, from the engine) **(proposal)**

| Option | Does |
|---|---|
| `--list-games` | This target and every game it wraps (recursively); a single game lists itself **(user)** |
| `--list-samples` | Its samples, by kind (human, ai, cpu) and role |
| `--run-samples` | Plays back every stimulus strictly and checks its response; exit status is pass/fail |
| `--run-demos` | Plays the demos, watched |
| `--demo NAME` | One demo |
| `--record-sample` | Human recording mode |
| `--explore` | Runs the explorer and writes the cpu stimulus and response |
| `--random-seed N` / `--random-seed random` | The engine owns the seed **(user)**; each target's default is a fixed seed the engine derives from its target name, so runs repeat with nothing set **(user)** |
| `--no-samples` (and a project setting) | The disable switch: on by default, off for developers who want it off **(user)** |

## 9. Later: the ai and superhuman kinds (plans, not built) **(user)**

The ai layer is not built yet **(user)**. Two kinds come after human and cpu:

| Kind | Made by | Adds |
|---|---|---|
| **ai** | a model reasoning about the human and cpu stimuli (and their responses) | the why: why the human acted, what the cpu kept missing |
| **superhuman** **(user)** | the ai's assessment of the human and cpu behaviour, written up, then corrected by a human | reviewed understanding: claims a person confirmed or fixed |

Human stimuli are rated highest; because they are precise and tuned by hand, every action is
assumed to have a reason (no double-jumps by accident). Ideas (proposals, 2026-10-25):

1. Frame-linked claims, not prose: the assessment is a list of claims tied to frames ("frame 412:
   jumped because a scarab was two tiles ahead"); the human marks each confirmed, wrong (with the
   right reason) or unsure; the corrections are kept beside the target's samples and seed the next
   assessment.
2. Mine the disagreements: the engine finds frames where human and cpu meet similar states but act
   differently, or where cpu dies and the human does not; the ai asks about those first.
3. Counterfactual replays: replays are deterministic, so at a human decision frame the engine can
   replay with another input (no jump) and show what would have happened: evidence for the why,
   and quicker corrections.
4. Confirmed intent becomes a test of meaning ("the player clears the scarab around frame 412"),
   checked as a condition rather than a pixel match: it survives art and timing changes that a
   frame-exact response cannot.
5. A reachability map: which states only the human reached, only the cpu, neither; it tells the ai
   where to explore and where a new human recording adds most.
6. Difficulty signals: where cpu dies repeatedly or the human hesitates, the report flags likely
   difficulty spikes.
7. Lineage: every stimulus's header records what it was made from (which human and cpu stimuli,
   which assessment, which round of corrections).

Rank **(user, 2026-10-26)**: superhuman ranks above human: it is a human plus an ai (the ai's
assessment, corrected by a human), which is why it is super. The order, highest first:
superhuman, human, ai, cpu.

## 10. Running many samples in one process

A wrapper runs several targets, an arcade dozens: no process per sample, no state between them.

1. Once per process: pygame and the display are initialised.
2. Per sample, setup: the engine's random streams, input state and clock reset; a fresh engine and
   scene from the stimulus's header.
3. Run: the stimulus is streamed, never decoded whole (today's are about 200 MB decoded); each
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

A guard test walks `--list-games` and fails if any target lacks a cpu stimulus and response (always
possible) or if any stimulus lacks its response. Today's gaps (no response, today's trace, for Mr. Muncher, Drawing Fire, the
Brave Adventurer launcher) are filled.

## 12. Known limits

- cpu plays badly by design; deep states need a human (or ai) stimulus.
- Raw-input games get a weaker explorer (documented per game in its samples).
- Committed samples grow the repository and each wheel (today about 1 MB compressed in all).

## 13. Open questions for the user

1. Names: settled (the user, 2026-10-25): stimulus and response; human, ai, cpu.
2. The existing scripted runs: settled (the user, 2026-10-25): cpu stimuli (section 7).
3. The ai and superhuman kinds: later plans (section 9); the ai layer is not built yet (the user).
4. The order: settled (the user, 2026-10-25): human and cpu first, with what they share (the runner
   and its leak guard, the engine options, discovery, the layout, the pre-push hook); then ai;
   then superhuman, last of all (the user, 2026-10-26).
