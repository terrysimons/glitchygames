# A Test Found SDL's Own Events Queued at Its Start

- **Description**: `tests/test_harness_empties_the_event_queue.py::test_without_a_display_there_is_no_queue_to_read`
  (added by #331) failed whenever it was not preceded by a test of the same file: run alone,
  `assert [4352, 4352, 32768, 32782, 32768, 32784, 32773, 32865] == [32865]`; after a test that
  resized the display, `[WINDOWSIZECHANGED, USEREVENT]`. It assumed an empty queue at its start.
- **Status**: Fixed (2026-11-27, `fix/every-test-starts-with-an-empty-queue`).
- **Priority**: High for CI. It was on main (`7991846cc`), so any shuffled run (the pre-push
  `test-random`, CircleCI's rolled orders) could fail on it; it refused #328's push.
- **Root Cause**: Nothing emptied the queue at a test's start. #331 empties it at a test's end,
  and does so deliberately before the harness puts a resized or moved display back, because
  restoring a display queues SDL's own window events, which are no test's fault. Those events were
  therefore left for the next test, and the first test on a worker found SDL's start-up
  notifications (audio device added, window shown, focus gained, ...).
- **Evidence**: Reproduced on main's code with the test alone, every run. A pytester run of the
  harness (`test_every_test_starts_with_an_empty_queue`) failed both ways before the fix: the
  worker's first test found 7 events starting with `AudioDeviceAdded`, the test after a resize
  found `WindowSizeChanged`.
- **Fix**: `ensure_pygame_graceful_quit` (`tests/harness.py`) empties the queue, unreported, after
  it has started the display and shown the canvas, so every test starts with an empty queue. This
  hides no leak: what a test leaves is reported at its own end, before the display is restored.
- **Test gap**: The new tests ran only in their file's order and in one lucky shuffle; none was run
  alone or after a test that resized the display, and nothing stated the invariant "every test
  starts with an empty queue".
- **Invariant**: `test_every_test_starts_with_an_empty_queue` runs the harness in a fresh process
  (the only place SDL's start-up events are real) and checks the queue is empty for the worker's
  first test and for a test after a resize.
- **Files**: `tests/harness.py`, `tests/test_harness_empties_the_event_queue.py`.
- **Siblings (swept)**: Every test asserting the queue's whole contents
  (`tests/test_recording.py`'s `TestDiscardCustomEventsQueuedBeforeTheRun`,
  `TestDiscardEventsLeftAtTheRunsEnd` and `TestEventOrigin`;
  `tests/replay/tools/test_scripted_sessions.py::test_the_supervisor_places_and_posts_per_frame_input_on_the_active_scene`;
  `src/games/brave-adventurer/tests/test_brave_adventurer_modes.py::TestTheTitleScreen::test_a_gamepads_b_or_back_quits`)
  passed alone on main: each empties the queue before posting. Covered: all.
