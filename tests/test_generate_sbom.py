"""Tests for scripts/generate_sbom.py: the SBOM it writes depends on the dependency set alone.

The documents are small hand-written CycloneDX SBOMs shaped like syft's output (a library with
its locations, a file component, a vendored copy, dependency entries with random refs). syft
itself is a system binary, so the module's own ``subprocess`` and ``shutil`` are replaced with
stand-ins where a test runs the scan; nothing else is patched.
"""

from __future__ import annotations

import copy
import json
import subprocess  # ruff: ignore[suspicious-subprocess-import] - CompletedProcess only
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from scripts import generate_sbom

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def location(path: str) -> dict[str, str]:
    """Return a syft location property for a path.

    Returns:
        The property.

    """
    return {'name': 'syft:location:0:path', 'value': path}


def syft_document(
    *, serial: str, timestamp: str, package_id: str, dependency_order: tuple[int, ...] = (0, 1, 2)
) -> dict[str, Any]:
    """Return a syft-shaped SBOM whose volatile fields carry the given values.

    Args:
        serial: The document's serialNumber.
        timestamp: Its metadata.timestamp.
        package_id: The ``?package-id=`` suffix (and bom-ref) syft would generate this run.
        dependency_order: The order of its three dependency entries.

    Returns:
        The document.

    """
    dependencies = [
        {
            'ref': f'pkg:pypi/jinja2@3.1.6?package-id={package_id}a',
            'dependsOn': [
                f'pkg:pypi/markupsafe@3.0.3?package-id={package_id}b',
                # syft sometimes points at the vendored copy, which is filtered out
                f'pkg:pypi/tomli@2.0.1?package-id={package_id}v',
                # a package that is not in the SBOM at all
                f'pkg:pypi/absent@1.0?package-id={package_id}x',
            ],
        },
        {'ref': f'pkg:pypi/markupsafe@3.0.3?package-id={package_id}b', 'dependsOn': []},
        {'ref': f'pkg:pypi/tomli@2.4.0?package-id={package_id}c', 'dependsOn': []},
    ]
    return {
        'bomFormat': 'CycloneDX',
        'serialNumber': serial,
        'metadata': {
            'timestamp': timestamp,
            'tools': {'components': [{'name': 'syft', 'version': '1.55.0'}]},
            'component': {'bom-ref': package_id, 'type': 'file', 'name': 'security-scan'},
        },
        'components': [
            {
                'bom-ref': f'pkg:pypi/jinja2@3.1.6?package-id={package_id}a',
                'type': 'library',
                'name': 'jinja2',
                'version': '3.1.6',
                'purl': f'pkg:pypi/jinja2@3.1.6?package-id={package_id}a',
                'properties': [location('/lib/python3.14/site-packages/jinja2-3.1.6.dist-info')],
            },
            {
                'bom-ref': f'pkg:pypi/markupsafe@3.0.3?package-id={package_id}b',
                'type': 'library',
                'name': 'markupsafe',
                'version': '3.0.3',
                'purl': f'pkg:pypi/markupsafe@3.0.3?package-id={package_id}b',
            },
            {
                'bom-ref': f'pkg:pypi/tomli@2.4.0?package-id={package_id}c',
                'type': 'library',
                'name': 'tomli',
                'version': '2.4.0',
                'purl': f'pkg:pypi/tomli@2.4.0?package-id={package_id}c',
                'properties': [location('/lib/python3.14/site-packages/tomli-2.4.0.dist-info')],
            },
            {
                'bom-ref': f'pkg:pypi/tomli@2.0.1?package-id={package_id}v',
                'type': 'library',
                'name': 'tomli',
                'version': '2.0.1',
                'purl': f'pkg:pypi/tomli@2.0.1?package-id={package_id}v',
                'properties': [
                    location('/lib/python3.14/site-packages/setuptools/_vendor/tomli.dist-info')
                ],
            },
            {
                'bom-ref': f'{package_id}f',
                'type': 'file',
                'name': '/lib/python3.14/site-packages/jinja2-3.1.6.dist-info/RECORD',
            },
        ],
        'dependencies': [dependencies[index] for index in dependency_order],
    }


def test_volatile_document_fields_are_stripped_and_syft_version_kept():
    """serialNumber, the timestamp and the scanned directory's bom-ref go; the tools stay."""
    sbom = generate_sbom.strip_volatile_fields(
        syft_document(serial='urn:uuid:1', timestamp='2026-10-28T16:00:00Z', package_id='aa')
    )

    assert 'serialNumber' not in sbom
    assert sbom['metadata'] == {
        'tools': {'components': [{'name': 'syft', 'version': '1.55.0'}]},
        'component': {'type': 'file', 'name': 'security-scan'},
    }


def test_file_components_and_vendored_copies_are_dropped():
    """Only the installed libraries stay, each without its bom-ref or purl query."""
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
    """A vendored target maps to the kept copy, an absent one is dropped, entries are anonymous."""
    sbom = generate_sbom.strip_volatile_fields(
        syft_document(serial='urn:uuid:1', timestamp='t', package_id='aa')
    )

    # The two empty entries (markupsafe's, tomli's) collapse into one once their refs are gone
    assert sbom['dependencies'] == [
        {'dependsOn': []},
        {'dependsOn': ['pkg:pypi/markupsafe@3.0.3', 'pkg:pypi/tomli@2.4.0']},
    ]


