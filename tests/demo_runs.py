"""Run a small demo's ``main()`` through the real engine, headless, for a few frames.

A root test helper (it imports the engine's golden-trace harness), shared by the demos' tests:
the demos layer's members (``src/demos/dt-demo/tests``, ``src/demos/joystick-demo/tests`` and
``src/demos/text-input-demo/tests``). A demo runs with its console script (``dt-demo``) or
``python -m``. Its ``main()`` builds ``GameEngine(game=Game)`` and starts it; the tests run that
same ``main()`` with the module's ``GameEngine`` replaced by ``DemoRunEngine``: the real engine
opening a plain window (SDL's dummy video driver has no renderer for GameEngine's SCALED window,
and the "no fast renderer available" warning it gives is an error under pytest's
filterwarnings; see ``GoldenTraceEngine``), with a supervisor that posts a scripted input per
frame and then QUIT, so the run ends on its own as a player quitting it would.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

import pygame

from glitchygames.recording import post_input_event
from glitchygames.replay.tools.golden_traces import GoldenTraceEngine

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from pytest_mock import MockerFixture

    from glitchygames.scenes import Scene

# The display a demo run opens unless told otherwise
DEMO_RUN_RESOLUTION = '320x240'
# The command line every demo run gets (after --resolution): headless, unpaced, quiet
DEMO_RUN_ARGUMENTS = (
    '--headless',
    '--target-fps',
    '0',
    '--log-level',
    'warning',
    '--input-mode',
    'joystick',
)


class ScriptedInput:
    """A supervisor posting each frame's scripted events, then QUIT after the last frame."""

    def __init__(self: Self, *, events_by_frame: dict[int, list[pygame.event.Event]]) -> None:
        """Hold the script.

        Args:
            events_by_frame: Frame number -> the events posted at that frame's supervisor slot
                (the game gets them in the next frame).

        """
        self.events_by_frame = events_by_frame
        self.quit_frame = max(events_by_frame, default=0) + 1
        self.scenes_seen: list[Scene | None] = []

    def on_frame(self: Self, *, frame_number: int, scene: Scene | None) -> None:
        """Post this frame's events (QUIT on the frame after the last scripted one)."""
        self.scenes_seen.append(scene)
        for event in self.events_by_frame.get(frame_number, []):
            post_input_event(event)
        if frame_number == self.quit_frame:
            post_input_event(pygame.event.Event(pygame.QUIT))


class DemoRunEngine(GoldenTraceEngine):
    """The real engine with a plain window, running SCRIPT as its supervisor."""

    SCRIPT: ClassVar[ScriptedInput | None] = None

    @override
    def start(self: Self) -> None:
        """Add the scripted supervisor, then run the game until it quits."""
        assert self.SCRIPT is not None
        self.scene_manager.add_supervisor(supervisor=self.SCRIPT)
        super().start()


def run_demo_main(
    *,
    mocker: MockerFixture,
    module: Any,
    main: Callable[[], None],
    events_by_frame: dict[int, list[pygame.event.Event]] | None = None,
    resolution: str = DEMO_RUN_RESOLUTION,
) -> ScriptedInput:
    """Run a demo's ``main()`` headless until the script quits it.

    Args:
        mocker: pytest-mock's fixture.
        module: The demo's module or package (its ``GameEngine`` is replaced for the run; its
            ``__name__`` is the run's program name).
        main: The demo's ``main``.
        events_by_frame: The input script (default: none, so the game quits after frame 1).
        resolution: The display size, as --resolution takes it ('WIDTHxHEIGHT').

    Returns:
        The script, holding the scene active at each frame's supervisor slot.

    """
    script = ScriptedInput(events_by_frame=events_by_frame or {0: []})
    mocker.patch.object(DemoRunEngine, 'SCRIPT', script)
    mocker.patch.object(module, 'GameEngine', DemoRunEngine)
    mocker.patch.object(
        sys, 'argv', [module.__name__, '--resolution', resolution, *DEMO_RUN_ARGUMENTS]
    )
    main()
    return script


def engine_run_environment(mocker: MockerFixture) -> Generator[None]:
    """Let a test start a real engine, leaving pygame usable for later tests.

    The engine's shutdown quits the display and pygame (later tests on the worker still need
    them), writes SDL hints to the environment, and its event managers block and allow event
    types: all of it is put back afterwards. (As tests/engine/test_engine_lifecycle.py's
    fixture of the same name.)

    Yields:
        None, while the environment is in place.

    """
    mocker.patch.object(pygame, 'quit')
    mocker.patch.object(pygame.display, 'quit')
    mocker.patch.dict(os.environ)
    blocked_before = [
        pygame.event.get_blocked(event_type) for event_type in range(pygame.NUMEVENTS)
    ]
    yield
    pygame.event.clear()
    for event_type, was_blocked in enumerate(blocked_before):
        if was_blocked:
            pygame.event.set_blocked(event_type)
        else:
            pygame.event.set_allowed(event_type)
