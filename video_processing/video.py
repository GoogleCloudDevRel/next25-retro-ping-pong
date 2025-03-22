import base64
import os
import asyncio
from datetime import datetime
import subprocess
from google.genai import types
from game.config import Game
import pygame


IMAGE_DIR = "images"
VIDEO_DIR = "videos"


def make_screenshot(canvas, frame_count):
    filename = os.path.join(IMAGE_DIR, f"frame_{frame_count:04d}.png")
    pygame.image.save(canvas, filename)
    with open(filename, "rb") as image_file:
        image_bytes = image_file.read()
    return {
        "mime_type": "image/png",
        "data": base64.b64encode(image_bytes).decode("utf-8")
    }


def create_video_from_single_image(image_path, output_path, duration=1, fps=Game.FPS):
    command = [
        "ffmpeg",
        "-y",  # Overwrite output file if it exists
        "-loop", "1",  # Loop the input image
        "-i", image_path,
        "-c:v", "libx264",
        "-t", str(duration),  # Set the duration
        "-pix_fmt", "yuv420p",
        "-vf", f"fps={fps}",  # Set the frame rate
        output_path
    ]

    try:
        subprocess.run(command, check=True, capture_output=True)
        print(f"Video created successfully: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error creating video: {e}")
        print(f"ffmpeg output: {e.output.decode()}")


async def create_video(start_frame, end_frame):
    try:
        now = datetime.now()
        output_filename = os.path.join(VIDEO_DIR, f"game_{now.strftime('%Y%m%d_%H%M%S_%f')}.mp4")
        print(f"Creating video: {output_filename} from frame {start_frame} to {end_frame}")

        if not os.path.exists(VIDEO_DIR):
            os.makedirs(VIDEO_DIR)

        command = [
            "ffmpeg",
            "-framerate", str(Game.FPS),
            "-start_number", str(start_frame),
            "-i", os.path.join(IMAGE_DIR, "frame_%04d.png"),
            "-frames:v", str(end_frame - start_frame + 1),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_filename
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        async def read_stream(stream):
            while True:
                line = await stream.readline()
                if not line:
                    break

        asyncio.create_task(read_stream(process.stdout))
        asyncio.create_task(read_stream(process.stderr))
        await process.wait()

        if process.returncode == 0:
            with open(output_filename, "rb") as f:
                video_data = f.read()
            return types.Content(parts=[types.Part(
                inline_data=types.Blob(
                    data=base64.b64encode(video_data).decode("utf-8"),
                    mime_type="video/mp4",
                )
            )])
        else:
            print(f"Error creating video using ffmpeg (Return code: {process.returncode}):")
            return None
    except FileNotFoundError:
        print("Error: ffmpeg command not found. Please ensure ffmpeg is installed and in your system's PATH.")
        return None
    except Exception as e:
        print(f"An error occurred during video creation: {e}")
        return None
