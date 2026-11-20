# Window-Owner Events: Cursor Visibility, Key Repeat and Text Input — Plan

> **Status: a plan for the owner's review (written overnight, 2026-11-20); nothing is built.**
> Source: the owner's two to-dos of 2026-11-20 in plans/future-work.md ("A cursor show/hide
> event" and "A key-repeat event", under Arcade sub-plan 3 follow-ups), the bugs-table row "A
> tile changes the outer game's key repeat", and the text widgets' text input start and stop,
> which is the same class. Open questions for the owner are at the end.

**Goal:** One mechanism for the three SDL settings that are one per process but wanted per game:
a game posts an engine event (cursor visible or hidden, key repeat, text input on or off); the
engine keeps each context's own value in a `ContextSlot` and applies it to SDL **only in the
context that owns the window**. A tile's events stay in its private queue, so an Arcade tile can
no longer hide the Arcade's cursor, turn its key repeat on, or start its text input. The event is
recorded and replayed. The text-input demo's strict xfail becomes a pass.

**Evidence, verified against origin/main `6f929051` (2026-11-20):**

| Setting | Calls today | In an inner context |
| --- | --- | --- |
| Cursor visibility | `pygame.mouse.set_visible(False/True)` in Bitmappy's canvas hover: `src/apps/bitmappy/src/bitmappy/animated_canvas.py:1157` and `1179` | a tile's recorded mouse crossing the canvas hides the Arcade's cursor |
| Key repeat | text-input demo `setup()`: `src/demos/text-input-demo/src/text_input_demo/__init__.py:69` (`set_repeat(350)`); `InputBox.on_key_up_event` on every release while active: `src/glitchygames/ui/inputs.py:195` (`set_repeat(200)`); text widgets: `src/glitchygames/ui/text_widgets.py:1220` (`(500, 50)`), `1262`, `1275`, `1329`, `1504` (`200`), `1511` (each of the last four also turns repeat off with no arguments) | measured: the demo's tile leaves SDL at `(200, 200)` where the outer game had `(0, 0)`; `test_a_tile_leaves_the_outer_key_repeat_as_it_was[text-input-demo/typing.jsonl.gz]` is a strict xfail |
| Text input | `pygame.key.start_text_input()` / `stop_text_input()`: `text_widgets.py:1218, 1260, 1274, 1328, 1503, 1509` | a tile's active text box would turn the Arcade's IME text input on or off (unmeasured: no recording activates one) |

(The future-work entry's line numbers for `text_widgets.py` were off by two; the above are
current.) Siblings of the same class found while checking, not in the owner's list: the cursor
**shape** (`pygame.mouse.set_cursor`, `game_engine.py:2107`, called from every engine's
`__init__` at `1790` including an inner one; the engine's own arrow, so every context sets the
same value, benign today), pygame's default font resolution
(`font_manager.py:307`, per-context font options: its own slot, not a window setting), and
`SDL_MOUSE_FOCUS_CLICKTHROUGH` (`game_engine.py:1571`, harmless once set). Question 2.

## How the engine already does the same thing (the mechanism to copy)

Nothing here is a new idea; each piece has a precedent in the code:

| Need | Precedent |
| --- | --- |
| A per-context value, with an isolation check | `ContextSlot` (`engine_context.py:63`), `RENDER_TARGET_SLOT` (`render_target.py`), `PRIVATE_EVENT_QUEUE_SLOT` (`recording.py:489`); every slot needs an entry in `ISOLATION_CHECKS` (`tests/test_engine_context.py:1265`) |
| "Only the context that owns the window touches SDL" | the caption (`game_engine.py:2126-2135`: an inner context sets none) and `events.set_event_types_allowed`, which returns early when `is_inner_context()` (`events/base.py:268`), "SDL's blocked event types are one set per process, and belong to the context that owns the window" |
| A tile's posts stay off SDL's queue | `recording.private_event_queue` (`recording.py:494`), used by `_post_tracked` (`recording.py:715`) |
| An engine-handled custom event, with a pydantic payload, a post helper and a handler that runs before any scene | `SpriteSpawn` (`events/sprite_spawn.py`), handled in `GameEngine.process_events` before scene dispatch (`game_engine.py:4411`), registered with `named_custom_event_type` so a recording's header names it |
| A recorded event type a replay may leave uncompared | `uncompared_event_types` in `replay/driver.py` `_merged_batch` (FPS events under `--replay-fps real`: "a recorded one takes the next live one; a live one left over is delivered; neither is a divergence") |
| A per-context service that changes hands | the audio route (`audio/route.py`): audible or silent per context, switched by the host |

