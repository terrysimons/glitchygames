r"""List the claims in the living documentation that the code no longer backs.

The whole-stack docs scrub's worklist (plans/2026-11-02-whole-stack-docs-scrub.md). Each living
document (the root Markdown files but BUGS.md; docs/ but its generated graphs and metrics and its
dated specs; every member's README.md) is read for the claims a machine can check, and each
claim that does not hold is listed:

  path    A repository path (``src/...``, ``tests/...``, ``scripts/...``, ``docs/...``,
          ``plans/...``, ``quality/...``) that exists neither from the repository root nor
          inside any member (a directory under src/ with its own pyproject.toml): a page may
          name a member's path as each member has it (``tests/fixtures/replays/``, every
          game's goldens), and a member's README names its own. A path with a placeholder
          (``<game>``, ``*``, ``{a,b}``) is no claim about one file: not checked.
  file    A backticked Python file name (```synth.py```) that no tracked file has. One that
          starts with ``_`` names a suffix (```_wheel.py```: each member's
          ``test_<member>_wheel.py``) and holds when some tracked file name ends with it.
  name    A backticked dotted Python name whose first part is the project's and whose rest is
          not defined there: a module (``glitchygames.audio.synth.to_sound``,
          ``clock.raw_sleep``), a class (``Scene.game_time``), or an instance named for its
          class (``camera.update()``, a ``Camera2D``'s). Names of other libraries
          (``pygame.mixer``, ``self.dt``) are not checked: their first part is nothing of the
          project's. Nor are bare calls (```get_pos()```): without a module there is no telling
          whose they are. A dotted file name (```bitmappy.zip```) is no name.
  option  A backticked command-line option (```--axis-deadzone```) that no tracked Python file
          and no project configuration (``OPTION_SOURCES``) spells.
  bug     A prose line that calls a BUGS.md entry open (``open``, ``active``, ``until #N``,
          ``unfixed``, ``workaround``) though the entry's status says it is fixed or closed.

Every name is read from the code's syntax trees (``ast``): nothing of the project is imported or
run. A claim that is right though no check can see it is listed in ``RECORDED_EXCEPTIONS`` with
the reason.

It writes one line per claim (``file:line: kind: claim``) and exits ``ExitCode.SUCCESS`` when
there is none, ``CLAIMS_FOUND`` (1, as scripts/check_licenses.py for its findings) when there
are some: a worklist, and once it is empty, a check.

Usage:
    uv run python -m scripts.docs_claims
    uv run python -m scripts.docs_claims --kind name --kind option
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from glitchygames.exit_codes import ExitCode
from scripts.git_checkout import NotAGitCheckoutError, run_git

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# The exit status when some claim does not hold (a finding, as scripts/check_licenses.py's)
CLAIMS_FOUND = 1

# The kinds of claim, in the order the module docstring describes them
CLAIM_KINDS = ('path', 'file', 'name', 'option', 'bug')

# The root directories a repository path starts with. Anything else (`games/x.md`, a link
# relative to its document) is mkdocs' to check (`mkdocs build --strict`). A path after a colon
# is another ref's (`origin/gh-pages:quality/metrics/x.jsonl`, git's REF:PATH), not the work
# tree's
REPOSITORY_PATH = re.compile(
    r'(?<![\w./~:-])(?:src|tests|scripts|docs|plans|quality)/[\w./<>*{},@+-]*'
)
# What a path claim may end with that is not part of it: a line number (`x.py:12`), a test id
# (`x.py::test_y`); and prose punctuation (TRAILING_PUNCTUATION)
PATH_TAIL = re.compile(r'(?:::[\w\[\]-]+|:\d+(?:-\d+)?)$')
TRAILING_PUNCTUATION = '.,;:)\'"'
PATH_PLACEHOLDER = re.compile(r'[<>*{}]')
BACKTICKED = re.compile(r'`([^`\n]+)`')
PYTHON_FILE_NAME = re.compile(r'^[\w-]+\.py$')
# `a.b`, `a.b.c()`, `Class.attribute`: two or more dotted parts, an optional call
DOTTED_NAME = re.compile(r'^(?P<name>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)(?:\(\))?$')
# A dotted token ending in one of these is a file name (`bitmappy.zip`, `player.toml`)
FILE_EXTENSIONS = frozenset({
    'cfg',
    'gz',
    'ini',
    'json',
    'jsonl',
    'md',
    'png',
    'spec',
    'toml',
    'txt',
    'wav',
    'yaml',
    'yml',
    'zip',
})
OPTION = re.compile(r'^(?P<option>--[a-z][a-z0-9-]*)(?:[ =].*)?$')
FENCE_LINE = re.compile(r'^\s*(?P<marker>`{3,}|~{3,})')
BUG_HEADING = re.compile(r'^### (?P<number>\d+)\. ')
BUG_STATUS = re.compile(r'^- \*\*Status\*\*: (?P<status>\w+)')
BUG_REFERENCE = re.compile(r'#(?P<number>\d+)\b')
# Wording that calls a bug open
OPEN_WORDING = re.compile(
    r'\b(?:open|active|until|unfixed|not (?:yet )?fixed|workaround|known bug|still)\b',
    re.IGNORECASE,
)
CLOSED_STATUSES = frozenset({'Fixed', 'Closed', 'Resolved'})
# Where an option the project defines is spelled, besides its Python files
OPTION_SOURCES = ('noxfile.py', 'pyproject.toml', '.pre-commit-config.yaml', '.circleci/')
# Pages under docs/ that are not checked: generated (gitignored) ones, and the dated specs, a
# record of decisions that describes the code of its date (as plans/ does)
UNCHECKED_DOCS = ('docs/quality/graphs/', 'docs/quality/metrics/', 'docs/specs/')
# Single documents that are not checked: document -> why
UNCHECKED_DOCUMENTS: dict[str, str] = {
    'docs/galimore.md': (
        "notes on another code base (Galimore's C++ files and functions), kept for future work "
        "(the owner, 2026-11-04): its paths and names are that code base's, not this one's"
    ),
}
MEMBER_MANIFEST = 'pyproject.toml'
# A mkdocstrings stub (the API reference): its page is generated from the code
API_STUB = re.compile(r'^:::\s', re.MULTILINE)
SELF_NAMES = frozenset({'self', 'cls'})

# Claims that hold though no check can see it: (document, claim text) -> why
RECORDED_EXCEPTIONS: dict[tuple[str, str], str] = {
    ('CLAUDE.md', 'tests/test_specific.py'): 'an example command line: any test file',
    ('README.md', 'tests/test_specific.py'): 'an example command line: any test file',
    ('CLAUDE.md', 'tests/x'): 'an example of a test path',
    ('CLAUDE.md', 'src/glitchygames/_build_info.json'): (
        'the build stamp, which exists only while a build runs (gitignored, removed after)'
    ),
    ('CLAUDE.md', 'scripts/replay_metrics.py'): 'named as deleted: its tools moved to measure',
    ('CLAUDE.md', 'scripts/recording_report.py'): 'named as deleted: it moved to report',
    ('CLAUDE.md', 'tests/workspace_expectations.MEMBER_PACKAGES'): (
        "a module's constant written path-style (tests/workspace_expectations.py)"
    ),
    ('CLAUDE.md', 'recording.recorded_frame_fields()'): (
        'a variable typed with the RecordedFrameFieldSource protocol (recording.py)'
    ),
    ('docs/architecture/gameplay_replay.md', 'glitchygames.bitmappy.editor'): (
        "named as the logical module Bitmappy's scene left"
    ),
    ('docs/games/clockwork_keep.md', 'glitchygames.examples.clockwork_keep'): (
        'named as the module the move left nothing of'
    ),
    ('docs/architecture/game_packages.md', 'src/glitchygames/examples'): (
        "named as a place the moves emptied, where an old checkout's leftovers are"
    ),
    ('docs/architecture/game_packages.md', 'src/glitchygames/bitmappy'): (
        "named as a place the moves emptied, where an old checkout's leftovers are"
    ),
    ('docs/architecture/game_packages.md', 'tests/examples'): (
        "named as a place the moves emptied, where an old checkout's leftovers are"
    ),
}


@dataclass(frozen=True)
class Claim:
    """One claim a document makes that the code does not back."""

    document: str
    line_number: int
    kind: str
    text: str

    def describe(self) -> str:
        """Return ``document:line: kind: text``.

        Returns:
            The claim's report line.

        """
        return f'{self.document}:{self.line_number}: {self.kind}: {self.text}'


@dataclass
class CodeIndex:
    """What the project's tracked Python files define, read from their syntax trees.

    Attributes:
        modules: Each dotted module name (``glitchygames.audio.synth``; a member's
            ``brave_adventurer.game``; a script's ``scripts.docs_claims``) -> its top-level
            names (functions, classes, assignments, imports).
        short_modules: Each module's every part (``synth``, ``audio``) -> the dotted modules it
            may be.
        classes: Each class name -> its members (methods, class attributes, ``self.x``
            assignments), merged over every class of that name and its bases in the project.
        file_names: Every tracked Python file's name (``synth.py``).

    """

    modules: dict[str, set[str]] = field(default_factory=dict)
    short_modules: dict[str, set[str]] = field(default_factory=dict)
    classes: dict[str, set[str]] = field(default_factory=dict)
    file_names: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Evidence:
    """What a document's claims are checked against.

    Attributes:
        project_root: The repository.
        index: What its Python files define.
        option_text: The text its options are spelled in (``option_source_text``).
        bug_statuses: Each BUGS.md entry's number -> its status word.
        member_roots: Each member's directory (``src/games/paddleslap``), where a path a page
            writes as each member has it is looked for.

    """

    project_root: Path
    index: CodeIndex
    option_text: str
    bug_statuses: dict[int, str]
    member_roots: tuple[Path, ...]


def tracked_files(*, project_root: Path) -> list[str]:
    """Return the repository's tracked files (``git ls-files``; a submodule's are not listed).

    Args:
        project_root: The repository.

    Returns:
        Their paths, relative and POSIX.

    Raises:
        NotAGitCheckoutError: When git cannot list them.

    """
    status, output = run_git(arguments=['ls-files', '-z'], directory=project_root)
    if status != 0:
        message = f'{project_root} is not in a git checkout (git ls-files said: {output.strip()})'
        raise NotAGitCheckoutError(message)
    return [name for name in output.split('\0') if name]


def module_name_for(*, relative: str) -> str:
    """Return the dotted module name a tracked Python file is imported as.

    A file under a ``src/`` directory is named from below its last ``src/``
    (``src/games/x/src/x_game/a.py`` is ``x_game.a``, ``src/glitchygames/a.py`` is
    ``glitchygames.a``); any other from the repository root (``scripts/a.py``). A package's
    ``__init__.py`` is the package.

    Args:
        relative: The file's repository path.

    Returns:
        The module name.

    """
    parts = relative.removesuffix('.py').split('/')
    if 'src' in parts:
        last_source = len(parts) - 1 - parts[::-1].index('src')
        parts = parts[last_source + 1 :]
    if parts[-1] == '__init__':
        parts = parts[:-1]
    return '.'.join(parts)


def _assigned_names(statement: ast.stmt) -> list[ast.expr]:
    """Return what an assignment statement assigns to (nothing for any other statement).

    Returns:
        Its targets.

    """
    if isinstance(statement, ast.Assign):
        return list(statement.targets)
    if isinstance(statement, (ast.AnnAssign, ast.AugAssign)):
        return [statement.target]
    return []


def class_members(node: ast.ClassDef) -> tuple[set[str], list[str]]:
    """Return a class's member names and its bases' names.

    Its methods and nested classes, its class-level assignments, and every ``self.x`` (or
    ``cls.x``) any of its methods assigns.

    Returns:
        (members, base class names).

    """
    members: set[str] = set()
    for statement in ast.walk(node):
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            members.add(statement.name)
        for target in _assigned_names(statement) if isinstance(statement, ast.stmt) else []:
            if isinstance(target, ast.Name):
                members.add(target.id)
            elif (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id in SELF_NAMES
            ):
                members.add(target.attr)
    bases = [
        base.id if isinstance(base, ast.Name) else base.attr
        for base in node.bases
        if isinstance(base, (ast.Name, ast.Attribute))
    ]
    return members, bases


def top_level_names(tree: ast.Module) -> set[str]:
    """Return a module's top-level names: definitions, assignments and imports.

    An import anywhere in the module counts (a function's local import names nothing at the top
    level, but a module importing a name under ``TYPE_CHECKING`` or in a ``try`` does).

    Returns:
        The names.

    """
    names: set[str] = set()
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(statement.name)
        names.update(
            target.id for target in _assigned_names(statement) if isinstance(target, ast.Name)
        )
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split('.')[0] for alias in node.names)
    return names


def _index_module(
    *, tree: ast.Module, relative: str, index: CodeIndex, class_bases: dict[str, list[str]]
) -> None:
    """Add one parsed file's module, its names and its classes to the index."""
    module = module_name_for(relative=relative)
    index.modules.setdefault(module, set()).update(top_level_names(tree))
    module_parts = module.split('.')
    for prefix_length in range(1, len(module_parts) + 1):
        prefix = module_parts[:prefix_length]
        index.short_modules.setdefault(prefix[-1], set()).add('.'.join(prefix))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            members, bases = class_members(node)
            index.classes.setdefault(node.name, set()).update(members)
            class_bases.setdefault(node.name, []).extend(bases)


