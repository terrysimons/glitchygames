"""One recorded game for a host's tile: it loops, fast-forwards and paces itself.

An outer game (the Arcade; plans/2026-10-23-arcade-showcase.md) shows recorded demos of other
games in tiles. A ``DemoPlayer`` owns one tile's demo: an ``InnerGame`` replaying a recording
through its game's own command (glitchygames/inner_game.py, whose rules and refusals it
inherits), a ``RecordedFramePacer`` that owes its frames from the time the host serves, and its
outcome (plans/2026-11-20-arcade-5-playback-core.md, decisions 4 to 13). It needs no game and
no Arcade: any outer host can hold one.

The rules:

1. **The host's time pays, a shared budget limits** (decision 5). ``tick(elapsed_seconds=...,
   budget=...)`` pays the pacer the real time since the player's last tick (the host's frame
   time; the player reads no clock) and runs the frames the pacer allows while the budget
   (``replay.pacer.TickBudget``, real time read from its own injected clock) lasts; it returns
   how many ran. A host passes one budget to its players in turn, so what one leaves the next
   gets. Frames are never skipped: a player that cannot keep up plays in slow motion
   (``is_behind``, ``effective_speed``), and owed time is dropped only past the pacer's owed
   limit, so a stalled host does not make its tiles burst. The budget is real time, so how far
   a tile has got after a given host frame depends on the machine: a recorded Arcade session
   replays its inputs, never its tiles' progress frame for frame (the owner's decision 5).
   Everything is synchronous: nothing awaits inside a tick. A host sharing a budget too small
   for every player's owed frames gives each at most one frame a turn (``most_frames=1``) and
   starts each tick with the player after the last one that ran: otherwise a player that fell
   behind takes the whole budget to catch up while the others wait for theirs (decision 3's
   reason; tests/test_demo_player.py measures it).
2. **A demo's end loops it** (decision 6). When the game ends matched, its ``InnerGame`` is
   already finished (it gives its channels back: rule 6 of inner_game.py) and a new one is built
   from the same command and recording, in a new context, from frame 0. ``on_new_game`` runs on
   each new game before its first frame (the first one's included), and ``generation`` counts
   the games built. After a tick that looped, the outcome reads ``LOOPED``, and ``PLAYING`` from
   the next tick on.
3. **A build is charged to the budget** (decision 7). A loop's build is one indivisible call: it
   is made when the player's turn comes and the budget is not already spent (otherwise on a
   later tick), and the real time it takes is gone from the budget the next players share.
4. **A divergence restarts once, then freezes** (the owner's decision 4). The first divergence a
   player meets (a frame that differs, or a recording longer than the run) is logged and the
   game rebuilt from frame 0 (until that rebuild, which may wait for a later tick's budget, the
   player reads ``PLAYING``, with the divergence's report); the second freezes it with
   ``DIVERGED``, logged, on the diverged frame. A frozen player (``DIVERGED``, ``CRASHED`` or
   ``COULD_NOT_START``) runs nothing more, and its last frame stays readable on ``surface``.
5. **Fast-forward is silent, sliced and resumable** (decision 8): ``fast_forward(to_frame=...,
   budget=...)`` is the current game's (``InnerGame.fast_forward``), so it is refused while the
   player is audible and frame ``to_frame`` is then the next tick's. A player with no running
   game (frozen, never started, or waiting to loop) reaches no frame: False. A divergence on
   the way is the player's (rule 4). ``poster_frame`` chooses where a tile's demo starts.
6. **Silent by default, and the setting is the player's** (decision 11). A new player is silent;
   ``set_audible`` switches the current game, and a looped game gets the player's setting
   before its first frame, so a heard tile stays heard across its loop. A looped game that
   cannot be heard (``InnerGameChannelsError``) plays silent and the player's setting turns
   silent, logged. Keeping one player heard is the host's job (rule 7 of inner_game.py).
7. **The surface is the current game's render target** (decision 12): a new surface after each
   loop, so a host reads it every frame and never keeps it; None when no game was ever built.
8. **The recording's size comes from its header** (decision 13), read once at construction; a
   recording that is missing, unreadable or without a screen size is ``COULD_NOT_START``, and
   so is a build that failed or a game refused (``InnerGameRefusedError``), each with its
   reason as the outcome's ``error``.
9. **The host finishes a player it drops** (``finish()``): its game is finished and gives its
   channels back; nothing gives them back otherwise (rule 6 of inner_game.py).
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict

from glitchygames.audio.voices import InnerGameChannelsError
from glitchygames.inner_game import InnerGame, InnerGameRefusedError, InnerGameState
from glitchygames.replay.driver import recorded_screen_size
from glitchygames.replay.pacer import RecordedFramePacer
from glitchygames.tracing import TraceReader

if TYPE_CHECKING:
    import random
    from collections.abc import Callable, Sequence
    from pathlib import Path

    import pygame

    from glitchygames.replay.pacer import TickBudget

LOG = logging.getLogger('game.demo_player')

# A demo plays at the speed it was recorded at
DEMO_SPEED = 1.0
# The span of a recording a poster frame is drawn from (decision 9): a demo's first frames are
# often a still title, its last a quit tail
POSTER_SPAN_START_FRACTION = 0.1
POSTER_SPAN_END_FRACTION = 0.9
# How many divergences a player meets before it freezes (the owner's decision 4: one restart)
DIVERGENCES_BEFORE_FREEZING = 2


class DemoState(StrEnum):
    """Where a demo player is (decision 10)."""

    PLAYING = 'playing'
    COULD_NOT_START = 'could not start'
    CRASHED = 'crashed'
    DIVERGED = 'diverged'
    LOOPED = 'looped'


class DemoOutcome(BaseModel):
    """How a demo player stands (read-only), for the host's label.

    Attributes:
        state: Playing, looped this tick, or frozen (could not start, crashed, diverged).
        error: Why it could not start or crashed; None otherwise.
        report: The last game's replay report once it ended (a divergence's says where); None
            before.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    state: DemoState
    error: str | None
    report: str | None


