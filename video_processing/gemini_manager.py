import asyncio
import base64
import traceback

import pyaudio
from google.genai import types
from config import Instruction, Gemini

AUDIO_FORMAT = pyaudio.paInt16
AUDIO_CHANNELS = 1
AUDIO_RECEIVE_SAMPLE_RATE = 24000
AUDIO_QUEUE_MAX_SIZE = 10
AUDIO_PREBUFFER_FRAMES = 5


class GeminiManager:
    def __init__(self, session, pya):
        self.session = session
        self._pya = pya
        self._audio_input_queue = asyncio.Queue(maxsize=AUDIO_QUEUE_MAX_SIZE)

        self._receive_audio_task = None
        self._play_audio_task = None
        self._audio_playback_buffer = []

        # self.out_queue = asyncio.Queue()
        # self.send_text_task = None
        # self.receive_audio_task = None
        # self.play_audio_task = None
        # self.start_tasks()
        # self.audio_buffer = []

    async def initialize(self):
        if self._receive_audio_task or self._play_audio_task:
            print("Warning: GeminiManager tasks seem to be already running.")
            return
        print("Starting GeminiManager background tasks...")
        self._receive_audio_task = asyncio.create_task(self._receive_audio_loop())
        self._play_audio_task = asyncio.create_task(self._play_audio_loop())
        print("GeminiManager background tasks started.")

    # async def start_tasks(self):
    #     self._receive_audio_task = asyncio.create_task(self._receive_audio_loop())
    #     self._play_audio_task = asyncio.create_task(self._play_audio_loop())

    async def shutdown(self):
        print("Shutting down GeminiManager")
        if self._play_audio_task and not self._play_audio_task.done():
            await self._audio_input_queue.Put(None)
        tasks_to_cancel = [self._receive_audio_task, self._play_audio_task]
        tasks_to_await = []

        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
                tasks_to_await.append(task)
        if tasks_to_await:
            print(f"Waiting for {len(tasks_to_await)} tasks to cancel...")
            await asyncio.gather(*tasks_to_await, return_exceptions=True)
            print("Background tasks cancelled.")
        else:
            print("No active background tasks to cancel.")

        while not self._audio_input_queue.empty():
            try:
                self._audio_input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self._receive_audio_task = None
        self._play_audio_task = None
        print("GeminiManager shutdown complete.")

    async def send_text_to_session(self, text):
        try:
            await self.session.send(input=text, end_of_turn=True)
        except Exception as e:
            print(f"Error sending text to Gemini session: {e}")
            traceback.print_exc()

    async def analyze_video(self, client, video_path):
        print(f"Analyzing video: {video_path}")
        try:
            with open(video_path, "rb") as f:
                video_bytes = f.read()
            video_base64 = base64.b64encode(video_bytes).decode("utf-8")
            video_part = types.Part(
                inline_data=types.Blob(
                    data=video_base64,
                    mime_type="video/mp4"
                )
            )
            video_content = types.Content(parts=[video_part])
            print("Sending video to Gemini for analysis...")
            response = await client.aio.models.generate_content(
                model=Gemini.MODEL,
                config=types.GenerateContentConfig(
                    system_instruction=Instruction.VIDEO_ANALYSIS
                ),
                contents=video_content
            )
            analysis_text = response.text
            print(f"FGemini Video Analysis Result: {analysis_text}")
            await self.send_text_to_session(analysis_text)
        except FileNotFoundError:
            print(f"Error: Video file not found at {video_path}")
        except Exception as e:
            print(f"An error occurred during video analysis or sending result: {e}")
            traceback.print_exc()

    async def _receive_audio_loop(self):
        print("Receive audio loop started.")
        while True:
            try:
                turn = await asyncio.to_thread(self.session.receive)
                async for response in turn:
                    if audio_data := response.data:
                        if self._audio_input_queue.full():
                            try:
                                self._audio_input_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                pass
                        self._audio_input_queue.put_nowait(audio_data)
                    if text_data := response.text:
                        print(f"\nText Response from Sessison: {text_data}")
            except asyncio.CancelledError:
                print("Receive audio loop cancelled.")
                break
            except Exception as e:
                print(f"Error in receive audio loop: {e}")
                traceback.print_exc()
                await asyncio.sleep(1)

    async def _play_audio_loop(self):
        print("Play audio loop started")
        stream = None
        try:
            stream=self._pya.open(
                format=AUDIO_FORMAT,
                channels=AUDIO_CHANNELS,
                rate=AUDIO_RECEIVE_SAMPLE_RATE,
                output=True,
            )
            print(f"PyAudio output stream opened.")
            self._audio_playback_buffer = []
            while True:
                item = await self._audio_input_queue.get()
                if item is None:
                    print("Playt audio loop: Received stop signal.")
                    if self._audio_playback_buffer:
                        print("Playing remaining audio buffer...")
                        remaining_data = b"".join(self._audio_playback_buffer)
                        await asyncio.to_thread(stream.write, remaining_data)
                        self._audio_playback_buffer = []
                    break

                self._audio_playback_buffer.append(item)
                if len(self._audio_playback_buffer) < AUDIO_PREBUFFER_FRAMES:
                    continue

                audio_data_to_play = b"".join(self._audio_playback_buffer)
                self._audio_playback_buffer = []

                try:
                    await asyncio.to_thread(stream.write, audio_data_to_play)
                except Exception as e:
                    print(f"Error writing to PyAudio stream: {e}")

        except asyncio.CancelledError:
            print("Play audio loop cancelled.")
        except Exception as e:
            print(f"Error in play audio loop:  {e}")
            traceback.print_exc()
        finally:
            print("play audio loop finishing.")
            if stream:
                try:
                    print("Stopping and closing PyAudio stream...")
                    await asyncio.to_thread(stream.stop_stream)
                    await asyncio.to_thread(stream.close)
                    print("PyAudio stream closed.")
                except Exception as e:
                    print(f"Error closing PyAudio stream: {e}")





    # async def cancel_tasks(self):
    #     self.receive_audio_task.cancel()
    #     self.play_audio_task.cancel()
    #     try:
    #         await self.receive_audio_task
    #     except asyncio.CancelledError:
    #         pass
    #     try:
    #         await self.play_audio_task
    #     except asyncio.CancelledError:
    #         pass
    #
    # # async def send_now(self):
    # #     await self.session.send(input=".", end_of_turn=True)
    #
    # async def send_text(self, text):
    #     await self.session.send(input=text, end_of_turn=True)
    #
    # async def analyze_video(self, client, video_path):
    #     try:
    #         with open(video_path, "rb") as f:
    #             video_bytes = f.read()
    #             video_content = types.Content(parts=[types.Part(
    #                 inline_data=types.Blob(
    #                     data=base64.b64encode(video_bytes).decode("utf-8"),
    #                     mime_type="video/mp4",
    #                 )
    #             )])
    #             response = await client.aio.models.generate_content(
    #                 model=Gemini.MODEL,
    #                 config=types.GenerateContentConfig(
    #                     system_instruction=Instruction.VIDEO_ANALYSIS
    #                 ),
    #                 contents=video_content
    #             )
    #             print(response.text)
    #             await self.session.send(input=response.text, end_of_turn=True)
    #     # test: "What does the last frame you see? Where is the ball? Can you see 'GOAL' message?"
    #     except Exception as e:
    #         print(f"An error occurred during streaming: {e}")
    #
    # async def receive_audio(self):
    #     while True:
    #         turn = self.session.receive()
    #
    #         async for response in turn:
    #             if data := response.data:
    #                 if self.audio_in_queue.full():
    #                     self.audio_in_queue.get_nowait()
    #                 self.audio_in_queue.put_nowait(data)
    #                 continue
    #             if text := response.text:
    #                 print(f"Text Response: {text}")
    #         while not self.audio_in_queue.empty():
    #             self.audio_in_queue.get_nowait()
    #
    # async def play_audio(self):
    #     stream = self.pya.open(
    #         format=FORMAT,
    #         channels=CHANNELS,
    #         rate=RECEIVE_SAMPLE_RATE,
    #         output=True,
    #     )
    #     while True:
    #         bytestream = await self.audio_in_queue.get()
    #         self.audio_buffer.append(bytestream)
    #         if len(self.audio_buffer) < PREBUFFER_FRAMES:
    #             continue
    #
    #         audio_data = b"".join(self.audio_buffer)
    #         await asyncio.to_thread(stream.write, audio_data)
    #         self.audio_buffer = []
    #     stream.stop_stream()
    #     stream.close()
