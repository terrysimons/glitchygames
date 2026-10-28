"""Tests for tests/collection_logger_levels.py: project loggers at NOTSET after collection."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from tests.collection_logger_levels import is_project_logger, project_logger_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    ('name', 'project'),
    [
        ('game', True),
        ('game.paddle', True),
        ('glitchygames', True),
        ('glitchygames.api', True),
        ('gamepad', False),
        ('urllib3', False),
    ],
)
def test_project_loggers_are_game_and_glitchygames_and_under_them(name, project):
    """``gamepad`` is not under ``game``: only the root or a dotted child is."""
    assert is_project_logger(name) is project


def test_this_run_collected_with_every_project_logger_at_notset():
    """The suite itself: nothing it imported set a level (else it would not have started)."""
    assert project_logger_settings() == []


def test_a_level_and_logging_disable_are_named(monkeypatch):
    """A project logger with a level, and logging.disable, are each named."""
    monkeypatch.setattr(logging.getLogger('game.collection_probe'), 'level', logging.INFO)
    monkeypatch.setattr(logging.root.manager, 'disable', logging.DEBUG)

    assert project_logger_settings() == [
        'game.collection_probe is at INFO',
        'logging.disable is at DEBUG',
    ]


def test_a_collected_module_setting_a_level_stops_the_run(pytester, monkeypatch):
    """Through pytest: a test module that sets ``game``'s level at import stops the run.

    In a child pytest (a level set in this process would outlive the test), with the repository
    on its path for the plugin.
    """
    monkeypatch.setenv('PYTHONPATH', str(PROJECT_ROOT))
    pytester.makepyfile(
        test_chatty=(
            "import logging\nlogging.getLogger('game.chatty').setLevel(logging.DEBUG)\n"
            'def test_nothing():\n    pass\n'
        )
    )

    result = pytester.runpytest_subprocess('-p', 'tests.collection_logger_levels')

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(['*set logging levels*game.chatty is at DEBUG*'])
