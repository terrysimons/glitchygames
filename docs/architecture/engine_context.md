# Engine Context

An engine context is the state one running game owns, so several games can run in one process
(the Arcade's demo tiles; design: `plans/2026-10-25-engine-context.md`). Ordinary games never
create one: they run in the default context, exactly as before.

What is per game today: the seventeen slots below, and the engine's and the scene manager's own
attributes (an engine's `options`, `game`, `running_game`, `event_handlers` and its event
bookkeeping; a scene manager's `engine_options`), which belong to the object, so two engines
never share them. The old class-level names of that state (`GameEngine.OPTIONS`,
`SceneManager.OPTIONS`, `Sprite.SPRITE_COUNT`, ...) are now read-only views of the current game's
(below). What is still one per process is the audit's shared rows (S1-S20 in
`plans/2026-10-25-engine-context.md`): the display and window services, the mixer and music,
SDL's event queue and its blocked types, the joystick subsystem, the process services (signal
handlers, the SDL environment, `pygame.init()`), the player's clipboard and files, and a few
recursion guards and registries; later sub-plans keep an inner context off each of them. The
engine does not run a game in another context yet; the one switch in `src/` is the sound-file
loader's scratch context for building a file's waves (`src/glitchygames/audio/assets.py`).

## Rules

1. Per-context state is a `ContextSlot` (`src/glitchygames/engine_context.py`), declared once at
   module level with a unique dotted name and a factory. `ContextSlot` is internal to the
   engine: only engine modules declare slots, and games keep their state on their scenes. The
   tests' `COUNTER_SLOT` exists only to test the class.
2. Code reads a slot when it needs it, `current_context().value(slot=...)`, never as its module
   is imported: the test suite scans the engine and every workspace member for such reads.
3. A context makes each value with the slot's factory the first time it is read there.
4. `current_context()` is the context switched to last in this thread or asyncio task, else the
   default context.
5. `with context.active():` makes a context current and puts the previous one back when the
   block ends, also by an exception; switches nest. An asyncio task made inside a switch keeps
   it, a switch held across an `await` is never seen by another task, and a thread sees it only
   when started with `context=contextvars.copy_context()` (or on an interpreter whose
   `sys.flags.thread_inherit_context` is set, such as free-threaded 3.14 builds).
6. A context owns only what its slots hold. The display, the mixer, SDL's event queue and the
   joystick subsystem are one per process. So are read-only caches of values computed only from their keys,
   such as the background pattern cache and the engine's own compiled sounds
   (`glitchygames.audio.library.ENGINE_SOUND_CACHE`: the CRT power-on's, compiled once per
   process and shared by every context as read-only samples; each context makes its own `Sound`
   over them).
7. `current_engine()` (`glitchygames.engine`) is the engine made last in the current context,
   until it shuts down; with none running it raises `NoRunningEngineError`.

## What belongs to a context today

