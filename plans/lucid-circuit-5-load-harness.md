# Lucid Circuit, Stage 5: finding the sweet spot, and the throttle

- **Date:** 2026-11-06
- **Status:** Agreed by the owner. Being built on branch `worktree-ai-service-ansible`.
- **Master plan:** [lucid-circuit.md](lucid-circuit.md), section 7, Stage 5.

## What this answers

Which Bonsai size should a game use, and how much does each one disturb a game that's really drawing?

The owner has one Mac, the 128 GB M4 Max, and no smaller one (2026-11-06). So this compares all four sizes on
that Mac. Stage 12 keeps the check on real low-end Macs.

| | This Mac can tell us | This Mac can't tell us |
|---|---|---|
| **Answers** | How good each size's answers are, which doesn't depend on the machine | |
| **Memory** | What each size holds, and so which Macs it could fit | How a Mac behaves when it's short of memory |
| **Speed and frames** | How the sizes compare here, and each one's cost beside a game | Absolute speed on a smaller Mac, whose GPU is smaller and has the same game to share with |

No result from this stage may be quoted as a smaller Mac's speed.

## Part 1: choosing a size for a run

(Built. Since 2026-11-07 every run uses 2B unless told otherwise: plans/lucid-circuit.md, section 5.)
`bin/ai-service.sh` always takes the largest size that fits, unless `config/selection.env` says otherwise. Add an
`AI_BONSAI_SIZE` environment override beside the existing `AI_MEMORY_MB` and `AI_FREE_PERCENT`, so a run can pick a
size without changing the machine's settings. It's a change to the Ansible template, so the playbook runs again.

This is also how the owner tries a size by hand: `AI_BONSAI_SIZE=4b uv run paddleslap`, once any running service
has been stopped. The script keeps whatever is already running.

## Part 2: answer quality, no game running

A fixed set of about 20 questions, asked of every size at `reasoning_effort` low, three times each. The states come
from real scenes, saved as JSON, so every size sees exactly the same thing.

| Kind | Example | Scored by |
|---|---|---|
| A fact in the state | How many balls are in play? | Compared with the state |
| A fact that isn't there | What's the rally count, on a screen without one? | Says it doesn't know, invents nothing |
| A small deduction | Which sprite is closest to the ball? | Compared with the state |
| A follow-up | "and where is it?" after an earlier answer | Compared with the state |
| Structured output | Answer in this JSON shape | Parses and validates, as Stage 6's agent loop will need |

Each result records the score, the time to the first token, the total time, the token count, and the answer itself.
The output is a page showing the sizes' answers side by side, because a score can't say whether an answer is useful.

## Part 2b: behaviour tests per game (the owner, 2026-11-07)

Ten questions per game, reviewed by the owner one game at a time, run on 2B at 8K so they also prove the lower bound.
They can be as slow as they need: they test what the AI does, not its speed. Every answer keeps llama-server's prompt
and generated counts, to see whether the context could shrink further. Each question runs as the model sees the game
today, then with each game's rules text, then with game facts, so each addition's worth shows and the model is checked
for saying it doesn't know when it can't.

**Categories,** a question may have several, and each carries how fast its answer goes stale, since an answer arrives
seconds after the frame it describes:

| Category | For |
|---|---|
| Live | Help while playing, worth it only when the answer stays true for several seconds |
| Analysis | Mechanics and strategy, where waiting is fine |
| Base context | Facts loaded once and kept in the cached opening (rules, scoring) |
| Testing | Checking the model: false premises, refusals |
| Performance | Debugging timing and frame cost |
| Visual | The answer is drawn on the overlay (an unreachable platform in red, the best route as a curve) |
| Code | The answer is Python: run freely in a copy of the game, and shown in the console for anything meant for the live game |

