"""A game's own command replayed inside its own engine context: the host's handle on it.

An outer game (the Arcade; plans/2026-11-12-arcade-3-inner-game.md) runs other games, unchanged,
inside itself. ``InnerGame.replay`` makes a fresh ``EngineContext``, gives it a render target of
its own (glitchygames/render_target.py: the context is then inner, so its engine draws there and
never touches the window or SDL's drivers) and turns on its private event queue
(``recording.private_event_queue``: its posts never reach SDL's queue, its replay doors never
drain or block SDL's). It then calls the installed command's own entry point, as the console
script would, with ``sys.argv`` swapped to the replay's command line for that call only
(decision 7). In an inner context ``GameEngine.start()`` is a hosted start: it builds the game up
to its first frame and hands the engine over (``take_started_engine``). The host then runs one
frame per ``step()``, unpaced (the host's own frame is the pacing), and reads how the game ended
from ``outcome``.

The rules:

1. **Only recordings run inner** (decision 5). Every inner game replays a recording headless
   (``--replay-trace PATH --headless``; ``--headless`` is a switch no later argument can undo).
   Arguments that would do anything else are refused before anything is built
   (``InnerGameRefusedError``): every tool flag (live play, ``--record-trace`` and another
   ``--replay-trace`` among them), ``--rebaseline``, ``--audit``, ``--compare-trace`` and the
   frame stream, a watched replay's restart options, ``--profile`` and ``--list-input-devices``
   (a hosted start would ignore them silently), and ``--help`` and ``--version`` (each prints
   to stdout and exits), with their short forms ``-p``, ``-h`` and ``-v``. Argparse takes any
   unambiguous prefix of a long flag, so a prefix of a refused flag is refused too, and reads a
   short-flag cluster letter by letter (``-ph`` is ``-p -h``) until a letter that takes a value,
   which takes the rest; after a bare ``--`` nothing is a flag.
2. **A failure belongs to the inner game** (decisions 2 and 4). An ``Exception`` or a
   ``SystemExit`` (a game's ``sys.exit()``, the engine's ``exit_with``, argparse's exit) raised
   while building, stepping or finishing makes the outcome ``FAILED`` with the error's text; the
   host and every other inner game go on. ``KeyboardInterrupt`` and ``GeneratorExit`` propagate.
   A build that fails leaves no engine current in the inner context and hands none over; one
   that fails after its engine was built (in ``begin_frames``) is finished as rule 4 says.
3. **An inner game writes nothing to stdout** (decision 3): the replay's report, which a headless
   replay prints, is the outcome's ``report`` and is logged at INFO.
4. **Finishing leaves the process as it was.** ``finish()`` ends the frames, closes any
   recording and the timer, and settles the replay's result, as the engine's teardown would,
   but never quits pygame, restores signal handlers or SDL's driver variables (a hosted start
   changed none of them) or exits. SDL's queue, its blocked event types
   (``events.set_event_types_allowed``) and the window are never touched; the default context
   is current again after every call. The process-wide mixer is still shared (Arcade sub-plan
   4, sound), and so are SDL's key repeat, text input and cursor visibility and pygame's default
   font resolution (plans/future-work.md).

A recorded quit (every golden ends with its game's quit control) ends only its inner game:
the QUIT is posted to and drained from the context's private queue, never SDL's.
"""

from __future__ import annotations

