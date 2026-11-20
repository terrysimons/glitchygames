# Dependabot Alert 196: the Locked tornado 6.6 Has an Open Redirect

- **Description**: GitHub's Dependabot alert 196 (opened 2026-11-14, severity low): «Tornado: Open redirect via triple-slash redirect paths», for tornado `<= 6.6.0`, first fixed in 6.6.1. `uv.lock` holds tornado 6.6, pulled in only by `bokeh`, a runtime dependency of `glitchygames`.
- **Status**: Fixed and closed (2026-11-15, #213, `dc4801d7`): its full upgrade locked tornado 6.6.1, and GitHub marked alert 196 fixed at 2026-11-15T23:26:30Z. This record stayed "Open" until the next upgrade (2026-11-20, branch `chore/dependency-upgrade`) caught it
- **Priority**: Low (no project code imports bokeh or tornado: `bokeh` is in deptry's `DEP002` list in `pyproject.toml`, declared but unused, and no code starts a bokeh or tornado server; the package still ships it to users)
- **Fix**: the full upgrade (`uv sync --upgrade --all-extras --all-groups --all-packages`) took tornado to 6.6.1 (#213); regenerate the SBOM with `nox -s security-scan` and commit it with `uv.lock`, as CLAUDE.md requires. `bokeh` is kept on purpose for future plotting tools (the owner, 2026-10-22, `pyproject.toml`)
- **Reporter**: Claude, from the push of `chore/instrument-audit-checks` (GitHub printed the alert)
- **Date Reported**: 2026-11-14
- **Files**: `uv.lock`, `pyproject.toml`, `docs/sbom.cyclonedx.json`
- **Closed**: `uv.lock` on `main` (b7c2abd3) locks tornado 6.6.1, the first fixed version (checked again 2026-11-20 by the overnight triage and in this branch's `uv.lock`). Nothing is left to do.