def _inherit_members(*, index: CodeIndex, class_bases: dict[str, list[str]]) -> None:
    """Give each class what its project bases define, pass after pass to a fixed point."""
    changed = True
    while changed:
        changed = False
        for name, bases in class_bases.items():
            for base in bases:
                inherited = index.classes.get(base, set()) - index.classes[name]
                if inherited:
                    index.classes[name] |= inherited
                    changed = True


def code_index(*, project_root: Path, files: Iterable[str]) -> CodeIndex:
    """Read every tracked Python file's definitions.

    Args:
        project_root: The repository.
        files: Its tracked files.

    Returns:
        The index. A file that does not parse is left out (its names are then reported, the
        right prompt to look at it).

    """
    index = CodeIndex()
    class_bases: dict[str, list[str]] = {}
    for relative in files:
        if not relative.endswith('.py'):
            continue
        index.file_names.add(relative.rsplit('/', 1)[-1])
        try:
            tree = ast.parse((project_root / relative).read_text(encoding='utf-8'))
        except OSError, SyntaxError, UnicodeDecodeError:
            continue
        _index_module(tree=tree, relative=relative, index=index, class_bases=class_bases)
    _inherit_members(index=index, class_bases=class_bases)
    return index


def living_documents(*, project_root: Path, files: Iterable[str]) -> list[str]:
    """Return the living documents: root Markdown (not BUGS.md), docs/, member READMEs.

    Args:
        project_root: The repository.
        files: Its tracked files.

    Returns:
        Their repository paths, sorted. docs/'s unchecked pages (``UNCHECKED_DOCS``), the
        unchecked documents (``UNCHECKED_DOCUMENTS``) and API stubs are left out.

    """
    documents: list[str] = []
    for relative in files:
        if not relative.endswith('.md') or relative == 'BUGS.md':
            continue
        if relative in UNCHECKED_DOCUMENTS:
            continue
        is_root = '/' not in relative
        is_docs = relative.startswith('docs/') and not relative.startswith(UNCHECKED_DOCS)
        is_member_readme = relative.startswith('src/') and relative.endswith('/README.md')
        if not (is_root or is_docs or is_member_readme):
            continue
        if is_docs and API_STUB.search((project_root / relative).read_text(encoding='utf-8')):
            continue
        documents.append(relative)
    return sorted(documents)


