#!/usr/bin/env python3
"""Generate the workspace members' API reference pages (mkdocs-gen-files; mkdocs.yml plugins).

The engine's reference pages are written by hand (docs/glitchygames/, one page per package with
the options each needs). Each workspace member's import packages (scripts/workspace_packages.py)
get one generated page each, ``<package>/index.md``: the package, then each of its modules (a
subpackage's by their dotted path; ``__main__`` left out), rendered as the engine's pages render
theirs, so a member's API is documented as soon as it joins the workspace. mkdocs.yml's nav names
each page (tests/test_workspace_config.py checks every member's is there) and mkdocstrings' python
``paths`` find the packages.

mkdocs-gen-files runs this file inside the build (``runpy.run_path``, so ``__name__`` is
``RUN_PATH_NAME``), where ``write_reference_pages`` writes the pages into the build;
``member_reference_pages`` is the part that decides them.
"""
# pyright: reportMissingImports=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportPrivateImportUsage=false

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import mkdocs_gen_files

if TYPE_CHECKING:
    from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# The name runpy.run_path gives a file it runs, as mkdocs-gen-files runs its scripts
RUN_PATH_NAME = '<run_path>'
# scripts/workspace_packages.py, loaded by its path: mkdocs does not put the project root on
# sys.path, so `import scripts.workspace_packages` fails inside the build
WORKSPACE_PACKAGES_PATH = PROJECT_ROOT / 'scripts' / 'workspace_packages.py'
WORKSPACE_PACKAGES_MODULE_NAME = 'scripts.workspace_packages'
# How each module is rendered (the engine's hand-written pages' options); the package's own block
# shows its docstring only, its modules follow
MODULE_OPTIONS = """    options:
      heading_level: 2
      inherited_members: true
      show_submodules: false
"""
PACKAGE_ONLY_OPTION = '      members: false\n'


def load_workspace_packages() -> ModuleType:
    """Return scripts/workspace_packages.py as a module (imported once, then reused).

    Returns:
        The module.

    """
    loaded = sys.modules.get(WORKSPACE_PACKAGES_MODULE_NAME)
    if loaded is not None:
        return loaded
    specification = importlib.util.spec_from_file_location(
        WORKSPACE_PACKAGES_MODULE_NAME, WORKSPACE_PACKAGES_PATH
    )
    assert specification is not None, f'{WORKSPACE_PACKAGES_PATH} is not a Python module'
    assert specification.loader is not None, f'{WORKSPACE_PACKAGES_PATH} has no loader'
    module = importlib.util.module_from_spec(specification)
    sys.modules[WORKSPACE_PACKAGES_MODULE_NAME] = module
    specification.loader.exec_module(module)
    return module


def reference_page_path(*, import_package: str) -> str:
    """Return where an import package's reference page goes in the docs (``mr_muncher/index.md``).

    Returns:
        The page's path, relative to docs/.

    """
    return f'{import_package}/index.md'


def package_module_names(*, package_directory: Path, import_package: str) -> list[str]:
    """Return a package's modules by dotted name, the package first (its ``__main__`` left out).

    Args:
        package_directory: The package's source directory.
        import_package: Its import name.

    Returns:
        The package, then its modules and subpackages, in path order.

    """
    names: list[str] = []
    for path in sorted(package_directory.rglob('*.py')):
        parts = (import_package, *path.relative_to(package_directory).with_suffix('').parts)
        if parts[-1] == '__main__':
            continue
        if parts[-1] == '__init__':
            parts = parts[:-1]
        names.append('.'.join(parts))
    # The package's own __init__ first, then the rest in path order
    return sorted(names, key=lambda name: (name != import_package, name))


def reference_page(*, module_names: list[str]) -> str:
    """Return a package's reference page: one mkdocstrings block per module.

    Args:
        module_names: The package, then its modules (``package_module_names``).

    Returns:
        The page's markdown.

    """
    package, *modules = module_names
    blocks = [f'::: {package}\n{MODULE_OPTIONS}{PACKAGE_ONLY_OPTION}']
    blocks.extend(f'::: {module}\n{MODULE_OPTIONS}' for module in modules)
    return '\n'.join(blocks)


def member_reference_pages(*, project_root: Path) -> dict[str, str]:
    """Return every workspace member package's reference page, by its path in the docs.

    Args:
        project_root: The repository.

    Returns:
        Each page's markdown, by ``reference_page_path``.

    """
    workspace_packages = load_workspace_packages()
    pages: dict[str, str] = {}
    for member in workspace_packages.workspace_members(project_root=project_root):
        for import_package, package_directory in zip(
            member.import_packages, member.package_directories, strict=True
        ):
            pages[reference_page_path(import_package=import_package)] = reference_page(
                module_names=package_module_names(
                    package_directory=package_directory, import_package=import_package
                )
            )
    return pages


def write_reference_pages() -> None:
    """Write every member package's reference page into the build (mkdocs-gen-files)."""
    for page_path, page in member_reference_pages(project_root=PROJECT_ROOT).items():
        with mkdocs_gen_files.open(page_path, 'w') as page_file:
            page_file.write(page)


if __name__ == RUN_PATH_NAME:
    write_reference_pages()