| Slot (its `ContextSlot` name) | Module | Public functions |
|---|---|---|
| `'glitchygames.pixel_snap.default_mode'` | `src/glitchygames/pixel_snap.py` | `set_active_default_snap_mode`, `active_default_snap_mode`, `resolve_snap_mode` |
| `'glitchygames.backgrounds.default_pattern'` | `src/glitchygames/backgrounds.py` | `set_active_default_background_pattern`, `active_default_background_pattern`, `paint_default_background` |
| `'glitchygames.input.state.current_input'` | `src/glitchygames/input/state.py` | `current_input`, `set_current_input`, `reset_current_input` |
| `'glitchygames.randomness.streams'` | `src/glitchygames/randomness.py` | `engine_random`, `random_stream`, `numpy_stream`, `reset_streams`, `seed_engine_random`, `engine_random_seed`, `capture_stream_states`, `restore_stream_states` |
| `'glitchygames.game_frames.clock'` | `src/glitchygames/game_frames.py` | `game_frame_clock`, `restart_game_frame_clock` |
| `'glitchygames.sources.registry'` | `src/glitchygames/sources.py` | `active_sources`, `install_sources`, `reset_sources`, `push_scoped_sources`, `pop_scoped_sources`, `has_scoped_sources`, `redeliver_events`, `pending_redelivered_events`, `take_redelivered_events`, `discard_scope_posts`, `without_discarded_scope_posts`, `mark_frames_started`, `advance_frame_clock`, `set_frame_clock_seconds`, `frame_clock_seconds`, `observe_save_store_openings`, `stop_observing_save_store_openings`, `notify_save_store_opened`, `observe_device_answers`, `stop_observing_device_answers`, `notify_device_answer` |
| `'glitchygames.scenes.scene.scene_managers'` | `src/glitchygames/scenes/scene.py` | `SceneManager()`, `SceneManager._reset()` |
| `'glitchygames.audio.waves.registry'` | `src/glitchygames/audio/waves.py` | `current_wave_registry` (the named waves a sound file or `Wave` registers; `AudioEngine.waves`) |
| `'glitchygames.audio.engine.audio_engine'` | `src/glitchygames/audio/engine.py` | `SceneManager.audio`, `existing_audio_engine`, `install_audio_engine`, `discard_audio_engine` |
| `'glitchygames.engine.game_engine.current_engine'` | `src/glitchygames/engine/game_engine.py` | `current_engine()` (the engine made last in the context; the `GameEngine` views read it) |
| `'glitchygames.recording.internal_posts'` | `src/glitchygames/recording.py` | `post_event`, `post_input_event`, `start_tracking_internal_posts`, `stop_tracking_internal_posts`, `reset_internal_post_tracking`, `forget_pending_posts`, `pending_internal_posts`, `live_game_posts`, `pending_code_post_count` |
| `'glitchygames.performance.adaptive_clamping.managers'` | `src/glitchygames/performance/adaptive_clamping.py` | `AdaptiveClamping()` (the context's performance manager: its FPS statistics and shutdown report) |
| `'glitchygames.events.base.shared_instances'` | `src/glitchygames/events/base.py` | `ResourceManager()` subclasses (the shared event managers and the `FontManager`: one per class per engine context), `ResourceManager.release_shared_instances`, `release_shared_instance` |
| `'glitchygames.fonts.font_manager.options'` | `src/glitchygames/fonts/font_manager.py` | `FontManager.OPTIONS` (a view of it), `FontManager.set_font_system`, `get_font_system` |
| `'glitchygames.sprites.bitmappy_sprite.singletons'` | `src/glitchygames/sprites/bitmappy_sprite.py` | `Singleton()`, `SingletonBitmappySprite()`, `FocusableSingletonBitmappySprite()` (one per class per engine context) |
| `'glitchygames.events.base.unhandled_event_types'` | `src/glitchygames/events/base.py` | `unhandled_event` (the event types already logged under `--debug-events`) |
| `'glitchygames.sprites.sprite.counters'` | `src/glitchygames/sprites/sprite.py` | `sprite_counters()` (the sprite creation counters and breakpoints the teardown report logs), `Sprite.break_when` |

`tests/test_engine_context.py` proves, for every slot, that two contexts in one process never
see each other's values; a slot added without such a check fails the suite.

## Read-only views

The class attributes that held one game's state are now read-only views. Each is read-only, the
current game's, and `None` (or its empty default) outside a game; engine code reads the instance
or the slot's owner function instead, and so does any code that writes.

| View | What it reads | Outside a game | Where to write |
|---|---|---|---|
| `GameEngine.game` | the current engine's game class (`engine.game`; the scene it built is `engine.running_game.instance`) | `None` | the engine's own: engine.game |
| `GameEngine.OPTIONS` | the current engine's parsed options | `None` | the engine's own: engine.options |
| `GameEngine.EVENT_HANDLERS` | the current engine's dispatch table, event type to bound handler | `None` | the engine's own: engine.event_handlers |
| `GameEngine.LAST_EVENT_MISS` | the `on_*_event` name the current engine last looked up and missed | `None` | the engine's own: engine.last_event_miss |
| `GameEngine.MISSING_EVENTS` | the handler names the current engine missed (each logged once) | `None` | the engine's own: engine.missing_events |
| `GameEngine.UNIMPLEMENTED_EVENTS` | the event types no handler of the current engine took (each logged once) | `None` | the engine's own: engine.unimplemented_events |
| `SceneManager.OPTIONS` | the current context's scene manager's copy of its engine's options (never makes a manager) | `None` | the manager's own: manager.engine_options (the game_engine setter sets it) |
| `FontManager.OPTIONS` | the current context's font options | an empty dict | the current context's font options in place (FontManager.OPTIONS.update(...)) or FontManager.set_font_system(...) |
| `Sprite.SPRITE_COUNTERS` | the current context's sprite counters, by sprite type | an empty dict | glitchygames.sprites.sprite.sprite_counters().counters |
| `Sprite.SPRITE_BREAKPOINTS` | the current context's sprite breakpoints (`Sprite.break_when`) | `None` (no breakpoints) | a breakpoint with Sprite.break_when(...) |
| `Sprite.SPRITE_COUNT` | how many sprites the current context made | `0` | glitchygames.sprites.sprite.sprite_counters().count |
| `glitchygames.performance.performance_manager` | `AdaptiveClamping()`, the current context's performance manager (made on first read) | a fresh manager, with no statistics yet | nothing: AdaptiveClamping() is the current context's manager; patch its methods |

Read on an instance, a class view answers that object's own state (`engine.OPTIONS` is
`engine.options`). The rules (`src/glitchygames/read_only_views.py`):

