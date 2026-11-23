"""Every field a script reads from a command's output is one a name can't move.

A field counted from the start of a line is moved by anything before it that holds a space or a
line break: setup.sh read df's fourth field, which a filesystem name with a space moved onto
Used (bugs/2026-11-20-free-space-read-from-the-wrong-column.md), and its checksum kept the escape
mark sha256sum puts before a name holding a backslash or a line break
(bugs/2026-11-19-model-checksum-kept-the-escape-mark.md).

So this scans the shell and Ansible files under ``ansible/``, ``scripts/`` and ``services/`` for
field reads (awk's ``$N``/``$NF``, ``cut -f``, ``read -r`` into two or more names, Jinja's
``.split()[N]``), and holds each to ``REVIEWED_FIELD_READERS``: the line as written, with why no
name can move what it reads. A new reader, or a changed one, fails until it is reviewed and
listed; a listed line that is gone fails too, so the list stays true.

What a line scan can't see: a read whose command and field are on different lines (an awk
program continued from the line before), a field taken by a tool it doesn't name (``sed``,
``grep -o``, parameter expansion), and Python reading a command's output. The free-space and
checksum readers have behaviour tests of their own (``tests/test_ansible_ai_service.py``).
"""

from __future__ import annotations

import re

from tests.ast_scanning import PROJECT_ROOT

SCANNED_DIRECTORIES = ('ansible', 'scripts', 'services')
SCANNED_SUFFIXES = ('.j2', '.sh', '.yml', '.yaml')
SHELL_FIELD_READ = re.compile(
    r'awk\b[^|]*\$(\d+|NF)\b|\bcut\b[^|]*\s-f\s*\d|\bread\s+-r\s+\w+\s+\w+'
)
JINJA_FIELD_READ = re.compile(r'\.split\([^)]*\)\s*\[')

DEB_POSTRM = 'ansible/roles/ai_package/templates/deb-postrm.sh.j2'
DEB_PRERM = 'ansible/roles/ai_package/templates/deb-prerm.sh.j2'
PLATFORM_FUNCTIONS = 'ansible/roles/ai_service/templates/platform_functions.sh.j2'
LLAMA_CPP_LINUX = 'ansible/roles/llama_cpp/tasks/linux.yml'
PI_BENCHMARK = 'scripts/raspberry_pi_llama_cpp/benchmark_llama_cpp.sh'

LOGIN_DEFS = 'login.defs lines are a keyword and a number; the number must be digits'
MEMINFO = "/proc/meminfo's lines are a label, a number and a unit; no name"
HASH_FROM_STANDARD_INPUT = (
    'the file is read on standard input, so the line names no file, only "-" '
    '(bugs/2026-11-19-model-checksum-kept-the-escape-mark.md)'
)
CORE_RANKING = 'the script builds each line itself: a capacity and a core number'
LIBSTDCXX_SEARCH = (
    'the search task prints two version numbers (GLIBCXX and CXXABI) and nothing else, and '
    'the assert before it checks there are exactly two'
)
PLACEMENT = "the service's own placement lines: a role word and a core list"
SYSFS_TEMPERATURE = 'the thermal zone file holds one number'
VCGENCMD = "vcgencmd's answers are name=value with fixed names and numeric values"
LOADAVG = "/proc/loadavg's first fields are numbers"
FREE = "free's Mem: line is a label and numbers"
RSS = 'ps -o rss= prints the number alone, with no header and no name'
PROC_STAT = (
    'field 2 of /proc/PID/stat is the process name, which can hold a space; the process is '
    'llama-server, which this script starts, so the name is fixed (a diagnostic, never a decision)'
)
MEMORY_EVENTS = 'cgroup memory.events lines are a fixed key and a number'

