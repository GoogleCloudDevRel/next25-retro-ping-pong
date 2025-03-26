import asyncio
import stat
import time
import dotenv
import pyaudio
import os
import sys
import atexit
import functools

from gemini_manager import GeminiManager
from obs_manager import ObsManager
from file_manager import FileManager
from config import Gemini, Instruction

from google import genai

RECORDING_INTERVAL = 5
PIPE_PATH = "/tmp/paddlebounce_pipe"

dotenv.load_dotenv()


def cleanup_pipe(path):
    try:
        if os.path.exists(path):
            os.remove(path)
            print(f"Cleaned up pipe: {path}")
    except Exception as e:
        print(f"Error cleaning up pipe {path}: {e}")


def read_pipe_sync(pipe_path, obs_manager, loop):
    print(f"Pipe reader thread started. Listening on {pipe_path}...")
    try:
        with open(pipe_path, 'r') as pipe_file:
            while True:
                line = pipe_file.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                command = line.strip()
                print(f"Pipe reader:Received command: '{command}'")
                if command == "START":
                    future = asyncio.run_coroutine_threadsafe(
                        obs_manager.async_start_recording(), loop
                    )
                    print("Pipe reader: Scheduled async_start_recording.")
                elif command == "STOP":
                    future = asyncio.run_coroutine_threadsafe(
                        obs_manager.async_stop_recording(), loop
                    )
                    print("Pipe reader: Scheduled async_stop_recording.")
    except FileNotFoundError:
        print(f"Pipe reader thread: Error - Pipe '{pipe_path}' was likely removed unexpectedly.", file=sys.stderr)
    except Exception as e:
        print(f"Pipe reader thread: An error occurred:{e}", file=sys.stderr)
    finally:
        print("Pipe reader thread finished")


async def main():
    if not os.path.exists(PIPE_PATH):
        try:
            os.mkfifo(PIPE_PATH)
            print(f"Created named pipe: {PIPE_PATH}")
        except OSError as e:
            print(f"Failed to create named pipe: {e}", file=sys.stderr)
            return
    else:
        if not stat.S_ISFIFO(os.stat(PIPE_PATH).st_mode):
            print(f"Error: {PIPE_PATH} exists but is not a FIFO pipe.", file=sys.stderr)
            try:
                os.remove(PIPE_PATH)
                os.mkfifo(PIPE_PATH)
                print(f"Removed existing file and created named pipe:{PIPE_PATH}")
            except OSError as e:
                print(f"Failed to recreated named pipe: {e}", file=sys.stderr)
                return
        else:
            print(f"Named pipe {PIPE_PATH} already exists. Using it.")
    atexit.register(cleanup_pipe, PIPE_PATH)

    segment_complete_event = asyncio.Event()

    gemini_aio_client = genai.Client(http_options={"api_version": "v1alpha"})
    pya = pyaudio.PyAudio()

    obs_manager = ObsManager(segment_complete_event=segment_complete_event)
    if not await obs_manager.async_connect():
        print("Exiting due to OBS connection failure.")
        return

    file_manager = FileManager(segment_complete_event=segment_complete_event)
    loop = asyncio.get_running_loop()
    pipe_reader_task = loop.run_in_executor(
        None,
        functools.partial(read_pipe_sync, PIPE_PATH, obs_manager, loop)
    )

    try:
        async with(gemini_aio_client.aio.live.connect(
            model=Gemini.MODEL, config=Gemini.CONFIG
        ) as session):
            gemini_manager = GeminiManager(session, pya)
            await gemini_manager.initialize()

            while True:
                completed_file = await file_manager.wait_for_completed_file()
                if completed_file:
                    print(f"Main loop: Processing completed file: {completed_file}")
                    asyncio.create_task(
                        gemini_manager.analyze_video(gemini_aio_client, completed_file)
                    )
                else:
                    print("Main loop:Signal received, but no file returned by FileManager.")

                if obs_manager.is_recording:
                    timer_start = obs_manager.recording_timer
                    if timer_start and (time.time() - timer_start >= RECORDING_INTERVAL):
                        print(f"Recording interval ({RECORDING_INTERVAL}s) reached (approx).")
                        if obs_manager.is_recording:
                            print("Initiating async recording restart...")
                            asyncio.create_task(obs_manager.async_restart_recording())
                        else:
                            print("Recording stopped betweel interval check and restart attempt.")
                await asyncio.sleep(0.1)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Shutting down.")
    except Exception as e:
        print(f"\nAn unexpected error occurred in the main loop: {e}")
    finally:
        print("Starting cleanup...")
        if obs_manager.is_connected:
            print("Disconnecting from OBS...")
            await obs_manager.async_disconnect()
        if pya:
            print("Terminating PyAudio...")
            pya.terminate()
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if tasks:
            print(f"Cancelling {len(tasks)} outstanding tasks...")
            [task.cancel() for task in tasks]
            await asyncio.gather(*tasks, return_exceptions=True)
        print("Cleanup complete. Exiting.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting before main loop started.")
