# Lucid Circuit: master plan for the GlitchyGames AI platform

- **Date:** 2026-11-06
- **Status:** In progress on branch `worktree-ai-service-ansible` (uncommitted). Built: the Ansible
  setup for the model service and its `.pkg` (`ansible/macos_ai_service.yml`), the service itself, and
  the engine's connection to it (section 7, Stages 0-3).
  Agents and everything after are not built.
- **Source:** the owner's brief, `/Users/terry/Documents/glitchygames-embedding-service-instructions.md`
  ("GlitchyGames AI platform"), plus the owner's decisions in the 2026-11-06 planning session. The
  brief stays the statement of intent; this plan says what to build first, how it connects to the
  engine as it exists, and where it departs from the brief and why.
- **Name:** the owner named this file. In the brief, "Lucid Circuit" names only the feature that
  inspects and changes game internals (Stage 7), not the whole platform. This file covers the
  whole platform, so the name is the project's, not a change to that decision.
- **Sub-plans:** this is the master plan. Each stage gets its own `plans/lucid-circuit-<stage>.md`
  when it starts, linked from here and linking back: [Stage 1](lucid-circuit-1-local-service.md),
  [Stage 3](lucid-circuit-3-engine-connection.md).

## 1. Goal

Every game started through the engine can get AI help without game-specific setup: local models
behind a stable API, agents in their own processes, and proposals applied on the game's main
thread at a safe point in the frame. The live game never waits for AI. The whole local stack
installs on a Mac with a `.pkg` and runs offline once installed.

**Non-goals for now:** hosted routing, subscriptions, Twitch, LiteLLM, HAProxy and nginx. They stay
in the brief as later studies, and nothing built here should need rework to allow them. Only the
API's shape has to stay stable.

**This would be a failure even if it worked:** a game's frame pacing gets worse with AI idle or
off; a recording stops replaying exactly; a player's data leaves the machine without them
choosing it; or a game has to change to keep running without AI.

## 2. Decisions

### Made by the owner

