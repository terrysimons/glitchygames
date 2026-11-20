# Pre-Push Checks Fail in a Worktree Synced With Only the dev Extra

- **Description**: In a new worktree synced with `uv sync --locked --extra dev`, the pre-push `static-analysis` and `test-random` hooks fail on missing modules (`ModuleNotFoundError: No module named 'mkdocs'`, `mkdocs_gen_files`, `cookiecutter`), in tests such as `tests/test_gen_ref_pages.py` and `tests/templates/test_template_errors.py`. `uv sync --locked --all-extras --all-packages` fixes it. Seen 2026-11-06 on the `fix/numpy-2` worktree, where the failure came at the end of a 20-minute push (the `feat/default-wayland` worktree was synced the same way)
- **Status**: Fixed (2026-11-19, `9a2127ec`; re-checked and closed 2026-11-20)
- **Priority**: Low (a re-sync fixes it, but only after a long push fails)
- **Reporter**: Claude, pushing from new worktrees
- **Date Reported**: 2026-11-14
- **Details**: Either the hooks should run in an environment that has every extra they need (as `docs-serve` does since #274: `uv run --isolated ... --all-extras`), or a check before the slow hooks should say which sync is missing
- **Files**: `.pre-commit-config.yaml`, `noxfile.py`, `.envrc`
- **Closed**: re-checked on `main` (b7c2abd3, overnight triage 2026-11-20): `test-random` runs `uv run --isolated --frozen --all-extras --all-groups --all-packages --python 3.15` (`noxfile.py` 876-884, since `9a2127ec`), and `static-analysis` installs its own nox environment from the lock file with every extra (`_install_from_lockfile`, `noxfile.py` 95-130, 706-711), so neither depends on how `.venv` was synced. The isolated environment imports `mkdocs`, `mkdocs_gen_files` and `cookiecutter`. Not run: rebuilding a dev-extra-only `.venv` and pushing through every hook. No test pins that the hook environments carry every extra.
