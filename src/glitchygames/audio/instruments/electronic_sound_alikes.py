"""Electronic's sound-alikes: listed instruments that share another entry's build.

A sound-alike is a distinct instrument, verified by its source, that no fetched source sets apart
in sound from an existing entry. The owner ruled (2026-11-08) that each is a catalog entry of its
own rather than an alias: "could we also consider making them full on instruments that inherit
from the parent and change their details? ... I want them to all show up." Each is listed under
its own name, so a person finds it by the name they know, and each builds its parent's
instrument through ``sounds_like`` (assembled in ``registry.sound_alikes_from``). It gives its own
sourced range, since a sound-alike of another size plays another span. A true alias, another name
for the same instrument, stays in ``aliases.py``. The family's builds are in ``electronic.py``.
"""

from __future__ import annotations

from typing import Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family, Tag

ELECTRONIC_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]] = (
    # --- Batch 6's sound-alikes (the machines), in the order of
    # plans/data/instrument-audit/batch-6.tsv: each a distinct instrument, verified by its source,
    # that no fetched source sets apart in sound from the entry it names. Each builds that entry's
    # instrument (``sounds_like``); the sheet's notes give each row's full quotes and why it
    # sounds like its parent. A later source giving a trait that sets one apart makes it a changed
    # sound-alike (``sound_changes``) or its own build. A parent may be in another family (the
    # drum-machine voices' are in drums and percussion), and an unpitched parent's sound-alike is
    # unpitched
    # Sound-alike of the chip square (no fetched source sets it apart in sound):
    # http://map.grauw.nl/resources/sound/generalinstrument_ay-3-8910.pdf (Sound Generating
    # Blocks: "Tone Generators produce the basic square wave tone frequencies for each channel
    # (A,B,C)"). Range: https://en.wikipedia.org/wiki/General_Instrument_AY-3-8910 ("the lowest
    # directly definable output frequency is 30.6 Hz, roughly equal to B0"; "This allows it to
    # generate tones with fundamental frequencies up to 125 kHz"): B0 (30.87 Hz) is the lowest
    # note at or above 30.6 Hz, and 125 kHz is clipped to C8, the catalog's top. The page gives
    # the chip's hertz, not one machine's (the controller's ruling, listed for the owner)
    CatalogEntry(
        'ay 3 8910',
        'General Instrument AY-3-8910',
        Family.ELECTRONIC,
        'B0',
        'C8',
        sounds_like='chip square',
        tags=frozenset({Tag.CHIP}),
    ),
    # Sound-alike of the claves (no fetched source sets it apart in sound):
    # https://www.soundonsound.com/techniques/synthesizing-cowbells-claves (the TR-808's clave:
    # "It's a Bridged-T oscillator kicked by a trigger and allowed to decay without further
    # interference. The signal is not even modified before being passed to the output."): one
    # decaying tone, as the claves build is; no source gives its frequency
    CatalogEntry(
        'electronic clave',
        'Electronic clave (Roland TR-808)',
        Family.ELECTRONIC,
        None,
        None,
        sounds_like='claves',
    ),
    # Sound-alike of the electronic kick (no fetched source sets it apart in sound):
    # https://www.manualslib.com/manual/1294765/Roland-Tr-808.html?page=6 (the TR-808 service
    # notes, toms and congas: "This sound generator is composed of a multi-feedback, bridged
    # T-network including IC5 as an active element."; "As the resonance is damped, its frequency
    # is lowered by the effect of increasing diodes' internal resistance."): a tone falling in
    # pitch as it decays, with no noise; no source gives the conga's frequency
    CatalogEntry(
        'electronic conga',
        'Electronic conga (Roland TR-808)',
        Family.ELECTRONIC,
        None,
        None,
        sounds_like='electronic kick',
    ),
    # Sound-alike of the cowbell (no fetched source sets it apart in sound):
    # https://hn.jakechampion.name/reader/http://outputchannel.com/post/tr-808-cowbell-web-audio
    # ("All you need is two square waves at specific frequencies of 800 and 540Hz."): the cowbell
    # is built as those two squares ringing together
    CatalogEntry(
        'electronic cowbell',
        'Electronic cowbell (Roland TR-808)',
        Family.ELECTRONIC,
        None,
        None,
        sounds_like='cowbell',
    ),
    # Sound-alike of the maracas (no fetched source sets it apart in sound):
    # https://www.manualslib.com/manual/1294765/Roland-Tr-808.html?page=6 (the TR-808 service
    # notes, Maracas: "White noise is gated by Q65 and supplied to the same buffer IC19 as for the
    # CP sound generator through the filter Q68."): a short filtered noise burst, as the maracas
    # build is; the notes give no filter kind or cutoff
    CatalogEntry(
        'electronic maracas',
        'Electronic maracas (Roland TR-808)',
        Family.ELECTRONIC,
        None,
        None,
        sounds_like='maracas',
    ),
    # Sound-alike of the electronic kick (no fetched source sets it apart in sound):
    # https://www.manualslib.com/manual/1294765/Roland-Tr-808.html?page=6 (the TR-808 service
    # notes, toms: "As the resonance is damped, its frequency is lowered by the effect of
    # increasing diodes' internal resistance."; "Pink noise with a slightly longer decay time is
    # mixed for Low Tom Tom to provide artificial reveberation."): a tone falling in pitch, the
    # low tom's noise a reverberation on one size only; no source gives the toms' frequencies
    CatalogEntry(
        'electronic tom',
        'Electronic tom (Roland TR-808)',
        Family.ELECTRONIC,
        None,
        None,
        sounds_like='electronic kick',
    ),
    # Sound-alike of the chip square (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/PC_speaker ("The PC speaker is normally meant to reproduce a
    # square wave via only 2 levels of output"; "The clock rate of the PC's programmable interval
    # timer which drives the speaker is fixed at 1,193,180 Hz"). Range:
    # https://en.wikipedia.org/wiki/Intel_8253 ("three 16-bit counters"; mode 3: "Thus, the period
    # will be n counts"): the lowest, 1193180 / 65536 = 18.2 Hz, is below A0, so clipped to A0;
    # the highest, 1193180 / 2 = 596.6 kHz, is clipped to C8
    CatalogEntry(
        'pc speaker',
        'IBM PC speaker',
        Family.ELECTRONIC,
        'A0',
        'C8',
        sounds_like='chip square',
        tags=frozenset({Tag.CHIP}),
    ),
    # Sound-alike of the saw lead (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/MOS_Technology_6581 ("four basic waveform types selectable:
    # triangle, sawtooth, pulse (with variable duty cycle), and pseudorandom noise"; "Each voice
    # may be routed into an analog filter"): the plain sawtooth. Range, the same page ("0.0625-
    # 4095.9375 Hz range on a 1 MHz clock", the en dash written as a hyphen): 0.0625 Hz is
    # clipped to A0; B7 (3951.07 Hz) is the highest note at or below 4095.9375 Hz (C8 is 4186.01
    # Hz)
    CatalogEntry(
        'sid sawtooth',
        'MOS Technology SID sawtooth (6581)',
        Family.ELECTRONIC,
        'A0',
        'B7',
        sounds_like='saw lead',
        tags=frozenset({Tag.CHIP}),
    ),
    # Sound-alike of the chip square (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Texas_Instruments_SN76489 ("3 square wave tone generators";
    # "Or typically 108 Hz to 111.6 kHz, with an NTSC color burst (~3.58 MHz) clock input"): A2
    # (110.0 Hz) is the lowest note at or above 108 Hz (G#2 is 103.8 Hz), and 111.6 kHz is clipped
    # to C8. The page gives the chip's hertz at its typical clock, not one machine's (the
    # controller's ruling, listed for the owner)
    CatalogEntry(
        'sn76489',
        'Texas Instruments SN76489',
        Family.ELECTRONIC,
        'A2',
        'C8',
        sounds_like='chip square',
        tags=frozenset({Tag.CHIP}),
    ),
    # Sound-alike of the electronic kick (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Pollard_Syndrum ("Although the Syndrum was capable of many
    # different sounds, the one favored by most recording artists was a sine wave that
    # pitch-bends down"): the electronic kick's gliding sine; no source gives its frequencies
    CatalogEntry(
        'syndrum',
        'Pollard Syndrum',
        Family.ELECTRONIC,
        None,
        None,
        sounds_like='electronic kick',
    ),
)
