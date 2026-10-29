"""Regenerate the committed CycloneDX SBOM, docs/sbom.cyclonedx.json, from uv.lock.

Adapted from exoneris scripts/generate_sbom.py (the owner's project, 2026-10-28: "swap syft/grype
for safety and pip-audit", wired the way exoneris does it). What differs here: one lock file, not
exoneris's three virtualenvs (it has diarization sidecars with venvs of their own; this project
has none), and no Markdown rendering beside the JSON.

``syft`` reads ``uv.lock`` (its ``python-package-cataloger`` knows uv's lock format), so the SBOM
lists every package the lock pins, for every platform, Python version, extra and dependency group
(``uv sync --all-extras --all-groups --all-packages`` installs a platform's share of them). The
SBOM is therefore the same on macOS, Linux and Windows and on every Python version: it depends on
the lock alone, not on the virtualenv that happens to be installed (plans/future-work.md, "The
SBOM's scope and platform", 2026-10-28; until then syft scanned the installed macOS virtualenv,
and a scan on Linux or Windows reported drift).

The lock records no licenses, and syft's own license lookup for Python packages is a PyPI query
(``python.search-remote-licenses``: the network, never offline), so each component's license is
added here, from one of two deterministic sources:

1. ``scripts/check_licenses.py``'s ``PACKAGE_LICENSE_OVERRIDES``, the reviewed table, which wins.
2. Otherwise the installed distribution's metadata in the environment running this script (the
   nox session's virtualenv, or the development one): its ``License-Expression``, else a
   one-line ``License`` field. Its version must equal the lock's, or the run fails naming it.

Only packages the lock installs on every supported platform and Python version
(``SUPPORTED_ENVIRONMENTS``, evaluated from the lock's dependency markers) may take their license
from metadata: a package installed only somewhere (pywin32 on Windows, macholib on macOS, tomli
before Python 3.15) must have an override, or the run fails naming it, on every platform alike.
So no platform writes a license another platform cannot read. A package installed everywhere but
missing here fails too (the environment is not synced). That one version's metadata is the same
on every platform is what the wheels of one release give: checked 2026-10-28, the SBOM written in
CircleCI's Linux image (cimg/python, amd64, Python 3.14) was byte-identical to macOS's (arm64);
Windows is not checked yet.

The fields CycloneDX tools regenerate on every run (``metadata.timestamp``, ``serialNumber``, the
random ``bom-ref`` values, syft's ``?package-id=`` purl suffix, the lock file component with its
absolute path, and the lock's digest, which a checkout with other line endings changes) are
stripped, so the written file is a function of the dependency set and the license sources alone:
two runs write the same bytes, and a ``git diff`` of the file means the dependencies (or a
license) changed. ``nox -s security-scan`` fails when the regenerated file differs from the
committed one (its drift check), so commit the regenerated SBOM with the uv.lock change that
caused it.

Exit codes: 0 when the SBOM was written; 1 when syft is missing, the lock does not exist, syft
failed or its output was not JSON, or a component's license has no deterministic source.

Usage:
    python -m scripts.generate_sbom [--lock uv.lock] [--output docs/sbom.cyclonedx.json]
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs syft, never a shell
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from packaging.markers import Marker
from packaging.utils import canonicalize_name
from packaging.version import Version

from scripts.check_licenses import PACKAGE_LICENSE_OVERRIDES

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SBOM_PATH = PROJECT_ROOT / 'docs' / 'sbom.cyclonedx.json'
LOCK_PATH = PROJECT_ROOT / 'uv.lock'


def _environment(
    *, sys_platform: str, platform_system: str, os_name: str, machine: str, python: str
) -> dict[str, str]:
    """Return a complete PEP 508 marker environment (every key, so none comes from this host).

    Returns:
        The environment.

    """
    return {
        'implementation_name': 'cpython',
        'implementation_version': python,
        'os_name': os_name,
        'platform_machine': machine,
        'platform_python_implementation': 'CPython',
        'platform_release': '',
        'platform_system': platform_system,
        'platform_version': '',
        'python_full_version': python,
        'python_version': '.'.join(python.split('.')[:2]),
        'sys_platform': sys_platform,
        'extra': '',
    }


# The platforms and Python versions the project is developed and tested on (CircleCI: macOS
# arm64, Linux amd64 and Windows amd64; Python 3.14, and 3.15 on macOS and Linux). A package the
# lock installs in all of them may take its license from installed metadata; any other needs a
# PACKAGE_LICENSE_OVERRIDES entry. Emscripten (the browser builds) is not among them: its
# packages, like any other platform's, need an override
SUPPORTED_ENVIRONMENTS: tuple[dict[str, str], ...] = tuple(
    _environment(
        sys_platform=sys_platform,
        platform_system=platform_system,
        os_name=os_name,
        machine=machine,
        python=python,
    )
    for sys_platform, platform_system, os_name, machine in (
        ('darwin', 'Darwin', 'posix', 'arm64'),
        ('linux', 'Linux', 'posix', 'x86_64'),
        ('win32', 'Windows', 'nt', 'AMD64'),
    )
    for python in ('3.14.0', '3.15.0')
)


class SyftError(RuntimeError):
    """syft failed, or wrote something that is not a JSON document."""


class LicenseSourceError(RuntimeError):
    """A component's license has no deterministic source (see the module docstring)."""


