import os
import sys
import traceback
import base64


import dotenv
import pyaudio
from google import genai
import pygame.locals
import asyncio

import video
from config import State, CLOCK, Gemini
from drawing import *
from game_manager import GameManager
from gemini import GeminiManager
from video import create_video, make_screenshot
import cv2

from google.genai import types

dotenv.load_dotenv()


async def main():
    client = genai.Client(http_options={"api_version": "v1alpha"})
    game_manager = GameManager()
    assets = Assets()
    last_video_frame = 0
    is_score_recorded = False
    render_count = 0

    background_image = assets.background

    splash_video = assets.splash_video
    video_surf = None

    try:
        async with(client.aio.live.connect(
            model=Gemini.MODEL, config=Gemini.CONFIG
        ) as session):
            gemini_manager = GeminiManager(session, game_manager, pya)

            async def process_video(task):
                try:
                    video_result = await task
                    if video_result:
                        await gemini_manager.analyze_video(client, video_result)
                except Exception as e:
                    print(e)

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
                    if not os.path.exists("images"):
                        os.makedirs("images")
                    for file in os.listdir("images"):
                        os.remove(os.path.join("images", file))
                    if not os.path.exists("videos"):
                        os.makedirs("videos")
                    for file in os.listdir("videos"):
                        os.remove(os.path.join("videos", file))
                elif game_manager.state == State.SELECT:
                    pass
                elif game_manager.state == State.GAME:
                    if is_score_recorded:
                        is_score_recorded = False

                    draw_game_screen(original_surface, game_manager, assets)

                    if render_count % 2 == 0:
                        make_screenshot(original_surface, game_manager.frame)
                        game_manager.frame += 1

                    if game_manager.frame - last_video_frame >= (Game.FPS * 5) // 2:
                        print("5 seconds")
                        asyncio.create_task(
                            create_video(
                                last_video_frame, game_manager.frame - 1
                            )).add_done_callback(
                            lambda task: asyncio.create_task(process_video(task)))
                        last_video_frame = game_manager.frame
                elif game_manager.state == State.PAUSE or game_manager.state == State.RESULT:
                    if game_manager.state == State.PAUSE:
                        draw_pause_screen(original_surface, game_manager, assets)
                    else:
                        draw_result_screen(original_surface, game_manager.left_score, game_manager.right_score, assets)

                    if not is_score_recorded:
                        make_screenshot(original_surface, game_manager.frame)
                        image_path = f"images/frame_{game_manager.frame:04}.png"
                        video_path = f"videos/single_frame_{game_manager.frame:04}.mp4"
                        video.create_video_from_single_image(image_path, video_path)

                        async def process_single_image_video():
                            try:
                                with open(video_path, "rb") as f:
                                    video_bytes = f.read()
                                    await gemini_manager.analyze_video(client, types.Content(parts=[types.Part(
                                        inline_data=types.Blob(
                                            data=base64.b64encode(video_bytes).decode("utf-8"),
                                            mime_type="video/mp4",
                                        )
                                    )]))
                            except Exception as e:
                                print("Error processing single image video: {e}")
                        asyncio.create_task(process_single_image_video())

                        game_manager.frame += 1
                        last_video_frame = game_manager.frame
                        is_score_recorded = True

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
                render_count += 1
                await asyncio.sleep(0)
    except ExceptionGroup as EG:
        traceback.print_exception(EG)


if __name__ == '__main__':
    pygame.init()
    pygame.mixer.init()
    pya = pyaudio.PyAudio()
    if Screen.FULLSCREEN:
        WINDOW = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        WINDOW = pygame.display.set_mode((Screen.WIDTH, Screen.HEIGHT))
    pygame.display.set_caption(Game.TITLE)
    asyncio.run(main())
    pya.terminate()
