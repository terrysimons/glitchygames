# Replay Performance

How long the engine takes to process each frame of the recorded sessions (the golden replays in
each game's `tests/fixtures/replays/` and the demos bundled with the games), commit by commit. Every
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
- **FPS by commit**: the same runs as frames per second. A live run's line (solid) is the FPS
  it achieved (1 / its frame time); it is paced, so it never passes the target (the dotted
  line, 1 / the frame budget). A replay's line (dashed) is its headroom (1 / its processing
  time): how fast the work alone could run. Each point is the average, with a bar from the
  "5% low" to the "5% high": the mean of the slowest and of the fastest 5% of frames (at least
  one frame; pause frames count; a live run's first frame, timed from the clock's start, does
  not). The axis is logarithmic, as headroom runs to thousands. Paced and unpaced numbers do
  not compare: the processor slows down between paced frames.
- **Machines**: each machine's latest replay, as a bar of its average headroom FPS with the
  same 5% low and high, so platforms compare at a glance for the same recording. Replays only;
  machines marked **(CI)** measured on continuous integration's virtual runners, which are
  noisy.

The figures are stored in seconds and turned into FPS only for display. Measurements from
before them (2026-10-28) have no FPS point. `glitchygames measure` and `glitchygames report`
print the same FPS beside the milliseconds.

- **Slowest frame across the recording, by commit**: a heatmap per machine. Each column is a
  stretch of the recording (about 1% of it, start to end) and each row a commit; the color is
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
   (`glitchygames measure`) into the local pending file
   (`test-results/replay-metrics/pending.jsonl`), which a local build shows.

The measuring and the pages are the engine's tools, so any game can keep its own ledger the same
way ([Tools for any game](../architecture/gameplay_replay.md#tools-for-any-game)), with the
paths in its `[tool.glitchygames]` (ours: `ledger-directory`, `pending-ledger`,
`published-ledger`, `measured-paths`):

```bash
uv run glitchygames unmeasured --game <game>   # what is not measured yet on this machine
uv run glitchygames measure --game <game>      # measure it into the pending ledger
uv run glitchygames performance-pages <directory>   # the ledger and one graph page per recording
```

(`<game> --measure`, `--unmeasured` and `--performance-pages <directory>` are the same tools as
the game's own flags.) Our docs build makes these pages through `scripts/mkdocs_hooks.py` and
`scripts/generate_performance_graphs.py`, which only add our docs paths and the snippet below.

A recording holds its own last ten runs too; `uv run glitchygames report PATH` (or
`<game> --report PATH`) prints them, which frames got slower or faster between runs (only frames that did the same
work, by their content hash), and where behavior changed (the frames whose content hash
differs, with both runs' commits). Design:
`plans/2026-10-23-recording-metrics.md` (Parts 1 and 2).

## What logging costs

A benchmark rebaselines every golden replay and bundled demo headless three times, through the
same child command `glitchygames measure` runs: at `--log-level warning` (the replay tools' level
and a game's default: logging off), at `--log-level info` (what a bug report asks a player to run
with) and at `--log-level debug` (everything on). It is not part of the test run (`nox -s test`;
it takes under a minute), but CI runs it with the other benchmarks in the macOS job's
`nox -s performance-test`, where a failed rebaseline fails the job. Run it alone with

```bash
uv run pytest tests/benchmarks/test_logging_cost.py -o addopts= -p no:xdist --benchmark-only --dummy-only
```

or with every other benchmark in `nox -s performance-test`. It prints two tables and writes them
to `test-results/logging-cost.md`:

1. **Top loggers by volume at `debug`, per recording**: each recording's five chattiest
   loggers, with their records per frame, record count and share of all the records. A logger
   far ahead of the others (tens of records a frame) is where logging needs cleaning up: a
   `log.debug` inside a per-frame or per-sprite loop.
2. **Logging cost**: per recording, the mean processing time per frame at each level and the
   change of `info` and of `debug` against `warning`, the medians, each run's peak resident
   memory, the records per frame at each level and how much output `info` and `debug` wrote.
   The processing times are the engine's own per-frame measurements (what the performance
   graphs above plot), so the change is the time logging adds to each frame's work. Times
   compare only on one machine and between runs of the same table. The peak memory is the
   replaying child's (`n/a` on Windows), and its output goes to a file, so a large difference
   there means the game keeps records in memory.

On one Mac (2026-10-28) `info` cost every recording within 1% of `warning` (0.08 to 0.33 records
a frame), while `debug` doubled PaddleSlap's processing time per frame (about 10 records a
frame) and added 15% to Brave Adventurer's papyrus golden (about 33).

At `warning` no recording should emit an INFO or DEBUG record (the startup options block is one
CRITICAL record a run): a logger that does has a level set behind the command line's back
(BUGS.md #236), which `tests/replay/test_replays_log_quietly.py`
and `tests/test_logger_levels_at_import.py` fail on in the ordinary test run.

Until a build generates them, this page has only this text.

--8<-- "docs/quality/metrics/performance_graphs.md"
