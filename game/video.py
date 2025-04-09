import asyncio
import base64
import time
import logging
import cv2
import os
import datetime

from pipe_manager import PipeManager, PIPE_V2G_PATH, PIPE_G2V_PATH
from gemini_manager import GeminiManager
from audio_manager import AudioPlayer
import numpy as np
from config import Instruction, Screen
from google.genai import types

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(funcName)s] %(message)s')
log = logging.getLogger(__name__)


def capture_and_encode_frame(cap, width=Screen.CAPTURE_WIDTH, height=Screen.CAPTURE_HEIGHT, jpeg_quality=Screen.CAPTURE_QUALITY):
    try:
        ret, frame = cap.read()
        if not ret:
            log.warning("Failed to capture frame from camera.")
            return None
        try:
            resized_frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
        except Exception as resize_err:
            log.error(f"Error during frame resize: {resize_err}", exc_info=True)
            resized_frame = frame
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
        ret, buffer = cv2.imencode('.jpg', resized_frame, encode_param)

        if not ret:
            log.warning("Failed to encode frame to JPEG.")
            return None

        # Save frame for debugging
        SAVE_DIRECTORY = "captured_frames"
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        os.makedirs(SAVE_DIRECTORY, exist_ok=True)
        filename = os.path.join(SAVE_DIRECTORY, f"frame_{timestamp}.jpg")
        save_success = cv2.imwrite(filename, frame)
        """
        """
        if not ret:
            log.warning("Failed to encode frame to PNG.")
            return None
        return buffer.tobytes()
    except Exception as e:
        log.error(f"Error during frame capture/encode: {e}", exc_info=True)
        return None


def create_image_part(image_bytes):
    return types.Part(
        inline_data={
            "mime_type": "image/jpg",
            "data": base64.b64encode(image_bytes).decode("utf-8"),
        }
    )


async def gemini_audio_listener(
        gemini_manager: GeminiManager,
        audio_player: AudioPlayer,
        game_id: str
):
    log.info(f"[{game_id}] Gemini audio listener task started.")
    if not audio_player or not audio_player.stream:
        log.error(f"[{game_id}] AudioPlayer is not available. Cannot play audio.")
        return

    try:
        while True:
            stream_started = False
            log.debug(f"[{game_id}] Waiting for the next audio stream from Gemini...")
            try:
                async for data in gemini_manager.receive_audio_chunks():
                    if not data:
                        await asyncio.sleep(0.01)
                        continue

                    # Ensure player is ready before processing
                    if not audio_player or not audio_player.stream:
                        log.warning(f"[{game_id}] AudioPlayer became unavailable mid-stream. Skipping chunk.")
                        continue

                    if not stream_started:
                        log.info(f"[{game_id}] New audio stream detected. Clearing queue and preparing for playback...")
                        # Mimic AUDIO_START: Stop previous stream and clear buffer
                        audio_player.stop_and_clear_queue()
                        log.debug(f"[{game_id}] Requested audio player to stop and clear queue.")
                        stream_started = True

                    log.debug(f"[{game_id}] Received audio chunk ({len(data)} bytes). Adding to player queue.")
                    # Mimic CHUNK: Add raw bytes directly to the player's queue
                    await audio_player.add_to_queue(data)
                    log.debug(f"[{game_id}] Added audio chunk to player queue (qsize: {audio_player.audio_queue.qsize()}).")

                # After the inner loop finishes (Gemini stops sending for this turn)
                if stream_started:
                    # Mimic AUDIO_END: Signal that this logical stream is complete
                    await audio_player.signal_stream_end()
                    stream_started = False
                    log.info(f"[{game_id}] Gemini audio stream finished. Signaled end to player.")
                else:
                    log.debug(f"[{game_id}] No audio chunks received in this iteration.")

            except asyncio.CancelledError:
                log.info(f"[{game_id}] Gemini audio listener task inner loop cancelled.")
                if stream_started and audio_player and audio_player.stream:
                    # Ensure end is signaled even if cancelled mid-stream
                    await audio_player.signal_stream_end()
                raise  # Re-raise cancellation
            except Exception as e:
                log.error(f"[{game_id}] Error processing an audio stream: {e}", exc_info=True)
                if stream_started and audio_player and audio_player.stream:
                    # Try to signal end even on error to potentially clean up state
                    await audio_player.signal_stream_end()
                stream_started = False
                await asyncio.sleep(1)  # Avoid busy-looping on persistent errors

    except asyncio.CancelledError:
        log.info(f"[{game_id}] Persistent audio listener task cancelled.")
    except Exception as e:
        log.error(f"[{game_id}] Fatal error in persistent audio listener task: {e}", exc_info=True)
    finally:
        log.info(f"[{game_id}] Persistent audio listener task finished.")


