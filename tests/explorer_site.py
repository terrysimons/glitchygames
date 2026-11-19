"""A built docs site holding the explorers' pages, for tests of the post-build hook.

The hook (``scripts/mkdocs_hooks.py`` ``on_post_build``) checks every build's explorer pages
(``missing_explorer_files``), so any test that runs the hook needs a site with them: one under
``tmp_path``, never the checkout's ``site/`` (a local build leaves one; a fresh CI checkout has
none).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

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


def make_explorer_site(directory: Path) -> Path:
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
