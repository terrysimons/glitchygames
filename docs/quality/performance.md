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

- **Slowest frame across the recording, by commit**: a heatmap per machine. Each column is a
  stretch of the recording (about 1% of it, start to end) and each row a commit; the colour is
  the slowest frame of that stretch. Hover a cell for its frames, its scene and the time. It
  shows time only: whether the work itself changed (frames whose content hash differs) is what
  `glitchygames report` shows. Measurements from before per-frame profiles have no row.

Hover a point for the commit's date and when it was measured.

Measurements made on a checkout with uncommitted changes (a trial: `nox -s replay-metrics --
--allow-dirty`) are never published: the published site leaves them out, while a local build
(`mkdocs build`, `mkdocs serve`, `nox -s docs-serve`) shows them, labelled "uncommitted
changes". They stay in the pending file after a deploy, so they remain visible locally only.

## Where the numbers come from

1. **Every commit carries the measurements of its code.** A pre-commit hook
   (`scripts/measure_staged_replays.py`, installed by `.envrc`) works out the *code tree* of what
   is being committed (`src/glitchygames/code_tree.py`: only what can change how the replays run,
   the engine, games, demos, apps, recordings, `uv.lock` and `pyproject.toml`). When this machine
   has not measured that code yet, it measures every golden replay and bundled demo on it and
   adds one small file per recording to the commit, under `quality/replay-ledger/`. A docs commit
   after a measured one is instant; code that arrived by a merge from `main` or a rebase is
   measured by the next commit (or by hand: `uv run python -m scripts.measure_staged_replays`,
   then commit). `SKIP=replay-metrics git commit ...` skips it.
2. **The site shows what landed on `main`.** Every docs build reads the repository's row files
   and keeps those whose code tree is the code tree of a commit that added rows: on `main`, the
   squash merge, so each is shown under the commit its code landed in. Rows of a branch's
   intermediate commits match none and are left out. A local build shows a branch's rows before
   it merges; only `main` is ever published (`nox -s docs-deploy` refuses anything else).
   After each merge to `main`, CircleCI deploys the site with them; CI never measures (its
   machines vary).
3. The history measured before this (rows naming their commit) was moved into the repository
   too (`scripts/import_published_ledger.py`). `nox -s replay-metrics` still measures by hand
   into the local pending file (`test-results/replay-metrics/pending.jsonl`), which a local build
   shows.

A recording holds its own last ten runs too; `uv run glitchygames report PATH` (or
`<game> --report PATH`) prints them, which frames got slower or faster between runs (only frames that did the same
work, by their content hash), and where behaviour changed (the frames whose content hash
differs, with both runs' commits). Design:
`plans/2026-10-23-recording-metrics.md` (Parts 1 and 2).

Until a build generates them, this page has only this text.

--8<-- "docs/quality/metrics/performance_graphs.md"
