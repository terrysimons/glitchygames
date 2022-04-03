"""
Vertical:
Adds movement functions along the vertical (Y) axis to a game object
"""


class Vertical:

    def __init__(self, speed):
        self.speed = speed
        self.current_speed = self.speed.y

    def _change_speed(self, value):
        self.current_speed = value

    def up(self):
        self._change_speed(-self.speed.y)

    def down(self):
        self._change_speed(self.speed.y)

    def stop(self):
        self._change_speed(0)
