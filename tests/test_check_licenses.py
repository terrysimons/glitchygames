"""Tests for scripts/check_licenses.py: the license policy over small hand-written SBOMs.

Permissive licenses and MPL-2.0 pass; GPL and AGPL are denied; LGPL and anything unrecognized
fail as unreviewed, since Bitmappy's frozen binary bundles what it depends on; the project's own
packages are skipped.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import pytest
from scripts import check_licenses
from scripts.check_licenses import (
    ALLOWLIST,
    DENYLIST,
    EXCEPTIONS,
    PACKAGE_LICENSE_OVERRIDES,
    UNREVIEWED,
    UNSPECIFIED,
    Violation,
    ViolationCategory,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

OWN_PACKAGES = frozenset({'glitchygames', 'bitmappy'})


def library(name: str, *licenses: dict[str, Any], version: str = '1.0') -> dict[str, Any]:
    """Return a CycloneDX library component with these license entries.

    Returns:
        The component.

    """
    return {'type': 'library', 'name': name, 'version': version, 'licenses': list(licenses)}


def spdx(identifier: str) -> dict[str, Any]:
    """Return a license entry naming an SPDX id.

    Returns:
        The entry.

    """
    return {'license': {'id': identifier}}


@pytest.mark.parametrize(
    ('label', 'expected'),
    [
        ('MIT', 'MIT'),
        ('mit license', 'MIT'),
        ('Apache License, Version 2.0', 'Apache-2.0'),
        ('BSD License', 'BSD-3-Clause'),
        ('GPLv3+', 'GPL-3.0-or-later'),
        ('LGPL v2.1', 'LGPL-2.1-only'),
        ('MPL-2.0', 'MPL-2.0'),
        ('Artistic License', 'Artistic-1.0'),
        # OR: an allowlisted arm is elected; otherwise a denied arm names the blocker
        ('GPL-3.0-only OR BSD-3-Clause', 'BSD-3-Clause'),
        ('GPL-3.0-only OR LGPL-3.0-only', 'GPL-3.0-only'),
        ('LGPL-3.0-only OR MPL-2.0', 'MPL-2.0'),
        # AND: every part must pass; the first that does not names the blocker
        ('MIT AND Apache-2.0', 'MIT'),
        ('MPL-2.0 AND MIT', 'MPL-2.0'),
        ('MIT AND (Apache-2.0 OR GPL-2.0-only)', 'MIT'),
        ('(Apache-2.0 OR MIT)', 'Apache-2.0'),
        # Commas are read as OR
        ('MIT, GPL-2.0-only', 'MIT'),
        ('Something, Else', UNREVIEWED),
        ('', UNSPECIFIED),
        (None, UNSPECIFIED),
        ('sha256:1efd6de77e03a0dc2652da8c425085e0284cc0e6eb17e64589643ed21ab0054f', UNSPECIFIED),
        ('UNKNOWN', UNREVIEWED),
        ('Dual License', UNREVIEWED),
    ],
)
def test_licenses_normalize_to_spdx(label, expected):
    """Each spelling and expression normalizes to the identifier the policy decides on."""
    assert check_licenses.normalize_license(label) == expected


def test_parenthesized_groups_survive_the_split():
    """An operator inside parentheses does not split."""
    assert check_licenses.split_preserving_parentheses(
        'MPL-2.0 AND (Apache-2.0 OR MIT)', separator=' AND '
    ) == ['MPL-2.0', '(Apache-2.0 OR MIT)']
    assert check_licenses.split_preserving_parentheses('MIT or BSD', separator=' OR ') == [
        'MIT',
        'BSD',
    ]


@pytest.mark.parametrize(
    ('component', 'expected'),
    [
        (library('a', {'expression': 'MIT OR Apache-2.0'}), 'MIT OR Apache-2.0'),
        (library('a', spdx('BSD-3-Clause')), 'BSD-3-Clause'),
        (library('a', {'license': {'name': 'BSD License'}}), 'BSD License'),
        (library('a', 'not an entry', {'license': 'not an object'}, spdx('ISC')), 'ISC'),
        (library('a', {'license': {}}), ''),
        (library('a'), ''),
        ({'type': 'library', 'name': 'a'}, ''),
    ],
)
def test_the_raw_license_is_the_first_one_named(component, expected):
    """An expression, else an SPDX id, else a name; malformed entries are skipped."""
    assert check_licenses.raw_license(component) == expected


def test_permissive_licenses_pass():
    """Every allowlisted license passes, own packages and non-libraries are not checked."""
    sbom = {
        'components': [
            library('requests', spdx('Apache-2.0')),
            library('six', {'expression': 'MIT'}),
            library('bitmappy'),
            library('glitchygames'),
            {'type': 'file', 'name': 'RECORD'},
            'not a component',
        ]
    }

    assert check_licenses.check_sbom(sbom, own_packages=OWN_PACKAGES) == []


def test_gpl_is_denied_lgpl_and_unknown_are_unreviewed_and_mpl_passes():
    """GPL and AGPL are refused; LGPL, a missing and an unknown license need review; MPL passes.

    The names are made up: a real package may be in EXCEPTIONS, which skips it.
    """
    sbom = {
        'components': [
            library('gpl-tool', spdx('GPL-3.0-or-later'), version='1.38.0'),
            library('agpl-thing', {'license': {'name': 'AGPLv3+'}}),
            library('lgpl-library', {'license': {'name': 'LGPL v2.1'}}, version='2.5.8'),
            library('mpl-library', spdx('MPL-2.0')),
            library('mystery'),
            library('odd', {'license': {'name': 'UNKNOWN'}}),
        ]
    }

    violations = check_licenses.check_sbom(sbom, own_packages=OWN_PACKAGES)

    assert violations == [
        Violation(
            package='gpl-tool',
            version='1.38.0',
            raw_license='GPL-3.0-or-later',
            normalized='GPL-3.0-or-later',
            category=ViolationCategory.DENIED,
        ),
        Violation(
            package='agpl-thing',
            version='1.0',
            raw_license='AGPLv3+',
            normalized='AGPL-3.0-or-later',
            category=ViolationCategory.DENIED,
        ),
        Violation(
            package='lgpl-library',
            version='2.5.8',
            raw_license='LGPL v2.1',
            normalized='LGPL-2.1-only',
            category=ViolationCategory.UNREVIEWED,
        ),
        Violation(
            package='mystery',
            version='1.0',
            raw_license='(none)',
            normalized=UNSPECIFIED,
            category=ViolationCategory.UNREVIEWED,
        ),
        Violation(
            package='odd',
            version='1.0',
            raw_license='UNKNOWN',
            normalized=UNREVIEWED,
            category=ViolationCategory.UNREVIEWED,
        ),
    ]


def test_an_override_replaces_the_sbom_license_and_is_still_checked(mocker: MockerFixture):
    """The pandas digest is replaced by its BSD-3-Clause; an overridden GPL is still denied."""
    mocker.patch.dict(
        PACKAGE_LICENSE_OVERRIDES, {'overridden-gpl-tool': ('GPL-2.0-or-later', 'its LICENSE')}
    )
    sbom = {
        'components': [
            library('pandas', {'license': {'name': 'sha256:1efd'}}),
            library('overridden-gpl-tool'),
        ]
    }

    violations = check_licenses.check_sbom(sbom, own_packages=OWN_PACKAGES)

    assert [(violation.package, violation.category) for violation in violations] == [
        ('overridden-gpl-tool', ViolationCategory.DENIED)
    ]


def test_an_exception_clears_a_package_by_name(mocker: MockerFixture):
    """A package the owner cleared is skipped whatever its license."""
    mocker.patch.dict(EXCEPTIONS, {'yamllint': 'GPL-3.0-or-later, dev tool only (owner, date)'})
    sbom = {'components': [library('yamllint', spdx('GPL-3.0-or-later'))]}

    assert check_licenses.check_sbom(sbom, own_packages=OWN_PACKAGES) == []


def test_the_policy_lists_are_consistent():
    """No license is both allowed and denied; GPL and AGPL are denied; MPL-2.0 is allowed.

    MPL-2.0 by the owner's decision (2026-10-28); LGPL is neither, each LGPL package reviewed by
    name.
    """
    assert ALLOWLIST.isdisjoint(DENYLIST)
    assert {'GPL-2.0-only', 'GPL-3.0-or-later', 'AGPL-3.0-only'} <= DENYLIST
    assert 'MPL-2.0' in ALLOWLIST
    assert not {'LGPL-2.1-only', 'LGPL-3.0-only'} & (ALLOWLIST | DENYLIST)


def test_every_override_names_a_license_the_policy_can_read():
    """An override is a real license with its source, never an unreadable string."""
    for package, (license_string, source) in PACKAGE_LICENSE_OVERRIDES.items():
        assert check_licenses.normalize_license(license_string) not in {UNREVIEWED, UNSPECIFIED}, (
            package
        )
        assert source, package


def test_every_exception_names_its_reviewer_and_date():
    """Each exception ends with '(reviewer, YYYY-MM-DD)', so an auditor can trace it."""
    for package, reason in EXCEPTIONS.items():
        assert re.search(r'\([^,()]+, \d{4}-\d{2}-\d{2}\)$', reason), package


def test_the_project_packages_are_the_engine_and_every_member():
    """The engine and the workspace members are the project's own distributions."""
    own_packages = check_licenses.project_packages(project_root=check_licenses.PROJECT_ROOT)

    assert {'glitchygames', 'bitmappy', 'paddleslap', 'mr-muncher'} <= own_packages


