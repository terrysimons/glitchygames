# Sprite color profiles, through the AI's tools — master plan

- **Date:** 2026-11-17
- **Status:** APPROVED by the owner (2026-11-17: "Approved"). Nothing built yet.
- **Branch:** `feature/sprite-color-profiles`, stacked on `feature/zombies-aint-my-neighbors`
  (PR #215). `/sprite` (`plans/2026-11-16-console-sprite-generation.md`, another session's,
  approved) lands on this branch too, stacked on it by that session once part 1 here is
  committed (the owner, 2026-11-17).
- **Related:** the profiles and color spaces were designed in `plans/future-work.md`, "Sprite color
  profiles and a glyph generator" (that entry keeps the full tables and points here); the
  mirror game and its tools, `plans/lucid-circuit-4b-mirror.md`; the AI service,
  `plans/lucid-circuit.md`.
- Feature plans, one per part, each linking back here:
  1. [Sprites as text](2026-11-17-sprite-color-profiles-1-sprite-text.md)

## Intent

The owner wants to try color profiles on a game's own art through the local AI, without changing
the game: ask in the AI console ("make Dex 8-bit with the NES palette"), and get back the sprite
converted, in the engine's sprite format. "Temporary for now": the running game is never changed,
nothing is saved, nothing reaches a recording. Wiring a returned sprite into the game is later work.

It is also the first real use of **tool calling**: the model calls tools the game runs, gets the
results, and continues. The owner: "ship it over to the AI instance and have it do a tool call into
the game engine and return the result. That keeps the processing off of the game loop, keeps the
game read only until we decide to wire it up, and allow us to do some testing."

## Goals

1. Profiles (how many colors one sprite may use) and color spaces (which colors exist), as engine
   data, with the notation `profile · color space` and the sprite-file keys `profile` and
   `color_space`.
