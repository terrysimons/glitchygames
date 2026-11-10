# Sprite tags

Part of the 2026-11-02 backlog run (the owner's explicit permission to plan, fix, commit, test
and push each item on its own branch). The request: `plans/future-work.md`, "Sprite tags".

## Design

**What a tag is.** A plain, free-form word or phrase saying what kind of thing a sprite is
(`item`, `weapon`, `sword`), for fuzzy search and for handing sprites to an LLM or a vector store.
One list per sprite (decided 2026-11-02: no controlled vocabulary, no separate kind field, no
per-animation tags; any of them can come later on top of the list).

**The file.** An optional array of strings in `[sprite]`, written after `description`:

```toml
[sprite]
name = "Sword"
description = "A short iron sword"
tags = ["item", "weapon", "sword"]
```

A file without `tags` loads with none and is written without the key, so every existing sprite
file is unchanged by a save.

**Normalization (the design's open question, decided here).** One spelling per tag, so matching
never depends on how a tag was typed: each tag is stripped, case-folded, and its runs of
whitespace become one space; an empty tag is dropped, and a repeat (after normalizing) is dropped,
keeping the first. Order is kept. Plurals are not merged (`swords` and `sword` stay two tags):
that needs a stemmer, and fuzzy search already scores them as close.

**Malformed tags.** `tags` that is not an array, or an item that is not a string, is logged and
skipped on load (as an unknown glyph draws magenta rather than refusing the file); the sprite-file
checks (`glitchygames.testing.sprite_files`) fail on it, so shipped sprites stay clean.

**Where tags go.**

- Engine: `glitchygames/sprites/tags.py` (`normalize_sprite_tags`, `sprite_tags_problems`, the
  TOML writer); `AnimatedSprite.tags` loaded by its loader, written by both writers (single-frame
  and animated), copied with the rest of the metadata, and in `check_metadata_survives_a_save_
  round_trip`'s metadata. `check_sprite_tags_are_well_formed` joins the sprite-file checks.
- Bitmappy: tags survive load and save (the canvas saves through `AnimatedSprite`); the AI is
  asked for tags in what it generates (its prompt and the TOML it writes), and its training
  example choice scores tags above name words (+8 per request word that is a tag, beside the +5
  per name word). The training examples carry the example's tags.
- Search and export: `glitchygames/sprites/catalog.py` reads each sprite file's text (path,
  name, description, tags; only `[sprite]`, no pixels), searches it fuzzily with the standard
  library (`difflib`; no new dependency): each query word against each tag, the name's words and
  the description's words, tags weighted most; and exports it as JSON lines (one sprite per line,
  its path the key, with a `text` field joining name, description and tags) for embedding into a
  vector store. Command line: `python -m glitchygames.sprites.catalog search QUERY PATH...` and
  `... export OUTPUT PATH...` (a path is a sprite file or a directory searched for `*.toml`).

**Deferred.** Editing tags in Bitmappy's UI: its only text box is the AI prompt (which shows the
description), so editing needs its own UI design. QuickLook ignores `[sprite]` keys it does not
draw (as it ignores `description`): nothing to change there.

## Plan

1. `tags.py` with tests (normalization, problems, the writer's TOML).
2. `AnimatedSprite`: load, both writers, the metadata copy and dictionary; tests including a
   round trip and a file without tags written unchanged.
3. Sprite-file checks: metadata includes tags; the well-formed check; run on every shipped sprite.
4. Bitmappy: the AI writer and prompt, the training examples and scoring; tests.
5. `catalog.py`: read, search, export, command line; tests.
6. Docs: the sprite file format reference, Bitmappy's AI notes, `plans/future-work.md` (done).
7. Full suite, type checks; commit, push, PR.
