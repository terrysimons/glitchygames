"""Audit TOML sprite files and compute tight bounding boxes for hitbox data.

This script scans TOML sprite files, computes the smallest bounding box
enclosing all opaque pixels for each animation frame, and can optionally
write hitbox data back into the TOML files.

Uses engine code from glitchygames.sprites for color map parsing and
bounding box computation -- no pygame initialization required.

Usage:
    # Audit report (default -- read-only)
    uv run python scripts/audit_hitboxes.py

    # Per-frame mode (default) or envelope mode
    uv run python scripts/audit_hitboxes.py --mode per-frame
    uv run python scripts/audit_hitboxes.py --mode envelope

    # Specific priority tier
    uv run python scripts/audit_hitboxes.py --priority 1

    # Single file
    uv run python scripts/audit_hitboxes.py --file path/to/sprite.toml

    # Show diffs without modifying files
    uv run python scripts/audit_hitboxes.py --dry-run

    # Apply hitbox data to TOML files
    uv run python scripts/audit_hitboxes.py --apply
"""

from __future__ import annotations

import argparse
import difflib
import logging
import operator
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

from glitchygames.sprites.animated import AnimatedSprite
from glitchygames.sprites.pixel_utils import (
    compute_bounding_box,
    compute_envelope_bounding_box,
)

log: logging.Logger = logging.getLogger('game.scripts.audit_hitboxes')

# Project root (scripts/ is one level below project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Priority tiers for sprite file discovery
PRIORITY_TIERS: dict[int, list[Path]] = {
    1: [PROJECT_ROOT / 'glitchygames' / 'examples' / 'brave_adventurer_papyrus' / 'sprites'],
    2: [PROJECT_ROOT / 'glitchygames' / 'examples' / 'resources' / 'sprites'],
    3: [
        PROJECT_ROOT / 'glitchygames' / 'assets',
        PROJECT_ROOT / 'sprites',
        PROJECT_ROOT / 'auto-generated' / 'sprites',
    ],
}

PRIORITY_LABELS: dict[int, str] = {
    1: 'Active Game Sprites (Brave Adventurer Papyrus)',
    2: 'Resource Library Sprites',
    3: 'Engine Assets, Flame, Auto-Generated',
}


def discover_toml_files(priority: int | None = None) -> dict[int, list[Path]]:
    """Discover TOML sprite files organized by priority tier.

    Args:
        priority: If specified, only discover files in this priority tier.

    Returns:
        Dict mapping priority tier to list of TOML file paths.

    """
    tiers_to_scan = {priority: PRIORITY_TIERS[priority]} if priority else PRIORITY_TIERS
    discovered: dict[int, list[Path]] = {}

    for tier, directories in tiers_to_scan.items():
        tier_files: list[Path] = []
        for directory in directories:
            if directory.exists():
                tier_files.extend(sorted(directory.rglob('*.toml')))
        # Filter out non-sprite TOML files (e.g., pyproject.toml)
        tier_files = [filepath for filepath in tier_files if filepath.name != 'pyproject.toml']
        if tier_files:
            discovered[tier] = tier_files

    return discovered


def parse_sprite_file(filepath: Path) -> dict[str, Any]:
    """Parse a TOML sprite file and extract sprite data.

    Args:
        filepath: Path to the TOML sprite file.

    Returns:
        Parsed TOML data dict.

    """
    with filepath.open('rb') as toml_file:
        return tomllib.load(toml_file)


