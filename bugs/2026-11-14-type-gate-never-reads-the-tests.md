# The Type Gate Never Reads the Tests

- **Description**: The `static-analysis` hook runs basedpyright and ty, but `[tool.ty.src]` in `pyproject.toml` leaves out `tests/`, so `uv run ty check` with no paths passes while ty, run on every tracked test file, reports 1126 diagnostics (2026-11-14: 784 `invalid-argument-type`, 241 `unresolved-attribute`, 63 `invalid-assignment`, 13 `unsupported-operator`, 5 `invalid-return-type`, 4 `unused-ignore-comment` and the rest scattered; `tests/audio/test_voices.py` has the most). Found when `tests/audio/test_instrument_catalog.py`'s 7 errors turned up only on a direct `ty check` of that file
- **Status**: Open (the owner's decision: adding `tests/` to the gate is a type-checker config change, and the existing diagnostics must be fixed first)
- **Priority**: Medium (a test's wrong type reaches main unseen; a test can pass by accident on a value it misreads)
- **Test gap**: nothing checks that the type gate covers every tracked Python file
- **Done so far**: `tests/audio/test_instrument_catalog.py`'s 7 errors were fixed on `chore/instrument-audit-checks` (0ae8c8f4): ty now reports none in that file
- **Reporter**: Claude
- **Date Reported**: 2026-11-14
- **Files**: `pyproject.toml` (`[tool.ty.src]`), `tests/`; plans/future-features.md #89
