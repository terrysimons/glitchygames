#!/usr/bin/env python3
"""Pixel data handling."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pygame

LOG = logging.getLogger("game.pixels")
LOG.addHandler(logging.NullHandler())


def indexed_rgb_triplet_generator(pixel_data: iter) -> iter[tuple[int, int, int]]:
    """Yield (R, G, B) pixel tuples from a buffer of pixel tuples."""
    try:
        for datum in pixel_data:
            yield datum[0]
    except StopIteration:
        pass


def rgb_555_triplet_generator(pixel_data: iter) -> iter[tuple[int, int, int]]:
    """Yield (R, G, B) pixel tuples for 555 formated color data."""
    try:
        # Construct RGB triplets.
        for packed_rgb_triplet in pixel_data:
            # struct unpacks as a 1 element tuple.
            rgb_data = bin(packed_rgb_triplet[0])

            # binary conversions start with 0b, so chop that off.
            rgb_data = rgb_data[2:]

            # Pad the data out.
            pad_bits = 16 - len(rgb_data)
            pad_data = "0" * pad_bits

            rgb_data = pad_data + rgb_data

            LOG.info(f"Padded {pad_bits} bits (now {rgb_data})")

            # red is 5 bits
            red = int(rgb_data[0:5] + "000", 2)

            if red:
                red += 7

            # green is 6 bits
            green = int(rgb_data[5:10] + "000", 2)

            if green:
                green += 7

            # blue is 5 bits
            blue = int(rgb_data[10:15] + "000", 2)

            # last bit is ignored or used for alpha.

            if blue:
                blue += 7

            LOG.info(f"Packed RGB: {rgb_data}")
            LOG.info(f"Red: {red}")
            LOG.info(f"Green: {green}")
            LOG.info(f"Blue: {blue}")

            yield (red, green, blue)
    except StopIteration:
        pass


def rgb_565_triplet_generator(pixel_data: iter) -> iter[tuple[int, int, int]]:
    """Yield (R, G, B) tuples for 565 formatted color data."""
    try:
        # Construct RGB triplets.
        for packed_rgb_triplet in pixel_data:
            # struct unpacks as a 1 element tuple.
            rgb_data = bin(packed_rgb_triplet[0])

            # binary conversions start with 0b, so chop that off.
            rgb_data = rgb_data[2:]

            # Pad the data out.
            pad_bits = 16 - len(rgb_data)
            pad_data = "0" * pad_bits

            rgb_data = pad_data + rgb_data

            LOG.info(f"Padded {pad_bits} bits (now {rgb_data})")

            # red is 5 bits
            red = int(rgb_data[0:5] + "000", 2)

            if red:
                red += 7

            # green is 6 bits
            green = int(rgb_data[5:11] + "00", 2)

            if green:
                green += 3

            # blue is 5 bits
            blue = int(rgb_data[11:] + "000", 2)

            if blue:
                blue += 7

            LOG.info(f"Packed RGB: {rgb_data}")
            LOG.info(f"Red: {red}")
            LOG.info(f"Green: {green}")
            LOG.info(f"Blue: {blue}")

            yield (red, green, blue)
    except StopIteration:
        pass


def rgb_triplet_generator(pixel_data: bytes) -> Iterator[tuple[int, int, int]]:
    """Generate RGB triplets from pixel data.

    Args:
        pixel_data: Raw pixel data as bytes

    Yields:
        Tuples of (r,g,b) values

    """
    # Validate input
    if not pixel_data:
        raise ValueError("Empty pixel data")

    if len(pixel_data) % 3 != 0:
        raise ValueError(f"Pixel data length ({len(pixel_data)}) is not divisible by 3")

    # Convert bytes to integers
    pixels = [int(b) for b in pixel_data]

    # Yield RGB triplets
    for i in range(0, len(pixels), 3):
        try:
            r = pixels[i]
            g = pixels[i + 1]
            b = pixels[i + 2]
            yield (r, g, b)
        except IndexError as e:
            raise ValueError(f"Not enough data for RGB triplet at index {i}") from e


def image_from_pixels(pixels: list, width: int, height: int) -> pygame.Surface:
    """Produce a pygame.image object for the specified [(R, G, B), ...] pixel data."""
    image = pygame.Surface((width, height))
    y = 0
    x = 0
    for pixel in pixels:
        image.fill(pixel, ((x, y), (1, 1)))

        if (x + 1) % width == 0:
            x = 0
            y += 1
        else:
            x += 1

    return image


def pixels_from_data(pixel_data: list) -> list:
    """Expand raw pixel data into [(R, G, B), ...] triplets."""
    pixels = rgb_triplet_generator(
        pixel_data=pixel_data,
    )

    # We are converting the data from a generator to
    # a list of data so that it can be referenced
    # multiple times.
    return list(pixels)


def pixels_from_path(path: str) -> list:
    """Expand raw pixel data from file into [(R, G, B), ...] triplets."""
    with Path.open(path, "rb") as fh:
        pixel_data = fh.read()

    return pixels_from_data(pixel_data=pixel_data)
