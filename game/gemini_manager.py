import aiohttp
import aiofiles
import base64
import json
import os

from google import genai, auth
from google.genai import types
from config import Gemini, Instruction


class GeminiManager:
    def __init__(self):
        self.client = genai.Client(http_options={"api_version": "v1alpha"})
        self.session = None
        self.context_manager = None
        self.send_text_task = None
        self.endpoint = f"{Gemini.BASE_URL}/projects/{Gemini.PROJECT_ID}/locations/{Gemini.LOCATION}/publishers/google/models/{Gemini.MODEL}:generateContent"
        self.key_file = Gemini.KEY_FILE
        self.access_token = None

    def get_access_token(self):
        try:
            scopes = ['https://www.googleapis.com/auth/cloud-platform']
            credentials, _ = auth.load_credentials_from_file(self.key_file, scopes=scopes)
            auth_req = auth.transport.requests.Request()
            credentials.refresh(auth_req)
            print("Successfully obtained service account access token.")
            self.access_token = credentials.token
        except FileNotFoundError:
            print(f"Error: Service account key file not found: {self.key_file}")
            return None
        except Exception as e:
            print(f"Error: Exception during service account token generation: {e}")
            return None

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
            # self.get_access_token()
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

    async def send_text(self, text):
        await self.session.send(input=text, end_of_turn=True)

    async def receive_audio_chunks(self):
        """Receives and yields audio data chunks from the Gemini session."""
        try:
            turn = self.session.receive()
            async for response in turn:
                if data := response.data:
                    if data:
                        yield data
        except Exception as e:
            print(f"Error during audio reception: ")

    async def analyze_video(self, client, video_content):
        try:
            response = await client.aio.models.generate_content(
                model=Gemini.MODEL,
                config=types.GenerateContentConfig(
                    system_instruction=Instruction.VIDEO_ANALYSIS
                ),
                contents=video_content
            )
            await self.send_text(response.text)
        except Exception as e:
            print(f"An error occurred during streaming: {e}")

    async def process_video(self, client, event_string):
        if not event_string or not event_string.startswith("COMPLETE_"):
            print(f"    [GeminiManager] Invalid or non-COMPLETE event received: '{event_string}")
            return
        try:
            video_path = event_string.split("_", 1)[1]
        except IndexError:
            print(f"    [GeminiManager] Malformed COMPLETE event: Couldn't extract path form '{event_string}'")
            return
        if not os.path.exists(video_path):
            print(f"   [GeminiManager] Error: Video file not found at {video_path}")
            return
        try:
            with open(video_path, "rb") as f:
                video_bytes = f.read()
            video_content = types.Content(parts=[types.Part(
                inline_data=types.Blob(
                    data=base64.b64encode(video_bytes).decode("utf-8"),
                    mime_type="video/mp4",
                )
            )])
            print(f"    [GeminiManager] Prepared video content for {video_path}]")
        except Exception as e:
            print(f"    [GeminiManager] Error reading or preparing video content from {video_path}: {e}")
            return
        await self.analyze_video(client, video_content)

    async def send_image(self, image_bytes):
        await self.session.send(input=image_bytes, end_of_turn=False)

    async def generate_content_fps(self, session, video_path):
        """
        Asynchronously sends a request to the Gemini API using an access token.

        Args:
            session (aiohttp.ClientSession): The HTTP client session.
            video_path (str): Path to the video file.
            fps (int): Frames per second of the video.
            access_token (str): OAuth2 access token.

        Returns:
            dict: API response (JSON format) or None on error.
        """
        if not self.access_token:
            print("Error: No valid access token provided.")
            return None

        # 2. Asynchronously read and Base64 encode the video file
        try:
            async with aiofiles.open(video_path, "rb") as f:
                video_bytes = await f.read()
            base64_video = base64.b64encode(video_bytes).decode("utf-8")
            print("Successfully read and encoded video file")
        except FileNotFoundError:
            print(f"Error: Video file not found: {video_path}")
            return None
        except Exception as e:
            print(f"Error: Problem processing video file: {e}")
            return None

        # 3. Set request headers
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        # 4. Set request payload
        payload = {
            "contents": {
                "role": "user",
                "parts": [
                    {"text": Instruction.VIDEO_ANALYSIS},
                    {
                        "inlineData": {
                            "mimeType": "video/mp4",
                            "data": base64_video
                        },
                        "videoMetadata": {
                            "fps": 20
                        }
                    }
                ]
            },
            "generationConfig": {
                "responseMimeType": "text/plain"
            }
        }

        try:
            async with session.post(self.endpoint, headers=headers, json=payload) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientResponseError as e:
            print(f"Error: API request failed with status {e.status}: {e.message}")
            return None
        except aiohttp.ClientError as e:
            print(f"Error: API request failed (aiohttp client error): {e}")
            return None
        except json.JSONDecodeError:
            print("Error: API response was not valid JSON.")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during API call: {e}")
            return None

    async def generate_content_fps_with_own_session(self, video_path):
        async with aiohttp.ClientSession() as session:
            response = await self.generate_content_fps(session, video_path)
            if response and 'candidates' in response:
                try:
                    generated_text = response['candidates'][0]['content']['parts'][0]['text']
                    await self.send_text(generated_text)
                except (IndexError, KeyError, TypeError) as e:
                    print(f"[Gemini Task Error parsing response for {os.path.basename(video_path)}]: {e}")
            elif response is None:
                print("[Gemini Task Failed in video_analysis] (returned None)")
            else:
                print(f"[Gemini Task Unexpected response for {os.path.basename(video_path)}]")
            return response
