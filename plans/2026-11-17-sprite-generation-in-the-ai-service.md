# Sprite generation moves into the AI service

Status: DESIGN (2026-11-17), agreed with the owner in conversation; branch
`feat/sprite-generation-in-the-ai-service`. Follows
plans/2026-11-16-console-sprite-generation.md (its part 1 moved `glitchygames-client` off
`glitchygames-server`; its part 2, the console's `/sprite`, calls what this builds).

## Intent

AI generation of sprites becomes a feature of the local AI service (`services/ai-service/`,
127.0.0.1:23231), "wired up to our new LLM routes" (the owner): the service's own model routing
(`workers.resolve`, request slots, authorization), not the engine calling chat completions from
outside. It completes `plans/lucid-circuit.md`'s row 10 ("bring over `glitchygames.api`'s sprite
routes only if they're still wanted, and fix its CORS setting first"): they are wanted (the owner:
"I absolutely want to keep this"), and "anything we want to migrate should move too".

The owner's idea for the generation itself (2026-11-17): the model does not write a sprite file
from nothing. It calls a tool with the size asked for or chosen, and gets back a complete blank
sprite: animated (one `[[animation]]`, one frame), every field filled in, optional ones too, and
the pixel body `height` rows of `width` dots, one row per line (built as
`'\n'.join('.' * width for _ in range(height))`, so the size can be read from the text). It may
change only the `.` cells. The measured failure this answers: of three 27B requests
(`lucid-circuit.md`, section 9) the nearest miss had one row of a 16-wide sprite 17 wide.

## Goals

