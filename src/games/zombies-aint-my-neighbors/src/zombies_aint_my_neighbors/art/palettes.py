"""Each kid's look: a 15-colour palette over the rig's characters, plus head and clothes styles.

Every kid uses the same palette characters (the rig draws with them), so the kids differ only in
colour and in their head and clothes details, never in pose (the BOM's shared rig, section 3).
Fifteen colours besides magenta, the SNES sprite budget (BOM decision 10), as shading ramps lit
from the top left: skin 3 tones, clothes 4 (the middle one is the player's colour), trousers 3,
plus hair, shoes, white, the headset's grey and the cast's shared outline.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict

type Colour = tuple[int, int, int]

# The rig's palette characters, the same for every kid
TRANSPARENT: Final = '.'
OUTLINE: Final = 'O'
SKIN_LIGHT: Final = 'a'
SKIN: Final = 'b'
SKIN_SHADE: Final = 'c'
HAIR: Final = 'h'
CLOTHES_LIGHT: Final = 'g'
CLOTHES: Final = 'G'
CLOTHES_SHADE: Final = 'd'
CLOTHES_DARK: Final = 'D'
PANTS_LIGHT: Final = 'j'
PANTS: Final = 'J'
PANTS_SHADE: Final = 'k'
SHOES: Final = 'r'
WHITE: Final = 'w'
HEADSET: Final = 'm'

# Shading ramps, lit to dark
SKIN_RAMP: Final = SKIN_LIGHT + SKIN + SKIN_SHADE
CLOTHES_RAMP: Final = CLOTHES_LIGHT + CLOTHES + CLOTHES_SHADE + CLOTHES_DARK
PANTS_RAMP: Final = PANTS_LIGHT + PANTS + PANTS_SHADE

# The transparency key and the colours every kid shares (BOM section 1)
MAGENTA: Final[Colour] = (255, 0, 255)
SHARED_OUTLINE: Final[Colour] = (24, 16, 32)
HEADSET_GREY: Final[Colour] = (120, 124, 146)
WHITE_COLOUR: Final[Colour] = (244, 244, 236)


class HeadStyle(StrEnum):
    """What sits on a kid's head besides the VR headset."""

    BEANIE = 'beanie'
    BUNS = 'buns'
    GLASSES = 'glasses'
    HEADPHONES = 'headphones'


class ClothesStyle(StrEnum):
    """What a kid wears on top."""

    HOODIE = 'hoodie'
    OVERALLS = 'overalls'
    VEST = 'vest'
    WINDBREAKER = 'windbreaker'


class KidLook(BaseModel):
    """One kid: a name, a palette over the rig's characters, and head and clothes styles."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    name: str
    palette: dict[str, Colour]
    head: HeadStyle
    clothes: ClothesStyle


def kid_palette(
    *,
    skin: tuple[Colour, Colour, Colour],
    hair: Colour,
    clothes: tuple[Colour, Colour, Colour, Colour],
    pants: tuple[Colour, Colour, Colour],
    shoes: Colour,
) -> dict[str, Colour]:
    """Return a full kid palette: the kid's ramps plus the cast's shared colours.

    Args:
        skin: Lit, middle and shaded skin.
        hair: The hair.
        clothes: Lit, middle (the player's colour), shaded and dark clothes.
        pants: Lit, middle and shaded trousers.
        shoes: The shoes.

    Returns:
        Palette character -> colour.

    """
    return {
        TRANSPARENT: MAGENTA,
        OUTLINE: SHARED_OUTLINE,
        **dict(zip(SKIN_RAMP, skin, strict=True)),
        HAIR: hair,
        **dict(zip(CLOTHES_RAMP, clothes, strict=True)),
        **dict(zip(PANTS_RAMP, pants, strict=True)),
        SHOES: shoes,
        WHITE: WHITE_COLOUR,
        HEADSET: HEADSET_GREY,
    }


# P1, ghoul green: green hoodie, knit beanie with a pom-pom, red sneakers
DEX: Final = KidLook(
    name='dex',
    palette=kid_palette(
        skin=((252, 212, 172), (228, 172, 128), (178, 118, 86)),
        hair=(92, 58, 36),
        clothes=((164, 252, 150), (92, 230, 92), (44, 158, 70), (24, 100, 52)),
        pants=((112, 140, 210), (64, 84, 150), (38, 50, 98)),
        shoes=(226, 62, 62),
    ),
    head=HeadStyle.BEANIE,
    clothes=ClothesStyle.HOODIE,
)

# P2, pumpkin orange: denim overalls over an orange shirt, two puff buns, pale high-tops
MARISOL: Final = KidLook(
    name='marisol',
    palette=kid_palette(
        skin=((196, 138, 98), (152, 102, 70), (108, 70, 46)),
        hair=(36, 24, 22),
        clothes=((255, 196, 120), (255, 140, 26), (196, 92, 14), (128, 56, 10)),
        pants=((110, 140, 210), (72, 102, 172), (42, 64, 120)),
        shoes=(214, 214, 206),
    ),
    head=HeadStyle.BUNS,
    clothes=ClothesStyle.OVERALLS,
)

# P3, seance violet: violet sweater vest, round glasses under the headset, brown loafers
THEO: Final = KidLook(
    name='theo',
    palette=kid_palette(
        skin=((252, 222, 196), (240, 202, 172), (200, 154, 124)),
        hair=(196, 120, 46),
        clothes=((214, 170, 255), (176, 97, 255), (120, 56, 196), (76, 32, 128)),
        pants=((200, 180, 138), (172, 150, 110), (122, 102, 72)),
        shoes=(100, 56, 32),
    ),
    head=HeadStyle.GLASSES,
    clothes=ClothesStyle.VEST,
)

# P4, TV-glow cyan: cyan windbreaker, headphones around her neck, yellow rain boots
JUNE: Final = KidLook(
    name='june',
    palette=kid_palette(
        skin=((232, 182, 140), (202, 150, 110), (150, 102, 70)),
        hair=(26, 26, 40),
        clothes=((160, 240, 255), (51, 214, 255), (18, 140, 196), (10, 84, 128)),
        pants=((88, 88, 104), (52, 52, 64), (30, 30, 40)),
        shoes=(244, 206, 46),
    ),
    head=HeadStyle.HEADPHONES,
    clothes=ClothesStyle.WINDBREAKER,
)

# In player order: P1 to P4
KIDS: Final = (DEX, MARISOL, THEO, JUNE)
