import sys
import traceback

import dotenv
import asyncio
from google import genai
import pygame.locals

from config import State, WINDOW, CLOCK
from drawing import *
from game_manager import GameManager
from gemini import GeminiManager

dotenv.load_dotenv()

MODEL = "models/gemini-2.0-flash-exp"
client = genai.Client(http_options={"api_version": "v1alpha"})
instruction = "You are a high-energy, concise sports commentator providing *very short*, real-time updates for a game. Think fast-paced radio broadcast! \
            **Game Setup:** \
            * **Game name:** Paddle Bounce \
            * **Players:** Player 1 (left), Player 2 (right) - using green paddles. \
            * **Objective:** Hit the red ball with your paddle past the opponent's side to score \
            * **Score:** Displayed at the top (Player 1 : Player 2). \
            **Task:** \
            Provide a *brief* and exciting commentary for each *5-second* gameplay clip. Focus on the *most important* actions within that short time frame. \
            Specifically highlight: \
                * **Ball Movement:**  Direction, speed, and changes in momentum. \
                * **Player Actions (Implied):**  Assume players are trying to hit the ball with paddles.  Describe their *attempts* to control the ball, even if unseen. \
                * **Current Score:**  Mention only if it changes *within* the 5-second clip.\
                * **Excitement & Key Moments:**  Emphasize any fast movements, near misses, or shifts in ball control that are exciting *within the 5 seconds*.\
                **Tone:**  Extremely energetic, enthusiastic, and *concise*.  Think rapid-fire sports commentary.  Every word counts! \
            **Important:** Keep the commentary *very short* and to the point for each 5-second clip.  Imagine you have only a few seconds to capture the action before the next clip comes in. \
                Focus on the *highlights* of each 5-second burst of gameplay."
CONFIG = {
    "generation_config": {"response_modalities": ["AUDIO"]},
    "system_instruction": instruction,
}


async def main():
    game_manager = GameManager()
    try:
        async with(client.aio.live.connect(model=MODEL, config=CONFIG) as session):
            gemini_manager = GeminiManager(session, game_manager)

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

                    image_bytes = make_screenshot(WINDOW, game_manager.frame)
                    asyncio.create_task(gemini_manager.send_image(image_bytes))
                    game_manager.frame += 1
                    if game_manager.frame == 120:
                        asyncio.create_task(gemini_manager.send_now())
                        game_manager.frame = 0
                elif game_manager.state == State.PAUSE:
                    draw_pause_screen(WINDOW, game_manager)
                    asyncio.create_task(gemini_manager.send_image(image_bytes))
                    if game_manager.frame > 0:
                        asyncio.create_task(gemini_manager.send_now())
                        game_manager.frame = 0
                elif game_manager.state == State.RESULT:
                    left_score = game_manager.left_score
                    right_score = game_manager.right_score
                    draw_result_screen(WINDOW, left_score, right_score)
                    asyncio.create_task(gemini_manager.send_image(image_bytes))
                    if game_manager.frame > 0:
                        asyncio.create_task(gemini_manager.send_now())
                        game_manager.frame = 0

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
                await asyncio.sleep(0)
    except ExceptionGroup as EG:
        traceback.print_exception(EG)


if __name__ == '__main__':
    asyncio.run(main())
