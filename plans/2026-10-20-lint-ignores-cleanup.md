# Lint Ignores Cleanup — Plan

- **Date:** 2026-10-20
- **Status:** Plan (user asked for it; each phase needs the user's go-ahead before it changes lint or
  type-checker configuration — standing rule).
- **Why:** several global ignores in `pyproject.toml` are dead, mislabelled or broader than needed,
  and some suppression comments no longer suppress anything. Tightening them makes the linters catch
  real problems again (broad try blocks hide bugs; a stray `random` call would break replay
  determinism).

## Inventory (measured 2026-10-20, ruff 0.17.1, package + tests + scripts)

| Rule | Violations if enabled | Decision |
|---|---|---|
| `EM101`, `EM102` | 0 | remove the ignores (dead) |
| `PLW0717` too many statements in try | 100 | fix, then remove the ignore (BUGS.md #19) |
| `S311` non-cryptographic random | 31 | narrow to `glitchygames/randomness.py` and tests |
| `ANN401` `Any` annotations | 159 | gradual typing work (phase 4) |
| `G004` f-string in logging | 1,123 | decide in phase 5 (optional) |
| `COM812` trailing comma | 786 | keep (conflicts with `ruff format`); fix its wrong comment |
| `ISC001`, `ISC002`, `D203`, `D213` | — | keep (formatter / mutual conflicts) |
| `CPY001` | — | keep unless the user wants copyright headers |
| `S101` assert | 13,240 | keep (pytest asserts) |
| `PLC0415` import outside top level | 517 | keep (deliberate: door modules defer imports to avoid cycles; optional/platform imports) |
| `SLF001` private access | 3,137 | keep for now (mostly tests) |
| `PLR6301` method could be function | 7,187 | keep (pytest class style) |
| `pytest-fixture-autouse` | 467 | keep (doors / signal-handler resets rely on autouse) |
| ty `unused-ignore-comment` warnings | 50 | delete the unused `ty: ignore` comments |
| per-file `PLR0913`/`PLR0917` ignores | — | revisit with the dataclass → pydantic audit (options objects) |
| basedpyright tests-folder overrides (~20 checks off) | — | keep (mock-heavy tests); the package stays strict |

## Phase 1 — Free cleanups (one small task)

1. Remove `EM101` and `EM102` from `[tool.ruff.lint] ignore` (0 violations; confirm with
   `uv run ruff check glitchygames tests scripts noxfile.py` after removal).
2. Fix the `COM812` comment (it says "Commented-out code"; it is the trailing-comma rule, ignored
   because it conflicts with `ruff format`).
3. Delete the 50 unused `ty: ignore` comments ty reports (`uv run nox -s static-analysis-ty`): for
   each, confirm basedpyright doesn't need the same line suppressed (the two checkers share some
   comments — `unused-type-ignore-comment` is disabled in ty for that reason); remove only the ones
   neither checker needs. Expected end state: ty shows 0 warnings (update CLAUDE.md / future-work
   wherever "the 50 known warnings" is written, and the global constraints for later tasks).
4. Verify: ruff, ruff format, basedpyright (0), ty (0 warnings), vulture, mkdocs strict, full suite.

## Phase 2 — Narrow `S311` (one small task)

1. Move `S311` from the global ignore list to `per-file-ignores` for `glitchygames/randomness.py`
   (the seeded streams are deliberately non-cryptographic) and `tests/**`.
2. Fix or justify each of the 31 current sites outside those files: gameplay randomness must already
   go through `random_stream()` / `numpy_stream()` (the randomness guard test enforces that); any
   remaining site is either a stream lookup that ruff can't see through (justify by moving the call
   into randomness.py) or a real bypass (fix it).
3. Verify as in phase 1, plus golden traces and golden replay fixtures unchanged.

## Phase 3 — `PLW0717`: narrow the 100 broad try blocks (one task, maybe split by area)

1. List the sites: `uv run ruff check glitchygames tests scripts --config 'lint.ignore=[]' --select
   PLW0717 --output-format concise`.
2. For each try block, keep only the statements that can raise the caught exceptions inside `try`;
   move the rest to `else:` or after the block. Read each block's comments first; where catching
   broadly is deliberate (a top-level crash boundary like `GameEngine.start()`, a plugin boundary),
   keep it and make the reason explicit — prefer restructuring (a helper function) over a
   suppression, and ask the user before adding any suppression.
3. Split into reviewable commits by area (engine/scenes, bitmappy, audio, ui, api, scripts, tests).
   Add a test wherever narrowing changes which exceptions propagate.
4. Remove `PLW0717` from the ignore list; mark BUGS.md #19 Resolved.
5. Verify: full suite, lint/type, golden traces and golden replays unchanged.

## Phase 4 — `ANN401`: replace `Any` with real types (gradual)

1. List the 159 sites; group by cause: dynamic dispatch (event handlers), loosely-typed game objects,
   AI client APIs, JSON values.
2. Replace with Protocols (house preference over mixins), TypedDicts / pydantic models for JSON
   shapes, generics, or `object` where only identity is used. Leave genuinely dynamic boundaries
   (e.g. third-party AI client payloads) on `Any` with a per-file ignore and a reason.
3. Do it area by area; remove the global ignore when the remaining sites are covered by per-file
   ignores with reasons.

## Phase 5 — `G004`: decide (optional)

1,123 f-strings in logging calls. Lazy `%` formatting avoids building messages for disabled log
levels, but the gain is small and the churn large. Measure the cost on a hot path (e.g. per-frame
debug logging) first; convert only hot paths, or the whole codebase if the user wants consistency.

## Order and dependencies

Phase 1 → Phase 2 → Phase 3 (independent of 4/5) → Phase 4 → Phase 5. Phases 1–2 are small and can
run right after the current replay tooling work; phase 3 is the most valuable for catching bugs.
Phase 4 overlaps the dataclass → pydantic audit (`plans/future-work.md`, Code quality) — do them in
the same area-by-area passes where they touch the same files.
