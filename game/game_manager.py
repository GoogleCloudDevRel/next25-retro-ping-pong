import random
import pygame
import pygame.locals
import logging
from config import State, Screen, Game
from ball import Ball
from paddle import Paddle

log = logging.getLogger(__name__)


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
        self.JOYSTICK_DEADZONE = 0.5  # Adjust if needed
        self.PLAYER1_JOYSTICK_ID = 0
        self.PLAYER2_JOYSTICK_ID = 1  # Assumes the second joystick controls player 2
        self.VERTICAL_AXIS_ID = 1   # Common axis for vertical movement (Y-axis on left stick)
        self.CONFIRM_BUTTONS = {0, 3}  # Buttons 0 and 3 for confirmation

    def init_game(self):
        """Initializes game state variables and game objects."""
        self.paddle1 = Paddle()
        self.paddle2 = Paddle()
        paddle1_x = 100 + self.paddle1.rect.width // 2 + 1
        paddle2_x = Screen.WIDTH - 100 - self.paddle2.rect.width // 2 - 1
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
            return  # Should not happen in GAME state, but safety check

        self.ball.move()
        ball_radius = self.ball.get_radius()

        top_border = ball_radius
        bottom_border = Screen.GAME_PANE_HEIGHT - ball_radius

        if self.ball.y <= top_border:
            self.ball.y = top_border + 1
            self.ball.rect.centery = int(self.ball.y)
            self.ball.bounce_y()
        elif self.ball.y >= bottom_border:
            self.ball.y = bottom_border - 1
            self.ball.rect.centery = int(self.ball.y)
            self.ball.bounce_y()

        collided = False
        collided_paddle = None

        if self.ball.x_vel < 0 and self.ball.rect.colliderect(self.paddle1.rect):
            if self.ball.rect.right > self.paddle1.rect.left:
                collided = True
                collided_paddle = self.paddle1
                self.ball.x = self.paddle1.rect.right + ball_radius
                self.ball.rect.centerx = int(self.ball.x)

        elif self.ball.x_vel > 0 and self.ball.rect.colliderect(self.paddle2.rect):
            if self.ball.rect.left < self.paddle2.rect.right:
                collided = True
                collided_paddle = self.paddle2
                self.ball.x = self.paddle2.rect.left - ball_radius
                self.ball.rect.centerx = int(self.ball.x)

        if collided:
            self.ball.bounce_x()
            self.ball.accelerate()
            collided_paddle.next_image()

            paddle_section_height = collided_paddle.rect.height / 4
            relative_y = self.ball.y - collided_paddle.rect.top

            relative_y = max(0, min(relative_y, collided_paddle.rect.height - 1))

            section_index = int(relative_y // paddle_section_height)
            section_index = max(0, min(section_index, 3))

            if section_index == 0 or section_index == 3:
                self.ball.y_vel *= 1.3
            elif section_index == 1 or section_index == 2:
                self.ball.y_vel *= 0.9

            max_y_vel = 15
            self.ball.y_vel = max(-max_y_vel, min(self.ball.y_vel, max_y_vel))

            min_y_vel_abs = 1
            if abs(self.ball.y_vel) < min_y_vel_abs:
                sign = 1 if self.ball.y_vel >= 0 else -1
                self.ball.y_vel = min_y_vel_abs * sign
                if self.ball.y_vel == 0:
                    self.ball.y_vel = min_y_vel_abs

        else:
            score_occurred = False
            if self.ball.rect.right < 0:
                self.right_score += 1
                self.last_scorer = Game.p2
                score_occurred = True
                log.info(f"Right scores! Score: {self.left_score} - {self.right_score}")
            elif self.ball.rect.left > Screen.WIDTH:
                self.left_score += 1
                self.last_scorer = Game.p1
                score_occurred = True
                log.info(f"Left scores! Score: {self.left_score} - {self.right_score}")
            if score_occurred:
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
                    y_vel=random.choice([-Game.BALL_VELOCITY_Y, Game.BALL_VELOCITY_Y]),
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
        # event attributes: joy (or instance_id), axis, value
        # Value range is -1.0 to 1.0
        log.debug(f"Handling JOYAXISMOTION - Joy: {event.joy}, Axis: {event.axis}, Value: {event.value:.4f}")
        if self.state == State.GAME:
            # Ensure paddles exist
            if not self.paddle1 or not self.paddle2:
                log.warning("Joystick axis ignored: Paddles not initialized in GAME state.")
                return

            # Check if it's the vertical axis we care about
            if event.axis == self.VERTICAL_AXIS_ID:
                # Player 1 Control (Joystick ID 0)
                if event.joy == self.PLAYER1_JOYSTICK_ID:
                    if event.value < -self.JOYSTICK_DEADZONE:  # Up
                        self.paddle1.move_up()
                    elif event.value > self.JOYSTICK_DEADZONE: # Down
                        self.paddle1.move_down()
                    else:  # Center (within deadzone)
                        # Only stop if it was previously moving due to joystick
                        if abs(self.paddle1.speed) > 0:  # Check if paddle has non-zero speed
                            log.debug(f"Joystick {event.joy} Axis {event.axis} in deadzone, stopping paddle 1.")
                            self.paddle1.stop_moving()

                # Player 2 Control (Joystick ID 1)
                elif event.joy == self.PLAYER2_JOYSTICK_ID:
                    # Check if the second joystick exists and is initialized
                    # Note: Pygame's event already ensures the joystick exists if event.joy is valid
                    if event.value < -self.JOYSTICK_DEADZONE: # Up
                        self.paddle2.move_up()
                    elif event.value > self.JOYSTICK_DEADZONE:  # Down
                        self.paddle2.move_down()
                    else:  # Center (within deadzone)
                        # Only stop if it was previously moving due to joystick
                        if abs(self.paddle2.speed) > 0:
                            log.debug(f"Joystick {event.joy} Axis {event.axis} in deadzone, stopping paddle 2.")
                            self.paddle2.stop_moving()

    def handle_joystick_button_down(self, event):
        """Handles joystick button presses."""
        # event attributes: joy (or instance_id), button
        log.debug(f"Handling JOYBUTTONDOWN - Joy: {event.joy}, Button: {event.button}")
        if event.button in self.CONFIRM_BUTTONS:
            # Allow confirm button from any connected joystick
            log.info(f"Confirm button {event.button} pressed on joystick {event.joy}")
            self._handle_confirm_action()
        # Add other button actions here if needed

    def handle_joystick_button_up(self, event):
        """Handles joystick button releases."""
        # event attributes: joy (or instance_id), button
        log.debug(f"Handling JOYBUTTONUP - Joy: {event.joy}, Button: {event.button}")
        # Add actions for button releases if needed

    def handle_joystick_hat(self, event):
        """Handles joystick hat (D-pad) motion."""
        # event attributes: joy (or instance_id), hat, value (tuple, e.g., (0, 1) for up)
        log.debug(f"Handling JOYHATMOTION - Joy: {event.joy}, Hat: {event.hat}, Value: {event.value}")
        if self.state == State.GAME:
            if not self.paddle1 or not self.paddle2:
                log.warning("Joystick hat ignored: Paddles not initialized in GAME state.")
                return

            hat_x, hat_y = event.value

            # Player 1 Control (Joystick ID 0)
            if event.joy == self.PLAYER1_JOYSTICK_ID:
                if hat_y > 0: # D-Pad Up
                    self.paddle1.move_up()
                elif hat_y < 0: # D-Pad Down
                    self.paddle1.move_down()
                elif hat_y == 0: # D-Pad Vertical Release
                    if abs(self.paddle1.speed) > 0:
                        self.paddle1.stop_moving()

            # Player 2 Control (Joystick ID 1)
            elif event.joy == self.PLAYER2_JOYSTICK_ID:
                if hat_y > 0: # D-Pad Up
                    self.paddle2.move_up()
                elif hat_y < 0: # D-Pad Down
                    self.paddle2.move_down()
                elif hat_y == 0: # D-Pad Vertical Release
                    if abs(self.paddle2.speed) > 0:
                        self.paddle2.stop_moving()

            # Add horizontal hat control if needed (hat_x)

    def handle_joystick_added(self, event):
        """Handles joystick connection."""
        # event attributes: device_index
        log.info(f"JOYDEVICEADDED - Joystick added at index: {event.device_index}")
        # You might want to re-initialize the specific joystick here
        try:
            new_joy = pygame.joystick.Joystick(event.device_index)
            log.info(f"   Name: {new_joy.get_name()}")
            new_joy.init() # Initialize the newly added joystick
        except pygame.error as e:
            log.error(f"   Error initializing added joystick {event.device_index}: {e}")

    def handle_joystick_removed(self, event):
        """Handles joystick disconnection."""
        # event attributes: instance_id (use this to know *which* joystick was removed)
        log.info(f"JOYDEVICEREMOVED - Joystick removed, instance ID: {event.instance_id}")
        # Add logic here if you need to handle a player losing their controller mid-game
        # e.g., pause the game, disable the corresponding paddle

    def get_paddle_color_index(self, player):
        # Ensure paddles exist before accessing index
        if player == 1 and self.paddle1:
            return self.paddle1.index
        elif player == 2 and self.paddle2:
            return self.paddle2.index
        return 0  # Default or error value

    def handle_pygame_events(self):
        """Processes all Pygame events, including keyboard and joystick."""
        for event in pygame.event.get():
            # --- Universal Exit ---
            if event.type == pygame.locals.QUIT:
                log.info("QUIT event received. Signalling exit.")
                return False  # exit the main loop

            # --- Keyboard Events ---
            elif event.type == pygame.locals.KEYDOWN:
                # Log ALL keydown events for debugging (optional)
                # log.debug(f"KEYDOWN: Scancode={event.scancode}, Key={event.key} ('{pygame.key.name(event.key)}'), Mod={event.mod}")
                self.handle_keydown(event)
            elif event.type == pygame.locals.KEYUP:
                # log.debug(f"KEYUP: Scancode={event.scancode}, Key={event.key} ('{pygame.key.name(event.key)}'), Mod={event.mod}")
                self.handle_keyup(event)

            # --- Joystick Events ---
            elif event.type == pygame.locals.JOYAXISMOTION:
                # *** LOGGING ADDED HERE ***
                # Using log.debug for less clutter, change to log.info if needed
                log.debug(f"[Joystick Raw] Type: JOYAXISMOTION, Joy: {event.joy}, Axis: {event.axis}, Value: {event.value:.4f}")
                self.handle_joystick_axis(event)
            elif event.type == pygame.locals.JOYBUTTONDOWN:
                # *** LOGGING ADDED HERE ***
                log.debug(f"[Joystick Raw] Type: JOYBUTTONDOWN, Joy: {event.joy}, Button: {event.button}")
                self.handle_joystick_button_down(event) # Changed to specific down handler
            elif event.type == pygame.locals.JOYBUTTONUP:
                # *** LOGGING ADDED HERE ***
                log.debug(f"[Joystick Raw] Type: JOYBUTTONUP, Joy: {event.joy}, Button: {event.button}")
                self.handle_joystick_button_up(event) # Added handler call
            elif event.type == pygame.locals.JOYHATMOTION:
                # *** LOGGING ADDED HERE ***
                # Value is a tuple (x, y) like (-1, 0) left, (1, 0) right, (0, 1) up, (0, -1) down, (0, 0) center
                log.debug(f"[Joystick Raw] Type: JOYHATMOTION, Joy: {event.joy}, Hat: {event.hat}, Value: {event.value}")
                self.handle_joystick_hat(event) # Added handler call
            elif event.type == pygame.locals.JOYDEVICEADDED:
                # *** LOGGING ADDED HERE ***
                log.info(f"[Joystick Raw] Type: JOYDEVICEADDED, Index: {event.device_index}")
                self.handle_joystick_added(event) # Added handler call
            elif event.type == pygame.locals.JOYDEVICEREMOVED:
                # *** LOGGING ADDED HERE ***
                log.info(f"[Joystick Raw] Type: JOYDEVICEREMOVED, Instance ID: {event.instance_id}")
                self.handle_joystick_removed(event) # Added handler call

        return True  # continue the main loop
