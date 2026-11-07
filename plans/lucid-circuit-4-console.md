# Lucid Circuit, Stage 4: the read-only console

- **Date:** 2026-11-06
- **Status:** Built and tried on real PaddleSlap with the real model on branch
  `worktree-ai-service-ansible`, except as listed under "Still open".
- **Master plan:** [lucid-circuit.md](lucid-circuit.md), section 7, Stage 4.

## What this builds

The `` ` `` key opens a console over any game with AI, with no change to the game
(`src/glitchygames/ai_console.py`, whose docstring holds the rules).

| Command | What it does |
|---|---|
| `/ask QUESTION`, or just type | Asks the model about what's on screen, streaming the answer. Nothing changes |
| `/inspect [NAME]` | Prints the scene, or the sprites with NAME in their name. No model involved |
| `/ai` | The connection, the models and the requests so far |
| `/cancel` | Stops the running request |
| `/history [TEXT \| clear]` | This game's past questions, those holding TEXT, or forgets them |
| `/clear`, `/help [COMMAND]` | Empties the screen and conversation; lists the commands |

Up and Down recall input, Tab completes commands, Page Up and Down scroll a page, Shift+Up and Shift+Down scroll
a line, and F4 reaches a new AI panel on the debug overlay. Ctrl-A and Ctrl-E go to the start and end of the
line. Ctrl-K cuts to the end of the line into the console's own buffer, never the clipboard, and Ctrl-Y pastes
it. A held Backspace repeats, faster the longer it's held; SDL's own key repeat, which a game may turn on, is
ignored.

## Decisions

- **It lives in the host layer, not a scene.** That answers both of section 4's warnings: a sprite would have
  entered the sprite comparison, and games that poll input would still have acted on typed keys. Here the
  drawing uses the doors' overlay, and the keys are hidden from both events and the snapshot. The recorder sits
  above, so a recording holds none of it.
- **Opening doesn't pause the game.** The brief asks for this to be defined. Pausing belongs to the game, so
  pause first if it matters: the console works over the pause screen and inspects the paused game.
- **One request at a time**, with `reasoning_effort` low, because an interactive question shouldn't wait for
  minutes of reasoning.
- **History is one JSONL file per game** under the service's install, so uninstalling removes it. It's capped at
  1,000 records, and each holds the question, the answer and the game state the model saw. It's written only on
  the worker thread.
- **A scene may add facts** with `describe_for_ai()`. PaddleSlap reports its rally count and balls in play.
- **The service moved to the owner's ports:** the API on 23231, Bonsai on 23232-23235, Qwen on 23236-23238.

Left for later, from the brief's list: `/augment`, `/glitch`, `/undo`, `/rate`, `/feedback`, request IDs in
`/cancel`, and the throttle (Stage 5).

## Evidence (2026-11-06)

Real PaddleSlap, real 27B on the owner's M4 Max, the keys posted through the real event path, on SDL's dummy
driver. Two questions ran one after the other across 1,198 frames, about 20 s.

| Question | Answer | Time |
|---|---|---|
| How many balls are in play, and where is the first one? | "1 ball is in play. The first one is at world position 43.82, 31.06..." | 8.6 s, 266 tokens |
| and what is the rally count? | "I do not know the rally count from the state shown." | 7.0 s, 149 tokens |

Both were checked against the state saved in the history file. The first matches it exactly: one ball, at world
position 43.82, 31.06, rect `[48, 29, 20, 20]`. The second is correct too: the game-over screen was up by then,
and that scene doesn't report a rally count. Its final score is on screen, in text sprites the description
doesn't read yet.

Frames during inference, against the idle `--no-ai` figures from Stage 3:

| | Frame p50 | Frame p99 | Frame max | Over 1 ms late | Processing p50 | p99 |
|---|---|---|---|---|---|---|
| Console in use, model answering | 16.66 ms | 16.72 ms | 17.70 ms | 1 of 1,198 | 0.233 ms | 1.256 ms |
| `--no-ai`, idle (Stage 3) | 16.66 ms | 16.93 ms | 20.13 ms | 6 of 1,940 | 0.312 ms | 1.059 ms |

So no hitch from inference here. This is a light game on the dummy driver, which puts nothing on the GPU. It says
nothing yet about a game really rendering beside the model, which is Stage 5's job.

## Still open

- **A real display.** The GPU contention that matters needs one, and needs a person at the keyboard to judge the
  console itself. The screenshots were drawn on a copy of the frame.
- **Whether the answers are useful.** Two questions prove the path, not the quality.
- **The old sprite requests** are still slow and failing validation, as Stage 1 recorded. The owner's refactor
  covers those.
- **Cancelling while the service starts.** `/cancel` frees the console at once, but the worker keeps
  polling for readiness (up to 120 s) until a stream opens. It's a daemon thread and changes nothing on
  screen, so it's harmless, but it isn't tidy.
- **Text fields.** A game's focused text field can't receive `` ` ``, as the key opens the console. Mouse clicks
  still reach the game while it's open.
