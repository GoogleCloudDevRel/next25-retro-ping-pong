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
        self.frame = 0

    def init_game(self):
        """Initializes game state variables and game objects."""
        self.paddle1 = Paddle()
        self.paddle2 = Paddle()
        paddle1_x = self.paddle1.rect.width // 2 + 1
        paddle2_x = Screen.WIDTH - self.paddle2.rect.width // 2 - 1
        paddle_y = Screen.GAME_PANE_HEIGHT // 2
        self.paddle1.init_location(paddle1_x, paddle_y)
        self.paddle2.init_location(paddle2_x, paddle_y)
        dir = 1 if random.randrange(0, 2) == 0 else -1
        self.ball = Ball(
            x_vel=Game.BALL_VELOCITY_X,
            y_vel=Game.BALL_VELOCITY_Y,
            multiplier=Game.BALL_SPEED_MULTIPLIER,
            direction=dir
        )
        self.left_score = 0
        self.right_score = 0
        self.state = State.GAME

    def update_paddles(self):
        self.paddle1.update_position()
        self.paddle2.update_position()

    def update_ball(self):
        def gutter_check(ball, paddle):
            if ball.x <= ball.rect.width // 2 + paddle.rect.width:
                return "Left"
            elif ball.x >= Screen.WIDTH - ball.rect.width // 2 - paddle.rect.width:
                return "Right"
            return False

        def collide_check(obj1: pygame.rect, obj2: pygame.rect):
            return obj1.rect.colliderect(obj2.rect)

        top_border = self.ball.radius
        bottom_border = Screen.GAME_PANE_HEIGHT - self.ball.radius

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

            collided_paddle = self.paddle1 if p1_collide else self.paddle2
            collided_paddle.next_image()
            paddle_section_height = collided_paddle.rect.height / 4
            relative_y = self.ball.y - collided_paddle.rect.top
            section_index = int(relative_y / paddle_section_height)

            if section_index == 0 or section_index == 3:
                self.ball.y_vel *= 1.2
            elif section_index == 1 or section_index == 2:
                self.ball.y_vel *= 0.8
            max_y_vel = 15
            self.ball.y_vel = max(-max_y_vel, min(self.ball.y_vel, max_y_vel))
        else:
            if gutter_side == "Left" and not p1_collide:
                self.right_score += 1
                self.last_scorer = Game.p2
            elif gutter_side == "Right" and not p2_collide:
                self.left_score += 1
                self.last_scorer = Game.p1

            if self.left_score == Game.GAME_OVER_SCORE or self.right_score == Game.GAME_OVER_SCORE:
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

    def get_paddle_color_index(self, player):
        return self.paddle1.index if player == 1 else self.paddle2.index
