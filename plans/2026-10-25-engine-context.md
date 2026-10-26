# Engine Context (master plan)

Status: IN PROGRESS. Sub-plan 1 (State) implemented on feature/engine-context-state
(commits 9d3a162e..faa2c616 and the documentation commit), verification in its Task 10. Sub-plan 1 has a full implementation plan; sub-plans 2-8 are one line each below and
get their plans when each starts, written against how the one before turned out. Execution is
subagent-driven (superpowers:subagent-driven-development), for every sub-plan. When this file
is committed, the controller adds it to `LIVING_PLAN_FILES` in `tests/test_suite_collection.py`
(it passes the living-documentation path guard); the sub-plans stay off that list (they quote
existing docstrings exactly).


Spec: [the Arcade master spec](2026-10-23-arcade-showcase.md), its sub-plan 1 ("Engine context
(its own master plan with sub-plans): `EngineContext`, the default context, switching, the
isolation tests. First."). This is that master plan; its sub-plans link back here.

## Goal

Several games running in one process, each in its own **engine context**, without any of them
seeing another's state: the Arcade runs nine-to-ten live, silent `DemoPlayer` tiles and the
highlighted one large with sound, each player in its own context, and a launched game in a fresh
context of its own (one process: the browser has no child processes). Ordinary games, which never
create a context, run in the **default context** and do not change: every existing test, golden
replay, golden trace and bundled demo passes unchanged in it.

What "state" means here: everything a running game depends on that is not on an object the game
holds. Today all of it is process-wide (module globals, class attributes, singletons), so a
second game in the same process would read the first one's random streams, frame clock, doors,
polled input, scene manager and options.

## The end state this plans for

- The engine at `src/glitchygames/`, with no example games left inside it; games in
  `src/games/<game>/`, demos in `src/demos/<demo>/`, apps in `src/apps/<app>/` (Bitmappy, the
  Arcade at `src/apps/arcade/`); every game discovered by an entry point; recordings name games
  by logical names.
- Nothing in these plans depends on a game's location. Engine tests use stand-in scenes inside
  `tests/`, never a real game's module path. Where the audit names a game's own state it names
  the game, not a path.

## The audit: every piece of process-wide mutable state a running game depends on

Treatments:

- **per context**: owned by the context; a new context starts with a fresh value, as a fresh
  process would. The sub-plan that moves it is named.
- **shared**: one per process (the display, the mixer, SDL's event queue, the joystick
  subsystem, the platform's clipboard). A context that does not own it is kept off it, as the
  last column says.
- **read-only**: constants, declarations, or caches of values computed only from their keys,
  which nobody writes after making them; sharing them cannot leak anything.

Line numbers are as of commit 53869ac4.

### Per context (19)

| # | State | Where | What it holds | Sub-plan |
|---|---|---|---|---|
| C1 | `_ActiveSnapSettings.default_mode` | `src/glitchygames/pixel_snap.py:61-64` | the default `PixelSnapMode` (the running scene's `PIXEL_SNAP_MODE`, set at scene setup) | 1 |
| C2 | `_ActiveBackgroundSettings.default_pattern` | `src/glitchygames/backgrounds.py:113-116` | the background a scene that sets none shows (`--default-background`) | 1 |
| C3 | `_CURRENT` | `src/glitchygames/input/state.py:327` | this frame's polled `InputSnapshot` | 1 |
| C4 | `_STATE` (`EngineRandomState`) | `src/glitchygames/randomness.py:71-79` | the master seed and every named `random`/numpy stream | 1 |
| C5 | `_REGISTRY` (`_SourcesRegistry`) | `src/glitchygames/sources.py:243-265` | the installed and scoped doors, `frames_started`, the frame clock, redelivered events, discarded scope posts, the save-store and device-answer observers | 1 |
| C6 | `SceneManager._instance` (with `__new__`, `_reset`) | `src/glitchygames/scenes/scene.py:191, 197-201, 305-317` | the scene manager and everything on it: active scene, frame number, supervision, playback scope, instant-replay journal, debug overlay, SCREEN shake, rumble, live audio, pacing clock and deadlines | 1 |
| C7 | `SceneManager.OPTIONS` | `src/glitchygames/scenes/scene.py:193` | the engine's options, copied on by the `game_engine` setter | 2 |
| C8 | `GameEngine.OPTIONS` | `src/glitchygames/engine/game_engine.py:407` | the run's parsed options | 2 |
| C9 | `GameEngine.game` | `src/glitchygames/engine/game_engine.py:398` | the running game | 2 |
| C10 | `GameEngine.EVENT_HANDLERS` | `src/glitchygames/engine/game_engine.py:420` | event type to bound methods of one engine instance | 2 |
| C11 | `GameEngine.LAST_EVENT_MISS`, `MISSING_EVENTS`, `UNIMPLEMENTED_EVENTS` | `src/glitchygames/engine/game_engine.py:409-411` | per-run event bookkeeping | 2 |
| C12 | `ResourceManager.__instances__` | `src/glitchygames/events/base.py:344` | the shared event managers (keyboard, mouse, joystick, controller, ...) and the `FontManager` | 2 |
| C13 | `FontManager.OPTIONS` | `src/glitchygames/fonts/font_manager.py:137` | the font options of the run | 2 |
| C14 | `performance_manager` (`AdaptiveClamping._instance`) | `src/glitchygames/performance/adaptive_clamping.py:78, 925` | FPS statistics and the per-scene shutdown reports | 2 |
| C15 | `Singleton`, `SingletonBitmappySprite`, `FocusableSingletonBitmappySprite` `__instance__` | `src/glitchygames/sprites/bitmappy_sprite.py:1019, 1053, 1101` | one-per-process widgets | 2 |
| C16 | `MultiControllerManager._instance` | `src/glitchygames/bitmappy/controllers/manager.py:69` (Bitmappy's; moves with it to `src/apps/bitmappy/`) | Bitmappy's controllers (a Bitmappy demo tile and a launched Bitmappy each need theirs) | 2 |
| C17 | `_unhandled_event_types` | `src/glitchygames/events/base.py:200` | the event types already logged under `--debug-events` (log once each) | 2 |
| C18 | `Sprite.SPRITE_COUNTERS`, `SPRITE_BREAKPOINTS` | `src/glitchygames/sprites/sprite.py:45-46` | sprite creation counters and breakpoints of the run | 2 |
| C19 | `_INTERNAL_POSTS` (`InternalEventPosts`) | `src/glitchygames/recording.py:414` | code-posted events awaiting their pump, their owners, live-game and input posts | 2 |

C19 moves into the context in sub-plan 2 with the other engine state; where a context's posts
go (today `pygame.event.post` into SDL's one queue, item S5) is sub-plan 6's. The 15 lines of
`tests/test_recording.py` that reach `recording._INTERNAL_POSTS`, and the 4 that reach
`events.base._unhandled_event_types` (C17), are rewritten by sub-plan 2 under the rule for
tests of moved state (Decisions, 1).

### Shared (15)

| # | State | Where | What it holds | How a context that does not own it is kept off it | Sub-plan |
|---|---|---|---|---|---|
| S1 | the display surface | `pygame.display`; opened by `GameEngine.initialize_display` and `src/glitchygames/display_mode.py:66`; 13 readers of `pygame.display.get_surface()` in the engine | the one window | only the presenting context presents; an inner context renders into a surface of its own (its render target) at its own resolution and never calls `set_mode` | 4 |
| S2 | window services | caption (`src/glitchygames/engine/game_engine.py:1510`, `src/glitchygames/scenes/scene.py:2741`), icon (`game_engine.py:401-403, 1507`, the class attribute `GameEngine.icon`), cursor (`game_engine.py:1488`), grab (`game_engine.py:3353-3359`), key repeat and text input (`src/glitchygames/ui/text_widgets.py:1153-1197`, `src/glitchygames/ui/inputs.py:192`), mouse visibility (Bitmappy) | what the window does | set only from the presenting context; an inner context's calls are dropped (it gets no real input, so repeat and text input mean nothing to it) | 4 |
| S3 | the mixer and its channels | `game_engine.py:2267-2276`; the reserved live-voice pool `src/glitchygames/audio/live.py:51, 77-79` (`_pool_grown_mixer_channel_counts`) | sound output | a context has an audio route: audible (the mixer) or silent (its sounds and live voices never reach the mixer); the pool belongs to the audible context | 5 |
| S4 | the music stream | `pygame.mixer.music`; `src/glitchygames/replay/silence.py:147` (`_MUSIC_FOLLOWING`, which replaces `pygame.mixer.music.pause`/`unpause`) | one music track | music only from the audible context; a silent context's music calls are dropped | 5 |
| S5 | SDL's event queue | read by `GameEngine._pump_events` through the live doors; written by `pygame.event.post` (`src/glitchygames/recording.py:596`) | real input and posted events | only the presenting context pumps it; an inner context gets its events from its doors (a recording) and its posts go to a queue of its own | 6 |
| S6 | SDL's blocked and allowed event types | `src/glitchygames/events/base.py` (`allow_every_event_type`), `src/glitchygames/replay/input_blocking.py:142-151`, every event manager's `set_allowed` | which types SDL queues | an inner context never blocks or allows (its doors never read SDL) | 6 |
| S7 | the joystick subsystem | `src/glitchygames/input/devices.py` (`LiveDeviceRegistry`), `pygame.joystick.init` (`src/glitchygames/events/joystick.py`) | real pads | an inner context's devices are replay stand-ins (`ReplayJoystick`, `ReplayController`); it never rumbles | 6 |
| S8 | process services | signal handlers (`game_engine.py:1798-1808`), `pygame.register_quit` (`:999`), `sys.setswitchinterval` (`:1037`), the SDL environment variables (`SDL_DRIVER_VARIABLES` `:173`, `SDL_NO_SIGNAL_HANDLERS` `:1033`), `pygame.init()` (`:1041`), `pygame.fastevent` (`:1049`) | the process | set only by the outer (process-owning) engine; an inner engine never touches them | 7 |
| S9 | the clipboard registry | `src/glitchygames/clipboard.py:133` | the player's clipboard (the browser page installs its own) | stays shared: it is the player's; an inner context gets no real input, so never pastes | none |
| S10 | the user-files registry | `src/glitchygames/user_files.py:56` | the browser's file picker and downloads | stays shared: the player's | none |
| S11 | the disk-save change observers | `src/glitchygames/state/manager.py:55` | the browser's IndexedDB flush | stays shared: demo contexts use `MemorySaveManager` and never call it | none |
| S12 | the viewer's sleep timer | `src/glitchygames/replay/viewer.py:85` | a `FastTimer` and its measured sleep model | stays shared: it paces the outer viewer only and holds no game state | none |
| S13 | `HashableEvent._hashing_ids`, `_comparing_ids` | `src/glitchygames/events/base.py:892, 924` | recursion guards, empty between calls | stays shared: empty whenever a switch can happen | none |
| S14 | `_scenes_warned_about_double_update` | `src/glitchygames/world.py:23` | scenes already warned (weak) | stays shared: keyed by scene, so it is per context in effect | none |
| S15 | Bitmappy's `_RUNNING_AI_MANAGERS`, `_AI_REQUEST_COUNTER` | `src/glitchygames/bitmappy/ai_manager.py:79, 83` | running AI workers (weak), request ids | stays shared: unique ids and shutdown bookkeeping across the process (AI features are off in the browser) | none |

### Read-only (14)

| # | State | Where | Why sharing it is safe |
|---|---|---|---|
| R1 | `EXAMPLES_LAYERS`, `MEMBER_LAYERS` | `src/glitchygames/logical_names.py:23, 35` | data, never written |
| R2 | `_default_colors` and the colour constants | `src/glitchygames/color/constants.py:29` | constants |
| R3 | `_EMPTY`, `_SCANCODE_OF_KEY_CODE`, `IDLE_INPUT` | `src/glitchygames/input/state.py:59, 71, 319` | immutable |
| R4 | `_NON_FINITE_FLOAT_NAMES`, `_TAG_DECODERS` | `src/glitchygames/recording.py:353, 774` | tables |
| R5 | `_SDL_CONTROLLER_MODULE` | `src/glitchygames/input/devices.py:70` | an import's result |
| R6 | `functools.cache` of the source revision and the machine | `src/glitchygames/build_info.py:224`, `src/glitchygames/machine_state.py:315` | one machine, one checkout |
| R7 | the background pattern cache | `src/glitchygames/backgrounds.py:245` | drawn from (pattern, size) only; its docstring: copy it, never draw on it |
| R8 | the debug text backing cache | `src/glitchygames/debug/panels.py:33` | identical blank backings by size |
| R9 | `FontManager.RENDER_CACHE`, `_font_cache` | `src/glitchygames/fonts/font_manager.py:138-139` | fonts and renders by their settings, one cache per process (the owner, 2026-10-25); safe only while nothing changes a cached font's style in place (bold, italic, underline, size), which sub-plan 2's guard test enforces |
| R10 | Bitmappy's `PIXEL_CACHE` | `src/glitchygames/bitmappy/pixel_sprite.py:22` | pixel surfaces by colour and size |
| R11 | the API server's `lru_cache` settings | `src/glitchygames/api/dependencies.py:8-30` | the server's configuration (not a game's) |
| R12 | class declarations and defaults | `Scene.TARGET_FPS` and the other scene declarations (`src/glitchygames/scenes/scene.py:2802-2824`), `GameEngine.USE_FASTEVENTS` (`game_engine.py:412`, decided by the pygame version), the class defaults `GameEngine.trace_recorder`/`replay_sources`/`rebaseline`/`recording_write_failed` (`game_engine.py:425-435`, overridden on the instance), `SceneManager._initialized` | declarations; each instance sets its own |
| R13 | the declared context slots (new in sub-plan 1) | `src/glitchygames/engine_context.py` (`_DECLARED_SLOTS`) | written once per slot, at import |
| R14 | the games' own module-level caches and tables | Brave Adventurer's gradient and pose caches, Drawing Fire's cached drawings, Clockwork Keep's floor tables | values computed from their keys or constants; sub-plan 2's guard keeps it that way for every member |

Totals: 19 per context (6 in sub-plan 1, 13 in sub-plan 2), 15 shared, 14 read-only. Instance attributes (a `GameEngine`'s, a `GameHost`'s `TickPacer`, an
`InputDevices` registry, a `Scene`'s `game_time` and camera) are not in the table: an object
belongs to the context that made it.

## Design

### EngineContext: one object, a fixed interface, a slot per piece of state

`src/glitchygames/engine_context.py`, a leaf module (standard library only, so every module, the
leaf modules `sources.py` and `randomness.py` included, may import it):

```python
class ContextSlot[T]:
    def __init__(self, *, name: str, factory: Callable[[], T]) -> None: ...  # declared once
    name: str
    factory: Callable[[], T]

class EngineContext:
    def __init__(self, *, name: str) -> None: ...
    name: str
    def value[T](self, *, slot: ContextSlot[T]) -> T: ...        # made by the factory on first read
    def reset_value[T](self, *, slot: ContextSlot[T]) -> T: ...  # a fresh value (tests, new runs)
    @contextlib.contextmanager
    def active(self) -> Iterator[Self]: ...                     # with context.active(): ...

def current_context() -> EngineContext: ...
def default_context() -> EngineContext: ...
def declared_context_slots() -> tuple[ContextSlot[Any], ...]: ...
```

The interface is frozen: `EngineContext` never grows an attribute per subsystem. Each module
declares the state it owns as a slot, next to the code that uses it, and keeps owning its type:

```python
# src/glitchygames/randomness.py
ENGINE_RANDOM_STATE_SLOT: ContextSlot[EngineRandomState] = ContextSlot(
    name='glitchygames.randomness.streams', factory=EngineRandomState
)

def _engine_random_state() -> EngineRandomState:
    return current_context().value(slot=ENGINE_RANDOM_STATE_SLOT)
```

Rules (the module docstring states them; sub-plan 1 writes them):

1. Per-context state is a `ContextSlot`, declared once at module level with a unique dotted
   name; a second slot of the same name is refused (`DuplicateContextSlotError`).
2. Code reads a slot when it needs it, never as a module is imported (a module-level,
   class-level or default-argument read would hold the default context's value for every
   context); a scan of the engine and every member enforces it.
3. A context makes each value with the slot's factory the first time it is read, so a new
   context starts as a fresh process would.
4. `current_context()` is the context switched to last in this thread or asyncio task, else the
   default context.
5. `with context.active():` makes it current and puts the previous one back when the block ends,
   normally or by an exception (which propagates); switches nest.
6. A context owns only what its slots hold; the shared resources are arbitrated (below), never
   switched.

### The default context

A module-level `EngineContext(name='default')`, current whenever nothing has switched. An
ordinary game never creates a context, so everything it does happens in the default context,
exactly as the process-wide state behaved: `GameEngine.__init__`'s `reset_sources()`,
`reset_current_input()` and `seed_engine_random(...)` reset the current context's values, which
is the default one; `SceneManager()` returns the default context's scene manager. The test
harness's resets (`tests/harness.py`) reset the default context, and a new harness fixture fails
any test that leaves another context current. That is why the existing suite, golden replays,
golden traces and bundled demos are the guard: they all run in the default context and must
pass unchanged.

### How module-level functions resolve to the current context

Every public function keeps its signature; only its body changes from the module global to the
current context's slot value:

| Function | Reads |
|---|---|
| `active_sources()`, `install_sources()`, `push_scoped_sources()`, `frame_clock_seconds()`, `advance_frame_clock()`, `redeliver_events()`, the observers | `current_context().value(slot=SOURCES_REGISTRY_SLOT)` |
| `random_stream()`, `numpy_stream()`, `engine_random_seed()`, `reset_streams()`, `capture_stream_states()`, `restore_stream_states()` | `ENGINE_RANDOM_STATE_SLOT` |
| `frame_clock_milliseconds()`, `elapsed_seconds()`, `wall_clock_time()` (`src/glitchygames/clock.py`) | through `sources.py` (unchanged code) |
| `current_input()`, `set_current_input()`, `reset_current_input()` | `CURRENT_INPUT_SLOT` |
| `active_default_snap_mode()`, `resolve_snap_mode()` | `SNAP_SETTINGS_SLOT` |
| `active_default_background_pattern()`, `paint_default_background()` | `BACKGROUND_SETTINGS_SLOT` |
| `SceneManager()`, `SceneManager._reset()` | `SCENE_MANAGERS_SLOT`: a dict from the class constructed to its manager, looked up along the class's MRO exactly as the class attribute `_instance` was (a subclass without an entry of its own answers with its base class's) |

Objects are not bound to a context: a stream object, a `LiveSources`, a scene keeps working on
its own state wherever it is used. Only the module-level lookups depend on the current context,
which is why a context's frames must run inside its switch (sub-plan 3 makes a scene manager
refuse to run a frame step outside the context that made it).

### Switching

`with context.active():` sets a `contextvars.ContextVar` and resets it with its token when the
block ends. There is nothing to save or restore, because everything a context owns is in it: a
switch costs one `ContextVar.set` and one `reset`. Reentrancy: switches nest (`a` inside `b`
inside `a` is fine) and each block restores what was current when it began. An exception inside
a block propagates after the previous context is back; the caller decides what a failure means
(the Arcade's `DemoPlayer` marks its player crashed and goes on, as the spec's "A player that
raises" asks: sub-plan 3).

Why a `ContextVar` and not a module global pointer: in the browser the game runs as one asyncio
task whose ticks are awaited (`GameHost.run_async`, `src/glitchygames/host.py`); a switch held
across an `await` with a plain global would leak into any other task or JS callback that runs
meanwhile. A `ContextVar` is per task: a task made inside a switch keeps that context (asyncio
copies the context when it makes a task), and a switch in one task is never seen by another. A
thread sees the context current where it is started only when started with
`context=contextvars.copy_context()` (or on an interpreter with
`sys.flags.thread_inherit_context`); otherwise it sees the default context. Sub-plan 1 pins all
three behaviours with tests; sub-plan 3 decides the rule for the engine's own threads
(controller audio, voice recognition).

### Shared resources (sub-plans 4-7)

The rule: a context either owns a shared resource or never touches it. Exactly one context owns
the process's resources at a time: the outer game's (the Arcade's, or an ordinary game's
default context). The others are inner contexts.

- **Display**: an inner context renders its scenes into a render target of its own (an
  offscreen surface at its game's resolution) and never presents; only the owning context
  presents. The engine's readers of `pygame.display.get_surface()` read the context's render
  target instead (sub-plan 4 audits all 13). A launched game becomes the owning context and
  gets the window at its resolution; the Arcade's comes back after.
- **Window services** (caption, icon, cursor, grab, key repeat, text input): only from the
  owning context.
- **Mixer**: an audio route per context, audible or silent. A silent context's sounds, music
  and live voices never reach the mixer (the spec's "a muted player gets a silent audio
  context"). Today's `FrameSilencer` stops every sound in the process after each frame, which
  would silence the audible context too, so it cannot be the mechanism; sub-plan 5 adds the
  route and a guard (like the doors guard) on direct mixer use in the engine and every member.
- **SDL's event queue**: only the owning context pumps it (`GameEngine._pump_events` through its
  live doors). An inner context's doors serve a recording and never read SDL; its posts go to a
  queue of its own, so they can never reach the owning game (sub-plan 6, which also moves the
  internal-post tracker C19). Input blocking at SDL (`replay/input_blocking.py`) is only ever
  done by the owning context.
- **Joystick subsystem**: inner contexts get replay stand-in devices; no rumble reaches a real
  pad from an inner context.
- **Process services** (signals, SDL environment, `pygame.init`, the GIL switch interval): only
  the outer engine; an inner engine (sub-plan 7) is built without them.

### The browser

One thread; `GameHost.run_async` awaits one tick per animation frame. The Arcade is the outer
game in the default context; within one tick it runs each `DemoPlayer`'s frames synchronously,
`with player.context.active(): ...`, never across an `await`. The `ContextVar` makes a mistake
here harmless to other tasks, and sub-plan 3 makes it an error. The clipboard and user files
stay installed by the page for the process (S9, S10): they are the player's, and only the
owning context gets real input.

### The replay viewer: the first existing user

The watched replay is already an outer game ticking an inner one (`src/glitchygames/replay/
viewer.py`, through `EngineSources.hold_frame`), but both share one state. Sub-plan 8 moves the
inner recorded game into its own context while the viewer stays the outer game in the default
context: the viewer pumps SDL and reads its keys in the default context; each inner frame runs
inside the inner context. It proves the design on code that exists, with its tests and every
golden replay watched, before the Arcade's playback core (the spec's sub-plan 2) builds on it.
The playback scope (`src/glitchygames/replay/playback.py`) keeps working inside one context: its
scoped doors are pushed in the current context's registry; whether a scope becomes a context of
its own is the playback core's decision.

## Options considered and set aside

- **Save and restore the module globals on every switch** (copy each global out and back in
  around a context's frames): costs a copy of every piece of state per switch, ten times per
  Arcade frame; one forgotten global leaks silently; and objects held across a switch (a running
  shake's stream) would point at a copy that is no longer live. The playback scope does this by
  hand today for the streams, the frame clock and the FPS timer, and its rules are long because
  of it.
- **An attribute per subsystem on `EngineContext`** (`context.random_state`,
  `context.sources`): the leaf modules (`sources.py`, `randomness.py`) would have to import a
  module that knows every subsystem's type, an import cycle; and the class would change with
  every subsystem. Slots keep each module owning its state and its type.
- **Pass the context explicitly** (an `engine` argument down every call): every game calls
  `random_stream()`, `SceneManager()` and `frame_clock_seconds()` freely; threading a parameter
  through all of them rewrites every game and breaks "ordinary games do not change".
- **Thread-local storage**: the browser is one thread with asyncio tasks, so it would not
  isolate a switch held across an `await`; a `ContextVar` covers threads and tasks.
- **A plain module-global "current context"**: costs the same as a `ContextVar` and leaks a
  switch across an `await` (above).
- **One child process per game**: not possible in the browser (the spec, option B / D2).
- **Subinterpreters** (`concurrent.interpreters`, Python 3.14): would isolate module globals for
  free, but pygame-ce/SDL is one per process and not subinterpreter-safe, numpy does not load in
  subinterpreters, surfaces cannot cross interpreters without copying, and Pyodide has none.
- **A fresh import of the engine per context** (fresh module copies): class identity breaks
  (`isinstance` across contexts), memory doubles per tile, and pygame's state is shared anyway.

## Risks

- **Import-time reads**: a module that reads a slot at import (or in a class body or a default
  argument) holds the default context's value for every context. Sub-plan 1's scan of the
  engine and every member fails the suite on one.
- **A switch that never unwinds** (entered by hand, a generator suspended inside one): the
  wrong context stays current for the rest of the process. `with` blocks only; the harness
  fails a test that leaves another context current.
- **Frames run outside their context**: a scene manager made in context A, stepped while B is
  current, would advance B's frame clock and draw from B's streams. Sub-plan 3 binds a scene
  manager to its context and refuses a frame step elsewhere.
- **Hot paths**: `resolve_snap_mode` runs per sprite per frame, `random_stream` per draw,
  `active_sources()` several times a frame. A slot read is one `ContextVar.get` and one dict
  lookup (tens of nanoseconds); the commits' replay-metrics rows (the pre-commit hook) show any
  slowdown per golden replay, and sub-plan 7 measures ten contexts in one frame.
- **State nobody listed**: a module- or class-level mutable added later bypasses the contexts.
  Sub-plan 2 turns the audit table into a guard (an AST scan of the engine and every member,
  like the doors guard's allowlist), so a new one fails the suite until it is a slot or listed
  as shared or read-only with its reason.
- **Games' own module state**: a game with gameplay state in a module global would leak between
  its demo tile and its launched copy. The same guard scans the members; `ContextSlot` is
  internal to the engine (Decisions, 3), so a game keeps its state on its scenes, and the guard
  fails a member's module-level mutable state unless it is a read-only cache or table.
- **Tests that reach private module state**: `tests/harness.py` patches `randomness._STATE`
  (sub-plan 1 changes that fixture); `tests/test_recording.py` reaches `recording._INTERNAL_POSTS`
  and `tests/engine/test_game_engine.py` and `tests/events/test_events_core.py` reach
  `events.base._unhandled_event_types` (sub-plan 2). Each sub-plan lists such lines before it
  moves the state and rewrites them under Decisions, 1.
- **pygame's own globals** cannot be in a context at all; they are the shared rows, and an inner
  context must never call the functions that change them (sub-plans 4-7 each add a guard for
  theirs).

## Sub-plans (in order; each written before its work starts, each linking back here)

1. **State** ([2026-10-25-engine-context-1-state.md](2026-10-25-engine-context-1-state.md),
   full implementation plan): `EngineContext`, `ContextSlot`, the default context,
   `current_context()` and `with context.active():`; audit rows C1-C6 moved into slots one by
   one; a test running two contexts in one process proving none of them leaks.
2. **The engine's own state**: rows C7-C19 (GameEngine and SceneManager class state, the shared
   event managers and `FontManager`, the performance manager, the singletons, the debug-events
   log set, sprite counters, the internal-post tracker), with the test lines that reach C17 and
   C19 rewritten under Decisions, 1; the guard test that nothing changes a cached font's style
   in place (R9, Decisions, 2); and the process-state guard (the audit as an allowlist scan of
   the engine and every member).
3. **Switching contract**: a scene manager bound to its context (a frame step elsewhere raises),
   switching only between a context's frames, an inner context's exception contained and its
   context marked failed, the browser rule (no switch across an `await`), the engine's threads,
   the switch's cost measured.
4. **The display and the window**: a render target per context (offscreen for inner contexts),
   the 13 `get_surface()` readers through it, window services only from the owning context.
5. **Sound**: an audio route per context (audible or silent), the live-voice pool and music
   owned by the audible context, a guard on direct mixer use; the spec's "sound only from the
   context that has it" test.
6. **Events and devices**: only the owning context pumps SDL; an inner context's posts go to a
   queue of its own (read by its doors, tracked by its own internal-post tracker, C19, already
   in the context since sub-plan 2); SDL blocking only by the owner; inner devices are replay
   stand-ins, no rumble.
7. **The inner engine**: a `GameEngine` built in a context that owns no process resource (no
   `pygame.init`, display mode, signals or SDL environment), from 4-6; two stand-in games in two
   contexts with frames interleaved, each equal frame for frame to running alone; each golden
   replay replayed in an inner context equal to its headless replay; ten contexts' cost per frame
   measured.
8. **The replay viewer's inner game in its own context**: the first existing user; the viewer
   stays the outer game in the default context; every watched-replay test and golden replay
   unchanged.

After sub-plan 8 the Arcade spec's sub-plan 2 (one playback core, then `DemoPlayer`) builds on
contexts.

## Decisions (the owner, 2026-10-25)

1. **Tests of state that moves into the context.** A test line that reaches private module
   state this plan moves (`randomness._STATE`, `recording._INTERNAL_POSTS`: 15 lines in
   `tests/test_recording.py`, `events.base._unhandled_event_types`: 4 lines, and any like them)
   is rewritten, in the sub-plan that moves the state, to test the behaviour where it is
   observable (posts tagged internal or external in a recorded session's event batches; the
   unhandled-event warning and the shutdown table through `caplog`), and to read through the
   current context (`current_context().value(slot=...)`) only where the state has no
   observable effect. The engine gets no test-only module accessors. Sub-plan 1 meets one such
   reach, the harness fixture `fresh_random_streams`, a reset with no behaviour of its own,
   which resets the slot through the default context; sub-plan 2 rewrites the C17 and C19
   lines.
2. **Fonts.** The font caches (R9) stay shared, one per process, with a guard test that nothing
   changes a cached font's style (bold, italic, underline, size) in place. Owned by sub-plan 2.
3. **`ContextSlot` is internal to the engine**, not public API, until a game needs module-level
   state; games keep their state on their scenes.
4. **Execution is subagent-driven**, every sub-plan.
5. **The path guard.** This master plan goes on `LIVING_PLAN_FILES` when it is committed (the
   controller adds it); the sub-plans do not.

Still open: **the engine's own threads** (controller audio, voice recognition) see the default
context unless started with a copied context: start them with `contextvars.copy_context()`, or
keep them out of inner contexts entirely. Sub-plan 3 decides.
