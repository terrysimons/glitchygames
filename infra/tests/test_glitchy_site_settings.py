"""The site's settings come from the CDK context, and a missing one stops the build by name."""

from __future__ import annotations

import aws_cdk
import pytest

from glitchy_site.settings import MissingSettingError, SiteSettings, site_settings_from_context

COMPLETE_CONTEXT = {
    'budget_alert_email': 'owner@example.com',
    'circleci_organization_id': 'organization-id',
    'circleci_project_id': 'project-id',
}


def test_settings_come_from_the_context():
    """Each setting is the context value of its key; the budget limit defaults to $10."""
    app = aws_cdk.App(context=COMPLETE_CONTEXT)

    settings = site_settings_from_context(node=app.node)

    assert settings == SiteSettings(
        budget_alert_email='owner@example.com',
        circleci_organization_id='organization-id',
        circleci_project_id='project-id',
    )
    assert settings.budget_limit_usd == 10


@pytest.mark.parametrize(
    'missing_key', ['budget_alert_email', 'circleci_organization_id', 'circleci_project_id']
)
@pytest.mark.parametrize('missing_value', [None, ''])
def test_a_missing_or_empty_setting_is_refused_by_name(missing_key, missing_value):
    """An absent or empty setting raises, naming its key, instead of building without it."""
    context = dict(COMPLETE_CONTEXT)
    if missing_value is None:
        del context[missing_key]
    else:
        context[missing_key] = missing_value

    with pytest.raises(MissingSettingError, match=missing_key):
        site_settings_from_context(node=aws_cdk.App(context=context).node)


def test_an_existing_circleci_provider_is_optional():
    """Without an existing provider's ARN the stack creates one; with it, the ARN is kept."""
    arn = 'arn:aws:iam::123456789012:oidc-provider/oidc.circleci.com/org/organization-id'

    without = site_settings_from_context(node=aws_cdk.App(context=COMPLETE_CONTEXT).node)
    with_arn = site_settings_from_context(
        node=aws_cdk.App(context={**COMPLETE_CONTEXT, 'circleci_oidc_provider_arn': arn}).node
    )

    assert without.circleci_oidc_provider_arn is None
    assert with_arn.circleci_oidc_provider_arn == arn


def test_the_budget_setting_names_the_environment_variable():
    """The budget email is passed from GLITCHY_SITE_BUDGET_EMAIL, so the refusal names it."""
    context = {key: value for key, value in COMPLETE_CONTEXT.items() if key != 'budget_alert_email'}

    with pytest.raises(MissingSettingError, match='GLITCHY_SITE_BUDGET_EMAIL'):
        site_settings_from_context(node=aws_cdk.App(context=context).node)
