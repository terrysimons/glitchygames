# A Playback That Fails to Open Its Devices Ended the Game

- **Description**: when `GameEngine.enter_playback_devices` raised as a demo or an instant replay
  was entered (`SceneManager._enter_playback`), the game ended instead of going on with the live
  scene. The entry's error was logged ("could not start; the live game goes on"), then ending the
  scope (`_exit_playback`) raised a second error, which nothing contained:
  `MissingValueError: the live rumble controller the playback set aside is missing`.
- **Status**: Fixed on `feature/midi-devices` (`3153e043b`)
- **Priority**: Medium. It takes a failure to open the recorded devices, and then the game is lost.
- **Root Cause**: the order in `_enter_playback`. It set the session, called
  `enter_playback_devices`, and only then set the live rumble controller aside
  (`_live_rumble_behind_scope`). `_exit_playback` requires that controller whenever there is a
  session. A failure between the two left a session with no controller set aside, so the
  `required(...)` in `_exit_playback`'s `finally` raised before the live scene was made active, the
  held events were redelivered or the frame effects were cleared.
- **History** (read with `git log -S` and each commit's own code):
  - `bb51239d5` (#95, 2026-10-21): the rumble was put back only if it had been set aside, so a failed
    entry was safe.
  - `fab884c1f` (#96, 2026-10-24): that check became `assert self._live_rumble_behind_scope is not
    None`. It held then: no device was opened in `_enter_playback` yet.
  - `357ad302b` (2026-11-01, the unified input devices bug sweep): added `enter_playback_devices`
    between the session and the rumble. The defect dates from here.
  - `c304708a9` (#271, 2026-11-22): the assert became `required(...)` (same outcome, another error).
    Its comment, "with nothing in between to fail", was already false.
- **Test gap**: `test_error_while_entering_restores_the_live_game` fails the entry in the played
  scene's `setup()`, after both steps. No test made the devices' opening fail through the scene
  manager; `test_live_midi_ports_come_back_when_entering_fails_part_way` calls the engine's enter
  and exit directly, with no rumble in it.
- **Fix**: the rumble is set aside right after the session, before anything that can fail, and the
  comment in `_exit_playback` says so.
- **Tests**: `tests/replay/test_playback_scope.py`,
  `TestErrorsOpeningTheScopesDevices::test_error_opening_the_scopes_devices_restores_the_live_game`
  (`open_connected_joysticks`, `open_connected_midi_ports`). With the old order put back
  (2026-11-24) both cases fail with the `MissingValueError` above; with the fix both pass.
- **Class**: teardown that requires state a failed entry may not have set.
- **Sweep** (2026-11-24, by reading every step of `_exit_playback`, the `required(...)` calls in
  `scenes/scene.py`, `GameEngine.exit_playback_devices` and `replay/playback.py`'s teardown):
  - `_live_rumble_behind_scope`: this bug; tested.
  - `exit_playback_devices`: does nothing when nothing was set aside; what it puts back is set aside
    before the first open, and it releases a controller manager that may not exist without error.
    Tested for failures in `open_connected_joysticks`, `open_connected_midi_ports`, `adopt_device`
    and `adopt_midi_port`. Not tested: a failure in `open_connected_controllers`,
    `adopt_controllers` or the controller manager's construction, and one in `recorded_devices`
    (before anything is set aside).
  - A failure after the doors are pushed and before the session: `_exit_playback` does nothing, and
    the entry pops the doors itself. Tested (`test_a_failure_entering_the_scope_pops_the_scoped_doors`).
  - The random streams, frame clock, FPS event timer, `previous_scene` and polled input: held by the
    session or its sources, which exist before the session is set. Safe by construction; the streams
    are tested by `test_error_while_entering_restores_the_live_game`.
  - `_cleanup_current_scene`: skipped while the live scene is still the active one, and an error in
    it is logged. Tested (`test_a_played_scene_whose_cleanup_fails_is_logged_and_the_live_game_returns`).
  - `_remove_scope_supervision`: empties lists, which may be empty. Safe by construction.
  - Posts and held events (`_forget_posts_still_pending`, `redeliver_events`): a scope that never
    pumped is handled (`has_pumped`), and run by the new test, which waits a held key release.
  - `PlaybackSources.on_uninstalled` (the silencer, the post tracker): run by the failed entries
    tested above, with nothing raised.
  - The journal: suspended last in the entry, so a failed one leaves it running, and `resume` does
    nothing to one not suspended. Safe by construction.
  - The other `required(...)` in a scope's path, the frame time the scope asked its doors for, is
    read only while there is a session. Safe by construction.
  - `terminate`: ends a scope only if there is one, and by then the failed entry has cleared it.
- **Not swept**: teardown outside `scenes/scene.py`, `replay/playback.py` and
  `exit_playback_devices`.
- **Reporter**: the reviewer of the MIDI devices plan's Task 5 (agent review, Ruling K)
- **Date Reported**: 2026-11-24
- **Files**: `src/glitchygames/scenes/scene.py` (`_enter_playback`, `_exit_playback`),
  `src/glitchygames/engine/game_engine.py` (`enter_playback_devices`, `exit_playback_devices`),
  `tests/replay/test_playback_scope.py`
