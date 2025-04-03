import asyncio
import sounddevice as sd
import numpy as np
import logging
from config import Audio

log = logging.getLogger(__name__)
_STREAM_END_MARKER = object()


class AudioPlayer:
    def __init__(self):
        self.sample_rate = Audio.SAMPLE_RATE
        self.channels = Audio.CHANNELS
        self.dtype = Audio.DTYPE
        self.audio_queue = asyncio.Queue()
        self.stream = None
        self.playback_task = None

        try:
            log.info("Initializing AudioPlayer...")
            log.debug("Available audio output devices:")
            try:
                log.debug(sd.query_devices())
                default_output_index = sd.default.device['output']
                default_output = sd.query_devices(default_output_index)
                log.info(f"Default output device: {default_output['name']} (Index: {default_output_index})")
            except Exception as query_e:
                log.warning(f"Could not query audio devices: {query_e}")

            log.debug(f"Creating sounddevice OutputStream with: "
                      f"samplerate={self.sample_rate}, channels={self.channels}, "
                      f"dtype={self.dtype}, latency='low'")
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                blocksize=0,
                latency='low'
            )
            log.info("Sounddevice OutputStream created.")

            self.playback_task = asyncio.create_task(self._audio_playback_loop(), name="audio_playback_loop")
            self.stream.start()
            log.info("Sounddevice stream started.")

        except sd.PortAudioError as e:
            log.critical(f"Sounddevice Error (PortAudio) during initialization: {e}", exc_info=True)
            log.critical("This often indicates issues with audio drivers, device selection, or permissions. Audio playback disabled.")
            self.stream = None
        except Exception as e:
            log.critical(f"Unexpected error during AudioPlayer initialization: {e}", exc_info=True)
            if self.stream:
                try:
                    self.stream.close()
                except Exception as close_e:
                    log.error(f"Error closing stream during init cleanup: {close_e}")
            self.stream = None
            if self.playback_task and not self.playback_task.done():
                self.playback_task.cancel()

    async def _audio_playback_loop(self):
        if not self.stream:
            log.error("Playback loop cannot start: Sounddevice stream is not available.")
            return

        log.info("Audio playback loop started.")
        expected_dtype = np.dtype(self.dtype)
        bytes_per_frame = expected_dtype.itemsize * self.channels

        try:
            while True:
                data_item = await self.audio_queue.get()

                if data_item is _STREAM_END_MARKER:
                    log.debug("Received stream end marker in playback loop.")
                    log.info("Logical audio stream ended.")
                    self.audio_queue.task_done()
                    continue

                data_bytes = data_item
                log.debug(f"Dequeued {len(data_bytes)} bytes for playback.")

                if not data_bytes:
                    log.warning("Dequeued empty data chunk. Skipping.")
                    self.audio_queue.task_done()
                    continue

                if len(data_bytes) % bytes_per_frame != 0:
                    log.warning(f"Received data chunk size ({len(data_bytes)}) is not aligned "
                                f"with frame size ({bytes_per_frame}). Skipping chunk.")
                    self.audio_queue.task_done()
                    continue

                try:
                    audio_array_1d = np.frombuffer(data_bytes, dtype=expected_dtype)
                    if self.channels > 0:
                        audio_array_reshaped = audio_array_1d.reshape(-1, self.channels)
                    else:
                        log.error("Channel count is zero, cannot reshape array.")
                        self.audio_queue.task_done()
                        continue

                    log.debug(f"Converted bytes to numpy array with shape {audio_array_reshaped.shape} and dtype {audio_array_reshaped.dtype}")

                    await asyncio.to_thread(self.stream.write, audio_array_reshaped)
                    log.debug(f"Wrote numpy array (shape: {audio_array_reshaped.shape}) to sounddevice stream.")

                except ValueError as ve:
                    log.error(f"ValueError during data conversion/reshape: {ve}. "
                              f"Data length: {len(data_bytes)}, dtype: {expected_dtype}, channels: {self.channels}", exc_info=True)
                except sd.PortAudioError as e:
                    log.error(f"Sounddevice write error: {e}", exc_info=True)
                except Exception as e:
                    log.error(f"Unexpected error processing/writing audio chunk: {e}", exc_info=True)
                self.audio_queue.task_done()

        except asyncio.CancelledError:
            log.info("Audio playback loop cancelled.")
        except Exception as e:
            log.error(f"Fatal error in audio playback loop: {e}", exc_info=True)
        finally:
            log.info("Audio playback loop finishing.")
            if self.stream:
                try:
                    log.debug("Stopping and closing sounddevice stream...")
                    self.stream.stop()
                    self.stream.close()
                    log.info("Sounddevice stream stopped and closed.")
                except sd.PortAudioError as e:
                    log.error(f"Sounddevice error during stream stop/close: {e}", exc_info=True)
                except Exception as e:
                    log.error(f"Error closing stream in finally block: {e}", exc_info=True)

    async def add_to_queue(self, data_bytes):
        if not self.stream:
            log.warning("Cannot add to queue: Audio stream is not available.")
            return
        try:
            await self.audio_queue.put(data_bytes)
            log.debug(f"Added {len(data_bytes)} bytes chunk to the audio queue (qsize: {self.audio_queue.qsize()})")
        except Exception as e:
            log.error(f"Error adding data to queue: {e}", exc_info=True)

    def stop_and_clear_queue(self):
        if not self.stream:
            log.warning("Cannot stop/clear: Audio stream is not available.")
            return

        log.info("Requesting immediate stop and clearing audio queue.")
        try:
            self.stream.abort()
            log.debug("Sounddevice stream aborted.")

            cleared_count = 0
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                    self.audio_queue.task_done()
                    cleared_count += 1
                except asyncio.QueueEmpty:
                    break
            log.info(f"Audio queue cleared. Removed {cleared_count} items.")

            self.stream.start()
            log.debug("Sounddevice stream restarted after abort.")

        except sd.PortAudioError as e:
            log.error(f"Sounddevice error during stop/clear: {e}", exc_info=True)
        except Exception as e:
            log.error(f"Error during stop_and_clear_queue: {e}", exc_info=True)

    async def signal_stream_end(self):
        if not self.stream:
            log.warning("Cannot signal end: Audio stream is not available.")
            return

        log.debug("Signaling end of the current logical audio stream by adding marker to queue.")
        await self.audio_queue.put(_STREAM_END_MARKER)

    def is_queue_empty(self):
        return self.audio_queue.empty()

    async def close(self):
        log.info("Closing AudioPlayer...")
        if self.playback_task and not self.playback_task.done():
            log.debug("Cancelling playback task...")
            self.playback_task.cancel()
            try:
                await self.playback_task
                log.debug("Playback task finished.")
            except asyncio.CancelledError:
                log.info("Playback task was cancelled as expected.")
            except Exception as e:
                log.error(f"Error waiting for playback task to finish during close: {e}", exc_info=True)

        if self.stream and self.stream.active:
            try:
                log.debug("Ensuring stream is stopped and closed during close().")
                self.stream.stop()
                self.stream.close()
                log.info("Sounddevice stream stopped and closed during close().")
            except sd.PortAudioError as e:
                log.error(f"Sounddevice error during stream stop/close in close(): {e}")
            except Exception as e:
                log.error(f"Error closing stream in close(): {e}")
        self.stream = None
        log.info("AudioPlayer closed.")
