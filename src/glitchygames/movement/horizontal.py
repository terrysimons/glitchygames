"""
Horizontal:
Adds movement functions along the horizontal (X) axis to a game object
"""


class Horizontal:

    def __init__(self, speed):

        self.speed = speed
        self.current_speed = self.speed.x

    def _change_speed(self, value):
        self.current_speed = value

    def left(self):
        self._change_speed(-self.speed.x)

    def right(self):
        self._change_speed(self.speed.x)

    def stop(self):
        self._change_speed(0)
