import json
import mimetypes
import os
from io import BytesIO

import aiohttp
import requests
import logging
from openai import OpenAI
from config import OPENAI_API_KEY, DEFAULT_MODEL_ENGINE, DEFAULT_TEMPERATURE, DEFAULT_FREQ_PENALTY, \
    DEFAULT_PRES_PENALTY, DEFAULT_TOP_P
from db import update_usage, get_description, set_description, set_name, get_name
from utils import run_async

client = OpenAI(
    api_key=OPENAI_API_KEY
)
logger = logging.getLogger(__name__)

tools = [{
    "type": "function",
    "function": {
        "name": "update_user_memory",
        "description": "Update memory about a user.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The ID of the user to update memory for."
                },
                "memory": {
                    "type": "string",
                    "description": "The new memory to replace the old memory (try to keep previous memory information intact by restating it unless requested to remove certain details)."
                }
            },
            "required": ["user_id", "memory"],
            "additionalProperties": False
        },
        "strict": True
    }
},
    {
        "type": "function",
        "function": {
            "name": "update_user_name",
            "description": "Update the preferred name of a user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The ID of the user to update name for."
                    },
                    "name": {
                        "type": "string",
                        "description": "The new preferred name for the user."
                    }
                },
                "required": ["user_id", "name"],
                "additionalProperties": False
            },
        "strict": True
    }
},
    {
        "type": "function",
        "function": {
            "name": "get_user_name",
            "description": "Get the preferred name of a user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The ID of the user to get name for."
                    }
                },
                "required": ["user_id"],
                "additionalProperties": False
            },
        "strict": True
    }
},
]

M = 1000000

pricing = {
    "gpt-4.1": {
        "input": 2.00 / M,
        "output": 8.00 / M
    },
    "gpt-4.1-mini": {
        "input": 0.4 / M,
        "output": 1.6 / M
    },
    "gpt-4.1-nano": {
        "input": 0.1 / M,
        "output": 0.4 / M
    },
    "gpt-4.5-preview": {
        "input": 75.00 / M,
        "output": 150.00 / M
    },
    "gpt-4o": {
        "input": 2.5 / M,
        "output": 10.0 / M
    },
    "gpt-4o-mini": {
        "input": 0.15 / M,
        "output": 0.6 / M
    },
    "o1": {
        "input": 15 / M,
        "output": 60 / M
    },
    "o1-pro": {
        "input": 150 / M,
        "output": 600 / M
    },
    "o3": {
        "input": 10 / M,
        "output": 40 / M
    },
    "o4-mini": {
        "input": 1.10 / M,
        "output": 4.40 / M
    },
    "o3-mini": {
        "input": 1.10 / M,
        "output": 4.40 / M
    },
    "o1-mini": {
        "input": 1.10 / M,
        "output": 4.40 / M
    },
    "gpt-image-1": {
        "input": 5.00 / M,
        "medium": 0.042,
        "high": 0.167,
    },
    "gpt-4o-mini-tts": {
        "input": 12.00 / M,
    },
    "tts-1": {
        "input": 15 / M,
    },
    "gpt-4": {
        "input": 30 / M,
        "output": 60.00 / M
    },
    "dall-e-2": {
        "1024x1024": 0.02,
    },
    "dall-e-3": {
        "1024x1024": 0.04,
        "1792x1024": 0.08,
        "1024x1792": 0.08,
    },

}


def update_user_memory(user_id, memory):
    try:
        set_description(user_id, memory)
        logger.info(f"Updated memory for user {user_id}")
        logger.info(f"New memory: {memory}")
        return {"status": "success", "message": "Memory updated successfully."}
    except Exception as e:
        logger.error(f"Error updating user memory: {e}")
        return {"status": "error", "message": str(e)}


def update_user_name(user_id, name):
    try:
        set_name(user_id, name)
        logger.info(f"Updated name for user {user_id} to {name}")
        return {"status": "success", "message": "Name updated successfully."}
    except Exception as e:
        logger.error(f"Error updating user name: {e}")
        return {"status": "error", "message": str(e)}

def get_user_name(user_id):
    try:
        name = get_name(user_id)
        if not name:
            logger.info(f"No name found for user {user_id}, returning default name.")
            return {"status": "success", "name": "User"}
        logger.info(f"Retrieved name for user {user_id}: {name}")
        return {"status": "success", "name": name}
    except Exception as e:
        logger.error(f"Error retrieving user name: {e}")
        return {"status": "error", "message": str(e)}


