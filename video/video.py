import cv2
import time
import datetime
import os
import threading
import traceback
try:
    from common.pipe_manager import PipeManager, PIPE_V2G_PATH, PIPE_G2V_PATH
except ImportError:
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from common.pipe_manager import PipeManager, PIPE_V2G_PATH, PIPE_G2V_PATH

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)

CAPTURE_DEVICE_INDEX = 0
INTERVAL = 10  # Seconds

CLIP_OUTPUT_DIR = os.path.join(PARENT_DIR, "recordings_short_clips")
FULL_OUTPUT_DIR = os.path.join(PARENT_DIR, "recordings_full_game")

VIDEO_EXTENSION = ".mp4"
FOURCC = cv2.VideoWriter_fourcc(*'mp4v')
FPS = 20.0

recording_thread = None
stop_event = threading.Event()
is_recording = False
pipe_fd = None
current_game_id = None


def generate_timestamp_filename(prefix="clip", game_id=None):
    """Generate timestamped filename including milliseconds."""
    now = datetime.datetime.now()
    ms = now.microsecond // 1000
    game_id_part = f"_{game_id}" if game_id else ""
    return f"{prefix}{game_id_part}_{now.strftime('%Y%m%d_%H%M%S')}_{ms:03d}{VIDEO_EXTENSION}"


def record_video(stop_signal, pipe_manager, game_id):
    global is_recording
    cap = None
    full_writer = None
    current_interval_writer = None
    full_video_path = None
    interval_output_path = None

    try:
        cap = cv2.VideoCapture(CAPTURE_DEVICE_INDEX)
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"Capture started: {frame_width}x{frame_height} @ {FPS} FPS")

        # Full video writer
        full_filename = generate_timestamp_filename("fullgame", game_id)
        full_video_path = os.path.join(FULL_OUTPUT_DIR, full_filename)
        full_writer = cv2.VideoWriter(full_video_path, FOURCC, FPS, (frame_width, frame_height))

        # Interval video vars
        interval_start_time = time.time()
        interval_output_path = os.path.join(CLIP_OUTPUT_DIR, generate_timestamp_filename("clip", game_id))
        interval_frame_count = 0
        print(f"[RecordThread]   Full video: {full_video_path}")
        print(f"[RecordThread]   First interval: {interval_output_path}")

        while not stop_signal.is_set():
            ret, frame = cap.read()
            if not ret:
                print("Warning: Couldn't read frame.")
                time.sleep(0.1)
                continue

            current_time = time.time()
            full_writer.write(frame)

            # --- Interval Logic ---
            if current_time - interval_start_time >= INTERVAL and interval_frame_count > 0:
                saved_interval_path = None
                if current_interval_writer:
                    current_interval_writer.release()
                    saved_interval_path = interval_output_path
                    print(f"Interval video saved: {interval_output_path}")
                    current_interval_writer = None
                if saved_interval_path:
                    abs_path = os.path.abspath(saved_interval_path)
                    completion_event = f"COMPLETE_{abs_path}"
                    print(f"[RecordThread] Sending event: {completion_event}")
                    if not pipe_manager.send_event(completion_event):
                        print(" Warning: Failed to send completion event")

                interval_output_path = os.path.join(CLIP_OUTPUT_DIR, generate_timestamp_filename("clip", game_id))
                interval_start_time = current_time
                interval_frame_count = 0

            if not current_interval_writer and interval_output_path:
                current_interval_writer = cv2.VideoWriter(interval_output_path, FOURCC, FPS, (frame_width, frame_height))
                print(f"Starting new interval: {interval_output_path}")

            if current_interval_writer:
                current_interval_writer.write(frame)
                interval_frame_count += 1
    except Exception:
        print("🚨 An error occurred in recording thread:")
        traceback.print_exc()
    finally:
        print("[RecordThread] Finishing...")
        if cap:
            cap.release()
        if full_writer:
            full_writer.release()
            print(f"[RecordThread]   Full video saved: {full_video_path}")
        final_saved_interval_path = None
        if current_interval_writer:
            current_interval_writer.release()
            final_saved_interval_path = interval_output_path
            print(f"[RecordThread]   Final interval clip saved: {final_saved_interval_path}")
        if final_saved_interval_path:
            abs_path = os.path.abspath(final_saved_interval_path)
            completion_event = f"COMPLETE_{abs_path}"
            print(f"[RecordThread]   Sending final completion event: {completion_event}")
            if not pipe_manager.send_event(completion_event):
                print("   🚨 Warning: Failed to send final completion event.")
        is_recording = False
        print("[RecordThread] Finished.")


def listen_for_events():
    """Listen for pipe commands and manage recording thread (simplified)."""
    global recording_thread, is_recording, current_game_id

    os.makedirs(CLIP_OUTPUT_DIR, exist_ok=True)
    os.makedirs(FULL_OUTPUT_DIR, exist_ok=True)

    pipe_manager = PipeManager(PIPE_V2G_PATH, PIPE_G2V_PATH)
    if not pipe_manager.setup_pipes():
        print("Exiting: Failed to set up pipes.")
        return

    try:
        while True:
            command = pipe_manager.receive_event()

            if command:
                print(f"[VideoApp] Received from GameApp: '{command}")
                if command.startswith("START_") and not is_recording:
                    try:
                        current_game_id = command.split("_", 1)[1]
                        print(f"Starting recording for game ID: {current_game_id}...")
                        is_recording = True
                        stop_event.clear()
                        recording_thread = threading.Thread(target=record_video, args=(stop_event, pipe_manager, current_game_id), daemon=True)
                        recording_thread.start()
                    except IndexError:
                        print(f"Warning: Malformed START command: {command}")
                        current_game_id = None
                    except Exception as start_e:
                        print(f"Error starting recording thread: {start_e}")
                        is_recording = False
                        current_game_id = None
                elif command == "STOP" and is_recording:
                    print("Stopping recording...")
                    stop_event.set()
                    if recording_thread and recording_thread.is_alive():
                        recording_thread.join(timeout=15.0)
                        if recording_thread.is_alive():
                            print("Warning: Recording thread didn't terminate gracefully after STOP.")
                    print("Recording stopped.")
                    current_game_id = None
                elif command == "START_" and is_recording:
                    print("Warning: Received START command while already recording. Ingoring")
                elif command == "STOP" and not is_recording:
                    print("Warning: Received STOP command while not recording. Ignoring")
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nCtrl+C detected, shutting down...")
    finally:
        print("Cleaning up video app...")
        if is_recording:
            print("Stopping active recording...")
            stop_event.set()
            if recording_thread and recording_thread.is_alive():
                recording_thread.join(timeout=15.0)
        pipe_manager.close_pipes()
        print("Listener stopped.")


if __name__ == "__main__":
    listen_for_events()
