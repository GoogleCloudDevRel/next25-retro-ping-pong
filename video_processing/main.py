import asyncio
import time
import json
import dotenv
import pyaudio
from google.cloud import pubsub_v1
from gemini import GeminiManager
from obs_manager import ObsManager
from file_manager import FileManager
from config import Gemini

from google import genai

# Google Cloud Pub/Sub settings
PROJECT_ID = "data-connect-interactive-demo"
SUBSCRIPTION_ID = "game_events-sub"
RECORDING_INTERVAL = 6

dotenv.load_dotenv()


def callback(
    message: pubsub_v1.subscriber.message.Message, obs_manager: ObsManager
):
    """Callback function to handle Pub/Sub messages."""
    try:
        data = json.loads(message.data.decode())
        event_type = data.get("event_type")
        print(f"Received message: data={data}, event_type={event_type}")
        if event_type == "RECORDING_START":
            print("Received RECORDING_START event")
            obs_manager.start_recording()
        elif event_type == "RECORDING_STOP":
            print("Received RECORDING_STOP event")
            obs_manager.stop_recording()
        message.ack()
    except Exception as e:
        print(f"Error processing message: {e}")
        message.nack()


async def main():
    """Sets up Pub/Sub subscription, manages recording, and monitors files."""
    gemini_aio_client = genai.Client(http_options={"api_version": "v1alpha"})
    pya = pyaudio.PyAudio()

    obs_manager = ObsManager()
    if not obs_manager.connect():
        return

    file_manager = FileManager()

    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)
    streaming_pull_future = subscriber.subscribe(
        subscription_path, callback=lambda msg: callback(msg, obs_manager)
    )
    print(f"Listening for messages on {subscription_path}...\n")

    try:
        async with(gemini_aio_client.aio.live.connect(
            model=Gemini.MODEL, config=Gemini.CONFIG
        ) as session):
            gemini_manager = GeminiManager(session, pya)
            with subscriber:
                while True:
                    if obs_manager.is_recording:
                        elapsed_time = time.time() - (obs_manager.recording_timer or time.time())
                        if elapsed_time >= RECORDING_INTERVAL:
                            obs_manager._update_recording_status()
                            if obs_manager.is_recording:
                                obs_manager._restart_recording()
                    completed_file = file_manager.monitor_folder()
                    if completed_file:
                        print(f"Completed file (in main loop): {completed_file}")
                        await gemini_manager.analyze_video(gemini_aio_client, completed_file)
                    time.sleep(0.5)  # OBS check interval.

    except TimeoutError:
        print("Timeout occurred.")
        streaming_pull_future.cancel()
    except KeyboardInterrupt:
        print("Interrupted. Exiting.")
        streaming_pull_future.cancel()
    except Exception as e:
        print(f"An error occurred: {e}")
        streaming_pull_future.cancel()


if __name__ == "__main__":
    asyncio.run(main())
