import cv2
import pygame
from config import Color, Screen, Game
from pathlib import Path

script_dir = Path(__file__).parent.resolve()
assets_dir = script_dir / "assets_1080"


class Assets:
    def __init__(self):
        self.COLORS = ["blue", "green", "red", "yellow"]
        self.splash_video = cv2.VideoCapture(assets_dir / "splash.mp4")
        self.center_line = pygame.image.load(assets_dir / "background" / "center_line.png")
        self.background = pygame.image.load(assets_dir / "background" / "background.png")
        self.bottom_pane = pygame.image.load(assets_dir / "background" / "bottom_pane.png")
        self.bottom_border = pygame.image.load(assets_dir / "background" / "bottom_border.png")
        self.text_scan = pygame.image.load(assets_dir / "text_headers" / "scan_for_full_game_summary.png")
        self.text_press = pygame.image.load(assets_dir / "text_headers" / "press_button_to_skip.png")
        self.scanline = pygame.image.load(assets_dir / "background" / "scanline.png")
        self.ball = pygame.image.load(assets_dir / "ball.png")

        self.goal = []
        self.winner1 = []
        self.winner2 = []
        self.score = []
        for i in range(4):
            for j in range(10):
                score_path = f"{assets_dir}/score/{j}-{i}.png"
                score_image = pygame.image.load(score_path)
                self.score.append(score_image)

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

        # self.optimize_assets()

    # def optimize_assets(self):
        # self.center_line = pygame.transform.scale(self.center_line, (50, Screen.GAME_PANE_HEIGHT * 1.2))
        # border_w, border_h = self.bottom_border.get_size()
        # new_border_h = int(border_h * (Screen.WIDTH / border_w))
        # self.bottom_border = pygame.transform.scale(self.bottom_border, (Screen.WIDTH, new_border_h))


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
    """Draws the score pane with player names and scores using images."""
    score_pane_bg = assets.bottom_pane
    pane_h = score_pane_bg.get_height()
    score_pane_bg_rect = score_pane_bg.get_rect(topleft=(0, Screen.HEIGHT - pane_h))
    canvas.blit(score_pane_bg, score_pane_bg_rect)

    bottom_border = assets.bottom_border
    bottom_border_rect = bottom_border.get_rect(center=(Screen.WIDTH // 2, Screen.HEIGHT - pane_h))
    canvas.blit(bottom_border, bottom_border_rect)

    # --- 점수 이미지 사용 시작 ---
    # 1. 플레이어별 점수와 색상 인덱스 가져오기
    left_score = game_manager.left_score # 점수는 정수여야 함
    right_score = game_manager.right_score # 점수는 정수여야 함
    p1_index = game_manager.get_paddle_color_index(1) # 왼쪽 플레이어(P1) 색상 인덱스 (0-3)
    p2_index = game_manager.get_paddle_color_index(2) # 오른쪽 플레이어(P2) 색상 인덱스 (0-3)

    # 2. assets.score 리스트에서 올바른 이미지 인덱스 계산
    # 인덱스 = 색상_인덱스 * 10 + 점수_숫자
    try:
        left_score_image_index = p1_index * 10 + left_score
        right_score_image_index = p2_index * 10 + right_score

        # 3. 해당 인덱스의 이미지 가져오기
        left_score_image = assets.score[left_score_image_index]
        right_score_image = assets.score[right_score_image_index]

        # 4. 이미지 위치 계산 (기존 텍스트 위치 로직 재사용)
        score_pane_y = score_pane_bg_rect.top
        left_score_rect = left_score_image.get_rect(center=(
            Screen.WIDTH // 5, Screen.HEIGHT - ((Screen.HEIGHT - score_pane_y) // 2)
        ))
        right_score_rect = right_score_image.get_rect(center=(
            Screen.WIDTH - (Screen.WIDTH // 5), Screen.HEIGHT - ((Screen.HEIGHT - score_pane_y) // 2)
        ))

        # 5. 이미지 그리기
        canvas.blit(left_score_image, left_score_rect)
        canvas.blit(right_score_image, right_score_rect)

    except IndexError:
        # 만약 계산된 인덱스가 assets.score 범위를 벗어나면 오류 발생 방지
        # (예: 점수가 9점을 초과하거나, color_index가 잘못된 경우)
        print(f"Error: Invalid score image index calculated.")
        print(f"  Left - Score: {left_score}, Index: {p1_index}, Calc Index: {p1_index * 10 + left_score}")
        print(f"  Right - Score: {right_score}, Index: {p2_index}, Calc Index: {p2_index * 10 + right_score}")
        # 오류 발생 시 대체 텍스트 또는 빈 공간 처리 등을 추가할 수 있음
        # 예: 기본 폰트로 점수 표시
        font = pygame.font.Font(pygame.font.get_default_font(), 40)
        fallback_left = font.render(str(left_score), True, Color.WHITE)
        fallback_right = font.render(str(right_score), True, Color.WHITE)
        score_pane_y = score_pane_bg_rect.top
        fb_left_rect = fallback_left.get_rect(center=(
            Screen.WIDTH // 5, Screen.HEIGHT - ((Screen.HEIGHT - score_pane_y) // 2)
        ))
        fb_right_rect = fallback_right.get_rect(center=(
            Screen.WIDTH - (Screen.WIDTH // 5), Screen.HEIGHT - ((Screen.HEIGHT - score_pane_y) // 2)
        ))
        canvas.blit(fallback_left, fb_left_rect)
        canvas.blit(fallback_right, fb_right_rect)


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

    text_scan = assets.text_scan
    text_scan_rect = text_scan.get_rect(center=(Screen.WIDTH // 2, Screen.HEIGHT * 0.70))
    canvas.blit(text_scan, text_scan_rect)

    text_press = assets.text_press
    text_press_rect = text_press.get_rect(center=(Screen.WIDTH // 2, Screen.HEIGHT * 0.90))
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
    goal_image = assets.goal[curr_frame]
    goal_rect = goal_image.get_rect()
    goal_rect.centerx = Screen.WIDTH // 2
    goal_rect.centery = Screen.HEIGHT * 0.41
    canvas.blit(goal_image, goal_rect)
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
