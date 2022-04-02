"""
Horizontal:
Adds movement functions along the horizontal (X) axis to a game object
"""


class Horizontal:

    def __init__(self, sprite, speed_value):
        self.sprite = sprite
        self.speed = speed_value

    def left(self):
        self.sprite.speed.x = -self.speed
        self.sprite.dirty = 1

    def right(self):
        self.sprite.speed.x = self.speed
        self.sprite.dirty = 1

    def stop(self):
        self.sprite.speed.x = 0
        self.sprite.dirty = 1

    def detect_edge(self):
        if self.sprite.rect.right + self.sprite.speed.x > self.sprite.screen_rect.right:
            self.sprite.rect.x = self.sprite.screen_rect.right - self.sprite.width
            self.stop()
        elif self.sprite.rect.left + self.sprite.speed.x < self.sprite.screen_rect.left:
            self.sprite.rect.x = 0
            self.stop()
        else:
            self.sprite.rect.x += self.sprite.speed.x
        self.sprite.dirty = 1
