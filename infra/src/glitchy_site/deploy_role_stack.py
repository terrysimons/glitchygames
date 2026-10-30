"""The role CircleCI's ``deploy-site`` job assumes to publish the site, with no stored AWS keys.

CircleCI signs a short-lived OIDC token for each job (``$CIRCLE_OIDC_TOKEN_V2``); AWS trusts
CircleCI as an identity provider for this organization, and this role trusts only tokens of this
project building ``main`` of this repository. A V2 token's ``sub`` is
``org/<org>/project/<project>/user/<user>/vcs-origin/<origin>/vcs-ref/<ref>``
(https://circleci.com/docs/guides/permissions-authentication/openid-connect-tokens/), so IAM
itself refuses a job on another branch, whatever that branch's configuration says; the
workflow's ``only: main`` filter (``.circleci/config.yml``, ``deploy-site``) only saves running it.
The role may only do what publishing needs (``glitchy_site.publish``).

IAM allows one provider per URL per account: an account that already trusts CircleCI names its
provider in the context (``circleci_oidc_provider_arn``), and this stack uses it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aws_cdk
from aws_cdk import aws_iam as iam

from glitchy_site.settings import (
    DEPLOY_REF,
    DEPLOY_ROLE_NAME,
    REPOSITORY_ORIGIN,
    SITE_STACK_NAME,
)

if TYPE_CHECKING:
    import constructs
    from aws_cdk import aws_cloudfront as cloudfront
    from aws_cdk import aws_s3 as s3

    from glitchy_site.settings import SiteSettings


class CircleCiDeployRoleStack(aws_cdk.Stack):
    """CircleCI as an identity provider, and the site's deploy role."""

    def __init__(
        self,
        scope: constructs.Construct,
        construct_id: str,
        *,
        settings: SiteSettings,
        bucket: s3.IBucket,
        distribution: cloudfront.IDistribution,
        **kwargs: Any,
    ) -> None:
        """Build the provider and the role.

        Args:
            scope: The app.
            construct_id: The stack's name.
            settings: The CircleCI organization and project IDs.
            bucket: The site's bucket, which the role may list and write.
            distribution: The site's distribution, which the role may invalidate.
            **kwargs: Passed to ``aws_cdk.Stack`` (its ``env``).

        """
        super().__init__(scope, construct_id, **kwargs)
        organization_id = settings.circleci_organization_id
        issuer = f'oidc.circleci.com/org/{organization_id}'
        if settings.circleci_oidc_provider_arn:
            provider_arn = settings.circleci_oidc_provider_arn
        else:
            provider_arn = iam.OidcProviderNative(
                self, 'CircleCiOidcProvider', url=f'https://{issuer}', client_ids=[organization_id]
            ).oidc_provider_arn
        # Any user may have started the job; the project, repository and ref are fixed
        main_branch_jobs = (
            f'org/{organization_id}/project/{settings.circleci_project_id}/user/*'
            f'/vcs-origin/{REPOSITORY_ORIGIN}/vcs-ref/{DEPLOY_REF}'
        )
        role = iam.Role(
            self,
            'DeployRole',
            role_name=DEPLOY_ROLE_NAME,
            description='CircleCI deploy-site on main: publish the glitchy.games site',
            assumed_by=iam.WebIdentityPrincipal(
                provider_arn,
                conditions={
                    'StringEquals': {f'{issuer}:aud': organization_id},
                    'StringLike': {f'{issuer}:sub': main_branch_jobs},
                },
            ),
        )
        role.add_to_policy(
            iam.PolicyStatement(actions=['s3:ListBucket'], resources=[bucket.bucket_arn])
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=['s3:PutObject', 's3:DeleteObject'],
                resources=[bucket.arn_for_objects('*')],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=['cloudfront:CreateInvalidation'],
                resources=[distribution.distribution_arn],
            )
        )
        # The publisher finds the bucket and distribution through the site stack's outputs
        role.add_to_policy(
            iam.PolicyStatement(
                actions=['cloudformation:DescribeStacks'],
                resources=[
                    self.format_arn(
                        service='cloudformation',
                        resource='stack',
                        resource_name=f'{SITE_STACK_NAME}/*',
                    )
                ],
            )
        )
        aws_cdk.CfnOutput(
            self,
            'DeployRoleArn',
            value=role.role_arn,
            description=(
                'CircleCI Project Settings > Environment Variables: SITE_DEPLOY_ROLE_ARN '
                '(names the account: never in the public .circleci/config.yml)'
            ),
        )