| Decision | Source |
|---|---|
| Build llama.cpp from source at the latest build tag (`b12167` as of 2026-11-06), Metal on | Session |
| Ansible role; per-user launchd service; `.pkg` installer | Session |
| Bonsai 2 sizes 2B, 4B, 9B and 27B, all downloaded, because none is gated | Session |
| Pick a reasonable default from the machine's specs | Session |
| Installs first for the owner, for players later | Session |
| Adopt the exoneris LaunchAgent pattern (section 6), with its defects fixed | Session |
| Wire the existing layers into this architecture | Session |
| **`--ai` is on by default; `--no-ai` turns it off** | Session |
| **No model uses memory until a game loads; sizes are picked then, from the machine's real state** | Session |
| **A model unloads after 30 idle minutes by default, and that's tunable** | Session |
| **Models load when the game loads** (not on first use) | Session |
| **Bonsai runs at its full 262K context with no separate output cap. A Mac it doesn't fit gets no AI for now**, not a smaller context. Measured with the game's 2 GB left free, that rules out 8 GB Macs, and 16 GB ones under memory pressure | Session |
| **Timeouts stay as they are for now** (900 s in the service, 600 s in the client), which caps a request at about 20,000 tokens on 27B. Revisit with Stage 5's throttle | Session |
| **`httpx2` everywhere** in place of `httpx` (done for the engine and the service) | Session |
| **`aisuite` is removed. AI requests go to the local service only for now**, through one client protocol (`glitchygames.ai.local_service`), so cloud can join later as a second implementation. Cloud isn't a focus yet | Session |
| **The old AI code (Bitmappy's worker, the voice assistant, the sprite service and `glitchygames.api`) gets refactored after the general architecture is in place.** Its tests were adapted to the new client, and none needed an xfail. Coverage **must be at 100% before anything is pushed** | Session |
| **The AI service ships its own sidecar Python in its package directory, as a plain folder. The engine is fully decoupled from it: a WebSocket for the live link, REST for everything else** | Session |
| **The existing wrapper is frozen: it's on every game, it's optimized, and it must not change** (section 4) | Session |
| Two model roles: Qwen3-Embedding and Bonsai 2 | Brief |
| Agents never run in the game's process or on its main thread | Brief |

### Recommended, awaiting the owner (section 3 and section 10)

Each row in section 3 that departs from the brief is a recommendation until the owner confirms it.

## 3. Where the brief, the session and the code disagree

| # | The brief says | What's actually true | Recommendation |
|---|---|---|---|
| 1 | Ship weights inside the `.pkg`, stored in Git LFS | The owner chose downloading. GitHub LFS rejects files over 2 GB on Free and Pro (5 GB at most on any plan), so `9b` (2.56 GB) and `27b` (7.63 GB) can't go in unsplit. `git lfs` isn't installed here, and this checkout is in Dropbox, which would sync the weights | Download from pinned revisions with SHA-256 checks. "Offline" means it runs offline once installed. No LFS. Keep the manifest fields (brief section 9) |
| 2 | Admin-owned files in `/Library/...`, agents in `/Library/LaunchAgents` | The owner asked for a service that "installs as the user" | Per-user install, no root, using the brief's `~/Library/...` paths (section 6). An all-users install can come later if players need it |
| 3 | A thin wrapper hosts AI hooks and is wrapped around each game | **`GameHost` is the wrapper, it's on every game, and it's frozen (owner, 2026-11-06).** All 12 game and demo entry points run `GameEngine(game=...)`, which builds a `GameHost` for live runs. The brief's "deferred instantiation" is in `GameEngine` (`game_engine.py:3687`). Its diagram's scene wrapping doesn't exist: no branch has a wrapper scene, and none is needed | Change nothing in `host.py`. AI is a subclass of `HostSources`, in the host's layer (section 4) |
| 4 | Every wrapped game inherits AI | True only for desktop live runs: `GameEngine.host` is None in a replay, and a browser can't start processes (`AI_FEATURES_ENABLED`, `RESTARTS_AVAILABLE`) **On by default, `--no-ai` to turn it off (owner, 2026-11-06).** Never in replays or browsers, whatever the flag says. Tests and the tools that record goldens run with it off (section 4). With `--no-ai`, no worker starts, no AI module loads and no per-frame call is added |
| 5 | Startup indexes each game's TOML sprites, song notation and waveforms | `clockwork-keep`, `mr-muncher` and `paddleslap` have no sprite files; Brave Adventurer Papyrus has 5 and `drawing-fire` 1. Bitmappy has 71. **No game has a sound file in TOML, and no game uses the new `audio.sound()` API**: their sounds are Python recipes, numpy code or two WAVs. Note strings parse (`audio/spec.py`), but a song format is M5, not built | Index what exists and report the rest as "no assets". For code-drawn games the useful index is their capability catalog (Stage 7). Build a game's asset inventory before writing any experiment |
| 6 | A mandatory engine loading scene before play | A pre-game scene would be recorded and shift frame numbers | Index in the background, so games show nothing. A game that needs indexing to finish first shows its own loading scene, built on a shared one, as an opt-in |
| 7 | Audit an 11-way frame-capture matrix, including GPU readback | The engine draws to a CPU surface (`LayeredDirty`), and `SCALED` only adds a renderer for presenting. GPU readback, front/back buffers and shared textures don't apply to the frame the game draws. `FrameStream` (`replay/tools/compare.py`) already sends frames to another process | Shorten the audit to CPU options: a pooled shared-memory ring, downscaled copies and existing `tobytes`. Measure against `FrameStream` as the baseline. Note the rest as not applicable, with this reason. The game draws in place on the display surface, so a thread reading it would tear. `end_frame` should read frame N just after it's presented, with shake and overlays restored off the surface. Measured at 1080p (microbenchmark, GIL and contention not covered): a pooled blit takes about 0.17 ms and a shared-memory copy about 0.10 ms, against 1.3 ms for `tobytes`, so `FrameStream`'s method isn't the one to reuse |
| 8 | Replay can step to any frame; a headless mirror follows live play | No state snapshots exist (`plans/future-work.md` lists them as a follow-up). Going back means rebuilding from the start in a new process (`--replay-pause-at-frame`). Recordings do flush line by line, but the reader always starts at byte 0 and nothing waits at the end of a growing file. Replays compare sprites and recorded events, **not pixels or other game state**, so "exact" can't mean identical pixels today. No shipped game enables instant replay | Start with a recent-frames ring. Treat checkpoints as their own project, shared with rollback and step-back. Mirror and branching wait for them. Headless replay is fast (PaddleSlap's golden ran at least 26x real time; one light game, one run), so rebuilding may be practical for short games |
| 9 | A future TTS path and speech via whisper.cpp | `audio/tts.py` and `audio/voice_assistant.py` (used by Brave Adventurer Classic) already exist, but the assistant and `events/voice.py` (used by Bitmappy) send microphone audio to Google (`recognize_google`), and the assistant's default AI provider is remote | Reuse the pipeline and speaker path; replace its speech and AI calls with the local API in Stage 11. **Offline and privacy rules don't hold until then** |
| 10 | A new FastAPI service | `glitchygames.api` already exists for sprite generation (`glitchygames-server`), but nothing except its own tests uses it. It has `allow_origins=['*']` and no authentication on any route. `fastapi`, `uvicorn`, `httpx` and `aisuite` (with 14 provider extras) are core engine dependencies, so anything depending on the engine inherits them all (347 MB against 18 MB, measured) | **The service is its own project with its own sidecar environment, sharing no code with the engine** (owner, section 4). Bring over `glitchygames.api`'s sprite routes only if they're still wanted, and fix its CORS setting first |
| 11 | Native tool calling, verified per model | Prism lists malformed and looping tool calls as open, and its tool-calling score is 74.92. Its template also needs exactly one leading system message and rejects `reasoning_effort: "high"` | Default to JSON-schema-constrained plans, with an adapter handling those template rules. Try native tool calls later as a measured option |
| 12 | Numeric RAM thresholds only after measuring | Prism publishes no memory figures | The session's tiers (section 5) are provisional defaults, replaced in Stage 0 and Stage 5 by measurements |
| 13 | Apache 2.0 for Qwen, to verify | Card metadata says `apache-2.0`, but neither the GGUF repositories nor `Qwen3-Embedding-0.6B` has a LICENSE file (404), and the card's text calls the model "proprietary" | Treat as a release blocker for players, not for the owner's own use. Record the evidence and ask a lawyer before shipping to players |

