# glitchy.games website on AWS — Design

- **Date:** 2026-10-27
- **Status:** DRAFT, awaiting the owner's review. Nothing is built yet.
- **Repo:** `glitchygames` (this repo). The site and its AWS setup live here; no separate repo.

## Intent

Put the GlitchyGames Arcade on the public web. A visitor opens `play.glitchy.games` and gets the
arcade (the gallery in the owner's mockup: a featured demo with sound on top, a grid of live
silent demo tiles below, arrows / d-pad to browse, Enter / A to play). Every game runs in the
visitor's own browser (Pyodide/WebAssembly; `plans/2026-10-23-game-host-and-browser-runner.md`,
`scripts/build_browser_bundle.py`), so the server only serves files.

Later, a GPU instance on AWS will run AI work (e.g. Bitmappy's AI sprite generation, AI players
driven through the outer `GameHost` layer). It is out of scope to build now, but it is scoped into
the cost estimate.

## Goals

1. `https://play.glitchy.games` serves the browser build, over HTTPS, fast worldwide.
2. Every push to `main` on GitHub publishes the site automatically.
3. The AWS setup is code in this repo, reproducible from scratch.
4. Launch cost stays around $1.50–2.50 / month.
5. The owner hears about it (email) before an AWS bill surprises them.

## Non-goals (for now)

- No servers at launch: no EC2, Lightsail, containers or databases.
- No GPU instance yet (later phase, below).
- No home page at `glitchy.games` yet — it redirects to `play.glitchy.games`.
- No docs site yet (`docs.glitchy.games` is reserved for the MkDocs site, later).
- The 24 other domains the owner holds at Namecheap (`glitchygames.*`, `twitchplaysglitchy*`)
  stay untouched.
- Not transferring any domain registration away from Namecheap.

## Anti-goals

- Long-lived AWS access keys stored in GitHub.
- A setup that only works because of hand-clicked console changes nobody can reproduce.
- A bill that can grow silently (runaway GPU instance, traffic spike) without an alert.

## Constraints and facts

- **AWS account:** the owner's existing, long-standing account. It is past the old 12-month free
  tier and was created before the July 15, 2025 credit-based free plan, so only the "Always Free"
  allowances apply (CloudFront: 1 TB transfer and 10M requests / month; Lambda; DynamoDB).
- **Domains:** registered at Namecheap (namecheap.com). Two are in scope:
  `glitchy.games` and `glitchygames.ai`.
- **Region:** us-east-1 (CloudFront certificates must live there; cheapest GPU pricing later).
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
| Placeholder | until the Arcade exists, the owner's mockup image is the placeholder |
| GPU | later, for AI work; include it in the cost picture only |

## Address map

| Address | Behaviour |
|---|---|
| `play.glitchy.games` | the site (S3 via CloudFront) |
| `glitchy.games`, `www.glitchy.games` | 301 to `https://play.glitchy.games` (path kept) |
| `glitchygames.ai`, `www.glitchygames.ai` | 301 to `https://play.glitchy.games` (path kept) |
| `http://` anything | upgraded to `https://` |
| `docs.glitchy.games`, `ai.glitchy.games` | reserved, later phases |

