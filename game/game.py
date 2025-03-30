import asyncio
import dotenv
import pygame.locals
import sys
import traceback
import uuid
import os
from config import Game, Screen, State
from drawing import (
    draw_splash_screen,
    draw_game_screen,
    draw_pause_screen,
    draw_result_screen,
    update_display,
    Assets
)

from audio_manager import AudioManager
from game_manager import GameManager
from gemini_manager import GeminiManager
try:
    from common.pipe_manager import PipeManager, PIPE_V2G_PATH, PIPE_G2V_PATH
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from common.pipe_manager import PipeManager, PIPE_V2G_PATH, PIPE_G2V_PATH

dotenv.load_dotenv()


async def handle_pipe_events(pipe_manager, gemini_manager: GeminiManager):
    def parse_event(event):
        try:
            video_path = event.split("_", 1)[1]
            if not os.path.exists(video_path):
                print(f"Error: Video file not found at {video_path}")
                return None
            return video_path
        except IndexError:
            print(f"Malformed COMPLETE event: Couldn't extract path from '{event}")
            return None

    received_event = pipe_manager.receive_event()
    if received_event:
        print(f"[GameApp] Received event from V2G Pipe: '{received_event}")
        if received_event.startswith("COMPLETE_") and gemini_manager:
            try:
                video_path = parse_event(received_event)
                if video_path:
                    asyncio.create_task(
                        gemini_manager.generate_content_fps_with_own_session(video_path),
                        name=f"gemini_task_{os.path.basename(video_path)}"
                    )
            except Exception as e:
                print(f"[GameApp] error occurred during event processing by GeminiManager: {e}")
                traceback.print_exc()


async def main():
    try:
        audio_manager = AudioManager()
        pygame.init()
    except Exception as e:
        print(f"Error during Pygame initialization: {e}")
        if pygame.get_init():
            pygame.quit()
        sys.exit(1)
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
    gemini_manager = GeminiManager()
    assets = Assets()

    is_recording = False
    current_game_id = None
    is_running = True

    current_audio_task = None

    while is_running:
        if not gemini_manager.is_connected() and game_manager.state in (State.GAME, State.PAUSE, State.RESULT):
            await gemini_manager.connect_gemini()
        elif gemini_manager.is_connected() and game_manager.state == State.SPLASH:
            print("State is SPLASH. Disconnecting from Gemini...")
            await gemini_manager.disconnect_gemini()
        if gemini_manager.is_connected() and not current_audio_task:
            audio_chunk = gemini_manager.receive_audio_chunks()
            current_audio_task = asyncio.create_task(
                audio_manager.play_audio(audio_chunk),
                name="audio_processing_task",
            )
            # await audio_manager.playback_finished.wait()
            # if audio_task and not audio_task.done():
            #     await audio_task

        original_surface.blit(assets.background, (0, 0))

        if game_manager.state == State.SPLASH:
            if is_recording:
                pipe_manager.send_event("STOP")
                is_recording = False
                current_game_id = None
            draw_splash_screen(original_surface, assets)
        elif game_manager.state == State.GAME:
            if not is_recording:
                current_game_id = str(uuid.uuid4())
                print(f"Starting recording for game ID: {current_game_id}...")
                pipe_manager.send_event(f"START_{current_game_id}")
                is_recording = True
            draw_game_screen(original_surface, game_manager, assets)
        elif game_manager.state == State.PAUSE:
            draw_pause_screen(original_surface, game_manager, assets)
        elif game_manager.state == State.RESULT:
            if is_recording:
                pipe_manager.send_event("STOP")
                is_recording = False
                # TODO: send to GCS: (current_game_id, game_manager.left_score, game_manager.right_score, full_video)
            draw_result_screen(original_surface, game_manager.left_score, game_manager.right_score, assets)

        update_display(original_surface, WINDOW)
        is_running = game_manager.handle_pygame_events()

        await handle_pipe_events(pipe_manager, gemini_manager)

        CLOCK.tick(Game.FPS)
        await asyncio.sleep(0)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Application interrupted. Exiting.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()
