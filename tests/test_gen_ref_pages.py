"""scripts/gen_ref_pages.py: every workspace member's packages get an API reference page."""

from __future__ import annotations

import contextlib
import importlib
import io
import runpy
from pathlib import Path
from typing import TYPE_CHECKING

import mkdocs_gen_files
from scripts import gen_ref_pages
from scripts.gen_ref_pages import member_reference_pages, reference_page_path
from scripts.workspace_packages import workspace_members

if TYPE_CHECKING:
    from collections.abc import Generator

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_mr_munchers_package_has_a_page_rendering_it_and_each_of_its_modules():
    """mr_muncher's page renders the package, then every module (its API reference)."""
    pages = member_reference_pages(project_root=PROJECT_ROOT)

    page = pages[reference_page_path(import_package='mr_muncher')]
    package_directory = PROJECT_ROOT / 'src' / 'games' / 'mr-muncher' / 'mr_muncher'
    modules = sorted(
        f'mr_muncher.{path.stem}'
        for path in package_directory.glob('*.py')
        if path.stem != '__init__'
    )
    assert modules, 'mr_muncher has modules'
    assert page.startswith('::: mr_muncher\n')
    for module in modules:
        assert f'::: {module}\n' in page


def test_every_member_package_has_a_page():
    """Every import package of every workspace member gets a page."""
    pages = member_reference_pages(project_root=PROJECT_ROOT)

    for member in workspace_members(project_root=PROJECT_ROOT):
        for import_package in member.import_packages:
            assert reference_page_path(import_package=import_package) in pages


def test_a_package_main_module_is_left_out_and_subpackages_are_named_by_their_path(tmp_path):
    """A member's __main__ is a script, not API; a subpackage's modules keep their dotted path."""
    member = tmp_path / 'src' / 'games' / 'a-game'
    package = member / 'a_game'
    (package / 'levels').mkdir(parents=True)
    for relative in (
        '__init__.py',
        '__main__.py',
        'game.py',
        'levels/__init__.py',
        'levels/one.py',
    ):
        (package / relative).write_text('', encoding='utf-8')
    (member / 'pyproject.toml').write_text(
        '[project]\nname = "a-game"\n\n[tool.hatch.build.targets.wheel]\npackages = ["a_game"]\n',
        encoding='utf-8',
    )
    (tmp_path / 'pyproject.toml').write_text(
        '[project]\nname = "root"\n\n[tool.uv.workspace]\nmembers = ["src/games/a-game"]\n',
        encoding='utf-8',
    )

    page = member_reference_pages(project_root=tmp_path)['a_game/index.md']

    blocks = [line for line in page.splitlines() if line.startswith(':::')]
    assert blocks == [
        '::: a_game',
        '::: a_game.game',
        '::: a_game.levels',
        '::: a_game.levels.one',
    ]


def test_run_as_gen_files_runs_it_the_script_writes_each_page_into_the_build(mocker, tmp_path):
    """mkdocs-gen-files runs the file with runpy.run_path; the pages go to its open()."""
    written: dict[str, str] = {}

    @contextlib.contextmanager
    def build_file(name: str, mode: str) -> Generator[io.StringIO]:
        assert mode == 'w'
        page_file = io.StringIO()
        try:
            yield page_file
        finally:
            written[name] = page_file.getvalue()

    mocker.patch.object(mkdocs_gen_files, 'open', build_file)

    runpy.run_path(str(PROJECT_ROOT / 'scripts' / 'gen_ref_pages.py'))

    assert written == member_reference_pages(project_root=PROJECT_ROOT)


def test_importing_the_script_writes_nothing(mocker):
    """Imported (tests, tools), it only defines; outside a build, open() would write into docs/."""
    open_page = mocker.patch.object(mkdocs_gen_files, 'open')

    importlib.reload(gen_ref_pages)

    open_page.assert_not_called()
