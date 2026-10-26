"""The uv workspace's members, read from the root and each member's pyproject.toml.

The one place that knows which packages the repository holds besides the engine: the engine's
guards (tests/test_engine_doors.py and others), the configuration check
(tests/test_workspace_config.py), the browser build and the replay metrics ask it. Members are
listed explicitly in the root ``[tool.uv.workspace] members`` (no globs).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Self, cast

from pydantic import BaseModel, ConfigDict, model_validator

from glitchygames.logical_names import LAYERS

ENGINE_PACKAGE = 'glitchygames'
# Where the engine's source package is, relative to the repository: under src/, so nothing run
# from the repository root imports the source tree by accident (the user, 2026-10-25)
ENGINE_DIRECTORY = Path('src') / ENGINE_PACKAGE


class WorkspaceMember(BaseModel):
    """One member package of the workspace.

    Attributes:
        directory: The member's directory (src/games/mr-muncher).
        distribution: Its distribution name (mr-muncher).
        import_packages: The packages its wheel holds (mr_muncher).
        package_relative_paths: Where each import package is below the directory (mr_muncher, or
            src/mr_muncher in a src layout); defaults to the import packages' names.
        console_scripts: Its console scripts (mr-muncher).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    directory: Path
    distribution: str
    import_packages: tuple[str, ...]
    console_scripts: tuple[str, ...]
    package_relative_paths: tuple[Path, ...] = ()

    @model_validator(mode='before')
    @classmethod
    def _default_package_relative_paths(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Fill package_relative_paths from the import packages when none were given.

        Args:
            values: The fields as given.

        Returns:
            The fields, with package_relative_paths set.

        """
        if not values.get('package_relative_paths'):
            values = {
                **values,
                'package_relative_paths': tuple(
                    Path(package) for package in values.get('import_packages', ())
                ),
            }
        return values

    @property
    def package_directories(self: Self) -> tuple[Path, ...]:
        """The source directories of its import packages."""
        return tuple(self.directory / relative for relative in self.package_relative_paths)

    @property
    def import_roots(self: Self) -> tuple[Path, ...]:
        """The directories its import packages are found in, each once, in package order.

        The member's own directory (``src/games/mr-muncher``), or its ``src/`` in a src layout
        (``src/games/brave-adventurer/src``): what a tool resolving imports (ruff's ``src``,
        ty's ``root``, pyright's ``extraPaths``) needs.
        """
        return tuple(dict.fromkeys(directory.parent for directory in self.package_directories))

    @property
    def layer(self: Self) -> str:
        """The workspace layer it belongs to: its directory's parent under src/ (``games``)."""
        return self.directory.parent.name

    @property
    def tests_directory(self: Self) -> Path:
        """Where its tests are."""
        return self.directory / 'tests'

    @property
    def replay_fixtures_directory(self: Self) -> Path:
        """Where its golden replays are, ``<name>.jsonl.gz`` directly in it."""
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
        FileNotFoundError: If a listed member has no pyproject.toml, or a package its wheel
            declares is not a directory.
        ValueError: If the workspace's members are not a list of strings, a member is not in
            src/<layer>/ (``glitchygames.logical_names.LAYERS``), or a member declares no wheel
            packages.

    """
    root = _read_toml(path=project_root / 'pyproject.toml')
    workspace = root.get('tool', {}).get('uv', {}).get('workspace', {})
    declared_members: object = workspace.get('members', [])
    if not isinstance(declared_members, list) or not all(
        isinstance(declared, str) for declared in cast('list[object]', declared_members)
    ):
        message = f'[tool.uv.workspace] members must be a list of strings, not {declared_members!r}'
        raise ValueError(message)
    member_paths = cast('list[str]', declared_members)
    members: list[WorkspaceMember] = []
    for member_path in member_paths:
        directory = project_root / member_path
        pyproject_path = directory / 'pyproject.toml'
        if not pyproject_path.is_file():
            message = f'Workspace member {member_path} has no pyproject.toml'
            raise FileNotFoundError(message)
        if directory.parent.parent != project_root / 'src' or directory.parent.name not in LAYERS:
            message = (
                f'Workspace member {member_path} is not in src/<layer>/ '
                f'(layers: {", ".join(LAYERS)})'
            )
            raise ValueError(message)
        member = _read_toml(path=pyproject_path)
        project = member['project']
        wheel = member.get('tool', {}).get('hatch', {}).get('build', {}).get('targets', {})
        packages = wheel.get('wheel', {}).get('packages', [])
        if not packages:
            message = (
                f'Workspace member {member_path} declares no '
                '[tool.hatch.build.targets.wheel] packages'
            )
            raise ValueError(message)
        for package in packages:
            if not (directory / package).is_dir():
                message = f'Workspace member {member_path} has no package directory {package}'
                raise FileNotFoundError(message)
        members.append(
            WorkspaceMember(
                directory=directory,
                distribution=project['name'],
                import_packages=tuple(Path(package).name for package in packages),
                package_relative_paths=tuple(Path(package) for package in packages),
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
    directories = [project_root / ENGINE_DIRECTORY]
    for member in workspace_members(project_root=project_root):
        directories.extend(member.package_directories)
    return directories


def declared_console_scripts(*, project_root: Path) -> dict[str, str]:
    """Return every console script the workspace declares: the root project's, then each member's.

    Args:
        project_root: The repository.

    Returns:
        Console script name -> its entry point (``module:function``), as each ``pyproject.toml``
        ``[project.scripts]`` gives it.

    """
    scripts: dict[str, str] = dict(
        _read_toml(path=project_root / 'pyproject.toml')['project'].get('scripts', {})
    )
    for member in workspace_members(project_root=project_root):
        member_project = _read_toml(path=member.directory / 'pyproject.toml')['project']
        scripts.update(member_project.get('scripts', {}))
    return scripts