def extract_frames(
    data: dict[str, Any],
    color_map: dict[str, tuple[int, ...]],
) -> list[dict[str, Any]]:
    """Extract all animation frames from parsed TOML data.

    Handles both static sprites (single [sprite].pixels) and animated
    sprites (multiple [[animation.frame]] sections).

    Args:
        data: Parsed TOML data.
        color_map: Character-to-color mapping.

    Returns:
        List of frame dicts, each with 'namespace', 'frame_index',
        'pixel_lines', 'width', 'height', and 'bounding_box' keys.

    """
    frames: list[dict[str, Any]] = []

    # Check for static sprite (single frame in [sprite] section)
    sprite_section = data.get('sprite', {})
    if 'pixels' in sprite_section:
        pixel_lines = AnimatedSprite.parse_toml_pixel_lines(sprite_section['pixels'])
        width = max(len(line) for line in pixel_lines) if pixel_lines else 0
        height = len(pixel_lines)
        bounding_box = compute_bounding_box(pixel_lines, color_map)
        frames.append({
            'namespace': 'static',
            'frame_index': 0,
            'pixel_lines': pixel_lines,
            'width': width,
            'height': height,
            'bounding_box': bounding_box,
        })
        return frames

    # Animated sprite: iterate [[animation]] sections
    animations = data.get('animation', [])
    for animation in animations:
        namespace = animation.get('namespace', 'default')
        animation_frames = animation.get('frame', [])
        for frame_index, frame_data in enumerate(animation_frames):
            pixel_data = frame_data.get('pixels', '')
            pixel_lines = AnimatedSprite.parse_toml_pixel_lines(pixel_data)
            width = max(len(line) for line in pixel_lines) if pixel_lines else 0
            height = len(pixel_lines)
            bounding_box = compute_bounding_box(pixel_lines, color_map)
            frames.append({
                'namespace': namespace,
                'frame_index': frame_index,
                'pixel_lines': pixel_lines,
                'width': width,
                'height': height,
                'bounding_box': bounding_box,
            })

    return frames


def analyze_sprite(filepath: Path) -> dict[str, Any]:
    """Analyze a single sprite file and compute all bounding boxes.

    Args:
        filepath: Path to the TOML sprite file.

    Returns:
        Analysis dict with sprite metadata, per-frame bounding boxes,
        and the recommended hitbox strategy.

    """
    data = parse_sprite_file(filepath)
    sprite_section = data.get('sprite', {})
    sprite_name = sprite_section.get('name', filepath.stem)

    color_map, _color_order, _alpha_values = AnimatedSprite.build_color_map(data)
    frames = extract_frames(data, color_map)

    # Collect non-None bounding boxes
    valid_bounding_boxes = [
        frame['bounding_box'] for frame in frames if frame['bounding_box'] is not None
    ]

    # Determine if all frames share the same bounding box
    minimum_frames_for_comparison = 2
    all_identical = len(valid_bounding_boxes) >= minimum_frames_for_comparison and all(
        bounding_box == valid_bounding_boxes[0] for bounding_box in valid_bounding_boxes[1:]
    )

    envelope = compute_envelope_bounding_box(valid_bounding_boxes)

    # Group frames by namespace for reporting
    namespaces: dict[str, list[dict[str, Any]]] = {}
    for frame in frames:
        namespace = frame['namespace']
        if namespace not in namespaces:
            namespaces[namespace] = []
        namespaces[namespace].append(frame)

    # Determine frame dimensions (use first frame)
    frame_width = frames[0]['width'] if frames else 0
    frame_height = frames[0]['height'] if frames else 0

    return {
        'filepath': filepath,
        'sprite_name': sprite_name,
        'frame_width': frame_width,
        'frame_height': frame_height,
        'total_frames': len(frames),
        'animation_count': len(namespaces),
        'namespaces': namespaces,
        'frames': frames,
        'all_identical': all_identical,
        'envelope': envelope,
        'valid_bounding_boxes': valid_bounding_boxes,
    }


def format_bounding_box(bounding_box: dict[str, int] | None) -> str:
    """Format a bounding box for display.

    Args:
        bounding_box: Bounding box dict or None.

    Returns:
        Formatted string representation.

    """
    if bounding_box is None:
        return '(fully transparent)'
    return (
        f'hitbox({bounding_box["offset_x"]}, {bounding_box["offset_y"]}, '
        f'{bounding_box["width"]}, {bounding_box["height"]})'
    )


