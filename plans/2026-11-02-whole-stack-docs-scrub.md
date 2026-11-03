# Whole-stack documentation scrub

Part of the 2026-11-02 backlog run (the owner's explicit permission to plan, fix, commit, test
and push each item on its own branch). The request: `plans/future-work.md`, "Documentation
scrub". Done last, after the run's other branches land, since they change docs too (#178.26,
#190, #225/#227, #251, #256, sprite tags, solid collision).

## Design

**What is scrubbed (about 170 documents):**

| Area | Count | What |
|---|---|---|
| Root | 8 | `README.md`, `CLAUDE.md`, `ANIMATION_README.md`, `API_README.md`, `BITMAPPY_ARCHITECTURE.md`, `CONTROLLER_CONTROLS_README.md`, `LOADER_README.md`, `TEST_UPDATE_PLAN.md` |
| `docs/` | 49 | architecture, playback, games, quality (the mkdocs site) |
| Members | ~13 | each `src/games/*`, `src/demos/*`, `src/apps/bitmappy`, `src/quicklook` README |
| Docstrings | the engine's modules | module docstrings that describe behavior (`src/glitchygames/**/__init__` and each module's opening docstring) |

`plans/` and `docs/specs/` are records of decisions, not descriptions of the code: they are left
as written (a dated plan describes the code of its date), except where living docs point readers
at them as current.

**How a claim is checked.** Two passes per area:

1. **Mechanical (a script, then kept as checks where cheap).** `scripts/docs_claims.py` lists, per
   document, every claim a machine can check, and whether it holds:
   - a repository path (one guard exists: `test_living_documentation_writes_repository_paths_
     from_the_repository_root`; this also checks the path exists);
   - a backticked Python name (`module.function`, `Class.method`, `function()`) that no longer
     exists in the code;
   - a command-line option (`--axis-deadzone`, `--input-mode`) that no command's `--help` lists,
     or a documented default that differs from the parser's;
   - a `BUGS.md #N` reference whose wording ("open", "active", "until #N is fixed") contradicts the
     entry's status.

   The report is the worklist. Checks that prove cheap and stable (names, options) become tests
   beside the path guard, so drift is caught when it happens, not at the next scrub.
2. **Reading.** Each document is read against the code it describes, for what no script can
   check: behavior described wrongly, steps that no longer apply, sections that duplicate a page
   in `docs/`. American spellings throughout.

**Root files: keep, fold or retire.** Each root Markdown file is decided once: still current and
needed at the root (`README.md`, `CLAUDE.md`), folded into the matching `docs/` page (the
architecture and controls READMEs), or retired because `docs/` already says it better. Retiring
a file is listed in the PR for the owner's review rather than done silently.

**Review shape.** One commit per area (root, docs/architecture, docs/playback, docs/games,
docs/quality, member READMEs, engine docstrings), so each is reviewable alone; reading-pass areas
can run in parallel (one reviewer each), the mechanical report first so every reviewer starts
from the same worklist.

**Done when:** the claims report is empty (or every remaining line is a recorded exception),
`mkdocs build --strict` passes, the docs guard tests pass, and the full suite is green.

## Plan

1. Wait for the backlog run's branches to land; rebase onto `main`.
2. `scripts/docs_claims.py` with tests; run it; commit the report's worklist into this plan.
3. Root files: decide keep, fold or retire; fix what stays.
4. `docs/` by area (architecture, playback, games, quality), one commit each.
5. Member READMEs; engine module docstrings.
6. Promote the cheap checks to tests beside the path guard.
7. `mkdocs build --strict`, the docs guard tests, the full suite; push; PR.
