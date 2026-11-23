# The Heaviest Tests All Run on One CI Machine

- **Description**: a split CircleCI test job (Linux, Windows: `parallelism: 3`) divided the suite file by file (`tests/circleci_test_split.py`, `circleci tests split --split-by=timings --timings-type=filename`), so a file's tests always shared one machine. tests/test_every_recording_replays_inside_an_inner_game.py (1,585 s summed, up to 153 s a case: each case replays a reference in a child process beside two inner games) went whole to one machine. On #285's Windows job (5051), that machine's test step took 1,914 s against 1,312 and 1,297 s for the others. The owner (2026-11-23): putting the most taxing tests together on one machine is the worst case (load, timeouts, races), not only the slowest. The shuffled order (pytest-randomly) only reorders within a machine.
- **Status**: Fixed on `ci/split-by-test-spread-heavy-replays` (2026-11-23); CI must confirm the timings and the memory
- **Priority**: Medium. Every split job's slowest machine sets its time, and concentrated load makes timing-sensitive and child-process tests flakier there.
- **Root Cause**: the split's unit was the file. It was chosen to save memory: a machine that skips other machines' files never imports them (about 150 MiB, 2026-11-19). That kept every case of a heavy file together.
- **Test gap**: the split's tests checked that the machines' file shares fit together. None checked how the tests within one file spread, or where the heaviest tests landed.
- **Decision** (the owner, 2026-11-23, through the coordinator): split by test, accepting the costs. Every machine collects the whole suite, so the memory saving is given up. Module-scoped fixtures are set up on each machine that runs one of their tests.
- **Fix**:
  - Every machine collects the whole suite, then keeps its share.
  - Tests marked `heavy_replay(reason=...)` are dealt round-robin in node-id order before anything else, so the machines' counts differ by at most one from the first run. Marked: the inner-game file's tile pairs and key-repeat cases (19 and 19), and tests/replay/tools/test_an_unseen_game.py's tool cases (176; 633 s for the file).
  - Every other test, named as its xunit1 JUnit report names it (`classname.name`), goes sorted to `circleci tests split --split-by=timings --timings-type=testname`. Sorted because each machine rolls its own order, and every machine must give the splitter the same list.
  - Two tests with one JUnit name, or a name the splitter wasn't given, stop the run.
- **Tests**: tests/test_circleci_test_split.py:
  - every collected test runs on exactly one machine (1 to 4 machines, each collecting in its own order);
  - the machines' heavy-test counts differ by at most one;
  - heavy tests never reach the splitter;
  - names match pytest's own xunit1 report;
  - names holding slashes, backslashes and brackets map back to their tests;
  - one file's cases split across machines.
  Each was run against the file-level splitter first and failed.
- **Measured locally** (macOS, 2026-11-23): collecting the whole suite peaks at 424 MiB, against 246 MiB for a third of its 606 test files, so about 180 MiB more per machine. The Linux machines peaked at 1105 and 1139 MiB of their 1400 MiB limit (job 3948), and the kernel slab swings about 120 MiB from run to run, so the margin shrinks to about 100 MiB. The suite has 20 module-scoped and 3 session-scoped fixtures; each module-scoped one is now set up on up to three machines.
- **What CI must confirm**:
  - Each Linux machine's memory-guard peak, against the 1400 MiB limit.
  - Whether CircleCI's `testname` timings match these names. Its docs don't say which JUnit attributes it matches. If none match, the splitter weighs the tests by name and says so in `test-results/test-split-messages-<pid>.txt`.
  - The machines' times compared with each other.
- **Reporter**: the owner, from CircleCI job 5051 (#285)
- **Date Reported**: 2026-11-23
- **Files**: `tests/circleci_test_split.py`, `tests/test_circleci_test_split.py`, `tests/test_every_recording_replays_inside_an_inner_game.py`, `tests/replay/tools/test_an_unseen_game.py`, `noxfile.py`, `docs/architecture/playback/testing.md`, `CLAUDE.md`
