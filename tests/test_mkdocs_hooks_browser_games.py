"""The docs site's post-build hook (scripts/mkdocs_hooks.py ``on_post_build``).

The browser games (play/), and the explorers' pages checked without a browser: each built page
holds its explorer, and every script, stylesheet and data file it names is in the site.
"""

from __future__ import annotations

import json

import pytest
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import PluginError
from scripts import mkdocs_hooks

from tests.explorer_site import EXPLORER_PAGE_FILES, make_explorer_site

# The commit the docs build from, in these tests, and another one
HEAD = 'a' * 40
OTHER_COMMIT = 'b' * 40


def make_games_site(directory, *, commit=HEAD, games=('paddleslap',), stamped=True):
    """Write a games site as ``build_browser_bundle.py all`` lays it out, stamped as it stamps.

    Returns:
        The directory.
    """
    for game in games:
        (directory / game).mkdir(parents=True, exist_ok=True)
        (directory / game / 'index.html').write_text(f'<title>{game}</title>')
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'index.html').write_text('<ul></ul>')
    if stamped:
        (directory / mkdocs_hooks.SITE_STAMP_NAME).write_text(
            json.dumps({'commit': commit, 'games': list(games)})
        )
    return directory


def copy_games(games, site, *, publishing=False):
    """Copy a games site in as the hook does, at HEAD.

    Returns:
        Whether it was copied.
    """
    return mkdocs_hooks.copy_browser_games(
        games_directory=games, site_directory=site, head_commit=HEAD, publishing=publishing
    )


@pytest.mark.parametrize('publishing', [False, True], ids=['local-build', 'deploy'])
def test_built_games_are_copied_into_the_site_as_play(tmp_path, publishing):
    """The games' site, built from the docs' commit, lands in the docs site as play/."""
    games = make_games_site(tmp_path / 'games')
    site = tmp_path / 'site'
    site.mkdir()

    copied = copy_games(games, site, publishing=publishing)

    assert copied
    assert (site / 'play' / 'index.html').read_text() == '<ul></ul>'
    assert (site / 'play' / 'paddleslap' / 'index.html').is_file()


def test_without_built_games_the_site_has_no_play(tmp_path, caplog):
    """A docs build that did not build the games (lint-docs, docs-serve) leaves play/ out."""
    site = tmp_path / 'site'
    site.mkdir()

    with caplog.at_level('INFO', logger='mkdocs.hooks.glitchygames'):
        copied = copy_games(tmp_path / 'missing', site)

    assert not copied
    assert not (site / 'play').exists()
    assert 'No browser games' in caplog.text


# Games sites a deploy must not publish: each would replace play/ with something other than this
# commit's games (2026-11-19: a deploy copied a site built six days earlier, and Zombies Ain't My
# Neighbors' play/ page vanished)
UNPUBLISHABLE_SITES = {
    'not-built': (lambda directory: directory, 'No browser games'),
    'built-before-stamps': (
        lambda directory: make_games_site(directory, stamped=False),
        'no site_build.json',
    ),
    'built-from-another-commit': (
        lambda directory: make_games_site(directory, commit=OTHER_COMMIT),
        f'built from {OTHER_COMMIT}, not {HEAD}',
    ),
    'a-game-missing': (
        lambda directory: (
            make_games_site(directory, games=('paddleslap',))
            .joinpath(mkdocs_hooks.SITE_STAMP_NAME)
            .write_text(json.dumps({'commit': HEAD, 'games': ['paddleslap', 'zombies']}))
            and directory
        ),
        'zombies',
    ),
}


@pytest.mark.parametrize(
    ('make_site', 'reason'), UNPUBLISHABLE_SITES.values(), ids=UNPUBLISHABLE_SITES.keys()
)
def test_a_deploy_refuses_games_that_are_not_this_commits(tmp_path, make_site, reason):
    """gh-deploy stops, naming why and how to build them, rather than publish the wrong play/."""
    games = make_site(tmp_path / 'games')
    site = tmp_path / 'site'
    site.mkdir()

    with pytest.raises(PluginError, match=r'scripts\.build_browser_bundle all') as refusal:
        copy_games(games, site, publishing=True)

    assert reason in str(refusal.value)
    assert not (site / 'play').exists()


@pytest.mark.parametrize(
    ('make_site', 'reason'), UNPUBLISHABLE_SITES.values(), ids=UNPUBLISHABLE_SITES.keys()
)
def test_a_local_build_leaves_games_that_are_not_this_commits_out(
    tmp_path, make_site, reason, caplog
):
    """docs-serve and lint-docs show no play/ rather than a stale one, and say why.

    Not as a warning: the strict build would stop on a games site left from an older build.
    """
    games = make_site(tmp_path / 'games')
    site = tmp_path / 'site'
    site.mkdir()

    with caplog.at_level('INFO', logger='mkdocs.hooks.glitchygames'):
        copied = copy_games(games, site)

    assert not copied
    assert not (site / 'play').exists()
    assert reason in caplog.text
    assert all(record.levelname == 'INFO' for record in caplog.records)


