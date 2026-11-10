"""The uv workspace's members, read from the root and each member's pyproject.toml.

The one place that knows which packages the repository holds besides the engine: the engine's
guards (tests/test_engine_doors.py and others), the configuration check
(tests/test_workspace_config.py), the browser build and the replay metrics ask it. Members are
listed explicitly in the root ``[tool.uv.workspace] members`` (no globs).
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any, Self, cast

from pydantic import BaseModel, ConfigDict, model_validator

from glitchygames.logical_names import LAYERS

ENGINE_PACKAGE = 'glitchygames'
# Where the engine's source package is, relative to the repository: under src/, so nothing run
# from the repository root imports the source tree by accident (the user, 2026-10-25)
ENGINE_DIRECTORY = Path('src') / ENGINE_PACKAGE
# A requirement's distribution name: what it starts with (PEP 508), and the separators PEP 503
# folds into one '-'
REQUIREMENT_NAME = re.compile(r'\s*([A-Za-z0-9][A-Za-z0-9._-]*)')
NAME_SEPARATORS = re.compile(r'[-_.]+')


def canonical_distribution_name(*, name: str) -> str:
    """Return a distribution name in PEP 503's canonical form (lower case, runs of -_. as -).

    Args:
        name: The name.

    Returns:
        The canonical name.

    """
    return NAME_SEPARATORS.sub('-', name).lower()


def requirement_distribution(*, requirement: str) -> str:
    """Return the canonical distribution name a ``[project] dependencies`` requirement names.

    Extras, version specifiers, URLs and markers are dropped (PEP 508: the name comes first).

    Args:
        requirement: The requirement (``aisuite[openai]>=0.1.14``).

    Returns:
        Its canonical distribution name (``aisuite``).

    Raises:
        ValueError: If it does not start with a name.

    """
    match = REQUIREMENT_NAME.match(requirement)
    if match is None:
        message = f'The requirement {requirement!r} names no distribution'
        raise ValueError(message)
    return canonical_distribution_name(name=match.group(1))


class WorkspaceMember(BaseModel):
    """One member package of the workspace.

    Attributes:
        directory: The member's directory (src/games/mr-muncher).
        distribution: Its distribution name (mr-muncher).
        import_packages: The packages its wheel holds (mr_muncher).
        package_relative_paths: Where each import package is below the directory (mr_muncher, or
            src/mr_muncher in a src layout); defaults to the import packages' names.
        console_scripts: Its console scripts (mr-muncher).
        dependencies: The distributions its ``[project] dependencies`` name, canonical
            (``requirement_distribution``), in the order given.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    directory: Path
    distribution: str
    import_packages: tuple[str, ...]
    console_scripts: tuple[str, ...]
    package_relative_paths: tuple[Path, ...] = ()
    dependencies: tuple[str, ...] = ()

    @model_validator(mode='before')
    @classmethod
    def _default_package_relative_paths(cls, values: object) -> object:
        """Fill package_relative_paths from the import packages when none were given.

        Args:
            values: The fields as given (anything else, such as an existing member, passes
                through for pydantic to validate).

        Returns:
            The fields, with package_relative_paths set.

        """
        if not isinstance(values, dict):
            return values
        values = cast('dict[str, Any]', values)
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

    Each member is read by ``_read_member``, which raises FileNotFoundError if a listed
    member's directory or its pyproject.toml is missing, or a package its wheel declares is not a
    directory; and ValueError if a member is not in src/<layer>/
    (``glitchygames.logical_names.LAYERS``), its pyproject.toml has no ``[project]`` table or no
    ``name``, or it declares no wheel packages (or declares them as anything but a list of
    strings).

    Returns:
        The members.

    Raises:
        ValueError: If the workspace's members are not a list of strings.

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
    return [_read_member(project_root=project_root, member_path=path) for path in member_paths]


def _read_member(*, project_root: Path, member_path: str) -> WorkspaceMember:
    """Read one workspace member (``workspace_members`` says what it refuses).

    Returns:
        The member.

    Raises:
        FileNotFoundError: If the member's directory or its pyproject.toml is missing.
        ValueError: If the member is not in src/<layer>/, or its pyproject.toml has no
            ``[project]`` table or no ``name``.

    """
    directory = project_root / member_path
    pyproject_path = directory / 'pyproject.toml'
    if not directory.is_dir():
        message = f'Workspace member {member_path} has no directory {directory}'
        raise FileNotFoundError(message)
    if not pyproject_path.is_file():
        message = f'Workspace member {member_path} has no pyproject.toml'
        raise FileNotFoundError(message)
    if directory.parent.parent != project_root / 'src' or directory.parent.name not in LAYERS:
        message = (
            f'Workspace member {member_path} is not in src/<layer>/ (layers: {", ".join(LAYERS)})'
        )
        raise ValueError(message)
    member = _read_toml(path=pyproject_path)
    project = member.get('project', {})
    if 'name' not in project:
        message = f'Workspace member {member_path} has no [project] name in its pyproject.toml'
        raise ValueError(message)
    packages = _wheel_packages(member_path=member_path, directory=directory, member=member)
    return WorkspaceMember(
        directory=directory,
        distribution=project['name'],
        import_packages=tuple(Path(package).name for package in packages),
        package_relative_paths=tuple(Path(package) for package in packages),
        console_scripts=tuple(project.get('scripts', {})),
        dependencies=tuple(
            requirement_distribution(requirement=requirement)
            for requirement in project.get('dependencies', [])
        ),
    )


def _wheel_packages(*, member_path: str, directory: Path, member: dict[str, Any]) -> list[str]:
    """Return the packages a member's wheel declares (``[tool.hatch.build.targets.wheel]``).

    Returns:
        The package paths, relative to the member's directory.

    Raises:
        FileNotFoundError: If a declared package is not a directory.
        ValueError: If none is declared, or they are not a list of strings.

    """
    wheel = member.get('tool', {}).get('hatch', {}).get('build', {}).get('targets', {})
    declared: object = wheel.get('wheel', {}).get('packages', [])
    if not isinstance(declared, list) or not all(
        isinstance(package, str) for package in cast('list[object]', declared)
    ):
        message = (
            f'Workspace member {member_path} must declare '
            f'[tool.hatch.build.targets.wheel] packages as a list of strings, not {declared!r}'
        )
        raise ValueError(message)
    packages = cast('list[str]', declared)
    if not packages:
        message = (
            f'Workspace member {member_path} declares no [tool.hatch.build.targets.wheel] packages'
        )
        raise ValueError(message)
    for package in packages:
        if not (directory / package).is_dir():
            message = f'Workspace member {member_path} has no package directory {package}'
            raise FileNotFoundError(message)
    return packages


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


def members_in_layer(*, project_root: Path, layer: str) -> list[WorkspaceMember]:
    """Return the workspace's members in one layer, in the order the root pyproject lists them.

    Args:
        project_root: The repository.
        layer: The layer (``games``: ``glitchygames.logical_names.LAYERS``).

    Returns:
        The members whose directory is in ``src/<layer>/``.

    Raises:
        ValueError: If the layer is not one of ``glitchygames.logical_names.LAYERS`` (a typo
            would otherwise find no member).

    """
    if layer not in LAYERS:
        message = f'{layer!r} is not a workspace layer (layers: {", ".join(LAYERS)})'
        raise ValueError(message)
    return [
        member for member in workspace_members(project_root=project_root) if member.layer == layer
    ]