## Decisions (recommended; the owner reviews them with the plan)

1. **One event type, three payloads** (`glitchygames/window_settings.py`): a named custom event
   type `WINDOW_SETTING_EVENT = named_custom_event_type('glitchygames.window_setting')`, carrying
   a pydantic discriminated union (`frozen=True`, `extra='forbid'`, `to_event()` /
   `from_event()` like `SpriteSpawn`):
   - `CursorVisibility(visible: bool)`;
   - `KeyRepeat(delay_milliseconds: int, interval_milliseconds: int)`, `0` for both meaning off
     (pygame's rule: `set_repeat()` with no arguments disables it, and a delay with no interval
     uses the delay as the interval, which the text-input demo's `set_repeat(350)` relies on: the
     helper takes both explicitly, so the demo posts `350, 350`);
   - `TextInput(active: bool)`.
   One type (not three) so a recording's header names one new id, and a handler routes by
   payload. Fields are JSON scalars, so `recording.event_to_record` encodes them as it does any
   event.
2. **The slot** `WINDOW_SETTINGS_SLOT` holds a small plain class (it is mutated) with two frozen
   pydantic values: `requested` (what this context asked for) and `applied` (what this context
   last put into SDL). Each field is `None` until asked: **an unset value never touches SDL**, so
   a game that asks for nothing leaves SDL as the process (or the Arcade) had it, and a platform's
   default (text input is on by default on desktop SDL2, unverified for pygame-ce here) is never
   guessed. Question 3.
3. **Applying.** The engine's handler (an engine-handled event like `SpriteSpawn`, handled before
   scene dispatch so no scene ever sees it and `--no-unhandled-events` never meets it) does:
   update `requested`; then, **only if `not is_inner_context()`** (a new
   `render_target.owns_window()` reads better than the negation at each site), and only if the
   value differs from `applied`, call the one SDL function and update `applied`. That also fixes
   the engine-widget oddity of `InputBox` calling `set_repeat(200)` on every key release: with
   `applied` it reaches SDL once.
4. **Two entry points, one apply path.** Games post the event (`request_cursor_visible(visible=)`,
   `request_key_repeat(...)`, `request_text_input(active=)`, each one `recording.post_event`, so a
   recording marks it internal and a replay expects the replayed code to post it again). Engine
   code that is itself deterministic game state (the text widgets reacting to a replayed click)
   calls `window_settings.apply_now(change=...)`, the same function the handler calls, with no
   queue hop and no recorded event. Recommended: question 1.
