# Dependabot Alert 196: the Locked tornado 6.6 Has an Open Redirect

- **Description**: GitHub's Dependabot alert 196 (opened 2026-11-14, severity low): «Tornado: Open redirect via triple-slash redirect paths», for tornado `<= 6.6.0`, first fixed in 6.6.1. `uv.lock` holds tornado 6.6, pulled in only by `bokeh`, a runtime dependency of `glitchygames`.
- **Status**: Open (not fixed; a branch of its own)
- **Priority**: Low (no project code imports bokeh or tornado: `bokeh` is in deptry's `DEP002` list in `pyproject.toml`, declared but unused, and no code starts a bokeh or tornado server; the package still ships it to users)
- **Fix to make**: `uv lock --upgrade-package tornado` (to 6.6.1 or later), regenerate the SBOM with `nox -s security-scan` and commit it with `uv.lock`, as CLAUDE.md requires. Separately: why `bokeh` is a runtime dependency nothing imports (`git log -S bokeh -- pyproject.toml`), and whether it should move to an extra or go
- **Reporter**: Claude, from the push of `chore/instrument-audit-checks` (GitHub printed the alert)
- **Date Reported**: 2026-11-14
- **Files**: `uv.lock`, `pyproject.toml`, `docs/sbom.cyclonedx.json`
