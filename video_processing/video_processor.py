import cv2
import time
import os
import json
import asyncio
from google.cloud import pubsub_v1
from concurrent.futures import TimeoutError
from google.api_core.exceptions import AlreadyExists


class VideoProcessor:
    def __init__(self, segment_duration=7, width=1920, height=1080, fps=24):
        self.segment_duration = segment_duration
        self.width = width
        self.height = height
        self.fps = fps

        self.output_dir = "videos"
        os.makedirs(self.output_dir, exist_ok=True)

        self.cap = None
        self.recording = False
        self.full_out = None
        self.chunk_out = None
        self.start_time = 0
        self.chunk_start_time = 0
        self.segment_count = 0
        self.full_video_filename = None
        self.segment_completed_callback = None

    def set_segment_completed_callback(self, callback):
        self.segment_completed_callback = callback

    def _init_capture(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("Error:Could not open video capture device.")
            return False
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        return True

    def _init_full_video_writer(self):
        timestamp = str(round(time.time() * 1000))
        self.full_video_filename = os.path.join(
            self.output_dir, f"full_video_{timestamp}.mp4"
        )
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # 또는 'H264', 'XVID' 등
        self.full_out = cv2.VideoWriter(
            self.full_video_filename, fourcc, self.fps, (self.width, self.height)
        )
        return self.full_out is not None

    def _init_chunk_video_writer(self):
        self.segment_count += 1
        timestamp = str(round(time.time() * 1000))
        chunk_filename = os.path.join(
            self.output_dir,
            f"segment_{self.segment_count}_{timestamp}.mp4"
        )
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        if self.chunk_out:
            self.chunk_out.release()
        self.chunk_out = cv2.VideoWriter(
            chunk_filename, fourcc, self.fps, (self.width, self.height)
        )
        return self.chunk_out is not None

    def _release_resources(self):
        if self.full_out:
            self.full_out.release()
            self.full_out = None
        if self.chunk_out:
            self.chunk_out.release()
            self.chunk_out = None
        if self.cap:
            self.cap.release()
            self.cap = None

    def _save_last_chunk(self):
        if self.chunk_out:
            self.chunk_out.release()
            self.chunk_out = None

    def start_recording(self):
        if self.recording:
            print("Already recording.")
            return

        if not self._init_capture():
            return

        if not self._init_full_video_writer():
            print("Error: Could not initialize full video writer.")
            self._release_resources()
            return

        self.segment_count = 0
        if not self._init_chunk_video_writer():
            print("Error initializing chunk video writer.")
            self._release_resources()
            return

        self.start_time = time.time()
        self.chunk_start_time = self.start_time
        self.recording = True
        print("Recording started.")

    def stop_recording(self):
        if not self.recording:
            print("Not recording.")
            return

        self.recording = False
        self._save_last_chunk()
        self._release_resources()
        self.segment_count = 0
        print("Recording stopped.")

    def process_frame(self):
        if not self.recording or not self.cap or not self.cap.isOpened():
            return

        ret, frame = self.cap.read()
        if not ret:
            print("Error: Could not read frame. Stopping recording.")
            self.stop_recording()
            return

        if self.full_out:
            self.full_out.write(frame)
        if self.chunk_out:
            self.chunk_out.write(frame)

        if time.time() - self.chunk_start_time >= self.segment_duration:
            chunk_filename = self._init_chunk_video_writer()
            self.chunk_start_time = time.time()
            if chunk_filename and self.segment_completed_callback:
                self.segment_completed_callback(chunk_filename)
