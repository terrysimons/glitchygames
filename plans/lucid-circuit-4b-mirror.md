# Lucid Circuit, Stage 4b: the mirror game

- **Date:** 2026-11-06
- **Status:** Agreed by the owner. Nothing is built yet. Step 1 measures whether the design holds.
- **Master plan:** [lucid-circuit.md](lucid-circuit.md), section 7. It comes before Stage 5's frame run.

## What the owner decided (2026-11-06)

The AI works on a copy of the game, not on the live game. The copy has the same seed, inputs and timings, runs on the
dummy driver at uncapped speed, and follows the live game by preferably under 5 seconds. There's no cap on what the
AI can see: just a very clean pipe to that layer. It gives real introspection into the game. Calls into the copy are
intercepted and posted back to the real game, which is an architectural update to these layers, and it's needed for
the full loop.

```
             frame stream: seed, dt, events, polled input, control events
Live game ──────────────────────────────────────────────────────> Clone
(the player's window)                                             (dummy driver, uncapped)
    ^                                                                 |
    |  validated on the main thread, applied as a recorded            | the AI inspects it
    |  control event, which the stream then carries to the clone      | and tries calls on it
    └─────────────────────────── intercepted calls <──────────────────┘
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
5. **Nothing runs in the clone that the live game didn't run,** or the two would part. An intercepted call is captured,
   not executed. It runs on the clone when the stream brings it back.
6. **A posted-back call is a proposal, not an order.** It's validated on the main thread and may be refused.

## How a call gets back

`SceneManager.record_control_event` already records an action into its frame and runs its handlers, and a replay
re-applies it at the same point in that frame. So:

1. The AI calls something on an object in the clone. A proxy captures the call instead of running it.
2. The call travels to the live game as data: a stable handle for the object, the method, and its arguments.
3. On the main thread, inside a budget, the host validates it against what's allowed and against the object's state.
4. If accepted, it's applied as a control event on the next frame, and recorded like any other.
5. The stream carries it to the clone, which applies it at the same frame. Both copies stay in step, and a recording of
   the run replays with no AI at all.

An action always lands on a later live frame than the one the AI was looking at. The AI can find the right moment in
what has happened, but it can't act in the past.

## Hard problems, to be settled here and not assumed

- **Object identity.** The clone and the live game share no objects, so a call needs a handle that names the same
  object in both: deterministic per scene if possible. Nothing like it exists yet.
- **Stale calls.** The object may have gone by the time the call lands. It's refused, and the AI is told.
- **What may be called.** Forwarding any call would amount to running AI-written code in the game, which the plan rules
  out (section 8). Stage 7 decides what's allowed, with discovery that doesn't run properties. The first version only
  carries a small allowlist.
- **Arguments.** Only JSON-safe values and handles can cross. Anything else is refused by name.
- **Silent drift.** Replays compare sprites and recorded events, not all game state, so a wrong `rally_count` would go
  unseen. The stream carries a per-frame check, and a clone that drifts is flagged and restarted from frame 0. Restarting
  a long session may be slow, which is where checkpoints would help later.
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
2. **The pipe.** A socket from the doors to a clone that starts with the game, a replay source that waits at the live
   edge, and supervision: start, restart, stop with the game. A frontier report: received, processed, age.
3. **Read-only introspection.** A query socket on the clone. The console's `/ask` and `/inspect` read it, with no cap, and
   the live-path `describe_scene` goes. The answer comparison's affected questions run again on the full state.
4. **Drift checks.**
5. **Posting calls back.** Handles, the proxy, validation, control events, refusal and stale-call handling, with one
   allowlisted call proved end to end: applied live, recorded, seen by the clone, and replayed with no AI.

## What this changes elsewhere

- **Stage 5's frame run waits for steps 1-3,** because the real load is game, clone and model together.
- **Stage 5's answer comparison still ranks the sizes,** on the capped states, and its affected questions run again.
- **Stage 7** builds on step 5, and its discovery can read the clone freely.
- **Stage 8** may draw frames in the clone rather than capture them from the live game. That's untested, and the dummy
  driver may not match the screen exactly.
- **Stage 10** keeps checkpoints and branching. A branch would be a disposable copy of the clone, labelled speculative.

## Exit evidence

- The live game's frame times with the clone running, against `--no-ai`, on a real display.
- The clone keeps under 5 seconds behind on the games measured, or the limit is stated for those that don't.
- `/inspect` shows every sprite in Mr. Muncher's scene, including the player.
- One call goes clone to live and back, and a recording of that run replays exactly with no AI.
- Killing the clone leaves the game playing, and the console says what happened.