The brief's filename says "embedding service", but its content is the whole AI platform. This plan
follows the content.

## 4. The architecture, built on what exists

```text
 Game process (never waits)                 Agent process (one small pool)
 +--------------------------------+         +---------------------------+
 | GameHost: the wrapper (FROZEN) |         | The sidecar's own Python  |
 | AiHostSources(HostSources):    |<------->|   agents                  |
 |   pump_events: AI input        | a socket|   retrieval, planning     |
 |   end_frame: drain, observe    | only    |   typed API client        |
 | beneath the recorder           |         +-------------+-------------+
 +--------------------------------+                       | HTTP (async), token
                                                          v
 launchd (per user)         +------------------------------------------+
   ai.glitchygames.api ---> | API: /v1, /health, /docs (Scalar offline)|
   ...bonsai-2-<size>       +----------+-------------------+-----------+
   ...qwen3-embedding-<size>           v                   v
                              llama-server (Metal)   llama-server (Metal)
                              Bonsai 2 + vision      Qwen3-Embedding
```

### The frozen wrapper

**`GameHost` is the wrapper: the layer that can do things around the game. `src/glitchygames/host.py`
doesn't change (owner, 2026-11-06).** It's a plain class with no base class, for live runs only.

**AI lives in that layer as a new subclass, `AiHostSources(HostSources)`, in `glitchygames/ai/`.** Its
hooks are the doors `HostSources` already forwards. By default `GameEngine.__init__` builds it where it
now builds `HostSources` (`game_engine.py:1397`); with `--no-ai` it builds `HostSources` as today, so
that path adds no code to any frame. A replay has no host, so it never runs.

**What "on by default" has to mean (proposed; Stage 3 proves it):**

| Situation | Behaviour |
|---|---|
| A live game, service installed | As the game loads, `bin/ai-service.sh start` picks sizes from physical and free memory and starts them, without the frame loop waiting. The worker proposes nothing until something asks: the console, or a game that enables an agent |
| Not enough memory free | `ai-service.sh` reports it and starts nothing; the game plays on with AI unavailable |
| AI idle during play | The model unloads after 30 minutes (down to about 150 MiB) and reloads on the next request, in seconds |
| The last game exits | Its WebSocket closes, and 30 s later the service stops the models and itself. It counts sessions, so one game leaving doesn't take the models from another, and a crashed game's socket closes the same way |
| A live game, service not installed | Runs normally. A single check at startup, one log line, no worker, no retries during play |
| Service dies during play | The game carries on; AI reports unavailable |
| Replay, audit, rebaseline | No host, so no AI. The option is replay-local, so a recording's stored value is ignored |
| Browser | Off, like `AI_FEATURES_ENABLED`: a browser can't start processes |
| `--record-golden-trace`, `--record-session`, `verify`, `measure` | Forced off, so AI can never enter a golden or a timing |
| The test suite | Off through the test harness; only AI's own tests turn it on |

**The cost that default-on adds:** every ordinary launch now runs `AiHostSources` and starts a process,
including for players who never use AI. Its per-frame cost when idle must be measured against
`--no-ai` in the run ledger. That number is an acceptance test for Stage 3, and exceeding the budget
blocks the stage.

Probed on real Bitmappy, headless, for 4 frames, with the subclass swapped in from outside the repo: a
key press added in `pump_events` reached `BitmapEditorScene`, was recorded `origin: external`, and plain
`bitmappy --replay-trace` then matched with no subclass present.

AI only *uses* what they already offer:

| Existing extension point | What AI does with it | Precedent |
|---|---|---|
| `HostSources.pump_events` | Adds proposals as input events, once per pump. It sits beneath the recorder, so they're recorded and a replay serves them with no AI, no model and no worker | `without_window_recreation_bursts` already edits batches here; probed above |
| `HostSources.end_frame` | Bounded result drain and observation capture, after the frame is presented. Receives the scene, frame number and dt | Runs after `_present_frame`, so this is the first point frame N is complete (read from the code, not yet tested) |
| `HostSources.input_snapshot` | For games that poll input (Drawing Fire): posted events don't change polled state, so AI input has to be laid over the snapshot here | `PostedPolledInput` does the same for scripted sessions |
| `HostSources.draws_overlay`, `draw_overlay` | AI status drawn over the presented frame, never recorded. **`draws_overlay` being true costs a full screen copy and flip each frame**, so it must be true only while something is showing | The `--compare-trace` ghost |
| `registry.TOOLS` | Puts `--ai` and `--no-ai` on every game's command line. **It only parses the option**; `GameEngine` reads it to choose the subclass | Every tool flag already works this way |

**To prove in Stage 3:** the same behaviour while a game is paused, in transitions and in a playback
scope (where other doors are pushed on top), `draws_overlay` changing during a run, and real frame
costs. Proposals are held while a playback scope plays.