def json_object(value: object) -> dict[str, Any] | None:
    """Return a parsed JSON value as an object, or None when it is not one.

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


def json_strings(value: object) -> list[str]:
    """Return the strings in a parsed JSON array (none when it is not an array).

    Returns:
        The array's strings, in order; its other entries are skipped.

    """
    entries = cast('list[object]', value) if isinstance(value, list) else []
    return [entry for entry in entries if isinstance(entry, str)]


def strip_package_id(purl: str) -> str:
    """Return a purl without its query (syft's per-run ``?package-id=...`` suffix).

    Args:
        purl: A package URL.

    Returns:
        Everything before the first ``?``.

    """
    return purl.partition('?')[0]


def _kept_purls_by_package_name(components: list[dict[str, Any]]) -> dict[str, str]:
    """Map each kept component's purl without its version (``pkg:pypi/zipp``) to its purl.

    Returns:
        The map, from the components in order (a later duplicate name wins).

    """
    kept_by_package_name: dict[str, str] = {}
    for component in components:
        purl = component.get('purl')
        if isinstance(purl, str):
            stripped = strip_package_id(purl)
            kept_by_package_name[stripped.partition('@')[0]] = stripped
    return kept_by_package_name


def _canonical_dependencies(
    dependencies: list[dict[str, Any]], *, kept_by_package_name: dict[str, str]
) -> list[dict[str, Any]]:
    """Return the dependency entries anonymous, canonical, de-duplicated and sorted.

    Each entry loses its ``ref`` (a random bom-ref); each ``dependsOn`` purl loses its query and
    is mapped by package name to the kept component's purl, and a purl whose package was not kept
    is dropped. Anonymous
    entries are then told apart only by ``dependsOn``, and syft emits them in no stable order,
    so they are de-duplicated and sorted by it.

    Returns:
        The canonical entries.

    """
    seen: set[tuple[str, ...]] = set()
    canonical_entries: list[dict[str, Any]] = []
    for dependency in dependencies:
        dependency.pop('ref', None)
        canonical_purls = {
            canonical_purl
            for entry in json_strings(dependency.get('dependsOn'))
            if (
                canonical_purl := kept_by_package_name.get(
                    strip_package_id(entry).partition('@')[0]
                )
            )
            is not None
        }
        canonical_depends_on = sorted(canonical_purls)
        dependency['dependsOn'] = canonical_depends_on
        key = tuple(canonical_depends_on)
        if key in seen:
            continue
        seen.add(key)
        canonical_entries.append(dependency)
    canonical_entries.sort(key=lambda entry: tuple(json_strings(entry['dependsOn'])))
    return canonical_entries


def strip_volatile_fields(sbom: dict[str, Any]) -> dict[str, Any]:
    """Drop what CycloneDX tools regenerate on every run, so the SBOM depends on packages alone.

    Removed: ``serialNumber``, ``metadata.timestamp``, the scanned lock's ``bom-ref`` and digest
    (``metadata.component``'s ``version``: ``sha256:...`` of the file's bytes, which a checkout
    with CRLF line endings changes), every ``type: file`` component (the lock itself, named by
    its absolute path), each component's ``bom-ref`` and purl query, and each dependency entry's
    ``ref``. Kept: ``metadata.tools`` (syft's version: an SBOM written by another syft differs,
    which is worth seeing).

    Args:
        sbom: A parsed CycloneDX document; changed in place.

    Returns:
        The same document.

    """
    sbom.pop('serialNumber', None)
    metadata = json_object(sbom.get('metadata'))
    if metadata is not None:
        metadata.pop('timestamp', None)
        scanned_component = json_object(metadata.get('component'))
        if scanned_component is not None:
            scanned_component.pop('bom-ref', None)
            scanned_component.pop('version', None)
    kept_components: list[dict[str, Any]] = []
    if 'components' in sbom:
        kept_components = [
            component
            for component in json_objects(sbom['components'])
            if component.get('type') != 'file'
        ]
        for component in kept_components:
            component.pop('bom-ref', None)
            purl = component.get('purl')
            if isinstance(purl, str):
                component['purl'] = strip_package_id(purl)
        sbom['components'] = kept_components
    if 'dependencies' in sbom:
        sbom['dependencies'] = _canonical_dependencies(
            json_objects(sbom['dependencies']),
            kept_by_package_name=_kept_purls_by_package_name(kept_components),
        )
    return sbom


def name_scanned_lock(*, sbom: dict[str, Any], name: str) -> dict[str, Any]:
    """Name the scanned lock (``metadata.component``) by its file name, never by its path.

    A path differs from checkout to checkout (``/Users/<user>/<checkout>/uv.lock`` here,
    CircleCI's project directory there), so the committed SBOM would differ between machines
    with the same lock.

    Args:
        sbom: A CycloneDX document; changed in place.
        name: The name to give it (the lock's file name).

    Returns:
        The same document.

    """
    metadata = json_object(sbom.get('metadata'))
    scanned_component = json_object(metadata.get('component')) if metadata is not None else None
    if scanned_component is not None:
        scanned_component['name'] = name
    return sbom


def scan_lock(*, lock: Path) -> dict[str, Any]:
    """Run syft over a uv lock file and return its CycloneDX document.

    ``--override-default-catalogers python`` keeps syft to its Python catalogers (the one that
    reads ``uv.lock`` among them).

    Args:
        lock: The lock file.

    Returns:
        The parsed document, unstripped.

    Raises:
        SyftError: syft exited non-zero, or its output was not JSON.

    """
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed syft call
        [  # ruff: ignore[start-process-with-partial-path] - syft from PATH (.envrc, CircleCI)
            'syft',
            'scan',
            f'file:{lock}',
            '--output',
            'cyclonedx-json',
            '--quiet',
            '--override-default-catalogers',
            'python',
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = f'syft exited {result.returncode}: {result.stderr.strip()}'
        raise SyftError(message)
    try:
        document = json_object(json.loads(result.stdout))
    except json.JSONDecodeError as error:
        message = f'syft output was not JSON: {error}'
        raise SyftError(message) from error
    if document is None:
        message = 'syft output was not a JSON object'
        raise SyftError(message)
    return document


# ---------------------------------------------------------------------------
# Where the lock installs each package
# ---------------------------------------------------------------------------


def _edge_applies(edge: dict[str, Any], *, environment: Mapping[str, str]) -> bool:
    """Return whether a lock dependency edge applies in a marker environment (no marker: always).

    Returns:
        True when its ``marker`` holds there.

    """
    marker = edge.get('marker')
    return not isinstance(marker, str) or Marker(marker).evaluate(dict(environment))


def _edges_of(package: dict[str, Any], *, extras: Iterable[str]) -> list[dict[str, Any]]:
    """Return a lock package's dependency edges with the given extras' (and, editable, all).

    A workspace member (an ``editable`` or ``virtual`` source) brings every extra and every
    dependency group, as ``uv sync --all-extras --all-groups --all-packages`` installs them; a
    registry package only its plain dependencies and the extras an edge asked of it.

    Returns:
        The edges.

    """
    edges = json_objects(package.get('dependencies'))
    optional = json_object(package.get('optional-dependencies')) or {}
    source = json_object(package.get('source')) or {}
    if 'editable' in source or 'virtual' in source:
        groups = json_object(package.get('dev-dependencies')) or {}
        for entries in (*optional.values(), *groups.values()):
            edges.extend(json_objects(entries))
    else:
        for extra in extras:
            edges.extend(json_objects(optional.get(extra)))
    return edges


def packages_installed_in(*, lock: dict[str, Any], environment: Mapping[str, str]) -> set[str]:
    """Return the names of the packages the lock installs in one marker environment.

    Walks the lock's dependency edges from every workspace member, following an edge only where
    its marker holds (so ``pywin32``, wanted only on ``win32``, is absent from macOS's set).

    Args:
        lock: The parsed uv.lock.
        environment: A complete PEP 508 marker environment.

    Returns:
        The canonical package names.

    """
    packages: dict[str, dict[str, Any]] = {
        canonicalize_name(str(package.get('name', ''))): package
        for package in json_objects(lock.get('package'))
    }
    pending: list[tuple[str, tuple[str, ...]]] = [
        (name, ())
        for name, package in packages.items()
        if {'editable', 'virtual'} & set(json_object(package.get('source')) or {})
    ]
    visited: set[tuple[str, tuple[str, ...]]] = set()
    while pending:
        name, extras = pending.pop()
        if (name, extras) in visited or name not in packages:
            continue
        visited.add((name, extras))
        for edge in _edges_of(packages[name], extras=extras):
            if _edge_applies(edge, environment=environment):
                edge_extras = tuple(sorted(str(extra) for extra in edge.get('extra', [])))
                pending.append((canonicalize_name(str(edge.get('name', ''))), ()))
                if edge_extras:
                    pending.append((canonicalize_name(str(edge.get('name', ''))), edge_extras))
    return {name for name, _extras in visited}


def packages_installed_everywhere(*, lock: dict[str, Any]) -> frozenset[str]:
    """Return the packages the lock installs in every one of ``SUPPORTED_ENVIRONMENTS``.

    Returns:
        The canonical package names.

    """
    first, *others = (
        packages_installed_in(lock=lock, environment=environment)
        for environment in SUPPORTED_ENVIRONMENTS
    )
    return frozenset(first.intersection(*others))


# ---------------------------------------------------------------------------
# Licenses
# ---------------------------------------------------------------------------


def metadata_license(metadata: importlib.metadata.PackageMetadata) -> dict[str, Any] | None:
    """Return the CycloneDX license entry a distribution's core metadata declares, if any.

    In order: ``License-Expression`` (PEP 639, SPDX); else the ``License`` field when it is one
    line and not ``UNKNOWN`` (a field holding a whole license text names no license); else the
    one ``License ::`` trove classifier, by its last part (``MIT License``, ``BSD License``),
    which syft read too. Several license classifiers name no single license (dual licensing),
    so they give none; ``PACKAGE_LICENSE_OVERRIDES`` covers such packages.

    Args:
        metadata: The distribution's core metadata.

    Returns:
        ``{'expression': ...}``, ``{'license': {'name': ...}}``, or None.

    """
    expression = (metadata.get('License-Expression') or '').strip()
    if expression:
        return {'expression': expression}
    license_field = (metadata.get('License') or '').strip()
    if license_field and '\n' not in license_field and license_field.upper() != 'UNKNOWN':
        return {'license': {'name': license_field}}
    license_classifiers = [
        classifier.rsplit('::', 1)[-1].strip()
        for classifier in metadata.get_all('Classifier') or []
        if classifier.startswith('License ::')
        and classifier.rsplit('::', 1)[-1].strip() != 'OSI Approved'
    ]
    if len(license_classifiers) == 1:
        return {'license': {'name': license_classifiers[0]}}
    return None


def installed_distributions(
    *, search_path: list[str] | None = None
) -> dict[str, tuple[str, dict[str, Any] | None]]:
    """Return the installed distributions: canonical name to (version, license entry).

    Args:
        search_path: The directories to look in (None: ``sys.path``, this environment's).

    Returns:
        The map (the first of two installs of one name wins, as Python's import would; a
        distribution without a name is skipped).

    """
    distributions = (
        importlib.metadata.distributions()
        if search_path is None
        else importlib.metadata.distributions(path=search_path)
    )
    installed: dict[str, tuple[str, dict[str, Any] | None]] = {}
    for distribution in distributions:
        name = canonicalize_name(distribution.metadata.get('Name') or '')
        if name and name not in installed:
            installed[name] = (distribution.version, metadata_license(distribution.metadata))
    return installed


def add_licenses(
    *,
    sbom: dict[str, Any],
    installed_everywhere: frozenset[str],
    installed: Mapping[str, tuple[str, dict[str, Any] | None]],
    overrides: Mapping[str, tuple[str, str]],
) -> dict[str, Any]:
    """Give each library component its license from the override table or installed metadata.

    An override wins and is written as an SPDX ``expression``. Otherwise the package must be one
    the lock installs everywhere, installed here at the lock's version, and its metadata's
    license (if it declares one) is written; a component whose metadata declares none keeps no
    license (the license check reports it).

    Args:
        sbom: The stripped document; changed in place.
        installed_everywhere: ``packages_installed_everywhere``'s answer.
        installed: ``installed_distributions``' answer.
        overrides: ``PACKAGE_LICENSE_OVERRIDES``.

    Returns:
        The same document.

    Raises:
        LicenseSourceError: Naming every component whose license has no deterministic source:
            installed only somewhere without an override, not installed here, or installed at
            another version than the lock's.

    """
    problems: list[str] = []
    for component in json_objects(sbom.get('components')):
        if component.get('type') != 'library':
            continue
        component.pop('licenses', None)
        raw_name = str(component.get('name', ''))
        name = canonicalize_name(raw_name)
        version = str(component.get('version', ''))
        override = overrides.get(raw_name) or overrides.get(name)
        if override is not None:
            component['licenses'] = [{'expression': override[0]}]
            continue
        if name not in installed_everywhere:
            problems.append(
                f'{raw_name} {version}: uv.lock installs it on some platforms or Python versions '
                'only, so its license must come from PACKAGE_LICENSE_OVERRIDES '
                "(scripts/check_licenses.py), not from one platform's metadata"
            )
            continue
        if name not in installed:
            problems.append(
                f'{raw_name} {version}: not installed in this environment (uv sync --all-extras '
                '--all-groups --all-packages), so its license cannot be read'
            )
            continue
        installed_version, license_entry = installed[name]
        if Version(installed_version) != Version(version):
            problems.append(
                f'{raw_name}: uv.lock pins {version} but {installed_version} is installed '
                '(sync the environment with the lock)'
            )
            continue
        if license_entry is not None:
            component['licenses'] = [license_entry]
    if problems:
        message = 'No deterministic license source for:\n' + '\n'.join(
            f'  {problem}' for problem in problems
        )
        raise LicenseSourceError(message)
    return sbom


def write_sbom(*, sbom: dict[str, Any], output: Path) -> None:
    """Write the SBOM with sorted keys, two-space indents and a trailing newline (byte-stable).

    Args:
        sbom: The stripped document.
        output: Where to write it.

    """
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(sbom, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8'
    )


def main(arguments: Sequence[str] | None = None) -> int:
    """Scan the lock, strip the volatile fields, add the licenses and write the SBOM.

    Args:
        arguments: The command line (None: ``sys.argv[1:]``).

    Returns:
        The exit status: 0 written, 1 not.

    """
    parser = argparse.ArgumentParser(description='Regenerate the CycloneDX SBOM with syft.')
    parser.add_argument(
        '--lock', type=Path, default=LOCK_PATH, help=f'the uv lock to scan (default {LOCK_PATH})'
    )
    parser.add_argument(
        '--output', type=Path, default=SBOM_PATH, help=f'the SBOM to write (default {SBOM_PATH})'
    )
    options = parser.parse_args(arguments)
    if shutil.which('syft') is None:
        sys.stderr.write('syft is not on PATH: brew install syft (or direnv allow)\n')
        return 1
    lock: Path = options.lock
    if not lock.is_file():
        sys.stderr.write(f'No lock file at {lock}\n')
        return 1
    try:
        sbom = add_licenses(
            sbom=name_scanned_lock(
                sbom=strip_volatile_fields(scan_lock(lock=lock)), name=lock.name
            ),
            installed_everywhere=packages_installed_everywhere(
                lock=tomllib.loads(lock.read_text(encoding='utf-8'))
            ),
            installed=installed_distributions(),
            overrides=PACKAGE_LICENSE_OVERRIDES,
        )
    except (SyftError, LicenseSourceError) as error:
        sys.stderr.write(f'{error}\n')
        return 1
    output: Path = options.output
    write_sbom(sbom=sbom, output=output)
    sys.stdout.write(f'Wrote {output}: {len(sbom.get("components", []))} components\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
