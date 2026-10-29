"""Tests for scripts/generate_sbom.py: the SBOM depends on uv.lock and its license sources alone.

The documents are small hand-written CycloneDX SBOMs shaped like syft's output for a uv.lock (a
library per locked package, the lock as a file component, dependency entries with random refs),
and the locks small hand-written uv.lock tables. syft itself is a system binary, so the module's
own ``subprocess`` and ``shutil`` are replaced with stand-ins where a test runs the scan; the
installed distributions are this test environment's own, never patched.
"""

from __future__ import annotations

import importlib.metadata
import json
import subprocess  # ruff: ignore[suspicious-subprocess-import] - CompletedProcess only
import tomllib
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from scripts import check_licenses, generate_sbom

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def syft_document(
    *,
    serial: str,
    timestamp: str,
    package_id: str,
    lock_path: str = '/checkout/uv.lock',
    dependency_order: tuple[int, ...] = (0, 1, 2),
) -> dict[str, Any]:
    """Return a syft-shaped SBOM of a uv.lock whose volatile fields carry the given values.

    Args:
        serial: The document's serialNumber.
        timestamp: Its metadata.timestamp.
        package_id: The ``?package-id=`` suffix (and bom-ref) syft would generate this run.
        lock_path: The scanned lock's path, as syft names its file component.
        dependency_order: The order of its three dependency entries.

    Returns:
        The document.

    """
    dependencies = [
        {
            'ref': f'pkg:pypi/jinja2@3.1.6?package-id={package_id}a',
            'dependsOn': [
                f'pkg:pypi/markupsafe@3.0.3?package-id={package_id}b',
                # another version of a kept package's name maps to the kept one
                f'pkg:pypi/tomli@2.0.1?package-id={package_id}v',
                # a package that is not in the SBOM at all
                f'pkg:pypi/absent@1.0?package-id={package_id}x',
            ],
        },
        {'ref': f'pkg:pypi/markupsafe@3.0.3?package-id={package_id}b', 'dependsOn': []},
        {'ref': f'pkg:pypi/tomli@2.4.0?package-id={package_id}c', 'dependsOn': []},
    ]
    libraries = [
        {
            'bom-ref': f'pkg:pypi/{name}@{version}?package-id={package_id}{suffix}',
            'type': 'library',
            'name': name,
            'version': version,
            'purl': f'pkg:pypi/{name}@{version}?package-id={package_id}{suffix}',
            'properties': [{'name': 'syft:location:0:path', 'value': '/uv.lock'}],
        }
        for name, version, suffix in (
            ('jinja2', '3.1.6', 'a'),
            ('markupsafe', '3.0.3', 'b'),
            ('tomli', '2.4.0', 'c'),
        )
    ]
    return {
        'bomFormat': 'CycloneDX',
        'serialNumber': serial,
        'metadata': {
            'timestamp': timestamp,
            'tools': {'components': [{'name': 'syft', 'version': '1.55.0'}]},
            'component': {
                'bom-ref': package_id,
                'type': 'file',
                'name': 'uv.lock',
                'version': f'sha256:{package_id}',
            },
        },
        'components': [
            *libraries,
            {'bom-ref': f'{package_id}f', 'type': 'file', 'name': lock_path},
        ],
        'dependencies': [dependencies[index] for index in dependency_order],
    }


def test_volatile_document_fields_are_stripped_and_syft_version_kept():
    """serialNumber, the timestamp, the lock's bom-ref and digest go; the tools stay."""
    sbom = generate_sbom.strip_volatile_fields(
        syft_document(serial='urn:uuid:1', timestamp='2026-10-28T16:00:00Z', package_id='aa')
    )

    assert 'serialNumber' not in sbom
    assert sbom['metadata'] == {
        'tools': {'components': [{'name': 'syft', 'version': '1.55.0'}]},
        'component': {'type': 'file', 'name': 'uv.lock'},
    }


def test_the_lock_file_component_is_dropped():
    """Only the locked packages stay, each without its bom-ref or purl query."""
    sbom = generate_sbom.strip_volatile_fields(
        syft_document(serial='urn:uuid:1', timestamp='t', package_id='aa')
    )

    assert [(component['name'], component['purl']) for component in sbom['components']] == [
        ('jinja2', 'pkg:pypi/jinja2@3.1.6'),
        ('markupsafe', 'pkg:pypi/markupsafe@3.0.3'),
        ('tomli', 'pkg:pypi/tomli@2.4.0'),
    ]
    assert all('bom-ref' not in component for component in sbom['components'])