def test_two_scans_of_the_same_packages_write_the_same_bytes(tmp_path: Path):
    """Different serials, timestamps, package ids and entry orders: identical files."""
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
                dependency_order=(2, 0, 1),
            )
        ),
        output=second,
    )

    assert first.read_bytes() == second.read_bytes()
    assert first.read_text(encoding='utf-8').endswith('}\n')


def test_a_component_with_one_real_location_is_kept():
    """A package found both installed and vendored is a real installation."""
    component = {
        'properties': [
            location('/lib/python3.14/site-packages/pip/_vendor/rich.dist-info'),
            location('/lib/python3.14/site-packages/rich-14.0.0.dist-info'),
        ]
    }

    assert generate_sbom.is_embedded_package(component) is False


def test_a_component_without_locations_is_kept():
    """No location recorded: nothing says it is embedded."""
    assert generate_sbom.is_embedded_package({}) is False
    assert generate_sbom.is_embedded_package({'properties': [{'name': 'syft:cpe23'}]}) is False


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


def test_main_scans_the_virtualenv_and_writes_the_stripped_sbom(
    mocker: MockerFixture, tmp_path: Path
):
    """The scan runs syft over the virtualenv's Python packages and writes the stripped SBOM."""
    virtualenv = tmp_path / 'venv'
    virtualenv.mkdir()
    output = tmp_path / 'docs' / 'sbom.cyclonedx.json'
    document = syft_document(serial='urn:uuid:1', timestamp='t', package_id='aa')
    run = syft_stand_in(mocker=mocker, returncode=0, stdout=json.dumps(document))

    status = generate_sbom.main(['--venv', str(virtualenv), '--output', str(output)])

    assert status == 0
    assert run.call_args.args[0] == [
        'syft',
        'scan',
        f'dir:{virtualenv}',
        '--output',
        'cyclonedx-json',
        '--quiet',
        '--override-default-catalogers',
        'python',
    ]
    expected = generate_sbom.name_scanned_directory(
        sbom=generate_sbom.strip_volatile_fields(copy.deepcopy(document)), name='venv'
    )
    assert json.loads(output.read_text(encoding='utf-8')) == expected


def test_main_fails_without_syft(mocker: MockerFixture, tmp_path: Path, capsys):
    """No syft on PATH: exit 1 and say how to install it."""
    mocker.patch.object(generate_sbom, 'shutil', SimpleNamespace(which=lambda _name: None))

    assert generate_sbom.main(['--venv', str(tmp_path)]) == 1
    assert 'syft is not on PATH' in capsys.readouterr().err


def test_main_fails_without_the_virtualenv(mocker: MockerFixture, tmp_path: Path, capsys):
    """A virtualenv that does not exist is an error, not an empty SBOM."""
    syft_stand_in(mocker=mocker, returncode=0, stdout='{}')

    assert generate_sbom.main(['--venv', str(tmp_path / 'missing')]) == 1
    assert 'No virtualenv at' in capsys.readouterr().err


def test_main_fails_when_syft_fails(mocker: MockerFixture, tmp_path: Path, capsys):
    """The exit status and message of a failed syft are reported; nothing is written."""
    output = tmp_path / 'sbom.json'
    syft_stand_in(mocker=mocker, returncode=2, stdout='', stderr='no such catalog')

    assert generate_sbom.main(['--venv', str(tmp_path), '--output', str(output)]) == 1
    assert 'syft exited 2: no such catalog' in capsys.readouterr().err
    assert not output.exists()


def test_main_fails_when_syft_writes_no_json(mocker: MockerFixture, tmp_path: Path, capsys):
    """Output that does not parse is an error."""
    syft_stand_in(mocker=mocker, returncode=0, stdout='not json')

    assert generate_sbom.main(['--venv', str(tmp_path)]) == 1
    assert 'syft output was not JSON' in capsys.readouterr().err


def test_main_fails_when_syft_writes_no_object(mocker: MockerFixture, tmp_path: Path, capsys):
    """JSON that is not an object is an error."""
    syft_stand_in(mocker=mocker, returncode=0, stdout='[]')

    assert generate_sbom.main(['--venv', str(tmp_path)]) == 1
    assert 'syft output was not a JSON object' in capsys.readouterr().err


def test_the_scanned_directory_is_named_without_its_path(mocker: MockerFixture, tmp_path: Path):
    """Two checkouts' scans of the same packages write the same SBOM."""
    outputs = []
    for checkout in ('one', 'two'):
        virtualenv = tmp_path / checkout / '.nox' / 'security-scan-3-14'
        virtualenv.mkdir(parents=True)
        document = syft_document(serial='urn:uuid:1', timestamp='t', package_id='aa')
        document['metadata']['component']['name'] = str(virtualenv)
        syft_stand_in(mocker=mocker, returncode=0, stdout=json.dumps(document))
        output = tmp_path / f'{checkout}.json'
        assert generate_sbom.main(['--venv', str(virtualenv), '--output', str(output)]) == 0
        outputs.append(output.read_bytes())

    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0])['metadata']['component']['name'] == 'security-scan-3-14'


def test_naming_a_document_without_a_scanned_directory_changes_nothing():
    """No metadata, or metadata without a component: left as it is."""
    assert generate_sbom.name_scanned_directory(sbom={}, name='venv') == {}
    assert generate_sbom.name_scanned_directory(sbom={'metadata': {}}, name='venv') == {
        'metadata': {}
    }
