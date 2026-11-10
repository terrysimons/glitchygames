# Bundled demos: a frozen pydantic record, and no silent skip — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `glitchygames.bundled_demos.BundledDemo` becomes a frozen pydantic model, and
`bundled_demos()` refuses a package it cannot find instead of silently skipping it.

**Architecture:** One engine leaf module changes (`src/glitchygames/bundled_demos.py`); its
callers pass explicit package lists and need no change. Tests change first.

**Tech Stack:** Python 3.14, pydantic v2, pytest.

**Origin (no separate spec):** the last open item of the Part 2 workspace plan
(`plans/2026-10-25-workspace-packages-2-games-demos-apps.md`, never committed, superseded by
#109–#111, which did everything else in it). The owner (2026-10-30, relayed by the
glitchygames-cb session and confirmed in the glitchy-games-website session): "BundledDemo becomes a
frozen pydantic model, `ConfigDict(frozen=True, extra='forbid')`; `bundled_demos()` stops silently
skipping a package `find_spec` cannot find: fail loudly or log, your call, with a test".

**The call (made while writing this plan):** **fail loudly.** Every caller names its packages
explicitly (a game's own `identity.package`; this repository's `MEMBER_PACKAGES`), so a package
`find_spec` cannot find is a typo or a broken install, and skipping it hides a demo that is then
never replayed or measured, which is the failure this item exists to stop. A **plain module**
(found, but no directory) and a package **without a `demos/` directory** still have no demos and
raise nothing: those are normal.

## Global Constraints

- The project's model idiom: `model_config = ConfigDict(frozen=True, extra='forbid')`
  (as in `src/glitchygames/code_tree.py`, `build_info.py`, `input/device_listing.py`).
- `glitchygames.bundled_demos` stays a leaf for tools: it imports neither pygame nor a game
  (pydantic is an engine dependency already).
- Keyword-only arguments, explicit long names, Google docstrings, 100 columns, ruff and
  basedpyright clean, 100% coverage (`pytest`; `--dummy-only` for iteration).
- No behaviour change for any committed recording: every golden replay and bundled demo still
  replays; `nox -s replay-metrics` / the pre-commit measurement still finds PaddleSlap's demo.
- Commit only on the owner's go-ahead; finished work goes up as a PR (the owner: "Open a PR
  always").

## Review Focus

1. **A game run as a script** (`python paddleslap.py`): its identity's `package` may be
   `__main__` or None, and `importlib.util.find_spec('__main__')` raises `ValueError` when
   `__main__.__spec__` is None. Before Task 2 lands, check what the callers pass in that case (`src/glitchygames/replay/tools/recordings.py` ~116, `replay/tools/measure.py` ~274
   with `demo_packages`); if they can pass such a package, the refusal must not turn a script run's
   `--verify` / `--measure` into a crash. Add a test for whatever the answer is.
2. **A package whose import raises** (`find_spec` of a dotted name imports its parent). Members are
   top-level packages, so this should not arise; if a caller can pass a dotted name, its
   `ModuleNotFoundError` must surface as the same refusal, not a traceback from inside discovery.
3. **The message names the package and the remedy** (`uv sync --all-packages`, or a typo in the
   list), so the pre-commit hook's output tells the owner what to do.

---

## File Structure

- Modify: `src/glitchygames/bundled_demos.py` (the model, the refusal, the module docstring)
- Modify: `tests/test_bundled_demo_discovery.py` (the frozen test; the not-installed test split
  into "no demos" and "refused")
- Modify: `CLAUDE.md` (the "Bundled demos" bullet: `BundledDemo` is a frozen pydantic model;
  `bundled_demos` refuses an unfindable package)

---

### Task 1: `BundledDemo` is a frozen pydantic model

**Files:**
- Modify: `src/glitchygames/bundled_demos.py:35-52`
- Test: `tests/test_bundled_demo_discovery.py:62-72`

**Interfaces:**
- Produces: `class BundledDemo(pydantic.BaseModel)` with
  `model_config = ConfigDict(frozen=True, extra='forbid')` and the same four fields
  (`package: str`, `console_script: str | None`, `path: Path`, `install_name: str`), constructed
  with keywords exactly as today (`bundled_demos` and the tests already do).

- [ ] **Step 1: Change the frozen test and add the extra-field test**

```python
def test_a_bundled_demo_is_a_frozen_record(tmp_path):
    """A demo's fields cannot be changed in place."""
    demo = BundledDemo(
        package='stand_in_game',
        console_script='stand-in-game',
        path=tmp_path / 'stand_in_game' / BUNDLED_DEMO_DIRECTORY_NAME / 'rally.jsonl.gz',
        install_name='stand_in_game/demos/rally.jsonl.gz',
    )

    with pytest.raises(pydantic.ValidationError, match='frozen'):
        demo.console_script = 'other'  # type: ignore[misc]


def test_a_bundled_demo_refuses_an_unknown_field(tmp_path):
    """A misspelt field is an error, not a silently ignored keyword."""
    with pytest.raises(pydantic.ValidationError, match='install_path'):
        BundledDemo(
            package='stand_in_game',
            console_script=None,
            path=tmp_path / 'rally.jsonl.gz',
            install_name='stand_in_game/demos/rally.jsonl.gz',
            install_path='stand_in_game/demos/rally.jsonl.gz',  # type: ignore[call-arg]
        )
```

  (Drop `import dataclasses` from the test file if nothing else uses it; import `pydantic`.)

