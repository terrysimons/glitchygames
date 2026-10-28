"""The game-frame clock: the frames a game's own logic ran in, a pause screen's left out.

The onion skin (``--compare-trace OLD``, glitchygames/replay/tools/compare.py, rule 11) pairs a
run's frames with OLD's by this clock, not by the frame number a recording counts, so pausing
the game freezes OLD's frame (the user, 2026-10-27: "Yes, the games should pause.").

1. **A game frame** is a frame whose logic ran on a scene that presents itself. A pause screen
   presents another scene (``Scene.debug_subject`` is the paused scene: ``PauseScene``), so a
   frame whose logic ran on it is no game frame. The scene is the one active as the frame's
   logic begins (``SceneManager._run_frame_steps``), not the one active as it ends: pausing
   (``Scene.pause``) switches after the frame renders, so the frame that paused ran the game's
   logic; resuming switches while the pause screen's events are handled, so the frame that
   resumed ran the pause screen's. A frame with no scene logic (a transition's) counts as a
   game frame: nothing is paused in it.
2. **The frame shown** (``shown_game_frame``): from the top of a game frame, its own number
   (game frames counted from 0); through the frames that are not, the last game frame's; None
   before the first game frame. It is set as each frame begins and holds until the next one
   begins, so live play (which presents a frame before it ends) and a watched replay (which
   presents it after) read the same number for the same frame.
3. **Recordings are unchanged**: they still count every frame. Only the onion skin's pairing
   reads this clock. A replay runs the same scenes' logic on the same frames, so it counts the
   same game frames as the run it replays, as OLD's child does for OLD.
4. **One clock per engine context** (``GAME_FRAME_CLOCK_SLOT``), started afresh by each run
   (``SceneManager.begin_run``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from glitchygames.engine_context import ContextSlot, current_context

if TYPE_CHECKING:
    from glitchygames.scenes import Scene


class GameFrameClock:
    """Counts a run's game frames (rule 1) and says which one each frame shows (rule 2).

    Attributes:
        game_frames_begun: How many game frames have begun.
        shown_game_frame: The game frame the frame running now (or last run) shows, or None.
        is_game_frame: Whether the frame running now (or last run) is a game frame.

    """

    def __init__(self: Self) -> None:
        """Start before any frame."""
        self.game_frames_begun = 0
        self.shown_game_frame: int | None = None
        self.is_game_frame = False

    def begin_frame(self: Self, *, logic_scene: Scene | None) -> None:
        """Begin a frame whose logic runs on ``logic_scene`` (None: a frame without scene logic).

        Args:
            logic_scene: The scene active as the frame's logic begins.

        """
        self.is_game_frame = logic_scene is None or logic_scene.debug_subject is logic_scene
        if self.is_game_frame:
            self.shown_game_frame = self.game_frames_begun
            self.game_frames_begun += 1


# Each engine context's clock (glitchygames.engine_context)
GAME_FRAME_CLOCK_SLOT: ContextSlot[GameFrameClock] = ContextSlot(
    name='glitchygames.game_frames.clock', factory=GameFrameClock
)


def game_frame_clock() -> GameFrameClock:
    """Return this engine context's game-frame clock.

    Returns:
        The clock.

    """
    return current_context().value(slot=GAME_FRAME_CLOCK_SLOT)


def restart_game_frame_clock() -> GameFrameClock:
    """Start this engine context's game-frame clock afresh (a new run: rule 4).

    Returns:
        The new clock.

    """
    return current_context().reset_value(slot=GAME_FRAME_CLOCK_SLOT)
