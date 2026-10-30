"""The CDK stacks synthesize the spec's AWS setup.

Spec: docs/specs/2026-10-27-glitchy-games-website-design.md.
"""

from __future__ import annotations

import dataclasses

import aws_cdk
import pytest
from aws_cdk.assertions import Template
from cdk_context import project_context

from glitchy_site.app import build_app
from glitchy_site.dns_zones_stack import DnsZonesStack
from glitchy_site.redirect_function import REDIRECT_FUNCTION_PATH
from glitchy_site.redirect_stack import GlitchygamesAiRedirectStack
from glitchy_site.settings import MissingSettingError
from glitchy_site.site_stack import SiteStack

TEST_ENVIRONMENT = aws_cdk.Environment(account='123456789012', region='us-east-1')


def zones_stack(*, app: aws_cdk.App) -> DnsZonesStack:
    """Return the DNS zones stack, built in the test account."""
    return DnsZonesStack(app, 'GlitchyGamesDnsZones', env=TEST_ENVIRONMENT)


def test_the_zones_stack_holds_both_zones_and_names_their_servers():
    """Both domains get a zone, each zone's name servers are an output, and no other records.

    The Namecheap email-forwarding records (MX, SPF) are deliberately not copied: the owner
    uses no email at these domains yet (spec, Risks).
    """
    template = Template.from_stack(zones_stack(app=aws_cdk.App(context=project_context())))

    template.resource_count_is('AWS::Route53::HostedZone', 2)
    template.has_resource_properties('AWS::Route53::HostedZone', {'Name': 'glitchy.games.'})
    template.has_resource_properties('AWS::Route53::HostedZone', {'Name': 'glitchygames.ai.'})
    template.resource_count_is('AWS::Route53::RecordSet', 0)
    assert template.find_outputs('GlitchyGamesNameServers')
    assert template.find_outputs('GlitchygamesAiNameServers')


def test_the_zones_outlive_their_stack():
    """Deleting the stack keeps the zones: their name servers are set at Namecheap."""
    template = Template.from_stack(zones_stack(app=aws_cdk.App(context=project_context())))

    zones = template.find_resources('AWS::Route53::HostedZone')
    assert {zone['DeletionPolicy'] for zone in zones.values()} == {'Retain'}


SITE_HOST_NAMES = ['play.glitchy.games', 'glitchy.games', 'www.glitchy.games']
GLITCHYGAMES_AI_HOST_NAMES = ['glitchygames.ai', 'www.glitchygames.ai']
# AWS's managed policies, by their fixed ids
SECURITY_HEADERS_POLICY_ID = '67f7725c-6f97-4210-82d7-5512b31e9d03'
CACHING_OPTIMIZED_POLICY_ID = '658327ea-f89d-4fab-a63d-7e88639e58f6'


@dataclasses.dataclass(frozen=True, kw_only=True)
class SiteTemplates:
    """The synthesized templates of the site and the glitchygames.ai redirect."""

    site: Template
    redirect: Template


def site_templates() -> SiteTemplates:
    """Build the zones, site and redirect stacks in one app and return the two templates."""
    app = aws_cdk.App(context=project_context())
    zones = zones_stack(app=app)
    site = SiteStack(app, 'GlitchyGamesSite', zone=zones.glitchy_games_zone, env=TEST_ENVIRONMENT)
    redirect = GlitchygamesAiRedirectStack(
        app, 'GlitchyGamesAiRedirect', zone=zones.glitchygames_ai_zone, env=TEST_ENVIRONMENT
    )
    return SiteTemplates(site=Template.from_stack(site), redirect=Template.from_stack(redirect))


def only_resource(*, template: Template, resource_type: str) -> dict:
    """Return the template's one resource of a type, failing when there are none or several."""
    resources = template.find_resources(resource_type)
    assert len(resources) == 1, f'{len(resources)} {resource_type} resources'
    return next(iter(resources.values()))


def distribution_config(*, template: Template) -> dict:
    """Return the template's one distribution's configuration."""
    distribution = only_resource(template=template, resource_type='AWS::CloudFront::Distribution')
    return distribution['Properties']['DistributionConfig']


