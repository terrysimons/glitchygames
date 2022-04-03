class Speed:
    def __init__(self, x=0, y=0, increment=0.2):
        self.x = x
        self.y = y
        self.increment = increment

    def speed_up(self):
        self.speed_up_horizontal()
        self.speed_up_vertical()

    def speed_up_horizontal(self):
        self.x += self.increment if self.x >= 0 else self.increment * -1

    def speed_up_vertical(self):
        self.y += self.increment if self.y >= 0 else self.increment * -1