# File -> each field-reading line as written (stripped) -> why no name can move the field it reads
REVIEWED_FIELD_READERS: dict[str, dict[str, str]] = {
    DEB_POSTRM: {
        (
            'uid_min=$(awk \'$1 == "UID_MIN" && $2 ~ /^[0-9]+$/ { value = $2 } '
            'END { print value + 0 }\' "$login_defs_file" 2>/dev/null)'
        ): LOGIN_DEFS,
        (
            'uid_max=$(awk \'$1 == "UID_MAX" && $2 ~ /^[0-9]+$/ { value = $2 } '
            'END { print value + 0 }\' "$login_defs_file" 2>/dev/null)'
        ): LOGIN_DEFS,
        '| while IFS=: read -r user home; do': (
            'passwd fields hold no colon, and the home is the last name read, so read keeps any '
            'space in it; a home with a line break is skipped (the comment above it)'
        ),
        'size=$(bounded_du "$folder" 2>/dev/null | awk \'NR == 1 { print $1 }\')': (
            'du prints the size first; a line break in the name would start a second line, and '
            'only the first is read (bugs/2026-11-19-model-checksum-kept-the-escape-mark.md)'
        ),
    },
    DEB_PRERM: {
        "for user in $(printf '%s\\n' \"$users\" | awk '{ print $2 }'); do": (
            "loginctl's lines are a uid and a user name, and a user name holds no space"
        ),
    },
    PLATFORM_FUNCTIONS: {
        "awk '/^MemTotal:/ { print int($2 / 1024) }' /proc/meminfo": MEMINFO,
        "awk '/^MemAvailable:/ { print int($2 / 1024) }' /proc/meminfo": MEMINFO,
        'sha256sum < "$1" | cut -d \' \' -f 1': HASH_FROM_STANDARD_INPUT,
        'shasum -a 256 < "$1" | cut -d \' \' -f 1': HASH_FROM_STANDARD_INPUT,
        (
            "ranked=$(printf '%s' \"$ranking\" | sort -k 1,1nr -k 2,2n | cut -d ' ' -f 2)"
        ): CORE_RANKING,
        "ranked=$(printf '%s' \"$ranking\" | cut -d ' ' -f 2)": CORE_RANKING,
    },
    LLAMA_CPP_LINUX: {
        (
            '- llama_cpp_libstdcxx_search.stdout.split()[0] in llama_cpp_glibcxx_releases'
        ): LIBSTDCXX_SEARCH,
        (
            '- llama_cpp_libstdcxx_search.stdout.split()[1] in llama_cpp_cxxabi_releases'
        ): LIBSTDCXX_SEARCH,
        (
            'llama_cpp_glibcxx_gcc: "{{ llama_cpp_glibcxx_releases'
            '[llama_cpp_libstdcxx_search.stdout.split()[0]] }}"'
        ): LIBSTDCXX_SEARCH,
        (
            'llama_cpp_cxxabi_gcc: "{{ llama_cpp_cxxabi_releases'
            '[llama_cpp_libstdcxx_search.stdout.split()[1]] }}"'
        ): LIBSTDCXX_SEARCH,
    },
    PI_BENCHMARK: {
        'game_cores=$(awk \'$1 == "game" {print $2}\' <<< "$placement")': PLACEMENT,
        '"") ai_cores=$(awk \'$1 == "ai" {print $2}\' <<< "$placement") ;;': PLACEMENT,
        (
            'temperature=$(awk \'{printf "%.1f C", $1/1000}\' '
            '/sys/class/thermal/thermal_zone0/temp 2>/dev/null)'
        ): SYSFS_TEMPERATURE,
        '"$(vcgencmd measure_clock arm | awk -F= \'{printf "%d", $2/1000000}\')" \\': VCGENCMD,
        (
            '"$(awk \'{printf "%.1f", $1/1000}\' /sys/class/thermal/thermal_zone0/temp)" \\'
        ): SYSFS_TEMPERATURE,
        '"$(vcgencmd get_throttled | cut -d= -f2)" \\': VCGENCMD,
        '"$(cut -d\' \' -f1 /proc/loadavg)" >> "$power_samples"': LOADAVG,
        (
            'say "memory: $(free -m | awk \'/^Mem:/ {print $2 " MiB total, " $7 '
            '" MiB available"}\')"'
        ): FREE,
        'say "load before: $(cut -d\' \' -f1-3 /proc/loadavg)"': LOADAVG,
        (
            'say "cores: AI ${ai_cores:-not pinned}; the service would place game '
            '${game_cores:-none}, AI $(awk \'$1 == "ai" {print $2}\' <<< "$placement")"'
        ): PLACEMENT,
        'resident() { ps -o rss= -p "$1" | awk \'{printf "%d MiB", $1/1024}\'; }': RSS,
        'major_faults() { awk \'{print $12}\' "/proc/$1/stat" 2>/dev/null; }': PROC_STAT,
        (
            "printf ', oom kills %s' \"$(awk '$1 == \"oom_kill\" {print $2}' "
            '"$cgroup/memory.events")"'
        ): MEMORY_EVENTS,
        (
            'kill -0 "$bonsai" 2>/dev/null && say "  both loaded: Bonsai $(resident "$bonsai"), '
            'Qwen $(resident "$qwen"); $(free -m | awk \'/^Mem:/ {print $7}\') MiB available"'
        ): FREE,
    },
}


