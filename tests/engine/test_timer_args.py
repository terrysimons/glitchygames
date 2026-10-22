#!/usr/bin/env python3
"""Tests for timer-related command-line argument parsing."""

import argparse
from types import SimpleNamespace

import pytest

from glitchygames.engine import GameEngine
from glitchygames.exit_codes import ExitCode
from glitchygames.scenes import Scene
from glitchygames.timing import DEFAULT_SLEEP_GRANULARITY_NS


class DummyGame(Scene):
    """Minimal Scene subclass for testing argument parsing."""

    NAME = 'Dummy'
    VERSION = '0.0'

    @classmethod
    def args(cls, parser):  # passthrough
        """Pass through the argument parser without adding arguments.

        Returns:
            The argument parser, unmodified.

        """
        return parser


def test_timer_args_defaults(mocker):
    """Test that default timer arguments are parsed correctly."""
    # Build a fake argparse result with required fields
    ns = SimpleNamespace(
        log_level='INFO',
        target_fps=0.0,
        fps_log_interval_ms=1000,
        windowed=True,
        resolution='800x480',
        use_gfxdraw=False,
        update_type='update',
        video_driver=None,
        # New flags
        timer_backend='pygame',
        sleep_granularity_ns=1_000_000,
        windows_timer_1ms=False,
        log_timer_jitter=False,
        profile=False,
    )
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=ns)
    opts = GameEngine.initialize_arguments(DummyGame)
    assert opts['timer_backend'] == 'pygame'
    assert opts['sleep_granularity_ns'] == 1_000_000
    assert opts['windows_timer_1ms'] is False
    assert opts['log_timer_jitter'] is False


def test_timer_args_overrides(mocker):
    """Test that overridden timer arguments are parsed correctly."""
    ns = SimpleNamespace(
        log_level='INFO',
        target_fps=60.0,
        fps_log_interval_ms=500,
        windowed=True,
        resolution='800x480',
        use_gfxdraw=False,
        update_type='update',
        video_driver=None,
        timer_backend='fast',
        sleep_granularity_ns=0,
        windows_timer_1ms=True,
        log_timer_jitter=True,
        profile=False,
    )
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=ns)
    opts = GameEngine.initialize_arguments(DummyGame)
    assert opts['timer_backend'] == 'fast'
    assert opts['sleep_granularity_ns'] == 0
    assert opts['windows_timer_1ms'] is True
    assert opts['log_timer_jitter'] is True


def _parse_graphics_arguments(argument_list):
    """Parse command-line arguments with the engine's real Graphics Options.

    Returns:
        The parsed argparse namespace.

    """
    parser = argparse.ArgumentParser()
    GameEngine.args(parser)
    return parser.parse_args(argument_list)


def test_timer_backend_defaults_to_auto():
    """The default is auto: the fast backend with the machine's sleep delay, 1 ms final spin."""
    arguments = _parse_graphics_arguments([])
    assert arguments.timer_backend == 'auto'
    assert arguments.sleep_granularity_ns == DEFAULT_SLEEP_GRANULARITY_NS


def test_timer_backend_accepts_fast():
    """The fast backend with its fixed 1 ms final spin can still be selected."""
    assert _parse_graphics_arguments(['--timer-backend=fast']).timer_backend == 'fast'


def test_timer_backend_accepts_pygame():
    """The legacy pygame backend can still be selected."""
    assert _parse_graphics_arguments(['--timer-backend=pygame']).timer_backend == 'pygame'


def test_timer_backend_rejects_invalid_choice(capsys):
    """An unknown timer backend is rejected by argparse."""
    with pytest.raises(SystemExit) as exit_info:
        _parse_graphics_arguments(['--timer-backend=bogus'])
    assert exit_info.value.code == ExitCode.ARGUMENT_PARSER_ERROR
    assert 'invalid choice' in capsys.readouterr().err
