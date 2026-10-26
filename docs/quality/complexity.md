# Code Complexity Metrics

How the most complex modules in `glitchygames/` changed over the project's git history, measured
by [wily](https://github.com/tonybaloney/wily). The modules are the 15 with the highest total
cyclomatic complexity (the sum over their functions and methods) at the published commit. Each
graph has one line per module (click a module in the legend to hide or show it), with a point at
each commit that changed the module's value. wily follows files by path; the engine moved from
`glitchygames/` to `src/glitchygames/` (2026-10-25), so each module's measurements under its former
path are joined to its current one (`MOVED_PATH_PREFIXES` in
`scripts/generate_complexity_graphs.py`), and its line runs through its whole history.

The graphs are generated, not kept in git: `nox -s docs-deploy` generates them before it builds
the published site. To see them in a local build (`mkdocs serve`), generate them first with
`uv run python scripts/generate_complexity_graphs.py` (or `nox -s code-complexity -- --graphs`),
which measures the committed history (HEAD) in a temporary worktree and writes them to
`docs/quality/graphs/`; until then this page has only this text.

--8<-- "docs/quality/graphs/complexity_graphs.md"
