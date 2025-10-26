#!/usr/bin/env python3
"""A minimal test script for GlitchyGames."""

import logging
import sys

# Configure logging to output to console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

LOG = logging.getLogger("test_script")
LOG.info("Starting test script")

try:
    import pygame
    LOG.info(f"Pygame version: {pygame.version.ver}")
    
    pygame.init()
    LOG.info("Pygame initialized successfully")
    
    from glitchygames.engine import GameEngine
    from glitchygames.scenes import Scene
    
    class TestScene(Scene):
        """A minimal test scene."""
        
        NAME = "Test Scene"
        VERSION = "0.1"
        
        def __init__(self, options=None):
            """Initialize the test scene."""
            super().__init__(options=options or {})
            LOG.info("TestScene initialized")
            
        def update(self):
            """Update the scene."""
            LOG.info("TestScene update called")
            
    LOG.info("Starting GameEngine")
    
    # Only initialize the engine, don't start it yet
    engine = GameEngine(game=TestScene)
    LOG.info("GameEngine initialized successfully")
    
    # Print some system info
    LOG.info(f"Display driver: {pygame.display.get_driver()}")
    LOG.info(f"Display info: {pygame.display.Info()}")
    
    LOG.info("Test completed successfully!")
    
except Exception as e:
    LOG.exception(f"Error during test: {e}")
    
finally:
    pygame.quit()
    LOG.info("Test script finished")