# glitchy.games website on AWS — Design

- **Date:** 2026-10-27
- **Status:** DRAFT, awaiting the owner's review (builder-checked 2026-10-28). Nothing is built
  yet.
- **Later, separate plans:** email at the domains; self-hosting PyScript/Pyodide (both in
  `plans/future-work.md`, Website); a real home page at `glitchy.games`; `docs.glitchy.games`;
  the other 24 domains.
- **Repo:** `glitchygames` (this repo). The site and its AWS setup live here; no separate repo.

## Intent

Put the GlitchyGames Arcade on the public web. A visitor opens `play.glitchy.games` and gets the
arcade (the gallery in the owner's mockup: a featured demo with sound on top, a grid of live
silent demo tiles below, arrows / d-pad to browse, Enter / A to play). Every game runs in the
visitor's own browser (Pyodide/WebAssembly; `plans/2026-10-23-game-host-and-browser-runner.md`,
`scripts/build_browser_bundle.py`), so the server only serves files.

## Goals

1. `https://play.glitchy.games` serves the browser build, over HTTPS.
2. Every push to `main` on GitHub publishes the site automatically.
3. The AWS setup is code in this repo, reproducible from scratch.
4. **The cheapest reasonable setup for a simple static site** (the owner, 2026-10-28): $0 / month
   expected, on CloudFront's Free flat-rate plan.
5. The owner hears about it (email) before an AWS bill surprises them.

## Non-goals (for now)

- No servers: no EC2, Lightsail, containers, databases or GPU instance (the owner, 2026-10-28:
  "We don't even need a GPU instance for this").
- No home page at `glitchy.games` yet — it redirects to `play.glitchy.games`.
- No docs site yet (`docs.glitchy.games` is reserved for the MkDocs site, later).
- The 24 other domains the owner holds at Namecheap (`glitchygames.*`, `twitchplaysglitchy*`)
  stay untouched.
- Not transferring any domain registration away from Namecheap.

## Anti-goals

- Long-lived AWS access keys stored in GitHub.
- A setup that only works because of hand-clicked console changes nobody can reproduce.
- A bill that can grow silently (a traffic spike, a forgotten resource) without an alert.

## Constraints and facts

- **AWS account:** the owner's existing, long-standing account. It is past the old 12-month free
  tier and was created before the July 15, 2025 credit-based free plan, so only the "Always Free"
  allowances apply (CloudFront: 1 TB transfer and 10M requests / month; Lambda; DynamoDB).
  Being off the AWS Free Tier matters: an account on it can't subscribe to flat-rate plans.
