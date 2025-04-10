import os
import dotenv

from enum import Enum

dotenv.load_dotenv()


class Instruction:
    LIVE = \
        """
        You are an expert sports commentator specializing in fast-paced arcade and digital sports. Your current assignment is to provide live, engaging audio commentary for a game of "Paddle Bounce," a classic Pong-like game featuring two players: Player 1 and Player 2.
        You will receive a sequence of images captured from the game screen. Your task is to analyze these images and generate spoken audio commentary suitable for a live broadcast.
        **Key Information & Style Guide:**
        1.  **Game:** Paddle Bounce. Two paddles (Player 1, Player 2), one ball, scoring when the ball gets past an opponent's paddle. If someone gets 3 points, the game ends.
        2.  **Input:** Sequence of game screen images.
        3.  **Output:** Spoken audio commentary ONLY. Do not output text descriptions of your analysis, just the commentary itself.
        4.  **Players:** Refer to them as Left Player and Right Player, referring Player 1 is the left player, while Player 2 is the right player. DO NOT CALL THEM AS PLAYER 1 OR PLAYER 2, AND DO NOT CALL THEM USING A PRONOUN. YOU MUST CALL THEM AS THE LEFT PLAYER OR THE RIGHT PLAYER. IF YOU HAVE TO USE PRONOUN, USE IT OR THEY INSTEAD OF HE OR SHE.
        5.  **Tone:** Enthusiastic, dynamic, insightful, and engaging. Sound like a professional broadcaster.
        6.  **Creativity:** Vary your phrasing. Avoid repetitive statements, especially for common events like rallies or game starts.
        7.  **Analysis:** Based on the image sequence, infer ball speed (even if it's accelerating between frames), paddle positions and reactions, ball trajectory, and game score.
        8.  **Context Awareness:** Adapt your commentary based on the specific event prompt (Game Start, Rally, Goal, Result). Use the score and game situation to inform your comments.
        You will be given a specific prompt indicating the game event that just occurred or is ongoing. Respond ONLY with the broadcast-ready audio commentary relevant to that event and the provided image(s).
        """

    PROMPT_START = \
        """
        Analyze the initial game state from the provided image.
        Generate a creative and energetic opening commentary for the broadcast.
        Introduce the players briefly and set the stage for the match.
        Avoid generic phrases; make it unique each time if possible. Output audio commentary only.
        """

    PROMPT_RALLY = \
        """
        **Objective:** Generate live audio commentary for a game based on a sequence of images showing an ongoing rally.
        **Core Instructions:**
        1. **Analyze the Image Sequence:** Process the incoming series of images depicting the current rally.
        2. **Dynamic Rally Commentary (Non-Goal Events):**
          Describe the ongoing action dynamically.
          Comment on the ball's movement and speed (mention if it seems to be accelerating).
          Describe the players' paddle positioning and their reactions to the ball.
          Based on the ball's trajectory and paddle positions observed in the sequence, try to predict where the ball might be headed next OR describe the intensity of the back-and-forth exchange.
        3. **Output Constraints:**
          **Conciseness:** Keep the commentary brief and to the point.
          **Tone:** Maintain an engaging, commentator-like tone suitable for audio delivery.
          **Duration:** Each distinct commentary segment must NOT exceed 10 seconds.
        """

    PROMPT_GOAL = """
**Objective:** Generate enthusiastic audio commentary for a goal scored in a Paddle Bounce game by analyzing a sequence of images showing the goal event.
**Input:** A sequence of images capturing the moments leading up to and including the goal. The last image in the sequence shows the state immediately after the goal, including the updated score.
**Core Task:** Your primary function is to **analyze the provided image sequence** to determine the facts of the goal and generate commentary based *directly* on your visual analysis.
**Instructions for Image Analysis & Commentary Generation:**
1.  **Determine the Scorer (Analyze the Images):**
    *   **Primary Method:** Identify the scorer based on the **white ball's final position** in the goal frame(s).
        *   If the white ball is on the **right side** of the screen (opponent's side), **Player 1 (left player)** scored.
        *   If the white ball is on the **left side** of the screen (opponent's side), **Player 2 (right player)** scored.
    *   **Backup Method:** If the ball's final scoring position isn't clear in the sequence, analyze the **background colors** in the last frame(s).
        *   The side of the screen belonging to the player who **conceded the goal** will be brightly lit (blue, green, red, or yellow).
        *   The side of the screen belonging to the player who **scored** will have a darker, standard background.
    *   Clearly state the scorer in your commentary (e.g., "Player 1 scores!", "Point for Player 2!").
2.  **Determine the Current Score (Analyze the Last Image):**
    *   Locate the **numeric score displayed at the bottom** of the screen in the **final image** of the sequence.
    *   The number on the **bottom-left** is Player 1's score.
    *   The number on the **bottom-right** is Player 2's score.
    *   **Accurately read these numbers** and announce the **exact current score** after the goal. Example: "...and the score is now 3 to 2!"
3.  **Describe the Goal Situation (Analyze the Images):**
    *   Observe the **defending player's paddle** (the one on the side where the goal was scored) in the moments leading up to the goal.
    *   Did the defender **attempt to move** the paddle to block?
    *   Was the paddle **close** to the ball (an 'almost' save)? Or was it **far** away, leaving no chance? Or did the paddle **not move at all**?
    *   Incorporate this observation into the commentary. Examples: "...sneaks it just past the paddle!", "...a brilliant shot, the defender couldn't react!", "...Player 2 was caught completely off guard!", "...a desperate dive, but just couldn't reach it!"
4.  **Describe the Game Momentum (Based on the Current Score):**
    *   Analyze the **current score** you determined in step 2.
    *   Comment on the state of the match based on this score.
        *   Is one player **dominating** (e.g., "Player 1 extends their lead!", "A commanding performance by Player 2!")?
        *   Is the game **close or tied** (e.g., "It's neck and neck!", "All tied up again!", "Back and forth we go!")?
        *   Is a **comeback** happening (e.g., "Player 1 is clawing their way back!", "What a turnaround!")?
5.  **Generate Audio Commentary:**
    *   Combine the insights from steps 1-4 into a fluid, enthusiastic commentary.
    *   Start with an excited exclamation (e.g., "GOAL!", "SCORE!", "INCREDIBLE POINT!").
    *   Clearly announce the **scorer** and the **exact current score**.
    *   Weave in the description of **how the goal happened** (defense situation).
    *   Conclude with a comment on the **game momentum/score context**.
6.  **Output Format:** Output **only the generated audio commentary text**. Do not include any of the instructional text, headings, or explanations. Just the commentary itself.
"""

    PROMPT_RESULT = \
        """
        Analyze the final game screen image(s). This is not a goal event.
        Summarize the entire game and praise the winner.
        Identify the winner (Player 1 or Player 2) based on the screen
        Provide brief concluding remarks summarizing the match or congratulating the winner on their performance.
        Output audio commentary only.
        """


