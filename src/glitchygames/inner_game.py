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

1. **Only recordings run inner, so far** (decision 5; a live game inside the Arcade is its
   sub-plan 7's). Every inner game replays a recording headless (``--replay-trace PATH
   --headless``; ``--headless`` is a switch no later argument can undo). It is given the outer
   game's command line next (the current engine's ``command_arguments``, up to a bare ``--``,
   less every refused flag below with its values: ``inherited_arguments``), so an Arcade run
   with ``--sound-cache ram`` or ``--log-level debug`` runs its tiles so, and one recording
   itself (``--record-trace``) or replayed (``--replay-trace``, its golden) still plays them;
   and the host's own arguments last, which win (argparse keeps the last value). A recording
   still overrides every option but its run-local ones (``replay.REPLAY_LOCAL_OPTIONS``). The
   host's own arguments that would do anything else are refused before anything is built
   (``InnerGameRefusedError``): every tool flag (live play, ``--record-trace`` and another
   ``--replay-trace`` among them), ``--rebaseline``, ``--audit``, ``--compare-trace`` and the
   frame stream, a watched replay's restart options, ``--profile`` and ``--list-input-devices``
   (a hosted start would ignore them silently), and ``--help`` and ``--version`` (each prints
   to stdout and exits), with their short forms ``-p``, ``-h`` and ``-v``. Argparse takes any
   unambiguous prefix of a long flag, so a prefix of a refused flag is refused too, unless it is
   an engine flag of its own (argparse takes an exact flag first: ``--sound-cache`` is the cache
   mode, though it begins ``--sound-cache-list``), and reads a short-flag cluster letter by
   letter (``-ph`` is ``-p -h``) until a letter that takes a value,
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
   is current again after every call. The mixer's channels are kept apart by rules 5 to 7 (Arcade
   sub-plan 4); still shared are ``pygame.mixer.music`` (no game uses it), SDL's key repeat,
   text input and cursor visibility and pygame's default font resolution
   (plans/future-work.md).
