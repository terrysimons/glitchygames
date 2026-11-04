"""Sung voices: soprano to basso profundo on five vowels, humming, choirs and whistling.

A sung vowel is the voice's harmonics heard through the vocal tract's resonances (formants).
The formant frequencies, bandwidths and gains for soprano, alto, countertenor, tenor and bass on
a, e, i, o and u are the Csound manual's "Formant Values" table (Csound Reference Manual,
Appendix, https://csound.com/docs/manual/MiscFormants.html). Mezzo-soprano uses the alto's,
baritone the tenor's and bass's averaged, basso profundo the bass's, treble (a boy soprano) the
soprano's. The harmonic levels are computed at the middle of each voice's range; the
instrument's harmonics keep those levels at every pitch, so the vowel is truest mid-range (no
formant filter moves with the note here). Choirs are three detuned voices; ranges are the usual
choral ranges.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import Formant, blown, formant_series
from glitchygames.audio.pitch import Note

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.audio.instrument import Instrument

# (frequency Hz, gain dB, bandwidth Hz) for formants 1-5, after the Csound manual's table
FormantRow = tuple[tuple[float, float, float], ...]
FORMANT_TABLE: Final[dict[str, dict[str, FormantRow]]] = {
    'soprano': {
        'a': ((800, 0, 80), (1150, -6, 90), (2900, -32, 120), (3900, -20, 130), (4950, -50, 140)),
        'e': ((350, 0, 60), (2000, -20, 100), (2800, -15, 120), (3600, -40, 150), (4950, -56, 200)),
        'i': ((270, 0, 60), (2140, -12, 90), (2950, -26, 100), (3900, -26, 120), (4950, -44, 120)),
        'o': ((450, 0, 40), (800, -11, 80), (2830, -22, 100), (3800, -22, 120), (4950, -50, 120)),
        'u': ((325, 0, 50), (700, -16, 60), (2700, -35, 170), (3800, -40, 180), (4950, -60, 200)),
    },
    'alto': {
        'a': ((800, 0, 80), (1150, -4, 90), (2800, -20, 120), (3500, -36, 130), (4950, -60, 140)),
        'e': ((400, 0, 60), (1600, -24, 80), (2700, -30, 120), (3300, -35, 150), (4950, -60, 200)),
        'i': ((350, 0, 50), (1700, -20, 100), (2700, -30, 120), (3700, -36, 150), (4950, -60, 200)),
        'o': ((450, 0, 70), (800, -9, 80), (2830, -16, 100), (3500, -28, 130), (4950, -55, 135)),
        'u': ((325, 0, 50), (700, -12, 60), (2530, -30, 170), (3500, -40, 180), (4950, -64, 200)),
    },
    'countertenor': {
        'a': ((660, 0, 80), (1120, -6, 90), (2750, -23, 120), (3000, -24, 130), (3350, -38, 140)),
        'e': ((440, 0, 70), (1800, -14, 80), (2700, -18, 100), (3000, -20, 120), (3300, -20, 120)),
        'i': ((270, 0, 40), (1850, -24, 90), (2900, -24, 100), (3350, -36, 120), (3590, -36, 120)),
        'o': ((430, 0, 40), (820, -10, 80), (2700, -26, 100), (3000, -22, 120), (3300, -34, 120)),
        'u': ((370, 0, 40), (630, -20, 60), (2750, -23, 100), (3000, -30, 120), (3400, -34, 120)),
    },
    'tenor': {
        'a': ((650, 0, 80), (1080, -6, 90), (2650, -7, 120), (2900, -8, 130), (3250, -22, 140)),
        'e': ((400, 0, 70), (1700, -14, 80), (2600, -12, 100), (3200, -14, 120), (3580, -20, 120)),
        'i': ((290, 0, 40), (1870, -15, 90), (2800, -18, 100), (3250, -20, 120), (3540, -30, 120)),
        'o': ((400, 0, 70), (800, -10, 80), (2600, -12, 100), (2800, -12, 130), (3000, -26, 135)),
        'u': ((350, 0, 40), (600, -20, 60), (2700, -17, 100), (2900, -14, 120), (3300, -26, 120)),
    },
    'bass': {
        'a': ((600, 0, 60), (1040, -7, 70), (2250, -9, 110), (2450, -9, 120), (2750, -20, 130)),
        'e': ((400, 0, 40), (1620, -12, 80), (2400, -9, 100), (2800, -12, 120), (3100, -18, 120)),
        'i': ((250, 0, 60), (1750, -30, 90), (2600, -16, 100), (3050, -22, 120), (3340, -28, 120)),
        'o': ((400, 0, 40), (750, -11, 80), (2400, -21, 100), (2600, -20, 120), (2900, -40, 120)),
        'u': ((350, 0, 40), (600, -20, 80), (2400, -32, 100), (2675, -28, 120), (2950, -36, 120)),
    },
}
VOWELS: Final[dict[str, str]] = {'a': 'ah', 'e': 'eh', 'i': 'ee', 'o': 'oh', 'u': 'oo'}
SINGER_FORMANT: Final[dict[str, str]] = {  # which table row each voice type sings with
    'soprano': 'soprano',
    'mezzo soprano': 'alto',
    'alto': 'alto',
    'treble': 'soprano',
    'countertenor': 'countertenor',
    'tenor': 'tenor',
    'baritone': 'baritone',
    'bass': 'bass',
    'basso profundo': 'bass',
}
# (catalog voice, title, lowest, highest): the usual solo ranges
SOLO_VOICES: Final[tuple[tuple[str, str, str, str], ...]] = (
    ('soprano', 'Soprano', 'C4', 'C6'),
    ('mezzo soprano', 'Mezzo-soprano', 'A3', 'A5'),
    ('alto', 'Alto (contralto)', 'F3', 'F5'),
    ('treble', 'Treble (boy soprano)', 'A3', 'A5'),
    ('countertenor', 'Countertenor', 'E3', 'E5'),
    ('tenor', 'Tenor', 'C3', 'C5'),
    ('baritone', 'Baritone', 'A2', 'A4'),
    ('bass', 'Bass', 'E2', 'E4'),
    ('basso profundo', 'Basso profundo', 'C2', 'C4'),
)
# (choir part, title, lowest, highest)
CHOIR_PARTS: Final[tuple[tuple[str, str, str, str], ...]] = (
    ('soprano', 'Choir sopranos', 'C4', 'A5'),
    ('alto', 'Choir altos', 'G3', 'D5'),
    ('tenor', 'Choir tenors', 'C3', 'A4'),
    ('bass', 'Choir basses', 'E2', 'D4'),
)
HUM_FORMANTS: Final[tuple[Formant, ...]] = (  # a closed-mouth nasal murmur
    Formant(hertz=250.0, bandwidth=100.0, decibels=0.0),
    Formant(hertz=2500.0, bandwidth=300.0, decibels=-30.0),
)


def _formants(voice: str, vowel: str) -> tuple[Formant, ...]:
    """The formants a voice type sings a vowel with (baritone: tenor and bass averaged).

    Args:
        voice: A key of ``SINGER_FORMANT``.
        vowel: One of a, e, i, o, u.

    Returns:
        The formants.
    """
    row_name = SINGER_FORMANT[voice]
    if row_name == 'baritone':
        tenor, bass = FORMANT_TABLE['tenor'][vowel], FORMANT_TABLE['bass'][vowel]
        rows: Sequence[tuple[float, float, float]] = tuple(
            (
                (high[0] + low[0]) / 2.0,
                (high[1] + low[1]) / 2.0,
                (high[2] + low[2]) / 2.0,
            )
            for high, low in zip(tenor, bass, strict=True)
        )
    else:
        rows = FORMANT_TABLE[row_name][vowel]
    return tuple(
        Formant(hertz=hertz, bandwidth=bandwidth, decibels=decibels)
        for hertz, decibels, bandwidth in rows
    )


def _middle_hz(lowest: str, highest: str) -> float:
    middle = (Note(lowest).midi_number + Note(highest).midi_number) / 2.0
    return 440.0 * 2.0 ** ((middle - 69.0) / 12.0)


def _sung(formants: Sequence[Formant], *, middle_hz: float, choir: bool) -> Instrument:
    return blown(
        formant_series(fundamental_hz=middle_hz, formants=formants),
        attack=0.15 if choir else 0.08,
        release=0.25 if choir else 0.15,
        breath=0.012 if choir else 0.008,
        breath_low_pass=5000.0,
        chorus_cents=11.0 if choir else 3.0,
    )


def _solo_entries() -> tuple[CatalogEntry, ...]:
    entries: list[CatalogEntry] = []
    for voice, title, lowest, highest in SOLO_VOICES:
        middle_hz = _middle_hz(lowest, highest)
        for vowel, sound in VOWELS.items():
            entries.append(
                CatalogEntry(
                    f'{voice} {sound}',
                    f'{title} ({sound})',
                    Family.VOICES,
                    lowest,
                    highest,
                    partial(_sung, _formants(voice, vowel), middle_hz=middle_hz, choir=False),
                )
            )
        entries.append(
            CatalogEntry(
                f'{voice} hum',
                f'{title} (humming)',
                Family.VOICES,
                lowest,
                highest,
                partial(_sung, HUM_FORMANTS, middle_hz=middle_hz, choir=False),
            )
        )
    return tuple(entries)


def _choir_entries() -> tuple[CatalogEntry, ...]:
    entries: list[CatalogEntry] = []
    for part, title, lowest, highest in CHOIR_PARTS:
        middle_hz = _middle_hz(lowest, highest)
        for vowel in ('a', 'o', 'u'):
            sound = VOWELS[vowel]
            entries.append(
                CatalogEntry(
                    f'choir {part} {sound}',
                    f'{title} ({sound})',
                    Family.CHOIRS,
                    lowest,
                    highest,
                    partial(_sung, _formants(part, vowel), middle_hz=middle_hz, choir=True),
                )
            )
    entries.append(
        CatalogEntry(
            'childrens choir',
            "Children's choir (ah)",
            Family.CHOIRS,
            'C4',
            'G5',
            partial(_sung, _formants('treble', 'a'), middle_hz=_middle_hz('C4', 'G5'), choir=True),
        )
    )
    return tuple(entries)


def _whistling() -> Instrument:
    return blown((1.0, 0.03), attack=0.04, release=0.08, breath=0.05, breath_low_pass=6000.0)


VOICES: Final[tuple[CatalogEntry, ...]] = (
    *_solo_entries(),
    CatalogEntry('whistling', 'Whistling', Family.VOICES, 'C5', 'C7', _whistling),
)
CHOIRS: Final[tuple[CatalogEntry, ...]] = _choir_entries()
