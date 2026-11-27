# A Test Left Its Event in pygame's Queue for the Next One

- **Description**: `tests/world/test_gameplay_replay.py::TestRecordedBatchMerging::test_an_unrepresentable_recorded_value_is_injected_as_recorded_and_noted_once`
  failed with `AttributeError: 'pygame.event.Event' object has no attribute 'sprite'` when it ran
  after `tests/test_ai_console.py::test_a_sprite_named_like_a_path_is_saved_in_the_sprites_folder`
  on the same worker.
- **Status**: Fixed (2026-11-26, `fix/event-queue-leak`).
- **Priority**: High for CI. Any PR failed whenever the shuffle put the two tests in that order on
  one machine, and a CircleCI "rerun from failed" keeps the first run's order, so it failed again
  on every rerun (#328: jobs 6258 and 6262).
- **Root Cause**: The AI console's `/sprite` posts a sprite-spawn event
  (`glitchygames.sprite_spawn`, `recording.post_input_event`) to SDL's real queue. Four console
  tests never took it, and SDL's queue is process-wide, so it was still queued for the worker's
  next test. `ReplaySources.pump_events` merges every queued event at or above `USEREVENT` into its
  batch as the game's own post (`replay/driver.py` `_sort_live_events`), so the replay test's batch
  held a spawn event, which has no `sprite`.
- **Evidence**: CircleCI job 6258 (#328 at `f41d3c2c7`, Linux node 3, seed 1289560758). The 300
  tests before the failure in that machine's order (its `junit.xml`) were bisected to the console
  test. Reproduced on main `806d1ea24` with those two tests alone, every run; `--showlocals` showed
  the stray spawn in the batch. A survey of every test in one full run (33,144) found 4 that left a
  game event: all four in `tests/test_ai_console.py`, each a spawn. 2,465 others left only SDL's
  own notifications (window size, shown, focus, enter; audio device added).
- **Fix**: The harness empties SDL's queue after every test (`tests/harness.py`
  `end_of_test_event_queue_problems`, called from `ensure_pygame_graceful_quit` beside the sound
  checks), so nothing a test leaves reaches the next one. It fails the test that left an event at
  or above `USEREVENT` or a `QUIT`, naming the event's registered name and fields. The four console
  tests now take the spawn they cause and check that one was posted.
- **Test gap**: Nothing failed a test that left events in SDL's queue. Other process-wide state
  (blocked event types, the mixer, child processes, context slots) had end-of-test checks; the
  queue had none.
- **Not reported, still emptied**: SDL's own notifications (queued whenever a display or the mixer
  starts, so no test is at fault) and input events (on a real driver they can come from the
  machine itself). An event posted by a thread after its test ended would be reported on the test
  that was running when it arrived.
- **Timed posts (found by #331's CI)**: CircleCI job 6275 (macOS, `846d5d7f8`) failed
  `tests/test_host.py::TestGameHost::test_run_is_the_blocking_loop` on an FPSEVENT. A frame posts
  FPSEVENT at the end of `_finish_frame`, after its own pump, once half of `fps_log_interval_ms`
  has passed on the frame clock, so the last frame of a run can leave one that no frame takes, and
  only on a machine slow enough to cross that time. Reproduced every time with the interval at 0.
  The engine already emptied the queue at a run's end (`discard_events_left_at_the_runs_end`,
  BUGS.md #276), but only in `GameEngine`'s teardown, which a stand-in engine never reaches. Now
  `SceneManager.end_frames` empties it too, where every driver of the frame loop ends (`start`,
  the host, an inner game, the replay viewer), and so does the golden-trace harness's
  `GoldenTraceSceneManager.uninstall`, which steps frames itself. To find every test that could
  leave a timed post, the whole suite ran with every frame posting FPSEVENT: three more did
  (`test_frame_seconds_sets_dt`, ended now by `uninstall`; the timer-pacing and benchmark frame
  steppers, which now end their runs with `end_frames`). That run also hung two workers in
  `tests/inner_game_tiles.py` (an FPSEVENT every frame, never a real setting): not investigated.
- **Files**: `tests/harness.py`, `tests/test_harness_empties_the_event_queue.py`,
  `tests/test_ai_console.py`, `src/glitchygames/scenes/scene.py`,
  `src/glitchygames/replay/tools/golden_traces.py`, `tests/test_host.py`,
  `tests/scenes/test_scene_timer_pacing.py`, `tests/benchmarks/test_engine_context_benchmarks.py`.
- **Siblings (swept)**: The private event queue of an inner game and the record of pending internal
  posts are context slots, isolated per test (`tests/test_engine_context.py`). Blocked event types
  are put back after each test (`tests/engine_written_state.py`). `pygame.time.set_timer` never
  runs in engine code (`tests/test_engine_doors.py` forbids it) or in tests. Covered: all.
- **Seen on the way, not fixed**: The console line and the spawn carry the model's sprite name as
  given (`#1 ../../evil added`); only the file name is cleaned (`sprites/saved_sprites.py`
  `sprite_file_name`). The name is a label, not a path, so nothing is written outside the sprites
  folder.
