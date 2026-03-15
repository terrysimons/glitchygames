#!/usr/bin/env python3
"""Test script to run paddleslap with debug logging enabled."""

import logging
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

# Set up debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Import and run the game
from glitchygames.examples.paddleslap import main  # noqa: E402

LOG = logging.getLogger(__name__)

if __name__ == "__main__":
    LOG.debug("=== DEBUG BALL MOVEMENT TEST ===")
    LOG.debug("Running paddleslap with debug logging enabled...")
    LOG.debug("Look for BALL MOVE, BALL BOUNCE, and PADDLE HIT messages")
    LOG.debug("Press Ctrl+C to stop when you see the weird movement")
    LOG.debug("=" * 50)

    try:
        main()
    except KeyboardInterrupt:
        LOG.debug("\n=== DEBUG TEST STOPPED ===")
        LOG.debug("Check the debug output above for any weird ball movement patterns")