5. **A new inner game is silent** (plans/2026-11-13-arcade-4-sound.md, decisions 1 and 2): its
   context's audio route (glitchygames/audio/route.py) is made silent when the context is
   created, and its host switches it with ``set_audible``. While a silent inner game builds,
   steps or finishes, every mixer channel is reserved (``every_channel_reserved``), so its plain
   ``Sound.play()`` finds no free channel, returns None and starts nothing; the reservation is
   put back after each call, on every exit path. Sounds already playing (the heard game's) play
   on. An audible inner game's plain plays are heard.
6. **An inner game's channels come from its host's declaration** (decisions 4, 5 and 7): the
   host declares its inner games once, before anything plays (``INNER_GAMES`` on its scene
   class, which its engine declares at construction, or
   ``glitchygames.audio.reserve_inner_game_channels(games=...)`` after ``GameEngine(...)`` and
   before ``start()``, which has that engine partition first; never in ``setup()``, after the
   CRT power-on's sound started), and the mixer never grows again. An inner game's engine never
   partitions the mixer: its build takes a live pool for its live voices, and its sound
   library has its recording's ``--sound-channels`` as slots, played on one of two heard sets
   only while it is heard (``set_audible(audible=True)`` takes one; the sets alternate between
   heard games, the old one fading out on its set while the new one starts on the other). So a
   game's steals and drops are those of the game run alone. A build with none declared, or
   with every declared live pool held, fails alone (``InnerGameChannelsError``, naming the
   call); a game whose ``--sound-channels`` outnumber a heard set's channels replays silent,
   and ``set_audible(audible=True)`` refuses it. ``finish()`` makes it silent (``audible``
   reads False afterwards), stops its live voices, discards
   its context's audio engine (never ``release_channels``, the process's) and gives its heard
   set and live pool back; so does a build that failed, each part contained as the finish's.
   The host must call ``finish()`` on every inner game it drops before its end: nothing gives
   the channels back otherwise (no ``__del__``: when a collection would run is not the host's
   to choose), so a host looping tiles that drops them unfinished runs out of its declared
   live pools, and the failing build's error names the contexts still holding them.
7. **Only the heard game is heard** (decisions 1 and 6). Keeping one inner game heard is the
   host's job: the engine lets two be heard at once, one on each heard set (a host may make the
   next game heard before it silences the last, a crossfade), and refuses a third
   (``InnerGameChannelsError`` from ``set_audible(audible=True)``). While an inner game is
   audible its plain ``Sound.play()`` plays are heard on the unreserved channels, and
   followed: each build, step and finish notes the channels it started a sound on
   (``plain_plays_followed``: an unreserved channel playing another sound after the call than
   before it; the host runs no code inside the call). When it goes silent
   (``set_audible(audible=False)``, or its finish), its heard voices fade over 50 ms, the plain
   plays it started that still play that very sound are stopped, and the chunks on its live
   pool are muted. The host's own sounds, and
   another inner game's, are never stopped, even on a channel one of its sounds left, except
   when both play the very same ``Sound`` object (``plain_plays_followed``'s edge). A plain play
   the game starts after it went silent within the same call (its finish) is stopped as the
   call ends.
8. **A fast-forward is silent and sliced** (plans/2026-11-20-arcade-5-playback-core.md, decision
   8): ``fast_forward(to_frame=..., budget=...)`` steps the game toward a frame (an Arcade
   tile's poster frame) until it stands there or the budget (``replay.pacer.TickBudget``, real
   time a host may share among its players) is spent, at least one frame a call, and the next
   call goes on. It is refused while the game is audible (``InnerGameAudibleError``, naming
   ``set_audible(audible=False)``): a host silences the game first, so the burst of frames is
   never heard, and the fast-forward itself never switches the route or silences a frame (its
   steps reserve the mixer as every silent step does: rule 5). It only steps, so the frames are
   the recording's: frame ``to_frame`` is then the next step's, as in a replay run alone.

A recorded quit (every golden ends with its game's quit control) ends only its inner game:
the QUIT is posted to and drained from the context's private queue, never SDL's.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys
from enum import StrEnum
from typing import TYPE_CHECKING, Self

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames.audio.engine import discard_audio_engine
from glitchygames.audio.route import AUDIO_ROUTE_SLOT, set_audible
from glitchygames.audio.voices import (
    every_channel_reserved,
    give_back_heard_set,
    plain_plays_followed,
    release_inner_context_channels,
    take_heard_set,
)
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
from glitchygames.scenes.scene import release_live_voices_in_the_current_context

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence
    from pathlib import Path

    from glitchygames.engine.game_engine import GameEngine
    from glitchygames.replay.driver import RecordedFrames
    from glitchygames.replay.pacer import TickBudget

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
# argparse's nargs for a flag taking values until the next flag (--verify's and --measure's)
ANY_NUMBER_OF_VALUES = '*'
# The kinds of value count a refused flag has (argparse's nargs): none, one, or any number. A
# refused flag of another kind would be left out with the wrong number of values, so
# tests/engine/test_inner_game.py fails on one
FLAG_VALUE_COUNTS: frozenset[object] = frozenset({0, None, ANY_NUMBER_OF_VALUES})


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


class InnerGameStateError(RuntimeError):
    """The inner game is in a state its own code never reaches (a bug, not a game failure)."""


class InnerGameAudibleError(RuntimeError):
    """A fast-forward was asked of an audible inner game (it runs only silent: decision 8)."""


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
    engine_flags = engine_long_flags()
    for argument in arguments:
        if argument == ARGUMENTS_SEPARATOR:
            break
        if (
            is_refused_argument(argument=argument, engine_flags=engine_flags)
            and argument not in refused
        ):
            refused.append(argument)
    return refused


def inherited_arguments(*, command_arguments: Sequence[str]) -> tuple[str, ...]:
    """Return what an inner game is given of the outer game's command line (rule 1).

    Every argument up to a bare ``--`` (what follows it is the outer game's own positionals,
    never options, and passed on it would make the host's own arguments positionals too), less
    each refused flag with its values: those say how the outer run itself is recorded, replayed
    or watched (an Arcade recording itself), not how its tiles run. Its values are the count
    argparse gives the flag (``FLAG_VALUE_COUNTS``), none when it is inline (``--flag=value``);
    a short cluster keeps its other letters (``-wp`` is ``-w``).

    Args:
        command_arguments: The outer engine's command line, after the command.

    Returns:
        The arguments.

    """
    arguments = tuple(command_arguments)
    if ARGUMENTS_SEPARATOR in arguments:
        arguments = arguments[: arguments.index(ARGUMENTS_SEPARATOR)]
    actions = engine_option_actions()
    engine_flags = frozenset(flag for flag in actions if flag.startswith(LONG_FLAG_PREFIX))
    kept: list[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        index += 1
        if argument.startswith(LONG_FLAG_PREFIX):
            if not is_refused_argument(argument=argument, engine_flags=engine_flags):
                kept.append(argument)
            elif INLINE_VALUE_SEPARATOR not in argument:
                index = _after_the_values(
                    arguments=arguments,
                    index=index,
                    value_count=_refused_flag_value_count(name=argument, actions=actions),
                )
        elif argument.startswith(SHORT_FLAG_PREFIX) and len(argument) > len(SHORT_FLAG_PREFIX):
            cluster = _cluster_without_refused_letters(cluster=argument[len(SHORT_FLAG_PREFIX) :])
            if cluster:
                kept.append(f'{SHORT_FLAG_PREFIX}{cluster}')
        else:
            kept.append(argument)
    return tuple(kept)


def _refused_flag_value_count(*, name: str, actions: dict[str, argparse.Action]) -> object:
    """Return how many values argparse gives a refused flag (its ``nargs``), or its abbreviation.

    The outer game's argparse took the command line, so an abbreviation names one flag. A flag
    the engine does not define (a game's ``--version``) takes none.

    Returns:
        Its ``nargs``.

    """
    flag = name if name in REFUSED_FLAGS else min(f for f in REFUSED_FLAGS if f.startswith(name))
    action = actions.get(flag)
    return 0 if action is None else action.nargs


def _after_the_values(*, arguments: Sequence[str], index: int, value_count: object) -> int:
    """Return where the arguments after a flag's values start (``FLAG_VALUE_COUNTS``' kinds).

    Returns:
        The index.

    """
    if value_count == 0:
        return index
    if value_count == ANY_NUMBER_OF_VALUES:
        # argparse's rule: values until the next argument that looks like a flag
        while index < len(arguments) and not arguments[index].startswith(SHORT_FLAG_PREFIX):
            index += 1
        return index
    return min(index + 1, len(arguments))


def _cluster_without_refused_letters(*, cluster: str) -> str:
    """Return a short-flag cluster without its refused letters (``wp`` is ``w``).

    A letter taking a value takes the rest of the cluster as it (argparse's rule): kept whole.

    Returns:
        The letters kept, empty when none is.

    """
    kept: list[str] = []
    for position, letter in enumerate(cluster):
        if letter in SHORT_FLAGS_TAKING_A_VALUE:
            kept.append(cluster[position:])
            break
        if letter not in REFUSED_SHORT_FLAG_LETTERS:
            kept.append(letter)
    return ''.join(kept)


def engine_option_actions() -> dict[str, argparse.Action]:
    """Return the engine's own options (``GameEngine.args``), by each of their flags.

    Returns:
        Each flag (long and short) and its argparse action.

    """
    from glitchygames.engine.game_engine import GameEngine

    parser = GameEngine.args(argparse.ArgumentParser())
    # argparse keeps its actions here, and only here
    return {flag: action for action in parser._actions for flag in action.option_strings}


def engine_long_flags() -> frozenset[str]:
    """Return the engine's own long flags (``GameEngine.args``), each read as itself by argparse.

    Returns:
        The flags.

    """
    return frozenset(flag for flag in engine_option_actions() if flag.startswith(LONG_FLAG_PREFIX))


def is_refused_argument(*, argument: str, engine_flags: frozenset[str] | None = None) -> bool:
    """Tell whether one argument is a refused flag, or a prefix argparse would read as one.

    An exact engine flag is itself, never a prefix (argparse takes an exact flag first). A game's
    own flag is not known here, so one that is a prefix of a refused flag is refused anyway: a
    refusal too many, never one too few.

    Args:
        argument: One command-line argument (``--audit``, ``--record-trace=PATH``, ``-ph``).
        engine_flags: The engine's long flags (``engine_long_flags``; None reads them).

    Returns:
        True when argparse could take it for a refused flag.

    """
    if argument.startswith(LONG_FLAG_PREFIX):
        name = argument.split(INLINE_VALUE_SEPARATOR, maxsplit=1)[0]
        if name in REFUSED_FLAGS:
            return True
        if name in (engine_long_flags() if engine_flags is None else engine_flags):
            return False
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
        # What it replays, kept after the engine is gone so a finished game still answers
        self._recording: RecordedFrames | None = None
        self._state = InnerGameState.RUNNING
        self._report: str | None = None
        self._diverged: bool | None = None
        self._error: str | None = None
        # What ended the run early (the failure, described), for the replay's report
        self._run_ended_by: str | None = None
        self._finished = False
        with self._context.active():
            # Silent from its creation (rule 5): keeping one inner game heard is its host's job
            set_audible(audible=False)
        with self._context.active(), self._plain_plays_kept_off_the_mixer():
            try:
                engine = self._build(command_line=command_line)
            except CONTAINED_ERRORS as error:
                self._fail(error=error)
                self._forget_a_half_built_engine()
                # A build that failed after its engine took its channels (rule 6)
                self._release_the_audio()
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
            arguments: More arguments for the game, after ``--replay-trace PATH --headless`` and
                the outer game's command line (``inherited_arguments``), so these win (argparse
                keeps the last value given).

        Returns:
            The inner game, built up to its first frame, or ``FAILED`` if that failed.

        Raises:
            InnerGameRefusedError: If an argument, the outer game's or these, asks for anything
                but a headless replay (nothing is built).

        """
        outer_engine = current_context().value(slot=CURRENT_ENGINE_SLOT).engine
        outer = (
            ()
            if outer_engine is None
            else inherited_arguments(command_arguments=outer_engine.command_arguments)
        )
        arguments = (*outer, *arguments)
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
    def audible(self: Self) -> bool:
        """Whether the game's sound is heard (False from its creation: rule 5)."""
        return self._context.value(slot=AUDIO_ROUTE_SLOT).audible

    def set_audible(self: Self, *, audible: bool) -> None:
        """Make the game's sound heard or silent (its context's audio route; rules 5 to 7).

        Heard, it takes a heard set to play its sound library on; silent, its heard voices fade
        out on that set over 50 ms and it gives the set back, and its plain ``Sound.play()``
        sounds still playing are stopped and its live chunks muted (rule 7). A game that cannot
        be heard (rule
        6: finished, its ``--sound-channels`` outnumbering a heard set's channels, or two inner
        games heard already) is refused with ``InnerGameChannelsError`` and nothing changes.

        Args:
            audible: True to hear the game, False to keep its sound off the mixer.

        """
        with self._context.active():
            if audible:
                # Refused (InnerGameChannelsError) before anything changes when it cannot be heard
                take_heard_set()
                set_audible(audible=True)
            else:
                # Its heard voices fade out on its heard set, which it then gives back
                set_audible(audible=False)
                give_back_heard_set()

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

    @property
    def frame_count(self: Self) -> int:
        """How many frames the recording holds (0 when the game never got as far as reading it)."""
        recording = self._replayed_recording()
        return 0 if recording is None else recording.frame_count

    @property
    def frame_index(self: Self) -> int:
        """The next frame to run: the frames run so far (``outcome.frames_run``)."""
        return self._frames_run

    @property
    def next_frame_seconds(self: Self) -> float:
        """How long the frame starting now lasted when recorded (``ReplaySources`` rule 4).

        The next frame's recorded ``dt`` (the duration of this one), the current frame's for the
        last, 0.0 past the end or when there is no recording. It is how a host that paces this
        game (``RecordedFramePacer``) learns what the next frame is owed.
        """
        recording = self._replayed_recording()
        if recording is None:
            return 0.0
        return recording.next_frame_seconds(frame_index=self._frames_run)

    def _replayed_recording(self: Self) -> RecordedFrames | None:
        """Return the recording the game replays: its engine's while running, else the kept one.

        Returns:
            The recorded frames, or None when the game never got as far as reading them.

        """
        engine = self._engine
        if engine is not None and engine.replay_sources is not None:
            return engine.replay_sources.recording
        return self._recording

    def _unfinished_engine(self: Self) -> GameEngine:
        """Return the engine of a game that is not finished (one that was not finished was built).

        Returns:
            The inner game's engine.

        Raises:
            InnerGameStateError: If the game has no engine though it is not finished.

        """
        engine = self._engine
        if engine is None:
            message = f'Inner game {self._context.name} is not finished but has no engine'
            raise InnerGameStateError(message)
        return engine

    def step(self: Self) -> bool:
        """Run one frame inside the game's context; finish it when that frame ended it.

        Returns:
            True while the game goes on; False once it has ended or failed (it is finished).

        """
        if self._finished:
            return False
        engine = self._unfinished_engine()
        with self._context.active(), self._plain_plays_kept_off_the_mixer():
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

    def fast_forward(self: Self, *, to_frame: int, budget: TickBudget) -> bool:
        """Run frames toward ``to_frame``, silent, until there or the budget is spent (rule 8).

        Runs frames ``[frame_index, to_frame)`` one ``step()`` each, checking the budget after
        each frame: at least one frame runs a call, so a host passing a spent budget (one
        another player used up) still moves on, and none runs past ``to_frame``. The next call
        goes on from where this one stopped. A divergence or a failure on the way ends the game
        with that outcome, as a step does. Once it returns True, frame ``to_frame`` is the next
        ``step()``'s, and the frames are those of the recording replayed alone: it only steps.
        A game already at or past ``to_frame`` runs nothing.

        Args:
            to_frame: The frame to stand at (the next to run), less than ``frame_count``.
            budget: The real time it may take (``glitchygames.replay.pacer.TickBudget``),
                possibly shared with other players: it decides how many frames run now, never
                what they do.

        Returns:
            True when the game is running and stands at or past ``to_frame``; False when the
            budget was spent first (call again), or the game has ended or failed (``outcome``
            says how; it never gets there).

        Raises:
            InnerGameAudibleError: If the game is audible: its frames would be heard, a burst
                of them at once (its host calls ``set_audible(audible=False)`` first). Nothing
                runs.
            ValueError: If ``to_frame`` is negative, or not less than the recording's frame
                count. Nothing runs.

        """
        if self.audible:
            message = (
                f'Inner game {self._context.name} is audible: a fast-forward runs silent, so '
                'call set_audible(audible=False) first'
            )
            raise InnerGameAudibleError(message)
        frame_count = self.frame_count
        if not 0 <= to_frame < frame_count:
            message = (
                f'Inner game {self._context.name} cannot fast-forward to frame {to_frame}: '
                f'the frame must be at least 0 and less than the frame count ({frame_count})'
            )
            raise ValueError(message)
        while self._frames_run < to_frame:
            if not self.step():
                return False
            if budget.is_spent:
                break
        return not self._finished and self._frames_run >= to_frame

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
        engine = self._unfinished_engine()
        self._finished = True
        with self._context.active(), self._plain_plays_kept_off_the_mixer():
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
            self._release_the_audio()
            self._forget_a_half_built_engine()
        self._engine = None
        if self._state is InnerGameState.RUNNING:
            self._state = InnerGameState.ENDED
        return self.outcome

    @contextlib.contextmanager
    def _plain_plays_kept_off_the_mixer(self: Self) -> Generator[None]:
        """Reserve every mixer channel for the body while the game is silent (rules 5 and 7).

        Each build, step and finish runs inside it. One inside another (an inner game stepping
        its own inner game) is a nested ``every_channel_reserved``, which leaves the outermost's
        reservation in place, so the reservation put back is always the host's. While the game
        is audible its plain plays are heard, and followed instead (``plain_plays_followed``),
        so going silent stops them (rule 7).

        Yields:
            Nothing; a silent game's plain ``Sound.play()`` finds no channel in the body.

        """
        if self.audible:
            with plain_plays_followed():
                yield
            return
        with every_channel_reserved():
            yield

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

        Raises:
            InnerGameStateError: If the engine has no replay sources (an inner game always
                replays).

        """
        replay_sources = engine.replay_sources
        if replay_sources is None:
            message = f'Inner game {self._context.name} has no replay sources (--replay-trace)'
            raise InnerGameStateError(message)
        report = engine.settle_replay_report(
            replay_sources=replay_sources, run_ended_by=self._run_ended_by
        )
        self._recording = replay_sources.recording
        self._report = report.text
        self._diverged = report.is_failure
        LOG.info('Inner game %s: %s', self._context.name, report.text)

    def _release_the_audio(self: Self) -> None:
        """Go silent, stop the live voices, discard the audio engine, give the channels back.

        Rule 6. Going silent first fades a heard game's voices on its heard set over 50 ms, and
        ``audible`` then reads False: a finished game holds no heard set. Each part runs even
        when one before it failed, as the finish's parts do; a failure is the inner game's
        (rule 2). Called inside the inner game's context.
        """
        for release_part in (
            self._go_silent,
            release_live_voices_in_the_current_context,
            self._discard_the_audio_engine,
            release_inner_context_channels,
        ):
            try:
                release_part()
            except CONTAINED_ERRORS as error:
                self._fail(error=error)

    @staticmethod
    def _go_silent() -> None:
        """Turn the context's route silent: its heard voices fade out on its heard set (rule 6)."""
        set_audible(audible=False)

    @staticmethod
    def _discard_the_audio_engine() -> None:
        """Close and forget the context's audio engine, waiting for no fade (rule 6).

        Its voices fade over 50 ms where they were heard; a silent context's touch no channel.
        Never ``release_channels``: the reservation is the process's, not this game's.
        """
        discard_audio_engine(wait_seconds=0.0)
