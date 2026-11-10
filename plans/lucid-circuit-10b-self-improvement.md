# Lucid Circuit, Stage 10b: the AI teaches itself each game

- **Date:** 2026-11-07
- **Status:** Planned with the owner. Nothing is built. It needs the mirror ([Stage 4b](lucid-circuit-4b-mirror.md)),
  disposable copies of the clone (Stage 10) and code installs with restoration (Stage 7), so it comes after those.
- **Master plan:** [lucid-circuit.md](lucid-circuit.md), section 7.

## What the owner decided (2026-11-07)

When a game starts, the AI learns how to play it. It does the collection step (Stage 4's cached opening: source,
controls, mechanics), then asks itself questions about the game state and teaches itself to play, by the scientific
method:

1. ask a question
2. make a hypothesis
3. test the hypothesis
4. measure
5. accept or reject the hypothesis
6. an accepted hypothesis gets a tool; a rejected one is reconsidered and reworked in the face of new evidence, until
   it's accepted or the question is judged a bad question
7. the tool gets optimized
8. the tool goes into use for the game
9. each new tool comes into the AI console as an FYI message

Further decisions, in the owner's words where quoted:

- **The game is canonical.** "If observations disagree with the hypothesis, then the hypothesis is wrong."
- **Adversarial:** "we should try to poke holes in the hypothesis to derive more questions."
- **Branching:** "We should also branch off of our existing knowledge to ask new and better questions."
- **No approval for tools:** a new tool goes straight into use, with the FYI in the console.
- **Kept between runs:** the next start of a game picks up where the last left off.
- **The AI plays the game.** Once a rule is in place, the game-over screen's demo is augmented with the AI playing,
  distinct from the recorded demo (the layering is the builder's call; ours is below). "The end result should be that
  the AI starts playing the game and continues for as long as it can."
- **"Anytime a new mechanic is plumbed, the demo starts over,"** so the attract screen shows each improvement.
- **"In AI Demo mode you can install code."**

## The loop

```
  game starts ──> collection (Stage 4's opening) ──┐
              ──> watch the demo, unthrottled ─────┤
                  (or a recording of play)         ├──> question queue
  always: unfamiliar events, progression ──────────┘          │
                                                              │
          ┌───────────────────────────────────────────────────┘
          v
      question ──> hypothesis ──> test in a copy ──> measure ──> survives the hole-poking?
          ^              ^                                        │yes            │no
          │              └──────── reworked with the evidence ────┼───────────────┘
          │                        (or the question is judged bad)│
          │                                                       v
          │                                                  accepted rule ──> tool ──> optimized
          │                                                       │                       │
          └──── new questions: holes found, and branches ─────────┘                       v
                from what's now known                                   in use: answers and AI demo
                                                                         + FYI in the console
                                                                         + the AI demo starts over
```

### Watching play (the owner, 2026-11-07)

- **The demo first.** A game with a bundled demo has it watched, unthrottled, in the AI's copy: the AI uses the demo's
  behaviour to ask what happened and why (why that ball sped up, why that life was lost, why the score jumped). So
  every game with a demo starts with a plethora of questions grounded in real play, beside those from the code.
- **Otherwise, a recording of play.** A game with no demo that the AI has never seen uses a recording of gameplay in
  its place. Our call: the game's own recordings where it ships any (its golden replays), and the live session itself,
  which the clone follows from frame 0. With no behaviour seen yet, the first questions come from the code alone.
- **Unfamiliar events.** Later, when the AI needs more context, it pays attention to events it's unfamiliar with
  (an event type, a scene change, a sprite class or a death no rule explains) and to how the game progresses (floors,
  waves, screens, difficulty), and asks about them.
- **A constant feedback loop** runs until the AI feels it has enough rules to really participate; then the AI demo
  takes over (below), and the loop goes on, fed by its own play as well.
- **What "playing well" means is learned too** (the owner, 2026-11-07): no game declares it. The AI works it out from
  the code and from watching how the game progresses (what the score counts, what ends a run, what the demo's player
  went after), as rules like any other: tested, open to hole-poking, and overturned when the game disagrees. It's
  among the first questions for every game, since question ranking and the AI demo's readiness depend on it.

### What the AI can look at (the owner, 2026-11-07)

Every observation is open to the loop, for asking questions, testing hypotheses and measuring:

- **Screenshots** of any frame, for context the state doesn't carry (what the player sees).
- **Fast forward and rewind** of game state in its copies: run ahead to see what follows, go back to the frames
  before something happened (rewinding is rebuilding from frame 0 until Stage 10's checkpoints exist).
- **Multi-frame screenshots with their event context:** a strip of frames around a moment, beside the events pumped
  in them (the contact sheet of Stage 9).
- **Game state variables:** any object, read as the introspection tools read it, properties included in copies.
- **High scores, saves and other persistent records,** read from the copy's sandboxed saves: what counts as a good
  run, and how earlier runs went.
- Our call: what the built-in tools already offer (scene, sprites, objects, history, source, calculate, draw) is the
  starting set; the loop's own tools join it as they're accepted.

### Finding mechanics nobody listed (the owner, 2026-11-07)

- Games may have mechanics we haven't thought of. None of ours has an item inventory, say, so a new game with one
  would be missed by an AI that only asks about what our games do. So **one of the first questions for every game is
  "what does this game do that's unusual?"**: what mechanics it has beyond the ones already known.
- Our call: the AI keeps a catalog of mechanics it knows across games (movement, jumping, collision, scoring, lives,
  pickups, timers, ...). It probes the new game for anything outside it: state no known mechanic explains (a list
  that grows when the player touches things, a menu no control in the opening opens), source the opening didn't
  cover, events and scenes it hasn't seen. Each find becomes a new mechanic in the catalog, and the catalog is shared
  across games.
- **Once a new mechanic is identified, the AI strives to understand and use it:** it gets its own questions (what goes
  in the inventory, what using an item does, when that helps), its rules and tools, and a place in the AI demo's
  policy once it helps to play well.

### Questions

- The first questions come from the opening (what each control does, what ends a life, what scores, what each sprite
  class does) and from the play watched above. After that, every question comes from the loop: a hole found in a
  hypothesis, an unfamiliar event, or a branch from an
  accepted rule ("a jump carries about 160 px" leads to "which pits can't be cleared?", then "what's the safest route
  through this screen?").
- Our call: questions are ranked by how much the answer would help the AI play (a death not yet explained ranks
  highest), so it doesn't wander into trivia. The player's own console questions join the queue too, ranked high.
- Our call: knowledge is a tree. Each question and rule records what it grew from, so a rule overturned later marks
  everything that grew from it for re-testing.

### Hypotheses and tests

- A hypothesis is a prediction that can be checked by code: a setup (a frame, or a state set up in a copy), an action
  (inputs, or a call), and the predicted measurement ("Tinker lands on the platform at world y 880").
- Tests run in disposable copies of the clone (Stage 10), never in the live game. The AI may do anything in a copy
  (the owner, 2026-11-07): set state, call methods, run its own Python, polymorphism and decorators included. So a
  hypothesis's setup, action and measurement are raw Python against the copy's scene objects, not a restricted
  language. Copies run as Stage 4b already requires: their own process, inside an operating-system sandbox with no
  network and no writes outside a scratch folder, with a timeout per test. Copies run uncapped on the dummy driver,
  so tests run faster than real time (PaddleSlap's golden replayed at least 26x real time). The measurement is read
  from the game by code, never judged by the model.
- Our call: a hypothesis is stored as data (pydantic, frozen): the question it answers, the setup, action and
  measurement code, the predicted value with its tolerance, and every result so far.
- **Hole-poking:** before a hypothesis is accepted, the AI attacks it with variations: edge cases, other sprites,
  other floors and speeds, the frames just before a death. Each hole becomes a new question. Our call: a hypothesis is
  accepted only after surviving a set number of attacks (start at 5; the builder tunes it), not after one passing test.
- **Rework:** a rejected hypothesis is reworked with the evidence that rejected it, keeping the failed predictions so
  the same one is never tried twice.
- **Bad questions:** a question is judged bad when no measurable prediction can be made for it, when the source shows
  it rests on something false (the "elevator" question in Clockwork Keep, which has no elevators), or when its
  hypotheses keep failing past a limit without getting closer. It's archived with its reason, never deleted, so it
  isn't asked again.
- Observations of the live game count as evidence too: a death in the AI demo that the AI didn't predict rejects the
  rule that predicted otherwise, and goes back into the loop.

### Tools

- An accepted rule becomes a tool: a Python function the AI wrote, reading game state and working something out
  (`can_reach(platform)`, `next_pit_distance()`, `safe_route(screen)`), with the evidence from its tests kept as the
  tool's own tests.
- **Optimized:** made faster, and its answer made compact (the 8K context must hold, as for the built-in tools), with
  its tests still passing.
- **In use:** added to that game's tool list, for answering the player and for playing the AI demo. No approval needed
  (the owner, 2026-11-07).
- **Where tools run:** in the clone, never in the live game's process (Stage 4b's contract: the live frame loop never
  reads game state for the AI). The clone holds what the live game held, so a tool's answer is the live game's, with
  its age. A tool reads state only; anything that changes the live game is a proposal (Stage 4b) or, outside an AI
  demo, a code install needing the owner's approval.
- **FYI:** each new tool shows in the console as one line, e.g. `FYI: new tool can_reach(platform): which platforms
  Tinker can jump to from where he stands (tested 12 ways).` A tool later overturned is withdrawn with an FYI too.

### Kept between runs

- Per game: the question tree, rules with their evidence, bad questions with reasons, and tools with their tests. The
  next start loads them and goes on.
- Our call: kept under the AI install root (beside the models), keyed by the game's identity and its source revision
  (`game_source_revision`). When the game's code changes, every rule is re-tested before its tool is used, since the
  game is canonical and it may have changed.
- Our call: "the game's code changed" is judged by a hash of the game package's source files, not the commit, so
  uncommitted edits during development don't re-test everything on every start, only after an edit that touches the
  game. Re-testing runs in the background; tools whose rules aren't re-tested yet are left out until they pass.

## AI demo mode

- **When:** in the slot where a game plays its recorded demo on the game-over screen (PaddleSlap's after 10 seconds
  idle), once the AI has enough accepted rules to play. Games without a demo slot get one through the same layer.
- **Layering (our call):** today's demo runs in a playback scope (the live scene set aside, saves sandboxed, any real
  input ends it). The scope's shared part is split from its input: `RecordingDemo` (today's, served from a recording)
  and `AIDemo` (inputs from the AI). Subclassing the recorded demo would inherit replay logic an AI demo doesn't need.
- **How it plays:** it presses buttons as a player would, through the same input events a supervisor posts
  (`post_input_event`, recorded as external), so the game can't tell it from a person, and a recording made during it
  replays exactly.
- **Who decides each frame (our call):** a model can't answer 60 times a second, so the AI writes a policy: Python,
  built from its tools, that turns the game state into the frame's inputs. The policy is installed in the demo's scope
  (code installs are allowed there) and runs each frame in the game's process, cheaply. The model plans at coarse
  intervals and between demos: it rewrites the policy as rules are accepted, and a death it didn't predict goes back
  into the loop.
- **When it's ready (our call):** the AI demo replaces the recorded one once its policy, run in a copy, does better
  than standing still (by the game's measure of playing well, below). Until then the recorded demo plays.
- **"A new mechanic is plumbed" (our call):** the policy changed, which happens when a tool it uses is added,
  optimized or withdrawn. A tool the policy doesn't use doesn't restart the demo.
- **Games without a demo slot (our call):** only PaddleSlap has one today. The idle timer moves into the engine's
  game-over and title screens, so every game gets the slot from the same place. Drawing Fire draws without sprites,
  so its AI demo waits for its conversion to sprites (plans/future-work.md).
- **How long:** as long as it can: until it loses its last life, or a real player presses a key or button, which ends
  it as a demo ends today. Then back to the game-over screen; the next idle period starts another run.
- **Starts over** whenever a new mechanic is plumbed in (a new tool, or a rule that changes how it plays), so each
  improvement is seen.
- **Code installs are allowed in AI demo mode** (the owner, 2026-11-07). The demo's scope sandboxes saves, and Stage
  7's restoration undoes every install when the demo ends, so the live game the player returns to is as it was.
  During live play, installing code still needs the owner's approval each time (the master plan, section 8).

## Order of building

Sequenced behind Stages 4b, 7 and 10, not stubbed: the loop's tests need real copies, and the AI demo's code
installs need real restoration. The behaviour suite (`scripts/ai_behaviour/`) is the measuring stick for exit
evidence 7, and its interfaces may change before then.

## Where it runs

- In the background, on the warm 2B model, under Stage 5's throttle: it never slows the live game.
- **The whole loop stays on 2B** (the owner, 2026-11-07), writing hypotheses and tool code included. 2B wrote code in
  only 4-16% of the behaviour suite's answers that asked for it (2026-11-07), so the loop scaffolds it: templates for
  a hypothesis's setup, action and measurement and for a tool's signature; every piece of code it writes is checked
  (parsed, run against its tests in a copy, timed) before it's trusted, and a failure goes back to the model with the
  error, a bounded number of times. Code that never passes is a rejected hypothesis like any other.
- Never in a replay, a headless run or a browser, like the rest of the AI.

## Goals, non-goals, anti-goals

- **Goal:** from a cold start, a game's AI demo gets visibly better over a session, each step matching an FYI line,
  and the next start begins where the last ended.
- **Non-goal (our call):** changing the model's weights. Learning lives in the knowledge store and the tools, not in
  fine-tuning.
- **Anti-goals:** a rule accepted on the model's word rather than a measurement; a slower live game; a real save
  changed by the AI demo; a live game left changed after an AI demo ends.

## Exit evidence

1. PaddleSlap from a cold start: within a set time (the builder proposes one from measurements), the AI demo keeps a
   longer rally than the AI managed in its first run, with the FYI lines for the tools it used.
2. A restart loads the knowledge and plays at least as well with no relearning.
3. A deliberately wrong rule planted in the store is overturned by the game's behaviour, and its tool withdrawn with
   an FYI.
4. A question resting on something false is judged bad, with its reason.
5. Frame times with the loop running against `--no-ai`, on a real display, within Stage 5's budget.
6. An AI demo that installed code leaves the live game exactly as it was: its golden replay still matches afterwards.
7. The behaviour suite (`scripts/ai_behaviour/`) scores at least as well with the discovered tools as without.

## Risks

| Risk | Effect | Mitigation |
|---|---|---|
| The model invents a measurement | False rules become tools | Measurements are read by code from the game; the model only proposes |
| Hole-poking never ends | No rule is ever accepted | A set number of attacks, and a limit on reworks per question |
| A tool is slow or huge | The 8K context overflows, or answers lag | Optimizing includes a size and time budget; a tool over it isn't used |
| Code installed in an AI demo survives it | The player's game is changed | Stage 7's restoration, checked by exit evidence 6 |
| Knowledge from an older version of the game | Wrong play after an update | Keyed by source revision; re-tested on change |
| Too many FYI lines | The console becomes noise | Our call: one line per tool; the builder may group a burst |
