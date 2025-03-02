import random
import pygame
from config import State, Screen, Game
from ball import Ball
from paddle import Paddle


class GameManager:
    def __init__(self):
        self.ball = None
        self.paddle1 = None
        self.paddle2 = None
        self.left_score = 0
        self.right_score = 0
        self.last_scorer = 0
        self.state = State.SPLASH

    def init_game(self):
        """Initializes game state variables and game objects."""
        self.paddle1 = Paddle()
        self.paddle2 = Paddle()
        paddle1_x = self.paddle1.half_width - 1
        paddle2_x = Screen.WIDTH - self.paddle2.half_width + 1
        paddle_y = Screen.GAME_PANE_START_Y + Screen.GAME_PANE_HEIGHT // 2
        self.paddle1.init_location(paddle1_x, paddle_y)
        self.paddle2.init_location(paddle2_x, paddle_y)
        self.ball = Ball(direction=1) if random.randrange(0, 2) == 0 else Ball(direction=-1)
        self.left_score = 0
        self.right_score = 0
        self.state = State.GAME

    def update_paddles(self):
        self.paddle1.update_position()
        self.paddle2.update_position()

    def update_ball(self):
        def gutter_check(ball, paddle):
            if ball.x <= ball.radius + paddle.width:
                return "Left"
            elif ball.x >= Screen.WIDTH - ball.radius - paddle.width:
                return "Right"
            return False

        def collide_check(obj1: pygame.rect, obj2: pygame.rect):
            return obj1.get_rect().colliderect(obj2.get_rect())

        top_border = self.ball.radius + Screen.GAME_PANE_START_Y
        bottom_border = Screen.GAME_PANE_START_Y + Screen.GAME_PANE_HEIGHT - self.ball.radius

        self.ball.move()
        if self.ball.y <= top_border or self.ball.y >= bottom_border:
            self.ball.bounce_y()

        gutter_side = gutter_check(self.ball, self.paddle1)
        if not gutter_side:
            return

        p1_collide = collide_check(self.ball, self.paddle1)
        p2_collide = collide_check(self.ball, self.paddle2)
        if p1_collide or p2_collide:
            self.ball.bounce_x()
            self.ball.accelerate()
        else:
            if gutter_side == "Left" and not p1_collide:
                self.right_score += 1
                self.last_scorer = Game.p2
            elif gutter_side == "Right" and not p2_collide:
                self.left_score += 1
                self.last_scorer = Game.p1

            if self.left_score == 5 or self.right_score == 5:
                self.state = State.RESULT
            else:
                self.state = State.PAUSE

    def handle_keydown(self, event):
        """Handles keydown events and updates game state"""
        if self.state == State.SPLASH:
            self.init_game()
        elif self.state == State.RESULT:
            self.state = State.SPLASH
        elif self.state == State.PAUSE:
            if event.key == pygame.K_RETURN:
                self.state = State.GAME
                direction = 1 if self.last_scorer == Game.p1 else -1
                self.ball = Ball(direction=direction)
        elif self.state == State.GAME:
            if event.key == pygame.K_UP:
                self.paddle2.move_up()
            elif event.key == pygame.K_DOWN:
                self.paddle2.move_down()
            elif event.key == pygame.K_w:
                self.paddle1.move_up()
            elif event.key == pygame.K_s:
                self.paddle1.move_down()

    def handle_keyup(self, event):
        """Handles keyup events within the GameManager."""
        if event.key in (pygame.K_w, pygame.K_s):
            self.paddle1.stop_moving()
        elif event.key in (pygame.K_UP, pygame.K_DOWN):
            self.paddle2.stop_moving()
