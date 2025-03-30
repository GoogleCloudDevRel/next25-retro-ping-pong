import pygame
from config import Screen
from drawing import Assets


class Paddle:
    def __init__(self, x=0, y=0, speed=10):
        self.x = x
        self.y = y
        self.speed = speed
        self.y_vel = 0
        assets = Assets()

        self.images = assets.paddle_images
        self.index = 0
        self.image = self.images[self.index]
        self.rect = pygame.Rect(0, 0, 10, 100)  # The actual paddle size
        self.rect.center = (self.x, self.y)

    def init_location(self, x, y):
        self.x = x
        self.y = y
        self.rect.center = (int(self.x), int(self.y))

    def move_up(self):
        self.y_vel = -self.speed

    def move_down(self):
        self.y_vel = self.speed

    def stop_moving(self):
        self.y_vel = 0

    def update_position(self):
        top_border = self.rect.height // 2
        bottom_border = Screen.GAME_PANE_HEIGHT - self.rect.height // 2
        paddle_next_pos = self.y + self.y_vel

        if top_border < paddle_next_pos < bottom_border:
            self.y += self.y_vel
        elif paddle_next_pos <= top_border:
            self.y = top_border
        elif paddle_next_pos >= bottom_border:
            self.y = bottom_border
        self.rect.centery = int(self.y)

    def draw(self, canvas):
        blit_pos = (self.rect.centerx - self.image.get_width() // 2,
                    self.rect.centery - self.image.get_height() // 2)
        canvas.blit(self.image, blit_pos)

    def get_rect(self):
        return self.rect

    def next_image(self):
        self.index = (self.index + 1) % len(self.images)
        self.image = self.images[self.index]
