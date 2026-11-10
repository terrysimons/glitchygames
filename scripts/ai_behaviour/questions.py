"""The behaviour tests' questions, as the owner reviewed them, each judged against its snapshot.

Every check works out the right answer from the snapshot by code, never from a number typed by
hand, and also checks how the model got there: which tools it called, and what it drew.
"""

from __future__ import annotations

import itertools
import math
import operator
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from glitchygames.ai_introspection import JsonValue

PADDLE_SPEED = 400.0
SPEED_CAP = 500.0
BALL_SIZE = 20
SCREEN_HEIGHT = 480
RIGHT_PADDLE_X = 780
NUMBER = r'(?<![\d.]){}(?![\d])'


class Answered(BaseModel):
    """What the model did with one question."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    text: str
    calls: list[dict[str, Any]]
    drawings: list[dict[str, Any]]
    snapshot: dict[str, Any]

    def called(self, name: str) -> bool:
        """Whether it called a tool.

        Returns:
            True when any of its calls was to that tool.

        """
        return any(call['name'] == name for call in self.calls)

    def says(self, *patterns: str) -> bool:
        """Whether its answer holds every pattern, ignoring case.

        Returns:
            True when each regular expression matches somewhere in the answer.

        """
        return all(re.search(pattern, self.text, re.IGNORECASE) for pattern in patterns)


class BehaviourQuestion(BaseModel):
    """One question about one moment of one game."""

    model_config = ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    name: str
    game: str
    moment: str
    text: str
    categories: tuple[str, ...]
    staleness: str
    check: Callable[[Answered], tuple[bool, str]]


def verdict(*failures: str | None) -> tuple[bool, str]:
    """Turn a check's possible failures into a result.

    Returns:
        Passed, and if not, every reason.

    """
    reasons = [failure for failure in failures if failure]
    return (not reasons, '; '.join(reasons))


# Positional on purpose: every check reads as require(condition, reason), like an assertion
def require(condition: bool, reason: str) -> str | None:  # ruff: ignore[boolean-type-hint-positional-argument]
    """Return the reason when a condition fails.

    Returns:
        None when the condition holds, else the reason.

    """
    return None if condition else reason


def drawn_sprite_ids(drawing: dict[str, Any]) -> list[str]:
    """The sprite ids a drawing highlights, whatever the model put there.

    Returns:
        Its ``sprite_ids`` that are strings, or none.

    """
    sprite_ids: JsonValue = drawing.get('sprite_ids')
    if not isinstance(sprite_ids, list):
        return []
    return [sprite_id for sprite_id in sprite_ids if isinstance(sprite_id, str)]


def balls(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """The snapshot's balls.

    Returns:
        Each BallSprite's read.

    """
    return [sprite for sprite in snapshot['sprites'].values() if sprite['class'] == 'BallSprite']


def ball_speed(ball: dict[str, Any]) -> float:
    """A ball's speed in pixels per second.

    Returns:
        The length of its speed vector.

    """
    return math.hypot(ball['speed']['x'], ball['speed']['y'])


def reaches_right_paddle(snapshot: dict[str, Any]) -> tuple[bool, str]:
    """Work out whether Player 2 can reach the ball heading its way, from the snapshot.

    Returns:
        Whether it can, and the ball it's about.

    """
    heading_right = [ball for ball in balls(snapshot) if ball['speed']['x'] > 0]
    ball = max(heading_right, key=operator.itemgetter('world_x'))
    seconds = (RIGHT_PADDLE_X - BALL_SIZE - ball['world_x']) / ball['speed']['x']
    # The ball's centre on arrival, bouncing off the top and bottom walls
    travel = ball['world_y'] + ball['speed']['y'] * seconds
    span = SCREEN_HEIGHT - BALL_SIZE
    folded = travel % (2 * span)
    arrival_centre = (folded if folded <= span else 2 * span - folded) + BALL_SIZE / 2
    paddle = snapshot['sprites']['VerticalPaddle#1']['rect']
    top, bottom = paddle[1], paddle[1] + paddle[3]
    distance = max(0.0, top - arrival_centre, arrival_centre - bottom)
    return distance <= PADDLE_SPEED * seconds, ball['id']


def check_heading(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about heading.

    Returns:
        Whether it passed, and if not, why.

    """
    words = {ball['id']: ball for ball in balls(answered.snapshot)}
    expected = {'right' if ball['speed']['x'] > 0 else 'left' for ball in words.values()} | {
        'down' if ball['speed']['y'] > 0 else 'up' for ball in words.values()
    }
    return verdict(
        require(answered.says(*expected), f'should give headings: {sorted(expected)}'),
        require(answered.called('get_sprite'), 'should read the balls with get_sprite'),
        require(bool(answered.drawings), 'should draw the predicted paths'),
    )


