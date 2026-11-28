# Nothing Replayed the AI Behaviour Recordings

- **Description**: `scripts/ai_behaviour/recordings/brave-adventurer-hazards.jsonl.gz` diverged at
  frame 0 on main from #328 (which changed Brave Adventurer's HUD labels) until #334 rebaselined
  it, and nothing failed. The two recordings in that directory are neither goldens nor bundled
  demos, and `tests/replay/test_recording_logical_names.py` listed them as read by
  `scripts/ai_behaviour/capture.py`, a script run by hand before an AI behaviour run.
- **Status**: Fixed (2026-11-28, `fix/ai-behaviour-recordings-are-replayed`).
- **Priority**: Medium: the AI behaviour tests' snapshots come from these recordings, and the
  first sign of a stale one came days later, misnamed.
- **Root Cause**: Two parts. The replayed-recordings check accepted any reader named in prose, so
  a script counted as one. And `capture.py` ran the replay in its own process inside
  `contextlib.suppress(SystemExit)`, dropping the replay's exit code: a headless replay stops at
  its first divergence (replay/driver.py, rule 8), so a stale recording was reported as
  `... ended before frames [1030, 1092, 1200]` (reproduced on 4e42b9a88 with today's recording).
- **Fix**: `test_every_ai_behaviour_recording_replays_to_its_end` (tests/test_ai_behaviour.py)
  replays each recording in the directory headless, through `replay_recording_headless`, the
  helper the bundled demos' test uses. `capture.recordings_replayed()` names them from the
  moments, and a second test holds that set equal to the directory's files. `capture.py` keeps
  the replay's exit code and, for anything but SUCCESS, says the recording no longer replays,
  with the exit code by name and how to rebaseline. Each entry in `RECORDINGS_NOT_REPLAYED` is
  now a `RecordingReader` naming the test that reads the recording.
- **Test gap**: Nothing replayed recordings outside goldens and demos, and the exemption list
  never checked that its readers were tests.
- **Invariant**: `test_every_listed_recording_names_a_test_that_exists`: each listed reader is
  `tests/...::test_...`, a function defined in that file. With a script named as the reader
  (the old entries), it fails naming both; with eb7deb256's Brave recording, the replay test
  fails with `Replay diverged at frame 0: sprite HudLabel#0`.
- **Files**: `scripts/ai_behaviour/capture.py`, `tests/test_ai_behaviour.py`,
  `tests/replay/test_recording_logical_names.py`.
- **Siblings (swept)**: Code that runs a replay in its own process and swallows its exit:
  `scripts/mirror_measurements/common.py:236` (frame-time measurement) and
  `tests/replay/removed_sprites_watch.py:93` (a child that reports watched sprites) do the same,
  so a divergence would cut their runs short without saying so. Not covered here.
  `scripts/frame_phase_probe.py:561` checks its own `finished` flag afterwards (not a sibling).
