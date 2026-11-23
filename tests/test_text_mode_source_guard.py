"""Every shipped package reads and writes its text files in text mode, with the default newline.

The owner's rule (2026-11-22): a file glitchygames writes for a person (a sprite, a sound file,
a recipe, Bitmappy's settings, a game save) has the OS's line ends, CRLF on Windows, so they
can open and change it in their usual text editor; a file is read in text mode and the string
parsed, so CRLF, an old Mac's lone CR and LF all load the same. Python's text mode does both
halves: ``read_text`` (or ``open`` with the default ``newline=None``) reads every line end as
LF, and ``write_text`` (or ``open('w')``) writes LF as the OS's line end.

So no shipped module (the engine, every app, game and demo) calls ``tomllib.load`` or
``tomli_w.dump`` (both take a binary file), reads or writes bytes, opens a file in a binary
mode, or passes an empty or line-feed ``newline``, except where ALLOWED_BINARY says, each for
its reason and as many times as given. A file that is genuinely binary (an image, a sound, a
compressed trace) joins ALLOWED_BINARY with its reason. The scan names the top-level class or
function, so an allowance covers it whole; its count keeps a second call there from passing
unseen.

This scans every package's source as files (it imports none of them), so it is a test of the
repository and lives in its own file.
"""

from __future__ import annotations

import pytest

from tests.ast_scanning import PROJECT_ROOT, untranslated_text_calls

SOURCE = PROJECT_ROOT / 'src'
PACKAGE_ROOTS = [SOURCE / 'glitchygames'] + [
    member / 'src'
    for layer in ('apps', 'games', 'demos')
    for member in sorted((SOURCE / layer).iterdir())
    if (member / 'src').is_dir()
]
MODULES = sorted(
    path.relative_to(SOURCE).as_posix() for root in PACKAGE_ROOTS for path in root.rglob('*.py')
)

# (module under src/, top-level class or function) -> (how many such calls it may hold, why)
ALLOWED_BINARY = {
    ('glitchygames/api/client.py', 'extract_frames'): (
        1,
        'reads an APNG image to send base64-encoded',
    ),
    ('glitchygames/api/client.py', 'save_files_locally'): (
        2,
        'writes the generated APNG and PNG images',
    ),
    ('glitchygames/api/client.py', '_save_apng_extracted_frames'): (
        1,
        'writes each extracted frame as a PNG image',
    ),
    ('glitchygames/api/sprite_requests.py', 'save_sprite_files'): (
        2,
        'writes the generated PNG image and its frames as PNG images',
    ),
    ('glitchygames/audio/cache_inventory.py', 'verify'): (
        1,
        'reads a compiled sound cache file (samples) to check it',
    ),
    ('glitchygames/audio/disk_cache.py', 'DiskSoundCache'): (
        1,
        'reads a compiled sound cache file (samples)',
    ),
    ('glitchygames/audio/offline.py', 'write_wave_file'): (
        1,
        'writes a WAV file',
    ),
    ('glitchygames/cpu_placement.py', 'read_cpu_placement'): (
        1,
        'reads a JSON placement for pydantic, which takes bytes; line ends are JSON whitespace',
    ),
    ('glitchygames/output_files.py', 'output_refusal'): (
        1,
        "opens the output 'ab' only to learn whether it can be written; writes nothing",
    ),
    ('glitchygames/pixels/pixel.py', 'pixels_from_path'): (
        1,
        'reads raw pixel bytes',
    ),
    ('glitchygames/recording_metrics.py', 'append_ledger_rows'): (
        1,
        'reads the last byte to learn whether a cut write left the last line unended',
    ),
    ('glitchygames/tracing.py', 'TraceWriter'): (
        1,
        'writes a gzip-compressed trace',
    ),
    ('glitchygames/tracing.py', 'TraceReader'): (
        1,
        'reads a gzip-compressed trace',
    ),
}