5. **A tile never applies.** An inner context's requests only update its slot. Highlight does not
   matter (the audio route's "audible" has no counterpart here): a recorded mouse inside a tile is
   not the user's mouse, so its cursor wish is never the window's.
6. **Switching owners reapplies.** SDL's value is whoever wrote last, so a context that becomes
   the window's owner again must put its own back, and a launched game must start from SDL's
   defaults: `window_settings.reapply_to_sdl()` (writes every non-`None` `requested` value,
   unconditionally) and `reset_sdl_to_defaults()` (the process defaults: cursor visible, repeat
   off; text input is left alone while its default is unverified). They are the primitives; **who
   calls them is Arcade sub-plan 7** (launching: "a live game owning the window in a fresh
   context, return with the highlight kept"), which does not exist as a plan yet. This plan
   delivers and tests the primitives with two non-inner contexts in sequence.
7. **Old recordings replay unchanged, and are not re-recorded.** See Replay compatibility.

## Worked example: Bitmappy's tile in the Arcade

Today. The Arcade shows `bitmappy/demos/drawing.jsonl.gz` in a tile. At some frame the recorded
mouse position crosses into the canvas, `AnimatedCanvas.on_mouse_motion_event` runs inside the
tile and calls `pygame.mouse.set_visible(False)`; SDL has one cursor, so the user's real cursor
over the Arcade vanishes, and comes back when the recorded mouse leaves, whatever the real mouse
is doing.

After. The canvas calls `window_settings.request_cursor_visible(visible=False)`, which posts the
event to the tile's private queue. The tile's engine handles it: its slot reads
`cursor_visible=False`, and because `is_inner_context()` is true SDL is not called. The Arcade's
cursor is untouched. Run alone, Bitmappy is the window's owner: the same event reaches the same
handler, which calls `pygame.mouse.set_visible(False)` as today, so the editor looks the same.
Replayed alone from a **new** recording, the same event is in the recording and the replayed
code posts it again at the same frame: matched exactly.

The same for the text-input demo: its `setup()` posts `KeyRepeat(350, 350)`; a tile's slot holds
it, SDL stays at the Arcade's `(0, 0)`; run alone, SDL gets `(350, 350)` as today.

## Replay compatibility (the part that can break goldens)

A recording is a promise about which internal events the code posts. Code that now posts an
event an **old** recording never contains would, under rule 2 of `replay/driver.py`, show as an
`unexpected internal event` divergence in every old recording that reaches those calls. The ones
that do (to confirm in the first sub-plan with a counting spy, not assume): the shipped demos
`bitmappy/demos/drawing.jsonl.gz` (the mouse crosses the canvas) and
`text-input-demo/demos/typing.jsonl.gz` (setup, then the input box). Neither is a golden trace,
but both are bundled demos replayed by `tests/replay/test_bundled_demos.py` and by the Arcade's
tiles, and "re-record only deliberately, as a reviewed step".

Design: **the type is uncompared for a recording that predates it**, the existing FPS-event
precedent. A recording's header names every custom event type it was made with
(`CUSTOM_EVENT_TYPES_HEADER_FIELD`, `recording.custom_event_types_header`, read by
`custom_event_type_remap`); a recording without `glitchygames.window_setting` in it was made
before the type existed, and `_merged_batch` adds `WINDOW_SETTING_EVENT` to
`uncompared_event_types` for it. Then the replayed code's posts are **delivered** (the engine
handler runs: slot updated, SDL touched only by an owner, harmlessly in a headless replay) and
are not divergences, while a new recording's records are matched exactly. Recordings with no
header field at all use `LEGACY_CUSTOM_EVENT_TYPES` (`FPSEVENT`, `GAMEEVENT`, `MENUEVENT`), so
they lack it too.

Alternatives, in the demos' own terms:

- *Re-record both demos.* Exact and honest, but it is the owner's reviewed step, changes two
  shipped files and the Arcade's tiles' digests, and leaves the next such event to need it again.
  Better done once, deliberately, later (question 5).
- *Never record or compare these events* (a pure output, like the caption). Simplest for replay,
  but then "the event is recorded and replayed" (the owner's words) would be untrue and a
  watched replay of a recording could not tell whether the game asked to hide the cursor.
- *Pre-header recordings only*: not enough, because 2026 recordings have headers.

Recommended: the tolerance above, with new recordings recording and comparing exactly.

**Id churn.** A new named custom type is allocated after `SPRITE_SPAWN_EVENT`; the header's names
remap recorded ids to this process's, and no game allocates an unnamed custom type today
(`grep -rn "custom_type()" src` finds only `events/base.py`), so no recording's ids move. A test
replays every shipped recording and the golden traces to prove it, instead of reasoning.

## The tile becoming the live one (Arcade sub-plan 7)

Sub-plan 7 is a list item in `plans/2026-10-23-arcade-showcase.md` (Sub-plans item 4 and 7,
"Launching in the same process"): a launched game is built **fresh** in its own context and runs
until it quits; the Arcade's context comes back, and the window takes the game's resolution and
then the Arcade's. So a tile's kept values are **not** carried into the live game (it is a new run
of the game, not a promotion of the replaying context); the live context starts with nothing
requested and its own `setup()` posts what it wants. Two things this plan guarantees for it:

- at launch, SDL is put back to the process defaults (decision 6), so a game launched from the
  Arcade starts exactly as a solo run would (the Arcade's cursor wishes cannot leak into it);
- at return, the Arcade's context calls `reapply_to_sdl()`, so a live Bitmappy that hid the cursor
  and was closed with the cursor hidden does not leave the Arcade without one.

If the Arcade later gains a handoff that promotes a replaying tile's context to live (the
critique's "take over" idea), the same primitive applies its kept values on promotion; the test
for it exists now (a context with kept values becomes the owner and its values reach SDL).

## The engine's own widgets and the text-input demo

- **`InputBox`** (`ui/inputs.py:195`): `set_repeat(200)` on each key release while active becomes
  `window_settings.apply_now(change=KeyRepeat(200, 200))`: no recorded event, one SDL call.
- **`TextBox` / `MultiLineTextBox`** (`text_widgets.py:1218-1220, 1260-1262, 1274-1275,
  1328-1329, 1503-1504, 1509-1511`): each start or stop of text input and each repeat change goes
  through `apply_now` with `TextInput(active=...)` and `KeyRepeat(...)`. **Behaviour is kept
  exactly** (the same values, the same last-writer-wins): this plan moves where the calls go, not
  what they ask for.
- Findings to report, not fix here: three widgets ask for three different repeats
  (`(500, 50)`, `200`, `200`) and the demo's `350` is overwritten by the first key release;
  `deactivate()` of one box turns repeat and text input off while another box may be active
  (there is no owner count). Question 4.
- **Text-input demo** (`text_input_demo/__init__.py:69`): `setup()` posts
  `request_key_repeat(delay_milliseconds=350, interval_milliseconds=350)` (a change to the demo,
  allowed by the owner as for Bitmappy's).
- **Bitmappy** (`animated_canvas.py:1157, 1179`): the two calls become
  `request_cursor_visible(visible=False/True)`.
- Stale text found: `replay/controls.py:34` and `tests/world/test_gameplay_replay.py:3603` say
  "PaddleSlap calls `pygame.key.set_repeat(1)`", but nothing in `src/games/paddleslap` does (grep
  at `6f929051`); the detailed plan checks `git log -S` and fixes the sentences.

## The workspace guard

`tests/test_workspace_config.py:1245` today: `CONTEXT_BLIND_PYGAME_CALLS =
frozenset({'pygame.display.get_surface'})` and `PYGAME_MODULES = frozenset({'pygame',
'pygame.display'})`, scanning every game, demo and app (keys starting `src/`) for the call
however it is spelled (attribute chain, from-import, alias). Widen both:

- calls: `pygame.mouse.set_visible`, `pygame.key.set_repeat`, `pygame.key.start_text_input`,
  `pygame.key.stop_text_input`, and (if question 2 says so) `pygame.mouse.set_cursor`;
- modules: add `pygame.mouse` and `pygame.key`, so `from pygame.key import set_repeat` and
  `from pygame import key as keys` are found (the guard's own spelling test,
  `test_the_screen_guard_finds_every_spelling`, grows to match, with a planted use of each);
- rename the assertion's text and test to say what the set now means (process-wide window
  settings, not only the screen), since the current message says "reads the window instead of
  its own screen".

The guard excludes the engine's own files (the engine answers per context), so **a second guard**
closes the gap that would otherwise let a widget go straight back to pygame: an engine-side test
(beside the allowlists of `tests/test_engine_doors.py`) that no module under `src/glitchygames`
except `window_settings.py` calls those four functions. It is planted-defect tested.

The guard widens in the same PR as the last member's call goes away (Bitmappy's, the demo's), not
before, or the suite is red.

## The browser

Unverified here; the detailed plan measures it rather than assuming (`nox -s browser -- bitmappy`
and `-- text-input-demo`, Pyodide's pygame-ce on SDL2):

- `pygame.mouse.set_visible` is expected to set the canvas's CSS cursor (works in a page);
- `pygame.key.set_repeat` is software repeat in SDL and expected to work;
- `start_text_input` on a touch device may raise the on-screen keyboard: a visible behaviour the
  owner should choose (question 8), and the browser's touch controls
  (`browser/touch_controls.js`) send ordinary key events that this does not touch.
The apply function wraps no exception it cannot name: if a call raises `pygame.error` in the
browser (display not initialised), the test names the exact error and the apply path checks
`pygame.display.get_init()` first, which is also what a headless engine without a display needs.
There is one context in the browser today; the browser Arcade (sub-plan 8) inherits the tile rule
with no further work, and its "no context switch across an `await`" rule is why the apply path is
synchronous.

## Sub-plan order

Each lands green alone (ruff, basedpyright, ty, `pytest` at 100%), no recording edited.

1. **The mechanism, no callers.** Create `src/glitchygames/window_settings.py` (event type,
   payloads, slot, `apply_now`, `request_*`, `reapply_to_sdl`, `reset_sdl_to_defaults`), add
   `render_target.owns_window()`, the engine handler in `process_events` beside the spawn
   handler, the `ISOLATION_CHECKS` entry, `docs/architecture/engine_context.md` (the inner
   rules: a new rule 4a), `docs/architecture/event_system.md`. First task: a counting spy that
   replays every shipped recording and lists which would post the event (confirming the two above).
2. **Replay compatibility.** The header test in `_merged_batch`, the uncompared rule, the
   recording of new events. No game posts yet, so the test posts from a stand-in scene.
3. **The engine's widgets and `InputBox`** call `apply_now`; the engine-side guard. The text-input
   demo's xfail is not removed yet (the demo itself still calls pygame).
4. **Bitmappy and the text-input demo post the event**; the workspace guard widens; the strict
   xfail in `tests/test_every_recording_replays_inside_an_inner_game.py` is removed
   (`CHANGES_THE_OUTER_KEY_REPEAT` becomes empty and its parametrisation and `xfail` branch go,
   with the docstring paragraph that describes it); the stale PaddleSlap sentences are fixed;
   `plans/future-work.md`'s two entries and the bugs-table row are closed.
5. **Owner hand-off primitives for the Arcade**: the two-contexts test of decision 6 (reapply on
   return, reset on launch), written against `InnerGame` contexts now, wired by sub-plan 7.
6. **Browser check and docs**: the measurements above, the docs page for window settings,
   `docs/architecture/bitmappy.md` (cursor), the text-input demo's README.

Sub-plans 1 and 2 can be one PR if the owner prefers; 3 to 4 should not wait on 5 or 6.

## Tests, named as behaviours

Mechanism (sub-plan 1):
- A game in the default context that posts hide-cursor has the cursor hidden (read back with `pygame.mouse.get_visible()`, or the previous
  state `set_visible` returns, whichever this pygame-ce has), and posting show restores it.
- A game in the default context that posts a key repeat reads it back with `pygame.key.get_repeat()`.
- A tile that posts hide-cursor, a key repeat and text-input start leaves SDL's cursor, repeat and
  text input as the outer game had them, and reads back its own values from its own slot.
- Two contexts keep their own requested values (the isolation check).
- Posting the same value twice calls SDL once.
- A value never requested never reaches SDL (a context that asks for nothing leaves a prior
  value alone).
- The event never reaches a scene's handlers and is never reported unhandled under
  `--no-unhandled-events`; a raw-event scene (`process_event`) never sees it either.
- A post during a transition still applies (the custom type is not in
  `TRANSITION_DISCARDED_EVENT_TYPES`; confirm and pin).
- With no display initialised the apply path does nothing and does not raise.

Replay (sub-plan 2):
- A new recording holds the event as an internal record and replays with no divergence.
- A recording whose header lacks the type replays with the replayed code's posts delivered and no
  divergence (use a copy of `typing.jsonl.gz` and `drawing.jsonl.gz` as they ship).
- A new recording with the event removed by hand diverges as `missing internal event` (the gate
  can fail).
- A tile replaying a recording that posts the event ends with SDL unchanged and its own slot set,
  and the same replay in the default context ends with SDL set.
- No shipped recording changes: `git diff --stat origin/main -- '*.jsonl.gz'` is empty, every
  golden trace and golden replay passes untouched.

Callers (sub-plans 3 and 4):
- Activating an `InputBox` or text box in the default context sets the same repeat and text input
  as before; in a tile it leaves SDL alone.
- A key release on an active `InputBox` reaches SDL once.
- Bitmappy's canvas hover hides and shows the cursor in the default context; a Bitmappy tile
  leaves the outer cursor as it was.
- `test_a_tile_leaves_the_outer_key_repeat_as_it_was` passes for **every** recording, including
  `text-input-demo/typing.jsonl.gz`, with no xfail left (this is the strict xfail turning into a
  pass; if the mark is left in place the strict xfail fails, as designed).
- The workspace guard finds each of the five calls in every spelling, and finds none in the
  current tree; the engine-side guard fails on a planted `pygame.key.set_repeat` in a widget.

Hand-off (sub-plan 5):
- After a live game that hid the cursor ends, the returning context's cursor is its own.
- A game launched from a context that had requested repeat starts with SDL's repeat off.

## Review focus

1. **Exactness of replay** (the risk above): the two shipped demos and every golden pass without a
   re-record; the tolerance applies to older recordings only.
2. **No tile reaches SDL**, including through `apply_now` from an engine widget inside a tile (the
   widgets run in the tile's context: the test uses a text box in a tile).
3. **A context's value is never read at import** (CLAUDE.md, engine context): `current_context()`
   at use time only.
4. **No pygame function is replaced** (the Arcade plans' rule): the engine's own code calls
   pygame in one module; games stop calling it.
5. The events a game posts are its own internal posts: not `post_input_event` (that marks
   external, and a replay would serve rather than re-run them).

## Open questions for the owner

1. **Do the engine's own widgets post the event, or call the shared function?** Worked example: a
   click in a Bitmappy text box today calls `start_text_input()` and `set_repeat(500, 50)` in the
   handler. As posts they would add two recorded internal events to every click in every
   recording that has a text box, and they apply one pump later; as direct calls they behave as
   today and nothing new is recorded (the widget is driven by the replayed click, so the replay
   runs it anyway). Recommended: direct calls for the engine, events for games (the owner's
   design), one apply path underneath.
2. **Siblings:** add the cursor shape (`pygame.mouse.set_cursor`, same value every context sets
   today) as a fourth setting now, or only note it? Font resolution is a font option and stays
   its own slot. Recommended: note both, do neither here.
3. **Unset means untouched** (recommended) or explicit defaults in the slot (cursor visible, repeat
   off, text input off)? The second is simpler to read but would make every context write SDL's
   defaults and would guess the text-input default.
4. **Text input and repeat with several active boxes:** keep last-writer-wins (today's behaviour,
   recommended for this plan) or count owners so a box deactivating does not turn the others'
   input off? The second is a behaviour change and its own small plan.
5. **After this lands, re-record the two demos** (`drawing`, `typing`) so the tolerance for older
   recordings can eventually go? Recommended: with the next deliberate demo re-record, not for
   this.
6. **Who calls `reapply_to_sdl()` and `reset_sdl_to_defaults()`:** sub-plan 7's launcher, as
   written. Confirm, since that plan is not written.
7. **Event shape:** one type with a discriminated payload (recommended) or three named types?
8. **Browser:** should text-input start raise the phone keyboard in the browser build, or is that
   a deliberate off there?

Related: plans/future-work.md (Arcade sub-plan 3 follow-ups: the cursor and key-repeat bullets,
and the bugs-table row), plans/2026-11-12-arcade-3-inner-game.md (Review Focus 4),
plans/2026-11-20-game-code-into-the-engine.md (the other overnight plan; independent),
bugs/2026-11-20-bitmappy-tile-read-the-hosts-window.md (the same class, display surface).
