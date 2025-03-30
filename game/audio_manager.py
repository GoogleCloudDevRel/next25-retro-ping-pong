import asyncio
import pygame

from config import Audio


class AudioManager:
    def __init__(self):
        self.playback_finished = asyncio.Event()
        pygame.mixer.init(
            frequency=Audio.RECEIVE_SAMPLE_RATE,
            size=Audio.AUDIO_FORMAT_SIZE,
            channels=Audio.CHANNELS,
            buffer=Audio.MIXER_BUFFER_SIZE,
        )
        self.audio_channel = pygame.mixer.find_channel(True)

    async def play_audio(self, audio_chunk):
        chunk_buffer = []
        current_buffer_bytes = 0
        processed_something = False
        try:
            async for data in audio_chunk:
                if not data:
                    continue
                print(f"data: {data}")

                chunk_buffer.append(data)
                current_buffer_bytes += len(data)
                processed_something = True

                if current_buffer_bytes >= Audio.TARGET_COMBINED_BYTES:
                    combined_data = b"".join(chunk_buffer)
                    try:
                        sound_chunk = await asyncio.to_thread(
                            pygame.mixer.Sound, buffer=combined_data
                        )
                        self.audio_channel.queue(sound_chunk)
                        chunk_buffer = []
                        current_buffer_bytes = 0
                        await asyncio.sleep(0.001)
                    except pygame.error as e:
                        print(f"Error creating/queuing combined chunk: {e}")
                        chunk_buffer = []
                        current_buffer_bytes = 0
                    except Exception as e:
                        print(f"Unexpected error processing combined chunk: {e}")
                        chunk_buffer = []
                        current_buffer_bytes = 0

            # Process any remaining data
            if chunk_buffer:
                combined_data = b"".join(chunk_buffer)
                try:
                    sound_chunk = await asyncio.to_thread(
                        pygame.mixer.Sound, buffer=combined_data
                    )
                    self.audio_channel.queue(sound_chunk)
                except pygame.error as e:
                    print(f"Error creating/queuing final chunk: {e}")
                except Exception as e:
                    print(f"Unexpected error processing final chunk: {e}")
            if not processed_something:
                print("No audio data received.")
                self.playback_finished.set()
                return
        except Exception as e:
            print(f"Error during audio reception: {e}")
            self.playback_finished.set()
        finally:
            # Wait for playback completion only if something was likely queued
            if processed_something:
                print("Reception finished. Monitoring playback completion...")
                while self.audio_channel.get_busy():
                    await asyncio.sleep(0.1)
                print("Pygame channel playback finished.")
                self.playback_finished.set()
            else:
                print("receive_combine_queue_audio task finished (no audio data).")
