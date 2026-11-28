# A Channel-Fade Recording Stepped off a Mixer Chunk Boundary on Windows CI

- **Description**: `tests/audio/test_channel_fades.py::test_the_mixer_changes_a_channels_level_only_between_chunks[steal-delayed]`
  failed on 2026-11-24 in CircleCI's `test-python-3-15-windows` job 5594, #300's first run
  (`fix/midi-reaches-the-midi-manager` at `a4398e67`), after 7.77 s:
  `assert all(step % DEFAULT_BUFFER_SAMPLES == 0 for step in steps)` was false, so at least one
  level step in the steal-delayed recording fell off a 512-frame mixer chunk boundary. The
  assertion before it (`steps.size > 0`) held. #300 touches MIDI event routing only; its next run
  (`f32ba3d3`) passed on Windows.
- **Second sighting** (2026-11-28): the `[bus-fade]` case, CircleCI job 6450 (#337 at `355ccbec3`,
  which touches only `scripts/ai_behaviour/` and two tests), after 18.3 s, in the fixed-order
  Windows machine 2. This time `steps` were all on the grid and the last assertion failed: a
  discontinuity spike off `{0, 511}` within its chunk. Nothing was kept or printed. #337's rerun
  of the failed job is the record of whether it repeats.
- **Status**: Open; cause unknown. Two sightings (jobs 5594 and 6450). Evidence capture added
  2026-11-28 (`fix/channel-fade-failures-keep-their-evidence`): the next failure keeps its proof.
- **Priority**: Medium (it fails a split Windows job and costs a run).
- **What the test checks**: the module docstring says the recordings (made in a child process on
  SDL's disk audio driver, which sleeps a buffer's length per chunk) assert "only what holds
  however the machine is loaded"; where a level changes is one of those. The failure says that
  premise did not hold once on a Windows runner.
- **Root Cause**: Unknown. Suspects, none measured: the disk driver's recording losing or
  repeating part of a chunk when its thread is late, which would shift every later sample off the
  chunk grid; a tone's own step exceeding `own_largest_step` near a boundary; something specific to
  Windows' timer resolution.
- **Test gap**: the failure does not print the offending step positions or their offsets within a
  chunk, so one off-grid step and a whole shifted recording look the same. The recording is made
  under pytest's temporary folder (`channel_fade_analysis.recording_directory`), so CI does not
  keep it, and job 5594's artifacts hold no `channel-fade-<case>.md` trial report either.
- **Baseline**: two trial reports from a passing macOS run (2026-11-20, the overnight audit's
  benchmark run) are kept beside this record, in
  `bugs/2026-11-24-channel-fade-step-off-a-chunk-boundary-on-windows/`:
  `macos-2026-11-20-channel-fade-steal-delayed.md` and `...-steal-immediate.md`. They were written
  by `tests/benchmarks/test_channel_fade_relations.py` (run only under `--benchmark-only`) from the
  same recorded cases: each trial's action chunk, the stolen and stealer levels, and whether the
  stealer sounds from then on. A failing Windows recording's trials can be set against them.
- **Healthy baseline** (macOS, 2026-11-28, all four cases): every recording is whole 512-frame
  chunks (235,520 to 256,512 frames, remainder 0), every step at offset 0 and every spike at 0 or
  511.
- **Evidence capture (done, 2026-11-28)**: `check_on_the_chunk_grid`
  (tests/audio/channel_fade_analysis.py) replaces the two bare `all(...)` asserts. A failure names
  every off-grid step and spike as `frame F: chunk C + offset`, gives the recording's length in
  chunks (and any leftover frames), and copies the recording to
  `test-results/channel-fade-failed/channel-fade-<case>.raw`, which CI stores. Planted on a real
  bus-fade recording with 3 frames cut inside chunk 100, it reports every later position at
  offset 509 and "500 chunks and 509 frames (not whole...)": a lost partial chunk shows as one
  offset shared by everything after it. `test_every_recording_is_whole_mixer_chunks` checks the
  premise every chunk-counting check here rests on, so a shifted recording fails as a recording.
- **Solution**: Not chosen; waiting for a kept recording. If the next failure's recording is not
  whole chunks, the cause is the disk driver losing part of a chunk under a starved thread
  (as it loses whole silences: `record`'s docstring), and the fix belongs in how the recording is
  made or checked, not in the mixer's behaviour.
- **Sweep** (2026-11-28): all four cases share the test and now the check. The level and plateau
  tests read levels per chunk from the file's start (`chunk_levels`, `trial_chunks`), so a shifted
  recording blurs them too: the whole-chunks test covers that premise for all of them. Outside
  these tests, `find_discontinuities` is used only by its own tests.
- **Tests**: `test_a_recording_on_the_chunk_grid_passes_and_keeps_nothing`,
  `test_an_off_grid_step_is_named_with_its_chunk_and_offset_and_the_recording_kept`,
  `test_a_recording_of_part_chunks_is_named_as_one` (made-up recordings, no audio), and
  `test_every_recording_is_whole_mixer_chunks`.
- **Reporter**: The coordinator (Ledger), from CircleCI job 5594.
- **Date Reported**: 2026-11-24
- **Files**: `tests/audio/test_channel_fades.py`, `tests/audio/channel_fade_analysis.py`,
  `tests/audio/channel_fade_probe.py`, `src/glitchygames/audio/diagnostics.py`
  (`DEFAULT_BUFFER_SAMPLES`, `find_discontinuities`).
