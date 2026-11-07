"""The AI's tools, standing in for the clone by answering from a captured snapshot.

Each tool has the name, arguments and kind of answer the real one will have on the clone
(plans/lucid-circuit-4b-mirror.md, "The console's design"), so the behaviour tests won't change
when the mirror exists. Tools needing a running copy (``screenshot``, ``run_in_copy``) say so;
drawing tools record what was asked, for the tests to check.

Every answer is compact (the baseline of 2026-11-07 overflowed 8K in 19 of 150 answers, one tool
answer reaching 68,563 tokens): summaries first, details only when asked, and no answer longer
than ``MAXIMUM_RESULT_CHARACTERS``, shrinking its lists before ever cutting it.
"""

from __future__ import annotations

import ast
import difflib
import functools
import importlib
import inspect
import json
import math
import operator
import pkgutil
import types
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glitchygames.scenes import Scene

if TYPE_CHECKING:
    from glitchygames.ai_introspection import JsonValue

# About 1,000 tokens: several answers and the cached opening still fit in 8K
MAXIMUM_RESULT_CHARACTERS = 3500
LIST_LIMITS = (20, 10, 5, 2)
FIELD_LIMITS = (30, 20, 12)
DEFAULT_LIST_LIMIT = 15
HISTORY_CHANGES_SHOWN = 30
TRACK_POINTS_SHOWN = 15
SHORT_LIST = 5
SUGGESTIONS_SHOWN = 8
# A rect is x, y, width and height
RECT_NUMBERS = 4
NEEDS_THE_MIRROR = {'unavailable': 'This needs a running copy of the game, which is not built yet.'}
# Where each game's code is, for read_source; the engine's classes are found too
GAME_PACKAGES: dict[str, tuple[str, ...]] = {
    'paddleslap': ('paddleslap', 'glitchygames.game_objects'),
    'clockwork-keep': ('clockwork_keep',),
    'mr-muncher': ('mr_muncher',),
    'brave-adventurer': ('brave_adventurer_core', 'brave_adventurer'),
    'drawing-fire': ('drawing_fire',),
}

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        'type': 'function',
        'function': {
            'name': name,
            'description': description,
            'parameters': {'type': 'object', 'properties': properties, 'required': required},
        },
    }
    for name, description, properties, required in (
        (
            'get_scene',
            "The scene now: its name, the game's own state and facts, and sprite counts by class.",
            {},
            [],
        ),
        (
            'list_sprites',
            (
                'Sprite ids now. With no class: counts by class. near=<sprite id> sorts them by '
                'distance from that sprite, nearest first.'
            ),
            {
                'class_name': {'type': 'string'},
                'near': {'type': 'string'},
                'limit': {'type': 'integer'},
            },
            [],
        ),
        (
            'get_sprite',
            "One sprite's state now, with speed and heading worked out when it moves.",
            {'sprite_id': {'type': 'string'}},
            ['sprite_id'],
        ),
        (
            'get_object',
            # No example names: 2B copied another game's ('battle') into every game (2026-11-07)
            (
                "Any of the game's objects that aren't sprites, by a dotted path from the scene "
                "(a field, then its fields; a list's items by number, e.g. 'field.items.3'). Start "
                'with an empty path: it lists what there is.'
            ),
            {'path': {'type': 'string'}},
            [],
        ),
        (
            'history',
            (
                'What changed between two frames: scene changes, scores, sprites coming and going, '
                "whether a demo was playing. Give sprite_id for that sprite's recent track."
            ),
            {
                'from_frame': {'type': 'integer'},
                'to_frame': {'type': 'integer'},
                'sprite_id': {'type': 'string'},
            },
            [],
        ),
        (
            'read_source',
            # {examples} is this game's own names (tool_definitions): fixed examples from one
            # game were copied into every other (2026-11-07)
            (
                "The game's code for a class or a method, e.g. {examples}. A large class lists its "
                'methods; then ask for one.'
            ),
            {'name': {'type': 'string'}},
            ['name'],
        ),
        (
            'calculate',
            'Work out arithmetic exactly, e.g. hypot(3, 4) or (760 - 716) / 154.',
            {'expression': {'type': 'string'}},
            ['expression'],
        ),
        (
            'draw',
            'Draw on the overlay for the player: highlight sprites, mark a point, or a path.',
            {
                'kind': {'type': 'string', 'enum': ['highlight', 'marker', 'path']},
                'sprite_ids': {'type': 'array', 'items': {'type': 'string'}},
                'points': {
                    'type': 'array',
                    'items': {'type': 'array', 'items': {'type': 'number'}},
                },
                'color': {'type': 'string'},
            },
            ['kind'],
        ),
        (
            'run_in_copy',
            (
                'Run Python in a disposable copy of the game, to try anything without touching the '
                'real game.'
            ),
            {'python': {'type': 'string'}},
            ['python'],
        ),
        (
            'screenshot',
            'A picture of a frame of the game.',
            {'frame': {'type': 'integer'}},
            [],
        ),
    )
]

