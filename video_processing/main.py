import asyncio
import base64
import json
import os
import traceback

from google.cloud import pubsub_v1
from concurrent.futures import TimeoutError
from google.api_core.exceptions import AlreadyExists

import dotenv
import pyaudio
from google import genai
from google.genai import types

from config import Gemini, Instruction, Cloud

from gemini import GeminiManager
from video_processor import VideoProcessor
import pyaudio

dotenv.load_dotenv()


async def main():
    client = genai.Client(http_options={"api_version": "v1alpha"})
    pya = pyaudio.PyAudio()
    video_processor = VideoProcessor(
        segment_duration=7, width=960, height=540, fps=24,
    )

    try:
        async with (client.aio.live.connect(
            model=Gemini.MODEL, config=Gemini.CONFIG
        ) as session):
            loop = asyncio.get_running_loop()
            gemini_manager = GeminiManager(session, pya, loop)
            await gemini_manager.start_tasks()

            def segment_completed_callback(video_path):
                process_segment(video_path)

            video_processor.set_segment_completed_callback(
                segment_completed_callback
            )

            def process_segment(video_path):
                print(f"Processing segment: {video_path}")
                try:
                    with open(video_path, "rb") as f:
                        video_bytes = f.read()
                        video_content = types.Content(
                            parts=[
                                types.Part(
                                    inline_date=types.Blob(
                                        data=base64.b64encode(video_bytes).decode(
                                            "utf-8"
                                        ),
                                        mime_type="video/mp4",
                                    )
                                )
                            ]
                        )
                    asyncio.create_task(
                        gemini_manager.analyze_video(client, video_content)
                    )
                except Exception as e:
                    print(f"Error processing segment {video_path}: {e}")

            def pubsub_callback(message):
                try:
                    data_str = message.data.decode("utf-8")
                    data = json.loads(data_str)
                    event_type = data.get("event_type")

                    if event_type == "RECORDING_START":
                        video_processor.start_recording()
                        message.ack()
                    elif event_type == "RECORDING_STOP":
                        video_processor.stop_recording()
                        message.ack()
                    else:
                        print(f"Unknown event type: {event_type}")
                        message.nack()

                except Exception as e:
                    print(f"Error processing message: {e}")
                    message.nack()

            sub = pubsub_v1.SubscriberClient()
            sub_path = sub.subscription_path(Cloud.PROJECT_ID, Cloud.SUB_ID)

            try:
                sub.create_subscription(
                    request={
                        "name": sub_path,
                        "topic": f"projects/{Cloud.PROJECT_ID}/topics/game_events"
                    }
                )
            except AlreadyExists:
                pass

            streaming_pull_future = sub.subscribe(
                sub_path, callback=pubsub_callback
            )
            print(f"Listening for messages on {sub_path}...")

            try:
                while True:
                    video_processor.process_frame()
                    await asyncio.sleep(0.05)
            except KeyboardInterrupt:
                print("Shutting down...")
            except TimeoutError:
                print("Timeout while pulling messages.")
            except Exception as e:
                print(f"An error occurred: {e}")
            finally:
                video_processor.stop_recording()
                streaming_pull_future.cancel()
                streaming_pull_future.result(timeout=5)
                await gemini_manager.cancel_tasks()
    except ExceptionGroup as EG:
        traceback.print_exception(EG)
    finally:
        pya.terminate()

if __name__ == "__main__":
    asyncio.run(main())
