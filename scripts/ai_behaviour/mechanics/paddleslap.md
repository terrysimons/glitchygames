STAND-IN: written by hand from the code (research report, 2026-11-07) until the startup task works
out each game's mechanics itself (plans/lucid-circuit-4b-mirror.md). The tests check the startup
task's mechanics against these.

PaddleSlap mechanics:
- Co-operative: two paddles, Player 1 on the left (W up, S down) and Player 2 on the right (Up and
  Down arrows), against the balls together. There is no score per player.
- rally_count goes up by 1 on every paddle hit by any ball. It is a running total for the game and
  never resets when a ball is lost. Nothing records rallies or their lengths.
- A ball is lost when it leaves past the left or right edge. Top and bottom walls bounce it. The
  game ends when no ball is left.
- A paddle hit flips the ball's horizontal direction only; its vertical speed is unchanged, so where
  it hits the paddle does not matter. Each paddle hit speeds the ball up a little (about x1.10 at
  first, then less), keeping its angle. Ball speed is capped at 500 pixels per second. A wall bounce
  flips the vertical direction.
- New balls: by default (ball spawn mode paddle_only) a paddle hit spawns a new ball, at most once
  every 2 seconds, at a random spot at least 100 px from other balls, served at 150 px/s. Losing a
  ball does not bring a new one.
- Paddles are 20 x 100 px, at x 0 and x 780, and move at 400 px/s. Balls are 20 x 20 px images.
- Space pauses (Space resumes, Esc quits from the pause screen). Esc or Q quits during play.
- Game over screen: the final score (the rally count), the top 5 high scores (10 are saved), and
  "Press SPACE or START to restart, ESC or BACK to quit". Left alone for 10 seconds of game time, it
  plays a recorded demo game, then returns to the game over screen. The demo is not the player's
  game.
- VerticalPaddle has a speed_up() method, but nothing in the game calls it; there is no control or
  setting to change paddle speed.
