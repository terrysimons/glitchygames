"""Brave Adventurer's shared primitives: the terrain sprites and the parallax backgrounds."""

import hashlib
from pathlib import Path

import pygame
import pytest

import brave_adventurer_core as brave_adventurer_core_package
from brave_adventurer_core.constants import (
    GROUND_Y,
)
from brave_adventurer_core.drawing import (
    draw_dunes_and_oasis,
    draw_near_ground_details,
    draw_pyramids,
    draw_sky,
)
from brave_adventurer_core.terrain import GroundSegment, StoneWall
from glitchygames.world import CoordinateSpace

BRAVE_ADVENTURER_CORE_PACKAGE = Path(brave_adventurer_core_package.__file__).parent
CORE_WORLD_SPRITE_CLASSES = (GroundSegment, StoneWall)
SCREEN_SIZE = (800, 480)


class TestEngineWorldSpace:
    """The shared terrain sprites are world sprites; the engine places them."""

    @pytest.mark.parametrize(
        'sprite_class', CORE_WORLD_SPRITE_CLASSES, ids=lambda cls: cls.__name__
    )
    def test_world_sprite_classes_declare_world_space(self, sprite_class):
        assert sprite_class.COORDINATE_SPACE is CoordinateSpace.WORLD

    @pytest.mark.parametrize(
        'sprite_class', CORE_WORLD_SPRITE_CLASSES, ids=lambda cls: cls.__name__
    )
    def test_no_sprite_class_positions_itself_from_the_camera(self, sprite_class):
        assert not hasattr(sprite_class, 'apply_camera')

    def test_ground_segment_has_its_world_y(self):
        segment = GroundSegment(
            world_x=40.0, segment_width=100, groups=pygame.sprite.LayeredDirty()
        )
        assert segment.world_y == GROUND_Y