def document_lines(text: str) -> Iterator[tuple[int, str, bool]]:
    """Yield each line but the fences, with its number and whether it is fenced code.

    Yields:
        (line number, line, fenced).

    """
    fence_marker: str | None = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        fence = FENCE_LINE.match(line)
        if fence is not None:
            marker = fence.group('marker')
            if fence_marker is None:
                fence_marker = marker
            elif marker[0] == fence_marker[0] and len(marker) >= len(fence_marker):
                fence_marker = None
            continue
        yield line_number, line, fence_marker is not None


def member_roots(*, project_root: Path, files: Iterable[str]) -> tuple[Path, ...]:
    """Return each member's directory: a directory under src/ with its own pyproject.toml.

    Args:
        project_root: The repository.
        files: Its tracked files.

    Returns:
        The directories, sorted.

    """
    return tuple(
        sorted(
            (project_root / relative).parent
            for relative in files
            if relative.startswith('src/') and relative.endswith(f'/{MEMBER_MANIFEST}')
        )
    )


def missing_paths(*, line: str, project_root: Path, roots: Sequence[Path]) -> list[str]:
    """Return the repository paths a line names that exist neither at the root nor in a member.

    Args:
        line: The line.
        project_root: The repository.
        roots: The members' directories: a path written as each member has it holds when one
            of them has it.

    Returns:
        The missing paths, as written (without trailing punctuation or a line number).

    """
    missing: list[str] = []
    for match in REPOSITORY_PATH.finditer(line):
        path = match.group(0).rstrip(TRAILING_PUNCTUATION)
        path = PATH_TAIL.sub('', path).rstrip(TRAILING_PUNCTUATION)
        if PATH_PLACEHOLDER.search(path):
            continue
        if not any((root / path).exists() for root in (project_root, *roots)):
            missing.append(path)
    return missing


