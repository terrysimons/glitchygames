# Recording Metrics Part 1: Frame Performance History — Sub-plan

- **Date:** 2026-10-23
- **Status:** Done (2026-10-23)
- **Master:** `plans/2026-10-23-recording-metrics.md` (Part 1)
- **Sibling:** `plans/2026-10-23-recording-metrics-2-behaviour-change-map.md` (Part 2 shares
  the analysis module)

## Decisions (the user's, 2026-10-23)

- The history beyond the 10 runs a recording holds (the run ledger) is JSON Lines on the
  **gh-pages branch**; the docs site graphs it. Publishing the site is how it persists.
- CI does not deploy docs: the user runs `nox -s docs-deploy` on their Mac, which measures first.

## Pieces

1. **Analysis** (`glitchygames/recording_metrics.py`, a leaf beside `recording_history.py`;
   pydantic frozen models, `extra='forbid'`):
   - `processing_comparisons(header=..., frames=...)`: for each adjacent pair of runs
     (newer `i`, older `i + 1`), every frame whose `content_hash` is equal in both and has both
     times is "same work"; it got slower (faster) when the newer time exceeds (falls short of)
     the older by more than `threshold` (default 25%) and by more than `minimum_seconds`
     (default 0.2 ms, below timer noise). Same-direction frames at most `SPAN_GAP_FRAMES` apart
     form one span; spans shorter than `MINIMUM_SPAN_FRAMES` are counted, not listed. Frames
     whose hash differs are "different work", never a speed change.
   - The ledger: `LedgerRow` (the recording's repo-relative path, console script, origin
     `replay-metrics` or `recording`, the `MeasurementRun`, its `RunSummary`, the recording's
     content hash for the run, the frame count, frames whose behaviour changed against the
     recording's own newest run, the rebaseline's exit, whether uncommitted changes were
     allowed). `row_key` (recording + `measured_at` + machine) dedupes; `parse_ledger` reads
     leniently (an unreadable line is skipped and counted), `merge_ledgers` dedupes and orders
     by commit date then `measured_at`, `ledger_text` writes it.
   - `performance_series(rows=...)`: per recording, per machine (CPU model), the rows in commit
     order (the latest measurement of each commit), for the graphs.
2. **`nox -s replay-metrics`** (`scripts/replay_metrics.py measure`): every golden replay and
   bundled demo is rebaselined headless into a temporary file through its console script
   (`replay_command` of `glitchygames/testing/replays.py` plus `--rebaseline`, started with
   `run_command`), which measures processing times and records the run's provenance; one row
   per recording is appended to `test-results/replay-metrics/pending.jsonl` (gitignored), plus
   one `recording` row for each run the recording itself holds. A recording already measured
   (pending or published) for the same commit and machine is skipped unless `--force`. A tree
   with uncommitted changes is refused (`OPTIONS_REFUSED`) unless `--allow-dirty` (recorded in
   the row) or `--skip-dirty` (measures nothing, exits `SUCCESS`: what docs-deploy passes).
   The session runs in the project's environment (`uv run`): the package must be the checkout
   for the run to know its commit.
3. **docs-deploy**: `git fetch origin gh-pages` (a deploy needs it: it republishes the merged
   ledger; `--build-only` tolerates offline), `replay_metrics.py measure
   --skip-dirty`, the build (or `gh-deploy`), then, after a successful deploy only,
   `replay_metrics.py clear-published`: pending rows now in `origin/gh-pages`'s ledger are
   removed (never a blind clear).
4. **The hook** (`scripts/mkdocs_hooks.py` `on_pre_build`, after the complexity graphs):
   `scripts/generate_performance_graphs.py` merges `git show
   origin/gh-pages:quality/metrics/replay-ledger.jsonl` (absent ref or file: empty) with the
   pending rows, writes `docs/quality/metrics/replay-ledger.jsonl` (gitignored; published at
   `quality/metrics/replay-ledger.jsonl`), one plotly page per recording (processing p50, p99
   and max by commit; frames over budget; live runs' frame times; one series per machine) and
   the snippet `docs/quality/performance.md` includes. Files are rewritten only when their text
   changed (no `mkdocs serve` reload loop).

## Follow-ups (user decisions, 2026-10-23; done)

5. **Frame x commit heatmap** ("Yes"): each replay-metrics row carries a `FrameProfile`
   (`frame_profile`): the run's per-frame processing times cut into `PROFILE_BUCKET_COUNT`
   (100) buckets of consecutive frames (one per frame for a shorter recording), each keeping
   its slowest frame in integer microseconds, with the scenes run-length encoded by bucket; the
   frame ranges are derived from the frame count, so a row grows by 0.4-0.6 KB (measured on the
   goldens). Old rows parse (`profile` defaults to None) and have no heatmap line; neither do a
   recording's own runs. The page shows one heatmap per machine (x: bucket, y: commits in the
   graphs' order, colour: milliseconds; hover: frames, scene, time) and says it shows time only:
   whether the work changed is the behaviour-change map's job (bucket data cannot tell).
6. **Uncommitted changes are never published** ("Leave them out"; "Can they still be viewed
   locally if built locally?": yes): `LedgerRow.from_uncommitted_changes` (an `--allow-dirty`
   trial or a run whose checkout had changes); `publishable_rows` drops them. The mkdocs hook's
   `on_startup(command=..., dirty=...)` (MkDocs 1.4+) records the command: `gh-deploy` (or no
   startup event) leaves them out of the ledger file and every graph, `build`/`serve` show them
   labelled. `clear-published` removes only rows gh-pages holds, so they stay pending, local only.

## Tests

`tests/test_recording_metrics.py` (pure analysis, real recordings from `record_session`),
`tests/test_replay_metrics.py` (the script end to end on a throwaway copy of a golden replay, a
throwaway git repository for clean and dirty trees), `tests/test_generate_performance_graphs.py`
(a throwaway repository with a `gh-pages` branch and an `origin` remote).