- **CloudFront flat-rate Free plan** (AWS docs, checked 2026-10-28): $0 / month, no overage
  charges ever; 1M requests and 100 GB transfer / month; includes the ACM certificate,
  CloudFront Functions, Origin Access Control, managed and custom response-header policies, the
  attached Route 53 hosted zone (its monthly fee, records, queries; 50 records per zone) and
  5 GB of S3 Standard storage credit. **One distribution per plan, one apex domain per plan,
  3 Free plans per account** (quotas can't be raised). Over the allowance, AWS notifies and may
  serve from fewer or more distant edges, but never bills. Origin Access Identity (OAI) is not
  supported (use OAC). A CloudFront Function already associated with another distribution
  can't be used by a plan's distribution, so each distribution gets its own function.
- **Domains:** registered at Namecheap (namecheap.com). Two are in scope:
  `glitchy.games` and `glitchygames.ai`.
- **Region:** us-east-1 (CloudFront certificates must live there).
- **Browser build:** `scripts/build_browser_bundle.py` (on `main`) writes
  `build/browser/<game>`: the page, the engine and our pygame-ce WebAssembly wheel. The wheel is
  built from the `third_party/pygame-ce` submodule and takes several minutes the first time.
- **The games already build as a site:** `python -m scripts.build_browser_bundle all` writes
  `build/browser/site` (a directory per game plus an `index.html` linking them). `nox -s
  docs-deploy` runs it and publishes it with the docs as `play/` on GitHub Pages
  (https://terrysimons.github.io/glitchygames/play/; `scripts/mkdocs_hooks.py`).
- **PyScript comes from a CDN:** `browser/index.html` loads `core.js` / `core.css` from
  `pyscript.net`.
- **The Arcade app** (`plans/2026-10-23-arcade-showcase.md`, feature #43) is a spec, not built.
  `src/apps/` holds only Bitmappy today.
- **CI is CircleCI** (`.circleci/config.yml`); there is no `.github/`. Its `deploy-docs` job
  runs after `build-and-test-macos` passes on `main` (macOS `m4pro.medium`, one at a time via
  `serial-group`), already caches the Pyodide toolchain (~2 GB) and the pygame-ce WebAssembly
  wheel keyed on the submodule commit, and runs `nox -s docs-deploy -- --no-measure`.
- **House style:** uv, nox sessions, Python 3.14, explicit long names.

## Decided by the owner

| Decision | Choice |
|---|---|
| Hosting provider | Amazon (AWS) |
| Where the code lives | this `glitchygames` repo |
| Main address | `play.glitchy.games` serves the Arcade |
| `glitchy.games` (bare) | redirects to `play.glitchy.games` for now; a home page may replace it later |
| `glitchygames.ai` | in scope (redirects; see below) |
| Other 24 domains | not now |
| Publishing | automatically on every push to `main` on GitHub (through the existing CircleCI pipeline) |
| Spec location | `docs/specs/` |
| The site | `src/website/`: its `index.html` and the owner's mockup image, until the real site is coded (2026-10-28) |
| GPU | not needed; dropped (2026-10-28) |
| Cost | cheapest reasonable for a simple static site (2026-10-28) |
| Self-hosting PyScript/Pyodide | later; a backlog task needing a brainstorm (2026-10-28) |

## Address map

| Address | Behaviour |
|---|---|
| `play.glitchy.games` | the site (S3 via CloudFront) |
| `glitchy.games`, `www.glitchy.games` | 301 to `https://play.glitchy.games` (path kept) |
| `glitchygames.ai`, `www.glitchygames.ai` | 301 to `https://play.glitchy.games` (path kept) |
| `http://` anything | upgraded to `https://` |
| `docs.glitchy.games` | reserved, later |

Redirect choices (301, path kept, `www` folded) are Claude's call. Keeping one canonical address
matters beyond SEO: browser storage (the Arcade's saves, `browser/browser_storage.py`) is
per-origin, so serving the site on two origins would split players' saves.

## Architecture (Claude's call unless noted)

```
                 Namecheap (registrar only)
                   | nameservers -> Route 53
                   v
 Route 53 zone: glitchy.games          Route 53 zone: glitchygames.ai
 (attached to Free plan 1)             (attached to Free plan 2)
   play, @, www -> ALIAS distribution 1  @, www -> ALIAS distribution 2
                   |                                   |
                   v                                   v
 Distribution 1: glitchy.games         Distribution 2: glitchygames.ai
 (CloudFront Free plan 1)              (CloudFront Free plan 2)
   - origin: private S3 bucket (OAC)     - no real origin; its own CloudFront
   - cert: glitchy.games,                  Function answers every request with a
     www., play. (ACM)                     301 to https://play.glitchy.games<path>
   - CloudFront Function: Host not       - cert: glitchygames.ai, www. (ACM)
     play.glitchy.games -> 301 to
     https://play.glitchy.games<path>
   - compression on
   - response headers policy
                   |
                   v
 S3 bucket (private, versioned) holding the site
```

Why this shape: a Free plan covers one distribution and one apex domain, so the
`glitchy.games` names (one apex) share distribution 1, and `glitchygames.ai` (a second apex)
needs distribution 2. That uses 2 of the account's 3 Free plans; the third is spare (e.g. a
future apex domain). Both zones are attached to their distribution's plan, so Route 53 costs
nothing either.

- **DNS:** move the nameservers of both domains to Route 53 at Namecheap (one manual step per
  domain, done once). Route 53 then holds every record as code; attached to the Free plans, the
  zones cost $0 (50-record limit per zone: plenty).
- **Certificates:** ACM in us-east-1, DNS-validated in Route 53 (automatic once the zones exist).
  One per distribution (3 names and 2 names). Free.
- **Plan subscription:** CloudFormation/CDK support for subscribing a distribution to a
  flat-rate plan and attaching a zone was not confirmed (aws-cdk issue #37857 asks for it). If
  CDK can't, subscribing both distributions and attaching both zones is a one-time console step
  (Manual steps). The distributions must not use anything the plan doesn't support (OAI,
  real-time logs; the builder checks the AWS "Unsupported features" list).
- **WAF web ACL (found in the final review, 2026-10-28):** a plan requires a WAF web ACL on its
  distribution, used by no other distribution and not removable while the plan lasts. Each
  stack defines its own (`glitchy_site.hosting.web_acl_for`: allow by default, one rule, AWS's
  IP reputation list; the Free plan allows 5), so the plan adopts it and a later deploy never
  detaches it. Covered by the plan; on pay-as-you-go it would cost $5 / month per ACL plus $1
  per rule.
- **S3:** private bucket, CloudFront Origin Access Control, Block Public Access on. Versioning on
  so a bad deploy can be rolled back; a lifecycle rule expires old versions after 30 days.
- **CloudFront (site):**
  - Serve `.wasm` as `application/wasm` (set at upload) and enable compression (gzip/brotli) for
    the large Pyodide / wheel / Python files.
  - Cache: `index.html` short (e.g. 60 s) so deploys show quickly; other assets long.
  - Response headers: HSTS and standard security headers. **No COOP/COEP** (cross-origin
    isolation): the build loads PyScript from `pyscript.net`, which COEP would block, and the
    runner uses JS Promise Integration rather than threads, so it doesn't need
    SharedArrayBuffer. If that ever changes, the bundle must self-host PyScript first. No strict
    Content-Security-Policy for the same reason (or one that allows `pyscript.net` and
    Pyodide's CDN — builder's call).
  - Self-hosting PyScript and Pyodide (which would allow COOP/COEP and a strict CSP) is a later
    task: `plans/future-work.md`, Website.
- **Budget alarm:** AWS Budgets, monthly, whole account (the owner, 2026-10-28: nothing else
  runs in it), emailing the owner at $10 actual and at forecast > $10. The address (the owner
  gave it 2026-10-28) is passed at deploy time (CDK context or an environment variable), never
  written in the repo: this spec and the infra code are public.

## Infrastructure as code (Claude's call)

- **AWS CDK in Python**, in `infra/` as its own small uv project (own `pyproject.toml`), so the
  engine's dependencies don't change.
- nox sessions in the existing style: `nox -s infra-deploy`, `nox -s infra-diff`,
  `nox -s site-publish` (build + sync + invalidate, also usable locally).
- Stacks: `GlitchyGamesSite` (zone, certificate, bucket, distribution 1), `GlitchyGamesAiRedirect`
  (zone, certificate, distribution 2), `CircleCiDeployRole`, `Budget`. Names are
  the builder's to settle.
- First deploy (`cdk bootstrap` + deploy) runs from the owner's Mac with admin credentials.

## Publishing (owner: on every push to `main`)

The repo's CI is CircleCI, which already builds the browser games on every merge to `main`, so
publishing to AWS joins that pipeline (Claude's call: no GitHub Actions, one CI system).

- A new `nox -s site-publish` session: syncs a built site directory to the bucket
  (`aws s3 sync --delete`, `.wasm` as `application/wasm`, short cache on `index.html` files,
  long on the rest) and invalidates the CloudFront distribution. Also runnable from the
  owner's Mac.
- CircleCI, at launch (mockup only, so nothing needs the browser build): a new lightweight
  `deploy-site` job (Linux Docker image, no Pyodide toolchain or wheel cache) that runs
  `nox -s site-publish` on `src/website/`. It runs on main after the docs publish (the owner,
  2026-10-28: "it should run on main after docs publish"): `requires: deploy-docs, test-infra`,
  `filters: branches: only: main`, its own `serial-group`. A failed docs deploy therefore skips
  the site's publish until the next green merge; a failed site publish can't touch the docs,
  which have already pushed.
- When the real site (the Arcade) replaces the mockup: the publish needs the browser build, so it moves to
  a final step of `deploy-docs` (which already holds the build and its caches), or receives the
  build through a CircleCI workspace. Decide then.
- **Credentials: CircleCI OIDC** (no stored AWS keys). The AWS role trusts CircleCI's OIDC
  provider for this organization and project only, and may only write to the site bucket and
  create invalidations on the site distribution. The organization ID and project ID are values
  the owner reads from CircleCI's settings.
- `serial-group` already keeps two merges from deploying at once.
- Infra changes (`infra/**`): Claude's call is to keep these manual (`nox -s infra-deploy`) at
  first. Automating them is a later option.
- GitHub Pages `play/` keeps publishing as today; once `play.glitchy.games` is live, the docs'
  "Play in the Browser" link (`mkdocs.yml`) points to it. Whether to stop publishing `play/` on
  GitHub Pages is a later cleanup.

## What gets published at launch

The site is `src/website/` (the owner, 2026-10-28: "src contains all source code pertaining to
glitchygames, the engine, the games, the tools, the website"): for now just its `index.html`
and the owner's mockup image (the gallery screenshot). The real site is coded later, in the same
place. `src/website/` is in `[tool.glitchygames] unmeasured-paths`, since `measured-paths` holds
all of `src/` and a site edit runs no game.

**Owner (2026-10-28): mockup only.** The page does not link to the already-built games
(`build/browser/site`); they stay on GitHub Pages `play/` until the real site replaces the
mockup.

## Costs

### Monthly, us-east-1

| Item | Cost |
|---|---|
| CloudFront, 2 distributions on Free plans (incl. certificates, Functions, response headers) | $0 |
| Route 53, 2 zones attached to the plans (fees, records, queries) | $0 |
| S3 storage (well under the 5 GB credit) | $0 |
| S3 requests (a few hundred PUT/LIST per deploy, at $0.005 / 1,000) | ~$0.01 |
| CloudFront invalidations (first 1,000 paths / month free) | $0 |
| AWS Budgets (first 2 budgets free) | $0 |
| **Total** | **~$0** |

Plus existing Namecheap renewals (unchanged). The Free plan's 100 GB / month is far more than a
mockup page needs. When the Arcade ships, Pyodide-based pages are ~10–30 MB per first visit, so
100 GB is roughly 3–10k first-time visitors / month; beyond that nothing is billed, but delivery
may slow. Upgrading that distribution to Pro ($15 / month: 10M requests, 50 TB) is the
step up when it matters.

Fallback if the Free plans can't be used (e.g. a plan restriction found while building):
pay-as-you-go CloudFront (Always Free 1 TB / 10M requests) costs the same $0 for traffic, plus
$0.50 / month per Route 53 zone: about $1 / month, once the two web ACLs are removed from the
stacks (they exist only for the plans; kept on pay-as-you-go they would add about $12 / month).

## Manual steps for the owner

1. Run the first `nox -s infra-deploy` with admin AWS credentials.
2. At Namecheap, set custom nameservers for `glitchy.games` and `glitchygames.ai` to the four
   Route 53 nameservers each zone reports.
3. Subscribe both distributions to the CloudFront Free plan and attach each Route 53 zone to its
   plan (CloudFront console, Manage Plan), unless CDK can do it.
4. Confirm the AWS Budgets email subscription.

## Today's DNS (checked 2026-10-27 with `dig`)

Both domains are identical: Namecheap BasicDNS (`dns1/dns2.registrar-servers.com`), a Namecheap
parking page on `@` and `www`, **Namecheap email forwarding** (MX `eforward1-5.registrar-servers.com`
and TXT `v=spf1 include:spf.efwd.registrar-servers.com ~all`), no `play` record, and **no DS
record (DNSSEC off)**, so a nameserver move needs no DNSSEC step. Nothing but the parking page
is served, so propagation time costs nothing.

## Risks

- **DNS cutover and email forwarding:** see "Today's DNS". The owner does not use email at
  either domain (2026-10-28), so the Route 53 zones do **not** copy the Namecheap forwarding MX
  or SPF records; mail to these domains stops being accepted after the move. Email is a later,
  separate plan (likely Amazon SES or another provider; it will add MX, SPF, DKIM and DMARC
  records to the Route 53 zones).
- **.games / .ai nameserver changes** can take up to 48 h to propagate; certificate validation
  waits on it.
- **CI build time:** already handled; `deploy-docs` caches the toolchain and wheel.
- **Third-party CDN:** the site depends on `pyscript.net` (and Pyodide's CDN) being up. Self-
  hosting them is a later option.

## Left to the builder

- Exact stack/construct names, bucket names, cache TTLs, CloudFront Function code.
- Whether redirects share the site distribution or have their own.
- Placeholder page markup.
- Step in `deploy-docs` versus separate CircleCI job.

## Calls Claude made after the builder check

- **Mockup image:** the owner supplied it in conversation. It is
  `src/website/arcade-mockup.png` beside a minimal `index.html` (first built in
  `web/placeholder/`; the owner moved the site to `src/website/` on 2026-10-28). The owner offered
  it as the site's content for now, so publishing it is intended.
- **A failed AWS publish turns the CircleCI build red** (so the owner hears about it). It is its
  own job, run after the docs deploy (owner, 2026-10-28), so it can't undo the docs.
- **CDK bootstrap:** the builder checks for an existing `CDKToolkit` stack, Route 53 zones, ACM
  certificates and a CircleCI OIDC provider in the account before creating any (read-only
  `aws` calls), and reuses what's there.

## Sources

- AWS free tier changes: https://tech-insider.org/what-changed-in-the-aws-free-tier-for-2026/ ,
  https://spot.rackspace.com/blog/aws-free-tier
- CloudFront flat-rate plans (allowances, quotas, unsupported features):
  https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/flat-rate-pricing-plan.html
- CDK support for flat-rate plans (open request): https://github.com/aws/aws-cdk/issues/37857
- Lightsail and EC2 (considered, not chosen: a static site needs no server): https://cloudburn.io/blog/amazon-lightsail-pricing
