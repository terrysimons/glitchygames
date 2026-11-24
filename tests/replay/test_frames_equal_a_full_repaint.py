"""Every frame of every golden and bundled demo equals a full repaint of that frame.

Dirty-rect drawing redraws only the sprites marked dirty; a sprite that changes without being
marked leaves the screen showing its old state, and no golden would see it (a golden compares
recorded sprite state, not pixels). Each recording is replayed headless in a child through the
engine's own replay command (as tests/logged_records.py does) with a prelude that runs
``glitchygames.testing.full_repaint`` over every frame and writes its counts and first mismatches
to a file. Every frame is compared, whole-screen scenes (``rects = None``) too.

What a scene draws outside its sprites cannot equal a sprite repaint, so it is excluded by name
(``EXCLUSIONS``), each with the plan or to-do that removes it, and counted: a recording's report
says how many frames it compared, how many were presented whole and how many had an exclusion,
so an exclusion never hides silently.

While ``Scene.dirty`` is never cleared (``Scene.update`` marks every sprite dirty every frame), a
missed mark cannot show here; this sweep guards the frames once it is cleared
(bugs/2026-11-21-a-resumed-scene-presents-only-its-dirty-rects.md;
fix/static-sprites-full-screen-update).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command
from glitchygames.replay.tools.children import (
    REPLAY_TIMEOUT_SECONDS,
    entry_point_command,
    game_entry_point,
    headless_replay_arguments,
)
from tests.workspace_goldens import every_golden_and_bundled_demo

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RECORDINGS = every_golden_and_bundled_demo(project_root=PROJECT_ROOT)
# entry_point_command's shape: [interpreter, '-c', code]
CODE_FLAG = '-c'
# A rectangle larger than any screen: the whole frame
WHOLE_FRAME = (0, 0, 100_000, 100_000)
# The score and lives text Brave Adventurer and Clockwork Keep blit straight onto the screen
# (their _draw_hud), measured at (11, 11, 752, 16) on an 800-wide screen
HUD_STRIP = (0, 0, 100_000, 40)
HUD_REASON = (
    'HUD text blitted straight onto the screen; plans/2026-11-20-game-code-into-the-engine.md '
    "moves it into sprites (the owner's decision c), and this exclusion goes with it"
)
# Scene class name: (the excluded area, why)
EXCLUSIONS: dict[str, tuple[tuple[int, int, int, int], str]] = {
    'BraveAdventurerScene': (HUD_STRIP, HUD_REASON),
    'PapyrusBraveAdventurerScene': (HUD_STRIP, HUD_REASON),
    'ClockworkKeepScene': (HUD_STRIP, HUD_REASON),
    'DrawingFireScene': (
        WHOLE_FRAME,
        (
            'draws its whole world straight onto the screen; its conversion to sprites is in '
            'plans/future-work.md'
        ),
    ),
}

# The child's prelude, run before the entry point's code; its names start with an underscore so
# they never shadow the entry point's. Formatted with the result path and the exclusions
PRELUDE = """\
import atexit as _atexit
import json as _json
import os as _os

import pygame as _pygame

from glitchygames.testing.full_repaint import (
    compare_each_frame_with_a_full_repaint as _compare,
)

_exclusions = {exclusions!r}


def _excluded_areas(scene):
    area = _exclusions.get(type(scene).__name__)
    return [] if area is None else [_pygame.Rect(area)]


# The context manager is kept for the whole run: once it is collected, its generator closes and
# puts the original render step back
_comparing = _compare(raise_on_mismatch=False, excluded_areas_of=_excluded_areas)
_comparison = _comparing.__enter__()


_game_process = _os.getpid()


def _write_result():
    # A child the game starts may inherit this handler (a fork): only the game's process writes
    if _os.getpid() != _game_process:
        return
    with open({result_path!r}, 'w', encoding='utf-8') as result_file:
        _json.dump(
            {{'counts': _comparison.counts(), 'mismatches': _comparison.mismatches}}, result_file
        )


_atexit.register(_write_result)
"""


def repaint_command(*, console_script: str, recording: Path, result_path: Path) -> list[str]:
    """Return the replay's child command with the comparing prelude in front of its code.

    Returns:
        The command, as an argument list.

    Raises:
        ValueError: If the entry point's command is not a ``python -c`` command.

    """
    interpreter, flag, code, *arguments = [
        *entry_point_command(entry_point=game_entry_point(console_script=console_script)),
        *headless_replay_arguments(recording=recording),
    ]
    if flag != CODE_FLAG:
        message = f'not a python -c command: {flag!r}'
        raise ValueError(message)
    exclusions = {name: area for name, (area, _reason) in EXCLUSIONS.items()}
    prelude = PRELUDE.format(exclusions=exclusions, result_path=str(result_path))
    return [interpreter, CODE_FLAG, f'{prelude}\n{code}', *arguments]


def report_line(*, recording: Path, counts: dict[str, Any]) -> str:
    """Describe what a recording's comparison covered.

    Returns:
        ``name: 342 compared, 0 presented whole, 0 with an exclusion, 0 differing``.

    """
    return (
        f'{recording.name}: {counts["compared"]} compared, {counts["whole_screen_frames"]} '
        f'presented whole, {counts["frames_with_excluded_areas"]} with an exclusion, '
        f'{counts["mismatch_count"]} differing'
    )


@pytest.mark.parametrize(
    ('console_script', 'recording'),
    RECORDINGS,
    ids=[f'{console_script}/{path.name}' for console_script, path in RECORDINGS],
)
def test_every_frame_equals_a_full_repaint(console_script, recording, tmp_path):
    """Each frame the replay renders equals its background with every visible sprite on it."""
    result_path = tmp_path / 'full_repaint.json'
    completed = run_command(
        command=repaint_command(
            console_script=console_script, recording=recording, result_path=result_path
        ),
        environment=os.environ,
        timeout_seconds=REPLAY_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
    )

    output_tail = '\n'.join((completed.stdout or '').splitlines()[-40:])
    assert completed.returncode == ExitCode.SUCCESS, output_tail
    assert result_path.is_file(), f'the child wrote no result; its output ended:\n{output_tail}'
    result = json.loads(result_path.read_text(encoding='utf-8'))
    counts = result['counts']
    assert counts['compared'] > 0, report_line(recording=recording, counts=counts)
    assert counts['mismatch_count'] == 0, '\n'.join([
        report_line(recording=recording, counts=counts),
        *result['mismatches'],
    ])


def test_the_recordings_are_every_golden_and_bundled_demo():
    """An empty list would skip the sweep, not fail it."""
    assert len(RECORDINGS) == len({path for _script, path in RECORDINGS})
    assert len(RECORDINGS) >= 19


def test_every_exclusion_says_what_removes_it():
    """Each exclusion names the plan or to-do that ends it, so the mask comes off with it."""
    for name, (_area, reason) in EXCLUSIONS.items():
        assert 'plans/' in reason, name
