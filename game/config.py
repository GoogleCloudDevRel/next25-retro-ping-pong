from enum import Enum
import pygame

pygame.init()
CLOCK = pygame.time.Clock()


class Screen:
    WIDTH = 960
    HEIGHT = 540
    BOTTOM_PANE_HEIGHT = 85
    GAME_PANE_HEIGHT = HEIGHT - BOTTOM_PANE_HEIGHT
    FULLSCREEN = True


class Game:
    FPS = 60
    GAME_OVER_SCORE = 3
    TITLE = "Paddle Bounce"
    FONT = pygame.font.Font(pygame.font.get_default_font(), 40)
    p1 = "Player 1"
    p2 = "Player 2"
    BALL_VELOCITY_X = 4
    BALL_VELOCITY_Y = 3
    BALL_SPEED_MULTIPLIER = 1.12


class Color:
    WHITE = (255, 255, 255)
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLACK = (0, 0, 0)
    GOOGLE_BLUE = (66, 103, 210)
    GOOGLE_GREEN = (52, 168, 83)
    GOOGLE_RED = (234, 67, 53)
    GOOGLE_YELLOW = (251, 188, 4)
    arr = [GOOGLE_BLUE, GOOGLE_GREEN, GOOGLE_RED, GOOGLE_YELLOW]


class State(Enum):
    SPLASH = 0
    SELECT = 1
    GAME = 2
    PAUSE = 3
    RESULT = 4