- A view stores nothing: its functions run on every read.
- A view is declared in its class body (`ReadOnlyView`, or `ClassOnlyView` for a name each
  instance keeps as its own attribute, `engine.game`). A module view is a name its module marks
  in `READ_ONLY_MODULE_VIEWS` and answers in its `__getattr__`; a module `__getattr__` alone
  (`glitchygames.audio`'s lazy `VoiceAssistant`) is not a view.
- Writing or deleting a view, on its class, an instance or its module, raises
  `ReadOnlyViewError` naming where to write instead (the last column).
- A class-level read costs about 2.3 slot reads (Performance, below), so engine code never
  reads a view: it reads its own objects (`self.options`, `self.event_handlers`), a slot once per
  function into a local, or the owner function (`sprite_counters()`, `AdaptiveClamping()`).

`current_engine()` answers the engine itself, for code that has none at hand.

## Guards

- `tests/test_engine_context.py`: every slot's isolation check, the import-time read scan, and
  that every test ends in the default context.
- `tests/test_read_only_views.py`: every view has a check (two contexts each see their own value,
  a fresh context reads `None` or the empty default, and writing it raises naming where to
  write); the engine never reads a view; this page lists every view and where to write, and the
  costs below stay within the gate.
- `tests/test_process_state_guard.py`: the audit as an allowlist scan of the engine and every
  member; module- or class-level mutable state that is neither a slot nor listed with its audit
  row and reason fails the suite.
- `tests/test_shared_font_cache_guard.py`: nothing changes a cached font's style in place, so the
  process-wide font caches (audit row R9) stay safe to share.
- `tests/test_suite_collection.py`: no living document writes a read-only view.

Each game's performance report covers that game alone (its context's `AdaptiveClamping()`); an
outer game that steps others (the Arcade's wrapper) reports the aggregate of every game it steps.

## Performance

What each kind of read costs (Apple M4 Max, Python 3.14):

| Read | Cost per read | Measured |
|---|---|---|
| `attribute read` | 30 ns | `engine.options`; Task 17, 2026-11-10, median (0.33 slot reads) |
| `instance property` | 19 ns | `timeit`; the owner, 2026-10-28 |
| `slot read` | 90 ns | `current_context().value(slot=...)`; Task 17, 2026-11-10, median (the reference) |
| `read-only view` | 210 ns | `GameEngine.OPTIONS` with an engine running; Task 17, 2026-11-10, median (2.32 slot reads) |
| `current_engine()` | 113 ns | Task 17, 2026-11-10, median (1.25 slot reads) |
| `context switch` | 430 ns | `with context.active():` entered and left; `timeit`; the owner, 2026-10-28 |

The four Task 17 rows are the medians of gate (c)'s per-read benchmarks
(`tests/benchmarks/test_engine_context_benchmarks.py`, `-k reading`, pytest-benchmark, one run on
2026-11-10, the machine's one-minute load 5.2). Each benchmarked function makes one read, so each
of those four medians includes the same one Python function call (about 18 ns: the attribute
read's 30 ns here against 12 ns under `timeit`): they compare with each other, not with the two
`timeit` rows, which have no call around the read. They replace Task 1's and Task 16's `timeit`
best-of-five figures (slot read 61 ns, view 126 ns or 2.07 slot reads, `current_engine()` 79 ns or
1.30 slot reads, attribute 12 ns).

What they mean per frame:

- Engine code reads its own objects (`self.options`, `self.event_handlers`: the dispatch runs per
  event), so those reads cost no more than before. What is new per frame: two slot reads per pump
  (the internal-post tracker, `pending_internal_posts()` and `forget_pending_posts()`, about
  50 ns more each than the old global), and one `clock.raw_counter_seconds()` per unpaced step,
  which is BUGS.md #268's fix, not the contexts.
- The slot-backed state a frame reads (the doors, the random streams, the polled input, the frame
  clock, the sprite counters, the internal-post tracker) costs roughly 1-3 µs a frame by the
  plan's estimate (not counted read by read). Task 17 (2026-11-10) measured it against main before
  the plan (cd60bd42), on a bare frame step of about 19-21 µs, in one informational longer pair
  (~70-85k rounds each, load 5.6-5.7): the frame step about 0.6-1.7 µs more, and dispatching a
  batch of two events about 0.3-1.2 µs more (minimum to median). That frame-step figure runs
  `paced=False`, so it includes #268's clock read. In gate (c)'s six short per-call pairs (two sets of
  three, load 3.6-4.1), pytest-benchmark's 5% median check failed 3 of 6 for the frame step and
  2 of 6 for event dispatch, never all three of a set, so not a regression by the gate's rule. In the games' goldens and bundled demos neither p50 nor
  p99 moved beyond timer noise (gate (a)).
- The Arcade pays about 0.4 µs per game per tick for switching.
- Each game's performance report covers that game alone; an outer game's (the Arcade wrapper's)
  is the aggregate of every game it steps.

The rules that follow:

- Engine code never reads a view (`test_the_engine_never_reads_a_view` enforces it).
- Games, tools and tests may read views for convenience, but read their own object or a local in
  a hot loop.
- Task 17's gate keeps the numbers honest and is never relaxed: the recordings A/B against the
  base with behaviour unchanged, the per-call benchmarks, and each read's ratio to a slot read
  (`READ_RATIO_LIMITS` in `tests/benchmarks/test_engine_context_benchmarks.py`: a view at most 4
  slot reads, `current_engine()` at most 2; `tests/test_read_only_views.py` checks this table
  against them).
