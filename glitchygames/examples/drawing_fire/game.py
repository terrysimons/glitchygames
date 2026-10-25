"""Drawing Fire: a pencil-on-paper stick-figure battle.

This cut is the battlefield (paper, and the ground with its hills) and a battle the computer
plays, the winner announced and the next battle started on its own. Players join it at any time
(``seats``): START on the keyboard (Enter) or a controller chooses a side and takes over one of
its soldiers. ``drawing`` and ``seat_drawing`` draw it all in pencil.
"""

from __future__ import annotations

import enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

import pygame

from glitchygames.engine import GameEngine
from glitchygames.events import GAMEEVENT
from glitchygames.examples.drawing_fire.battle import (
    ARMY_NAMES,
    SOLDIERS_PER_SIDE,
    Battle,
    Side,
    SoldierKilled,
)
from glitchygames.examples.drawing_fire.drawing import (
    draw_banner,
    draw_bullet,
    draw_hud,
    draw_sandbag,
    draw_soldier,
    draw_terrain,
    load_soldier_frames,
)
from glitchygames.examples.drawing_fire.drivers import (
    ComputerSoldier,
    computer_intents,
    muster_battle,
)
from glitchygames.examples.drawing_fire.players import (
    KEYBOARD,
    ButtonEdges,
    connected_devices,
    device_intent,
)
from glitchygames.examples.drawing_fire.seat_drawing import (
    SEAT_TAG_ABOVE_FEET_PIXELS,
    SEAT_TAG_STAGGER_PIXELS,
    draw_join_prompt,
    draw_seat_card,
    draw_seat_tag,
    draw_seats_panel,
    draw_soldier_highlight,
)
from glitchygames.examples.drawing_fire.seats import (
    COMPUTER_DRIVER_NAME,
    SeatLogEntry,
    Seats,
    Stage,
)
from glitchygames.input.state import current_input
from glitchygames.randomness import random_stream
from glitchygames.recording import post_event
from glitchygames.scenes import Scene

if TYPE_CHECKING:
    from random import Random

    from glitchygames.camera import Camera2D
    from glitchygames.events.base import GameEvent, KeyEvent
    from glitchygames.examples.drawing_fire.players import Device
    from glitchygames.examples.drawing_fire.seats import PlayerSeat
    from glitchygames.examples.drawing_fire.terrain import Terrain

PAPER_COLOR = (251, 248, 239)
SOLDIER_SPRITE_PATH = Path(__file__).parent / 'sprites' / 'soldier.toml'
# How long the winner is announced before the next battle starts (s)
VICTORY_SECONDS = 3.0
SECONDS_PER_MINUTE = 60
PANEL_SEPARATOR = ' · '
# Drawing Fire's GAMEEVENT subtypes. The scene posts one (an internal event) for every soldier
# killed and every seat log entry, so a recording holds what happened in the battle and a replay
# in which it happens differently diverges ("missing internal event"): the soldiers are drawn,
# not sprites, so nothing else a replay compares would notice
SOLDIER_KILLED_SUBTYPE = 1
SEAT_CHANGED_SUBTYPE = 2
DRAWING_FIRE_EVENT_SUBTYPES = frozenset({SOLDIER_KILLED_SUBTYPE, SEAT_CHANGED_SUBTYPE})
# The soldier_id a seat change without a soldier carries (an event attribute is never None)
NO_SOLDIER_ID = -1
# The sign before the computer soldiers' count in the panel
COMPUTER_COUNT_MARK = '×'  # ruff: ignore[ambiguous-unicode-character-string] - intended


