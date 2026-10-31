# Engine Context

An engine context is the state one running game owns, so several games can run in one process
(the Arcade's demo tiles; design: `plans/2026-10-25-engine-context.md`). Ordinary games never
create one: they run in the default context, exactly as before. Only the six slots below are
per context today; the rest of the process-wide state (`GameEngine` and its `OPTIONS`,
`SceneManager.OPTIONS`, `FontManager`, `ResourceManager`, the event managers and the other rows
of the audit in `plans/2026-10-25-engine-context.md`) is still shared and belongs to later
sub-plans. The engine does not switch contexts yet: nothing in `src/` calls `.active()`, only
tests do.

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
   joystick subsystem are one per process.

## What belongs to a context today

| Slot | Module | Public functions |
|---|---|---|
| `glitchygames.pixel_snap.default_mode` | `src/glitchygames/pixel_snap.py` | `set_active_default_snap_mode`, `active_default_snap_mode`, `resolve_snap_mode` |
| `glitchygames.backgrounds.default_pattern` | `src/glitchygames/backgrounds.py` | `set_active_default_background_pattern`, `active_default_background_pattern`, `paint_default_background` |
| `glitchygames.input.state.current_input` | `src/glitchygames/input/state.py` | `current_input`, `set_current_input`, `reset_current_input` |
| `glitchygames.randomness.streams` | `src/glitchygames/randomness.py` | `engine_random`, `random_stream`, `numpy_stream`, `reset_streams`, `seed_engine_random`, `engine_random_seed`, `capture_stream_states`, `restore_stream_states` |
| `glitchygames.game_frames.clock` | `src/glitchygames/game_frames.py` | `game_frame_clock`, `restart_game_frame_clock` |
| `glitchygames.sources.registry` | `src/glitchygames/sources.py` | `active_sources`, `install_sources`, `reset_sources`, `push_scoped_sources`, `pop_scoped_sources`, `has_scoped_sources`, `redeliver_events`, `pending_redelivered_events`, `take_redelivered_events`, `discard_scope_posts`, `without_discarded_scope_posts`, `mark_frames_started`, `advance_frame_clock`, `set_frame_clock_seconds`, `frame_clock_seconds`, `observe_save_store_openings`, `stop_observing_save_store_openings`, `notify_save_store_opened`, `observe_device_answers`, `stop_observing_device_answers`, `notify_device_answer` |
| `glitchygames.scenes.scene.scene_managers` | `src/glitchygames/scenes/scene.py` | `SceneManager()`, `SceneManager._reset()` |

`tests/test_engine_context.py` proves, for every slot, that two contexts in one process never
see each other's values; a slot added without such a check fails the suite.
