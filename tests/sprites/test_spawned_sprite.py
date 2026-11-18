"""SpawnedSprite: a world-space sprite built from a sprite file's text, centered on a point.

The console's ``/sprite`` adds one (plans/2026-11-17-sprite-command.md, Task 1).
"""

import pygame
import pytest

from glitchygames import world
from glitchygames.display_mode import set_display_mode
from glitchygames.sprites import SpriteFactory
from glitchygames.sprites.spawned import SpawnedSprite

# Four pixels wide, two high
WIDE_STATIC_TEXT = """\
[sprite]
name = "bar"
pixels = \"\"\"
####
####
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 255
"""

# Two frames on different holds
ANIMATED_TEXT = """\
[sprite]
name = "blink"

[[animation]]
namespace = "blink"
frame_interval = 0.25

[[animation.frame]]
pixels = \"\"\"
#.
\"\"\"

[[animation.frame]]
frame_interval = 1.5
pixels = \"\"\"
.#
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0

[colors."."]
red = 255
green = 255
blue = 255
"""


@pytest.fixture(autouse=True)
def display():
    """Give AnimatedSprite a real display for loading."""
    pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(96, 64))


def test_a_spawned_sprite_is_centered_on_its_point():
    """Its world position is the point less half its native size, and the engine positions it."""
    sprite = SpawnedSprite.from_text(
        text=WIDE_STATIC_TEXT, source_name='console', center_x=100.0, center_y=50.0
    )

    assert (sprite.world_x, sprite.world_y) == (98.0, 49.0)
    assert world.is_world_positioned(sprite)
    assert sprite.name == 'bar'


def test_a_spawned_sprite_animates_as_a_loaded_one():
    """Its frames and their holds are the text loader's for the same text."""
    spawned = SpawnedSprite.from_text(
        text=ANIMATED_TEXT, source_name='console', center_x=0.0, center_y=0.0
    )
    loaded = SpriteFactory.load_sprite_from_text(text=ANIMATED_TEXT, source_name='console')

    def holds(sprite):
        return {
            name: [frame.duration for frame in frames] for name, frames in sprite.frames.items()
        }

    assert holds(spawned) == holds(loaded) == {'blink': [0.25, 1.5]}


def test_text_that_cannot_build_a_sprite_is_refused():
    """The factory's refusal, naming where the text came from."""
    with pytest.raises(ValueError, match='console'):
        SpawnedSprite.from_text(text='[sprite\n', source_name='console', center_x=0.0, center_y=0.0)
