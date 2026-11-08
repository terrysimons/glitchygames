# Lucid Circuit, Stage 4b: the mirror game

- **Date:** 2026-11-06
- **Status:** Agreed by the owner. Step 1 is measured (2026-11-08): the design holds. Nothing is built yet; step 2,
  the pipe, is next.
- **Master plan:** [lucid-circuit.md](lucid-circuit.md), section 7. It comes before Stage 5's frame run.

## What the owner decided (2026-11-06)

The AI works on a copy of the game, not on the live game. The copy has the same seed, inputs and timings, runs on the
dummy driver at uncapped speed, and follows the live game by preferably under 5 seconds. There's no cap on what the
AI can see: just a very clean pipe to that layer. It gives real introspection into the game. Calls into the copy are
intercepted and posted back to the real game, which is an architectural update to these layers, and it's needed for
the full loop.

```
             the AI socket, forwards: events, with dt and polled input
Live game ──────────────────────────────────────────────────────> Clone
(the player's window)                                             (dummy driver, uncapped)
    ^                                                                 |
    |  validated, added to the live pump, recorded,                   | the AI inspects it
    |  and so sent forwards like any other event                      | and acts through events
    └─────────────── the AI socket, backwards: events <───────────────┘
```

Earlier plans put the mirror in Stage 10, behind checkpoints. That was wrong: a clone that starts with the game replays
from frame 0, so it needs none.

## The contract

1. **The live frame loop never waits for the clone,** and never reads game state for the AI. `describe_scene`, and its
   40-sprite cap, leave the live path.
2. **The clone holds what the live game held at that frame, and is told nothing else.** It replays the doors' stream,
   its saves stay in memory, and it plays no sound. It's never ahead of the live game.
3. **Every answer says its age:** which frame it describes, and how far behind that is.
4. **A clone that's behind or gone is said to be so.** The console reports it rather than falling back to the main
   thread. The game plays on regardless.
5. **Nothing runs in the clone that the live game didn't run,** or the two would part. An event the AI makes is captured,
   not handled. It's handled on the clone when the socket brings it back.
6. **An event from the AI is a proposal, not an order.** It's validated on the main thread and may be refused.

## How the two games talk

**Events pump backwards and forwards across the AI socket. That's all** (the owner, 2026-11-06). There's no separate
call-forwarding layer.

1. **Forwards:** each frame's events go from the live game to the clone over the socket, with their timing.
2. **Backwards:** what the AI does in the clone is captured as events instead of being handled there, and goes back over
   the same socket. An event can name its object with a sprite id.
3. **Into the game:** the host adds them to the live pump, as `AiHostSources.pump_events` already does for AI input,
   beneath the recorder. Refused ones go no further.
4. **And round again:** being in the pump, they're recorded and go forwards like any other event, reaching the clone at
   the frame the live game handled them. Both copies stay in step, and a recording of the run replays with no AI at all.

A replay also needs each frame's dt and polled input, so those ride on the same socket beside the events.

An action always lands on a later live frame than the one the AI was looking at. The AI can find the right moment in
what has happened, but it can't act in the past.

## The console's design: tool calls and a cached opening (the owner, 2026-11-07)

The model reads the game through **tool calls** on the clone, rather than a description pushed with every question.
Bonsai 2B made correct OpenAI-style calls through the installed llama-server on the first try (2026-11-07: it listed
the sprites, read one, then answered), but combined a speed's two parts by adding them, so tools do the arithmetic:

| Tool | Returns |
|---|---|
| `get_scene()` | Name, class, paused, game time, screen, sprite counts by class |
| `list_sprites(class_name=...)` | Sprite ids, optionally of one class |
| `get_sprite(id)` | Every plain attribute, read without running properties, with speed and direction worked out |
| `get_game_facts()` | What the game reports of itself (`describe_for_ai()`) |
| `calculate(expression)` | Arithmetic, so the model doesn't guess |
| `read_source(name)` | The code of a class or method, one method at a time or a short list of where to look, within a size limit. For any question about how a mechanic works, the model reads the source and quotes the lines that decide it, never inventing physics (the owner, 2026-11-07, after 2B explained Clockwork Keep's one-way platforms with physics that isn't there). The startup task reads the code with it too |
| Later: `history(from_frame, to_frame)` | Events and changes over a window, for the "why" questions |
| Later: `draw_*` | Overlay drawings: highlight, curve, marker |
| Later: `screenshot(frame)` | A picture of that frame, rendered in the clone or a copy (replaying to a past frame), scaled down and sent to the model's vision part. Never part of ordinary reads (`ai_introspection.NEVER_READ`), as rendering on every read would cost too much. A picture costs hundreds to thousands of tokens, so the tests measure it; it's drawn on the dummy driver, which can differ from the screen, and the answer says so (the owner, 2026-11-07; Stage 8's simplest form) |
| Later: `try_in_copy(events)` | Inputs run through a disposable copy, and what happened |
| Later: `set_in_copy`, `call_in_copy`, `run_in_copy(python)` | Anything in a disposable copy: set attributes, call methods, run the AI's own Python, including changing code at runtime: replacing methods, wrapping them in decorators, patching classes, swapping an object's class. The AI may manipulate a copy any way it wishes (the owner, 2026-11-07); the live game stays reachable only through validated events, and the sandbox keeps the copy off the network and out of the owner's files |

Each call is another turn of generation, so a Live question should need few. The description pushed today stays as a
fallback until the tools exist.

**Every prompt opens the same way for a game,** so the prompt cache serves it nearly free after the first question:
the system prompt, the tools, the engine's shared mechanics (pausing, world and screen positions, ids never reused),
then this game's mechanics and controls. The conversation and question follow. Its size counts against the context, so
the tests measure it per game at 8K.

**The game's mechanics are worked out by the AI as a startup task,** by introspecting the game's code and state in the
clone, not written by hand (the owner, 2026-11-07). Getting ready may take a while. The model starts when the game
does and is kept warm while it runs. Proposed, to be confirmed: keep the result per game version, reusing the
engine's game source revision, so a launch with unchanged code reuses it; read the code a class at a time and combine
the summaries, as a game's code doesn't fit in 8K. The research reports of 2026-11-07, which cite file and line, are
a reference the tests check the model's mechanics against, catching invented rules.

## Hard problems, to be settled here and not assumed

- **Object identity.** The clone's objects and the live game's are the same objects, in the sense that matters: the
  same seed and inputs give the same objects, which is the contract (the owner, 2026-11-06). They need a stable way to
  be referenced, and one exists: `tracing.StableSpriteIds` gives each sprite `<ClassName>#<n>`, the next number for its
  class, and every golden replay already depends on the two sides agreeing. A hash would be no more stable, and the name
  is readable. It's inherent to every game: no game opts in, and none may need to (the owner, 2026-11-06).

  **An id is never recycled** (the owner, 2026-11-06). The numbers only go up, for the whole run: when `Ball#2` leaves,
  the next ball is `Ball#3`, whatever happens to memory, scenes or the object. Anything built on these ids must keep
  that, with a test that a removed sprite's number is never given out again. What it needs for this:
  - **A way back:** today it goes from object to id only, and a call needs id to object. `sprite.alive()` says whether
    it's gone.
  - **Holding no sprite alive (done, 2026-11-06):** it used to hold every sprite it had seen for the whole run, because
    it looks them up by Python's `id()`, which Python gives to a new object once the old one is freed. Now it watches each
    through a weak reference and forgets it as it's freed, with tests that a freed sprite's number isn't given out again.
  - **Pooled objects:** a game that reuses one sprite object for a new ball would keep its old number. No game here pools
    sprites today. If one ever does, it counts as the same object until there's a way to say otherwise.
  - **Its cost:** it's assigned on first sight while sampling each frame, on the main thread. If Step 1 finds that too
    dear, assign the same kind of id when a sprite is created instead (`RootSprite.__init__`), which costs nothing per
    frame but needs its own proof that both sides agree.
  - **Beyond sprites:** it covers sprites in `all_sprites`. Other game objects are for Stage 7.
- **Objects in the timing gap.** The clone is behind, so anything it can name already exists in the live game, or did.
  A call can only find its object gone, never not yet made, and a gone object's id can't have passed to another. Such a
  call is refused, and the AI is told. New objects it hasn't reached yet simply aren't known to it until it does.
- **Which events may come back.** `ALLOWED_INPUT_EVENT_TYPES` holds only key presses and releases today. Stable ids are
  what let this grow massively (the owner, 2026-11-06): once an event can name any object, the AI's capabilities can
  expand far beyond input. The small first list proves the path and isn't the goal. Each widening is still deliberate,
  as an event a game handles can do whatever its handler does, and text the AI read could be trying to steer it
  (section 8). Stage 7 decides how far it goes.
- **Event fields.** Only JSON-safe values and sprite ids can cross. Anything else is refused by name.
- **Silent drift.** Replays compare sprites and recorded events, not all game state, so a wrong `rally_count` would go
  unseen. The stream carries a per-frame check. **A clone that drifts or crashes is a bug, and should never happen**
  (the owner, 2026-11-08):
  1. A restart is recovery, not routine. It keeps the AI working while the bug is found, and it's logged loudly as a
     bug.
  2. The drift check reports precisely: the first frame where the clone parted from the live game and the state that
     differed, as a replay's divergence report does, so the cause can be fixed.
  3. The slow catch-up after a restart then matters much less, as it only happens when something is already wrong.

  A restarted clone replays from frame 0 uncapped (fast-forward) until it reaches the live edge: for a session T
  seconds old and a clone at S times real time, that takes T / (S - 1). At Brave Adventurer's 11x (Step 1's
  measurements), 30 minutes in, about 3 minutes. Checkpoints would bound it later.