def _module_path_holds(*, module: str, rest: list[str], index: CodeIndex) -> bool:
    """Return whether ``rest`` names submodules of ``module`` and then one of its names.

    When that name is a class, the part after it must be one of the class's members; any parts
    after that are the value's own (not checked).

    Returns:
        Whether it holds.

    """
    for position, part in enumerate(rest):
        submodule = f'{module}.{part}'
        if submodule in index.modules:
            module = submodule
            continue
        if part not in index.modules.get(module, set()):
            return False
        following = rest[position + 1 :]
        if following and part in index.classes:
            return following[0] in index.classes[part]
        return True
    return True


def name_holds(*, name: str, index: CodeIndex) -> bool | None:
    """Return whether a dotted name is defined, or None when it is nothing of the project's.

    A lowercase first part may be an instance named for its class: the name holds when a class
    whose name holds its words (``camera``: ``Camera2D``; ``scene_start``: ``SceneStart``) has
    the member. Otherwise the first part decides whose name it is: a module (``glitchygames``,
    ``synth``), else a class (``Scene``).

    Args:
        name: The dotted name (no call parentheses).
        index: What the project defines.

    Returns:
        True or False for a name of the project's; None for another library's.

    """
    parts = name.split('.')
    head, member = parts[0], parts[1]
    head_words = head.replace('_', '')
    if head.islower() and any(
        head_words in class_name.lower() and member in members
        for class_name, members in index.classes.items()
    ):
        return True
    modules = {head} if head in index.modules else index.short_modules.get(head, set())
    if modules:
        return any(
            _module_path_holds(module=module, rest=parts[1:], index=index)
            for module in sorted(modules)
        )
    if head in index.classes:
        return member in index.classes[head]
    return None


