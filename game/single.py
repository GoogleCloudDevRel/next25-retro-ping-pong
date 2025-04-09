import asyncio
import base64
import dotenv
import mss
import pygame.locals
import sys
import traceback
import uuid
from PIL import Image
import io
import time

from config import Game, Screen, State, Instruction
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

dotenv.load_dotenv()

RESIZE_FACTOR = 0.25


def capture_and_process_sync():
    with mss.mss() as sct:
        sct_img = sct.grab(sct.monitors[1])
        pillow_img = Image.frombytes('RGB', sct_img.size, sct_img.rgb)

        pillow_img = pillow_img.resize(
            (int(pillow_img.size[0] * RESIZE_FACTOR),
             int(pillow_img.size[1] * RESIZE_FACTOR))
        )
        byte_stream = io.BytesIO()
        pillow_img.save(byte_stream, format="PNG")
        return byte_stream.getvalue()


async def capture_and_send(gemini_manager, prompt, is_send_now):
    img_bytes = await asyncio.to_thread(capture_and_process_sync)
    if img_bytes:
        image_data = {
            "mime_type": "image/png",
            "data": base64.b64encode(img_bytes).decode("utf-8")
        }
        try:
            await gemini_manager.send_image(image_data)
            if is_send_now:
                print(f"Sending prompt to Gemini: {prompt[:20]}")
                await gemini_manager.send_text(prompt)
        except Exception as e:
            print(f"Error sending image to Gemini: {e}")
            traceback.print_exc()
    else:
        print("Capture failed, not sending image.")


