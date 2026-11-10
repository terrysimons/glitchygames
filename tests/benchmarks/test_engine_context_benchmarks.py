"""What engine contexts cost per read: the limits the documented and measured reads stay within.

plans/2026-10-27-engine-context-2-engine-state.md: Task 16 made this module with
``READ_RATIO_LIMITS`` only; Task 17 adds the per-read benchmarks its gate (c) measures. A read is
compared with a slot read (``current_context().value(slot=...)``) on the same machine, so the
limits are ratios, not nanoseconds: a class-level read-only view (``GameEngine.OPTIONS``) and
``current_engine()`` each cost at most this many slot reads. The engine context page's
"Performance" table (docs/architecture/engine_context.md) is checked against them by
tests/test_read_only_views.py, so the documented costs never drift past the gate.
"""

from __future__ import annotations

# Each read's limit, as a multiple of a slot read, by its row label in the engine context page's
# "Performance" table (about twice the ratios Task 1 measured: a view about 2.1 slot reads)
READ_RATIO_LIMITS: dict[str, float] = {'read-only view': 4.0, 'current_engine()': 2.0}