def check_bounce(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about bounce.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(answered.says('paddle'), 'should say it hit a paddle'),
        require(
            answered.says(r'horizontal|\bx\b|left.{0,40}right|right.{0,40}left'),
            'should say the horizontal direction changed',
        ),
        require(
            answered.says(
                r'vertical.{0,60}(same|unchanged|kept|not change)|(same|unchanged).{0,60}vertical'
            )
            or answered.says(r"doesn't matter|does not matter|regardless"),
            'should say the vertical speed is unchanged, wherever it hits',
        ),
    )


def check_spawning(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about spawning.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(answered.says('paddle'), 'should say a paddle hit spawns a ball'),
        require(answered.says(r'\b2\b.{0,12}s|two second'), 'should give the 2 second gap'),
    )


def check_reach(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about reach.

    Returns:
        Whether it passed, and if not, why.

    """
    can_reach, ball_id = reaches_right_paddle(answered.snapshot)
    yes, no = (
        answered.says(r'\byes\b|\bcan\b|will reach|in time'),
        answered.says(r"\bno\b|can't|cannot|won't|will not"),
    )
    return verdict(
        require(
            yes if can_reach else no, f'should say {"yes" if can_reach else "no"} for {ball_id}'
        ),
        require(answered.called('get_sprite'), 'should read the ball and paddle'),
        require(bool(answered.drawings), "should mark where it'll arrive"),
    )


def check_fastest(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about fastest.

    Returns:
        Whether it passed, and if not, why.

    """
    fastest = max(balls(answered.snapshot), key=ball_speed)
    speed = round(ball_speed(fastest))
    close = [str(value) for value in range(speed - 2, speed + 3)]
    at_cap = speed >= SPEED_CAP - 1
    return verdict(
        require(
            any(re.search(NUMBER.format(value), answered.text) for value in close),
            f'should give about {speed} px/s',
        ),
        require(
            answered.says('500') and (answered.says(r'\bnot\b|below|under|less') != at_cap),
            f'should say it is {"" if at_cap else "not "}at the 500 cap',
        ),
    )


def check_longest_rally(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about longest rally.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(answered.says(r'\b0\b|zero|no rall|none'), 'the real game had no rally: 0'),
        require(answered.says('demo'), 'should tell the demo apart from the real game'),
        require(answered.called('history'), 'should work it out from history'),
    )


def check_passed_through(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about passed through.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(answered.says(r'\bno\b|did not|didn\'t|never'), 'they never touched: no'),
        require(answered.called('get_sprite') or answered.called('history'), 'should look'),
    )


def check_high_scores(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about high scores.

    Returns:
        Whether it passed, and if not, why.

    """
    scores = [entry['score'] for entry in answered.snapshot['scene'].get('high_scores', [])]
    return verdict(
        require(
            all(re.search(NUMBER.format(score), answered.text) for score in scores),
            f'should give the high scores {scores}',
        ),
    )


def check_paddle_code(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about paddle code.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(
            answered.says(r'no (control|setting|way)|can\'t|cannot|isn\'t|no built'),
            'should say there is no control',
        ),
        require('```' in answered.text or answered.called('run_in_copy'), 'should draft Python'),
        require(answered.says(r'speed_up|speed'), 'should use the paddle speed'),
    )


def check_idle_demo(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about idle demo.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(answered.says('demo'), 'should say a demo plays'),
        require(answered.says(r'\b10\b|ten'), 'should say after 10 seconds'),
    )


PADDLESLAP_QUESTIONS: tuple[BehaviourQuestion, ...] = (
    BehaviourQuestion(
        name='paddleslap-heading',
        game='paddleslap',
        moment='two-balls-after-a-hit',
        text='Where is each ball heading? Draw its predicted path.',
        categories=('analysis', 'visual'),
        staleness='fast',
        check=check_heading,
    ),
    BehaviourQuestion(
        name='paddleslap-bounce',
        game='paddleslap',
        moment='two-balls-after-a-hit',
        text='Why did BallSprite#0 just bounce at that angle?',
        categories=('analysis',),
        staleness='never',
        check=check_bounce,
    ),
    BehaviourQuestion(
        name='paddleslap-spawning',
        game='paddleslap',
        moment='two-balls-after-a-hit',
        text='What triggers a new ball to spawn?',
        categories=('base context',),
        staleness='never',
        check=check_spawning,
    ),
    BehaviourQuestion(
        name='paddleslap-reach',
        game='paddleslap',
        moment='ball-heading-for-player-2',
        text="Will Player 2 reach the ball in time? Mark where it'll arrive.",
        categories=('analysis', 'visual'),
        staleness='fast',
        check=check_reach,
    ),
    BehaviourQuestion(
        name='paddleslap-fastest',
        game='paddleslap',
        moment='four-balls',
        text='How fast is the fastest ball, and is it at the speed cap?',
        categories=('analysis', 'performance'),
        staleness='moderate',
        check=check_fastest,
    ),
    BehaviourQuestion(
        name='paddleslap-longest-rally',
        game='paddleslap',
        moment='after-the-demo',
        text='What was the longest rally in my game?',
        categories=('analysis', 'testing'),
        staleness='never',
        check=check_longest_rally,
    ),
    BehaviourQuestion(
        name='paddleslap-passed-through',
        game='paddleslap',
        moment='closest-two-balls',
        text='Did two balls just pass through each other?',
        categories=('testing', 'analysis'),
        staleness='never',
        check=check_passed_through,
    ),
    BehaviourQuestion(
        name='paddleslap-high-scores',
        game='paddleslap',
        moment='game-over',
        text='What are the high scores?',
        categories=('live', 'base context'),
        staleness='slow',
        check=check_high_scores,
    ),
    BehaviourQuestion(
        name='paddleslap-faster-paddle',
        game='paddleslap',
        moment='two-balls-after-a-hit',
        text='Speed up the left paddle.',
        categories=('code', 'testing'),
        staleness='never',
        check=check_paddle_code,
    ),
    BehaviourQuestion(
        name='paddleslap-idle-demo',
        game='paddleslap',
        moment='game-over',
        text='What happens if I leave the game over screen alone?',
        categories=('base context',),
        staleness='never',
        check=check_idle_demo,
    ),
)

TINKER_HEIGHT = 44
RUNNING_JUMP_RISE = 140
BONUS_REEL_AT = (70, 170)
# A drawn route needs at least a start, a turn and an end
ROUTE_POINTS_REQUIRED = 3
# Naming at least two chasers counts as naming them
CHASERS_NAMED_REQUIRED = 2


def tinker(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Clockwork Keep's player.

    Returns:
        Tinker's read.

    """
    return next(sprite for sprite in snapshot['sprites'].values() if sprite['class'] == 'Tinker')


def sprites_of(snapshot: dict[str, Any], class_name: str) -> list[dict[str, Any]]:
    """A snapshot's sprites of one class.

    Returns:
        Their reads.

    """
    return [sprite for sprite in snapshot['sprites'].values() if sprite['class'] == class_name]


def highest_unreachable_platform(snapshot: dict[str, Any]) -> dict[str, Any]:
    """The lowest platform above Tinker that even a running jump can't reach from where he stands.

    Returns:
        The platform.

    """
    feet = tinker(snapshot)['world_y'] + TINKER_HEIGHT
    too_high = [
        platform
        for platform in sprites_of(snapshot, 'Platform')
        if feet - platform['world_y'] > RUNNING_JUMP_RISE
    ]
    return max(too_high, key=operator.itemgetter('world_y'))


def check_floor_lives_score(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about floor lives score.

    Returns:
        Whether it passed, and if not, why.

    """
    player = tinker(answered.snapshot)
    return verdict(
        require(answered.says(r'boiler|floor 0|first floor|ground floor'), 'should name the floor'),
        require(
            answered.says(NUMBER.format(player['lives'])), f'should give {player["lives"]} lives'
        ),
        require(
            answered.says(NUMBER.format(player['score'])), f'should give {player["score"]} points'
        ),
    )


def check_reach_platform(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about reach platform.

    Returns:
        Whether it passed, and if not, why.

    """
    platform = highest_unreachable_platform(answered.snapshot)
    red = [
        drawing
        for drawing in answered.drawings
        if platform['id'] in drawn_sprite_ids(drawing)
        and 'red' in str(drawing.get('color', '')).lower()
    ]
    return verdict(
        require(
            answered.says(r"\bno\b|can't|cannot|not reach|too high|unreachable"), 'should say no'
        ),
        require(bool(red), f'should colour {platform["id"]} red'),
    )


def check_nearest_cog(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about nearest cog.

    Returns:
        Whether it passed, and if not, why.

    """
    player = tinker(answered.snapshot)
    nearest = min(
        sprites_of(answered.snapshot, 'CogCollectible'),
        key=lambda cog: math.hypot(
            cog['world_x'] - player['world_x'], cog['world_y'] - player['world_y']
        ),
    )
    return verdict(
        require(
            answered.says(re.escape(nearest['id']))
            or answered.says(NUMBER.format(round(nearest['world_y']))),
            f'should name {nearest["id"]}',
        ),
        require(
            answered.says(NUMBER.format(nearest['points'])),
            f'should say it is worth {nearest["points"]}',
        ),
    )


def check_elevator(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about elevator.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(
            answered.says(
                r"doesn't move|does not move|stationary|fixed|not move|stays|press w|\bW\b"
            ),
            "should correct the premise: it doesn't move, you ride it with W",
        ),
    )


def check_up_through(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about up through.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(
            answered.says(
                r'one.?way|from below|up through|jump.{0,30}through|only.{0,40}(falling|land)'
            ),
            'should explain one-way platforms',
        ),
        require(answered.called('history'), 'should look at the frames before'),
    )


def check_route(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about route.

    Returns:
        Whether it passed, and if not, why.

    """
    paths = [drawing for drawing in answered.drawings if drawing.get('kind') == 'path']
    return verdict(
        require(
            bool(paths) and len(paths[0].get('points') or []) >= ROUTE_POINTS_REQUIRED,
            'should draw a route of 3+ points',
        ),
    )


def check_cog_scoring(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about cog scoring.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(answered.says(r'\b10\b', r'\b50\b', r'\b100\b'), 'should give 10, 50 and 100')
    )


def check_frame_cap(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about frame cap.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(answered.says(r'\bno\b|not|doesn'), 'should say no'),
        require(answered.says(r'\b50\b|hitch'), 'should say it only matters in hitches over 50 ms'),
    )


def check_extra_life(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about extra life.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(
            answered.says(
                r"no way|can't|cannot|isn't|no (mechanic|pickup|extra)|only (go|be) (down|lost)"
            ),
            'should say there is no way',
        ),
        require('```' in answered.text or answered.called('run_in_copy'), 'should draft Python'),
    )


def check_gear_works(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about gear works.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(
            answered.says(r'1440|taller|narrow|gap|running jump|\b9\b'),
            'should give real differences',
        ),
    )


def munchers(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Mr. Muncher's chasers by id.

    Returns:
        Each Muncher's read, by its sprite id.

    """
    return {sprite['id']: sprite for sprite in sprites_of(snapshot, 'Muncher')}


def killer(snapshot: dict[str, Any]) -> str:
    """The chaser nearest the player at the frame of the death, from the window.

    Returns:
        Its name.

    """
    death_frame = next(entry['frame'] for entry in snapshot['log'] if entry.get('phase') == 'DYING')
    entry = next(item for item in snapshot['window'] if item['frame'] == death_frame)
    player = next(value for key, value in entry['sprites'].items() if key.startswith('Player'))
    chasers = munchers(snapshot)
    nearest = min(
        (key for key in entry['sprites'] if key in chasers),
        key=lambda key: math.hypot(
            entry['sprites'][key]['world_x'] - player['world_x'],
            entry['sprites'][key]['world_y'] - player['world_y'],
        ),
    )
    return chasers[nearest]['name']


def check_closest_chaser(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about closest chaser.

    Returns:
        Whether it passed, and if not, why.

    """
    chasers = munchers(answered.snapshot)
    highlighted = {
        sprite_id
        for drawing in answered.drawings
        for sprite_id in drawn_sprite_ids(drawing)
        if sprite_id in chasers
    }
    return verdict(
        require(
            bool(highlighted),
            'should highlight a chaser (process only: the maze path is not checked)',
        )
    )


def check_pickups(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about pickups.

    Returns:
        Whether it passed, and if not, why.

    """
    scene = answered.snapshot['scene']
    to_next = next(threshold for threshold in BONUS_REEL_AT if threshold > scene['sprockets_eaten'])
    more = to_next - scene['sprockets_eaten']
    return verdict(
        require(
            answered.says(NUMBER.format(scene['sprockets_left'])),
            f'should give {scene["sprockets_left"]} left',
        ),
        require(answered.says(NUMBER.format(more)), f'should say {more} more until the bonus reel'),
    )


def check_targets(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about targets.

    Returns:
        Whether it passed, and if not, why.

    """
    names = [chaser['name'] for chaser in munchers(answered.snapshot).values()]
    return verdict(
        require(
            sum(bool(re.search(name, answered.text, re.IGNORECASE)) for name in names)
            >= CHASERS_NAMED_REQUIRED,
            'should name the chasers',
        ),
        require(bool(answered.drawings), 'should draw their targets (process only)'),
    )


def check_chaser_rules(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about chaser rules.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(
            answered.says('chomper', 'snapper', r'\b4\b|four'), "should give each chaser's rule"
        ),
    )


def check_who_caught_me(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about who caught me.

    Returns:
        Whether it passed, and if not, why.

    """
    name = killer(answered.snapshot)
    return verdict(
        require(answered.says(name), f'should infer it was {name}, the nearest at the moment'),
        require(answered.called('history'), 'should work it out from history'),
    )


def check_sugar_rush(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about sugar rush.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(require(answered.says(r'\b8\b|eight'), 'should say 8 seconds on level 1'))


def check_route_to_pickup(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about route to pickup.

    Returns:
        Whether it passed, and if not, why.

    """
    paths = [drawing for drawing in answered.drawings if drawing.get('kind') == 'path']
    return verdict(
        require(bool(paths), 'should draw the route (process only: the path is not checked)')
    )


def check_muncher_controls(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about muncher controls.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(
            answered.says(r'arrow|wasd|w.?a.?s.?d', r'\bp\b|esc'), 'should give move and pause keys'
        )
    )


def check_slower_chasers(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about slower chasers.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(
            answered.says(r"no (setting|control|way)|can't|cannot|isn't|in the code"),
            'should say there is no setting',
        ),
        require('```' in answered.text or answered.called('run_in_copy'), 'should draft Python'),
    )


def check_second_extra_life(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about second extra life.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(
            answered.says(r'only one|just one|once|no second|no other|not possible|can\'t'),
            'should say there is only one',
        ),
        require(answered.says(r'10,?000'), 'should say at 10,000 points'),
    )


CLOCKWORK_AND_MUNCHER_QUESTIONS: tuple[BehaviourQuestion, ...] = (
    BehaviourQuestion(
        name='clockwork-floor-lives-score',
        game='clockwork-keep',
        moment='climbing',
        text='Which floor am I on, and how many lives and points do I have?',
        categories=('live', 'base context'),
        staleness='slow',
        check=check_floor_lives_score,
    ),
    # Platform#6 is the lowest platform above Tinker out of a running jump's reach (the check works
    # it out from the snapshot, and fails loudly if that ever stops being Platform#6)
    BehaviourQuestion(
        name='clockwork-reach-platform',
        game='clockwork-keep',
        moment='after-jumping-up-through',
        text='Can Tinker reach Platform#6 from here? If not, colour it red.',
        categories=('analysis', 'visual'),
        staleness='fast',
        check=check_reach_platform,
    ),
    BehaviourQuestion(
        name='clockwork-nearest-cog',
        game='clockwork-keep',
        moment='after-jumping-up-through',
        text="Where's the nearest cog, and what's it worth?",
        categories=('live', 'analysis'),
        staleness='slow',
        check=check_nearest_cog,
    ),
    BehaviourQuestion(
        name='clockwork-elevator',
        game='clockwork-keep',
        moment='climbing',
        text='When does the elevator arrive?',
        categories=('testing',),
        staleness='never',
        check=check_elevator,
    ),
    BehaviourQuestion(
        name='clockwork-up-through',
        game='clockwork-keep',
        moment='after-jumping-up-through',
        text='Why did Tinker pass up through Platform#2 instead of hitting it from below?',
        categories=('analysis',),
        staleness='never',
        check=check_up_through,
    ),
    BehaviourQuestion(
        name='clockwork-route',
        game='clockwork-keep',
        moment='after-jumping-up-through',
        text="What's the best route up this floor? Draw it.",
        categories=('analysis', 'visual'),
        staleness='slow',
        check=check_route,
    ),
    BehaviourQuestion(
        name='clockwork-scoring',
        game='clockwork-keep',
        moment='climbing',
        text='How does scoring work?',
        categories=('base context',),
        staleness='never',
        check=check_cog_scoring,
    ),
    BehaviourQuestion(
        name='clockwork-frame-cap',
        game='clockwork-keep',
        moment='climbing',
        text='Is the frame-time cap slowing my jump?',
        categories=('testing', 'performance'),
        staleness='fast',
        check=check_frame_cap,
    ),
    BehaviourQuestion(
        name='clockwork-extra-life',
        game='clockwork-keep',
        moment='climbing',
        text='Give me an extra life.',
        categories=('code', 'testing'),
        staleness='never',
        check=check_extra_life,
    ),
    BehaviourQuestion(
        name='clockwork-gear-works',
        game='clockwork-keep',
        moment='climbing',
        text='How is Gear Works different from the Boiler Room?',
        categories=('analysis', 'base context'),
        staleness='never',
        check=check_gear_works,
    ),
    BehaviourQuestion(
        name='muncher-closest-chaser',
        game='mr-muncher',
        moment='playing',
        text='Which chaser is closest to me along the maze, not in a straight line? Highlight it.',
        categories=('analysis', 'visual'),
        staleness='fast',
        check=check_closest_chaser,
    ),
    BehaviourQuestion(
        name='muncher-pickups-left',
        game='mr-muncher',
        moment='playing',
        text='How many pickups are left, and how close am I to the next bonus reel?',
        categories=('live',),
        staleness='slow',
        check=check_pickups,
    ),
    BehaviourQuestion(
        name='muncher-targets',
        game='mr-muncher',
        moment='playing',
        text='Where is each chaser aiming right now? Draw its target.',
        categories=('analysis', 'visual'),
        staleness='fast',
        check=check_targets,
    ),
    BehaviourQuestion(
        name='muncher-chaser-rules',
        game='mr-muncher',
        moment='playing',
        text='How do the chasers decide where to go?',
        categories=('base context',),
        staleness='never',
        check=check_chaser_rules,
    ),
    BehaviourQuestion(
        name='muncher-who-caught-me',
        game='mr-muncher',
        moment='just-died',
        text='Why did I die just then? Which chaser got me?',
        categories=('analysis', 'testing'),
        staleness='never',
        check=check_who_caught_me,
    ),
    BehaviourQuestion(
        name='muncher-sugar-rush',
        game='mr-muncher',
        moment='sugar-rush',
        text='How long will a sugar rush last on this level?',
        categories=('base context',),
        staleness='slow',
        check=check_sugar_rush,
    ),
    BehaviourQuestion(
        name='muncher-route-to-pickup',
        game='mr-muncher',
        moment='playing',
        text='Show me the route to the nearest pickup. Draw it.',
        categories=('analysis', 'visual'),
        staleness='fast',
        check=check_route_to_pickup,
    ),
    BehaviourQuestion(
        name='muncher-controls',
        game='mr-muncher',
        moment='playing',
        text='What are the controls?',
        categories=('base context',),
        staleness='never',
        check=check_muncher_controls,
    ),
    BehaviourQuestion(
        name='muncher-slower-chasers',
        game='mr-muncher',
        moment='playing',
        text='Make the chasers slower.',
        categories=('code', 'testing'),
        staleness='never',
        check=check_slower_chasers,
    ),
    BehaviourQuestion(
        name='muncher-second-extra-life',
        game='mr-muncher',
        moment='playing',
        text='How do I get another extra life after the first one?',
        categories=('testing',),
        staleness='never',
        check=check_second_extra_life,
    ),
)

FULL_SPEED_JUMP_ACROSS = 165
SIDE_NAMES = {'PLATOON': 'Pencil Platoon', 'BRIGADE': 'Graphite Brigade'}
SIDE_COLOURS = {'PLATOON': 'yellow', 'BRIGADE': 'grey'}


def brave_player(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Brave Adventurer's player, in either edition.

    Returns:
        The player's read.

    """
    return next(
        sprite
        for sprite in snapshot['sprites'].values()
        if sprite['class'] in {'Player', 'PapyrusPlayer'}
    )


def next_pit(snapshot: dict[str, Any]) -> tuple[float, float]:
    """The distance from the player's front to the next pit, and the pit's width.

    Returns:
        Both, in pixels.

    Raises:
        ValueError: If the snapshot shows no pit ahead of the player.

    """
    player = brave_player(snapshot)
    front = player['world_x'] + player['rect'][2]
    segments = sorted(sprites_of(snapshot, 'GroundSegment'), key=operator.itemgetter('world_x'))
    for current, following in itertools.pairwise(segments):
        end = current['world_x'] + current['rect'][2]
        if end >= front and following['world_x'] > end:
            return end - front, following['world_x'] - end
    message = 'no pit ahead in the snapshot'
    raise ValueError(message)


def check_next_pit(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about next pit.

    Returns:
        Whether it passed, and if not, why.

    """
    distance, width = next_pit(answered.snapshot)
    near = [str(value) for value in range(round(distance) - 3, round(distance) + 4)]
    clearable = width <= FULL_SPEED_JUMP_ACROSS
    red = [
        drawing for drawing in answered.drawings if 'red' in str(drawing.get('color', '')).lower()
    ]
    return verdict(
        require(
            any(re.search(NUMBER.format(value), answered.text) for value in near),
            f'should give about {round(distance)} px',
        ),
        require(
            answered.says(r'\byes\b|\bcan\b|clear')
            if clearable
            else answered.says(r"\bno\b|can't|cannot"),
            f'should say it {"can" if clearable else "cannot"} be cleared ({round(width)} px wide)',
        ),
        require(clearable or bool(red), 'should mark it red when it cannot be cleared'),
    )


def check_edition(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about edition.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(answered.says('classic'), 'should say Classic'),
        require(
            answered.says(r'same|identical|pixel art|papyrus'), 'should say how the editions differ'
        ),
    )


def check_missed_jump(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about missed jump.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(
            answered.says(
                r"didn't jump|did not jump|no jump|never jumped|walked|ran (off|into)"
                r'|without jumping'
            ),
            'should say there was no jump',
        ),
        require(answered.called('history'), 'should look at the frames before'),
    )


def check_best_distance(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about best distance.

    Returns:
        Whether it passed, and if not, why.

    """
    furthest = round(brave_player(answered.snapshot)['max_distance'])
    near = [str(value) for value in range(furthest - 3, furthest + 4)]
    return verdict(
        require(
            any(re.search(NUMBER.format(value), answered.text) for value in near),
            f'should give about {furthest} px',
        ),
    )


def check_danger_ahead(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about danger ahead.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(bool(answered.drawings), 'should highlight what is coming (process only)')
    )


def check_brave_controls(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about brave controls.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(answered.says(r'arrow', r'space|\bup\b'), 'should give move and jump keys')
    )


def check_faster_than_start(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about faster than start.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(answered.says(r'\bno\b|not|same|constant'), 'should say no: speed is constant'),
        require(answered.says(r'\b200\b'), 'should give 200 px/s'),
    )


def check_ground_generation(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about ground generation.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(
            answered.says(
                r"hand.?made|isn't generated|not generated|fixed|designed|authored|no random"
            ),
            "should correct the premise: it isn't generated",
        ),
    )


def check_place_before_pit(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about place before pit.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(
            answered.says(r"no (control|way|command)|can't|cannot|isn't"),
            'should say there is no control',
        ),
        require('```' in answered.text or answered.called('run_in_copy'), 'should draft Python'),
    )


def check_every_pit(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about every pit.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(
            answered.called('run_in_copy')
            or answered.says(
                r"can't (tell|be sure|know)|don't know|would need to (try|test)|not sure"
                r'|try (it|each)'
            ),
            "should test it in a copy, or say it can't tell without trying "
            '(process only: waits for copies)',
        ),
    )


def battle(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Drawing Fire's battle, from the checks-only read.

    Returns:
        The battle's read.

    """
    return snapshot['for_checks']['battle']


def living_by_side(snapshot: dict[str, Any]) -> dict[str, int]:
    """How many soldiers each army has standing.

    Returns:
        The count, by side.

    """
    counts = dict.fromkeys(SIDE_NAMES, 0)
    for soldier in battle(snapshot)['soldiers']:
        if soldier['alive']:
            counts[soldier['side']] += 1
    return counts


def health_by_side(snapshot: dict[str, Any]) -> dict[str, int]:
    """Each army's total health, the tie-break when both have as many standing.

    Returns:
        The total, by side.

    """
    totals = dict.fromkeys(SIDE_NAMES, 0)
    for soldier in battle(snapshot)['soldiers']:
        if soldier['alive']:
            totals[soldier['side']] += soldier['health']
    return totals


def check_winning(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about winning.

    Returns:
        Whether it passed, and if not, why.

    """
    counts, health = living_by_side(answered.snapshot), health_by_side(answered.snapshot)
    ranking = sorted(SIDE_NAMES, key=lambda side: (counts[side], health[side]), reverse=True)
    leader, trailer = ranking
    if (counts[leader], health[leader]) == (counts[trailer], health[trailer]):
        return verdict(
            require(
                answered.says(r'even|tie|tied|level|neither'),
                f'should say it is even ({counts}, {health})',
            )
        )
    word = SIDE_NAMES[leader].split()[0]
    return verdict(
        require(
            answered.says(word),
            f'should say the {SIDE_NAMES[leader]} (standing {counts}, health {health})',
        ),
    )


def check_join(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about join.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(answered.says(r'enter|start', r'side'), 'should give Enter or Start, then a side')
    )


def check_swatches(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about swatches.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(answered.says(r'colou?r'), 'should say they change colour'),
        require(
            answered.says(r"only|just|nothing|doesn't|does not|no effect"),
            'should say they do nothing to play',
        ),
    )


def check_who_shot(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about who shot.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(
            answered.says(r"can't|cannot|don't know|not recorded|only.{0,30}side|which side"),
            'should say only the side is known',
        ),
        require(answered.called('history'), 'should look at history (process only)'),
    )


def check_seats(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about seats.

    Returns:
        Whether it passed, and if not, why.

    """
    players = answered.snapshot['for_checks']['seats']['players']
    sides = {SIDE_NAMES[seat['side']].split()[0] for seat in players.values()}
    return verdict(
        require(all(answered.says(name) for name in players), f'should name {sorted(players)}'),
        # Naming a seat's side shows it read the seats, not the mechanics' "P1, P2 and so on"
        require(
            all(answered.says(side) for side in sides), f'should give their sides {sorted(sides)}'
        ),
        require(answered.says(r'start|enter'), 'should say how another player joins'),
    )


def check_most_hits(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about most hits.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        # Nothing counts hits, but history can be worked through: a bare "can't tell" gives up
        require(answered.called('history'), 'should work through history'),
        require(
            answered.says(r'soldier\s*#?\d+|#\d+|id \d+'),
            'should name a soldier (process only: the count is not checked)',
        ),
    )


def check_my_colour(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about my colour.

    Returns:
        Whether it passed, and if not, why.

    """
    side = next(iter(answered.snapshot['for_checks']['seats']['players'].values()))['side']
    return verdict(require(answered.says(SIDE_COLOURS[side]), f'should say {SIDE_COLOURS[side]}'))


def check_deaths(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about deaths.

    Returns:
        Whether it passed, and if not, why.

    """
    dead = sum(1 for soldier in battle(answered.snapshot)['soldiers'] if not soldier['alive'])
    return verdict(require(answered.says(NUMBER.format(dead)), f'should give {dead} deaths'))


def check_easier(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about easier.

    Returns:
        Whether it passed, and if not, why.

    """
    return verdict(
        require(
            answered.says(r"no (setting|control|way|difficulty)|can't|cannot|isn't|constants"),
            'should say there is no setting',
        ),
        require('```' in answered.text or answered.called('run_in_copy'), 'should draft Python'),
    )


def check_on_screen(answered: Answered) -> tuple[bool, str]:
    """Judge an answer about on screen.

    Returns:
        Whether it passed, and if not, why.

    """
    counts = living_by_side(answered.snapshot)
    return verdict(
        require(answered.says('platoon', 'brigade'), 'should name both armies'),
        require(
            all(answered.says(NUMBER.format(count)) for count in counts.values()),
            f'should give the standing counts {counts}',
        ),
    )


BRAVE_AND_FIRE_QUESTIONS: tuple[BehaviourQuestion, ...] = (
    BehaviourQuestion(
        name='brave-next-pit',
        game='brave-adventurer',
        moment='before-the-first-pit',
        text='How far is the next pit, and can I clear it? Mark it red if not.',
        categories=('analysis', 'visual'),
        staleness='moderate',
        check=check_next_pit,
    ),
    BehaviourQuestion(
        name='brave-edition',
        game='brave-adventurer',
        moment='past-the-first-pit',
        text='Which edition am I playing, and how does it differ?',
        categories=('base context',),
        staleness='never',
        check=check_edition,
    ),
    BehaviourQuestion(
        name='brave-missed-jump',
        game='brave-adventurer',
        moment='just-missed-the-pit',
        text='Why did I miss that jump?',
        categories=('analysis',),
        staleness='never',
        check=check_missed_jump,
    ),
    BehaviourQuestion(
        name='brave-best-distance',
        game='brave-adventurer',
        moment='past-the-first-pit',
        text="What's my best distance this game?",
        categories=('live',),
        staleness='slow',
        check=check_best_distance,
    ),
    BehaviourQuestion(
        name='brave-danger-ahead',
        game='brave-adventurer',
        moment='before-the-first-pit',
        text="What's dangerous coming up? Highlight it.",
        categories=('live', 'visual'),
        staleness='moderate',
        check=check_danger_ahead,
    ),
    BehaviourQuestion(
        name='brave-controls',
        game='brave-adventurer',
        moment='past-the-first-pit',
        text='What are the controls?',
        categories=('base context',),
        staleness='never',
        check=check_brave_controls,
    ),
    BehaviourQuestion(
        name='brave-faster-than-start',
        game='brave-adventurer',
        moment='past-the-first-pit',
        text='Am I running faster than at the start?',
        categories=('testing',),
        staleness='never',
        check=check_faster_than_start,
    ),
    BehaviourQuestion(
        name='brave-ground-generation',
        game='brave-adventurer',
        moment='past-the-first-pit',
        text='How does the ground get generated?',
        categories=('testing',),
        staleness='never',
        check=check_ground_generation,
    ),
    BehaviourQuestion(
        name='brave-place-before-pit',
        game='brave-adventurer',
        moment='past-the-first-pit',
        text='Put me just before the next pit.',
        categories=('code', 'testing'),
        staleness='never',
        check=check_place_before_pit,
    ),
    BehaviourQuestion(
        name='brave-every-pit',
        game='brave-adventurer',
        moment='past-the-first-pit',
        text='Can every pit in this level be cleared?',
        categories=('analysis', 'testing'),
        staleness='never',
        check=check_every_pit,
    ),
    BehaviourQuestion(
        name='fire-winning',
        game='drawing-fire',
        moment='mid-battle',
        text="Who's winning right now?",
        categories=('live',),
        staleness='moderate',
        check=check_winning,
    ),
    BehaviourQuestion(
        name='fire-join',
        game='drawing-fire',
        moment='mid-battle',
        text='How do I join the battle?',
        categories=('base context',),
        staleness='never',
        check=check_join,
    ),
    BehaviourQuestion(
        name='fire-swatches',
        game='drawing-fire',
        moment='mid-battle',
        text='What do the swatches do?',
        categories=('base context', 'testing'),
        staleness='never',
        check=check_swatches,
    ),
    BehaviourQuestion(
        name='fire-who-shot',
        game='drawing-fire',
        moment='battle-won',
        text='Who shot the last soldier to fall?',
        categories=('analysis', 'testing'),
        staleness='never',
        check=check_who_shot,
    ),
    BehaviourQuestion(
        name='fire-seats',
        game='drawing-fire',
        moment='mid-battle',
        text='Which seats are taken, and how can a second player join?',
        categories=('live', 'base context'),
        staleness='slow',
        check=check_seats,
    ),
    BehaviourQuestion(
        name='fire-most-hits',
        game='drawing-fire',
        moment='battle-won',
        text='Which computer soldier has hit the most enemies?',
        categories=('analysis', 'testing'),
        staleness='never',
        check=check_most_hits,
    ),
    BehaviourQuestion(
        name='fire-my-colour',
        game='drawing-fire',
        moment='mid-battle',
        text='What colour is my soldier, and why?',
        categories=('analysis',),
        staleness='never',
        check=check_my_colour,
    ),
    BehaviourQuestion(
        name='fire-deaths',
        game='drawing-fire',
        moment='battle-won',
        text='How many soldiers have died so far?',
        categories=('analysis', 'testing'),
        staleness='never',
        check=check_deaths,
    ),
    BehaviourQuestion(
        name='fire-easier',
        game='drawing-fire',
        moment='mid-battle',
        text='Make the computer soldiers easier.',
        categories=('code', 'testing'),
        staleness='never',
        check=check_easier,
    ),
    BehaviourQuestion(
        name='fire-on-screen',
        game='drawing-fire',
        moment='mid-battle',
        text="What's happening on screen right now?",
        categories=('live', 'testing'),
        staleness='fast',
        check=check_on_screen,
    ),
)

QUESTIONS: tuple[BehaviourQuestion, ...] = (
    *PADDLESLAP_QUESTIONS,
    *CLOCKWORK_AND_MUNCHER_QUESTIONS,
    *BRAVE_AND_FIRE_QUESTIONS,
)

CHECKS: dict[str, Callable[[Answered], tuple[bool, str]]] = {
    question.name: question.check for question in QUESTIONS
}