async def stop_and_cancel_audio(audio_manager, audio_task):
    if audio_task and not audio_task.done():
        task_name = audio_task.get_name()
        print(f"Interrupting current audio task: {task_name}")
        audio_manager.stop_playback()
        audio_task.cancel()
        try:
            await asyncio.wait_for(audio_task, timeout=0.1)
        except asyncio.CancelledError:
            pass


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

    game_manager = GameManager()
    gemini_manager = GeminiManager()
    assets = Assets()

    current_game_id = None
    is_running = True
    current_audio_task = None
    capture_send_time = None
    capture_image_time = None
    prev_state = None

    while is_running:
        curr_state = game_manager.state
        curr_ticks = pygame.time.get_ticks()

        if current_audio_task and current_audio_task.done():
            task_name = current_audio_task.get_name()
            try:
                current_audio_task.result()
                print(f"Audio task '{task_name}' completed successfully.")
            except asyncio.CancelledError:
                print(f"Audio task '{task_name}' was cancelled.")
            except Exception as e:
                print(f"Audio task '{task_name}' failed: {e}")
                # traceback.print_exc()
            current_audio_task = None

        if not gemini_manager.is_connected() and curr_state in (State.GAME, State.PAUSE, State.RESULT):
            await gemini_manager.connect_gemini()

        original_surface.blit(assets.background, (0, 0))

        if curr_state == State.SPLASH:
            draw_splash_screen(original_surface, assets)
            if gemini_manager.is_connected():
                print("State is SPLASH. Disconnecting from Gemini...")
                await stop_and_cancel_audio(audio_manager, current_audio_task)
                current_audio_task = None
                await gemini_manager.disconnect_gemini()
            if prev_state == State.RESULT:
                print("re-init game...")
                capture_send_time = None
                capture_image_time = None

        elif curr_state == State.GAME:
            draw_game_screen(original_surface, game_manager, assets)
            game_manager.update_paddles()
            game_manager.update_ball()

            if not capture_image_time or not capture_send_time:
                capture_image_time = curr_ticks
                capture_send_time = curr_ticks

            # case: splash -> game
            if prev_state == State.SPLASH:
                curr_game_id = str(uuid.uuid4())
                # capture_task = asyncio.create_task(
                #     capture_and_send(gemini_manager, Instruction.PROMPT_START, True)
                # )
                await capture_and_send(gemini_manager, Instruction.PROMPT_START, True)
                audio_generator = gemini_manager.receive_audio_chunks()
                sound_chunk = await audio_manager.process_audio(audio_generator)
                if sound_chunk:
                    await stop_and_cancel_audio(audio_manager, current_audio_task)
                    task_name = f"play_interrupt_{int(time.time())}"
                    current_audio_task = asyncio.create_task(audio_manager.play(sound_chunk), name=task_name)
                else:
                    print("Failed to process START audio chunk.")

            if capture_send_time and curr_ticks - capture_send_time >= 10000:
                # capture one image, send and end_of_turn
                capture_send_time = curr_ticks
                capture_image_time = curr_ticks
                # capture_task = asyncio.create_task(
                #     capture_and_send(gemini_manager, Instruction.PROMPT_RALLY, True)
                # )
                await capture_and_send(gemini_manager, Instruction.PROMPT_RALLY, True)
                audio_generator = gemini_manager.receive_audio_chunks()
                sound_chunk = await audio_manager.process_audio(audio_generator)
                if sound_chunk:
                    await stop_and_cancel_audio(audio_manager, current_audio_task)
                    task_name = f"play_interrupt_{int(time.time())}"
                    current_audio_task = asyncio.create_task(audio_manager.play(sound_chunk), name=task_name)
                else:
                    print("Failed to process RALLY audio chunk.")

            elif capture_image_time and curr_ticks - capture_image_time >= 1000:
                # capture one image, send and not end_of_turn
                capture_image_time = curr_ticks
                # capture_task = asyncio.create_task(
                #     capture_and_send(gemini_manager, None, False)
                # )
                await capture_and_send(gemini_manager, None, False)

        elif curr_state == State.PAUSE:
            draw_pause_screen(original_surface, game_manager, assets)
            if capture_image_time and curr_ticks - capture_image_time >= 1000:
                capture_image_time = None
                capture_send_time = None
                # capture_task = asyncio.create_task(
                #     capture_and_send(gemini_manager, Instruction.PROMPT_GOAL, True)
                # )
                await capture_and_send(gemini_manager, Instruction.PROMPT_GOAL, True)
                audio_generator = gemini_manager.receive_audio_chunks()
                sound_chunk = await audio_manager.process_audio(audio_generator)
                if sound_chunk:
                    await stop_and_cancel_audio(audio_manager, current_audio_task)
                    task_name = f"play_interrupt_{int(time.time())}"
                    current_audio_task = asyncio.create_task(audio_manager.play(sound_chunk), name=task_name)
                else:
                    print("Failed to process GOAL audio chunk.")

        elif curr_state == State.RESULT:
            draw_result_screen(original_surface, game_manager.left_score, game_manager.right_score, assets)
            if prev_state == State.PAUSE and not capture_image_time:
                capture_image_time = curr_ticks

            if capture_image_time and curr_ticks - capture_image_time >= 1000:
                capture_image_time = None
                capture_send_time = None
                # capture_task = asyncio.create_task(
                #     capture_and_send(gemini_manager, Instruction.PROMPT_RESULT, True)
                # )
                await capture_and_send(gemini_manager, Instruction.PROMPT_RESULT, True)
                audio_generator = gemini_manager.receive_audio_chunks()
                sound_chunk = await audio_manager.process_audio(audio_generator)
                if sound_chunk:
                    await stop_and_cancel_audio(audio_manager, current_audio_task)
                    task_name = f"play_interrupt_{int(time.time())}"
                    current_audio_task = asyncio.create_task(audio_manager.play(sound_chunk), name=task_name)
                else:
                    print("Failed to process RESULT audio chunk.")
                
            # TODO: send to GCS: (current_game_id, game_manager.left_score, game_manager.right_score, full_video)
        update_display(original_surface, WINDOW)
        is_running = game_manager.handle_pygame_events()
        CLOCK.tick(Game.FPS)
        prev_state = curr_state
        curr_state = game_manager.state
        await asyncio.sleep(0)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Application interrupted. Exiting.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()
