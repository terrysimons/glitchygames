"""Publishing a directory to the site: what is uploaded, how, what is deleted, and what is refused.

Only the network is replaced (botocore's Stubber answers the AWS calls); files are real
(``tmp_path``) and so is the site in ``src/website``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import boto3
import pytest
from botocore import UNSIGNED
from botocore.config import Config
from botocore.stub import ANY, Stubber

from glitchy_site.publish import (
    PublishRefusedError,
    SiteTarget,
    cache_control_for,
    content_type_for,
    main,
    plan_publish,
    publish,
    site_target,
)

WEBSITE_DIRECTORY = Path(__file__).resolve().parents[2] / 'src' / 'website'
STACK_NAME = 'GlitchyGamesSite'
BUCKET_NAME = 'site-bucket'
DISTRIBUTION_ID = 'E2EXAMPLE'


@pytest.mark.parametrize(
    ('file_name', 'content_type'),
    [
        ('index.html', 'text/html; charset=utf-8'),
        ('boot.js', 'text/javascript'),
        ('touch_controls.mjs', 'text/javascript'),
        ('core.css', 'text/css'),
        ('boot_config.json', 'application/json'),
        ('pyodide.asm.wasm', 'application/wasm'),
        ('arcade-mockup.png', 'image/png'),
        ('glitchygames.zip', 'application/zip'),
        ('pygame_ce-2.5-cp314-pyodide.whl', 'application/zip'),
        ('pyscript.toml', 'text/plain; charset=utf-8'),
        ('no-extension', 'application/octet-stream'),
    ],
)
def test_content_types(file_name, content_type):
    """Each file is served as what it is; .wasm as application/wasm, which browsers require."""
    assert content_type_for(path=Path(file_name)) == content_type


def test_html_is_cached_briefly_and_the_rest_for_a_day():
    """Pages show a deploy within a minute; other files may be cached a day."""
    assert cache_control_for(key='index.html') == 'public, max-age=60'
    assert cache_control_for(key='games/paddleslap/index.html') == 'public, max-age=60'
    assert cache_control_for(key='arcade-mockup.png') == 'public, max-age=86400'


def test_the_plan_uploads_every_file_and_deletes_what_is_gone(tmp_path):
    """Every local file is uploaded under its relative path; bucket keys with no file go."""
    (tmp_path / 'index.html').write_text('<!doctype html>', encoding='utf-8')
    (tmp_path / 'games' / 'a').mkdir(parents=True)
    (tmp_path / 'games' / 'a' / 'index.html').write_text('<!doctype html>', encoding='utf-8')

    plan = plan_publish(source_directory=tmp_path, existing_keys=['index.html', 'old.png'])

    assert [upload.key for upload in plan.uploads] == ['games/a/index.html', 'index.html']
    assert plan.uploads[1].local_path == tmp_path / 'index.html'
    assert plan.uploads[1].content_type == 'text/html; charset=utf-8'
    assert plan.uploads[1].cache_control == 'public, max-age=60'
    assert plan.deletions == ('old.png',)


def test_dotfiles_are_neither_uploaded_nor_kept(tmp_path):
    """Finder's .DS_Store (and any dot-directory) never reaches the site."""
    (tmp_path / 'index.html').write_text('<!doctype html>', encoding='utf-8')
    (tmp_path / '.DS_Store').write_bytes(b'\x00')
    (tmp_path / '.hidden').mkdir()
    (tmp_path / '.hidden' / 'secret.txt').write_text('x', encoding='utf-8')

    plan = plan_publish(source_directory=tmp_path, existing_keys=['.DS_Store'])

    assert [upload.key for upload in plan.uploads] == ['index.html']
    assert plan.deletions == ('.DS_Store',)


def refused_sources(tmp_path: Path) -> dict[str, Path]:
    """Return the sources publishing must refuse, by name."""
    a_file = tmp_path / 'a-file.html'
    a_file.write_text('<!doctype html>', encoding='utf-8')
    empty = tmp_path / 'empty'
    empty.mkdir()
    without_index = tmp_path / 'without-index'
    without_index.mkdir()
    (without_index / 'other.html').write_text('<!doctype html>', encoding='utf-8')
    return {
        'missing': tmp_path / 'missing',
        'a file': a_file,
        'empty': empty,
        'without index.html': without_index,
    }


@pytest.fixture
def aws_clients(monkeypatch) -> dict[str, object]:
    """Return S3, CloudFormation and CloudFront clients that never reach AWS unstubbed.

    The developer's own AWS profile is not read: a test must not depend on it.
    """
    monkeypatch.delenv('AWS_PROFILE', raising=False)
    monkeypatch.delenv('AWS_DEFAULT_PROFILE', raising=False)
    # Unsigned: no credentials are needed, since the Stubber answers before anything is sent
    unsigned = Config(signature_version=UNSIGNED)
    session = boto3.Session(region_name='us-east-1')
    return {
        's3_client': session.client('s3', config=unsigned),
        'cloudformation_client': session.client('cloudformation', config=unsigned),
        'cloudfront_client': session.client('cloudfront', config=unsigned),
    }


@pytest.mark.parametrize('source_name', ['missing', 'a file', 'empty', 'without index.html'])
def test_publishing_refuses_a_missing_empty_or_index_less_source(
    tmp_path, source_name, aws_clients
):
    """A wrong source must never empty the bucket: refused before any AWS call, by name."""
    source = refused_sources(tmp_path)[source_name]
    clients = aws_clients
    stubbers = [Stubber(client) for client in clients.values()]
    for stubber in stubbers:
        stubber.activate()

    with pytest.raises(PublishRefusedError, match=str(source)):
        publish(source_directory=source, **clients)

    for stubber in stubbers:
        stubber.assert_no_pending_responses()


