# A readable Performance page, platform comparison, and benchmarks beside the replays

Status: proposed; only the game list is built (below). Part 1 stands alone. Part 2 starts only if
its audit says the benchmarks add enough.

Built since this was written: a list above the graphs picks one game, and only that game's graphs
load. It replaces the one-section-per-recording layout described under Today, and does the lazy
loading of stage 2 per game rather than per collapsed section.

## Goal

Make <https://terrysimons.github.io/glitchygames/quality/performance/> answer three questions
quickly: how is each game doing, how do two platforms compare, and where did a slowdown come from.

## Today

- The page is explanation text, a "Latest measurements" table, then one section per recording: a
  file path as its heading (`src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz`) and a
  1550 px iframe of Plotly charts. Seven recordings make about 11,000 px of graphs, all loading at
  once, with no controls.
- Machines appear as lines inside each chart and in a per-recording "Machines" bar chart. Nothing
  puts two chosen platforms side by side.
- Code: `src/glitchygames/replay/tools/performance_pages.py` builds the pages from the merged ledger
  (the engine's tool, usable by any game); `scripts/generate_performance_graphs.py` adds this site's
  paths and the snippet.
- `.benchmarks/` is read by nothing, and nothing compares its numbers.

## Part 1: the page

### Default view

1. **Overview first.** One table at the top: a row per recording, grouped under its game, a column
   per machine, each cell the latest average headroom FPS. Mark any cell whose p99 is over the frame
   budget. Show which commit each number came from.
2. **Headers people can read.** "Mr. Muncher" with "Golden replay" under it, not a file path. Keep the
   path as small text beneath, and keep today's anchors working if that is cheap. Names come from the
   project's settings and the recording's path, so other games using the engine's tool get them too.
3. **Details on demand.** Each recording's charts in a collapsed section whose iframe loads only when
   opened. The explanation text moves below the graphs, or to its own page.

### Comparing platforms

Dropdowns above a comparison section, all filled from the published `replay-ledger.jsonl`:

- **Game**, then **Recording** (narrowed by the game), or "All recordings".
- **Platform A** and **Platform B**.
- **Metric**: average headroom FPS (default), p50, p99, max, frames over budget.

It shows the two platforms' latest values, the ratio between them ("M4 Max is 12x the Pi"), and their
history. The selection lives in the URL, so a comparison can be linked. It is client-side JavaScript
with Plotly, since the site is static. Rules:

- **Say when commits differ.** Machines measure at different times: the Pi only when someone measures
  there. A comparison uses the newest commit both measured, or says plainly that the two numbers come
  from different commits.
- **Replays only, or live only.** Paced and unpaced numbers do not compare (the page says so today).
- **Mark CI machines**, as the Machines chart does.
- **Graceful empty states.** A platform with no row for a recording says so; no blank chart.

### Stages

1. Overview table and readable headers (generated at build time; no JavaScript needed).
2. Collapsed, lazily loaded recording sections; the text moved.
3. The comparison section. Check at phone width, since this site is read in a browser too.

## Part 2: benchmarks beside the replays

### What it would add

Replays show that a frame got slower; benchmarks can point closer to why. They also cover code the
recordings may not reach (Bitmappy), catch small changes lost in a whole frame's time, and compare
platforms per operation. They do not show whether a game holds its budget; replays do.

### Step 1: audit (the gate)

Go through what is there (34 test functions, 38 collected: `src/apps/bitmappy/tests/
test_bitmappy_benchmarks.py` 19, `tests/benchmarks/test_benchmarks.py` 12,
`test_channel_fade_relations.py` 2, `test_logging_cost.py` 1) and answer: what do they cover beyond
the replays, and do they hold still between runs on one machine? Stop here if the answer is "little".

### Step 2: recording them, if the audit passes

- **Exclude what is not a timing history.** `test_logging_cost.py` never runs on the Pi (SD card) and
  reports its own tables; `test_channel_fade_relations.py` asserts behaviour under load. Single-round
  benchmarks have no spread to show (their stddev is 0).
- **A Pi-safe nox session,** separate from `performance-test`, writing small row files the way
  `quality/replay-ledger/` does and landing them by the same code-tree rule. CI never measures.
- **One machine name.** pytest-benchmark's directories are per OS and Python
  (`Linux-CPython-3.14-64bit`), so every Linux machine would share one, and it calls the Pi's CPU
  `Cortex-A72` where the ledger says `Raspberry Pi 4 Model B Rev 1.4`. Rows use the ledger's name
  (`measure.this_machine`).
- **Show them with Part 1's controls:** the same Platform A and B, grouped by area (Bitmappy, engine).

### Step 3: clean up either way

Whatever the audit says, stop `performance-test` saving (`--benchmark-save`) into the repository, add
`.benchmarks/` to `.gitignore` and delete the committed files (they stay in git history). The 21
Darwin files are from Python 3.13, last changed in March. `performance-test` stays as CI's pass/fail
check. If the audit passes, import the Pi's three runs first.

## Decisions for the owner

1. **More than two platforms?** Recommended: exactly two in the comparison; the overview table already
   shows every machine.
2. **When do benchmarks get measured?** Recommended: by hand (`nox -s ...`) and in the pre-commit hook
   only if the Pi and M4 runs stay short. The Pi's run took under two minutes.
3. **Engine or this site?** Recommended: the overview, headers and comparison go in the engine's tool
   so every game gets them; only this site's paths stay in `scripts/`.