2. A converter: a sprite file in, the same sprite converted to a profile and color space out.
3. Sprites as text in memory, both directions, built once and shared: sprite to sprite file text,
   sprite file text to sprite, an image (an APNG's frames) to sprite file text, and one sprite's
   frames split into a sprite file each. `/sprite` and `glitchygames-client --extract-frames` build
   on these (the other session, 2026-11-17).
4. Tool calling: the game sends its tools with the question, runs the model's tool calls, sends
   the results back, and asks again, until the model answers.
5. The console's requests are async, on the desktop and (later) in the browser, with no threads in
   the game.

## Non-goals

- Changing the running game, saving converted sprites, or recording anything about this.
- The glyph generator: converting down (8-bit, 16-bit, 8-bit+) never needs more than today's 64
  glyphs. It comes with 16-bit+ and High Color output, later.
- Palette swaps, color cycling, fades (the backlog's palette features).
- The console in the browser. This design removes the obstacle (threads); turning it on is later.
- Better models. Bonsai's tool calls are used as they are, guarded.

## Anti-goals (a failure even if it works)

- A frame that waits on the AI, the network or a conversion.
- A thread in the game for any of this (the browser has none; the owner, 2026-11-17).
- The model retyping a sprite file: a small model corrupts pixel rows it copies.
- Two copies of the sprite-text code (one for this, one for `/sprite`).
- A converter whose result depends on the run: the same input and arguments give the same file.

## Decisions (the owner's, 2026-11-17, unless marked as the designer's)

1. **Profiles, color spaces and alpha** are as recorded in `plans/future-work.md`. In short:
   - Profiles, per sprite, never a total: 8-bit (4 colors), 16-bit (16), 8-bit+ (64, today's
     format), 16-bit+ (256), High Color (32,768), True Color (no budget).
   - Color spaces: 32-bit RGBA (the default, the only one with partial alpha), 24-bit RGB, the NES
     palette, 9-bit and 15-bit RGB, 1-, 2- and 4-bit mono with named tints, and the agreed
     candidates (6-bit and 12-bit RGB, C64, CGA, ZX Spectrum, web-safe; community palettes after
     license checks).
   - Each distinct color with its alpha is one entry of the budget, the magenta key included.
   - Written `8-bit+ · 9-bit RGB`; in a file, `profile` and `color_space` keys in `[sprite]`. A
     file without them reads as True Color · 32-bit RGBA, as every file does today.
2. **Temporary, read-only.** The game is never changed by this.
3. **The engine converts; the AI judges.** The conversion is exact engine code. The model chooses
   what to protect when colors merge (a zombie's red eyes kept apart from its green skin) and
   passes those as hints.
4. **Sprite files in, sprite files out** ("Return the updated sprite in glitchygames sprite format.
   That's what you'll get as input, return it as output").
5. **The game runs the tool rounds (approach A), async** ("Ok yes, I agree A async"). The console
   asks over the service's HTTP route as today, streamed; when the model answers with tool calls,
   the game runs them and asks again with the results. The live link is unchanged.
6. **No threads in the game** ("we can't run threads in web"; "That layer will need to call over
   the socket anyway so might as well do it for the desktop version, too"). The console's request
   and its tool rounds are one async task stepped by the frame loop, on the desktop too.
7. **Native tool calls now**, guarded; measuring them with the behaviour harness
   (`scripts/ai_behaviour/`) is a later follow-up (the owner: "Good for now").
8. **The converted file reaches the console from the game's own tool result**, never from the
   model's text (the designer's, from the anti-goal above).
9. **The tools read the live game, for now: a recorded, temporary exception** to the owner's rule
   of 2026-11-06 that the AI works on a copy of the game (`plans/lucid-circuit-4b-mirror.md`),
   which isn't built yet (the owner, 2026-11-17: "1. Ok", to reading live with a cost guard until
   the copy exists). The exception covers reading only: `list_sprites` and `sprite_file` (a
   sprite written out as text); `convert_sprite` reads no game at all. **It ends when the copy
   works:** the tools then read the copy instead, a one-place change, because each tool takes the
   game it reads as a parameter rather than reaching for the running one.

## Constraints (from the project)

- **The console's rules** (`src/glitchygames/ai_console.py` docstring): rule 1 read-only stays true
  (the tools only read and return text); rule 2, never in a recording, stays true; rule 5, the
  frame never waits, now holds by async steps instead of a worker thread, and its wording changes
  to say so.
- **Today's transport** (read 2026-11-17): the console asks over HTTP (`/v1/chat/completions`,
  streamed, `ai/local_service.py`), on a new `ai-console` thread per request; the live link
  (`ai_link.py`, protocol version 1) carries only `hello`, `welcome`, `ping`, `pong`, `refused`,
  `error`, plus `input_event`, and is read by an `ai-link` thread. The service's `serve_session`
  answers only `ping` ("Agents join this in a later stage").
- **The service shares no code with the engine** (`plans/lucid-circuit.md`, row 10): its tool
  definitions are data the game sends, never engine imports.
- **The service refuses tools today**, deliberately (`ChatRequest` has `extra='forbid'`;
  `services/ai-service/tests/test_rest.py` checks `tools` is refused; `ChatMessage` has no
  `tool_call_id`, no assistant `tool_calls` and no empty `content`). Accepting them is a change to
  the service's own contract, in its own project, with its own tests.
- **The model** is Bonsai, pinned to 2B, through llama-server `b12167`. Its tool calls work through
  the installed server (`lucid-circuit-4b-mirror.md`: correct calls on the first try, 2026-11-07),
  but can be malformed or loop (`lucid-circuit.md`, decision 11). Its template needs one leading
  system message (the service merges them). Its context is about 8K tokens, so a few tool rounds
  with a sprite file in them can exhaust it.
- **Limits:** the service's 1 MB live-link message limit and its four concurrent requests; the
  console's one request at a time.
- **Engine rules:** time only through `glitchygames/clock.py`; no new module-level mutable state
  outside a `ContextSlot`; sprites load through `SpriteFactory`; every sprite class stands on
  `RootSprite`; sprite files are checked with `glitchygames.testing.sprite_files`.
- **The live link is untouched:** protocol version 1, `hello`, `ping` and `input_event` as today.
- **The browser, later:** the service requires its key on every request and checks each live
  link's Origin. A page served from a website calling a service on the player's machine needs that
  (and the browser's cross-origin rules) decided when the console comes to the browser (recorded,
  not decided here).

## Approaches

- **Who runs the tool rounds:**
  - **A. The game** (the console's request loops over HTTP rounds, running each round's tool
    calls between them). **Chosen**, built async: one connection, one place that loops, and the
    service only learns to accept and forward tools. `scripts/ai_behaviour/run.py` already runs
    this loop against the same llama-server.
  - **B. The service** (it holds the conversation, sends tool calls to the game over the live link,
    and continues). Rejected: it adds a protocol version 2, new link messages, conversation state
    in the service and the game answering mid-stream, and keeps every connection A has.
- **Threads or async:** a worker thread per request, as today (rejected: the browser has no
  threads) or one async task stepped by the frame loop (chosen, on the desktop too).
- **Who converts:** the engine (chosen: exact, instant, the same every time) or the model
  (rejected: seconds a sprite, different each run, corrupts what it copies). The model contributes
  hints.
- **What the result is:** a temporary look applied to the game, recorded (rejected for now), or
  a sprite file returned and nothing changed (chosen: "Temporary for now").
- **Sprite text:** passed through the model (rejected: thousands of tokens a sprite, corrupted
  copies) or referenced by sprite id, with files moving only between the game's tools and the
  console (chosen).

## Design

### Part 1: sprites as text (shared)

- **Sprite file text to sprite:** the sprite loader gains a load from text; the file loader reads
  the file and calls it, so there is one path and never a temporary file. `SpriteFactory` gains the
  same, returning what `load_sprite` returns (an `AnimatedSprite`). Today the file is read in
  several places (`SpriteFactory._analyze_toml_file`, `_get_toml_data`, `AnimatedSprite._load_toml`,
  the constructor): each takes the text or the parsed data instead.
- **Sprite to sprite file text:** the writers (`AnimatedSprite._save_toml` and its
  `_write_toml_*` helpers) write to an open file today; they write to a string, and `save` writes
  that string to the file.
- **Image to sprite file text:** each frame of an image (an APNG's frames, a PNG as one frame)
  becomes a frame of an in-memory `AnimatedSprite` (built empty, then `add_animation` and
  `add_frame`), then sprite to text. Bitmappy's image import (`film_strip_sprite.py`,
  `_load_image_as_sprite_frame`) does the pixel reading tied to its canvas size; the shared code
  keeps the image's own size, and Bitmappy uses it.
- **Split frames:** one sprite's animation frames, each as its own single-frame sprite file.
- **Round trips:** a sprite file loaded and written again holds the same sprite: the same parsed
  data (names, colors, glyphs, frames, animations, hitboxes, tags), for every sprite file in the
  repository. Not byte for byte: comments and layout aren't kept (the designer's call: a
  byte-identical bar would mean rewriting the writers for formatting nobody reads).
- **The interface** (the designer's call, reviewed by the `/sprite` session, 2026-11-17). Two
  modules, so that the text-only half needs neither pygame nor `AnimatedSprite`: the AI service
  cannot import the engine, and the owner approved (2026-11-17) moving sprite generation into it,
  in `plans/2026-11-17-sprite-generation-in-the-ai-service.md` on that session's branch, which
  lifts the text-only module into a small pygame-free package without changing its signatures.
  - `glitchygames/sprites/sprite_toml.py`, pygame-free, a sprite file's text as data:
    - `parse_sprite_toml(*, text: str, source_name: str) -> dict[str, Any]`: the document as
      `tomllib` reads it; a file that isn't valid TOML raises `ValueError` naming `source_name`.
    - `write_sprite_toml(*, data: Mapping[str, Any]) -> str`: the document in the engine's
      sprite format (the writers' layout today: `[sprite]`, `[[animation]]` and its frames,
      `[colors]`, `[[transition]]`). Every engine writer goes through it.
    - `split_sprite_text(*, text: str) -> list[str]`: one single-frame sprite file per frame, in
      animation and frame order, each named `<sprite>-<animation>-<frame>`.
  - `glitchygames/sprites/sprite_text.py`, the engine's, built on it:
    - `sprite_from_text(*, text: str, source_name: str) -> AnimatedSprite`: what
      `SpriteFactory.load_sprite` returns; `source_name` names the text in repair warnings. The file
      loader reads the file and calls it (one path, never a temporary file);
      `SpriteFactory.load_sprite_from_text` is the same call. `COORDINATE_SPACE` is left to the
      caller.
    - `sprite_to_text(*, sprite: AnimatedSprite) -> str`: what `save` writes; `save` writes it.
    - `sprite_text_from_frames(*, frames: Sequence[pygame.Surface], frame_intervals:
      Sequence[float], name: str) -> str`: an image's frames, each a surface of the image's size
      with alpha kept, each with its own interval in seconds (an APNG's frames each have their
      own delay; the two sequences must be the same length), as one animation. Decoding files is
      the caller's.
  - **Too many colors:** an image whose frames use more colors than the glyphs hold (64 today) is
    refused with `SpriteColorLimitError` (a `ValueError`) carrying its color count and the limit,
    never reduced silently; reducing colors is the converter's, asked for.
  - The loader's value checks (a non-number `frame_interval` loads today and crashes later) belong
    to that package's work, on the other session's branch.

### Part 2: profiles, color spaces and the converter

- **Data:** profiles and color spaces as engine data (frozen pydantic models), color spaces either
  a bit depth or a named palette; named palettes from palette files beside today's
  `color/resources/nes.palette`, each with its source credited.
- **The converter**, sprite file text in, sprite file text out, working on the parsed sprite (its
  `[colors]` map and pixel rows), never on drawn surfaces:
  1. snap each color to the color space (nearest in a perceptual color space, so merges look
     right, not plain RGB distance);
  2. if the space is not 32-bit RGBA, make alpha on or off (partial alpha to its nearer end);
  3. merge colors down to the profile's budget, closest pairs first, never merging a color the
     hints protect into another (hints that cannot all be kept are reported, not ignored);
  4. rewrite `[colors]` and replace merged glyphs in every frame's rows;
  5. write `profile` and `color_space` into `[sprite]`;
  6. report what changed: which colors snapped, which merged into which, which hints held.
- **Deterministic:** the same input, profile, color space and hints give the same file, glyph for
  glyph.
- **Never more colors than the input:** a sprite already within the budget keeps every color (only
  snapped).
- **The magenta key** (255, 0, 255, the transparency key) is not a color: it is never snapped or
  merged, and it is what "off" means in the on/off spaces. It counts as one entry of the budget
  (decision 1), so 8-bit leaves 3 colors besides it. Partial alpha in an on/off space becomes the
  key (at or below half opacity) or the color made opaque (above). A sprite with no transparency
  spends no entry on the key (the designer's call, following the consoles: their transparent slot
  was there to be used, not owed).
- **The hints** name colors as the sprite's own file does, `#rrggbb` (or `#rrggbbaa` with alpha):
  the colors as they were before snapping, as `sprite_file` shows them. A hint naming a color the
  sprite doesn't have is reported ("not in the sprite") and the conversion goes on; more hints than
  the budget allows keep the first ones in order and report the rest (the designer's call).

### Part 3: async requests with tool rounds

- **The service accepts tools on its HTTP route:** `tools` and `tool_choice` in the request;
  messages with the assistant's `tool_calls`, the `tool` role's `tool_call_id`, and empty `content`
  where the model gave only tool calls; all forwarded to llama-server as they are. The service
  still merges system messages for Bonsai. Its test that refuses `tools` becomes tests that accept
  and forward them, and still refuse unknown fields.
- **No threads in the game.** The console's request is one async task stepped by the frame loop
  once per frame, after the frame's logic and events and before drawing (as `GameHost.run_async`
  steps a browser game), replacing the per-request `ai-console` thread.
  Each step does what is ready (sends, reads the stream's available pieces, runs a tool) and
  returns; nothing ever blocks a frame. Rule 5 holds by this, and its wording changes to say so.
  The HTTP streaming client (`ai/local_service.py`) becomes async, with no new dependency:
  `httpx2`, already the engine's, has an async streaming client (`AsyncClient.stream`, 2.16.0).
  On the desktop the engine owns one asyncio event loop per running game (a `ContextSlot`, with
  its isolation check, so the Arcade's games never share one) and runs it one step per frame, at
  one point in the frame: after its logic and events, before drawing (ready callbacks only, never
  waiting). A frame is one pass of `SceneManager`'s loop, not a logic tick (`dt_tick`): there is
  one tick a frame today, but under the refresh-aware plan
  (`plans/2026-11-17-refresh-aware-rendering-and-fixed-simulation.md`) a frame may run none or
  several, and the network and the tools belong to the frame (the owner
  asked, 2026-11-17); in the browser, the page's own loop steps it
  (`GameHost.run_async`). The request's task code is the same in both; only how the HTTP request
  is sent differs in the browser (Pyodide has no sockets, so its fetch), which is the browser's
  later work (the designer's call).
- **The service ships in the same PR, first** (the designer's call): its commit accepts tools, the
  game's commits use them. A game asking an older installed service gets its 422 refusal of
  `tools`; the console then says the AI service is older than the game and to update it with the
  AI service playbook (`ansible/macos_ai_service.yml`), and still answers questions without tools.
- **Tool rounds:** the stream's pieces are read as today (reasoning and answer text), plus the
  model's `tool_calls` (gathered from their streamed fragments) and why the stream ended. When it
  ends on tool calls, the game runs each (part 4), adds the results to the conversation, and asks
  again, up to the round cap.
- **Guards** (decision 7): at most a fixed number of rounds per question; a tool call that is
  malformed (not JSON, an unknown tool, arguments that fail the tool's schema) or repeats the same
  call gets an error result once, then the question ends with the reason shown; `/cancel` stops the
  stream and the rounds; one question at a time, as today.
- **The live link** is unchanged; the `ai-link` thread that reads it is not part of this (the
  console in the browser, later, will need it async too, recorded).

### Part 4: the tools

The game's tool registry: each tool has a name, a description, a JSON schema for its arguments
(the definitions sent to the model with each request) and a function. Tools run on the main thread
in part 3's async step, after the frame's logic and events and before drawing, so they read the
state the player is about to see, directly and consistently, and they never change it. Names
avoid the mirror plan's `get_sprite(id)`, which returns attributes.

- **The game a tool reads is a parameter** (decision 9): the live game's scene today, the copy's
  when it exists.
- **A cost guard:** each tool's time on the frame is measured. A read that would take more than a
  set share of the frame budget is split across frames (one sprite written out per frame), so a
  tool never causes a hitch; the share is the builder's, with its reason.

| Tool | Arguments | Returns (to the model) |
|---|---|---|
| `list_sprites` | optional class name | sprite ids with their names and classes |
| `sprite_file` | sprite id | the sprite's file text (part 1), within a size limit; over it, its size, colors and frames instead, said plainly |
| `convert_sprite` | sprite id, profile, color space, colors to keep | the converter's report (part 2); the converted file itself goes to the console, not the model (decision 8) |
| `list_color_profiles` | none | the profiles and color spaces, with what each means |

Sprite ids are the stable ids the engine gives every sprite (they are never reused within a run).

### Part 5: the console

- A question is asked as today; while tools run, the console shows each call and its short result
  ("convert_sprite dex → 8-bit · NES palette: 11 colors → 4").
- A conversion's file is shown in the console and kept as the latest result; `/copy` puts it on the
  clipboard.
- The console's docstring rules are updated (rule 5's mechanism; the tools named under rule 1).

## Tests (behaviours)

- **Part 1:** text and file loading give the same sprite, for every sprite file in the repository;
  writing a loaded sprite gives the same file; an image's frames become a sprite of the image's
  size, alpha kept; split frames give one file per frame, each loading as one frame; every game's
  and Bitmappy's sprite tests pass with the shared path.
- **Part 2:** each profile's budget is never exceeded, the magenta key counted; the same arguments
  give the same file; a sprite within budget keeps all its colors; protected colors stay distinct;
  partial alpha becomes on/off in every space but 32-bit RGBA; the written file loads and passes
  `glitchygames.testing.sprite_files`' checks; the NES palette's colors are the palette file's.
- **Part 3:** with a stand-in service built from the service's HTTP contract (its SSE stream,
  llama-server's `tool_calls` deltas): a question streams its pieces to the console; a tool call
  is run and its result sent in the next round; each guard ends a question with its reason; no
  frame waits (the frame loop is stepped while the stand-in delays); `/cancel` stops the stream;
  no thread is started (the thread count before and after is the same). Service side: tools,
  tool messages and empty content are accepted and forwarded unchanged; unknown fields are still
  refused.
- **Part 4:** each tool's schema accepts what the model is told and refuses what it isn't; tools
  change nothing in the game (state before and after compared); `sprite_file` over the size limit
  answers with the summary; `convert_sprite`'s file reaches the console and only its report reaches
  the model.
- **Part 5:** a conversion shows its calls and its file; `/copy` copies the file.

## Answered after the builder check (the owner, 2026-11-17)

1. **Which color spaces this branch ships** ("Agree with you on the color spaces"): the ones that
   are pure math, with nothing to source: 32-bit RGBA, 24-bit, 15-bit, 12-bit, 9-bit and 6-bit
   RGB, web-safe, and 1-, 2- and 4-bit mono in even grays; plus the NES palette, already in the
   repository. The named hardware palettes (C64, CGA, ZX Spectrum, and the Game Boy green, amber
   and green phosphor tints) are a follow-up part in this branch, each with its values' source
   recorded and credited. Community palettes wait for their license checks, as agreed.
2. **When the network and the tools are stepped:** once per frame, at one fixed point (after the
   frame's logic and events, before drawing), in this branch. Per tick was considered and is not
   offered (see Follow-ups). Servicing the network in the pacer's idle wait is a follow-up, as an
   enumerated option beside `frame` ("let's plan for frame vs idle as options").

## Follow-ups

### `--ai-stepping frame|idle`: when the network is serviced

Planned (the owner, 2026-11-17); built with the pacer work in
`plans/2026-11-17-refresh-aware-rendering-and-fixed-simulation.md`, which changes how a frame
waits. This branch builds the single behavior that becomes `frame`, as one step function the frame
loop calls at its fixed point; `idle` later calls the same function from the pacer's wait too (a
second caller, never a second implementation).

| Value | What happens | Valid uses |
|---|---|---|
| `frame` (the default) | The network and the tools step once per frame, at the fixed point. A reply that arrives mid-frame waits for the next frame's step: at most one frame per pause in a request (16.7 ms at 60 FPS). | Any game by default: AI work happens at one known point, so frame-time measurements stay easy to read (the refresh plan measures first). A game that uses its whole frame budget, where the pacer has no idle time to give. The browser, where the page's own loop steps once per frame and there is no pacer wait to use: `frame` is the only mode there. Recording and replay work, where the console is off anyway and nothing should change how a frame spends its time. |
| `idle` | As `frame`, plus the network is serviced during the pacer's wait before each frame's deadline: a reply is read the moment it arrives instead of at the next frame. Tools still run only at the fixed point, so they always read a settled game. | A game running at a low frame rate, where `frame` costs a whole long frame per pause: a turn-based or menu scene at 10 FPS waits up to 100 ms each time. Long tool exchanges: `scripts/ai_behaviour/` found sixteen tool rounds needed, so up to sixteen frames saved per question, half a second at 30 FPS. An AI that talks while you play (a narrator or companion reacting live), where responsiveness is the point. And on the Pi, time the pacer would otherwise spend spinning goes to waiting on the network instead (the refresh brief: no busy waiting by default on the Pi). |

- **Set by** a command-line option, `--ai-stepping frame|idle`, documented with the other options
  in its branch; a game may set its own default with a scene class attribute (as `TARGET_FPS`), so
  a game that wants the fastest loop says so in code.
- **Not offered: `tick`** (stepping per logic tick). Today a frame runs one tick, so it would be
  `frame` under another name. Under the refresh plan it is never better: with more ticks than
  frames it saves a few milliseconds against seconds of model time; with fewer (the brief's 60 Hz
  simulation at 120 Hz drawing) frames without a tick would step nothing, so it is slower. Recorded
  so nobody adds it thinking it was overlooked.
- **Not the AI as a player.** An AI whose answers change the game (a character it controls) acts
  through recorded input events consumed by ticks, as the mirror plan designs
  (`plans/lucid-circuit-4b-mirror.md`): a different feature from this read-only console.
- Both values are tested: the same exchange gives the same answer either way, `idle` reads a reply
  that arrives during the wait in the same frame, tools never run outside the fixed point, and the
  browser refuses `idle` with a message and uses `frame`.

### The named hardware palettes

C64, CGA, ZX Spectrum, Game Boy green, amber, green phosphor: a later part of this branch, each
palette file naming the reference its values come from.

## Left to the builder

- The round cap and `sprite_file`'s size limit, each with its reason.
- The perceptual color space (CIELAB or OKLab) and the merge rule's details, within decision 3.
- Where each new module lives, following the engine's layout.
- The order of commits within each part.
