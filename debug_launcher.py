#!/usr/bin/env python3
"""Debug launcher for GlitchyGames."""

import os
import sys
import traceback
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

LOG = logging.getLogger("debug_launcher")

def main():
    """Main function to launch GlitchyGames modules with debugging."""
    parser = argparse.ArgumentParser(description="Debug launcher for GlitchyGames")
    parser.add_argument("module", choices=["joystick", "paddle", "bitmappy"], 
                        help="Module to launch")
    parser.add_argument("--resolution", default="800x480", 
                        help="Screen resolution (default: 800x480)")
    parser.add_argument("--windowed", action="store_true", 
                        help="Run in windowed mode")
    
    args = parser.parse_args()
    
    LOG.info(f"Launching {args.module} with resolution {args.resolution}")
    
    try:
        # Set environment variables for better debugging
        os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"  # Hide pygame welcome message
        
        # Import the appropriate module based on user selection
        if args.module == "joystick":
            LOG.info("Importing joystick_demo")
            from glitchygames.examples import joystick_demo
            LOG.info("Starting joystick_demo")
            joystick_demo.main()
        elif args.module == "paddle":
            LOG.info("Importing paddleslap")
            from glitchygames.examples import paddleslap
            LOG.info("Starting paddleslap")
            paddleslap.main()
        elif args.module == "bitmappy":
            LOG.info("Importing bitmappy")
            from glitchygames.tools import bitmappy
            LOG.info("Starting bitmappy")
            bitmappy.main()
        
    except ImportError as e:
        LOG.error(f"Failed to import module: {e}")
        LOG.error(f"Python path: {sys.path}")
        LOG.error(traceback.format_exc())
    except Exception as e:
        LOG.error(f"Error running module: {e}")
        LOG.error(traceback.format_exc())

if __name__ == "__main__":
    main()