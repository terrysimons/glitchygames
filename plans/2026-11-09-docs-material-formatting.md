# The docs site in Material's formatting

The owner, 2026-11-09: the site moved to the Material theme (#145, `d4257fb5`: mkdocs < 2.0,
`zensical.yml` with `mkdocs.yml` a link to it); now the pages and the theme's configuration should
use what Material offers. The pages stay markdown: Material's formatting is markdown syntax
(Python-Markdown and PyMdown Extensions), so every page is still a `.md` file edited as text.
It stays Material, with mkdocs pinned below 2.0 (the owner, 2026-11-09); the move to Zensical
comes later (`plans/future-work.md`, "Move the docs site to Zensical"). Zensical is Material's
successor from the same team and reads the same markdown and the same configuration, so nothing
written here is lost by that move.

Part of the documentation scrub (`plans/2026-11-02-whole-stack-docs-scrub.md`): its reading pass
opens every page, so each page is reformatted in the same visit.

## Where it stands

| Material feature | Used now |
|---|---|
| Admonitions (`!!! note`) | 6, in `event_system.md` and `requirements.md` |
| Content tabs (`=== "..."`) | 3, on the requirements page |
| Titled or annotated code blocks | 0 of 329 |
| Collapsible blocks (`???`) | 0 |
| Material icons | 0 |
| Blockquotes doing a callout's job | 24, all in `quality/upstream_issues.md` |
| Light/dark palette, logo, favicon | none |
| Code copy buttons, search suggestions, edit links, footer links | off |

53 pages, about 15,300 lines. The largest: `architecture/event_system.md` (2,728),
`gameplay_replay.md` (1,138), the four game pages (634-808), `bitmappy.md` (557). Most raw HTML in
the pages is `<br/>` inside Mermaid labels, which stays.

## Design

### Part 1: the theme's configuration (`zensical.yml`)

One commit, no page changes:

- **Palette**: light and dark, following the reader's system setting, with the toggle in the
  header (`palette` with `media: "(prefers-color-scheme: ...)"`); primary color indigo, as now.
  The explorers already read Material's colour variables, and `performance.js` picks its dark
  palette from `data-md-color-scheme="slate"`; `complexity.js` and `requirements.js` are checked
  the same way. Mermaid follows the scheme: `js/mermaid-config.js` sets Mermaid's `dark` theme on
  slate (Material re-renders its diagrams when the scheme changes; to verify with all 96 event
  system diagrams).
- **Features**: `content.code.copy` (a copy button on every code block), `content.code.annotate`,
  `content.action.edit` with `edit_uri: edit/main/docs/` (an "Edit this page" link to the file on
  GitHub's main), `navigation.footer` (previous and next page), `search.suggest`,
  `search.highlight`, `search.share`, `content.tooltips` (abbreviations and link titles as
  tooltips).
- **Markdown extensions**: `def_list` (option and term lists), `footnotes`, `abbr` with
  `pymdownx.snippets`' `auto_append` of one glossary file (`docs/includes/abbreviations.md`: SDL,
  FPS, p99, CI ... explained on hover everywhere), `pymdownx.emoji` with Material's icon index
  (`:material-...:`, `:octicons-...:`), `pymdownx.highlight` with `line_spans` and
  `pygments_lang_class` (needed by annotations).
- **Logo and favicon**: a sprite of ours drawn as a PNG/SVG (the owner picks which; a Bitmappy
  library sprite or a game's hero), `theme.logo` and `theme.favicon`.
- Left out unless the owner wants them: last-updated dates (the `git-revision-date-localized`
  plugin: a new dependency, and every build walks git history per page), social cards (need
  Cairo), blog, tags.

### Part 2: the pages

What each kind of passage becomes (the conventions; written into the top of the scrub plan's
reading checklist so every page gets the same treatment):

| Passage | Becomes |
|---|---|
| A caveat, gotcha or rule a reader must not miss ("never read a world sprite's rect in game logic") | `!!! warning "<the rule>"` |
| A side note, history or design reason | `!!! note` (or `!!! info` for background) |
| A recommended way of doing something | `!!! tip` |
| A long reference table or listing a reader scans only when they need it (more than about 40 lines: every event's fields, every exit code) | `??? note "<what it is>"` (collapsed), or `???+` (open, collapsible) when most readers want it |
| The same command or snippet per platform or per front end (`<game> --flag` and `glitchygames subcommand`) | content tabs (`=== "macOS"`, `=== "Raspberry Pi"`) |
| A code excerpt from a file | `title="src/glitchygames/clock.py"` on its fence |
| A code excerpt whose lines need explaining | annotations (`# (1)!` plus a numbered list after) instead of prose that points at line numbers |
| An option or term list written as "**--x**: does y" lines | a definition list |
| A bug write-up (`upstream_issues.md`'s blockquotes) | `!!! bug "<title>"` |

Not converted: prose that reads fine as prose (an admonition per paragraph is noise), Mermaid
diagrams (unchanged), the generated API reference pages (mkdocstrings' own output), `docs/specs/`
and `plans/` (records of decisions, left as written, as the scrub plan says), and the root
`*.md` files (GitHub renders them, and shows `!!! note` as plain text).

Order (the most read first, each page one commit or a few):

1. `index.md` (Getting Started), `requirements.md`.
2. `architecture/`: `gameplay_replay.md`, `playback/` (5 pages), `event_system.md` (the largest:
   its per-event tables become collapsible blocks), `engine_context.md`, `argument_system.md`,
   `sound.md`, `game_packages.md`, `bitmappy.md`.
3. `games/` (5 pages).
4. `quality/` (`performance.md`, `complexity.md`, `driver_comparison.md`, `upstream_issues.md`).
5. `multi_controller_system.md`, `galimore.md`, the rest.

### Checks

- `nox -s lint-docs` (the strict build) after each commit.
- Headless Chrome screenshots of each changed page in light and dark (the scratch script used
  for the explorers), Mermaid diagrams included.
- A test in `tests/test_workspace_config.py` that the features this plan turns on stay on (the
  palette's two schemes, `content.code.copy`, `content.action.edit` with `edit_uri`), as it
  already checks the nav.
- The scrub plan's `scripts/docs_claims.py` runs unchanged: admonitions and tabs keep their text
  in the markdown, so its claims are still found.

## Decisions for the owner

1. The logo and favicon: which sprite.
2. Last-updated dates: worth a plugin and a slower build?
3. Whether the content pass waits for the scrub's reading pass (one visit per page, slower to
   start) or goes first page by page (sooner, but each page is opened twice).

## Plan

- [ ] Part 1: the configuration commit; dark-mode check of every explorer and Mermaid; the
      configuration test.
- [ ] The glossary file (`docs/includes/abbreviations.md`).
- [ ] Part 2, in the order above; each page's commit names the conventions it applied.
- [ ] `CLAUDE.md`'s documentation note: the formatting conventions, one line pointing here.
