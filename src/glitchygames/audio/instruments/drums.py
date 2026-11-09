"""Drums and percussion: drums, rattles, scrapers, clappers, cymbals and gongs, all unpitched.

The family holds the Hornbostel-Sachs classes 1 (idiophones: rattles, scrapers, clappers,
blocks, cymbals, gongs, bells) and 2 (membranophones: struck and friction drums) whose sound has
no definite pitch (https://en.wikipedia.org/wiki/Hornbostel%E2%80%93Sachs). Tuned bars, bells,
pans and timpani are tuned percussion (``percussion.py``). Untuned percussion is fixed tones and
filtered noise: its sounds do not follow the note's pitch, so these entries have no range, and a
fixed tone ignores the pitch given. Each is built with ``drum``: a struck tone that rings out, a
noise band for the stick, hand or snares, and a tail; a ring is cut when the note ends, fading
out over the entry's ``tail``. The family's sound-alikes, instruments that share an entry's
build (``sounds_like``), are listed in the sibling module ``drum_sound_alikes.py``;
``DRUMS_AND_PERCUSSION`` is this module's builds followed by them.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.drum_sound_alikes import DRUM_SOUND_ALIKES
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


_DRUM_BUILDS: Final[tuple[CatalogEntry, ...]] = (
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
    # --- Batch 3: idiophones (Hornbostel-Sachs 1), in the order of
    # plans/data/instrument-audit/batch-3.tsv, whose notes hold each row's full quotes. In every
    # entry below each tone, glide, ring, noise band, level, drive and tail is sound design (the
    # udu's three measured frequencies excepted): no fetched source gives a number. The source
    # gives the traits each comment names.
    #
    # Sound: https://en.wikipedia.org/wiki/Agung ("The agung is a large, heavy, wide-rimmed gong
    # shaped like a kettle gong"; "The larger, lower pitched gong of the two is called the
    # pangandungan"; mallets "padded with soft but tough material such as rubber at one end"; "A
    # series of solid, fast decaying sounds are produced using dampening techniques")
    # The pangandungan struck on its knob with a padded mallet and damped: a deep, steady
    # bossed-gong tone (110 Hz) with two inharmonic partials (290 and 655 Hz) that dies quickly,
    # under a soft, dark mallet thump (noise below 600 Hz). The page gives no note, so the tone is
    # fixed
    CatalogEntry(
        'agung',
        'Agung',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=110.0, ring_seconds=0.45),
                Tone(hertz=290.0, ring_seconds=0.3, level=0.35),
                Tone(hertz=655.0, ring_seconds=0.3, level=0.25),
            ),
            noise=0.15,
            noise_ring_seconds=0.03,
            noise_low_pass=600.0,
            tail=0.45,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Anvil ("The vast majority of extant works use the anvil
    # as unpitched"; "Steel anvils are used for tuning for use as musical instruments, because
    # those based partly on cast iron and similar materials give a duller sound; ... pure steel
    # anvils are troublesomely noisy")
    # A struck steel block: a hammer's bright crack (noise above 2 kHz) over three inharmonic steel
    # partials (1150, 2780 and 4370 Hz) ringing a little under a second, with drive for the noisy
    # steel
    CatalogEntry(
        'anvil',
        'Anvil',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=1150.0, ring_seconds=0.8),
                Tone(hertz=2780.0, ring_seconds=0.6, level=0.6),
                Tone(hertz=4370.0, ring_seconds=0.4, level=0.4),
            ),
            noise=0.7,
            noise_ring_seconds=0.03,
            noise_high_pass=2000.0,
            tail=0.8,
            drive=1.5,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Bak_(instrument) ("The upper part of the six long and
    # narrow boards are tied with a string, and the lower part is held open with both hands, and
    # then closed rapidly, creating a clear impact sound"; "The bak is made of 6 flat wood boards
    # that are about 13 1/2 in. x 2 3/4 in")
    # Six long boards slapped shut: a loud, broad slap (noise above 700 Hz) over a low, short wood
    # knock (820 and 1370 Hz)
    CatalogEntry(
        'bak',
        'Bak',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=820.0, ring_seconds=0.05),
                Tone(hertz=1370.0, ring_seconds=0.03, level=0.4),
            ),
            noise=0.9,
            noise_ring_seconds=0.05,
            noise_high_pass=700.0,
            tail=0.08,
        ),
    ),
    # Sound: https://www.geidai.ac.jp/labs/koizumi/gcat0/english/html-text/063.html (daluo: "brass;
    # Dm. 18.5cm"; "mallet: 1, wood"; "The central raised area of this gong is struck with a
    # mallet."; "After striking, the pitch falls.") and https://en.wikipedia.org/wiki/Gong ("a pair
    # of gongs, the larger with a descending tone, the smaller with a rising tone")
    # A small brass opera gong struck at its centre with a wooden mallet: a mid tone and its upper
    # partial each falling after the strike (330 to 290 Hz and 760 to 670 Hz over 0.6 s), under a
    # short wooden knock (noise below 2.5 kHz)
    CatalogEntry(
        'daluo',
        'Daluo',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=330.0, glide_to=290.0, glide_seconds=0.6, ring_seconds=1.6),
                Tone(hertz=760.0, glide_to=670.0, glide_seconds=0.6, ring_seconds=1.0, level=0.4),
            ),
            noise=0.3,
            noise_ring_seconds=0.03,
            noise_low_pass=2500.0,
            tail=1.6,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Flat_ride_cymbal ("a ride cymbal without a bell"; "A flat
    # ride cymbal produces the tightest, driest, most controlled stick sound of all ride cymbals,
    # but with an airy wash"; "The lack of bell makes this cymbal quieter")
    # A ride with no bell: a dry stick ping (2900, 4100 and 5600 Hz, under 0.5 s) under a quiet,
    # airy wash (noise above 6 kHz) that outlasts it
    CatalogEntry(
        'flat ride cymbal',
        'Flat ride cymbal',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=2900.0, ring_seconds=0.5),
                Tone(hertz=4100.0, ring_seconds=0.45, level=0.6),
                Tone(hertz=5600.0, ring_seconds=0.4, level=0.6),
            ),
            noise=0.45,
            noise_ring_seconds=1.4,
            noise_high_pass=6000.0,
            tail=1.4,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Garamut ("Carved from a single log, a garamut is beaten
    # with sticks to produce sound from its central cavity"; "Sounds are made by striking beater
    # sticks near the slit which leads to a large central cavity"; "The sound can be heard for
    # multiple kilometres")
    # A log slit drum struck with a stick by its slit: a deep, steady cavity tone (130 Hz) ringing
    # long (1.4 s, standing for the large cavity and far-carrying sound), a wood partial (330 Hz)
    # and a short, hard stick knock (1150 Hz and noise above 1.5 kHz)
    CatalogEntry(
        'garamut',
        'Garamut',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=130.0, ring_seconds=1.4),
                Tone(hertz=330.0, ring_seconds=0.3, level=0.5),
                Tone(hertz=1150.0, ring_seconds=0.03, level=0.35),
            ),
            noise=0.35,
            noise_ring_seconds=0.01,
            noise_high_pass=1500.0,
            tail=1.4,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Ghatam ("It is a clay pot with a narrow mouth"; "The
    # Manamadurai ghatam is a heavy, thick pot with tiny shards of brass mixed into the clay. This
    # type of ghatam ... produces a sharp metallic ringing sound"; "The performer uses their
    # fingers, thumbs, palms, and heels of the hands to strike its outer surface")
    # A finger stroke on the pot's side: a short, low clay thud (240 Hz) with a sharp metallic ring
    # above it (1650 Hz) and a soft finger knock (noise above 2 kHz). The pitch varies with each
    # pot, so the tone is fixed
    CatalogEntry(
        'ghatam',
        'Ghatam',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=240.0, ring_seconds=0.12),
                Tone(hertz=1650.0, ring_seconds=0.3, level=0.45),
            ),
            noise=0.35,
            noise_ring_seconds=0.015,
            noise_high_pass=2000.0,
            tail=0.3,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Gongu%C3%AA ("a type of cowbell consisting of a big, flat
    # iron bell, measuring from 20-30 centimetres"; "usually played with a metal drumstick"; "Due
    # to its size, the Gongue has a loud and strident sound, more clangorous than other types of
    # cowbells")
    # A big flat iron cowbell struck with a metal stick: square-wave partials lower than the
    # cowbell's (380 and 570 Hz), a metal tick (noise above 3 kHz) and drive for the clangour
    CatalogEntry(
        'gongue',
        'Gonguê',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=380.0, ring_seconds=0.45, level=0.6, wave='square'),
                Tone(hertz=570.0, ring_seconds=0.45, level=0.6, wave='square'),
            ),
            noise=0.4,
            noise_ring_seconds=0.05,
            noise_high_pass=3000.0,
            tail=0.45,
            drive=1.5,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/G%C3%BCira ("It is made of a metal sheet (commonly steel)
    # and played with a stiff brush"; "its uniquely swishy metallic timbre"; "the guira is usually
    # brushed (lightly scraped transversely) steadily on the downbeat")
    # One brush stroke across the steel tube: a bright swish (noise above 4.5 kHz, a 0.06 s attack)
    # with a light metallic ring from the sheet (3400 and 5200 Hz)
    CatalogEntry(
        'guira',
        'Güira',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=3400.0, ring_seconds=0.12, level=0.25),
                Tone(hertz=5200.0, ring_seconds=0.1, level=0.25),
            ),
            noise=1.0,
            noise_ring_seconds=0.18,
            noise_high_pass=4500.0,
            tail=0.2,
            attack=0.06,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Jing_(instrument) ("is a large gong"; "struck by a stick
    # that is layered with cloth at one end to soften the texture of the sound produced"; "capable
    # of producing a gentle and lingering sound"; "it has a constant pitch and produces a
    # harmonious sound on its own")
    # A large brass gong struck gently with a cloth-padded stick: a steady tone with harmonic
    # partials (205, 410 and 615 Hz) lingering for seconds, under a soft, dark thump (noise below
    # 700 Hz). The page gives no note, so the tone is fixed
    CatalogEntry(
        'jing',
        'Jing',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=205.0, ring_seconds=4.0),
                Tone(hertz=410.0, ring_seconds=3.0, level=0.4),
                Tone(hertz=615.0, ring_seconds=2.0, level=0.2),
            ),
            noise=0.15,
            noise_ring_seconds=0.08,
            noise_low_pass=700.0,
            tail=4.0,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Jingle_bell ("A jingle bell or sleigh bell is a type of
    # bell which produces a distinctive 'jingle' sound, especially in large numbers"; "a single
    # piece of sheet metal bent into a roughly spherical shape to contain a small ball bearing or
    # short piece of metal rod")
    # A cluster of small closed bells shaken: bell partials (3300, 4900 and 6800 Hz) ringing under
    # the balls' high rattle (noise above 5 kHz)
    CatalogEntry(
        'jingle bells',
        'Jingle bells',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=3300.0, ring_seconds=0.45),
                Tone(hertz=4900.0, ring_seconds=0.4, level=0.6),
                Tone(hertz=6800.0, ring_seconds=0.35, level=0.6),
            ),
            noise=0.5,
            noise_ring_seconds=0.2,
            noise_high_pass=5000.0,
            tail=0.45,
            attack=0.01,
        ),
    ),
    # Sound: https://www.afroton.de/en/karkabou-pair-pro-1214-en ("handforged top-quality iron
    # castanets"; "strong, penetrating, highly variable metal sound") and
    # https://en.wikipedia.org/wiki/Krakebs ("an iron castanet-like musical instrument"; "In the
    # Gnawa style, krakeb stay closed between hits so that the instrument clanging shut is the
    # most prominent sound")
    # Iron castanets clanged shut: short square-wave metal partials (1850 and 3050 Hz, cut short as
    # the plates stay closed) under a clack (noise above 3 kHz), with drive for the strong,
    # penetrating sound
    CatalogEntry(
        'karkabou',
        'Karkabou (qraqeb)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=1850.0, ring_seconds=0.08, level=0.6, wave='square'),
                Tone(hertz=3050.0, ring_seconds=0.06, level=0.6, wave='square'),
            ),
            noise=0.8,
            noise_ring_seconds=0.04,
            noise_high_pass=3000.0,
            tail=0.1,
            drive=2.0,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Kemanak ("a banana-shaped idiophone made of bronze";
    # "It is actually a metal slit drum. It is struck with a padded stick and then allowed to
    # resonate"; "It has a specific pitch ... but it is not matched to the other instruments of the
    # gamelan")
    # A bronze slit drum struck with a padded stick and left to ring: a metal tone (600 Hz) with an
    # inharmonic partial (1620 Hz) resonating almost two seconds, under a soft, dark strike (noise
    # below 1 kHz). No compass is given, so the tone is fixed
    CatalogEntry(
        'kemanak',
        'Kemanak',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=600.0, ring_seconds=1.8),
                Tone(hertz=1620.0, ring_seconds=1.0, level=0.35),
            ),
            noise=0.1,
            noise_ring_seconds=0.02,
            noise_low_pass=1000.0,
            tail=1.8,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Khartal ("This wooden clapper ... has discs or plates
    # that produce a clinking sound when clapped together"; "Kartals (blocks). It consists of a
    # pair of wooden blocks with jingles or crotales")
    # A pair of wooden blocks with jingles clapped together: a dry wooden click (2400 Hz, 0.03 s)
    # with the jingles' clink ringing over it (5800 and 7900 Hz, and noise above 6 kHz)
    CatalogEntry(
        'khartal',
        'Khartal',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=2400.0, ring_seconds=0.03),
                Tone(hertz=5800.0, ring_seconds=0.3, level=0.5),
                Tone(hertz=7900.0, ring_seconds=0.25, level=0.4),
            ),
            noise=0.6,
            noise_ring_seconds=0.2,
            noise_high_pass=6000.0,
            tail=0.3,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Kkwaenggwari ("a small flat gong ... made of brass and
    # is played with a hard stick"; "a distinctively high-pitched, metallic tone that breaks into a
    # cymbal-like crashing timbre when struck forcefully"; "a brass plate with a diameter of
    # around 20 cm"; the back "is blocked with the left hand to control the volume and tone")
    # A small flat brass gong struck with a hard stick: high metallic partials (1250, 2050 and 3300
    # Hz) under a cymbal-like crash (noise above 3 kHz), cut short by the hand behind it
    CatalogEntry(
        'kkwaenggwari',
        'Kkwaenggwari',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=1250.0, ring_seconds=0.5),
                Tone(hertz=2050.0, ring_seconds=0.45, level=0.6),
                Tone(hertz=3300.0, ring_seconds=0.4, level=0.6),
            ),
            noise=0.6,
            noise_ring_seconds=0.3,
            noise_high_pass=3000.0,
            tail=0.5,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Monkey_stick (Lagerphone redirects there: "a stout pole
    # with metal "jingles" fastened at intervals along the shaft. These are commonly beer-bottle
    # tops"; "When played on a wooden floor ..., the sound produced is a combination of a bass drum
    # and tambourine"; "In Australia, this instrument constructed with beer-bottle tops is known as
    # a lagerphone")
    # The pole struck on a wooden floor: a short, low thump (75 Hz, the bass drum part) with the
    # bottle tops clattering over it (5000 and 6900 Hz, and noise above 5 kHz: the tambourine part)
    CatalogEntry(
        'lagerphone',
        'Lagerphone',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=75.0, ring_seconds=0.18),
                Tone(hertz=5000.0, ring_seconds=0.3, level=0.5),
                Tone(hertz=6900.0, ring_seconds=0.25, level=0.4),
            ),
            noise=0.7,
            noise_ring_seconds=0.25,
            noise_high_pass=5000.0,
            tail=0.3,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Sizzle_cymbal ("a cymbal to which rivets, chains or other
    # rattles have been added"; "the sound of the 'wash' of the cymbal is made louder and more
    # penetrating, and is dominated by the sound of the rattles themselves"; "the cymbal loses some
    # of its sustain"; "a large ride cymbal with a number of rivets")
    # A large ride with rivets: a ride's ping (2300, 3300 and 4700 Hz) under a loud, bright rivet
    # wash (full noise above 3.5 kHz) that dominates it, ringing shorter than a plain ride
    CatalogEntry(
        'sizzle cymbal',
        'Sizzle cymbal',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=2300.0, ring_seconds=1.3),
                Tone(hertz=3300.0, ring_seconds=1.1, level=0.6),
                Tone(hertz=4700.0, ring_seconds=0.9, level=0.5),
            ),
            noise=1.0,
            noise_ring_seconds=1.3,
            noise_high_pass=3500.0,
            tail=1.3,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Gong ("A tiger gong is a slightly descending or less
    # commonly ascending gong, larger than an opera gong and with a less pronounced pitch shift.
    # Most commonly 38 cm")
    # The common descending tiger gong: a low gong tone and its upper partial sinking slightly
    # after the strike (175 to 165 Hz and 410 to 387 Hz over 0.8 s), ringing long, under a quiet
    # mallet (noise below 2 kHz)
    CatalogEntry(
        'tiger gong',
        'Tiger gong',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=175.0, glide_to=165.0, glide_seconds=0.8, ring_seconds=2.5),
                Tone(hertz=410.0, glide_to=387.0, glide_seconds=0.8, ring_seconds=1.6, level=0.4),
            ),
            noise=0.3,
            noise_ring_seconds=0.03,
            noise_low_pass=2000.0,
            tail=2.5,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Tingsha ("are small cymbals"; "The cymbals are struck
    # together producing a clear and high pitched tone"; "Tingsha are very thick and produce a
    # unique long ringing tone. Antique tingsha were made from special bronze alloys that produce
    # harmonic overtones")
    # A pair of thick small cymbals struck together: a clear, high tone with harmonic overtones
    # (2350, 4700 and 7050 Hz) ringing a long time, with a faint click as they meet (noise above
    # 5 kHz)
    CatalogEntry(
        'tingsha',
        'Tingsha',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=2350.0, ring_seconds=4.0),
                Tone(hertz=4700.0, ring_seconds=3.0, level=0.4),
                Tone(hertz=7050.0, ring_seconds=2.0, level=0.2),
            ),
            noise=0.15,
            noise_ring_seconds=0.01,
            noise_high_pass=5000.0,
            tail=4.0,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Udu ("Usually, the Udu is made of clay"; "The player
    # produces a bass sound by quickly striking the larger hole.") and
    # https://physics.byu.edu/docs/publication/1551 (Anderson, Hilton and Giorgini, J. Acoust. Soc.
    # Am. 133 (3), 2013: "The signature sounds of the Udu are the deep bass aerophonic resonances
    # and terminal octave slide"; "When the hand strikes a hole and immediately releases, the tone
    # quickly slides up nearly an octave before dissipating"; "The three aerophone resonance
    # frequencies are 73, 113, and 137 Hz"; "the lowest dominant partial is at 556 Hz")
    # The palm strikes the hole and releases: a deep bass sliding up nearly an octave as it dies
    # (73 rising to 137 Hz, the measured lowest and highest resonances), a faint clay partial (556
    # Hz, measured) and a soft palm (noise below 1.2 kHz). The frequencies are the paper's Udu
    # Utar, so the tone is fixed; the glide time, rings, levels, noise and tail are sound design
    CatalogEntry(
        'udu',
        'Udu',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=73.0, glide_to=137.0, glide_seconds=0.15, ring_seconds=0.5),
                Tone(hertz=556.0, ring_seconds=0.12, level=0.2),
            ),
            noise=0.15,
            noise_ring_seconds=0.02,
            noise_low_pass=1200.0,
            tail=0.5,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Washboard_(musical_instrument) ("employing the ribbed
    # metal surface of the cleaning device as a rhythm instrument"; "the washboard remains in its
    # wooden frame and is played primarily by tapping, but also by scraping with thimbles")
    # Its main stroke, a thimble tap on the ribbed metal: a short, bright, tinny tick (3600 and 5300
    # Hz under noise above 4 kHz)
    CatalogEntry(
        'washboard',
        'Washboard',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=3600.0, ring_seconds=0.07, level=0.5),
                Tone(hertz=5300.0, ring_seconds=0.05, level=0.4),
            ),
            noise=0.6,
            noise_ring_seconds=0.015,
            noise_high_pass=4000.0,
            tail=0.08,
        ),
    ),
    # Sound: https://www.geidai.ac.jp/labs/koizumi/gcat0/english/html-text/064.html (xiaoluo:
    # "brass; Dm. 22.5cm beater: 1, wood"; "struck at the middle with a long rectangular beater
    # held lightly"; "After being struck, the pitch of the gong rises") and
    # https://en.wikipedia.org/wiki/Gong ("a pair of gongs, the larger with a descending tone, the
    # smaller with a rising tone")
    # The opera gong whose pitch rises: a bright gong tone and its upper partial climbing as they
    # ring (360 to 420 Hz and 830 to 970 Hz over 0.5 s), under a light wooden beater (noise below
    # 3 kHz)
    CatalogEntry(
        'xiaoluo',
        'Xiaoluo',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=360.0, glide_to=420.0, glide_seconds=0.5, ring_seconds=1.2),
                Tone(hertz=830.0, glide_to=970.0, glide_seconds=0.5, ring_seconds=0.8, level=0.4),
            ),
            noise=0.3,
            noise_ring_seconds=0.02,
            noise_low_pass=3000.0,
            tail=1.2,
        ),
    ),
)

# The family: its builds, then the sound-alikes that share them (``drum_sound_alikes.py``)
DRUMS_AND_PERCUSSION: Final[tuple[CatalogEntry, ...]] = _DRUM_BUILDS + DRUM_SOUND_ALIKES
