"""Guard CLAUDE.md against its old, long sections coming back beside the condensed ones.

CLAUDE.md is loaded into every Claude Code session, so its size is paid on every turn. It was
condensed to about 20 KB (#202), and merges have twice put the pre-condensation sections back
beside the condensed ones: #192 (undone by #203) and #207 (2026-11-14: 312 lines grew to 1476,
every engine component described twice). Both times the file kept each section's heading twice
and grew far past its condensed size, which is what these tests check.
"""

import re
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD_PATH = PROJECT_ROOT / 'CLAUDE.md'

# The condensed file is 312 lines (2026-11-14). A little room for new rules; raising it is a
# deliberate decision, not a way to make a merge pass (#207's merge reached 1476 lines)
MAXIMUM_LINE_COUNT = 360

# A Markdown heading (## Testing Guidelines), or a bold component name opening a line
# (**GameEngine** (`src/glitchygames/engine/__init__.py`): ...), as the Architecture Overview
# introduces each component
HEADING = re.compile(r'^(?:#{1,6} (?P<heading>.+)|\*\*(?P<component>[^*]+)\*\*(?= |\(|:|$))')


def section_names(*, text: str) -> list[str]:
    """Return each heading and bold component name that opens a line, in order.

    Fenced code blocks are skipped: a ``# comment`` in a bash block is no heading.

    Returns:
        The names, as written.

    """
    names: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING.match(line)
        if match is not None:
            names.append(match.group('heading') or match.group('component'))
    return names


def test_section_names_finds_headings_and_components_outside_code_blocks():
    """The scanner sees both kinds of section and ignores comments in code blocks."""
    text = (
        '## Architecture Overview\n'
        '**GameEngine** (`engine/__init__.py`): one per game\n'
        '```bash\n'
        '# a comment\n'
        '```\n'
        'Text with **bold** inside is no section.\n'
        '**Clocks**: every time read\n'
    )

    assert section_names(text=text) == ['Architecture Overview', 'GameEngine', 'Clocks']


def test_no_section_of_claude_md_appears_twice():
    """Each heading and component is described once (a re-merged old section repeats them)."""
    counts = Counter(section_names(text=CLAUDE_MD_PATH.read_text(encoding='utf-8')))
    repeated = sorted(name for name, count in counts.items() if count > 1)

    assert repeated == []


def test_claude_md_stays_near_its_condensed_size():
    """CLAUDE.md stays under MAXIMUM_LINE_COUNT lines; detail belongs in docs and docstrings."""
    line_count = len(CLAUDE_MD_PATH.read_text(encoding='utf-8').splitlines())

    assert line_count <= MAXIMUM_LINE_COUNT