def test_the_site_bucket_is_private_and_versioned():
    """Only CloudFront reads the bucket; old versions of overwritten files go after 30 days."""
    bucket = only_resource(template=site_templates().site, resource_type='AWS::S3::Bucket')

    properties = bucket['Properties']
    assert properties['PublicAccessBlockConfiguration'] == {
        'BlockPublicAcls': True,
        'BlockPublicPolicy': True,
        'IgnorePublicAcls': True,
        'RestrictPublicBuckets': True,
    }
    assert properties['VersioningConfiguration'] == {'Status': 'Enabled'}
    assert {'NoncurrentVersionExpiration': {'NoncurrentDays': 30}, 'Status': 'Enabled'} in (
        properties['LifecycleConfiguration']['Rules']
    )
    assert bucket['DeletionPolicy'] == 'Retain'


def test_the_site_distribution_serves_the_three_glitchy_games_names():
    """Distribution 1: one apex (one Free plan), HTTPS only, index.html at the root."""
    config = distribution_config(template=site_templates().site)

    assert config['Aliases'] == SITE_HOST_NAMES
    assert config['DefaultCacheBehavior']['ViewerProtocolPolicy'] == 'redirect-to-https'
    assert config['DefaultCacheBehavior']['CachePolicyId'] == CACHING_OPTIMIZED_POLICY_ID
    assert config['DefaultCacheBehavior']['Compress'] is True
    assert config['DefaultRootObject'] == 'index.html'
    assert config['HttpVersion'] == 'http2and3'


def test_the_redirect_distribution_serves_the_glitchygames_ai_names():
    """Distribution 2: the second apex, HTTPS only."""
    config = distribution_config(template=site_templates().redirect)

    assert config['Aliases'] == GLITCHYGAMES_AI_HOST_NAMES
    assert config['DefaultCacheBehavior']['ViewerProtocolPolicy'] == 'redirect-to-https'


def test_the_site_reaches_s3_through_origin_access_control_only():
    """OAC, never an origin access identity (a flat-rate plan refuses OAI); no real-time logs."""
    templates = site_templates()

    templates.site.resource_count_is('AWS::CloudFront::OriginAccessControl', 1)
    for template in (templates.site, templates.redirect):
        template.resource_count_is('AWS::CloudFront::CloudFrontOriginAccessIdentity', 0)
        template.resource_count_is('AWS::CloudFront::RealtimeLogConfig', 0)


def test_each_distribution_has_its_own_function():
    """Each distribution runs the redirect code from its own Function, as a viewer request.

    A function already associated with another distribution can't be used on a flat-rate plan.
    """
    templates = site_templates()

    for template in (templates.site, templates.redirect):
        functions = template.find_resources('AWS::CloudFront::Function')
        assert len(functions) == 1
        ((function_id, function),) = functions.items()
        assert function['Properties']['FunctionConfig']['Runtime'] == 'cloudfront-js-2.0'
        assert function['Properties']['FunctionCode'] == REDIRECT_FUNCTION_PATH.read_text(
            encoding='utf-8'
        )
        associations = distribution_config(template=template)['DefaultCacheBehavior'][
            'FunctionAssociations'
        ]
        assert associations == [
            {
                'EventType': 'viewer-request',
                'FunctionARN': {'Fn::GetAtt': [function_id, 'FunctionARN']},
            }
        ]


def test_the_site_sends_no_cross_origin_isolation_headers():
    """AWS's managed security headers (HSTS among them); no custom policy, so no COEP.

    COEP would block PyScript, which loads from pyscript.net (spec, CloudFront (site)).
    """
    templates = site_templates()

    config = distribution_config(template=templates.site)
    assert config['DefaultCacheBehavior']['ResponseHeadersPolicyId'] == SECURITY_HEADERS_POLICY_ID
    for template in (templates.site, templates.redirect):
        template.resource_count_is('AWS::CloudFront::ResponseHeadersPolicy', 0)


def test_every_host_has_ipv4_and_ipv6_alias_records():
    """A and AAAA alias records for each host, in its own domain's zone."""
    templates = site_templates()

    for template, host_names in (
        (templates.site, SITE_HOST_NAMES),
        (templates.redirect, GLITCHYGAMES_AI_HOST_NAMES),
    ):
        records = template.find_resources('AWS::Route53::RecordSet')
        named = sorted(
            (record['Properties']['Name'], record['Properties']['Type'])
            for record in records.values()
        )
        assert named == sorted(
            (f'{host_name}.', record_type)
            for host_name in host_names
            for record_type in ('A', 'AAAA')
        )
        for record in records.values():
            assert 'AliasTarget' in record['Properties']


