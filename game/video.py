import asyncio
import base64
import time
import logging
import cv2

from pipe_manager import PipeManager, PIPE_V2G_PATH, PIPE_G2V_PATH
from gemini_manager import GeminiManager
from config import Instruction

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(funcName)s] %(message)s')
log = logging.getLogger(__name__)


def capture_and_encode_frame(cap):
    try:
        ret, frame = cap.read()
        if not ret:
            log.warning("Failed to capture frame from camera.")
            return None
        ret, buffer = cv2.imencode('.png', frame)
        if not ret:
            log.warning("Failed to encode frame to PNG.")
            return None
        return buffer.tobytes()
    except Exception as e:
        log.error(f"Error during frame capture/encode: {e}", exc_info=True)
        return None


async def gemini_audio_listener(gemini_manager, pipe_manager, game_id):
    log.info(f"[{game_id}] Persistent audio listener task started. Waiting for audio streams...")
    try:
        while True:
            stream_started = False

            log.debug(f"[{game_id}] Waiting for the next audio stream from Gemini...")
            try:
                async for data in gemini_manager.receive_audio_chunks():
                    if not data:
                        await asyncio.sleep(0.01)
                        continue
                    if not stream_started:
                        log.info(f"[{game_id}] New audio stream detected. Receiving chunks...")
                        pipe_manager.send_event(f"AUDIO_START_{game_id}")
                        stream_started = True
                    log.debug(f"[{game_id}] Received audio chunk ({len(data)} bytes).")
                    encoded_bytes = base64.b64encode(data)
                    encoded_string = encoded_bytes.decode('ascii')
                    pipe_manager.send_event(f"CHUNK_{encoded_string}")
                pipe_manager.send_event(f"AUDIO_END_{game_id}")
                stream_started = False
                log.debug(f"[{game_id}] Gemini audio stream finished.")
            except Exception:
                log.error(f"[{game_id}] Error processing an audio stream:")
                await asyncio.sleep(1)
    except asyncio.CancelledError:
        log.info(f"[{game_id}] Persistent audio listener task cancelled.")
    except Exception:
        log.error(f"[{game_id}] Fatal error in persistent audio listener task")
    finally:
        log.info(f"[{game_id}] Persistent audio listener task finished.")


async def screenshot_sender(gemini_manager, game_id):
    log.info(f"[{game_id}] Screenshot sender task started.")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        log.error(f"[{game_id}] Cannot open camera 0.")
        return
    try:
        while True:
            start_time = time.monotonic()
            image_bytes = await asyncio.to_thread(capture_and_encode_frame, cap)
            if image_bytes:
                image_data = {
                    "mime_type": "image/png",
                    "data": base64.b64encode(image_bytes).decode("utf-8")
                }
                try:
                    await gemini_manager.send_image(image_data)
                    log.debug(f"[{game_id}] Sent screenshot to Gemini.")
                except Exception:
                    log.error(f"[{game_id}] Failed to send image to Gemini:")
            elapsed_time = time.monotonic() - start_time
            # TODO: parameterize interval
            sleep_duration = max(0, 1.5 - elapsed_time)
            await asyncio.sleep(sleep_duration)
    except asyncio.CancelledError:
        log.info(f"[{game_id}] Screenshot sender task cancelled.")
    except Exception:
        log.error(f"[{game_id}] Error in screenshot sender task:")
    finally:
        log.info(f"[{game_id}] Releasing camera...")
        cap.release()
        log.info(f"[{game_id}] Screenshot sender task finished.")


async def rally_prompter(gemini_manager, game_id):
    log.info(f"[{game_id}] Rally prompter task started.")
    try:
        while True:
            # TODO: Parameterize interval
            await asyncio.sleep(20.0)
            try:
                log.info(f"[{game_id}] Sending PROMPT_RALLY to Gemini...")
                await gemini_manager.send_text(Instruction.PROMPT_RALLY)
                log.debug(f"[{game_id}] PROMPT_RALLY sent.")
            except Exception:
                log.error(f"[{game_id}] Failed to send rally prompt to Gemini")
    except asyncio.CancelledError:
        log.info(f"[{game_id}] Rally prompter task cancelled.")
    except Exception:
        log.error(f"[{game_id}] Error in rally prompter task")
    finally:
        log.info(f"[{game_id}] Rally prompter task finished.")


