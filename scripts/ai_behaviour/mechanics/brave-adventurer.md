STAND-IN: written by hand from the code (research report, 2026-11-07) until the startup task works
out each game's mechanics itself (plans/lucid-circuit-4b-mirror.md).

Brave Adventurer mechanics:
- A side-scrolling platformer in ancient Egypt: one hand-made level, "The Path of the Pharaoh", 20
  screens of 800 px each, the same every time. Nothing is generated and nothing is random.
- Two editions with identical gameplay: Classic draws its sprites in code, and has a voice assistant;
  Papyrus uses pixel art at 2x scale. They keep separate high scores.
- Hold Right or Left to move; there is no auto-run. Top speed is a constant 200 px/s and never
  increases. Space or Up jumps, only from the ground: about 104 px high and about 165 px across at
  full speed, about 0.83 s in the air.
- Pits are gaps between Ground sprites: a pit runs from the end of one Ground segment (its world_x
  plus its width) to the start of the next. Falling below the screen loses a life. Inside a pit the
  ground edges act as walls, so there is no climbing out.
- Walls are 32 px wide and 48 to 80 px tall. Cobras stay in place and strike every 2 s; scarabs roll
  and turn at walls; scorpions patrol at 60 px/s. Touching any enemy loses a life.
- Score: the furthest distance reached divided by 10, plus 100 per gold scarab collected.
- Lives: 3. Losing one respawns you 200 px back. At 0 lives the game ends and the score is saved.
- The camera follows about 250 px behind the player.
- Controls: Right and Left arrows move, Space or Up jumps, Esc pauses, Q quits. Gamepad: D-pad moves,
  A jumps.