- [ ] **Step 2: Run** `uv run pytest tests/test_bundled_demo_discovery.py --dummy-only --no-cov -q`.
  Expected: the two tests FAIL (a dataclass raises `FrozenInstanceError`, and accepts no unknown
  keyword with `TypeError`, not `ValidationError`).
- [ ] **Step 3: Implement** the model in `bundled_demos.py` (replace `import dataclasses` with
  `from pydantic import BaseModel, ConfigDict`; keep the class docstring's Attributes).
- [ ] **Step 4: Run** the same command, then every user:
  `uv run pytest tests/test_bundled_demo_discovery.py tests/replay/test_bundled_demos.py tests/replay/test_recording_logical_names.py tests/replay/test_replay_plugin.py tests/replay/tools/test_measure.py tests/test_our_measured_recordings.py src/games/paddleslap/tests --dummy-only --no-cov -q`.
  Expected: PASS.
- [ ] **Step 5: Checkpoint** (the owner commits).

---

### Task 2: `bundled_demos()` refuses a package it cannot find

**Files:**
- Modify: `src/glitchygames/bundled_demos.py:94-129` (and the module docstring's "A package that
  is not installed has no demos to find")
- Test: `tests/test_bundled_demo_discovery.py:117-132`

**Interfaces:**
- Produces: `class PackageNotFoundError(LookupError)` in `glitchygames.bundled_demos` (a
  `LookupError`, like `replay/tools/children.py`'s `UnknownGameError`), raised by
  `bundled_demos(*, packages)` for the first package `importlib.util.find_spec` returns None for
  (or raises `ModuleNotFoundError` / `ValueError` for: Review Focus 1 and 2). Message:
  `f'{package!r}: no installed package by that name, so its bundled demos cannot be found (a typo in the list, or not installed: uv sync --all-packages)'`.
  Signature and return type unchanged.

- [ ] **Step 1: Split the existing test in two**

```python
def test_packages_without_demos_have_none(tmp_path, monkeypatch):
    """No demos directory, an empty one, or a plain module: no demos, and nothing raised."""
    write_stand_in_package(directory=tmp_path, package='stand_in_game_with_no_demos', demo_names=())
    (tmp_path / 'stand_in_module.py').write_text('', encoding='utf-8')
    monkeypatch.syspath_prepend(tmp_path)

    demos = bundled_demos(
        packages=('glitchygames', 'stand_in_game_with_no_demos', 'stand_in_module')
    )

    assert demos == []


def test_a_package_that_cannot_be_found_is_refused_by_name(tmp_path, monkeypatch):
    """A package not installed (or misspelt) is an error: a skip would hide its demos.

    Every caller names its packages, so one that cannot be found is a mistake; silently skipping
    it left that package's demos unreplayed and unmeasured.
    """
    write_stand_in_package(
        directory=tmp_path, package='stand_in_game', demo_names=('rally.jsonl.gz',)
    )
    monkeypatch.syspath_prepend(tmp_path)

    with pytest.raises(PackageNotFoundError, match="'no_such_installed_package'.*uv sync"):
        bundled_demos(packages=('stand_in_game', 'no_such_installed_package'))
```

  Plus one test per answer to Review Focus 1 and 2 (for example,
  `test_a_script_run_game_has_no_bundled_demos` if a `__main__` package is to return `[]`, or
  `..._is_refused` if it should raise), written once the callers are checked.

- [ ] **Step 2: Run** `uv run pytest tests/test_bundled_demo_discovery.py --dummy-only --no-cov -q`.
  Expected: `test_a_package_that_cannot_be_found_is_refused_by_name` FAILS (nothing raised) and
  fails to import `PackageNotFoundError`; the "no demos" test PASSES (today's behaviour, kept).
- [ ] **Step 3: Implement** the error and the refusal in place of `continue`; update the module
  docstring and `bundled_demos`' docstring (`Raises:`).
- [ ] **Step 4: Run** the Task 1 Step 4 command, then the whole suite: `uv run pytest`
  (driver comparison included, 100% coverage). Expected: PASS. Then
  `uv run python -m scripts.measure_staged_replays` on a staged change to confirm the pre-commit
  hook still finds PaddleSlap's demo (`rally.jsonl.gz` measured).
- [ ] **Step 5: Docs.** `CLAUDE.md`'s "Bundled demos" bullet: `BundledDemo` is a frozen pydantic
  model; `bundled_demos` raises `PackageNotFoundError` for a package it cannot find (a plain
  module or a package without `demos/` has none). Remove item 7 from the workspace follow-ups
  wherever it is tracked.
- [ ] **Step 6: Checkpoint** (the owner commits; open a PR).
