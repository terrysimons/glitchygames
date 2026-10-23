# Lint Ignores Cleanup — Plan

- **Date:** 2026-10-20
- **Status:** Phases 1 and 2 done 2026-10-21 on `feature/gameplay-replay` (the user's go-ahead:
  "start addressing those future lint issues here and now"). Phase 1: `EM101`/`EM102` removed (0
  violations), the `COM812` comment corrected, the 50 unused `ty: ignore` comments deleted (none
  shared with basedpyright, which reads only `# pyright:`/`# type:` comments; ty now reports
  nothing). Phase 2: `S311` moved to per-file ignores for `glitchygames/randomness.py` and
  `tests/**`; the 34 measured sites were all in those two places, so no engine code changed.
  Phase 3 done 2026-10-22: the 36 sites outside Bitmappy narrowed on 2026-10-21, the last 60 in
  Bitmappy on 2026-10-22, and the `PLW0717` ignore removed (BUGS.md #19 resolved; the bugs it
  found are #175, fixed, and #176-#178). Phase 4 in progress (the user's go-ahead 2026-10-22, as
  part of the post-replay cleanup): 128 of 152 sites typed; the 24 left are listed under Phase 4.
  Phase 5 done 2026-10-22 (the user's choice: convert all): every logging f-string is lazy
  `%`-style and the `G004` ignore is removed; measurements under Phase 5.
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

Progress (2026-10-22): 128 of 152 typed; 151 of 152 after the Bitmappy and joystick demo sites
(below), the last one `events/base.py`'s `__getattr__`. New shared types: `tracing.JsonValue` (recursive JSON
alias, reused by `recording.py`), `supervision.FrozenJsonValue`/`JsonShapedValue`,
`input.devices.OpenedJoystick`/`OpenedController` (live or replay device), the collision
`RectSprite`/`WorldRectSprite` Protocols, `debug.protocols.InspectedScene`, a generic
`Tween[TargetT]`, minimal Protocols for the untyped aisuite client (`services/` and
`bitmappy/ai_worker.py`). Left, each waiting on a decision:
- ~~`examples/joystick_demo.py` (12)~~ done 2026-10-22: rewritten on one `InputDevice` per
  physical device (`plans/2026-10-22-unified-input-devices.md`); it lists every device with no
  mode and no `Any`. The package's last ANN401 site is `events/base.py`'s `__getattr__` (below).
- `events/base.py` `HashableEvent.__getattr__` (1): the event attribute bag (pygame's own is
  `Any`; `object` gave 292 caller errors). Keeps `Any` with a per-file ignore and its reason
  until typed per-family event subclasses exist (to be planned; basedpyright does not let
  `__getattr__` satisfy a Protocol, so typed views must be classes).
- Bitmappy (11), done 2026-10-22 (the user's choices: public APIs; the editor required):
  `AnimatedSprite.animation_data`/`pause()`, `FilmStripWidget.refresh(recalculate_layout=...)`,
  `EditorContext.applying_undo_redo`; the trackers require `editor`; the dead aisuite
  `_providers` timeout setup removed (timeouts go in the client config; BUGS.md #183). Before:
  4 in `history/commands.py` and 3 in `ai_worker.py` reach protected members
  (`AnimatedSprite._animations`, `FilmStripWidget._calculate_layout`, aisuite's
  `client._providers`); typed, every access is a `reportPrivateUsage` error, so they need public
  APIs (and test stand-ins that set them). 4 in `history/operations.py`: the trackers' `editor`
  defaults to `None`; either the editor becomes required or the commands accept `None`.

## Phase 5 — `G004`: decide (optional)

1,123 f-strings in logging calls. Lazy `%` formatting avoids building messages for disabled log
levels, but the gain is small and the churn large. Measure the cost on a hot path (e.g. per-frame
debug logging) first; convert only hot paths, or the whole codebase if the user wants consistency.

Measured 2026-10-22 (1,099 sites): a disabled `log.debug(f'...')` costs 106-713 ns against 61-88 ns
lazy (two plain values ~200 vs 63 ns; PaddleSlap's six-float ball message 713 vs 88 ns; Bitmappy's
mouse-drag message, which formats two events and the sprite, 1.8 us vs 75 ns). Disabled calls made
inside frames (counted by wrapping `logging.Logger`'s methods over each golden replay, and over 600
Bitmappy frames of mouse motion and drags): Bitmappy 27.2 per frame (~26 us saved per frame, 0.16%
of a 60 FPS frame; 20 us of it the drag message), PaddleSlap 9.3 (~5.5 us), Brave Adventurer
Papyrus 9.3 (~0.5 us), Brave Adventurer and Clockwork Keep ~0. Enabled calls (0.2-0.3 per frame)
save nothing. Lazy formatting still evaluates the arguments; only removing a per-frame debug line
or guarding it with `isEnabledFor` saves that. Decision (the user, 2026-10-22): convert all of
them, then remove the ignore.

Done 2026-10-22: 1,096 sites converted by a script (each string piece converted on its own, so
implicit concatenation keeps its line breaks; `%`-specs where `%` formats identically, otherwise
`format(value, spec)` as the argument: 11 sites, the `,` thousands separator), one by hand (a
computed width, `%*s`). Typing the arguments exposed 22 basedpyright errors that f-strings had
hidden (untyped values, suppressions left on the wrong line); fixed at the source, which also
removed 7 `# type: ignore` comments. Tests that read a mocked logger's raw format string now
format it as logging does (`tests/logged_messages.py`) or read `caplog` records.

## Order and dependencies

Phase 1 → Phase 2 → Phase 3 (independent of 4/5) → Phase 4 → Phase 5. Phases 1–2 are small and can
run right after the current replay tooling work; phase 3 is the most valuable for catching bugs.
Phase 4 overlaps the dataclass → pydantic audit (`plans/future-work.md`, Code quality) — do them in
the same area-by-area passes where they touch the same files.
