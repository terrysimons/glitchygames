"""Render the AI service's Ansible variables and templates, with no Ansible and no host.

Every test of the Ansible roles that needs a rendered value goes through here, so they all resolve
variables the same way: every role's defaults, then the platform's group variables, then the
facts a host would report. Only the filters the roles use are provided; Ansible's own
implementations are the reference (https://docs.ansible.com/ansible/latest/collections/ansible/builtin/).
"""

import functools
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
# What ansible-core's setup module reports as `architecture` (and `machine`) on each system: an
# Apple Silicon Mac says arm64, 64-bit ARM Linux aarch64
type MacArchitecture = Literal['arm64']
type LinuxArchitecture = Literal['aarch64', 'x86_64']
type Architecture = MacArchitecture | LinuxArchitecture


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


def _fail_on_undefined(value: Any) -> Any:
    """Let JSON encoding of an undefined value fail as Ansible's does: as an undefined variable.

    Raises:
        TypeError: The value is something else JSON can't encode.
    """
    if isinstance(value, jinja2.Undefined):
        # A StrictUndefined raises UndefinedError, naming what was missing, as soon as it's used
        str(value)
    message = f'Object of type {type(value).__name__} is not JSON serializable'
    raise TypeError(message)


def _to_json(value: Any, *, sort_keys: bool = False) -> str:
    """Ansible's `to_json`, which separates with a comma and a space like Python's default.

    Returns:
        The JSON text.
    """
    return json.dumps(value, sort_keys=sort_keys, default=_fail_on_undefined)


def _to_nice_json(value: Any, *, indent: int = 4, sort_keys: bool = True) -> str:
    """Ansible's `to_nice_json`.

    Returns:
        The indented JSON text.
    """
    return json.dumps(value, indent=indent, sort_keys=sort_keys, default=_fail_on_undefined)


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


def _regex_search(
    value: str, pattern: str, *groups: str, ignorecase: bool = False, multiline: bool = False
) -> str | list[str] | None:
    r"""Ansible's `regex_search`, with its group arguments and its two flags.

    A group is named as '\1' or '\g<name>'. Ansible's templating keeps a backslash in a
    single-quoted Jinja string as written, where plain Jinja reads '\1' as the character with code 1
    (checked with ansible-core 2.19.11, which picks group 1 from '\1' in smoke_test.yml), so that
    character also names group 1 here.

    Returns:
        The first match, or with groups the list of those groups' text; None when nothing matches.

    Raises:
        ValueError: A group argument Ansible's filter refuses ("Unknown argument").
    """
    wanted: list[int | str] = []
    for group in groups:
        named = re.fullmatch(r'\\g<(\S+)>', group)
        numbered = re.fullmatch(r'\\(\d+)', group)
        if named:
            wanted.append(named.group(1))
        elif numbered:
            wanted.append(int(numbered.group(1)))
        elif len(group) == 1 and 1 <= ord(group) <= 9:
            wanted.append(ord(group))
        else:
            message = f'regex_search: unknown argument {group!r}'
            raise ValueError(message)
    flags = (re.IGNORECASE if ignorecase else 0) | (re.MULTILINE if multiline else 0)
    found = re.search(pattern, value, flags)
    if found is None:
        return None
    if not wanted:
        return found.group(0)
    return [found.group(group) for group in wanted]


def _search(value: str, pattern: str) -> bool:
    """Ansible's `search` test.

    Returns:
        Whether the pattern matches anywhere in the value.
    """
    return re.search(pattern, value) is not None


def _version(value: str, other: str, operator: str = 'eq') -> bool:
    """Ansible's `version` test, for dotted whole numbers (its default `loose` comparison).

    Returns:
        Whether the value compares with the other as the operator says.

    Raises:
        ValueError: An operator Ansible's test does not name.
    """
    left = tuple(int(part) for part in str(value).split('.'))
    right = tuple(int(part) for part in str(other).split('.'))
    comparisons = {
        '<': left < right,
        'lt': left < right,
        '<=': left <= right,
        'le': left <= right,
        '>': left > right,
        'gt': left > right,
        '>=': left >= right,
        'ge': left >= right,
        '==': left == right,
        '=': left == right,
        'eq': left == right,
        '!=': left != right,
        'ne': left != right,
    }
    if operator not in comparisons:
        message = f'the version test has no operator {operator!r}'
        raise ValueError(message)
    return comparisons[operator]


def _extract(item: Any, container: Any) -> Any:
    """Ansible's `extract`, as `map('extract', container)` uses it.

    Returns:
        The container's value for the item.
    """
    return container[item]


def _zip(first: Any, *others: Any) -> list[tuple[Any, ...]]:
    """Ansible's `zip`.

    Returns:
        The lists' items paired up, as Python's zip pairs them.
    """
    return list(zip(first, *others, strict=False))