def test_the_hook_reads_the_stamp_the_builder_writes():
    """The hook is loaded by path and cannot import the builder: the stamp's name is held equal."""
    from scripts import build_browser_bundle

    assert mkdocs_hooks.SITE_STAMP_NAME == build_browser_bundle.SITE_STAMP_NAME


def test_a_gh_deploy_builds_the_games_afresh_then_publishes_them(tmp_path, mocker):
    """Every deploy rebuilds the browser games (a game may have changed), whatever ran it.

    nox -s docs-deploy and a bare mkdocs gh-deploy alike: the games published are the ones built
    from this checkout now, never a site left from an older build (the owner, 2026-11-19).
    """
    games = make_games_site(tmp_path / 'games', commit=OTHER_COMMIT)
    mocker.patch.object(mkdocs_hooks, 'BROWSER_GAMES_DIRECTORY', games)
    mocker.patch.object(mkdocs_hooks, 'repository_head_commit', return_value=HEAD)
    mocker.patch.object(mkdocs_hooks.BUILD_STATE, 'command', 'gh-deploy')
    build = mocker.patch.object(
        mkdocs_hooks,
        'build_browser_games',
        side_effect=lambda: make_games_site(games, games=('paddleslap', 'zombies')),
    )
    config = MkDocsConfig()
    config['site_dir'] = str(make_explorer_site(tmp_path / 'site'))

    mkdocs_hooks.on_post_build(config)

    build.assert_called_once_with()
    assert (tmp_path / 'site' / 'play' / 'zombies' / 'index.html').is_file()


@pytest.mark.parametrize('command', ['build', 'serve', None])
def test_a_local_build_builds_no_games(tmp_path, mocker, command):
    """docs-serve and lint-docs never build the games: that needs the WebAssembly toolchain."""
    games = make_games_site(tmp_path / 'games')
    mocker.patch.object(mkdocs_hooks, 'BROWSER_GAMES_DIRECTORY', games)
    mocker.patch.object(mkdocs_hooks, 'repository_head_commit', return_value=HEAD)
    mocker.patch.object(mkdocs_hooks.BUILD_STATE, 'command', command)
    build = mocker.patch.object(mkdocs_hooks, 'build_browser_games')
    config = MkDocsConfig()
    config['site_dir'] = str(make_explorer_site(tmp_path / 'site'))

    mkdocs_hooks.on_post_build(config)

    build.assert_not_called()
    assert (tmp_path / 'site' / 'play' / 'paddleslap' / 'index.html').is_file()


def test_a_failed_games_build_stops_the_deploy(mocker):
    """The builder's failure stops gh-deploy before anything is published."""
    mocker.patch.object(
        mkdocs_hooks,
        'run_command',
        return_value=mocker.Mock(returncode=1),
    )

    with pytest.raises(PluginError, match='build_browser_bundle all failed'):
        mkdocs_hooks.build_browser_games()


def test_the_games_build_runs_the_builder_from_the_repository(mocker):
    """The build is the builder itself, run as ``python -m`` from the repository root."""
    run = mocker.patch.object(mkdocs_hooks, 'run_command', return_value=mocker.Mock(returncode=0))

    mkdocs_hooks.build_browser_games()

    (call,) = run.call_args_list
    assert call.kwargs['command'][1:] == ['-m', 'scripts.build_browser_bundle', 'all']
    assert call.kwargs['working_directory'] == mkdocs_hooks.SCRIPTS_DIRECTORY.parent


def test_a_gh_deploy_stops_when_the_fresh_games_are_not_this_commits(tmp_path, mocker):
    """Should the build leave another commit's site, the deploy still refuses to publish it."""
    games = make_games_site(tmp_path / 'games', commit=OTHER_COMMIT)
    mocker.patch.object(mkdocs_hooks, 'BROWSER_GAMES_DIRECTORY', games)
    mocker.patch.object(mkdocs_hooks, 'repository_head_commit', return_value=HEAD)
    mocker.patch.object(mkdocs_hooks.BUILD_STATE, 'command', 'gh-deploy')
    mocker.patch.object(mkdocs_hooks, 'build_browser_games')
    config = MkDocsConfig()
    config['site_dir'] = str(make_explorer_site(tmp_path / 'site'))

    with pytest.raises(PluginError, match=f'built from {OTHER_COMMIT}'):
        mkdocs_hooks.on_post_build(config)


def test_the_post_build_hook_copies_into_the_configured_site(tmp_path, mocker):
    """The post-build event (mkdocs) copies into the configuration's site_dir."""
    games = make_games_site(tmp_path / 'games')
    mocker.patch.object(mkdocs_hooks, 'BROWSER_GAMES_DIRECTORY', games)
    mocker.patch.object(mkdocs_hooks, 'repository_head_commit', return_value=HEAD)
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
