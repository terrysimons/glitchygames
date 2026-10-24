# Replay Performance

How long the engine takes to process each frame of the recorded sessions (the golden replays in
`tests/fixtures/replays/` and the demos bundled with the games), commit by commit. Every
measurement replays a recording headless and unpaced on one machine (`--rebaseline`, which times
each frame's work without the pacing sleep), so a line moves only when the code got faster or
slower, or the machine changed. Times compare only on one machine: each machine (its CPU model)
and kind of run is its own line.

## What the graphs show

- **Processing time per frame**: the median (p50), the 99th percentile (p99) and the slowest
  frame (max) of one replay, in milliseconds, by commit (oldest on the left, labelled with the
  short hash). A frame's budget at 60 FPS is 16.7 ms.
- **Frames over budget**: frames whose processing alone took longer than the budget.
- **Live frame time**: for the runs that recorded a session live (paced, in a window), how long
  each frame really took, start to start: how steady pacing was. Replays have none.

Hover a point for the commit's date, when it was measured and whether the checkout had
uncommitted changes (a trial: `nox -s replay-metrics -- --allow-dirty`).

## Where the numbers come from

1. `nox -s replay-metrics` measures every recording not yet measured for the current commit on
   this machine and appends one row per recording to the run ledger's pending file
   (`test-results/replay-metrics/pending.jsonl`). It refuses a checkout with uncommitted changes.
2. `nox -s docs-deploy` measures first, then builds and publishes the site. The build merges the
   published ledger (from the `gh-pages` branch) with the pending rows and publishes the result
   with the site, at `quality/metrics/replay-ledger.jsonl`: publishing is how the history is
   kept. After a successful deploy the published rows leave the pending file.

A recording holds its own last ten runs too; `uv run python scripts/recording_report.py PATH`
prints them, which frames got slower or faster between runs (only frames that did the same
work, by their content hash), and where behaviour changed (the frames whose content hash
differs, with both runs' commits). Design:
`plans/2026-10-23-recording-metrics.md` (Parts 1 and 2).

Until a build generates them, this page has only this text.

--8<-- "docs/quality/metrics/performance_graphs.md"