def test_dependencies_point_at_kept_packages_deduplicated_and_sorted():
    """Another version maps to the kept package, an absent one is dropped, entries anonymous."""
    sbom = generate_sbom.strip_volatile_fields(
        syft_document(serial='urn:uuid:1', timestamp='t', package_id='aa')
    )

    # The two empty entries (markupsafe's, tomli's) collapse into one once their refs are gone
    assert sbom['dependencies'] == [
        {'dependsOn': []},
        {'dependsOn': ['pkg:pypi/markupsafe@3.0.3', 'pkg:pypi/tomli@2.4.0']},
    ]


def test_two_scans_of_the_same_lock_write_the_same_bytes(tmp_path: Path):
    """Different serials, timestamps, package ids, digests and entry orders: identical files."""
    first = tmp_path / 'first.json'
    second = tmp_path / 'second.json'

    generate_sbom.write_sbom(
        sbom=generate_sbom.strip_volatile_fields(
            syft_document(serial='urn:uuid:1', timestamp='2026-10-28', package_id='aa')
        ),
        output=first,
    )
    generate_sbom.write_sbom(
        sbom=generate_sbom.strip_volatile_fields(
            syft_document(
                serial='urn:uuid:2',
                timestamp='2026-10-29',
                package_id='bb',
                lock_path='C:\\checkout\\uv.lock',
                dependency_order=(2, 0, 1),
            )
        ),
        output=second,
    )

    assert first.read_bytes() == second.read_bytes()
    assert first.read_text(encoding='utf-8').endswith('}\n')


def test_malformed_entries_are_skipped():
    """Non-object components and dependencies, non-string targets: skipped, never a crash."""
    sbom: dict[str, Any] = {
        'metadata': 'not an object',
        'components': ['not an object', {'type': 'library', 'name': 'a', 'purl': 7}],
        'dependencies': ['not an object', {'ref': 'x', 'dependsOn': [3, 'pkg:pypi/a@1']}],
    }

    stripped = generate_sbom.strip_volatile_fields(sbom)

    assert stripped['components'] == [{'type': 'library', 'name': 'a', 'purl': 7}]
    assert stripped['dependencies'] == [{'dependsOn': []}]


def test_a_document_without_components_or_dependencies_gains_none():
    """Absent sections stay absent."""
    assert generate_sbom.strip_volatile_fields({'bomFormat': 'CycloneDX'}) == {
        'bomFormat': 'CycloneDX'
    }


def test_naming_a_document_without_a_scanned_lock_changes_nothing():
    """No metadata, or metadata without a component: left as it is."""
    assert generate_sbom.name_scanned_lock(sbom={}, name='uv.lock') == {}
    assert generate_sbom.name_scanned_lock(sbom={'metadata': {}}, name='uv.lock') == {
        'metadata': {}
    }


# ---------------------------------------------------------------------------
# Where the lock installs each package
# ---------------------------------------------------------------------------

REGISTRY = {'registry': 'https://pypi.org/simple'}


def lock_with_platform_markers() -> dict[str, Any]:
    """Return a uv.lock table shaped like ours: members, extras, groups and markers.

    Returns:
        The parsed lock.

    """
    return {
        'package': [
            {
                'name': 'engine',
                'source': {'editable': '.'},
                'dependencies': [{'name': 'pyinstaller'}, {'name': 'aisuite', 'extra': ['mcp']}],
                'optional-dependencies': {'dev': [{'name': 'deptry'}]},
                'dev-dependencies': {'dev': [{'name': 'game'}]},
            },
            {
                'name': 'game',
                'source': {'virtual': 'src/game'},
                'dependencies': [{'name': 'Engine'}],
            },
            {
                'name': 'pyinstaller',
                'source': REGISTRY,
                'dependencies': [
                    {'name': 'macholib', 'marker': "sys_platform == 'darwin'"},
                    {'name': 'pefile', 'marker': "sys_platform == 'win32'"},
                ],
            },
            {
                'name': 'aisuite',
                'source': REGISTRY,
                'optional-dependencies': {
                    'mcp': [{'name': 'mcp'}],
                    # an extra nobody asks for is never installed
                    'unrequested': [{'name': 'never-installed'}],
                },
            },
            {
                'name': 'mcp',
                'source': REGISTRY,
                'dependencies': [{'name': 'pywin32', 'marker': "sys_platform == 'win32'"}],
            },
            {
                'name': 'deptry',
                'source': REGISTRY,
                'dependencies': [
                    {'name': 'tomli', 'marker': "python_full_version < '3.15'"},
                    # an edge to a package the lock does not hold is skipped
                    {'name': 'missing-from-the-lock'},
                ],
            },
            *(
                {'name': name, 'source': REGISTRY}
                for name in ('macholib', 'pefile', 'pywin32', 'tomli', 'never-installed')
            ),
        ]
    }


