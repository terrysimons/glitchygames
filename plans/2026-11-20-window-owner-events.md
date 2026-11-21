# Window-Owner Events: Cursor, Key Repeat and Text Input — Plan

> **Status: APPROVED by the owner (2026-11-20); the owner's decisions are folded into the body and
> recorded at the end; nothing is built.**
> Source: the owner's two to-dos of 2026-11-20 in plans/future-work.md ("A cursor show/hide
> event" and "A key-repeat event", under Arcade sub-plan 3 follow-ups), the bugs-table row "A
> tile changes the outer game's key repeat", and the text widgets' text input start and stop,
> which is the same class.

**Goal:** One mechanism for the four SDL settings that are one per process but wanted per game:
the cursor's visibility, the cursor's shape (an image or an animated sprite), key repeat and text
input. Games ask through a plain API (`self.window.hide_cursor()`, ...) and never build events;
the engine posts one recorded event, keeps each context's own values in a `ContextSlot` and puts
them into SDL **only in the context that owns the window**, and only when they change. A tile's
requests stay in its private queue and its slot, so an Arcade tile can no longer hide the
Arcade's cursor, change its shape, turn its key repeat on or start its text input. When the window
changes owner, the engine re-applies the new owner's settings by itself, from one place. Several
active text boxes share text input and key repeat by owner counting, which fixes a box that stops
taking typing. In the browser, text input raises the phone keyboard. The text-input demo's strict
xfail becomes a pass.