CALCULATOR_FUNCTIONS: dict[str, Any] = {
    'abs': abs,
    'atan2': math.atan2,
    'cos': math.cos,
    'degrees': math.degrees,
    'hypot': math.hypot,
    'max': max,
    'min': min,
    'radians': math.radians,
    'round': round,
    'sin': math.sin,
    'sqrt': math.sqrt,
}
CALCULATOR_CONSTANTS = {'pi': math.pi}


def divided(left: float, right: float) -> float:
    """``left / right``, typed: the standard library's ``operator.truediv`` stub isn't.

    Returns:
        The quotient.

    """
    return left / right


def floor_divided(left: float, right: float) -> float:
    """``left // right``, typed for the same reason.

    Returns:
        The floored quotient.

    """
    return left // right


def raised(base: float, exponent: float) -> float:
    """``base ** exponent``, typed for the same reason.

    Returns:
        The power, as a float.

    """
    return float(base**exponent)


CALCULATOR_BINARY_OPERATORS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: divided,
    ast.FloorDiv: floor_divided,
    ast.Mod: operator.mod,
    ast.Pow: raised,
}
CALCULATOR_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def calculate(*, expression: str) -> float:
    """Work out an arithmetic expression, allowing numbers, operators and a few functions only.

    Anything else is refused by ``evaluated`` with a ValueError naming it.

    Returns:
        Its value.

    """
    return evaluated(ast.parse(expression, mode='eval').body)