COMMON_PACKAGES = frozenset({'engine', 'game', 'pyinstaller', 'aisuite', 'mcp', 'deptry'})


@pytest.mark.parametrize(
    ('sys_platform', 'python_version', 'platform_packages'),
    [
        ('darwin', '3.14', {'macholib', 'tomli'}),
        ('darwin', '3.15', {'macholib'}),
        ('linux', '3.14', {'tomli'}),
        ('linux', '3.15', set()),
        ('win32', '3.14', {'pefile', 'pywin32', 'tomli'}),
        ('win32', '3.15', {'pefile', 'pywin32'}),
    ],
)
def test_each_environment_installs_what_its_markers_allow(
    sys_platform: str, python_version: str, platform_packages: set[str]
):
    """Each platform gets its marked packages (tomli before 3.15); unrequested extras none."""
    [environment] = [
        environment
        for environment in generate_sbom.SUPPORTED_ENVIRONMENTS
        if (environment['sys_platform'], environment['python_version'])
        == (sys_platform, python_version)
    ]

    assert generate_sbom.packages_installed_in(
        lock=lock_with_platform_markers(), environment=environment
    ) == {*COMMON_PACKAGES, *platform_packages}


def test_only_packages_installed_in_every_supported_environment_are_everywhere():
    """The intersection over macOS, Linux and Windows on Python 3.14 and 3.15."""
    assert (
        generate_sbom.packages_installed_everywhere(lock=lock_with_platform_markers())
        == COMMON_PACKAGES
    )


def test_every_supported_environment_names_every_marker_variable():
    """No marker variable falls back to the machine running the script."""
    variables = {
        'implementation_name',
        'implementation_version',
        'os_name',
        'platform_machine',
        'platform_python_implementation',
        'platform_release',
        'platform_system',
        'platform_version',
        'python_full_version',
        'python_version',
        'sys_platform',
        'extra',
    }

    assert len(generate_sbom.SUPPORTED_ENVIRONMENTS) == 6
    assert all(
        set(environment) == variables for environment in generate_sbom.SUPPORTED_ENVIRONMENTS
    )


def test_our_lock_installs_the_overridden_platform_packages_somewhere_only():
    """uv.lock's packages outside some supported environment are all overridden."""
    lock = tomllib.loads(generate_sbom.LOCK_PATH.read_text(encoding='utf-8'))
    locked = {str(package['name']) for package in lock['package']}
    somewhere_only = locked - generate_sbom.packages_installed_everywhere(lock=lock)

    assert {'pywin32', 'macholib', 'tomli'} <= somewhere_only
    assert somewhere_only <= set(check_licenses.PACKAGE_LICENSE_OVERRIDES)


# ---------------------------------------------------------------------------
# Licenses
# ---------------------------------------------------------------------------


def core_metadata(
    fields: dict[str, str | list[str]], *, directory: Path
) -> importlib.metadata.PackageMetadata:
    """Return a distribution's core metadata, read from a METADATA file.

    A list value repeats its field; a value's further lines are folded as setuptools writes a
    whole license text (each continuation line indented eight spaces).

    Returns:
        The metadata, as ``importlib.metadata`` reads it.

    """
    lines = ['Metadata-Version: 2.4', 'Name: demo', 'Version: 1.0']
    for field, value in fields.items():
        for entry in value if isinstance(value, list) else [value]:
            first, *continuation = entry.split('\n')
            lines.extend([f'{field}: {first}', *(f'        {line}' for line in continuation)])
    dist_info = directory / 'demo-1.0.dist-info'
    dist_info.mkdir()
    (dist_info / 'METADATA').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return importlib.metadata.PathDistribution(dist_info).metadata


