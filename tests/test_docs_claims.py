"""Tests for scripts/docs_claims.py: the documentation claims the code no longer backs.

Each check runs on a small throwaway git repository holding a claim that holds and one that
does not, of each kind: paths (from the root, and as each member has them: in a member's
README and in an engine page), Python file names
(whole and suffixes), dotted names (module, class and inherited members, an instance named
for its class, another library's), command-line options, and BUGS.md entries called open
after they were fixed. The pages that are not checked (dated specs, API stubs, a document
listed as unchecked) and the recorded exceptions are left out of the report.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from scripts import docs_claims
from scripts.docs_claims import (
    CLAIMS_FOUND,
    Claim,
    all_claims,
    main,
    module_name_for,
)
from scripts.git_checkout import NotAGitCheckoutError

from glitchygames.exit_codes import ExitCode
from tests.ledger_repositories import git

if TYPE_CHECKING:
    from pathlib import Path

ENGINE_CAMERA = """\
class Camera2D:
    def __init__(self):
        self.zoom = 1.0

    def update(self):
        pass
"""
ENGINE_SCENE = """\
from glitchygames.camera import Camera2D


class SceneBase:
    game_time = 0.0


class Scene(SceneBase):
    def switch_to(self):
        pass
"""
MEMBER_GAME = """\
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--real-option')
"""
BUGS = """\
# Bugs

### 6. Still Broken
- **Status**: Active

### 5. Long Gone
- **Status**: Fixed (2026-11-01)
"""
CLAUDE = """\
# Notes

See src/glitchygames/camera.py and src/glitchygames/gone.py:12, then `tests/<game>/x.py`.
Files: `camera.py`, `missing.py`, `_wheel.py`, `_missing_suffix.py`.
Names: `glitchygames.camera.Camera2D.update`, `glitchygames.camera.Camera2D.missing`.
Names: `glitchygames.gone`, `Scene.game_time`, `Scene.missing()`, `camera.zoom`.
Names: `pygame.mixer.Sound`, `self.dt`, `bitmappy.zip`, `get_pos()`.
Options: `--real-option`, `--real-option VALUE`, `--missing-option`, `--real`.
Bug #6 is still open; #5 is open too; #5 was fixed.

```text
#5 is open in this fenced example, and src/glitchygames/fenced-gone.py
```
"""
MEMBER_README = """\
# X game

Its golden is tests/fixtures/real.txt; its other one tests/fixtures/gone.txt.
"""
MEMBER_RELATIVE_PAGE = """\
Each game keeps its golden in tests/fixtures/real.txt; none has tests/fixtures/nowhere.txt.
"""
UNCHECKED_SPEC = 'The spec names src/glitchygames/old.py, as of its date.\n'
API_STUB = '::: glitchygames.camera\n\nsrc/glitchygames/stub-gone.py\n'


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """Return a throwaway repository with one holding and one stale claim of each kind.

    Returns:
        Its root.

    """
    files = {
        'src/glitchygames/__init__.py': '',
        'src/glitchygames/camera.py': ENGINE_CAMERA,
        'src/glitchygames/scenes/__init__.py': '',
        'src/glitchygames/scenes/scene.py': ENGINE_SCENE,
        'src/games/x/pyproject.toml': '[project]\nname = "x-game"\n',
        'src/games/x/src/x_game/__init__.py': MEMBER_GAME,
        'src/games/x/tests/test_x_game_wheel.py': '',
        'src/games/x/tests/fixtures/real.txt': 'golden\n',
        'src/games/x/README.md': MEMBER_README,
        'BUGS.md': BUGS,
        'CLAUDE.md': CLAUDE,
        'docs/specs/2026-01-01-spec.md': UNCHECKED_SPEC,
        'docs/reference/camera.md': API_STUB,
        'docs/galimore.md': 'Another code base: src/galibmap.cpp.\n',
        'docs/games/x.md': MEMBER_RELATIVE_PAGE,
    }
    for relative, text in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    git(repository=tmp_path, arguments=['init', '--quiet'])
    git(repository=tmp_path, arguments=['add', '.'])
    return tmp_path


def _described(claims: list[Claim]) -> list[str]:
    """Return each claim's report line."""
    return [claim.describe() for claim in claims]


