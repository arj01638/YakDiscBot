import openai
import tiktoken
import logging

from openai import OpenAI

from config import OPENAI_API_KEY

client = OpenAI(
    api_key=OPENAI_API_KEY
)
logger = logging.getLogger(__name__)

async def get_chat_response(messages, model_engine, temperature, freq_penalty, pres_penalty, top_p, stream=False):
    logger.info(f"Getting chat response with model {model_engine} \n messages: {messages} \n")
    try:
        response = client.chat.completions.create(
            model=model_engine,
            messages=messages,
            temperature=temperature,
            frequency_penalty=freq_penalty,
            presence_penalty=pres_penalty,
            top_p=top_p,
            stream=stream
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error getting chat response: {e}")
        return f"Error: {str(e)}"

async def get_tts(model, voice, text):
    try:
        response = await openai.Audio.speech.acreate(
            model=model,
            voice=voice,
            input=text
        )
        return response
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise e

async def get_image(model, prompt, n, size, quality="standard"):
    try:
        response = await openai.Images.acreate(
            model=model,
            prompt=prompt,
            n=n,
            size=size,
            quality=quality
        )
        return response
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        raise e

def count_tokens(text, model_engine):
    encoding = tiktoken.encoding_for_model(model_engine)
    return len(encoding.encode(text))