@pytest.mark.parametrize(
    ('fields', 'expected'),
    [
        (
            {'License-Expression': 'MIT OR Apache-2.0', 'License': 'BSD'},
            {'expression': 'MIT OR Apache-2.0'},
        ),
        ({'License': 'BSD-3-Clause'}, {'license': {'name': 'BSD-3-Clause'}}),
        (
            {
                'License': 'UNKNOWN',
                'Classifier': ['License :: OSI Approved :: MIT License', 'Topic :: Games'],
            },
            {'license': {'name': 'MIT License'}},
        ),
        (
            {
                'License': 'The MIT License (MIT)\n\nCopyright (c) 2014',
                'Classifier': ['License :: OSI Approved', 'License :: OSI Approved :: BSD License'],
            },
            {'license': {'name': 'BSD License'}},
        ),
        ({'Classifier': ['License :: Public Domain']}, {'license': {'name': 'Public Domain'}}),
        (
            {
                'Classifier': [
                    'License :: OSI Approved :: BSD License',
                    'License :: OSI Approved :: Apache Software License',
                ]
            },
            None,
        ),
        ({'Classifier': ['Topic :: Games']}, None),
        ({}, None),
    ],
)
def test_the_license_metadata_declares(
    fields: dict[str, str | list[str]], expected: dict[str, Any] | None, tmp_path: Path
):
    """License-Expression, else a one-line License, else the one license classifier, else none."""
    assert generate_sbom.metadata_license(core_metadata(fields, directory=tmp_path)) == expected


def test_installed_distributions_are_this_environments():
    """Each installed distribution by canonical name, with its version and declared license."""
    installed = generate_sbom.installed_distributions()

    assert installed['pytest'] == (
        importlib.metadata.version('pytest'),
        generate_sbom.metadata_license(importlib.metadata.distribution('pytest').metadata),
    )
    assert 'pytest-mock' in installed


def test_a_distribution_installed_twice_counts_once_and_one_without_a_name_not_at_all(
    tmp_path: Path,
):
    """The first install of a name wins, as Python's import would; a nameless one is skipped."""
    for directory, metadata in (
        ('first', 'Name: Demo_Package\nVersion: 1.0\nLicense: MIT\n'),
        ('second', 'Name: demo-package\nVersion: 2.0\n'),
        ('second', 'Version: 3.0\n'),
    ):
        location = tmp_path / directory
        location.mkdir(exist_ok=True)
        dist_info = location / f'demo_package-{metadata.split("Version: ")[1][:3]}.dist-info'
        dist_info.mkdir()
        (dist_info / 'METADATA').write_text(metadata, encoding='utf-8')

    installed = generate_sbom.installed_distributions(
        search_path=[str(tmp_path / 'first'), str(tmp_path / 'second')]
    )

    assert installed == {'demo-package': ('1.0', {'license': {'name': 'MIT'}})}


def test_a_document_whose_metadata_names_no_scanned_lock_keeps_its_metadata():
    """Metadata without a component loses its timestamp only."""
    assert generate_sbom.strip_volatile_fields({'metadata': {'timestamp': 't', 'tools': {}}}) == {
        'metadata': {'tools': {}}
    }


def library(name: str, version: str, **fields: Any) -> dict[str, Any]:
    """Return a stripped library component.

    Returns:
        The component.

    """
    return {'type': 'library', 'name': name, 'version': version, **fields}


def test_an_override_wins_over_metadata_and_a_licensed_package_takes_its_metadata():
    """Overrides (by name as written or canonical) are SPDX expressions; others their metadata."""
    sbom: dict[str, Any] = {
        'components': [
            library('PyWin32', '312'),
            library('jinja2', '3.1.6', licenses=[{'license': {'id': 'stale'}}]),
            library('markupsafe', '3.0.3'),
            library('tomli', '2.4.0'),
            {'type': 'application', 'name': 'not a library'},
        ]
    }

    generate_sbom.add_licenses(
        sbom=sbom,
        installed_everywhere=frozenset({'jinja2', 'markupsafe'}),
        installed={
            'jinja2': ('3.1.6', {'expression': 'BSD-3-Clause'}),
            'markupsafe': ('3.0.3', None),
            'pywin32': ('312', {'license': {'name': 'PSF'}}),
        },
        overrides={'pywin32': ('PSF-2.0', 'METADATA'), 'tomli': ('MIT', 'METADATA')},
    )

    assert [component.get('licenses') for component in sbom['components']] == [
        [{'expression': 'PSF-2.0'}],
        [{'expression': 'BSD-3-Clause'}],
        None,
        [{'expression': 'MIT'}],
        None,
    ]


