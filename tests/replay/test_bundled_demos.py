"""Every demo bundled in a game's package replays without divergence (spec 5.3).

A bundled demo is an ordinary recording shipped in a workspace member's package, as package data
(``<package>/demos/<name>.jsonl.gz``). The suite collects only ``tests/``, so
the demos are reached through this module: one headless replay per demo
(``bundled_demo_paths``, glitchygames/testing/replays.py; ``replay_recording_headless``,
glitchygames/replay/tools/children.py), so a change that makes a demo diverge fails here before
it ships. PaddleSlap's own tests play its demo the way the game plays it, through
``SceneManager.play_recording``
(src/games/paddleslap/tests/test_paddleslap_demo_plays_in_game.py).
"""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest
from scripts.workspace_packages import workspace_members

from glitchygames.bundled_demos import bundled_demos
from glitchygames.exit_codes import ExitCode
from glitchygames.replay.tools.children import replay_recording_headless
from glitchygames.testing.replays import bundled_demo_paths
from glitchygames.tracing import TraceReader
from tests.workspace_expectations import (
    EXPECTED_BUNDLED_DEMOS,
    MAXIMUM_DEMO_BYTES,
    MEMBER_PACKAGES,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BUNDLED_DEMOS = bundled_demo_paths(packages=MEMBER_PACKAGES)


def test_the_bundled_demos_are_the_expected_ones():
    """The bundled demos are the expected ones, each replayed by its own member's console script.

    Compared by ``(package, name)``, not by path: nox's test sessions install the members
    non-editable. This is the replay test's expected set (an empty parametrization would skip,
    not fail), so the demos it replays are exactly these.
    """
    demos = bundled_demos(packages=MEMBER_PACKAGES)
    members = workspace_members(project_root=PROJECT_ROOT)

    assert {(demo.package, demo.path.name) for demo in demos} == EXPECTED_BUNDLED_DEMOS
    assert [(console_script, path.name) for console_script, path in BUNDLED_DEMOS] == [
        (demo.console_script, demo.path.name) for demo in demos
    ]
    for demo in demos:
        (member,) = [member for member in members if demo.package in member.import_packages]
        assert demo.console_script in member.console_scripts


def test_every_bundled_demo_is_small_enough_to_ship():
    """No bundled demo is larger than the plan's limit."""
    for demo in bundled_demos(packages=MEMBER_PACKAGES):
        assert demo.path.stat().st_size <= MAXIMUM_DEMO_BYTES, demo.install_name


# Event type -> the kind of input it presses or releases (the same table as
# tests/test_record_bundled_demos.py, for what a recording holds rather than a script)
PRESS_KINDS = {
    pygame.KEYDOWN: 'key',
    pygame.MOUSEBUTTONDOWN: 'mouse',
    pygame.JOYBUTTONDOWN: 'joystick',
    pygame.CONTROLLERBUTTONDOWN: 'controller',
}
RELEASE_KINDS = {
    pygame.KEYUP: 'key',
    pygame.MOUSEBUTTONUP: 'mouse',
    pygame.JOYBUTTONUP: 'joystick',
    pygame.CONTROLLERBUTTONUP: 'controller',
}


def held_input_of(*, kind, attributes):
    """Return what a press or release record is about: the same tuple for both.

    Args:
        kind: ``'key'``, ``'mouse'``, ``'joystick'`` or ``'controller'``.
        attributes: The event record's attributes.

    Returns:
        ``('key', key)``, ``('mouse', button)`` or ``(kind, instance_id, button)``.

    """
    if kind == 'key':
        return (kind, attributes['key'])
    if kind == 'mouse':
        return (kind, attributes['button'])
    return (kind, attributes['instance_id'], attributes['button'])


def input_held_after_the_last_frame(*, path):
    """Return the external input a recording presses and never releases.

    Args:
        path: The recording.

    Returns:
        The set of held inputs after the last frame (see ``held_input_of``).

    """
    held = set()
    with TraceReader(path=path) as reader:
        for frame in reader:
            for batch in frame.get('event_batches', []):
                for record in batch:
                    if record['origin'] != 'external':
                        continue
                    if record['type'] in PRESS_KINDS:
                        kind = PRESS_KINDS[record['type']]
                        held.add(held_input_of(kind=kind, attributes=record['attributes']))
                    elif record['type'] in RELEASE_KINDS:
                        kind = RELEASE_KINDS[record['type']]
                        held.discard(held_input_of(kind=kind, attributes=record['attributes']))
    return held


def test_no_bundled_demo_ends_with_input_held():
    """The Arcade loops a demo, so nothing a demo pressed may still be down after its last frame."""
    for demo in bundled_demos(packages=MEMBER_PACKAGES):
        assert input_held_after_the_last_frame(path=demo.path) == set(), demo.install_name


@pytest.mark.parametrize(
    ('console_script', 'demo_path'),
    BUNDLED_DEMOS,
    ids=[f'{console_script}/{path.name}' for console_script, path in BUNDLED_DEMOS],
)
def test_bundled_demo_replays_without_divergence(console_script, demo_path):
    """The game still reproduces the demo frame for frame (a headless replay exits SUCCESS)."""
    completed = replay_recording_headless(console_script=console_script, path=demo_path)

    assert completed.returncode == ExitCode.SUCCESS, completed.stdout
