from config import Gemini, Instruction
from google import genai, auth
from google.genai import types
from pathlib import Path
from collections import deque

script_dir = Path(__file__).parent.resolve()
assets_dir = script_dir / "assets"


class GeminiManager:
    def __init__(self):
        self.client = genai.Client(http_options={"api_version": "v1alpha"})
        self.session = None
        self.context_manager = None
        self.send_text_task = None
        self.images = deque(maxlen=10)

    def is_connected(self):
        return self.session is not None

    async def connect_gemini(self):
        try:
            self.context_manager = self.client.aio.live.connect(
                model=Gemini.MODEL, config={
                    "response_modalities": ["AUDIO"],
                    "system_instruction": Instruction.LIVE2,
                    "generation_config": {
                        "temperature": 2
                    }
                }
            )
            self.session = await self.context_manager.__aenter__()
            print("Gemini connection successful")
        except Exception as e:
            print(f"Failed to connect to Gemini: {e}")

    async def disconnect_gemini(self):
        if not self.context_manager:
            return
        print("Disconnecting from Gemini...")
        try:
            await self.context_manager.__aexit__(None, None, None)
            self.access_token = None
            self.session = None
            self.context_manager = None
            print("Gemini connection Closed.")
        except Exception as e:
            print(f"Error during Gemini disconnection: {e}") 

    async def send_chunk(self, prompt_text):
        prompt = types.Part(text=prompt_text)
        self.images.append(prompt)
        await self.session.send_client_content(turns=types.Content(parts=self.images))

    async def receive_audio_chunks(self):
        """Receives and yields audio data chunks from the Gemini session."""
        try:
            turn = self.session.receive()
            async for response in turn:
                if data := response.data:
                    if data:
                        yield data
        except Exception:
            print("Error during audio reception: ")
