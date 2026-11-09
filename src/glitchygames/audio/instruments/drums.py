"""Drums and percussion: drums, rattles, scrapers, clappers, cymbals and gongs, all unpitched.

The family holds the Hornbostel-Sachs classes 1 (idiophones: rattles, scrapers, clappers,
blocks, cymbals, gongs, bells) and 2 (membranophones: struck and friction drums) whose sound has
no definite pitch (https://en.wikipedia.org/wiki/Hornbostel%E2%80%93Sachs). Tuned bars, bells,
pans and timpani are tuned percussion (``percussion.py``). Untuned percussion is fixed tones and
filtered noise: its sounds do not follow the note's pitch, so these entries have no range, and a
fixed tone ignores the pitch given. Each is built with ``drum``: a struck tone that rings out, a
noise band for the stick, hand or snares, and a tail; a ring is cut when the note ends, fading
out over the entry's ``tail``.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import Tone, drum

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument


def _tom(hertz: float) -> Instrument:
    return drum(
        tones=(Tone(hertz=hertz, glide_to=hertz * 0.82, glide_seconds=0.15, ring_seconds=0.5),),
        noise=0.15,
        noise_ring_seconds=0.05,
        noise_low_pass=4000.0,
        tail=0.5,
    )


def _hand_drum(hertz: float, *, ring_seconds: float, slap: float = 0.15) -> Instrument:
    return drum(
        tones=(
            Tone(hertz=hertz, glide_to=hertz * 0.95, glide_seconds=0.05, ring_seconds=ring_seconds),
        ),
        noise=slap,
        noise_ring_seconds=0.03,
        noise_low_pass=6000.0,
        tail=ring_seconds,
    )


def _metal(
    frequencies: tuple[float, ...],
    *,
    ring_seconds: float,
    noise: float = 0.0,
    wave: str = 'sine',
    noise_high_pass: float | None = None,
) -> Instrument:
    return drum(
        tones=tuple(
            Tone(hertz=hertz, ring_seconds=ring_seconds, level=0.6, wave=wave)
            for hertz in frequencies
        ),
        noise=noise,
        noise_ring_seconds=ring_seconds / 2.0,
        noise_high_pass=noise_high_pass,
        tail=ring_seconds,
    )


def _cymbal(
    *, ring_seconds: float, high_pass: float, drive: float = 0.0, attack: float = 0.0
) -> Instrument:
    return drum(
        noise=1.0,
        noise_ring_seconds=ring_seconds,
        noise_high_pass=high_pass,
        tail=ring_seconds,
        drive=drive,
        attack=attack,
    )


def _shaker(*, ring_seconds: float, high_pass: float, attack: float = 0.01) -> Instrument:
    return drum(
        noise=1.0,
        noise_ring_seconds=ring_seconds,
        noise_high_pass=high_pass,
        tail=ring_seconds,
        attack=attack,
    )


DRUMS_AND_PERCUSSION: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry(
        'kick drum',
        'Kick drum',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=110.0, glide_to=45.0, glide_seconds=0.07, ring_seconds=0.45),),
            noise=0.2,
            noise_ring_seconds=0.01,
            noise_low_pass=3000.0,
            tail=0.4,
        ),
    ),
    CatalogEntry(
        'electronic kick',
        'Electronic kick (808-style)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=65.0, glide_to=42.0, glide_seconds=0.12, ring_seconds=1.2),),
            tail=1.0,
        ),
    ),
    CatalogEntry(
        'orchestral bass drum',
        'Orchestral bass drum',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=55.0, glide_to=48.0, glide_seconds=0.2, ring_seconds=1.8),),
            noise=0.25,
            noise_ring_seconds=0.4,
            noise_low_pass=500.0,
            tail=1.5,
        ),
    ),
    CatalogEntry(
        'snare drum',
        'Snare drum',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=190.0, ring_seconds=0.1),),
            noise=0.9,
            noise_ring_seconds=0.2,
            noise_high_pass=1500.0,
            tail=0.25,
        ),
    ),
    CatalogEntry(
        'snare rimshot',
        'Snare rimshot',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=220.0, ring_seconds=0.08),
                Tone(hertz=1700.0, ring_seconds=0.03, level=0.6),
            ),
            noise=0.9,
            noise_ring_seconds=0.18,
            noise_high_pass=2000.0,
            tail=0.25,
            drive=1.5,
        ),
    ),
    CatalogEntry(
        'snare brush',
        'Snare (brush swish)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_shaker, ring_seconds=0.35, high_pass=2500.0, attack=0.06),
    ),
    CatalogEntry(
        'electronic snare',
        'Electronic snare',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=180.0, ring_seconds=0.12),
                Tone(hertz=330.0, ring_seconds=0.08, level=0.5),
            ),
            noise=0.7,
            noise_ring_seconds=0.18,
            noise_high_pass=3000.0,
            tail=0.25,
        ),
    ),
    CatalogEntry(
        'high tom', 'High tom', Family.DRUMS_AND_PERCUSSION, None, None, partial(_tom, 210.0)
    ),
    CatalogEntry(
        'mid tom', 'Mid tom', Family.DRUMS_AND_PERCUSSION, None, None, partial(_tom, 160.0)
    ),
    CatalogEntry(
        'low tom', 'Low tom', Family.DRUMS_AND_PERCUSSION, None, None, partial(_tom, 120.0)
    ),
    CatalogEntry(
        'floor tom', 'Floor tom', Family.DRUMS_AND_PERCUSSION, None, None, partial(_tom, 88.0)
    ),
    CatalogEntry(
        'closed hi hat',
        'Closed hi-hat',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=0.05, high_pass=7000.0),
    ),
    CatalogEntry(
        'pedal hi hat',
        'Pedal hi-hat',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=0.08, high_pass=5000.0, attack=0.004),
    ),
    CatalogEntry(
        'open hi hat',
        'Open hi-hat',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=0.6, high_pass=6500.0),
    ),
    CatalogEntry(
        'crash cymbal',
        'Crash cymbal',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=2.5, high_pass=3000.0),
    ),
    CatalogEntry(
        'ride cymbal',
        'Ride cymbal',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            _metal, (2600.0, 3720.0, 5310.0), ring_seconds=1.8, noise=0.5, noise_high_pass=5000.0
        ),
    ),
    CatalogEntry(
        'ride bell',
        'Ride cymbal bell',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            _metal, (880.0, 2390.0, 3410.0), ring_seconds=1.5, noise=0.15, noise_high_pass=6000.0
        ),
    ),
    CatalogEntry(
        'splash cymbal',
        'Splash cymbal',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=0.8, high_pass=4500.0),
    ),
    CatalogEntry(
        'china cymbal',
        'China cymbal',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=1.8, high_pass=2000.0, drive=3.0),
    ),
    CatalogEntry(
        'suspended cymbal roll',
        'Suspended cymbal (swell)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=3.0, high_pass=3000.0, attack=1.0),
    ),
    CatalogEntry(
        'crash cymbals pair',
        'Clash cymbals (pair)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=3.5, high_pass=2000.0, drive=1.0),
    ),
    CatalogEntry(
        'tam tam',
        'Tam-tam',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=72.0, ring_seconds=6.0),
                Tone(hertz=133.0, ring_seconds=5.0, level=0.5),
            ),
            noise=0.6,
            noise_ring_seconds=5.0,
            noise_low_pass=2500.0,
            tail=6.0,
            attack=0.15,
        ),
    ),
    CatalogEntry(
        'tambourine',
        'Tambourine',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_metal, (5400.0, 7300.0), ring_seconds=0.25, noise=0.8, noise_high_pass=6000.0),
    ),
    CatalogEntry(
        'triangle',
        'Triangle',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_metal, (4200.0, 7580.0, 10500.0), ring_seconds=2.5),
    ),
    CatalogEntry(
        'cowbell',
        'Cowbell',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_metal, (540.0, 800.0), ring_seconds=0.35, wave='square'),
    ),
    CatalogEntry(
        'high agogo',
        'Agogô (high)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_metal, (930.0, 2510.0), ring_seconds=0.5),
    ),
    CatalogEntry(
        'low agogo',
        'Agogô (low)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_metal, (660.0, 1780.0), ring_seconds=0.5),
    ),
    CatalogEntry(
        'finger cymbals',
        'Finger cymbals',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_metal, (3700.0, 5300.0, 8900.0), ring_seconds=2.0),
    ),
    CatalogEntry(
        'wind gong',
        'Wind gong',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=150.0, ring_seconds=3.0),),
            noise=0.8,
            noise_ring_seconds=3.0,
            noise_high_pass=1200.0,
            tail=3.0,
            attack=0.05,
        ),
    ),
    CatalogEntry(
        'claves',
        'Claves',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(drum, tones=(Tone(hertz=2500.0, ring_seconds=0.06),), tail=0.08),
    ),
    CatalogEntry(
        'woodblock',
        'Woodblock',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=1050.0, ring_seconds=0.07),
                Tone(hertz=1680.0, ring_seconds=0.04, level=0.4),
            ),
            noise=0.2,
            noise_ring_seconds=0.01,
            noise_high_pass=2000.0,
            tail=0.1,
        ),
    ),
    CatalogEntry(
        'temple block',
        'Temple block',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=620.0, ring_seconds=0.15),
                Tone(hertz=1430.0, ring_seconds=0.06, level=0.3),
            ),
            noise=0.15,
            noise_ring_seconds=0.01,
            noise_high_pass=2000.0,
            tail=0.2,
        ),
    ),
    CatalogEntry(
        'castanets',
        'Castanets',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=3100.0, ring_seconds=0.02),),
            noise=0.7,
            noise_ring_seconds=0.02,
            noise_high_pass=2500.0,
            tail=0.05,
        ),
    ),
    CatalogEntry(
        'shaker',
        'Shaker',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_shaker, ring_seconds=0.08, high_pass=5000.0),
    ),
    CatalogEntry(
        'maracas',
        'Maracas',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_shaker, ring_seconds=0.06, high_pass=4000.0, attack=0.005),
    ),
    CatalogEntry(
        'cabasa',
        'Cabasa',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_shaker, ring_seconds=0.1, high_pass=6000.0, attack=0.02),
    ),
    CatalogEntry(
        'guiro',
        'Güiro',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_shaker, ring_seconds=0.25, high_pass=2500.0, attack=0.15),
    ),
    CatalogEntry(
        'hand clap',
        'Hand clap',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(drum, noise=1.0, noise_ring_seconds=0.12, noise_low_pass=2500.0, tail=0.15),
    ),
    CatalogEntry(
        'finger snap',
        'Finger snap',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=2200.0, ring_seconds=0.02, level=0.5),),
            noise=1.0,
            noise_ring_seconds=0.03,
            noise_high_pass=2000.0,
            tail=0.05,
        ),
    ),
    CatalogEntry(
        'high bongo',
        'Bongo (high)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 420.0, ring_seconds=0.15),
    ),
    CatalogEntry(
        'low bongo',
        'Bongo (low)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 310.0, ring_seconds=0.18),
    ),
    CatalogEntry(
        'conga',
        'Conga (open)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 215.0, ring_seconds=0.35),
    ),
    CatalogEntry(
        'tumba',
        'Tumba',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 165.0, ring_seconds=0.4),
    ),
    CatalogEntry(
        'conga slap',
        'Conga (slap)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 330.0, ring_seconds=0.06, slap=0.8),
    ),
    CatalogEntry(
        'high timbale',
        'Timbale (high)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 480.0, ring_seconds=0.4, slap=0.5),
    ),
    CatalogEntry(
        'low timbale',
        'Timbale (low)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 350.0, ring_seconds=0.45, slap=0.5),
    ),
    CatalogEntry(
        'djembe bass',
        'Djembe (bass)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 75.0, ring_seconds=0.4, slap=0.1),
    ),
    CatalogEntry(
        'djembe tone',
        'Djembe (tone)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 330.0, ring_seconds=0.2),
    ),
    CatalogEntry(
        'djembe slap',
        'Djembe (slap)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 520.0, ring_seconds=0.05, slap=0.9),
    ),
    CatalogEntry(
        'cajon bass',
        'Cajón (bass)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 85.0, ring_seconds=0.25, slap=0.2),
    ),
    CatalogEntry(
        'cajon slap',
        'Cajón (slap)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=260.0, ring_seconds=0.05),),
            noise=0.9,
            noise_ring_seconds=0.12,
            noise_high_pass=1800.0,
            tail=0.15,
        ),
    ),
    CatalogEntry(
        'tabla bayan',
        'Tabla (bayan)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=95.0, glide_to=125.0, glide_seconds=0.25, ring_seconds=0.6),),
            tail=0.5,
        ),
    ),
    CatalogEntry(
        'taiko',
        'Taiko (ōdaiko)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=70.0, glide_to=56.0, glide_seconds=0.2, ring_seconds=1.2),),
            noise=0.35,
            noise_ring_seconds=0.08,
            noise_low_pass=1500.0,
            tail=1.0,
        ),
    ),
    CatalogEntry(
        'bodhran',
        'Bodhrán',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=95.0, glide_to=85.0, glide_seconds=0.1, ring_seconds=0.35),),
            noise=0.3,
            noise_ring_seconds=0.04,
            noise_low_pass=2500.0,
            tail=0.3,
        ),
    ),
    CatalogEntry(
        'frame drum',
        'Frame drum',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 130.0, ring_seconds=0.5, slap=0.2),
    ),
    CatalogEntry(
        'darbuka doum',
        'Darbuka (doum)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 140.0, ring_seconds=0.4, slap=0.1),
    ),
    CatalogEntry(
        'darbuka tek',
        'Darbuka (tek)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=750.0, ring_seconds=0.04),),
            noise=0.8,
            noise_ring_seconds=0.04,
            noise_high_pass=2500.0,
            tail=0.08,
        ),
    ),
    CatalogEntry(
        'surdo',
        'Surdo',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 62.0, ring_seconds=0.9, slap=0.1),
    ),
    CatalogEntry(
        'cuica',
        'Cuíca',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(
                    hertz=420.0,
                    glide_to=780.0,
                    glide_seconds=0.12,
                    ring_seconds=0.2,
                    wave='triangle',
                ),
            ),
            tail=0.15,
        ),
    ),
    CatalogEntry(
        'vibraslap',
        'Vibraslap',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            _metal,
            (1150.0, 2480.0),
            ring_seconds=0.8,
            noise=0.5,
            wave='square',
            noise_high_pass=3000.0,
        ),
    ),
    CatalogEntry(
        'whip',
        'Whip (slapstick)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum, noise=1.0, noise_ring_seconds=0.03, noise_high_pass=1000.0, tail=0.05, drive=2.0
        ),
    ),
    # --- Batch 3: membranophones (Hornbostel-Sachs 2), in the order of
    # plans/data/instrument-audit/batch-3.tsv, whose notes hold each row's full quotes. In every
    # entry below each tone, glide, ring, noise band, level, drive and tail is sound design: no
    # fetched source gives a number. The source gives the traits each comment names.
    #
    # Sound: https://en.wikipedia.org/wiki/Bendir ("a wooden-framed frame drum"; "The bandir often
    # has a snare (usually made of gut) stretched across the head, which gives the tone a buzzing
    # quality when the drum is struck with the fingers or palm")
    # A large hand-struck frame drum: a low tone (105 Hz falling to 98 Hz) under the gut snare's
    # buzz, a noise band above 1.2 kHz that rings 0.25 s with the head
    CatalogEntry(
        'bendir',
        'Bendir',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=105.0, glide_to=98.0, glide_seconds=0.05, ring_seconds=0.45),),
            noise=0.6,
            noise_ring_seconds=0.25,
            noise_high_pass=1200.0,
            tail=0.45,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Bombo_leg%C3%BCero ("Because the fur is left on the
    # hide, the bombo's sound is deep and dark"; "The player's hands hold a soft-headed mallet")
    # A bass drum damped by its fur-covered head: a deep tone (58 Hz falling to 50 Hz) that dies in
    # 0.5 s, and the soft mallet's noise kept dark (below 300 Hz) and short
    CatalogEntry(
        'bombo leguero',
        'Bombo legüero',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=58.0, glide_to=50.0, glide_seconds=0.1, ring_seconds=0.5),),
            noise=0.3,
            noise_ring_seconds=0.06,
            noise_low_pass=300.0,
            tail=0.45,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Chenda ("famous for its loud and rigid sound"; "the
    # "Valamthala" will have a five/seven layer skin, so as to have a bass sound")
    # A loud stick hit: the layered bass head's tone (160 Hz falling to 140 Hz), the stick on the
    # head (600 Hz, 0.06 s) and a bright crack above 1.8 kHz, driven for the loud, rigid sound
    CatalogEntry(
        'chenda',
        'Chenda',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=160.0, glide_to=140.0, glide_seconds=0.05, ring_seconds=0.3),
                Tone(hertz=600.0, ring_seconds=0.06, level=0.5),
            ),
            noise=0.7,
            noise_ring_seconds=0.08,
            noise_high_pass=1800.0,
            tail=0.3,
            drive=4.0,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Daf ("an Iranian frame drum"; "a round wooden frame
    # ..., jingles, and a thin, translucent head")
    # A low frame-drum tone (85 Hz falling to 80 Hz) with its jingles ringing over it: a 5.8 kHz
    # metal ring and a noise band above 5 kHz, both ringing 0.35 s
    CatalogEntry(
        'daf',
        'Daf',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=85.0, glide_to=80.0, glide_seconds=0.05, ring_seconds=0.5),
                Tone(hertz=5800.0, ring_seconds=0.35, level=0.3),
            ),
            noise=0.5,
            noise_ring_seconds=0.35,
            noise_high_pass=5000.0,
            tail=0.5,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Dhol ("a double-sided barrel drum"; "to produce the
    # preferred loud bass"; the thick bass stick, the dagga, and "the teeli, is much thinner and
    # flexible and used to play the higher note end of the instrument")
    # Both sticks on both heads in one hit (sounding them together is sound design): the bass
    # head's low tone (70 Hz falling to 58 Hz) and the treble head's short 380 Hz tone, driven
    CatalogEntry(
        'dhol',
        'Dhol',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=70.0, glide_to=58.0, glide_seconds=0.12, ring_seconds=0.6),
                Tone(hertz=380.0, ring_seconds=0.08, level=0.5),
            ),
            noise=0.35,
            noise_ring_seconds=0.04,
            noise_low_pass=3000.0,
            tail=0.5,
            drive=2.0,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Dholak ("a two-headed hand drum"; a smaller drumhead
    # "made for sharp notes while the bigger drumhead ... is made for low pitch"; "the typical
    # Dholak sliding sound ("giss" or "gissa")")
    # A hand stroke on both heads: the bass head sliding (120 Hz down to 95 Hz over 0.25 s; the
    # slide's direction, depth and speed are sound design) under the small head's short 520 Hz note
    CatalogEntry(
        'dholak',
        'Dholak',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=120.0, glide_to=95.0, glide_seconds=0.25, ring_seconds=0.45),
                Tone(hertz=520.0, ring_seconds=0.08, level=0.5),
            ),
            noise=0.2,
            noise_ring_seconds=0.02,
            noise_low_pass=5000.0,
            tail=0.4,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Snare_drum ("Military drum/field drum: a snare drum
    # with a diameter of 14-16 in and 9-16 in deep"; the kit snare is "5" to 8" deep")
    # A snare drum with a deep shell: a lower, longer tone than the kit snare (150 Hz, 0.15 s)
    # under a longer, darker snare rattle (noise above 1 kHz ringing 0.3 s)
    CatalogEntry(
        'field drum',
        'Field drum',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=150.0, ring_seconds=0.15),),
            noise=0.85,
            noise_ring_seconds=0.3,
            noise_high_pass=1000.0,
            tail=0.35,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Tom_drum ("A gong bass drum ... is a large,
    # single-headed tom often sized at 20 in (51 cm) or 22 in (56 cm)"; "similar to a bass drum,
    # though it is more open and has longer sustain")
    # A very low tone (50 Hz falling to 46 Hz) that rings 3 s, longer than the orchestral bass
    # drum's 1.8 s, with less beater noise (below 400 Hz)
    CatalogEntry(
        'gong bass drum',
        'Gong bass drum',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=50.0, glide_to=46.0, glide_seconds=0.3, ring_seconds=3.0),),
            noise=0.15,
            noise_ring_seconds=0.3,
            noise_low_pass=400.0,
            tail=2.5,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Janggu ("an hourglass-shaped body with two heads"; "The
    # two heads produce sounds of different pitch and timbre"; the left head's "thick cowhide ...
    # to produce deep and low tones", the right's lighter skin "to produce higher tones")
    # Both heads struck together: the thick left head under the round mallet (140 Hz falling to
    # 130 Hz) and the thin right head under the bamboo stick (420 Hz, 0.1 s) with its slap
    CatalogEntry(
        'janggu',
        'Janggu',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=140.0, glide_to=130.0, glide_seconds=0.08, ring_seconds=0.4),
                Tone(hertz=420.0, ring_seconds=0.1, level=0.6),
            ),
            noise=0.4,
            noise_ring_seconds=0.02,
            noise_high_pass=2500.0,
            tail=0.4,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Kanjira ("a frame drum with a single pair of
    # jingles"; "between 7 and 9 inches in width"; "it has a very high pitched sound")
    # A small, very high frame-drum tone (480 Hz falling to 460 Hz) with one quiet jingle pair (a
    # 6.5 kHz ring and a little noise above 6 kHz); the player's pitch bend is not modelled
    CatalogEntry(
        'kanjira',
        'Kanjira',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=480.0, glide_to=460.0, glide_seconds=0.03, ring_seconds=0.15),
                Tone(hertz=6500.0, ring_seconds=0.15, level=0.25),
            ),
            noise=0.3,
            noise_ring_seconds=0.12,
            noise_high_pass=6000.0,
            tail=0.2,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Kebero ("a double-headed, conical hand drum"; "hard
    # particles are inserted into it"; "two cow leather membranes, so that one can be tuned higher
    # than the other")
    # A low head (100 Hz falling to 94 Hz), the head tuned higher (190 Hz), and the rattle of the
    # particles inside (noise above 3 kHz ringing 0.15 s)
    CatalogEntry(
        'kebero',
        'Kebero',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=100.0, glide_to=94.0, glide_seconds=0.05, ring_seconds=0.45),
                Tone(hertz=190.0, ring_seconds=0.25, level=0.4),
            ),
            noise=0.35,
            noise_ring_seconds=0.15,
            noise_high_pass=3000.0,
            tail=0.45,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Kendang ("a two-headed drum"; "hit with the hands on
    # either side"; "Buffalo hide is often used for the bam (inferior surface which emits low-pitch
    # beats) while soft goatskin is used for the chang (superior surface which emits high-pitch
    # beats)")
    # The medium (ciblon) drum, a hand stroke on both heads: the low bam (115 Hz falling to 108 Hz)
    # under the high chang (360 Hz)
    CatalogEntry(
        'kendang',
        'Kendang',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=115.0, glide_to=108.0, glide_seconds=0.05, ring_seconds=0.35),
                Tone(hertz=360.0, ring_seconds=0.1, level=0.5),
            ),
            noise=0.2,
            noise_ring_seconds=0.02,
            noise_low_pass=5000.0,
            tail=0.35,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Kendang ("Kendhang ageng ... is the largest kendang,
    # which usually has the deepest tone"), https://nat.museum-digital.de/tag/37818 ("Kendang
    # Ageng is very large and deep in pitch")
    # The kendang's hand stroke on the largest drum: both heads lower (80 and 250 Hz) and ringing
    # longer
    CatalogEntry(
        'kendang ageng',
        'Kendang ageng',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=80.0, glide_to=75.0, glide_seconds=0.06, ring_seconds=0.6),
                Tone(hertz=250.0, ring_seconds=0.15, level=0.4),
            ),
            noise=0.15,
            noise_ring_seconds=0.03,
            noise_low_pass=4000.0,
            tail=0.6,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Kendang ("Kendhang ketipung is the smallest kendang"),
    # https://nat.museum-digital.de/tag/37818 ("Kendang Kitipung - Java. A very small version of
    # the Ciblon")
    # The kendang's hand stroke on the smallest drum: both heads higher (200 and 560 Hz) and
    # shorter
    CatalogEntry(
        'ketipung',
        'Ketipung',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=200.0, glide_to=190.0, glide_seconds=0.03, ring_seconds=0.2),
                Tone(hertz=560.0, ring_seconds=0.07, level=0.5),
            ),
            noise=0.25,
            noise_ring_seconds=0.02,
            noise_low_pass=6000.0,
            tail=0.2,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Khol ("a terracotta two-sided drum"; "The right face of
    # the drum has a high pitch and produces a metallic sound, whereas the left face, produces a
    # lower bass sound")
    # A hand stroke on both faces: the left face's bass (95 Hz falling to 90 Hz) under the right
    # face's high tone (450 Hz) with an inharmonic 1170 Hz partial that rings, for its metallic
    # sound
    CatalogEntry(
        'khol',
        'Khol',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=95.0, glide_to=90.0, glide_seconds=0.05, ring_seconds=0.4),
                Tone(hertz=450.0, ring_seconds=0.3, level=0.6),
                Tone(hertz=1170.0, ring_seconds=0.2, level=0.3),
            ),
            noise=0.15,
            noise_ring_seconds=0.02,
            noise_low_pass=5000.0,
            tail=0.4,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Lambeg_drum ("beaten with curved malacca canes"; "one
    # of the loudest acoustic instruments in the world, frequently reaching over 120 dB"; "(92.1
    # cm) in diameter"; "The thin heads are pulled tight until the tone is bright and hard")
    # A very large drum's deep tone (72 Hz falling to 66 Hz) with a bright upper tone that rings
    # (300 Hz, 0.2 s), the canes' crack above 2 kHz, and drive for the loudness
    CatalogEntry(
        'lambeg drum',
        'Lambeg drum',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=72.0, glide_to=66.0, glide_seconds=0.08, ring_seconds=0.8),
                Tone(hertz=300.0, ring_seconds=0.2, level=0.5),
            ),
            noise=0.75,
            noise_ring_seconds=0.05,
            noise_high_pass=2000.0,
            tail=0.7,
            drive=3.0,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Mridangam ("a double-sided drum"; "The smaller
    # membrane, when struck, produces higher pitched sounds with a metallic timbre"; "unique and
    # distinct harmonics"; the paste "lowers the pitch of the wider membrane and gives it a very
    # powerful resonating bass sound")
    # Tuned to the singer, so a fixed tone, as the tabla bayan is (plan decision): the small head
    # ringing at 280 Hz with an overtone at twice it (560 Hz) over the wide head's 80 Hz bass;
    # sounding both heads together is sound design (the page names no strokes)
    CatalogEntry(
        'mridangam',
        'Mridangam',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=280.0, ring_seconds=0.6),
                Tone(hertz=560.0, ring_seconds=0.45, level=0.5),
                Tone(hertz=80.0, ring_seconds=0.4, level=0.6),
            ),
            noise=0.15,
            noise_ring_seconds=0.02,
            noise_low_pass=5000.0,
            tail=0.6,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Naqareh ("The rounded section of a naqqara is made of
    # baked clay"; "one naqqara will produce low pitch beats called nar"; "beaten with short wooden
    # sticks ... called damka"; "The diameter of the bam is about 22 cm")
    # The low drum of the pair struck with a short wooden stick: a small clay kettle's short tone
    # (230 Hz falling to 218 Hz, 0.2 s) with a bright stick click above 2.5 kHz
    CatalogEntry(
        'naqareh',
        'Naqareh (naqqara)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=230.0, glide_to=218.0, glide_seconds=0.03, ring_seconds=0.2),),
            noise=0.55,
            noise_ring_seconds=0.015,
            noise_high_pass=2500.0,
            tail=0.2,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/%C5%8Ctsuzumi ("higher and sharper in pitch, resembling
    # more of a dry, almost metallic "crack""; "The heads of the drum are taut very tightly";
    # "struck with a player's bare hands")
    # A bare-hand stroke on a very tight, stiff head: a high tone (1100 Hz) with an inharmonic
    # partial (2650 Hz), both very short, under a bright, dry crack above 3 kHz
    CatalogEntry(
        'otsuzumi',
        'Ōtsuzumi',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=1100.0, ring_seconds=0.05),
                Tone(hertz=2650.0, ring_seconds=0.035, level=0.5),
            ),
            noise=0.8,
            noise_ring_seconds=0.02,
            noise_high_pass=3000.0,
            tail=0.07,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Pandeiro ("a type of hand frame drum"; "The drumhead is
    # tunable, and the rim holds metal jingles (platinelas) which are cupped, creating a crisper,
    # drier and less sustained tone on the pandeiro than on the tambourine")
    # A hand stroke on the head (210 Hz falling to 200 Hz) with the cupped jingles' short, dry
    # jingle (a 6.2 kHz ring and noise above 4.5 kHz, both under 0.1 s)
    CatalogEntry(
        'pandeiro',
        'Pandeiro',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=210.0, glide_to=200.0, glide_seconds=0.03, ring_seconds=0.15),
                Tone(hertz=6200.0, ring_seconds=0.05, level=0.2),
            ),
            noise=0.6,
            noise_ring_seconds=0.06,
            noise_high_pass=4500.0,
            tail=0.15,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Snare_drum ("Because the piccolo snare has a narrower
    # depth ..., a higher-pitched "pop" is more widely associated with it"; "the "sharper" sound of
    # the piccolo"; "about 3 in (7.6 cm) deep")
    # A snare drum with a shallow shell: a higher, shorter tone (330 Hz, 0.06 s), the pop, under a
    # brighter snare rattle (noise above 2.5 kHz)
    CatalogEntry(
        'piccolo snare',
        'Piccolo snare',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=330.0, ring_seconds=0.06),),
            noise=0.85,
            noise_ring_seconds=0.15,
            noise_high_pass=2500.0,
            tail=0.2,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Snare_drum ("pipe band snares are deep and tuned quite
    # tightly"; "a second set of snare wires beneath the batter head ... This gives them an even
    # more crisp and snappy sound")
    # A deep, tightly tuned snare drum: a lowish tone that dies fast (175 Hz, 0.08 s) under the two
    # snare sets' crisp, snappy rattle (full noise above 3.5 kHz, 0.08 s)
    CatalogEntry(
        'pipe band snare',
        'Pipe band snare',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=175.0, ring_seconds=0.08),),
            noise=1.0,
            noise_ring_seconds=0.08,
            noise_high_pass=3500.0,
            tail=0.15,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Thavil ("the right drum head is stretched very tightly";
    # "The player usually wears thumb caps on all the fingers of the right hand, made of hardened
    # glue from maida flour")
    # The right-hand stroke: fingers in hard thumb caps on the very tight right head, a high tone
    # (400 Hz falling to 385 Hz) with a hard click above 3.5 kHz
    CatalogEntry(
        'thavil',
        'Thavil',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=400.0, glide_to=385.0, glide_seconds=0.03, ring_seconds=0.18),),
            noise=0.85,
            noise_ring_seconds=0.012,
            noise_high_pass=3500.0,
            tail=0.2,
        ),
    ),
    # --- Batch 3's sound-alikes (membranophones), in the order of
    # plans/data/instrument-audit/batch-3.tsv: each a distinct instrument, verified by its source,
    # that no fetched source sets apart in sound from the entry it names (the owner, 2026-11-08:
    # each is listed under its own name, so a person finds it by the name they know). Each builds
    # that entry's instrument (``sounds_like``); the sheet's notes give each row's full quotes and
    # why it sounds like its parent. A later source giving a trait that sets one apart makes it a
    # changed sound-alike (``sound_changes``) or its own build.
    # Sound-alike of the taiko (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Alfaia ("Alfaias are usually between 40 centimetres (16 in) and
    # 55 centimetres (22 in) in diameter")
    CatalogEntry('alfaia', 'Alfaia', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='taiko'),
    # Sound-alike of the djembe tone (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Ashiko ("The ashiko is a drum, shaped like a tapered cylinder or
    # truncated cone with the head on the wide end, and the narrow end open")
    CatalogEntry(
        'ashiko', 'Ashiko', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='djembe tone'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Atabaque ("is a tall, wooden, Afro-Brazilian hand drum, similar
    # to conga")
    CatalogEntry(
        'atabaque', 'Atabaque', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'
    ),
    # Sound-alike of the tumba (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Atumpan_(drum) ("Played in pairs, these drums provide the bass
    # part in Adowa dance ensembles")
    CatalogEntry(
        'atumpan', 'Atumpan', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='tumba'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Bamboula ("percussion instrument or type of drum made from a rum
    # barrel with skin stretched over one end")
    CatalogEntry(
        'bamboula', 'Bamboula', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'
    ),
    # Sound-alike of the darbuka tek (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Bangu_(drum) ("is a Chinese frame drum that, when struck by one
    # or two small bamboo sticks, creates a sharp dry sound essential to the aesthetics of Chinese
    # opera")
    CatalogEntry(
        'bangu', 'Bangu', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='darbuka tek'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Bat%C3%A1_drum ("The bàtá drum is a double-headed hourglass drum
    # with one end larger than the other")
    CatalogEntry(
        'bata drum', 'Batá drum', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'
    ),
    # Sound-alike of the orchestral bass drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Bedug ("A bedug is a large double-headed drum with water buffalo
    # or cow leather on both ends")
    CatalogEntry(
        'bedug',
        'Bedug',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='orchestral bass drum',
    ),
    # Sound-alike of the djembe bass (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Bougarabou ("The drums are single headed (cow skin), with an
    # elongated goblet or roughly conical shape")
    CatalogEntry(
        'bougarabou',
        'Bougarabou',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='djembe bass',
    ),
    # Sound-alike of the taiko (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Buk_(drum) ("it is most often used to refer to a shallow
    # barrel-shaped drum, with a round wooden body that is covered on both ends with animal skin")
    CatalogEntry('buk', 'Buk', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='taiko'),
    # Sound-alike of the snare drum (no fetched source sets it apart in sound):
    # https://kalango.com/en/produktberater/caixa https://en.wikipedia.org/wiki/Snare_drum ("12'' x
    # 17cm (Malacacheta / Caixa de Guerra)")
    CatalogEntry(
        'caixa malacacheta',
        'Caixa malacacheta',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='snare drum',
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Candombe_drums ("They are single skin headed and there are three
    # sizes: piano (bass range), repique (tenor range), and the chico (alto range)")
    CatalogEntry(
        'candombe drums',
        'Candombe drums (tamboriles)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='conga',
    ),
    # Sound-alike of the tumba (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Carimb%C3%B3 ("The drummer, or batedor, sits on the body of the
    # drum, which is often fitted with a wooden support, and strikes it with both hands")
    CatalogEntry(
        'carimbo', 'Carimbó', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='tumba'
    ),
    # Sound-alike of the mid tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tom_drum ("Single-headed tom-toms, also known as concert toms,
    # have also been used in drum kits")
    CatalogEntry(
        'concert tom', 'Concert tom', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='mid tom'
    ),
    # Sound-alike of the bodhran (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Cultrun ("It is approximately 35 to 40 cm in diameter and has a
    # height of 12 to 15 cm")
    CatalogEntry(
        'cultrun', 'Cultrun', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='bodhran'
    ),
    # Sound-alike of the conga slap (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dabakan ("The dabakan is a single-headed Philippine drum,
    # primarily used as a supportive instrument in the kulintang ensemble")
    CatalogEntry(
        'dabakan', 'Dabakan', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga slap'
    ),
    # Sound-alike of the bodhran (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Damphu_drum ("is like a bodhrán, a single-sided circular frame
    # drum decorated with symbols or left plain")
    CatalogEntry(
        'damphu', 'Damphu', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='bodhran'
    ),
    # Sound-alike of the dhol (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Davul ("is a large double-headed drum that is played with
    # mallets")
    CatalogEntry('davul', 'Davul', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='dhol'),
    # Sound-alike of the dhol (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dhak_(instrument) ("The dhak is a huge membranophone instrument
    # from Bengal and Assam")
    CatalogEntry('dhak', 'Dhak', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='dhol'),
    # Sound-alike of the surdo (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dhimay ("it belongs to the category of double-headed cylindrical
    # membranophone")
    CatalogEntry('dhimay', 'Dhimay', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='surdo'),
    # Sound-alike of the dhol (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dohol ("is a large cylindrical drum with two skinheads")
    CatalogEntry('dohol', 'Dohol', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='dhol'),
    # Sound-alike of the dhol (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dollu ("The dollu is a double-headed drum native to Karnataka,
    # India")
    CatalogEntry('dollu', 'Dollu', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='dhol'),
    # Sound-alike of the floor tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dunun ("A dunun is a rope-tuned cylindrical drum with a rawhide
    # skin at both ends, most commonly cow or goat. The drum is played with a stick")
    CatalogEntry(
        'dunun', 'Dunun', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='floor tom'
    ),
    # Sound-alike of the orchestral bass drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Fontomfrom ("Fontomfrom is a Bono type of hourglass-shaped drum
    # mostly used in a royal music ensemble")
    CatalogEntry(
        'fontomfrom',
        'Fontomfrom',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='orchestral bass drum',
    ),
    # Sound-alike of the orchestral bass drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Gbedu ("Gbedu literally means 'big drum' and is a percussion
    # instrument traditionally used in ceremonial Yoruba music in Nigeria and Benin")
    CatalogEntry(
        'gbedu',
        'Gbedu',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='orchestral bass drum',
    ),
    # Sound-alike of the cajon bass (no fetched source sets it apart in sound):
    # https://africandrumming.com.au/cart/gome ("The Gome drum is a fundamental solo and ensemble
    # drum among the Ga and Ashanti of Ghana")
    CatalogEntry('gome', 'Gome', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='cajon bass'),
    # Sound-alike of the high timbale (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Gudugudu ("It is designed to produce a sharp and loud beat that
    # all the other drummers can hear and keep in time with")
    CatalogEntry(
        'gudugudu', 'Gudugudu', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='high timbale'
    ),
    # Sound-alike of the taiko (no fetched source sets it apart in sound):
    # https://artdrum.com/HIRA_DAIKO.HTM ("Hira means stout or flat which describes the Hira Daiko
    # shape")
    CatalogEntry(
        'hira daiko', 'Hira-daiko', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='taiko'
    ),
    # Sound-alike of the tumba (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Huehuetl ("It is an upright tubular drum made from a wooden body
    # opened at the bottom that stands on three legs cut from its base, with skin stretched over the
    # top")
    CatalogEntry(
        'huehuetl', 'Huēhuētl', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='tumba'
    ),
    # Sound-alike of the low bongo (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Igba ("is a tom-tom that has a beating surface of the same
    # approximate diameter as a bongo")
    CatalogEntry('igba', 'Igba', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='low bongo'),
    # Sound-alike of the taiko (no fetched source sets it apart in sound):
    # https://collectionapi.metmuseum.org/public/collection/v1/objects/503213
    # https://en.wikipedia.org/wiki/Buk_(drum) ("Membranophone-double-headed / cylindrical drum")
    CatalogEntry('jwago', 'Jwago', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='taiko'),
    # Sound-alike of the high tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Kakko_(instrument) ("The kakko (羯鼓/鞨鼓) is a Japanese
    # double-headed drum")
    CatalogEntry('kakko', 'Kakko', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='high tom'),
    # Sound-alike of the kendang (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Kendang https://nat.museum-digital.de/tag/37818 ("Kendhang
    # batangan or kendhang ciblon is a medium-sized drum, used for the most complex or lively
    # rhythms")
    CatalogEntry(
        'kendang ciblon',
        'Kendang ciblon',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='kendang',
    ),
    # Sound-alike of the kendang (no fetched source sets it apart in sound):
    # https://nat.museum-digital.de/tag/37818 ("Most are played with the hands but some larger
    # varieties are played with a ball headed stick on the larger head")
    CatalogEntry(
        'kendang wadon',
        'Kendang wadon',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='kendang',
    ),
    # Sound-alike of the mid tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dunun ("The kenkeni is the smallest dunun and has the highest
    # pitch. Typical size is 45-50 cm (18-20 in) in length and 25-35 cm (9.8-13.8 in) in diameter")
    CatalogEntry(
        'kenkeni', 'Kenkeni', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='mid tom'
    ),
    # Sound-alike of the kendang (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Klong_khaek ("is a type of double-headed barrel drum used in
    # Thai music")
    CatalogEntry(
        'klong khaek', 'Klong khaek', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='kendang'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Kpanlogo_(drum)
    # https://www.djembedirect.com/hand-carved-african-kpanlogo-peg-drum-from-ghana-11x25-cow-skin/
    # ("is a type of barrel drum that is associated with Kpanlogo music, and is usually played with
    # two hands")
    CatalogEntry(
        'kpanlogo', 'Kpanlogo', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Kundu_(drum) ("Kundu is a pidgin name in Papua New Guinea for an
    # hourglass drum")
    CatalogEntry('kundu', 'Kundu', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'),
    # Sound-alike of the taiko (no fetched source sets it apart in sound):
    # https://ktb.gov.tr/EN-98653/janissary-mehter-music.html
    # https://blog.soton.ac.uk/music/2014/10/22/instruments-istanbul/ ("The Ruler's Drum (Kös) -
    # This large drum stood in front of the ruler's tent")
    CatalogEntry('kus', 'Kös (kus)', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='taiko'),
    # Sound-alike of the kendang (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Madal ("The madal has a cylindrical body with a slight bulge at
    # its center and heads at both ends, one head larger than the other. It is usually played
    # horizontally in a seated position, with both heads played simultaneously")
    CatalogEntry('madal', 'Madal', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='kendang'),
    # Sound-alike of the mridangam (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Madhalam ("It has two sides for playing, made out of leather,
    # and has different kinds of sounds on each side")
    CatalogEntry(
        'maddalam', 'Maddalam', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='mridangam'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Makuta_(drum) ("Makuta drums are tall cylindrical or
    # barrel-shaped Afro-Cuban drums, often cited as an important influence on the development of
    # the tumbadora or conga drum")
    CatalogEntry('makuta', 'Makuta', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'),
    # Sound-alike of the field drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Snare_drum ("Marching snares are typically 12 in (30 cm) deep
    # and 14 in (36 cm) wide. The larger design allows for a deeper-sounding tone, one that is
    # effective for marching bands")
    CatalogEntry(
        'marching snare',
        'Marching snare',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='field drum',
    ),
    # Sound-alike of the taiko (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Taiko ("The typical byō-uchi-daiko is the nagadō-daiko, an
    # elongated drum that is roughly shaped like a wine barrel")
    CatalogEntry(
        'nagado daiko', 'Nagadō-daiko', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='taiko'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Ngoma_drums ("Ngoma is derived from the Kikongo word for
    # 'drum'")
    CatalogEntry('ngoma', 'Ngoma', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'),
    # Sound-alike of the high tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Octoban ("are deep, small diameter, single-head tom-toms")
    CatalogEntry(
        'octoban', 'Octoban', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='high tom'
    ),
    # Sound-alike of the high tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Taiko ("Okedō-daiko or simply okedō, are a type of shime-daiko
    # that are stave-constructed using narrower strips of wood, have a tube-shaped frame")
    CatalogEntry(
        'okedo daiko',
        'Okedō-daiko',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='high tom',
    ),
    # Sound-alike of the tumba (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Pahu ("Carved from a single log and covered on the playing end
    # with a stretched sharkskin, the pahu is played with the palms and fingers of the hand")
    CatalogEntry('pahu', 'Pahu', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='tumba'),
    # Sound-alike of the mridangam (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Pakhavaj https://en.wikipedia.org/wiki/Mridangam ("The pakhavaj
    # or pakhawaj is a barrel-shaped, two-headed drum")
    CatalogEntry(
        'pakhavaj', 'Pakhavaj', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='mridangam'
    ),
    # Sound-alike of the tambourine (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Pandero_jarocho ("The pandero jarocho is an octagonal tambourine
    # or pandero traditionally played by men in the Veracruz region of Mexico")
    CatalogEntry(
        'pandero jarocho',
        'Pandero jarocho',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='tambourine',
    ),
    # Sound-alike of the bodhran (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Parai ("It consists of a shallow circular ring made of wood of
    # diameter 16-22 in (410-560 mm)")
    CatalogEntry('parai', 'Parai', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='bodhran'),
    # Sound-alike of the piccolo snare (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Snare_drum ("There are many kinds of piccolo snare which can be
    # piccolos, including the popcorn, soprano and standard snares. Popcorn snares typically have a
    # diameter of 10 in (25 cm)")
    CatalogEntry(
        'popcorn snare',
        'Popcorn snare',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='piccolo snare',
    ),
    # Sound-alike of the high bongo (no fetched source sets it apart in sound):
    # https://collectionapi.metmuseum.org/public/collection/v1/objects/501368
    # https://en.wikipedia.org/wiki/Pahu ("Membranophone-single-headed / kettle drum")
    CatalogEntry(
        'puniu',
        'Puniu (knee drum)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='high bongo',
    ),
    # Sound-alike of the tambourine (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Rebana ("The rebana or terbangan is a tambourine that is used in
    # Islamic devotional music in Southeast Asia")
    CatalogEntry(
        'rebana', 'Rebana', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='tambourine'
    ),
    # Sound-alike of the high timbale (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Repinique ("It is tuned very high to produce a tone that cuts
    # through the sound of the rest of the bateria and is used as both a lead and solo instrument")
    CatalogEntry(
        'repinique',
        'Repinique',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='high timbale',
    ),
    # Sound-alike of the djembe tone (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Sabar ("The drum is generally played with one hand and one stick
    # or 'galan'")
    CatalogEntry(
        'sabar', 'Sabar', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='djembe tone'
    ),
    # Sound-alike of the bodhran (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Sakara_drum ("The Sakara drum is a shallow membranophone with a
    # circular body made of baked clay")
    CatalogEntry(
        'sakara drum', 'Sakara drum', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='bodhran'
    ),
    # Sound-alike of the kendang (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Samphor ("is a small, 2-headed barrel drum indigenous to
    # Cambodia, approximately .35 meter wide by .5 meter long")
    CatalogEntry(
        'samphor', 'Samphor', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='kendang'
    ),
    # Sound-alike of the low tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dunun ("The sangban is of medium size, with higher pitch than
    # the dundunba. Typical size is 50-60 cm (20-24 in) in length and 30-40 cm (12-16 in) in
    # diameter")
    CatalogEntry(
        'sangban', 'Sangban', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='low tom'
    ),
    # Sound-alike of the high tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Taiko ("Shime-daiko are a set of smaller, roughly snare
    # drum-sized instrument that are tunable")
    CatalogEntry(
        'shime daiko',
        'Shime-daiko',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='high tom',
    ),
    # Sound-alike of the field drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tabor_(instrument) ("is a double-skinned portable drum, often
    # with a gut snare on the batter head, typically played with a single stick in the right hand")
    CatalogEntry(
        'tabor', 'Tabor', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='field drum'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tambora_(Dominican_drum) ("The Dominican tambora (from the
    # Spanish word tambor, meaning 'drum') is a two headed drum played in merengue music")
    CatalogEntry(
        'tambora',
        'Tambora (Dominican)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='conga',
    ),
    # Sound-alike of the darbuka tek (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tamborim ("is a small round Brazilian frame drum")
    CatalogEntry(
        'tamborim', 'Tamborim', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='darbuka tek'
    ),
    # Sound-alike of the surdo (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tan-tan ("A tan-tan is a cylindrical hand drum from Brazil that
    # is used in small samba and pagode ensembles. It imitates the big Surdo")
    CatalogEntry(
        'tan tan', 'Tan-tan', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='surdo'
    ),
    # Sound-alike of the mid tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tanggu_(drum) ("It is medium in size and barrel-shaped, with two
    # heads made of animal skin, and is played with two sticks")
    CatalogEntry(
        'tanggu', 'Tanggu', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='mid tom'
    ),
    # Sound-alike of the kendang (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Taphon ("It is barrel-shaped with two heads")
    CatalogEntry(
        'taphon', 'Taphon', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='kendang'
    ),
    # Sound-alike of the frame drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tar_(drum) ("is an ancient, single-headed frame drum. It is
    # commonly played in the Middle East and North Africa. The tar's drumhead is struck with one
    # hand")
    CatalogEntry(
        'tar drum',
        'Tar (frame drum)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='frame drum',
    ),
    # Sound-alike of the snare drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Snare_drum ("The tarol snare has similar dimensions to the kit
    # snare. The major distinction is that the snares in this type are on the top head rather than
    # the bottom one")
    CatalogEntry(
        'tarol', 'Tarol', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='snare drum'
    ),
    # Sound-alike of the naqareh (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tassa ("The tassa drum proper is a conical or bowl-shaped
    # nagaara- (aka nagada or nagaada) type drum")
    CatalogEntry(
        'tasha', 'Tassa (tasha)', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='naqareh'
    ),
    # Sound-alike of the high bongo (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tbilat ("The tbilat is a percussion instrument from Morocco
    # which resembles bongos and tabla. It consists of a pair of decorated pottery drums of
    # different sizes")
    CatalogEntry(
        'tbilat', 'Tbilat', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='high bongo'
    ),
    # Sound-alike of the orchestral bass drum (no fetched source sets it apart in sound):
    # https://theatrecrafts.com/pages/home/topics/sound/sound-effects-for-the-stage/
    # https://en.wikipedia.org/wiki/Thunder_sheet ("A large wooden frame, covered with a tight
    # drumskin, with a stick with one end covered with chamois")
    CatalogEntry(
        'thunder drum',
        'Thunder drum',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='orchestral bass drum',
    ),
    # Sound-alike of the thunder sheet (no fetched source sets it apart in sound):
    # https://patents.google.com/patent/US20170178612A1/en
    # https://remo.com/product/spring-drum-thunder-tube ("The spring drum consists of a resonant
    # tube, open at one end and closed by a membrane at the other, with a spring attached to the
    # membrane near its center")
    CatalogEntry(
        'thunder tube',
        'Thunder tube (spring drum)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='thunder sheet',
    ),
    # Sound-alike of the djembe tone (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tifa_(drum) ("The tifa, tiwa or tiva is a single-headed goblet
    # drum used throughout the Maluku Islands of Eastern Indonesia")
    CatalogEntry(
        'tifa', 'Tifa', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='djembe tone'
    ),
    # Sound-alike of the darbuka doum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tombak ("is an Iranian goblet drum")
    CatalogEntry(
        'tombak',
        'Tombak (zarb)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='darbuka doum',
    ),
    # Sound-alike of the darbuka tek (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tr%E1%BB%91ng_ch%E1%BA%A7u ("It is a small double-headed drum,
    # beaten with a long wooden stick on the top side, causing a loud snapping sound")
    CatalogEntry(
        'trong chau',
        'Trống chầu',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='darbuka tek',
    ),
    # Sound-alike of the kendang (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tr%E1%BB%91ng_c%C6%A1m ("is a kind of traditional barrel-shaped
    # Vietnamese drum")
    CatalogEntry(
        'trong com', 'Trống cơm', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='kendang'
    ),
    # Sound-alike of the orchestral bass drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Taiko ("The tsuri-daiko (釣太鼓, 'suspended drum') is a smaller
    # drum that produces a lower sound, its head measuring about 55 cm (22 in) in diameter")
    CatalogEntry(
        'tsuri daiko',
        'Tsuri-daiko',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='orchestral bass drum',
    ),
    # Sound-alike of the bodhran (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Taiko ("Uchiwa-daiko (団扇太鼓; literally, fan drum) is a type
    # of racket-shaped Japanese drum. It is the only Japanese traditional drum without a sound box
    # and only one skin. It is played with a drumstick while hanging it with the other hand")
    CatalogEntry(
        'uchiwa daiko',
        'Uchiwa-daiko',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='bodhran',
    ),
    # Sound-alike of the high tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Urumi_(drum) ("is a double-headed hourglass drum from the state
    # of Tamil Nadu, South India")
    CatalogEntry('urumi', 'Urumi', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='high tom'),
    # Sound-alike of the dhol (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Zabumba ("The top head is usually muted with tape or cloth
    # strip(s) and struck with a cloth-covered mallet (held in the right hand) to produce a low
    # fundamental note with minimal overtones")
    CatalogEntry('zabumba', 'Zabumba', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='dhol'),
    # Sound-alike of the daf (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Khanjani ("Khanjani is a percussion musical instrument, a
    # variety of Daf, found in West Bengal & Odisha")
    CatalogEntry(
        'khanjani', 'Khanjani', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='daf'
    ),
    # Sound-alike of the dhol (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Davul https://en.wikipedia.org/wiki/Tabl ("The Tabl, tapan,
    # atabal or davul is a large double-headed drum that is played with mallets")
    CatalogEntry('tabl', 'Tabl', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='dhol'),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Timbau ("The timbau or Brazilian timbal is a membranophone
    # instrument derived from the caxambu drum, usually played with both hands")
    CatalogEntry(
        'timbal', 'Timbal (timbau)', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'
    ),
    # Sound-alike of the darbuka doum (no fetched source sets it apart in sound):
    # https://www.outlookindia.com/culture-society/tumbhaknari-the-soulful-rhythm-of-kashmirs-heartbeat
    # https://www.greaterkashmir.com/news/opinion/clay-musical-instruments-of-kashmir/ ("a goblet
    # drum traditional to Jammu and Kashmir")
    CatalogEntry(
        'tumbaknari',
        'Tumbaknari',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='darbuka doum',
    ),
)
