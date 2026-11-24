# MIDI Events Skip the MIDI Manager

- **Description**: `GameEngine.process_midi_event` (`src/glitchygames/engine/game_engine.py`) passed
  `MIDIIN` and `MIDIOUT` to `scene_manager.handle_event` and returned True. `SceneManager.handle_event`
  acts only on `QUIT` (and a focused sprite's `KEYDOWN`), so a MIDI event reached nothing: the
  `MidiEventManager` the engine builds in `_initialize_event_managers` was never called, and a scene's
  or sprite's `on_midi_in_event` / `on_midi_out_event` never ran. As the event counted as handled,
  `--no-unhandled-events` (on in every test) could not catch it either. Found 2026-11-22 by the
  architecture docs scrub (session ac); reproduced with a `MIDIIN` and a `MIDIOUT` posted to SDL's
  queue on a real engine: `process_events` returned True and the scene received neither. No game was
  affected: nothing in the repository posts MIDI events (`pygame.midi.midis2events`) or handles them.
- **Status**: Fixed (2026-11-22, `fix/midi-reaches-the-midi-manager`)
- **Priority**: Low (no game uses MIDI yet; the first one would have received nothing, silently)
- **Root Cause**: MIDI was never wired to its manager. The 2021 dispatcher logged MIDI as
  "UNIMPLEMENTED" (4290fa55), later "NOT IMPLEMENTED" while returning True. `7c5895d2` (2025-10-19,
  "Fix drag and drop png support") replaced the log line with `self.scene_manager.handle_event(event)`,
  a call that ignores MIDI, instead of the manager's handlers as every other family has. The move to
  `src/` (#105, b29f85fc) carried it as it was. Nothing depended on the routing: `handle_event` did
  nothing with it.
- **Test gap**: `tests/engine/test_game_engine.py::TestProcessMidiEvent` mocked
  `scene_manager.handle_event` and asserted it was called, pinning the implementation, not that a
  scene receives the event; and `tests/engine/test_engine_event_system.py`, which posts each family's
  events through the real path to a recording scene, had no MIDI test. `tests/events/test_midi_events.py`
  calls the manager directly, so it never saw that the engine skips it.
- **Fix**: `process_midi_event` calls `self.midi_manager.on_midi_in_event` and `on_midi_out_event`,
  which forward to the active scene through the scene manager. A scene with no MIDI handler now gets
  the stub's `unhandled_event`, as for any other family (it raises under `--no-unhandled-events`).
- **Regression tests** (each failed before the fix):
  - `tests/engine/test_engine_event_system.py::TestEngineEventSystem::test_midi_events_reach_the_scenes_midi_handlers`
    (posted to SDL's queue, pumped and dispatched by a real engine);
  - `tests/engine/test_game_engine.py::TestProcessMidiEvent::test_midi_in` and `test_midi_out`,
    changed to assert the MIDI manager receives the event (they asserted the bug before).
- **The class and its invariant**: an event manager the engine builds that its events go around.
  `tests/engine/test_engine_event_system.py::TestEngineEventSystem::test_every_event_manager_the_engine_builds_is_the_one_its_events_go_through`
  hands one event of each family to the engine's handler for its type, with the built manager stood
  in for by a recording double, and requires that manager to receive it and the event to count as
  handled. It first requires the set of `*EventManager`s the engine built to equal its table, so a new
  manager without an entry fails. It failed before the fix for `midi_manager` alone.
- **Sweep** (every manager `_initialize_event_managers` builds):
  - Covered, each family through its own manager: app, audio, controller, drop, game, joystick,
    keyboard, mouse, touch, window; MIDI now too.
  - No manager to bypass: text events go to the scene manager's `on_text_*_event` directly
    (BUGS.md #200 item 1); the font manager handles no events.
  - Not covered by this invariant: a single type inside a family that its dispatcher misses (as
    `WINDOWTAKEFOCUS` was, BUGS.md #200 item 1). The invariant sends one event per family.
- **Reporter**: Claude (session ac found it; session 21f7657c fixed it)
- **Date Reported**: 2026-11-22
- **Files**: `src/glitchygames/engine/game_engine.py`, `tests/engine/test_engine_event_system.py`,
  `tests/engine/test_game_engine.py`