def test_the_certificates_cover_exactly_their_hosts():
    """One DNS-validated certificate per distribution, naming exactly that distribution's hosts."""
    templates = site_templates()

    for template, host_names in (
        (templates.site, SITE_HOST_NAMES),
        (templates.redirect, GLITCHYGAMES_AI_HOST_NAMES),
    ):
        certificate = only_resource(
            template=template, resource_type='AWS::CertificateManager::Certificate'
        )
        properties = certificate['Properties']
        assert [properties['DomainName'], *properties.get('SubjectAlternativeNames', [])] == (
            host_names
        )
        assert properties['ValidationMethod'] == 'DNS'


def test_the_site_stack_names_its_bucket_and_distribution():
    """The publisher finds the bucket and distribution through these outputs."""
    template = site_templates().site

    assert template.find_outputs('SiteBucketName')
    assert template.find_outputs('SiteDistributionId')


COMPLETE_CONTEXT = {
    'budget_alert_email': 'owner@example.com',
    'circleci_organization_id': 'organization-id',
    'circleci_project_id': 'project-id',
}
CIRCLECI_ISSUER = 'oidc.circleci.com/org/organization-id'


def built_app(*, context: dict[str, str]) -> aws_cdk.App:
    """Return an app with every stack built for the test account."""
    app = aws_cdk.App(context=project_context(**context))
    build_app(app=app, account='123456789012')
    return app


def stack_template(*, app: aws_cdk.App, stack_name: str) -> Template:
    """Return one of the app's stacks' template."""
    stack = app.node.find_child(stack_name)
    assert isinstance(stack, aws_cdk.Stack)
    return Template.from_stack(stack)


def test_the_app_builds_five_stacks_in_us_east_1():
    """Zones, site, glitchygames.ai redirect, deploy role and budget, all in us-east-1."""
    assembly = built_app(context=COMPLETE_CONTEXT).synth()

    stacks = {stack.stack_name: stack.environment.region for stack in assembly.stacks}
    assert stacks == {
        'GlitchyGamesDnsZones': 'us-east-1',
        'GlitchyGamesSite': 'us-east-1',
        'GlitchyGamesAiRedirect': 'us-east-1',
        'GlitchyGamesSiteDeployRole': 'us-east-1',
        'GlitchyGamesBudget': 'us-east-1',
    }


def test_the_app_refuses_to_build_without_the_budget_email():
    """No budget without its subscriber: the build stops naming GLITCHY_SITE_BUDGET_EMAIL."""
    context = {key: value for key, value in COMPLETE_CONTEXT.items() if key != 'budget_alert_email'}

    with pytest.raises(MissingSettingError, match='GLITCHY_SITE_BUDGET_EMAIL'):
        built_app(context=context)


def test_circleci_is_an_identity_provider_for_this_organization():
    """AWS trusts tokens CircleCI issues for the organization, with the organization as audience."""
    template = stack_template(
        app=built_app(context=COMPLETE_CONTEXT), stack_name='GlitchyGamesSiteDeployRole'
    )

    provider = only_resource(template=template, resource_type='AWS::IAM::OIDCProvider')
    assert provider['Properties']['Url'] == f'https://{CIRCLECI_ISSUER}'
    assert provider['Properties']['ClientIdList'] == ['organization-id']


def test_the_deploy_role_trusts_only_this_projects_main_branch():
    """Only jobs of this project, building main of this repository, may assume the role.

    A V2 token's ``sub`` names the repository and ref
    (``org/<org>/project/<project>/user/<user>/vcs-origin/<origin>/vcs-ref/<ref>``), so IAM
    itself refuses another branch's job, whatever its configuration says.
    """
    template = stack_template(
        app=built_app(context=COMPLETE_CONTEXT), stack_name='GlitchyGamesSiteDeployRole'
    )

    role = only_resource(template=template, resource_type='AWS::IAM::Role')
    assert role['Properties']['RoleName'] == 'glitchy-games-site-deploy'
    (statement,) = role['Properties']['AssumeRolePolicyDocument']['Statement']
    assert statement['Action'] == 'sts:AssumeRoleWithWebIdentity'
    assert statement['Condition'] == {
        'StringEquals': {f'{CIRCLECI_ISSUER}:aud': 'organization-id'},
        'StringLike': {
            f'{CIRCLECI_ISSUER}:sub': (
                'org/organization-id/project/project-id/user/*'
                '/vcs-origin/github.com/terrysimons/glitchygames/vcs-ref/refs/heads/main'
            )
        },
    }


