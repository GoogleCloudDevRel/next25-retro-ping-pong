import random
import pygame
from config import Color, Screen


class Ball:
    def __init__(
        self, x=Screen.WIDTH // 2,
        y=Screen.GAME_PANE_START_Y + Screen.GAME_PANE_HEIGHT // 2, radius=15,
        color=Color.RED, x_vel=8, y_vel=6, multiplier=1.15, direction=1
    ):
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
        self.x_vel = x_vel * direction
        self.y_vel = y_vel if random.randrange(0, 2) == 0 else -x_vel
        self.multiplier = multiplier

    def move(self):
        self.x += self.x_vel
        self.y += self.y_vel

    def bounce_y(self):
        self.y_vel = -self.y_vel

    def bounce_x(self):
        self.x_vel = -self.x_vel

    def accelerate(self):
        self.x_vel *= self.multiplier
        self.y_vel *= self.multiplier

    def draw(self, canvas):
        pygame.draw.circle(
            canvas,
            self.color,
            [int(self.x), int(self.y)],
            self.radius,
            0
        )

    def reset_position(self, x, y):
        self.x = x
        self.y = y

    def reset_velocity(self, x_vel, y_vel):
        self.x_vel = x_vel
        self.y_vel = y_vel

    def get_rect(self):
        return pygame.Rect(
            self.x - self.radius,
            self.y - self.radius,
            self.radius * 2,
            self.radius * 2
        )
