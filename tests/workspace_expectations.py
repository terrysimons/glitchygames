"""The expected sets of the tests that find the workspace's members, written out by hand.

A root test that discovers members (their golden replays, bundled demos and console scripts)
must assert it found each one it expects, so it can never pass on zero, and so a lost or extra
recording fails. These are read from the repository on 2026-10-26 and edited deliberately when a
game, golden, demo or console script is added or removed: ``EXPECTED_GOLDENS`` (the six goldens
by ``(distribution, file name)``), ``EXPECTED_GAME_CONSOLE_SCRIPTS`` (the five games-layer
console scripts), ``EXPECTED_ALL_CONSOLE_SCRIPTS`` (the nine members' console scripts: the
games, the demos and Bitmappy) and ``EXPECTED_BUNDLED_DEMOS`` (by ``(package, name)``).

What is read from the workspace (scripts/workspace_packages.py) to compare with them is in
tests/workspace_goldens.py, so an engine test that needs only an expected set here never
imports ``scripts.*`` (Part 3, Stage D, Task D9).
"""

from __future__ import annotations

from glitchygames.logical_names import MEMBER_LAYERS

# The layer whose every member is a game with a golden replay (glitchygames.logical_names.LAYERS)
GAMES_LAYER = 'games'
# A golden replay's suffix (scripts/record_scripted_session.py REPLAY_FIXTURE_SUFFIX)
GOLDEN_SUFFIX = '.jsonl.gz'
# The bundled demos, by (package, name): PaddleSlap's rally is the one today
# (src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz). Never by path: nox's test sessions
# install the members non-editable, so a demo's path is in site-packages there
EXPECTED_BUNDLED_DEMOS = frozenset({('paddleslap', 'rally.jsonl.gz')})
# The import packages whose bundled demos the workspace's tests search: every member's
# (glitchygames.bundled_demos.bundled_demos takes them explicitly, with no default: Stage D,
# Task D5)
MEMBER_PACKAGES = tuple(MEMBER_LAYERS)
# The goldens, by (games-layer distribution, file name), written out by hand: every games-layer
# member holds at least one, Brave Adventurer one per game (5 games, 6 goldens)
EXPECTED_GOLDENS = frozenset({
    ('brave-adventurer', 'golden-classic.jsonl.gz'),
    ('brave-adventurer', 'golden-papyrus.jsonl.gz'),
    ('clockwork-keep', 'golden.jsonl.gz'),
    ('drawing-fire', 'golden.jsonl.gz'),
    ('mr-muncher', 'golden.jsonl.gz'),
    ('paddleslap', 'golden.jsonl.gz'),
})
# The games-layer members' console scripts, written out by hand (one per game member: Brave
# Adventurer's launcher starts both its games)
EXPECTED_GAME_CONSOLE_SCRIPTS = frozenset({
    'brave-adventurer',
    'clockwork-keep',
    'drawing-fire',
    'mr-muncher',
    'paddleslap',
})
# Every member's console script, written out by hand: the five games, the three demos and Bitmappy
EXPECTED_ALL_CONSOLE_SCRIPTS = frozenset({
    'bitmappy',
    'brave-adventurer',
    'clockwork-keep',
    'drawing-fire',
    'dt-demo',
    'joystick-demo',
    'mr-muncher',
    'paddleslap',
    'text-input-demo',
})
