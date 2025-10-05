"""Simple INI to TOML converter that manually parses INI files and creates TOML files."""

import argparse
import configparser
from pathlib import Path

import toml


def convert_ini_to_toml(ini_file_path: str, toml_file_path: str) -> bool:
    """Convert a single .ini sprite file to .toml format."""
    try:
        # Read the INI file
        config = configparser.ConfigParser()
        config.read(ini_file_path)

        if not config.has_section("sprite"):
            return False

        # Get sprite data
        sprite_name = config.get("sprite", "name", fallback="unknown_sprite")
        pixels_str = config.get("sprite", "pixels", fallback="")

        if not pixels_str:
            return False

        # Clean up pixel data and calculate dimensions (assuming square sprites)
        clean_pixels = pixels_str.replace("\n", "").replace("\t", "")
        pixel_count = len(clean_pixels)
        width = height = int(pixel_count**0.5)

        if width * height != pixel_count:
            return False

        # Format pixels into rows for TOML
        pixel_rows = [clean_pixels[y * width : (y + 1) * width] for y in range(height)]

        # Create TOML content with proper structure
        toml_content = f'''[sprite]
name = "{sprite_name}"
pixels = """
'''
        for row in pixel_rows:
            toml_content += f"{row}\n"
        toml_content += '"""\n\n[colors]\n'

        # Add color definitions
        for section_name in config.sections():
            if section_name.isdigit():
                toml_content += f"""[colors.{section_name}]
red = {config.getint(section_name, "red", fallback=0)}
green = {config.getint(section_name, "green", fallback=0)}
blue = {config.getint(section_name, "blue", fallback=0)}

"""

        # Write TOML file
        Path(toml_file_path).write_text(toml_content, encoding="utf-8")

        # Verify the TOML file can be loaded
        try:
            toml_data = toml.loads(Path(toml_file_path).read_text(encoding="utf-8"))
        except toml.TomlDecodeError:
            return False

        # Verify basic structure
        try:
            assert "sprite" in toml_data, "Missing [sprite] section"
            assert "name" in toml_data["sprite"], "Missing sprite name"
            assert "pixels" in toml_data["sprite"], "Missing pixels in sprite section"
            assert "colors" in toml_data, "Missing [colors] section"

            # Verify pixel data is a string (block format)
            pixels = toml_data["sprite"]["pixels"]
            assert isinstance(pixels, str), "Pixel data should be a string (block format)"
            assert len(pixels) > 0, "Pixel data should not be empty"

            # Verify dimensions match
            pixel_lines = [line.strip() for line in pixels.split("\n") if line.strip()]
            assert len(pixel_lines) == height, f"Expected {height} lines, got {len(pixel_lines)}"
            assert all(len(line) == width for line in pixel_lines), (
                f"All lines should be {width} characters wide"
            )
        except AssertionError:
            return False
        else:
            return True
    except (configparser.Error, FileNotFoundError, PermissionError):
        return False


def main():
    """Convert all .ini sprite files to .toml format."""
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Convert INI sprite files to TOML format")
    parser.add_argument(
        "--directory",
        "-d",
        default="examples/resources/sprites",
        help="Directory containing .ini sprite files (default: examples/resources/sprites)",
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="Search for .ini files recursively in subdirectories",
    )

    args = parser.parse_args()

    # Find all .ini files in the specified directory
    sprites_dir = Path(args.directory)

    if not sprites_dir.exists():
        return

    if args.recursive:
        ini_files = list(sprites_dir.rglob("*.ini"))
    else:
        ini_files = list(sprites_dir.glob("*.ini"))

    if not ini_files:
        return

    success_count = 0
    error_count = 0

    for ini_file in sorted(ini_files):
        # Create corresponding .toml filename
        toml_file = ini_file.with_suffix(".toml")

        # Convert the file
        if convert_ini_to_toml(str(ini_file), str(toml_file)):
            success_count += 1
        else:
            error_count += 1

    if error_count == 0:
        pass  # All conversions successful
    else:
        pass  # Some conversions failed


if __name__ == "__main__":
    main()
