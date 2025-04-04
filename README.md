This is not an officially supported Google product. This project is not
eligible for the [Google Open Source Software Vulnerability Rewards
Program](https://bughunters.google.com/open-source-security).

This project is intended for demonstration purposes only. It is not
intended for use in a production environment.

You can review [Google Cloud terms of service
here](https://console.cloud.google.com/tos?id=cloud).


# Paddle Bounce - Next 2025 Interactive Demo

## Overview

Paddle Bounce is a technology demonstration created for Google Cloud Next 2025. It showcases the real-time, multimodal capabilities of the [Gemini 2.0 Flash Experimental Live API](https://ai.google.dev/gemini-api/docs/live).

The project consists of a classic arcade game (`Paddle Bounce`) where gameplay is commentated *live* by an AI, powered by Gemini. The game sends visual information (video frames) and game state events to Gemini, which analyzes them in real-time and streams back audio commentary, mimicking a live sports broadcast.

This demo highlights:

*   **Real-time AI Interaction:** Gemini processes information and generates responses with low latency.
*   **Multimodal Input:** Gemini understands visual input (game frames) combined with text prompts representing game events.
*   **Streaming Audio Output:** Gemini streams audio commentary back for immediate playback.
*   **Inter-Process Communication:** Demonstrates how separate applications (game and AI handler) can communicate effectively.

## Features

*   2-player gameplay.
*   Real-time, AI-generated audio commentary powered by Gemini Live API.
*   Dynamic commentary adapting to game events (Start, Rally, Goal, Result).
*   Visual analysis of game frames for commentary context.
*   Support for Keyboard and Joystick input for game control.
*   Separate processes for game logic and AI interaction, communicating via named pipes (FIFOs).
*   Multiple game states: Splash Screen (video intro), Game, Pause (on goal), Result Screen.

## Architecture

The application runs as two main Python processes:

1.  **Game Process (`game.py`):**
    *   Runs the main game loop using Pygame.
    *   Manages game state (splash, game, pause, result).
    *   Handles user input (keyboard, joystick).
    *   Renders game graphics and assets.
    *   Sends game state events (START, GOAL, RESUME, RESULT, STOP) to the Video Process via a named pipe (`/tmp/paddlebounce_pipe_g2v`).
    *   Receives audio stream events (AUDIO_START, CHUNK, AUDIO_END) from the Video Process via another named pipe (`/tmp/paddlebounce_pipe_v2g`).
    *   Plays the received audio chunks using `audio_manager.py`.

2.  **Video Process (`video.py`):**
    *   Captures frames from a connected capture card using OpenCV (`cv2`).
    *   Receives game state events from the Game Process via the named pipe.
    *   Connects to the Gemini Live API using `gemini_manager.py`.
    *   Sends captured video frames (encoded as PNG/base64) and contextual text prompts (based on game events) to Gemini.
    *   Receives streaming audio data back from Gemini.
    *   Encodes and sends the audio data (chunk by chunk) along with stream markers (AUDIO_START, AUDIO_END) to the Game Process via the other named pipe.

**Communication:** Inter-process communication (IPC) relies on two named pipes (FIFOs) managed by `pipe_manager.py`:
*   `/tmp/paddlebounce_pipe_g2v`: Game -> Video (Events like START, GOAL, RESULT)
*   `/tmp/paddlebounce_pipe_v2g`: Video -> Game (Audio commands like AUDIO_START, CHUNK, AUDIO_END)

## Technology Stack

*   **Language:** Python 3.9+ (leveraging `asyncio` extensively)
*   **Game Engine:** Pygame
*   **AI Model:** Google Gemini (via `google-genai` SDK, specifically the Live API)
*   **Video Capture:** OpenCV (`opencv-python`)
*   **Audio Playback:** SoundDevice (`sounddevice`) + NumPy
*   **IPC:** Linux Named Pipes (FIFOs) via Python's `os` module.
*   **Configuration:** `python-dotenv`

## Setup and Installation

1.  **Clone the Repository:**
    ```bash
    git clone git@github.com:GoogleCloudDevRel/next25-retro-ping-pong.git
    cd next25-retro-ping-pong
    ```

2.  **Create a Virtual Environment:**
    ```bash
    python -m venv paddle
    source paddle/bin/activate  # On Windows use `paddle\Scripts\activate`
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *Note: You might need additional system libraries for Pygame, OpenCV, or PortAudio (for SoundDevice) depending on your OS.*

4.  **Google Cloud Setup:**
    *   Ensure you have a Google Cloud Project.
    *   Get API Key in [Google AI Studio](https://aistudio.google.com/apikey).
    *   Create `.env` file in this folder, and set the following variables
    ```bash
    GOOGLE_API_KEY=YOUR_API_KEY
    ```

5.  **Hardware:**
    *   A working **capture card** connected to your computer (the code defaults to device index 0).
    *   It can also work without a capture card using parameter. More details in below.

## Running the Project

You need to run the two main processes separately, typically in two different terminals. It's often best to start the `video.py` process first, as it establishes the pipes that `game.py` will try to connect to.

1.  **Terminal 1: Start the Video/Gemini Process:**
    ```bash
    source venv/bin/activate # If not already active
    python video.py
    ```
    *(This process will initialize, set up pipes, wait for the game to start, connect to Gemini, and start video capture.)*

2.  **Terminal 2: Start the Game Process:**
    ```bash
    python game.py
    ```
    *(This process will start Pygame, show the splash screen, and attempt to connect to the pipes created by `video.py`. Once the game starts, it will send the START event.)*

**Gameplay Controls:**

*   **Player 1 (Left Paddle):** W (Up), S (Down) / Joystick 0 Vertical Axis
*   **Player 2 (Right Paddle):** Up Arrow (Up), Down Arrow (Down) / Joystick 1 Vertical Axis
*   **Confirm/Advance:** Enter Key / Joystick Buttons 0 or 3

## How it Works (Event Flow)

1.  `game.py` starts. Player presses Enter on the splash screen.
2.  `game.py` sends `START_<game_id>` message via the G2V pipe.
3.  `video.py` receives `START`, connects to Gemini, starts `capture_task` (capturing frames), `gemini_audio_listener` (listening for Gemini audio), and `send_task`.
4.  `send_task` (in `video.py`) queues a "START" event internally. When processed, it sends `Instruction.PROMPT_START` along with the latest captured frame(s) to Gemini.
5.  `video.py`'s `capture_task` continuously captures frames and adds them to a shared deque (`gemini_manager.images`).
6.  `send_task` periodically sends `Instruction.PROMPT_RALLY` with recent frames to Gemini to generate ongoing commentary.
7.  Gemini analyzes the prompt + frames and streams back audio commentary.
8.  `gemini_audio_listener` (in `video.py`) receives audio chunks. It sends `AUDIO_START_<game_id>` once, followed by multiple `CHUNK_<base64_audio_data>` messages, and finally `AUDIO_END_<game_id>` via the V2G pipe.
9.  `game.py` receives these messages. `handle_pipe_events` directs the audio data to `audio_manager.py`, which queues and plays the audio chunks seamlessly.
10. A player scores. `game.py` transitions to the `PAUSE` state and sends `GOAL_<game_id>` via the G2V pipe.
11. `video.py`'s `send_task` receives "GOAL", pauses the rally timer, and sends `Instruction.PROMPT_GOAL` with recent frames to Gemini.
12. Gemini generates goal commentary (e.g., "Player 1 scores! The score is now 1-0!"). Audio is streamed and played as in step 8/9.
13. Player presses Enter in the `PAUSE` state. `game.py` transitions back to `GAME` (if score limit not reached) and sends `RESUME_<game_id>`.
14. `video.py`'s `send_task` receives "RESUME" and restarts the rally commentary timer.
15. The game ends (score limit reached). `game.py` transitions to `RESULT` state after the final pause and sends `RESULT_<game_id>`.
16. `video.py`'s `send_task` receives "RESULT", stops the timer, and sends `Instruction.PROMPT_RESULT` with final frame(s) to Gemini.
17. Gemini generates final result commentary. Audio is streamed and played.
18. Player presses Enter on the `RESULT` screen. `game.py` transitions to `SPLASH` and sends `STOP_<game_id>`.
19. `video.py` receives `STOP`, triggers `stop_game_tasks` which cancels running tasks (capture, sender, listener), disconnects from Gemini, and cleans up resources.

## Project Structure

    next25-retro-ping-pong/
    ├──game
    │   ├── assets/             # Game assets (images, videos)
    │   ├── audio_manager.py    # Plays back audio streams using SoundDevice
    │   ├── game.py             # Main game application (Pygame loop, state, audio playback trigger)
    │   ├── video.py            # Video capture, Gemini interaction, audio generation trigger
    │   ├── gemini_manager.py   # Handles Gemini API connection and communication
    │   ├── pipe_manager.py     # Manages IPC via named pipes
    │   ├── game_manager.py     # Core game logic (state, score, physics interactions)
    │   ├── drawing.py          # Handles all visual rendering and asset loading
    │   ├── config.py           # Configuration constants, Gemini prompts, game settings
    │   ├── paddle.py           # Paddle object class
    │   └── ball.py             # Ball object class
    ├── .env                    # Environment variables (User created)
    └── requirements.txt        # Python dependencies