**Clockwork Keep, as the owner reviewed it:** floor, lives and score (live, base context); can Tinker reach that
platform, and colour it red if not (analysis, visual); the nearest cog and its worth (live, analysis); when the
elevator arrives (testing: it doesn't move); why Tinker fell through a platform, from the frames and events before it
(analysis); the best route up, drawn as a curve (analysis, visual); scoring (base context); whether the frame-time cap
slows a jump (testing, performance); an extra life, explained as impossible, with a Python draft (code, testing); how
Gear Works differs from the Boiler Room (analysis, base context).

**Built (2026-11-07):** `scripts/ai_behaviour/` (capture snapshots from real recordings, stand-in tools over them,
the 50 questions with checks that work out the expected answers by code, a runner with a tool loop, and
`report.py` for the statistics), tested by `tests/test_ai_behaviour.py`. Snapshots aren't committed: `uv run python
-m scripts.ai_behaviour.capture GAME` writes them. Findings, all on 2B, five passes per question (250 answers a run):

| Run | Passed | Overflows | What changed |
|---|---|---|---|
| 8K, 16 rounds | 118 (47%) | 6 | Up to 16 tool rounds, a nudge 2 before the end, repeated calls answered with a note (8 rounds had left 16 of 150 still exploring) |
| 16K, same code | 109 (44%) | 0 | Only the context; the largest answer used 8,912 tokens |
| 8K, helpful errors | 104 (42%) | 5 | A wrong name gets what does exist |
| 8K, each game's own examples | 123 (49%) | 5 | `read_source`'s examples had been Clockwork Keep's for every game, and 2B copied them |
| 8K, forgiving names | 107 (43%) | 7 | A leading `scene.`, quoted ids, a class with one sprite |

- **The noise is about ±8 points a run,** with near-identical code (104 to 123), so one run can't show a change in
  passes smaller than that; tool error rates are steadier (`read_source` 64% → 34%, `get_sprite` 10% → 3%).
  **Paired runs, built (2026-11-07):** `scripts/ai_behaviour/paired.py` asks every question and repeat of two
  versions (git refs, or the working tree) back to back on one server, in a seeded coin's order, each version in a
  worker process run from its own exported tree; `report.py` adds the pairs that split and McNemar's exact test,
  which only those pairs move. Checked with a short real run on 2B.
- **8K overflows in about 2.4% of answers,** 16K in none, at no measurable cost in answers and about 0.3 GB more
  memory: 8K only where memory forces it.
- **The opening is about 1,800 tokens** (prompt, tools, mechanics): 22% of 8K before the question.
- **Still weak:** visual (20-33%) and code (4-28%); `get_object` still fails about 60% of the time, mostly asking
  for sprites (`ground`, `walls`) as objects.

## Part 3: frames beside a real game

**This waits for [Stage 4b](lucid-circuit-4b-mirror.md), steps 1-3** (the owner, 2026-11-06): the AI will work on a
clone, so the real load is game, clone and model together. The AI load below must include the clone.

Real games on the real display, driven by the existing scripted sessions (`record_scripted_session`,
`PostedPolledInput`), with their existing frame-time summaries. The load comes from a separate process calling the
service's REST API, so the game is exactly what a player runs.

| Setting | Values |
|---|---|
| Games | PaddleSlap, and the busiest other game found by a quick measurement |
| Model | 2B, 4B, 9B, 27B |
| AI load | `--no-ai` (baseline); connected but idle; 25%, 50% and 100% of the time generating |
| Repeats | Three passes, in shuffled order, so warmth and drift don't favour one size |

Each run records frame p50, p95, p99 and maximum, frames over 1 ms late, and processing time, plus the service's
memory and tokens per second. A separate measurement records the wait from launch to the first usable answer,
which is the model load a player would sit through.

**Warning about these games:** pygame draws mostly on the CPU, so these games put little on the GPU beyond presenting
the frame. A clean result here doesn't prove a GPU-heavy game would be safe. The report must say so, and if the
games show nothing, add a deliberately heavy scene before calling it safe.

The Mac has to be otherwise idle, with windows opening on screen, for about two hours (an estimate). It needs nobody
at the keyboard.

## Part 4: the checkpoint

The owner gets the side-by-side page and one table, one row per size: score, time to first token, tokens per second,
memory, and added p99 at each load. The owner then picks the sweet spot. Proposed rule to start from: **the smallest
size whose factual score is within 10% of 27B's, adding under 1 ms to p99 at the load the owner expects.**

The result replaces the guesses in section 5 as far as this Mac can: the default size and the memory each size
needs. The speed figures stay marked as this Mac's.

## Part 5: the throttle, designed from Part 3's numbers

llama.cpp can't pause in the middle of generating, so the possible controls are limited: leave gaps between requests,
limit how many tokens a request may generate, use a smaller batch so each GPU job is shorter, or cancel. Which of
these matter depends on what Part 3 finds, so the design waits for it.

- **If Part 3 shows real hitches:** the engine reports frame lateness over the existing session, the service backs
  off quickly, and it recovers slowly. Tested by forcing load on and off and checking that it doesn't oscillate.
- **If Part 3 shows nothing:** the throttle is a simple budget on requests, plus the heavy-scene check above.

Either way, it has to pass before any game runs an agent without being asked.

## Exit evidence

- The table and side-by-side page above, with the owner's choice of default size recorded.
- Frame figures on a real display against `--no-ai`, for each size and load.
- The throttle tested as above.
- The limits of a single Mac stated beside the results.

## Decisions (the owner, 2026-11-06)

1. **The sweet spot favours both** console questions and what Stage 6's agents will need. Both are scored, and the
   owner weighs them at the checkpoint.
2. **Part 4's rule is the starting point:** the smallest size within 10% of 27B on facts, adding under 1 ms to p99 at
   the expected load. The owner can still overrule it.
3. **Add a smaller-context run for the smaller sizes.** Much of what the small sizes reserve is probably their full
   262K context, which may matter as much as model size on a small Mac.
4. **The owner is asked before the two-hour run** in Part 3.