def file_name_holds(*, file_name: str, index: CodeIndex) -> bool:
    """Return whether a tracked Python file has this name (or, for ``_x.py``, this ending).

    Returns:
        Whether it holds.

    """
    if file_name in index.file_names:
        return True
    return file_name.startswith('_') and any(name.endswith(file_name) for name in index.file_names)


def option_holds(*, option: str, option_text: str) -> bool:
    """Return whether the project spells an option anywhere it could define one.

    Returns:
        Whether the option is spelled (quoted or bare, never as part of a longer option).

    """
    return re.search(rf'(?<![\w-]){re.escape(option)}(?![\w-])', option_text) is not None


def option_source_text(*, project_root: Path, files: Iterable[str]) -> str:
    """Return the text an option the project defines would be spelled in.

    Every tracked Python file (sources, scripts, the tests' command lines) and the project's
    configuration (``OPTION_SOURCES``).

    Returns:
        Their texts, joined.

    """
    texts: list[str] = []
    for relative in files:
        if relative.endswith('.py') or relative.startswith(OPTION_SOURCES):
            try:
                texts.append((project_root / relative).read_text(encoding='utf-8'))
            except OSError, UnicodeDecodeError:
                continue
    return '\n'.join(texts)


def bug_statuses(*, project_root: Path) -> dict[int, str]:
    """Return each BUGS.md entry's number and the first word of its status.

    Returns:
        Entry number -> status word (``Fixed``, ``Active``, ``Closed``...); empty without a
        BUGS.md.

    """
    bugs = project_root / 'BUGS.md'
    statuses: dict[int, str] = {}
    if not bugs.is_file():
        return statuses
    number: int | None = None
    for line in bugs.read_text(encoding='utf-8').splitlines():
        heading = BUG_HEADING.match(line)
        if heading is not None:
            number = int(heading.group('number'))
            continue
        status = BUG_STATUS.match(line)
        if status is not None and number is not None and number not in statuses:
            statuses[number] = status.group('status')
    return statuses


