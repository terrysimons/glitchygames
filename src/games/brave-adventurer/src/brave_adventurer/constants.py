"""Constants and tuning values for Brave Adventurer (the classic edition).

Its drawn sprites' sizes and colours and its running animation's swing; what both games share
is in brave_adventurer_core.constants.
"""

from __future__ import annotations

# Animation tuning
# Amplitude: pixels of displacement during running animation
ARM_SWING_AMPLITUDE = 2
LEG_SWING_AMPLITUDE = 3

# Player dimensions
PLAYER_WIDTH = 32
PLAYER_HEIGHT = 48

# Enemy dimensions
COBRA_WIDTH = 24
COBRA_HEIGHT = 32
SCARAB_WIDTH = 20
SCARAB_HEIGHT = 16
SCORPION_WIDTH = 28
SCORPION_HEIGHT = 20

# Collectible
GOLD_SCARAB_SIZE = 16

# Egyptian color palette: the sprites
PLAYER_SKIN = (180, 130, 80)
PLAYER_CLOTH = (220, 220, 200)
PLAYER_HAIR = (40, 30, 20)
PLAYER_BELT = (160, 100, 40)
COBRA_BODY = (80, 120, 60)
COBRA_HOOD = (60, 100, 40)
COBRA_EYE = (200, 50, 50)
SCARAB_BODY = (40, 60, 100)
SCARAB_SHELL = (30, 50, 90)
GOLD_COLOR = (220, 190, 50)
GOLD_HIGHLIGHT = (255, 220, 100)
SCORPION_BODY = (100, 60, 30)
SCORPION_TAIL = (120, 70, 35)