def test_the_report_lists_denied_then_unreviewed_with_remedies():
    """Denied first, each section sorted by package, each with what to do."""
    report = check_licenses.violation_report([
        Violation(
            package='zeta',
            version='2',
            raw_license='MPL-2.0',
            normalized='MPL-2.0',
            category=ViolationCategory.UNREVIEWED,
        ),
        Violation(
            package='Alpha',
            version='1',
            raw_license='(none)',
            normalized=UNSPECIFIED,
            category=ViolationCategory.UNREVIEWED,
        ),
        Violation(
            package='yamllint',
            version='1.38.0',
            raw_license='GPL-3.0-or-later',
            normalized='GPL-3.0-or-later',
            category=ViolationCategory.DENIED,
        ),
    ])

    lines = report.splitlines()
    assert lines[0] == 'License policy violations: DENIED:'
    assert lines[1] == "  yamllint 1.38.0: 'GPL-3.0-or-later' -> GPL-3.0-or-later"
    unreviewed_start = lines.index('License policy violations: UNREVIEWED:')
    assert lines[unreviewed_start + 1] == "  Alpha 1: '(none)' -> UNSPECIFIED"
    assert lines[unreviewed_start + 2] == "  zeta 2: 'MPL-2.0' -> MPL-2.0"
    assert 'PACKAGE_LICENSE_OVERRIDES' in report
    assert not check_licenses.violation_report([])


