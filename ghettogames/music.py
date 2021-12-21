import logging

from ghettogames.events import ResourceManager


log = logging.getLogger('game.music')
log.addHandler(logging.NullHandler())


class MusicManager(ResourceManager):
    def __init__(self, game=None):  # noqa: W0235
        """
        Manage music.

        MusicManager manages music.

        Args:
        ----
        game -

        """
        super().__init__(game=game)

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Music Options')  # noqa: W0612

        return parser