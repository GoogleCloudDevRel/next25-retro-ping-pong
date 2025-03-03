import asyncio
import pyaudio

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024
pya = pyaudio.PyAudio()


class GeminiManager:
    def __init__(self, session, game_manager):
        self.session = session
        self.audio_in_queue = asyncio.Queue()
        self.out_queue = asyncio.Queue(maxsize=120)
        self.send_text_task = None
        self.receive_audio_task = None
        self.play_audio_task = None
        self.start_tasks()
        self.game_manager = game_manager

    def start_tasks(self):
        asyncio.create_task(self.send_realtime())
        asyncio.create_task(self.receive_audio())
        asyncio.create_task(self.play_audio())

    async def send_now(self):
        await self.session.send(input=".", end_of_turn=True)

    async def send_image(self, image_bytes):
        await self.session.send(input=image_bytes, end_of_turn=False)

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send(input=msg, end_of_turn=False)

    async def receive_audio(self):
        while True:
            turn = self.session.receive()
            print("turn called")

            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    print(f"Text Response: {text}")
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)