# Pixel digests of the parallax layers as drawn by the per-column / per-row drawing code these
# functions replaced (recorded 2026-10-22 from that code, before the cached-gradient and
# filled-run rewrite). Key: (function name, surface size, camera offset); the layer is drawn
# onto a cleared SRCALPHA surface with camera_y = camera offset / 2 (unused by these layers).
# Sizes: the game's screen, an odd size, and one shorter than the horizon and the dunes.
# Offsets are what ParallaxLayer.update_scroll passes: a snapped camera position times the
# layer's scroll factor, so fractional, negative (a shaken camera at the left bound) and large.
PARALLAX_DRAWING_GOLDEN_DIGESTS = {
    ('draw_sky', (800, 480), 0.0): '54327c311f76800e3d64d596d6558789',
    ('draw_sky', (513, 397), 0.0): '1db6d9aa7ffd1d031ced02714130a8cb',
    ('draw_sky', (300, 240), 0.0): '6483e81a0edf0e5465a7df352feeb06f',
    ('draw_pyramids', (800, 480), 0.0): 'f01ddcac601adb6f6df019738c08eb3e',
    ('draw_pyramids', (800, 480), 0.3): 'f01ddcac601adb6f6df019738c08eb3e',
    ('draw_pyramids', (800, 480), 12.3): '22093d59ffc45e1ff61a64a67b4e8b87',
    ('draw_pyramids', (800, 480), 700.7): 'c696cd257491f13dc93896c1201bd087',
    ('draw_pyramids', (800, 480), 2399.9): 'f01ddcac601adb6f6df019738c08eb3e',
    ('draw_pyramids', (800, 480), 3001.5): '977c85de6310bba303411cdada9f8ee7',
    ('draw_pyramids', (800, 480), 100000.3): 'ad12fbfea75a7ce6613ed134f651600f',
    ('draw_pyramids', (800, 480), -0.7): 'e082d29596c5c1efaa93295397a933ab',
    ('draw_pyramids', (800, 480), -250.0): 'b28fcb98dc50c224aa3084f764ba339f',
    ('draw_pyramids', (513, 397), 0.0): '95e48bb56432931707c5483b2123d9c6',
    ('draw_pyramids', (513, 397), 0.3): '95e48bb56432931707c5483b2123d9c6',
    ('draw_pyramids', (513, 397), 12.3): 'd4deaeb8276d905cdcfda4922d16b64d',
    ('draw_pyramids', (513, 397), 700.7): 'd0280ca820ec14ca7038f64a26f62c6c',
    ('draw_pyramids', (513, 397), 2399.9): '95e48bb56432931707c5483b2123d9c6',
    ('draw_pyramids', (513, 397), 3001.5): '65db89d687314e31ded4fc35e3124465',
    ('draw_pyramids', (513, 397), 100000.3): '50da6f41b04b448e09a742ed1ebf2231',
    ('draw_pyramids', (513, 397), -0.7): 'f8a0f3978c2b9dab42972b27ff883e84',
    ('draw_pyramids', (513, 397), -250.0): '13cfc490cfb9f97a89a73d9c1ca417bb',
    ('draw_pyramids', (300, 240), 0.0): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), 0.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), 12.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), 700.7): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), 2399.9): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), 3001.5): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), 100000.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), -0.7): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), -250.0): '0c88d932bf1a2aa2833e27e1a7d33e1e',
    ('draw_dunes_and_oasis', (800, 480), 0.0): 'ba2d90f47217e92dffdb74963ca19d21',
    ('draw_dunes_and_oasis', (800, 480), 0.3): '9cbc314220d61efeb75820ad9fb654d0',
    ('draw_dunes_and_oasis', (800, 480), 12.3): '536afc3aa0f11a126d5ba9f40254ce3f',
    ('draw_dunes_and_oasis', (800, 480), 700.7): '2cce7ebe65bee81d957e372859cbdd9e',
    ('draw_dunes_and_oasis', (800, 480), 2399.9): 'ba7cca61a028ec3b19117107a323f067',
    ('draw_dunes_and_oasis', (800, 480), 3001.5): '7f81ff8548aadd0b0f717d2cdd1c926d',
    ('draw_dunes_and_oasis', (800, 480), 100000.3): 'd5c4ffe894119641306e3d7e8e53e3dc',
    ('draw_dunes_and_oasis', (800, 480), -0.7): 'ced9122d3378c5aa51a1216d55164c9a',
    ('draw_dunes_and_oasis', (800, 480), -250.0): 'f5f54af860bdead369693e113fc40ec0',
    ('draw_dunes_and_oasis', (513, 397), 0.0): '9bba35f5dd2835f263358c7c4d1bf601',
    ('draw_dunes_and_oasis', (513, 397), 0.3): '02ef565d313a0a8eab6ee59529c604b0',
    ('draw_dunes_and_oasis', (513, 397), 12.3): '6708d317b09c5f79f5cf424b6c143941',
    ('draw_dunes_and_oasis', (513, 397), 700.7): 'e72c82105b12b52f44b76300025ab343',
    ('draw_dunes_and_oasis', (513, 397), 2399.9): '15a55a6cb9d189979fcf17c8387565c1',
    ('draw_dunes_and_oasis', (513, 397), 3001.5): '5a2026dedcfa2ff28cb44409c68c8a87',
    ('draw_dunes_and_oasis', (513, 397), 100000.3): '05f3a94682d72fc12f56ba4dc61e71e2',
    ('draw_dunes_and_oasis', (513, 397), -0.7): '831aee8fc61b64070c911dda138bfe89',
    ('draw_dunes_and_oasis', (513, 397), -250.0): 'c6bb577e97846a6663c472ecbbc90e9c',
    ('draw_dunes_and_oasis', (300, 240), 0.0): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), 0.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), 12.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), 700.7): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), 2399.9): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), 3001.5): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), 100000.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), -0.7): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), -250.0): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (800, 480), 0.0): '826d1ca7bddc505ce313524e982d1867',
    ('draw_near_ground_details', (800, 480), 0.3): '826d1ca7bddc505ce313524e982d1867',
    ('draw_near_ground_details', (800, 480), 12.3): 'fe2ff33a2f432eca1474d0d5057a3d73',
    ('draw_near_ground_details', (800, 480), 700.7): '5909be69351a440e95845c7e517f3b24',
    ('draw_near_ground_details', (800, 480), 2399.9): 'aab3e9cc76b85e71829a31db19c06eec',
    ('draw_near_ground_details', (800, 480), 3001.5): '79ce5c6f1c25040cd665380befedb183',
    ('draw_near_ground_details', (800, 480), 100000.3): 'e10413fe998e9d68f18f41751859bc39',
    ('draw_near_ground_details', (800, 480), -0.7): 'af67ccad971663558a090fb7efa6c5bc',
    ('draw_near_ground_details', (800, 480), -250.0): '99b3a0bee2b2f9301b2407696f542115',
    ('draw_near_ground_details', (513, 397), 0.0): 'd89f1938327c889140760efe1b4ad3d3',
    ('draw_near_ground_details', (513, 397), 0.3): 'd89f1938327c889140760efe1b4ad3d3',
    ('draw_near_ground_details', (513, 397), 12.3): '2b3e4e4975e65fa05cb16e26fc3187aa',
    ('draw_near_ground_details', (513, 397), 700.7): '1d99fce2cf61d26ebed40f48d9003797',
    ('draw_near_ground_details', (513, 397), 2399.9): '160b66e2dd48675d395150879a9f3443',
    ('draw_near_ground_details', (513, 397), 3001.5): '6e06f8a8e831e50d0e4af1c2db872cae',
    ('draw_near_ground_details', (513, 397), 100000.3): '4541d2196ecb48dad1f2abb5d6be596d',
    ('draw_near_ground_details', (513, 397), -0.7): '74a7d2c6792fa1ac2994c06d601f1cb1',
    ('draw_near_ground_details', (513, 397), -250.0): '15a10c74496602b5b971c5ea480c8a25',
    ('draw_near_ground_details', (300, 240), 0.0): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), 0.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), 12.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), 700.7): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), 2399.9): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), 3001.5): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), 100000.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), -0.7): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), -250.0): 'f656f8a7837fb9588293572f43d0bfc5',
}
PARALLAX_DRAW_FUNCTIONS = {
    'draw_sky': draw_sky,
    'draw_pyramids': draw_pyramids,
    'draw_dunes_and_oasis': draw_dunes_and_oasis,
    'draw_near_ground_details': draw_near_ground_details,
}


