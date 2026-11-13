# Moving the docs site to Zensical

The owner, 2026-11-13: plan the move, but don't make it yet. This is the plan for
`plans/future-work.md`'s "Move the docs site to Zensical". Material for MkDocs reaches end of life
on 2027-05-05. Zensical is its successor from the same team, and it reads our `zensical.yml`
(`mkdocs.yml` links to it) and our markdown unchanged.

Sources: Zensical's migration guide (https://zensical.org/docs/compatibility/mkdocs/migration/) and
its plugin compatibility page (https://zensical.org/docs/compatibility/mkdocs/plugins/), both read
2026-11-13.

## Where it stands

A trial build on 2026-11-13, `uv run --with zensical zensical build --config-file zensical.yml` on
main (`d3295b56`) plus the sidebar-navigation change, finished with one warning in 393 s (the mkdocs
`lint-docs` build: 296 s, the complexity graphs already current). Built as before: the theme,
palette, sidebar navigation, search, every markdown extension, and the engine's hand-written API
pages through mkdocstrings (676 objects on the engine page). Missing: everything the hook and
gen-files make, and every page's last-updated date.

| What we use | Zensical (2026-11-13) | What the move needs |
|---|---|---|
| `hooks: scripts/mkdocs_hooks.py` | Not supported: no MkDocs plugin API, and arbitrary plugins never run | Its jobs move into the nox sessions (Step 1) |
| `gen-files` (`scripts/gen_ref_pages.py`) | Not supported (config ignored without a word) | Run the script before the build, writing real files (Step 1) |
| `git-revision-date-localized` | Planned | Wait: no page has a date until it lands |
| `mkdocstrings` (python) | Supported; sources outside the project are not watched in preview, `watch` ignored | Nothing |
| `autorefs` | Supported | Nothing |
| `macros` | Supported, with differences (only `define_env` is called) | Drop it: no page uses it (Step 1) |
| `search`, `section-index` | Built in (entries ignored) | Drop the entries at the switch |
| `mkdocs gh-deploy` | Not provided | Our own push of `site/` to gh-pages (Step 2) |
| `--strict` | No strict mode; the build reports "N issues found" and succeeds | Fail the session on any reported issue, until Zensical has one (Step 2) |
| Material's look | The `classic` variant keeps it | `theme.variant: classic` at the switch, unless the owner picks `modern` |

The trial's one warning was the missing member API pages (`games/mr_muncher.md` links
`../mr_muncher/index.md`, a gen-files page).

## Step 1: the site built the same by either builder (mkdocs stays)

Done on mkdocs, deployed as today. Afterwards `mkdocs build` and `zensical build` make the same
site except for the page dates, so the switch (Step 2) is only commands.

1. **The graphs before a build.** The hook's `on_pre_build` (the complexity graphs when stale,
   then the performance graphs) becomes a nox step run before every `mkdocs build`, `serve` and
   `gh-deploy` (`lint-docs`, `docs-serve`, `docs-deploy`). The performance graphs' published/local
   choice comes from the hook's `on_startup` command today (`BUILD_STATE.command`,
   `LOCAL_BUILD_COMMANDS`); the step takes it as an argument instead (`docs-deploy` without
   `--build-only` is the published build). A `serve` no longer regenerates them on a rebuild: they
   change only with a commit or new rows, and restarting `docs-serve` makes them again.
2. **The member API pages.** `scripts/gen_ref_pages.py` writes through `mkdocs_gen_files`; it
   writes real files instead, before the build, into the docs directory (gitignored). The
   `gen-files` plugin and its dependency go. `tests/test_gen_ref_pages.py` follows. The other
   choice is Zensical's `api-autonav` or `autoapi` plugin, which would change the pages' layout;
   decide when doing it.
3. **After a build.** The hook's `on_post_build` jobs become nox steps after the build:
   `copy_browser_games` (`play/`) and `missing_explorer_files` (the explorers' check). Under
   `serve` the check does not run on each rebuild; `lint-docs` and `docs-deploy` still run it.
   `tests/test_mkdocs_hooks_browser_games.py` and `tests/explorer_site.py` follow the code.
4. **What stays in the hook.** Only the cache clearing (`documentation_caches`, BUGS.md #213),
   which is mkdocs' `serve` leak; the hook goes away with mkdocs in Step 2.
5. **`macros`.** No page uses it (no `{{`/`{%` in `docs/`, no `main.py`): remove the plugin and
   `mkdocs-macros-plugin` from both dependency lists in `pyproject.toml`.
6. **Check.** `nox -s lint-docs`, then a `zensical build` of the same commit: the same pages, and
   the explorers' check passing on its `site/`.

## Step 2: the switch (when Zensical is ready)

Start it when Zensical supports `git-revision-date-localized` (or the owner accepts pages without
dates) and has a strict mode (or the issue-count check below is accepted). Check both pages above
again first: the status will have moved.

1. **Commands.** `zensical build` and `zensical serve` in `lint-docs`, `docs-serve` and
   `docs-deploy` (`noxfile.py`); `zensical` replaces `mkdocs`, `mkdocs-material`,
   `mkdocs-gen-files`, `mkdocs-section-index` and the `mkdocs<2.0` pin in `pyproject.toml`.
   Zensical takes no `--site-dir` or `--theme`; `site_dir` stays in the config.
2. **Strict.** Until Zensical has a strict mode, the sessions fail when the build reports any issue
   (its "N issues found" line, or its exit status if it gains one). Our `validation` settings
   (`omitted_files`, `not_found`, `absolute_links`) are checked again against what Zensical
   validates.
3. **Deploy.** `docs-deploy` builds, then pushes `site/` to gh-pages itself (`ghp-import`, or a
   commit in a gh-pages worktree), keeping today's order: fetch gh-pages, measure, build, push,
   then `glitchygames clear-published`. CircleCI's `deploy-docs` job runs the same session, so only
   its comment changes; `tests/test_ci_config.py` follows.
4. **Config.** `theme.variant` (`classic`), the `search` and `section-index` entries removed, the
   hook removed (and its cache clearing with it), `mkdocs.yml` the link removed:
   `tests/test_workspace_config.py`'s `test_mkdocs_yml_is_a_link_to_zensical_yml` becomes a check
   that no `mkdocs.yml` comes back. Moving to `zensical.toml` is not needed (Zensical reads the
   YAML) and is a later choice.
5. **Docs.** `CLAUDE.md` (Nox Sessions' docs entries, Important Notes' documentation note), the
   docstrings of the three sessions and `docs/` pages naming mkdocs.
6. **Check.** Compare representative pages with the last mkdocs build: an engine API page, a
   member API page, an explorer page, the requirements page's tabs, a Mermaid diagram, search, and
   `play/`. Then a `docs-deploy -- --build-only`.

## Not part of this

The sidebar navigation (tabs removed, 2026-11-13) and the Material formatting
(`plans/2026-11-09-docs-material-formatting.md`) carry over unchanged: both builders read the same
`theme.features`.