Redirect choices (301, path kept, `www` folded) are Claude's call. Keeping one canonical address
matters beyond SEO: browser storage (the Arcade's saves, `browser/browser_storage.py`) is
per-origin, so serving the site on two origins would split players' saves.

## Architecture (Claude's call unless noted)

```
                 Namecheap (registrar only)
                   | nameservers -> Route 53
                   v
 Route 53 zone: glitchy.games          Route 53 zone: glitchygames.ai
   play  -> ALIAS site distribution      @, www -> ALIAS redirect distribution
   @,www -> ALIAS redirect distribution
                   |                                   |
                   v                                   v
 CloudFront "site" distribution        CloudFront "redirect" distribution
   - origin: private S3 bucket (OAC)     - no real origin; a CloudFront Function
   - HTTPS cert (ACM, us-east-1)           answers every request with a 301 to
   - compression on                        https://play.glitchy.games<path>
   - response headers policy             - HTTPS cert (ACM) for the four names
                   |
                   v
 S3 bucket (private, versioned) holding build/browser/...
```

- **DNS:** move the nameservers of both domains to Route 53 at Namecheap (one manual step per
  domain, done once). Route 53 then holds every record as code. $0.50 / zone / month.
- **Certificates:** ACM in us-east-1, DNS-validated in Route 53 (automatic once the zones exist).
  Six names total, under ACM's default 10-name limit. Free.
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
  - PriceClass_100 (North America + Europe edges) to keep costs down — Claude's call; widen
    later if needed.
- **CloudFront (redirect):** separate distribution with a CloudFront Function (viewer request)
  returning the 301. Could instead be one distribution with a host-header check; two keeps the
  site's config simple. Builder may merge if it's cleaner.
- **Budget alarm:** AWS Budgets, monthly, email the owner at $10 actual and at forecast > $10.

## Infrastructure as code (Claude's call)

- **AWS CDK in Python**, in `infra/` as its own small uv project (own `pyproject.toml`), so the
  engine's dependencies don't change.
- nox sessions in the existing style: `nox -s infra-deploy`, `nox -s infra-diff`,
  `nox -s site-publish` (build + sync + invalidate, also usable locally).
- Stacks: `DnsAndCertificates`, `Site`, `Redirects`, `GitHubDeployRole`, `Budget`. Names are
  the builder's to settle.
- First deploy (`cdk bootstrap` + deploy) runs from the owner's Mac with admin credentials.

## Publishing (owner: on every push to `main`)

The repo's CI is CircleCI, which already builds the browser games on every merge to `main`, so
publishing to AWS joins that pipeline (Claude's call: no GitHub Actions, one CI system).

- A new `nox -s site-publish` session: syncs a built site directory to the bucket
  (`aws s3 sync --delete`, `.wasm` as `application/wasm`, short cache on `index.html` files,
  long on the rest) and invalidates the CloudFront distribution. Also runnable from the
  owner's Mac.
- CircleCI: after `docs-deploy` has built `build/browser/site`, run `nox -s site-publish` on
  that same directory — either as a final step of the `deploy-docs` job (no second ~2 GB
  toolchain restore) or a separate job that receives the directory through a workspace. The
  builder picks; Claude's lean is a step in `deploy-docs`, since it already holds the build. A
  failed AWS publish must not undo or block the GitHub Pages docs deploy that already pushed.
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

The Arcade does not exist yet. Until it does, `play.glitchy.games` serves a placeholder built
around the owner's mockup image (the gallery screenshot), stored in the repo. When the Arcade
app lands, the arcade bundle replaces it.

**OPEN (owner):** the games already build as a playable site (`build/browser/site`). The
placeholder could link to them (each game at `play.glitchy.games/<game>/`), or the mockup could
stand alone until the Arcade is ready.

## Costs

### Launch (monthly, us-east-1)

| Item | Cost |
|---|---|
| Route 53 hosted zones (2) | $1.00 |
| Route 53 queries | ~$0 |
| S3 storage (~100 MB incl. versions) + requests | ~$0.05 |
| CloudFront (within Always Free 1 TB / 10M req) | $0 |
| ACM certificates | $0 |
| CloudFront Functions (2M free invocations / month) | $0 |
| AWS Budgets (first 2 budgets free) | $0 |
| **Total** | **~$1.50–2.50** |

Plus existing Namecheap renewals (unchanged). Pyodide-based pages are ~10–30 MB per first visit,
so 1 TB covers roughly 35–100k first-time visitors / month before CloudFront charges (~$0.085/GB
in NA/EU).

### Later: GPU for AI work (not built now)

Prices from third-party trackers (verify on AWS before buying):

| Instance | GPU | On-demand | 24/7 | Start/stop on demand |
|---|---|---|---|---|
| g4dn.xlarge | NVIDIA T4, 16 GB | ~$0.53/hr | ~$384/mo | ~$20–60/mo |
| g6.xlarge | NVIDIA L4, 24 GB | ~$0.80/hr | ~$588/mo | ~$30–90/mo |

Plus EBS storage (~$8/mo per 100 GB gp3) and ~$3.60/mo for a public IPv4 while running. Spot
pricing is often 60–70% lower. New accounts usually have a GPU (G-family) vCPU quota of 0 — check
and request an increase well before it's needed. "Dedicated Instances" (AWS's single-tenant
option) cost extra and aren't needed; a normal on-demand instance is the owner's own machine.

## Manual steps for the owner

1. Run the first `nox -s infra-deploy` with admin AWS credentials.
2. At Namecheap, set custom nameservers for `glitchy.games` and `glitchygames.ai` to the four
   Route 53 nameservers each zone reports.
3. Confirm the AWS Budgets email subscription.

## Today's DNS (checked 2026-10-27 with `dig`)

Both domains are identical: Namecheap BasicDNS (`dns1/dns2.registrar-servers.com`), a Namecheap
parking page on `@` and `www`, **Namecheap email forwarding** (MX `eforward1-5.registrar-servers.com`
and TXT `v=spf1 include:spf.efwd.registrar-servers.com ~all`), no `play` record, and **no DS
record (DNSSEC off)**, so a nameserver move needs no DNSSEC step. Nothing but the parking page
is served, so propagation time costs nothing.

## Risks

- **DNS cutover and email forwarding:** see "Today's DNS". Namecheap's email forwarding is
  configured in Namecheap's panel and expects Namecheap DNS; whether it keeps working with the MX
  and SPF records copied into Route 53 must be verified (or the owner confirms the forwarding is
  unused).
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

- **Mockup image:** the owner supplied it in conversation (not yet in the repo). It goes in
  the repo at `site/placeholder/arcade-mockup.png` beside a minimal `index.html`; the owner
  offered it as the placeholder, so publishing it is intended.
- **A failed AWS publish turns the CircleCI build red** (so the owner hears about it), and runs
  after the GitHub Pages push, so it can never undo the docs. A docs build failure also skips
  the AWS publish; the site may fall behind until the next green merge, which is acceptable.
- **CDK bootstrap:** the builder checks for an existing `CDKToolkit` stack, Route 53 zones, ACM
  certificates and a CircleCI OIDC provider in the account before creating any (read-only
  `aws` calls), and reuses what's there.

## Sources

- AWS free tier changes: https://tech-insider.org/what-changed-in-the-aws-free-tier-for-2026/ ,
  https://spot.rackspace.com/blog/aws-free-tier
- GPU pricing: https://calculator.holori.com/aws/ec2/g4dn.xlarge/us-east-1 ,
  https://calculator.holori.com/aws/ec2/g6.xlarge/us-east-1
- Lightsail pricing (considered, not chosen): https://cloudburn.io/blog/amazon-lightsail-pricing
