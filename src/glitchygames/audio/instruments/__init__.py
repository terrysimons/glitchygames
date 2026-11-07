"""The instrument catalog: ready-made instruments for every family, with their ranges.

Usage:
    from glitchygames.audio import instruments

    violin = instruments.get('violin')                  # an ordinary Instrument
    sound = self.scene_manager.audio.sound(violin, notes='G3:0.5 D4:0.5 A4:1')
    instruments.entry('alto saxophone').playing_range   # (Note('Db3'), Note('Ab5'))
    instruments.names(family=instruments.Family.BRASS)  # every brass instrument's name
    instruments.names(tag=instruments.Tag.MECHANICAL)   # every entry carrying a tag

Every entry is an ``Instrument`` made from the engine's own parts (waves from overtone series,
noise, layered sources with their own envelopes and pitches, filters and drive; see
``timbres``), so it plays, caches and renders offline like any other. The voices come in every
range (soprano, mezzo-soprano, alto, treble, countertenor, tenor, baritone, bass, basso
profundo) on five vowels, and the families' sizes have their variants (sopranino to contrabass
saxophones and recorders, alto to contrabass trombones, piccolo to contrabass flutes, and so
on). They are synthesized approximations: there are no recorded samples, vibrato or moving
filters in the engine yet, so sustained tones are steady and a vowel is truest mid-range.

``instruments.get`` builds each instrument once per process and returns the same (immutable)
instrument afterwards.
"""

from glitchygames.audio.instruments.catalog import CatalogEntry, Family, Tag
from glitchygames.audio.instruments.registry import (
    CATALOG,
    entries,
    entry,
    families,
    get,
    names,
)

__all__ = [
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
