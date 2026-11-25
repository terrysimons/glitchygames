# Engine Context

An engine context is the state one running game owns, so several games can run in one process
(the Arcade's demo tiles; design: `plans/2026-10-25-engine-context.md`). Ordinary games never
create one: they run in the default context, exactly as before.

What is per game today: the twenty-two slots below, and the engine's and the scene manager's own
attributes (an engine's `options`, `game`, `running_game`, `event_handlers` and its event
bookkeeping; a scene manager's `engine_options`), which belong to the object, so two engines
never share them. The old class-level names of that state (`GameEngine.OPTIONS`,
`SceneManager.OPTIONS`, `Sprite.SPRITE_COUNT`, ...) are now read-only views of the current game's
(below). What is still one per process is the audit's shared rows (S1-S20 in
`plans/2026-10-25-engine-context.md`): the display and window services, the mixer and music
(an inner game's sound is kept off the channels the heard game uses: Inner contexts, rule 9),
SDL's event queue and its blocked types, the joystick subsystem, the process services (signal
handlers, the SDL environment, `pygame.init()`), the player's clipboard and files, and a few
recursion guards and registries; later sub-plans keep an inner context off each of them. A game
runs in another context as an inner game: a recording replayed through the game's own command,
unchanged, inside a context with a render target of its own (Inner contexts, below; Arcade
sub-plan 3, `plans/2026-11-12-arcade-3-inner-game.md`). The sound-file loader also switches to a
scratch context for building a file's waves (`src/glitchygames/audio/assets.py`).

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

!!! warning "Read a slot when you need it, never at import"
    A module-level, class-body or default-argument read of `current_context().value(slot=...)`
    runs once, in the default context, so every other context would share that one value. The
    scan in `tests/test_engine_context.py` finds only literal reads: a module-level call of a
    helper that reads a slot, or a reader under another name, passes it unseen (BUGS.md #228
    item 1).

## What belongs to a context today

???+ note "The twenty-two slots, with their public functions"

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
    | `'glitchygames.render_target.target'` | `src/glitchygames/render_target.py` | `set_render_target`, `render_target`, `is_inner_context`, `display_surface`, `request_hosted_start`, `hosted_start_requested`, `note_started_engine`, `take_started_engine` (the context's render target and its hosted start) |
    | `'glitchygames.recording.private_event_queue'` | `src/glitchygames/recording.py` | `private_event_queue` (an inner context's own event queue: its posts go there and its replay doors drain it, never SDL's) |
    | `'glitchygames.audio.route.audio_route'` | `src/glitchygames/audio/route.py` | `is_audible`, `set_audible` (whether the context's sound is heard: the default context audible, a new inner game silent; `InnerGame.audible`, `InnerGame.set_audible`) |
    | `'glitchygames.audio.voices.inner_channels'` | `src/glitchygames/audio/voices.py` | `inner_context_partition`, `take_heard_set`, `give_back_heard_set`, `heard_set_start`, `release_inner_context_channels`, `plain_plays_followed`, `plain_play_channel_indices`, `stop_plain_plays_and_mute_the_live_pool`, `current_inner_context_channel_indices` (an inner context's channels: its partition, live pool, heard set while heard, and the plain plays it started while heard) |
    | `'glitchygames.feature_flags.options'` | `src/glitchygames/feature_flags.py` | `flag_state`, `flag_state_lines`, `take_flag_options` (what the context's latest engine was asked of each feature flag) |

`tests/test_engine_context.py` proves, for every slot, that two contexts in one process never
see each other's values; a slot added without such a check fails the suite.

## Inner contexts

An inner context runs a game inside another game (an Arcade tile). The rules
(`src/glitchygames/render_target.py` and `src/glitchygames/inner_game.py`, whose docstrings are
the contract; `plans/2026-11-12-arcade-3-inner-game.md`):

1. **A context with a render target is inner** (`is_inner_context()`). The default context has
   none, so an ordinary game draws on the display as before. The engine reads
   `display_surface()` (the render target, else the display) where it read
   `pygame.display.get_surface()`.
2. **An inner context owns no window or process service** (audit rows S1 and S2): it never
   opens, resizes, captions or presents the window, never sets its icon, and never changes SDL's
   driver variables or restarts the display or mixer (`--headless` included).
3. **Its frames are drawn, never presented**, and made opaque after each one (`make_opaque` on
   the render target, BUGS.md #142's rule: in the display's format on cocoa the target carries
   alpha, and its host copies it). Neither SCREEN shake nor any overlay (the debug overlay, a
   replay's status bar, an onion skin) is drawn in it: those belong to the outer game.
4. **It posts to a queue of its own** (`private_event_queue()`, audit rows S5 and S6): while the
   queue is enabled, `post_event` and `post_input_event` append there and the context's replay
   doors drain it, never SDL's queue, and never block real input at SDL. An inner game never
   takes an event another context posted, nor leaves one for it to take; its recorded QUIT ends
   only that game.
5. **`GameEngine.start()` in it is a hosted start**: it builds the game up to its first frame,
   keeps the engine for the host (`take_started_engine()`, once) and returns. No signal
   handlers, no blocking loop, no crash boundary (whose teardown would quit pygame for every
   context), and neither `_begin_start` nor `_begin_run` (no options block; `--profile` and
   `--list-input-devices`, which those run, are refused rather than ignored). A context that asked with `request_hosted_start()` keeps
   the request for its whole life, so a host makes a fresh context for each game.
6. **`InnerGame` is the host's handle** (`src/glitchygames/inner_game.py`):
   `InnerGame.replay(command=..., path=..., name=..., size=..., arguments=())` makes a fresh
   context with a render target of `size` and its private queue enabled, and calls the
   installed command's own entry point with `sys.argv` swapped to `--replay-trace PATH
   --headless`, then the outer game's command line (up to a bare `--`, less every refused flag
   below with its values), then `arguments`, for that call only: so `uv run arcade --sound-cache
   ram` runs its tiles on `ram`, an Arcade recording itself or replaying its golden still plays
   them, and a host's own arguments win (argparse keeps the last value). A recording still overrides every option but
   its run-local ones. `step()` runs one unpaced frame; `finish()` ends the run
   and settles the replay's result into `outcome` (`InnerGameOutcome`: `RUNNING`, `ENDED` or
   `FAILED`, the frames run, the replay's report, the error), without quitting pygame or
   exiting. Only recordings run inner so far (a live game is the Arcade's sub-plan 7): live play,
   every tool flag, `--rebaseline`, `--audit`,
   `--compare-trace`, the frame stream, a watched replay's restart options, `--profile`,
   `--list-input-devices`, `--help` and `--version` (with argparse's prefixes and short-flag
   clusters, an exact engine flag being itself) in the host's `arguments` raise
   `InnerGameRefusedError` before anything is built.
7. **A failure belongs to the inner game**: an `Exception` or `SystemExit` while building,
   stepping or finishing makes its outcome `FAILED`; the host and every other inner game go on,
   and the default context is current again after every call. `KeyboardInterrupt` and
   `GeneratorExit` propagate.
8. **An inner game writes nothing to stdout**: the replay's report, which a headless replay
   prints, is the outcome's `report`, logged at INFO.
9. **Only the heard game is heard** (Arcade sub-plan 4, `plans/2026-11-13-arcade-4-sound.md`;
   [Sound](sound.md), "Inner games"): each context has an audio route (`is_audible()`); a new
   inner game is silent and keeping one heard is its host's job (`InnerGame.set_audible`; the
   engine lets two be heard at once, one per heard set, and refuses a third). The host
   declares its inner games once, before anything plays (`Scene.INNER_GAMES`, or
   `reserve_inner_game_channels`), and the mixer grows that once to two heard sets and a live
   pool per inner game; an inner build never partitions the mixer. A silent tile touches no
   channel (its plain plays find every channel reserved, its voice table makes no mixer call,
   its live chunks play at volume 0 on its own pool); switching a heard tile silent fades its
   voices, stops its plain plays and mutes its live chunks, never another context's sound.
10. **A tile's demo is a `DemoPlayer`** (Arcade sub-plan 5,
    `plans/2026-11-20-arcade-5-playback-core.md`; `src/glitchygames/demo_player.py`, whose
    docstring is the contract): an engine module that holds one `InnerGame` replaying a recording
    and needs no game or Arcade. `tick(elapsed_seconds=..., budget=..., most_frames=None)` pays a
    `RecordedFramePacer` the host's frame time and runs the frames it owes within a
    `TickBudget` (`src/glitchygames/replay/pacer.py`, the watched replay's pacing, shared), which
    a host hands to its players in turn; frames are never skipped (a player that cannot keep up
    plays in slow motion, `is_behind`, `effective_speed`). At its end the demo loops: the game is
    finished (giving its channels back) and a new one built from frame 0 in a new context,
    `on_new_game` running before its first frame, the build charged to the budget. A divergence
    restarts it once, then freezes it on the diverged frame (`DemoOutcome`, `DemoState`).
    `fast_forward(to_frame=..., budget=...)` runs silent, sliced and resumable toward a poster
    frame (`poster_frame`, drawn from the host's named stream), building a waiting loop or
    restart itself, so it gets there or the player freezes (`is_frozen`). The budget is real time
    (`clock.measured_seconds`), so how far a tile gets in a host frame depends on the machine: a
    recorded Arcade session replays its inputs exactly, but not its tiles' progress frame for
    frame (tiles may be a frame or two apart, as a watched replay's viewer already is), and
    nothing compares an Arcade session's tile pixels frame for frame.

An inner game never changes SDL's blocked event types: every engine call that blocks or allows
goes through `events.set_event_types_allowed`, which changes nothing in an inner context (its
private queue is all it reads). What an inner game can still change in the process (each in
`plans/future-work.md`): `pygame.mixer.music` (no game uses it), SDL's key repeat (the text-input
demo's tile changes the outer game's), text input start and stop (the engine's text widgets),
the mouse cursor's visibility (Bitmappy's canvas), pygame's default font resolution (an inner
`FontManager` sets it from its `--font-dpi`), `SDL_MOUSE_FOCUS_CLICKTHROUGH` when unset
(`os.environ.setdefault`). (An inner game registers nothing with `pygame.register_quit`: pygame
can't undo it, so only the host's own engine does.) The proof is
`tests/test_every_recording_replays_inside_an_inner_game.py`: every golden and bundled demo,
replayed as an inner game beside another, unevenly interleaved, inside an outer window of
another size, matches its solo headless replay's digests frame for frame and draws the pixels it
draws alone, with every tile silent and with the first switched heard for the middle third of
its recording and back (Bitmappy's demo, which measured the outer window, reads its own screen
since 2026-11-20: `bugs/2026-11-20-bitmappy-tile-read-the-hosts-window.md`). The same file
proves it through `DemoPlayer`: each pair as two players ticked with uneven time and budgets,
the first fast-forwarded to a seeded poster frame, looped, and heard for the middle third of its
second run, and again in slow motion with one frame each of a shared budget a tick; every game
they build ends with its solo replay's digests and every tick draws the recording's pixels alone
at its frame (the budgets run on a fake clock there, so the runs are the same on every machine).
Ten stand-in inner games stepped once per outer frame cost about 0.29 ms on the machine it was
measured on (`test_ten_inner_games_per_outer_frame`, an Apple M4 Max, 2026-11-12); what demo
players of the real bundled demos cost is under Performance.

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
  that every test ends in the default context. A workspace member's slot is checked in the
  member's own tests, listed in a `MEMBER_ISOLATION_CHECKS` dict (Bitmappy's onion skinning
  manager: `src/apps/bitmappy/tests/test_bitmappy_onion_skinning.py`), since engine tests never
  import a member; `tests/test_engine_context_source_guards.py` finds that dict by AST and fails
  on a member slot without its check, or a check naming no slot.
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

What each kind of read costs (Apple M4 Max; measured on Python 3.14, before the tests moved to 3.15,
except the `ten demo players` row, measured on Python 3.15):

| Read | Cost per read | Measured |
|---|---|---|
| `attribute read` | 30 ns | `engine.options`; Task 17, 2026-11-10, median (0.33 slot reads) |
| `instance property` | 19 ns | `timeit`; the owner, 2026-10-28 |
| `slot read` | 90 ns | `current_context().value(slot=...)`; Task 17, 2026-11-10, median (the reference) |
| `read-only view` | 210 ns | `GameEngine.OPTIONS` with an engine running; Task 17, 2026-11-10, median (2.32 slot reads) |
| `current_engine()` | 113 ns | Task 17, 2026-11-10, median (1.25 slot reads) |
| `context switch` | 430 ns | `with context.active():` entered and left; `timeit`; the owner, 2026-10-28 |
| `ten demo players` | 6.9 ms | one Arcade frame of ten `DemoPlayer`s of the real bundled demos sharing an 11 ms budget; Arcade sub-plan 5's Task 6, 2026-11-20, Apple M4 Max, Python 3.15, median (Demo players, below) |

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

### Demo players

Measured by `tests/benchmarks/test_demo_player_benchmarks.py` (pytest-benchmark under
`--benchmark-only`, dummy drivers, one run on 2026-11-20 on an Apple M4 Max with Python 3.15, the
machine's one-minute load 3.2 to 3.7): ten `DemoPlayer`s of the real bundled demos (all but the text-input demo), each paid one
60 Hz Arcade frame a round and sharing one `INNER_FRAME_BUDGET_SECONDS` (11 ms) budget:

- **Per Arcade frame:** median 6.9 ms (minimum 3.2 ms, mean 7.1 ms) for about ten frames a round
  (mean 9.97, at most 17 after a hitch); every player kept speed 1.00 over 1,200 rounds (Mr.
  Muncher 1.02). The budget was spent in 19 of the 1,200 rounds, and the players looped twelve
  times in all over the 1,200. The worst round, 376 ms, matches a Bitmappy build (below; Bitmappy looped once),
  not traced round by round: one build held the Arcade for about 22 frames.
- **A restart's build** (`InnerGame.replay`, the call decision 7 charges to the budget), five
  per demo, the first with the harness's emptied sound and sprite caches: dt, joystick and
  text-input demos 5 to 10 ms; PaddleSlap 7 to 11 ms; Clockwork Keep 7 ms (26 ms cold); Drawing
  Fire 13 to 19 ms; Mr. Muncher 24 ms (207 ms cold); Brave Adventurer 33 to 71 ms; Zombies Ain't
  My Neighbors 100 to 176 ms (860 ms cold), of which about 160 ms is reading and decoding its
  1,538-frame recording again (a profile of one warm build); Bitmappy 355 to 450 ms. A profile
  of one Bitmappy build splits it into about 275 ms waiting for the AI worker process it has just
  started to exit (its `main()` shuts its workers down in a `finally` after `engine.start()`,
  which in an inner game returns as soon as the game is built, so each build starts a worker
  and joins it) and about 147 ms in `load_ai_training_data` (it renders 71 sprite files as text
  for a log line even at `--log-level error`). That join waits up to
  `AI_WORKER_JOIN_TIMEOUT_SECONDS` (2 s) and then 1 s more after terminating, so a slow worker
  start costs about 3 s: the likely reading of the 3.1 s build the plan's first measurement saw
  (neither that 3.1 s nor its 73 to 180 ms readings is reproduced here).
- **The ten posters' fast-forward** (seed 5, the 11 ms budget shared each Arcade frame): about
  2.6 s in total (three rounds, 2.60 to 2.68 s), 180 Arcade frames (3 s at 60 Hz) before every
  tile stands at its poster.

Not measured: a Raspberry Pi (the budget will bind there, which is what slow motion is for), and
a build in the browser (Pyodide).