import logging
import sys
from enum import StrEnum
from typing import TYPE_CHECKING, Self

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames.engine.game_engine import CURRENT_ENGINE_SLOT
from glitchygames.engine_context import EngineContext, current_context
from glitchygames.exit_codes import ExitCode
from glitchygames.recording import private_event_queue
from glitchygames.render_target import set_render_target, take_started_engine
from glitchygames.replay.tools.children import game_entry_point
from glitchygames.replay.tools.registry import (
    AUDIT_OPTION,
    COMPARE_TRACE_OPTION,
    REBASELINE_OPTION,
    REPLAY_FRAME_STREAM_OPTION,
    TOOLS,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from glitchygames.engine.game_engine import GameEngine

LOG = logging.getLogger('game.inner_game')

# What a failure inside an inner game may be (decision 4); KeyboardInterrupt and GeneratorExit
# are the host's and propagate
CONTAINED_ERRORS: tuple[type[BaseException], ...] = (Exception, SystemExit)
# The flags an inner game refuses (rule 1): each tool's own flag, the replay options that record,
# audit, compare or stream, a watched replay's restart options (GameEngine.args), and the flags a
# hosted start would ignore or that print to stdout
REFUSED_FLAGS: frozenset[str] = frozenset({
    *(tool.flag for tool in TOOLS),
    REBASELINE_OPTION.flag,
    AUDIT_OPTION.flag,
    COMPARE_TRACE_OPTION.flag,
    REPLAY_FRAME_STREAM_OPTION.flag,
    '--replay-restart-handoff',
    '--replay-viewer-state',
    '--profile',
    '--list-input-devices',
    '--help',
    '--version',
})
# The refused flags' short forms, by their letter: argparse's -h (--help) and the engine's -p
# (--profile, glitchygames/events/game.py), checked against the engine's parser by
# tests/engine/test_inner_game.py; and -v, the short form our games give --version (a game's own
# flag: argparse's version action prints to stdout and exits)
REFUSED_SHORT_FLAG_LETTERS: frozenset[str] = frozenset({'h', 'p', 'v'})
# The engine's short flags that take a value (-f, -l, -r): in a cluster the rest of the argument
# is that value, so no letter after one is a flag (argparse's rule). A game's own short flag
# taking a value (-b, -s) is not known here, so a refused letter after one is refused anyway: a
# refusal too many, never one too few
SHORT_FLAGS_TAKING_A_VALUE: frozenset[str] = frozenset({'f', 'l', 'r'})
# After it every argument is positional (argparse's rule)
ARGUMENTS_SEPARATOR = '--'
LONG_FLAG_PREFIX = '--'
SHORT_FLAG_PREFIX = '-'
# A long flag's inline value (--record-trace=PATH)
INLINE_VALUE_SEPARATOR = '='


class InnerGameState(StrEnum):
    """Where an inner game is: running, ended (matched or not), or failed."""

    RUNNING = 'running'
    ENDED = 'ended'
    FAILED = 'failed'


class InnerGameOutcome(BaseModel):
    """How an inner game stands, or how it ended (read-only).

    Attributes:
        state: Running, ended or failed.
        frames_run: How many frames ran to their end.
        report: The replay's report once settled (``Replay matched N frames ...``, a divergence,
            or where a failure stopped it); None before, or when the game was never built.
        diverged: Once the report is settled, whether the replay diverged
            (``ReplayReport.is_failure``): a frame differed, or the run ended before the
            recording did (``ReplaySources.finish_run`` makes that a length divergence; the
            state is then ``FAILED``). False when it matched; None while ``report`` is None.
        error: The failure's text when ``state`` is ``FAILED``, else None.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    state: InnerGameState
    frames_run: int
    report: str | None
    diverged: bool | None
    error: str | None


class InnerGameRefusedError(ValueError):
    """The arguments ask for something other than a headless replay (rule 1)."""


class InnerGameStartError(RuntimeError):
    """The command could not be started inside the context; its message is the outcome's error."""


def refused_arguments(*, arguments: Sequence[str]) -> list[str]:
    """Return the arguments an inner game refuses (rule 1), each once, in the order given.

    Args:
        arguments: The game's arguments, after the replay's own.

    Returns:
        The refused arguments as given (empty when every one may run inner).

    """
    refused: list[str] = []
    for argument in arguments:
        if argument == ARGUMENTS_SEPARATOR:
            break
        if is_refused_argument(argument=argument) and argument not in refused:
            refused.append(argument)
    return refused


def is_refused_argument(*, argument: str) -> bool:
    """Tell whether one argument is a refused flag, or a prefix argparse would read as one.

    Args:
        argument: One command-line argument (``--audit``, ``--record-trace=PATH``, ``-ph``).

    Returns:
        True when argparse could take it for a refused flag.

    """
    if argument.startswith(LONG_FLAG_PREFIX):
        name = argument.split(INLINE_VALUE_SEPARATOR, maxsplit=1)[0]
        return any(flag.startswith(name) for flag in REFUSED_FLAGS)
    if argument.startswith(SHORT_FLAG_PREFIX):
        return is_refused_short_flag_cluster(cluster=argument[len(SHORT_FLAG_PREFIX) :])
    return False


def is_refused_short_flag_cluster(*, cluster: str) -> bool:
    """Tell whether a short-flag cluster holds a refused letter before any value starts.

    Argparse reads ``-ph`` as ``-p -h``, and ``-fp`` as ``-f p`` (``-f`` takes a value, the rest
    of the argument). A letter after one of ``SHORT_FLAGS_TAKING_A_VALUE`` is part of its value.

    Args:
        cluster: The argument without its leading ``-`` (``ph``).

    Returns:
        True when argparse could read a refused short flag in it.

    """
    for letter in cluster:
        if letter in REFUSED_SHORT_FLAG_LETTERS:
            return True
        if letter in SHORT_FLAGS_TAKING_A_VALUE:
            return False
    return False


def describe_failure(*, error: BaseException) -> str:
    """Describe what failed an inner game, for its outcome and the log.

    Args:
        error: The contained exception or SystemExit.

    Returns:
        ``the game exited with UNUSABLE_INPUT (65)`` for an exit with a status,
        ``the game exited with SystemExit('...')`` for one without, an ``InnerGameStartError``'s
        message alone, else ``<Type>: <message>``.

    """
    if isinstance(error, InnerGameStartError):
        return str(error)
    if isinstance(error, SystemExit):
        if isinstance(error.code, int):
            return f'the game exited with {ExitCode.describe_status(error.code)}'
        return f'the game exited with SystemExit({error.code!r})'
    return f'{type(error).__name__}: {error}'


class InnerGame:
    """One game replayed inside its own engine context, stepped by its host (the module's rules).

    Made by ``InnerGame.replay``. Every call switches to the inner game's context for its work
    and back, so the caller's context is current again afterwards.
    """

    def __init__(
        self: Self, *, command: str, command_line: Sequence[str], name: str, size: tuple[int, int]
    ) -> None:
        """Build the game in a fresh context; use ``InnerGame.replay``, which refuses first.

        Args:
            command: The installed command (console script) whose entry point starts the game.
            command_line: ``sys.argv`` while the entry point runs (the command first).
            name: The context's name.
            size: The render target's size.

        """
        self._command = command
        self._context = EngineContext(name=name)
        self._surface = pygame.Surface(size)
        self._engine: GameEngine | None = None
        self._frame_start_seconds = 0.0
        self._frames_run = 0
        self._state = InnerGameState.RUNNING
        self._report: str | None = None
        self._diverged: bool | None = None
        self._error: str | None = None
        # What ended the run early (the failure, described), for the replay's report
        self._run_ended_by: str | None = None
        self._finished = False
        with self._context.active():
            try:
                engine = self._build(command_line=command_line)
            except CONTAINED_ERRORS as error:
                self._fail(error=error)
                self._forget_a_half_built_engine()
                self._finished = True
                return
            self._engine = engine
            try:
                self._frame_start_seconds = engine.scene_manager.begin_frames()
            except CONTAINED_ERRORS as error:
                self._fail(error=error)
                began_its_frames = False
            else:
                began_its_frames = True
        if not began_its_frames:
            # The engine was built: its run is finished as any other (rule 4)
            self.finish()

    @classmethod
    def replay(
        cls,
        *,
        command: str,
        path: Path,
        name: str,
        size: tuple[int, int],
        arguments: Sequence[str] = (),
    ) -> InnerGame:
        """Replay a recording headless through a game's own command, inside its own context.

        Args:
            command: The installed command (console script) that starts the game.
            path: The recording.
            name: The context's name.
            size: The render target's size (a replay is refused at another size than recorded:
                the outcome is then ``FAILED``).
            arguments: More arguments for the game, after ``--replay-trace PATH --headless``.

        Returns:
            The inner game, built up to its first frame, or ``FAILED`` if that failed.

        Raises:
            InnerGameRefusedError: If an argument asks for anything but a headless replay
                (nothing is built).

        """
        refused = refused_arguments(arguments=arguments)
        if refused:
            message = (
                f'{", ".join(refused)} cannot run inside another game: an inner game only '
                'replays a recording headless'
            )
            raise InnerGameRefusedError(message)
        return cls(
            command=command,
            command_line=[command, '--replay-trace', str(path), '--headless', *arguments],
            name=name,
            size=size,
        )

    @property
    def context(self: Self) -> EngineContext:
        """The inner game's engine context."""
        return self._context

    @property
    def surface(self: Self) -> pygame.Surface:
        """What the game draws on: its context's render target (opaque after every frame)."""
        return self._surface

    @property
    def outcome(self: Self) -> InnerGameOutcome:
        """How the game stands, or how it ended."""
        return InnerGameOutcome(
            state=self._state,
            frames_run=self._frames_run,
            report=self._report,
            diverged=self._diverged,
            error=self._error,
        )

    def step(self: Self) -> bool:
        """Run one frame inside the game's context; finish it when that frame ended it.

        Returns:
            True while the game goes on; False once it has ended or failed (it is finished).

        """
        if self._finished:
            return False
        engine = self._engine
        assert engine is not None  # a game not finished was built
        with self._context.active():
            scene_manager = engine.scene_manager
            try:
                self._frame_start_seconds = scene_manager.run_frame_step(
                    frame_start_seconds=self._frame_start_seconds, paced=False
                )
                self._frames_run += 1
                still_running = scene_manager.should_run_frames()
            except CONTAINED_ERRORS as error:
                self._fail(error=error)
                still_running = False
        if not still_running:
            self.finish()
        return still_running

    def finish(self: Self) -> InnerGameOutcome:
        """End the game's run inside its context and settle its replay's result (idempotent).

        As the engine's teardown does for its own run (``GameEngine._shut_down_the_run``), each
        part runs even when one before it failed: the frames end, any recording closes, the
        timer gives back what it holds and the replay's result is settled into the outcome. It
        never quits pygame, restores signal handlers or driver variables, or exits. The engine
        then stops being its context's current engine.

        Returns:
            The outcome: ``ENDED`` with the replay's report, or ``FAILED``.

        """
        if self._finished:
            return self.outcome
        self._finished = True
        engine = self._engine
        assert engine is not None  # a game not finished was built
        with self._context.active():
            for finish_part in (
                self._end_frames,
                self._stop_trace_recording,
                self._close_timer,
                self._settle_replay_report,
            ):
                try:
                    finish_part(engine=engine)
                except CONTAINED_ERRORS as error:
                    self._fail(error=error)
            self._forget_a_half_built_engine()
        self._engine = None
        if self._state is InnerGameState.RUNNING:
            self._state = InnerGameState.ENDED
        return self.outcome

    def _build(self: Self, *, command_line: Sequence[str]) -> GameEngine:
        """Call the command's entry point in this (current) context and take its engine.

        Args:
            command_line: ``sys.argv`` while the entry point runs.

        Returns:
            The engine the hosted start built.

        Raises:
            InnerGameStartError: If no installed command has the name, or its entry point
                started no engine here.

        """
        try:
            entry_point = game_entry_point(console_script=self._command)
        except KeyError:
            message = f'no installed command is named {self._command!r}'
            raise InnerGameStartError(message) from None
        # In the display's format, as the window's surface would be (on cocoa: an alpha mask
        # without SRCALPHA, which each frame's make_opaque handles; BUGS.md #142)
        self._surface = self._surface.convert()
        set_render_target(surface=self._surface)
        private_event_queue().enabled = True
        start_game = entry_point.load()
        # argparse reads sys.argv, one per process: the replay's command line for this call
        # only (decision 7); frame steps never read it
        outer_arguments = sys.argv
        sys.argv = list(command_line)
        try:
            start_game()
        finally:
            sys.argv = outer_arguments
        engine = take_started_engine()
        if engine is None:
            message = f'{self._command} started no game engine in its context'
            raise InnerGameStartError(message)
        return engine

    def _fail(self: Self, *, error: BaseException) -> None:
        """Make the outcome ``FAILED`` with the error, or log it when an earlier one did.

        Args:
            error: The contained exception or SystemExit (being handled).

        """
        description = describe_failure(error=error)
        # A traceback for an exception; an exit says what it is (the engine logged why)
        with_traceback = isinstance(error, Exception) and not isinstance(error, InnerGameStartError)
        if self._error is None:
            self._state = InnerGameState.FAILED
            self._error = description
            self._run_ended_by = description
            LOG.error(
                'Inner game %s failed: %s', self._context.name, description, exc_info=with_traceback
            )
        else:
            LOG.error(
                'Inner game %s failed again while finishing: %s',
                self._context.name,
                description,
                exc_info=with_traceback,
            )

    @staticmethod
    def _forget_a_half_built_engine() -> None:
        """Leave no engine current, or waiting for a host, in the current (inner) context."""
        take_started_engine()
        current_context().value(slot=CURRENT_ENGINE_SLOT).engine = None

    @staticmethod
    def _end_frames(*, engine: GameEngine) -> None:
        """End the run's frames: the scene manager logs why and tears its scenes down.

        Args:
            engine: The inner game's engine.

        """
        engine.scene_manager.end_frames()

    @staticmethod
    def _stop_trace_recording(*, engine: GameEngine) -> None:
        """Close any recording the run holds (none is ever asked for inner: rule 1).

        Args:
            engine: The inner game's engine.

        """
        engine.stop_trace_recording()

    @staticmethod
    def _close_timer(*, engine: GameEngine) -> None:
        """Give back what the run's timer holds (none when it failed to start).

        Args:
            engine: The inner game's engine.

        """
        if engine.timer is not None:
            engine.timer.close()

    def _settle_replay_report(self: Self, *, engine: GameEngine) -> None:
        """Settle the replay's result into the outcome's report and log it at INFO (rule 3).

        Args:
            engine: The inner game's engine.

        """
        replay_sources = engine.replay_sources
        assert replay_sources is not None  # an inner game always replays (--replay-trace)
        report = engine.settle_replay_report(
            replay_sources=replay_sources, run_ended_by=self._run_ended_by
        )
        self._report = report.text
        self._diverged = report.is_failure
        LOG.info('Inner game %s: %s', self._context.name, report.text)