def compute_padding_percent(
    bounding_box: dict[str, int],
    frame_width: int,
    frame_height: int,
) -> float:
    """Compute percentage of frame area that is transparent padding.

    Args:
        bounding_box: The tight bounding box.
        frame_width: Full frame width.
        frame_height: Full frame height.

    Returns:
        Padding percentage (0.0 to 100.0).

    """
    frame_area = frame_width * frame_height
    if frame_area == 0:
        return 0.0
    hitbox_area = bounding_box['width'] * bounding_box['height']
    return (1.0 - hitbox_area / frame_area) * 100.0


def _log_sprite_analysis(analysis: dict[str, Any]) -> bool:
    """Log analysis for a single sprite and return whether it needs per-frame hitboxes.

    Args:
        analysis: Single sprite analysis result.

    Returns:
        True if the sprite needs per-frame hitboxes.

    """
    filepath = analysis['filepath']
    relative_path = filepath.relative_to(PROJECT_ROOT)
    dimensions = f'{analysis["frame_width"]}x{analysis["frame_height"]}'
    anim_count = analysis['animation_count']
    frame_count = analysis['total_frames']

    log.info(
        '  %s (%s, %d animation(s), %d frame(s))',
        relative_path,
        dimensions,
        anim_count,
        frame_count,
    )

    for namespace, namespace_frames in analysis['namespaces'].items():
        log.info('    %s (%d frame(s)):', namespace, len(namespace_frames))
        for frame in namespace_frames:
            bounding_box = frame['bounding_box']
            bbox_str = format_bounding_box(bounding_box)
            if bounding_box is not None:
                padding = compute_padding_percent(
                    bounding_box,
                    frame['width'],
                    frame['height'],
                )
                log.info(
                    '      frame %d: %s -- %.0f%% padding',
                    frame['frame_index'],
                    bbox_str,
                    padding,
                )
            else:
                log.info('      frame %d: %s', frame['frame_index'], bbox_str)

    if analysis['all_identical']:
        log.info('    Strategy: Sprite-level hitbox (all frames identical)')
        if analysis['envelope']:
            log.info('    -> %s', format_bounding_box(analysis['envelope']))
        return False

    if len(analysis['valid_bounding_boxes']) <= 1:
        log.info('    Strategy: Sprite-level hitbox (single frame)')
        if analysis['envelope']:
            log.info('    -> %s', format_bounding_box(analysis['envelope']))
        return False

    log.info('    Strategy: Per-frame hitboxes needed (frames differ)')
    if analysis['envelope']:
        log.info('    Envelope: %s', format_bounding_box(analysis['envelope']))
    return True


def log_audit_report(
    analyses: dict[int, list[dict[str, Any]]],
    mode: str,
) -> None:
    """Log a human-readable audit report.

    Args:
        analyses: Dict mapping priority tier to list of sprite analysis results.
        mode: Hitbox mode ('per-frame' or 'envelope').

    """
    log.info('=' * 60)
    log.info('  HITBOX AUDIT REPORT  (mode: %s)', mode)
    log.info('=' * 60)
    log.info('')

    total_files = 0
    total_frames = 0
    files_needing_per_frame = 0

    for tier in sorted(analyses.keys()):
        tier_analyses = analyses[tier]
        label = PRIORITY_LABELS.get(tier, f'Priority {tier}')
        log.info('--- Priority %d: %s ---', tier, label)
        log.info('')

        for analysis in tier_analyses:
            total_files += 1
            total_frames += analysis['total_frames']
            if _log_sprite_analysis(analysis):
                files_needing_per_frame += 1
            log.info('')

        log.info('')

    log.info('=' * 60)
    log.info('  Summary: %d files, %d frames', total_files, total_frames)
    log.info('  Files needing per-frame hitboxes: %d', files_needing_per_frame)
    log.info('  Files with uniform hitboxes: %d', total_files - files_needing_per_frame)
    log.info('=' * 60)