def describe_stacks_response() -> dict:
    """Return CloudFormation's description of the site stack with its two outputs."""
    return {
        'Stacks': [
            {
                'StackName': STACK_NAME,
                'CreationTime': datetime(2026, 10, 28, tzinfo=UTC),
                'StackStatus': 'CREATE_COMPLETE',
                'Outputs': [
                    {'OutputKey': 'SiteBucketName', 'OutputValue': BUCKET_NAME},
                    {'OutputKey': 'SiteDistributionId', 'OutputValue': DISTRIBUTION_ID},
                ],
            }
        ]
    }


def test_the_site_target_comes_from_the_stack_outputs(aws_clients):
    """The bucket and distribution are read from the site stack, never configured by hand."""
    cloudformation_client = aws_clients['cloudformation_client']
    with Stubber(cloudformation_client) as stubber:
        stubber.add_response(
            'describe_stacks', describe_stacks_response(), {'StackName': STACK_NAME}
        )

        target = site_target(cloudformation_client=cloudformation_client, stack_name=STACK_NAME)

    assert target == SiteTarget(bucket_name=BUCKET_NAME, distribution_id=DISTRIBUTION_ID)


def test_publish_uploads_then_deletes_then_invalidates(tmp_path, aws_clients):
    """Uploads first (no page is ever missing), then stale keys go, then one /* invalidation."""
    (tmp_path / 'index.html').write_text('<!doctype html>', encoding='utf-8')
    (tmp_path / 'arcade-mockup.png').write_bytes(b'\x89PNG')
    clients = aws_clients
    stubbers = {name: Stubber(client) for name, client in clients.items()}
    stubbers['cloudformation_client'].add_response(
        'describe_stacks', describe_stacks_response(), {'StackName': STACK_NAME}
    )
    stubbers['s3_client'].add_response(
        'list_objects_v2',
        {'IsTruncated': False, 'Contents': [{'Key': 'index.html'}, {'Key': 'old.png'}]},
        {'Bucket': BUCKET_NAME},
    )
    for key, content_type, cache_control in (
        ('arcade-mockup.png', 'image/png', 'public, max-age=86400'),
        ('index.html', 'text/html; charset=utf-8', 'public, max-age=60'),
    ):
        stubbers['s3_client'].add_response(
            'put_object',
            {},
            {
                'Bucket': BUCKET_NAME,
                'Key': key,
                'Body': ANY,
                'ContentType': content_type,
                'CacheControl': cache_control,
            },
        )
    stubbers['s3_client'].add_response(
        'delete_objects',
        {'Deleted': [{'Key': 'old.png'}]},
        {'Bucket': BUCKET_NAME, 'Delete': {'Objects': [{'Key': 'old.png'}], 'Quiet': True}},
    )
    stubbers['cloudfront_client'].add_response(
        'create_invalidation',
        {
            'Location': 'https://cloudfront.amazonaws.com/invalidation/I1',
            'Invalidation': {
                'Id': 'I1',
                'Status': 'InProgress',
                'CreateTime': datetime(2026, 10, 28, tzinfo=UTC),
                'InvalidationBatch': {
                    'Paths': {'Quantity': 1, 'Items': ['/*']},
                    'CallerReference': 'reference',
                },
            },
        },
        {
            'DistributionId': DISTRIBUTION_ID,
            'InvalidationBatch': {
                'Paths': {'Quantity': 1, 'Items': ['/*']},
                'CallerReference': ANY,
            },
        },
    )
    for stubber in stubbers.values():
        stubber.activate()

    plan = publish(source_directory=tmp_path, stack_name=STACK_NAME, **clients)

    for stubber in stubbers.values():
        stubber.assert_no_pending_responses()
    assert plan.deletions == ('old.png',)


def test_a_dry_run_prints_the_plan_and_touches_nothing(capsys):
    """--dry-run plans against an empty bucket, prints each upload, and needs no credentials."""
    exit_code = main(['--source', str(WEBSITE_DIRECTORY), '--dry-run'])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert 'upload index.html (text/html; charset=utf-8, public, max-age=60)' in output
    assert 'upload arcade-mockup.png (image/png, public, max-age=86400)' in output


def test_a_refused_source_exits_1_with_its_reason(tmp_path, capsys):
    """The command line reports a refusal on stderr and exits 1 rather than raising."""
    exit_code = main(['--source', str(tmp_path / 'missing'), '--dry-run'])

    assert exit_code == 1
    assert str(tmp_path / 'missing') in capsys.readouterr().err


def test_the_website_is_publishable():
    """The site is exactly its page and the owner's mockup, as HTML and PNG."""
    plan = plan_publish(source_directory=WEBSITE_DIRECTORY, existing_keys=[])

    assert [(upload.key, upload.content_type) for upload in plan.uploads] == [
        ('arcade-mockup.png', 'image/png'),
        ('index.html', 'text/html; charset=utf-8'),
    ]


def test_the_website_loads_nothing_from_elsewhere():
    """The page is self-contained: its only outside URL is a link to the repository."""
    page = (WEBSITE_DIRECTORY / 'index.html').read_text(encoding='utf-8')

    assert 'src="http' not in page
    assert page.count('href="http') == 1
    assert 'href="https://github.com/terrysimons/glitchygames"' in page
    assert 'src="arcade-mockup.png"' in page
