"""The docs site's browser games (scripts/mkdocs_hooks.py ``on_post_build``): play/."""

from __future__ import annotations

from mkdocs.config.defaults import MkDocsConfig
from scripts import mkdocs_hooks


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
    config['site_dir'] = str(tmp_path / 'site')

    mkdocs_hooks.on_post_build(config)

    assert (tmp_path / 'site' / 'play' / 'paddleslap' / 'index.html').is_file()
