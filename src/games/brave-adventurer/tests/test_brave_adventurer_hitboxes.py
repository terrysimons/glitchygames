"""Brave Adventurer's sprites' hitboxes: the Cobra's follow its pose, Papyrus's scale with it.

Moved from the engine's tests (tests/collision/test_collision.py, which keep the engine's
collision rects covered with stand-in sprites): the subjects are the game's own sprites, the
Cobra (``brave_adventurer.enemies``) and Papyrus's ``SPRITE_SCALE`` hitboxes.
"""

import pygame
import pytest

from glitchygames.collision.layers import get_sprite_collision_rect
from glitchygames.display_mode import set_display_mode


class TestRedrawnGameSprites:
    """Games that redraw into the same image each update get up-to-date hitboxes."""

    @pytest.fixture(autouse=True)
    def real_display(self):
        """Brave Adventurer's sprites convert against a real display."""
        pygame.init()
        if pygame.display.get_surface() is None:
            set_display_mode(size=(800, 600))

    def test_cobra_hitbox_follows_first_draw_and_strike(self):
        """Brave Adventurer's Cobra: idle as it is made, then the strike pose dt_tick draws.

        The pose is drawn when the cobra is made and in dt_tick (before collision), never in
        update(), so its hitbox is never a blank image's or a frame behind (BUGS.md #209.6).
        """
        from brave_adventurer.enemies import Cobra

        cobra = Cobra(500.0, pygame.sprite.LayeredDirty())
        idle_rect = get_sprite_collision_rect(cobra)
        idle_visible = cobra.image.get_bounding_rect()
        assert idle_rect.size == idle_visible.size
        assert idle_visible.size != cobra.image.get_size()  # drawn, not a blank image

        cobra.dt_tick(Cobra.STRIKE_INTERVAL)

        assert cobra.striking
        striking_visible = cobra.image.get_bounding_rect()
        assert striking_visible != idle_visible
        assert get_sprite_collision_rect(cobra).size == striking_visible.size


class TestPapyrusHitboxScale:
    """Papyrus draws sprites at SPRITE_SCALE, so its TOML hitboxes must scale with them."""

    @pytest.fixture(autouse=True)
    def real_display(self):
        """Papyrus sprites load TOML art and convert against a real display."""
        pygame.init()
        if pygame.display.get_surface() is None:
            set_display_mode(size=(800, 600))

    def test_scaled_papyrus_player_collides_at_twice_the_toml_hitbox(self):
        """After its first tick the player's collision rect is the TOML hitbox times 2."""
        from brave_adventurer_papyrus.constants import SPRITE_SCALE
        from brave_adventurer_papyrus.player import PapyrusPlayer

        player = PapyrusPlayer(100.0, 200.0, pygame.sprite.LayeredDirty())
        player.dt_tick(0.0)

        assert player.scale == SPRITE_SCALE == 2
        frame = player.get_current_frame()
        assert frame is not None
        native_hitbox = frame.hitbox if frame.has_explicit_hitbox else player.default_hitbox
        assert native_hitbox is not None
        draw_offset_x, draw_offset_y = player.draw_offset  # BOTTOM frame anchoring
        assert get_sprite_collision_rect(player) == pygame.Rect(
            round(player.world_x) + native_hitbox.x * 2 + draw_offset_x,
            round(player.world_y) + native_hitbox.y * 2 + draw_offset_y,
            native_hitbox.width * 2,
            native_hitbox.height * 2,
        )

    @pytest.mark.parametrize(
        'sprite_name', ['player', 'cobra', 'scarab', 'scorpion', 'gold_scarab']
    )
    def test_freshly_constructed_sprites_have_scaled_hitboxes_before_any_tick(self, sprite_name):
        """No frame ever uses native-size hitboxes: the scale is set when the sprite is built."""
        from brave_adventurer_papyrus.constants import SPRITE_SCALE
        from brave_adventurer_papyrus.enemies import (
            PapyrusCobra,
            PapyrusScarab,
            PapyrusScorpion,
        )
        from brave_adventurer_papyrus.player import PapyrusPlayer
        from brave_adventurer_papyrus.terrain import PapyrusGoldScarab

        group = pygame.sprite.LayeredDirty()
        builders = {
            'player': lambda: PapyrusPlayer(100.0, 200.0, group),
            'cobra': lambda: PapyrusCobra(100.0, group),
            'scarab': lambda: PapyrusScarab(100.0, group),
            'scorpion': lambda: PapyrusScorpion(100.0, group),
            'gold_scarab': lambda: PapyrusGoldScarab(100.0, 200.0, group),
        }
        sprite = builders[sprite_name]()

        assert sprite.scale == SPRITE_SCALE
        frame = sprite.get_current_frame()
        assert frame is not None
        if frame.has_explicit_hitbox:
            native_hitbox = frame.hitbox
        elif sprite.default_hitbox is not None:
            native_hitbox = sprite.default_hitbox
        else:
            native_hitbox = frame.opaque_bounds()
        assert sprite.hitbox.size == (
            native_hitbox.width * SPRITE_SCALE,
            native_hitbox.height * SPRITE_SCALE,
        )

    def test_scale_one_keeps_native_hitbox(self):
        """A scale of 1 leaves hitboxes native."""
        from brave_adventurer_papyrus.player import PapyrusPlayer

        player = PapyrusPlayer(100.0, 200.0, pygame.sprite.LayeredDirty())
        player.scale = 1

        assert player.scale == 1
        frame = player.get_current_frame()
        assert frame is not None
        native_hitbox = frame.hitbox if frame.has_explicit_hitbox else player.default_hitbox
        assert native_hitbox is not None
        assert player.hitbox == native_hitbox.move(player.draw_offset)