def evaluated(node: ast.AST) -> float:
    """Work out one node of an arithmetic expression.

    Returns:
        Its value.

    Raises:
        ValueError: For anything that isn't a number, an allowed operator, constant or function.

    """
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in CALCULATOR_CONSTANTS:
        return CALCULATOR_CONSTANTS[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in CALCULATOR_BINARY_OPERATORS:
        return CALCULATOR_BINARY_OPERATORS[type(node.op)](
            evaluated(node.left), evaluated(node.right)
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in CALCULATOR_UNARY_OPERATORS:
        return CALCULATOR_UNARY_OPERATORS[type(node.op)](evaluated(node.operand))
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in CALCULATOR_FUNCTIONS
        and not node.keywords
    ):
        return CALCULATOR_FUNCTIONS[node.func.id](*(evaluated(item) for item in node.args))
    message = f'not arithmetic: {ast.unparse(node)}'
    raise ValueError(message)


def limited(value: JsonValue, *, limit: int, field_limit: int | None = None) -> JsonValue:
    """Cap every list in a value at a number of items, and each object's fields only if asked.

    Returns:
        The capped value, each cut saying how many more there were.

    """
    if isinstance(value, list):
        items: list[JsonValue] = [
            limited(item, limit=limit, field_limit=field_limit) for item in value[:limit]
        ]
        if len(value) > limit:
            items.append(f'... {len(value) - limit} more')
        return items
    if isinstance(value, dict):
        pairs = list(value.items())
        kept = pairs if field_limit is None else pairs[:field_limit]
        capped: dict[str, JsonValue] = {
            str(key): limited(item, limit=limit, field_limit=field_limit) for key, item in kept
        }
        if len(kept) < len(pairs):
            capped['...'] = f'{len(pairs) - len(kept)} more fields'
        return capped
    return value


def fits(value: JsonValue) -> bool:
    """Whether an answer is short enough to send.

    Returns:
        True when its compact JSON is at most ``MAXIMUM_RESULT_CHARACTERS`` long.

    """
    return len(json.dumps(value, separators=(',', ':'))) <= MAXIMUM_RESULT_CHARACTERS


def fitted(value: JsonValue) -> JsonValue:
    """Shrink an answer to fit ``MAXIMUM_RESULT_CHARACTERS``: lists first, fields next, cut last.

    An object's fields are cut only when shortening its lists wasn't enough, as the fields are
    the answer (cutting them first once lost a ball's worked-out speed).

    Returns:
        The answer, or the start of it with a note saying how to ask for less.

    """
    if fits(value):
        return value
    for limit in LIST_LIMITS:
        candidate = limited(value, limit=limit)
        if fits(candidate):
            return candidate
    for field_limit in FIELD_LIMITS:
        candidate = limited(value, limit=LIST_LIMITS[-1], field_limit=field_limit)
        if fits(candidate):
            return candidate
    text = json.dumps(limited(value, limit=LIST_LIMITS[-1]), separators=(',', ':'))
    return {
        'start': text[:MAXIMUM_RESULT_CHARACTERS],
        'note': 'Too long to show whole: ask for one sprite, one object path or a smaller range.',
    }


def is_sprite_id(value: object) -> bool:
    """Whether a value names a sprite, like BallSprite#2.

    Returns:
        True for a string of a class name, ``#`` and a number.

    """
    return isinstance(value, str) and '#' in value and value.rsplit('#', 1)[1].isdigit()


def compacted(value: JsonValue) -> JsonValue:
    """Drop what's no use to the AI: pictures and long lists of sprite ids, which become counts.

    Returns:
        The value, smaller.

    """
    if isinstance(value, dict):
        if set(value) == {'surface'}:
            return None
        kept = {
            key: compacted(item)
            for key, item in value.items()
            if key not in {'image', 'background', 'background_pattern'}
        }
        return {key: item for key, item in kept.items() if item is not None}
    if isinstance(value, list) and len(value) > SHORT_LIST and all(map(is_sprite_id, value)):
        return f'{len(value)} sprites (list_sprites names them)'
    if isinstance(value, list):
        return [compacted(item) for item in value]
    return value


def with_motion(sprite: dict[str, Any]) -> dict[str, Any]:
    """Add a moving sprite's speed and heading, worked out, in words a player would use.

    Returns:
        The sprite, with ``speed_pixels_per_second`` and ``heading`` when it has a speed.

    """
    speed: JsonValue = sprite.get('speed')
    if not isinstance(speed, dict):
        return sprite
    across, down = speed.get('x'), speed.get('y')
    if not isinstance(across, (int, float)) or not isinstance(down, (int, float)):
        return sprite
    horizontal = 'right' if across > 0 else 'left' if across < 0 else ''
    vertical = 'down' if down > 0 else 'up' if down < 0 else ''
    # First, so they're the last fields an answer too long would lose
    return {
        'speed_pixels_per_second': round(math.hypot(across, down), 1),
        'heading': ' and '.join(part for part in (horizontal, vertical) if part) or 'still',
        **sprite,
    }


def centre(sprite: dict[str, Any]) -> tuple[float, float] | None:
    """A sprite's position: its world position, else its rect's centre.

    Returns:
        x and y, or None when it has neither.

    """
    if isinstance(sprite.get('world_x'), (int, float)) and isinstance(
        sprite.get('world_y'), (int, float)
    ):
        return float(sprite['world_x']), float(sprite['world_y'])
    rect: JsonValue = sprite.get('rect')
    numbers = (
        [number for number in rect if isinstance(number, (int, float))]
        if isinstance(rect, list)
        else []
    )
    if len(numbers) == RECT_NUMBERS:
        left, top, width, height = numbers
        return left + width / 2, top + height / 2
    return None


def unquoted(text: str) -> str:
    """Text without the quotes and spaces 2B sometimes leaves around a name ('"Player#0"').

    Returns:
        The bare name.

    """
    return text.strip().strip('"\'').strip()


def tool_definitions(*, game: str) -> list[dict[str, Any]]:
    """The tools as offered for one game: read_source's examples are the game's own names.

    The same for every question about the game, so the opening stays cached.

    Returns:
        The definitions.

    """
    examples = ' or '.join(f"'{name}'" for name in source_examples(game=game))
    definitions = json.loads(json.dumps(TOOL_DEFINITIONS))
    for definition in definitions:
        function = definition['function']
        function['description'] = function['description'].replace('{examples}', examples)
    return definitions


def source_examples(*, game: str) -> list[str]:
    """Two real names read_source accepts for a game: its scene class and one of its methods.

    Returns:
        The names; the first class and its first method when the game has no scene class.

    """
    classes = game_classes(game)
    scenes = [name for name, cls in classes.items() if issubclass(cls, Scene)]
    class_name = (scenes or list(classes))[0]
    methods = [name for name in code_names(game) if name.startswith(f'{class_name}.')]
    preferred = [name for name in methods if name.endswith('.dt_tick')]
    return [class_name, *(preferred or methods)[:1]]


@functools.cache
def game_classes(game: str) -> dict[str, type]:
    """Every class a game's packages define, by name.

    Returns:
        The classes, defined in the game's own modules (not ones they import).

    """
    classes: dict[str, type] = {}
    for package_name in GAME_PACKAGES.get(game, ()):
        package = importlib.import_module(package_name)
        modules = [package]
        for found in pkgutil.walk_packages(
            getattr(package, '__path__', []), prefix=f'{package_name}.'
        ):
            try:
                modules.append(importlib.import_module(found.name))
            except ImportError:
                continue
        for module in modules:
            for name, candidate in vars(module).items():
                if inspect.isclass(candidate) and candidate.__module__.startswith(package_name):
                    classes.setdefault(name, candidate)
    return classes


def code_names(game: str) -> list[str]:
    """Every name read_source accepts for a game: its classes, and ``Class.method`` for each.

    Returns:
        The names.

    """
    names: list[str] = []
    for class_name, cls in game_classes(game).items():
        names.append(class_name)
        names += [
            f'{class_name}.{member_name}'
            for member_name, member in vars(cls).items()
            if (inspect.isfunction(member) or isinstance(member, property))
            # Python's own hooks (__eq__, __hash__) only crowd the suggestions out
            and (member_name == '__init__' or not member_name.startswith('__'))
        ]
    return names


def named_code(*, name: str, game: str) -> type | types.FunctionType | None:
    """Find a class, or a class's method, in a game's packages.

    A property is its getter, and a static or class method its function: inspect reads source
    only from functions and classes, and failed with a bare TypeError on the others.

    Returns:
        The class or function, or None when the name is neither (a class constant, say).

    """
    class_name, _, method_name = name.partition('.')
    cls = game_classes(game).get(class_name)
    if cls is None:
        return None
    if not method_name:
        return cls
    member: object = vars(cls).get(method_name)
    # A property's code is its getter; a static or class method's is its __func__, which a
    # plain function doesn't have
    member = member.fget if isinstance(member, property) else getattr(member, '__func__', member)
    return member if isinstance(member, types.FunctionType) else None


def suggestions(*, wanted: str, names: list[str]) -> list[str]:
    """The names closest to one that wasn't found, so a wrong guess points the way.

    Returns:
        Up to ``SUGGESTIONS_SHOWN`` names, closest first.

    """
    close = difflib.get_close_matches(wanted, names, n=SUGGESTIONS_SHOWN, cutoff=0.4)
    # A short guess (spawn) can still be found inside a long name (_spawn_new_ball)
    lowered = wanted.lower().rsplit('.', 1)[-1]
    inside = [name for name in names if lowered and lowered in name.lower() and name not in close]
    return (close + inside)[:SUGGESTIONS_SHOWN]


def source_text(*, code: type | types.FunctionType) -> dict[str, Any]:
    """A class's or function's source, with its file and line, or a class's methods when long.

    Returns:
        The source, or the methods to choose from.

    """
    lines, first = inspect.getsourcelines(code)
    source_file = Path(inspect.getsourcefile(code) or '')
    shown_file = (
        source_file.relative_to(Path.cwd())
        if source_file.is_relative_to(Path.cwd())
        else source_file.name
    )
    where = f'{shown_file}:{first}'
    numbered = [f'{first + index}: {line}' for index, line in enumerate(lines)]
    whole: dict[str, JsonValue] = {'where': where, 'source': ''.join(numbered)}
    if fits(whole):
        return whole
    if inspect.isclass(code):
        methods = {
            member_name: (inspect.getdoc(member) or '').split('\n')[0]
            for member_name, member in vars(code).items()
            if inspect.isfunction(member) or isinstance(member, property)
        }
        return {'where': where, 'too_long': 'ask for one method', 'methods': methods}
    # A long function: its first lines, as many as fit once escaped as JSON
    shown = len(numbered)
    while shown > 1 and not fits({'where': where, 'source': ''.join(numbered[:shown]), 'cut': ''}):
        shown -= 1
    return {
        'where': where,
        'source': ''.join(numbered[:shown]),
        'cut': f'{len(numbered) - shown} more lines not shown',
    }


class SnapshotTools:
    """Answer the AI's tool calls from one snapshot, recording every call."""

    def __init__(self, *, snapshot: dict[str, Any]) -> None:
        """Hold the snapshot."""
        self.snapshot = snapshot
        self.calls: list[dict[str, Any]] = []
        self.drawings: list[dict[str, Any]] = []
        self.signatures: set[str] = set()
        self.repeated_calls = 0

    def call(self, *, name: str, arguments: dict[str, Any]) -> JsonValue:
        """Run one tool call by name, as the model asked.

        Returns:
            The tool's answer, fitted to size, or an error the model can read.

        """
        self.calls.append({'name': name, 'arguments': arguments})
        signature = f'{name}:{json.dumps(arguments, sort_keys=True, default=str)}'
        if signature in self.signatures:
            # The answer is already above it: say so rather than spend the context again
            self.repeated_calls += 1
            return {'repeat': 'You asked this already; the answer is above. Use it, or answer.'}
        self.signatures.add(signature)
        handler = getattr(self, f'tool_{name}', None)
        if handler is None:
            return {'error': f'no tool {name}'}
        try:
            return fitted(handler(**arguments))
        except (TypeError, ValueError, KeyError, IndexError, ZeroDivisionError, OSError) as error:
            return {'error': f'{type(error).__name__}: {error}'}

    def tool_get_scene(self) -> dict[str, Any]:
        """The ``get_scene`` tool.

        Returns:
            Its answer.

        """
        counts: dict[str, int] = {}
        for sprite in self.snapshot['sprites'].values():
            counts[sprite['class']] = counts.get(sprite['class'], 0) + 1
        scene = compacted({
            key: value for key, value in self.snapshot['scene'].items() if key != 'all_sprites'
        })
        return {
            'frame': self.snapshot['frame'],
            # compacted keeps a dict a dict; the check is for the type checker
            **(scene if isinstance(scene, dict) else {}),
            'facts': self.snapshot['facts'],
            'sprite_counts': counts,
        }

    def tool_list_sprites(
        self,
        class_name: str | None = None,
        near: str | None = None,
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> object:
        """The ``list_sprites`` tool.

        Returns:
            Its answer.

        """
        sprites = self.snapshot['sprites']
        # 2B sometimes writes "no class" as the word, and sends ids with their quotes on
        class_name = unquoted(class_name) if class_name else None
        if class_name in {'None', 'null'}:
            class_name = None
        if near:
            near = self.resolved_sprite_id(wanted=near) or unquoted(near)
        classes = sorted({sprite['class'] for sprite in sprites.values()})
        if class_name and class_name not in classes:
            return {
                'error': f'no sprites of class {class_name} now',
                'classes_present': classes,
            }
        chosen = [
            (sprite_id, sprite)
            for sprite_id, sprite in sprites.items()
            if class_name in {None, ''} or sprite['class'] == class_name
        ]
        if not class_name and not near:
            counts: dict[str, int] = {}
            for _sprite_id, sprite in chosen:
                counts[sprite['class']] = counts.get(sprite['class'], 0) + 1
            return {'counts_by_class': counts, 'hint': 'give class_name or near to list ids'}
        if near:
            origin = centre(sprites[near]) if near in sprites else None
            if origin is None:
                return {
                    'error': f'no sprite {near} with a position now',
                    'some_ids': self.ids_like(wanted=near),
                }
            placed = [
                (sprite_id, centre(sprite)) for sprite_id, sprite in chosen if sprite_id != near
            ]
            ordered = sorted(
                ((sprite_id, math.dist(origin, where)) for sprite_id, where in placed if where),
                key=operator.itemgetter(1),
            )
            return [
                {'id': sprite_id, 'distance': round(distance)}
                for sprite_id, distance in ordered[:limit]
            ]
        ids = [sprite_id for sprite_id, _sprite in chosen]
        return ids[:limit] + ([f'... {len(ids) - limit} more'] if len(ids) > limit else [])

    def tool_get_sprite(self, sprite_id: str) -> JsonValue:
        """The ``get_sprite`` tool.

        Returns:
            Its answer.

        """
        resolved = self.resolved_sprite_id(wanted=sprite_id)
        sprite = self.snapshot['sprites'].get(resolved) if resolved else None
        if sprite is None:
            some_ids: list[JsonValue] = [*self.ids_like(wanted=sprite_id)]
            return {
                'error': f'no sprite {sprite_id} now: it may have gone, or never existed',
                'some_ids': some_ids,
            }
        return compacted(with_motion(sprite))

    def resolved_sprite_id(self, *, wanted: str) -> str | None:
        """The id 2B meant: as given, unquoted, or a class name with only one sprite of it now.

        Returns:
            The id, or None when it can't be told which sprite was meant.

        """
        sprites = self.snapshot['sprites']
        wanted = unquoted(wanted)
        if wanted in sprites:
            return wanted
        same_class = [
            sprite_id for sprite_id, sprite in sprites.items() if sprite['class'] == wanted
        ]
        return same_class[0] if len(same_class) == 1 else None

    def ids_like(self, *, wanted: str) -> list[str]:
        """Real sprite ids for a wrong one: those of the class it names, else one per class.

        Returns:
            Up to ``SUGGESTIONS_SHOWN`` ids.

        """
        ids = list(self.snapshot['sprites'])
        class_part = wanted.split('#', 1)[0].lower()
        same_class = [
            sprite_id for sprite_id in ids if sprite_id.split('#', 1)[0].lower() == class_part
        ]
        if same_class:
            return same_class[:SUGGESTIONS_SHOWN]
        one_per_class: dict[str, str] = {}
        for sprite_id in ids:
            one_per_class.setdefault(sprite_id.split('#', 1)[0], sprite_id)
        return list(one_per_class.values())[:SUGGESTIONS_SHOWN]

    def tool_get_object(self, path: str = '') -> object:
        """The ``get_object`` tool.

        Returns:
            Its answer.

        """
        node: JsonValue = self.snapshot.get('objects', {})
        walked: list[str] = []
        steps = [part for part in unquoted(path).split('.') if part]
        # Paths start at the scene, but 2B often names it first ('scene.maze'): the same place
        scene_named = steps and steps[0] in {'scene', 'self'}
        if scene_named and not (isinstance(node, dict) and steps[0] in node):
            steps = steps[1:]
        for step in steps:
            if isinstance(node, dict) and step in node:
                node = node[step]
            elif isinstance(node, list) and step.isdigit() and int(step) < len(node):
                node = node[int(step)]
            else:
                # Say what is there, so the next try can take a real step
                answer: dict[str, Any] = {
                    'error': f'nothing at {step!r} in {path!r}',
                    'reached': '.'.join(walked) or '(the scene)',
                }
                if isinstance(node, dict):
                    answer['fields_here'] = (
                        suggestions(wanted=step, names=list(node)) or list(node)[: LIST_LIMITS[0]]
                    )
                elif isinstance(node, list):
                    answer['list_length'] = len(node)
                else:
                    answer['value_here'] = limited(node, limit=SHORT_LIST)
                return answer
            walked.append(step)
        if not path and isinstance(node, dict):
            return {key: type(value).__name__ for key, value in node.items()}
        return compacted(node)

    def tool_history(
        self, from_frame: int = 0, to_frame: int | None = None, sprite_id: str | None = None
    ) -> dict[str, Any]:
        """The ``history`` tool.

        Returns:
            Its answer.

        """
        last = self.snapshot['frame'] if to_frame is None else to_frame
        changes = [
            compacted(entry)
            for entry in self.snapshot['log']
            if from_frame <= entry['frame'] <= last
        ]
        if len(changes) > HISTORY_CHANGES_SHOWN:
            half = HISTORY_CHANGES_SHOWN // 2
            changes = [
                *changes[:half],
                f'... {len(changes) - 2 * half} more changes',
                *changes[-half:],
            ]
        answer: dict[str, Any] = {'changes': changes}
        if sprite_id:
            track = [
                {'frame': entry['frame'], **entry['sprites'][sprite_id]}
                for entry in self.snapshot['window']
                if sprite_id in entry['sprites'] and from_frame <= entry['frame'] <= last
            ]
            step = max(1, len(track) // TRACK_POINTS_SHOWN)
            answer['track'] = track[::step][:TRACK_POINTS_SHOWN]
        if self.snapshot['window']:
            answer['tracks_cover_frames'] = [
                self.snapshot['window'][0]['frame'],
                self.snapshot['window'][-1]['frame'],
            ]
        return answer

    def tool_read_source(self, name: str) -> dict[str, Any]:
        """The ``read_source`` tool.

        Returns:
            Its answer.

        """
        game = self.snapshot['game']
        code = named_code(name=name, game=game)
        if code is None:
            names = code_names(game)
            return {
                'error': f'no class or method {name} in this game',
                'closest_names': suggestions(wanted=name, names=names),
                'classes': list(game_classes(game))[: LIST_LIMITS[0]],
            }
        return source_text(code=code)

    def tool_calculate(self, expression: str) -> dict[str, Any]:
        """The ``calculate`` tool.

        Returns:
            Its answer.

        """
        try:
            value = calculate(expression=expression)
        except (TypeError, ValueError, KeyError, ZeroDivisionError, SyntaxError) as error:
            return {
                'error': f'{type(error).__name__}: {error}',
                'allowed': 'numbers, + - * / // % **, parentheses, pi, and '
                + ', '.join(sorted(CALCULATOR_FUNCTIONS)),
            }
        return {'expression': expression, 'value': value}

    def tool_draw(self, kind: str, **details: Any) -> dict[str, Any]:
        """The ``draw`` tool.

        Returns:
            Its answer.

        """
        self.drawings.append({'kind': kind, **details})
        return {'drawn': kind}

    def tool_run_in_copy(self, python: str) -> dict[str, Any]:
        """The ``run_in_copy`` tool.

        Returns:
            Its answer.

        """
        return {**NEEDS_THE_MIRROR, 'python_received': len(python)}

    def tool_screenshot(self, frame: int | None = None) -> dict[str, Any]:
        """The ``screenshot`` tool.

        Returns:
            Its answer.

        """
        return {**NEEDS_THE_MIRROR, 'frame': frame}


def tool_result_text(result: JsonValue) -> str:
    """Write a tool's answer as the model will read it.

    Returns:
        Compact JSON.

    """
    return json.dumps(result, separators=(',', ':'))
