# Whole-stack documentation scrub

Part of the 2026-11-02 backlog run (the owner's explicit permission to plan, fix, commit, test
and push each item on its own branch). The request: `plans/future-work.md`, "Documentation
scrub". Done last, after the run's other branches land, since they change docs too (#178.26,
#190, #225/#227, #251, #256, sprite tags, solid collision).

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

## Worklist (scripts/docs_claims.py, 2026-11-04: 68 claims in 11 documents)

Triage before the reading pass; each item is decided there, against the code.

- **Retire candidates** (25 of the 68): `TEST_UPDATE_PLAN.md` (16: a finished plan naming test
  files that were merged or renamed; a plan, so it moves out of the root or is retired) and
  `docs/galimore.md` (9: it describes another code base's C++ files and functions; keep as the
  history page it is, and record its claims as exceptions, or move it).
- **`docs/architecture/game_packages.md`** (16): the move's own history, partly still in the
  present tense: `src/glitchygames/examples/`, `tests/examples`, `glitchygames.bitmappy`,
  `src/paddleslap/`. Rewrite as the layout now, the move as one paragraph of history.
- **Paths written relative to a member** in engine pages: `tests/fixtures/replays/` (each
  game's) in `CLAUDE.md`, `gameplay_replay.md`, `game_packages.md`, `performance.md`: write them
  as `src/games/<game>/tests/fixtures/replays/` (a placeholder, so no claim about one file).
- **`docs/architecture/engine_context.md`** (8): the context keys are written as dotted names
  (`glitchygames.audio.engine.audio_engine`); check each is the key's string, then write them as
  strings (quoted) or record them.
- **Stale names and scripts**: `CLAUDE.md` `scripts/replay_metrics.py`,
  `scripts/recording_report.py`, `recording.recorded_frame_fields()`, `_build_info.json` (a build
  artifact: say so); `gameplay_replay.md` `glitchygames.bitmappy.editor`,
  `quality/metrics/replay-ledger.jsonl`; `clockwork_keep.md` `glitchygames.examples.
  clockwork_keep`; `drawing_fire.md` `tests/test_drawing_fire_golden_replay.py`;
  `paddleslap.md` `paddleslap.spawn`, `paddleslap.colors`.
- **Examples, not claims** (record as exceptions): `tests/test_specific.py` (`README.md`,
  `CLAUDE.md`), `tests/x`, `tests/workspace_expectations.MEMBER_PACKAGES` (a module's constant,
  written path-style).