def seats_panel_lines(seats: Seats, battle: Battle) -> list[str]:
    """List the debug panel's lines: each army's drivers, then the seat log, newest last.

    An army line is its name, two spaces, then its players (a chooser or a waiting player marked)
    and its living computer soldiers: ``PLATOON  P1 · CPU`` and the count. An army with no
    computer soldiers shows only its players, one with no players only the computer count (a
    count of 0 when it has neither). A player who has not yet chosen a side is on no army's line.

    Args:
        seats: The players' seats and the seat log.
        battle: The battle, whose living soldiers are counted.

    Returns:
        The lines.

    """
    lines: list[str] = []
    for side in Side:
        parts = [
            _seat_label(seat) for _, seat in sorted(seats.players.items()) if seat.side is side
        ]
        computer_count = sum(
            1
            for soldier in battle.living(side)
            if seats.driver_of(soldier.soldier_id) == COMPUTER_DRIVER_NAME
        )
        if computer_count or not parts:
            parts.append(f'{COMPUTER_DRIVER_NAME} {COMPUTER_COUNT_MARK}{computer_count}')
        lines.append(f'{side.name}  {PANEL_SEPARATOR.join(parts)}')
    lines.extend(
        f'{int(entry.seconds) // SECONDS_PER_MINUTE}:'
        f'{int(entry.seconds) % SECONDS_PER_MINUTE:02d}  {entry.text}'
        for entry in seats.log
    )
    return lines


def _seat_label(seat: PlayerSeat) -> str:
    """Name a player for the panel, marking one who is not yet driving.

    Returns:
        The name, with (choosing) or (waiting) after it when he is not playing.

    """
    if seat.stage is Stage.CHOOSING_SOLDIER:
        return f'{seat.name} (choosing)'
    if seat.stage is Stage.WAITING:
        return f'{seat.name} (waiting)'
    return seat.name


class Phase(enum.Enum):
    """Where the scene is: fighting, or announcing the winner."""

    BATTLE = 'battle'
    VICTORY = 'victory'


