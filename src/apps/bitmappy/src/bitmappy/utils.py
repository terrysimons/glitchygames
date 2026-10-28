"""Utility values for the Bitmappy pixel art editor."""

from __future__ import annotations

from pathlib import Path

# The sprite library (AI training data and Bitmappy's example sprites), package data beside this
# module. PyInstaller sets a bundled module's __file__ under sys._MEIPASS, and bitmappy.spec
# bundles the resources at bitmappy/resources there, so this path holds in the frozen app too
# (as src/glitchygames/fonts/font_manager.py's BUNDLED_FONT_DIRECTORY does for the fonts)
SPRITE_CONFIG_DIR = Path(__file__).parent / 'resources' / 'sprites'
