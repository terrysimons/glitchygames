STAND-IN: written by hand from the code (research report, 2026-11-07) until the startup task works
out each game's mechanics itself (plans/lucid-circuit-4b-mirror.md).

Clockwork Keep mechanics:
- Climb three floors as Tinker: Boiler Room (floor 0, 960 px tall, 14 platforms, 6 cogs), Gear
  Works (floor 1, 1440 px, 19 platforms, 9 cogs, narrower platforms and bigger gaps, its top needs
  running jumps) and Clock Face (floor 2, 1920 px, 21 platforms, 14 cogs, a moving gear to ride, no
  elevator). Standing on the Clock Face's highest platform wins.
- The elevator does not move on a floor: stand on it and press W to ride it to the next floor, a
  4 second ride. Score and lives carry over.
- Cogs: bronze 10 points, silver 50, gold 100. Touching one collects it. Cogs are the only points.
- Lives: 3. A life is lost only by falling 100 px below the bottom of the floor. There is no way to
  gain a life.
- Platforms are one-way: Tinker jumps up through them from below and lands on them only while
  falling. A platform's world_y is its top edge; y grows downward. Tinker is 28 x 44 px, and his
  world_y is his top, so his feet are at world_y + 44.
- Movement: walk 160 px/s, run 280 px/s (hold Left Shift). Gravity 1200 px/s squared. A normal jump
  rises about 96 px; a running jump about 140 px. Air time is about 0.8 s, or 0.97 s running.
- The playfield runs from x 100 to x 700.
- Each frame's game time is capped at 50 ms, so after a hitch the game slows rather than jumps
  ahead. The cap never changes jump height; it matters only during hitches longer than 50 ms.
- Controls: Left and Right arrows move, Space or Up jumps, W rides the elevator, Left Shift runs,
  Esc pauses, Q quits. Controller: D-pad, A jump, Y elevator, X run.
