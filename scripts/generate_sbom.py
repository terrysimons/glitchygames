"""Regenerate the committed CycloneDX SBOM, docs/sbom.cyclonedx.json, from a virtualenv.

Adapted from exoneris scripts/generate_sbom.py (the owner's project, 2026-10-28: "swap syft/grype
for safety and pip-audit", wired the way exoneris does it). What differs here: one virtualenv,
not exoneris's three (it has diarization sidecars with venvs of their own; this project has
none), no Markdown rendering beside the JSON, and the virtualenv is named on the command line
(``nox -s security-scan`` passes its own, built from uv.lock with every extra), never guessed.

``syft`` inventories every installed Python distribution, direct and transitive; the fields
CycloneDX tools regenerate on every run (``metadata.timestamp``, ``serialNumber``, the random
``bom-ref`` values and syft's ``?package-id=`` purl suffix) are stripped, so the written file is
a function of the dependency set alone: two runs on unchanged dependencies write the same
bytes, and a ``git diff`` of the file means the dependencies changed. ``nox -s security-scan``
fails when the regenerated file differs from the committed one (its drift check), so commit
the regenerated SBOM with the uv.lock change that caused it.

Exit codes: 0 when the SBOM was written; 1 when syft is missing, the virtualenv does not exist,
syft failed, or its output was not JSON.

Usage:
    python scripts/generate_sbom.py --venv .nox/security-scan [--output docs/sbom.cyclonedx.json]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs syft, never a shell
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SBOM_PATH = PROJECT_ROOT / 'docs' / 'sbom.cyclonedx.json'

# Path fragments marking a component as an artifact shipped inside another package rather than
# an installed distribution (adapted from exoneris scripts/generate_sbom.py's
# _EMBEDDED_PACKAGE_MARKERS, without its ansible_collections entry: nothing here installs
# Ansible). Two kinds: test fixtures a package ships for its own tests (toy eggs), and vendored
# copies (pip's and setuptools' ``_vendor``), which syft promotes to top-level components and
# whose dependency edges flip between the real and the vendored copy from run to run. The
# manifest names are defense in depth: an installed distribution's metadata never lives in a
# requirements file or a lock file a package happens to ship.
EMBEDDED_PACKAGE_MARKERS = (
    '/tests/data/',
    '/tests/fixtures/',
    '/test/data/',
    '/test/fixtures/',
    '/_vendor/',
    '/vendor/',
    '/requirements.txt',
    '/requirements-',
    '/test-requirements.txt',
    '/Pipfile.lock',
    '/poetry.lock',
)


class SyftError(RuntimeError):
    """syft failed, or wrote something that is not a JSON document."""


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


def is_embedded_package(component: dict[str, Any]) -> bool:
    """Return whether every location syft recorded for a component is inside another package.

    A component with any location outside the markers is a real installation and is kept: an
    installed distribution is never reachable only through another package's internals.

    Args:
        component: A CycloneDX component.

    Returns:
        True when the component is an embedded artifact (drop it), False otherwise.

    """
    paths = [
        str(entry.get('value', ''))
        for entry in json_objects(component.get('properties'))
        if str(entry.get('name', '')).startswith('syft:location:')
    ]
    if not paths:
        return False
    return all(any(marker in path for marker in EMBEDDED_PACKAGE_MARKERS) for path in paths)


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
    is mapped by package name to the kept component's purl (syft sometimes points at a vendored
    copy that was filtered out), and a purl whose package was not kept is dropped. Anonymous
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

    Removed: ``serialNumber``, ``metadata.timestamp``, the scanned directory's ``bom-ref``
    (``metadata.component``), every ``type: file`` component (syft lists each file of each
    package; the library components carry the name, version and license that matter), embedded
    artifacts (``is_embedded_package``), each component's ``bom-ref`` and purl query, and each
    dependency entry's ``ref``. Kept: ``metadata.tools`` (syft's version: an SBOM written by
    another syft differs, which is worth seeing).

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
    kept_components: list[dict[str, Any]] = []
    if 'components' in sbom:
        kept_components = [
            component
            for component in json_objects(sbom['components'])
            if component.get('type') != 'file' and not is_embedded_package(component)
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


def scan_virtualenv(*, virtualenv: Path) -> dict[str, Any]:
    """Run syft over a virtualenv's Python distributions and return its CycloneDX document.

    ``--override-default-catalogers python`` keeps syft to Python packages: otherwise it also
    classifies the binaries inside wheels (exoneris found a 12 MB SBOM of misidentified
    launchers and stray gemspecs).

    Args:
        virtualenv: The virtualenv's directory.

    Returns:
        The parsed document, unstripped.

    Raises:
        SyftError: syft exited non-zero, or its output was not JSON.

    """
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed syft call
        [  # ruff: ignore[start-process-with-partial-path] - syft from PATH (.envrc, CircleCI)
            'syft',
            'scan',
            f'dir:{virtualenv}',
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
    """Scan the virtualenv, strip the volatile fields and write the SBOM.

    Args:
        arguments: The command line (None: ``sys.argv[1:]``).

    Returns:
        The exit status: 0 written, 1 not.

    """
    parser = argparse.ArgumentParser(description='Regenerate the CycloneDX SBOM with syft.')
    parser.add_argument(
        '--venv',
        required=True,
        type=Path,
        help='the virtualenv to inventory (nox -s security-scan passes its own)',
    )
    parser.add_argument(
        '--output', type=Path, default=SBOM_PATH, help=f'the SBOM to write (default {SBOM_PATH})'
    )
    options = parser.parse_args(arguments)
    if shutil.which('syft') is None:
        sys.stderr.write('syft is not on PATH: brew install syft (or direnv allow)\n')
        return 1
    virtualenv: Path = options.venv
    if not virtualenv.is_dir():
        sys.stderr.write(f'No virtualenv at {virtualenv}\n')
        return 1
    try:
        sbom = strip_volatile_fields(scan_virtualenv(virtualenv=virtualenv))
    except SyftError as error:
        sys.stderr.write(f'{error}\n')
        return 1
    output: Path = options.output
    write_sbom(sbom=sbom, output=output)
    sys.stdout.write(f'Wrote {output}: {len(sbom.get("components", []))} components\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
