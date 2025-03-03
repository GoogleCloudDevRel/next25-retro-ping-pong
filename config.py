from enum import Enum
import pygame

pygame.init()
CLOCK = pygame.time.Clock()


class Screen:
    WIDTH = 800
    HEIGHT = 600
    SCORE_PANE_HEIGHT = 100
    LOG_PANE_HEIGHT = 100
    GAME_PANE_HEIGHT = HEIGHT - SCORE_PANE_HEIGHT - LOG_PANE_HEIGHT
    GAME_PANE_START_Y = SCORE_PANE_HEIGHT
    LOG_PANE_START_Y = SCORE_PANE_HEIGHT + GAME_PANE_HEIGHT


class Game:
    FPS = 24
    GAME_OVER_SCORE = 5
    TITLE = "Paddle Bounce"
    FONT = "Comic Sans MS"
    p1 = "Player 1"
    p2 = "Player 2"


class Color:
    WHITE = (255, 255, 255)
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLACK = (0, 0, 0)


class State(Enum):
    SPLASH = 0
    SELECT = 1
    GAME = 2
    PAUSE = 3
    RESULT = 4


WINDOW = pygame.display.set_mode((Screen.WIDTH, Screen.HEIGHT), 0, 32)
pygame.display.set_caption('Paddle Bounce')
