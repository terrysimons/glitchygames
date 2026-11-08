"""Other names for catalog instruments (``instruments.entry`` and ``get`` resolve them).

Each key is an alias, lower-case words separated by single spaces, and each value is the catalog
name it stands for. ``registry.aliases_from`` checks the table when the catalog is assembled: an
alias may not be a catalog name, and its target must be one.
"""

from typing import Final

ALIASES: Final[dict[str, str]] = {
    # https://en.wikipedia.org/wiki/Slapstick_(instrument): "a whip or slapstick is a clapper"
    'slapstick': 'whip',
    # https://en.wikipedia.org/wiki/Mbira: the mbira is "also known as kalimba and zanza"
    'zanza': 'mbira',
    # https://en.wikipedia.org/wiki/Music_box: pins "on a revolving cylinder or disc" pluck "the
    # tuned teeth ... of a steel comb"; the catalog music box is this cylinder comb
    'cylinder music box': 'music box',
    # https://en.wikipedia.org/wiki/Polyphon: star wheels pluck the same kind of comb; no range
    'disc music box': 'music box',
    # https://en.wikipedia.org/wiki/Wurlitzer_electric_piano: sound by "striking a metal reed with
    # a felt hammer", read by an electrostatic pickup: the catalog reed electric piano (the
    # audit's spelling is "electronic")
    'wurlitzer electronic piano': 'reed electric piano',
    # https://en.wikipedia.org/wiki/Hohner_Clavinet: Hohner's instrument, "most models have 60
    # keys ranging from F1 to E6", the catalog clavinet's range
    'hohner clavinet': 'clavinet',
    # https://api.vam.ac.uk/v2/object/O74191: the object history says "This rain box" and the brief
    # description calls it a "rain machine": the same device
    'rain box': 'rain machine',
    # https://theatrecrafts.com/pages/home/topics/sound/sound-effects-for-the-stage/: "the classic
    # coconut halves for horses hooves"
    'horse hooves': 'coconut shells',
}
