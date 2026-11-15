# Bitmappy's Collision Avoidance Logs Every Offset Again on Every Indicator Added

- **Description**: `VisualCollisionManager._apply_collision_avoidance` logs one DEBUG line per controller in a collision group (`Applied film_strip offset (15, -15) to controller 42`, `collision.py:398`), and it runs again for the whole group every time an indicator is added. `test_bulk_assignment_and_indicators` (`src/apps/bitmappy/tests/test_bitmappy_benchmarks.py`, 1000 controllers) logs about 2.5 million lines. Under pyproject's `addopts` (`--log-cli-level=DEBUG`) and `pytest -n0`, that one test peaked at 3.26 GB and took 46 s on the Mac (229 MB and 2.8 s at `--log-cli-level=WARNING`), and on a Raspberry Pi 4 it passed the 1,600 MiB `GLITCHYGAMES_TEST_RSS_LIMIT_MB` by itself (+1,425 MiB in a fresh process)
- **Status**: Open
- **Priority**: Low (only DEBUG runs with many controllers; nox's sessions run at WARNING)
- **Reporter**: Claude, running the suite on the Raspberry Pi 4 (2026-11-06)
- **Date Reported**: 2026-11-14
- **Details**: The logging grows with the square of the indicators at one position. Logging once per group change, or only the controllers whose offset changed, would keep the record without the volume
- **Files**: `src/apps/bitmappy/src/bitmappy/indicators/collision.py`