def insert_hitbox_into_toml(
    original_content: str,
    analysis: dict[str, Any],
    mode: str,
) -> str:
    """Insert hitbox sections into TOML content via text insertion.

    Preserves all existing comments, formatting, and structure.

    Args:
        original_content: The original TOML file content.
        analysis: The sprite analysis result.
        mode: 'per-frame' or 'envelope'.

    Returns:
        Modified TOML content with hitbox sections inserted.

    """
    lines = original_content.split('\n')
    insertions: list[tuple[int, str]] = []

    # Always insert a sprite-level hitbox (envelope or shared box)
    _insert_sprite_hitbox(lines, analysis, insertions)

    # Per-frame hitboxes (only in per-frame mode when frames differ)
    uses_per_frame = (
        mode == 'per-frame'
        and not analysis['all_identical']
        and len(analysis['valid_bounding_boxes']) > 1
    )
    if uses_per_frame:
        _insert_per_frame_hitboxes(lines, analysis, insertions)

    # Apply insertions in reverse order (so line numbers stay valid)
    insertions.sort(key=operator.itemgetter(0), reverse=True)
    for line_number, text in insertions:
        lines.insert(line_number, text)

    return '\n'.join(lines)


def _insert_sprite_hitbox(
    lines: list[str],
    analysis: dict[str, Any],
    insertions: list[tuple[int, str]],
) -> None:
    """Insert sprite-level hitbox (envelope or shared box).

    Args:
        lines: File content as list of lines.
        analysis: Sprite analysis result.
        insertions: Accumulator for (line_number, text) tuples.

    """
    envelope = analysis['envelope']
    if envelope is not None:
        insert_line = _find_sprite_hitbox_insertion_line(lines)
        if insert_line is not None:
            hitbox_text = _format_hitbox_section(
                '[sprite.hitbox]',
                envelope,
            )
            insertions.append((insert_line, hitbox_text))


def _insert_per_frame_hitboxes(
    lines: list[str],
    analysis: dict[str, Any],
    insertions: list[tuple[int, str]],
) -> None:
    """Insert per-frame hitbox sections for frames that differ.

    Args:
        lines: File content as list of lines.
        analysis: Sprite analysis result.
        insertions: Accumulator for (line_number, text) tuples.

    """
    frame_insertion_lines = _find_frame_hitbox_insertion_lines(lines)
    for frame_index, frame in enumerate(analysis['frames']):
        if frame_index < len(frame_insertion_lines) and frame['bounding_box'] is not None:
            insert_line = frame_insertion_lines[frame_index]
            hitbox_text = _format_hitbox_section(
                '[animation.frame.hitbox]',
                frame['bounding_box'],
            )
            insertions.append((insert_line, hitbox_text))


def _find_sprite_hitbox_insertion_line(lines: list[str]) -> int | None:
    """Find the line number where [sprite.hitbox] should be inserted.

    Inserts after the last key in the [sprite] section, before [colors]
    or [[animation]].

    Args:
        lines: File content as list of lines.

    Returns:
        Line number for insertion, or None if not found.

    """
    in_sprite_section = False
    last_sprite_key_line = None

    for line_index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '[sprite]':
            in_sprite_section = True
            last_sprite_key_line = line_index + 1
            continue
        if in_sprite_section:
            # Check if we've hit another section
            if stripped.startswith('[') and stripped != '[sprite]':
                break
            if stripped and not stripped.startswith('#'):
                last_sprite_key_line = line_index + 1

    return last_sprite_key_line