def call_function(name, args):
    if name == "update_user_memory":
        return update_user_memory(**args)
    elif name == "update_user_name":
        return update_user_name(**args)
    else:
        logger.error(f"Unknown function call: {name} with args {args}")
        return {"error": f"Unknown function call: {name}"}


async def get_chat_response(messages,
                            user_id,
                            model_engine=DEFAULT_MODEL_ENGINE,
                            temperature=DEFAULT_TEMPERATURE,
                            freq_penalty=DEFAULT_FREQ_PENALTY,
                            pres_penalty=DEFAULT_PRES_PENALTY,
                            top_p=DEFAULT_TOP_P,
                            stream=False):
    logger.info(f"Getting chat response with model {model_engine} \n messages: {messages} \n")
    try:
        while True:
            response = client.chat.completions.create(
                model=model_engine,
                messages=messages,
                temperature=temperature,
                frequency_penalty=freq_penalty,
                presence_penalty=pres_penalty,
                top_p=top_p,
                stream=stream,
                tools=tools
            )

            # billing
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            cost = pricing[model_engine]["input"] * input_tokens \
                   + pricing[model_engine]["output"] * output_tokens
            update_usage(user_id, cost)

            tool_calls = response.choices[0].message.tool_calls
            if not tool_calls:
                return response.choices[0].message.content

            # for each function call, execute and append a function result
            for call in tool_calls:
                name = call.function.name
                args = json.loads(call.function.arguments)
                result = call_function(name, args)

                messages.append({
                    "role": "function",
                    "name": name,
                    "content": str(result)
                })
            #
    except Exception as e:
        logger.error(f"Error getting chat response: {e}")
        return f"Error: {str(e)}"


async def get_tts(text, model, user_id, voice="onyx"):
    try:
        response = await client.Audio.speech.create(
            model=model,
            voice=voice,
            input=text
        )
        input_tokens = response.usage.prompt_tokens
        input_price = pricing[model]["input"] * input_tokens
        total_price = input_price
        logger.info(f"Input tokens: {input_tokens}, Input price: {input_price}, Total price: {total_price}")
        update_usage(user_id, total_price)

        return response
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise e


async def get_image(model, prompt, user_id, n, size, quality):
    try:
        if model == "dall-e-3" and n != 1:
            raise ValueError("DALL-E 3 only supports n=1")
        # todo write checks for quality congruence with model
        response = await run_async(
            client.images.generate,
            model=model, prompt=prompt, n=n, size=size, quality=quality
        )
        if model == "gpt-image-1":
            total_cost = pricing[model][quality] * n
        elif model.startswith("dall"):
            total_cost = pricing[model][size] * n
        else:
            total_cost = 0.0
            logging.error(f"Unknown model {model} for image generation succeeded in image generation")
        logger.info(f"Image generation cost: {total_cost}")
        update_usage(user_id, total_cost)

        return response
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        raise e


async def edit_image(prompt, user_id, image_urls):
    try:
        images = []
        async with aiohttp.ClientSession() as session:
            for url in image_urls:
                async with session.get(url, timeout=10) as resp:
                    resp.raise_for_status()
                    data = await resp.read()
                buf = BytesIO(data)
                filename = os.path.basename(url).split("?")[0]
                buf.name = filename
                mime_type = resp.headers.get("Content-Type", "").split(";")[0]
                if not mime_type or mime_type == "application/octet-stream":
                    ext = os.path.splitext(filename)[1].lower()
                    mime_type = mimetypes.types_map.get(ext, "image/png")
                images.append((filename, buf, mime_type))

        response = await run_async(
            client.images.edit,
            model="gpt-image-1", prompt=prompt, image=images
        )
        total_cost = pricing["gpt-image-1"]["high"]
        logger.info(f"Image editing cost: {total_cost}")
        update_usage(user_id, total_cost)

        return response
    except Exception as e:
        logger.error(f"Image editing error: {e}")
        raise e

# def count_tokens(text, model_engine):
#     encoding = tiktoken.encoding_for_model(model_engine)
#     return len(encoding.encode(text))
