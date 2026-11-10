# Whole-stack documentation scrub

Part of the 2026-11-02 backlog run (the owner's explicit permission to plan, fix, commit, test
and push each item on its own branch). The request: `plans/future-work.md`, "Documentation
scrub". Done last, after the run's other branches land, since they change docs too (#178.26,
#190, #225/#227, #251, #256, sprite tags, solid collision).

The site's Material formatting (the owner, 2026-11-09) goes first, page by page:
`plans/2026-11-09-docs-material-formatting.md`. Its conventions (which passages become
admonitions, tabs, collapsible blocks or titled code) hold for every page this scrub edits.
#145 landed the Material theme, the explorers and this plan before the reading pass below; the
reading pass is its own branch.

## Design

**What is scrubbed (73 documents, then the engine's module docstrings):**

| Area | Count | What |
|---|---|---|
| Root | 8 | `README.md`, `CLAUDE.md`, `ANIMATION_README.md`, `API_README.md`, `BITMAPPY_ARCHITECTURE.md`, `CONTROLLER_CONTROLS_README.md`, `LOADER_README.md`, `TEST_UPDATE_PLAN.md` |
| `docs/` | 51 | architecture, playback, games, quality (the mkdocs site; not `docs/specs/`) |
| Audio | the sound engine | `src/glitchygames/audio/` and what uses it (#147, landed 2026-11-04): see below |
| Members | 13 | each `src/games/*`, `src/demos/*`, `src/apps/bitmappy`, `src/quicklook` README |
| Docstrings | the engine's modules | module docstrings that describe behavior (`src/glitchygames/**/__init__` and each module's opening docstring) |

`plans/` and `docs/specs/` are records of decisions, not descriptions of the code: they are left
as written (a dated plan describes the code of its date), except where living docs point readers
at them as current.

**How a claim is checked.** Two passes per area:

1. **Mechanical (a script, then kept as checks where cheap).** `scripts/docs_claims.py` (run as
   `uv run python -m scripts.docs_claims`) lists every claim a machine can check that does not
   hold, read from the code's syntax trees (nothing imported):
   - a repository path that does not exist (one guard exists:
     `test_living_documentation_writes_repository_paths_from_the_repository_root`, for the
     `src/` layout; this checks existence);
   - a backticked Python file name no tracked file has;
   - a backticked dotted Python name of the project's (`module.name`, `Class.member`, an instance
     named for its class, `camera.update()`) that is not defined. Bare calls (`get_pos()`) are
     not checked: without a module there is no telling whose they are (most are pygame's);
   - a backticked command-line option that no tracked Python file or project configuration
     spells. (Documented defaults are left to the reading pass: the parsers are spread over the
     engine, the games and the tools, and a default is often computed);
   - a `BUGS.md #N` reference whose wording ("open", "until", "workaround") contradicts the
     entry's Fixed or Closed status.

   The report is the worklist. Checks that prove cheap and stable (names, options) become tests
   beside the path guard, so drift is caught when it happens, not at the next scrub.
2. **Reading.** Each document is read against the code it describes, for what no script can
   check: behavior described wrongly, steps that no longer apply, sections that duplicate a page
   in `docs/`. American spellings throughout.

**Audio (the owner's addition, 2026-11-04: "re-audit the tree around the audio engine, so we
cover that properly in the docs").** #147 added the sound engine: 16 modules in
`src/glitchygames/audio/`, `replay/tools/sound_tools.py`, the Audio debug panel
(`debug/panels.py`), the CRT power-on sound, the instrument catalog, the Sound Board demo and
the M1 specs. `docs/architecture/sound.md` covers using it (one call, short names, cache modes,
voices and buses, accounting, the panel, the catalog, offline rendering), but nothing maps the
package: 9 of the 16 modules (`spec`, `pitch`, `voices`, `waves`, `offline`, `assets`,
`accounting`, `live`, `recipes`; `exceptions`, `synth`) are named in no living document, and
nothing says how a sound flows from its TOML through them to a channel. This area:
- reads the audio package and its callers (scenes, the engine's options, replay, the debug
  panel, the sound tools, the games' `sounds` modules) against `sound.md`, `CLAUDE.md`'s audio
  section, `engine_context.md`'s audio keys, `argument_system.md`'s sound options and the Sound
  Board's README;
- adds to `sound.md` a map of the package: each module's job, and the path a sound takes
  (spec, library and assets, render and voices, buses, the engine), the shims (`synth`, `live`,
  `recipes`) marked as such; and the sound tools' commands;
- checks the audio modules' docstrings with the engine's (step 5), and that the API reference
  (`docs/glitchygames/audio/`) lists every public module.

**Root files: keep, fold or retire.** Each root Markdown file is decided once: still current and
needed at the root (`README.md`, `CLAUDE.md`), folded into the matching `docs/` page (the
architecture and controls READMEs), or retired because `docs/` already says it better. Retiring
a file is listed in the PR for the owner's review rather than done silently.

**Review shape.** One commit per area (root, docs/architecture, docs/playback, docs/games,
docs/quality, audio, member READMEs, engine docstrings), so each is reviewable alone; reading-pass areas
can run in parallel (one reviewer each), the mechanical report first so every reviewer starts
from the same worklist.

**Done when:** the claims report is empty (or every remaining line is a recorded exception),
`mkdocs build --strict` passes, the docs guard tests pass, and the full suite is green.

## Plan

1. Wait for the backlog run's branches to land; rebase onto `main`. (Done 2026-11-04: `main`
   at 380a33d4, with #143, #147, #149.)
2. `scripts/docs_claims.py` with tests; run it; commit the report's worklist into this plan.
   (Done: the worklist below.)
3. Root files: decide keep, fold or retire; fix what stays.
4. `docs/` by area (architecture, playback, games, quality), one commit each; then audio.
5. Member READMEs; engine module docstrings.
6. Promote the cheap checks to tests beside the path guard.
7. `mkdocs build --strict`, the docs guard tests, the full suite; push; PR.

## Worklist (scripts/docs_claims.py)

2026-11-04, first run: 68 claims in 11 documents. The owner's decisions the same day:
- `TEST_UPDATE_PLAN.md`: removed once verified accounted for (it was: the YAML and INI
  rejection tests, static and animated, and the unsupported-format message are in
  `tests/sprites/test_sprite_file_formats.py`; TOML save and load are tested; the factory
  detects `.yaml` only to name it in its refusal). One stale docstring found and fixed with it:
  `bitmappy/canvas_interfaces.py` `save()` said it wrote `"ini" or "yaml"`.
- `docs/galimore.md`: kept for future work; not checked (`UNCHECKED_DOCUMENTS`: its paths and
  names are another code base's).
- Member-relative paths (`tests/fixtures/replays/`, each game's) are right as written: the
  checker looks for a path in every member as well as at the root.
- Stale names updated. On reading, all but the docstring were right and only looked stale: the
  context slots and random streams are strings (now written quoted), a gh-pages `REF:PATH` is
  another ref's path (the checker skips a path after a colon), and the rest name deleted or
  moved things as deleted or moved (recorded exceptions, each with its reason).
- `docs/architecture/game_packages.md`: planned (below) and done. The move recipe became
  "Adding a member", from the Sound Board demo's diff (e8e88b44) and what
  `tests/test_workspace_config.py` checks; it names the entries no test checks
  (`[tool.glitchygames] games` for a member with no recording, a demo's deptry `DEP002`, the
  mkdocstrings `paths`, which only the docs build catches) and the hand-written tables a fresh
  member also needs (`tests/test_logical_names.py`, `EXPECTED_ALL_CONSOLE_SCRIPTS`,
  `OUR_GAMES`). Its sample `pyproject.toml` was stale (no engine floor, no declared imports).
  The special case keeps its name, "A game that is one module", which five `pyproject.toml`
  comments cite. The history section names the emptied places (recorded exceptions).
- Found with it, stale counts since the Sound Board demo: "the three demos" (`pyproject.toml`,
  `tests/workspace_expectations.py`) and "the nine members" (`tests/workspace_expectations.py`,
  `docs/architecture/gameplay_replay.md`); now four and ten.

After those: 0 claims. The reading pass (steps 3-7) is next.

## `docs/architecture/game_packages.md`

### Design

**What is wrong.** Its claims report holds 12 stale paths and names (`src/glitchygames/
examples/`, `tests/examples`, `glitchygames.bitmappy`, `src/paddleslap/__init__.py`,
`docs/glitchygames/examples/index.md`, PaddleSlap "a game that is one module" `paddleslap.py`),
but the larger problem is its shape. Over half the page (its lines 139-367, nine steps) is the
recipe for moving a game out of the engine's `examples` package, which is finished (Part 3,
2026-10-26): every game, demo and Bitmappy are members. What a reader needs now, adding a new
game, demo or app, has no recipe: the page says only "a new game or demo starts as a fresh
member". (`scripts/create.py` makes a cookiecutter template game, not a member.) The one member
added fresh, the Sound Board demo (#147), is the ground truth for what adding one takes.

**The page after.** Same title and place (five game pages and `bitmappy.md` link to it; no link
names an anchor):

1. **The layout**, **What a member is**, **Working with a member**: kept; each list and command
   checked against the workspace (the layers' members, the extras, `uv sync` flags).
2. **Adding a member** (new; replaces the move recipe as the page's recipe): create the member
   (`pyproject.toml`, `README.md`, `src/<package>/`, `tests/` with the subject-named move tests
   a fresh member has: `_logical_names`, `_install_location` without the old-example check,
   `_entry_points`, and `_wheel`/`_package_data` when it ships data); register it in the root
   configuration (the table of files and keys, re-derived from #147's sound-board-demo diff
   and from what `tests/test_workspace_config.py` now derives on its own, so the table lists
   only what a person must write); the engine's tables (`MEMBER_LAYERS`); a game's golden
   inputs, scripted-session and golden-trace tables and the cross-member expectations
   (`tests/workspace_expectations.py`), for a game only; the browser build (games only: demos
   have none); its docs page and API page; verify (the existing step 8 commands, without the
   move's); commit (the `replay-metrics` hook).
3. **Special cases**: kept, in the present tense: several games in one member (Brave
   Adventurer), a game whose package is its `__init__` (PaddleSlap: `Game` must stay in
   `src/games/paddleslap/src/paddleslap/__init__.py` for its logical name), bundled demos,
   engine-private names, the member-test seams exemption.
4. **Pitfalls**: the ones that apply to any member (the dev tools, the coverage gate on a
   subset, the console script needing `--all-packages`).
5. **History: the moves out of the engine** (new, short): what moved and when (the plans);
   what still matters for old recordings and old checkouts: logical names did not change for
   games already in a layer, Bitmappy's did (`glitchygames.bitmappy.editor` ->
   `apps.bitmappy.editor`, converted by a rebaseline), `recording-renames` keeps moved
   recordings' ledger history, and a checkout from before the moves can hold ignored
   leftovers (`src/glitchygames/examples`, `src/glitchygames/bitmappy`, `tests/examples`) that
   the members' `test_the_old_example_module_is_gone` and
   `test_the_engines_examples_directory_is_gone` catch (`rm -rf` them). The step-by-step move
   recipe itself is left to the plans that record it (`plans/2026-10-24-workspace-packages*.md`).

**Not changed:** the members, the configuration, the tests. If writing "Adding a member" finds
a step the workspace guards do not catch, it is reported, not fixed here.

**Done when:** `scripts/docs_claims.py` lists nothing for the page (no recorded exception
needed: history names old paths in prose a reader sees as history, so the history section
writes them without backticks only where they are not claims; where they are, as exceptions
with the reason), `mkdocs build --strict` passes, and `CLAUDE.md:231` ("the recipe is
docs/architecture/game_packages.md") still reads true.

### Plan

1. Inventory: list every file and key #147 touched to add `sound-board-demo` (`git show
   e8e88b44 -- pyproject.toml pyrightconfig.json noxfile.py mkdocs.yml wily.cfg`), and what
   `tests/test_workspace_config.py` checks; from them, the "register it" table.
2. Re-check sections 1 (layout, member, working) against the workspace; fix what differs.
3. Write "Adding a member" from the inventory and the old steps 2-9 (keeping what applies to a
   fresh member).
4. Rewrite the special cases and pitfalls in the present tense with today's paths; write the
   history section; delete the move recipe.
5. `scripts/docs_claims.py` (nothing for the page), `mkdocs build --strict`, the docs guard
   tests; commit as the page's own commit in the docs/architecture area.
