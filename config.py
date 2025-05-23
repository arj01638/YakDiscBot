import os
from dotenv import load_dotenv

load_dotenv()  # Load from .env file

# General configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")  # Optional; may be None

# Bot settings
DEFAULT_MODEL_ENGINE = "gpt-4.1-mini"
DEFAULT_TEMPERATURE = 1.0
DEFAULT_FREQ_PENALTY = 0.0
DEFAULT_PRES_PENALTY = 0.0
DEFAULT_TOP_P = 1.0

# TTS settings
TTS_MODEL = "tts-1"
TTS_HD_MODEL = "tts-1-hd"
DEFAULT_VOICE = "onyx"
AVAILABLE_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

# Reaction emojis
UPVOTE_EMOJI = '🔥'
DOWNVOTE_EMOJI ='🍅'

# Other settings
INITIAL_DABLOONS = 0.5  # starting dollar balance

ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

DO_HANDLE_ALARMING_WORDS = False

BOT_NAME = "Gluemo"

TEST_SERVER_ID = 798943158708863016