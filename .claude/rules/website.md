---
paths:
  - "infra/**"
  - "src/website/**"
  - "docs/specs/2026-10-27-glitchy-games-website-design.md"
  - "plans/2026-10-28-glitchy-games-website-implementation.md"
---

# Website (`infra/`: https://play.glitchy.games)

Claude Code loads this rule when it reads or edits a file under `infra/` or `src/website/`, or the
website's design or plan (the `paths` above), so `CLAUDE.md` stays within its size limit
(`tests/test_claude_md.py`).

How to sign in, bring it up from nothing, deploy, publish, check it and troubleshoot:
`infra/README.md`. Design `docs/specs/2026-10-27-glitchy-games-website-design.md`, plan
`plans/2026-10-28-glitchy-games-website-implementation.md` (Task 8 records the first go-live).
Credentials: `aws login --profile <profile>`; pass `--profile <profile>` after `--` to
`infra-diff`/`infra-deploy` (keys exported in the shell beat `AWS_PROFILE`, and stale ones stop
the app with `KeyError: 'CDK_DEFAULT_ACCOUNT'`). `infra/` is its own uv project with
its own `uv.lock` (its own workspace root, not a member: the engine's lock never holds the CDK):
the CDK app (`glitchy_site.app`: stacks `GlitchyGamesDnsZones`, `GlitchyGamesSite`,
`GlitchyGamesAiRedirect`, `GlitchyGamesSiteDeployRole`, `GlitchyGamesBudget`, all us-east-1), the
viewer-request CloudFront Function both distributions run
(`glitchy_site/functions/redirect_to_play.js`: every host but play.glitchy.games gets a 301
there, path and query kept; directory URLs fetch their `index.html`) and the publisher
(`glitchy_site.publish`). Each distribution has its own Function and WAF web ACL
(`glitchy_site.hosting`): CloudFront's Free flat-rate plan requires both to be unshared, and
the web ACL can't be detached while the plan lasts. The deploy role trusts only CircleCI jobs
of this project on `main` (the OIDC token's `vcs-ref`). The site itself is `src/website/`
(for now its `index.html` and the Arcade mockup; listed in `unmeasured-paths`, so editing it
measures no replay).

```bash
nox -s infra-test          # pytest infra/tests (CDK templates built with infra/cdk.json's feature flags) + node --test 'infra/tests/functions/**/*.test.mjs'
nox -s infra-diff -- --profile P     # cdk diff (needs AWS credentials and GLITCHY_SITE_BUDGET_EMAIL, never written in the repo)
nox -s infra-deploy -- --profile P   # cdk deploy --all (or `-- GlitchyGamesDnsZones --profile P` first); the owner's Mac only
nox -s site-publish        # Upload src/website (or `-- --source DIR`) and invalidate; `-- --dry-run` changes nothing
                           # Refused off origin/main or with uncommitted source; `-- --allow-unmerged` previews a branch
# CircleCI: test-infra on every branch (cimg/python -node image); deploy-site after a merge to main
# (requires test-infra only: it publishes beside deploy-docs, each under its own lock), signing in with the job's OIDC token
# (the role's ARN is the CircleCI project environment variable SITE_DEPLOY_ROLE_ARN, kept out of the
# public config because it names the AWS account; no AWS keys are stored)
```
