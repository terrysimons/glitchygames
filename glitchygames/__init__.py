"""GlitchyGames - A Pygame wrapper for low-powered systems."""

import logging
import sys

# Set up a default logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Package version
__version__ = '0.1.0'

# Import submodules for easier access
from glitchygames import color
from glitchygames import engine
from glitchygames import events
from glitchygames import fonts
from glitchygames import interfaces
from glitchygames import movement
from glitchygames import pixels
from glitchygames import scenes
from glitchygames import sprites
from glitchygames import ui

# Initialize pygame when the package is imported
import pygame
pygame.init()