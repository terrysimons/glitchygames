# The Docs Deploy Ran Out of Memory on the Complexity Graphs

- **Description**: CircleCI's `deploy-docs` failed after the merges of #334 (3f15acb58, job 6400)
  and #335 (4074969f5, job 6415): `mkdocs gh-deploy` ended with exit code -9 during the hook's
  "Complexity graphs" stage, 579 s and 621 s into the step. The site stayed on eb7deb256's docs.
  A rerun fails the same way.
- **Status**: Fixed (2026-11-28, `fix/complexity-graphs-read-one-revision-at-a-time`).
- **Priority**: High: no docs deploy could succeed again, and every commit made it worse.
- **Root Cause**: `scripts/generate_complexity_graphs.py`'s `wily_revisions` parsed every wily
  revision file and kept each one whole: every function's measurements (`detailed`) and every
  operator's totals, for every file in the repository. On 2026-11-28 that was 435 files, 4.57 GB
  of JSON (the largest 150.7 MB), and the process peaked at 9.66 GB. CircleCI's large machine has
  8 GB, so the kernel killed the build (SIGKILL, -9). Each commit adds a revision; eb7deb256's
  deploy (job 6376) still fit, taking 599.7 s on the stage.
- **Evidence**: `/usr/bin/time -l` on a local generation: 9,664,151,552 bytes maximum resident.
  A probe wrapping each step: peak 1.34 GB before `wily_revisions`, 9.66 GB after it; the steps
  after it added under 0.01 GB. The job's own log: the stage started, then nox reported exit
  code -9 with no Python traceback (a kernel kill, not an exception).
- **Fix**: `drawn_measurements` keeps only what the explorer draws, as each revision is read:
  the `METRICS`' totals of `RANKED_PACKAGE`'s paths. Only one whole revision is held at a time.
  Generated from 4074969f5 (442 commits) with the old code and the new, the peak fell from
  10.03 GB to 2.05 GB and the explorer's data was identical byte for byte (164,298 bytes). The hook's stage lines now end with the process's peak memory
  (`peak_memory_text`), and the docstring's "about a minute" for the wily build is corrected.
- **Test gap**: Nothing measured the docs build's memory, and the stage log gave time only.
  The docstring's estimate had gone stale (about a minute; 600 s on CircleCI), so nobody saw
  the curve.
- **Invariant**: `test_wily_revisions_keep_only_what_the_explorer_draws`: a revision keeps
  nothing but the metrics' totals for the ranked package (failed before the fix, showing
  `detailed`, an unlisted operator and a path outside the package kept). Every stage line
  carries its peak memory (`STAGE_DONE`, `STAGE_FAILED`), so growth shows in the deploy log
  before the machine's limit.
- **Files**: `scripts/generate_complexity_graphs.py`, `scripts/mkdocs_hooks.py`,
  `tests/test_generate_complexity_graphs.py`.
- **Siblings (swept)**: `join_moved_paths` reads and rewrites one revision file at a time (the
  probe's peak before `wily_revisions`, 1.34 GB, includes it). Not measured: the performance
  graphs' and browser build's memory (they now log it on their stage lines).
- **Not a near miss**: eb7deb256's stage ran 599.7 s with nothing printed (the generator's own
  log lines do not reach mkdocs' output), close to CircleCI's default 10-minute limit on a
  silent step. The deploy step sets `no_output_timeout: 60m` (.circleci/continue_config.yml), so
  that limit is an hour; the strict docs build in `checks-linux`, where 10 minutes did kill a
  build (job 5089, #261), writes a placeholder and never generates. wily's build time still
  grows with the history, and the stage lines now log it.
