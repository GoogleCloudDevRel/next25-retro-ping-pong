import sys
import dotenv
import pygame.locals

from config import State, WINDOW, CLOCK
from drawing import *
from game_manager import GameManager

dotenv.load_dotenv()


def main():
    game_manager = GameManager()

    while True:
        WINDOW.fill(Color.BLACK)

        if game_manager.state == State.SPLASH:
            draw_splash_screen(WINDOW)
        elif game_manager.state == State.SELECT:
            pass
        elif game_manager.state == State.GAME:
            draw_score_pane(WINDOW, game_manager)
            draw_game_pane(WINDOW, game_manager)
            draw_log_pane(WINDOW)
            game_manager.update_paddles()
            game_manager.update_ball()
        elif game_manager.state == State.PAUSE:
            draw_pause_screen(WINDOW, game_manager)
        elif game_manager.state == State.RESULT:
            left_score = game_manager.left_score
            right_score = game_manager.right_score
            draw_result_screen(WINDOW, left_score, right_score)

        for event in pygame.event.get():
            if event.type == pygame.locals.KEYDOWN:
                game_manager.game_state = game_manager.handle_keydown(event)
            elif event.type == pygame.locals.KEYUP:
                game_manager.handle_keyup(event)
            elif event.type == pygame.locals.QUIT:
                pygame.quit()
                sys.exit()
        pygame.display.update()
        CLOCK.tick(Game.FPS)


if __name__ == '__main__':
    main()