Rejected: a `SceneManager` supervisor (it runs before drawing, so it sees only the previous frame, and
it isn't the layer the owner named; it stays available for frame-exact supervisor actions); a
`game_handler` that builds a second engine (it loses what `main()` does around the engine, such as
Bitmappy's icon and training-data load); and per-game calls from `setup()` (every game would have to
opt in).

**Needs the owner's approval first:** a control event of a new kind diverges in a replay unless that kind
is in `REAPPLIED_CONTROL_EVENT_KINDS` (only `breakpoint` today) with a handler registered both live
and in replay. So Stage 7's direct field writes need that change. Prefer posted input and game events
the game already handles, and ask for this only if they prove too limiting.

### Existing layers and how each is wired in

| Existing layer | Role in this platform | Change needed |
|---|---|---|
| `GameHost`, `HostSources`, `TickPacer` (`host.py`) | The wrapper | **None. Frozen** |
| `GameEngine.__init__` (`game_engine.py:1397`) | Builds the host's doors | Builds `AiHostSources` by default, `HostSources` with `--no-ai` |
| `Supervisor`, `post_input_event`, control events | Not the main path. Available for actions that need the supervisor slot | None |
| `SceneManager.in_playback_scope`, `Scene.debug_subject` | Demos, instant replay and pause | The session holds proposals during a scope, and reads the paused game through `debug_subject` |
| `process.py` (`start_command`, `stop_command`) | The engine's one subprocess launcher, with reaping | Runs `ai-service.sh start` as the game loads, if the service is installed. Agents run in the sidecar, so the engine starts no Python worker of its own |
| Crash boundary and teardown (`game_engine.py`) | Stops and reaps on every exit path | A worker exits on its own when its socket to the game closes, so a crash or a kill can't strand one and teardown needs no change. AI failure never changes the game's exit code |
| `ContextSlot` (`engine_context.py`) | One state per running game; the Arcade runs several | The session is a slot, with an isolation check in `ISOLATION_CHECKS` |
| `glitchygames.clock`, `random_stream` | Replay-safe time and randomness | Deadlines use `clock.elapsed_seconds`, not `time`. Anything measured stays diagnostic |
| `FrameStream` (`replay/tools/compare.py`) | Sends frames to another process today | Baseline for Stage 8. Its `tobytes` copy is too slow for the live game (section 3, row 7) |
| `instant_replay.py`, `playback.py`, `ghosts.py` | In-memory frame journal and isolated playback | First source of "what just happened?" context (Stage 9) |
| `--headless`, `record_scripted_session`, `PostedPolledInput` | Real games driven by repeatable input, live | The load harness (Stage 5) is built on these, not a new runner |
| `processing_seconds`, `RunSummary`, the run ledger, `report` | Per-frame timing with percentiles, already recorded | Compare AI off against AI on with these. New measurement goes in the same format |
| `registry.TOOLS`, `[tool.glitchygames]` | One definition per tool, on both front ends | `--ai` and `glitchygames ai-status` etc. are `Tool`s. Their settings go in the same table |
| `glitchygames.api` (`routes`, `client.py`, `services/`) | Existing FastAPI app, HTTP client and sprite service; used only by their own tests | The service is a new member (row 10, section 3). `SpriteGenerationService` can target the local API through its `aisuite` config if it's kept |
| `src/apps/bitmappy` `ai_manager.py`, `ai_worker.py` | A working separate AI process, with `AI_MODEL` hardcoded to a remote provider | First real client: a setting that points it at local Bonsai. Its worker lessons move into the engine's pool, and it adopts that pool last |
| `audio/voice_assistant.py`, `audio/tts.py`, `controller_audio.py`, `events/voice.py` | Push-to-talk to speaker pipeline, on threads in the game process | Stage 11: speech and AI move behind the API. The threads leave the game process |
| `debug/overlay.py`, `debug/panels.py` | F3/F4 panels, including Audio built from a snapshot | Add an AI panel: requests, budget, throttle reason |
| `ui/text_widgets.py`, `ui/inputs.py`, `MessageScreen` | Text and input widgets | The `/`-command console is built from these. Focus handling comes from `active` |
| `state.open_saves` | Saves, sandboxed in replays | Persists glitch state and history, so replays stay safe by default |
| `testing/sprite_files.py`, `SpriteFactory`, `audio/assets.py`, `render_to_file`, `renderer_service.py` | Real parsers, renderers and offline audio | The preview-first pipeline validates with these, off the frame loop |
| `ansible/`, `scripts/check_licenses.py`, `scripts/generate_sbom.py`, `nox -s security-scan` | Deployment and license checks | Role goes in `ansible/roles/`. Model manifest and notices extend the existing license and SBOM checks |
| `bitmappy.spec`, `packaging/`, `src/quicklook/` | PyInstaller and Mac app packaging precedents. No `codesign`, `productbuild` or notarization anywhere yet | The installer is new work |

### Where the code goes

- **`src/glitchygames/ai/`** (engine): `AiHostSources` and the socket client, nothing else. It imports no
  service code and knows only the wire protocol, so a game runs unchanged with the service absent.
- **The AI service, its own project with its own `pyproject.toml` and lock file, outside the uv
  workspace** (proposed: `services/ai-service/`): the API, the agents, llama.cpp adapters and Scalar
  assets. Outside the workspace, the rule that every member depends on the engine doesn't apply, and no
  guard needs an exception. It needs its own test, lint, license and SBOM runs.
- **The sidecar environment** (proposed: `~/Library/Application Support/GlitchyGames/AI/sidecar/`): a
  standalone CPython and the service's packages, in the service's package directory. Tested 2026-11-06
  by moving one to another folder: a venv failed to run, because it points at its Python by absolute
  path, and every player's home differs. A bundled Python with packages in a plain folder used nothing
  outside itself and served a request in 0.53 s (about 88 MB on disk, 62 MiB running). **Plain folder,
  the owner's choice.**
- **`ansible/roles/llama_cpp/`** and **`packaging/macos/`**: build, install, `.pkg`.
- **Models live outside the repository**, never under this Dropbox checkout. So does the llama.cpp
  build tree.

### Engine rules this has to follow

- A replay of a recording made with AI on must match with no service running. "Match" means what a
  replay compares today: scene class, sprite rect, visibility and draw order, and recorded events.
- A direct state change that isn't recorded either diverges or goes undetected, so it's never allowed.
- A console sprite in `all_sprites` would appear in the sprite comparison, and games that poll input
  (Drawing Fire) still act on typed keys. Stage 4 has to handle both.
- `tests/test_engine_doors.py`: no `time`, direct polling or direct `pygame.event` use outside the doors.
- 100% coverage. Hardware, network and the model server are the only things tests may fake; the
  fake server is a real local HTTP process.
- Data classes are frozen pydantic models. Keyword arguments. Exit codes from `ExitCode`.
- The wrapper is frozen: `host.py` shows no diff, and with AI off frame timings match today's in the
  run ledger. With AI off, every golden replay's content hashes stay the same. These are the
  first acceptance tests.
- Measure what the main thread pays with AI on and idle. Numbers set the budget; the brief gives none.

## 5. Models and runtime

**Runtime:** stock llama.cpp `b12167` (commit `240d68fc`, MIT), `-DGGML_METAL=ON
-DGGML_METAL_EMBED_LIBRARY=ON`. llama.cpp has no MLX backend, so MLX isn't part of this. The role
pins the tag and checks its commit; a newer tag is a deliberate update, with the smoke test re-run.

| Model | Revision | File | Bytes | SHA-256 starts |
|---|---|---|---|---|
| Bonsai 2 2B | `a6032a50` | `Ternary-Bonsai-2-2B-Q2_0.gguf` | 546689504 | `c2893fa6` |
| | | `Ternary-Bonsai-2-2B-mmproj-Q8_0.gguf` | 364664352 | `ac9934e8` |
| Bonsai 2 4B | `50ebba61` | `Ternary-Bonsai-2-4B-Q2_0.gguf` | 1212103520 | `64a5183b` |
| | | `Ternary-Bonsai-2-4B-mmproj-Q8_0.gguf` | 366894624 | `db939d5f` |
| Bonsai 2 9B | `82265ccc` | `Ternary-Bonsai-2-9B-Q2_0.gguf` | 2556640128 | `1f884aa5` |
| | | `Ternary-Bonsai-2-9B-mmproj-Q8_0.gguf` | 624229664 | `e0cb6f69` |
| Bonsai 2 27B | `839bd570` | `Ternary-Bonsai-2-27B-Q2_0.gguf` | 7626008928 | `4f99aed0` |
| | | `Ternary-Bonsai-2-27B-mmproj-Q8_0.gguf` | 629246976 | `6807ede6` |
| Qwen3-Embedding 0.6B (Compact) | `370f27d7` | `Qwen3-Embedding-0.6B-Q8_0.gguf` | 639150592 | `06507c7b` |
| Qwen3-Embedding 4B (Standard) | `f4602530` | `Qwen3-Embedding-4B-Q8_0.gguf` | 4279660224 | `b60ae5ce` |
| Qwen3-Embedding 8B (Extended) | `69d0e58a` | `Qwen3-Embedding-8B-Q8_0.gguf` | 8047105824 | `d20ddc71` |

The Bonsai files are the same bytes as Ollama's `bonsai-2:<size>` tags (their digests match). Why
`Q2_0`: it's the only compact packing stock llama.cpp runs. The role's manifest holds full hashes
and full revisions, read from the Hub API at implementation time.

**Download size:** Bonsai 13.93 GB; with Compact Qwen 14.57 GB; with all three Qwen 26.89 GB.
Recommended: all four Bonsai and Compact Qwen on the owner's Mac. Whether players get all four is
open (section 10).

**Picking a model (`bin/ai-service.sh`).** Nothing is picked at install. When a game loads, the script
takes the largest size that the physical-memory table below allows, that's downloaded, and whose
reserved memory plus Qwen's fits in free memory (`kern.memorystatus_level`) less 2 GB for the game. If
none fits, AI is unavailable for that run. Tested with faked figures: 128 GB with 12% free picks 9B, and
with 3% free picks nothing. A hand-picked size goes in `config/selection.env`.

**Physical-memory ceilings (provisional).** Reserved memory and speed were measured on the owner's M4 Max
(128 GB) at `b12167` on 2026-11-06, with every layer on Metal and `graph splits = 1`. Reserved memory
is llama.cpp's reported buffers, mapped weights included, with Bonsai at its full 262K context (the
owner's choice, with no separate output cap) and Qwen's at 8192; it leaves out
the vision file until an image loads it. Speed is one short answer, so it's only a rough guide, and
other Macs will differ. The tiers are still guesses until they're run with a game on smaller Macs.

| Memory | Bonsai 2 | Qwen3-Embedding | Reserved, both | Bonsai decode |
|---|---|---|---|---|
| Under 16 GB | 2B | 0.6B | 6.5 GB | 239 tok/s |
| 16-23 GB | 4B | 0.6B | 12.8 GB | 141 tok/s |
| 24-31 GB | 9B | 0.6B | 13.9 GB | 98 tok/s |
| 32 GB or more | 27B | 0.6B | 26.7 GB | 39 tok/s |

Intel Macs are refused. The owner can always override. A larger Qwen needs its own index (brief:
identical dimensions don't make indexes compatible), so it's never picked automatically after the
first index exists. Selection also reads memory pressure before each load, not only total memory.

**Server settings to start from:** Bonsai `--gpu-layers 99 --flash-attn on --ctx-size 65536
--n-predict 16384 --parallel 1`, default `reasoning_effort: "medium"`, Prism's 27B values applied to
every size until measured. `--cache-ram` is set well below Prism's 24 GiB, because a game and Qwen
share the same memory. Qwen `--embedding --pooling last -ub 8192 --ctx-size 8192`, instructions
applied once on the query side (left to default, its context reserved 3.6 GB). Checking vectors and
dimension reduction against the reference implementation is still to do.

**Reality check on speed:** Prism measured 47 tok/s on an M5 Max and 18 tok/s on an M4 Pro, with the
fork's `PQ2_0` file and an earlier build. This model reasons at length before it answers, so a
reply can take many seconds to minutes. Agents plan over longer horizons and hand ordinary game
code the urgent decisions, as the brief says.

## 6. Service and installer

| Item | Value |
|---|---|
| Labels | `ai.glitchygames.api`, `ai.glitchygames.bonsai-2-<size>.llama-cpp`, `ai.glitchygames.qwen3-embedding-<size>.llama-cpp`. `glitchygames.ai` is a domain the project holds; this replaces the session's `com.glitchygames.*` |
| Plists | `~/Library/Application Support/GlitchyGames/AI/agents/`, **not** `~/Library/LaunchAgents/`, where launchd would load them at every login. `launchctl bootstrap` by path starts one, and `bootout` stops it |
| Binaries, models, manifests, notices | `~/Library/Application Support/GlitchyGames/AI/` (versioned, so rollback works) |
| Settings | Same directory, `.env` then `.env.runtime` |
| Logs | `~/Library/Logs/GlitchyGames/AI/`. Rotation isn't built yet |
| API port | `127.0.0.1:11449`, public to local clients |
| Worker ports | Bonsai `11450`-`11453`, Qwen `11454`-`11456`: private. Avoids Ollama's `11434` and exoneris's `11435`, `11437`, `11439` and `11440`. Checked at install; a conflict is reported, and no other process is ever killed |
| Running | Nothing until a game loads, then one Bonsai and one Qwen, which settles the session's open question and matches the brief's one resident Qwen. The game never sees a port |
| Unloading | `llama-server --sleep-idle-seconds`, 1800 by default: `ai_service_sleep_idle_seconds`, or `AI_SLEEP_IDLE_SECONDS` in a model's `.env.runtime` |
| Auth | A locally generated token in a `0600` file. Loopback alone isn't authentication. CORS restricted |

**Kept from exoneris's agents:** one agent per model with a backend-named label, `RunAtLoad`, restart on
failure, `ThrottleInterval` 10, `ExitTimeOut` 30, `NumberOfFiles` 65536, layered settings, a clear
message on bad settings, `--alias`, `--parallel`, `--mmproj`.

**Fixed from them:** the shell script is a file, not XML inside the plist (raw `&&` made all four
installed plists invalid); `plutil -lint` validates before install; `127.0.0.1` not `0.0.0.0`;
`launchctl bootstrap`, not `load`; no `UserName` or hardcoded home paths; bad settings exit 0, as
launchd would otherwise restart the job forever; no speculative-decoding block (Prism: `ngram` has no
effect, and its drafters need the fork).

**Ansible (built):** `ansible/macos_ai_service.yml`, `hosts: macos`, run through `uvx --from
ansible-core` like the Pi playbook. Every directory, download and agent comes from it. It doesn't
install Xcode or CMake, only checks for them. Ansible runs only where the package is built; players
never need it.

| Role | What it does |
|---|---|
| `llama_cpp` | Checks arm64 and the SDK, clones the tag, refuses a moved commit, builds `llama-server` with no web UI or OpenSSL, and checks for Metal and no Homebrew libraries |
| `ai_models` | Checks disk space, then downloads with `curl` to `FILE.part`, resuming, and only names a file once its SHA-256 matches. `curl`, because Python's downloader hangs for minutes on a network whose IPv6 doesn't reach the CDN |
| `ai_service` | Generates the key, installs validated plists, settings and `ai-service.sh`, starts what this machine would pick, asks questions with known answers, and stops it all again, so an install leaves nothing running |
| `ai_package` | Renders the package's scripts from the same variables, builds the `.pkg`, and fails if a model got into it |
| `ai_validate` | Only when asked: checks every model in its own temporary server, with speed, memory and GPU evidence |
| `ai_uninstall` | Only when asked: removes the service, keeping models unless told otherwise |

**`.pkg` (built, unsigned):** `productbuild` with the "only for me" domain, 6.3 MB. `installer -target
CurrentUserHomeDirectory` installed it as uid 501 with no root, and `postinstall` could run
`launchctl`. Payload: `llama-server`, plists, settings templates, notices, `setup.sh`, the uninstaller.
No weights, so the installer can't hang on a download: a one-shot launchd job downloads the default
models with resume and hash checks, readies the agents without starting them, then removes itself.
A player's Mac has only those models, and `ai-service.sh` can pick only what's there. There's no download
progress or consent yet (Stage 12), and the service's Python and Scalar assets join once the API
exists. Signing needs Developer ID Application and Installer certificates (this Mac has none) and
`notarytool`.

**Licenses:** ship `LICENSE`, `NOTICE.txt` per Bonsai size (each names its Qwen base), llama.cpp's MIT
notice, and `THIRD_PARTY_NOTICES`. Packaging fails on missing evidence. Scalar's `scalar-fastapi` (MIT)
defaults to a CDN, and its docs suggest a remote proxy: pin the JS locally with `scalar_js_url`,
leave the proxy empty, and test with the network off.

## 7. Stages

Each stage ends with evidence, gets a sub-plan when it starts, and can stop there. The order puts a
small end-to-end result first, and proves frame safety before AI is on by default.

| # | Stage | Exit evidence |
|---|---|---|
| 0 | **Measure first** (done, through `ai_validate`, except the reference check) | On this Mac at `b12167`: all four Bonsai sizes answered text and image questions correctly on Metal, with all layers on the GPU and `graph splits = 1`, so the `MUL_MAT_HADAMARD` concern didn't bite. Memory figures are in section 5. **Not done:** comparing Qwen's vectors with the reference implementation (only shape, norms and a similarity check so far) |
| 1 | **Local service** ([sub-plan](lucid-circuit-1-local-service.md)) | **Done:** roles install and rerun cleanly; all the REST routes and the WebSocket, with real models; Scalar with the network blocked; everything stops when the last game leaves. **Not done:** agents surviving a crash and a reboot; the service in CI, the SBOM and the license check |
| 2 | **Installer (owner)** | Unsigned `.pkg` installs and uninstalls with no root as the owner, its setup job downloads what's missing and starts nothing, and the picker was tried against faked memory figures by hand (**done**). **Not done:** a second user account with no developer tools; an automated test of the picker |
| 3 | **Engine connection** ([sub-plan](lucid-circuit-3-engine-connection.md)) | **Done:** no diff in `host.py`; a default run connects, and a run with no service plays normally; a proposal reaches the scene, is recorded, and replays with no service; crashes of the API, a model or the game all recover. Idle cost about 0.03-0.06 ms a frame on the dummy driver. **Not done:** a real display; a budget for that figure, which the owner decides |
| 4 | **First playable: read-only** | In one real game (proposed: PaddleSlap), `/ask` and `/inspect` in a console, with an AI debug panel and history. Bitmappy can use local Bonsai through a setting |
| 5 | **Load harness and throttle** | Scripted sessions at fixed AI loads; p50/p95/p99 frame times against AI off, on the owner's Mac and at least one smaller Mac. Real numbers replace section 5's tiers. Throttle backs off fast and recovers without oscillating. Must pass before any game runs an agent without being asked |
| 6 | **Retrieval and agent loop** | Asset and capability index with versioned model identity; dense + BM25 + filters; a bounded agent loop that retrieves, plans in JSON, validates and stops on budget |
| 7 | **Lucid Circuit** | Capability discovery on unannotated classes without running properties; validated field edits and one composed behaviour nobody wrote a command for, in two games; restoration tested; glitch manifest and `/augment`, `/undo`, `/glitch` |
| 8 | **Frame context and vision** | CPU capture audit with numbers; sampled frames to Bonsai with bounded frame age and no hitches beyond budget; capture off is the fallback |
| 9 | **Recent history** | Interesting-event markers, before/after windows, the contact-sheet comparison against single and multiple images, using the journal and ring |
| 10 | **Checkpoints and headless lab** | State snapshots (own design, shared with step-back and rollback); then reset/step/observe episodes, branch experiments, mirror study |
| 11 | **Local speech** | whisper.cpp behind the API; `voice_assistant.py` moved onto it; nothing leaves the machine; push-to-talk first; voice debugger |
| 12 | **Players' release** | Signed and notarized; license review done; tiers measured on real low-end Macs; download consent; clean-machine, upgrade, rollback and uninstall tests |
| Later | Creative lab experiments run from Stage 6 on as content allows. Twitch, LiteLLM/HAProxy/nginx, `glitchygames.ai` and subscriptions stay as the brief's studies, each gated by evidence from earlier stages | |

## 8. Risks

| Risk | Consequence | Handling |
|---|---|---|
| Bonsai isn't fast or reliable enough for interesting behaviour on ordinary Macs | The feature's appeal shrinks to slow, high-end use | Stage 0 and Stage 4 answer this early and cheaply. Stage 5's smaller Mac is the real test |
| GPU contention hurts the game even with perfect process isolation | Frame hitches on Macs where both share a GPU | Stage 5 throttle. Long kernels can't be pre-empted, so cap work unit size |
| Runtime patching and reversal is unreliable in Python | Hard-to-undo changes, broken saves | Prefer declared capabilities. Patches are a labelled experiment, off by default |
| AI-written proposals act on prompt-injected content (Twitch, assets, retrieved text) | Unwanted game changes | Proposals are data, validated on the main thread against an allowlist. No code execution |
| An upgrade breaks correct output silently (older builds give gibberish without errors) | Silent garbage | Smoke test checks answers; every tag change repeats it |
| A brief this large never finishes | Effort spreads across research with nothing usable | Stages stop independently; each one delivers something. Stage 4 is the first decision point |

## 9. Not verified yet

**Measured 2026-11-06, for the old-AI refactor:** three real sprite requests through the sprite service
with 27B on the owner's M4 Max all failed validation, at 148-292 s each. Two returned nothing, each using
exactly the service's 8192-token limit on reasoning. The third took 4832 tokens and was nearly right, with
one row of a 16-wide sprite 17 wide. A larger limit, a lower `reasoning_effort` and repairing near-miss rows
are the first things to try. Three samples prove little about quality. Bitmappy asks for 64000 tokens, so it
shouldn't hit this limit, but could take much longer; it wasn't run.

- Behaviour after a reboot or login, including that nothing starts.
- How far free memory (`kern.memorystatus_level`) predicts what a model can really use under pressure.
- What loading a model at game start costs the game's frames (Stage 3).
- Installing on another Mac or account; downloaded-package Gatekeeper behaviour; any Mac but this one.
- Long reasoning: every measured answer so far is a one-line question.
- Notarization's size limits (I couldn't find a source; a 6.3 MB package makes this unlikely to matter).
- Dimension reduction through `llama-server`.
- Qwen's redistribution terms beyond its card metadata.
- Frame costs: nothing in section 7's budgets has a number until measured.

## 10. Questions for the owner

Most important first. Each has a default this plan uses until told otherwise.

1. **The wrapper.** Resolved 2026-11-06: `GameHost` stays exactly as it is, and it's the layer that
   does things around the game, so AI is a `HostSources` subclass (section 4).
2. **First destination.** Is Stage 4 (ask and inspect, read-only, in a real game) the right first
   milestone, and PaddleSlap the right game? Default: yes.
3. **Downloads over bundled weights.** Does "offline" mean running offline once installed? The brief
   says it ships in the installer with LFS; the session says download. Default: download.
4. **Per-user or all-users.** Confirm per-user, no root, over the brief's `/Library` layout. Default:
   per-user.
5. **Default-on behaviour.** Resolved 2026-11-06: `--ai` is on by default and `--no-ai` turns it off.
   Still to confirm: "on" starts an idle worker and makes no model requests until asked (section 4).
   Default: yes.
6. **Which models players get.** All four Bonsai sizes (13.93 GB) or just their default, with others
   on request? Doesn't block the owner's install. Default: just the default, for players.
7. **The socket.** Resolved 2026-11-06: both, on one port. A WebSocket for the live game link, as agents
   have to push proposals and cancellations without the game polling, and REST for models, status and
   docs, as OpenAPI and Scalar document only REST. The WebSocket checks the token and `Origin`, and
   exchanges a protocol version on connect. `glitchygames.api` stays where it is for now.
8. **Label prefix.** `ai.glitchygames.*`, or `games.glitchy.*`? Default: `ai.glitchygames.*`.

## 11. References

- [Bonsai 2 27B GGUF](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf) and its
  [known issues](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/blob/main/KNOWN_ISSUES.md)
- [Prism ML docs](https://docs.prismml.com/models/bonsai-2-27b),
  [Bonsai demo](https://github.com/PrismML-Eng/Bonsai-demo)
- [Qwen3-Embedding 0.6B GGUF](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF)
- [llama.cpp build docs](https://github.com/ggml-org/llama.cpp/blob/b12167/docs/build.md)
- [GitHub LFS limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage)
- [Scalar FastAPI integration](https://scalar.com/products/api-references/integrations/fastapi)
- `plans/2026-10-23-game-host-and-browser-runner.md` (the host), `plans/future-work.md` (snapshots,
  cheat device), `plans/2026-10-23-arcade-showcase.md` (several games in one process),
  `plans/2026-10-25-engine-context.md` (context slots)
