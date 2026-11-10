STAND-IN: written by hand from the code (research report, 2026-11-07) until the startup task works
out each game's mechanics itself (plans/lucid-circuit-4b-mirror.md).

Drawing Fire mechanics:
- A battle between two armies of 8 soldiers each: the Pencil Platoon (yellow, on the left) and the
  Graphite Brigade (grey, on the right). Each soldier has 6 health and a pistol; each bullet hit
  takes 1, and a soldier dies at 0. Bullets record only which side fired them, not who.
- The computer drives every soldier no player has taken: it targets the nearest enemy, advances to a
  stand-off distance, takes cover and shoots when it can see its target within 420 px. Its aim,
  reaction time (0.15-0.45 s) and range are constants in the code; there is no difficulty setting.
- Sandbags stop soldiers walking and wear down when hit. Hills stop bullets.
- A battle ends when an army has no soldier left; the other army wins. If both fall at once it is a
  draw ("Nobody wins!"). The next battle starts 3 seconds later.
- Joining: press Enter (keyboard) or Start (controller) on a device with no seat, choose a side
  with Left/Right (or A/D) and Enter, then a soldier the same way. There is no fixed number of seats:
  each device gets one, named P1, P2 and so on. When your soldier dies you take a free soldier of
  your side, or wait. Hold Back or Escape for 1 second to leave.
- Keyboard and mouse: A/D or Left/Right move, the mouse aims, the left button fires. Q quits.
  Controller: left stick or D-pad moves, right stick aims, right trigger fires.
- Swatches only recolour soldiers by palette (helmet and uniform in their army's colours); they do
  nothing to play. A soldier's colour changes only if you join the other side.
- The game posts an event for every death and every seat change. Nothing counts kills or hits.
- The game draws its soldiers without sprites: its state is in its objects (the battle, its
  soldiers and sandbags, and the seats), not in sprites.
