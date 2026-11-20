# Code Complexity Metrics

How the modules and packages in `src/glitchygames/` changed over the project's git history,
measured by [wily](https://github.com/tonybaloney/wily). The explorer below draws one metric at a
time (maintainability index, cyclomatic complexity, lines of code, Halstead effort) for modules or
packages. Modules come in rank order: the highest total cyclomatic complexity (the sum over their
functions and methods) at the published commit first, the top 15 to begin with; type part of a
path to narrow them (`scenes/`, `replay`), or show 30 or all. Each line has a point at each commit
that changed its value, and holds as a step until the next one (click a line in the legend to
hide it). wily follows files by path; the engine moved from the repository root into
`src/glitchygames/` (2026-10-25), so each module's and package's measurements under its former
path are joined to its current one (`MOVED_PATH_PREFIXES` in
`scripts/generate_complexity_graphs.py`), and its line runs through its whole history.

The measurements are generated, not kept in git: every docs build generates them when HEAD
changed (`nox -s docs-deploy` before it builds the published site). To generate them by hand, run
`uv run python scripts/generate_complexity_graphs.py` (or `nox -s code-complexity -- --graphs`),
which measures the committed history (HEAD) in a temporary worktree and writes
`docs/quality/graphs/complexity-explorer.json`; until then this page has only this text.

--8<-- "docs/quality/graphs/complexity_graphs.md"