def test_a_component_without_a_deterministic_license_source_fails_naming_each():
    """Somewhere-only without an override, not installed, or another version: all named."""
    sbom = {
        'components': [
            library('pefile', '2024.8.26'),
            library('jinja2', '3.1.6'),
            library('markupsafe', '3.0.3'),
            library('numpy', '1.26.4'),
        ]
    }

    with pytest.raises(generate_sbom.LicenseSourceError) as raised:
        generate_sbom.add_licenses(
            sbom=sbom,
            installed_everywhere=frozenset({'jinja2', 'markupsafe', 'numpy'}),
            installed={
                'pefile': ('2024.8.26', None),
                'markupsafe': ('3.0.2', None),
                'numpy': ('1.26.4.0', {'expression': 'BSD-3-Clause'}),
            },
            overrides={},
        )

    message = str(raised.value)
    assert 'pefile 2024.8.26: uv.lock installs it on some platforms' in message
    assert 'jinja2 3.1.6: not installed in this environment' in message
    assert 'markupsafe: uv.lock pins 3.0.3 but 3.0.2 is installed' in message
    # 1.26.4.0 is 1.26.4: versions compare as versions, not strings
    assert 'numpy' not in message


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


def syft_stand_in(*, mocker: MockerFixture, returncode: int, stdout: str, stderr: str = '') -> Any:
    """Replace the module's own ``subprocess`` and ``shutil`` so syft appears to run.

    Returns:
        The stand-in ``run`` (a mock), to inspect the command.

    """
    run = mocker.Mock(
        return_value=subprocess.CompletedProcess(
            args=['syft'], returncode=returncode, stdout=stdout, stderr=stderr
        )
    )
    mocker.patch.object(generate_sbom, 'subprocess', SimpleNamespace(run=run))
    mocker.patch.object(
        generate_sbom, 'shutil', SimpleNamespace(which=lambda name: f'/usr/local/bin/{name}')
    )
    return run


def write_lock(directory: Path) -> Path:
    """Write a uv.lock of one member depending on pytest, which this environment installs.

    Returns:
        The lock's path.

    """
    lock = directory / 'uv.lock'
    lock.write_text(
        'version = 1\n\n[[package]]\nname = "member"\nsource = { editable = "." }\n'
        'dependencies = [{ name = "pytest" }]\n\n'
        '[[package]]\nname = "pytest"\nsource = { registry = "https://pypi.org/simple" }\n',
        encoding='utf-8',
    )
    return lock


def pytest_document(*, package_id: str, lock: Path) -> dict[str, Any]:
    """Return a syft-shaped SBOM of ``write_lock``'s lock.

    Returns:
        The document.

    """
    version = importlib.metadata.version('pytest')
    return {
        'bomFormat': 'CycloneDX',
        'serialNumber': f'urn:uuid:{package_id}',
        'metadata': {
            'timestamp': package_id,
            'tools': {'components': [{'name': 'syft', 'version': '1.55.0'}]},
            'component': {'bom-ref': package_id, 'type': 'file', 'name': str(lock)},
        },
        'components': [
            library('pytest', version, purl=f'pkg:pypi/pytest@{version}?package-id={package_id}'),
            {'bom-ref': package_id, 'type': 'file', 'name': str(lock)},
        ],
    }


