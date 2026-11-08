"""Sound effects: theatre and Foley devices that imitate a non-musical sound.

This family is defined by use, not by how the sound is made: a thunder sheet, a rain machine or
a pair of coconut shells exists to stand in for thunder, rain or a horse. The Foley craft, the
reproduction of everyday sounds for film and stage, is described at
https://en.wikipedia.org/wiki/Foley_(filmmaking)

Every effect plays as a note, so it can be used in music; each is unpitched and ignores the
pitch it is given, as a drum does, so each is built with ``drum``: a noise band with a ring for
a one-shot (a thunder sheet's crash), with an attack for a swell (a thunder run, an ocean drum).
None of them sustains while held: each dies away after its ring.
"""

from __future__ import annotations

from functools import partial
from typing import Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import Tone, drum

SOUND_EFFECTS: Final[tuple[CatalogEntry, ...]] = (
    # Sound: https://en.wikipedia.org/wiki/Thunder_sheet (shaken or struck "a thin sheet of metal";
    # no frequencies), https://props.eric-hart.com/how-to/mechanical-sound-effects ("Thunder was
    # created by hanging a large sheet of thin iron and shaking it")
    # The 0.8 noise level, 1.5 kHz low pass, 0.25 s attack, 3.0 s ring, the 120 Hz metal ring (level
    # 0.3, 2.5 s), the drive and the 1.0 s tail are sound design (no source gives a figure): the
    # shaken sheet is a long metallic ring under a swelling roar
    CatalogEntry(
        'thunder sheet',
        'Thunder sheet',
        Family.SOUND_EFFECTS,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=120.0, ring_seconds=2.5, level=0.3),),
            noise=0.8,
            noise_ring_seconds=3.0,
            noise_low_pass=1500.0,
            attack=0.25,
            tail=1.0,
            drive=2.0,
        ),
    ),
    # Sound: https://bristololdvic.org.uk/archive/thunder-run (iron weights "rolled down" a wooden
    # trough), https://theatrecrafts.com/pages/home/topics/sound/sound-effects-for-the-stage/
    # The 0.9 noise level, 400 Hz low pass, 0.6 s attack, 4.0 s ring and 1.5 s tail are sound
    # design (no source gives a figure): a low rolling rumble with no metal ring, so no tone
    CatalogEntry(
        'thunder run',
        'Thunder run',
        Family.SOUND_EFFECTS,
        None,
        None,
        partial(
            drum,
            noise=0.9,
            noise_ring_seconds=4.0,
            noise_low_pass=400.0,
            attack=0.6,
            tail=1.5,
        ),
    ),
    # Sound: https://api.vam.ac.uk/v2/object/O74191 (a "Sound machine" holding dried peas or small
    # stones, made "to produce the sound of rain")
    # The 0.7 noise level, 3 kHz high pass, 0.05 s attack, 1.5 s ring and 0.5 s tail are sound
    # design (no source gives a figure): a patter of many small impacts as one steady high band
    CatalogEntry(
        'rain machine',
        'Rain machine (rain box)',
        Family.SOUND_EFFECTS,
        None,
        None,
        partial(
            drum,
            noise=0.7,
            noise_ring_seconds=1.5,
            noise_high_pass=3000.0,
            attack=0.05,
            tail=0.5,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Ocean_drum (metal beads "roll over the bottom head like
    # water rolling over the shore"; no frequencies)
    # The 0.8 noise level, 2 kHz low pass, 0.8 s attack, 2.5 s ring and 1.0 s tail are sound design
    # (no source gives a figure): a low-passed swell, unlike the rain machine's high patter
    CatalogEntry(
        'ocean drum',
        'Ocean drum',
        Family.SOUND_EFFECTS,
        None,
        None,
        partial(
            drum,
            noise=0.8,
            noise_ring_seconds=2.5,
            noise_low_pass=2000.0,
            attack=0.8,
            tail=1.0,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/1812_Overture (cannon shots, often a substitute; no
    # frequencies), https://props.eric-hart.com/how-to/mechanical-sound-effects
    # The 70 Hz tone gliding to 35 Hz in 0.3 s (level 0.9, 0.6 s ring), the 0.7 noise level, 600 Hz
    # low pass, 0.8 s ring, the drive and the 0.5 s tail are sound design (no source gives a
    # figure); the tone stays audible, not sub-audio
    CatalogEntry(
        'cannon',
        'Cannon',
        Family.SOUND_EFFECTS,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=70.0, ring_seconds=0.6, glide_to=35.0, glide_seconds=0.3, level=0.9),
            ),
            noise=0.7,
            noise_ring_seconds=0.8,
            noise_low_pass=600.0,
            tail=0.5,
            drive=6.0,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Crash_box_(stagecraft)
    # ("a device which reproduces a crash or collision sound effect"; glassware or crockery dropped)
    # The 0.9 noise level, 2 kHz high pass, 0.6 s ring, the 1.2 kHz and 2.1 kHz rings (level 0.3,
    # 0.3 s), the drive and the 0.3 s tail are sound design (no source gives a figure): bright,
    # glassy noise with two high rings
    CatalogEntry(
        'crash box',
        'Crash box',
        Family.SOUND_EFFECTS,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=1200.0, ring_seconds=0.3, level=0.3),
                Tone(hertz=2100.0, ring_seconds=0.3, level=0.3),
            ),
            noise=0.9,
            noise_ring_seconds=0.6,
            noise_high_pass=2000.0,
            tail=0.3,
            drive=3.0,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Foley_(filmmaking)
    # (the page says coconut shells "cut in half and stuffed with padding make horse hoof noises")
    # The 900 Hz and 1.7 kHz tones (0.04 s and 0.02 s rings, levels 1.0 and 0.4), the 0.2 noise
    # level, 2 kHz high pass and 0.01 s ring are sound design (no source gives a figure), with no
    # tail: a short hollow clop, higher and less dry than the catalog woodblock
    CatalogEntry(
        'coconut shells',
        'Coconut shells (horse hooves)',
        Family.SOUND_EFFECTS,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=900.0, ring_seconds=0.04),
                Tone(hertz=1700.0, ring_seconds=0.02, level=0.4),
            ),
            noise=0.2,
            noise_ring_seconds=0.01,
            noise_high_pass=2000.0,
            tail=0.0,
        ),
    ),
    # Sound: https://theatrecrafts.com/pages/home/topics/sound/sound-effects-for-the-stage/
    # ("A wooden box with a hinged lid, fitted with door handles and a lock", slammed offstage)
    # The 110 Hz tone (0.15 s ring), the 0.6 noise level, 1.2 kHz low pass, 0.12 s ring and drive
    # are sound design (no source gives a figure), with no tail: a short wooden thud
    CatalogEntry(
        'door slam',
        'Door slam',
        Family.SOUND_EFFECTS,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=110.0, ring_seconds=0.15),),
            noise=0.6,
            noise_ring_seconds=0.12,
            noise_low_pass=1200.0,
            tail=0.0,
            drive=2.0,
        ),
    ),
    # Sound: https://theatrecrafts.com/pages/home/topics/sound/sound-effects-for-the-stage/ ("sprung
    # wooden plungers ... fall onto a wooden box and produce a loud thud")
    # The 55 Hz tone gliding to 40 Hz in 0.1 s (0.3 s ring) and the 0.1 s tail are sound design (no
    # source gives a figure): one deep thud, tone only
    CatalogEntry(
        'giants footsteps',
        'Giants footsteps',
        Family.SOUND_EFFECTS,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=55.0, ring_seconds=0.3, glide_to=40.0, glide_seconds=0.1),),
            tail=0.1,
        ),
    ),
    # Sound: https://www.props.eric-hart.com/?p=1063 (glass-paper imitating a railway engine)
    # The 0.7 noise level, 4 kHz high pass, 0.03 s attack and 0.15 s ring are sound design (no
    # source gives a figure), with no tail: one short rasp, a quick high swish
    CatalogEntry(
        'sandpaper blocks',
        'Sandpaper blocks',
        Family.SOUND_EFFECTS,
        None,
        None,
        partial(
            drum,
            noise=0.7,
            noise_ring_seconds=0.15,
            noise_high_pass=4000.0,
            attack=0.03,
            tail=0.0,
        ),
    ),
)
