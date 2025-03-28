# YakBot

YakBot is a Discord bot that has grown organically from a fun “spaghetti” project into a fully featured, multifunctional bot. It supports:

- **Daily token resets:** Users get “dabloons” (usage points) that reset every day.
- **AI Chat:** Ping the bot or reply to one of its messages to dynamically interact with it.
- **Psychoanalysis:** The `psychoanalyze` command analyzes a user’s message history using OpenAI.
- **Text-to-Speech (TTS):** Converts text into speech via OpenAI’s audio API and packages the audio as a short video for mobile viewing.
- **Image Generation & Editing:** Commands like `genimage`, `sdultra`, `dalle2`, etc., generate or edit images via OpenAI and Stability AI.
- **Karma & Reaction Tracking:** Upvote/downvote reactions that update user karma, with leaderboards and statistics.
- **Persistent Data:** All dynamic data (usage, karma, reactions) is stored in a lightweight SQLite database.
- **Configuration:** Static configuration (personality text, user mappings, insults, etc.) is stored in JSON.

## Setup

1. Clone this repository.
2. Create a virtual environment and install requirements:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the root directory with your API keys and bot token:
   ```
   DISCORD_TOKEN=your_discord_bot_token
   OPENAI_API_KEY=your_openai_api_key
   STABILITY_API_KEY=your_stability_api_key
   ```
4. Run the bot:
   ```bash
   python bot.py
   ```

## Help Commands

YakBot provides a comprehensive help system:
- **@Yak help**: Displays a list of all available commands and their usage.
- **@Yak aihelp**: Displays a detailed help message covering all advanced prompt modifiers and AI functionalities.

## Project Structure

- **bot.py** – Main entry point.
- **config.py** – Loads configuration from environment variables.
- **db.py** – Manages SQLite database for persistent storage.
- **openai_helper.py** – Wrappers for OpenAI API calls.
- **messages.py** – Message processing and cleaning.
- **discord_helper.py** – Discord-specific utility functions.
- **personality.py** – Loads personality and static settings from data/static_config.json.
- **commands/** – Contains all the Discord commands split by functionality.