def _find_frame_hitbox_insertion_lines(lines: list[str]) -> list[int]:
    """Find line numbers where [animation.frame.hitbox] should be inserted.

    Inserts after each frame's closing triple-quote of the pixels field.

    Args:
        lines: File content as list of lines.

    Returns:
        List of line numbers, one per frame.

    """
    insertion_lines: list[int] = []
    in_pixels = False

    for line_index, line in enumerate(lines):
        stripped = line.strip()
        if not in_pixels and re.match(r'^pixels\s*=\s*"""', stripped):
            # Check if it's a single-line pixels (opening and closing on same line)
            opening_and_closing_quotes = 2
            if stripped.count('"""') >= opening_and_closing_quotes:
                insertion_lines.append(line_index + 1)
            else:
                in_pixels = True
        elif in_pixels and '"""' in stripped:
            in_pixels = False
            insertion_lines.append(line_index + 1)

    return insertion_lines


def _format_hitbox_section(section_header: str, hitbox: dict[str, int]) -> str:
    """Format a hitbox section for TOML insertion.

    Args:
        section_header: TOML section header (e.g., '[sprite.hitbox]').
        hitbox: Bounding box dict with offset_x, offset_y, width, height.

    Returns:
        Formatted TOML text block.

    """
    return (
        f'\n{section_header}\n'
        f'offset_x = {hitbox["offset_x"]}\n'
        f'offset_y = {hitbox["offset_y"]}\n'
        f'width = {hitbox["width"]}\n'
        f'height = {hitbox["height"]}\n'
    )


def show_diff(filepath: Path, original: str, modified: str) -> bool:
    """Log a unified diff between original and modified content.

    Args:
        filepath: File path for display.
        original: Original file content.
        modified: Modified file content.

    Returns:
        True if there are differences.

    """
    relative_path = str(filepath.relative_to(PROJECT_ROOT))
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = list(
        difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f'a/{relative_path}',
            tofile=f'b/{relative_path}',
        )
    )

    if diff:
        log.info('%s', ''.join(diff))
        return True
    return False


def run_audit(
    discovered: dict[int, list[Path]],
) -> dict[int, list[dict[str, Any]]]:
    """Run the audit analysis on discovered files.

    Args:
        discovered: Dict mapping priority tier to file paths.

    Returns:
        Dict mapping priority tier to analysis results.

    """
    analyses: dict[int, list[dict[str, Any]]] = {}

    for tier in sorted(discovered.keys()):
        tier_analyses: list[dict[str, Any]] = []
        for filepath in discovered[tier]:
            try:
                analysis = analyze_sprite(filepath)
                tier_analyses.append(analysis)
            except (OSError, tomllib.TOMLDecodeError, KeyError, ValueError) as error:
                log.warning('Failed to analyze %s: %s', filepath, error)
        analyses[tier] = tier_analyses

    return analyses


def run_dry_run(
    analyses: dict[int, list[dict[str, Any]]],
    mode: str,
) -> None:
    """Show diffs for what --apply would change.

    Args:
        analyses: Analysis results from run_audit.
        mode: Hitbox mode.

    """
    files_with_changes = 0
    for tier in sorted(analyses.keys()):
        for analysis in analyses[tier]:
            filepath = analysis['filepath']
            original = filepath.read_text(encoding='utf-8')
            modified = insert_hitbox_into_toml(original, analysis, mode)
            if show_diff(filepath, original, modified):
                files_with_changes += 1

    log.info('%d file(s) would be modified.', files_with_changes)


def run_apply(
    analyses: dict[int, list[dict[str, Any]]],
    mode: str,
) -> None:
    """Apply hitbox data to TOML files.

    Args:
        analyses: Analysis results from run_audit.
        mode: Hitbox mode.

    """
    files_modified = 0
    for tier in sorted(analyses.keys()):
        for analysis in analyses[tier]:
            filepath = analysis['filepath']
            original = filepath.read_text(encoding='utf-8')
            modified = insert_hitbox_into_toml(original, analysis, mode)
            if original != modified:
                filepath.write_text(modified, encoding='utf-8')
                relative_path = filepath.relative_to(PROJECT_ROOT)
                log.info('  Updated: %s', relative_path)
                files_modified += 1

    log.info('%d file(s) modified.', files_modified)


