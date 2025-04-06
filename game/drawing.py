import cv2
import pygame
from config import Color, Screen, Game
from pathlib import Path

script_dir = Path(__file__).parent.resolve()
assets_dir = script_dir / "assets"


class Assets:
    def __init__(self):
        self.COLORS = ["blue", "green", "red", "yellow"]
        self.splash_video = cv2.VideoCapture(assets_dir / "splash.mp4")
        self.center_line = pygame.image.load(assets_dir / "background" / "center_line.png")
        self.background = pygame.image.load(assets_dir / "background" / "background.png")
        self.bottom_pane = pygame.image.load(assets_dir / "background" / "bottom_pane.png")
        self.bottom_border = pygame.image.load(assets_dir / "background" / "bottom_border.png")
        self.text_scan = pygame.image.load(assets_dir / "text_headers" / "text_scan.png")
        self.text_press = pygame.image.load(assets_dir / "text_headers" / "press_button_to_skip.png")
        self.scanline = pygame.image.load(assets_dir / "background" / "scanline.png")
        self.ball = pygame.image.load(assets_dir / "ball.png")
        self.cookbook = pygame.image.load(assets_dir / "cookbook.png")
        self.github = pygame.image.load(assets_dir / "github.png")

        self.goal = []
        self.winner1 = []
        self.winner2 = []

        def append_sequence(arr, path):
            for i in range(4):
                image_path = f"{path}/{i}.png"
                image = pygame.image.load(image_path)
                arr.append(image)
        append_sequence(self.goal, assets_dir / "sequences" / "goal")
        append_sequence(self.winner1, assets_dir / "sequences" / "win" / "p1")
        append_sequence(self.winner2, assets_dir / "sequences" / "win" / "p2")

        self.goal_backgrounds = {}
        for color in self.COLORS:
            self.goal_backgrounds[color] = pygame.image.load(assets_dir / "background" / f"{color}.png")
            self.goal_backgrounds[color] = pygame.image.load(assets_dir / "background" / f"{color}.png")
            self.goal_backgrounds[color+"_rev"] = pygame.image.load(assets_dir / "background" / f"{color}_rev.png")
        
        self.paddle_images = []
        for i in range(4):
            image_path = assets_dir / "paddle" / f"paddle_{i}.png"
            image = pygame.image.load(image_path)
            self.paddle_images.append(image)

        self.optimize_assets()

    def optimize_assets(self):
        self.center_line = pygame.transform.scale(self.center_line, (50, Screen.GAME_PANE_HEIGHT * 1.2))
        border_w, border_h = self.bottom_border.get_size()
        new_border_h = int(border_h * (Screen.WIDTH / border_w))
        self.bottom_border = pygame.transform.scale(self.bottom_border, (Screen.WIDTH, new_border_h))


def draw_splash_screen(canvas, assets):
    splash_video = assets.splash_video
    success, video_image = splash_video.read()
    if success:
        video_image = cv2.resize(video_image, (Screen.WIDTH, Screen.HEIGHT))
        video_image = cv2.cvtColor(video_image, cv2.COLOR_BGR2RGB)
        video_surf = pygame.image.frombuffer(
            video_image.tobytes(), video_image.shape[1::-1], "RGB"
        )
    else:
        splash_video.set(cv2.CAP_PROP_POS_FRAMES, 0)
        success, video_image = splash_video.read()
        if success:
            video_image = cv2.cvtColor(video_image, cv2.COLOR_BGR2RGB)
            video_surf = pygame.image.frombuffer(
                video_image.tobytes(), video_image.shape[1::-1], "RGB")
    if video_surf:
        canvas.blit(video_surf, (0, 0))


