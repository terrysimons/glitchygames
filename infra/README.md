# The website's infrastructure (`infra/`)

`play.glitchy.games` is served from a private S3 bucket behind CloudFront, on CloudFront's Free
flat-rate plan. `glitchy.games`, `www.glitchy.games`, `glitchygames.ai` and
`www.glitchygames.ai` answer `301` to it. This directory is the AWS CDK app (Python) that builds
all of it, and the publisher that uploads the site. The why is in the design,
`docs/specs/2026-10-27-glitchy-games-website-design.md`; the record of building and first
deploying it is in the plan, `plans/2026-10-28-glitchy-games-website-implementation.md` (Task 8).

`infra/` is its own uv project with its own `uv.lock`, not a workspace member, so the engine's
lock never holds the CDK. Run everything from the repository root through the nox sessions below.

## What it deploys

Five stacks, all in us-east-1 (`glitchy_site.app`):

| Stack | What it holds | Outputs |
|---|---|---|
| `GlitchyGamesDnsZones` | The Route 53 hosted zones for `glitchy.games` and `glitchygames.ai` | Each zone's four name servers |
| `GlitchyGamesSite` | The versioned private bucket, Origin Access Control, certificate, distribution 1 (`play.` and the `glitchy.games` names), its alias records | `SiteBucketName`, `SiteDistributionId` |
| `GlitchyGamesAiRedirect` | Distribution 2, for `glitchygames.ai` (a Free plan covers one apex domain), with its certificate and records | |
| `GlitchyGamesSiteDeployRole` | CircleCI as an OIDC provider, and a least-privilege role only this project's jobs on `main` can assume | `DeployRoleArn` |
| `GlitchyGamesBudget` | A $10 / month budget, emailing at actual and forecast spend | |

Each distribution runs the redirect CloudFront Function
(`infra/src/glitchy_site/functions/redirect_to_play.js`: every host but `play.glitchy.games` gets
a `301` with the path and query kept; directory URLs fetch their `index.html`) and has its own web
ACL, because a Free plan needs both unshared. The site itself is `src/website/`.

The domains stay registered at Namecheap; only their name servers point at Route 53.

## The nox sessions

```bash
nox -s infra-test                                   # pytest infra/tests + node --test 'infra/tests/functions/**/*.test.mjs' (no AWS)
GLITCHY_SITE_BUDGET_EMAIL=... nox -s infra-diff -- --profile <profile>                 # What a deploy would change
GLITCHY_SITE_BUDGET_EMAIL=... nox -s infra-diff -- GlitchyGamesSite --profile <profile>
GLITCHY_SITE_BUDGET_EMAIL=... nox -s infra-deploy -- GlitchyGamesDnsZones --profile <profile>
GLITCHY_SITE_BUDGET_EMAIL=... nox -s infra-deploy -- --profile <profile>                # Every stack
nox -s site-publish                                 # Upload src/website, delete stale files, invalidate /*
nox -s site-publish -- --dry-run                    # Print the plan, change nothing
nox -s site-publish -- --source build/browser/site  # Publish another directory
```

- `infra-diff` and `infra-deploy` run the CDK CLI at the version the noxfile pins
  (`_AWS_CDK_CLI_VERSION`, through `npx`), and pass anything after `--` to it: stack names,
  `--profile`. `infra-deploy` stops for approval when a change widens IAM permissions.
- `GLITCHY_SITE_BUDGET_EMAIL` is the budget alert's address. It is never written in the
  repository: set it in the command each time. Only the budget stack uses it, but the app needs
  it set to synthesize at all.
- `site-publish` uses boto3, which takes `AWS_PROFILE`, not a `--profile` option. It reads the
  bucket and distribution from the site stack's outputs, and refuses a missing, empty or
  index-less source before calling AWS, so a wrong path can't empty the site.

## Credentials

Sign in with the AWS CLI (2.32 or later), in the browser, to a named profile:

```bash
aws login --region us-east-1 --profile <profile>
aws sts get-caller-identity --profile <profile>      # Check: the account and who you are
```

The credentials last 12 hours and renew without signing in again for 90 days; run `aws login`
again when they lapse. The CDK CLI reads an `aws login` session itself.

- **Pass `--profile` to the CDK, rather than setting `AWS_PROFILE`, if your shell exports
  `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`.** Keys in the environment take precedence over
  `AWS_PROFILE`; if they are stale, the CDK's account lookup fails and the app stops with
  `KeyError: 'CDK_DEFAULT_ACCOUNT'`. For `site-publish` (no `--profile`), unset them:
  `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY AWS_PROFILE=<profile> nox -s site-publish`.
- **Use an administrator identity that is not the root user** (an IAM Identity Center user, or
  an IAM user in an administrators group). Root works, but it cannot assume the CDK bootstrap's
  roles, so the CDK warns "current credentials could not be used to assume ..." and deploys with
  root's own credentials, and nothing can restrict what root does.
- No AWS keys are stored anywhere for CI: CircleCI's `deploy-site` job signs in with its OIDC
  token and assumes the deploy role.

