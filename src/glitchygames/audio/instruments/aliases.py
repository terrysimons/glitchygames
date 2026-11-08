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
}