def test_every_kind_of_stale_claim_is_listed_and_every_holding_one_is_not(repository):
    """Each stale claim is listed once per occurrence, in line order; no holding claim is."""
    assert _described(all_claims(project_root=repository)) == [
        'CLAUDE.md:3: path: src/glitchygames/gone.py',
        'CLAUDE.md:4: file: missing.py',
        'CLAUDE.md:4: file: _missing_suffix.py',
        'CLAUDE.md:5: name: glitchygames.camera.Camera2D.missing',
        'CLAUDE.md:6: name: glitchygames.gone',
        'CLAUDE.md:6: name: Scene.missing()',
        'CLAUDE.md:8: option: --missing-option',
        'CLAUDE.md:8: option: --real',
        'CLAUDE.md:9: bug: #5 (Fixed)',
        'CLAUDE.md:9: bug: #5 (Fixed)',
        'CLAUDE.md:12: path: src/glitchygames/fenced-gone.py',
        'docs/games/x.md:1: path: tests/fixtures/nowhere.txt',
        'src/games/x/README.md:3: path: tests/fixtures/gone.txt',
    ]


def test_kinds_narrow_the_report(repository):
    """--kind keeps only the claims of the kinds named."""
    assert _described(all_claims(project_root=repository, kinds=('option', 'bug'))) == [
        'CLAUDE.md:8: option: --missing-option',
        'CLAUDE.md:8: option: --real',
        'CLAUDE.md:9: bug: #5 (Fixed)',
        'CLAUDE.md:9: bug: #5 (Fixed)',
    ]


def test_a_recorded_exception_is_left_out(repository, monkeypatch):
    """A claim recorded as an exception is not reported; the others still are."""
    monkeypatch.setattr(
        docs_claims,
        'RECORDED_EXCEPTIONS',
        {('CLAUDE.md', '--missing-option'): 'an example of a typo'},
    )

    assert _described(all_claims(project_root=repository, kinds=('option',))) == [
        'CLAUDE.md:8: option: --real'
    ]


def test_an_untracked_document_is_not_read(repository):
    """Only tracked documents are living documentation."""
    (repository / 'NOTES.md').write_text('src/glitchygames/untracked-gone.py\n', encoding='utf-8')

    assert 'NOTES.md' not in {claim.document for claim in all_claims(project_root=repository)}


def test_a_directory_outside_any_checkout_is_refused(tmp_path):
    """Without git's list of tracked files there is nothing to check against."""
    with pytest.raises(NotAGitCheckoutError, match='is not in a git checkout'):
        all_claims(project_root=tmp_path)


@pytest.mark.parametrize(
    ('relative', 'module'),
    [
        ('src/glitchygames/camera.py', 'glitchygames.camera'),
        ('src/glitchygames/audio/__init__.py', 'glitchygames.audio'),
        ('src/games/mr-muncher/src/mr_muncher/game.py', 'mr_muncher.game'),
        ('scripts/docs_claims.py', 'scripts.docs_claims'),
    ],
)
def test_a_file_is_named_as_it_is_imported(relative, module):
    """A file below a src/ is named from there; any other from the repository root."""
    assert module_name_for(relative=relative) == module


def test_main_writes_the_claims_and_exits_claims_found(repository, monkeypatch, capsys):
    """The claims go to standard output, their count to standard error."""
    monkeypatch.setattr(docs_claims, 'PROJECT_ROOT', repository)

    status = main(['--kind', 'option'])

    captured = capsys.readouterr()
    assert status == CLAIMS_FOUND
    assert captured.out == ('CLAUDE.md:8: option: --missing-option\nCLAUDE.md:8: option: --real\n')
    assert captured.err == '2 claims\n'


def test_main_exits_success_when_every_claim_holds(repository, monkeypatch, capsys):
    """No claim: no output but the count, and success."""
    (repository / 'CLAUDE.md').write_text('See `--real-option`.\n', encoding='utf-8')
    (repository / 'src/games/x/README.md').write_text('# X\n', encoding='utf-8')
    (repository / 'docs/games/x.md').write_text('# X\n', encoding='utf-8')
    monkeypatch.setattr(docs_claims, 'PROJECT_ROOT', repository)

    status = main([])

    assert status == ExitCode.SUCCESS
    assert capsys.readouterr() == ('', '0 claims\n')
