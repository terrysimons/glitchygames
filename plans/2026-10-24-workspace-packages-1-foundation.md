# Workspace Packages, Part 1: Foundation and the Mr. Muncher Pilot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repository a uv workspace whose members can be games, with every engine guard,
tool and harness covering members; name games in recordings by logical names; move the engine's
source to `src/glitchygames/`; and prove it by moving Mr. Muncher to `src/games/mr-muncher/`.

**Status:** DONE (2026-10-25), merged as #105, b29f85fc.

> **Amended 2026-10-25 (the user's decisions 7, 8 and 9 in the master plan).** Decision 7:
> everything lives under `src/`: the engine at `src/glitchygames/`, members at
> `src/games/<game>/`, `src/demos/<demo>/`, `src/apps/<app>/`. Decision 8: recordings name games
> and scenes by logical names (`games.mr_muncher.game:MrMuncherScene`), and
> `Scene.PREVIOUS_MODULES` is removed. Decision 9: a member's golden replays live directly in
> `<member>/tests/fixtures/replays/` (Mr. Muncher's: `src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz`),
> its bundled demos in its package (`<package>/demos/`; PaddleSlap's demo is converted in place
> here and moves in Part 2), the root `tests/` keeps only the engine's own recordings, and
> `RECORDING_PATH_RENAMES` gets one line per moved recording. Tasks 1-4 are done and kept as written (Task 2 added
> `PREVIOUS_MODULES`, which Task 5 now removes; Tasks 3-4's example paths, `games/space-game`
> and `glitchygames/`, are moved to the new layout by Task 7). New tasks, in order: **5** logical
> names (reworks Task 2), **6** the one conversion of the six committed recordings, **7** the
> engine to `src/glitchygames/`; the old Tasks 5-9 follow as **8-12**. The SDD ledger's
> pre-flight rows name the old numbers: ledger Task 2 is reworked by Task 5, and ledger Task N,
> for N >= 5, is this plan's Task N + 3. The pre-flight rulings stay in force, except:
> - **A3, B12** no longer apply: there is no `PREVIOUS_MODULES` to set or annotate (Task 9 needs
>   nothing for recordings: Mr. Muncher's logical name is the same before and after its move).
>
> Those whose paths or tasks changed, as they now read in this plan:
> - **B11** (Task 9): the sed runs `git grep -l ... -- ':!plans'`; the root script line it
>   rewrites is deleted.
> - **B13** (Task 9): the member's `requires-python = ">=3.14,<4.0"`.
> - **B14** (Task 9): after the move, `rm -rf src/glitchygames/examples/mr_muncher`.
> - **B15** (Task 7, was ledger Task 6): `RECORDING_PATH_RENAMES` and the one-path
>   `performance_series` fix land with the engine's move, because that move already renames a
>   recording (PaddleSlap's bundled demo, `glitchygames/examples/paddleslap_demos/` ->
>   `src/glitchygames/examples/...`); Task 9 adds Mr. Muncher's entry.
> - **B16, B17, A8** (Task 10): unchanged in substance.
> - **A7** (Tasks 8/9): the checks, plus coverage `paths`, ty `root` and `MEMBER_LAYERS`.
> - **C2** (Task 9): untracked files under `src/` (not `games/`) refuse the commit; the new rows
>   are named `...-src-games-mr-muncher-tests-fixtures-replays-golden.json`.
> - **C3-C6** (Task 9): unchanged in substance.
> - **C7** (Task 9): `MEASURED_PATHS` holds `src` (Task 7), which covers every member.
> - **C9** (Tasks 8/9): the ruff per-file-ignores glob is `"src/games/*/tests/**/*.py"`.
> - **C10** (Tasks 8/9): the pyright environment is `src/games/mr-muncher/tests`; both test
>   environments' `extraPaths` are `[".", "src", "src/games/mr-muncher"]`, so the blocks stay
>   equal apart from `root`.
> - **C11** (Tasks 8/9): `known_first_party = ["glitchygames", "mr_muncher"]` (`glitchygames`
>   from Task 7) and `extend_exclude` gains `src/games`.
> - **C12** (Task 9): if ty reads member tests, exclude `src/games/*/tests`.
> - **C14** (Task 9): `tests/test_replay_metrics.py` expects
>   `src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz`.
> - **C17** (Task 9): still applies (frame 1's `scene_start.scene_module` changes with the move;
>   its logical `scene` does not).
> - **B19** (Task 12).
>
> Commits that change the measured paths (the `replay-metrics` hook measures, ~12 s): Tasks 5,
> 6, 7 and 9.

**Architecture:** The root project stays the engine (`glitchygames`), its source in
`src/glitchygames/` (wheel contents unchanged: `glitchygames/` at the top level), so nothing at
the repository root is importable as the engine. `[tool.uv.workspace]` lists members explicitly
(under `src/games/`, later `src/demos/` and `src/apps/`); each member has its own
`pyproject.toml`, import package and `tests/`. A small reader, `scripts/workspace_packages.py`,
is the one place that knows the members; guards, config checks, the browser build and the
replay metrics ask it. Recordings name games and scenes by logical names
(`glitchygames/logical_names.py`: `<layer>.<module inside the package>:<qualified name>`), which
a move does not change; the engine holds the layers as data (an installed engine has no
workspace to read), kept equal to the workspace by a test. The tests' shared harness becomes a
plugin the root `conftest.py` loads, so a member's tests get it.

**Tech Stack:** Python 3.14, uv workspaces (`uv sync --all-packages`), hatchling, pytest +
pytest-cov + xdist, pygame-ce 2.5.8, PyScript/Pyodide browser bundles, mkdocs + mkdocstrings.

**Spec:** [2026-10-24-workspace-packages.md](2026-10-24-workspace-packages.md) (the master plan:
layout, the user's decisions 1-8, what every part keeps true).

## Global Constraints

- Branch from the latest `main` (`5a243b96` or later: it has the browser builds, #97).
- Names: directory and distribution `mr-muncher`, import package `mr_muncher`, console script
  `mr-muncher` (unchanged).
- Layout: the engine in `src/glitchygames/`, members in `src/games/<game>/` (and later
  `src/demos/`, `src/apps/`); nothing importable as our package at the repository root.
- Workspace members are listed explicitly (`members = ["src/games/mr-muncher"]`), never by glob.
- Recordings change only by the one logical-name conversion rebaseline (Task 6), each verified
  by a strict replay. Moving a recording's file (Task 9) is not a change: its bytes stay, and
  `RECORDING_PATH_RENAMES` gets one line for it.
- Where recordings live: a member's golden replays in `<member>/tests/fixtures/replays/`
  (`golden.jsonl.gz`, no console-script folder), its bundled demos in `<package>/demos/`; the
  root `tests/fixtures/replays/` keeps the engine's own and the not-yet-moved games'.
- Coverage stays at 100% (`--cov-fail-under=100`) over the engine and every member, measured
  on the installed copies and reported under `src/` (`[tool.coverage.paths]`).
- No `# noqa`, no type-ignore additions, no lint configuration loosened to make a check pass;
  configuration only grows to include members.
- pytest-mock (`mocker`) only; keyword arguments; full names; new data classes are frozen
  pydantic models (`ConfigDict(frozen=True, extra='forbid')`).
- Lint (`ruff`, `basedpyright`, `ty`) before tests; run the failing test before the fix.
- Every commit ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`;
  never push without the user's go-ahead.

## Review Focus

1. **A member's tests silently not running**: a test directory pytest never collects (testpaths,
   a basename clash with `tests/`) passes CI by running nothing. Task 9 adds a collection check
   that each member's test files are collected.
2. **A member outside a guard**: a raw clock read or `random.random()` in `mr_muncher/` must fail
   the doors and randomness guards exactly as in `src/glitchygames/`. Task 4 tests that the
   guards' roots include the member and that a planted bypass in a member path is reported;
   Task 7 keeps the engine's allowlist keys unchanged after the move (relative to
   `src/glitchygames/`).
3. **A recording of the wrong game accepted, or of the right one refused**: a recording whose
   logical name is another game's must be refused; the same game after a move (another module,
   the same logical name) and an old-format recording of the exact module must replay. Task 5
   tests all three; Task 6's conversion must leave every committed recording replaying strictly
   with names that resolve.
4. **The installed copy, not the source**: nox installs non-editable; tests, coverage and the
   replay plugin must import and measure the installed `glitchygames` and `mr_muncher` (console
   script found, coverage mapped to `src/`), never a source tree reached through the root on
   `sys.path`. Task 7 adds the import check and runs `CI=true nox -s test`; Task 12 runs the
   real `nox -s test` and `nox -s build-wheel` again with the member.
5. **The browser bundle missing the game**: the engine archive covers only `src/glitchygames/`;
   the bundle must ship `mr_muncher` too, and the engine wheel must no longer contain it.
   Tasks 10 and 12 check both.
6. **Paths that silently stop matching after the move**: ruff per-file-ignores keys, coverage
   source, pyright/ty search paths, wily and the complexity scripts, the code tree's measured
   paths. A path that no longer exists usually fails quietly (a lint rule no longer ignored
   fails loudly; a measured path that matches nothing does not). Task 7 checks each by its
   effect (file counts, the code-tree tests, the coverage report's paths).
7. **Layers out of step**: the engine's `MEMBER_LAYERS` is data; a member added to the workspace
   but not to it would be recorded under its bare module path. Task 8's check fails on any
   difference.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/glitchygames/` | the engine (moved from `./glitchygames/`, Task 7) |
| `pyproject.toml` (root) | wheel `packages = ["src/glitchygames"]`; coverage paths; workspace members; no `mr-muncher` script; tool configs include members |
| `src/games/mr-muncher/pyproject.toml` | the member: name, dependency on `glitchygames`, script, wheel packages |
| `src/games/mr-muncher/mr_muncher/` | the game (moved from `src/glitchygames/examples/mr_muncher/`) |
| `src/games/mr-muncher/tests/` | its tests (moved from `tests/examples/test_mr_muncher*.py`) and golden replay |
| `scripts/workspace_packages.py` | reads the workspace: members, their layers, import packages, test and fixture directories |
| `tests/harness.py` | the shared test harness (was `tests/conftest.py`), loaded as a plugin by the root `conftest.py` |
| `tests/test_suite_collection.py` | the root holds no importable engine; every member's tests are collected |
| `src/glitchygames/logical_names.py` | logical names: `EXAMPLES_LAYERS`, `MEMBER_LAYERS`, `logical_name`, the inverse (Task 5) |
| `src/glitchygames/replay/driver.py`, `src/glitchygames/replay/playback.py`, `src/glitchygames/scene_start.py`, `src/glitchygames/engine/game_engine.py`, `src/glitchygames/replay/rebaseline.py` | record (`game`, `scene`) and compare logical names; a rebaseline writes the current game's |
| `tests/replay/test_recording_logical_names.py` | every committed recording's logical names resolve |
| `tests/fixtures/replays/*/golden.jsonl.gz`, `src/glitchygames/examples/paddleslap_demos/rally.jsonl.gz` | converted once to logical names (Task 6) |
| `src/glitchygames/code_tree.py` | `MEASURED_PATHS = ('src', ...)` |
| `tests/test_workspace_config.py` | every tool's configuration names every member; `MEMBER_LAYERS` equals the workspace |
| `noxfile.py` | installs every member (`--all-packages`), lints and formats `src/` paths |
| `scripts/build_browser_bundle.py` | the engine archive from `src/glitchygames/`; ships a game's member package as its own archive |
| `src/glitchygames/recording_metrics.py` | `RECORDING_PATH_RENAMES`: a moved recording keeps its history (Task 7: the demo; Task 9: Mr. Muncher) |

---

### Task 1: The shared test harness as a plugin

The 528-line `tests/conftest.py` (autouse fixtures, SDL defaults, display canvas, black-frame
check, memory collector) only applies under `tests/`. Member tests need it, so it becomes a
plugin module the root `conftest.py` loads first.

**Files:**
- Move: `tests/conftest.py` -> `tests/harness.py`
- Modify: `conftest.py` (root)
- Test: `tests/test_suite_collection.py`

**Interfaces:**
- Produces: `tests.harness` (the same fixtures and hooks `tests/conftest.py` had), first in the
  root `pytest_plugins`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_suite_collection.py`)

```python
def test_the_shared_harness_is_a_plugin_loaded_before_any_other():
    """Every package's tests get the harness: SDL defaults set before anything imports pygame."""
    import conftest as root_conftest

    assert root_conftest.pytest_plugins[0] == 'tests.harness'
    assert not (TESTS_ROOT / 'conftest.py').exists(), 'the harness lives in tests/harness.py'
```

(`TESTS_ROOT` is already defined in that file; check its name with
`grep -n "TESTS_ROOT =" tests/test_suite_collection.py`.)

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_suite_collection.py -k shared_harness`
Expected: FAIL (`'pytester' == 'tests.harness'`).

- [ ] **Step 3: Move the harness and load it**

```bash
git mv tests/conftest.py tests/harness.py
```

Root `conftest.py`, the plugin list becomes (its comment gains one line):

```python
# tests.harness is the shared test harness (fixtures, SDL defaults, display canvas): first, so its
# SDL defaults are in place before any other plugin imports pygame, and loaded here so every
# package's tests (tests/, games/*/tests/) get it
pytest_plugins = [
    'tests.harness',
    'pytester',
    'glitchygames.testing.replays',
    'tests.driver_comparison',
    'glitchygames.testing.frame_fingerprints',
]
```

Update the harness's module docstring first line to say it is the plugin
(`"""The shared test harness, loaded by the root conftest.py for every package's tests."""`) and
any comment in it that says "conftest" about itself. Fix references to `tests/conftest.py` in
docs and comments: `git grep -n "tests/conftest.py"` (CLAUDE.md, docs, tests/sdl_defaults.py,
tests/garbage_collection.py and others).

- [ ] **Step 4: Run the test and the whole suite**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_suite_collection.py`, then `uv run pytest`.
Expected: PASS; the whole suite unchanged (same counts as before the move, 100% coverage).

- [ ] **Step 5: Commit**

```bash
git add -A conftest.py tests/ CLAUDE.md docs
git commit -m "Test harness as a plugin the root conftest loads, so member packages' tests get it"
```

---

### Task 2: Scenes declare the modules they used to live in

**Files:**
- Modify: `glitchygames/scenes/scene.py` (class attributes beside `CAPTURES_SCENE_START`, ~line 2813)
- Modify: `glitchygames/replay/driver.py` (`check_recorded_game` ~2729, `start_replay` ~2826)
- Modify: `glitchygames/replay/playback.py` (`find_scene_class` ~1029)
- Modify: `glitchygames/engine/game_engine.py` (`_start_requested_replay` ~1805)
- Test: `tests/world/test_gameplay_replay.py` (the `check_recorded_game` tests ~1466),
  `tests/replay/test_playback_scope.py` (the `find_scene_class` tests ~465)

**Interfaces:**
- Produces: `Scene.PREVIOUS_MODULES: ClassVar[frozenset[str]] = frozenset()`;
  `check_recorded_game(*, header, game_class_name, game_module, previous_game_modules: frozenset[str] = frozenset())`;
  `start_replay(..., previous_game_modules: frozenset[str] = frozenset(), ...)`;
  `find_scene_class` honours each candidate class's `PREVIOUS_MODULES`.

- [ ] **Step 1: Write the failing tests**

In `tests/world/test_gameplay_replay.py`, beside `test_another_game_of_the_same_name_is_refused`:

```python
    def test_a_recording_of_a_previous_module_is_accepted(self):
        """A game that moved (glitchygames.examples -> its own package) replays old recordings."""
        check_recorded_game(
            header={'game_class': 'Game', 'game_module': 'glitchygames.examples.paddleslap'},
            game_class_name='Game',
            game_module='paddleslap',
            previous_game_modules=frozenset({'glitchygames.examples.paddleslap'}),
        )

    def test_a_previous_module_of_another_game_is_still_refused(self):
        """Only the modules the game itself lists count."""
        with pytest.raises(ReplayRefusedError, match=r'glitchygames\.examples\.joystick_demo'):
            check_recorded_game(
                header={'game_class': 'Game', 'game_module': 'glitchygames.examples.joystick_demo'},
                game_class_name='Game',
                game_module='paddleslap',
                previous_game_modules=frozenset({'glitchygames.examples.paddleslap'}),
            )
```

In `tests/replay/test_playback_scope.py`, beside the find-by-module tests (module-level classes,
so the subclass walk finds them):

```python
class MovedScene(Scene):
    """A scene that used to live in another module."""

    PREVIOUS_MODULES = frozenset({'old_package.old_module'})


def test_a_scene_start_naming_a_previous_module_finds_the_moved_scene():
    assert find_scene_class(name='MovedScene', module='old_package.old_module') is MovedScene


def test_a_scene_start_naming_another_module_is_refused():
    assert find_scene_class(name='MovedScene', module='unrelated.module') is None
```

And in a scene test file (`tests/scenes/test_scene.py`):

```python
def test_a_scene_names_no_previous_modules_by_default():
    assert Scene.PREVIOUS_MODULES == frozenset()
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/world/test_gameplay_replay.py tests/replay/test_playback_scope.py tests/scenes/test_scene.py -k "previous or moved or another_module"`
Expected: FAIL (`unexpected keyword argument 'previous_game_modules'`,
`AttributeError: ... PREVIOUS_MODULES`).

- [ ] **Step 3: Implement**

`glitchygames/scenes/scene.py`, beside `CAPTURES_SCENE_START`:

```python
    # The modules this scene class was defined in before it moved (e.g. a game moved out of
    # glitchygames/examples into its own package): a recording naming one of them replays as
    # this class (glitchygames/replay/driver.py check_recorded_game, replay/playback.py
    # find_scene_class), so committed recordings never need rewriting after a move
    PREVIOUS_MODULES: ClassVar[frozenset[str]] = frozenset()
```

`glitchygames/replay/driver.py` `check_recorded_game`: add the parameter, document it, and
widen `modules_differ`:

```python
def check_recorded_game(
    *,
    header: Mapping[str, Any],
    game_class_name: str,
    game_module: str,
    previous_game_modules: frozenset[str] = frozenset(),
) -> None:
    """Refuse a recording of another game.

    The class names must match. So must the modules, when the header holds one (recordings
    made before headers held it do not) and neither is ``__main__`` (a game file run as a
    script, ``python paddleslap.py``, is the same game as its console script). A module the
    game lists in ``Scene.PREVIOUS_MODULES`` (where it lived before it moved) matches too.

    Args:
        header: The recording's header fields.
        game_class_name: The class name of the game being started.
        game_module: The module the game being started is defined in.
        previous_game_modules: The modules the game was defined in before (its
            ``PREVIOUS_MODULES``).

    Raises:
        ReplayRefusedError: If the recording's ``game_class`` (or ``game_module``) is a
            different game's.

    """
    recorded_game = header.get(GAME_CLASS_HEADER_FIELD)
    recorded_module = header.get(GAME_MODULE_HEADER_FIELD)
    modules_differ = (
        recorded_module is not None
        and SCRIPT_MODULE_NAME not in {recorded_module, game_module}
        and recorded_module != game_module
        and recorded_module not in previous_game_modules
    )
```

(the rest unchanged). `start_replay` gains `previous_game_modules: frozenset[str] = frozenset()`
(documented in Args) and passes it to `check_recorded_game`. In `game_engine.py`
`_start_requested_replay`, pass `previous_game_modules=game_class.PREVIOUS_MODULES`.

`glitchygames/replay/playback.py` `find_scene_class`: the exact match also takes a previous
module (and the docstring says so):

```python
    exact_matches = [
        scene_class
        for scene_class in named_alike
        if module is not None
        and (scene_class.__module__ == module or module in scene_class.PREVIOUS_MODULES)
    ]
```

- [ ] **Step 4: Lint, then run the tests**

Run: `uv run ruff check glitchygames tests && uv run basedpyright glitchygames/replay glitchygames/scenes/scene.py glitchygames/engine/game_engine.py`,
then the Step 2 command, then `uv run pytest --dummy-only tests/world tests/replay tests/scenes`.
Expected: PASS.

- [ ] **Step 5: Document and commit**

`docs/architecture/gameplay_replay.md` (where the game and scene checks are described) and
CLAUDE.md's replay section ("a recording of another game ... is refused"): add that a scene
class's `PREVIOUS_MODULES` match too.

```bash
git add glitchygames tests docs CLAUDE.md
git commit -m "Scene.PREVIOUS_MODULES: a moved game replays recordings of where it used to live"
```

---

### Task 3: The workspace reader

**Files:**
- Create: `scripts/workspace_packages.py`
- Test: `tests/test_workspace_packages.py`

**Interfaces:**
- Produces:
  ```python
  class WorkspaceMember(BaseModel):  # frozen, extra='forbid'
      directory: Path            # games/mr-muncher (absolute)
      distribution: str          # mr-muncher
      import_packages: tuple[str, ...]   # ('mr_muncher',)
      console_scripts: tuple[str, ...]   # ('mr-muncher',)
      @property
      def package_directories(self) -> tuple[Path, ...]  # directory / each import package
      @property
      def tests_directory(self) -> Path                  # directory / 'tests'
      @property
      def replay_fixtures_directory(self) -> Path        # tests_directory / 'fixtures' / 'replays'
  def workspace_members(*, project_root: Path) -> list[WorkspaceMember]
  def source_package_directories(*, project_root: Path) -> list[Path]  # glitchygames/ + every member's
  ```

- [ ] **Step 1: Write the failing tests** (`tests/test_workspace_packages.py`)

```python
"""scripts/workspace_packages.py reads the uv workspace: the one list of member packages."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.workspace_packages import (
    WorkspaceMember,
    source_package_directories,
    workspace_members,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ROOT_PYPROJECT = """
[project]
name = "glitchygames"

[tool.uv.workspace]
members = ["games/space-game"]
"""
MEMBER_PYPROJECT = """
[project]
name = "space-game"

[project.scripts]
space-game = "space_game:main"

[tool.hatch.build.targets.wheel]
packages = ["space_game"]
"""


def write_workspace(root: Path) -> None:
    """Write a root project with one member, games/space-game."""
    (root / 'pyproject.toml').write_text(ROOT_PYPROJECT, encoding='utf-8')
    member = root / 'games' / 'space-game'
    (member / 'space_game').mkdir(parents=True)
    (member / 'pyproject.toml').write_text(MEMBER_PYPROJECT, encoding='utf-8')


def test_a_member_is_read_from_its_own_pyproject(tmp_path):
    write_workspace(tmp_path)

    (member,) = workspace_members(project_root=tmp_path)

    assert member == WorkspaceMember(
        directory=tmp_path / 'games' / 'space-game',
        distribution='space-game',
        import_packages=('space_game',),
        console_scripts=('space-game',),
    )
    assert member.package_directories == (tmp_path / 'games' / 'space-game' / 'space_game',)
    assert member.replay_fixtures_directory == (
        tmp_path / 'games' / 'space-game' / 'tests' / 'fixtures' / 'replays'
    )


def test_source_packages_are_the_engine_then_every_member(tmp_path):
    write_workspace(tmp_path)

    assert source_package_directories(project_root=tmp_path) == [
        tmp_path / 'glitchygames',
        tmp_path / 'games' / 'space-game' / 'space_game',
    ]


def test_a_member_without_its_pyproject_is_refused(tmp_path):
    write_workspace(tmp_path)
    (tmp_path / 'games' / 'space-game' / 'pyproject.toml').unlink()

    with pytest.raises(FileNotFoundError, match='space-game'):
        workspace_members(project_root=tmp_path)

```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_workspace_packages.py`
Expected: FAIL (`ModuleNotFoundError: scripts.workspace_packages`).

- [ ] **Step 3: Implement** (`scripts/workspace_packages.py`)

```python
"""The uv workspace's members, read from the root and each member's pyproject.toml.

The one place that knows which packages the repository holds besides the engine: the engine's
guards (tests/test_engine_doors.py and others), the configuration check
(tests/test_workspace_config.py), the browser build and the replay metrics ask it. Members are
listed explicitly in the root ``[tool.uv.workspace] members`` (no globs).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict

ENGINE_PACKAGE = 'glitchygames'


class WorkspaceMember(BaseModel):
    """One member package of the workspace.

    Attributes:
        directory: The member's directory (games/mr-muncher).
        distribution: Its distribution name (mr-muncher).
        import_packages: The packages its wheel holds (mr_muncher).
        console_scripts: Its console scripts (mr-muncher).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    directory: Path
    distribution: str
    import_packages: tuple[str, ...]
    console_scripts: tuple[str, ...]

    @property
    def package_directories(self: Self) -> tuple[Path, ...]:
        """The source directories of its import packages."""
        return tuple(self.directory / package for package in self.import_packages)

    @property
    def tests_directory(self: Self) -> Path:
        """Where its tests are."""
        return self.directory / 'tests'

    @property
    def replay_fixtures_directory(self: Self) -> Path:
        """Where its golden replays are (``<console-script>/<name>.jsonl.gz`` below it)."""
        return self.tests_directory / 'fixtures' / 'replays'


def _read_toml(*, path: Path) -> dict[str, object]:
    with path.open('rb') as toml_file:
        return tomllib.load(toml_file)


def workspace_members(*, project_root: Path) -> list[WorkspaceMember]:
    """Return the workspace's members, in the order the root pyproject lists them.

    Args:
        project_root: The repository.

    Returns:
        The members.

    Raises:
        FileNotFoundError: If a listed member has no pyproject.toml.

    """
    root = _read_toml(path=project_root / 'pyproject.toml')
    workspace = root.get('tool', {}).get('uv', {}).get('workspace', {})
    members: list[WorkspaceMember] = []
    for member_path in workspace.get('members', []):
        directory = project_root / member_path
        pyproject_path = directory / 'pyproject.toml'
        if not pyproject_path.is_file():
            message = f'Workspace member {member_path} has no pyproject.toml'
            raise FileNotFoundError(message)
        member = _read_toml(path=pyproject_path)
        project = member['project']
        wheel = member.get('tool', {}).get('hatch', {}).get('build', {}).get('targets', {})
        packages = wheel.get('wheel', {}).get('packages', [])
        members.append(
            WorkspaceMember(
                directory=directory,
                distribution=project['name'],
                import_packages=tuple(Path(package).name for package in packages),
                console_scripts=tuple(project.get('scripts', {})),
            )
        )
    return members


def source_package_directories(*, project_root: Path) -> list[Path]:
    """Return every source package the engine's guards scan: the engine's, then each member's.

    Returns:
        The package directories.

    """
    directories = [project_root / ENGINE_PACKAGE]
    for member in workspace_members(project_root=project_root):
        directories.extend(member.package_directories)
    return directories
```

(`tomllib` returns plain dicts; the `.get` chains are typed `object` by basedpyright: cast each
level with `typing.cast('dict[str, Any]', ...)` as the existing scripts do — check
`scripts/replay_metrics.py` or `scripts/record_scripted_session.py` for the house pattern.)

- [ ] **Step 4: Lint, then run the tests**

Run: `uv run ruff check scripts tests && uv run basedpyright scripts/workspace_packages.py tests/test_workspace_packages.py && uv run pytest --dummy-only --no-cov -q tests/test_workspace_packages.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/workspace_packages.py tests/test_workspace_packages.py
git commit -m "scripts/workspace_packages.py: the one reader of the workspace's member packages"
```

---

### Task 4: The engine's guards scan every member package

**Files:**
- Modify: `tests/test_engine_doors.py` (`PACKAGE` ~line 24, the scan ~234-241)
- Modify: `tests/test_randomness.py` (~465-471)
- Modify: `tests/test_recording.py` (~1340-1350)
- Test: the same files (one new test each)

**Interfaces:**
- Consumes: `source_package_directories(project_root=...)` (Task 3).
- Produces: each guard scans `glitchygames/` and every member package. Allowlist keys stay as
  they are for engine files (relative to `glitchygames/`); a member file's key is its path
  relative to the repository (`games/mr-muncher/mr_muncher/game.py`), so the two never clash.

- [ ] **Step 1: Write the failing tests**

`tests/test_engine_doors.py`:

```python
def test_the_doors_guard_scans_every_member_package():
    """A game moved out of glitchygames/ stays inside the guard."""
    scanned_roots = set(DOOR_SCAN_ROOTS)

    assert set(source_package_directories(project_root=PROJECT_ROOT)) <= scanned_roots


def test_a_bypass_in_a_member_package_is_reported(tmp_path):
    """The scan reads a member file the same way as an engine file."""
    member_file = tmp_path / 'games' / 'space-game' / 'space_game' / 'game.py'
    member_file.parent.mkdir(parents=True)
    member_file.write_text('import time\n\n\ndef now():\n    return time.monotonic()\n', encoding='utf-8')

    assert door_bypasses(source_path=member_file) == ['5: time.monotonic']
```

(`door_bypasses` already exists, see its tests ~line 262; `PROJECT_ROOT` = the repository root,
define it beside `PACKAGE` if missing.) The same pair for `tests/test_randomness.py` (a member
file calling `random.random()` is reported by its scan function) and the roots check for
`tests/test_recording.py`'s pump-seam scan.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_engine_doors.py tests/test_randomness.py tests/test_recording.py -k "member"`
Expected: FAIL (`NameError: DOOR_SCAN_ROOTS`).

- [ ] **Step 3: Implement**

In each guard, replace the single package root with the list:

```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# The engine and every workspace member package (scripts/workspace_packages.py)
DOOR_SCAN_ROOTS = source_package_directories(project_root=PROJECT_ROOT)
```

and iterate `for root in DOOR_SCAN_ROOTS: for path in sorted(root.rglob('*.py')):`, computing
the allowlist key as `path.relative_to(PACKAGE)` for engine files and
`path.relative_to(PROJECT_ROOT)` for member files. Keep each guard's failure message listing
the offending file and line.

- [ ] **Step 4: Run the guards**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_engine_doors.py tests/test_randomness.py tests/test_recording.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_engine_doors.py tests/test_randomness.py tests/test_recording.py
git commit -m "Doors, randomness and pump-seam guards scan every workspace member package"
```

---

### Task 5: Recordings name games by logical names (replaces `PREVIOUS_MODULES`)

The user's decision 8 (2026-10-25): a recording names its game and scenes by **logical names**,
which do not change when a game moves, instead of Python module paths plus a list of modules a
class used to live in. Task 2's commits (19255ee8, eecc76d7) exist, so this task removes
`Scene.PREVIOUS_MODULES` and everything that reads it, keeps `start_replay` taking the game
class, and adds the logical names.

A logical name mirrors the four layers: the layer, then the module path inside the package
starting with the package's name, then `:` and the class's qualified name:

| Class | Module | Logical name |
|---|---|---|
| `MrMuncherScene` | `glitchygames.examples.mr_muncher.game` (today) | `games.mr_muncher.game:MrMuncherScene` |
| `MrMuncherScene` | `mr_muncher.game` (after Task 9) | `games.mr_muncher.game:MrMuncherScene` |
| `Game` | `glitchygames.examples.paddleslap` | `games.paddleslap:Game` |
| `Game` | `glitchygames.examples.joystick_demo` | `demos.joystick_demo:Game` |
| `PauseScene` | `glitchygames.scenes.builtin_scenes.pause` | `glitchygames.scenes.builtin_scenes.pause:PauseScene` |
| a test's scene | `tests.replay.test_playback_scope` | `tests.replay.test_playback_scope:CountingScene` |

A module in no layer (the engine's own, a test's, a third-party game's, `__main__`) keeps its
module path. The `:` separates the module from the qualified name, so a logical name resolves
unambiguously (`module:qualname`, as entry points are written).

**Where the reader lives** (decided here): the engine needs the layer at run time (every
recording's header and scene starts, every replay's check), but an installed engine (the wheel,
nox's non-editable venv, the browser bundle) has no workspace `pyproject.toml` to read, and the
engine cannot import `scripts/`. So the mapping is data in the engine,
`glitchygames/logical_names.py` (a leaf module): `EXAMPLES_LAYERS` (the games still in
`glitchygames/examples/`, keyed by their package name there) and `MEMBER_LAYERS` (workspace
members' top-level import packages; empty until Task 9). `scripts/workspace_packages.py` stays
the one reader of the workspace, and `tests/test_workspace_config.py` (Task 8) keeps
`MEMBER_LAYERS` equal to what it reads (each member's layer is its directory's parent under
`src/`: `src/games/mr-muncher` -> `games`). Part 2 deletes `EXAMPLES_LAYERS` once nothing is
left in `glitchygames/examples/`.

**Files:**
- Create: `glitchygames/logical_names.py`
- Modify: `glitchygames/scenes/scene.py` (remove `PREVIOUS_MODULES`, ~2813-2818),
  `glitchygames/replay/driver.py` (`GAME_HEADER_FIELD`, `check_recorded_game`, `start_replay`'s
  docstring), `glitchygames/replay/playback.py` (`find_scene_class` and its caller ~1196),
  `glitchygames/scene_start.py` (`SceneStart.scene`, set at ~310), `glitchygames/engine/game_engine.py`
  (the header ~1661, `Rebaseline(...)` ~966), `glitchygames/instant_replay.py` (its header ~206),
  `glitchygames/replay/rebaseline.py` (`rebaseline_header`, `Rebaseline.__init__`),
  `glitchygames/recording.py` (the format description of the header and `scene_start`)
- Test: `tests/test_logical_names.py` (new), `tests/world/test_gameplay_replay.py` (the
  `check_recorded_game` tests ~1466-1530, the rebaseline header tests ~3901, ~5514),
  `tests/replay/test_playback_scope.py` (`MovedScene` and its two tests ~119, the start tests
  ~516), `tests/scenes/test_scene.py` (~118), `tests/world/test_gameplay_recording.py` (~480),
  `tests/replay/test_recording_logical_names.py` (new: every committed recording resolves)
- Docs: `docs/architecture/gameplay_replay.md` (~253), CLAUDE.md (the replay section ~493, ~508)

**Interfaces:**
- Produces:
  ```python
  # glitchygames/logical_names.py
  LAYERS: tuple[str, ...] = ('games', 'demos', 'apps')
  EXAMPLES_PACKAGE = 'glitchygames.examples'
  EXAMPLES_LAYERS: dict[str, str]   # package name in glitchygames/examples -> layer
  MEMBER_LAYERS: dict[str, str]     # a member's top-level import package -> layer ({} until Task 9)
  def logical_module_name(*, module: str) -> str          # 'glitchygames.examples.paddleslap' -> 'games.paddleslap'
  def logical_name(*, scene_class: type) -> str           # -> 'games.paddleslap:Game'
  def module_for_logical_module(*, logical_module: str) -> str   # the inverse, for today's layout
  ```
  Header field `game` (`GAME_HEADER_FIELD`, the game class's logical name); `SceneStart.scene:
  str | None = None` (the scene class's logical name; None in recordings made before);
  `check_recorded_game(*, header, game_class: type[Scene])`; `find_scene_class(*, name, module=None,
  logical=None)`; `rebaseline_header(..., game_class: type[Scene])` writes the current game's
  `game` (and `game_class`, `game_module`) into NEW's header; `Rebaseline(..., game_class=...)`.
- Removes: `Scene.PREVIOUS_MODULES`, `check_recorded_game`'s `previous_game_modules`, and their
  tests.

- [ ] **Step 1: Write the failing tests**

`tests/test_logical_names.py`:

```python
"""glitchygames/logical_names.py: a recording names a game by where it belongs, not its module."""

from __future__ import annotations

import pytest

from glitchygames import logical_names
from glitchygames.logical_names import (
    logical_module_name,
    logical_name,
    module_for_logical_module,
)
from glitchygames.scenes import Scene


class LocalScene(Scene):
    """A scene in a module that belongs to no layer (this test file)."""


@pytest.mark.parametrize(
    ('module', 'expected'),
    [
        ('glitchygames.examples.mr_muncher.game', 'games.mr_muncher.game'),
        ('glitchygames.examples.paddleslap', 'games.paddleslap'),
        ('glitchygames.examples.joystick_demo', 'demos.joystick_demo'),
        ('glitchygames.scenes.builtin_scenes.pause', 'glitchygames.scenes.builtin_scenes.pause'),
        ('tests.test_logical_names', 'tests.test_logical_names'),
        ('__main__', '__main__'),
    ],
)
def test_a_module_gets_its_layer_or_keeps_its_path(module, expected):
    assert logical_module_name(module=module) == expected


def test_a_class_is_its_logical_module_and_qualified_name():
    assert logical_name(scene_class=LocalScene) == 'tests.test_logical_names:LocalScene'


def test_a_class_that_moved_into_a_member_keeps_its_logical_name(mocker):
    """The same game reported in its member package names the same logical name."""
    mocker.patch.dict(logical_names.MEMBER_LAYERS, {'space_game': 'games'})
    mocker.patch.dict(logical_names.EXAMPLES_LAYERS, {'space_game': 'games'})

    before = logical_module_name(module='glitchygames.examples.space_game.game')
    after = logical_module_name(module='space_game.game')

    assert before == after == 'games.space_game.game'


def test_a_logical_module_maps_back_to_the_module_that_holds_it(mocker):
    mocker.patch.dict(logical_names.MEMBER_LAYERS, {'space_game': 'games'})

    assert module_for_logical_module(logical_module='games.paddleslap') == (
        'glitchygames.examples.paddleslap'
    )
    assert module_for_logical_module(logical_module='games.space_game.game') == 'space_game.game'
    assert module_for_logical_module(logical_module='glitchygames.scenes') == 'glitchygames.scenes'


def test_every_example_game_and_demo_has_a_layer():
    """The owner's table (2026-10-25); Part 2 deletes it when glitchygames/examples is empty."""
    assert logical_names.EXAMPLES_LAYERS == {
        'paddleslap': 'games',
        'brave_adventurer': 'games',
        'brave_adventurer_papyrus': 'games',
        'clockwork_keep': 'games',
        'mr_muncher': 'games',
        'dt_demo': 'demos',
        'joystick_demo': 'demos',
        'text_input_demo': 'demos',
    }
```

`tests/world/test_gameplay_replay.py`, class `TestRefusals` and the `check_recorded_game` tests
beside it (~1440-1530):
- delete the three `PREVIOUS_MODULES` tests (~1466-1513: the engine handing `PREVIOUS_MODULES`
  over, a previous module accepted, another game's previous module refused);
- the unit tests pass plain stand-in classes, never `Scene` subclasses (so `find_scene_class`'s
  subclass walk never sees them): `stand_in_game(*, name, module)` returns
  `type(name, (), {'__module__': module})`; `test_without_both_modules_the_name_alone_is_checked`
  becomes `check_recorded_game(header=header, game_class=stand_in_game(name='Game', module=game_module))`
  and the refusal `stand_in_game(name='Other', module=game_module)`;
- `test_wrong_game_is_refused` and `test_a_same_named_game_from_another_module_is_refused`
  rewrite an engine-made recording, which now holds `game`: their `change` also drops it
  (`lambda trace: (trace.pop('game'), trace.update(game_class='SomeOtherGame'))`), so they keep
  testing the old-format rule, and one new test refuses by logical name.

Add:

```python
def stand_in_game(*, name: str, module: str) -> type:
    """A plain class standing in for a game class (not a Scene: no subclass walk finds it)."""
    return type(name, (), {'__module__': module})
```

and in `TestRefusals`:

```python
    def test_a_recording_naming_another_logical_name_is_refused(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        rewrite_recording(
            recording_path=recording_path,
            change=lambda trace: trace.update(game='games.some_other_game:DepartureRecordedScene'),
        )
        with pytest.raises(SystemExit) as exit_info:
            replay_session(recording_path=recording_path, mocker=mocker)
        assert exit_info.value.code == ExitCode.UNUSABLE_INPUT
        assert 'games.some_other_game:DepartureRecordedScene' in caplog.text

    def test_a_recording_made_through_the_engine_holds_logical_names_and_replays(
        self, mocker, tmp_path
    ):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        trace = read_trace_result(path=recording_path).trace
        starts = [frame[SCENE_START_FIELD] for frame in trace['frames'] if SCENE_START_FIELD in frame]

        assert trace['game'] == logical_name(scene_class=DepartureRecordedScene)
        assert starts
        for start in starts:
            module = logical_module_name(module=start['scene_module'])
            assert start['scene'] == f"{module}:{start['scene_class']}"
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources.result.divergence is None
```

beside `test_another_game_of_the_same_name_is_refused`:

```python
    def test_a_recording_naming_the_games_logical_name_is_accepted(self):
        game = stand_in_game(name='Game', module='glitchygames.examples.paddleslap')
        check_recorded_game(header={'game_class': 'Game', 'game': 'games.paddleslap:Game'}, game_class=game)

    def test_a_logical_name_of_another_game_is_refused(self):
        game = stand_in_game(name='Game', module='glitchygames.examples.paddleslap')
        with pytest.raises(ReplayRefusedError, match=r'demos\.joystick_demo:Game'):
            check_recorded_game(header={'game_class': 'Game', 'game': 'demos.joystick_demo:Game'}, game_class=game)

    def test_a_game_that_moved_still_matches_its_logical_name(self, mocker):
        """The same game reported in a member package (after a move) is the same game."""
        mocker.patch.dict(logical_names.MEMBER_LAYERS, {'paddleslap': 'games'})
        moved = stand_in_game(name='Game', module='paddleslap')
        check_recorded_game(header={'game_class': 'Game', 'game': 'games.paddleslap:Game'}, game_class=moved)

    def test_an_old_format_recording_is_compared_by_its_exact_module(self):
        """No `game` field (recorded before logical names): the module must match exactly."""
        game = stand_in_game(name='Game', module='glitchygames.examples.paddleslap')
        check_recorded_game(
            header={'game_class': 'Game', 'game_module': 'glitchygames.examples.paddleslap'}, game_class=game
        )
        moved = stand_in_game(name='Game', module='paddleslap')
        with pytest.raises(ReplayRefusedError, match=r'glitchygames\.examples\.paddleslap'):
            check_recorded_game(
                header={'game_class': 'Game', 'game_module': 'glitchygames.examples.paddleslap'},
                game_class=moved,
            )
```

(imports: `from glitchygames import logical_names`, `from glitchygames.logical_names import
logical_module_name, logical_name`, `from glitchygames.recording import SCENE_START_FIELD` where
not already imported; `record_session`, `replay_session`, `rewrite_recording` and
`read_trace_result` are this file's.)

In `TestRebaselinedHeader` (~5505):

```python
    def test_a_rebaseline_writes_the_current_games_logical_name(self, tmp_path):
        """NEW names the game that ran, not OLD's header: how old recordings are converted."""
        from glitchygames.replay.rebaseline import rebaseline_header

        game = stand_in_game(name='Game', module='glitchygames.examples.paddleslap')
        header = rebaseline_header(
            original_header={'random_seed': 5, 'game_class': 'Game', 'game_module': 'old.module'},
            original_path=tmp_path / 'old.jsonl.gz',
            measurement_run=rebaseline_measurement_run(),
            game_class=game,
        )

        assert header['game'] == 'games.paddleslap:Game'
        assert header['game_module'] == 'glitchygames.examples.paddleslap'
```

`tests/replay/test_playback_scope.py`: delete `MovedScene` and its two tests (~119 and the two
functions after it); add:

```python
def test_a_scene_start_naming_a_logical_name_finds_its_scene():
    assert (
        find_scene_class(
            name='CountingScene', module='somewhere.else', logical=logical_name(scene_class=CountingScene)
        )
        is CountingScene
    )


def test_a_scene_start_naming_another_logical_name_is_refused():
    assert find_scene_class(name='CountingScene', module=None, logical='games.other:CountingScene') is None
```

and in the start-capture test (~516) `assert start.scene == logical_name(scene_class=CountingScene)`,
and the old-start read-back (~523) also deletes `scene` and asserts it reads back as None.

`tests/scenes/test_scene.py`: delete `test_a_scene_names_no_previous_modules_by_default` (~118).
`tests/world/test_gameplay_recording.py` (~480): add
`assert header['game'] == logical_name(scene_class=DepartureRecordedScene)` after the
`game_module` assertion.

`tests/replay/test_recording_logical_names.py`:

```python
"""Every committed recording names its game and scenes by logical names that resolve."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from glitchygames.logical_names import module_for_logical_module
from glitchygames.recording import SCENE_START_FIELD
from glitchygames.testing.replays import bundled_demo_paths
from glitchygames.tracing import read_trace
from scripts.workspace_packages import workspace_members

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COMMITTED_RECORDINGS = sorted(
    [
        *PROJECT_ROOT.glob('tests/fixtures/replays/*/*.jsonl.gz'),
        *(
            recording
            for member in workspace_members(project_root=PROJECT_ROOT)
            for recording in member.replay_fixtures_directory.glob('*.jsonl.gz')
        ),
        *(path for _console_script, path in bundled_demo_paths()),
    ]
)


def resolves(logical: str) -> bool:
    """Whether ``layer.module:qualname`` names a class of a real module in the workspace."""
    logical_module, _, qualified_name = logical.partition(':')
    try:
        target: object = importlib.import_module(module_for_logical_module(logical_module=logical_module))
    except ImportError:
        return False
    for attribute in qualified_name.split('.'):
        target = getattr(target, attribute, None)
    return isinstance(target, type)


def recording_id(path: Path) -> str:
    """The recording's repository path (the bundled demo, in the installed engine: its name)."""
    return path.relative_to(PROJECT_ROOT).as_posix() if path.is_relative_to(PROJECT_ROOT) else path.name


@pytest.mark.parametrize('recording', COMMITTED_RECORDINGS, ids=recording_id)
def test_every_logical_name_in_the_recording_resolves(recording):
    trace = read_trace(path=recording)
    names = [trace.get('game')] + [
        frame[SCENE_START_FIELD].get('scene')
        for frame in trace['frames']
        if SCENE_START_FIELD in frame
    ]

    unresolved = [name for name in names if name is None or not resolves(name)]
    assert not unresolved, f'{recording}: logical names missing or unresolved: {unresolved}'


def test_the_committed_recordings_are_all_checked():
    """Five golden replays and PaddleSlap's demo (more as games, demos and apps gain them)."""
    assert len(COMMITTED_RECORDINGS) >= 6
```

(`read_trace` returns the header's fields at the top level with `frames` beside them, as
`tests/world/test_gameplay_replay.py` reads `read_trace_result(...).trace['frames']`.)

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_logical_names.py tests/world/test_gameplay_replay.py tests/replay/test_playback_scope.py tests/world/test_gameplay_recording.py tests/replay/test_recording_logical_names.py -k "logical or old_format or moved or rebaseline_writes or refused"`
Expected: FAIL (`ModuleNotFoundError: glitchygames.logical_names`; then, once it exists, the
six committed recordings fail the resolve check: `logical names missing or unresolved: [None,
...]`, which Task 6 fixes by converting them).

- [ ] **Step 3: Implement**

`glitchygames/logical_names.py`:

```python
"""Logical names: how a recording names a game or scene class, unchanged when its code moves.

A logical name is ``<layer>.<module path inside its package>:<qualified name>``
(``games.mr_muncher.game:MrMuncherScene``). The layer (``games``, ``demos``, ``apps``) is the
workspace layer the class's package belongs to (``src/<layer>/<member>/``,
plans/2026-10-24-workspace-packages.md); the module path starts with the package's name, wherever
the package is installed. A module that belongs to no layer (the engine's own, a test's, a
third-party game's, ``__main__``) keeps its module path.

The layers are data here, not read from the workspace: an installed engine has no workspace to
read, and the engine never imports scripts/. ``MEMBER_LAYERS`` is kept equal to the workspace
(scripts/workspace_packages.py) by tests/test_workspace_config.py; ``EXAMPLES_LAYERS`` covers
the games and demos still inside glitchygames/examples/ and goes when that directory does.
A leaf module: it imports nothing from the engine.
"""

from __future__ import annotations

LAYERS: tuple[str, ...] = ('games', 'demos', 'apps')
EXAMPLES_PACKAGE = 'glitchygames.examples'
# Games and demos not yet moved out of glitchygames/examples/: package name there -> layer
# (the user, 2026-10-25; Part 2 of the workspace plan deletes it)
EXAMPLES_LAYERS: dict[str, str] = {
    'paddleslap': 'games',
    'brave_adventurer': 'games',
    'brave_adventurer_papyrus': 'games',
    'clockwork_keep': 'games',
    'mr_muncher': 'games',
    'dt_demo': 'demos',
    'joystick_demo': 'demos',
    'text_input_demo': 'demos',
}
# Workspace members: top-level import package -> layer (src/<layer>/<member>/); equal to the
# workspace, checked by tests/test_workspace_config.py
MEMBER_LAYERS: dict[str, str] = {}


def logical_module_name(*, module: str) -> str:
    """Return a module's logical name: its layer and its path inside its package.

    Args:
        module: A module's import path (``glitchygames.examples.paddleslap``, ``mr_muncher.game``).

    Returns:
        ``<layer>.<path from the package>`` (``games.paddleslap``), or the module itself when it
        belongs to no layer.

    """
    examples_prefix = f'{EXAMPLES_PACKAGE}.'
    if module.startswith(examples_prefix):
        inside_examples = module.removeprefix(examples_prefix)
        layer = EXAMPLES_LAYERS.get(inside_examples.split('.')[0])
        return module if layer is None else f'{layer}.{inside_examples}'
    layer = MEMBER_LAYERS.get(module.split('.')[0])
    return module if layer is None else f'{layer}.{module}'


def logical_name(*, scene_class: type) -> str:
    """Return a class's logical name, as recordings name games and scenes.

    Args:
        scene_class: The class (a game or scene class).

    Returns:
        ``<logical module>:<qualified name>`` (``games.paddleslap:Game``).

    """
    return f'{logical_module_name(module=scene_class.__module__)}:{scene_class.__qualname__}'


def module_for_logical_module(*, logical_module: str) -> str:
    """Return the module that holds a logical module today (the inverse of ``logical_module_name``).

    Args:
        logical_module: A logical module (``games.paddleslap``).

    Returns:
        The import path (``glitchygames.examples.paddleslap``, ``mr_muncher.game``), or the name
        itself when its first part is not a layer.

    """
    layer, _, inside_package = logical_module.partition('.')
    if layer not in LAYERS or not inside_package:
        return logical_module
    package = inside_package.split('.')[0]
    if MEMBER_LAYERS.get(package) == layer:
        return inside_package
    if EXAMPLES_LAYERS.get(package) == layer:
        return f'{EXAMPLES_PACKAGE}.{inside_package}'
    return logical_module
```

`glitchygames/scenes/scene.py`: delete `PREVIOUS_MODULES` and its comment.

`glitchygames/replay/driver.py`: `GAME_HEADER_FIELD = 'game'` beside `GAME_MODULE_HEADER_FIELD`;
`check_recorded_game` becomes:

```python
def check_recorded_game(*, header: Mapping[str, Any], game_class: type[Scene]) -> None:
    """Refuse a recording of another game.

    A recording holding ``game`` (the game class's logical name, glitchygames/logical_names.py)
    must name the started game's logical name; when either side's module is ``__main__`` (a
    game file run as a script, ``python paddleslap.py``, is the same game as its console
    script) only the qualified names are compared. A recording without ``game`` (made before
    logical names) is compared as before: the class names must match, and so must the modules
    when the header holds one and neither is ``__main__``.

    Args:
        header: The recording's header fields.
        game_class: The game being started.

    Raises:
        ReplayRefusedError: If the recording is of a different game.

    """
    recorded_game = header.get(GAME_CLASS_HEADER_FIELD)
    recorded_logical_name = header.get(GAME_HEADER_FIELD)
    started_logical_name = logical_name(scene_class=game_class)
    if recorded_logical_name is not None:
        recorded_module, _, recorded_qualified_name = str(recorded_logical_name).partition(':')
        started_module, _, started_qualified_name = started_logical_name.partition(':')
        differs = (
            recorded_qualified_name != started_qualified_name
            if SCRIPT_MODULE_NAME in {recorded_module, started_module}
            else recorded_logical_name != started_logical_name
        )
        recorded_place = str(recorded_logical_name)
    else:
        recorded_module = header.get(GAME_MODULE_HEADER_FIELD)
        modules_differ = (
            recorded_module is not None
            and SCRIPT_MODULE_NAME not in {recorded_module, game_class.__module__}
            and recorded_module != game_class.__module__
        )
        differs = recorded_game != game_class.__name__ or modules_differ
        recorded_place = f'{recorded_game} ({recorded_module or "module not recorded"})'
    if differs:
        message = (
            f'The recording is of the game {recorded_place}, not {started_logical_name}; '
            'refusing to replay it'
        )
        raise ReplayRefusedError(message)
```

`start_replay` calls `check_recorded_game(header=sources.header, game_class=game_class)` and its
docstring's `game_class` entry says "its logical name (or, for a recording made before logical
names, its class name and module) must match the recording's". (Check how the existing
"another game of the same name is refused" tests match the message and keep them passing with
this wording, adjusting their `match=` only.)

`glitchygames/scene_start.py`: `SceneStart` gains, after `scene_module`,

```python
    scene: str | None = None
```

(Attributes: "The scene class's logical name (glitchygames/logical_names.py), which a playback's
lookup compares; None in recordings made before logical names."), set at the capture:
`scene=logical_name(scene_class=type(scene))`.

`glitchygames/replay/playback.py` `find_scene_class(*, name, module=None, logical=None)`: when
`logical` is given, the exact matches are the classes named alike whose
`logical_name(scene_class=...) == logical`, and a class is taken by name alone only when
`SCRIPT_MODULE_NAME` is either side's logical module; without it, today's module rule (minus
`PREVIOUS_MODULES`):

```python
    if logical is not None:
        logical_module = logical.partition(':')[0]
        exact_matches = [
            scene_class for scene_class in named_alike if logical_name(scene_class=scene_class) == logical
        ]
        matches_by_name = [
            scene_class
            for scene_class in named_alike
            if SCRIPT_MODULE_NAME in {logical_module, scene_class.__module__}
        ]
    else:
        exact_matches = [
            scene_class for scene_class in named_alike if module is not None and scene_class.__module__ == module
        ]
        matches_by_name = [
            scene_class
            for scene_class in named_alike
            if module is None or SCRIPT_MODULE_NAME in {module, scene_class.__module__}
        ]
```

(the rest unchanged; the docstring says a start's logical name decides when it holds one). The
caller (~1196): `find_scene_class(name=start.scene_class, module=start.scene_module, logical=start.scene)`.

`glitchygames/engine/game_engine.py` header (~1661): after `'game_module'`,
`'game': logical_name(scene_class=type(self.game)),` with the comment "the game's logical name,
which replays compare (glitchygames/logical_names.py): unchanged when the game's code moves".
`glitchygames/instant_replay.py` (~206): the same field when `game is not None`.

`glitchygames/replay/rebaseline.py`: `rebaseline_header(..., game_class: type[Scene])` sets, after
copying OLD's header, `header['game_class'] = game_class.__name__`, `header['game_module'] =
game_class.__module__` and `header[GAME_HEADER_FIELD] = logical_name(scene_class=game_class)`
(docstring: "the game that ran, not OLD's: so a rebaseline converts a recording made before
logical names"); `Rebaseline.__init__` gains `game_class: type[Scene]`, passed on in
`start_recording`; `game_engine.py` (~966) passes `game_class=game`. The existing
`rebaseline_header` test calls (~3901, ~5514, ~5529, ~5791, ~5811) gain `game_class=` the test's
game class.

`glitchygames/recording.py` docstring: the header lists `game` and the scene start lists `scene`.

- [ ] **Step 4: Lint, then run the tests**

Run: `uv run ruff check glitchygames tests && uv run basedpyright glitchygames/logical_names.py glitchygames/replay glitchygames/scene_start.py glitchygames/engine/game_engine.py glitchygames/instant_replay.py tests/test_logical_names.py tests/replay/test_recording_logical_names.py`,
then the Step 2 command, then `uv run pytest --dummy-only tests/world tests/replay tests/scenes tests/test_logical_names.py`.
Expected: PASS, except `tests/replay/test_recording_logical_names.py`, which fails for all six
committed recordings until Task 6 (they hold no `game` and no `scene`; they still replay, by
the old-format rule: the golden replay items pass). Commit this task with
`test_every_logical_name_in_the_recording_resolves` marked
`@pytest.mark.xfail(reason='converted in Task 6', strict=True)`; Task 6 removes the mark.

`git grep -n "PREVIOUS_MODULES\|previous_game_modules" -- ':!plans'`
Expected: no output.

- [ ] **Step 5: Document and commit**

`docs/architecture/gameplay_replay.md` (~253) and CLAUDE.md's replay section (~493, ~508): a
recording names its game (header `game`) and each scene start (`scene`) by logical names
(`glitchygames/logical_names.py`), compared by the header check and the playback's lookup; a
recording without them is compared by its exact module; `PREVIOUS_MODULES` is gone.

This commit changes `glitchygames/` (a measured path): the `replay-metrics` hook measures (~12 s)
and stages rows; `git add` first, never `git commit <path>`.

```bash
git add glitchygames tests docs CLAUDE.md
git commit -m "Recordings name games and scenes by logical names; Scene.PREVIOUS_MODULES removed"
```

---

### Task 6: Convert the six committed recordings to logical names, once

Before anything moves, rebaseline every committed recording on the current code, so each holds
`game` and `scene` (Task 5). This is the one change the recordings get in this part (Global
Constraints); each NEW must replay strictly before it replaces OLD. A rebaseline refuses NEW ==
OLD (and `NEW.partial` == OLD), so NEW is written beside OLD under a temporary name, verified,
then moved over OLD.

**Files:**
- Modify (rebaselined): `tests/fixtures/replays/brave-adventurer/golden.jsonl.gz`,
  `tests/fixtures/replays/brave-adventurer-papyrus/golden.jsonl.gz`,
  `tests/fixtures/replays/clockwork-keep/golden.jsonl.gz`,
  `tests/fixtures/replays/mr-muncher/golden.jsonl.gz`,
  `tests/fixtures/replays/paddleslap/golden.jsonl.gz`,
  `glitchygames/examples/paddleslap_demos/rally.jsonl.gz`
- Modify: `tests/replay/test_recording_logical_names.py` (remove the `xfail` mark)

- [ ] **Step 1: Rebaseline each recording to a temporary name**

```bash
convert() {
  console_script=$1; recording=$2
  converted="${recording%.jsonl.gz}.logical-names.jsonl.gz"
  SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run "$console_script" \
    --replay-trace "$recording" --rebaseline "$converted" --headless
  echo "$console_script $recording -> exit $?"
}
convert brave-adventurer tests/fixtures/replays/brave-adventurer/golden.jsonl.gz
convert brave-adventurer-papyrus tests/fixtures/replays/brave-adventurer-papyrus/golden.jsonl.gz
convert clockwork-keep tests/fixtures/replays/clockwork-keep/golden.jsonl.gz
convert mr-muncher tests/fixtures/replays/mr-muncher/golden.jsonl.gz
convert paddleslap tests/fixtures/replays/paddleslap/golden.jsonl.gz
convert paddleslap glitchygames/examples/paddleslap_demos/rally.jsonl.gz
```

Expected: each prints `Rebaselined N frames to ...logical-names.jsonl.gz: no frames differ`
and exits 0 (`SUCCESS`). Any other summary (frames differ, `recorded input events not
delivered`, exit 7 `REBASELINE_INPUT_LOST`) stops the task: the current code does not reproduce
that recording, which is a bug to report, not to convert over.

- [ ] **Step 2: Replay each NEW strictly and check its names**

```bash
verify() {
  console_script=$1; converted=$2
  SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run "$console_script" --replay-trace "$converted" --headless
  echo "$console_script $converted -> exit $?"
}
verify brave-adventurer tests/fixtures/replays/brave-adventurer/golden.logical-names.jsonl.gz
verify brave-adventurer-papyrus tests/fixtures/replays/brave-adventurer-papyrus/golden.logical-names.jsonl.gz
verify clockwork-keep tests/fixtures/replays/clockwork-keep/golden.logical-names.jsonl.gz
verify mr-muncher tests/fixtures/replays/mr-muncher/golden.logical-names.jsonl.gz
verify paddleslap tests/fixtures/replays/paddleslap/golden.logical-names.jsonl.gz
verify paddleslap glitchygames/examples/paddleslap_demos/rally.logical-names.jsonl.gz
for converted in tests/fixtures/replays/*/golden.logical-names.jsonl.gz glitchygames/examples/paddleslap_demos/rally.logical-names.jsonl.gz; do
  uv run python -c "import sys; from glitchygames.tracing import read_trace; trace = read_trace(path=__import__('pathlib').Path(sys.argv[1])); print(sys.argv[1], trace.get('game'))" "$converted"
done
```

Expected: each replay prints `Replay matched N frames (end of recording)` and exits 0; each
recording prints its game's logical name (`games.brave_adventurer:...`, `games.paddleslap:Game`,
`games.mr_muncher.game:MrMuncherScene` and so on).

- [ ] **Step 3: Replace OLD with NEW**

```bash
for converted in tests/fixtures/replays/*/golden.logical-names.jsonl.gz glitchygames/examples/paddleslap_demos/rally.logical-names.jsonl.gz; do
  mv "$converted" "${converted%.logical-names.jsonl.gz}.jsonl.gz"
done
git status --short tests/fixtures/replays glitchygames/examples/paddleslap_demos
```

Expected: six modified recordings, no untracked file left.

- [ ] **Step 4: The whole replay suite**

Remove the `xfail` mark from `tests/replay/test_recording_logical_names.py`, then run:
`uv run pytest --dummy-only -q tests/replay tests/world/test_golden_traces.py tests/fixtures/replays`
and `uv run python scripts/recording_report.py tests/fixtures/replays/paddleslap/golden.jsonl.gz`.
Expected: PASS: every golden replay item, the bundled demos, the tamper and fixture-set checks
in `tests/replay/test_golden_replays.py`, the resolve check for all six recordings; the report
shows the new run stacked in front (its behaviour-change map names at most the frames holding a
scene start, whose `scene_start` content gained `scene`, as pre-flight C17 foresaw for Mr.
Muncher).

- [ ] **Step 5: Commit**

This commit changes `tests/fixtures/replays` and `glitchygames/` (measured paths): the hook
measures the converted recordings and stages their rows.

```bash
git add tests/fixtures/replays glitchygames/examples/paddleslap_demos tests/replay/test_recording_logical_names.py
git commit -m "The committed recordings are converted once to logical names (rebaselined, each replayed strictly)"
```

---

### Task 7: Move the engine to `src/glitchygames/`

The user's decision 7 (2026-10-25): with `./glitchygames/` at the root, pytest (the root
`conftest.py` puts the root on `sys.path`) imported the source tree, not the installed package,
even under nox's non-editable install. After this task the root holds no importable engine; the
engine's import name, wheel contents and console scripts are unchanged. No member exists yet:
Mr. Muncher moves in Task 9. The six committed recordings were converted to logical names in
Task 6, so moving the engine changes none of them: logical names never mention `src/` (import
paths do not change), and `glitchygames.examples.<game>` modules keep their logical names.

What was checked before writing this task (2026-10-25, read-only, in a scratch project and this
repository's `.venv`):

- hatchling 1.32.4 (`uv build`): `[tool.hatch.build.targets.wheel] packages = ["src/demo_engine"]`
  writes `demo_engine/...` at the wheel's top level (no `src/`), and an `artifacts` entry
  `src/demo_engine/_build_info.json` puts the gitignored stamp into the wheel as
  `demo_engine/_build_info.json`. Its editable install writes a `.pth` holding `<root>/src`
  (today's `_editable_impl_glitchygames.pth` holds the repository root, which is why
  `uv run python scripts/x.py` can import `scripts.*` and `tests.*` today, and cannot after).
- coverage 7.17.0 + pytest-cov 7.1.0 + xdist (`-n 2`), package installed non-editable:
  `source = ["demo_engine"]` (no `./demo_engine/` directory) measures the installed copy,
  unexecuted lines included; with `[tool.coverage.paths] demo_engine = ["src/demo_engine",
  "*/site-packages/demo_engine"]` the report names `src/demo_engine/core.py`, without it
  `.venv-test/lib/python3.14/site-packages/demo_engine/core.py`.
- ruff 0.17.2: `include = ["src/demo_engine/*.py"]` matches nested files; a per-file-ignores key
  `"demo_engine/events/base.py"` stops matching once the file is under `src/` (the key needs the
  `src/` prefix).
- basedpyright 1.40.2: an execution environment that sets `extraPaths` loses pyright's automatic
  `src` search path, so `tests` (`extraPaths: ["."]`) and the engine's environment
  (`extraPaths: ["scripts"]`) cannot resolve `glitchygames` without an installed copy until
  `"src"` is added to their `extraPaths`; with it, 0 errors.
- ty 0.0.91: with `[tool.ty.environment] root = ["."]` the src package is unresolved; with
  `root = ["src", "."]` all checks pass.
- deptry (`deptry .`) guesses first-party modules from the root's direct children only, so
  `glitchygames` under `src/` must be named in `known_first_party`.

**Files:**
- Move: `glitchygames/` -> `src/glitchygames/`
- Modify: `pyproject.toml` (hatch `packages` and `artifacts`, coverage `source` and a new
  `[tool.coverage.paths]`, ruff `src`/`include`/per-file-ignores keys, ty `root`/`include`,
  bandit `exclude_dirs`, deptry `known_first_party`), `pyrightconfig.json`, `wily.cfg`,
  `.gitattributes`, `.gitignore`, `MANIFEST.in`, `bitmappy.spec`, `.pre-commit-config.yaml`,
  `mkdocs.yml`, `noxfile.py` (`_CODE_DIRS`, vulture, bandit)
- Modify (engine): `src/glitchygames/code_tree.py` (`MEASURED_PATHS`),
  `src/glitchygames/recording_metrics.py` (`RECORDING_PATH_RENAMES`, `performance_series`)
- Modify (scripts): `scripts/workspace_packages.py` (`ENGINE_DIRECTORY`),
  `scripts/build_browser_bundle.py` (`PACKAGE_DIRECTORY`), `scripts/replay_metrics.py`
  (`EXAMPLES_PATH`), `scripts/complexity_report.py` (`DIFF_PATHS`, `RANKED_PATH`),
  `scripts/generate_complexity_graphs.py` (`RANKED_PACKAGE`), `scripts/audit_hitboxes.py`
  (`PRIORITY_TIERS`), `scripts/gen_ref_pages.py` (its source root),
  `scripts/measure_staged_replays.py` and `scripts/record_scripted_session.py` (usage lines)
- Modify (tests): `tests/ast_scanning.py`, `tests/test_engine_doors.py` (`PACKAGE`),
  `tests/test_workspace_packages.py`, `tests/test_code_tree.py`,
  `tests/test_measure_staged_replays.py`, `tests/test_generate_performance_graphs.py`,
  `tests/test_complexity_report.py`, `tests/test_generate_complexity_graphs.py`,
  `tests/test_replay_metrics.py`, `tests/test_recording_metrics.py`, `tests/test_build_info.py`,
  `tests/world/test_gameplay_replay.py`, `tests/harness.py`, and the engine-data readers:
  `tests/animation/test_animation_hardware.py`, `tests/animation/test_animation_system_audit.py`,
  `tests/animation/test_animation_timing.py`, `tests/benchmarks/test_benchmarks.py`,
  `tests/game_objects/test_game_objects_sounds.py`, `tests/sprites/test_sprite_animation.py`,
  `tests/sprites/test_animated_sprite.py`, `tests/tools/test_bitmappy_user_files.py`,
  `tests/tools/test_canvas_panning.py`, `tests/events/test_events_font_events.py`,
  `tests/examples/test_examples_sprites.py`
- Modify (docs): `CLAUDE.md`, `README.md`, `docs/quality/performance.md`,
  `docs/quality/complexity.md`
- Test: `tests/test_suite_collection.py` (the root holds no importable engine),
  `tests/test_recording_metrics.py` (a renamed recording is one series)

**Interfaces:**
- Produces: `scripts/workspace_packages.py` `ENGINE_DIRECTORY = Path('src') / ENGINE_PACKAGE`
  (repository-relative); `source_package_directories` returns `project_root / ENGINE_DIRECTORY`
  first; `tests/ast_scanning.py` `scanned_source_files` keys engine files relative to
  `project_root / ENGINE_DIRECTORY` (allowlist keys unchanged: `clock.py`, `debug/overlay.py`)
  and member files relative to the repository (`src/games/space-game/space_game/game.py`);
  `glitchygames.code_tree.MEASURED_PATHS = ('src', 'tests/fixtures/replays', 'uv.lock',
  'pyproject.toml')`; `glitchygames.recording_metrics.RECORDING_PATH_RENAMES: dict[str, str]`
  (old repository path -> new), honoured by `performance_series`; `tests.harness.imported_engine_is_the_checkouts() -> bool`.
- Consumes: `ENGINE_PACKAGE`, `source_package_directories` (Task 3), `scanned_source_files`
  and `write_project_with_member_module` (Task 4), the converted recordings (Task 6).

The rule for paths in prose: comments, docstrings and docs that name an engine file by its
package path (`glitchygames/clock.py`, ~360 in engine code, ~460 lines in docs) stay as they
are: they name the file inside the package, as its import path does. Only paths that are
resolved from the repository root change: code, configuration and commands (`ruff check
glitchygames`, `git add glitchygames`, `Path('glitchygames/...')`). CLAUDE.md says so once
(Step 9).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_suite_collection.py` (add `import importlib.metadata` and `import json`
to its imports):

```python
def test_the_engine_is_imported_from_its_installed_package_never_the_source_tree():
    """The repository root holds no glitchygames/ (src layout, the user's decision 7, 2026-10-25).

    The root conftest.py puts the root on sys.path, so a glitchygames/ there would be imported
    instead of the installed package. nox installs the engine non-editable (site-packages);
    uv sync installs it editable, through a .pth naming src/. Either way the engine imported is
    the one the distribution installed.
    """
    import glitchygames

    project_root = PROJECT_ROOT.resolve()
    assert not (project_root / 'glitchygames').exists(), 'the engine lives in src/glitchygames'
    assert glitchygames.__file__ is not None
    imported_from = Path(glitchygames.__file__).resolve().parent
    distribution = importlib.metadata.distribution('glitchygames')
    direct_url = json.loads(distribution.read_text('direct_url.json') or '{}')
    if direct_url.get('dir_info', {}).get('editable', False):
        assert imported_from == project_root / 'src' / 'glitchygames'
    else:
        assert imported_from == Path(str(distribution.locate_file('glitchygames'))).resolve()
```

In `tests/test_recording_metrics.py`, beside
`test_series_group_order_and_keep_the_latest_measurement_per_commit` (B15's ruling: the series
key and `console_scripts` both use the renamed path, and rows only under the old path still make
a series):

```python
    def test_a_recording_that_moved_keeps_one_series(self):
        """Rows from before a move (old path) and after (new path) are one series, new path."""
        old_path, new_path = next(iter(RECORDING_PATH_RENAMES.items()))
        before = ledger_row(
            commit=OLDER_COMMIT, committed_at='2026-10-22T12:00:00-07:00', recording=old_path
        )
        after = ledger_row(recording=new_path)

        (moved,) = performance_series(rows=[before, after])
        (only_old,) = performance_series(rows=[before])

        assert moved.recording == new_path
        assert [row.recording for row in moved.rows] == [old_path, new_path]
        assert only_old.recording == new_path
```

(import `RECORDING_PATH_RENAMES` from `glitchygames.recording_metrics` beside
`performance_series`; `ledger_row` and `OLDER_COMMIT` are that file's helpers, used by the test
beside it.)

Then the expectations of the layout itself (all `sed -i ''`, macOS; review each diff):

```bash
# Task 3's tests: the engine and the example member live under src/
sed -i '' \
  -e "s#tmp_path / 'glitchygames'#tmp_path / 'src' / 'glitchygames'#g" \
  -e "s#PROJECT_ROOT / 'glitchygames'#PROJECT_ROOT / 'src' / 'glitchygames'#g" \
  -e "s#/ 'games' / 'space-game'#/ 'src' / 'games' / 'space-game'#g" \
  -e 's#"games/space-game"#"src/games/space-game"#g' \
  -e 's#, games/space-game#, src/games/space-game#g' \
  tests/test_workspace_packages.py
```

`tests/test_code_tree.py`: the parametrized measured paths become

```python
    [
        'src/glitchygames/world.py',
        'src/games/mr-muncher/mr_muncher/game.py',
        'src/demos/joystick-demo/joystick_demo/demo.py',
        'src/apps/bitmappy/bitmappy/editor.py',
        'tests/fixtures/replays/paddleslap/golden.jsonl.gz',
        'uv.lock',
        'pyproject.toml',
    ],
```

and its other `relative_path='glitchygames/game.py'` writes (lines ~66, 74, 126, 149, 168)
become `'src/glitchygames/game.py'`:
`sed -i '' "s#relative_path='glitchygames/#relative_path='src/glitchygames/#g" tests/test_code_tree.py tests/test_measure_staged_replays.py`.
In `tests/test_measure_staged_replays.py` also
`(repository / 'glitchygames' / 'new_module.py')` -> `(repository / 'src' / 'glitchygames' / 'new_module.py')`
and the expected `'glitchygames/new_module.py'` -> `'src/glitchygames/new_module.py'` (~144,
149), and the hook check (~171) `'scripts/measure_staged_replays.py' in configuration` ->
`'python -m scripts.measure_staged_replays' in configuration`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_suite_collection.py tests/test_recording_metrics.py tests/test_workspace_packages.py tests/test_code_tree.py tests/test_measure_staged_replays.py`
Expected: FAIL (`the engine lives in src/glitchygames`; `ImportError: cannot import name
'RECORDING_PATH_RENAMES'`; `source_package_directories` returns `glitchygames`, not
`src/glitchygames`; `src/glitchygames/world.py` leaves the code tree unchanged; the hook
configuration still names `scripts/measure_staged_replays.py`).

- [ ] **Step 3: Move the engine**

```bash
git status --short --ignored glitchygames | grep -v '^!! .*__pycache__/$'
mkdir -p src
git mv glitchygames src/glitchygames
rm -rf glitchygames
test ! -e glitchygames && echo "root holds no glitchygames/"
```

The first command lists what `git mv` leaves behind (ignored files only: `.DS_Store` files, the
`glitchygames/scenes/builtin/` leftover of `__pycache__`, any `_build_info.json`); expected:
only `!!` lines. Removing the leftover directory matters: with any `__pycache__` left there,
`./glitchygames/` is an importable namespace package from the root (as B14 found for
Mr. Muncher), the very import this task ends.

- [ ] **Step 4: Packaging and coverage**

`pyproject.toml`:

```toml
[tool.hatch.build]
# The build stamp is gitignored (hatch leaves ignored files out); nox -s build-wheel and
# build-binary write it before building (glitchygames/build_info.py)
artifacts = ["src/glitchygames/_build_info.json"]

[tool.hatch.build.targets.wheel]
# The engine's source is under src/ (the user, 2026-10-25), its wheel holds glitchygames/ at
# the top level as before
packages = ["src/glitchygames"]
```

```toml
[tool.coverage.run]
source = ["glitchygames"]
```

stays as it is (with no `./glitchygames/` directory, coverage reads `glitchygames` as the
package name and measures the imported copy wherever it is installed); add after
`[tool.coverage.run]`:

```toml
[tool.coverage.paths]
# The imported copy (nox: site-packages, not editable; uv sync: src/ itself) is reported as the
# repository's src/glitchygames, so the report and its 100% gate name the files in git
glitchygames = ["src/glitchygames", "*/site-packages/glitchygames"]
```

`.gitattributes`: `glitchygames/_git_archival.txt export-subst` ->
`src/glitchygames/_git_archival.txt export-subst` (its comment unchanged).
`.gitignore` line 206: `glitchygames/_build_info.json` -> `src/glitchygames/_build_info.json`;
the comment at line 194 says `src/glitchygames/examples/resources/sprites/`.
`MANIFEST.in` (a setuptools leftover hatch does not read): `include src/glitchygames/assets/raspberry.toml`.
`bitmappy.spec` `datas`: each source path gains `src/`, destinations unchanged:

```python
        ('src/glitchygames/fonts/bitstream_vera', 'glitchygames/fonts/bitstream_vera'),
        ('src/glitchygames/color/resources', 'glitchygames/color/resources'),
        ('src/glitchygames/assets', 'glitchygames/assets'),
        ('src/glitchygames/bitmappy/resources', 'glitchygames/bitmappy/resources'),
        ('src/glitchygames/examples/resources/sprites', 'glitchygames/examples/resources/sprites'),
```

Reinstall the editable engine so its `.pth` names `src/`:

```bash
uv sync --all-extras --all-groups --reinstall-package glitchygames
cat .venv/lib/python3.14/site-packages/_editable_impl_glitchygames.pth
```

Expected: the `.pth` holds `/Users/.../glitchygames/src`.

- [ ] **Step 5: Lint, type-check and analysis configuration**

`pyproject.toml`:

```toml
[tool.ruff]
...
src = ["src", "tests", "scripts"]
include = [
  "src/glitchygames/*.py",
  "tests/**/*.py",
  "scripts/**/*.py",
  "noxfile.py",
]
```

Every `[tool.ruff.lint.per-file-ignores]` key naming an engine file gains `src/` (lines
228-296: `events/base.py` ... `services/sprite_generation_service.py`, the two
`glitchygames/examples/*.py` keys included); `"tests/**/*.py"` is unchanged:

```bash
sed -i '' -E 's#^"glitchygames/#"src/glitchygames/#' pyproject.toml
grep -n '^"glitchygames/\|^"src/glitchygames/' pyproject.toml
```

Expected: every key printed starts `"src/glitchygames/` (20 keys); none `"glitchygames/`.
`[tool.ruff.lint.isort] known-first-party = ["glitchygames"]` is unchanged (the import name).

```toml
[tool.ty.environment]
python-version = "3.14"
# src/ first: the engine's source package (explicit; ty's automatic src root is not relied on)
root = ["src", "."]
extra-paths = ["scripts"]

[tool.ty.src]
include = ["src/glitchygames", "scripts"]
```

```toml
[tool.bandit]
exclude_dirs = ["tests", "src/glitchygames/tests"]
```

```toml
[tool.deptry]
...
# The engine's own package, under src/ (deptry guesses first-party modules from the root's
# direct children only)
known_first_party = ["glitchygames"]
```

`pyrightconfig.json`: `"include": ["src/glitchygames", "tests", "scripts"]`; the engine's
environment becomes `{"root": "src/glitchygames", "extraPaths": ["src", "scripts"]}` and the
`tests` environment's `"extraPaths": [".", "src"]` (an environment with `extraPaths` loses
pyright's automatic `src` path; checked above). Its other settings are unchanged.

`wily.cfg`: `path = src/glitchygames,tests,scripts`.

`noxfile.py`: `_CODE_DIRS = ['noxfile.py', 'src/glitchygames', 'scripts', 'tests']`; the vulture
run `session.run('vulture', 'src/glitchygames', 'vulture_whitelist.py', '--min-confidence=80')`;
`_bandit_scan`'s `'-r', 'glitchygames'` -> `'-r', 'src/glitchygames'`. The
`'--reinstall-package', 'glitchygames'` in `_install_from_lockfile` is the distribution name:
unchanged.

`mkdocs.yml` mkdocstrings: `paths: [src]` (griffe finds `glitchygames` under `src/`; checked with
griffe's `load(..., search_paths=[<scratch>/src])`).

CircleCI (`.circleci/config.yml`) was checked: it names no engine path (its only
`.../glitchygames/...` path is the pygame-ce submodule's own
`third_party/pygame-ce/buildconfig/glitchygames/build_pyodide_wheel.sh`): unchanged. There is no
`.github/` directory.

- [ ] **Step 6: Engine and script paths resolved from the repository root**

`src/glitchygames/code_tree.py`:

```python
# What can change how the golden replays run: the only paths a code tree holds. src/ holds the
# engine and every workspace member (games, demos, apps: plans/2026-10-24-workspace-packages.md)
MEASURED_PATHS = (
    'src',
    'tests/fixtures/replays',
    'uv.lock',
    'pyproject.toml',
)
```

and its module docstring's "(the engine, games, demos, apps, recordings, ...)" becomes "(`src/`:
the engine, games, demos and apps; the recordings, the locked dependencies and the project
configuration)".

`src/glitchygames/recording_metrics.py`, beside the ledger's constants:

```python
# Recordings that moved, old repository path -> new: their ledger rows from before the move are
# the same series (performance_series groups by the new path), so history continues across a
# move (plans/2026-10-24-workspace-packages.md)
RECORDING_PATH_RENAMES: dict[str, str] = {
    'glitchygames/examples/paddleslap_demos/rally.jsonl.gz': (
        'src/glitchygames/examples/paddleslap_demos/rally.jsonl.gz'
    ),
}
```

and in `performance_series`, compute the path once and use it for the series key and
`console_scripts` (B15):

```python
    for row in sorted(rows, key=_row_order):
        if row.commit is None or row.summary is None:
            continue
        # A moved recording's rows from before the move join its series under the new path
        recording = RECORDING_PATH_RENAMES.get(row.recording, row.recording)
        series_key = (recording, row.machine, row.run.processing_paced)
        # Sorted by measurement within a commit, so the latest measurement of a commit wins
        grouped.setdefault(series_key, {})[row.commit] = row
        console_scripts[recording] = row.console_script
```

(the docstring gains: "A recording that moved (``RECORDING_PATH_RENAMES``) is one series under
its new path.")

`scripts/workspace_packages.py`:

```python
ENGINE_PACKAGE = 'glitchygames'
# Where the engine's source package is, relative to the repository: under src/, so nothing run
# from the repository root imports the source tree by accident (the user, 2026-10-25)
ENGINE_DIRECTORY = Path('src') / ENGINE_PACKAGE
```

`source_package_directories`: `directories = [project_root / ENGINE_DIRECTORY]`. The
`WorkspaceMember` docstring examples say `src/games/mr-muncher`.

`tests/ast_scanning.py`: import `ENGINE_DIRECTORY` instead of `ENGINE_PACKAGE`;
`scanned_source_files` uses `engine_directory = project_root / ENGINE_DIRECTORY` and its
docstring says "relative to ``src/glitchygames/``" and gives the member example
`src/games/mr-muncher/mr_muncher/game.py`; `write_project_with_member_module` writes the new
layout:

```python
    (project_root / ENGINE_DIRECTORY).mkdir(parents=True)
    (project_root / 'pyproject.toml').write_text(
        '[tool.uv.workspace]\nmembers = ["src/games/space-game"]\n', encoding='utf-8'
    )
    member_directory = project_root / 'src' / 'games' / 'space-game'
    ...
    return 'src/games/space-game/space_game/game.py'
```

(its docstring: "an empty ``src/glitchygames/`` and the member ``src/games/space-game``"). The
engine allowlist keys in `tests/test_engine_doors.py` and `tests/test_randomness.py` stay exactly
as they are.

`tests/test_engine_doors.py`: `PACKAGE = PROJECT_ROOT / ENGINE_DIRECTORY` (import
`ENGINE_DIRECTORY` from `scripts.workspace_packages`): it reads engine source files to scan them,
so it reads the repository's.

Scripts:
- `scripts/build_browser_bundle.py`: `PACKAGE_DIRECTORY = REPOSITORY_DIRECTORY / 'src' / 'glitchygames'`
  (the archive's names stay `glitchygames/...`: they are relative to the package directory's
  parent). It runs as a file (`python scripts/build_browser_bundle.py`), so it spells the path
  rather than importing `scripts.workspace_packages`.
- `scripts/replay_metrics.py`: `EXAMPLES_PATH = Path('src') / 'glitchygames' / 'examples'`
  (the bundled demo is now measured as `src/glitchygames/examples/paddleslap_demos/rally.jsonl.gz`,
  which `RECORDING_PATH_RENAMES` joins to its history).
- `scripts/complexity_report.py`: `DIFF_PATHS = ('src/glitchygames', 'scripts')`,
  `RANKED_PATH = 'src/glitchygames'`.
- `scripts/generate_complexity_graphs.py`: `RANKED_PACKAGE = 'src/glitchygames'`.
- `scripts/audit_hitboxes.py` `PRIORITY_TIERS`: `PROJECT_ROOT / 'glitchygames'` ->
  `PROJECT_ROOT / 'src' / 'glitchygames'` (three entries).
- `scripts/gen_ref_pages.py`: `src = Path(Path(__file__).parent.parent) / 'src'` (module paths
  are then relative to `src/`, as they were to the root; it is not wired into `mkdocs.yml`).
- `scripts/write_build_stamp.py`: unchanged (it writes into `glitchygames.build_info.PACKAGE_DIRECTORY`,
  the imported engine; `uv run` imports the editable one, `src/glitchygames/`, which the
  `artifacts` entry above names).

Scripts that import `scripts.*` must run as modules from the root now (the editable `.pth`
names `src/`, not the root): `scripts/complexity_report.py`, `scripts/driver_configurations.py`
and `scripts/driver_frame_matrix.py` already do (noxfile `-m`); change the two that do not:
- `.pre-commit-config.yaml` hook `replay-metrics`: `entry: uv run python -m scripts.measure_staged_replays`,
  and the usage line in `scripts/measure_staged_replays.py`'s docstring the same.
- `scripts/record_scripted_session.py` docstring commands: `uv run python -m scripts.record_scripted_session ...`.

`git grep -n "python scripts/" -- ':!plans' ':!quality'` lists every other file invocation;
expected: none of them names one of the five scripts above.

- [ ] **Step 7: Tests that build a path to the engine from the repository root**

Tests reading engine data files (sprites, fonts, sounds) read them from the imported engine, the
copy the code under test loads: each file gets

```python
import glitchygames

# The imported engine's directory (installed: never the source tree by accident)
ENGINE_PACKAGE_DIRECTORY = Path(glitchygames.__file__).resolve().parent
```

and `Path(__file__).parent.parent.parent / 'glitchygames'` (or `.parents[2] / 'glitchygames'`,
or `Path('glitchygames/...')`) becomes `ENGINE_PACKAGE_DIRECTORY / ...`:
- `tests/animation/test_animation_hardware.py` (~41), `tests/animation/test_animation_system_audit.py` (~32),
  `tests/animation/test_animation_timing.py` (~28), `tests/benchmarks/test_benchmarks.py` (~30),
  `tests/sprites/test_sprite_animation.py` (~27): the `examples/resources/sprites` fixture paths
- `tests/game_objects/test_game_objects_sounds.py` (~37): `game_objects/snd_files`
- `tests/events/test_events_font_events.py` (~30): `fonts/bitstream_vera/Vera.ttf`
- `tests/sprites/test_animated_sprite.py` (~2801 `examples/foo2.toml`, ~3160 the papyrus player)
- `tests/tools/test_bitmappy_user_files.py` (~12), `tests/tools/test_canvas_panning.py` (~70)
- `tests/examples/test_examples_sprites.py` (~59, ~300-301, ~557, ~572): `BUNDLED_SPRITE_FILES`
  keeps its test ids relative, `ids=lambda path: path.relative_to(ENGINE_PACKAGE_DIRECTORY).as_posix()`
  instead of `ids=str` (an absolute site-packages path would differ between nox and `uv run`)

Tests building a synthetic repository in `tmp_path` follow the layout:
- `tests/test_generate_performance_graphs.py`: `clone_with_measured_rows` writes
  `clone / 'src' / 'glitchygames' / 'world.py'` and adds `'src/glitchygames/world.py'` (~295-298);
  `DEMO = 'src/glitchygames/examples/paddleslap_demos/rally.jsonl.gz'` (~50).
- `tests/test_generate_complexity_graphs.py`: `FIXTURE_WILY_CONFIGURATION` `path = src/glitchygames`;
  `fixture_repository` writes `package = repository / 'src' / 'glitchygames'`; the fixture
  repository's expected names gain `src/` (~281 `checkout / 'src' / 'glitchygames' / 'branchy.py'`,
  ~299 `src_glitchygames_old_module_py_raw_loc.html`, ~314-315 `"src\\u002fglitchygames\\u002f..."`,
  ~322). The `rank_modules` tests (~123-161) pass literal dictionaries and do not read the
  layout: unchanged.
- `tests/test_complexity_report.py` (~51, 57, 64, 75, 84): `repository / 'src' / 'glitchygames' / 'simple.py'`,
  expected `src/glitchygames/simple.py`, `src/glitchygames/branchy\.py`.
- `tests/test_replay_metrics.py` (~159, ~480): the demo is `'src/glitchygames/examples/paddleslap_demos/rally.jsonl.gz'`.
- `tests/test_recording_metrics.py` (~520, ~527): the `other_recording` row's path becomes
  `'src/glitchygames/examples/paddleslap_demos/rally.jsonl.gz'` (the old path would now be
  renamed into it).

Tests that assumed the imported engine is this checkout's (true today only because the root was
on `sys.path`; under nox after the move it is a built copy, whose revision is `unknown`, as the
noxfile's `_replay_metrics` docstring already says):
- `tests/test_build_info.py` `test_this_engine_running_from_its_checkout_names_head`: ask the
  checkout explicitly, `revision = source_revision(package_directory=CHECKOUT_ENGINE_DIRECTORY)`
  and `repository = CHECKOUT_ENGINE_DIRECTORY`, with
  `CHECKOUT_ENGINE_DIRECTORY = Path(__file__).resolve().parent.parent / 'src' / 'glitchygames'`.
- `tests/world/test_gameplay_replay.py` (~5328-5330): keep
  `run.source_revision == engine_source_revision()`; the source check becomes
  `assert run.source_revision.source is (RevisionSource.GIT_CHECKOUT if imported_engine_is_the_checkouts() else RevisionSource.UNKNOWN)`.
- `tests/test_replay_metrics.py` `clean_revision()` (~47-57, used by most of its tests):
  `source_revision(package_directory=CHECKOUT_ENGINE_DIRECTORY)` (same constant), since
  `replay_metrics measure` refuses an unknown commit. Its tests that compare that revision with
  what a child rebaseline recorded (children run `sys.executable`'s console script, so under nox
  the built copy, `unknown`) compare with `imported_engine_is_the_checkouts()` deciding the
  expected source, as below; the nox run in this step shows which.
- `tests/harness.py` gains the helper these use:

```python
def imported_engine_is_the_checkouts() -> bool:
    """Whether the imported glitchygames is this checkout's src/glitchygames.

    True under ``uv sync`` (an editable install, its .pth naming src/), False under nox (a built,
    non-editable copy in the session's site-packages, which cannot name its commit).

    Returns:
        Whether the engine imported is the checkout's own source.

    """
    import glitchygames

    checkout_engine = Path(__file__).resolve().parent.parent / 'src' / 'glitchygames'
    return glitchygames.__file__ is not None and Path(glitchygames.__file__).resolve().is_relative_to(
        checkout_engine
    )
```

Run `CI=true uv run --extra dev nox -s test` after Step 8's lint (Step 10 runs it again) to find
any other test that assumed the source tree was imported; fix each the same way (ask the
checkout explicitly where the test means the checkout; compare with what the imported engine
reports where it means a run) and list them in the task report.

Checked and unchanged: `tests/test_build_browser_bundle.py` (~54: a synthetic package passed as
`package_directory`), `tests/test_build_info.py` (~142: a fake site-packages), the SDL cache
paths in `tests/test_build_sdl_x11.py` and `tests/test_driver_configurations.py`
(`~/Library/Caches/glitchygames`), `tests/test_logging.py:13` (inserts `tests/glitchygames`, a
directory that has never existed: dead, not an engine path; reported in the task report, not
changed here).

Confirm nothing else builds a root-relative engine path:

```bash
git grep -nE "(PROJECT_ROOT|REPOSITORY_DIRECTORY|ROOT|root|repository|clone|parents?\[[0-9]\]|parent)\s*/\s*'glitchygames'|Path\('glitchygames" -- tests scripts noxfile.py conftest.py
git grep -n -B2 "^\s*/ 'glitchygames'" -- tests scripts
```

Expected: no output from either (the multi-line form is what the second catches).

- [ ] **Step 8: Lint and types**

Run: `uv run ruff format src/glitchygames tests scripts noxfile.py && uv run ruff check src/glitchygames tests scripts noxfile.py`,
`uv run basedpyright`, `uv run ty check`, `uv run --extra dev nox -s lint-dependencies lint-dead-code bandit-scan`.
Expected: PASS, with the same counts of checked files as before the move (`uv run ruff check --show-files | wc -l`
before and after: equal).

- [ ] **Step 9: Docs**

- CLAUDE.md: the Project Overview gains one paragraph: "The engine's source is
  `src/glitchygames/` (members: `src/games/`, `src/demos/`, `src/apps/`;
  plans/2026-10-24-workspace-packages.md). Nothing at the repository root is importable as our
  package: tests and tools import the installed engine (`uv sync`: editable, its `.pth` naming
  `src/`; nox: not editable). Paths like `glitchygames/clock.py` in this file, the docs and
  comments name the file inside the package (`src/glitchygames/clock.py` in the repository). A
  script that imports `scripts.*` runs as `uv run python -m scripts.<name>` from the root."
  Linting and Type Checking: `ruff format src tests scripts noxfile.py`, `ruff check --select I
  --fix src tests scripts noxfile.py`, `ruff check src tests scripts noxfile.py`. The run-ledger
  paragraph's `uv run python scripts/measure_staged_replays.py` ->
  `uv run python -m scripts.measure_staged_replays`, and its `MEASURED_PATHS` list ->
  "`src/` (the engine, games, demos, apps), recordings, `uv.lock`, `pyproject.toml`".
- README.md (~332-338): the same three ruff commands with `src`.
- `docs/quality/performance.md` (~41): `uv run python -m scripts.measure_staged_replays`.
- `docs/quality/complexity.md`: one sentence: wily follows files by path, so the engine's
  module graphs begin at the move to `src/glitchygames/` (2026-10-25).

- [ ] **Step 10: Verify everything**

Run, in order:
1. `uv run pytest` (both drivers, outside CI): PASS at 100% coverage, the report naming
   `src/glitchygames/...` files; every golden replay item (`tests/fixtures/replays/*/golden`)
   passes; `tests/world/test_golden_traces.py` and `tests/replay/test_bundled_demos.py` pass;
   the native run shows no driver differences.
2. `CI=true uv run --extra dev nox -s test`: PASS at 100% coverage with the engine imported from
   the nox venv's site-packages (the new `test_suite_collection` test's non-editable branch),
   the report naming `src/glitchygames/...` (the `[tool.coverage.paths]` mapping).
3. `uv run --extra dev nox -s lint static-analysis`: PASS.
4. `uv run --extra dev nox -s build-wheel`, then
   `unzip -l dist/glitchygames-*.whl | awk '{print $4}' | grep -c '^src/'` and
   `unzip -l dist/glitchygames-*.whl | grep -E ' glitchygames/(__init__\.py|_git_archival\.txt|_build_info\.json)$'`:
   0, then all three names (the wheel holds `glitchygames/` at its top level, with the stamp).
5. `uv run --extra dev nox -s build-binary`: PASS (the spec's data paths).
6. `uv run --extra dev nox -s lint-docs`: PASS (`mkdocs build --strict`, the API pages found
   under `src/`).

- [ ] **Step 11: Commit**

This commit changes the code tree (everything under `src/`), so the `replay-metrics` hook
measures every golden replay and the demo (~12 s) and stages new `quality/replay-ledger/` rows:
the golden replays under their unchanged paths, the demo under its new path (file names ending
`-src-glitchygames-examples-paddleslap-demos-rally.json`), which `RECORDING_PATH_RENAMES` joins
to its old rows (`...-glitchygames-examples-paddleslap-demos-rally.json`, kept). The hook runs
`python -m scripts.measure_staged_replays` (Step 6), refuses untracked files under `src/`
(`git status --short src` must show nothing untracked) and a partial commit, so stage first and
never `git commit <path>`:

```bash
git add -A src glitchygames pyproject.toml pyrightconfig.json wily.cfg .gitattributes .gitignore MANIFEST.in bitmappy.spec .pre-commit-config.yaml mkdocs.yml noxfile.py scripts tests CLAUDE.md README.md docs
git status --short | grep -v '^[MADRC] ' ; echo "(nothing unstaged above)"
git commit -m "The engine moves to src/glitchygames: nothing at the repository root imports as the engine"
```

Expected: the hook prints that it measured 6 recordings and staged their rows; the commit holds
the move (renames), the configuration, the rows. Note the rows in the task report.

---

### Task 8: Every tool's configuration names every member

**Files:**
- Create: `tests/test_workspace_config.py`
- Modify: `scripts/workspace_packages.py` (`WorkspaceMember.layer`, members validated to live
  in `src/<layer>/`), `tests/test_workspace_packages.py`
- Modify (in Task 9, with the member): `pyproject.toml` (coverage, pytest, ruff, ty, deptry),
  `pyrightconfig.json`, `wily.cfg`, `noxfile.py` (`_CODE_DIRS`, `_SOURCE_PACKAGE_DIRS`,
  `_install_from_lockfile`)

**Interfaces:**
- Consumes: `workspace_members` (Task 3), Task 7's layout (`src/`, `[tool.coverage.paths]`,
  the `src` search paths), `MEMBER_LAYERS` (Task 5).
- Produces: a check that fails when a member is missing from: coverage `source` and `paths`,
  pytest `addopts` `--cov=`, `testpaths`, ruff `src`/`include`/`known-first-party` and the
  member tests' per-file-ignores, ty `include` and `root`, `pyrightconfig.json` `include` and
  the member's two execution environments, deptry, `wily.cfg` `path`, nox `_CODE_DIRS` and the
  vulture/bandit targets (`_SOURCE_PACKAGE_DIRS`), and when the root `[project.scripts]` still
  holds a member's script (the pre-flight's A7), and when the engine's `MEMBER_LAYERS`
  (Task 5) differs from the workspace (each member's `layer`, a new `WorkspaceMember`
  property: its directory's parent under `src/`).

- [ ] **Step 1: Write the failing test** (`tests/test_workspace_config.py`)

```python
"""Every tool covers every workspace member: a new game cannot slip out of lint, types or coverage."""

from __future__ import annotations

import configparser
import json
import tomllib
from pathlib import Path
from typing import Any

import pytest

import noxfile
from scripts.workspace_packages import WorkspaceMember, workspace_members

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMBERS = workspace_members(project_root=PROJECT_ROOT)


def root_pyproject() -> dict[str, Any]:
    with (PROJECT_ROOT / 'pyproject.toml').open('rb') as pyproject_file:
        return tomllib.load(pyproject_file)


def pyright_configuration() -> dict[str, Any]:
    return json.loads((PROJECT_ROOT / 'pyrightconfig.json').read_text(encoding='utf-8'))


def repository_path(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def member_name(member: WorkspaceMember) -> str:
    return member.distribution


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_coverage_measures_every_member_package(member):
    pyproject = root_pyproject()
    sources = pyproject['tool']['coverage']['run']['source']
    paths = pyproject['tool']['coverage']['paths']
    addopts = pyproject['tool']['pytest']['ini_options']['addopts'].split()

    for package, package_directory in zip(
        member.import_packages, member.package_directories, strict=True
    ):
        assert package in sources
        assert f'--cov={package}' in addopts
        # The installed copy is reported as the member's source under src/ (Task 7's mapping)
        assert paths[package] == [repository_path(package_directory), f'*/site-packages/{package}']


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_pytest_collects_every_members_tests(member):
    testpaths = root_pyproject()['tool']['pytest']['ini_options']['testpaths']

    assert repository_path(member.tests_directory) in testpaths


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_lint_and_type_checks_cover_every_member(member):
    pyproject = root_pyproject()
    member_path = repository_path(member.directory)
    pyright = pyright_configuration()

    assert member_path in pyproject['tool']['ruff']['src']
    assert f'{member_path}/**/*.py' in pyproject['tool']['ruff']['include']
    assert set(member.import_packages) <= set(
        pyproject['tool']['ruff']['lint']['isort']['known-first-party']
    )
    assert member_path in pyproject['tool']['ty']['src']['include']
    assert member_path in pyproject['tool']['ty']['environment']['root']
    assert member_path in pyright['include']
    assert member_path in noxfile._CODE_DIRS


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_member_tests_get_the_tests_relaxations(member):
    """A member's tests lint and type-check like tests/ (pre-flight C9, C10)."""
    per_file_ignores = root_pyproject()['tool']['ruff']['lint']['per-file-ignores']
    # src/games/*/tests/**/*.py: one glob per layer (games, demos, apps)
    layer = repository_path(member.directory.parent)
    assert per_file_ignores[f'{layer}/*/tests/**/*.py'] == per_file_ignores['tests/**/*.py']

    environments = pyright_configuration()['executionEnvironments']
    roots = [environment['root'] for environment in environments]
    tests_path = repository_path(member.tests_directory)
    member_path = repository_path(member.directory)
    # The member's tests environment comes before the member's own (pyright takes the first match)
    assert roots.index(tests_path) < roots.index(member_path)
    member_tests = {key: value for key, value in environments[roots.index(tests_path)].items() if key != 'root'}
    engine_tests = {key: value for key, value in environments[roots.index('tests')].items() if key != 'root'}
    assert member_tests == engine_tests
    assert member_path in engine_tests['extraPaths']
    assert 'src' in environments[roots.index(member_path)]['extraPaths']


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_dependency_dead_code_security_and_complexity_scans_cover_every_member(member):
    """deptry, vulture, bandit and wily (pre-flight A7, C11)."""
    pyproject = root_pyproject()
    deptry = pyproject['tool']['deptry']
    wily = configparser.ConfigParser()
    wily.read(PROJECT_ROOT / 'wily.cfg', encoding='utf-8')

    assert set(member.import_packages) <= set(deptry['known_first_party'])
    # Members are projects of their own: the root's dependency check leaves their layer out
    assert repository_path(member.directory.parent) in deptry['extend_exclude']
    for package_directory in member.package_directories:
        assert repository_path(package_directory) in noxfile._SOURCE_PACKAGE_DIRS
    assert repository_path(member.directory) in wily['wily']['path'].split(',')


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_a_members_console_scripts_are_its_own(member):
    """The root project no longer declares a script a member does (pre-flight A7)."""
    root_scripts = root_pyproject()['project']['scripts']

    assert not set(member.console_scripts) & set(root_scripts)


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_the_engine_knows_every_members_layer(member):
    """Recordings name a member's classes by its layer (glitchygames/logical_names.py)."""
    for package in member.import_packages:
        assert logical_names.MEMBER_LAYERS[package] == member.layer


def test_the_engine_knows_no_layer_the_workspace_lacks():
    """Not parametrized: it holds with no members too ({} == {})."""
    workspace_packages = {package for member in MEMBERS for package in member.import_packages}

    assert set(logical_names.MEMBER_LAYERS) == workspace_packages
```

(add `from glitchygames import logical_names` to its imports.)

`scripts/workspace_packages.py`: `WorkspaceMember` gains

```python
    @property
    def layer(self: Self) -> str:
        """The workspace layer it belongs to: its directory's parent under src/ (``games``)."""
        return self.directory.parent.name
```

and `workspace_members` refuses a member outside `src/<layer>/` (after the pyproject check):

```python
        if directory.parent.parent != project_root / 'src' or directory.parent.name not in LAYERS:
            message = (
                f'Workspace member {member_path} is not in src/<layer>/ '
                f'(layers: {", ".join(LAYERS)})'
            )
            raise ValueError(message)
```

(`from glitchygames.logical_names import LAYERS`: scripts may import the engine; the `Raises`
section names it.) `tests/test_workspace_packages.py` gains:

```python
def test_a_member_knows_its_layer(tmp_path):
    write_workspace(tmp_path)

    (member,) = workspace_members(project_root=tmp_path)

    assert member.layer == 'games'


def test_a_member_outside_a_layer_is_refused(tmp_path):
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.uv.workspace]\nmembers = ["space-game"]\n', encoding='utf-8'
    )
    (tmp_path / 'space-game' / 'space_game').mkdir(parents=True)
    (tmp_path / 'space-game' / 'pyproject.toml').write_text(MEMBER_PYPROJECT, encoding='utf-8')

    with pytest.raises(ValueError, match='src/<layer>/'):
        workspace_members(project_root=tmp_path)
```

(these run now: the two are not parametrized over the real members.)

(The key paths were checked against today's `pyproject.toml`: ty's `include` is under
`[tool.ty.src]` and its `root` under `[tool.ty.environment]` (Task 7 adds it),
`known-first-party` under `[tool.ruff.lint.isort]`, `known_first_party` and `extend_exclude`
under `[tool.deptry]` (Task 7 adds the former). If one differs when this task runs, adjust the
lookup to the file, not the file to the test.)

- [ ] **Step 2: Run it**

Run: `uv run pytest --dummy-only --no-cov -q -rs tests/test_workspace_config.py`
Expected: every test SKIPPED (`got empty parameter set`): there are no members yet. Task 9 adds
the first member, so these tests run there: they fail until Step 3's configuration changes are
made, which land with the member in one commit.

- [ ] **Step 3: Configuration changes (applied in Task 9, listed here)**

- `pyproject.toml`: `[tool.coverage.run] source = ["glitchygames", "mr_muncher"]`;
  `[tool.coverage.paths]` gains `mr_muncher = ["src/games/mr-muncher/mr_muncher",
  "*/site-packages/mr_muncher"]`; addopts `--cov=glitchygames --cov=mr_muncher`;
  `testpaths = ["tests", "src/games/mr-muncher/tests"]`; ruff `src` and `include` gain
  `"src/games/mr-muncher"` and `"src/games/mr-muncher/**/*.py"`; per-file-ignores gain
  `"src/games/*/tests/**/*.py"` with the `"tests/**/*.py"` list (C9); isort
  `known-first-party = ["glitchygames", "mr_muncher"]`; ty `include` and
  `[tool.ty.environment] root` gain `"src/games/mr-muncher"` (`root = ["src", ".",
  "src/games/mr-muncher"]`); deptry `known_first_party = ["glitchygames", "mr_muncher"]` and
  `extend_exclude` gains `"src/games"` (C11).
- `pyrightconfig.json` `include` gains `"src/games/mr-muncher"`; `executionEnvironments` gain,
  after `tests` and in this order, `{"root": "src/games/mr-muncher/tests", ...}` (a copy of the
  `tests` block apart from `root`, C10) and `{"root": "src/games/mr-muncher", "extraPaths":
  ["src"]}`; both tests blocks' `extraPaths` become `[".", "src", "src/games/mr-muncher"]` (so
  `tests/` and the member's tests resolve `mr_muncher` without an installed copy, as Task 7
  found pyright needs).
- `wily.cfg` `path = src/glitchygames,src/games/mr-muncher,tests,scripts`.
- `noxfile.py`: `_CODE_DIRS` gains `'src/games/mr-muncher'`; a new
  `_SOURCE_PACKAGE_DIRS = ['src/glitchygames', 'src/games/mr-muncher/mr_muncher']` (the
  packages vulture and bandit scan; one list) replaces the literal `'src/glitchygames'` in the
  vulture run and bandit's `-r` (`session.run('vulture', *_SOURCE_PACKAGE_DIRS,
  'vulture_whitelist.py', '--min-confidence=80')`; bandit `'-r', *_SOURCE_PACKAGE_DIRS`);
  `_install_from_lockfile` adds `'--all-packages'` and `--reinstall-package <distribution>` for
  every member (C3); `_LINUX_X11_SYNC` gains `--all-packages` (C5). `.envrc`, CLAUDE.md and
  README `uv sync` commands gain `--all-packages` (C4).

- [ ] **Step 4: Commit the check alone**

```bash
git add tests/test_workspace_config.py scripts/workspace_packages.py tests/test_workspace_packages.py
git commit -m "tests/test_workspace_config.py: every tool's configuration must name every member"
```

---

### Task 9: Move Mr. Muncher into `src/games/mr-muncher/`

Mr. Muncher's logical name is `games.mr_muncher.game:...` before and after the move (Task 5:
`EXAMPLES_LAYERS['mr_muncher']` before, `MEMBER_LAYERS['mr_muncher']` after), so its recordings
need nothing: no previous modules, no remap. Its golden replay file still moves into the member,
and `RECORDING_PATH_RENAMES` (Task 7) keeps its performance history connected.

Where recordings live (the user's decision 9, 2026-10-25): a member's golden replays live with
its tests, directly in `<member>/tests/fixtures/replays/` (`golden.jsonl.gz`: no
`<console-script>/` folder, the member names the game), and the golden plugin collects them
across members, so the engine's suite still runs every one; a member's bundled demos ship in its
import package (`<package>/demos/<name>.jsonl.gz`, Part 2 for PaddleSlap's); the engine's root
`tests/fixtures/replays/` keeps only recordings of its own (and, until Part 2 moves them, the
four other games' goldens in `<console-script>/` folders).

**Files:**
- Move: `src/glitchygames/examples/mr_muncher/` -> `src/games/mr-muncher/mr_muncher/`
- Move: `tests/examples/test_mr_muncher.py`, `tests/examples/test_mr_muncher_maze_and_actors.py`
  -> `src/games/mr-muncher/tests/`
- Move: `tests/fixtures/replays/mr-muncher/golden.jsonl.gz` ->
  `src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz` (bytes unchanged)
- Create: `src/games/mr-muncher/pyproject.toml`, `src/games/mr-muncher/README.md` (one paragraph:
  what it is, how to run and test it)
- Modify: `src/glitchygames/testing/replays.py` (`recording_console_script`, `ReplayFile`,
  `ReplayItem`), root `pyproject.toml` (workspace, scripts, Task 8's tool configs), `uv.lock`,
  `pyrightconfig.json`, `wily.cfg`, `noxfile.py`, `.envrc`, `src/glitchygames/logical_names.py`
  (`mr_muncher` from `EXAMPLES_LAYERS` to `MEMBER_LAYERS`), `scripts/record_golden_traces.py`,
  `scripts/record_scripted_session.py`, `tests/replay/test_golden_replays.py`,
  `scripts/replay_metrics.py`, `src/glitchygames/recording_metrics.py`,
  `tests/test_replay_metrics.py`, `tests/test_generate_performance_graphs.py`,
  `tests/test_logical_names.py`, `tests/engine/test_engine_lifecycle.py`, `tests/test_ci_config.py`
- Test: `src/games/mr-muncher/tests/test_logical_names_after_the_move.py`,
  `tests/test_workspace_config.py`, `tests/test_workspace_packages.py`, the golden replay item,
  `tests/replay/test_recording_logical_names.py`

**Interfaces:**
- Consumes: `logical_name`, `MEMBER_LAYERS` (Task 5), `WorkspaceMember` (Task 3),
  `RECORDING_PATH_RENAMES` and the `src/` layout (Task 7), Task 8's checks.
- Produces: `mr_muncher` importable; console script `mr-muncher = "mr_muncher:main"`;
  `GAME_MODULES: dict[str, str]` in `scripts/record_golden_traces.py` (game key -> the module
  holding its `main`: `'mr_muncher': 'mr_muncher'`, the others `glitchygames.examples.<key>`);
  `REPLAY_FIXTURE_DIRECTORIES: dict[str, Path]` (game key -> its fixtures root);
  `MEMBER_LAYERS == {'mr_muncher': 'games'}`;
  `glitchygames.testing.replays.recording_console_script(*, path: Path) -> str` (the console
  script that replays a recording in either fixtures layout).

- [ ] **Step 1: Write the failing tests**

`src/games/mr-muncher/tests/test_logical_names_after_the_move.py` (create the directory; no
`__init__.py`):

```python
"""Mr. Muncher moved from glitchygames/examples/mr_muncher: its logical names did not change."""

from __future__ import annotations

import inspect

import mr_muncher.game
from glitchygames.logical_names import logical_name
from glitchygames.scenes import Scene


def test_every_scene_keeps_the_logical_name_its_recordings_hold():
    """Recordings made before the move name games.mr_muncher.game:<scene>; so does the moved code."""
    scenes = [
        scene_class
        for _name, scene_class in inspect.getmembers(mr_muncher.game, inspect.isclass)
        if issubclass(scene_class, Scene) and scene_class.__module__ == mr_muncher.game.__name__
    ]

    assert scenes, 'mr_muncher.game defines its scenes'
    for scene_class in scenes:
        assert logical_name(scene_class=scene_class) == (
            f'games.mr_muncher.game:{scene_class.__qualname__}'
        )
```

Append to `tests/test_suite_collection.py`:

```python
def test_every_member_packages_tests_are_collected(pytestconfig):
    """A member's tests directory is in testpaths and its test files are importable by name."""
    from scripts.workspace_packages import workspace_members

    testpaths = pytestconfig.getini('testpaths')
    for member in workspace_members(project_root=PROJECT_ROOT):
        relative = member.tests_directory.relative_to(PROJECT_ROOT).as_posix()
        assert relative in testpaths, f'{relative} is not collected'
        assert not (member.tests_directory / '__init__.py').exists(), (
            f'{relative} must not be a package named "tests" (it would shadow tests/)'
        )


def test_test_file_names_are_unique_across_packages():
    """Member tests are not packages, so pytest imports them by file name: names must differ."""
    from scripts.workspace_packages import workspace_members

    roots = [TESTS_ROOT] + [
        member.tests_directory for member in workspace_members(project_root=PROJECT_ROOT)
    ]
    names = [path.name for root in roots for path in root.rglob('test_*.py')]

    assert len(names) == len(set(names))
```

Append to `tests/test_workspace_packages.py`:

```python
def test_this_repositorys_members_are_read():
    """The real workspace (members grow part by part)."""
    distributions = [member.distribution for member in workspace_members(project_root=PROJECT_ROOT)]

    assert 'mr-muncher' in distributions
```

In `tests/replay/test_golden_replays.py`:

```python
def test_a_members_golden_replay_is_replayed_by_the_members_console_script():
    """<member>/tests/fixtures/replays/<name>.jsonl.gz: the member distribution names the game."""
    (member,) = [
        member for member in workspace_members(project_root=PROJECT_ROOT) if member.distribution == 'mr-muncher'
    ]
    golden = member.replay_fixtures_directory / 'golden.jsonl.gz'

    assert recording_console_script(path=golden) == 'mr-muncher'
    assert recording_console_script(
        path=PROJECT_ROOT / 'tests' / 'fixtures' / 'replays' / 'paddleslap' / 'golden.jsonl.gz'
    ) == 'paddleslap'


def test_a_recording_of_a_folder_that_is_no_member_is_refused(tmp_path):
    """A distribution that is not installed (or has several console scripts) names no game."""
    misplaced = tmp_path / 'not-a-member' / 'tests' / 'fixtures' / 'replays' / 'golden.jsonl.gz'

    with pytest.raises(KeyError, match='not-a-member'):
        recording_console_script(path=misplaced)
```

(imports: `recording_console_script` from `glitchygames.testing.replays`, `workspace_members`
from `scripts.workspace_packages`; `PROJECT_ROOT` is the repository root, defined beside
`REPLAY_FIXTURE_DIRECTORY` if the file has none.)

`tests/test_logical_names.py` `test_every_example_game_and_demo_has_a_layer`: the expected table
loses `'mr_muncher': 'games'`, and a new assertion `assert logical_names.MEMBER_LAYERS ==
{'mr_muncher': 'games'}`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_suite_collection.py tests/test_workspace_packages.py tests/test_workspace_config.py tests/test_logical_names.py`
Expected: FAIL (no member `mr-muncher`; `src/games/mr-muncher/tests` not collected; the
configuration checks still skipped; `MEMBER_LAYERS` empty).

- [ ] **Step 3: Move and wire the member**

```bash
mkdir -p src/games/mr-muncher/tests/fixtures/replays
git mv src/glitchygames/examples/mr_muncher src/games/mr-muncher/mr_muncher
rm -rf src/glitchygames/examples/mr_muncher
git mv tests/examples/test_mr_muncher.py tests/examples/test_mr_muncher_maze_and_actors.py src/games/mr-muncher/tests/
git mv tests/fixtures/replays/mr-muncher/golden.jsonl.gz src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz
git grep -l "glitchygames\.examples\.mr_muncher\|glitchygames\.examples import mr_muncher" -- ':!plans' | xargs sed -i '' \
  -e 's/glitchygames\.examples\.mr_muncher/mr_muncher/g' \
  -e 's/from glitchygames\.examples import mr_muncher/import mr_muncher/g'
```

(`rm -rf` removes the ignored `__pycache__` the move leaves, which would otherwise keep an
importable namespace directory: pre-flight B14. The `':!plans'` keeps the sed out of the plans:
B11.) Then review the sed's diff by hand (`git diff`): it must touch only imports and module
names, never a recording. It reaches one test case on purpose:
`tests/test_logical_names.py`'s `('glitchygames.examples.mr_muncher.game', 'games.mr_muncher.game')`
becomes `('mr_muncher.game', 'games.mr_muncher.game')`, which is right after the move (the
member's module, through `MEMBER_LAYERS`); keep it.

`src/glitchygames/testing/replays.py`: one function decides which console script replays a
recording, for both layouts, and `ReplayFile.collect` (the location check and the item name)
and `ReplayItem` (~335, which today reads `self.path.parent.name`) use it:

```python
def recording_console_script(*, path: Path) -> str:
    """Return the console script that replays a recording under a ``fixtures/replays/`` directory.

    Two layouts: a workspace member's recordings lie directly in
    ``<member>/tests/fixtures/replays/`` and are replayed by the member distribution's one console
    script (the member's directory is named after its distribution: ``src/games/mr-muncher``);
    the engine's own (and the games not yet moved) lie in
    ``tests/fixtures/replays/<console-script>/``, whose folder names the script.

    Args:
        path: The recording.

    Returns:
        The console script's name.

    Raises:
        KeyError: If the member's distribution is not installed or has not exactly one console
            script, or the folder names no installed console script.

    """
    if path.parent.parts[-len(REPLAY_FIXTURES_PATH_PARTS) :] == REPLAY_FIXTURES_PATH_PARTS:
        distribution_name = path.parent.parent.parent.parent.name
        try:
            distribution = importlib.metadata.distribution(distribution_name)
        except importlib.metadata.PackageNotFoundError:
            message = f'{path}: {distribution_name!r} is not an installed workspace member'
            raise KeyError(message) from None
        console_scripts = [
            entry_point.name
            for entry_point in distribution.entry_points
            if entry_point.group == CONSOLE_SCRIPTS_GROUP
        ]
        if len(console_scripts) != 1:
            message = f'{path}: {distribution_name!r} has {len(console_scripts)} console scripts, not one'
            raise KeyError(message)
        return console_scripts[0]
    game_entry_point(console_script=path.parent.name)
    return path.parent.name
```

`ReplayFile.collect` accepts a recording whose parent, or whose parent's parent, ends in
`fixtures/replays`, names the item `f'{recording_console_script(path=self.path)}/{name}'`, and
turns the `KeyError` into its `CollectError` (the message gives both layouts:
`REPLAY_FIXTURES_LAYOUT` gains the member form `<member>/tests/fixtures/replays/<name>.jsonl.gz`).
Every other place that reads a golden's console script from its folder uses the function:
`git grep -n "parent.name" -- tests/replay scripts/replay_metrics.py scripts/record_scripted_session.py src/glitchygames/testing/replays.py`
lists them (`tests/replay/test_golden_replays.py`'s
`test_every_fixture_directory_is_a_game_console_script` and the controls check that maps
recordings to games, `scripts/replay_metrics.py` `metric_recordings`); expected after the change:
no `parent.name` left that means a console script. `WorkspaceMember.replay_fixtures_directory`'s
docstring says "its golden replays, ``<name>.jsonl.gz`` directly in it".

`src/glitchygames/logical_names.py`: delete `'mr_muncher': 'games'` from `EXAMPLES_LAYERS` and
set `MEMBER_LAYERS: dict[str, str] = {'mr_muncher': 'games'}`.

`src/games/mr-muncher/pyproject.toml`:

```toml
[project]
name = "mr-muncher"
version = "1.0.0"
description = "Mr. Muncher: a maze chase at the movies, built on GlitchyGames"
requires-python = ">=3.14,<4.0"
dependencies = ["glitchygames"]

[project.scripts]
mr-muncher = "mr_muncher:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["mr_muncher"]

[tool.uv.sources]
glitchygames = { workspace = true }
```

(`requires-python` copied from the root: B13; match the root's `[build-system]` exactly.)

Root `pyproject.toml`: the sed turned the `mr-muncher` line of `[project.scripts]` into
`mr-muncher = "mr_muncher:main"`: delete it (B11); add

```toml
[tool.uv.workspace]
# Each a package of its own beside the engine, under src/<layer>/
# (plans/2026-10-24-workspace-packages.md); listed one by one, never by glob
members = ["src/games/mr-muncher"]
```

and Task 8's configuration changes (Task 8 Step 3, with pre-flight C9-C12). Then:

```bash
uv lock
uv sync --all-extras --all-groups --all-packages
```

`.envrc` gains `--all-packages` in its `uv sync` and its upgrade comment (C4).
`noxfile.py` `_LINUX_X11_SYNC` gains `--all-packages` (C5), and `_install_from_lockfile` the
member reinstall (C3), with `tests/test_ci_config.py::test_nox_sessions_always_reinstall_the_project`
extended to the member. `tests/engine/test_engine_lifecycle.py::test_every_game_console_script_is_covered`
compares `GAME_CONSOLE_SCRIPTS` with the root scripts plus every member's `console_scripts`
(C6; `git grep -n "\['scripts'\]"` for any other reader of the root scripts table).

`scripts/record_golden_traces.py`: imports `from mr_muncher...`; add

```python
# Game key -> the module holding its main() (where its console script's entry point is):
# a game moved into its own package names its package (plans/2026-10-24-workspace-packages.md)
GAME_MODULES: dict[str, str] = {
    'clockwork_keep': 'glitchygames.examples.clockwork_keep',
    'brave_adventurer': 'glitchygames.examples.brave_adventurer',
    'brave_adventurer_papyrus': 'glitchygames.examples.brave_adventurer_papyrus',
    'paddleslap': 'glitchygames.examples.paddleslap',
    'mr_muncher': 'mr_muncher',
}
```

`scripts/record_scripted_session.py`: `CONSOLE_SCRIPT_GAME_KEYS` uses
`console_script_in_module(module=GAME_MODULES[game_key])`; `fixture_path` returns
`<the game's fixtures directory>/<name>.jsonl.gz` for a member game (no console-script folder)
and `REPLAY_FIXTURE_DIRECTORY / <console-script> / <name>.jsonl.gz` for the others:
`REPLAY_FIXTURE_DIRECTORIES = {'mr_muncher': <the member's replay_fixtures_directory>}`, read from
`workspace_members(project_root=PROJECT_ROOT)` (it runs as `python -m
scripts.record_scripted_session`, Task 7, so it may import `scripts.workspace_packages`); a game
key not in it uses the root layout.
`tests/replay/test_golden_replays.py` `REPLAY_FIXTURES`: glob
`tests/fixtures/replays/*/*.jsonl.gz` plus every member's `replay_fixtures_directory.glob('*.jsonl.gz')`.
`scripts/replay_metrics.py`: `GOLDEN_REPLAYS_GLOB` becomes a list of globs (the engine's and
each member's), read via `workspace_members`; because it now imports `scripts.workspace_packages`,
it runs as a module: noxfile `_replay_metrics` runs `'python', '-m', 'scripts.replay_metrics'`
(and its docstring, CLAUDE.md and `docs/quality/performance.md` say `python -m
scripts.replay_metrics`). `tests/test_replay_metrics.py` (~160-163) expects
`src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz` (C14).

`src/glitchygames/recording_metrics.py` `RECORDING_PATH_RENAMES` gains (one line per moved
recording)

```python
    'tests/fixtures/replays/mr-muncher/golden.jsonl.gz': (
        'src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz'
    ),
```

(`performance_series` already groups by it: Task 7.)

Remove the `::: glitchygames.examples.mr_muncher.game` block (the sed made it
`::: mr_muncher.game`) from `docs/glitchygames/examples/index.md` (Task 11 adds the game's own
API section).

- [ ] **Step 4: Lint, then run everything that names the game**

Run: `uv run --extra dev nox -s format-code lint-code lint-dependencies`, `uv run basedpyright`,
`uv run --extra dev nox -s static-analysis-ty` (C12: if ty reads the member's tests, add
`src/games/*/tests` to its `exclude`), then
`uv run pytest --dummy-only -q src/games/mr-muncher/tests tests/test_suite_collection.py tests/test_workspace_config.py tests/test_workspace_packages.py tests/test_logical_names.py tests/replay tests/test_replay_metrics.py tests/test_generate_performance_graphs.py`.
Expected: PASS, including the golden replay item `mr-muncher/golden` collected from
`src/games/mr-muncher/tests/fixtures/replays/` replaying the unchanged recording (its `game` is
`games.mr_muncher.game:MrMuncherScene`, which the moved class still names), and the resolve
check for it.

- [ ] **Step 5: Commit**

The code tree changes (everything under `src/`): the hook measures (~12 s) and stages rows,
Mr. Muncher's under its new path (`...-src-games-mr-muncher-tests-fixtures-replays-golden.json`;
the old rows stay, joined by `RECORDING_PATH_RENAMES`). It refuses untracked files under `src/`
and a partial commit (C2), so `uv sync --all-extras --all-groups --all-packages` first (the hook
runs `mr-muncher` from `.venv`), stage every new member file, and never `git commit <path>`.
Frame 1's `scene_start.scene_module` now records `mr_muncher.game`, so that run's content hash
differs at the frame holding the scene start (C17): confirm with `uv run python
scripts/recording_report.py src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz`
after the hook ran and note it in the task report.

```bash
git add -A src pyproject.toml uv.lock pyrightconfig.json wily.cfg noxfile.py .envrc scripts tests docs CLAUDE.md README.md
git status --short src | grep '^??' ; echo "(no untracked file under src above)"
git commit -m "Mr. Muncher is its own package: src/games/mr-muncher (distribution mr-muncher, import mr_muncher)"
```

---

### Task 10: The browser build ships the game's own package

**Files:**
- Modify: `scripts/build_browser_bundle.py` (`GameSpecification`, `GAMES`, `pyscript_config`,
  `write_bundle`: by name, pre-flight B17), `noxfile.py` (its two runs of the script)
- Test: `tests/test_build_browser_bundle.py`

**Interfaces:**
- Produces: `GameSpecification.member_package: str | None = None` (the member's import package,
  e.g. `'mr_muncher'`); a bundle for such a game holds `<member_package>.zip` (the package's
  files, `write_engine_archive`'s format without dist-info) and `pyscript.toml` lists it in
  `[files]` beside `glitchygames.zip`. Part 5 (the browser IDE) reads this archive.

- [ ] **Step 1: Write the failing tests** (in `tests/test_build_browser_bundle.py`)

```python
def test_a_member_games_package_is_its_own_archive():
    """Mr. Muncher's bundle ships mr_muncher.zip beside the engine's archive."""
    config = pyscript_config(wheel_name='pygame_ce.whl', member_package='mr_muncher')

    assert '"./glitchygames.zip" = "./*"' in config
    assert '"./mr_muncher.zip" = "./*"' in config


def test_the_engine_archive_no_longer_holds_the_moved_game():
    """The moved game's code is not under src/glitchygames/ any more."""
    files = bundled_package_files(package_directory=PACKAGE_DIRECTORY)

    assert not any(path.parts[:2] == ('examples', 'mr_muncher') for path in files)
```

(B16: no `tmp_path`; import `PACKAGE_DIRECTORY`, which Task 7 points at `src/glitchygames`.)
Plus a `write_bundle` test (follow the boot_config bundle test) asserting the written bundle
directory contains `mr_muncher.zip` holding `mr_muncher/game.py`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_build_browser_bundle.py -k "member or moved"`
Expected: FAIL (`unexpected keyword argument 'member_package'`).

- [ ] **Step 3: Implement**

`GameSpecification` gains `member_package: str | None = None` (documented). `GAMES['mr-muncher']`
gains `member_package='mr_muncher'` only (its `module` is already `mr_muncher.game` from Task
9's sed: A8). `pyscript_config(*, wheel_name, member_package: str | None = None)` adds
`f'"./{member_package}.zip" = "./*"\n'` after the engine archive line when given.
`write_bundle` writes the member archive with
`write_engine_archive(package_directory=<member's package directory>, archive_path=output_directory / f'{member_package}.zip', excluded_subpackages=frozenset())`,
finding the member's directory with `workspace_members` (so the script imports
`scripts.workspace_packages` and runs as a module: noxfile's two runs become
`session.run('python', '-m', 'scripts.build_browser_bundle', ...)`, and CLAUDE.md, the mkdocs
hook's comments and `docs/` say `python -m scripts.build_browser_bundle`). `browser/boot.py`
needs no change: the archive unpacks `mr_muncher/` beside `glitchygames/` and
`importlib.import_module('mr_muncher.game')` finds it. A browser recording names Mr. Muncher by
`games.mr_muncher.game:...` too: `MEMBER_LAYERS` is engine data, so it needs no metadata the
bundle lacks.

- [ ] **Step 4: Run the tests, then build the real bundle**

Run: the Step 2 command, then `uv run --extra dev nox -s browser -- mr-muncher` and open the
served page (the session prints its address); the game must start.
Expected: PASS; Mr. Muncher runs in the browser from `mr_muncher.zip`.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_browser_bundle.py noxfile.py tests/test_build_browser_bundle.py CLAUDE.md docs scripts/mkdocs_hooks.py
git commit -m "Browser bundles ship a member game's package as its own archive"
```

---

### Task 11: Docs

**Files:**
- Modify: `docs/games/mr_muncher.md` (its file table and paths), `mkdocs.yml` (mkdocstrings
  `paths: [src, src/games/mr-muncher]`), `docs/glitchygames/examples/index.md`,
  `README.md` (Example Games; the `uv sync` commands), `CLAUDE.md` (Development Setup, Example
  Games, the replay and testing sections), `plans/future-features.md` (a feature entry linking
  the master plan), `plans/2026-10-24-workspace-packages.md` (Part 1 status)

- [ ] **Step 1: Write the docs**

- `docs/games/mr_muncher.md`: every `glitchygames/examples/mr_muncher/...` path becomes
  `src/games/mr-muncher/mr_muncher/...`; add a short "Its package" section (the member layout,
  how to run `uv run mr-muncher` and its tests `uv run pytest src/games/mr-muncher/tests`) and an
  "API reference" section with `::: mr_muncher.game`.
- CLAUDE.md: Development Setup gains `--all-packages`; "Example Games" says Mr. Muncher is
  `src/games/mr-muncher/` and links the master plan; the replay section documents logical
  names (`glitchygames/logical_names.py`: header `game`, scene start `scene`, `MEMBER_LAYERS`
  kept equal to the workspace) and where recordings live (a member's goldens in
  `<member>/tests/fixtures/replays/<name>.jsonl.gz`, replayed by its console script,
  `recording_console_script`; its demos in `<package>/demos/`; root `tests/fixtures/replays/`
  for the engine's own); Testing Guidelines say the harness is `tests/harness.py`,
  loaded for every package.

- [ ] **Step 2: Build strictly**

Run: `uv run --extra dev nox -s lint-docs`
Expected: PASS (`mkdocs build --strict`).

- [ ] **Step 3: Commit**

```bash
git add docs mkdocs.yml README.md CLAUDE.md plans
git commit -m "Docs: Mr. Muncher's own package, logical names, the src/ layout, the harness plugin"
```

---

### Task 12: Whole-branch verification

- [ ] **Step 1: Lint and types**

Run: `uv run --extra dev nox -s lint static-analysis`
Expected: PASS.

- [ ] **Step 2: The suite as CI runs it, and locally on both drivers**

Run: `CI=true uv run --extra dev nox -s test`, then `uv run pytest`.
Expected: PASS at 100% coverage; the coverage report lists `src/glitchygames/...` and
`src/games/mr-muncher/mr_muncher/...` files (the installed copies mapped back); the native run
shows no driver differences; `mr-muncher/golden` is collected from the member; every committed
recording's logical names resolve.

- [ ] **Step 3: Wheels**

Run: `uv run --extra dev nox -s build-wheel` and `uv build --package mr-muncher --wheel --out-dir dist`;
list both wheels (`unzip -l`).
Expected: the engine wheel has `glitchygames/` at its top level, no `src/`, no `mr_muncher`
files and no `examples/mr_muncher`; the `mr_muncher` wheel has `mr_muncher/` at its top level
and the `mr-muncher` console script.

- [ ] **Step 4: Docs with the browser games**

Run: `uv run --extra dev nox -s docs-deploy -- --build-only`, then check
`site/play/mr-muncher/` exists and holds `mr_muncher.zip`.
Expected: PASS (it also measures and builds every browser bundle: B19, expect the time).

- [ ] **Step 5: Record and hand off**

Update the master plan's Part 1 status (done, with the commit range), write any finding into
BUGS.md, and stop for the user's review before pushing or opening the PR.
