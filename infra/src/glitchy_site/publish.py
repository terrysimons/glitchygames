"""Publish a directory to the site: upload every file, delete what is gone, invalidate the cache.

``nox -s site-publish`` runs it (CircleCI's ``deploy-site`` job, or the owner's Mac). The bucket
and distribution come from the site stack's outputs (``SiteBucketName``, ``SiteDistributionId``),
so nothing names them by hand. Uploads come before deletions, so a visitor never meets a missing
page mid-deploy. A source that is missing, not a directory, or without ``index.html`` is refused
before any AWS call: publishing it would empty the site.

Usage:
    python -m glitchy_site.publish --source src/website
    python -m glitchy_site.publish --source src/website --dry-run
"""

from __future__ import annotations

import argparse
import dataclasses
import mimetypes
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import boto3

from glitchy_site.settings import REGION, SITE_STACK_NAME

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from botocore.client import BaseClient

# Explicit types for what the site serves (the browser games' bundles included): mimetypes'
# answers vary by platform, and a browser runs WebAssembly only from application/wasm
CONTENT_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript',
    '.mjs': 'text/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.wasm': 'application/wasm',
    '.png': 'image/png',
    '.zip': 'application/zip',
    '.whl': 'application/zip',
    '.toml': 'text/plain; charset=utf-8',
}
DEFAULT_CONTENT_TYPE = 'application/octet-stream'

# Pages show a deploy within a minute; other files may be cached a day (every deploy also
# invalidates the whole distribution)
HTML_CACHE_CONTROL = 'public, max-age=60'
ASSET_CACHE_CONTROL = 'public, max-age=86400'

INVALIDATION_PATHS = ['/*']
DELETE_BATCH_SIZE = 1000
"""S3's most keys per DeleteObjects request."""


class PublishRefusedError(ValueError):
    """The source can't be published: publishing it would empty or break the site."""


@dataclasses.dataclass(frozen=True, kw_only=True)
class Upload:
    """One file to upload.

    Attributes:
        local_path: The file.
        key: Its key in the bucket (its POSIX path relative to the source).
        content_type: Its Content-Type.
        cache_control: Its Cache-Control.

    """

    local_path: Path
    key: str
    content_type: str
    cache_control: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class PublishPlan:
    """What a publish does, uploads before deletions.

    Attributes:
        uploads: Every file of the source, by key.
        deletions: The bucket's keys with no file in the source, sorted.

    """

    uploads: tuple[Upload, ...]
    deletions: tuple[str, ...]


@dataclasses.dataclass(frozen=True, kw_only=True)
class SiteTarget:
    """Where the site is published.

    Attributes:
        bucket_name: The site's bucket.
        distribution_id: The distribution to invalidate.

    """

    bucket_name: str
    distribution_id: str


def content_type_for(*, path: Path) -> str:
    """Return the Content-Type a file is served with.

    Args:
        path: The file (only its suffix is read).

    Returns:
        ``CONTENT_TYPES``'s answer, else mimetypes', else ``application/octet-stream``.

    """
    suffix = path.suffix.lower()
    if suffix in CONTENT_TYPES:
        return CONTENT_TYPES[suffix]
    guessed_type, _ = mimetypes.guess_type(path.name)
    return guessed_type or DEFAULT_CONTENT_TYPE


def cache_control_for(*, key: str) -> str:
    """Return the Cache-Control a key is served with: brief for pages, a day for the rest.

    Args:
        key: The bucket key.

    Returns:
        The header's value.

    """
    return HTML_CACHE_CONTROL if key.endswith('.html') else ASSET_CACHE_CONTROL


def _refuse_unpublishable(*, source_directory: Path) -> None:
    """Refuse a source whose publishing would empty or break the site.

    Args:
        source_directory: The directory to publish.

    Raises:
        PublishRefusedError: It is missing, not a directory, or has no ``index.html``.

    """
    if not source_directory.is_dir():
        message = f'{source_directory} is not a directory: nothing to publish'
        raise PublishRefusedError(message)
    if not (source_directory / 'index.html').is_file():
        message = f'{source_directory} has no index.html: publishing it would break the site'
        raise PublishRefusedError(message)


def plan_publish(*, source_directory: Path, existing_keys: Iterable[str]) -> PublishPlan:
    """Plan a publish: every file uploaded, every key with no file deleted.

    Dotfiles and anything under a dot-directory (``.DS_Store``) are not part of the site: they
    are never uploaded, and a bucket key for one is deleted. A source that can't be published
    raises ``PublishRefusedError`` (``_refuse_unpublishable``).

    Args:
        source_directory: The directory to publish.
        existing_keys: The bucket's keys now.

    Returns:
        The plan, uploads sorted by key.

    """
    _refuse_unpublishable(source_directory=source_directory)
    uploads = []
    for path in sorted(source_directory.rglob('*')):
        relative_path = path.relative_to(source_directory)
        if not path.is_file() or any(part.startswith('.') for part in relative_path.parts):
            continue
        key = relative_path.as_posix()
        uploads.append(
            Upload(
                local_path=path,
                key=key,
                content_type=content_type_for(path=path),
                cache_control=cache_control_for(key=key),
            )
        )
    uploads.sort(key=lambda upload: upload.key)
    uploaded_keys = {upload.key for upload in uploads}
    deletions = sorted(set(existing_keys) - uploaded_keys)
    return PublishPlan(uploads=tuple(uploads), deletions=tuple(deletions))


