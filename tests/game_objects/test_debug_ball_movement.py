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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Import and run the game
from glitchygames.examples.paddleslap import main

if __name__ == "__main__":
    print("=== DEBUG BALL MOVEMENT TEST ===")
    print("Running paddleslap with debug logging enabled...")
    print("Look for BALL MOVE, BALL BOUNCE, and PADDLE HIT messages")
    print("Press Ctrl+C to stop when you see the weird movement")
    print("=" * 50)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n=== DEBUG TEST STOPPED ===")
        print("Check the debug output above for any weird ball movement patterns")
