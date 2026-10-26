# Engine Context

An engine context is the state one running game owns, so several games can run in one process
(the Arcade's demo tiles; design: `plans/2026-10-25-engine-context.md`). Ordinary games never
create one: they run in the default context, exactly as before.

## Rules

1. Per-context state is a `ContextSlot` (`src/glitchygames/engine_context.py`), declared once at
   module level with a unique dotted name and a factory.
2. Code reads a slot when it needs it, `current_context().value(slot=...)`, never as its module
   is imported: the test suite scans the engine and every workspace member for such reads.
3. A context makes each value with the slot's factory the first time it is read there.
4. `current_context()` is the context switched to last in this thread or asyncio task, else the
   default context.
5. `with context.active():` makes a context current and puts the previous one back when the
   block ends, also by an exception; switches nest. An asyncio task made inside a switch keeps
   it, a switch held across an `await` is never seen by another task, and a thread sees it only
   when started with `context=contextvars.copy_context()`.
6. A context owns only what its slots hold. The display, the mixer, SDL's event queue and the
   joystick subsystem are one per process.

## What belongs to a context today

| Slot | Module | Public functions |
|---|---|---|
| `glitchygames.pixel_snap.default_mode` | `src/glitchygames/pixel_snap.py` | `set_active_default_snap_mode`, `active_default_snap_mode`, `resolve_snap_mode` |
| `glitchygames.backgrounds.default_pattern` | `src/glitchygames/backgrounds.py` | `set_active_default_background_pattern`, `active_default_background_pattern`, `paint_default_background` |
| `glitchygames.input.state.current_input` | `src/glitchygames/input/state.py` | `current_input`, `set_current_input`, `reset_current_input` |
| `glitchygames.randomness.streams` | `src/glitchygames/randomness.py` | `random_stream`, `numpy_stream`, `reset_streams`, `seed_engine_random`, `engine_random_seed`, `capture_stream_states`, `restore_stream_states` |
| `glitchygames.sources.registry` | `src/glitchygames/sources.py` | `active_sources`, `install_sources`, the scoped sources, the frame clock, held events, observers |
| `glitchygames.scenes.scene.scene_managers` | `src/glitchygames/scenes/scene.py` | `SceneManager()`, `SceneManager._reset()` |

`tests/test_engine_context.py` proves, for every slot, that two contexts in one process never
see each other's values; a slot added without such a check fails the suite.