async def main():
    pipe_manager = PipeManager(PIPE_V2G_PATH, PIPE_G2V_PATH)
    gemini_manager = GeminiManager()
    current_game_id = None
    gemini_listener_task = None
    screenshot_task = None
    rally_task = None

    if not pipe_manager.setup_pipes():
        log.error("Failed to set up pipes. Exiting.")
        return

    log.info("Video app started. Waiting for events from game...")
    active_tasks = []
    try:
        while True:
            try:
                command = pipe_manager.receive_event()
                if not command:
                    await asyncio.sleep(0.1)
                    continue
                log.info(f"Received command: {command}")

                if command.startswith("START_"):
                    for task in active_tasks:
                        if task and not task.done():
                            task.cancel()
                    active_tasks.clear()

                    game_id = command.split("START_")[1][:4]
                    current_game_id = game_id
                    log.info(f"[{game_id}] Processing START event...")

                    try:
                        log.info(f"[{game_id}] Connecting to Gemini...")
                        await gemini_manager.connect_gemini()
                        if not gemini_manager.is_connected():
                            raise ConnectionError("Failed to connect to Gemini")
                        log.info(f"[{game_id}] Connected to Gemini.")

                        await gemini_manager.send_text(Instruction.PROMPT_START)
                        log.info(f"[{game_id}] PROMPT_START sent.")

                        gemini_listener_task = asyncio.create_task(
                            gemini_audio_listener(gemini_manager, pipe_manager, game_id),
                            name=f"AudioListener_{game_id}"
                        )
                        screenshot_task = asyncio.create_task(
                            screenshot_sender(gemini_manager, game_id),
                            name=f"ScreenshotSender_{game_id}"
                        )
                        rally_task = asyncio.create_task(
                            rally_prompter(gemini_manager, game_id),
                            name=f"RallyPrompter_{game_id}"
                        )
                        active_tasks = [gemini_listener_task, screenshot_task, rally_task]
                        log.info(f"[{game_id}] All associated tasks started.")

                    except Exception:
                        log.error(f"[{game_id}] Error during START PROMPT processing")
                        for task in active_tasks:
                            if task and not task.done():
                                task.cancel()
                        active_tasks.clear()
                        current_game_id = None
                        if gemini_manager.is_connected():
                            await gemini_manager.disconnect_gemini()

                elif command.startswith("STOP"):
                    game_id = current_game_id or "N/A"
                    log.info(f"[{game_id}] Processing STOP event...")
                    log.info(f"[{game_id}] Cancelling all active tasks...")
                    for task in active_tasks:
                        if task and not task.done():
                            task.cancel()
                            log.info(f"[{game_id}] Cancel requested for task: {task.get_name()}")
                    if active_tasks:
                        await asyncio.gather(*[t for t in active_tasks if t], return_exceptions=True)
                        log.info(f"[{game_id}] All active tasks finished or cancelled.")
                    active_tasks.clear()
                    current_game_id = None
                    if gemini_manager.is_connected():
                        log.info(f"[{game_id}] Disconnecting from Gemini...")
                        await gemini_manager.disconnect_gemini()
                    log.info(f"[{game_id}] STOP processing finished.")

                elif command.startswith("GOAL"):
                    game_id = current_game_id
                    log.info(f"[{game_id}] Received GOAL event. Processing...")
                    await gemini_manager.send_text(Instruction.PROMPT_GOAL)

                # elif command.startswith("RESUME"):
                #     game_id = current_game_id or "N/A"
                #     log.info(f"[{game_id}] Received RESUME event. Processing...")
                #     # TODO: RESUME logic
                #     await gemini_manager.send_text(Instruction.PROMPT_RESUME)

                # TODO: RESULT command

                else:
                    log.warning("TEST")
            except pipe_manager.PipeClosedError:
                log.warning("Pipe connection closed by game app. Exiting loop.")
                break
            except Exception:
                log.error("Error in main event loop")
                await asyncio.sleep(1)
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt received. Initiating shutdown...")
    finally:
        log.info("Shutting down video app...")
        log.info("Cancelling any remaining active tasks...")
        for task in active_tasks:
            if task and not task.done():
                task.cancel()
        if active_tasks:
            await asyncio.gather(*[t for t in active_tasks if t], return_exceptions=True)
            log.info("Remaining tasks finished or cancelled.")
        active_tasks.clear()
        if gemini_manager.is_connected():
            log.info("Disconnecting from Gemini...")
            await gemini_manager.disconnect_gemini()
        pipe_manager.close_pipes()
        log.info("Pipes closed.")
        log.info("Video app finished.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutdown requested by user.")
