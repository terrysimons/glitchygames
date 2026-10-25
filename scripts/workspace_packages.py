"""The uv workspace's members, read from the root and each member's pyproject.toml.

The one place that knows which packages the repository holds besides the engine: the engine's
guards (tests/test_engine_doors.py and others), the configuration check
(tests/test_workspace_config.py), the browser build and the replay metrics ask it. Members are
listed explicitly in the root ``[tool.uv.workspace] members`` (no globs).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Self

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


def _read_toml(*, path: Path) -> dict[str, Any]:
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

    Args:
        project_root: The repository.

    Returns:
        The package directories.

    """
    directories = [project_root / ENGINE_PACKAGE]
    for member in workspace_members(project_root=project_root):
        directories.extend(member.package_directories)
    return directories
