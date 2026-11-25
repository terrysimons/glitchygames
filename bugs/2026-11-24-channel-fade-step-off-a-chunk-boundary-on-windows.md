# A Channel-Fade Recording Stepped off a Mixer Chunk Boundary on Windows CI

- **Description**: `tests/audio/test_channel_fades.py::test_the_mixer_changes_a_channels_level_only_between_chunks[steal-delayed]`
  failed on 2026-11-24 in CircleCI's `test-python-3-15-windows` job 5594, #300's first run
  (`fix/midi-reaches-the-midi-manager` at `a4398e67`), after 7.77 s:
  `assert all(step % DEFAULT_BUFFER_SAMPLES == 0 for step in steps)` was false, so at least one
  level step in the steal-delayed recording fell off a 512-frame mixer chunk boundary. The
  assertion before it (`steps.size > 0`) held. #300 touches MIDI event routing only; its next run
  (`f32ba3d3`) passed on Windows.
- **Status**: Open. Not reproduced; cause unknown. One sighting confirmed from CircleCI's records.
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
- **Solution**: Not chosen. Next steps: (1) make the assertion report each off-grid step and its
  offset, and keep the failing recording under `test-results/` (stored by CI); (2) check the recording's length against the chunks played, which would show a lost
  or repeated chunk directly.
- **Sweep**: Not done yet: the other cases of the same test and the fade tests that assert on
  sample positions.
- **Tests**: None yet.
- **Reporter**: The coordinator (Ledger), from CircleCI job 5594.
- **Date Reported**: 2026-11-24
- **Files**: `tests/audio/test_channel_fades.py`, `tests/audio/channel_fade_analysis.py`,
  `tests/audio/channel_fade_probe.py`, `src/glitchygames/audio/diagnostics.py`
  (`DEFAULT_BUFFER_SAMPLES`, `find_discontinuities`).
