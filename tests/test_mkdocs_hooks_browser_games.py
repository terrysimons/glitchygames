"""The docs site's post-build hook (scripts/mkdocs_hooks.py ``on_post_build``).

The browser games (play/), and the explorers' pages checked without a browser: each built page
holds its explorer, and every script, stylesheet and data file it names is in the site.
"""

from __future__ import annotations

import pytest
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import PluginError
from scripts import mkdocs_hooks

# What each explorer's built page names, as mkdocs writes it: relative to the page's directory
EXPLORER_PAGE_FILES = {
    'requirements/index.html': ('requirements-explorer', '../data/requirements.json'),
    'quality/performance/index.html': (
        'performance-explorer',
        '../metrics/performance-explorer.json',
    ),
    'quality/complexity/index.html': (
        'complexity-explorer',
        '../graphs/complexity-explorer.json',
    ),
}
SITE_FILES = (
    'js/requirements.js',
    'css/explorer.css',
    'data/requirements.json',
    'quality/metrics/performance-explorer.json',
    'quality/graphs/complexity-explorer.json',
)


def explorer_page(*, depth: int, explorer_class: str, data_source: str) -> str:
    """A built explorer page: another site's script and font, ours, an icon and the explorer.

    Returns:
        The page's HTML.
    """
    to_site_root = '../' * depth
    return (
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Roboto">'
        f'<link rel="stylesheet" href="{to_site_root}css/explorer.css">'
        f'<link rel="icon" href="{to_site_root}img/not-checked.ico">'
        f'<div class="md-content"><div class="{explorer_class} wide" data-source="{data_source}">'
        '</div></div>'
        '<script src="https://unpkg.com/mermaid@12.2.0/dist/mermaid.min.js"></script>'
        f'<script src="{to_site_root}js/requirements.js?v=1#top"></script>'
        '<script>inline()</script>'
    )


def make_explorer_site(directory):
    """Write a built site holding the explorers' pages and every file they name.

    Returns:
        The directory.
    """
    for page, (explorer_class, data_source) in EXPLORER_PAGE_FILES.items():
        page_path = directory / page
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(
            explorer_page(
                depth=page.count('/'), explorer_class=explorer_class, data_source=data_source
            )
        )
    for site_file in SITE_FILES:
        (directory / site_file).parent.mkdir(parents=True, exist_ok=True)
        (directory / site_file).write_text('{}')
    return directory


def make_games_site(directory):
    """Write a games site as ``build_browser_bundle.py all`` lays it out.

    Returns:
        The directory.
    """
    (directory / 'paddleslap').mkdir(parents=True)
    (directory / 'paddleslap' / 'index.html').write_text('<title>Paddle Slap</title>')
    (directory / 'index.html').write_text('<ul></ul>')
    return directory


def test_built_games_are_copied_into_the_site_as_play(tmp_path):
    """The games' site lands in the docs site as play/, every game in it."""
    games = make_games_site(tmp_path / 'games')
    site = tmp_path / 'site'
    site.mkdir()

    copied = mkdocs_hooks.copy_browser_games(games_directory=games, site_directory=site)

    assert copied
    assert (site / 'play' / 'index.html').read_text() == '<ul></ul>'
    assert (site / 'play' / 'paddleslap' / 'index.html').is_file()


def test_without_built_games_the_site_has_no_play(tmp_path, caplog):
    """A docs build that did not build the games (lint-docs, docs-serve) leaves play/ out."""
    site = tmp_path / 'site'
    site.mkdir()

    with caplog.at_level('INFO', logger='mkdocs.hooks.glitchygames'):
        copied = mkdocs_hooks.copy_browser_games(
            games_directory=tmp_path / 'missing', site_directory=site
        )

    assert not copied
    assert not (site / 'play').exists()
    assert 'No browser games' in caplog.text


def test_the_post_build_hook_copies_into_the_configured_site(tmp_path, mocker):
    """The post-build event (mkdocs) copies into the configuration's site_dir."""
    games = make_games_site(tmp_path / 'games')
    mocker.patch.object(mkdocs_hooks, 'BROWSER_GAMES_DIRECTORY', games)
    config = MkDocsConfig()
    config['site_dir'] = str(make_explorer_site(tmp_path / 'site'))

    mkdocs_hooks.on_post_build(config)

    assert (tmp_path / 'site' / 'play' / 'paddleslap' / 'index.html').is_file()


def test_explorer_pages_whose_files_are_all_built_miss_nothing(tmp_path):
    """Other sites' scripts and fonts, inline scripts and icons are not the site's to check."""
    site = make_explorer_site(tmp_path / 'site')

    assert mkdocs_hooks.missing_explorer_files(site_directory=site) == []


def test_an_explorers_missing_data_file_is_named(tmp_path):
    """The JSON a data-source names, resolved against its page's directory as a browser does."""
    site = make_explorer_site(tmp_path / 'site')
    (site / 'quality' / 'graphs' / 'complexity-explorer.json').unlink()

    page = 'quality/complexity/index.html'
    reference = '../graphs/complexity-explorer.json'

    assert mkdocs_hooks.missing_explorer_files(site_directory=site) == [
        f'{page}: {reference} (quality/graphs/complexity-explorer.json)'
    ]


def test_a_missing_stylesheet_is_named_on_every_page_that_loads_it(tmp_path):
    """Every page loads the same stylesheets, so each reports the missing one."""
    site = make_explorer_site(tmp_path / 'site')
    (site / 'css' / 'explorer.css').unlink()

    missing = mkdocs_hooks.missing_explorer_files(site_directory=site)

    assert missing == [
        f'{page}: {"../" * page.count("/")}css/explorer.css (css/explorer.css)'
        for page in EXPLORER_PAGE_FILES
    ]


def test_a_missing_page_or_explorer_is_named(tmp_path):
    """A page that was not built, and a page built without its explorer's element."""
    site = make_explorer_site(tmp_path / 'site')
    (site / 'requirements' / 'index.html').unlink()
    (site / 'quality' / 'performance' / 'index.html').write_text('<p>No explorer</p>')

    assert mkdocs_hooks.missing_explorer_files(site_directory=site) == [
        'requirements/index.html: the page itself',
        'quality/performance/index.html: its explorer (an element of class performance-explorer)',
    ]


def test_a_reference_outside_the_site_is_missing(tmp_path):
    """A path that climbs out of the site is no file of it, even when one is there."""
    site = make_explorer_site(tmp_path / 'site')
    (tmp_path / 'outside.js').write_text('')
    page = site / 'requirements' / 'index.html'
    page.write_text(page.read_text() + '<script src="../../outside.js"></script>')

    assert mkdocs_hooks.missing_explorer_files(site_directory=site) == [
        'requirements/index.html: ../../outside.js (../outside.js)'
    ]


def test_the_post_build_hook_stops_a_build_missing_an_explorers_file(tmp_path, mocker):
    """The strict build (nox -s lint-docs) and a deploy fail rather than publish a dead page."""
    mocker.patch.object(mkdocs_hooks, 'BROWSER_GAMES_DIRECTORY', tmp_path / 'no-games')
    site = make_explorer_site(tmp_path / 'site')
    (site / 'data' / 'requirements.json').unlink()
    config = MkDocsConfig()
    config['site_dir'] = str(site)

    with pytest.raises(
        PluginError, match=r'requirements/index\.html: \.\./data/requirements\.json'
    ):
        mkdocs_hooks.on_post_build(config)
