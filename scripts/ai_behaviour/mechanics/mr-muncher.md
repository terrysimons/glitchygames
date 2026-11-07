STAND-IN: written by hand from the code (research report, 2026-11-07) until the startup task works
out each game's mechanics itself (plans/lucid-circuit-4b-mirror.md).

Mr. Muncher mechanics:
- You are Mr. Muncher (the Player sprite), a popcorn bucket in a maze. The maze is a 27 x 24 tile
  grid; sprites' tile_x and tile_y give their tile.
- Pickups: sprockets are 10 points each. The 4 snacks are 50 each and start a sugar rush: for 8
  seconds on level 1 (0.9 s less each level, never under 2 s) the chasers turn blue and run, and
  eating a blue chaser scores 200, then 400, 800 and 1600.
- A bonus reel appears after 70 and after 170 pickups eaten, for 9.5 seconds.
- Four chasers (Muncher sprites): Chomper aims at your tile; Snapper aims 4 tiles ahead of you;
  Gnasher aims at a point found by doubling the line from Chomper to 2 tiles ahead of you; Nibbles
  aims at you when more than 8 tiles away, otherwise at its own corner. At each tile a chaser never
  reverses, and takes the open way whose next tile is closest in a straight line to its target. In
  scatter time they aim at their corners instead. A chaser's target is its target tile.
- Touching a chaser that isn't blue loses a life. The game does not record which chaser it was.
- Lives: 3, and one extra life once, at 10,000 points. There is no second extra life.
- Clearing every pickup ends the level. Chaser speed is set per level in the code; there is no
  setting or control to change it.
- Controls: arrow keys or W A S D move (a turn pressed early is remembered), Esc or P pauses, Q
  quits. A gamepad's D-pad or left stick steers and Start pauses.
