#!/usr/bin/env python3
"""Fix common issues with GlitchyGames."""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def run_command(command):
    """Run a command and return its output."""
    print(f"Running: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    print(f"Success: {result.stdout}")
    return True

# Check if we're in a virtual environment
in_venv = sys.prefix != sys.base_prefix
if not in_venv:
    print("Warning: You are not in a virtual environment. It's recommended to use one.")

# Ensure pip is up to date
print("Updating pip...")
run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

# Install or reinstall dependencies
print("Reinstalling dependencies...")
if os.path.exists("pyproject.toml"):
    # Use poetry if available
    if shutil.which("poetry"):
        run_command(["poetry", "install"])
    else:
        run_command([sys.executable, "-m", "pip", "install", "-e", "."])
else:
    # Fallback to manual installation of key dependencies
    run_command([sys.executable, "-m", "pip", "install", "pygame", "pyyaml", "cookiecutter", "toml"])

# Check for common pygame issues
print("\\nChecking for common pygame issues...")

# Check SDL version
try:
    import pygame
    print(f"Pygame version: {pygame.version.ver}")
    print(f"SDL version: {pygame.get_sdl_version()}")
except ImportError:
    print("Pygame is not installed correctly.")

# Check for display issues
try:
    os.environ['SDL_VIDEODRIVER'] = 'dummy'  # Use dummy driver for headless environments
    pygame.init()
    print("Pygame initialized with dummy driver")
    pygame.quit()
    
    # Reset to default
    if 'SDL_VIDEODRIVER' in os.environ:
        del os.environ['SDL_VIDEODRIVER']
except Exception as e:
    print(f"Pygame initialization issue: {e}")

print("\\nFix completed. Try running your project again.")