@functools.cache
def _environment(
    *, search_directories: tuple[Path, ...] = (), keep_trailing_newline: bool = True
) -> jinja2.Environment:
    """Build Jinja with the Ansible filters the roles use, once per configuration.

    Shared, so compiled_template's cache holds across renders; nothing changes an environment
    after it is built (every setting is one of these arguments).

    Args:
        search_directories: Where `{% include %}` and `{% import %}` find a template, in order.
        keep_trailing_newline: Keep a template's last line break.

    Returns:
        The environment, the same object for the same arguments.
    """
    environment = jinja2.Environment(  # ruff: ignore[jinja2-autoescape-false] - these render shell and plist text, not HTML
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=keep_trailing_newline,
        # The template module's default: a block tag's own line break is dropped
        trim_blocks=True,
        loader=jinja2.FileSystemLoader(search_directories) if search_directories else None,
    )
    filters: dict[str, Callable[..., Any]] = {
        # Ansible's quotes any value as its text
        'quote': lambda value: shlex.quote(str(value)),
        'to_json': _to_json,
        'to_nice_json': _to_nice_json,
        'hash': _hash,
        'combine': _combine,
        'dict2items': _dict2items,
        'bool': _bool,
        'regex_search': _regex_search,
        'regex_escape': re.escape,
        'basename': lambda path: Path(path).name,
        'extract': _extract,
        'zip': _zip,
    }
    for name, function in filters.items():
        environment.filters[name] = function
    # Ansible's `is search(pattern)`, which `reject('search', pattern)` also uses
    tests: dict[str, Any] = environment.tests
    tests['search'] = _search
    tests['version'] = _version
    return environment


@functools.cache
def compiled_template(*, environment: jinja2.Environment, source: str) -> jinja2.Template:
    """Compile a template's text once per environment, however often it is rendered.

    A compiled template is immutable and renders with whatever variables each call gives it, so
    sharing one changes no result; an undefined name still fails when it is rendered. Compiling
    on every render cost memory, not just time: coverage's sysmon core (the default on Python
    3.14+) keeps every code object it sees for the life of the process, about 3 KiB a compile,
    which took CI's Linux job past its memory guard (job 4020, 376,812 compiles of 488 sources).

    Args:
        environment: The Jinja environment the template belongs to (by identity).
        source: The template's text.

    Returns:
        The compiled template, the same object on every call with these arguments.
    """
    return environment.from_string(source)


def _resolve_string(
    *, text: str, variables: dict[str, Any], environment: jinja2.Environment
) -> Any:
    """Render the Jinja in a string, as Ansible templates a value when it is used.

    A string naming a variable, key or attribute nobody defined raises Jinja's UndefinedError,
    as Ansible's templating fails.

    Returns:
        The rendered text, or, when the string is one expression, its value: Ansible keeps a lone
        expression's type, so a number stays a number and a list a list.
    """
    if not _holds_jinja(value=text):
        return text
    lone_expression = re.fullmatch(r'\s*\{\{(?:(?!\{\{|\}\}).)*\}\}\s*', text, flags=re.DOTALL)
    if lone_expression:
        inner = text.strip().removeprefix('{{').removesuffix('}}')
        expression = '{{ (' + inner + ') | to_json }}'
        rendered = compiled_template(environment=environment, source=expression).render(variables)
        return json.loads(rendered)
    return compiled_template(environment=environment, source=text).render(variables)


def _holds_jinja(*, value: Any) -> bool:
    """Whether a value, or anything inside it, still has Jinja to render.

    Returns:
        True when some string in it holds an expression or a statement.
    """
    if isinstance(value, str):
        return '{{' in value or '{%' in value
    if isinstance(value, dict):
        return any(_holds_jinja(value=item) for item in value.values())
    if isinstance(value, list):
        return any(_holds_jinja(value=item) for item in value)
    return False