async def capture_task(
        game_id: str, gemini_manager: GeminiManager, stop_event: asyncio.Event
):
    log.info(f"[{game_id}] Capture task started.")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        log.error(f"[{game_id}] Cannot open camera 0.")
        return

    capture_interval = 0.5

    try:
        while not stop_event.is_set():
            start_time = time.monotonic()

            image_bytes = await asyncio.to_thread(capture_and_encode_frame, cap)
            if image_bytes:
                image_part = create_image_part(image_bytes)
                gemini_manager.images.append(image_part)
            elapsed_time = time.monotonic() - start_time
            # TODO: parameterize interval
            sleep_duration = max(0, capture_interval - elapsed_time)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=sleep_duration)
                log.info(f"[{game_id}] Stop event received during sleep, exiting capture task.]")
                break
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                log.info(f"[{game_id}] Capture task sleep cancelled.")
                break
    except asyncio.CancelledError:
        log.info(f"[{game_id}] Capture task cancelled.")
    except Exception:
        log.error(f"[{game_id}] Error in capture task.")
    finally:
        log.info(f"[{game_id}] Releasing camera...")
        cap.release()
        log.info(f"[{game_id}] Capture task finished.")


async def send_task(
    game_id: str,
    gemini_manager: GeminiManager,
    event_queue: asyncio.Queue,
    stop_event: asyncio.Event
):
    """
    Manages sending prompts to Gemini based on game events and timers.
    """
    log.info(f"[{game_id}] Send task started.")
    last_send_time = None  # last time to successfully called send_chunk()
    timer_active = False
    start_sent = False
    rally_interval = 10.0  # seconds

    cap_for_goal_result = None

    try:
        while not stop_event.is_set():
            # Determine wait time: either remaining rally interval or indefinite/short poll
            wait_timeout = None
            if timer_active and last_send_time is not None:
                time_since_last_send = time.monotonic() - last_send_time
                if time_since_last_send < rally_interval:
                    wait_timeout = rally_interval - time_since_last_send
                else:
                    # Timer expired, process RALLY immediately
                    wait_timeout = 0.001  # Very short timeout to proceed quickly
            elif not timer_active:
                wait_timeout = None  # Wait indefinitely for an event if timer is off
            else:  # timer_active is True but last_send_time is None (shouldn't happen after START)
                wait_timeout = rally_interval  # Default to rally interval if something is odd

            event = None
            try:
                # Wait for an event from the queue OR timeout
                log.debug(f"[{game_id}] Send task waiting for event or timeout ({wait_timeout}s)")
                event = await asyncio.wait_for(event_queue.get(), timeout=wait_timeout)
                log.info(f"[{game_id}] Send task received event: {event}")
                event_queue.task_done()
            except asyncio.TimeoutError:
                # send RALLY using TimeoutError
                if timer_active and last_send_time is not None and (time.monotonic() - last_send_time >= rally_interval):
                    log.info(f"[{game_id}] Rally timer triggered.")
                    try:
                        log.info(f"[{game_id}] Sending RALLY prompt...")
                        # Grab all available images for context
                        await gemini_manager.send_chunk(Instruction.PROMPT_RALLY)
                        last_send_time = time.monotonic()
                        log.info(f"[{game_id}] RALLY prompt sent (with {len(list(gemini_manager.images))} images).")
                    except Exception:
                        log.error(f"[{game_id}] Failed to send RALLY prompt")
                        await asyncio.sleep(1)
                continue
            except asyncio.CancelledError:
                log.info(f"[{game_id}] Send task wait cancelled.")
                break

            if isinstance(event, tuple):
                payload = event[1:]
                event = event[0]

            if event == "START":
                if not start_sent:
                    log.info(f"[{game_id}] Processing START event in send_task...")
                    # Wait for at least one image from capture_task
                    while len(gemini_manager.images) == 0 and not stop_event.is_set():
                        log.debug(f"[{game_id}] Waiting for first image...")
                        await asyncio.sleep(0.2)
                    if stop_event.is_set():
                        break

                    if len(gemini_manager.images) > 0:
                        try:
                            log.info(f"[{game_id}] Sending START prompt...")
                            await gemini_manager.send_chunk(Instruction.PROMPT_START)
                            last_send_time = time.monotonic()
                            timer_active = True # Start the rally timer
                            start_sent = True
                            log.info(f"[{game_id}] START prompt sent (with {len(list(gemini_manager.images))} images).")
                        except Exception:
                            log.error(f"[{game_id}] Failed to send START prompt")
                    else:
                         log.warning(f"[{game_id}] Could not send START prompt, no images captured before stop.")

            elif event == "GOAL":
                scorer, left, right = payload
                log.info(f"[{game_id}] Processing GOAL event...")
                timer_active = False
                while len(gemini_manager.images) == 0 and not stop_event.is_set():
                    log.debug(f"[{game_id}] Waiting for image before sending GOAL...")
                    # Optional: Capture an image directly here if waiting is too long
                    # if cap_for_goal_result is None: cap_for_goal_result = cv2.VideoCapture(0) # Reuse?
                    # image_bytes = await asyncio.to_thread(capture_and_encode_frame, cap_for_goal_result)
                    # if image_bytes: gemini_manager.images.append(create_image_part(image_bytes))
                    await asyncio.sleep(0.2)
                if stop_event.is_set():
                    break

                if len(gemini_manager.images) > 0:
                    try:
                        log.info(f"[{game_id}] Sending GOAL prompt...")
                        await gemini_manager.send_chunk(
                            Instruction.PROMPT_GOAL_TEMPLATE.format(
                                scorer_name=scorer, left_score=left, right_score=right
                            ))
                        last_send_time = time.monotonic()
                        log.info(f"[{game_id}] GOAL prompt sent (with {len(list(gemini_manager.images))} images). Timer paused.")
                    except Exception as e:
                         log.error(f"[{game_id}] Failed to send GOAL prompt")
                else:
                    log.warning(f"[{game_id}] Could not send GOAL prompt, no images available before stop.")

            elif event == "RESUME":
                log.info(f"[{game_id}] Processing RESUME event...")
                timer_active = True
                last_send_time = time.monotonic()
                log.info(f"[{game_id}] Rally timer resumed and reset.")

            elif event == "RESULT":
                log.info(f"[{game_id}] Processing RESULT event...")
                timer_active = False
                # Ensure at least one *current* image. Capture one directly?
                # Let's try grabbing from deque first, assuming capture_task runs frequently.
                # If issues arise, uncomment and refine direct capture here.

                # Optional direct capture for RESULT:
                # log.debug(f"[{game_id}] Capturing final image for RESULT...")
                # if cap_for_goal_result is None: 
                #     cap_for_goal_result = cv2.VideoCapture(0)
                # image_bytes = await asyncio.to_thread(capture_and_encode_frame, cap_for_goal_result)
                # if image_bytes:
                #     gemini_manager.images.append(create_image_part(image_bytes))
                #     log.debug(f"[{game_id}] Added freshly captured image for RESULT.")
                # else:
                #     log.warning(f"[{game_id}] Failed to capture specific image for RESULT.")

                # Wait if deque is empty after potential capture attempt
                while len(gemini_manager.images) == 0 and not stop_event.is_set():
                    log.debug(f"[{game_id}] Waiting for image before sending RESULT...")
                    await asyncio.sleep(0.2)
                if stop_event.is_set():
                    break

                if len(gemini_manager.images) > 0:
                    try:
                        log.info(f"[{game_id}] Sending RESULT prompt...")
                        await gemini_manager.send_chunk(Instruction.PROMPT_RESULT)
                        last_send_time = time.monotonic() # Update last send time
                        log.info(f"[{game_id}] RESULT prompt sent (with {len(list(gemini_manager.images))} images). Timer stopped.")
                        # This task will be cancelled soon by main() upon receiving STOP.
                    except Exception as e:
                        log.error(f"[{game_id}] Failed to send RESULT prompt: {e}", exc_info=True)
                else:
                    log.warning(f"[{game_id}] Could not send RESULT prompt, no images available before stop.")

            else:
                log.warning(f"[{game_id}] Send task received unknown event: {event}")


    except asyncio.CancelledError:
        log.info(f"[{game_id}] Send task cancelled.")
    except Exception as e:
        log.error(f"[{game_id}] Error in send task: {e}", exc_info=True)
    finally:
        # Clean up camera if it was used directly
        if cap_for_goal_result:
            log.info(f"[{game_id}] Releasing specific camera used by send_task...")
            cap_for_goal_result.release()
        log.info(f"[{game_id}] Send task finished.")


