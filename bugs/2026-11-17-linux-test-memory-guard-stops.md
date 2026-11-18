# The Linux CI Job's Test Run Stopped at the Memory Limit

- **Description**: CircleCI's Linux job (resource class `small`, 2 GB, the suite run serially) stops a run past `GLITCHYGAMES_TEST_RSS_LIMIT_MB=1600` (`tests/memory_guard.py`, which counts the container's memory less page cache, kernel slab included). In November 2026, main peaked at 1460 MiB, so any branch adding a little stopped: #216 at 1603 MiB (job 3632, in the Mr. Muncher golden) and the zombies branch at 1607 MiB (job 3629, in the inner-game pairs test).
- **Status**: Fixed (2026-11-17, #218, `8f93f8d0`): main's Linux job peaks at 1341-1350 MiB (jobs 3654, 3658). The structural options below are open, and are the owner's call.
- **Priority**: High while it stopped every branch near the limit; now headroom of about 250 MiB
- **Root Cause**: memory one process kept across the whole run, from four places:
  1. `Wave.band_limited_peak` built about 11 band tables (16 KiB each) to measure a peak and kept them. The instrument catalog keeps all 431 instruments: 85 MiB of Python.
  2. glibc keeps freed heap: about 135 MiB of the catalog file's Linux growth was freed memory. `malloc_trim(0)` returns it (171 MiB after the catalog file). Trimming after each file alone was not enough, because the inner-game file grows within itself.
  3. `tests/events/test_events_core.py`'s `mocker.spy` recorded all 65,535 calls of `pygame.event.event_name`: +69 MiB peak, freed, but kept by glibc.
  4. `scanned_file` (`tests/test_read_only_views.py`, `@functools.cache`) kept every engine file's syntax tree, about 100 MiB, for the rest of the run.
  Collection itself holds 312 MiB of Python on macOS (28,000 items, fixture definitions, rewritten modules): no leak.
- **Test gap**: no test measured what one test file leaves behind, so retained growth was found only when CI stopped
- **Solution** (#218): `waves.py` keeps only the band tables it plays (`_kept_harmonics`, `_band_table`); the events test counts calls with a wrapper; module-scoped fixtures clear `scanned_file`'s cache when its file ends; `tests/memory_by_file.py`, an opt-in plugin, writes what each test file kept and its peak (docs/architecture/playback/testing.md, "Memory by test file")
- **Tests**: `tests/audio/test_waves.py` (a wave keeps no band table it doesn't play: 297 KiB per wave before), the events test (a planted uncached scan still fails it, 196,605 calls), `tests/test_memory_by_file.py`
- **Reporter**: Claude
- **Date Reported**: 2026-11-17
- **Files**: `src/glitchygames/audio/waves.py`, `tests/events/test_events_core.py`, `tests/test_read_only_views.py`, `tests/test_engine_context_source_guards.py`, `tests/memory_by_file.py`, `scripts/memory_triage.py`

## How it was measured

- The memory guard's figure in the real job: `nox -s test-linux-ci` runs CircleCI's Linux job in Docker.
- Resident memory per test file: `GLITCHYGAMES_MEMORY_BY_FILE=rows.json pytest -p tests.memory_by_file -n 0`. On macOS, figures are for ranking only: macOS keeps freed memory, so benchmarks look huge there (17 MiB on Linux).
- Python memory, by allocating line and by owner: `uv run python -m scripts.memory_triage` (`collection`, `held`, `traced`, `per-test`).
- The trim experiment, not committed, added this at the end of `FileMemoryRecorder.finish_file`, before the row is appended, with `GLITCHYGAMES_MEMORY_BY_FILE_TRIM=1`:

  ```python
  if os.environ.get('GLITCHYGAMES_MEMORY_BY_FILE_TRIM') and sys.platform == 'linux':
      ctypes.CDLL('libc.so.6').malloc_trim(0)
      row['after_trim'] = round(self.read_resident(), 1)
  ```

- Clearing caches one at a time after the catalog file found cause 1: clearing `registry._built` freed most of it, and the live `Wave`s' band tables were the bulk. Those two probes reach private names, so they are kept here ("Cache probes", below) rather than in `scripts/`.

## Measurements (`2026-11-17-linux-test-memory-guard-stops/`)

| File | What |
|---|---|
| `serial-macos-main.json` | whole suite serially on macOS (main plus the sprite schema): ranking only |
| `linux-zombies-3.14.json` | `nox -s test-linux-ci`, zombies `19fc5381`: stopped at 41%, 1603 MiB, slab 296; pytest held 503 MiB before its first test; the catalog file kept 234 MiB |
| `linux-run-2-3.14.json` | plus cause 1's fix: stopped in the inner-game pairs test (as CI did), 1612 MiB, slab 43 |
| `linux-run-3-trim-3.14.json` | plus `malloc_trim(0)` after each file: stopped in the same test, 1621 MiB, slab 263; its first case alone +138 MiB |
| `linux-run-4-3.14.json`, `linux-run-4-3.15.json` | causes 1, 3 and 4 fixed, plus the trim: 3.14 stopped in the inner-game test at 1601 MiB (slab 258), 3.15 in `test_driver_comparison` `TestEndToEnd` at 1614 MiB (slab 457) |
| `inner-game-per-test-macos.txt` | the inner-game test, Python memory after each case (`memory_triage per-test`) |

CircleCI's real peaks before the fix:

| Run | Peak | Slab |
|---|---|---|
| main `80a57547` (job 3622) | 1460, passed | 258 |
| #217 `583bcae9` (3635) | 1516, passed | 268 |
| #216 `fa768397` (3632) | 1603, stopped (Mr. Muncher golden) | 354 |
| zombies `19fc5381` (3629) | 1607, stopped (inner-game pairs) | 228 |

## What remains (run 4: pytest grows from 503 to 859 MiB over 274 files)

- Spread thin: source guards 59 MiB (glibc keeps freed syntax-tree space), audio integration 32, committed recordings 31, the catalog 30, benchmarks 17; 393 MiB of growth over many files.
- The inner-game test keeps little per case (+1 to +8 MiB of Python); its cost is each case's peak, 140 to 160 MiB above the start in Python and more on Linux, where SDL surfaces are not traced. A stop is pytest's built-up size plus one heavy case's peak, and a child process per case would carry the same peak.
- The slab carries over: the 3.15 session runs in the same container after 3.14's and starts with about 460 MiB of slab (3.14: about 260), every run.

## Options (the owner's; not started)

1. Run the Linux job's suite as two pytest processes (engine tests, then members), with coverage combined: each starts at about 500 MiB with half the growth. Robust; a noxfile and CI change.
2. `malloc_trim(0)` after each test file on Linux (a harness hook): about 100 MiB back, cheap.
3. Run the parse-heavy scans (source guards, read-only views) in a child process.
4. The slab: 3.15 inherits about 200 MiB of 3.14's in the same container. Counting slab was the owner's 2026-10-28 choice.

## Cache probes (run with `uv run python <probe>.py tests/audio/test_instrument_catalog.py`)

`what_frees.py` read resident memory through the first, macOS-only version of the plugin (`_resident_mib`, `task_info`); the committed plugin's `resident_reader()` replaces it.

`what_frees.py`:

```python
"""Run one test file in this process, then clear candidate caches one at a time, reporting what each frees."""
import gc, sys
import pytest
import memory_by_file as measure

target = sys.argv[1]
start = measure._resident_mib()
pytest.main([target, '-q', '-n', '0', '-p', 'no:randomly', '--no-cov', '-p', 'no:cacheprovider', '--dummy-only'])
gc.collect()
after = measure._resident_mib()
print(f'\nstart {start:.0f} MiB, after the file {after:.0f} MiB (kept {after - start:.0f})')

def clear(label, action):
    before = measure._resident_mib()
    action(); gc.collect()
    print(f'{label}: freed {before - measure._resident_mib():.0f} MiB')

from glitchygames.audio import render, library, assets
from glitchygames.audio.instruments import registry
clear('instruments registry._built', registry._built.cache_clear)
clear('render caches', lambda: (render._lfsr_sequence.cache_clear(), render._anti_alias_kernel.cache_clear()))
clear('ENGINE_SOUND_CACHE', lambda: library.ENGINE_SOUND_CACHE.clear() if hasattr(library.ENGINE_SOUND_CACHE, 'clear') else None)
clear('assets caches', lambda: (assets._CACHE.clear(), assets._DEFINITIONS_CACHE.clear()))
import ctypes
libc = ctypes.CDLL('/usr/lib/libSystem.dylib')
before = measure._resident_mib(); libc.malloc_zone_pressure_relief(None, 0)
print(f'malloc pressure relief (allocator returns free pages): freed {before - measure._resident_mib():.0f} MiB')
print(f'left above start: {measure._resident_mib() - start:.0f} MiB')
```

`what_frees_traced.py`:

```python
"""Run the catalog file under tracemalloc, then clear the registry cache and see how much Python memory is freed."""
import gc, sys, tracemalloc
import pytest
tracemalloc.start()
pytest.main([sys.argv[1], '-q', '-n', '0', '-p', 'no:randomly', '--no-cov', '-p', 'no:cacheprovider', '--dummy-only'])
gc.collect()
held = tracemalloc.get_traced_memory()[0]
from glitchygames.audio.instruments import registry
from glitchygames.audio import waves
registry._built.cache_clear(); gc.collect()
after_registry = tracemalloc.get_traced_memory()[0]
alive = [obj for obj in gc.get_objects() if isinstance(obj, waves.Wave)]
band_bytes = sum(table.nbytes for wave in alive for table in wave._bands.values())
print(f'traced after the file {held/1048576:.0f} MiB; clearing registry._built freed {(held-after_registry)/1048576:.0f} MiB')
print(f'Waves still alive: {len(alive)}, their band tables {band_bytes/1048576:.1f} MiB, tables per wave max {max(len(w._bands) for w in alive)}')
print('WAVE_TABLE_LENGTH', waves.WAVE_TABLE_LENGTH)
```
