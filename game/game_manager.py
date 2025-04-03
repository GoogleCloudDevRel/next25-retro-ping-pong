# game_manager.py
import random
import pygame
import pygame.locals  # Import locals explicitly
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
        # Define joystick constants
        self.JOYSTICK_DEADZONE = 0.5 # Adjust if needed
        self.PLAYER1_JOYSTICK_ID = 0
        self.PLAYER2_JOYSTICK_ID = 1 # Assumes the second joystick controls player 2
        self.VERTICAL_AXIS_ID = 1   # Common axis for vertical movement (Y-axis on left stick)
        self.CONFIRM_BUTTONS = {0, 3} # Buttons 0 and 3 for confirmation

    def init_game(self):
        """Initializes game state variables and game objects."""
        self.paddle1 = Paddle()
        self.paddle2 = Paddle()
        paddle1_x = self.paddle1.rect.width // 2 + 1
        paddle2_x = Screen.WIDTH - self.paddle2.rect.width // 2 - 1
        paddle_y = Screen.GAME_PANE_HEIGHT // 2
        self.paddle1.init_location(paddle1_x, paddle_y)
        self.paddle2.init_location(paddle2_x, paddle_y)
        direction = 1 if random.randrange(0, 2) == 0 else -1
        self.ball = Ball(
            x=Screen.WIDTH // 2,
            y=Screen.GAME_PANE_HEIGHT // 2,
            x_vel=Game.BALL_VELOCITY_X,
            y_vel=Game.BALL_VELOCITY_Y,
            multiplier=Game.BALL_SPEED_MULTIPLIER,
            direction=direction
        )
        self.left_score = 0
        self.right_score = 0
        self.state = State.GAME

    def update_paddles(self):
        # Ensure paddles exist before updating
        if self.paddle1:
            self.paddle1.update_position()
        if self.paddle2:
            self.paddle2.update_position()

    def update_ball(self):
        # Ensure ball and paddles exist before updating
        if not self.ball or not self.paddle1 or not self.paddle2:
            return # Should not happen in GAME state, but safety check

        def gutter_check(ball, paddle):
            if ball.x <= ball.rect.width // 2 + paddle.rect.width:
                return "Left"
            elif ball.x >= Screen.WIDTH - ball.rect.width // 2 - paddle.rect.width:
                return "Right"
            return False

        def collide_check(obj1: pygame.rect, obj2: pygame.rect):
            return obj1.rect.colliderect(obj2.rect)

        top_border = self.ball.get_radius()
        bottom_border = Screen.GAME_PANE_HEIGHT - self.ball.get_radius()

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

            # Clamp section_index to valid range [0, 3]
            section_index = max(0, min(section_index, 3))

            if section_index == 0 or section_index == 3: # Top or bottom section
                self.ball.y_vel *= 1.2
            elif section_index == 1 or section_index == 2: # Middle sections
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
            self.state = State.PAUSE

    def _handle_confirm_action(self):
        """Handles the action triggered by RETURN key or joystick confirm buttons."""
        if self.state == State.SPLASH:
            self.init_game()
        elif self.state == State.RESULT:
            self.state = State.SPLASH
        elif self.state == State.PAUSE:
            if self.left_score == Game.GAME_OVER_SCORE or self.right_score == Game.GAME_OVER_SCORE:
                self.state = State.RESULT
            else:
                self.state = State.GAME
                direction = 1 if self.last_scorer == Game.p1 else -1
                self.ball = self.ball = Ball(
                    x=Screen.WIDTH // 2,
                    y=Screen.GAME_PANE_HEIGHT // 2,
                    x_vel=Game.BALL_VELOCITY_X,
                    y_vel=random.uniform(-Game.BALL_VELOCITY_Y, Game.BALL_VELOCITY_Y),
                    multiplier=Game.BALL_SPEED_MULTIPLIER,
                    direction=direction
                )

    def handle_keydown(self, event):
        """Handles keydown events and updates game state"""
        is_return_key = (event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER)

        if is_return_key:
            self._handle_confirm_action() # Use the refactored method
        elif self.state == State.GAME:
            # Ensure paddles exist before trying to move them
            if not self.paddle1 or not self.paddle2:
                return

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
        if self.state == State.GAME:
            # Ensure paddles exist before trying to stop them
            if not self.paddle1 or not self.paddle2:
                return

            if event.key in (pygame.K_w, pygame.K_s):
                self.paddle1.stop_moving()
            elif event.key in (pygame.K_UP, pygame.K_DOWN):
                self.paddle2.stop_moving()

    def handle_joystick_axis(self, event):
        """Handles joystick axis motion."""
        # event attributes: joy, axis, value
        if self.state == State.GAME:
            # Ensure paddles exist
            if not self.paddle1 or not self.paddle2:
                return

            # Check if it's the vertical axis we care about
            if event.axis == self.VERTICAL_AXIS_ID:
                # Player 1 Control (Joystick ID 0)
                if event.joy == self.PLAYER1_JOYSTICK_ID:
                    if event.value < -self.JOYSTICK_DEADZONE: # Up
                        self.paddle1.move_up()
                    elif event.value > self.JOYSTICK_DEADZONE: # Down
                        self.paddle1.move_down()
                    else: # Center (within deadzone)
                        self.paddle1.stop_moving()
                # Player 2 Control (Joystick ID 1)
                elif event.joy == self.PLAYER2_JOYSTICK_ID:
                    # Check if the second joystick exists and is initialized
                    if pygame.joystick.get_count() > self.PLAYER2_JOYSTICK_ID:
                        if event.value < -self.JOYSTICK_DEADZONE: # Up
                            self.paddle2.move_up()
                        elif event.value > self.JOYSTICK_DEADZONE: # Down
                            self.paddle2.move_down()
                        else: # Center (within deadzone)
                            self.paddle2.stop_moving()

    def handle_joystick_button(self, event):
        """Handles joystick button presses."""
        # event attributes: joy, button
        if event.button in self.CONFIRM_BUTTONS:
            # Allow confirm button from any connected joystick
            print(f"Confirm button {event.button} pressed on joystick {event.joy}")
            self._handle_confirm_action()

    def get_paddle_color_index(self, player):
        # Ensure paddles exist before accessing index
        if player == 1 and self.paddle1:
            return self.paddle1.index
        elif player == 2 and self.paddle2:
            return self.paddle2.index
        return 0 # Default or error value

    def handle_pygame_events(self):
        """Processes all Pygame events, including keyboard and joystick."""
        for event in pygame.event.get():
            if event.type == pygame.locals.QUIT:
                return False  # exit the main loop

            # Keyboard Events
            elif event.type == pygame.locals.KEYDOWN:
                self.handle_keydown(event)
            elif event.type == pygame.locals.KEYUP:
                self.handle_keyup(event)

            # Joystick Events
            elif event.type == pygame.locals.JOYAXISMOTION:
                # Optional: print axis events for debugging
                print(f"Joy: {event.joy}, Axis: {event.axis}, Value: {event.value:.2f}")
                self.handle_joystick_axis(event)
            elif event.type == pygame.locals.JOYBUTTONDOWN:
                # Optional: print button events for debugging
                print(f"Joy: {event.joy}, Button: {event.button}")
                self.handle_joystick_button(event)
            # Add JOYBUTTONUP, JOYHATMOTION etc. if needed later

        return True  # continue the main loop
