#!/usr/bin/env python3
from types import SimpleNamespace
from unittest.mock import patch

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene


class DummyGame(Scene):
    NAME = "Dummy"
    VERSION = "0.0"

    @classmethod
    def args(cls, parser):  # passthrough
        return parser


def test_timer_args_defaults(monkeypatch):
    # Build a fake argparse result with required fields
    ns = SimpleNamespace(
        log_level="INFO",
        target_fps=0.0,
        fps_log_interval_ms=1000,
        windowed=True,
        resolution="800x480",
        use_gfxdraw=False,
        update_type="update",
        video_driver=None,
        # New flags
        timer_backend="pygame",
        sleep_granularity_ns=1_000_000,
        windows_timer_1ms=False,
        log_timer_jitter=False,
        profile=False,
    )
    with patch("argparse.ArgumentParser.parse_args", return_value=ns):
        opts = GameEngine.initialize_arguments(DummyGame)
        assert opts["timer_backend"] == "pygame"
        assert opts["sleep_granularity_ns"] == 1_000_000
        assert opts["windows_timer_1ms"] is False
        assert opts["log_timer_jitter"] is False


def test_timer_args_overrides(monkeypatch):
    ns = SimpleNamespace(
        log_level="INFO",
        target_fps=60.0,
        fps_log_interval_ms=500,
        windowed=True,
        resolution="800x480",
        use_gfxdraw=False,
        update_type="update",
        video_driver=None,
        timer_backend="fast",
        sleep_granularity_ns=0,
        windows_timer_1ms=True,
        log_timer_jitter=True,
        profile=False,
    )
    with patch("argparse.ArgumentParser.parse_args", return_value=ns):
        opts = GameEngine.initialize_arguments(DummyGame)
        assert opts["timer_backend"] == "fast"
        assert opts["sleep_granularity_ns"] == 0
        assert opts["windows_timer_1ms"] is True
        assert opts["log_timer_jitter"] is True