def test_main_scans_the_lock_and_writes_the_stripped_licensed_sbom(
    mocker: MockerFixture, tmp_path: Path
):
    """The SBOM of the lock is stripped, named by its file name and licensed from metadata."""
    lock = write_lock(tmp_path)
    output = tmp_path / 'docs' / 'sbom.cyclonedx.json'
    run = syft_stand_in(
        mocker=mocker, returncode=0, stdout=json.dumps(pytest_document(package_id='a', lock=lock))
    )

    status = generate_sbom.main(['--lock', str(lock), '--output', str(output)])

    assert status == 0
    assert run.call_args.args[0] == [
        'syft',
        'scan',
        f'file:{lock}',
        '--output',
        'cyclonedx-json',
        '--quiet',
        '--override-default-catalogers',
        'python',
    ]
    sbom = json.loads(output.read_text(encoding='utf-8'))
    assert sbom['metadata']['component'] == {'type': 'file', 'name': 'uv.lock'}
    [component] = sbom['components']
    declared = generate_sbom.metadata_license(importlib.metadata.distribution('pytest').metadata)
    assert component.get('licenses') == ([declared] if declared is not None else None)


def test_two_checkouts_of_the_same_lock_write_the_same_sbom(mocker: MockerFixture, tmp_path: Path):
    """The lock's path and syft's per-run fields leave no trace."""
    outputs = []
    for checkout in ('one', 'two'):
        directory = tmp_path / checkout
        directory.mkdir()
        lock = write_lock(directory)
        document = pytest_document(package_id=checkout, lock=lock)
        syft_stand_in(mocker=mocker, returncode=0, stdout=json.dumps(document))
        output = tmp_path / f'{checkout}.json'
        assert generate_sbom.main(['--lock', str(lock), '--output', str(output)]) == 0
        outputs.append(output.read_bytes())

    assert outputs[0] == outputs[1]


def test_main_fails_when_a_license_has_no_deterministic_source(
    mocker: MockerFixture, tmp_path: Path, capsys
):
    """A locked version other than the installed one: exit 1, named; nothing written."""
    lock = write_lock(tmp_path)
    output = tmp_path / 'sbom.json'
    document = pytest_document(package_id='a', lock=lock)
    document['components'][0]['version'] = '0.0.1'
    syft_stand_in(mocker=mocker, returncode=0, stdout=json.dumps(document))

    assert generate_sbom.main(['--lock', str(lock), '--output', str(output)]) == 1
    assert 'pytest: uv.lock pins 0.0.1 but' in capsys.readouterr().err
    assert not output.exists()


def test_main_fails_without_syft(mocker: MockerFixture, tmp_path: Path, capsys):
    """No syft on PATH: exit 1 and say how to install it."""
    mocker.patch.object(generate_sbom, 'shutil', SimpleNamespace(which=lambda _name: None))

    assert generate_sbom.main(['--lock', str(write_lock(tmp_path))]) == 1
    assert 'syft is not on PATH' in capsys.readouterr().err


def test_main_fails_without_the_lock(mocker: MockerFixture, tmp_path: Path, capsys):
    """A lock that does not exist is an error, not an empty SBOM."""
    syft_stand_in(mocker=mocker, returncode=0, stdout='{}')

    assert generate_sbom.main(['--lock', str(tmp_path / 'missing.lock')]) == 1
    assert 'No lock file at' in capsys.readouterr().err


def test_main_fails_when_syft_fails(mocker: MockerFixture, tmp_path: Path, capsys):
    """The exit status and message of a failed syft are reported; nothing is written."""
    output = tmp_path / 'sbom.json'
    syft_stand_in(mocker=mocker, returncode=2, stdout='', stderr='no such catalog')

    assert generate_sbom.main(['--lock', str(write_lock(tmp_path)), '--output', str(output)]) == 1
    assert 'syft exited 2: no such catalog' in capsys.readouterr().err
    assert not output.exists()


def test_main_fails_when_syft_writes_no_json(mocker: MockerFixture, tmp_path: Path, capsys):
    """Output that does not parse is an error."""
    syft_stand_in(mocker=mocker, returncode=0, stdout='not json')

    assert generate_sbom.main(['--lock', str(write_lock(tmp_path))]) == 1
    assert 'syft output was not JSON' in capsys.readouterr().err


def test_main_fails_when_syft_writes_no_object(mocker: MockerFixture, tmp_path: Path, capsys):
    """JSON that is not an object is an error."""
    syft_stand_in(mocker=mocker, returncode=0, stdout='[]')

    assert generate_sbom.main(['--lock', str(write_lock(tmp_path))]) == 1
    assert 'syft output was not a JSON object' in capsys.readouterr().err