def unexpected_calls(*, module: str, source: str) -> list[str]:
    """Return each call past text mode in a module beyond what ALLOWED_BINARY lets it hold.

    Returns:
        ``module:line in owner`` for each such call of an owner with no allowance, or for every
        such call of an owner holding more than its allowance.

    """
    calls = untranslated_text_calls(source=source)
    unexpected = []
    for owner in sorted({owner for owner, _line in calls}):
        lines = [line for name, line in calls if name == owner]
        allowed_count, _reason = ALLOWED_BINARY.get((module, owner), (0, ''))
        if len(lines) > allowed_count:
            unexpected.extend(f'{module}:{line} in {owner}' for line in lines)
    return unexpected


def test_every_package_is_scanned():
    """An empty scan would pass for any code: the engine, an app, a game and a demo are there."""
    assert {
        'glitchygames/audio/assets.py',
        'glitchygames/state/manager.py',
        'apps/bitmappy/src/bitmappy/alpha.py',
        'games/drawing-fire/src/drawing_fire/swatches.py',
    } <= set(MODULES)
    assert any(module.startswith('demos/') for module in MODULES)


@pytest.mark.parametrize('module', MODULES)
def test_no_module_skips_text_modes_line_ends(module):
    """A module reads with read_text and parses the string, and writes in text mode."""
    source = (SOURCE / module).read_text(encoding='utf-8')

    assert unexpected_calls(module=module, source=source) == [], (
        'Read with read_text and parse the string (tomllib.loads, json.loads); write with '
        'write_text or open("w") and the default newline. A genuinely binary file joins '
        'ALLOWED_BINARY with its count and reason.'
    )


@pytest.mark.parametrize(('module', 'owner'), sorted(ALLOWED_BINARY))
def test_every_allowance_is_still_used_as_many_times(module, owner):
    """A stale allowance would let a new call of that name through unseen."""
    source = (SOURCE / module).read_text(encoding='utf-8')
    allowed_count, _reason = ALLOWED_BINARY[module, owner]

    calls = [line for name, line in untranslated_text_calls(source=source) if name == owner]

    assert len(calls) == allowed_count


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        ("def f(path):\n    tomllib.load(path.open('rb'))\n", [('f', 2), ('f', 2)]),
        ("def f(data, path):\n    tomli_w.dump(data, path.open('wb'))\n", [('f', 2), ('f', 2)]),
        ('def f(path):\n    path.read_bytes()\n', [('f', 2)]),
        ("def f(path):\n    path.write_bytes(b'x')\n", [('f', 2)]),
        ("def f(name):\n    open(name, 'wb')\n", [('f', 2)]),
        ("def f(path):\n    path.open(mode='rb')\n", [('f', 2)]),
        ("def f(path):\n    path.open('w', encoding='utf-8', newline='\\n')\n", [('f', 2)]),
        ("def f(path):\n    path.open('r', encoding='utf-8', newline='')\n", [('f', 2)]),
        ("def f(path):\n    tomllib.loads(path.read_text(encoding='utf-8'))\n", []),
        ("def f(path):\n    path.open('w', encoding='utf-8')\n", []),
        ("def f(path):\n    path.write_text('x', encoding='utf-8')\n", []),
        ('def f(data):\n    tomli_w.dumps(data)\n', []),
        ('def f(stream):\n    json.load(stream)\n', []),
    ],
    ids=[
        'tomllib-load-binary',
        'tomli-w-dump-binary',
        'read-bytes',
        'write-bytes',
        'builtin-open-binary',
        'binary-mode-keyword',
        'newline-lf',
        'newline-empty',
        'read-text-then-parse',
        'text-mode-write',
        'write-text',
        'tomli-w-dumps',
        'json-load-text',
    ],
)
def test_the_scan_finds_every_way_past_text_mode(source, expected):
    """The guard can fail: each way past text mode's translation is found, text mode is not."""
    assert untranslated_text_calls(source=source) == expected


def test_a_second_binary_call_in_an_allowed_owner_is_found():
    """The count holds: a sprite save put back as bytes beside an allowed read is reported."""
    source = (
        'class TraceReader:\n'
        '    def open(self, path):\n'
        "        path.open('rb')\n"
        '    def save(self, path, text):\n'
        "        path.write_bytes(text.encode('utf-8'))\n"
    )

    assert unexpected_calls(module='glitchygames/tracing.py', source=source) == [
        'glitchygames/tracing.py:3 in TraceReader',
        'glitchygames/tracing.py:5 in TraceReader',
    ]