class DrawingFireScene(Scene):
    """The battlefield: a sheet of paper with a hilly ground line."""

    NAME = 'Drawing Fire'
    VERSION = '0.1'
    # After a hitch (a window drag, focus loss) logic advances at most this much in one frame
    MAX_FRAME_SECONDS: ClassVar[float | None] = 0.05

    def __init__(
        self: Self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Build the battlefield: its paper and its seeded terrain.

        Args:
            options: Command-line options.
            groups: The sprite group (a new one when None).

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        super().__init__(options=options, groups=groups)
        self.background_color = PAPER_COLOR
        self.battle_number = 0
        self.phase = Phase.BATTLE
        self.victory_message = ''
        self.victory_seconds = 0.0
        # The soldier sprite, scaled once and recoloured once per army
        self.soldier_frames = load_soldier_frames(path=SOLDIER_SPRITE_PATH)
        self.walking_soldier_ids: set[int] = set()
        # The players: who sits where, from the seats' own stream (never a soldier's)
        self.seats = Seats(random=random_stream('drawing_fire.seats'))
        self.button_edges = ButtonEdges()
        # The devices plugged in at the latest tick (the keyboard is always there)
        self.devices: tuple[Device, ...] = (KEYBOARD,)
        self.start_battle()

    @override
    def setup(self: Self) -> None:
        """Register the scene's own game event subtypes with the engine.

        The scene manager hands every GAMEEVENT to the callback registered for its subtype (and
        logs an error for an unregistered one). The scene's posts are markers for recordings,
        so their callback does nothing.
        """
        super().setup()
        for subtype in sorted(DRAWING_FIRE_EVENT_SUBTYPES):
            self.scene_manager.register_game_event(event_type=subtype, callback=_take_marker)

    def start_battle(self: Self) -> None:
        """Start the next battle: new terrain, sandbags and soldiers from the seeded streams."""
        self.battle_number += 1
        battle, minds, streams = muster_battle(
            battle_number=self.battle_number,
            width=self.screen_width,
            height=self.screen_height,
            soldiers_per_side=SOLDIERS_PER_SIDE,
        )
        self.battle: Battle = battle
        self.terrain: Terrain = battle.terrain
        self.minds: dict[int, ComputerSoldier] = minds
        self.soldier_streams: dict[int, Random] = streams
        self.phase = Phase.BATTLE
        self.victory_message = ''
        self.victory_seconds = 0.0
        self.walking_soldier_ids = set()
        # The ground is pencilled onto clean paper, under every sprite (it never changes in a
        # battle, and LayeredDirty repaints the background, so it has to be on the background)
        self.background.fill(PAPER_COLOR)
        draw_terrain(self.background, self.terrain)
        # Joined players choose a soldier of their side again
        self.seats.battle_started(battle=self.battle)

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Seat the players, then play the battle (or count down the victory).

        Players' soldiers are driven by their devices, every other soldier by the computer.

        Args:
            dt: The seconds to advance.

        """
        super().dt_tick(dt)
        snapshot = current_input()
        self.button_edges.update(snapshot)
        self.devices = connected_devices(snapshot)
        self.seats.update(
            edges=self.button_edges,
            devices=self.devices,
            battle=self.battle,
            seconds=self.game_time,
        )
        if self.phase is Phase.BATTLE:
            # The computer thinks for every soldier, so a player's soldier's mind and stream stay
            # current and he is handed back cleanly; a player's intent then replaces its own
            intents = computer_intents(
                battle=self.battle, minds=self.minds, streams=self.soldier_streams
            )
            for seat in self.seats.players.values():
                if seat.stage is Stage.PLAYING and seat.soldier_id is not None:
                    soldier = self.battle.soldier(seat.soldier_id)
                    intents[seat.soldier_id] = device_intent(
                        device=seat.device,
                        snapshot=snapshot,
                        soldier_position=soldier.chest,
                        last_aim=soldier.aim_angle,
                    )
            walked_from = {soldier.soldier_id: soldier.x for soldier in self.battle.soldiers}
            events = self.battle.step(dt=dt, intents=intents)
            for event in events:
                if isinstance(event, SoldierKilled):
                    self._post_soldier_killed(event)
                    self.seats.soldier_killed(
                        soldier_id=event.soldier_id, battle=self.battle, seconds=self.game_time
                    )
            # A soldier whose x changed this step is walking
            self.walking_soldier_ids = {
                soldier.soldier_id
                for soldier in self.battle.soldiers
                if soldier.alive and soldier.x != walked_from[soldier.soldier_id]
            }
            winner = self.battle.winner
            if winner is not None:
                self.phase = Phase.VICTORY
                self.victory_message = f'{ARMY_NAMES[winner]} wins!'
        else:
            self.victory_seconds += dt
            if self.victory_seconds >= VICTORY_SECONDS:
                self.start_battle()
        for entry in self.seats.take_new_entries():
            _post_seat_changed(entry)

    def _post_soldier_killed(self: Self, event: SoldierKilled) -> None:
        """Post a soldier's death as an internal event: who he was, and who drove him.

        Args:
            event: The battle's report of the death.

        """
        soldier = self.battle.soldier(event.soldier_id)
        post_event(
            pygame.event.Event(
                GAMEEVENT,
                {
                    'subtype': SOLDIER_KILLED_SUBTYPE,
                    'soldier_id': event.soldier_id,
                    'side': soldier.side.value,
                    # Read before the seats move a player on to another soldier
                    'driver': self.seats.driver_of(event.soldier_id),
                },
            )
        )

    @override
    def render(self: Self, screen: pygame.Surface) -> None:
        """Draw the paper and ground, then the sandbags, soldiers and bullets in pencil.

        Args:
            screen: The display surface.

        """
        screen.blit(self.background, (0, 0))
        self.all_sprites.clear(screen, self.background)
        self.all_sprites.draw(screen)
        for sandbag in self.battle.sandbags:
            draw_sandbag(screen, sandbag, self.terrain)
        # The fallen are drawn first, so the standing are never hidden behind them
        for soldier in sorted(self.battle.soldiers, key=lambda soldier: soldier.alive):
            driver = self.seats.driver_of(soldier.soldier_id)
            draw_soldier(
                screen,
                soldier,
                frames=self.soldier_frames,
                marked=None if driver == COMPUTER_DRIVER_NAME else driver,
                walking=soldier.soldier_id in self.walking_soldier_ids,
                seconds=self.battle.seconds,
            )
        for bullet in self.battle.bullets:
            draw_bullet(screen, bullet)
        draw_hud(screen, self.battle)
        self._render_seats(screen)
        if self.victory_message:
            draw_banner(screen, self.victory_message)
        self.rects = None  # The whole screen is presented

    def _render_seats(self: Self, screen: pygame.Surface) -> None:
        """Draw the join note while a device has no seat, each player's card and highlight.

        Args:
            screen: The display surface.

        """
        if any(self.seats.seat_of(device) is None for device in self.devices):
            draw_join_prompt(screen)
        # Every player not yet playing has a card, in name order
        slot = 0
        for name in sorted(self.seats.players):
            seat = self.seats.players[name]
            if seat.stage is Stage.PLAYING:
                continue
            draw_seat_card(screen, seat, slot=slot, battle_over=self.phase is Phase.VICTORY)
            slot += 1
            if seat.stage is Stage.CHOOSING_SOLDIER:
                highlighted = self.seats.highlighted_soldier(seat, battle=self.battle)
                if highlighted is not None:
                    draw_soldier_highlight(screen, highlighted, name=seat.name)

    def debug_draw(self: Self, surface: pygame.Surface, camera: Camera2D) -> None:
        """Tag every living soldier with who drives him and list the seats (the debug overlay).

        The field never scrolls, so a soldier's world position is his screen position and the
        camera is not used.

        Args:
            surface: The overlay surface (screen coordinates).
            camera: The scene's camera (unused: the field never scrolls).

        """
        del camera
        standing = sorted(
            self.battle.living(Side.PLATOON) + self.battle.living(Side.BRIGADE),
            key=lambda soldier: (soldier.x, soldier.soldier_id),
        )
        for rank, soldier in enumerate(standing):
            # Neighbours left to right take turns being raised, so their tags never overlap
            raised = (rank % 2) * SEAT_TAG_STAGGER_PIXELS
            draw_seat_tag(
                surface,
                text=self.seats.driver_of(soldier.soldier_id),
                at=(soldier.x, soldier.y - SEAT_TAG_ABOVE_FEET_PIXELS - raised),
            )
        draw_seats_panel(surface, lines=seats_panel_lines(self.seats, self.battle))

    @override
    def on_key_up_event(self: Self, event: KeyEvent) -> None:
        """Quit on a Q release as every scene does, but never on an Escape release.

        Escape is the keyboard's Back, held to leave a seat (``seats``), so the base scene's
        quit on its release would end the game for a player who only meant to leave. Like
        Mr. Muncher's override (``mr_muncher/game.py``, where Escape pauses), this reads no
        gameplay input: the seats read Escape from the frame's snapshot.

        Args:
            event: The key up event.

        """
        if event.key == pygame.K_ESCAPE:
            return
        super().on_key_up_event(event)


def _take_marker(event: GameEvent) -> None:
    """Take one of the scene's own game events: a marker for recordings, with nothing to do.

    Args:
        event: The game event.

    """
    del event


def _post_seat_changed(entry: SeatLogEntry) -> None:
    """Post a seat log entry as an internal event: what changed, for whom, and his soldier.

    Args:
        entry: The entry.

    """
    post_event(
        pygame.event.Event(
            GAMEEVENT,
            {
                'subtype': SEAT_CHANGED_SUBTYPE,
                'change': entry.change.value,
                'player': entry.player,
                'soldier_id': NO_SOLDIER_ID if entry.soldier_id is None else entry.soldier_id,
                'text': entry.text,
            },
        )
    )


def main() -> None:
    """Run Drawing Fire."""
    GameEngine(game=DrawingFireScene).start()


if __name__ == '__main__':
    main()