def run_benchmark() -> None:
    """Benchmark all three hitbox lookup modes.

    Requires pygame initialization for Rect objects.
    Runs timeit on hitbox property access for single, per-animation,
    and per-frame modes.
    """
    import pygame

    pygame.init()

    single_ns, per_animation_ns, per_frame_ns = _calibrate_lookup_cost()

    log.info('=' * 60)
    log.info('  HITBOX LOOKUP BENCHMARK')
    log.info('=' * 60)
    log.info('')
    log.info('  get_hitbox_world_rect cost per lookup:')
    log.info('    Single (envelope):  %.1f ns', single_ns)
    log.info('    Per-animation:      %.1f ns', per_animation_ns)
    log.info('    Per-frame:          %.1f ns', per_frame_ns)
    log.info('')

    # Practical impact at 60fps
    sprites_per_frame = 10
    fps = 60
    lookups_per_second = sprites_per_frame * fps
    single_to_per_frame_overhead_ns = abs(per_frame_ns - single_ns) * lookups_per_second
    single_to_per_anim_overhead_ns = abs(per_animation_ns - single_ns) * lookups_per_second
    log.info('  Overhead at %dfps with %d sprites:', fps, sprites_per_frame)
    log.info(
        '    Single -> Per-animation: %.0f ns/sec (%.4f ms/sec)',
        single_to_per_anim_overhead_ns,
        single_to_per_anim_overhead_ns / 1e6,
    )
    log.info(
        '    Single -> Per-frame:     %.0f ns/sec (%.4f ms/sec)',
        single_to_per_frame_overhead_ns,
        single_to_per_frame_overhead_ns / 1e6,
    )
    log.info('')
    log.info('=' * 60)

    pygame.quit()


def _calibrate_lookup_cost() -> tuple[float, float, float]:
    """Measure per-lookup nanosecond cost for all three hitbox modes.

    The three modes correspond to different resolution paths in the
    AnimatedSprite.hitbox property:

    1. Single hitbox (envelope): frame has no explicit hitbox, falls
       back to _default_hitbox. Path: has_explicit_hitbox (False) ->
       _default_hitbox (not None) -> return.

    2. Per-animation hitbox: all frames in an animation share the same
       explicit hitbox value. Same lookup path as per-frame since every
       frame has has_explicit_hitbox=True. The only difference from
       per-frame is that the hitbox values are identical across frames.

    3. Per-frame hitbox: every frame has its own unique explicit hitbox.
       Path: has_explicit_hitbox (True) -> return frame.hitbox.

    Returns:
        Tuple of (single_ns, per_animation_ns, per_frame_ns).

    """
    import timeit

    import pygame

    from glitchygames.sprites.frame import SpriteFrame

    frame_surface = pygame.Surface((20, 28))
    default_hitbox = pygame.Rect(2, 0, 16, 27)

    # Mode 1: Single hitbox -- frame has NO explicit hitbox, falls to default
    frame_no_hitbox = SpriteFrame(surface=frame_surface, duration=0.5)

    # Mode 2: Per-animation -- frame HAS explicit hitbox (shared across animation)
    # Same hitbox value as the sprite-level default, but stored on the frame
    frame_shared_hitbox = SpriteFrame(
        surface=frame_surface,
        duration=0.5,
        hitbox=pygame.Rect(2, 0, 16, 27),
    )

    # Mode 3: Per-frame -- frame HAS explicit hitbox (unique per frame)
    frame_unique_hitbox = SpriteFrame(
        surface=frame_surface,
        duration=0.5,
        hitbox=pygame.Rect(3, 0, 14, 25),
    )

    world_x, world_y = 150.5, 200.3
    calibration_iterations = 500_000

    def single_hitbox_lookup() -> pygame.Rect:
        hitbox = frame_no_hitbox.hitbox if frame_no_hitbox.has_explicit_hitbox else default_hitbox
        return pygame.Rect(
            round(world_x) + hitbox.x,
            round(world_y) + hitbox.y,
            hitbox.width,
            hitbox.height,
        )

    def per_animation_hitbox_lookup() -> pygame.Rect:
        hitbox = (
            frame_shared_hitbox.hitbox
            if frame_shared_hitbox.has_explicit_hitbox
            else default_hitbox
        )
        return pygame.Rect(
            round(world_x) + hitbox.x,
            round(world_y) + hitbox.y,
            hitbox.width,
            hitbox.height,
        )

    def per_frame_hitbox_lookup() -> pygame.Rect:
        hitbox = (
            frame_unique_hitbox.hitbox
            if frame_unique_hitbox.has_explicit_hitbox
            else default_hitbox
        )
        return pygame.Rect(
            round(world_x) + hitbox.x,
            round(world_y) + hitbox.y,
            hitbox.width,
            hitbox.height,
        )

    single_total = timeit.timeit(single_hitbox_lookup, number=calibration_iterations)
    per_anim_total = timeit.timeit(per_animation_hitbox_lookup, number=calibration_iterations)
    per_frame_total = timeit.timeit(per_frame_hitbox_lookup, number=calibration_iterations)

    single_ns = (single_total / calibration_iterations) * 1e9
    per_anim_ns = (per_anim_total / calibration_iterations) * 1e9
    per_frame_ns = (per_frame_total / calibration_iterations) * 1e9

    return single_ns, per_anim_ns, per_frame_ns


