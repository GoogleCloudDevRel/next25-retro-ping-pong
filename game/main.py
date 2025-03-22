import sys
import pygame.locals
from config import State, CLOCK
from drawing import *
from game_manager import GameManager
import cv2


def main():
    game_manager = GameManager()
    assets = Assets()
    background_image = assets.background
    splash_video = assets.splash_video
    video_surf = None

    while True:
        original_surface = pygame.Surface((Screen.WIDTH, Screen.HEIGHT))
        original_surface.blit(background_image, (0, 0))

        if game_manager.state == State.SPLASH:
            success, video_image = splash_video.read()
            if success:
                video_image = cv2.resize(video_image, (Screen.WIDTH, Screen.HEIGHT))
                video_image = cv2.cvtColor(video_image, cv2.COLOR_BGR2RGB)
                video_surf = pygame.image.frombuffer(
                    video_image.tobytes(), video_image.shape[1::-1], "RGB")
            else:
                splash_video.set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, video_image = splash_video.read()
                if success:
                    video_image = cv2.cvtColor(video_image, cv2.COLOR_BGR2RGB)
                    video_surf = pygame.image.frombuffer(
                        video_image.tobytes(), video_image.shape[1::-1], "RGB")
            if video_surf:
                original_surface.blit(video_surf, (0, 0))
        elif game_manager.state == State.GAME:
            draw_game_screen(original_surface, game_manager, assets)
        elif game_manager.state == State.PAUSE:
            draw_pause_screen(original_surface, game_manager, assets)
        elif game_manager.state == State.RESULT:
            draw_result_screen(original_surface, game_manager.left_score, game_manager.right_score, assets)

        scaled_surface = pygame.transform.scale(
            original_surface, (
                pygame.display.Info().current_w,
                pygame.display.Info().current_h
            )
        )
        WINDOW.blit(scaled_surface, (0, 0))

        for event in pygame.event.get():
            if event.type == pygame.locals.KEYDOWN:
                game_manager.handle_keydown(event)
            elif event.type == pygame.locals.KEYUP:
                game_manager.handle_keyup(event)
            elif event.type == pygame.locals.QUIT:
                pygame.quit()
                sys.exit()
        pygame.display.update()
        CLOCK.tick(Game.FPS)


if __name__ == '__main__':
    pygame.init()
    if Screen.FULLSCREEN:
        WINDOW = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        WINDOW = pygame.display.set_mode((Screen.WIDTH, Screen.HEIGHT))
    pygame.display.set_caption(Game.TITLE)
    main()