def test_an_existing_circleci_provider_is_reused():
    """An account that already trusts CircleCI keeps its provider: IAM allows one per URL."""
    existing_arn = 'arn:aws:iam::123456789012:oidc-provider/oidc.circleci.com/org/organization-id'
    template = stack_template(
        app=built_app(context={**COMPLETE_CONTEXT, 'circleci_oidc_provider_arn': existing_arn}),
        stack_name='GlitchyGamesSiteDeployRole',
    )

    template.resource_count_is('AWS::IAM::OIDCProvider', 0)
    role = only_resource(template=template, resource_type='AWS::IAM::Role')
    (statement,) = role['Properties']['AssumeRolePolicyDocument']['Statement']
    assert statement['Principal'] == {'Federated': existing_arn}


def test_each_distribution_has_its_own_web_acl():
    """A flat-rate plan needs a WAF web ACL on its distribution, one no other distribution uses.

    It is in the stacks, so a later deploy never detaches the one the plan requires. It allows
    by default and stays within the Free plan's 5 rules.
    """
    templates = site_templates()

    for template in (templates.site, templates.redirect):
        web_acls = template.find_resources('AWS::WAFv2::WebACL')
        assert len(web_acls) == 1
        ((web_acl_id, web_acl),) = web_acls.items()
        properties = web_acl['Properties']
        assert properties['Scope'] == 'CLOUDFRONT'
        assert properties['DefaultAction'] == {'Allow': {}}
        assert len(properties['Rules']) <= 5
        assert distribution_config(template=template)['WebACLId'] == {
            'Fn::GetAtt': [web_acl_id, 'Arn']
        }


def test_the_deploy_role_may_only_publish_the_site():
    """List and write the site bucket, invalidate its distribution, read its stack: nothing else."""
    template = stack_template(
        app=built_app(context=COMPLETE_CONTEXT), stack_name='GlitchyGamesSiteDeployRole'
    )

    policy = only_resource(template=template, resource_type='AWS::IAM::Policy')
    statements = policy['Properties']['PolicyDocument']['Statement']
    actions = sorted(
        action
        for statement in statements
        for action in (
            statement['Action'] if isinstance(statement['Action'], list) else [statement['Action']]
        )
    )
    assert actions == [
        'cloudformation:DescribeStacks',
        'cloudfront:CreateInvalidation',
        's3:DeleteObject',
        's3:ListBucket',
        's3:PutObject',
    ]
    for statement in statements:
        assert statement['Effect'] == 'Allow'
        assert statement['Resource'] != '*'
    assert template.find_outputs('DeployRoleArn')


def test_the_budget_emails_the_owner_at_ten_dollars():
    """$10 a month, an email when the actual or the forecast spend passes it."""
    template = stack_template(
        app=built_app(context=COMPLETE_CONTEXT), stack_name='GlitchyGamesBudget'
    )

    budget = only_resource(template=template, resource_type='AWS::Budgets::Budget')
    properties = budget['Properties']
    assert properties['Budget']['BudgetType'] == 'COST'
    assert properties['Budget']['TimeUnit'] == 'MONTHLY'
    assert properties['Budget']['BudgetLimit'] == {'Amount': 10, 'Unit': 'USD'}
    notifications = sorted(
        (
            entry['Notification']['NotificationType'],
            entry['Notification']['ComparisonOperator'],
            entry['Notification']['Threshold'],
            entry['Notification']['ThresholdType'],
            tuple(
                (subscriber['SubscriptionType'], subscriber['Address'])
                for subscriber in entry['Subscribers']
            ),
        )
        for entry in properties['NotificationsWithSubscribers']
    )
    assert notifications == [
        ('ACTUAL', 'GREATER_THAN', 100, 'PERCENTAGE', (('EMAIL', 'owner@example.com'),)),
        ('FORECASTED', 'GREATER_THAN', 100, 'PERCENTAGE', (('EMAIL', 'owner@example.com'),)),
    ]
