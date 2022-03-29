import pygame
from glitchygames.color import WHITE
from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene

# Adapted from:
# https://github.com/ChristianD37/YoutubeTutorials/tree/master/Framerate%20Independence


class Game(Scene):
    # Set your game name/version here.
    NAME = "Delta Time Demo"
    VERSION = "1.0"

    def __init__(self, options, groups=pygame.sprite.LayeredDirty()):
        super().__init__(options=options, groups=groups)
        self.font = pygame.font.SysFont('Calibri', 40)
        self.rect_pos = 0
        self.velocity = 5
        self.record = 0
        self.passed = False
        self.start = False

    @classmethod
    def args(cls, parser):
        parser.add_argument('-v', '--version',
                            action='store_true',
                            help='print the game version and exit')

        parser.add_argument('-b', '--balls',
                            type=int,
                            help='the number of balls to start with',
                            default=1)

    # def setup(self):
    #     self.target_fps = 30

    def dt_tick(self, dt):
        # self.dt = dt
        # self.dt_timer += self.dt

        # for sprite in self.all_sprites:
        #     sprite.dt_tick(dt)

        if self.start:
            self.dt_timer += dt
            self.rect_pos += self.velocity * dt

    def update(self):
        self.screen.fill((0, 0, 0))

        if self.rect_pos > self.screen_width and not self.passed:
            self.record = self.dt_timer / 100
            self.passed = True

        countdown = self.font.render("Time: " + str(round(self.dt_timer / 100, 5)), False, (255, 255, 255))
        fps_text = self.font.render(
            f"FPS: {str(round(self.fps, 2))}", False, (255, 255, 255)
        )

        self.screen.blit(countdown, (0, 0))
        self.screen.blit(fps_text, (0, 50))

        pygame.draw.rect(self.screen, WHITE, (self.rect_pos, (self.screen_height / 2) + 30, 40, 40))
        if self.record:
            record_text = self.font.render(
                f"Time: {str(round(self.record, 5))}", False, (255, 255, 255)
            )

            self.screen.blit(record_text, (self.screen_width / 4, self.screen_height / 2))

    def on_key_down_event(self, event):
        pressed_keys = pygame.key.get_pressed()

        if pressed_keys[pygame.K_SPACE]:
            self.start = True


def main():
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
