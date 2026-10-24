# Recording Metrics Part 2: Behaviour-Change Map — Sub-plan

- **Date:** 2026-10-23
- **Status:** Done (2026-10-23)
- **Master:** `plans/2026-10-23-recording-metrics.md` (Part 2)
- **Sibling:** `plans/2026-10-23-recording-metrics-1-frame-performance-history.md` (Part 1's
  ledger counts changed frames with the same functions)

## What it answers

"Run 1 -> run 0 (abc1234 -> def5678): behaviour changed in frames 812-940 (scene Game), 3
spans": the commit range and the exact frames to look at, the first half of a bisect.

## Pieces

1. **Analysis** (`glitchygames/recording_metrics.py`):
   - `recorded_measurement_runs(header=...)`: every `measurement_runs` entry, read leniently
     (as `latest_measurement_run` reads the newest), None for an unreadable one, so indexes stay
     aligned with the frames' histories.
   - `behaviour_changes(header=..., frames=...)`: for each adjacent pair of runs (newer `i`,
     older `i + 1`), frames whose `content_hash[i]` differs from `content_hash[i + 1]`, grouped
     into spans of consecutive frames (`FrameSpan`: first and last frame, frame count, the first
     frame's scene); frames lacking either hash are counted as unknown, never as changed.
     `BehaviourChange.describe()` gives the line above.
2. **Report** (`scripts/recording_report.py PATH`, a thin CLI): each run's provenance (commit
   short hash, CPU, power source, `measured_at`, `rebaselined_from`) and summary (stored, else
   computed: `recording_run_summaries`), Part 1's processing comparisons (`--threshold PERCENT`,
   `--minimum-ms`), then the behaviour-change map. Exit codes: `SUCCESS`, `MISSING_INPUT` for a
   missing file, `UNUSABLE_INPUT` for one that is not a recording.

## Tests

`tests/test_recording_metrics.py` (spans from hand-built and real frames) and
`tests/test_recording_report.py` (the script on a real recording rebaselined in-process twice,
missing and corrupt files).