## Bringing it up from nothing

The first deploy, in order (the plan's Task 8 has the detail and what each step found). Steps
that need a person: the sign-in, the Namecheap change, the CloudFront console and CircleCI's
settings.

1. **Credentials and reuse.** Sign in (above). Look for things to reuse: a `CDKToolkit` stack in
   us-east-1, hosted zones for the two domains, an IAM OIDC provider for
   `oidc.circleci.com/org/<organization id>`. IAM allows one provider per URL: if one exists, put
   its ARN in `infra/cdk.json` as `circleci_oidc_provider_arn` and the stack reuses it.
2. **CircleCI IDs.** Put the organization ID (Organization Settings) and project ID (Project
   Settings) in `infra/cdk.json` (`circleci_organization_id`, `circleci_project_id`). The deploy
   role trusts only that project.
3. **Bootstrap.** Once per account and Region, from a directory without a `cdk.json` (so the app
   isn't synthesized), with the CLI version the noxfile pins:
   `npx --yes aws-cdk@<version> bootstrap aws://<account>/us-east-1 --profile <profile>`.
4. **The zones.** `nox -s infra-deploy -- GlitchyGamesDnsZones --profile <profile>` (with
   `GLITCHY_SITE_BUDGET_EMAIL` set). Its outputs are each zone's four name servers; check a zone
   answers with `dig +short NS glitchy.games @<one of its servers>`.
5. **Namecheap.** Before switching, read each domain's records under Advanced DNS: the zones
   hold only the website's records, so anything still needed (mail, verifications) must be added
   to them first. Then Domain List → Manage → Nameservers → Custom DNS → the four servers, for
   each domain. Check: `dig +short NS glitchy.games` and `dig +short NS glitchygames.ai` show the
   `awsdns` servers (up to 48 hours for `.games` and `.ai`).
6. **Everything else.** `nox -s infra-diff -- --profile <profile>`, then
   `nox -s infra-deploy -- --profile <profile>` with the real budget address. The certificates
   validate through the zones, so this waits on step 5. Check: five stacks `CREATE_COMPLETE`.
7. **Free plans.** CloudFront console → each distribution → Pricing plan → Free; Manage Plan →
   attach the `glitchy.games` zone to distribution 1 and the `glitchygames.ai` zone to
   distribution 2, keeping each distribution's own web ACL. Then `infra-diff` should show no
   distribution changes.
8. **Budget email.** Confirm the subscription email AWS Budgets sends.
9. **CircleCI.** Project Settings → Environment Variables: `SITE_DEPLOY_ROLE_ARN` = the deploy
   role stack's `DeployRoleArn` output. It names the AWS account, so it never goes in
   `.circleci/config.yml`.
10. **Check it from outside** (below).

## Publishing

A merge to `main` publishes: CircleCI's `deploy-site` job runs `nox -s site-publish` once
`test-website-aws-infrastructure` passes, at the same time as the docs deploy (`deploy-docs`,
which waits for no job). The job first moves to main's latest commit, so an older pipeline's
deploy can't put an older site back. `test-website-aws-infrastructure` runs `nox -s infra-test`
on every branch. To publish by hand, run `site-publish` with your profile (above). It refuses unless HEAD is on `origin/main` and the
source has no uncommitted changes; `-- --allow-unmerged` publishes a branch's preview on
purpose, and `-- --dry-run` changes nothing.

## Checking it's live

```bash
curl -sI https://play.glitchy.games/          # 200, text/html, strict-transport-security present
curl -sI 'https://glitchy.games/x?y=1'        # 301, location: https://play.glitchy.games/x?y=1
curl -sI https://www.glitchy.games/           # 301 to https://play.glitchy.games/
curl -sI 'https://glitchygames.ai/x?y=1'      # 301, the path and query kept
curl -sI http://play.glitchy.games/           # 301 to https://
```

## Troubleshooting

| What you see | Why, and what to do |
|---|---|
| `KeyError: 'CDK_DEFAULT_ACCOUNT'` from `glitchy_site.app` | The CDK found no working credentials, usually stale keys exported in the shell beating `AWS_PROFILE`. Pass `--profile`, or unset the key variables; check with `aws sts get-caller-identity --profile <profile>`. |
| `current credentials could not be used to assume 'arn:aws:iam::...:role/cdk-...'` | The identity can't assume the bootstrap's roles (always the case for root). The CDK carries on with the identity's own credentials. |
| `Set GLITCHY_SITE_BUDGET_EMAIL ...` | Set it in the command; the app needs it to synthesize. |
| A certificate stays "pending validation" | The name servers haven't switched yet (step 5). |
| `deploy-site` fails: `SITE_DEPLOY_ROLE_ARN is not set` | Step 9 isn't done. |
| `This software has not been tested with node v...` | jsii (under the CDK's Python library) warns about Node versions newer than it tests. It works; Node 22 or 24 silences it. |
| Expired or missing credentials mid-deploy | `aws login --region us-east-1 --profile <profile>` again. |