def _resolve(
    *,
    value: Any,
    variables: dict[str, Any],
    environment: jinja2.Environment,
    leave_undefined: bool = False,
) -> Any:
    """Render the Jinja inside a value.

    Args:
        value: A string, or a dict or list holding them.
        variables: What the Jinja may name.
        environment: The Jinja to render with.
        leave_undefined: Leave a string that names something undefined as it is, rather than
            raising: one pass of resolving the variables among themselves, where a later pass or
            the final check deals with it.

    Returns:
        The value with every resolvable reference replaced.

    Raises:
        jinja2.UndefinedError: A string names something undefined, and leave_undefined is False.
    """
    if isinstance(value, str):
        try:
            return _resolve_string(text=value, variables=variables, environment=environment)
        except jinja2.UndefinedError:
            if leave_undefined:
                return value
            raise
    if isinstance(value, dict):
        return {
            key: _resolve(
                value=item,
                variables=variables,
                environment=environment,
                leave_undefined=leave_undefined,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _resolve(
                value=item,
                variables=variables,
                environment=environment,
                leave_undefined=leave_undefined,
            )
            for item in value
        ]
    return value


def _check_architecture(*, system: Literal['Darwin', 'Linux'], architecture: Architecture) -> None:
    """Refuse facts no real host reports, so no test can pass on a machine that doesn't exist.

    Raises:
        ValueError: The architecture isn't one the system reports.
    """
    reported: dict[str, tuple[str, ...]] = {'Darwin': ('arm64',), 'Linux': ('aarch64', 'x86_64')}
    if architecture not in reported[system]:
        message = (
            f'{system} reports architecture {" or ".join(reported[system])}, not {architecture}'
        )
        raise ValueError(message)


def host_architecture(*, system: Literal['Darwin', 'Linux']) -> Architecture:
    """The architecture a test's host of this system reports: an Apple Silicon Mac, or a Pi.

    Returns:
        arm64 for Darwin, aarch64 for Linux.
    """
    return 'arm64' if system == 'Darwin' else 'aarch64'


def ansible_variables(
    *,
    system: Literal['Darwin', 'Linux'],
    architecture: Architecture,
    home: Path,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Every role's defaults plus the platform's group variables, with a host's facts.

    The facts are `system`, `architecture` (and `machine`, which reads the same on both systems),
    `user_dir` (the home) and `processor_vcpus`, and the environment is empty, so the XDG folders
    take their defaults. References between variables are resolved until nothing changes. A
    variable that names something undefined on this host (another platform's key, a fact it lacks)
    becomes an undefined value that fails wherever a test or template uses it, as Ansible fails
    only when a task uses it.

    Args:
        system: The host's `ansible_facts['system']`.
        architecture: The host's `ansible_facts['architecture']`, as that system reports it:
            arm64 on a Mac, aarch64 or x86_64 on Linux.
        home: The host user's home.
        overrides: Values set before references are resolved, as a task's `vars` would be, so
            every variable built from one follows it.

    Returns:
        The variables, as a playbook run on that host would see them.

    Raises:
        RuntimeError: The references never settle.
    """
    _check_architecture(system=system, architecture=architecture)
    variables: dict[str, Any] = {}
    for defaults in sorted((ANSIBLE_DIRECTORY / 'roles').glob('*/defaults/main.yml')):
        variables.update(yaml.safe_load(defaults.read_text(encoding='utf-8')) or {})
    group = 'macos' if system == 'Darwin' else 'linux'
    variables.update(
        yaml.safe_load(
            (ANSIBLE_DIRECTORY / 'group_vars' / f'{group}.yml').read_text(encoding='utf-8')
        ),
    )
    variables.update(overrides or {})
    variables['ansible_facts'] = {
        'system': system,
        'machine': architecture,
        'architecture': architecture,
        'user_dir': str(home),
        'processor_vcpus': 4,
        'env': {},
    }
    environment = _environment()
    for _ in range(MAXIMUM_RESOLUTION_PASSES):
        resolved = _resolve(
            value=variables, variables=variables, environment=environment, leave_undefined=True
        )
        if resolved == variables:
            break
        variables = resolved
    else:
        unsettled = sorted(name for name, value in variables.items() if _holds_jinja(value=value))
        message = f'still changing after {MAXIMUM_RESOLUTION_PASSES} passes: {", ".join(unsettled)}'
        raise RuntimeError(message)
    unsettled: list[str] = []
    for name, value in list(variables.items()):
        if not _holds_jinja(value=value):
            continue
        try:
            _resolve(value=value, variables=variables, environment=environment)
        except jinja2.UndefinedError as error:
            variables[name] = jinja2.StrictUndefined(hint=f'{name} names {error.message}')
        else:
            # It renders, yet still holds Jinja: it refers to itself, which Ansible refuses as a
            # recursive loop
            unsettled.append(name)
    if unsettled:
        message = f'these refer to themselves and never resolve: {", ".join(sorted(unsettled))}'
        raise RuntimeError(message)
    return variables


def render_template(*, path: Path, variables: dict[str, Any]) -> str:
    """Render one Jinja file with the variables, finding what it includes as Ansible does.

    Ansible's template module searches the rendered template's own folder and the playbook's
    folder (its loader's base directory, here ansible/), so one role's template can import
    another's by its path from there (ansible-core 2.20, plugins/action/template.py).

    Returns:
        The rendered text.
    """
    # As the template module does: an included template's last line break is dropped, and the
    # rendered file keeps its own
    environment = _environment(
        search_directories=(path.parent, ANSIBLE_DIRECTORY), keep_trailing_newline=False
    )
    source = path.read_text(encoding='utf-8')
    rendered = compiled_template(environment=environment, source=source).render(variables)
    return rendered + '\n' if source.endswith('\n') else rendered


def render_value(*, value: Any, variables: dict[str, Any]) -> Any:
    """Render the Jinja inside a task's value (a string, or a dict or list of them).

    Returns:
        The value with every reference replaced; a lone expression that renders to a whole
        number becomes an int, as in Ansible.
    """
    return _resolve(value=value, variables=variables, environment=_environment())


def render_expression(*, expression: str, variables: dict[str, Any]) -> Any:
    """Evaluate one `{{ ... }}` expression, as a set_fact or a loop holds it, keeping its type.

    Returns:
        The expression's value: a list stays a list and a dict a dict.
    """
    inner = expression.strip().removeprefix('{{').removesuffix('}}')
    template = compiled_template(
        environment=_environment(), source='{{ (' + inner + ') | to_json }}'
    )
    return json.loads(template.render(variables))
