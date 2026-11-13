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
saxophones, sopranino to subcontrabass recorders, alto to contrabass trombones, piccolo to
contrabass flutes, and so on). They are synthesized approximations: there are no recorded
samples, vibrato or moving filters in the engine yet, so sustained tones are steady and a vowel
is truest mid-range.

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

Flutes (33 entries) hold their builds in ``flutes.py`` (``piccolo`` to ``contrabass flute``,
``recorder`` sizes, ``tin whistle``, ``shakuhachi``, ``pan flute``, ``ocarina``) and their
sound-alikes in ``flute_sound_alikes.py`` (``csakan`` and ``soprano recorder``, ``subcontrabass
recorder`` and ``contrabass recorder``, ``ryuteki`` and ``bansuri``). The family is pitched, so each
sound-alike gives its own sourced range (sounding, stated, never hedged or extreme). A flute whose
sound is a moving one (``slide whistle``, ``pea whistle``), a buzzing membrane (``qudi``,
``daegeum``) or a voice (``tsuur``) waits, and ``dizi`` stays as the approximation it was, never a
parent. ``penny whistle``, ``syrinx`` and three more names are aliases.

Voices (56 entries) and choirs (13 entries) hold their builds in ``voices.py`` (``soprano ah`` to
``basso profundo hum``, ``whistling``, ``choir soprano ah``, ``childrens choir``), which shares one
formant table between the two families, and their sound-alikes in ``voice_sound_alikes.py``, one
table per family (``basso buffo ah``, a sound-alike of ``bass ah``; the choirs' table is empty).
An entry is a voice type, a voice device or a choir part: singing techniques, styles and genres
are not instruments. A voice type that no source sets apart in sound is a sound-alike of the type
its source names, on ``ah`` alone, and it gives its own sourced range (stated, never hedged or
extreme). Everything that needs moving formants (throat singing, ``yodel``), a vibrato, or a
buzzing membrane (``kazoo``, ``swazzle``) waits, and ``contralto`` and ``boy soprano`` are aliases.

Brass (44 entries) holds the family's builds in ``brass.py`` (``piccolo trumpet`` to
``tuba``, the trombones, the mutes, ``natural horn``, ``alphorn``, ``serpent``) and its
sound-alikes in ``brass_sound_alikes.py`` (``bass wagner tuba`` and ``wagner tuba``, ``soprano
trombone`` and ``trumpet``). The family is pitched, so each sound-alike gives its own sourced
range (sounding, stated, never hedged or extreme: a written range counts only with the
transposition its source states). A brass instrument whose sound is a moving one (``bazooka``,
``didjeribone``) or a buzzing membrane (``sudrophone``) waits, as does ``subcontrabass tuba``
(sub-audio fundamentals), or one that needs a build of its own (``tenor cornett``, ``vienna
horn``), and ``didgeridoo`` stays as the approximation it was,
never a parent, though it has aliases (``yidaki``, ``mako``). The shells are aliases of ``conch``
only where a source presents the name as the conch itself.

Double reeds (25 entries) hold the family's builds in ``double_reeds.py`` (``oboe``, ``english
horn``, ``bassoon``, ``contrabassoon``, ``heckelphone``, ``sarrusophone``, the shawms, the
crumhorns, ``suona``, ``zurna``, ``duduk``) and their sound-alikes in
``double_reed_sound_alikes.py`` (``contraforte`` and ``contrabassoon``, ``piccolo heckelphone``
and ``heckelphone``). ``winds.py`` keeps the saxophones and free
reeds. The family is pitched, so each sound-alike gives its own sourced range
(sounding, stated, never hedged, "comfortable" or "theoretical"). A double reed whose range no
source states waits (most of them, among them the other sarrusophone sizes, the folk shawms and
``aulos``; ``balaban`` waits for a build that models its cylindrical bore), and ``piri`` stays as
the approximation it was, never a parent. ``cor anglais``,
``fagott``, ``bombard`` and eight more names are aliases.

Bagpipes (9 entries) hold the family's builds in ``bagpipes.py`` (``highland bagpipe``,
``uilleann pipes``, ``border pipes``, ``galician gaita``, ``bulgarian gaida``, ``musette de cour``
and ``sackpipa``, the family's first cylindrical chanter) and their sound-alikes in
``bagpipe_sound_alikes.py`` (none yet). ``winds.py`` keeps the saxophones and free
reeds. A bagpipe's drones are fixed pitches inside its build, so a sound-alike in another tuning
carries its own drones as ``sound_changes``. The family is pitched, so a sound-alike gives its own
sourced range (sounding, stated, never hedged) and sourced drones. A bagpipe whose range no source
states waits (nearly all of them), and ``scottish smallpipes`` joins ``piri`` as an approximation
(a cylindrical bore the build lacks), never a parent. ``irish pipes``, ``lowland pipes``, ``half
long pipes`` and ``gaita galega`` are aliases.

Clarinets (10 entries) hold the family's builds in ``clarinets.py`` (``e flat clarinet``,
``clarinet``, ``a clarinet``, ``basset horn``, the alto to contrabass clarinets and
``chalumeau``) and their sound-alikes in ``clarinet_sound_alikes.py`` (``c clarinet``, of
``clarinet``). ``winds.py`` keeps the saxophones and free reeds. A clarinet is a single reed on a
cylindrical bore (a conical one is a saxophone), which favours the odd harmonics, so a clarinet of
another key or size is a sound-alike of the catalog clarinet its own source relates it to, or
else of the catalog clarinet (``chalumeau`` excluded) whose lowest note is nearest its own, and
gives its own sourced range (sounding, a written range only with its stated transposition). No
drone or detuned double clarinet shipped, so no clarinet carries drones. A clarinet whose range
no source states waits (34 names), the tenor and contrabass ``birbyne`` wait for a sourced reed
and bore (2 names) and 4 names wait for their target (40 waits in all).

Organs (19 entries) hold the family's builds in ``organs.py`` (the ``pipe organ`` stops and
``plenum``, ``positive organ``, ``theatre organ``, ``calliope``, and the batch's ``stopped
diapason``, ``cornet organ`` and ``organ clarinet``) and their sound-alikes in
``organ_sound_alikes.py`` (``salicional``, ``voix celeste``, ``organ oboe``, ``organ krummhorn``,
``organ tuba``, ``posthorn`` and ``bourdon``). ``keyboards.py`` keeps the keyboards and
``electromechanical.py`` the electromechanical instruments. A stop sounds at its footage against its
keys (a 16' an octave below, a 4' an octave above), and a sound-alike stop at another footage than
its parent carries it as ``sound_changes`` (``bourdon``, the stopped diapason at 16'). A stop's
range is its keys at 8' pitch. A stop whose footage no source gives, whose sounding span passes C8
(the 2' stops and high mutations), whose mixture breaks back or whose tone needs a tremulant waits
(16 names are held back for such a reason), and ``open diapason``, ``organ trompette``, ``air
calliope`` and ``calliaphone`` are aliases. No self-playing organ shipped (each waits for a sourced
range), so ``Tag.MECHANICAL`` is still only on the ``music box``.

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
