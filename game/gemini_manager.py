import os

from config import Gemini, Instruction
from google import genai
from google.genai import types
from pathlib import Path
from collections import deque
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_file(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
script_dir = Path(__file__).parent.resolve()
assets_dir = script_dir / "assets"


class GeminiManager:
    def __init__(self):
        self.client = genai.Client(
            vertexai=True,
            http_options=types.HttpOptions(api_version="v1beta1"),
            credentials=credentials,
        )
        self.session = None
        self.context_manager = None
        self.send_text_task = None
        self.images = deque(maxlen=20)

    def is_connected(self):
        return self.session is not None

    async def connect_gemini(self):
        try:
            self.context_manager = self.client.aio.live.connect(
                model=Gemini.MODEL, config={
                    "response_modalities": ["AUDIO"],
                    "system_instruction": Instruction.LIVE,
                    "generation_config": {
                        "temperature": 2
                    },
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

    async def send(self, prompt, end_of_turn):
        await self.session.send(input=prompt, end_of_turn=end_of_turn)

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