def _log_fps_table(
    target_fps_values: list[int],
    single_ns: float,
    per_animation_ns: float,
    per_frame_ns: float,
    budget_percent: int = 100,
) -> None:
    """Log a table of sprite counts that fill a frame budget at given FPS targets.

    Args:
        target_fps_values: FPS targets to compute for (e.g. [30, 25, 20]).
        single_ns: Nanoseconds per single-hitbox (envelope) lookup.
        per_animation_ns: Nanoseconds per per-animation hitbox lookup.
        per_frame_ns: Nanoseconds per per-frame hitbox lookup.
        budget_percent: What percentage of the frame budget to allocate
            to hitbox lookups (100 = entire frame, 5 = realistic slice).

    """
    nanoseconds_per_second = 1e9
    full_budget = 100
    budget_fraction = budget_percent / full_budget

    budget_label = 'Frame Budget' if budget_percent == full_budget else 'Hitbox Budget'
    log.info(
        '  %5s  %13s  %10s  %13s  %10s',
        'FPS',
        budget_label,
        'Single',
        'Per-Animation',
        'Per-Frame',
    )
    log.info(
        '  %5s  %13s  %10s  %13s  %10s',
        '---',
        '---',
        '---',
        '---',
        '---',
    )

    for target_fps in target_fps_values:
        frame_budget_ns = (nanoseconds_per_second / target_fps) * budget_fraction

        single_max = int(frame_budget_ns / single_ns)
        per_anim_max = int(frame_budget_ns / per_animation_ns)
        per_frame_max = int(frame_budget_ns / per_frame_ns)

        log.info(
            '  %3dfps  %10.2f ms  %10s  %13s  %10s',
            target_fps,
            frame_budget_ns / 1e6,
            f'{single_max:,}',
            f'{per_anim_max:,}',
            f'{per_frame_max:,}',
        )


