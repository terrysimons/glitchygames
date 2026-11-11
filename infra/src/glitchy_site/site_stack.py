"""The site: a private S3 bucket behind CloudFront at play.glitchy.games.

Distribution 1 of the spec (Architecture): it serves ``SITE_HOSTS``, one apex domain, so one
CloudFront Free flat-rate plan covers it. Its redirect function sends glitchy.games and
www.glitchy.games to play.glitchy.games and gives directory URLs their index.html.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aws_cdk
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as cloudfront_origins
from aws_cdk import aws_s3 as s3

from glitchy_site.hosting import (
    add_alias_records,
    certificate_for,
    redirect_function_association,
    web_acl_for,
)
from glitchy_site.settings import SITE_HOSTS

if TYPE_CHECKING:
    import constructs
    from aws_cdk import aws_route53 as route53

NONCURRENT_VERSION_DAYS = 30
"""How long an overwritten or deleted file's old version is kept, for rolling back a deploy."""


class SiteStack(aws_cdk.Stack):
    """The site's bucket, certificate, distribution and DNS records.

    Attributes:
        bucket: The site's files (written by ``glitchy_site.publish``).
        distribution: The distribution serving them.

    """

    def __init__(
        self,
        scope: constructs.Construct,
        construct_id: str,
        *,
        zone: route53.IHostedZone,
        **kwargs: Any,
    ) -> None:
        """Build the site.

        Args:
            scope: The app.
            construct_id: The stack's name.
            zone: The glitchy.games zone.
            **kwargs: Passed to ``aws_cdk.Stack`` (its ``env``).

        """
        super().__init__(scope, construct_id, **kwargs)
        self.bucket = s3.Bucket(
            self,
            'Bucket',
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    noncurrent_version_expiration=aws_cdk.Duration.days(NONCURRENT_VERSION_DAYS)
                )
            ],
            removal_policy=aws_cdk.RemovalPolicy.RETAIN,
        )
        self.distribution = cloudfront.Distribution(
            self,
            'Distribution',
            default_behavior=cloudfront.BehaviorOptions(
                origin=cloudfront_origins.S3BucketOrigin.with_origin_access_control(self.bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                # gzip and brotli; honours the Cache-Control the publisher sets on each file
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                compress=True,
                # HSTS and the other standard headers; no COOP/COEP, which would block PyScript
                # from pyscript.net (spec, CloudFront (site))
                response_headers_policy=cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS,
                function_associations=[redirect_function_association(self)],
            ),
            domain_names=list(SITE_HOSTS),
            certificate=certificate_for(self, zone=zone, host_names=SITE_HOSTS),
            default_root_object='index.html',
            http_version=cloudfront.HttpVersion.HTTP2_AND_3,
            web_acl_id=web_acl_for(self, name='glitchy-games-site').attr_arn,
            comment='play.glitchy.games (glitchy.games and www redirect here)',
        )
        add_alias_records(self, zone=zone, host_names=SITE_HOSTS, distribution=self.distribution)
        aws_cdk.CfnOutput(self, 'SiteBucketName', value=self.bucket.bucket_name)
        aws_cdk.CfnOutput(self, 'SiteDistributionId', value=self.distribution.distribution_id)
