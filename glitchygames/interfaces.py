class SpriteInterface:
    def update_nested_sprites(self):
        pass

    def update(self):
        pass

    def render(self, screen):
        pass

class SceneInterface:
    def switch_to_scene(self, next_scene):
        pass

    def terminate(self):
        pass