async def stop_game_tasks(game_id, tasks, gemini_manager, audio_player, stop_event):
    """Helper function to stop all tasks associated with a game."""
    log.info(f"[{game_id}] Initiating stop sequence for game tasks...")

    # 1. Signal tasks relying on the event to stop (capture, send_task)
    if stop_event and not stop_event.is_set():
        log.info(f"[{game_id}] Setting stop event.")
        stop_event.set()

    # 1a. Stop any immediate audio playback (added)
    if audio_player and audio_player.stream:
        log.info(f"[{game_id}] Aborting any ongoing audio playback.")
        try:
            audio_player.stop_and_clear_queue() # Stop sound quickly
        except Exception as audio_err:
            log.error(f"[{game_id}] Error stopping audio player during task shutdown: {audio_err}")

    # 2. Cancel all running tasks explicitly
    log.info(f"[{game_id}] Cancelling tasks: {list(tasks.keys())}")
    cancelled_tasks = []
    for name, task in tasks.items():
        if task and not task.done():
            task.cancel()
            cancelled_tasks.append(task)
            log.info(f"[{game_id}] Cancel requested for task: {name}")
        elif task:
            log.debug(f"[{game_id}] Task {name} already done.")

    # 3. Wait for tasks to finish cancellation
    if cancelled_tasks:
        log.info(f"[{game_id}] Waiting for cancelled tasks to finish...")
        # Use return_exceptions=True to prevent one task failure from stopping the gather
        results = await asyncio.gather(*cancelled_tasks, return_exceptions=True)
        log.info(f"[{game_id}] Gather results: {results}")
        log.info(f"[{game_id}] All active tasks finished or cancelled.")
    else:
        log.info(f"[{game_id}] No tasks needed explicit cancellation.")

    # 4. Disconnect Gemini
    if gemini_manager.is_connected():
        log.info(f"[{game_id}] Disconnecting from Gemini...")
        await gemini_manager.disconnect_gemini()
        log.info(f"[{game_id}] Disconnected from Gemini.")
    else:
        log.info(f"[{game_id}] Gemini was not connected.")

    # 5. Clear image deque for safety
    gemini_manager.images.clear()
    log.info(f"[{game_id}] Game tasks stopped and resources cleaned.")


