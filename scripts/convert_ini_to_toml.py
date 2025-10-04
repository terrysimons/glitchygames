#!/usr/bin/env python3
"""
Simple INI to TOML converter that manually parses INI files and creates TOML files.
"""

import os
import sys
import configparser
from pathlib import Path


def convert_ini_to_toml(ini_file_path: str, toml_file_path: str) -> bool:
    """Convert a single .ini sprite file to .toml format."""
    try:
        print(f"Converting {ini_file_path} -> {toml_file_path}")
        
        # Read the INI file
        config = configparser.ConfigParser()
        config.read(ini_file_path)
        
        if not config.has_section('sprite'):
            print(f"  ERROR: No [sprite] section in {ini_file_path}")
            return False
        
        # Get sprite data
        sprite_name = config.get('sprite', 'name', fallback='unknown_sprite')
        pixels_str = config.get('sprite', 'pixels', fallback='')
        
        if not pixels_str:
            print(f"  ERROR: No pixels data in {ini_file_path}")
            return False
        
        # Clean up pixel data (remove newlines and tabs)
        clean_pixels = pixels_str.replace('\n', '').replace('\t', '')
        
        # Calculate dimensions (assuming square sprites)
        pixel_count = len(clean_pixels)
        width = height = int(pixel_count ** 0.5)
        
        if width * height != pixel_count:
            print(f"  ERROR: Invalid pixel count {pixel_count} in {ini_file_path}")
            return False
        
        # Format pixels into rows for TOML
        pixel_rows = []
        for y in range(height):
            start = y * width
            end = start + width
            pixel_rows.append(clean_pixels[start:end])
        
        # Create TOML content with proper structure
        toml_content = f'''[sprite]
name = "{sprite_name}"
pixels = """
'''
        for row in pixel_rows:
            toml_content += f'{row}\n'
        toml_content += '"""\n\n[colors]\n'
        
        # Add color definitions
        for section_name in config.sections():
            if section_name.isdigit():
                red = config.getint(section_name, 'red', fallback=0)
                green = config.getint(section_name, 'green', fallback=0)
                blue = config.getint(section_name, 'blue', fallback=0)
                toml_content += f'''[colors.{section_name}]
red = {red}
green = {green}
blue = {blue}

'''
        
        # Write TOML file
        with open(toml_file_path, 'w') as f:
            f.write(toml_content)
        
        # Verify the TOML file can be loaded
        try:
            import toml
            with open(toml_file_path, 'r') as f:
                toml_data = toml.load(f)
            
            # Verify basic structure
            assert 'sprite' in toml_data, "Missing [sprite] section"
            assert 'name' in toml_data['sprite'], "Missing sprite name"
            assert 'pixels' in toml_data['sprite'], "Missing pixels in sprite section"
            assert 'colors' in toml_data, "Missing [colors] section"
            
            # Verify pixel data is a string (block format)
            pixels = toml_data['sprite']['pixels']
            assert isinstance(pixels, str), "Pixel data should be a string (block format)"
            assert len(pixels) > 0, "Pixel data should not be empty"
            
            # Verify dimensions match
            pixel_lines = [line.strip() for line in pixels.split('\n') if line.strip()]
            assert len(pixel_lines) == height, f"Expected {height} lines, got {len(pixel_lines)}"
            assert all(len(line) == width for line in pixel_lines), f"All lines should be {width} characters wide"
            
            print(f"  SUCCESS: Converted {width}x{height} sprite '{sprite_name}' (verified)")
            return True
            
        except Exception as e:
            print(f"  ERROR: TOML verification failed for {toml_file_path}: {e}")
            return False
        
    except Exception as e:
        print(f"  ERROR: Failed to convert {ini_file_path}: {e}")
        return False


def main():
    """Convert all .ini sprite files to .toml format."""
    import argparse
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Convert INI sprite files to TOML format')
    parser.add_argument('--directory', '-d', 
                       default='examples/resources/sprites',
                       help='Directory containing .ini sprite files (default: examples/resources/sprites)')
    parser.add_argument('--recursive', '-r', 
                       action='store_true',
                       help='Search for .ini files recursively in subdirectories')
    
    args = parser.parse_args()
    
    # Find all .ini files in the specified directory
    sprites_dir = Path(args.directory)
    
    if not sprites_dir.exists():
        print(f"ERROR: Directory '{sprites_dir}' does not exist")
        return
    
    if args.recursive:
        ini_files = list(sprites_dir.rglob("*.ini"))
    else:
        ini_files = list(sprites_dir.glob("*.ini"))
    
    if not ini_files:
        print("No .ini files found")
        return
    
    print(f"Found {len(ini_files)} .ini sprite files in {sprites_dir}")
    if args.recursive:
        print("(Searching recursively)")
    print("Converting to TOML format...")
    print()
    
    success_count = 0
    error_count = 0
    
    for ini_file in sorted(ini_files):
        # Create corresponding .toml filename
        toml_file = ini_file.with_suffix('.toml')
        
        # Convert the file
        if convert_ini_to_toml(str(ini_file), str(toml_file)):
            success_count += 1
        else:
            error_count += 1
    
    print()
    print(f"Conversion complete!")
    print(f"  Successfully converted: {success_count} files")
    print(f"  Errors: {error_count} files")
    
    if error_count == 0:
        print("All files converted successfully! 🎉")
    else:
        print(f"Some files had errors. Check the output above.")


if __name__ == "__main__":
    main()