def run_stress_benchmark() -> None:
    """Find the sprite count at which hitbox lookups consume an entire frame budget.

    Ramps up the number of sprites doing hitbox lookups per frame until
    the lookup time alone would consume the full frame budget at 20fps,
    25fps, and 30fps. Compares envelope vs per-frame modes.
    """
    import pygame

    pygame.init()

    single_ns, per_animation_ns, per_frame_ns = _calibrate_lookup_cost()
    target_fps_values = [30, 25, 20]

    log.info('=' * 70)
    log.info('  HITBOX STRESS TEST')
    log.info('  Finding sprite counts that consume the full frame budget')
    log.info('=' * 70)
    log.info('')
    log.info('  Calibrated lookup cost (get_hitbox_world_rect):')
    log.info('    Single (envelope):  %.1f ns/lookup', single_ns)
    log.info('    Per-animation:      %.1f ns/lookup', per_animation_ns)
    log.info('    Per-frame:          %.1f ns/lookup', per_frame_ns)
    log.info('')
    log.info('  Single:        one [sprite.hitbox] for all frames')
    log.info('  Per-animation: one hitbox shared per animation namespace')
    log.info('  Per-frame:     unique [animation.frame.hitbox] per frame')
    log.info('')

    # Full budget: hitbox lookups are the ONLY thing running
    _log_fps_table(
        target_fps_values,
        single_ns,
        per_animation_ns,
        per_frame_ns,
        budget_percent=100,
    )

    log.info('')
    log.info('  Note: These are theoretical maximums assuming hitbox lookups')
    log.info('  are the ONLY work done per frame. Real games spend most of')
    log.info('  the frame budget on rendering, physics, and event processing.')
    log.info('')

    # Realistic: hitbox lookups get 5% of the frame budget
    hitbox_budget_percent = 5
    log.info('  Realistic (%d%% of frame budget for hitbox lookups):', hitbox_budget_percent)
    log.info('')
    _log_fps_table(
        target_fps_values,
        single_ns,
        per_animation_ns,
        per_frame_ns,
        budget_percent=hitbox_budget_percent,
    )

    log.info('')
    log.info('=' * 70)

    pygame.quit()


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(format='%(message)s', level=logging.INFO)

    parser = argparse.ArgumentParser(
        description='Audit TOML sprite files and compute hitbox bounding boxes.',
    )
    parser.add_argument(
        '--mode',
        choices=['per-frame', 'envelope'],
        default='per-frame',
        help=(
            'Hitbox strategy: per-frame (tight per frame) '
            'or envelope (union of all frames). Default: per-frame.'
        ),
    )
    parser.add_argument(
        '--priority',
        type=int,
        choices=[1, 2, 3],
        help='Only process files in this priority tier.',
    )
    parser.add_argument(
        '--file',
        type=Path,
        help='Audit a single TOML sprite file.',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show diffs without modifying files.',
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Write hitbox data into TOML files.',
    )
    parser.add_argument(
        '--benchmark',
        action='store_true',
        help='Benchmark per-frame vs envelope hitbox lookup performance.',
    )
    parser.add_argument(
        '--stress',
        action='store_true',
        help='Find sprite counts that saturate the frame budget at 20/25/30fps.',
    )

    args = parser.parse_args()

    if args.benchmark:
        run_benchmark()
        return

    if args.stress:
        run_stress_benchmark()
        return

    # Discover files
    if args.file:
        filepath = args.file.resolve()
        if not filepath.exists():
            log.error('File not found: %s', filepath)
            sys.exit(1)
        discovered = {0: [filepath]}
    else:
        discovered = discover_toml_files(priority=args.priority)

    if not discovered:
        log.info('No TOML sprite files found.')
        sys.exit(0)

    total_files = sum(len(file_list) for file_list in discovered.values())
    log.info('Discovered %d TOML sprite file(s).\n', total_files)

    # Run analysis
    analyses = run_audit(discovered)

    if args.dry_run:
        run_dry_run(analyses, mode=args.mode)
    elif args.apply:
        run_apply(analyses, mode=args.mode)
    else:
        # Default: audit report
        log_audit_report(analyses, mode=args.mode)


if __name__ == '__main__':
    main()
