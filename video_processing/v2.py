import cv2
import time
import os
import json
from google.cloud import pubsub_v1
from concurrent.futures import TimeoutError
from google.api_core.exceptions import AlreadyExists


class VideoProcessor:
    def __init__(self):
        self.project_id = "data-connect-interactive-demo"
        self.subscription_id = "game_events-sub"
        self.output_dir = "videos"
        self.chunk_duration = 7
        self.fps = 20
        self.width = 960
        self.height = 540

        os.makedirs(self.output_dir, exist_ok=True)
        self.subscriber = pubsub_v1.SubscriberClient()
        self.subscription_path = self.subscriber.subscription_path(
            self.project_id, self.subscription_id
        )
        self.cap = None
        self.recording = False
        self.full_out = None
        self.chunk_out = None
        self.start_time = 0
        self.chunk_start_time = 0
        self.segment_count = 0
        self.full_video_filename = None

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
        chunk_filename = os.path.join(self.output_dir, f"segment_{self.segment_count}_{timestamp}.mp4")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        if self.chunk_out:
            self.chunk_out.release()
        self.chunk_out = cv2.VideoWriter(chunk_filename, fourcc, self.fps, (self.width, self.height))
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

        if time.time() - self.chunk_start_time >= self.chunk_duration:
            self._init_chunk_video_writer()
            self.chunk_start_time = time.time()

    def callback(self, message):
        try:
            data_str = message.data.decode("utf-8")

            if not data_str:
                print("Received empty message.")
                message.ack()
                return

            data = json.loads(data_str)
            print(f"Received message: {data}, type: {type(data)}")

            if not isinstance(data, dict):
                print(f"Error: Expected a dictionary, but got: {type(data)}")
                message.nack()
                return

            event_type = data.get("event_type")
            print(f"Received message: {data}")

            if event_type == "RECORDING_START":
                self.start_recording()
                message.ack()
            elif event_type == "RECORDING_STOP":
                self.stop_recording()
                message.ack()
            else:
                print(f"Unknown event type: {event_type}")
                message.nack()
        except Exception as e:
            print(f"Error processing message: {e}")
            message.nack()

    def run(self):
        try:
            self.subscriber.create_subscription(
                request={
                    "name": self.subscription_path,
                    "topic": f"projects/{self.project_id}/topics/game_events"
                }
            )
        except AlreadyExists:
            pass

        streaming_pull_future = self.subscriber.subscribe(
            self.subscription_path, callback=self.callback
        )
        print(f"Listening for messages on {self.subscription_path}...")

        try:
            while True:
                self.process_frame()
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("Shutting down...")
            self.stop_recording()
            streaming_pull_future.cancel()
        except TimeoutError:
            print("Timeout while pulling messages.")
            self.stop_recording()
            streaming_pull_future.cancel()
        except Exception as e:
            print(f"An error occurred: {e}")
            self.stop_recording()
            streaming_pull_future.cancel()

        streaming_pull_future.result()


if __name__ == "__main__":
    processor = VideoProcessor()
    processor.run()