def site_target(*, cloudformation_client: BaseClient, stack_name: str) -> SiteTarget:
    """Read the site's bucket and distribution from its stack's outputs.

    Args:
        cloudformation_client: A boto3 CloudFormation client.
        stack_name: The site stack (``GlitchyGamesSite``).

    Returns:
        The target.

    """
    response = cloudformation_client.describe_stacks(StackName=stack_name)
    outputs = {
        output['OutputKey']: output['OutputValue']
        for output in response['Stacks'][0].get('Outputs', [])
    }
    return SiteTarget(
        bucket_name=outputs['SiteBucketName'], distribution_id=outputs['SiteDistributionId']
    )


def _bucket_keys(*, s3_client: BaseClient, bucket_name: str) -> list[str]:
    """Return every key in the bucket.

    Args:
        s3_client: A boto3 S3 client.
        bucket_name: The bucket.

    Returns:
        The keys.

    """
    keys = []
    for page in s3_client.get_paginator('list_objects_v2').paginate(Bucket=bucket_name):
        keys.extend(entry['Key'] for entry in page.get('Contents', []))
    return keys


def publish(
    *,
    source_directory: Path,
    s3_client: BaseClient,
    cloudformation_client: BaseClient,
    cloudfront_client: BaseClient,
    stack_name: str = SITE_STACK_NAME,
) -> PublishPlan:
    """Publish a directory: upload every file, delete stale keys, invalidate the distribution.

    The source is checked before any AWS call (``plan_publish``'s refusal is raised first, so a
    wrong source never empties the bucket).

    Args:
        source_directory: The directory to publish.
        s3_client: A boto3 S3 client.
        cloudformation_client: A boto3 CloudFormation client.
        cloudfront_client: A boto3 CloudFront client.
        stack_name: The site stack, whose outputs name the bucket and distribution.

    Returns:
        The plan that was carried out.

    """
    _refuse_unpublishable(source_directory=source_directory)
    target = site_target(cloudformation_client=cloudformation_client, stack_name=stack_name)
    plan = plan_publish(
        source_directory=source_directory,
        existing_keys=_bucket_keys(s3_client=s3_client, bucket_name=target.bucket_name),
    )
    for upload in plan.uploads:
        s3_client.put_object(
            Bucket=target.bucket_name,
            Key=upload.key,
            Body=upload.local_path.read_bytes(),
            ContentType=upload.content_type,
            CacheControl=upload.cache_control,
        )
    for start in range(0, len(plan.deletions), DELETE_BATCH_SIZE):
        batch = plan.deletions[start : start + DELETE_BATCH_SIZE]
        s3_client.delete_objects(
            Bucket=target.bucket_name,
            Delete={'Objects': [{'Key': key} for key in batch], 'Quiet': True},
        )
    cloudfront_client.create_invalidation(
        DistributionId=target.distribution_id,
        InvalidationBatch={
            'Paths': {'Quantity': len(INVALIDATION_PATHS), 'Items': INVALIDATION_PATHS},
            # Unique per request: CloudFront treats a repeated reference as the same request
            'CallerReference': uuid.uuid4().hex,
        },
    )
    return plan


def _print_plan(*, plan: PublishPlan) -> None:
    """Print each upload and deletion, one per line.

    Args:
        plan: The plan.

    """
    for upload in plan.uploads:
        sys.stdout.write(f'upload {upload.key} ({upload.content_type}, {upload.cache_control})\n')
    for key in plan.deletions:
        sys.stdout.write(f'delete {key}\n')


def main(argv: Sequence[str] | None = None) -> int:
    """Publish ``--source`` to the site, or print the plan with ``--dry-run``.

    Credentials come from boto3's usual chain: CircleCI's web identity token
    (``AWS_ROLE_ARN``, ``AWS_WEB_IDENTITY_TOKEN_FILE``) or the owner's profile.

    Args:
        argv: The arguments (default: ``sys.argv[1:]``).

    Returns:
        0 when published (or planned), 1 when the source is refused.

    """
    parser = argparse.ArgumentParser(prog='python -m glitchy_site.publish', description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='The directory to publish')
    parser.add_argument('--stack', default=SITE_STACK_NAME, help='The site stack')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what an empty bucket would get; no credentials, no changes',
    )
    arguments = parser.parse_args(argv)
    try:
        if arguments.dry_run:
            plan = plan_publish(source_directory=arguments.source, existing_keys=[])
        else:
            session = boto3.Session(region_name=REGION)
            plan = publish(
                source_directory=arguments.source,
                s3_client=session.client('s3'),
                cloudformation_client=session.client('cloudformation'),
                cloudfront_client=session.client('cloudfront'),
                stack_name=arguments.stack,
            )
    except PublishRefusedError as error:
        sys.stderr.write(f'Refused: {error}\n')
        return 1
    _print_plan(plan=plan)
    return 0


if __name__ == '__main__':
    sys.exit(main())