def field_readers(*, lines_by_file: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Find every line that reads a field from a command's output.

    Args:
        lines_by_file: Each scanned file's lines, by its path from the repository.

    Returns:
        ``(file, stripped line)`` for each field read, in file order; comments are skipped.
    """
    found: list[tuple[str, str]] = []
    for path, lines in lines_by_file.items():
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if SHELL_FIELD_READ.search(stripped) or JINJA_FIELD_READ.search(stripped):
                found.append((path, stripped))
    return found


def scanned_files() -> dict[str, list[str]]:
    """Read every shell and Ansible file under the scanned directories, hidden folders left out.

    A hidden folder is never the project's (``services/ai-service/.venv``, ``.pytest_cache``).

    Returns:
        Each file's lines, by its path from the repository.
    """
    lines_by_file: dict[str, list[str]] = {}
    for directory in SCANNED_DIRECTORIES:
        for path in sorted((PROJECT_ROOT / directory).rglob('*')):
            relative = path.relative_to(PROJECT_ROOT)
            if any(part.startswith('.') for part in relative.parts):
                continue
            if path.is_file() and path.name.endswith(SCANNED_SUFFIXES):
                lines_by_file[relative.as_posix()] = path.read_text(encoding='utf-8').splitlines()
    return lines_by_file


def test_every_field_read_from_command_output_is_reviewed():
    """Each field read is listed with why no name moves it, and every listed one still exists."""
    found = field_readers(lines_by_file=scanned_files())
    reviewed = [
        (path, line) for path, readers in REVIEWED_FIELD_READERS.items() for line in readers
    ]

    unreviewed = [reader for reader in found if reader not in reviewed]
    assert unreviewed == [], (
        'read a field a name cannot move (print only the value, read it on standard input), '
        f'then list the line with why: {unreviewed}'
    )
    gone = [reader for reader in reviewed if reader not in found]
    assert gone == [], f'listed field readers no longer in the files: {gone}'


def test_the_scan_finds_the_free_space_read_it_was_written_for():
    """The df read that shifted on a filesystem name with a space is found, in each form it had.

    Planted as setup.sh and the llama.cpp check wrote it before the fix, with the checksum's
    old form, so the scan can fail; a comment naming one is not a read.
    """
    planted = {
        'setup.sh.j2': ['    available_kb=$(df -k "$models" | tail -1 | awk \'{print $4}\')'],
        'main.yml': ['        that: (llama_cpp_disk.stdout_lines[-1].split()[3] | int) >= 4096'],
        'checksum.sh': ['    sha256sum "$1" | cut -d " " -f 1'],
        'comment.sh': ["# awk '{print $4}' in a comment is no read"],
    }

    assert field_readers(lines_by_file=planted) == [
        ('setup.sh.j2', 'available_kb=$(df -k "$models" | tail -1 | awk \'{print $4}\')'),
        ('main.yml', 'that: (llama_cpp_disk.stdout_lines[-1].split()[3] | int) >= 4096'),
        ('checksum.sh', 'sha256sum "$1" | cut -d " " -f 1'),
    ]
