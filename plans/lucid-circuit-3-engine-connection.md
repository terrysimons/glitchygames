# Lucid Circuit, Stage 3: the engine's connection

- **Date:** 2026-11-06
- **Status:** Built and measured on the owner's Mac on branch `worktree-ai-service-ansible`, except as
  listed under "Still open".
- **Master plan:** [lucid-circuit.md](lucid-circuit.md), section 7, Stage 3.

## What this builds

```text
 GameEngine: --ai (on by default), --no-ai
   create_link()    None for --no-ai, --headless, a browser, or no service installed
   AiHostSources    a subclass of HostSources; host.py is unchanged
     pump_events    adds validated AI input, beneath the recorder
   AiLink           one WebSocket, on its own thread, importing websockets only there
```

## How it differs from the master plan as first written

- **`--ai` is a plain game flag, not a registry `Tool`.** The engine refuses two tool flags at once, so a
  default-on tool would have broken every other tool.
- **`--headless` turns AI off.** That one rule covers scripted sessions, golden traces and the tools, so AI
  can't enter a golden or a timing. A later headless AI lab (Stage 10) will have to ask explicitly.
- **The engine starts no agent process.** Agents will live in the sidecar, so the game only holds a socket.
- **A proposal can only be a key press or release for now**, as anything else could quit the game or reach
  the event system's internals. The service sends no proposals until there are agents.

## Evidence (2026-11-06)

**What AI costs a frame.** Real PaddleSlap at 60 FPS with real 27B on the owner's M4 Max, on SDL's dummy
driver, 3 rounds of 12 s each, per-frame times from real recordings. The models were idle: no inference ran.

| Condition | Processing p50 | p95 | p99 | Frame p99 | Frames over 1 ms late |
|---|---|---|---|---|---|
| `--no-ai` | 0.312 ms | 0.533 ms | 1.059 ms | 16.93 ms | 6 of 1940 |
| AI, models loading | 0.338 ms | 0.737 ms | 0.983 ms | 17.10 ms | 14 of 1988 |
| AI, models loaded | 0.368 ms | 0.599 ms | 1.127 ms | 17.02 ms | 10 of 1986 |

About 0.03-0.06 ms at the median, or 0.2-0.3% of a 16.67 ms frame. The rounds varied by about as much as the
conditions did, so treat the small differences as an upper bound, not a precise cost. The few extra late
frames are a real but small signal worth watching.

**Crashes, with the real service:**

- `kill -9` of the API mid-game: the game ran on, and its session came back after 6 s.
- `kill -9` of a model server mid-game: the game ran on, and the model answered again after 2 s.
- `kill -9` of the game: everything stopped 30 s later, with no port left open.

**Replay.** A recording of a run with AI on replayed clean with the service stopped (`Replay matched 691
frames`), and a test proves the same for a proposal: it reaches the scene, is recorded, and replays with
no service.

**No AI, no change.** `host.py` shows no diff. `--no-ai`, `--headless`, a browser and a machine without the
service all build plain `HostSources`, and never import `websockets`, so the golden replays' content hashes
are untouched. 24,534 tests pass at 100% coverage, and no test can reach the real service.

## Still open

- **A real display.** Everything above is on the dummy driver, and PaddleSlap is a light game.
- **Inference during play.** The models were idle. GPU contention is the real risk, and Stage 5's load harness
  is what measures it.
- **A budget.** The owner accepted these figures for prototyping (2026-11-06). A hard frame budget comes with
  Stage 5, from inference numbers on a real display.
- **Two games at once**, which the service's counting handles and its tests cover, hasn't run with real models.
- **A reboot or login.** Nothing should start, as no plist is in `LaunchAgents`, but it's untested.
