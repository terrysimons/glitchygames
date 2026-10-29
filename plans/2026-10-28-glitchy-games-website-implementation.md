# glitchy.games Website Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the owner's mockup at `https://play.glitchy.games` from S3 + CloudFront on the
Free flat-rate plan, with `glitchy.games`, `www.glitchy.games`, `glitchygames.ai` and
`www.glitchygames.ai` redirecting to it, all defined as AWS CDK code in this repo and published
by CircleCI on every merge to `main`.

**Architecture:** A separate uv project, `infra/` (not a workspace member, so the engine's
`uv.lock` is untouched), holds the CDK app (five stacks: DNS zones, the site, the
glitchygames.ai redirect, the CircleCI deploy role, the budget), one CloudFront Function shared
as source by both distributions, and `glitchy_site.publish`, which uploads a directory to the
site bucket with boto3 and invalidates the cache. nox sessions wrap it; a new CircleCI job runs
the publish with OIDC credentials.

**Tech Stack:** Python 3.14, uv, nox, AWS CDK v2 (Python, `aws-cdk-lib`, CLI via `npx`),
boto3, CloudFront Functions (JavaScript runtime 2.0), Node's built-in test runner, pytest,
CircleCI.

**Spec:** `docs/specs/2026-10-27-glitchy-games-website-design.md`

> **Update 2026-10-28 (after the build):** the site moved from `web/placeholder/` to
> `src/website/` (the owner: `src/` holds all glitchygames source, the website included), and
> is no longer called a placeholder. `nox -s site-publish` defaults to `src/website`, whose path
> is in `[tool.glitchygames] unmeasured-paths`. The tasks below keep their original paths as a
> record; the role ARN also moved from a pipeline parameter to a CircleCI project environment
> variable (Task 7, Task 8 Step 8).

## Global Constraints

