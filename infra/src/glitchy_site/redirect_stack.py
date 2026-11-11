"""glitchygames.ai and www.glitchygames.ai, redirecting to play.glitchy.games.

Distribution 2 of the spec (Architecture): a second apex domain needs its own distribution (a
Free flat-rate plan covers one apex). Its redirect function answers every request with a 301, so
its origin is never reached.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aws_cdk
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as cloudfront_origins

from glitchy_site.hosting import (
    add_alias_records,
    certificate_for,
    redirect_function_association,
    web_acl_for,
)
from glitchy_site.settings import CANONICAL_HOST, GLITCHYGAMES_AI_HOSTS

if TYPE_CHECKING:
    import constructs
    from aws_cdk import aws_route53 as route53


class GlitchygamesAiRedirectStack(aws_cdk.Stack):
    """The glitchygames.ai certificate, redirect distribution and DNS records."""

    def __init__(
        self,
        scope: constructs.Construct,
        construct_id: str,
        *,
        zone: route53.IHostedZone,
        **kwargs: Any,
    ) -> None:
        """Build the redirect.

        Args:
            scope: The app.
            construct_id: The stack's name.
            zone: The glitchygames.ai zone.
            **kwargs: Passed to ``aws_cdk.Stack`` (its ``env``).

        """
        super().__init__(scope, construct_id, **kwargs)
        distribution = cloudfront.Distribution(
            self,
            'Distribution',
            default_behavior=cloudfront.BehaviorOptions(
                # Never reached: the viewer-request function answers every request
                origin=cloudfront_origins.HttpOrigin(CANONICAL_HOST),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                function_associations=[redirect_function_association(self)],
            ),
            domain_names=list(GLITCHYGAMES_AI_HOSTS),
            certificate=certificate_for(self, zone=zone, host_names=GLITCHYGAMES_AI_HOSTS),
            http_version=cloudfront.HttpVersion.HTTP2_AND_3,
            web_acl_id=web_acl_for(self, name='glitchygames-ai-redirect').attr_arn,
            comment='glitchygames.ai: 301 to https://play.glitchy.games',
        )
        add_alias_records(
            self, zone=zone, host_names=GLITCHYGAMES_AI_HOSTS, distribution=distribution
        )