def write_sbom(*, path: Path, components: list[Any]) -> Path:
    """Write an SBOM with these components.

    Returns:
        Its path.

    """
    path.write_text(json.dumps({'components': components}), encoding='utf-8')
    return path


def test_main_passes_a_permissive_sbom(tmp_path: Path, capsys):
    """Exit 0 and say how many libraries were checked."""
    sbom = write_sbom(
        path=tmp_path / 'sbom.json',
        components=[library('requests', spdx('Apache-2.0')), library('glitchygames')],
    )

    assert check_licenses.main(['--sbom', str(sbom)]) == 0
    assert capsys.readouterr().out == 'License policy OK: sbom.json, 2 libraries\n'


def test_main_fails_on_a_violation(tmp_path: Path, capsys):
    """Exit 1 with the report on stderr."""
    sbom = write_sbom(
        path=tmp_path / 'sbom.json', components=[library('yamllint', spdx('GPL-3.0-or-later'))]
    )

    assert check_licenses.main(['--sbom', str(sbom)]) == 1
    error = capsys.readouterr().err
    assert 'yamllint 1.0' in error
    assert error.endswith('1 package(s) fail the license policy\n')


def test_main_fails_without_an_sbom(tmp_path: Path, capsys):
    """A missing SBOM is an error, never a pass."""
    assert check_licenses.main(['--sbom', str(tmp_path / 'missing.json')]) == 1
    assert 'No SBOM at' in capsys.readouterr().err


@pytest.mark.parametrize(
    ('content', 'message'), [('not json', 'is not JSON'), ('[]', 'is not a JSON object')]
)
def test_main_fails_on_an_unreadable_sbom(tmp_path: Path, capsys, content, message):
    """An SBOM that is not a JSON object is an error."""
    sbom = tmp_path / 'sbom.json'
    sbom.write_text(content, encoding='utf-8')

    assert check_licenses.main(['--sbom', str(sbom)]) == 1
    assert message in capsys.readouterr().err