def draw_game_pane(canvas, game_manager, assets):
    """Draws the game pane, paddles, ball, and center elements."""
    center_line_image = assets.center_line
    center_line_rect = center_line_image.get_rect(
        center=(Screen.WIDTH // 2, Screen.GAME_PANE_HEIGHT // 2)
    )
    canvas.blit(center_line_image, center_line_rect)

    game_manager.paddle1.draw(canvas)
    game_manager.paddle2.draw(canvas)
    game_manager.ball.draw(canvas)


def draw_score_pane(canvas, game_manager, assets):
    """Draws the score pane with player names and scores."""
    score_pane_bg = assets.bottom_pane
    pane_h = score_pane_bg.get_height()
    score_pane_bg_rect = score_pane_bg.get_rect(topleft=(0, Screen.HEIGHT - pane_h))
    canvas.blit(score_pane_bg, score_pane_bg_rect)

    bottom_border = assets.bottom_border
    bottom_border_rect = bottom_border.get_rect(topleft=(0, Screen.HEIGHT - pane_h))
    canvas.blit(bottom_border, bottom_border_rect)

    font = pygame.font.Font(pygame.font.get_default_font(), 40)

    left_score_str = str(game_manager.left_score)
    right_score_str = str(game_manager.right_score)
    p1_index = game_manager.get_paddle_color_index(1)
    p2_index = game_manager.get_paddle_color_index(2)

    left_score_surface = font.render(left_score_str, True, Color.arr[p1_index])
    right_score_surface = font.render(right_score_str, True, Color.arr[p2_index])

    score_pane_y = score_pane_bg_rect.top
    left_score_rect = left_score_surface.get_rect(center=(
        Screen.WIDTH // 5, Screen.HEIGHT - ((Screen.HEIGHT - score_pane_y) // 2)
    ))
    right_score_rect = right_score_surface.get_rect(center=(
        Screen.WIDTH - (Screen.WIDTH // 5), Screen.HEIGHT - ((Screen.HEIGHT - score_pane_y) // 2)
    ))

    canvas.blit(left_score_surface, left_score_rect)
    canvas.blit(right_score_surface, right_score_rect)


def draw_game_screen(canvas, game_manager, assets):
    draw_game_pane(canvas, game_manager, assets)
    draw_score_pane(canvas, game_manager, assets)


def draw_result_screen(canvas, left_score, right_score, assets):
    """Draws the result screen."""
    canvas.fill(Color.BLACK)

    scanline = assets.scanline
    canvas.blit(scanline, (0, 0))

    winner = Game.p1 if left_score == Game.GAME_OVER_SCORE else Game.p2
    winner_sequence = assets.winner1 if winner == Game.p1 else assets.winner2
    curr_frame = (pygame.time.get_ticks() // 150) % len(winner_sequence)
    image = winner_sequence[curr_frame]
    image_rect = image.get_rect(center=(Screen.WIDTH // 2, Screen.HEIGHT * 0.18))
    canvas.blit(image, image_rect)

    qr = assets.cookbook
    # qr = assets.github
    qr_original_w, qr_original_h = qr.get_size()
    new_w, new_h = int(qr_original_w * 0.5), int(qr_original_h * 0.5)
    qr = pygame.transform.scale(qr, (new_w, new_h))
    qr_rect = qr.get_rect(center=(Screen.WIDTH // 2, Screen.HEIGHT * 0.55))
    canvas.blit(qr, qr_rect)

    text_scan = assets.text_scan
    text_original_w, text_original_h = text_scan.get_size()
    new_w, new_h = int(text_original_w * 0.5), int(text_original_h * 0.5)
    text_scan = pygame.transform.scale(text_scan, (new_w, new_h))
    text_scan_rect = text_scan.get_rect(center=(Screen.WIDTH // 2, Screen.HEIGHT * 0.80))
    canvas.blit(text_scan, text_scan_rect)

    text_press = assets.text_press
    text_press_rect = text_press.get_rect(center=(Screen.WIDTH // 2, Screen.HEIGHT * 0.85))
    canvas.blit(text_press, text_press_rect)


def draw_pause_screen(canvas, game_manager, assets):
    """Draws the pause screen."""
    loser = int(Game.p2[-1]) if game_manager.last_scorer == Game.p1 else int(Game.p1[-1])
    loser_color = game_manager.get_paddle_color_index(loser)

    bg_name = assets.COLORS[loser_color]
    bg_pos = (0, 0)
    if loser == 2:
        bg_name += "_rev"
        bg_pos = (Screen.WIDTH - assets.goal_backgrounds[bg_name].get_width(), 0)

    canvas.blit(assets.goal_backgrounds[bg_name], bg_pos)
    curr_frame = (pygame.time.get_ticks() // 150) % len(assets.goal)
    canvas.blit(assets.goal[curr_frame], (0, 110))
    draw_game_pane(canvas, game_manager, assets)
    draw_score_pane(canvas, game_manager, assets)


def update_display(original_surface, window):
    scaled_surface = pygame.transform.scale(
        original_surface, (
            pygame.display.Info().current_w,
            pygame.display.Info().current_h
        )
    )
    window.blit(scaled_surface, (0, 0))
    pygame.display.update()
