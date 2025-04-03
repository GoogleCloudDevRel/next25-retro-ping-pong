import asyncio
import base64
import dotenv
import pygame.locals
import traceback
import uuid
import logging

from config import Game, Screen, State
from drawing import (
    draw_splash_screen,
    draw_game_screen,
    draw_pause_screen,
    draw_result_screen,
    update_display,
    Assets
)

from audio_manager import AudioPlayer
from game_manager import GameManager
from pipe_manager import PipeManager, PIPE_G2V_PATH, PIPE_V2G_PATH

dotenv.load_dotenv()
log = logging.getLogger(__name__)


async def handle_pipe_events(pipe_manager, audio_player):
    received_event = pipe_manager.receive_event()

    if not received_event:
        return
    # log.debug(f"Received event from V2G Pipe: '{received_event[:100]}'...")

    log_event = received_event[:150] + "..." if len(received_event) > 150 else received_event
    log.debug(f"Received event from V2G Pipe: '{log_event}'")

    if not audio_player or not audio_player.stream:
        log.warning(f"AudioPlayer not available, cannot process event: '{log_event}'")
        return

    try:
        if received_event.startswith("AUDIO_START_"):
            log.info("Received AUDIO_START event. Preparing for new audio stream.")
            audio_player.stop_and_clear_queue()

            log.debug("Requested audio player to stop and clear queue.")

        elif received_event.startswith("CHUNK_"):
            log.debug("Received CHUNK event.")
            try:
                encoded_data = received_event.split("_", 1)[1]
                data_bytes = base64.b64decode(encoded_data.encode('ascii'))
                log.debug(f"Decoded {len(data_bytes)} bytes of audio data.")

                await audio_player.add_to_queue(data_bytes)
                log.debug("Added audio chunk to player queue.")

            except (IndexError, ValueError, base64.binascii.Error) as e:
                log.error(f"Failed to parse or decode CHUNK data: {received_event[:100]}... Error: {e}")
            except Exception as e:
                 log.error(f"Error handling CHUNK data bytes: {e}", exc_info=True)

        elif received_event.startswith("AUDIO_END_"):
            log.info("Received AUDIO_END event.")
            await audio_player.signal_stream_end()
            log.debug("Signaled end of audio stream to player.")

        else:
            log.warning(f"Received unknown or unhandled event format: {received_event[:100]}...")

    except Exception as e:
        log.error(f"Error processing event '{received_event[:100]}...': {e}", exc_info=True)


async def main():
    pygame.init()
    pygame.display.set_caption(Game.TITLE)
    CLOCK = pygame.time.Clock()

    if Screen.FULLSCREEN:
        WINDOW = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        WINDOW = pygame.display.set_mode((Screen.WIDTH, Screen.HEIGHT))
    original_surface = pygame.Surface((Screen.WIDTH, Screen.HEIGHT))

    pipe_manager = PipeManager(PIPE_G2V_PATH, PIPE_V2G_PATH)
    if not pipe_manager.setup_pipes():
        print("Exiting: Failed to set up pipes.")

    game_manager = GameManager()
    audio_player = AudioPlayer()
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
                # TODO: send RESUME
                pass
        elif game_manager.state == State.PAUSE:
            draw_pause_screen(original_surface, game_manager, assets)
            if prev_state == State.GAME:
                pipe_manager.send_event(f"GOAL_{current_game_id}")
        elif game_manager.state == State.RESULT:
            draw_result_screen(original_surface, game_manager.left_score, game_manager.right_score, assets)
            # if prev_state == State.PAUSE:
            #     pipe_manager.send_event(f"STOP_{current_game_id}")
                # TODO: send to GCS: (current_game_id, game_manager.left_score, game_manager.right_score, full_video)

        update_display(original_surface, WINDOW)
        is_running = game_manager.handle_pygame_events()
        await handle_pipe_events(pipe_manager, audio_player)
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
