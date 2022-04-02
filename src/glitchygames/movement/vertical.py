"""
Vertical:
Adds movement functions along the vertical (Y) axis to a game object
"""


class Vertical:

    def __init__(self, sprite, speed_value):
        self.sprite = sprite
        self.speed = speed_value

    def up(self):
        self.sprite.speed.y = -self.speed
        self.sprite.dirty = 1

    def down(self):
        self.sprite.speed.y = self.speed
        self.sprite.dirty = 1

    def stop(self):
        self.sprite.speed.y = 0
        self.sprite.dirty = 1

    def detect_edge(self):
        if self.sprite.rect.bottom + self.sprite.speed.y > self.sprite.screen_rect.bottom:
            self.sprite.rect.y = self.sprite.screen_rect.bottom - self.sprite.height
            self.stop()
        elif self.sprite.rect.top + self.sprite.speed.y < self.sprite.screen_rect.top:
            self.sprite.rect.y = 0
            self.stop()
        else:
            self.sprite.rect.y += self.sprite.speed.y
        self.sprite.dirty = 1