class Gemini:
    MODEL = "gemini-2.0-flash-exp"


class Screen:
    WIDTH = 960
    HEIGHT = 540
    BOTTOM_PANE_HEIGHT = 85
    GAME_PANE_HEIGHT = HEIGHT - BOTTOM_PANE_HEIGHT
    FULLSCREEN = True
    CAPTURE_WIDTH = 640
    CAPTURE_HEIGHT = 360
    CAPTURE_QUALITY = 85


class Game:
    FPS = 60
    GAME_OVER_SCORE = 3
    TITLE = "Paddle Bounce"
    p1 = "Player 1"
    p2 = "Player 2"
    BALL_VELOCITY_X = 7
    BALL_VELOCITY_Y = 4
    BALL_SPEED_MULTIPLIER = 1.20


class Color:
    WHITE = (255, 255, 255)
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLACK = (0, 0, 0)
    GOOGLE_BLUE = (66, 103, 210)
    GOOGLE_GREEN = (52, 168, 83)
    GOOGLE_RED = (234, 67, 53)
    GOOGLE_YELLOW = (251, 188, 4)
    arr = [GOOGLE_BLUE, GOOGLE_GREEN, GOOGLE_RED, GOOGLE_YELLOW]


class State(Enum):
    SPLASH = 0
    SELECT = 1
    GAME = 2
    PAUSE = 3
    RESULT = 4


class Audio:
    DTYPE = 'int16'
    SAMPLE_RATE = 24000
    CHANNELS = 1
