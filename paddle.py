import pygame
from config import Color, Screen


class Paddle:
    def __init__(
        self, x=0, y=0, width=8, height=80,
        color=Color.GREEN, speed=15
    ):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.half_width = width // 2
        self.half_height = height // 2
        self.color = color
        self.speed = speed
        self.y_vel = 0

    def init_location(self, x, y):
        self.x = x
        self.y = y

    def move_up(self):
        self.y_vel = -self.speed

    def move_down(self):
        self.y_vel = self.speed

    def stop_moving(self):
        self.y_vel = 0

    def update_position(self):
        top_border = Screen.GAME_PANE_START_Y + self.half_height
        bottom_border = Screen.GAME_PANE_START_Y + Screen.GAME_PANE_HEIGHT - self.half_height
        paddle_next_pos = self.y + self.y_vel

        if top_border < paddle_next_pos < bottom_border:
            self.y += self.y_vel
        elif paddle_next_pos <= top_border:
            self.y = top_border
        elif paddle_next_pos >= bottom_border:
            self.y = bottom_border

    def draw(self, canvas):
        pygame.draw.polygon(
            canvas,
            self.color,
            [
                [self.x - self.half_width, self.y - self.half_height],
                [self.x - self.half_width, self.y + self.half_height],
                [self.x + self.half_width, self.y + self.half_height],
                [self.x + self.half_width, self.y - self.half_height],
            ],
            0
        )

    def get_rect(self):
        return pygame.Rect(
            self.x - self.half_width,
            self.y - self.half_height,
            self.width,
            self.height
        )
