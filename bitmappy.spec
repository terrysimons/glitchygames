# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Bitmappy pixel art editor.

Builds a single-file executable with all required data files bundled.
Platform-agnostic — PyInstaller handles OS-specific binary formats automatically:
  - Linux:   dist/bitmappy
  - macOS:   dist/bitmappy  (set PYINSTALLER_TARGET_ARCH=universal2 for fat binary)
  - Windows: dist/bitmappy.exe

Usage (via nox):
    nox -s build-binary
    nox -s build            # binary + wheel

Usage (direct):
    pyinstaller bitmappy.spec --distpath dist/ --noconfirm

Environment variables:
    PYINSTALLER_TARGET_ARCH — macOS only. Set to "universal2" to build a fat binary
                              containing both arm64 and x86_64 slices. Requires a
                              universal2 Python interpreter. Defaults to None (native).
"""

import os

# Read target architecture from environment (macOS universal2 support).
# None means "use the current interpreter's architecture".
_target_arch = os.environ.get('PYINSTALLER_TARGET_ARCH') or None

a = Analysis(
    ['scripts/bitmappy_entry.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Fonts — font_manager.py resolves via Path(__file__).parent / 'bitstream_vera'
        ('glitchygames/fonts/bitstream_vera', 'glitchygames/fonts/bitstream_vera'),
        # Color palettes — palette.py resolves via Path(__file__).parent / 'resources'
        ('glitchygames/color/resources', 'glitchygames/color/resources'),
        # Editor assets — eraser.toml, raspberry.toml, icons
        ('glitchygames/assets', 'glitchygames/assets'),
        # Editor resources — bitmappy.png icon, bitmappy.cfg
        ('glitchygames/bitmappy/resources', 'glitchygames/bitmappy/resources'),
        # Sprite examples — AI training data loaded via SPRITE_CONFIG_DIR
        ('glitchygames/examples/resources/sprites', 'glitchygames/examples/resources/sprites'),
    ],
    hiddenimports=[
        # Conditionally imported at runtime (inside try/except or function bodies)
        'glitchygames.performance',
        'glitchygames.performance.adaptive_clamping',
        'apng',
        'pyperclip',
        'speech_recognition',
        'miniaudio',
        'glitchygames.events.voice',
        'glitchygames.events.voice_miniaudio',
        'glitchygames.events.voice_backends.voice_portaudio',
        # numpy is required by pygame.surfarray (array3d/array4d)
        'numpy',
        # pygame._sdl2 (imported by glitchygames.events.controller) imports its audio
        # extension at package import; PyInstaller's analysis currently finds it, but it is
        # listed so the binary cannot lose it (BUGS.md #48)
        'pygame._sdl2.audio',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Dev/build/lint tools — not needed at runtime
        'pytest',
        'nox',
        'ruff',
        'bandit',
        'safety',
        'basedpyright',
        'mkdocs',
        'deptry',
        'vulture',
        'wily',
        'hypothesis',
        'pip_audit',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='bitmappy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=_target_arch,
    codesign_identity=None,
    entitlements_file=None,
)
