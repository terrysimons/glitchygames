"""Render the AI service's Ansible variables and templates, with no Ansible and no host.

Every test of the Ansible roles that needs a rendered value goes through here, so they all resolve
variables the same way: every role's defaults, then the platform's group variables, then the
facts a host would report. Only the filters the roles use are provided; Ansible's own
implementations are the reference (https://docs.ansible.com/ansible/latest/collections/ansible/builtin/).
"""

import hashlib
import json
import re
import shlex
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import jinja2
import yaml

if TYPE_CHECKING:
    from collections.abc import Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANSIBLE_DIRECTORY = PROJECT_ROOT / 'ansible'
MAXIMUM_RESOLUTION_PASSES = 20


def _combine(base: dict[str, Any], *others: dict[str, Any]) -> dict[str, Any]:
    """Ansible's `combine`: later dicts win.

    Returns:
        The merged dict.
    """
    merged = dict(base)
    for other in others:
        merged.update(other)
    return merged


def _dict2items(mapping: dict[str, Any]) -> list[dict[str, Any]]:
    """Ansible's `dict2items`.

    Returns:
        One key and value pair per entry.
    """
    return [{'key': key, 'value': value} for key, value in mapping.items()]


def _to_json(value: Any, *, sort_keys: bool = False) -> str:
    """Ansible's `to_json`, which separates with a comma and a space like Python's default.

    Returns:
        The JSON text.
    """
    return json.dumps(value, sort_keys=sort_keys)


def _to_nice_json(value: Any, *, indent: int = 4, sort_keys: bool = True) -> str:
    """Ansible's `to_nice_json`.

    Returns:
        The indented JSON text.
    """
    return json.dumps(value, indent=indent, sort_keys=sort_keys)


def _hash(value: str, algorithm: str = 'sha1') -> str:
    """Ansible's `hash`.

    Returns:
        The hex digest.
    """
    return hashlib.new(algorithm, value.encode('utf-8')).hexdigest()


def _bool(value: Any) -> bool:
    """Ansible's `bool`.

    Returns:
        Whether the value reads as true.
    """
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on', 'y', 't'}
    return bool(value)


def _regex_search(value: str, pattern: str) -> str | None:
    """Ansible's `regex_search`.

    Returns:
        The first match, or None.
    """
    found = re.search(pattern, value)
    return found.group(0) if found else None


def _search(value: str, pattern: str) -> bool:
    """Ansible's `search` test.

    Returns:
        Whether the pattern matches anywhere in the value.
    """
    return re.search(pattern, value) is not None


def _environment() -> jinja2.Environment:
    """Build Jinja with the Ansible filters the roles use.

    Returns:
        The environment.
    """
    environment = jinja2.Environment(  # ruff: ignore[jinja2-autoescape-false] - these render shell and plist text, not HTML
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    filters: dict[str, Callable[..., Any]] = {
        'quote': shlex.quote,
        'to_json': _to_json,
        'to_nice_json': _to_nice_json,
        'hash': _hash,
        'combine': _combine,
        'dict2items': _dict2items,
        'bool': _bool,
        'regex_search': _regex_search,
        'regex_escape': re.escape,
        'basename': lambda path: Path(path).name,
    }
    for name, function in filters.items():
        environment.filters[name] = function
    # Ansible's `is search(pattern)`, which `reject('search', pattern)` also uses
    environment.tests['search'] = _search
    return environment


def _resolve_string(
    *, text: str, variables: dict[str, Any], environment: jinja2.Environment
) -> Any:
    """Render the Jinja in a string, leaving one that names a missing variable as it is.

    Returns:
        The rendered text, or an int when one expression renders to a whole number.
    """
    if '{{' not in text and '{%' not in text:
        return text
    try:
        rendered = environment.from_string(text).render(variables)
    except jinja2.UndefinedError:
        return text
    # Ansible keeps a lone expression's type: a number stays one
    if re.fullmatch(r'-?\d+', rendered.strip()) and text.strip().startswith('{{'):
        return int(rendered)
    return rendered


def _resolve(*, value: Any, variables: dict[str, Any], environment: jinja2.Environment) -> Any:
    """Render the Jinja inside a value.

    Returns:
        The value with every resolvable reference replaced.
    """
    if isinstance(value, str):
        return _resolve_string(text=value, variables=variables, environment=environment)
    if isinstance(value, dict):
        return {
            key: _resolve(value=item, variables=variables, environment=environment)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _resolve(value=item, variables=variables, environment=environment) for item in value
        ]
    return value


def ansible_variables(
    *,
    system: Literal['Darwin', 'Linux'],
    architecture: Literal['aarch64', 'x86_64'],
    home: Path,
) -> dict[str, Any]:
    """Every role's defaults plus the platform's group variables, with a host's facts.

    The facts are `system`, `architecture`, `user_dir` (the home) and `processor_vcpus`, and the
    environment is empty, so the XDG folders take their defaults. References between variables
    are resolved until nothing changes.

    Returns:
        The variables, as a playbook run on that host would see them.
    """
    variables: dict[str, Any] = {}
    for defaults in sorted((ANSIBLE_DIRECTORY / 'roles').glob('*/defaults/main.yml')):
        variables.update(yaml.safe_load(defaults.read_text(encoding='utf-8')) or {})
    group = 'macos' if system == 'Darwin' else 'linux'
    variables.update(
        yaml.safe_load(
            (ANSIBLE_DIRECTORY / 'group_vars' / f'{group}.yml').read_text(encoding='utf-8')
        ),
    )
    variables['ansible_facts'] = {
        'system': system,
        'machine': 'arm64' if system == 'Darwin' else architecture,
        'architecture': architecture,
        'user_dir': str(home),
        'processor_vcpus': 4,
        'env': {},
    }
    environment = _environment()
    for _ in range(MAXIMUM_RESOLUTION_PASSES):
        resolved = _resolve(value=variables, variables=variables, environment=environment)
        if resolved == variables:
            break
        variables = resolved
    return variables


def render_template(*, path: Path, variables: dict[str, Any]) -> str:
    """Render one Jinja file with the variables.

    Returns:
        The rendered text.
    """
    return _environment().from_string(path.read_text(encoding='utf-8')).render(variables)
