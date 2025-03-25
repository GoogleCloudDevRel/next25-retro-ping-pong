import random
import pygame
from config import Screen


class Ball:
    def __init__(
        self, x=Screen.WIDTH // 2, y=Screen.GAME_PANE_HEIGHT // 2, radius=15,
        x_vel=7, y_vel=4, multiplier=1.12, direction=1
    ):
        self.x = x
        self.y = y
        self.radius = radius
        self.x_vel = x_vel * direction
        self.y_vel = y_vel if random.randrange(0, 2) == 0 else -x_vel
        self.multiplier = multiplier

        self.image = pygame.image.load("assets/ball.png")
        self.rect = pygame.Rect(0, 0, 15, 15)
        self.rect.center = (self.x, self.y)

    def move(self):
        self.x += self.x_vel
        self.y += self.y_vel
        self.rect.center = (int(self.x), int(self.y))

    def bounce_y(self):
        self.y_vel = -self.y_vel

    def bounce_x(self):
        self.x_vel = -self.x_vel

    def accelerate(self):
        self.x_vel *= self.multiplier
        self.y_vel *= self.multiplier

    def draw(self, canvas):
        blit_pos = (
            self.rect.centerx - self.image.get_width() // 2,
            self.rect.centery - self.image.get_height() // 2
        )
        canvas.blit(self.image, blit_pos)

    def reset_position(self, x, y):
        self.x = x
        self.y = y
        self.rect.center = (int(self.x), int(self.y))

    def reset_velocity(self, x_vel, y_vel):
        self.x_vel = x_vel
        self.y_vel = y_vel

    def get_rect(self):
        return self.rect
