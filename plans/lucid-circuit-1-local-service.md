# Lucid Circuit, Stage 1: the local AI service

- **Date:** 2026-11-06
- **Status:** Built and tested on the owner's Mac on branch `worktree-ai-service-ansible`, except as
  listed under "Still open".
- **Master plan:** [lucid-circuit.md](lucid-circuit.md), section 7, Stage 1. The owner's decisions are
  in its section 2. The brief's API contract is its section 6.

## What this builds

A small service in its own project, `services/ai-service/`, sharing no code with the engine. It runs in
a sidecar Python and is the one thing games talk to:

```text
 Game --- WebSocket /v1/session ---+
                                   +--> ai.glitchygames.api --> llama-server (Bonsai 2)
 Tools --- REST /v1/*, /docs ------+                        --> llama-server (Qwen)
```

| Endpoint | Purpose | Token |
|---|---|---|
| `POST /v1/chat/completions` | Bonsai text and images, streaming, cancelled by disconnecting | Yes |
| `POST /v1/embeddings` | Qwen vectors | Yes |
| `GET /v1/models` | Each model's size, capabilities and state | Yes |
| `GET /v1/status` | Live sessions and model states | Yes |
| `WS /v1/session` | One game's live link: hello, ping, later observations and proposals | Yes |
| `GET /health/live` | The API process is up | No |
| `GET /health/ready` | The models are answering | No |
| `GET /openapi.json`, `GET /docs` | Generated contract, and Scalar from local files | No |

## Decisions in this stage

- **The game link ends the models.** When the last session closes, the service waits a grace period
  (30 s, so a scene reload or quick relaunch doesn't reload a model) and runs `ai-service.sh stop`, which
  stops it too. This fills the master plan's gap of nothing calling `stop`, and counts sessions, so one
  game exiting doesn't take the models from another. A crashed game's socket closes the same way.
- **Two tokens.** Clients use `service-api-key`, and only the service holds `worker-api-key`.
- **Ask for a role, get what's running.** `model` may be `reasoning`, `vision` or `embedding`, which
  resolve to the running size, or an exact alias such as `bonsai-2-27b`. Asking for a size that isn't
  running is a clear 503, never a silent substitute.
- **Unsupported fields are refused.** Requests are strict pydantic models, as the brief asks. A
  `dimensions` other than the model's own is refused until dimension reduction is validated.
- **Prism's template rules are handled here:** system messages merge into one leading message, and
  `reasoning_effort: "high"`, which its template answers with a 500, is refused with a clear 422.
- **Scalar is a pinned local file**, fetched at build time by checksum, with the default fonts and the
  proxy off, so `/docs` needs no network.
- **The protocol has a version.** A mismatched game gets a clear refusal and plays on without AI.

## Not in this stage

Agents, observations and proposals over the socket (Stages 3 and 6), the query-type aliases beyond the
three above, the throttle (Stage 5), and moving `glitchygames.api`.

## Evidence (2026-11-06)

- 67 tests at 100% coverage, against a real local fake model server (`cd services/ai-service && uv run
  pytest`).
- `ai_sidecar` builds a 91 MB sidecar, and checks that it uses nothing outside itself. The `.pkg` is 34 MB.
- From the `.pkg`, as a plain user, with real models: nothing runs after install; chat, streaming and
  embeddings answer correctly; a session is welcomed and a website refused; and everything stopped by
  itself when the last session closed, leaving no port open.
- `/docs` in headless Chrome with everything but loopback blocked: it shows the title and the operation
  groups, fetches `/openapi.json` and `scalar.js` locally, and contacted no other host apart from
  Chrome's own traffic, which the check filtered out.

## Still open

- `/docs` shows Scalar's cloud buttons ("Ask AI", "Generate SDK", "Deploy API"). Nothing reaches out until
  one is clicked, as far as the load shows; hide them or replace the page before players see it.
- The SBOM and license check read the root `uv.lock`, so they don't cover the service's own lock file yet,
  and nothing in CI runs the service's tests yet.
- Agents surviving a crash and a reboot, and an install on another Mac or account.