def stale_bug_references(*, line: str, statuses: dict[int, str]) -> list[str]:
    """Return the closed BUGS.md entries a line calls open.

    Returns:
        ``#N (Status)`` for each, when the line has open wording.

    """
    if OPEN_WORDING.search(line) is None:
        return []
    return [
        f'#{match.group("number")} ({statuses[int(match.group("number"))]})'
        for match in BUG_REFERENCE.finditer(line)
        if statuses.get(int(match.group('number'))) in CLOSED_STATUSES
    ]


def backticked_claim(*, token: str, evidence: Evidence) -> tuple[str, str] | None:
    """Return the claim one backticked token makes that does not hold, if any.

    Returns:
        (kind, text), or None when it holds or is no claim a check can read.

    """
    if PYTHON_FILE_NAME.match(token):
        holds = file_name_holds(file_name=token, index=evidence.index)
        return None if holds else ('file', token)
    dotted = DOTTED_NAME.match(token)
    if dotted is not None:
        name = dotted.group('name')
        if name.rsplit('.', 1)[-1] in FILE_EXTENSIONS:
            return None
        holds_or_unknown = name_holds(name=name, index=evidence.index)
        return ('name', token) if holds_or_unknown is False else None
    option = OPTION.match(token)
    if option is not None and not option_holds(
        option=option.group('option'), option_text=evidence.option_text
    ):
        return ('option', option.group('option'))
    return None


def document_claims(*, document: str, text: str, evidence: Evidence) -> list[Claim]:
    """Return every claim in one document that the code does not back.

    Fenced code is read for paths, names and options too (commands and examples are claims);
    BUGS.md references are read in prose only. A recorded exception is left out.

    Returns:
        The claims, in line order.

    """
    found: list[tuple[int, str, str]] = []
    for line_number, line, fenced in document_lines(text):
        found.extend(
            (line_number, 'path', path)
            for path in missing_paths(
                line=line,
                project_root=evidence.project_root,
                roots=evidence.member_roots,
            )
        )
        for backticked in BACKTICKED.findall(line):
            claim = backticked_claim(token=backticked.strip(), evidence=evidence)
            if claim is not None:
                found.append((line_number, *claim))
        if not fenced:
            found.extend(
                (line_number, 'bug', reference)
                for reference in stale_bug_references(line=line, statuses=evidence.bug_statuses)
            )
    return [
        Claim(document=document, line_number=line_number, kind=kind, text=claim_text)
        for line_number, kind, claim_text in found
        if (document, claim_text) not in RECORDED_EXCEPTIONS
    ]


def all_claims(*, project_root: Path, kinds: Sequence[str] = CLAIM_KINDS) -> list[Claim]:
    """Return every living document's claims that the code does not back.

    Args:
        project_root: The repository.
        kinds: The kinds of claim to list.

    Returns:
        The claims, by document then line.

    """
    files = tracked_files(project_root=project_root)
    evidence = Evidence(
        project_root=project_root,
        index=code_index(project_root=project_root, files=files),
        option_text=option_source_text(project_root=project_root, files=files),
        bug_statuses=bug_statuses(project_root=project_root),
        member_roots=member_roots(project_root=project_root, files=files),
    )
    claims: list[Claim] = []
    for document in living_documents(project_root=project_root, files=files):
        text = (project_root / document).read_text(encoding='utf-8')
        claims.extend(
            claim
            for claim in document_claims(document=document, text=text, evidence=evidence)
            if claim.kind in kinds
        )
    return claims


def main(argv: Sequence[str] | None = None) -> int:
    """Write the claims and return the exit status.

    Returns:
        ``ExitCode.SUCCESS`` when there is none, ``CLAIMS_FOUND`` otherwise.

    """
    parser = argparse.ArgumentParser(
        description='List the claims in the living documentation that the code no longer backs.'
    )
    parser.add_argument(
        '--kind',
        action='append',
        choices=CLAIM_KINDS,
        help='list only claims of this kind (repeatable; default: every kind)',
    )
    arguments = parser.parse_args(argv)
    claims = all_claims(project_root=PROJECT_ROOT, kinds=arguments.kind or CLAIM_KINDS)
    sys.stdout.writelines(f'{claim.describe()}\n' for claim in claims)
    sys.stderr.write(f'{len(claims)} claims\n')
    return ExitCode.SUCCESS if not claims else CLAIMS_FOUND


if __name__ == '__main__':
    sys.exit(main())
