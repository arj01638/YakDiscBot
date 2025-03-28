import json
import os

def load_static_config():
    config_path = os.path.join("data", "static_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    # Fallback default static config if file does not exist
    return {
        "personality_short": "You are a disillusioned, but helpful assistant named Yak. Your creator is ...",
        "personality_full": "Full personality text goes here.",
        "people": "Static info about people.",
        "user_dict": {
            "247406035705266176": "Wimne",
            "267450712072519680": "BBT",
            # ... add the rest
        },
        "nick_dict": {
            "Wimne": "Wine",
            "BBT": "BBT",
            # ... add the rest
        },
        "insults": [
            "insult1", "insult2", "insult3"
        ]
    }

static_config = load_static_config()

def get_personality(guild_name, message_list):
    # Determine which personality string to use
    if guild_name == "yikyak my love <3":
        return static_config["personality_short"]
    else:
        return static_config["personality_short"]
