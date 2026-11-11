"""The parts both distributions are built from: certificate, function, web ACL, alias records.

Each stack (the site's, glitchygames.ai's) calls these for its own hosts and zone, so each
distribution has its own certificate, Function and web ACL, as a flat-rate plan needs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aws_cdk import aws_certificatemanager as certificatemanager
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_route53 as route53
from aws_cdk import aws_route53_targets as route53_targets
from aws_cdk import aws_wafv2 as wafv2

from glitchy_site.redirect_function import redirect_function_code

if TYPE_CHECKING:
    from collections.abc import Sequence

    import constructs


def certificate_for(
    scope: constructs.Construct, *, zone: route53.IHostedZone, host_names: Sequence[str]
) -> certificatemanager.Certificate:
    """Return a DNS-validated certificate naming exactly these hosts, the first as its domain.

    Args:
        scope: The stack.
        zone: The zone the validation records go in.
        host_names: The hosts; the first is the certificate's domain name.

    Returns:
        The certificate.

    """
    return certificatemanager.Certificate(
        scope,
        'Certificate',
        domain_name=host_names[0],
        subject_alternative_names=list(host_names[1:]) or None,
        validation=certificatemanager.CertificateValidation.from_dns(zone),
    )


def redirect_function_association(scope: constructs.Construct) -> cloudfront.FunctionAssociation:
    """Return a viewer-request association of a new Function running the redirect code.

    Args:
        scope: The stack.

    Returns:
        The association, for the distribution's default behaviour.

    """
    function = cloudfront.Function(
        scope,
        'RedirectFunction',
        code=redirect_function_code(),
        runtime=cloudfront.FunctionRuntime.JS_2_0,
        comment='Redirect to https://play.glitchy.games; directory URLs fetch index.html',
    )
    return cloudfront.FunctionAssociation(
        function=function, event_type=cloudfront.FunctionEventType.VIEWER_REQUEST
    )


def web_acl_for(scope: constructs.Construct, *, name: str) -> wafv2.CfnWebACL:
    """Return the distribution's own WAF web ACL: allow by default, block known-bad addresses.

    A flat-rate plan requires a web ACL on its distribution that no other distribution uses, and
    it can't be detached while the plan lasts. Defining it here keeps it in the template, so a
    later deploy never detaches it (the plan's console sign-up would otherwise attach one this
    code doesn't know about). One rule, within the Free plan's 5: Amazon's IP reputation list,
    which only blocks addresses AWS has seen attacking, so no visitor's request is judged by its
    content. On pay-as-you-go pricing (no plan), a web ACL costs $5 a month plus $1 per rule.

    Args:
        scope: The stack.
        name: The web ACL's name (unique in the account's CloudFront scope).

    Returns:
        The web ACL, for the distribution's ``web_acl_id`` (its ``attr_arn``).

    """
    return wafv2.CfnWebACL(
        scope,
        'WebAcl',
        name=name,
        scope='CLOUDFRONT',
        default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
        visibility_config=_visibility(metric_name=name),
        rules=[
            wafv2.CfnWebACL.RuleProperty(
                name='AmazonIpReputationList',
                priority=0,
                statement=wafv2.CfnWebACL.StatementProperty(
                    managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                        vendor_name='AWS', name='AWSManagedRulesAmazonIpReputationList'
                    )
                ),
                override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                visibility_config=_visibility(metric_name=f'{name}-ip-reputation'),
            )
        ],
    )


def _visibility(*, metric_name: str) -> wafv2.CfnWebACL.VisibilityConfigProperty:
    """Return WAF's required visibility settings: sampled requests and metrics on.

    Args:
        metric_name: The CloudWatch metric's name.

    Returns:
        The settings.

    """
    return wafv2.CfnWebACL.VisibilityConfigProperty(
        cloud_watch_metrics_enabled=True,
        metric_name=metric_name,
        sampled_requests_enabled=True,
    )


def add_alias_records(
    scope: constructs.Construct,
    *,
    zone: route53.IHostedZone,
    host_names: Sequence[str],
    distribution: cloudfront.IDistribution,
) -> None:
    """Point each host at the distribution with an A and an AAAA alias record.

    Args:
        scope: The stack.
        zone: The hosts' zone.
        host_names: The hosts.
        distribution: Where they point.

    """
    target = route53.RecordTarget.from_alias(route53_targets.CloudFrontTarget(distribution))
    for host_name in host_names:
        construct_name = ''.join(part.capitalize() for part in host_name.split('.'))
        route53.ARecord(
            scope, f'{construct_name}A', zone=zone, record_name=host_name, target=target
        )
        route53.AaaaRecord(
            scope, f'{construct_name}Aaaa', zone=zone, record_name=host_name, target=target
        )
