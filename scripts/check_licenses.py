"""Enforce the project's license policy against the committed SBOM, docs/sbom.cyclonedx.json.

Adapted from exoneris scripts/check_licenses.py (the owner, 2026-10-28: "use the audit script
there for license pinning"). What differs here: one SBOM, not exoneris's three (no sidecars);
and the policy. exoneris is proprietary and ships wheels and images; glitchygames is
BSD-3-Clause, and Bitmappy also ships as a frozen PyInstaller binary that bundles its
dependencies (bitmappy.spec), so a bundled dependency's license travels inside that binary.
Hence exoneris's allowlisted weak copyleft (LGPL, MPL) is not allowlisted here: an LGPL library
frozen into one file asks for relinking rights the binary does not give, and MPL asks for a
source offer for its files; each is the owner's decision, so it fails as unreviewed until made.

``scripts/generate_sbom.py`` writes the SBOM (``nox -s security-scan`` runs both). Each library
component's license string is normalized to an SPDX identifier and checked against:

- ``ALLOWLIST``: permissive licenses (attribution at most), accepted without review.
- ``DENYLIST``: strong copyleft (GPL, AGPL), refused.
- ``EXCEPTIONS``: packages the owner reviewed and cleared by name, with reviewer and date.

Anything else, LGPL and MPL included, is unreviewed and fails: a new package with unclear
license metadata surfaces to a reviewer rather than slipping in. Exits non-zero on any violation.

Usage:
    python -m scripts.check_licenses [--sbom docs/sbom.cyclonedx.json]
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from scripts.workspace_packages import ENGINE_PACKAGE, workspace_members

if TYPE_CHECKING:
    from collections.abc import Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SBOM_PATH = PROJECT_ROOT / 'docs' / 'sbom.cyclonedx.json'

# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

ALLOWLIST: frozenset[str] = frozenset({
    # Permissive: attribution at most, no source or relinking obligation, so they may be frozen
    # into the Bitmappy binary as they are (their notices travel with it)
    'MIT',
    # MIT No Attribution: MIT without the attribution requirement (https://spdx.org/licenses/MIT-0.html)
    'MIT-0',
    'Apache-2.0',
    # The LLVM exception only adds permissions to Apache-2.0 (it waives the binary attribution
    # requirements; https://spdx.org/licenses/LLVM-exception.html)
    'Apache-2.0 WITH LLVM-exception',
    'BSD-2-Clause',
    'BSD-3-Clause',
    '0BSD',
    'ISC',
    'PSF-2.0',
    'Python-2.0',
    'Unlicense',
    'CC0-1.0',
    'Zlib',
    # Boost Software License 1.0: attribution in source redistribution only, none for binaries
    # (https://spdx.org/licenses/BSL-1.0.html). Not the Business Source License (BUSL-1.1)
    'BSL-1.0',
    # Zope Public License 2.1: permissive, BSD-style
    'ZPL-2.1',
    # Mozilla Public License 2.0: file-level copyleft; using or bundling an unmodified package
    # asks only for its notice and a pointer to its source (the owner, 2026-10-28: "Allow
    # MPL-2.0: it asks only for a notice and a pointer to the source"). certifi and tqdm at
    # runtime; pathspec and hypothesis in development
    'MPL-2.0',
})
"""Licenses accepted without per-package review (SPDX identifiers, https://spdx.org/licenses/)."""

DENYLIST: frozenset[str] = frozenset({
    # Strong copyleft: bundled into the Bitmappy binary, these would put the binary under their
    # terms, which a BSD-3-Clause project cannot accept
    'GPL-2.0-only',
    'GPL-2.0-or-later',
    'GPL-3.0-only',
    'GPL-3.0-or-later',
    'AGPL-3.0-only',
    'AGPL-3.0-or-later',
})
"""Licenses refused outright (the owner, 2026-10-28: deny GPL and AGPL)."""

EXCEPTIONS: dict[str, str] = {
    # Format: 'package-name': 'license, why it is acceptable here (reviewer, date)'
    #
    # Only the owner adds entries: a package the policy would reject, reviewed and cleared by
    # name (for example a GPL tool run only in development and never bundled into a wheel or
    # the Bitmappy binary). Each names its reviewer and date, so an auditor can trace it
    'pygame-ce': (
        'LGPL-2.1, bundled into the Bitmappy binary. Acceptable because the project ships its '
        'whole source tree publicly on GitHub, so anyone can rebuild the binary against another '
        'pygame-ce (the owner: "we\'re good because we also ship the source tree on github '
        'publicly"; Terry Simons, 2026-10-28)'
    ),
    'pyinstaller-hooks-contrib': (
        'GPL-2.0-or-later AND Apache-2.0, split by file (its LICENSE): the build hooks are '
        'GPL-2.0-or-later and run inside PyInstaller at build time, never bundled; the runtime '
        'hooks (_pyinstaller_hooks_contrib/rthooks), the only files bundled into the Bitmappy '
        'binary, are Apache-2.0. What ships is Apache-2.0 (the owner: "can we opt for '
        'Apache-2.0 for pyinstaller-hooks-contrib"; Terry Simons, 2026-10-28)'
    ),
    'text-unidecode': (
        'GPL-2.0-or-later OR Artistic-1.0 (its LICENSE: "either GPL or GPLv2+ ... or Artistic '
        'License"), at runtime through cookiecutter and python-slugify. The Artistic License is '
        'elected: bundled unmodified, it asks only that its notice be kept, and the GPL arm never '
        'applies (the owner: "Artistic"; Terry Simons, 2026-10-28)'
    ),
}
"""Per-package exceptions to the allowlist and denylist, each reviewed."""

PACKAGE_LICENSE_OVERRIDES: dict[str, tuple[str, str]] = {
    # Format: 'package-name': ('SPDX id', 'where the license was read')
    #
    # For packages whose SBOM entry has no license (syft reads the License and
    # License-Expression metadata fields, not trove classifiers or LICENSE files) though the
    # installed distribution declares one. Not a bypass: the override goes through the same
    # allowlist and denylist as a license from the SBOM. Each was read from the distribution
    # installed from uv.lock (its dist-info METADATA classifier or LICENSE file), 2026-10-28.
    # Keep it alphabetical.
    'aisuite': ('MIT', 'dist-info licenses/LICENSE: MIT License'),
    'arrow': ('Apache-2.0', 'classifier: License :: OSI Approved :: Apache Software License'),
    'basedpyright': ('MIT', 'classifier: License :: OSI Approved :: MIT License'),
    'colorama': ('BSD-3-Clause', 'dist-info licenses/LICENSE.txt: the three-clause BSD text'),
    'cookiecutter': ('BSD-3-Clause', 'dist-info licenses/LICENSE: the three-clause BSD text'),
    # Three licenses at the user's choice (dist-info licenses/LICENSE.txt): GPL-3.0, a
    # BSD-style license (LICENSE-bsd.txt, the three-clause text) or the original cython-hidapi
    # license. Written as the OR it is; the OR rule elects the allowlisted arm
    'hidapi': (
        'GPL-3.0-only OR BSD-3-Clause',
        'dist-info licenses/LICENSE.txt: GPL-3.0, BSD-style or the original license',
    ),
    'jinja2': ('BSD-3-Clause', 'dist-info licenses/LICENSE.txt: the three-clause BSD text'),
    # License: UNKNOWN, no LICENSE file; the classifier names BSD without its variant (both
    # two- and three-clause are allowlisted)
    'lomond': ('BSD-3-Clause', 'classifier: License :: OSI Approved :: BSD License'),
    'markdown-it-py': ('MIT', 'classifier: License :: OSI Approved :: MIT License'),
    'mergedeep': ('MIT', 'classifier: License :: OSI Approved :: MIT License; License: UNKNOWN'),
    'mistralai': ('Apache-2.0', 'dist-info licenses/LICENSE: Apache License, Version 2.0'),
    'nodejs-wheel-binaries': ('MIT', 'classifier: License :: OSI Approved :: MIT License'),
    # syft reports a sha256 digest in the license slot; METADATA says License: BSD 3-Clause
    'pandas': ('BSD-3-Clause', 'METADATA License: BSD 3-Clause License'),
    'pathspec': ('MPL-2.0', 'classifier: License :: OSI Approved :: Mozilla Public License 2.0'),
    # Its hooks are GPL-2.0-or-later (run by PyInstaller at build time), its runtime hooks,
    # which are bundled into a frozen binary, Apache-2.0 (dist-info licenses/LICENSE): both
    # apply, so AND
    'pyinstaller-hooks-contrib': (
        'GPL-2.0-or-later AND Apache-2.0',
        'dist-info licenses/LICENSE: hooks GPL-2.0-or-later, runtime hooks Apache-2.0',
    ),
    # License: Dual License; classifiers BSD and Apache (LICENSE: Apache-2.0 for contributions
    # since 2017-12-01, BSD-3-Clause before)
    'python-dateutil': (
        'Apache-2.0 OR BSD-3-Clause',
        'classifiers: BSD License, Apache Software License',
    ),
    'tokenizers': ('Apache-2.0', 'classifier: License :: OSI Approved :: Apache Software License'),
    'ty': ('MIT', 'classifier: License :: OSI Approved :: MIT License'),
}
"""License strings the SBOM should have carried, by package (each from installed metadata)."""

# ---------------------------------------------------------------------------
# License normalization
# ---------------------------------------------------------------------------

# Common non-SPDX spellings mapped to SPDX identifiers, keyed in lower case (adapted from
# exoneris scripts/check_licenses.py's _NORMALIZE_MAP). The LGPL and GPL spellings are kept so a
# report names the license plainly: GPL lands on the denylist, LGPL is unreviewed
_NORMALIZE_MAP: dict[str, str] = {
    # MIT
    'mit': 'MIT',
    'mit license': 'MIT',
    'the mit license': 'MIT',
    'the mit license (mit)': 'MIT',
    'mit-cmu': 'MIT',
    'mit-0': 'MIT-0',
    'mit no attribution': 'MIT-0',
    # Apache 2.0
    'apache': 'Apache-2.0',
    'apache-2.0': 'Apache-2.0',
    'apache 2.0': 'Apache-2.0',
    'apache 2': 'Apache-2.0',
    'apache v2.0': 'Apache-2.0',
    'apache-2.0 license': 'Apache-2.0',
    'apache 2.0 license': 'Apache-2.0',
    'apache license 2.0': 'Apache-2.0',
    'apache license, version 2.0': 'Apache-2.0',
    'apache license version 2.0': 'Apache-2.0',
    'apache software license': 'Apache-2.0',
    'apache software license 2.0': 'Apache-2.0',
    'apache software license, version 2.0': 'Apache-2.0',
    # BSD
    'bsd': 'BSD-3-Clause',
    'bsd license': 'BSD-3-Clause',
    'bsd-3-clause': 'BSD-3-Clause',
    '3-clause bsd license': 'BSD-3-Clause',
    'new bsd license': 'BSD-3-Clause',
    'bsd 3-clause license': 'BSD-3-Clause',
    'bsd-2-clause': 'BSD-2-Clause',
    '2-clause bsd license': 'BSD-2-Clause',
    'simplified bsd license': 'BSD-2-Clause',
    'bsd-0-clause': '0BSD',
    '0-clause bsd license': '0BSD',
    # Python
    'psf-2.0': 'PSF-2.0',
    'psf': 'PSF-2.0',
    'psfl': 'PSF-2.0',
    'python software foundation license': 'PSF-2.0',
    'python-2.0': 'Python-2.0',
    'cnri-python': 'Python-2.0',
    # Zope
    'zpl-2.1': 'ZPL-2.1',
    'zope public license': 'ZPL-2.1',
    # ISC
    'isc': 'ISC',
    'isc license': 'ISC',
    'isc license (iscl)': 'ISC',
    # Public domain
    'unlicense': 'Unlicense',
    'the unlicense (unlicense)': 'Unlicense',
    'public domain': 'Unlicense',
    'cc0-1.0': 'CC0-1.0',
    # MPL (unreviewed here)
    'mpl-2.0': 'MPL-2.0',
    'mozilla public license 2.0': 'MPL-2.0',
    'mozilla public license 2.0 (mpl 2.0)': 'MPL-2.0',
    # Artistic (unreviewed here)
    'artistic license': 'Artistic-1.0',
    'artistic-1.0': 'Artistic-1.0',
    # LGPL (unreviewed here)
    'lgpl v2.1': 'LGPL-2.1-only',
    'lgpl-3.0-only': 'LGPL-3.0-only',
    'lgpl-3.0-or-later': 'LGPL-3.0-or-later',
    'lgpl-2.1-only': 'LGPL-2.1-only',
    'lgpl-2.1-or-later': 'LGPL-2.1-or-later',
    'lgplv2+': 'LGPL-2.1-or-later',
    'lgplv3': 'LGPL-3.0-only',
    'lgplv3+': 'LGPL-3.0-or-later',
    'gnu lesser general public license v2 or later (lgplv2+)': 'LGPL-2.1-or-later',
    'gnu lesser general public license v3 (lgplv3)': 'LGPL-3.0-only',
    'gnu lesser general public license v3 or later (lgplv3+)': 'LGPL-3.0-or-later',
    # GPL, refused by the denylist
    'gpl-2.0': 'GPL-2.0-only',
    'gpl-3.0': 'GPL-3.0-only',
    'gplv2': 'GPL-2.0-only',
    'gplv3': 'GPL-3.0-only',
    'gplv2+': 'GPL-2.0-or-later',
    'gplv3+': 'GPL-3.0-or-later',
    'agpl-3.0': 'AGPL-3.0-only',
    'agplv3': 'AGPL-3.0-only',
    'agplv3+': 'AGPL-3.0-or-later',
    'gnu general public license v2 (gplv2)': 'GPL-2.0-only',
    'gnu general public license v3 (gplv3)': 'GPL-3.0-only',
    'gnu general public license v2 or later (gplv2+)': 'GPL-2.0-or-later',
    'gnu general public license v3 or later (gplv3+)': 'GPL-3.0-or-later',
    'gnu affero general public license v3': 'AGPL-3.0-only',
    'gnu affero general public license v3 or later (agplv3+)': 'AGPL-3.0-or-later',
    # Zlib
    'zlib': 'Zlib',
    'zlib/libpng license': 'Zlib',
}

UNSPECIFIED = 'UNSPECIFIED'
UNREVIEWED = 'UNREVIEWED'


def json_object(value: object) -> dict[str, Any] | None:
    """Return a parsed JSON value as an object, or None when it is not one.

    Kept apart from scripts/generate_sbom.py's (as exoneris keeps its two scripts), so neither
    script depends on the other.

    Returns:
        The value, typed, or None.

    """
    return cast('dict[str, Any]', value) if isinstance(value, dict) else None


def json_objects(value: object) -> list[dict[str, Any]]:
    """Return the objects in a parsed JSON array (none when it is not an array).

    Returns:
        The array's objects, in order; its other entries are skipped.

    """
    entries = cast('list[object]', value) if isinstance(value, list) else []
    return [entry for entry in map(json_object, entries) if entry is not None]


def library_components(sbom: dict[str, Any]) -> list[dict[str, Any]]:
    """Return an SBOM's library components (``type: library``), in order.

    Returns:
        The components.

    """
    return [
        component
        for component in json_objects(sbom.get('components'))
        if component.get('type') == 'library'
    ]


def _normalize_atom(label: str) -> str:
    """Normalize one license atom (no ``OR``/``AND``).

    Returns:
        Its SPDX identifier, ``UNSPECIFIED`` when empty, or ``UNREVIEWED``.

    """
    stripped = label.strip()
    if not stripped:
        return UNSPECIFIED
    # A parenthesized group left whole by the split: normalize its inside
    if stripped.startswith('(') and stripped.endswith(')'):
        return normalize_license(stripped[1:-1])
    if stripped in ALLOWLIST or stripped in DENYLIST:
        return stripped
    return _NORMALIZE_MAP.get(stripped.lower(), UNREVIEWED)


def _resolve_or_atoms(normalized_atoms: list[str]) -> str:
    """Pick the atom an ``OR`` (or comma-separated) expression stands for.

    Any allowlisted atom passes (the recipient elects it); otherwise a denylisted atom, so the
    report names the blocker; otherwise the first atom.

    Returns:
        The representative atom.

    """
    for atom in normalized_atoms:
        if atom in ALLOWLIST:
            return atom
    for atom in normalized_atoms:
        if atom in DENYLIST:
            return atom
    return normalized_atoms[0] if normalized_atoms else UNREVIEWED


def _resolve_and_atoms(normalized_atoms: list[str]) -> str:
    """Pick the atom an ``AND`` expression stands for: the first not allowlisted, else the first.

    Returns:
        The representative atom.

    """
    for atom in normalized_atoms:
        if atom not in ALLOWLIST:
            return atom
    return normalized_atoms[0] if normalized_atoms else UNREVIEWED


def split_preserving_parentheses(text: str, *, separator: str) -> list[str]:
    """Split on a separator (case-insensitive) outside parentheses only.

    ``'MPL-2.0 AND (Apache-2.0 OR MIT)'`` split on ``' AND '`` gives ``['MPL-2.0',
    '(Apache-2.0 OR MIT)']``.

    Args:
        text: The expression.
        separator: The operator with its spaces (``' OR '``).

    Returns:
        The parts, stripped, in their original case.

    """
    parts: list[str] = []
    depth = 0
    buffer: list[str] = []
    separator_upper = separator.upper()
    index = 0
    while index < len(text):
        character = text[index]
        if character == '(':
            depth += 1
        elif character == ')':
            depth -= 1
        elif depth == 0 and text[index : index + len(separator)].upper() == separator_upper:
            parts.append(''.join(buffer).strip())
            buffer = []
            index += len(separator)
            continue
        buffer.append(character)
        index += 1
    if buffer:
        parts.append(''.join(buffer).strip())
    return parts


def normalize_license(label: str | None) -> str:
    """Normalize a raw license string to an SPDX identifier.

    ``A OR B`` passes when either is allowlisted, ``A AND B`` only when both are; fully
    parenthesized groups recurse, and a comma-separated list is read as ``OR`` (as pip-licenses
    renders multi-license packages). Mixed operators without parentheses are not guessed at.

    Args:
        label: The raw string from the SBOM (or an override).

    Returns:
        The SPDX identifier, ``UNSPECIFIED`` when missing (or a sha256 digest, which syft
        reports when a license field is malformed), or ``UNREVIEWED``.

    """
    stripped = label.strip() if label else ''
    if not stripped or stripped.startswith('sha256:'):
        return UNSPECIFIED
    # The whole string first: 'Apache License, Version 2.0' holds a comma but is one license
    direct = _normalize_atom(stripped)
    if direct != UNREVIEWED:
        return direct
    upper = stripped.upper()
    if ',' in stripped and ' OR ' not in upper and ' AND ' not in upper:
        comma_atoms = [atom.strip() for atom in stripped.split(',') if atom.strip()]
        if len(comma_atoms) > 1:
            return _resolve_or_atoms([_normalize_atom(atom) for atom in comma_atoms])
    or_atoms = split_preserving_parentheses(stripped, separator=' OR ')
    if len(or_atoms) > 1:
        return _resolve_or_atoms([_normalize_atom(atom) for atom in or_atoms])
    and_atoms = split_preserving_parentheses(stripped, separator=' AND ')
    if len(and_atoms) > 1:
        return _resolve_and_atoms([_normalize_atom(atom) for atom in and_atoms])
    return UNREVIEWED


def raw_license(component: dict[str, Any]) -> str:
    """Return a CycloneDX component's license string: its expression, SPDX id or name.

    Args:
        component: A CycloneDX component.

    Returns:
        The first license found, or ``''``.

    """
    for entry in json_objects(component.get('licenses')):
        if expression := entry.get('expression'):
            return str(expression)
        information = json_object(entry.get('license'))
        if information is None:
            continue
        if spdx_id := information.get('id'):
            return str(spdx_id)
        if name := information.get('name'):
            return str(name)
    return ''


# ---------------------------------------------------------------------------
# Policy check
# ---------------------------------------------------------------------------


class ViolationCategory(enum.StrEnum):
    """Why a package failed the policy."""

    DENIED = 'denied'
    UNREVIEWED = 'unreviewed'


@dataclasses.dataclass(frozen=True)
class Violation:
    """One package that failed the license policy."""

    package: str
    version: str
    raw_license: str
    normalized: str
    category: ViolationCategory


def project_packages(*, project_root: Path) -> frozenset[str]:
    """Return this repository's own distributions: the engine and every workspace member.

    They are in the SBOM because they are installed, but the policy is about what they depend
    on; their own license is the project's.

    Args:
        project_root: The repository.

    Returns:
        The distribution names.

    """
    members = workspace_members(project_root=project_root)
    return frozenset({ENGINE_PACKAGE, *(member.distribution for member in members)})


def check_sbom(sbom: dict[str, Any], *, own_packages: frozenset[str]) -> list[Violation]:
    """Return every library component that violates the license policy.

    Args:
        sbom: A CycloneDX document.
        own_packages: The project's own distributions, skipped.

    Returns:
        The violations, in the SBOM's order.

    """
    violations: list[Violation] = []
    for component in library_components(sbom):
        name = str(component.get('name', ''))
        if name in own_packages:
            continue
        override = PACKAGE_LICENSE_OVERRIDES.get(name)
        license_string = override[0] if override is not None else raw_license(component)
        normalized = normalize_license(license_string)
        if normalized in ALLOWLIST or name in EXCEPTIONS:
            continue
        violations.append(
            Violation(
                package=name,
                version=str(component.get('version', '')),
                raw_license=license_string or '(none)',
                normalized=normalized,
                category=(
                    ViolationCategory.DENIED
                    if normalized in DENYLIST
                    else ViolationCategory.UNREVIEWED
                ),
            )
        )
    return violations


def violation_report(violations: list[Violation]) -> str:
    """Return the human-readable report of the violations, denied first.

    Args:
        violations: What ``check_sbom`` found.

    Returns:
        The report's text (empty when there are none).

    """
    lines: list[str] = []
    for category, heading, remedies in (
        (
            ViolationCategory.DENIED,
            'License policy violations: DENIED',
            ['Remove the dependency, or the owner clears it in EXCEPTIONS (reviewer, date).'],
        ),
        (
            ViolationCategory.UNREVIEWED,
            'License policy violations: UNREVIEWED',
            [
                '1. A spelling of an allowlisted license: add it to _NORMALIZE_MAP.',
                '2. No license in the SBOM but one in the installed metadata: add it to',
                '   PACKAGE_LICENSE_OVERRIDES, naming where it was read.',
                '3. Otherwise the owner reviews it: EXCEPTIONS (reviewer, date), or remove it.',
            ],
        ),
    ):
        found = sorted(
            (violation for violation in violations if violation.category is category),
            key=lambda violation: violation.package.lower(),
        )
        if not found:
            continue
        lines.append(f'{heading}:')
        lines.extend(
            f'  {violation.package} {violation.version}: {violation.raw_license!r} -> '
            f'{violation.normalized}'
            for violation in found
        )
        lines.extend(f'  {remedy}' for remedy in remedies)
        lines.append('')
    return '\n'.join(lines)


def main(arguments: Sequence[str] | None = None) -> int:
    """Check the SBOM against the policy and report.

    Args:
        arguments: The command line (None: ``sys.argv[1:]``).

    Returns:
        The exit status: 0 when every library passes, 1 otherwise (or no readable SBOM).

    """
    parser = argparse.ArgumentParser(description='Check the SBOM against the license policy.')
    parser.add_argument(
        '--sbom', type=Path, default=SBOM_PATH, help=f'the SBOM to check (default {SBOM_PATH})'
    )
    options = parser.parse_args(arguments)
    sbom_path: Path = options.sbom
    if not sbom_path.is_file():
        sys.stderr.write(
            f'No SBOM at {sbom_path}: run nox -s security-scan (scripts/generate_sbom.py) first\n'
        )
        return 1
    try:
        sbom = json_object(json.loads(sbom_path.read_text(encoding='utf-8')))
    except json.JSONDecodeError as error:
        sys.stderr.write(f'The SBOM at {sbom_path} is not JSON: {error}\n')
        return 1
    if sbom is None:
        sys.stderr.write(f'The SBOM at {sbom_path} is not a JSON object\n')
        return 1
    violations = check_sbom(sbom, own_packages=project_packages(project_root=PROJECT_ROOT))
    if violations:
        sys.stderr.write(violation_report(violations))
        sys.stderr.write(f'{len(violations)} package(s) fail the license policy\n')
        return 1
    library_count = len(library_components(sbom))
    sys.stdout.write(f'License policy OK: {sbom_path.name}, {library_count} libraries\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