**Evidence, verified against origin/main `6f929051` (2026-11-20; line numbers rechecked at
`e646fa26`, which changes none of these files' cited lines):**

| Setting | Calls today | In an inner context |
| --- | --- | --- |
| Cursor visibility | `pygame.mouse.set_visible(False/True)` in Bitmappy's canvas hover: `src/apps/bitmappy/src/bitmappy/animated_canvas.py:1157` and `1179` | a tile's recorded mouse crossing the canvas hides the Arcade's cursor |
| Cursor shape | `GameEngine.set_cursor` (`src/glitchygames/engine/game_engine.py:2046`, the pygame call at `2107`), called from every engine's `__init__` at `1790`, an inner one included | the engine's own monochrome arrow: every context sets the same value, benign today, but a game that sets its own cursor would leak it out of a tile |
| Key repeat | text-input demo `setup()`: `src/demos/text-input-demo/src/text_input_demo/__init__.py:69` (`set_repeat(350)`); `InputBox.on_key_up_event` on every release while active: `src/glitchygames/ui/inputs.py:195` (`set_repeat(200)`); text widgets: `src/glitchygames/ui/text_widgets.py:1220` (`(500, 50)`), `1262`, `1275`, `1329`, `1504` (`200`), `1511` (`1262`, `1275`, `1329` and `1511` turn repeat off with no arguments) | measured: the demo's tile leaves SDL at `(200, 200)` where the outer game had `(0, 0)`; `test_a_tile_leaves_the_outer_key_repeat_as_it_was[text-input-demo/typing.jsonl.gz]` is a strict xfail |
| Text input | `pygame.key.start_text_input()` / `stop_text_input()`: `text_widgets.py:1218, 1260, 1274, 1328, 1503, 1510` | a tile's active text box would turn the Arcade's IME text input on or off (unmeasured: no recording activates one) |

(The future-work entry's line numbers are off: `text_widgets.py`'s last stop is at `1510`, not
`1509`; Bitmappy's calls are at `1157`/`1179`, not `1153`/`1175`; `SDL_MOUSE_FOCUS_CLICKTHROUGH`
is at `game_engine.py:1593`, not `1571`.) Two more one-per-process settings of the same class,
not window settings: pygame's default font resolution (`src/glitchygames/fonts/font_manager.py:307`,
from the context's `--font-dpi`) stays a font option with its own slot, outside this plan; and
`SDL_MOUSE_FOCUS_CLICKTHROUGH` (`game_engine.py:1593`, `os.environ.setdefault`) is harmless once
set.

## How the engine already does the same thing (the mechanism to copy)

Nothing here is a new idea; each piece has a precedent in the code:

| Need | Precedent |
| --- | --- |
| A per-context value, with an isolation check | `ContextSlot` (`engine_context.py:63`), `RENDER_TARGET_SLOT` (`render_target.py`), `PRIVATE_EVENT_QUEUE_SLOT` (`recording.py:489`); every slot needs an entry in `ISOLATION_CHECKS` (`tests/test_engine_context.py:1265`) |
| "Only the context that owns the window touches SDL" | the icon and caption (`game_engine.py:2126-2135`: an inner context sets neither) and `events.set_event_types_allowed` (`events/base.py:268`), which returns early when `is_inner_context()`: "SDL's blocked event types are one set per process, and belong to the context that owns the window" |
| A tile's posts stay off SDL's queue | `recording.private_event_queue` (`recording.py:494`), used by `_post_tracked` (`recording.py:715`) |
| An engine-handled custom event, with a pydantic payload, a post helper and a handler that runs before any scene | `SpriteSpawn` (`events/sprite_spawn.py`), handled in `GameEngine.process_events` before scene dispatch (`game_engine.py:4411`), registered with `named_custom_event_type` so a recording's header names it |
| A recorded event type a replay may leave uncompared | `uncompared_event_types` in `replay/driver.py` `_merged_batch` (`driver.py:2157`; FPS events under `--replay-fps real`: "a recorded one takes the next live one; a live one left over is delivered; neither is a divergence") |
| Something drawn on the presented frame but never in screenshots, traces or compared sprites | the debug overlay, drawn in `_present_frame` (`scenes/scene.py:1538`) |
| A per-context service that changes hands | the audio route (`audio/route.py`): audible or silent per context, switched by the host |

## Decisions

The owner's decisions (2026-11-20, recorded at the end), as design:

1. **One event type, a discriminated payload** (`src/glitchygames/window_settings.py`): a named
   custom event type `WINDOW_SETTING_EVENT = named_custom_event_type('glitchygames.window_setting')`
   whose payload `WindowSettingChange` carries `setting`, a pydantic discriminated union tagged by
   `kind` (each model `frozen=True`, `extra='forbid'`; `to_event()` / `from_event()` like
   `SpriteSpawn`):
   - `CursorVisible(kind='cursor_visible', visible: bool)`;
   - `CursorShape(kind='cursor_shape', sprite_file: str | None, hotspot: tuple[int, int])`:
     `sprite_file` names a sprite file (TOML, one frame or an `[[animation]]`) or an image, by
     the same resolution `SpriteFactory.load_sprite` uses; `None` is the engine's own arrow;
   - `KeyRepeat(kind='key_repeat', delay_milliseconds: int, interval_milliseconds: int)`, `0` for
     both meaning off; a positive delay needs a positive interval (pygame would silently use the
     delay as the interval, which the demo's `set_repeat(350)` relies on: the API takes both,
     so the demo asks for `350, 350`);
   - `TextInput(kind='text_input', active: bool)`.
   One type, not four, so a recording's header names one new id and one handler routes by `kind`.
   Fields are JSON scalars, so `recording.event_to_record` encodes them as it does any event.
2. **A plain API; games never build events.** `Scene.window` is a `GameWindow` (in
   `window_settings.py`), made in `Scene.__init__` and holding no state of its own: every method
   acts on the **current** context's slot at call time (engine context rules 2 and 6), so the same
   scene code asks for its own context's values in a tile and alone. Code with no scene at hand
   calls `window_settings.game_window()`. Interface:
   - `hide_cursor()`, `show_cursor()`;
   - `set_cursor(sprite_file: str | Path, hotspot: tuple[int, int])`, `reset_cursor()` (the
     engine's arrow);
   - `set_key_repeat(delay_milliseconds: int, interval_milliseconds: int)`, `stop_key_repeat()`;
   - `start_text_input()`, `stop_text_input()`;
   - `requested` (read-only): the context's requested values, a frozen model of four optional
     fields, for a game that wants to read back.
   Each method validates its arguments by building the model, then `recording.post_event`s one
   `WINDOW_SETTING_EVENT`, so a recording marks it internal and a replay expects the replayed code
   to post it again (not `post_input_event`, which marks external).
3. **Declarative conveniences on top of the API**, posting through it (so they are recorded like
   any game request):
   - a sprite's `CURSOR_WHILE_HOVERED: CursorVisible | CursorShape | None = None`: the engine
     tracks the topmost sprite under the mouse that declares one (its drawn `rect`, the same
     test Bitmappy's canvas makes today, in the scene's mouse-motion dispatch); on enter it
     requests the sprite's value, on leave it requests back what the scene had before;
   - a scene's `KEY_REPEAT: KeyRepeat | None`, `CURSOR_VISIBLE: bool | None` and
     `CURSOR: CursorShape | None`: requested on enter (`SceneManager._setup_new_scene`,
     `scenes/scene.py:2956`, before `setup()`), and undone on exit
     (`_cleanup_current_scene`, `scene.py:2949`, after `cleanup()`) by requesting back the value
     from before the scene.
   A scene or sprite that declares nothing posts nothing, so no existing golden changes.
4. **The slot** `WINDOW_SETTINGS_SLOT` holds a small plain class (it is mutated) with two frozen
   pydantic values: `requested` (what this context's game asked for) and `applied` (what this
   context last put into SDL), plus the widgets' holds (decision 8). Each field is `None` until
   asked: **unset means untouched**. A game that asks for nothing never writes SDL, so it leaves
   SDL as the process (or the Arcade) had it, and a platform default (text input is on by default
   on desktop SDL2, unverified for pygame-ce here) is never guessed.
5. **Applying: one path.** `window_settings.apply_setting(setting=...)` updates `requested`, works
   out the effective value (holds over `requested`), and, **only if `owns_window()`** (a new
   `render_target.owns_window()`, the negation of `is_inner_context()`, which reads better at each
   site) **and SDL is held for this context** (decision 7), and only if the effective value
   differs from `applied`, calls the one SDL function and updates `applied`. The engine's handler
   for `WINDOW_SETTING_EVENT` (in `process_events` beside the spawn handler, before scene
   dispatch, so no scene sees it and `--no-unhandled-events` never meets it) calls it; so do the
   engine's own widgets, directly (decision 6). `applied` also ends `InputBox` reaching SDL on
   every key release: it reaches SDL once. Only `window_settings.py` calls the SDL functions.
6. **The engine's own widgets call `apply_setting` directly**; games go through the API. A text
   box reacting to a replayed click is deterministic engine code: as posts its requests would add
   recorded events to every click in every recording with a text box, and apply one pump later;
   as direct calls they behave as today and nothing new is recorded. The engine's own arrow
   (`GameEngine.set_cursor`) is engine code too and goes the same way.
7. **The engine re-applies automatically when the window changes owner, from one place.** SDL
   holds whoever wrote last, so the process keeps one record of the context SDL's settings are
   held for (process-wide on purpose, since SDL is: a weak reference with its audit row in
   `tests/test_process_state_guard.py`). `window_settings.follow_window_owner()` runs once per
   frame at the top of `SceneManager._run_frame` (`scenes/scene.py:2076`), its only call site:
   in a context that owns the window and is not the one SDL is held for, it writes every setting
   (the new owner's effective value, or for a setting the new owner never asked for, the process
   baseline: the value SDL had before any context first wrote that setting) and records the new
   holder. A tile's frames run it too and it does nothing there (`owns_window()` is false), and
   the outer game's next frame finds itself still the holder, so stepping tiles causes no churn.
   A request made before the context's first frame (an engine's `__init__`, a scene's declared
   `KEY_REPEAT` before its first frame) only updates the slot and is written by that first
   frame's call. This covers Arcade sub-plan 7 (launching a game in a fresh context, returning to
   the Arcade's) and any later handoff without the launcher calling anything.
8. **Owner counting for text input and key repeat** (a behaviour change, its own step after the
   refactor). A widget holds a setting while it wants it: `hold_setting(owner=..., setting=...)`
   and `release_settings(owner=...)`. Text input is on while the game asked for it or any widget
   holds it, off when the last lets go; key repeat is the most recent holder's value, then the
   game's request, then the baseline. This fixes a box deactivating that turns off text input and
   repeat under another active box (the owner has seen a box stop taking typing).
9. **A tile never applies.** An inner context's requests and holds only update its slot. Highlight
   does not matter (the audio route's "audible" has no counterpart here): a recorded mouse inside
   a tile is not the user's mouse, so its cursor wish is never the window's.
10. **The cursor shape.** A cursor is an image or an `AnimatedSprite` plus a hotspot. By default
    the engine makes one SDL color cursor per frame (`pygame.cursors.Cursor(hotspot, surface)`,
    pygame-ce's `SDL_CreateColorCursor`: full RGBA on macOS, Windows, X11, Wayland and KMSDRM's
    cursor plane), once, when the shape is set, and switches between them as the animation
    advances (on `clock.frame_clock_seconds()`, in the owning context's frame, beside the frame
    services). Where that does not work (the browser, if its check shows it cannot; a size the
    platform refuses) the engine hides the system cursor and draws the sprite at the polled mouse
    position (`current_input()`), in `_present_frame` like the debug overlay: outside the scene's
    groups and the compared sprites, so it never changes a golden, a screenshot or a trace. This
    is a deliberate exception to "every game object is a sprite": the cursor is window chrome,
    not game state. `CursorVisible(False)` hides the drawn cursor as it hides the system one.
11. **Old recordings replay with the new type uncompared until the demos are re-recorded**, with
    the HUD re-record. See Replay compatibility.

## Worked example: Bitmappy's tile in the Arcade

Today. The Arcade shows `bitmappy/demos/drawing.jsonl.gz` in a tile. At some frame the recorded
mouse position crosses into the canvas, `AnimatedCanvas.on_mouse_motion_event` runs inside the
tile and calls `pygame.mouse.set_visible(False)`; SDL has one cursor, so the user's real cursor
over the Arcade vanishes, and comes back when the recorded mouse leaves, whatever the real mouse
is doing.

After. The canvas declares `CURSOR_WHILE_HOVERED = CursorVisible(visible=False)` and its two
`set_visible` calls go. When the recorded mouse enters the canvas the engine's hover tracking
calls `self.window.hide_cursor()` for it, which posts `WINDOW_SETTING_EVENT` to the tile's
private queue. The tile's engine handles it: its slot's `requested` reads `cursor_visible=False`,
and because the tile does not own the window SDL is not called. The Arcade's cursor is untouched.
Run alone, Bitmappy owns the window: the same event reaches the same handler, which calls
`pygame.mouse.set_visible(False)` as today, so the editor looks the same. Replayed alone from a
**new** recording (the re-recorded demo), the event is in the recording and the replayed code
posts it again at the same frame: matched exactly.

The text-input demo: its scene declares `KEY_REPEAT = KeyRepeat(delay_milliseconds=350,
interval_milliseconds=350)`; in a tile its slot holds it and SDL stays at the Arcade's `(0, 0)`;
run alone, SDL gets `(350, 350)` as today. Its input box holds `(200, 200)` while active (the
engine widget's own value, applied directly, nothing recorded) and lets go when deactivated, when
the scene's `(350, 350)` comes back.

The handoff: from the Arcade the owner launches Bitmappy live (Arcade sub-plan 7) in a fresh
context. Bitmappy's first frame finds SDL held for the Arcade's context and writes Bitmappy's
settings, each one it never asked for at its baseline, so it starts as a solo run would. The user
closes Bitmappy with the cursor over the canvas (hidden). The Arcade's next frame finds SDL held
for Bitmappy's context and writes the Arcade's settings back: the cursor is visible again, with
no call in the launcher.

## Replay compatibility (the part that can break goldens)

A recording is a promise about which internal events the code posts. Code that now posts an
event an **old** recording never contains would, under rule 2 of `replay/driver.py`, show as an
`unexpected internal event` divergence in every old recording that reaches those calls. The ones
that do (to confirm in the first step with a counting spy, not assume): the shipped demos
`bitmappy/demos/drawing.jsonl.gz` (the mouse crosses the canvas) and
`text-input-demo/demos/typing.jsonl.gz` (the scene's declared repeat). Neither is a golden trace,
but both are bundled demos replayed by `tests/replay/test_bundled_demos.py` and by the Arcade's
tiles. No game's golden reaches these calls (no game declares or calls any of them), and the
engine widgets' direct calls record nothing.

Design: **until the re-record, the type is uncompared for a recording that predates it**, the
FPS-event precedent. A recording's header names every custom event type it was made with
(`CUSTOM_EVENT_TYPES_HEADER_FIELD`, `recording.custom_event_types_header`, read by
`custom_event_type_remap`); a recording without `glitchygames.window_setting` was made before the
type existed, and `_merged_batch` adds `WINDOW_SETTING_EVENT` to `uncompared_event_types` for it.
The replayed code's posts are then **delivered** (the handler runs: slot updated, SDL touched only
by an owner, harmlessly in a headless replay) and are not divergences, while a new recording's
records are matched exactly. Recordings with no header field use `LEGACY_CUSTOM_EVENT_TYPES`
(`FPSEVENT`, `GAMEEVENT`, `MENUEVENT`), so they lack it too.

**The re-record and the end of the tolerance** (the owner's decision 5). The `drawing` and
`typing` demos are re-recorded together with the HUD re-record of
plans/2026-11-20-game-code-into-the-engine.md (its decision 7: between Arcade sub-plans 5 and 6),
under the same only-expected-differences check: every difference must be a `WINDOW_SETTING_EVENT`
record where the new code posts one. Then the tolerance and its test are removed, so every
recording is compared exactly. This needs the callers' step (Bitmappy and the demo posting) landed
first; if it has not landed by then, the tolerance stays until the next deliberate demo re-record,
and the controller says so.

**Id churn.** A new named custom type is allocated after `SPRITE_SPAWN_EVENT`; the header's names
remap recorded ids to this process's, and no game allocates an unnamed custom type today
(`grep -rn "custom_type()" src` finds only `events/base.py`), so no recording's ids move. A test
replays every shipped recording and the golden traces to prove it, instead of reasoning.

## The engine's own widgets and the callers

- **`InputBox`** (`ui/inputs.py:195`): `set_repeat(200)` on each key release while active becomes
  `apply_setting(setting=KeyRepeat(200, 200))` in the refactor step (one SDL call, nothing
  recorded), and a hold for as long as the box is active in the owner-counting step.
- **`TextBox` / `MultiLineTextBox`** (`text_widgets.py:1218-1220, 1260-1262, 1274-1275,
  1328-1329, 1503-1504, 1510-1511`): each start or stop of text input and each repeat change goes
  through `apply_setting` with `TextInput(active=...)` and `KeyRepeat(...)`. **The refactor step
  keeps behaviour exactly** (the same values, the same last-writer-wins): it moves where the calls
  go, not what they ask for. The owner-counting step then turns each activate into a hold and each
  deactivate into a release, reviewed apart.
- Kept as found, for the owner-counting step's review: three widgets ask for three different
  repeats (`(500, 50)`, `200`, `200`); with holds, the most recent active box's wins and the
  scene's own comes back when the last box lets go.
- **`GameEngine.set_cursor`** (`game_engine.py:2046`, `2107`): the engine's arrow becomes a
  `CursorShape(sprite_file=None, ...)` through `apply_setting`, so a tile's engine never sets the
  window's cursor.
- **Text-input demo** (`text_input_demo/__init__.py:69`): `setup()`'s `set_repeat(350)` becomes
  the scene's `KEY_REPEAT` (a change to the demo, allowed by the owner as for Bitmappy's).
- **Bitmappy** (`animated_canvas.py:1157, 1179`): the two calls become the canvas's
  `CURSOR_WHILE_HOVERED`. If the step finds the engine's hover test differs from the canvas's
  (something drawn over the canvas), the canvas calls `self.window` itself instead.
- Stale text found: `replay/controls.py:34` and `tests/world/test_gameplay_replay.py:3603` say
  "PaddleSlap calls `pygame.key.set_repeat(1)`", but nothing in `src/games/paddleslap` does (grep
  at `6f929051`); the callers' step checks `git log -S` and fixes the sentences.

## The workspace guard

`tests/test_workspace_config.py:1245` today: `CONTEXT_BLIND_PYGAME_CALLS =
frozenset({'pygame.display.get_surface'})` and `PYGAME_MODULES = frozenset({'pygame',
'pygame.display'})` (`1246`), scanning every game, demo and app (keys starting `src/`) for the
call however it is spelled (attribute chain, from-import, alias). Widen both:

- calls: `pygame.mouse.set_visible`, `pygame.key.set_repeat`, `pygame.key.start_text_input`,
  `pygame.key.stop_text_input` (callers' step), and `pygame.mouse.set_cursor` (cursor-shape step);
- modules: add `pygame.mouse` and `pygame.key`, so `from pygame.key import set_repeat` and
  `from pygame import key as keys` are found (the guard's own spelling test,
  `test_the_screen_guard_finds_every_spelling` at `1291`, grows to match, with a planted use of
  each);
- rename the assertion's text and test to say what the set now means (process-wide window
  settings, not only the screen), since the current message says "reads the window instead of
  its own screen".

The guard excludes the engine's own files (the engine answers per context), so **a second guard**
closes the gap that would otherwise let a widget go straight back to pygame: an engine-side test
(beside the allowlists of `tests/test_engine_doors.py`) that no module under `src/glitchygames`
except `window_settings.py` calls those five functions. It is planted-defect tested. A third,
small guard: `follow_window_owner` has exactly one call site.

Each guard widens in the same PR as the last call it forbids goes away, not before, or the suite
is red.

## The browser

Measured in the browser step, not assumed (`nox -s browser -- bitmappy` and
`-- text-input-demo`, Pyodide's pygame-ce on SDL2):

- **The phone keyboard** (the owner's decision 8): text input, and only text input, raises the
  on-screen keyboard; it closes when the last box lets go (so it needs owner counting landed). If
  SDL's emscripten text input does not raise it, the page keeps a hidden `<input>` element that the
  apply path focuses and blurs (through Pyodide's `js` module, in `window_settings.py`'s browser
  branch), and its typed characters reach the game as ordinary key and text events, the same path
  the touch controls (`browser/touch_controls.js`) use, so a browser recording looks like a
  desktop one. A risk the check settles: mobile Safari raises the keyboard only for a `focus()`
  inside a user gesture, and the game reacts to the tap a frame later; if so, the page's own
  touch handler focuses the hidden input when the game has text input wanted. Checked on a real
  phone (iOS and Android).
- **Cursor visibility** is expected to set the canvas's CSS cursor; **key repeat** is software
  repeat in SDL and expected to work.
- **Cursor shape**: whether SDL's emscripten color cursor works (it would become a CSS cursor);
  if not, the browser uses the drawn fallback. On a touch-only device there is no mouse, so the
  fallback draws nothing until a mouse has moved.
- The apply function wraps no exception it cannot name: if a call raises `pygame.error` (display
  not initialised), the test names the exact error and the apply path checks
  `pygame.display.get_init()` first, which is also what a headless engine without a display needs.

There is one context in the browser today; the browser Arcade (sub-plan 8) inherits the tile rule
and the automatic re-apply with no further work, and its "no context switch across an `await`"
rule is why the apply path is synchronous. Bitmappy's browser Save working like Load is a separate
to-do (plans/future-work.md, Bitmappy, "In the browser, Save works like Load"), not part of this
plan.

## Sub-plan order

Each lands green alone (ruff, basedpyright, ty, `pytest` at 100%), and no recording is edited
before step 10.

1. **The mechanism for three settings, no callers.** Create `src/glitchygames/window_settings.py`
   (event type, `CursorVisible`, `KeyRepeat`, `TextInput`, `WindowSettingChange`, the slot with
   `requested` and `applied`, `apply_setting`), add `render_target.owns_window()`, the engine
   handler in `process_events` beside the spawn handler, the `ISOLATION_CHECKS` entry,
   `docs/architecture/engine_context.md` (the inner rules: a new rule 4a),
   `docs/architecture/event_system.md`. First task: a counting spy that replays every shipped
   recording and lists which would post the event (confirming the two demos).
2. **Replay compatibility.** The header test in `_merged_batch`, the uncompared rule, the
   recording of new events. No game posts yet, so the test posts from a stand-in scene.
3. **Automatic re-apply on ownership change.** The process-wide holder record and its audit row,
   the baseline, `follow_window_owner()` at the top of `_run_frame` (its only call site, guarded),
   tested with two non-inner contexts in sequence and with tiles stepped inside an owner.
4. **The engine's widgets and `InputBox` call `apply_setting`**, behaviour kept exactly; the
   engine-side guard. The demo's xfail stays (the demo itself still calls pygame).
5. **The plain API and the declarative conveniences.** `GameWindow`, `Scene.window`,
   `game_window()`, the hover tracking for `CURSOR_WHILE_HOVERED`, a scene's `KEY_REPEAT`,
   `CURSOR_VISIBLE` (and `CURSOR` once step 8 lands); the docs page for window settings. Tested
   with stand-in scenes; no shipped game uses them yet.
6. **Bitmappy and the text-input demo use the API**; the workspace guard widens; the strict xfail
   in `tests/test_every_recording_replays_inside_an_inner_game.py` is removed
   (`CHANGES_THE_OUTER_KEY_REPEAT` becomes empty and its parametrisation and `xfail` branch go,
   with the docstring paragraph that describes it); the stale PaddleSlap sentences are fixed;
   `plans/future-work.md`'s two entries and the bugs-table row are closed.
7. **Owner counting, with its bug record.** Triage first: reproduce the box that stops taking
   typing and confirm this cause with evidence; write the bug record
   (`bugs/YYYY-MM-DD-a-text-box-stops-taking-typing.md`) and the regression test (two active
   boxes, one deactivates, the other still types), proven to fail first; then `hold_setting` /
   `release_settings` and the widgets' holds.
8. **The cursor shape and the animated-cursor fallback.** `CursorShape`, `set_cursor` /
   `reset_cursor`, the scene's `CURSOR`, per-frame SDL color cursors switched as the animation
   advances, the drawn fallback in `_present_frame`, the engine's arrow through `apply_setting`,
   `pygame.mouse.set_cursor` in both guards. Per-platform check (macOS, Windows, X11, Wayland,
   KMSDRM), flicker when frames switch included; `docs/architecture/bitmappy.md` if Bitmappy
   gains a cursor.
9. **The browser.** The measurements above, the phone keyboard (hidden input if needed) checked on
   a real phone, the browser's cursor shape or its fallback; the text-input demo's README.
10. **Re-record `drawing` and `typing` with the HUD re-record** (between Arcade sub-plans 5 and 6,
    plans/2026-11-20-game-code-into-the-engine.md), under its only-expected-differences check;
    then remove the old-recording tolerance and its test.

Steps 1 and 2 can be one PR if the owner prefers. Step 6 waits on 4 and 5; 7 waits on 4; 8 on 5;
9 on 7 and 8; 10 on 6 and on the HUD re-record's slot. 3 is needed by Arcade sub-plan 7 and by
nothing else here.

## Tests, named as behaviours

Mechanism (step 1):
- A game in the default context that asks to hide the cursor has it hidden (read back with
  `pygame.mouse.get_visible()`, or the previous state `set_visible` returns, whichever this
  pygame-ce has), and asking to show it restores it.
- A game in the default context that asks for a key repeat reads it back with
  `pygame.key.get_repeat()`.
- A tile that asks to hide the cursor, for a key repeat and for text input leaves SDL's cursor,
  repeat and text input as the outer game had them, and reads back its own values from its slot.
- Two contexts keep their own requested values (the isolation check).
- Asking for the same value twice calls SDL once.
- A value never asked for never reaches SDL (a context that asks for nothing leaves a prior value
  alone).
- The event never reaches a scene's handlers and is never reported unhandled under
  `--no-unhandled-events`; a raw-event scene (`process_event`) never sees it either.
- A post during a transition still applies (the custom type is not in
  `TRANSITION_DISCARDED_EVENT_TYPES`, `scenes/scene.py:121`; confirm and pin).
- With no display initialised the apply path does nothing and does not raise.
- A setting model refuses an unknown field, an unknown `kind`, a negative repeat and a positive
  delay with a zero interval.

Replay (step 2):
- A new recording holds the event as an internal record and replays with no divergence.
- A recording whose header lacks the type replays with the replayed code's posts delivered and no
  divergence (copies of `typing.jsonl.gz` and `drawing.jsonl.gz` as they ship).
- A new recording with the event removed by hand diverges as `missing internal event` (the gate
  can fail).
- A tile replaying a recording that posts the event ends with SDL unchanged and its own slot set,
  and the same replay in the default context ends with SDL set.
- No shipped recording changes: `git diff --stat origin/main -- '*.jsonl.gz'` is empty, every
  golden trace and golden replay passes untouched.

Re-apply (step 3):
- When a second owning context takes the window, SDL gets its requested values, and its baseline
  for each setting it never asked for.
- When the first context takes the window back, SDL holds the first context's values again (a
  game that ended with the cursor hidden does not leave the returning context without one).
- Stepping a tile inside an owner's frame never re-applies (SDL is written zero times by the
  owner's next frame).
- A request made before a context's first frame is written by that first frame.
- `follow_window_owner` has exactly one call site (planted second call fails).

Callers (steps 4 to 6):
- Activating an `InputBox` or text box in the default context sets the same repeat and text input
  as before; in a tile it leaves SDL alone (the widget runs in the tile's context).
- A key release on an active `InputBox` reaches SDL once.
- `self.window`'s every method posts one recorded `WINDOW_SETTING_EVENT` with the matching
  `setting`, and in a tile posts to the tile's private queue.
- A sprite's `CURSOR_WHILE_HOVERED` applies when the mouse enters it and the scene's previous
  value comes back when it leaves; two overlapping declaring sprites give the topmost's.
- A scene's `KEY_REPEAT` applies on enter and the previous value comes back on exit; a scene that
  declares nothing posts nothing.
- Bitmappy's canvas hover hides and shows the cursor in the default context; a Bitmappy tile
  leaves the outer cursor as it was.
- `test_a_tile_leaves_the_outer_key_repeat_as_it_was` passes for **every** recording, including
  `text-input-demo/typing.jsonl.gz`, with no xfail left (if the mark is left in place the strict
  xfail fails, as designed).
- The workspace guard finds each call in every spelling, and finds none in the current tree; the
  engine-side guard fails on a planted `pygame.key.set_repeat` in a widget.

Owner counting (step 7):
- Two active boxes, one deactivates: the other still types (SDL's text input still on, its repeat
  unchanged); proven to fail before the fix.
- Text input goes off when the last holder lets go, and stays on while the game itself asked for
  it.
- Repeat is the most recent holder's while held, then the scene's, then the baseline.
- A widget released twice, or released without a hold, changes nothing.

Cursor shape (step 8):
- Setting a one-frame cursor gives SDL one color cursor with the hotspot asked for; a hotspot
  outside the image is refused.
- An animated cursor builds each frame's cursor once and switches to frame N's when the frame
  clock reaches it, not before (a fake frame clock).
- In a tile, setting a cursor leaves the window's cursor alone.
- Where cursor creation fails (an injected `pygame.error`), the system cursor is hidden and the
  sprite is drawn at the polled mouse position minus the hotspot on the presented frame, and the
  same frame's screenshot, trace and compared sprites are identical to a run with no cursor.
- Hiding the cursor hides the drawn fallback too.
- Every golden replay passes with a cursor set by a stand-in game (the cursor never changes a
  golden).
- Manual, per platform: no flicker or blank frame as the animation switches cursors.

Browser (step 9, manual on a real phone and desktop browser, with what can be automated in the
browser tests):
- Activating a text box raises the phone keyboard; typing reaches the box; deactivating the last
  box closes it; a key repeat or cursor request never raises it.

## Review focus

1. **Exactness of replay**: the two shipped demos and every golden pass without a re-record until
   step 10; the tolerance applies to older recordings only and is removed after the re-record.
2. **No tile reaches SDL**, including through `apply_setting` from an engine widget inside a tile
   and through the re-apply trigger in a tile's frame.
3. **One trigger for ownership changes**: `follow_window_owner` is called from one place, and the
   holder record is the only process-wide state added (with its audit row).
4. **A context's value is never read at import** (CLAUDE.md, engine context): `current_context()`
   at use time only, `GameWindow` included.
5. **No pygame function is replaced** (the Arcade plans' rule): the engine's own code calls pygame
   in one module; games stop calling it.
6. **The cursor never reaches a compared frame**: the fallback is drawn only on the presented
   display, like the debug overlay.
7. The events a game posts are its own internal posts: not `post_input_event` (that marks
   external, and a replay would serve rather than re-run them). Engine widgets record nothing.
8. The refactor (step 4) and the behaviour change (step 7) are reviewed apart.

## Decided by the owner (2026-11-20)

1. Engine widgets call the shared apply function directly; games use the plain API; one apply
   path.
2. The cursor shape is a fourth setting now; an image or an `AnimatedSprite` plus a hotspot, SDL
   color cursors by default, a drawn fallback, never in a golden, checked per platform. Font
   resolution stays a font option.
3. Unset means untouched.
4. Several active text boxes: fix it with owner counting, its own step after the mechanism, with a
   bug record and a regression test proven to fail first.
5. The `drawing` and `typing` demos are re-recorded with the HUD re-record, between Arcade
   sub-plans 5 and 6; the old-recording tolerance goes after.
6. The engine re-applies automatically when window ownership changes, from one tested trigger.
7. One event type with a discriminated payload, behind a plain API (`self.window`), with
   declarative conveniences (`CURSOR_WHILE_HOVERED`, a scene's `KEY_REPEAT` and the like).
8. In the browser, text input raises the phone keyboard, checked on a real phone. Bitmappy's
   browser Save working like Load is a separate to-do.

9. At a handoff, a setting the new owner never asked for goes back to the process baseline (what
   SDL had before any game wrote it), so a launched game starts as a solo run would (the owner,
   2026-11-20, "a good first step"). Next, a to-do in plans/future-work.md: a game declares its own
   default window settings and the engine records each game's last active settings, so a wrapped
   game gets its own settings instead of the baseline.

Related: plans/future-work.md (Arcade sub-plan 3 follow-ups: the cursor and key-repeat bullets,
and the bugs-table row; Bitmappy: Save works like Load in the browser),
plans/2026-11-12-arcade-3-inner-game.md (Review Focus 4), plans/2026-10-23-arcade-showcase.md
(sub-plan 7, launching in the same process), plans/2026-11-20-game-code-into-the-engine.md (the
HUD re-record that step 10 joins), bugs/2026-11-20-bitmappy-tile-read-the-hosts-window.md (the
same class, display surface).