def parallax_layer_digest(
    *, function_name: str, surface_size: tuple[int, int], camera_offset: float
) -> str:
    """Draw one parallax layer onto a cleared SRCALPHA surface and digest its RGBA pixels.

    Returns:
        The hex digest of the drawn pixels (independent of the surface's pixel format).

    """
    surface = pygame.Surface(surface_size, pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))
    PARALLAX_DRAW_FUNCTIONS[function_name](surface, camera_offset, camera_offset * 0.5)
    return hashlib.blake2b(pygame.image.tobytes(surface, 'RGBA'), digest_size=16).hexdigest()


class TestParallaxDrawingGoldens:
    """The parallax layers draw exactly the pixels the per-column drawing code drew."""

    @pytest.mark.parametrize(
        ('function_name', 'surface_size', 'camera_offset'),
        list(PARALLAX_DRAWING_GOLDEN_DIGESTS),
    )
    def test_layer_matches_golden(self, function_name, surface_size, camera_offset):
        digest = parallax_layer_digest(
            function_name=function_name, surface_size=surface_size, camera_offset=camera_offset
        )

        golden_digest = PARALLAX_DRAWING_GOLDEN_DIGESTS[function_name, surface_size, camera_offset]
        assert digest == golden_digest

    @pytest.mark.parametrize('function_name', list(PARALLAX_DRAW_FUNCTIONS))
    def test_redrawing_at_another_size_and_back_is_unchanged(self, function_name):
        """A cache keyed by surface size never hands one size's drawing to another."""
        first_digest = parallax_layer_digest(
            function_name=function_name, surface_size=SCREEN_SIZE, camera_offset=12.3
        )
        parallax_layer_digest(
            function_name=function_name, surface_size=(513, 397), camera_offset=12.3
        )

        assert (
            parallax_layer_digest(
                function_name=function_name, surface_size=SCREEN_SIZE, camera_offset=12.3
            )
            == first_digest
        )

    def test_sky_draws_its_gradient_once_per_size(self, mocker):
        """The sky gradient is built once per surface size and blitted afterwards."""
        draw_sky(pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA), 0.0, 0.0)
        draw_line_spy = mocker.spy(pygame.draw, 'line')

        draw_sky(pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA), 0.0, 0.0)

        assert draw_line_spy.call_count == 0

    def test_pyramids_draw_the_ground_gradient_once_per_size(self, mocker):
        """The horizon-to-sand gradient is built once and blitted, not drawn row by row."""
        surface = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        draw_pyramids(surface, 0.0, 0.0)
        draw_line_spy = mocker.spy(pygame.draw, 'line')

        draw_pyramids(surface, 40.0, 0.0)

        assert draw_line_spy.call_count == 0

    def test_dunes_draw_no_line_per_column(self, mocker):
        """The dune sand is filled in runs of equal height, not one line per screen column.

        At camera offset 1700 both oases are off screen, so no line is drawn at all.
        """
        surface = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        draw_line_spy = mocker.spy(pygame.draw, 'line')

        draw_dunes_and_oasis(surface, 1700.0, 0.0)

        assert draw_line_spy.call_count == 0
