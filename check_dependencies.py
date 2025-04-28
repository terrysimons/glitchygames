#!/usr/bin/env python3
"""Check if all required dependencies are installed."""

import sys
import importlib.util

def check_module(module_name):
    """Check if a module is installed."""
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        print(f"❌ {module_name} is NOT installed")
        return False
    else:
        print(f"✅ {module_name} is installed")
        return True

# List of required modules
required_modules = [
    "pygame",
    "yaml",
    "cookiecutter",
    "configparser",
    "toml"
]

all_installed = True
print("Checking required dependencies:")
for module in required_modules:
    if not check_module(module):
        all_installed = False

# Check Python version
print(f"\\nPython version: {sys.version}")
if sys.version_info < (3, 9):
    print("❌ Python version should be at least 3.9")
    all_installed = False
else:
    print("✅ Python version is compatible")

# Try to import specific modules from the project
print("\\nChecking project modules:")
try:
    from glitchygames.engine import GameEngine
    print("✅ GameEngine imported successfully")
except ImportError as e:
    print(f"❌ Failed to import GameEngine: {e}")
    all_installed = False

try:
    from glitchygames.scenes import Scene
    print("✅ Scene imported successfully")
except ImportError as e:
    print(f"❌ Failed to import Scene: {e}")
    all_installed = False

if all_installed:
    print("\\n✅ All dependencies are properly installed!")
else:
    print("\\n❌ Some dependencies are missing. Please install them and try again.")