def poster_frame(*, frame_count: int, stream: random.Random) -> int:
    """Return a frame drawn uniformly from a recording's 10% to 90% span (decision 9).

    A pure function of the stream the caller passes (the Arcade's named stream), so the same
    seed gives the same frames.

    Args:
        frame_count: How many frames the recording holds.
        stream: The random stream to draw from.

    Returns:
        A frame index, less than ``frame_count`` (0 for a one-frame recording).

    Raises:
        ValueError: If the recording holds no frame.

    """
    if frame_count < 1:
        message = f'A recording of {frame_count} frames has no frame to show as its poster'
        raise ValueError(message)
    first = int(frame_count * POSTER_SPAN_START_FRACTION)
    last = max(first, int(frame_count * POSTER_SPAN_END_FRACTION))
    return stream.randint(first, min(last, frame_count - 1))


class DemoPlayer:
    """One recording replayed as an inner game, looped and paced for a tile (module rules).

    A plain class, not a data model: its state changes every frame of every tile.
    """

    def __init__(
        self: Self,
        *,
        command: str,
        recording: Path,
        nominal_tick_seconds: float,
        arguments: Sequence[str] = (),
        on_new_game: Callable[[InnerGame], None] | None = None,
    ) -> None:
        """Read the recording's size and build its first game (rule 8).

        Args:
            command: The installed command (console script) that replays it.
            recording: The recording.
            nominal_tick_seconds: The host's frame period (the pacer's tick).
            arguments: More arguments for each game (``InnerGame.replay``'s), after the replay's
                own and the outer game's.
            on_new_game: Called with each new game before its first frame (rule 2).

        """
        self._command = command
        self._recording = recording
        self._arguments = tuple(arguments)
        # Its games' contexts and its log lines are named after its demo
        self._name = f'{command}/{recording.name}'
        self._on_new_game = on_new_game
        self._pacer = RecordedFramePacer(nominal_tick_seconds=nominal_tick_seconds)
        self._inner_game: InnerGame | None = None
        self._generation = 0
        self._frames_of_earlier_games = 0
        self._divergences = 0
        self._wants_audible = False
        self._state = DemoState.PLAYING
        self._error: str | None = None
        self._report: str | None = None
        # Nothing more runs: could not start, crashed, diverged twice, or finished
        self._frozen = False
        # The game ended (matched, or its first divergence): a new one is built on its turn
        self._needs_new_game = False
        self._size = self._recorded_size()
        if self._size is not None:
            self._start_new_game()

    @property
    def name(self: Self) -> str:
        """What its games' contexts and its log lines call it: ``command/recording-file``."""
        return self._name

    @property
    def outcome(self: Self) -> DemoOutcome:
        """How the player stands."""
        return DemoOutcome(state=self._state, error=self._error, report=self._report)

    @property
    def generation(self: Self) -> int:
        """How many games were built (0 when the recording could not be read)."""
        return self._generation

    @property
    def inner_game(self: Self) -> InnerGame | None:
        """The current game (finished once frozen); None when none was ever built."""
        return self._inner_game

    @property
    def surface(self: Self) -> pygame.Surface | None:
        """The current game's render target, read every frame (rule 7); None without a game."""
        return None if self._inner_game is None else self._inner_game.surface

    @property
    def frame_count(self: Self) -> int:
        """How many frames the recording holds (0 when no game got as far as reading it)."""
        return 0 if self._inner_game is None else self._inner_game.frame_count

    @property
    def frame_index(self: Self) -> int:
        """The current game's next frame (its frames run so far)."""
        return 0 if self._inner_game is None else self._inner_game.frame_index

    @property
    def frames_played(self: Self) -> int:
        """Every frame the player's games have run, across its loops (for a host's overlay)."""
        return self._frames_of_earlier_games + self.frame_index

    @property
    def is_behind(self: Self) -> bool:
        """True while its frames cannot keep up (the pacer's, over the last second)."""
        return self._pacer.is_behind

    def effective_speed(self: Self) -> float:
        """Return the speed its frames really ran at over the last second of ticks.

        Returns:
            Recorded seconds run over real seconds paid (0.0 before any were paid).

        """
        return self._pacer.effective_speed()

    @property
    def audible(self: Self) -> bool:
        """Whether the current game is heard (False without one, or once it finished)."""
        return self._inner_game is not None and self._inner_game.audible

    def set_audible(self: Self, *, audible: bool) -> None:
        """Make the player heard or silent, now and for its later games (rule 6).

        A current game that cannot be heard refuses it (``InnerGameChannelsError``, from
        ``InnerGame.set_audible``) and nothing changes.

        Args:
            audible: True to hear it.

        """
        game = self._running_game()
        if game is not None:
            game.set_audible(audible=audible)
        self._wants_audible = audible

    def tick(
        self: Self, *, elapsed_seconds: float, budget: TickBudget, most_frames: int | None = None
    ) -> int:
        """Pay the elapsed time and run the frames it owes while the budget lasts (rules 1 to 4).

        Args:
            elapsed_seconds: The real time since the player's last tick (the host's frame time).
            budget: The real time it may take, possibly shared with other players.
            most_frames: The most frames this tick may run (rule 1's fair share), or None for
                as many as the pacer owes and the budget allows. What it leaves is owed to the
                next ticks, never skipped.

        Returns:
            How many frames ran.

        """
        if self._state is DemoState.LOOPED:
            self._state = DemoState.PLAYING
        self._pacer.pay(
            elapsed_seconds=elapsed_seconds, speed=DEMO_SPEED, is_running=not self._frozen
        )
        frames_run = 0
        while not self._frozen:
            if most_frames is not None and frames_run >= most_frames:
                self._pacer.close_tick()
                break
            if self._needs_new_game:
                if budget.is_spent:
                    self._pacer.close_tick()
                    break
                self._start_new_game()
                continue
            game = self._current_game()
            if not self._pacer.should_run_frame(
                frame_seconds=game.next_frame_seconds, speed=DEMO_SPEED, budget=budget
            ):
                break
            frame_before = game.frame_index
            still_running = game.step()
            frames_run += game.frame_index - frame_before
            if not still_running:
                self._settle_the_end(game=game)
        else:
            self._pacer.close_tick()
        return frames_run

    def fast_forward(self: Self, *, to_frame: int, budget: TickBudget) -> bool:
        """Run the current game silently toward a frame until there or the budget is spent.

        Rule 5: ``InnerGame.fast_forward``'s contract, for a running game.

        Args:
            to_frame: The frame to stand at (the next tick's first), less than ``frame_count``.
            budget: The real time it may take, possibly shared with other players.

        Returns:
            True when the game stands at or past ``to_frame``; False when the budget was spent
            first (call again), or the player has no running game.

        """
        game = self._running_game()
        if game is None:
            return False
        reached = game.fast_forward(to_frame=to_frame, budget=budget)
        if game.outcome.state is not InnerGameState.RUNNING:
            self._settle_the_end(game=game)
        return reached

    def finish(self: Self) -> None:
        """Finish the current game, giving its channels back; nothing runs afterwards (rule 9)."""
        self._frozen = True
        self._needs_new_game = False
        if self._inner_game is not None:
            self._inner_game.finish()

    def _recorded_size(self: Self) -> tuple[int, int] | None:
        """Read the recording's screen size from its header (rule 8).

        Returns:
            The size, or None when the recording could not give one (the player could not
            start, with the reason).

        """
        try:
            with TraceReader(path=self._recording) as reader:
                size = recorded_screen_size(header=reader.header)
        except (OSError, ValueError) as error:
            self._could_not_start(reason=str(error))
            return None
        if size is None:
            self._could_not_start(reason=f'{self._recording} records no screen size')
        return size

    def _start_new_game(self: Self) -> None:
        """Build a new game from frame 0, with the player's setting, then call the hook.

        Raises:
            RuntimeError: If the recording's size is unknown (such a player is frozen).

        """
        self._needs_new_game = False
        size = self._size
        if size is None:  # pragma: no cover - a player whose size is unknown is frozen
            message = f'Demo {self._name} has no screen size, so it builds no game'
            raise RuntimeError(message)
        if self._inner_game is not None:
            self._frames_of_earlier_games += self._inner_game.frame_index
        try:
            game = InnerGame.replay(
                command=self._command,
                path=self._recording,
                name=f'{self._name} #{self._generation + 1}',
                size=size,
                arguments=self._arguments,
            )
        except InnerGameRefusedError as error:
            self._could_not_start(reason=str(error))
            return
        self._inner_game = game
        self._generation += 1
        if game.outcome.state is not InnerGameState.RUNNING:
            self._could_not_start(reason=game.outcome.error or 'the game ended as it was built')
            return
        if self._wants_audible:
            try:
                game.set_audible(audible=True)
            except InnerGameChannelsError as error:
                self._wants_audible = False
                LOG.warning('Demo %s plays silent: it cannot be heard (%s)', self._name, error)
        if self._on_new_game is not None:
            self._on_new_game(game)
        if self._generation > 1:
            self._state = DemoState.LOOPED

    def _settle_the_end(self: Self, *, game: InnerGame) -> None:
        """Decide what follows a game's end: a loop, one restart, or freezing (rules 2 and 4).

        Args:
            game: The game that ended (finished).

        """
        outcome = game.outcome
        self._report = outcome.report
        if outcome.state is InnerGameState.FAILED:
            self._frozen = True
            if outcome.frames_run == 0:
                self._state = DemoState.COULD_NOT_START
            else:
                self._state = DemoState.CRASHED
                LOG.warning(
                    'Demo %s crashed on frame %d and stays on its last frame: %s',
                    self._name,
                    outcome.frames_run,
                    outcome.error,
                )
            self._error = outcome.error
            return
        if outcome.diverged:
            self._divergences += 1
            if self._divergences >= DIVERGENCES_BEFORE_FREEZING:
                self._frozen = True
                self._state = DemoState.DIVERGED
                LOG.warning(
                    'Demo %s diverged again and is frozen on its diverged frame: %s',
                    self._name,
                    outcome.report,
                )
                return
            # DIVERGED means frozen: until its rebuild the player still reads PLAYING (the
            # report says where it diverged), so a host never shows the error label of a tile
            # that gets one more try
            LOG.warning('Demo %s diverged, restarting once: %s', self._name, outcome.report)
        self._needs_new_game = True

    def _could_not_start(self: Self, *, reason: str) -> None:
        """Freeze the player as ``COULD_NOT_START`` with the reason, logged."""
        self._frozen = True
        self._state = DemoState.COULD_NOT_START
        self._error = reason
        LOG.warning('Demo %s could not start: %s', self._name, reason)

    def _running_game(self: Self) -> InnerGame | None:
        """Return the current game while it runs.

        Returns:
            The game, or None when the player is frozen or waiting to build its next game.

        """
        if self._frozen or self._needs_new_game:
            return None
        return self._inner_game

    def _current_game(self: Self) -> InnerGame:
        """Return the current game of a player that is neither frozen nor waiting to loop.

        Returns:
            The game.

        Raises:
            RuntimeError: If it has none (a player that is not frozen always built one).

        """
        game = self._inner_game
        if game is None:  # pragma: no cover - a player that is not frozen built a game
            message = f'Demo {self._name} is not frozen but has no game'
            raise RuntimeError(message)
        return game
