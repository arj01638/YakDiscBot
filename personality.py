import json
import os

from config import TEST_SERVER_ID


def load_static_config():
    config_path = os.path.join("data", "static_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    # Fallback default static config if file does not exist
    return {
        "default_personality": "You are an assistant named Gluemo."
    }

static_config = load_static_config()

def get_personality(guild_id, message_list):
    # old bot used different personalities per server but no need for that right now except for test server
    if guild_id == TEST_SERVER_ID:
        return None
    return static_config["default_personality"]
