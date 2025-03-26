import asyncio
import base64

import pyaudio
from google.genai import types
from config import Instruction, Gemini

FORMAT = pyaudio.paInt16
CHANNELS = 1
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 2048
MAX_QUEUE_SIZE = 5
PREBUFFER_FRAMES = 5


class GeminiManager:
    def __init__(self, session, pya):
        self.session = session
        self.audio_in_queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        self.out_queue = asyncio.Queue()
        self.send_text_task = None
        self.receive_audio_task = None
        self.play_audio_task = None
        self.start_tasks()
        self.pya = pya
        self.audio_buffer = []

    async def start_tasks(self):
        self.receive_audio_task = asyncio.create_task(self.receive_audio())
        self.play_audio_task = asyncio.create_task(self.play_audio())

    async def cancel_tasks(self):
        self.receive_audio_task.cancel()
        self.play_audio_task.cancel()
        try:
            await self.receive_audio_task
        except asyncio.CancelledError:
            pass
        try:
            await self.play_audio_task
        except asyncio.CancelledError:
            pass

    # async def send_now(self):
    #     await self.session.send(input=".", end_of_turn=True)

    async def send_text(self, text):
        await self.session.send(input=text, end_of_turn=True)

    async def analyze_video(self, client, video_path):
        try:
            with open(video_path, "rb") as f:
                video_bytes = f.read()
                video_content = types.Content(parts=[types.Part(
                    inline_data=types.Blob(
                        data=base64.b64encode(video_bytes).decode("utf-8"),
                        mime_type="video/mp4",
                    )
                )])
                response = await client.aio.models.generate_content(
                    model=Gemini.MODEL,
                    config=types.GenerateContentConfig(
                        system_instruction=Instruction.VIDEO_ANALYSIS
                    ),
                    contents=video_content
                )
                print(response.text)
                await self.session.send(input=response.text, end_of_turn=True)
        # test: "What does the last frame you see? Where is the ball? Can you see 'GOAL' message?"
        except Exception as e:
            print(f"An error occurred during streaming: {e}")

    async def receive_audio(self):
        while True:
            turn = self.session.receive()

            async for response in turn:
                if data := response.data:
                    if self.audio_in_queue.full():
                        self.audio_in_queue.get_nowait()
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    print(f"Text Response: {text}")
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        stream = self.pya.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            self.audio_buffer.append(bytestream)
            if len(self.audio_buffer) < PREBUFFER_FRAMES:
                continue

            audio_data = b"".join(self.audio_buffer)
            await asyncio.to_thread(stream.write, audio_data)
            self.audio_buffer = []
        stream.stop_stream()
        stream.close()
