"""The site's fixed names and the settings it reads from the CDK context.

The names are the spec's (docs/specs/2026-10-27-glitchy-games-website-design.md, Address map).
The settings are values that differ per owner and must not be written in this public repository
(the budget email), or that the owner fills in once (the CircleCI IDs, in ``infra/cdk.json``).
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import constructs

REGION = 'us-east-1'
"""Every stack's region: CloudFront's certificates must live in us-east-1."""

CANONICAL_HOST = 'play.glitchy.games'
"""The one address the site is served at; every other host redirects here."""

GLITCHY_GAMES_APEX = 'glitchy.games'
GLITCHYGAMES_AI_APEX = 'glitchygames.ai'

SITE_HOSTS = ('play.glitchy.games', 'glitchy.games', 'www.glitchy.games')
"""The hosts of the site's distribution (one apex: one CloudFront Free plan)."""

GLITCHYGAMES_AI_HOSTS = ('glitchygames.ai', 'www.glitchygames.ai')
"""The hosts of the redirect distribution (the second apex: a second Free plan)."""

SITE_STACK_NAME = 'GlitchyGamesSite'
DEPLOY_ROLE_NAME = 'glitchy-games-site-deploy'

BUDGET_EMAIL_CONTEXT_KEY = 'budget_alert_email'
ORGANIZATION_CONTEXT_KEY = 'circleci_organization_id'
PROJECT_CONTEXT_KEY = 'circleci_project_id'
OIDC_PROVIDER_CONTEXT_KEY = 'circleci_oidc_provider_arn'
"""Optional: an existing CircleCI provider's ARN (IAM allows one provider per URL per account)."""

REPOSITORY_ORIGIN = 'github.com/terrysimons/glitchygames'
"""The repository as CircleCI's OIDC tokens name it (``vcs-origin``: its URL without https://)."""

DEPLOY_REF = 'refs/heads/main'
"""The only ref whose jobs may deploy (the token's ``vcs-ref``)."""

BUDGET_EMAIL_ENVIRONMENT_VARIABLE = 'GLITCHY_SITE_BUDGET_EMAIL'
"""Where the nox sessions read the budget email from, to pass it as context."""


class MissingSettingError(ValueError):
    """A setting the stacks need is absent or empty in the CDK context."""


@dataclasses.dataclass(frozen=True, kw_only=True)
class SiteSettings:
    """The per-owner values the stacks are built from.

    Attributes:
        budget_alert_email: Where AWS Budgets sends its alerts.
        circleci_organization_id: The CircleCI organization whose OIDC tokens the deploy role
            trusts.
        circleci_project_id: The CircleCI project (this repository) whose jobs may deploy.
        budget_limit_usd: The monthly budget, in US dollars.
        circleci_oidc_provider_arn: An existing CircleCI OIDC provider to trust, or None to
            create one.

    """

    budget_alert_email: str
    circleci_organization_id: str
    circleci_project_id: str
    budget_limit_usd: int = 10
    circleci_oidc_provider_arn: str | None = None


def _required_context_value(*, node: constructs.Node, key: str, how_to_set: str) -> str:
    """Return a context value, refusing an absent or empty one.

    Args:
        node: The construct node whose context is read (the app's).
        key: The context key.
        how_to_set: Where the value comes from, for the refusal's message.

    Returns:
        The value.

    Raises:
        MissingSettingError: The value is absent or empty.

    """
    value = node.try_get_context(key)
    if not value:
        message = f'The CDK context has no {key!r}: {how_to_set}'
        raise MissingSettingError(message)
    return str(value)


def site_settings_from_context(*, node: constructs.Node) -> SiteSettings:
    """Read the site's settings from the CDK context.

    A setting that is absent or empty raises ``MissingSettingError`` (from
    ``_required_context_value``), its message naming the key and how to set it.

    Args:
        node: The construct node whose context is read (the app's).

    Returns:
        The settings.

    """
    return SiteSettings(
        budget_alert_email=_required_context_value(
            node=node,
            key=BUDGET_EMAIL_CONTEXT_KEY,
            how_to_set=(
                f'set {BUDGET_EMAIL_ENVIRONMENT_VARIABLE} (the nox sessions pass it as '
                f'-c {BUDGET_EMAIL_CONTEXT_KEY}=...)'
            ),
        ),
        circleci_organization_id=_required_context_value(
            node=node,
            key=ORGANIZATION_CONTEXT_KEY,
            how_to_set='fill it in infra/cdk.json (CircleCI: Organization Settings)',
        ),
        circleci_project_id=_required_context_value(
            node=node,
            key=PROJECT_CONTEXT_KEY,
            how_to_set='fill it in infra/cdk.json (CircleCI: Project Settings)',
        ),
        circleci_oidc_provider_arn=node.try_get_context(OIDC_PROVIDER_CONTEXT_KEY) or None,
    )
