# Measured Replay Rows in the Repository — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every commit that can change how the golden replays run carries its own measurements,
made by a pre-commit hook, and the CI docs deploy publishes exactly the measurements whose code
landed on `main`.

**Architecture:** A pre-commit hook (the pre-commit framework's, so unstaged edits are stashed
while it runs) measures the staged code when the staged diff touches it, and stages one JSON
file per measured recording under `quality/replay-ledger/`. Each row names the **code tree** it
measured: the staged index's tree hash with `quality/replay-ledger/` removed, which survives
amends and squash merges. The docs build reads the rows from the checkout, keeps those whose
code tree is the code tree of a `main` commit (labelled with the first such commit), and merges
them with the history already published; the published history moves into the repository once.

**Tech Stack:** pre-commit (local hook), git plumbing (`write-tree`, `read-tree` with a temporary
index), the existing replay metrics (`scripts/replay_metrics.py`,
`glitchygames/recording_metrics.py` `LedgerRow`), mkdocs hook and performance graphs.

**Spec:** the design agreed 2026-10-24/25 in conversation (recorded in
plans/future-features.md #46's follow-ups by Task 6): rows tracked, one file per measurement,
keyed by code tree, measured in a pre-commit hook, skipped for commits that cannot change the
replays, published only for code that landed on `main`, history moved in from gh-pages.

## Proven before planning (2026-10-25, a throwaway repository)

- A pre-commit framework hook that writes a new file and `git add`s it: the hook passes and the
  file is in the same commit.
- With unstaged edits to another tracked file at commit time: the framework stashes them before
  the hook (so the hook sees exactly the staged code), the hook's file is committed, and the
  unstaged edits are restored untouched.

## Global Constraints

- Branch from `main` after #102 merged (done) and its docs deployed.
- Rows are append-only facts: a row file is never edited after it is committed.
- One file per measured recording per measurement:
  `quality/replay-ledger/<code tree 12>-<machine slug>-<measured_at compact>-<recording slug>.json`
  (no two branches ever write the same path: no merge conflicts).
- The hook measures only when the staged diff touches `glitchygames/`, `games/`, `demos/`,
  `apps/`, `tests/fixtures/replays/`, `uv.lock` or a bundled demo; otherwise it exits at once.
  `SKIP=replay-metrics git commit ...` skips it (the framework's own switch).
- CI never measures (`nox -s docs-deploy -- --no-measure`, unchanged).
- pytest-mock only; keyword arguments; full names; frozen pydantic models; no `# noqa`; lint
  before tests; 100% coverage.

## Review Focus

1. **A row measured on code that differs from what is committed**: the hook must measure the
   staged tree, not the working tree. The framework's stash guarantees it; Task 3 tests the
   hook through the framework in a temporary repository with unstaged edits present.
2. **A squash merge whose tree differs from the branch head** (the branch was behind main): its
   rows match no main commit and are not published. Task 4 tests that, and the hand-off note in
   CLAUDE.md says to measure after updating a branch.
3. **A row file left out of the commit** (the hook failed half way): the hook writes all rows
   before staging any, and a failed measurement fails the commit with the recording named.
4. **Rows from intermediate commits** reaching main in a squash: kept in the repository, never
   published (no main commit has their tree). Task 4 tests it.
5. **The hook's cost on commits that cannot change the replays**: docs, plans, BUGS.md commits
   must not measure. Task 3 tests the path filter.

---

### Task 1: The code tree

**Files:** Create `glitchygames/code_tree.py`; Test `tests/test_code_tree.py`

**Interfaces:**
- Produces: `LEDGER_DIRECTORY = 'quality/replay-ledger'`;
  `def staged_code_tree(*, repository: Path) -> str` (the index's tree with `LEDGER_DIRECTORY`
  removed, via `GIT_INDEX_FILE` pointing at a temporary copy of the index:
  `git rm -r --cached --ignore-unmatch quality/replay-ledger`, then `git write-tree`);
  `def commit_code_tree(*, repository: Path, commit: str) -> str` (the same for a commit:
  `git read-tree <commit>` into a temporary index, then the same removal and `write-tree`).
  Every git call through `glitchygames.process.run_command`.

- [ ] Tests (real git in `tmp_path`): the staged code tree equals the commit's code tree after
  committing; adding or changing a file under `quality/replay-ledger/` changes neither; changing
  any other file changes both; the real index is untouched (`git status` the same before and
  after).
- [ ] Fail, implement, pass, lint, commit.

### Task 2: Rows know their code tree; row files

**Files:** Modify `glitchygames/recording_metrics.py` (`LedgerRow`), `scripts/replay_metrics.py`;
Test `tests/test_recording_metrics.py`, `tests/test_replay_metrics.py`

**Interfaces:**
- Produces: `LedgerRow.code_tree: str | None = None` (read leniently: published rows lack it);
  `def row_file_name(*, row: LedgerRow) -> str`; `def write_row_files(*, rows, directory) -> list[Path]`;
  `def read_row_files(*, directory) -> list[LedgerRow]`;
  `replay_metrics.py measure --code-tree TREE --rows-directory DIR` writes row files (instead of
  appending to the pending ledger) with `code_tree` set and `allowed_uncommitted_changes` true
  (the staged code is uncommitted by definition; `code_tree` names it exactly).

- [ ] Tests: a row round-trips through its file; file names are unique per recording,
  machine and time; reading a directory returns every row, sorted; an old row without
  `code_tree` still reads.
- [ ] Fail, implement, pass, lint, commit.

### Task 3: The pre-commit hook

**Files:** Create `scripts/measure_staged_replays.py`; Modify `.pre-commit-config.yaml`;
Test `tests/test_measure_staged_replays.py`

**Interfaces:**
- Produces: `def touches_replays(*, staged_paths: Sequence[str]) -> bool` (the path filter in
  Global Constraints); `def main() -> int`: staged paths (`git diff --cached --name-only`); if
  none touch the replays, exit 0 at once; else `staged_code_tree`, run
  `replay_metrics.py measure --code-tree ... --rows-directory quality/replay-ledger`, then
  `git add` the new row files; exit non-zero naming the recording if a measurement fails.
- `.pre-commit-config.yaml`: a local hook `replay-metrics`, `stages: [pre-commit]`,
  `pass_filenames: false`, `always_run: true` (the script filters).

- [ ] Tests: the filter (docs/plans/BUGS.md only: no; a `glitchygames/` or fixture or `uv.lock`
  change: yes); in a temporary repository with the pre-commit framework installed and a stand-in
  measure step: a code commit gets its row files in the same commit, a docs commit gets none,
  an unstaged edit elsewhere is restored and not measured.
- [ ] Fail, implement, pass, lint, commit. Then commit a real code change in this repository and
  read the commit: its row files are in it.

### Task 4: Publishing what landed

**Files:** Modify `scripts/generate_performance_graphs.py` (and `scripts/mkdocs_hooks.py` if the
inputs change); Test `tests/test_generate_performance_graphs.py`

**Interfaces:**
- Produces: `def landed_rows(*, rows, main_code_trees: Mapping[str, str]) -> list[LedgerRow]`
  (rows whose `code_tree` is a main commit's code tree, each labelled with the first such
  commit; rows without `code_tree`, the published history, pass through);
  `def main_code_trees(*, repository, first_commit) -> dict[str, str]` (code tree -> first main
  commit, from `git rev-list --reverse origin/main`; cached in the build directory by commit).
  The page's inputs become: the repository's rows (landed only), then the published history
  (until Task 5 moves it in), then local pending rows in a local build.

- [ ] Tests: a row of the branch's final tree is published under the squash commit; a row of an
  intermediate tree is not; a row of a branch that was behind main (tree never on main) is not;
  published history rows still appear.
- [ ] Fail, implement, pass, lint, commit.

### Task 5: The history moves into the repository

- [ ] A one-off script run (kept as `scripts/import_published_ledger.py`, its docstring the
  record): read `quality/metrics/replay-ledger.jsonl` from `origin/gh-pages`, write each row as
  a row file under `quality/replay-ledger/`; commit them. The page then reads only the
  repository (the gh-pages ledger stays as generated output). Test it on a fixture ledger.

### Task 6: Docs and hand-off

- [ ] CLAUDE.md (Recording metrics: rows in the repository, the hook, landed-only publishing,
  measure after updating a branch), docs/quality/performance.md, plans/future-features.md #46
  follow-ups, the master plan of the workspace packages (Part 1's games' recordings feed it).
- [ ] Full suite on both drivers, `nox -s lint static-analysis`, a real commit through the hook,
  PR.