- **Never commit or push** (the owner's rule). Each task ends with a checkpoint: show
  `git status --short` and the diff summary; the owner commits.
- Work on a new branch from `origin/main`, e.g. `feature/glitchy-games-website` (the main
  checkout is on another feature branch with staged work: don't disturb it; use a worktree).
- Region `us-east-1` for every stack and every boto3 client, passed explicitly.
- Canonical host `play.glitchy.games`; every other host gets a 301 to
  `https://play.glitchy.games<path>?<query>`, path and query kept.
- Hosts: distribution 1 serves `play.glitchy.games`, `glitchy.games`, `www.glitchy.games`;
  distribution 2 serves `glitchygames.ai`, `www.glitchygames.ai`.
- Nothing a CloudFront flat-rate plan doesn't support: no Origin Access Identity (use OAC), no
  real-time logs, and a separate CloudFront Function resource per distribution.
- No COOP/COEP headers, no Content-Security-Policy (PyScript loads from `pyscript.net`).
- Cache-Control at upload: `public, max-age=60` for `.html`, `public, max-age=86400` for the rest.
  `.wasm` uploads as `application/wasm`.
- No AWS keys anywhere: CircleCI uses OIDC; the owner's Mac uses their own profile.
- The budget alert email never appears in the repo: passed at deploy time from the environment
  variable `GLITCHY_SITE_BUDGET_EMAIL`. Budget: $10 / month, ACTUAL > 100 % and FORECASTED > 100 %.
- House style: explicit long names (no abbreviations), keyword-only arguments (`*`), Google
  docstrings, ruff (root config, 100 columns), `from __future__ import annotations`, single quotes.
- The placeholder lives in `web/placeholder/` (`site/` is the gitignored MkDocs output).

## Review Focus

1. **An empty or wrong `--source` directory**: publishing must refuse (non-zero exit, message
   naming the directory) instead of deleting every object in the bucket. Owned by Task 6.
2. **Host header case** (`Play.Glitchy.Games`): the function must treat it as canonical, not
   redirect-loop. Owned by Task 2.
3. **Query strings** with several values for one key or characters needing encoding (`?a=1&a=2`,
   `?q=hello%20world`) survive the redirect exactly. Owned by Task 2.
4. **Directory URLs** (`/paddleslap/` and `/paddleslap`) on the canonical host must fetch
   `/paddleslap/index.html` (S3 behind OAC has no directory index; the Arcade later needs it).
   Owned by Task 2.
5. **A deploy without `GLITCHY_SITE_BUDGET_EMAIL`** must fail at synth, naming the variable,
   never create a budget with no subscriber. Owned by Task 1 (settings) and Task 5 (budget).

---

## File Structure

```
infra/
  pyproject.toml            uv project glitchy-site: aws-cdk-lib, constructs, boto3; dev: pytest
  uv.lock
  cdk.json                  "app" + context circleci_organization_id / circleci_project_id
  src/glitchy_site/
    __init__.py
    settings.py             constants + SiteSettings from CDK context
    redirect_function.py    loads functions/redirect_to_play.js as cloudfront.FunctionCode
    functions/redirect_to_play.js
    dns_zones_stack.py      DnsZonesStack
    site_stack.py           SiteStack
    redirect_stack.py       GlitchygamesAiRedirectStack
    deploy_role_stack.py    CircleCiDeployRoleStack
    budget_stack.py         BudgetStack
    app.py                  build_app() + main()
    publish.py              plan_publish() + publish() + main()
  tests/
    test_glitchy_site_settings.py
    test_glitchy_site_stacks.py
    test_glitchy_site_publish.py
    functions/redirect_to_play.test.mjs
web/placeholder/
  index.html
  arcade-mockup.png
noxfile.py                  + infra-test, infra-diff, infra-deploy, site-publish; _CODE_DIRS + 'infra'
pyproject.toml              ruff src + "infra/src"
.circleci/config.yml        + test-infra and deploy-site jobs (role ARN from a project env var)
tests/test_ci_config.py     + tests for both jobs
```

---

### Task 1: The `infra/` project, its settings, and `nox -s infra-test`

**Files:**
- Create: `infra/pyproject.toml`, `infra/uv.lock` (by `uv lock`), `infra/cdk.json`,
  `infra/src/glitchy_site/__init__.py`, `infra/src/glitchy_site/settings.py`
- Test: `infra/tests/test_glitchy_site_settings.py`
- Modify: `noxfile.py` (`_CODE_DIRS` gains `'infra'`; new session `infra-test`),
  `pyproject.toml` (`[tool.ruff] src` gains `"infra/src"`)

**Interfaces:**
- Produces (`glitchy_site.settings`):
  - `REGION = 'us-east-1'`
  - `CANONICAL_HOST = 'play.glitchy.games'`
  - `GLITCHY_GAMES_APEX = 'glitchy.games'`, `GLITCHYGAMES_AI_APEX = 'glitchygames.ai'`
  - `SITE_HOSTS = ('play.glitchy.games', 'glitchy.games', 'www.glitchy.games')`
  - `GLITCHYGAMES_AI_HOSTS = ('glitchygames.ai', 'www.glitchygames.ai')`
  - `SITE_STACK_NAME = 'GlitchyGamesSite'`, `DEPLOY_ROLE_NAME = 'glitchy-games-site-deploy'`
  - `BUDGET_EMAIL_CONTEXT_KEY = 'budget_alert_email'`,
    `ORGANIZATION_CONTEXT_KEY = 'circleci_organization_id'`,
    `PROJECT_CONTEXT_KEY = 'circleci_project_id'`
  - `class MissingSettingError(ValueError)`
  - `@dataclasses.dataclass(frozen=True, kw_only=True) class SiteSettings` with
    `budget_alert_email: str`, `circleci_organization_id: str`, `circleci_project_id: str`,
    `budget_limit_usd: int = 10`
  - `def site_settings_from_context(*, node: constructs.Node) -> SiteSettings`

- [ ] **Step 1: Create the project.** `infra/pyproject.toml`: name `glitchy-site`,
  `requires-python = ">=3.14"`, dependencies `aws-cdk-lib`, `constructs`, `boto3` (latest at
  implementation, pinned by the lock), dependency group `dev` = `pytest`; hatchling build with
  package `src/glitchy_site`; `[tool.pytest.ini_options] testpaths = ["tests"]`. Run
  `uv lock --project infra`. `infra/cdk.json`:
  `{"app": "uv run --frozen python -m glitchy_site.app", "context": {"circleci_organization_id": "", "circleci_project_id": ""}}`
  (the owner fills both IDs in Task 8).

- [ ] **Step 2: Write the failing tests** in `infra/tests/test_glitchy_site_settings.py`:

```python
def test_settings_come_from_the_context():
    app = aws_cdk.App(context={
        'budget_alert_email': 'owner@example.com',
        'circleci_organization_id': 'organization-id',
        'circleci_project_id': 'project-id',
    })
    settings = site_settings_from_context(node=app.node)
    assert settings == SiteSettings(
        budget_alert_email='owner@example.com',
        circleci_organization_id='organization-id',
        circleci_project_id='project-id',
    )
    assert settings.budget_limit_usd == 10


@pytest.mark.parametrize('missing_key', [
    'budget_alert_email', 'circleci_organization_id', 'circleci_project_id',
])
@pytest.mark.parametrize('missing_value', [None, ''])
def test_a_missing_or_empty_setting_is_refused_by_name(missing_key, missing_value):
    context = {
        'budget_alert_email': 'owner@example.com',
        'circleci_organization_id': 'organization-id',
        'circleci_project_id': 'project-id',
    }
    if missing_value is None:
        del context[missing_key]
    else:
        context[missing_key] = missing_value
    with pytest.raises(MissingSettingError, match=missing_key):
        site_settings_from_context(node=aws_cdk.App(context=context).node)


def test_the_budget_setting_names_the_environment_variable():
    context = {'circleci_organization_id': 'organization-id', 'circleci_project_id': 'project-id'}
    with pytest.raises(MissingSettingError, match='GLITCHY_SITE_BUDGET_EMAIL'):
        site_settings_from_context(node=aws_cdk.App(context=context).node)
```

- [ ] **Step 3: Run:** `uv run --project infra pytest infra/tests -q`. Expected: FAIL (import error).

- [ ] **Step 4: Implement `settings.py`** with the names above. `site_settings_from_context`
  reads each key with `node.try_get_context`; a missing or empty value raises
  `MissingSettingError` naming the key, and for `budget_alert_email` also
  `GLITCHY_SITE_BUDGET_EMAIL`.

- [ ] **Step 5: Run** the same command. Expected: PASS.

- [ ] **Step 6: Add the nox session** `infra-test` (`venv_backend='none'`, `default=False`,
  beside the other test sessions): runs `uv run --project infra --frozen pytest infra/tests` and,
  from Task 2 on, `node --test infra/tests/functions`. Add `'infra'` to `_CODE_DIRS` and
  `"infra/src"` to `[tool.ruff] src`. Run `nox -s infra-test` and `nox -s lint-code`. Expected:
  both pass.

- [ ] **Step 7: Checkpoint** for the owner (no commit).

---

### Task 2: The redirect CloudFront Function

**Files:**
- Create: `infra/src/glitchy_site/functions/redirect_to_play.js`,
  `infra/src/glitchy_site/redirect_function.py`
- Test: `infra/tests/functions/redirect_to_play.test.mjs`
- Modify: `noxfile.py` (`infra-test` also runs `node --test infra/tests/functions`)

**Interfaces:**
- Produces: `redirect_to_play.js` defines a top-level `function handler(event)` (CloudFront
  Functions JavaScript runtime 2.0, viewer request). `glitchy_site.redirect_function`:
  `REDIRECT_FUNCTION_PATH: Path`, `def redirect_function_code() -> cloudfront.FunctionCode`
  (`FunctionCode.from_file(file_path=str(REDIRECT_FUNCTION_PATH))`).
- Behaviour, for every distribution that uses it:
  - Host (lowercased, port stripped) is not `play.glitchy.games` → return
    `{statusCode: 301, statusDescription: 'Moved Permanently', headers: {location: {value: 'https://play.glitchy.games' + uri + query}}}`.
  - Otherwise return the request; a URI ending `/` gets `index.html` appended, and a URI whose
    last segment has no `.` gets `/index.html` appended.

- [ ] **Step 1: Write the failing tests** with `node:test`. Load the function the way
  CloudFront does (no module system): read the file and evaluate it in a `vm` context, ending
  with `;handler`. A helper `requestFor({host, uri, querystring = {}})` builds the event
  (`{request: {uri, querystring, headers: {host: {value: host}}}}`). Tests:

```javascript
test('another host is sent to the canonical host with its path', () => {
  const response = handler(requestFor({host: 'glitchy.games', uri: '/paddleslap/'}));
  assert.equal(response.statusCode, 301);
  assert.equal(response.headers.location.value, 'https://play.glitchy.games/paddleslap/');
});
test('every non-canonical host redirects', () => { /* www.glitchy.games, glitchygames.ai,
  www.glitchygames.ai: each 301 to https://play.glitchy.games/ */ });
test('the query string survives, repeated keys and encoding included', () => {
  const response = handler(requestFor({host: 'glitchygames.ai', uri: '/', querystring: {
    a: {value: '1', multiValue: [{value: '1'}, {value: '2'}]},
    q: {value: 'hello%20world'},
  }}));
  assert.equal(response.headers.location.value, 'https://play.glitchy.games/?a=1&a=2&q=hello%20world');
});
test('the canonical host is recognised in any case and with a port', () => {
  /* 'Play.Glitchy.Games' and 'play.glitchy.games:443' return a request, not a 301 */ });
test('directory URLs on the canonical host fetch their index', () => {
  /* '/' -> '/index.html'; '/paddleslap/' -> '/paddleslap/index.html';
     '/paddleslap' -> '/paddleslap/index.html'; '/arcade-mockup.png' unchanged */ });
```

  (CloudFront passes query values as received, already percent-encoded; the function must not
  encode them again.)

- [ ] **Step 2: Run:** `node --test infra/tests/functions`. Expected: FAIL.
- [ ] **Step 3: Implement** `redirect_to_play.js` (`var`/`function` style is fine; runtime 2.0
  also allows `const`/`let`; no `require`, no network) and `redirect_function.py`.
- [ ] **Step 4: Run** `nox -s infra-test`. Expected: PASS.
- [ ] **Step 5: Checkpoint.**

---

### Task 3: The DNS zones stack

**Files:**
- Create: `infra/src/glitchy_site/dns_zones_stack.py`
- Test: `infra/tests/test_glitchy_site_stacks.py`

**Interfaces:**
- Produces: `class DnsZonesStack(aws_cdk.Stack)`, `__init__(self, scope, construct_id, **kwargs)`,
  attributes `glitchy_games_zone: route53.PublicHostedZone` and
  `glitchygames_ai_zone: route53.PublicHostedZone`; outputs `GlitchyGamesNameServers` and
  `GlitchygamesAiNameServers` (each `Fn.join(',', zone.hosted_zone_name_servers)`). Both zones
  `RemovalPolicy.RETAIN`.
- Test helper (used by Tasks 3-5): `TEST_ENVIRONMENT = aws_cdk.Environment(account='123456789012', region='us-east-1')`.

- [ ] **Step 1: Write the failing test** `test_the_zones_stack_holds_both_zones_and_names_their_servers`:
  `Template.from_stack(stack).resource_count_is('AWS::Route53::HostedZone', 2)`;
  `has_resource_properties` for `Name` `glitchy.games.` and `glitchygames.ai.`; both outputs
  exist (`template.find_outputs('GlitchyGamesNameServers')` non-empty, likewise the other); no
  `AWS::Route53::RecordSet` other than what CDK adds by default (none: no MX, no TXT; the
  Namecheap email-forwarding records are deliberately not copied).
- [ ] **Step 2: Run** `uv run --project infra pytest infra/tests -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** again. Expected: PASS.
- [ ] **Step 5: Checkpoint.**

---

### Task 4: The site stack and the glitchygames.ai redirect stack

**Files:**
- Create: `infra/src/glitchy_site/site_stack.py`, `infra/src/glitchy_site/redirect_stack.py`
- Test: `infra/tests/test_glitchy_site_stacks.py`

**Interfaces:**
- Consumes: `DnsZonesStack` zones; `redirect_function_code()`; settings constants.
- Produces:
  - `class SiteStack(aws_cdk.Stack)`, `__init__(self, scope, construct_id, *, zone: route53.IHostedZone, **kwargs)`;
    attributes `bucket: s3.Bucket`, `distribution: cloudfront.Distribution`; outputs
    `SiteBucketName`, `SiteDistributionId`.
  - `class GlitchygamesAiRedirectStack(aws_cdk.Stack)`, `__init__(self, scope, construct_id, *, zone: route53.IHostedZone, **kwargs)`.
- Site stack contents: private bucket (`BlockPublicAccess.BLOCK_ALL`, `enforce_ssl=True`,
  versioned, lifecycle rule expiring noncurrent versions after 30 days,
  `RemovalPolicy.RETAIN`); ACM certificate for `SITE_HOSTS` validated against `zone`;
  distribution with origin `S3BucketOrigin.with_origin_access_control(bucket)`,
  `domain_names=list(SITE_HOSTS)`, `ViewerProtocolPolicy.REDIRECT_TO_HTTPS`,
  `CachePolicy.CACHING_OPTIMIZED` (gzip + brotli), `ResponseHeadersPolicy.SECURITY_HEADERS`,
  `default_root_object='index.html'`, `HttpVersion.HTTP2_AND_3`, and its own
  `cloudfront.Function` (viewer request) from `redirect_function_code()`; Route 53 A and AAAA
  alias records for all three hosts.
- Redirect stack contents: certificate for `GLITCHYGAMES_AI_HOSTS`; distribution with
  `HttpOrigin(CANONICAL_HOST)` (never reached: the function answers every request), the same
  protocol policy, its own `cloudfront.Function` from the same code; A and AAAA alias records
  for both hosts.

- [ ] **Step 1: Write the failing tests:**
  - `test_the_site_bucket_is_private_and_versioned`: `PublicAccessBlockConfiguration` all four
    true; `VersioningConfiguration.Status == 'Enabled'`; a lifecycle rule with
    `NoncurrentVersionExpiration.NoncurrentDays == 30`; `DeletionPolicy == 'Retain'`.
  - `test_the_site_distribution_serves_the_three_glitchy_games_names`: `Aliases` equals
    `['play.glitchy.games', 'glitchy.games', 'www.glitchy.games']`;
    `ViewerProtocolPolicy == 'redirect-to-https'`; `DefaultRootObject == 'index.html'`.
  - `test_the_site_reaches_s3_through_origin_access_control_only`: one
    `AWS::CloudFront::OriginAccessControl`; no `AWS::CloudFront::CloudFrontOriginAccessIdentity`;
    no `RealtimeLogConfig`.
  - `test_each_distribution_has_its_own_function`: across both stacks, two
    `AWS::CloudFront::Function` resources, each referenced by its own distribution as
    `viewer-request`, both with `FunctionConfig.Runtime == 'cloudfront-js-2.0'`.
  - `test_the_site_sends_no_cross_origin_isolation_headers`: the response headers policy is the
    managed SecurityHeadersPolicy id `67f7725c-6f97-4210-82d7-5512b31e9d03`; no custom policy
    defines `Cross-Origin-Embedder-Policy`.
  - `test_every_host_has_ipv4_and_ipv6_alias_records`: A and AAAA records for each of the five
    hosts, in the right zone.
  - `test_the_certificates_cover_exactly_their_hosts`: site certificate names = `SITE_HOSTS`;
    redirect certificate names = `GLITCHYGAMES_AI_HOSTS`; both DNS-validated.
  - `test_the_site_stack_names_its_bucket_and_distribution`: outputs `SiteBucketName` and
    `SiteDistributionId` exist.
- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement both stacks.**
- [ ] **Step 4: Run** `nox -s infra-test`. Expected: PASS.
- [ ] **Step 5: Checkpoint.**

---

### Task 5: The deploy role, the budget, the app, and the infra nox sessions

**Files:**
- Create: `infra/src/glitchy_site/deploy_role_stack.py`, `infra/src/glitchy_site/budget_stack.py`,
  `infra/src/glitchy_site/app.py`
- Test: `infra/tests/test_glitchy_site_stacks.py`
- Modify: `noxfile.py` (sessions `infra-diff`, `infra-deploy`)

**Interfaces:**
- Consumes: `SiteSettings`, `SiteStack.bucket` / `.distribution`, `DnsZonesStack`.
- Produces:
  - `class CircleCiDeployRoleStack(aws_cdk.Stack)`, `__init__(self, scope, construct_id, *, settings: SiteSettings, bucket: s3.IBucket, distribution: cloudfront.IDistribution, **kwargs)`;
    output `DeployRoleArn`.
  - `class BudgetStack(aws_cdk.Stack)`, `__init__(self, scope, construct_id, *, settings: SiteSettings, **kwargs)`.
  - `def build_app(*, app: aws_cdk.App, account: str) -> None` adds the stacks
    `GlitchyGamesDnsZones`, `GlitchyGamesSite` (= `SITE_STACK_NAME`), `GlitchyGamesAiRedirect`,
    `GlitchyGamesSiteDeployRole`, `GlitchyGamesBudget`, each with
    `env=Environment(account=account, region=REGION)`.
  - `def main() -> None`: `build_app(app=App(), account=os.environ['CDK_DEFAULT_ACCOUNT'])`,
    then `app.synth()`; `python -m glitchy_site.app` calls it.
- Deploy role: an `iam.OpenIdConnectProvider` for
  `https://oidc.circleci.com/org/<organization id>` with client id = the organization id; role
  `DEPLOY_ROLE_NAME` trusting `sts:AssumeRoleWithWebIdentity` with conditions
  `StringEquals <issuer>:aud = <organization id>` and
  `StringLike <issuer>:sub = org/<organization id>/project/<project id>/user/*`; permissions:
  `s3:ListBucket` on the bucket, `s3:PutObject` and `s3:DeleteObject` on `bucket/*`,
  `cloudfront:CreateInvalidation` on the site distribution's ARN only,
  `cloudformation:DescribeStacks` on the `GlitchyGamesSite` stack's ARN only. IAM cannot
  condition on CircleCI's branch claim, so "main only" is enforced by the workflow filter
  (Task 7); note this in the stack's docstring.
- Budget: `budgets.CfnBudget`, `COST`, `MONTHLY`, limit `settings.budget_limit_usd` USD; two
  notifications (`ACTUAL` > 100 %, `FORECASTED` > 100 %, `PERCENTAGE`), each with one `EMAIL`
  subscriber `settings.budget_alert_email`.
- nox sessions (`venv_backend='none'`, `default=False`), each run from `infra/` with
  `npx --yes aws-cdk@<pinned CLI version>` (a module constant `_AWS_CDK_CLI_VERSION`, at least
  the version `aws-cdk-lib` in `infra/uv.lock` needs):
  - `infra-diff`: `cdk diff`.
  - `infra-deploy`: `cdk deploy` of the stacks named in `session.posargs` (default `--all`),
    `--require-approval broadening`. Both pass `-c budget_alert_email=$GLITCHY_SITE_BUDGET_EMAIL`
    and refuse to start (`session.error`, naming the variable) when it is unset.

- [ ] **Step 1: Write the failing tests:**
  - `test_the_deploy_role_trusts_only_this_circleci_project`: the trust policy's `aud` and
    `sub` conditions equal the values above for `organization-id` / `project-id`.
  - `test_the_deploy_role_may_only_publish_the_site`: its policy statements are exactly the
    four above (actions and resources); no `*` resource; no `s3:*`.
  - `test_the_budget_emails_the_owner_at_ten_dollars`: limit `10` `USD`; notifications
    `ACTUAL` and `FORECASTED`, threshold `100`, subscriber address from the context.
  - `test_the_app_builds_five_stacks_in_us_east_1`: `build_app(app=App(context=...), account='123456789012')`;
    `app.synth().stacks` names the five stacks, each with region `us-east-1`.
  - `test_the_app_refuses_to_build_without_the_budget_email`: no `budget_alert_email` →
    `MissingSettingError` matching `GLITCHY_SITE_BUDGET_EMAIL` (Review Focus 5).
- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement** both stacks, `app.py` and the two nox sessions.
- [ ] **Step 4: Run** `nox -s infra-test`, then `GLITCHY_SITE_BUDGET_EMAIL= nox -s infra-diff`.
  Expected: tests PASS; the diff session stops with the message naming
  `GLITCHY_SITE_BUDGET_EMAIL` before calling `npx`.
- [ ] **Step 5: Checkpoint.**

---

### Task 6: The publisher, the placeholder, and `nox -s site-publish`

**Files:**
- Create: `infra/src/glitchy_site/publish.py`, `web/placeholder/index.html`,
  `web/placeholder/arcade-mockup.png`
- Test: `infra/tests/test_glitchy_site_publish.py`
- Modify: `noxfile.py` (session `site-publish`)

**Interfaces:**
- Consumes: `SITE_STACK_NAME`, `REGION`; the stack outputs `SiteBucketName` and
  `SiteDistributionId` (Task 4).
- Produces (`glitchy_site.publish`):
  - `@dataclasses.dataclass(frozen=True, kw_only=True) class Upload`: `local_path: Path`,
    `key: str`, `content_type: str`, `cache_control: str`
  - `@dataclasses.dataclass(frozen=True, kw_only=True) class PublishPlan`:
    `uploads: tuple[Upload, ...]`, `deletions: tuple[str, ...]`
  - `@dataclasses.dataclass(frozen=True, kw_only=True) class SiteTarget`: `bucket_name: str`,
    `distribution_id: str`
  - `class PublishRefusedError(ValueError)`
  - `def content_type_for(*, path: Path) -> str`
  - `def cache_control_for(*, key: str) -> str`
  - `def plan_publish(*, source_directory: Path, existing_keys: Iterable[str]) -> PublishPlan`
  - `def site_target(*, cloudformation_client: Any, stack_name: str) -> SiteTarget`
  - `def publish(*, source_directory: Path, s3_client: Any, cloudformation_client: Any, cloudfront_client: Any, stack_name: str = SITE_STACK_NAME) -> PublishPlan`
    (clients passed in, so tests attach a botocore `Stubber` to each)
  - `def main(argv: Sequence[str] | None = None) -> int`: `--source PATH` (required),
    `--stack NAME` (default `SITE_STACK_NAME`), `--dry-run` (print the plan, change nothing);
    builds the three clients from `boto3.Session(region_name=REGION)`;
    `PublishRefusedError` → message on stderr, exit 1.
- Rules: every file under the source is uploaded every time (keys are POSIX paths relative to
  the source); dotfiles and dot-directories (`.DS_Store`) are skipped; bucket keys with no local
  file are deleted; the source must exist, be a directory, and contain `index.html`, otherwise
  `PublishRefusedError` naming it (Review Focus 1); after uploading and deleting, one
  invalidation of `/*`. Uploads before deletions, so a visitor never sees a missing page.
  Content types: `.html` `text/html; charset=utf-8`, `.js`/`.mjs` `text/javascript`, `.css`
  `text/css`, `.json` `application/json`, `.wasm` `application/wasm`, `.png` `image/png`,
  `.zip`/`.whl` `application/zip`, `.toml` `text/plain; charset=utf-8`, else `mimetypes`, else
  `application/octet-stream`.
- Placeholder: `index.html` titled "GlitchyGames Arcade — coming soon", showing
  `arcade-mockup.png` full-width with alt text, a one-line "coming soon" caption and a link to
  https://github.com/terrysimons/glitchygames; dark background matching the mockup; no external
  resources. The PNG is the owner's mockup (2000 x 1417, from this session's conversation:
  `/private/tmp/claude-501/-Users-terry-Dropbox-dev-glitchygames/dc61ca66-e699-491a-b580-de29c3fab4ca/images/1.png`;
  if that file is gone, ask the owner for it).
- nox `site-publish` (`venv_backend='none'`, `default=False`):
  `uv run --project infra --frozen python -m glitchy_site.publish --source <posargs or web/placeholder>`.

- [ ] **Step 1: Write the failing tests:**
  - `test_content_types` (parametrized over the table above, `.wasm` → `application/wasm`
    included) and `test_html_is_cached_briefly_and_the_rest_for_a_day`.
  - `test_the_plan_uploads_every_file_and_deletes_what_is_gone` (`tmp_path` with
    `index.html`, `games/a/index.html`; existing keys `index.html`, `old.png` → uploads both
    files with keys `index.html` and `games/a/index.html`; deletions `('old.png',)`).
  - `test_dotfiles_are_neither_uploaded_nor_kept` (`.DS_Store` not uploaded; an existing
    `.DS_Store` key is deleted).
  - `test_publishing_refuses_a_missing_empty_or_index_less_source` (parametrized: missing
    path, a file, an empty directory, a directory without `index.html`) →
    `PublishRefusedError` naming the path, and no S3 call is made.
  - `test_the_site_target_comes_from_the_stack_outputs` (botocore `Stubber` on a
    `cloudformation` client: `describe_stacks` returns the two outputs).
  - `test_publish_uploads_then_deletes_then_invalidates` (`Stubber` on each of the `s3`,
    `cloudformation` and `cloudfront` clients, made from `boto3.Session(region_name='us-east-1', aws_access_key_id='test', aws_secret_access_key='test')`;
    expected calls in order: `describe_stacks`, `list_objects_v2`, `put_object` per file with
    `ContentType` and `CacheControl`, `delete_objects`, `create_invalidation` with
    `Paths={'Quantity': 1, 'Items': ['/*']}`).
  - `test_the_placeholder_is_publishable`: `plan_publish(source_directory=<repo>/web/placeholder, existing_keys=[])`
    uploads exactly `index.html` (`text/html; charset=utf-8`) and `arcade-mockup.png`
    (`image/png`).
  - `test_the_placeholder_loads_nothing_from_elsewhere`: `index.html` has no `http` URL in
    `src=` or `href=` other than the GitHub link.
- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement** `publish.py`, the placeholder files and the nox session. Patch
  only the network (Stubber); everything else real (`tmp_path`).
- [ ] **Step 4: Run** `nox -s infra-test` and
  `uv run --project infra --frozen python -m glitchy_site.publish --source web/placeholder --dry-run`.
  Expected: PASS; the dry run prints the two uploads (it needs no credentials: `--dry-run`
  plans against an empty key list and never builds a client).
- [ ] **Step 5: Checkpoint.**

---

### Task 7: CircleCI: test the infra on every branch, publish from `main`

**Files:**
- Modify: `.circleci/config.yml`, `tests/test_ci_config.py`

**Interfaces:**
- Consumes: `nox -s infra-test` (Task 1), `nox -s site-publish` (Task 6), role
  `glitchy-games-site-deploy` (Task 5).
- Produces:
  - The role's ARN comes from the CircleCI project environment variable `SITE_DEPLOY_ROLE_ARN`
    (set by the owner in Task 8), not a pipeline parameter: it names the AWS account, and the
    configuration is public (the owner, 2026-10-28: "Make SITE_DEPLOY_ROLE_ARN private").
  - Job `test-infra`: `cimg/python:<< pipeline.parameters.PYTHON_LATEST_VERSION >>-node`
    (CDK's Python library needs Node), `resource_class: small`, `restore-uv-cache-posix`,
    `install-deps-posix`, `uvx --from "nox[uv]==<< pipeline.parameters.NOX_VERSION >>" nox -s infra-test`,
    `save-uv-cache-posix`. In the workflow with no filters (every branch).
  - Job `deploy-site`: `cimg/python:<< pipeline.parameters.PYTHON_LATEST_VERSION >>`,
    `resource_class: small`, `environment: AWS_REGION: us-east-1`, a step that writes
    `$CIRCLE_OIDC_TOKEN_V2` to a file and exports `AWS_WEB_IDENTITY_TOKEN_FILE` and
    `AWS_ROLE_ARN` (from `SITE_DEPLOY_ROLE_ARN`; refuses to run when it is unset, with a message
    saying where to set it), then `nox -s site-publish`. boto3 assumes the role from those variables by
    itself; no AWS CLI. In the workflow: `requires: [build-and-test-macos, test-infra]`,
    `filters: branches: only: main`, `serial-group: << pipeline.project.slug >>/deploy-site`.

- [ ] **Step 1: Write the failing tests** in `tests/test_ci_config.py`, using the existing
  `circleci_workflow_job` helper:
  - `test_the_infra_tests_run_on_every_branch`: the `test-infra` entry has no `filters:`; the
    config runs `nox -s infra-test`.
  - `test_the_site_deploys_from_main_after_its_tests`: the `deploy-site` entry requires
    `build-and-test-macos` and `test-infra`, has `only: main` and a `serial-group:`.
  - `test_the_site_deploy_uses_oidc_not_stored_keys`: the job's text contains
    `CIRCLE_OIDC_TOKEN_V2` and `AWS_WEB_IDENTITY_TOKEN_FILE`, and the whole config contains no
    `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`.
- [ ] **Step 2: Run** `uv run pytest tests/test_ci_config.py --dummy-only -q`. Expected: the
  three new tests FAIL.
- [ ] **Step 3: Implement** the parameter, both jobs and the workflow entries.
- [ ] **Step 4: Run** the same tests, then `nox -s lint-yaml` and `nox -s lint-circleci`.
  Expected: PASS.
- [ ] **Step 5: Checkpoint.**

---

### Task 8: Go live (the owner, with the implementer guiding)

Manual steps from the spec, in order; each has its check. Nothing here is automated, and
nothing is done without the owner at the keyboard.

- [ ] **Step 1: Credentials.** The owner has an admin AWS profile on the Mac (`brew install
  awscli`, then `aws configure sso` or `aws configure`). Check: `aws sts get-caller-identity`
  prints the account. Check for things to reuse (spec, "Calls Claude made"):
  `aws cloudformation describe-stacks --stack-name CDKToolkit --region us-east-1`,
  `aws route53 list-hosted-zones`, `aws iam list-open-id-connect-providers`. If a provider for
  `oidc.circleci.com/org/<organization id>` already exists, put its ARN in `infra/cdk.json` as
  `circleci_oidc_provider_arn` (IAM allows one per URL; the stack then reuses it).
- [ ] **Step 2: CircleCI IDs.** The owner copies the organization ID (Organization Settings)
  and project ID (Project Settings) into `infra/cdk.json`.
- [ ] **Step 3: Bootstrap and zones.** `cd infra && npx --yes aws-cdk@<version> bootstrap aws://<account>/us-east-1`
  (skip if `CDKToolkit` exists), then
  `GLITCHY_SITE_BUDGET_EMAIL=<address> nox -s infra-deploy -- GlitchyGamesDnsZones`. Check: the
  two NameServers outputs, four servers each.
- [ ] **Step 4: Namecheap.** For `glitchy.games` and `glitchygames.ai`: Domain List → Manage →
  Nameservers → Custom DNS → the four servers from Step 3. Check:
  `dig +short NS glitchy.games` and `dig +short NS glitchygames.ai` show the `awsdns` servers
  (may take hours).
- [ ] **Step 5: Everything else.** `GLITCHY_SITE_BUDGET_EMAIL=<address> nox -s infra-deploy`.
  Certificate validation waits for Step 4 to propagate. Check: five stacks `CREATE_COMPLETE`;
  the `DeployRoleArn` output.
- [ ] **Step 6: Free plans.** CloudFront console → each distribution → Pricing plan → Free;
  Manage Plan → attach `glitchy.games` zone to distribution 1 and `glitchygames.ai` zone to
  distribution 2. Keep each distribution's own web ACL (from its stack) when asked. Check: both
  distributions show "Free" and the attached zone, and `nox -s infra-diff` then shows no
  distribution changes (the plan adopted the stacks' web ACLs rather than attaching new ones).
  If AWS refuses a feature, note it in the spec and remove it (fallback: pay-as-you-go, about
  $1 / month once the web ACLs are removed).
- [ ] **Step 7: Budget email.** Confirm the subscription email AWS Budgets sends.
- [ ] **Step 8: CircleCI.** In CircleCI, Project Settings > Environment Variables, add
  `SITE_DEPLOY_ROLE_ARN` = the `DeployRoleArn` output (never in `.circleci/config.yml`: it names
  the AWS account). The owner commits and merges the branch. Check: the `deploy-site` job is
  green on `main`.
- [ ] **Step 9: Verify from outside.**
  - `curl -sI https://play.glitchy.games/` → `200`, `content-type: text/html; charset=utf-8`,
    `strict-transport-security` present, no `cross-origin-embedder-policy`.
  - `curl -sI https://glitchy.games/x?y=1`, `https://www.glitchy.games/`,
    `https://glitchygames.ai/x?y=1`, `https://www.glitchygames.ai/` → `301` with `location:
    https://play.glitchy.games/x?y=1` (or `/`).
  - `curl -sI http://play.glitchy.games/` → `301` to `https://`.
  - The page shows the mockup in a browser.
- [ ] **Step 10: Docs.** Update the spec's Status to "Built (date)", the `Website` section of
  `plans/future-work.md` if anything new came up, and `CLAUDE.md` with a short "Website
  (`infra/`)" section naming the nox sessions and the spec. The docs' "Play in the Browser" link
  stays on GitHub Pages (the games aren't on `play.glitchy.games` yet).
- [ ] **Step 11: Checkpoint** for the owner.
