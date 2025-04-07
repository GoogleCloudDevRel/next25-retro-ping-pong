import asyncio
import dotenv
import pygame
import os
import traceback
import uuid
import logging
import datetime

from google.oauth2 import service_account
from google.cloud import logging as cloud_logging
from config import Game, Screen, State
from drawing import (
    draw_splash_screen,
    draw_game_screen,
    draw_pause_screen,
    draw_result_screen,
    update_display,
    Assets
)

from game_manager import GameManager
from pipe_manager import PipeManager, PIPE_G2V_PATH, PIPE_V2G_PATH

dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

credentials = service_account.Credentials.from_service_account_file(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))

try:
    logging_client = cloud_logging.Client(credentials=credentials)
    LOG_NAME = "paddle_bounce_game_results"
    cloud_logger = logging_client.logger(LOG_NAME)
    log.info(f"Google Cloud Logging client initialized. Will log results to: {LOG_NAME}")
except Exception as e:
    log.error(f"Failed to initialize Google Cloud Logging client: {e}", exc_info=True)
    log.warning("Game results will NOT be sent to Google Cloud Logging.")
    logging_client = None
    cloud_logger = None


def init_joysticks():
    """Initializes Pygame joysticks and returns a list of Joystick objects."""
    initialized_joysticks = [] # Create list to store initialized joysticks
    try:
        pygame.joystick.init()
        count = pygame.joystick.get_count()
        log.info(f"Pygame reports {count} joystick(s) available.")

        if count == 0:
            log.warning("No joysticks found by Pygame.")
            return initialized_joysticks # Return empty list

        for i in range(count):
            try:
                joystick = pygame.joystick.Joystick(i)
                joystick.init() # Initialize the specific joystick instance
                log.info(f"Initialized Joystick {i}: {joystick.get_name()} (Instance ID: {joystick.get_instance_id()})")
                initialized_joysticks.append(joystick) # Add the initialized object to our list
            except pygame.error as e:
                log.error(f"Failed to initialize joystick {i}: {e}")

    except pygame.error as e:
        log.error(f"Error during pygame.joystick.init(): {e}")

    # Return the list containing references to the initialized Joystick objects
    return initialized_joysticks


async def main():
    pygame.init()
    pygame.display.set_caption(Game.TITLE)
    CLOCK = pygame.time.Clock()
    active_joysticks = init_joysticks()
    if not active_joysticks:
        log.warning("Initialization returned no active joysticks. Controls may be limited.")
    log.info(f"Joystick initialization complete. {len(active_joysticks)} joystick(s) ready.")

    if Screen.FULLSCREEN:
        WINDOW = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        WINDOW = pygame.display.set_mode((Screen.WIDTH, Screen.HEIGHT))
    original_surface = pygame.Surface((Screen.WIDTH, Screen.HEIGHT))

    print("init pipe manager")

    pipe_manager = PipeManager(PIPE_G2V_PATH, PIPE_V2G_PATH)
    if not pipe_manager.setup_pipes():
        print("Exiting: Failed to set up pipes.")

    game_manager = GameManager()
    assets = Assets()

    current_game_id = None
    is_running = True
    prev_state = None

    while is_running:
        curr_state = game_manager.state
        original_surface.blit(assets.background, (0, 0))

        if curr_state == State.SPLASH:
            draw_splash_screen(original_surface, assets)
            if prev_state == State.RESULT:
                pipe_manager.send_event(f"STOP_{current_game_id}")
                current_game_id = None

        elif game_manager.state == State.GAME:
            draw_game_screen(original_surface, game_manager, assets)
            game_manager.update_paddles()
            game_manager.update_ball()

            if prev_state == State.SPLASH:  
                current_game_id = str(uuid.uuid4())
                print(f"Starting recording for game ID: {current_game_id}...")
                pipe_manager.send_event(f"START_{current_game_id}")
            elif prev_state == State.PAUSE:
                pipe_manager.send_event(f"RESUME_{current_game_id}")
                pass
        elif game_manager.state == State.PAUSE:
            draw_pause_screen(original_surface, game_manager, assets)
            if prev_state == State.GAME:
                scorer = game_manager.last_scorer
                left = game_manager.left_score
                right = game_manager.right_score
                pipe_manager.send_event(f"GOAL_{current_game_id}_{scorer}_{left}_{right}")
        elif game_manager.state == State.RESULT:
            draw_result_screen(original_surface, game_manager.left_score, game_manager.right_score, assets)
            if prev_state == State.PAUSE:
                pipe_manager.send_event(f"RESULT_{current_game_id}")
                log.info(f"Sent RESULT event for game ID: {current_game_id}")
                if cloud_logger:
                    try:
                        log_payload = {
                            "gameId": current_game_id,
                            "leftScore": game_manager.left_score,
                            "rightScore": game_manager.right_score,
                            "gameEndTimeUtc": datetime.datetime.utcnow().isoformat() + "Z"
                        }
                        cloud_logger.log_struct(log_payload, severity="INFO")
                        log.info(f"Successfully logged result for game {current_game_id} to Cloud Logging.")
                    except Exception as e:
                        log.error(f"Failed to log result for game {current_game_id} to Cloud Logging: {e}", exc_info=True)
                else:
                    log.warning(f"Cloud Logging client not available. Skipping result logging for game {current_game_id}.")

        update_display(original_surface, WINDOW)
        is_running = game_manager.handle_pygame_events()
        CLOCK.tick(Game.FPS)
        prev_state = curr_state
        curr_state = game_manager.state
        await asyncio.sleep(0)

    if pipe_manager:
        if curr_state != State.SPLASH:
            print("[GameApp] Sending final STOP event on exit.")
            pipe_manager.send_event("STOP")
        pipe_manager.close_pipes()
    if pygame.get_init():
        pygame.quit()
    print("[GameApp] Application finished.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Application interrupted. Exiting.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()
