"""Shipped code draws text in the bundled fonts, never pygame's default font or a system font.

PR #328's recordings replayed on macOS and Linux but diverged on Windows from frame 0: the HUD's
text was pygame's default font (freesansbold), which Windows' SDL_ttf lays out one pixel narrower
(``Score: 10`` 88 pixels wide on macOS, 87 on Windows), and a text sprite's rect is its text's
size, so the recorded rects differed. The bundled Vera fonts lay out the same on all three
(#328's CI). Every font is therefore built from a bundled file (``font_manager.bundled_font``,
``FontManager``) and this scans the engine's and every workspace member's shipped source
(tests/workspace_sources.py) for the two ways around it, reported as ``'<line>: <what>'``:

1. ``Font(None, ...)`` (``pygame.font.Font``, ``pygame.freetype.Font`` or a bare ``Font``, with
   ``None`` as its file, positional or ``file=``): pygame's default font.
2. Any ``SysFont(...)`` call: a font the machine has, which differs from machine to machine.

``ALLOWED`` names the files that may, each for one kind and with its reason; an entry no longer
needed fails, so the list cannot go stale. Tests may use the default font (they are not scanned).
bugs/2026-11-27-text-in-pygames-default-font-differs-by-platform.md.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from tests.ast_scanning import PROJECT_ROOT
from tests.workspace_sources import scanned_source_files

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_FONT = 'Font(None)'
SYSTEM_FONT = 'SysFont'

# (allowlist key, kind): why that file may
ALLOWED: dict[tuple[str, str], str] = {
    ('fonts/font_manager.py', SYSTEM_FONT): (
        'a font the player names with --font-name that is not bundled is, by definition, theirs'
    ),
    ('testing/text_metrics.py', DEFAULT_FONT): (
        "the triage tool measures pygame's default font on purpose, to compare platforms"
    ),
}


def _called_name(call: ast.Call) -> str | None:
    """Return the last part of a call's dotted name (``Font`` for ``pygame.font.Font``)."""
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


def _is_none(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def font_findings(*, source: str) -> list[str]:
    """Report each default-font and system-font call in a module's source.

    Args:
        source: The module's source.

    Returns:
        ``'<line>: Font(None)'`` and ``'<line>: SysFont'``, in source order.

    """
    findings: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name = _called_name(node)
        if name == SYSTEM_FONT:
            findings.append((node.lineno, SYSTEM_FONT))
        elif name == 'Font':
            file_argument = node.args[0] if node.args else None
            file_keyword = next((kw.value for kw in node.keywords if kw.arg == 'file'), None)
            if _is_none(file_argument) or (not node.args and _is_none(file_keyword)):
                findings.append((node.lineno, DEFAULT_FONT))
    return [f'{line}: {kind}' for line, kind in sorted(findings)]


def kinds_found(*, path: Path) -> set[str]:
    """Return which kinds a file's findings are."""
    findings = font_findings(source=path.read_text(encoding='utf-8'))
    return {finding.split(': ', 1)[1] for finding in findings}


def test_the_scan_finds_every_default_and_system_font():
    """Positional and keyword None, both pygame modules, a bare name, SysFont from either."""
    source = (
        'import pygame\n'
        'import pygame.freetype\n'
        'from pygame.font import Font\n'
        'a = pygame.font.Font(None, 16)\n'
        'b = pygame.freetype.Font(None, size=16)\n'
        'c = Font(file=None, size=16)\n'
        "d = pygame.font.SysFont('arial', 16)\n"
        "e = pygame.freetype.SysFont('arial', 16)\n"
    )

    assert font_findings(source=source) == [
        '4: Font(None)',
        '5: Font(None)',
        '6: Font(None)',
        '7: SysFont',
        '8: SysFont',
    ]


def test_a_font_from_a_file_is_not_reported():
    """A bundled file, a path held in a name, and a call that only shares part of the name."""
    source = (
        'import pygame\n'
        "a = pygame.font.Font('Vera.ttf', 16)\n"
        'b = pygame.font.Font(path, 16)\n'
        'c = pygame.font.Font(file=path, size=16)\n'
        'd = make_font(None, 16)\n'
    )

    assert font_findings(source=source) == []


def test_shipped_code_draws_text_only_in_bundled_fonts():
    """No file outside ALLOWED builds pygame's default font or a system font."""
    unexpected = {
        key: findings
        for key, path in scanned_source_files(project_root=PROJECT_ROOT)
        if (
            findings := [
                finding
                for finding in font_findings(source=path.read_text(encoding='utf-8'))
                if (key, finding.split(': ', 1)[1]) not in ALLOWED
            ]
        )
    }

    assert unexpected == {}, (
        'draw text in font_manager.bundled_font (or through FontManager): pygame default font '
        'and system fonts lay text out differently per platform, so recorded rects diverge'
    )


def test_every_allowed_file_still_needs_its_entry():
    """An entry whose file no longer makes that kind of font is removed, not left to excuse one."""
    paths = dict(scanned_source_files(project_root=PROJECT_ROOT))

    stale = [
        (key, kind)
        for key, kind in ALLOWED
        if key not in paths or kind not in kinds_found(path=paths[key])
    ]

    assert stale == []
