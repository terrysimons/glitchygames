# Workspace Packages, Part 1: Foundation and the Mr. Muncher Pilot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repository a uv workspace whose members can be games, with every engine guard,
tool and harness covering members, and prove it by moving Mr. Muncher to `games/mr-muncher/`.

**Architecture:** The root project stays the engine (`glitchygames`). `[tool.uv.workspace]`
lists members explicitly; each member has its own `pyproject.toml`, import package and `tests/`.
A small reader, `scripts/workspace_packages.py`, is the one place that knows the members; guards,
config checks, the browser build and the replay metrics ask it. Recordings keep replaying through
`Scene.PREVIOUS_MODULES`. The tests' shared harness becomes a plugin the root `conftest.py` loads,
so a member's tests get it.

**Tech Stack:** Python 3.14, uv workspaces (`uv sync --all-packages`), hatchling, pytest +
pytest-cov + xdist, pygame-ce 2.5.8, PyScript/Pyodide browser bundles, mkdocs + mkdocstrings.

**Spec:** [2026-10-24-workspace-packages.md](2026-10-24-workspace-packages.md) (the master plan:
layout, the user's decisions 1-6, what every part keeps true).

## Global Constraints

- Branch from the latest `main` (`5a243b96` or later: it has the browser builds, #97).
- Names: directory and distribution `mr-muncher`, import package `mr_muncher`, console script
  `mr-muncher` (unchanged).
- Workspace members are listed explicitly (`members = ["games/mr-muncher"]`), never by glob.
- The committed recordings are never edited or re-recorded in this part.
- Coverage stays at 100% (`--cov-fail-under=100`) over the engine and every member.
- No `# noqa`, no type-ignore additions, no lint configuration loosened to make a check pass;
  configuration only grows to include members.
- pytest-mock (`mocker`) only; keyword arguments; full names; new data classes are frozen
  pydantic models (`ConfigDict(frozen=True, extra='forbid')`).
- Lint (`ruff`, `basedpyright`, `ty`) before tests; run the failing test before the fix.
- Every commit ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`;
  never push without the user's go-ahead.

## Review Focus

1. **A member's tests silently not running**: a test directory pytest never collects (testpaths,
   a basename clash with `tests/`) passes CI by running nothing. Task 6 adds a collection check
   that each member's test files are collected.
2. **A member outside a guard**: a raw clock read or `random.random()` in `mr_muncher/` must fail
   the doors and randomness guards exactly as in `glitchygames/`. Task 4 tests that the guards'
   roots include the member and that a planted bypass in a member path is reported.
3. **A recording of the old module refused**: the golden replay and any old recording of
   `glitchygames.examples.mr_muncher.game` must replay; a recording naming a *different* old
   module must still be refused. Task 2 tests both.
4. **The installed copy, not the source**: nox installs non-editable; coverage and the replay
   plugin must see the installed `mr_muncher` (console script found, coverage mapped). Task 9
   runs the real `nox -s test` and `nox -s build-wheel`.
5. **The browser bundle missing the game**: the engine archive covers only `glitchygames/`; the
   bundle must ship `mr_muncher` too, and the engine wheel must no longer contain it. Tasks 7
   and 9 check both.

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` (root) | workspace members; no `mr-muncher` script; tool configs include members |
| `games/mr-muncher/pyproject.toml` | the member: name, dependency on `glitchygames`, script, wheel packages |
| `games/mr-muncher/mr_muncher/` | the game (moved from `glitchygames/examples/mr_muncher/`) |
| `games/mr-muncher/tests/` | its tests (moved from `tests/examples/test_mr_muncher*.py`) and golden replay |
| `scripts/workspace_packages.py` | reads the workspace: members, their import packages, test and fixture directories |
| `tests/harness.py` | the shared test harness (was `tests/conftest.py`), loaded as a plugin by the root `conftest.py` |
| `glitchygames/scenes/scene.py` | `Scene.PREVIOUS_MODULES` |
| `glitchygames/replay/driver.py`, `glitchygames/replay/playback.py`, `glitchygames/engine/game_engine.py` | accept a recording naming a previous module |
| `tests/test_workspace_config.py` | every tool's configuration names every member |
| `noxfile.py` | installs every member (`--all-packages`), lints and formats member paths |
| `scripts/build_browser_bundle.py` | ships a game's member package as its own archive |
| `glitchygames/recording_metrics.py` | `RECORDING_PATH_RENAMES`: a moved recording keeps its history |

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

### Task 5: Every tool's configuration names every member

**Files:**
- Create: `tests/test_workspace_config.py`
- Modify: `pyproject.toml` (coverage, pytest, ruff, ty), `pyrightconfig.json`, `wily.cfg`,
  `noxfile.py` (`_CODE_DIRS`, `_install_from_lockfile`, vulture and bandit targets)

**Interfaces:**
- Consumes: `workspace_members` (Task 3).
- Produces: a check that fails when a member is missing from: coverage `source`, pytest
  `addopts` `--cov=`, `testpaths`, ruff `src`/`include`/`known-first-party`, ty `include`,
  `pyrightconfig.json` `include`, `wily.cfg` `path`, nox `_CODE_DIRS`, vulture and bandit paths.

- [ ] **Step 1: Write the failing test** (`tests/test_workspace_config.py`)

```python
"""Every tool covers every workspace member: a new game cannot slip out of lint, types or coverage."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

import noxfile
from scripts.workspace_packages import workspace_members

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMBERS = workspace_members(project_root=PROJECT_ROOT)


def root_pyproject() -> dict:
    with (PROJECT_ROOT / 'pyproject.toml').open('rb') as pyproject_file:
        return tomllib.load(pyproject_file)


@pytest.mark.parametrize('member', MEMBERS, ids=lambda member: member.distribution)
def test_coverage_measures_every_member_package(member):
    pyproject = root_pyproject()
    sources = pyproject['tool']['coverage']['run']['source']
    addopts = pyproject['tool']['pytest']['ini_options']['addopts'].split()

    for package in member.import_packages:
        assert package in sources
        assert f'--cov={package}' in addopts


@pytest.mark.parametrize('member', MEMBERS, ids=lambda member: member.distribution)
def test_pytest_collects_every_members_tests(member):
    testpaths = root_pyproject()['tool']['pytest']['ini_options']['testpaths']

    assert member.tests_directory.relative_to(PROJECT_ROOT).as_posix() in testpaths


@pytest.mark.parametrize('member', MEMBERS, ids=lambda member: member.distribution)
def test_lint_and_type_checks_cover_every_member(member):
    pyproject = root_pyproject()
    member_path = member.directory.relative_to(PROJECT_ROOT).as_posix()
    pyright = json.loads((PROJECT_ROOT / 'pyrightconfig.json').read_text(encoding='utf-8'))

    assert member_path in pyproject['tool']['ruff']['src']
    assert f'{member_path}/**/*.py' in pyproject['tool']['ruff']['include']
    assert set(member.import_packages) <= set(
        pyproject['tool']['ruff']['lint']['isort']['known-first-party']
    )
    assert member_path in pyproject['tool']['ty']['src']['include']
    assert member_path in pyright['include']
    assert member_path in noxfile._CODE_DIRS
```

(Check the exact key paths in `pyproject.toml` before writing: ty's `include` may live under
`[tool.ty.src]` or `[tool.ty.environment]`, `known-first-party` under
`[tool.ruff.lint.isort]`; adjust the lookups to the file, not the file to the test. Add the
`wily.cfg` and nox vulture/bandit checks in the same style.)

- [ ] **Step 2: Run it**

Run: `uv run pytest --dummy-only --no-cov -q -rs tests/test_workspace_config.py`
Expected: every test SKIPPED (`got empty parameter set`): there are no members yet. Task 6 adds
the first member, so these tests run there: they fail until Step 3's configuration changes are
made, which land with the member in one commit.

- [ ] **Step 3: Configuration changes (applied in Task 6, listed here)**

- `pyproject.toml`: `[tool.coverage.run] source = ["glitchygames", "mr_muncher"]`; addopts
  `--cov=glitchygames --cov=mr_muncher`; `testpaths = ["tests", "games/mr-muncher/tests"]`;
  ruff `src` and `include` gain `"games/mr-muncher"` and `"games/mr-muncher/**/*.py"`;
  isort `known-first-party = ["glitchygames", "mr_muncher"]`; ty `include` gains
  `"games/mr-muncher"`.
- `pyrightconfig.json` `include` gains `"games/mr-muncher"` (and an executionEnvironment for it
  with `extraPaths: ["."]`, like `tests`, so its tests can import `tests.*` and `scripts.*`).
- `wily.cfg` `path` gains `games/mr-muncher`.
- `noxfile.py`: `_CODE_DIRS` gains `'games/mr-muncher'`; `_install_from_lockfile` adds
  `'--all-packages'` to `uv sync`; vulture and bandit runs gain the member's package directory.
  `.envrc`, CLAUDE.md and README `uv sync` commands gain `--all-packages`.

- [ ] **Step 4: Commit the check alone**

```bash
git add tests/test_workspace_config.py
git commit -m "tests/test_workspace_config.py: every tool's configuration must name every member"
```

---

### Task 6: Move Mr. Muncher into `games/mr-muncher/`

**Files:**
- Move: `glitchygames/examples/mr_muncher/` -> `games/mr-muncher/mr_muncher/`
- Move: `tests/examples/test_mr_muncher.py`, `tests/examples/test_mr_muncher_maze_and_actors.py`
  -> `games/mr-muncher/tests/`
- Move: `tests/fixtures/replays/mr-muncher/golden.jsonl.gz` ->
  `games/mr-muncher/tests/fixtures/replays/mr-muncher/golden.jsonl.gz`
- Create: `games/mr-muncher/pyproject.toml`, `games/mr-muncher/README.md` (one paragraph: what
  it is, how to run and test it)
- Modify: root `pyproject.toml` (workspace, scripts, Task 5's tool configs), `uv.lock`,
  `scripts/record_golden_traces.py`, `scripts/record_scripted_session.py`,
  `tests/replay/test_golden_replays.py`, `scripts/replay_metrics.py`,
  `glitchygames/recording_metrics.py`, `tests/test_replay_metrics.py`,
  `tests/test_generate_performance_graphs.py`
- Test: `games/mr-muncher/tests/test_previous_modules.py`, `tests/test_workspace_config.py`,
  `tests/test_workspace_packages.py`, the golden replay item

**Interfaces:**
- Consumes: `PREVIOUS_MODULES` (Task 2), `WorkspaceMember` (Task 3), Task 5's checks.
- Produces: `mr_muncher` importable; console script `mr-muncher = "mr_muncher:main"`;
  `GAME_MODULES: dict[str, str]` in `scripts/record_golden_traces.py` (game key -> the module
  holding its `main`: `'mr_muncher': 'mr_muncher'`, the others `glitchygames.examples.<key>`);
  `REPLAY_FIXTURE_DIRECTORIES: dict[str, Path]` (game key -> its fixtures root);
  `RECORDING_PATH_RENAMES: dict[str, str]` in `glitchygames/recording_metrics.py`.

- [ ] **Step 1: Write the failing tests**

`games/mr-muncher/tests/test_previous_modules.py` (create the directory; no `__init__.py`):

```python
"""Mr. Muncher moved from glitchygames/examples/mr_muncher: its scenes name where they lived."""

from __future__ import annotations

import inspect

import mr_muncher.game
from glitchygames.scenes import Scene

OLD_PACKAGE = 'glitchygames.examples.mr_muncher'


def test_every_scene_names_the_module_it_was_moved_from():
    """Recordings made before the move name the old modules; each scene accepts its own."""
    scenes = [
        scene_class
        for _name, scene_class in inspect.getmembers(mr_muncher.game, inspect.isclass)
        if issubclass(scene_class, Scene) and scene_class.__module__ == mr_muncher.game.__name__
    ]

    assert scenes, 'mr_muncher.game defines its scenes'
    for scene_class in scenes:
        assert scene_class.PREVIOUS_MODULES == frozenset({f'{OLD_PACKAGE}.game'})
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

(`PROJECT_ROOT`/`TESTS_ROOT`: use the names that file already defines.) Append to
`tests/test_workspace_packages.py`:

```python
def test_this_repositorys_members_are_read():
    """The real workspace (members grow part by part)."""
    distributions = [member.distribution for member in workspace_members(project_root=PROJECT_ROOT)]

    assert 'mr-muncher' in distributions
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_suite_collection.py tests/test_workspace_packages.py tests/test_workspace_config.py`
Expected: FAIL (no member `mr-muncher`; `games/mr-muncher/tests` not collected; the
configuration checks still skipped).

- [ ] **Step 3: Move and wire the member**

```bash
mkdir -p games/mr-muncher/tests/fixtures/replays/mr-muncher
git mv glitchygames/examples/mr_muncher games/mr-muncher/mr_muncher
git mv tests/examples/test_mr_muncher.py tests/examples/test_mr_muncher_maze_and_actors.py games/mr-muncher/tests/
git mv tests/fixtures/replays/mr-muncher/golden.jsonl.gz games/mr-muncher/tests/fixtures/replays/mr-muncher/golden.jsonl.gz
git grep -l "glitchygames\.examples\.mr_muncher\|glitchygames\.examples import mr_muncher" | xargs sed -i '' \
  -e 's/glitchygames\.examples\.mr_muncher/mr_muncher/g' \
  -e 's/from glitchygames\.examples import mr_muncher/import mr_muncher/g'
```

Then review the sed's diff by hand (`git diff`): it must touch only imports and module names,
never a recording or `PREVIOUS_MODULES` value. Write `PREVIOUS_MODULES` after the sed:

```python
class MrMuncherScene(Scene):
    ...
    # Where it lived before games became their own packages (glitchygames/examples/mr_muncher)
    PREVIOUS_MODULES = frozenset({'glitchygames.examples.mr_muncher.game'})
```

and the same on `MrMuncherGameOverScene`.

`games/mr-muncher/pyproject.toml`:

```toml
[project]
name = "mr-muncher"
version = "1.0.0"
description = "Mr. Muncher: a maze chase at the movies, built on GlitchyGames"
requires-python = ">=3.14"
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

(Match the root's `[build-system]` pin, version style and `requires-python` exactly; copy them.)

Root `pyproject.toml`: remove the `mr-muncher` line from `[project.scripts]`; add

```toml
[tool.uv.workspace]
# Each a package of its own beside the engine (plans/2026-10-24-workspace-packages.md);
# listed one by one, never by glob
members = ["games/mr-muncher"]
```

and Task 5's configuration changes. Then `uv lock` and `uv sync --all-extras --all-groups --all-packages`.

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
`console_script_in_module(module=GAME_MODULES[game_key])`; `fixture_path` uses the game's
fixtures root: `REPLAY_FIXTURE_DIRECTORIES = {key: REPLAY_FIXTURE_DIRECTORY for key in
GAME_MODULES} | {'mr_muncher': PROJECT_ROOT / 'games' / 'mr-muncher' / 'tests' / 'fixtures' /
'replays'}` (derive the member's from `workspace_members` instead of spelling the path, if it
reads cleanly). `tests/replay/test_golden_replays.py` `REPLAY_FIXTURES`: glob
`tests/fixtures/replays/*/*.jsonl.gz` plus every member's `replay_fixtures_directory`.
`scripts/replay_metrics.py`: `GOLDEN_REPLAYS_GLOB` becomes a list of globs (the engine's and
each member's), read via `workspace_members`.

`glitchygames/recording_metrics.py`:

```python
# Recordings that moved, old repository path -> new: their ledger rows before the move are the
# same series (performance_series groups by the new path), so history continues across a move
RECORDING_PATH_RENAMES: dict[str, str] = {
    'tests/fixtures/replays/mr-muncher/golden.jsonl.gz': (
        'games/mr-muncher/tests/fixtures/replays/mr-muncher/golden.jsonl.gz'
    ),
}
```

and in `performance_series`, group by `RECORDING_PATH_RENAMES.get(row.recording, row.recording)`.
Test it in `tests/test_generate_performance_graphs.py` or the recording-metrics tests: two rows,
one under the old path and one under the new, make one series.

Remove the `::: glitchygames.examples.mr_muncher.game` block from
`docs/glitchygames/examples/index.md` (Task 8 adds the game's own API section).

- [ ] **Step 4: Lint, then run everything that names the game**

Run: `uv run --extra dev nox -s format-code lint-code`, `uv run basedpyright`, then
`uv run pytest --dummy-only -q games/mr-muncher/tests tests/test_suite_collection.py tests/test_workspace_config.py tests/test_workspace_packages.py tests/replay tests/test_replay_metrics.py tests/test_generate_performance_graphs.py`.
Expected: PASS, including the golden replay item `mr-muncher/golden` collected from
`games/mr-muncher/tests/fixtures/replays/` and replaying the unchanged recording (it names
`glitchygames.examples.mr_muncher.game`; `PREVIOUS_MODULES` accepts it).

- [ ] **Step 5: Commit**

```bash
git add -A games pyproject.toml uv.lock pyrightconfig.json wily.cfg noxfile.py .envrc scripts tests glitchygames docs CLAUDE.md README.md
git commit -m "Mr. Muncher is its own package: games/mr-muncher (distribution mr-muncher, import mr_muncher)"
```

---

### Task 7: The browser build ships the game's own package

**Files:**
- Modify: `scripts/build_browser_bundle.py` (`GameSpecification` ~100, `GAMES` ~114,
  `pyscript_config` ~243, `write_bundle` ~343)
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


def test_the_engine_archive_no_longer_holds_the_moved_game(tmp_path):
    """The moved game's code is not under glitchygames/ any more."""
    files = bundled_package_files(package_directory=PACKAGE_DIRECTORY)

    assert not any(path.parts[:2] == ('examples', 'mr_muncher') for path in files)
```

plus a `write_bundle` test (follow the file's existing bundle test at ~172) asserting the
written bundle directory contains `mr_muncher.zip` holding `mr_muncher/game.py`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_build_browser_bundle.py -k "member or moved"`
Expected: FAIL (`unexpected keyword argument 'member_package'`).

- [ ] **Step 3: Implement**

`GameSpecification` gains `member_package: str | None = None` (documented). `GAMES['mr-muncher']`
becomes `module='mr_muncher.game', member_package='mr_muncher'`. `pyscript_config(*, wheel_name,
member_package: str | None = None)` adds `f'"./{member_package}.zip" = "./*"\n'` after the
engine archive line when given. `write_bundle` writes the member archive with
`write_engine_archive(package_directory=<member's package directory>, archive_path=output_directory / f'{member_package}.zip', excluded_subpackages=frozenset())`
(find the member's directory with `workspace_members`). `browser/boot.py` needs no change: the
archive unpacks `mr_muncher/` beside `glitchygames/` and `importlib.import_module('mr_muncher.game')`
finds it.

- [ ] **Step 4: Run the tests, then build the real bundle**

Run: the Step 2 command, then `uv run --extra dev nox -s browser -- mr-muncher` and open the
served page (the session prints its address); the game must start.
Expected: PASS; Mr. Muncher runs in the browser from `mr_muncher.zip`.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_browser_bundle.py tests/test_build_browser_bundle.py
git commit -m "Browser bundles ship a member game's package as its own archive"
```

---

### Task 8: Docs

**Files:**
- Modify: `docs/games/mr_muncher.md` (its file table and paths), `mkdocs.yml` (mkdocstrings
  `paths: [glitchygames, games/mr-muncher]`), `docs/glitchygames/examples/index.md`,
  `README.md` (Example Games; the `uv sync` commands), `CLAUDE.md` (Development Setup, Example
  Games, the replay and testing sections), `plans/future-features.md` (a feature entry linking
  the master plan), `plans/2026-10-24-workspace-packages.md` (Part 1 status)

- [ ] **Step 1: Write the docs**

- `docs/games/mr_muncher.md`: every `glitchygames/examples/mr_muncher/...` path becomes
  `games/mr-muncher/mr_muncher/...`; add a short "Its package" section (the member layout, how
  to run `uv run mr-muncher` and its tests `uv run pytest games/mr-muncher/tests`) and an
  "API reference" section with `::: mr_muncher.game`.
- CLAUDE.md: Development Setup gains `--all-packages`; "Example Games" says Mr. Muncher is
  `games/mr-muncher/` and links the master plan; the replay section documents
  `PREVIOUS_MODULES`; Testing Guidelines say the harness is `tests/harness.py`, loaded for every
  package.

- [ ] **Step 2: Build strictly**

Run: `uv run --extra dev nox -s lint-docs`
Expected: PASS (`mkdocs build --strict`).

- [ ] **Step 3: Commit**

```bash
git add docs mkdocs.yml README.md CLAUDE.md plans
git commit -m "Docs: Mr. Muncher's own package, PREVIOUS_MODULES, the harness plugin"
```

---

### Task 9: Whole-branch verification

- [ ] **Step 1: Lint and types**

Run: `uv run --extra dev nox -s lint static-analysis`
Expected: PASS.

- [ ] **Step 2: The suite as CI runs it, and locally on both drivers**

Run: `CI=true uv run --extra dev nox -s test`, then `uv run pytest`.
Expected: PASS at 100% coverage; the coverage report lists `mr_muncher` files; the native run
shows no driver differences; `mr-muncher/golden` is collected from the member.

- [ ] **Step 3: Wheels**

Run: `uv run --extra dev nox -s build-wheel` and `uv build --package mr-muncher --wheel --out-dir dist`;
list both wheels (`unzip -l`).
Expected: the engine wheel has no `mr_muncher` files and no `examples/mr_muncher`; the
`mr_muncher` wheel has the game and the `mr-muncher` console script.

- [ ] **Step 4: Docs with the browser games**

Run: `uv run --extra dev nox -s docs-deploy -- --build-only`, then check
`site/play/mr-muncher/` exists and holds `mr_muncher.zip`.
Expected: PASS.

- [ ] **Step 5: Record and hand off**

Update the master plan's Part 1 status (done, with the commit range), write any finding into
BUGS.md, and stop for the user's review before pushing or opening the PR.
