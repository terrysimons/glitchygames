# Swept ball-ball collisions in PaddleSlap (BUGS.md #174)

Part of the 2026-11-02 backlog run (the owner's explicit permission to plan, fix, commit, test
and push each item on its own branch).

## The bug

PaddleSlap checks ball pairs once per frame, where the frame left them (`check_overlap`, an AABB
broad phase, then a whole-pixel circle check). A pair closing fast can cross between two samples
and end the frame in a state that check misses or gets wrong:

- **on the same centre** (pinned by the strict xfails: head-on at 300 px/s each, aimed to meet on
  a frame; no contact direction exists, the pair is skipped);
- **overlapping on the wrong sides** (two balls at the 500 px/s cap close 16.7 px a frame: from
  11 px apart they end 5.7 px apart, crossed; the end check computes the contact direction from
  the crossed centres, reversed);
- **apart again on the far side** (faster than the cap, which a ball's speed-ups can pass; the
  cap applies only after ball collisions).

## Design

Follow each pair's path through the frame, before the end-of-frame check:

- `BallSprite` records where each `dt_tick` started (`frame_start_world_position`, an engine
  addition next to the existing `_last_tick_dt`; None before the first tick).
- `paddleslap.first_contact_fraction(start, motion, contact_distance)`: the pair's separation
  moves in a straight line over the frame; the first fraction `t` with
  `|start + t * motion| == contact_distance` while closing (0.0 when already touching at the
  start; None when not closing, passing wide, or touching only at or after the frame's end).
- `Game._swept_contact` takes a pair only when it touched within the frame **and** the end check
  would miss it or get it wrong: same centre, apart again, or crossed (the end separation points
  against the separation at contact). The end distance is measured as the end check measures it
  (whole-pixel centres), so every pair that check handled before stays with it: play in which no
  pair crosses is unchanged.
- `Game._collide_at_contact` puts both balls back where they touched and collides them there as
  the end check does (the same elastic exchange, speed cap, separation and per-pair cooldown;
  the cooldown makes the end check skip the pair).

Rejected: sub-stepping the whole frame (changes every ball's motion and costs a pass per step);
a full continuous solver (time of impact for every pair, events ordered within the frame): more
than PaddleSlap's two-to-few balls need.

## Plan

1. `frame_start_world_position` on `BallSprite`, tested.
2. The swept pass, run first in `_handle_ball_collisions`; the strict xfails come off.
3. Tests: each end state (overlapping-crossed, apart again, same centre), a non-crossing overlap
   left to the end check, touching only at the frame's end left to the next frame, an unticked
   ball, a pair in cooldown, and `first_contact_fraction`'s branches.
4. The full suite, golden replays included: any recording in which a pair crossed now plays
   differently (the intended change); none expected to.
5. BUGS.md #174; commit, push, PR.