1. **One sprite format package** (approach C, the owner: "C for sure. That seems the cleanest and
   would allow for some interesting future possibilities too"): the rules of sprite TOML as text
   (read, write, validate, the blank template), with no pygame and no engine import. The engine,
   Bitmappy and the AI service all depend on it; nothing copies it.
2. **The service generates and refines sprites:** `POST /v1/sprites/generate` and
   `POST /v1/sprites/refine`, on the service's model routes, behind its authorization, from local
   origins only.
3. **The blank canvas tool:** the model gets the template from a tool (`blank_sprite(width,
   height)`, the format package's), paints only its `.` cells, and the service checks the result
   against the template in code, sending precise repair requests when it fails.
4. **Every caller moves to the routes:** `glitchygames-client`, Bitmappy's AI generation and the
   console's `/sprite` (part 2 of the earlier design). The engine keeps rendering and frame
   extraction (they need the sprite loader and pygame).
5. **`glitchygames-server` on port 8000 retires; its functionality is kept** (the owner,
   2026-11-17: "I want the functionality kept - we can migrate it into the other service"): its
   sprite routes live in the service now, so the separate program you start by hand goes. What
   needs the engine (rendering, frame extraction) stays in the engine's callers.

## Non-goals

- Rendering or frame extraction in the service (pygame and the loader stay in the engine).
- Cloud providers (`lucid-circuit.md`: local only for now).
- A model self-review pass (see Decisions, 4).

## Anti-goals (a failure even if it works)

- Two copies of the sprite format's rules (the engine's and the service's) that can drift.
- The service importing the engine or pygame (Lucid Circuit's decoupling).
- A sprite the service accepts that the engine's loader refuses, or the reverse.
- A route reachable from any web origin.

## Constraints (from the project)

- The AI service is its own uv project (own lock file, own tests at 100% coverage) and shares no
  code with the engine (`CLAUDE.md`, `lucid-circuit.md`); a shared format package is the one
  deliberate exception, a leaf with no engine import.
- The engine's sprite files are TOML only, magenta 255,0,255 the transparency key,
  `[[animation]]` sections with `frame_interval` (ANIMATION_README.md).
- The service's routes are FastAPI with `authorized` dependencies, request slots and
  role-resolved models (`services/ai-service/src/glitchygames_ai_service/app.py`).
- Tool calling over the live link is being built in the color profiles branch (the zombies
  session's), with sprite-to-TOML and TOML-to-TOML text conversions; the format package is the
  same seam, so it is built once, coordinated with that session.

## Approaches (the owner chose C)

- **A. Copy the format rules into the service.** Quick; two copies that drift.
- **B. The service depends on the engine.** One copy; overturns Lucid Circuit's decoupling and
  installs pygame and the engine in the service.
- **C. A sprite format package both depend on (chosen).** One copy, no engine in the service, and
  the seam the color profiles branch needs.

## Decisions (agreed in conversation)

1. **The template is animated, complete and blank.** One `[[animation]]` with one frame; every
   field present, optional ones included; `.` maps to the transparency key, so the blank canvas is
   see-through; the model adds its own colour keys.
2. **The model may change only the `.` cells** (and set the fields the template leaves to it: its
   name, its colours). The instructions say so.
3. **Code checks the result against the template, exactly** (the owner asked for an adversarial
   comparison of input and output): the same rows, each the same width; every non-pixel field
   unchanged but the allowed ones; every pixel `.` or a declared colour. A failure goes back to the
   model as a precise repair request ("row 7 is 17 wide; it must be 16"), for a small number of
   rounds; then the route answers that it failed and why.
4. **No model self-review** in the first build: models report their own success unreliably and a
   review pass costs minutes on 27B; the code check is exact and free. (The designer's call;
   the owner may add one.)
5. **Refinement is the same check** with the current sprite as the template: only its pixel cells
   may change.
6. **The sprite loader's own rules move into the package too**, so the loader and the service
   accept exactly the same files. First case: a `frame_interval` that is not a number (the loader
   keeps it as written today and a game fails later, in `AnimatedSprite.update`; reproduced
   2026-11-17).

## Settled after the builder check (the designer's calls, for the owner to check)

1. **The earlier design** (`plans/2026-11-16-console-sprite-generation.md`) is on branch
   `feat/sprite-client-without-server` (its PR is opening as this is written); this branch
   rebases on `main` once that merges, and builds on its `glitchygames.api.sprite_requests`.
2. **What the template holds, and what the model may change.** The template is
   `blank_sprite(width, height, frame_count=1, animation_count=1)`: `[sprite]` with `name` (the
   model's to set) and `tags = []`; each `[[animation]]` with `namespace`, `frame_interval` and
   `loop`; each `[[animation.frame]]` with its `pixels` (rows of `.`); `[colors."."]` the
   transparency key. The model may set `name`, the namespaces, add colour keys, and change `.`
   cells; nothing else. Animation requests keep working: they ask for more frames or animations
   in the template, and every frame is checked the same way.
3. **Callers authenticate as `local_service.py` does today:** the service key file under the
   install root (`<install_root>/config/service-api-key`), on the same machine. The REST sprite
   routes refuse a request whose `Origin` is not a local one (a browser page); native clients
   send none and pass.
4. **Retiring `glitchygames-server` means removing it:** `api/main.py`, `api/routes/`,
   `api/dependencies.py`, their tests, the `glitchygames-server` console script and `fastapi` and
   `uvicorn` from the engine's core dependencies. `glitchygames-client` and the request and
   response models stay (the client calls the service's routes).
5. **Callers keep what they read today:** the route answers with the TOML and its name, whether
   it is animated, and its frame count (what Bitmappy reads from `GenerationResult`), and the
   failure's reason.
6. **Tests stand in a model server from the worker's contract** (llama-server's chat
   completions response), scripted with good sprites, rows of the wrong width and undeclared
   colours, for the repair rounds and 100% coverage.
7. **The loader rejects a value of the wrong type or range** with an error naming the file and the
   field, never coerces it; a parity test loads every shipped sprite (the engine's, every game's,
   Bitmappy's library) through the loader and through the package's validation and requires the
   same answer.

8. **The package starts from the color profiles branch's text half** (agreed with that session,
   2026-11-17; `plans/2026-11-17-sprite-color-profiles.md`, part 1, on
   `feature/sprite-color-profiles`): `glitchygames/sprites/sprite_toml.py` is pygame-free and
   `AnimatedSprite`-free, with `parse_sprite_toml(*, text, source_name) -> dict`,
   `write_sprite_toml(*, data) -> str` and `split_sprite_text(*, text) -> list[str]`. This branch
   lifts that module into the package unchanged and adds the schema, the value checks and the
   blank template. The surface functions (`sprite_from_text`, `sprite_to_text`,
   `sprite_text_from_frames`, with one interval per frame and `SpriteColorLimitError` above 64
   colours) stay in the engine's `sprite_text.py`, built on it.

## Decided after the builder check (the owner, 2026-11-17)

1. **The service hands the model the blank canvas** ("Yours", on the designer's recommendation):
   the service calls `blank_sprite` itself and puts the template in the prompt; the model's output
   is held to a grammar (llama.cpp), so every pixel row is exactly `width` characters of declared
   keys. Native tool calls come later, once measured reliable (`lucid-circuit.md` row 11).
2. **Streamed progress:** the sprite routes stream server-sent events ("loading model",
   "generating", "repair round 2: row 7 is 17 wide", the result), as the chat route streams;
   disconnecting cancels the work and frees its model slot. Jobs (submit, then poll) are added
   later only if batches or remote callers need them, wrapping the same generator.
3. **The package is `glitchygames-sprite-format`** (imported as `glitchygames_sprite_format`), its
   own project under `packages/`, a member of the engine's workspace and a path dependency of the
   service's own lock; the installer builds it into the service's Python.
4. **The sprite file schema is pydantic** (the owner: "can we harden it with pydantic?"), built
   first in the engine's loader as the fix for the `frame_interval` bug, then lifted into the
   package. `frame_interval` stays a positive number of seconds (`0.25` is a quarter of a second),
   as every sprite file and ANIMATION_README.md already have it.

## Left to the plan

- The package's name, layer and how the service's separate uv project depends on it (a path
  dependency on the workspace member, for example).
- The routes' request and response models, the tool's exact fields, the number of repair rounds.
- How the client, Bitmappy and `/sprite` authenticate to the service.
- The order: the package (with the color profiles session), the routes, the callers, retiring
  `glitchygames-server`.
