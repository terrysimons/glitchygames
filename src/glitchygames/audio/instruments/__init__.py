"""The instrument catalog: ready-made instruments for every family, with their ranges.

Usage:
    from glitchygames.audio import instruments

    violin = instruments.get('violin')                  # an ordinary Instrument
    sound = self.scene_manager.audio.sound(violin, notes='G3:0.5 D4:0.5 A4:1')
    instruments.entry('alto saxophone').playing_range   # (Note('Db3'), Note('Ab5'))
    instruments.names(family=instruments.Family.BRASS)  # every brass instrument's name
    instruments.names(tag=instruments.Tag.MECHANICAL)   # every entry carrying a tag
    instruments.names(tag=instruments.Tag.CHIP)         # every sound-chip voice
    instruments.get('slapstick')                        # an alias: the same instrument as 'whip'

Every entry is an ``Instrument`` made from the engine's own parts (waves from overtone series,
noise, layered sources with their own envelopes and pitches, filters and drive; see
``timbres``), so it plays, caches and renders offline like any other. The voices come in every
range (soprano, mezzo-soprano, alto, treble, countertenor, tenor, baritone, bass, basso
profundo) on five vowels, and the families' sizes have their variants (sopranino to contrabass
saxophones and recorders, alto to contrabass trombones, piccolo to contrabass flutes, and so
on). They are synthesized approximations: there are no recorded samples, vibrato or moving
filters in the engine yet, so sustained tones are steady and a vowel is truest mid-range.

Three families hold the instruments that are neither struck bars nor blown: plucked idiophones
(``kalimba``, ``mbira``, ``music box``, ``sansula``), friction instruments (``glass harmonica``,
``glass harp``, ``terpodion``) and noise makers (``whip crack``, ``diaphone``, ``air horn``,
``vehicle horn``, ``party horn``). A ``Tag`` marks a quality across families (``Tag.MECHANICAL``,
on the ``music box``; ``Tag.CHIP``, on the sound-chip voices such as ``chip square``, ``sn76489``
and ``nes triangle``), so ``names(tag=...)`` finds those wherever they sound.

Electromechanical takes the electric pianos (``tine electric piano``, ``reed electric
piano``), the ``clavinet`` and the ``tonewheel organ ...`` registrations from keyboards and
organs, and adds the ``hohner pianet``. Sound effects is a new family (``thunder sheet``,
``rain machine``, ``ocean drum``, ``cannon``, ``coconut shells``, ``door slam``), each effect
playable as a note.

Electronic (26 entries) holds the family's builds in ``electronic.py`` (``theremin``, ``ondes
martenot``, the synth patches such as ``saw lead`` and ``synth pad``, the chiptune voices such as
``chip square`` and ``nes triangle``) and its sound-alikes in ``electronic_sound_alikes.py``: sound
chips (``sn76489``, ``ay 3 8910``, ``pc speaker``, ``sid sawtooth``) and drum-machine voices
(``electronic tom``, ``electronic cowbell``, ``syndrum``). It is pitched, but the drum-machine
voices are unpitched, as the drums' are, and a chip's range is its hertz at a sourced clock (from a
chip page such as Wikipedia's or NESdev's, or a datasheet's formula), rounded inward to notes.

Drums and percussion (237 entries) holds the family's builds in ``drums.py`` (hand drums such as
``daf``, ``dhol``, ``kendang`` and ``mridangam``, snares, gongs such as ``agung`` and ``jing``,
cymbals, shakers, clappers, ``garamut``, ``washboard``) and its sound-alikes in
``drum_sound_alikes.py``. A sound-alike is a verified instrument no source sets apart in sound
from an existing entry (``bamboula`` and ``conga``): its own entry, listed under its own name,
with ``CatalogEntry.sounds_like`` naming the parent whose build it shares.
``CatalogEntry.sound_changes`` (empty so far) would let one differ by a sourced trait.

Plucked strings (92 entries) holds the family's builds in ``plucked_strings.py`` (guitars,
basses, ukuleles, banjos, mandolins, lutes such as ``angelique``, zithers such as ``qanun``,
``tar``, ``ruan`` and ``chapman stick``) and its sound-alikes in ``plucked_sound_alikes.py``
(``requinto guitar`` and ``classical guitar``, ``liuqin`` and ``pipa``). The family is pitched,
so a pitched sound-alike gives its own sourced range, a requinto's span being its own: it
shares its parent's build, not its range.

Bowed strings (29 entries) holds the family's builds in ``bowed_strings.py`` (violin to double
bass, sections, pizzicato, viols, ``erhu``, ``hurdy gurdy``) and its sound-alikes in
``bowed_sound_alikes.py`` (``viola pomposa`` and ``viola``, ``bowed psaltery`` and ``violin``). The
family is pitched, so each sound-alike gives its own sourced range. Instruments that need
sympathetic strings or a buzzing bridge wait, and ``sarangi``, ``hardanger fiddle``, ``viola d
amore``, ``nyckelharpa`` and ``hurdy gurdy`` stay as the approximations they were, never a parent.

Voices (56 entries) and choirs (13 entries) hold their builds in ``voices.py`` (``soprano ah`` to
``basso profundo hum``, ``whistling``, ``choir soprano ah``, ``childrens choir``), which shares one
formant table between the two families, and their sound-alikes in ``voice_sound_alikes.py``, one
table per family (``basso buffo ah``, a sound-alike of ``bass ah``; the choirs' table is empty).
An entry is a voice type, a voice device or a choir part: singing techniques, styles and genres
are not instruments. A voice type that no source sets apart in sound is a sound-alike of the type
its source names, on ``ah`` alone, and it gives its own sourced range (stated, never hedged or
extreme). Everything that needs moving formants (throat singing, ``yodel``), a vibrato, or a
buzzing membrane (``kazoo``, ``swazzle``) waits, and ``contralto`` and ``boy soprano`` are aliases.

Tuned percussion (36 entries) holds the family's builds in ``percussion.py`` (glockenspiel,
xylophone, marimba, vibraphone, bells, steel pans, timpani, gamelan, ``boomwhackers`` and
``gangsa``) and its sound-alikes in ``tuned_sound_alikes.py`` (``alto xylophone`` and
``xylophone``, ``kantilan`` and ``gangsa``). It is pitched too: each sound-alike gives its own
sourced range.

``instruments.ALIASES`` (read-only, as ``CATALOG`` is) maps each other name (``slapstick``) to
its catalog name (``whip``): another name for the same instrument, where a sound-alike is a
different instrument. ``entry`` and ``get`` resolve aliases, while ``names`` and ``entries``
list catalog names only.

``instruments.get`` builds each instrument once per process and returns the same (immutable)
instrument afterwards. A sound-alike is built under its own name: its instrument is equal by
value to its parent's, not the same object.
"""

from glitchygames.audio.instruments.catalog import CatalogEntry, Family, Tag
from glitchygames.audio.instruments.registry import (
    ALIAS_TABLE as ALIASES,
)
from glitchygames.audio.instruments.registry import (
    CATALOG,
    entries,
    entry,
    families,
    get,
    names,
)

__all__ = [
    'ALIASES',
    'CATALOG',
    'CatalogEntry',
    'Family',
    'Tag',
    'entries',
    'entry',
    'families',
    'get',
    'names',
]