- **The stream's cost.** The recorder's per-frame work runs on the main thread. Sending hashes rather than whole sprite
  samples may be needed.
- **The clone's cost.** It takes CPU and roughly doubles the game's memory. 26x real time came from one light game, one
  run, so a heavy game may not keep to 5 seconds.
- **What goes in a prompt.** The pipe has no cap, but the model reads every token. Choosing what to send becomes a matter
  of speed, decided off the frame loop.
- **Games that can't replay.** A game that reads something outside the doors would part from its clone. The doors guard
  makes that rare, and the drift check should catch what's left.

## Steps

1. **Measure the risk.** On PaddleSlap and a heavier game, on a real display: the stream's main-thread cost, how fast the
   clone runs, and how far behind it stays. Every other step depends on this.

   Also measure allocation churn on every game's golden replay, as the clone repeats the same allocations uncapped.
   The engine leaves the garbage collector on Python's defaults, so measure, in separate runs so one doesn't skew
   another: collector pauses (`gc.callbacks`) and whether they line up with slow frames, allocations by type
   (`tracemalloc`), `pygame.Surface` creations, and what each sprite class costs to build. That decides what follows:

   | Finding | What follows |
   |---|---|
   | Pauses match slow frames, and sprites dominate | An engine `SpritePool`: `acquire()` gives a reset sprite the next id, so numbers never recycle |
   | Pauses match slow frames, and small objects dominate | Tune the collector (`gc.freeze()` after loading) and cut those allocations. No pool |
   | Pauses don't match slow frames | Neither helps frame times. A pool waits for a game that needs one |

   PaddleSlap's golden built 4 balls at about 0.2 ms each in 622 frames, so a pool wouldn't help it on that evidence.

   Also track the context a question needs, as the game goes on (the owner, 2026-11-07). A question carries one frame's
   state, roughly fixed while the scene is (the same balls in play), plus the recent conversation, plus the model's
   reasoning, which was up to about 6,000 tokens on hard questions. With no sprite cap, a busy frame is large: Mr.
   Muncher's 267 sprites are about 35 KB. Measure each frame's whole state over every golden replay, and keep
   llama-server's own prompt and generated counts for every answer, so the service's context size is set from these.

   **Measured (2026-11-08, one 16-core Mac, every golden replay and PaddleSlap's demo).** The measurements are
   `scripts/mirror_measurements/` (its docstring has the commands), to run again once the pipe exists. The design
   holds:

   - **The clone keeps up.** Headless and uncapped, the stand-in clone (a headless replay in its own process, its
     frames timed) ran three times per recording, agreeing within 3%:

     | Recording | Speed | Frame p50 / p99 | Start-up to frame 0 |
     |---|---|---|---|
     | Brave Adventurer Classic / Papyrus | 11.5x / 10.8x | 1.67 / 1.89 ms; 1.78 / 2.04 ms | 0.28 s; 0.30 s |
     | Mr. Muncher | 22.5x | 0.76 / 0.96 ms | 0.47 s |
     | Clockwork Keep | 39.6x | 0.42 / 0.71 ms | 0.27 s |
     | Drawing Fire | 40.8x | 0.40 / 0.59 ms | 0.25 s |
     | PaddleSlap (golden / demo) | 152x / 169x | 0.10 / 0.19 ms | 0.23 s |

     No frame took longer to replay than it took live, so a clone that starts with the game stays its start-up behind:
     0.23 to 0.49 s, well inside 5 s. Only a restart is slower (Silent drift, below). Measured on short goldens (8 to 35
     s); a later level may be heavier.
   - **The stream is cheap; the recording file isn't.** Live on the real display (cocoa), the recorder's main-thread
     work per frame, from timers on each piece:

     | Piece | PaddleSlap mean (p99) | Mr. Muncher, 267 sprites, mean (p99) |
     |---|---|---|
     | The events, dt and polled-input diff | 0.014 (0.04) ms | 0.007 (0.03) ms |
     | Every sprite's id, rect and visibility | 0.013 (0.04) ms | 0.078 (0.16) ms |
     | Content hash | 0.071 (0.18) ms | 0.306 (0.59) ms |
     | Delta encoding, JSON and gzip | 0.146 (0.34) ms | 0.545 (1.02) ms |

     A clone needs only the first row, about 0.01 ms a frame. Writing a recording costs Mr. Muncher 0.94 ms, 6% of a
     60 FPS frame. The drift check should be cheaper than the full content hash (0.3 ms).
   - **The clone doesn't slow the live game.** A stand-in clone replaying uncapped, over and over, on another core
     (the worst case: a real clone idles at the live edge) left PaddleSlap's and Mr. Muncher's live frame times
     unchanged (p99 16.67 ms with and without; one 27.7 ms frame in Mr. Muncher, with and without).
   - **Allocation churn: the third row of the table above.** No generation-2 collection ran in any golden. Young
     collections are at most 2.5 ms (generation 1, Mr. Muncher), nearly all while the game loads, and no frame among the
     slowest 1% had one (every game but PaddleSlap, whose frames are a tenth of a millisecond). Building sprites is
     negligible (1 to 26 ms per golden; Papyrus's player 2.4 ms). Neither a sprite pool nor tuning the collector would
     help frame times. Python's allocations grow only into bounded histories (the overlay's 5,000 frame times, the
     performance manager's 100,000 samples).
   - **Surface churn: Brave Adventurer Papyrus made 51 `Surface.copy` calls a frame.** Every other game makes 0 to 6
     Surface-making calls a frame (Clockwork Keep's 5.4 are `Font.render`). Fixed (BUGS.md #265): a helper copied every
     Papyrus sprite's frame each tick, though only the player's fade needed it; now none in its golden.
   - **A frame's whole state is too big for one prompt, so the tools choose.** Read as the tools read it (properties
     on, plumbing off, no sprite cap), compact JSON: Mr. Muncher 74 KB (267 sprites, about 250 B each), Brave
     Adventurer Classic 30 KB, Clockwork Keep 7 KB, PaddleSlap 5 KB, Drawing Fire 1 KB (no sprites). The state is
     nearly constant within a scene. Papyrus read as 352 KB because each `AnimatedSprite` gave every animation frame's
     pixels, three times (`frames`, `animations`, `animation_data`). Fixed (2026-11-08): `ai_introspection` reads a
     `SpriteFrame` as its size and duration and leaves `animation_data` out as plumbing, so Papyrus reads as 92 KB (854 B
     a sprite, its frames shown twice as summaries).
   - **What an answer uses.** From llama-server's own counts in the last paired run (2B, 8K, 150 answers): the opening
     prompt (system prompt and tools) is about 1,800 tokens; an answer used 2,900 to 4,700 tokens of context at the
     median across the games, and its generation 670 to 1,300 tokens (up to 5,400). Some answers in Brave Adventurer,
     Clockwork Keep and Mr. Muncher reached the whole 8,192.
2. **The pipe.** A socket from the doors to a clone that starts with the game, a replay source that waits at the live
   edge, and supervision: start, restart, stop with the game. A frontier report: received, processed, age.
3. **Read-only introspection.** A query socket on the clone. The console's `/ask` and `/inspect` read it through the
   tool calls above, with no cap, and the live-path `describe_scene` goes. The startup task works out the game's
   mechanics, and the cached opening carries them. The answer comparison's affected questions run again.
4. **Drift checks.** A drift or crash is a bug to find and fix, never routine (the owner, 2026-11-08; see Silent
   drift): the check names the first differing frame and what differed, a restart is logged as a bug, and the console
   says the clone is catching up and how far behind it is.
5. **Events backwards.** Capturing the AI's events in the clone, ids in their fields, refusal and stale handling, with one
   allowed event proved end to end: applied live, recorded, seen by the clone, and replayed with no AI.

## What this changes elsewhere

- **Stage 5's frame run waits for steps 1-3,** because the real load is game, clone and model together.
- **Stage 5's answer comparison still ranks the sizes,** on the capped states, and its affected questions run again.
- **Stage 7** builds on step 5, and its discovery can read the clone freely.
- **Stage 8** may draw frames in the clone rather than capture them from the live game. That's untested, and the dummy
  driver may not match the screen exactly.
- **Stage 10** keeps checkpoints and branching. A branch would be a disposable copy of the clone, labelled speculative.
- **Copies the AI experiments in** (the owner, 2026-11-07). The AI introspects the game and runs events through
  disposable copies to work out how it behaves, with nothing wired by the game. The copies are the physics: a search
  over inputs ("run right, jump at x 340"), run uncapped and read back by introspection, finds routes and reach in any
  game. In order:
  1. **Input search in copies:** game-agnostic, no generated code. It gives a best route, drawn as a curve on the
     overlay, and which platforms can't be reached, coloured red.
  2. **Saved findings:** jump reach and the like, kept as facts for later questions.
  3. **Model-written code (a planner, say), run freely in sandboxed copies:** no network, no writes outside a scratch
     folder. Only installing code on the live game needs the owner's approval (section 8 of the master plan).

  The hard parts: a copy at frame N replays from frame 0 until checkpoints exist, and forking the clone's process on
  macOS needs testing; copies use CPU and memory within a budget behind the live game and the clone; copies drift as the
  clone can, so the drift check covers them; and a 2B model should choose and explain searches well but write planners
  poorly, which is why search comes first.
- **AI drawings** use the host's overlay, the console's layer: never recorded, never in screenshots, never changing
  the game, and shown without the debug overlay (the owner, 2026-11-07).

## Exit evidence

- The live game's frame times with the clone running, against `--no-ai`, on a real display.
- The clone keeps under 5 seconds behind on the games measured, or the limit is stated for those that don't.
- `/inspect` shows every sprite in Mr. Muncher's scene, including the player.
- One event goes clone to live and back, and a recording of that run replays exactly with no AI.
- Killing the clone leaves the game playing, and the console says what happened.