async def main():
    pipe_manager = PipeManager(PIPE_V2G_PATH, PIPE_G2V_PATH)
    gemini_manager = GeminiManager()
    audio_player = None
    current_game_id = None
    active_tasks = {}
    event_queue = None
    capture_stop_event = None

    if not pipe_manager.setup_pipes():
        log.error("Failed to set up pipes. Exiting.")
        return

    # --- Initialize Audio Player ---
    try:
        audio_player = AudioPlayer()
        if not audio_player.stream:
            log.error("Failed to initialize AudioPlayer stream. Audio will not play.")
    except Exception as e:
        log.critical(f"Failed to create AudioPlayer instance: {e}", exc_info=True)

    log.info("Video app started. Waiting for events from game...")

    try:
        while True:
            try:
                command = pipe_manager.receive_event()
                if not command:
                    await asyncio.sleep(0.1)
                    continue
                log.info(f"Received command: {command}")

                if command.startswith("START_"):
                    # Cleanup previous game
                    if current_game_id:
                        log.warning(f"[{current_game_id}] Received START while game already active. Stopping previous game first.")
                        await stop_game_tasks(current_game_id, active_tasks, gemini_manager, audio_player, capture_stop_event)
                        active_tasks.clear()
                        current_game_id = None
                        event_queue = None
                        capture_stop_event = None

                    # start new game
                    game_id = command.split("START_")[1][:8]
                    current_game_id = game_id
                    log.info(f"[{game_id}] Processing START event...")

                    # init resources for the game
                    event_queue = asyncio.Queue()
                    capture_stop_event = asyncio.Event()
                    gemini_manager.images.clear()

                    try:
                        log.info(f"[{game_id}] Connecting to Gemini...")
                        await gemini_manager.connect_gemini()
                        if not gemini_manager.is_connected():
                            raise ConnectionError("Failed to connect to Gemini")
                        log.info(f"[{game_id}] Connected to Gemini.")

                        active_tasks['listener'] = asyncio.create_task(
                            gemini_audio_listener(gemini_manager, audio_player, game_id),
                            name=f"AudioListener_{game_id}"
                        )

                        active_tasks['capture'] = asyncio.create_task(
                            capture_task(game_id, gemini_manager, capture_stop_event),
                            name=f"Capture_{game_id}"
                        )

                        active_tasks['sender'] = asyncio.create_task(
                            send_task(game_id, gemini_manager, event_queue, capture_stop_event),
                            name=f"Sender_{game_id}"
                        )
                        await event_queue.put("START")
                        log.info(f"[{game_id}] All associated tasks started.")

                    except Exception:
                        log.error(f"[{game_id}] Error during START PROMPT processing")
                        await stop_game_tasks(game_id, active_tasks, gemini_manager, audio_player, capture_stop_event)
                        active_tasks.clear()
                        current_game_id = None
                        event_queue = None
                        capture_stop_event = None
                        await asyncio.sleep(2)

                elif command.startswith("STOP"):
                    game_id = current_game_id
                    log.info(f"[{game_id}] Processing STOP event...")
                    await stop_game_tasks(game_id, active_tasks, gemini_manager, audio_player, capture_stop_event)
                    active_tasks.clear()
                    current_game_id = None
                    event_queue = None
                    capture_stop_event = None
                    log.info(f"[{game_id}] STOP processing finished.")

                elif command.startswith("GOAL"):
                    scorer, left, right = command.split("_")[2:]
                    game_id = current_game_id
                    log.info(f"[{game_id}] Received GOAL event. Queueing for send_task.")
                    await event_queue.put(("GOAL", scorer, left, right))

                elif command.startswith("RESUME"):
                    game_id = current_game_id
                    log.info(f"[{game_id}] Received RESUME event. Processing...")
                    await event_queue.put("RESUME")

                elif command.startswith("RESULT"):
                    game_id = current_game_id
                    log.info(f"[{game_id}] Received RESULT event. Queueing for send_task.")
                    await event_queue.put("RESULT")

            except pipe_manager.PipeClosedError:
                log.warning("Pipe connection closed by game app. Exiting loop.")
                break
            except Exception:
                log.error("Error in main event loop")
                if current_game_id:
                    log.error(f"[{current_game_id}] Shutting down due to error in main loop.")
                    await stop_game_tasks(current_game_id, active_tasks, gemini_manager, audio_player, capture_stop_event)
                    active_tasks.clear()
                    current_game_id = None
                    event_queue = None
                    capture_stop_event = None
                await asyncio.sleep(1)
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt received. Initiating shutdown...")
    finally:
        log.info("Shutting down video app...")
        if current_game_id:
            await stop_game_tasks(current_game_id, active_tasks, gemini_manager, audio_player, capture_stop_event)
            active_tasks.clear()

        if audio_player:
            log.info("Closing AudioPlayer...")
            await audio_player.close()
            log.info("AudioPlayer closed.")

        if pipe_manager:
            pipe_manager.close_pipes()
            log.info("Pipes closed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutdown requested by user.")
