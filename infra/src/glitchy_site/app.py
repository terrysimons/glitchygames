"""The CDK app: every stack of the glitchy.games website, in us-east-1.

``infra/cdk.json`` runs ``python -m glitchy_site.app``; the nox sessions ``infra-diff`` and
``infra-deploy`` run the CDK CLI on it. Deploy ``GlitchyGamesDnsZones`` first and point Namecheap
at its name servers: the other stacks' certificates validate through those zones (spec, Manual
steps).
"""

from __future__ import annotations

import os

import aws_cdk

from glitchy_site.budget_stack import BudgetStack
from glitchy_site.deploy_role_stack import CircleCiDeployRoleStack
from glitchy_site.dns_zones_stack import DnsZonesStack
from glitchy_site.redirect_stack import GlitchygamesAiRedirectStack
from glitchy_site.settings import REGION, SITE_STACK_NAME, site_settings_from_context
from glitchy_site.site_stack import SiteStack


def build_app(*, app: aws_cdk.App, account: str) -> None:
    """Add every stack to the app, each in the account and ``REGION``.

    Args:
        app: The app; its context holds the settings (``glitchy_site.settings``).
        account: The AWS account to deploy to.

    """
    settings = site_settings_from_context(node=app.node)
    environment = aws_cdk.Environment(account=account, region=REGION)
    zones = DnsZonesStack(app, 'GlitchyGamesDnsZones', env=environment)
    site = SiteStack(app, SITE_STACK_NAME, zone=zones.glitchy_games_zone, env=environment)
    GlitchygamesAiRedirectStack(
        app, 'GlitchyGamesAiRedirect', zone=zones.glitchygames_ai_zone, env=environment
    )
    CircleCiDeployRoleStack(
        app,
        'GlitchyGamesSiteDeployRole',
        settings=settings,
        bucket=site.bucket,
        distribution=site.distribution,
        env=environment,
    )
    BudgetStack(app, 'GlitchyGamesBudget', settings=settings, env=environment)


def main() -> None:
    """Build the app for the CLI's account (``CDK_DEFAULT_ACCOUNT``) and synthesize it."""
    app = aws_cdk.App()
    build_app(app=app, account=os.environ['CDK_DEFAULT_ACCOUNT'])
    app.synth()


if __name__ == '__main__':
    main()
