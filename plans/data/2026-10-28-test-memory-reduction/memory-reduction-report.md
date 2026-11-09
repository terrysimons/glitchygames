# Serial Linux test run: memory reduction

Branch `feature/test-memory-reduction` (from 29adc6ee, limit 1600 MiB). Six commits, not pushed.

| Commit | What |
|---|---|
| 906ed3db | Replay: a recording read for a replay shares unchanged sprite records (`share_records`) |
| be5e6651 | Tests: the root-tests import scans parse one file at a time |
| 3d3d0fc8 | Tests: the golden-replay checks read with shared records |
| 2687f88e | Tests: collect garbage when malloc's bytes in use grew 32 MiB, not only the peak |
| 4a32a850 | Tests: empty each finished test's class instance, which pytest keeps all run |
| ea449023 | BUGS.md #237 |

## Container peak (the guard's figure: cgroup memory less page cache)

| Run | Peak |
|---|---|
| Before (instrumented, limit 2000) | 1781 MiB |
| After (same instrumentation) | 1444 MiB |
| After, plain `nox -s test-linux-ci`, limit 1600 | 1409 MiB, passed |

The instrumented runs include a 1 s sampler process, about 20 MiB, in both figures. All Docker
runs are amd64 emulated on Apple silicon, as `test-linux-ci` is.

## Contributors, before and after

| Contributor | Before | After |
|---|---|---|
| pytest process, its own peak RSS | 1317 MiB (end of run, climbing in Bitmappy) | 895 MiB |
| Bitmappy editor scenes kept by pytest's test instances | 79 alive, 230 MiB of surfaces (macOS) | 3 MiB of surfaces |
| Uncollected scenes (Brave Adventurer both-editions file, macOS) | 483 MiB at its end | 353 MiB |
| Mr. Muncher replay child (macOS max RSS) | 342 MB | 191 MB |
| Mr. Muncher-style replay child in the container | 322 MiB | 175-183 MiB |
| `test_golden_replays.py` peak (macOS, alone) | 310 MiB | 177 MiB |
| Import scans (`test_suite_collection.py`, macOS, alone) | 335 MiB peak | 144 MiB |

Where the peak sits now: `tests/test_driver_comparison.py::TestEndToEnd` (pytest 685 MiB plus
an inner pytest and two workers, about 100 MiB each), then the golden replays near the end
(pytest about 850 MiB plus a 150-185 MiB child).

## Not from the tests, still counted by the guard

- Reclaimable kernel slab: about 290 MiB (`slab_reclaimable`), flat from before the first
  test. It is dentries and inodes from the checkout and the installs. The kernel reclaims it
  before it kills, but the guard counts it. Not changed: subtracting it would loosen the
  guard. That is the owner's decision.
- The `uvx` parent that waits for nox: about 47 MiB anonymous (70-95 MiB RSS). Installing nox
  with `uv tool install` and running `nox` directly would remove it. That is a CI change to
  every POSIX job. Not done.
- The `nox` parent: about 47 MiB RSS.
- pytest's own bookkeeping: about 2 KB of reports and 1 KB of JUnit data per test, about
  65 MiB over 22k tests. pytest-benchmark's samples in a serial run: about 20 MiB.

## Method

- A sampler in the container: every 0.5 s, `memory.stat` and each process's RSS, tagged with
  the running test.
- A plugin recording RSS, malloc in use (`mallinfo2`) and pymalloc blocks after each test.
- On macOS: tracemalloc, `gc.DEBUG_SAVEALL` garbage census, surface-owner census and referrer
  chains.
- An audit before the record-sharing change: the whole suite, with every decoded sprite record
  frozen. Only test tamper helpers changed records, and they read with copies.

## Is 1600 MiB safe?

Yes, with about 190 MiB of headroom. The plain run peaked at 1409 MiB against 1600. That run
was emulated, so CircleCI's real figure may differ. The guard prints `memory guard: peak N MiB`
at the end of every run, so the first CircleCI runs will confirm it. Going lower than 1600
would mostly mean dealing with the slab or the uvx parent, not the tests.

## Checks

- `nox -s lint`: passed. `nox -s static-analysis`: passed.
- `CI=true nox -s test`: 22226 passed, 6 skipped, 23 xfailed, coverage 100%, no warnings.
- `nox -s test-linux-ci`: passed, guard peak 1409 MiB at limit 1600.

## Noticed, not fixed

- `test_driver_comparison.py`'s end-to-end tests start an inner pytest with two worker
  processes in the serial job: the current peak. I did not find where the inner run gets its
  workers.
- `tests/world/test_golden_traces.py` still adds about 116 MiB to the pytest process.
  `record_trace` holds the whole current run in memory. Reading the baseline with shared
  records did not change it, so that edit was dropped.
