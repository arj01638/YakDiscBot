import base64
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
        set_description(int(user_id), memory)
        logger.info(f"Updated memory for user {user_id}")
        logger.info(f"New memory: {memory}")
        return {"status": "success", "message": f"Memory for user {user_id} updated successfully to '{memory}'."}
    except Exception as e:
        logger.error(f"Error updating user memory: {e}")
        return {"status": "error", "message": str(e)}


def update_user_name(user_id, name):
    try:
        set_name(int(user_id), name)
        logger.info(f"Updated name for user {user_id} to {name}")
        return {"status": "success", "message": f"Name for user {user_id} updated successfully to '{name}'."}
    except Exception as e:
        logger.error(f"Error updating user name: {e}")
        return {"status": "error", "message": str(e)}

def get_user_name(user_id):
    try:
        name = get_name(int(user_id))
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
    elif name == "get_user_name":
        return get_user_name(**args)
    else:
        logger.error(f"Unknown function call: {name} with args {args}")
        return {"error": f"Unknown function call: {name}"}


async def get_chat_response(messages,
                            user_id,
                            model_engine=DEFAULT_MODEL_ENGINE,
                            temperature=DEFAULT_TEMPERATURE,
                            top_p=DEFAULT_TOP_P):
    logger.info(f"Getting chat response with model {model_engine} \n messages: {messages} \n")
    try:
        while True:
            response = client.responses.create(
                model=model_engine,
                input=messages,
                temperature=temperature,
                top_p=top_p,
                tools=tools
            )

            # billing
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            cost = pricing[model_engine]["input"] * input_tokens \
                   + pricing[model_engine]["output"] * output_tokens
            update_usage(user_id, cost)
            logger.info(f"Usage: {response.usage}")

            # image generation
            image_generation_calls = [
                output
                for output in response.output
                if output.type == "image_generation_call"
            ]
            image_data = [output.result for output in image_generation_calls]
            if image_data:
                image_base64 = image_data[0]
                return_image = base64.b64decode(image_base64)

            # function calls
            if not any(out.type == "function_call" for out in response.output):
                return response.output_text, return_image if image_data else None

            # for each function call, execute and append a function result
            for tool_call in response.output:
                if tool_call.type != "function_call":
                    continue
                name = tool_call.name
                args = json.loads(tool_call.arguments)
                result = call_function(name, args)

                messages.append({
                    "type": "function_call_output",
                    "call_id": tool_call.call_id,
                    "output": str(result)
                })
            #
    except Exception as e:
        logger.error(f"Error getting chat response: {e}")
        return f"Error: {str(e)}"


async def get_tts(text, model, user_id, voice="onyx"):
    try:
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text
        )
        # todo: pricing?
        # input_tokens = response.usage.input_tokens
        # input_price = pricing[model]["input"] * input_tokens
        # total_price = input_price
        # logger.info(f"Input tokens: {input_tokens}, Input price: {input_price}, Total price: {total_price}")
        # update_usage(user_id, total_price)

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
            model=model, prompt=prompt, n=n, size=size, quality=quality, moderation="low"
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
