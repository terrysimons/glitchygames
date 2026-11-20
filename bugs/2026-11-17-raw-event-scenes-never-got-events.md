# A Scene's `process_event` Never Got Any Event in a Running Game

- **Description**: The event-system docs offer incremental porting: a scene that defines `process_event(event)` receives every raw pygame event itself, in order, instead of the `on_*_event` callbacks (docs/architecture/event_system.md, docs/glitchygames/index.md). `GameEngine.process_events` looked for that method on `self._active_scene`, a field set to None at start-up that nothing ever assigned: the scene manager holds the active scene. In a running game the check never matched, so a scene relying on `process_event` got no events at all, with no error. No shipped scene uses it, so nothing visible broke.
- **Status**: Fixed (2026-11-17, branch `chore/keep-memory-triage-records`, #219)
- **Priority**: Medium (a documented porting path silently did nothing)
- **Root Cause**: the engine kept its own copy of the active scene. The 2021 scene refactor (`d01d4526`, "Refactor logging, and scenes & simplify boilerplate") commented out the engine's `active_scene` property and setter, the only code that assigned `_active_scene`, and left the read in `process_events`: since then the field was always None
- **Test gap**: the raw-event tests set `engine._active_scene` by hand, a state no run reaches, so they passed against the field rather than against a running game; no test drove a raw-event scene through a real frame. Found while building `/sprite` (`feat/sprite-command`), whose spawn handler read the same field and dropped every live spawn until its replay test, which runs a real game, caught it.
- **Solution**: `process_events` reads `self.scene_manager.active_scene`; the `_active_scene` field is removed, so the scene manager's is the only active scene.
- **Tests** (`tests/engine/test_game_engine.py`): `test_a_raw_event_game_gets_its_events_in_a_running_frame` runs a real headless game one frame (got `[]` before the fix); `test_the_scene_managers_raw_event_scene_gets_the_raw_events`; `test_the_engine_keeps_no_active_scene_of_its_own`, the guard against a second copy; the nine existing raw-event tests now set the scene on the scene manager.
- **Siblings** (tests setting a private engine attribute that no run assigns, swept across every test): none; the other two hits (`engine._shutdown`, `engine._initialize_event_managers`) replace methods with mocks. Other classes were not swept.
- **Reporter**: Claude
- **Date Reported**: 2026-11-17
- **Files**: `src/glitchygames/engine/game_engine.py`, `tests/engine/test_game_engine.py`
