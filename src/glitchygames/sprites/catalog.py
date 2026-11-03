"""A catalog of sprite files' text: name, description and tags, searched and exported.

Each sprite file is read for its ``[sprite]`` text only (no pixels): its path, name, description
and tags (``glitchygames.sprites.tags``). ``search_sprites`` finds sprites by fuzzy matching with
the standard library (``difflib``): each word of the query against each tag's words, the name's
words and the description's words, tags weighted most, so ``swords`` still finds a sprite tagged
``sword``. ``export_sprite_texts`` writes one JSON line per sprite, its path the key, with a
``text`` field joining name, description and tags, ready for embedding into a vector store.

Command line::

    python -m glitchygames.sprites.catalog search QUERY PATH...
    python -m glitchygames.sprites.catalog export OUTPUT.jsonl PATH...

A PATH is a sprite file or a directory searched (recursively) for ``*.toml`` files; a TOML file
without a ``[sprite]`` table is not a sprite and is skipped. Design:
plans/2026-11-02-sprite-tags.md.
"""

from __future__ import annotations

import argparse
import difflib
import json
import logging
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from glitchygames.exit_codes import ExitCode
from glitchygames.sprites.tags import TAGS_KEY, normalize_sprite_tags

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

log = logging.getLogger('game.sprites.catalog')

# How alike two words must be to match (difflib's ratio: 1.0 the same word); 0.8 matches a plural
# or a one-letter slip in a word of five or more letters
WORD_MATCH_THRESHOLD = 0.8
# What a matching word counts for, by where it matched: a tag says what the sprite is
TAG_WEIGHT = 3.0
NAME_WEIGHT = 2.0
DESCRIPTION_WEIGHT = 1.0
# How many matches a search returns unless asked
DEFAULT_SEARCH_LIMIT = 10


@dataclass(frozen=True)
class SpriteText:
    """A sprite file's text: what search and export read.

    Attributes:
        path: The sprite file.
        name: ``[sprite] name`` ('' when the file names none).
        description: ``[sprite] description`` ('' when none).
        tags: ``[sprite] tags``, in their one spelling.

    """

    path: Path
    name: str
    description: str
    tags: tuple[str, ...]

    def text(self: SpriteText) -> str:
        """Return the sprite's text as one passage, for an embedding model.

        Returns:
            The name, the description and the tags, each that is present, as sentences.

        """
        parts = [part for part in (self.name, self.description) if part]
        if self.tags:
            parts.append(f'Tags: {", ".join(self.tags)}')
        return '. '.join(part.rstrip('.') for part in parts) + ('.' if parts else '')


@dataclass(frozen=True)
class SpriteMatch:
    """A sprite a search found, with its score (higher matches the query better).

    Attributes:
        sprite: The sprite's text.
        score: The sum, over the query's words, of each word's best weighted match.

    """

    sprite: SpriteText
    score: float


def read_sprite_text(path: Path) -> SpriteText | None:
    """Read a sprite file's text, or None for a TOML file that is not a sprite.

    A file that is not valid TOML raises tomllib's ``TOMLDecodeError`` (``read_sprite_texts``
    logs and skips it).

    Args:
        path: The file.

    Returns:
        The text, or None when the file has no ``[sprite]`` table.

    """
    with path.open('rb') as file:
        data = tomllib.load(file)
    sprite = data.get('sprite')
    if not isinstance(sprite, dict):
        return None
    sprite_table = cast('dict[str, Any]', sprite)
    return SpriteText(
        path=path,
        name=str(sprite_table.get('name', '')),
        description=str(sprite_table.get('description', '')),
        tags=tuple(normalize_sprite_tags(sprite_table.get(TAGS_KEY))),
    )


def read_sprite_texts(paths: Iterable[Path]) -> list[SpriteText]:
    """Read every sprite file at the paths (a directory: every ``*.toml`` under it), in order.

    A TOML file that is not a sprite is skipped; one that is not valid TOML is logged and
    skipped.

    Args:
        paths: Sprite files and directories.

    Returns:
        The sprites' texts, by path.

    """
    files: set[Path] = set()
    for path in paths:
        files.update(path.rglob('*.toml') if path.is_dir() else {path})
    texts: list[SpriteText] = []
    for file in sorted(files):
        try:
            text = read_sprite_text(file)
        except tomllib.TOMLDecodeError as error:
            log.warning('Skipping %s: not valid TOML (%s)', file, error)
            continue
        if text is not None:
            texts.append(text)
    return texts


def _words(text: str) -> list[str]:
    """Return a text's words, case-folded, without the punctuation around them.

    Returns:
        The words.

    """
    return [
        word.strip('.,;:!?"\'()[]')
        for word in text.casefold().split()
        if word.strip('.,;:!?"\'()[]')
    ]


