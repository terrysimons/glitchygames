# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Bitmappy pixel art editor.

Builds a single-file executable with all required data files bundled.
Platform-agnostic — PyInstaller handles OS-specific binary formats automatically:
  - Linux:   dist/bitmappy
  - macOS:   dist/bitmappy  (the build machine's architecture; see PYINSTALLER_TARGET_ARCH)
  - Windows: dist/bitmappy.exe

Usage (via nox):
    nox -s build-binary
    nox -s build            # binary + wheel

Usage (direct):
    pyinstaller bitmappy.spec --distpath dist/ --noconfirm

Environment variables:
    PYINSTALLER_TARGET_ARCH — macOS only. Set to "universal2" to build a fat binary
                              containing both arm64 and x86_64 slices. Requires a
                              universal2 Python interpreter and every compiled extension
                              fat; PyInstaller fails otherwise, it does not fall back.
                              CI cannot: numpy, scipy, pandas, Pillow and pydantic-core
                              ship arm64-only wheels for Python 3.14 (2026-10-21).
                              Defaults to None (native).
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
        ('src/glitchygames/fonts/bitstream_vera', 'glitchygames/fonts/bitstream_vera'),
        # Color palettes — palette.py resolves via Path(__file__).parent / 'resources'
        ('src/glitchygames/color/resources', 'glitchygames/color/resources'),
        # Editor assets — eraser.toml, raspberry.toml, icons
        ('src/glitchygames/assets', 'glitchygames/assets'),
        # Bitmappy's resources — the bitmappy.png icon, bitmappy.cfg, and the sprite library (AI
        # training data). editor.py and utils.py resolve them via Path(__file__).parent /
        # 'resources', and a bundled module's __file__ is under _MEIPASS, at bitmappy/
        ('src/apps/bitmappy/src/bitmappy/resources', 'bitmappy/resources'),
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
    # Project hooks: hook-aisuite.py bundles aisuite's providers, which it finds by globbing
    # *_provider.py files on disk (otherwise AI requests fail with "Supported providers: set()")
    hookspath=['packaging/pyinstaller_hooks'],
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
