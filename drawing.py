import pygame
from config import Color, Screen, Game


def draw_splash_screen(canvas):
    """Draws the splash screen."""
    canvas.fill(Color.BLACK)

    title_pos = (Screen.WIDTH // 2, Screen.HEIGHT // 3)
    title_font = pygame.font.SysFont(Game.FONT, 50)
    title_surface = title_font.render(Game.TITLE, False, Color.WHITE)
    title_rect = title_surface.get_rect(center=title_pos)

    instruction_pos = (Screen.WIDTH // 2, Screen.HEIGHT // 2)
    instruction_font = pygame.font.SysFont(Game.FONT, 30)
    instruction_surface = instruction_font.render("Press any key to start", False, Color.WHITE)
    instruction_rect = instruction_surface.get_rect(center=instruction_pos)

    canvas.blit(title_surface, title_rect)
    canvas.blit(instruction_surface, instruction_rect)


def draw_game_pane(canvas, game_manager):
    """Draws the game pane, paddles, ball, and center elements."""
    pane_rect = (0, Screen.GAME_PANE_START_Y, Screen.WIDTH, Screen.GAME_PANE_HEIGHT)
    pygame.draw.rect(canvas, Color.WHITE, pane_rect, 1)
    center_x = Screen.WIDTH // 2
    pane_top = Screen.GAME_PANE_START_Y
    pane_bottom = Screen.GAME_PANE_START_Y + Screen.GAME_PANE_HEIGHT
    pygame.draw.line(
        canvas,
        Color.WHITE,
        [center_x, pane_top],
        [center_x, pane_bottom],
        width=1
    )
    pygame.draw.circle(
        canvas,
        Color.WHITE,
        [Screen.WIDTH // 2, Screen.GAME_PANE_START_Y + Screen.GAME_PANE_HEIGHT // 2],
        radius=70,
        width=1
    )
    game_manager.paddle1.draw(canvas)
    game_manager.paddle2.draw(canvas)
    game_manager.ball.draw(canvas)


def draw_score_pane(canvas, game_manager):
    """Draws the score pane with player names and scores."""
    pygame.draw.rect(canvas, Color.BLACK, (0, 0, Screen.WIDTH, Screen.SCORE_PANE_HEIGHT))
    font = pygame.font.SysFont(Game.FONT, 30)
    score_label = f"{game_manager.left_score} : {game_manager.right_score}"
    p1_text = font.render("Player 1", 1, Color.WHITE)
    p2_text = font.render("Player 2", 1, Color.WHITE)
    score_text = font.render(score_label, 1, Color.WHITE)
    canvas.blit(p1_text, p1_text.get_rect(center=(Screen.WIDTH // 4, 50)))
    canvas.blit(p2_text, p2_text.get_rect(center=(Screen.WIDTH - (Screen.WIDTH // 4), 50)))
    canvas.blit(score_text, ((Screen.WIDTH // 2) - 30, 30))


def draw_log_pane(canvas):
    """Draws the log pane (currently empty placeholder)."""
    pane_rect = (0, Screen.LOG_PANE_START_Y, Screen.WIDTH, Screen.LOG_PANE_HEIGHT)
    text_center_pos = (Screen.WIDTH // 2, Screen.LOG_PANE_START_Y + Screen.LOG_PANE_HEIGHT // 2)
    font = pygame.font.SysFont(Game.FONT, 10)
    pygame.draw.rect(canvas, Color.BLACK, pane_rect)
    log_label = font.render("Log Pane (Empty)", 1, Color.WHITE)
    log_rect = log_label.get_rect(center=text_center_pos)
    canvas.blit(log_label, log_rect)


def draw_result_screen(canvas, left_score, right_score):
    """Draws the result screen."""
    winner_pos = (Screen.WIDTH // 2, Screen.HEIGHT // 3)
    winner_font = pygame.font.SysFont(Game.FONT, 50)
    canvas.fill(Color.BLACK)

    winner = Game.p1 if left_score == 5 else Game.p2
    winner_text = f"{winner} wins!"
    winner_surface = winner_font.render(winner_text, True, Color.WHITE)
    winner_rect = winner_surface.get_rect(center=winner_pos)
    canvas.blit(winner_surface, winner_rect)

    score_pos = (Screen.WIDTH // 2, Screen.HEIGHT // 2)
    score_font = pygame.font.SysFont(Game.FONT, 30)
    score_text = f"Score {left_score}:{right_score}"
    score_surface = score_font.render(score_text, True, Color.WHITE)
    score_rect = score_surface.get_rect(center=score_pos)
    canvas.blit(score_surface, score_rect)

    instruction_pos = (Screen.WIDTH // 2, Screen.HEIGHT * 2 // 3)
    instruction_font = pygame.font.SysFont(Game.FONT, 20)
    instruction_surface = instruction_font.render("Press any key", True, Color.WHITE)
    instruction_rect = instruction_surface.get_rect(center=instruction_pos)
    canvas.blit(instruction_surface, instruction_rect)


def draw_pause_screen(canvas, game_manager):
    """Draws the pause screen."""
    message_pos = (Screen.WIDTH // 2, Screen.HEIGHT // 3)
    instruction_pos = (Screen.WIDTH // 2, Screen.HEIGHT // 2)
    draw_game_pane(canvas, game_manager)
    draw_score_pane(canvas, game_manager)
    draw_log_pane(canvas)
    font = pygame.font.SysFont("Comic Sans MS", 40)
    message_surface = font.render(f"{game_manager.last_scorer} scored!", True, Color.WHITE)
    message_rect = message_surface.get_rect(center=message_pos)
    canvas.blit(message_surface, message_rect)

    instruction_font = pygame.font.SysFont("Comic Sans MS", 30)
    instruction_surface = instruction_font.render("Press ENTER to continue", True, Color.WHITE)
    instruction_rect = instruction_surface.get_rect(center=instruction_pos)
    canvas.blit(instruction_surface, instruction_rect)