def _best_match(word: str, candidates: Iterable[str]) -> float:
    """Return how well a word matches its best candidate (0.0 below the match threshold).

    Returns:
        difflib's ratio for the best candidate, or 0.0.

    """
    best = 0.0
    for candidate in candidates:
        ratio = difflib.SequenceMatcher(None, word, candidate).ratio()
        best = max(best, ratio)
    return best if best >= WORD_MATCH_THRESHOLD else 0.0


def score_sprite(query: str, sprite: SpriteText) -> float:
    """Return how well a sprite matches a query: each query word's best weighted match, summed.

    Args:
        query: The search, in any case.
        sprite: The sprite's text.

    Returns:
        The score; 0.0 when no word matches.

    """
    tag_words = [word for tag in sprite.tags for word in tag.split()]
    name_words = _words(sprite.name)
    description_words = _words(sprite.description)
    return sum(
        max(
            TAG_WEIGHT * _best_match(word, tag_words),
            NAME_WEIGHT * _best_match(word, name_words),
            DESCRIPTION_WEIGHT * _best_match(word, description_words),
        )
        for word in _words(query)
    )


def search_sprites(
    query: str, sprites: Iterable[SpriteText], *, limit: int = DEFAULT_SEARCH_LIMIT
) -> list[SpriteMatch]:
    """Return the sprites matching a query, best first (ties by path), at most ``limit``.

    Args:
        query: The search.
        sprites: The sprites to search.
        limit: How many matches at most.

    Returns:
        The matches with a score above 0.

    """
    matches = [SpriteMatch(sprite=sprite, score=score_sprite(query, sprite)) for sprite in sprites]
    found = [match for match in matches if match.score > 0]
    found.sort(key=lambda match: (-match.score, str(match.sprite.path)))
    return found[:limit]


def export_sprite_texts(sprites: Iterable[SpriteText], output: Path) -> int:
    """Write one JSON line per sprite (path, name, description, tags, text) for embedding.

    Args:
        sprites: The sprites.
        output: The JSON lines file to write.

    Returns:
        How many sprites were written.

    """
    count = 0
    with output.open('w', encoding='utf-8') as file:
        for sprite in sprites:
            record = {
                'path': str(sprite.path),
                'name': sprite.name,
                'description': sprite.description,
                'tags': list(sprite.tags),
                'text': sprite.text(),
            }
            file.write(json.dumps(record, ensure_ascii=False) + '\n')
            count += 1
    return count


def build_parser() -> argparse.ArgumentParser:
    """Return the command line's parser: ``search`` and ``export``.

    Returns:
        The parser.

    """
    parser = argparse.ArgumentParser(
        prog='python -m glitchygames.sprites.catalog',
        description='Search sprite files by name, description and tags, or export their text.',
    )
    commands = parser.add_subparsers(dest='command', required=True)
    search = commands.add_parser('search', help='list the sprites matching a query, best first')
    search.add_argument('query', help='the words to look for')
    search.add_argument('paths', nargs='+', type=Path, help='sprite files or directories')
    search.add_argument('--limit', type=int, default=DEFAULT_SEARCH_LIMIT, help='most matches')
    export = commands.add_parser('export', help='write each sprite as a JSON line, to embed')
    export.add_argument('output', type=Path, help='the JSON lines file to write')
    export.add_argument('paths', nargs='+', type=Path, help='sprite files or directories')
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the command line.

    Args:
        arguments: The arguments after the program's name (None: ``sys.argv[1:]``).

    Returns:
        ``ExitCode.SUCCESS``; ``ExitCode.MISSING_INPUT`` when a path does not exist;
        ``ExitCode.CANNOT_WRITE_OUTPUT`` when the export cannot be written. argparse exits
        with ``ExitCode.ARGUMENT_PARSER_ERROR`` itself on a usage error.

    """
    parsed = build_parser().parse_args(arguments)
    missing = [path for path in parsed.paths if not path.exists()]
    if missing:
        sys.stderr.write(f'No such file or directory: {", ".join(map(str, missing))}\n')
        return ExitCode.MISSING_INPUT
    sprites = read_sprite_texts(parsed.paths)
    if parsed.command == 'search':
        for match in search_sprites(parsed.query, sprites, limit=parsed.limit):
            tags = f'  [{", ".join(match.sprite.tags)}]' if match.sprite.tags else ''
            sys.stdout.write(
                f'{match.score:5.2f}  {match.sprite.path}  {match.sprite.name}{tags}\n'
            )
        return ExitCode.SUCCESS
    try:
        count = export_sprite_texts(sprites, parsed.output)
    except OSError as error:
        sys.stderr.write(f'Cannot write {parsed.output}: {error}\n')
        return ExitCode.CANNOT_WRITE_OUTPUT
    sys.stdout.write(f'Wrote {count} sprites to {parsed.output}\n')
    return ExitCode.SUCCESS


if __name__ == '__main__':  # pragma: no cover - the command line's entry; main is tested
    sys.exit(main())
