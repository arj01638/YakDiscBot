import asyncio
import base64
import io
from collections import OrderedDict

import discord
import math
import re
import logging

logger = logging.getLogger(__name__)

cache = OrderedDict()
MAXSIZE = 300

def add_to_cache(obj):
    key = obj.id
    cache[key] = obj
    if len(cache) > MAXSIZE:
        cache.popitem(last=False)

async def get_msg(bot, channel, message_id):
    # Check bot's cache first
    msg = discord.utils.get(bot.cached_messages, id=message_id)
    if msg:
        return msg
    # Then our cache
    if cache[message_id]:
        msg = cache[message_id]
        return msg
    # Else fetch from channel
    try:
        msg = await channel.fetch_message(message_id)
        add_to_cache(msg)
        return msg
    except Exception as e:
        logger.error(f"Error fetching message {message_id}: {e}")
        return None

async def reply_split(message, reply_text="", image_b64=None):
    if not reply_text.strip() and not image_b64:
        await message.reply("Error: Empty response")
        return
    if len(reply_text) <= 1950:
        if image_b64:
            img_bytes = base64.b64decode(image_b64)
            await message.reply(reply_text, file=discord.File(io.BytesIO(img_bytes), filename="image.png"))
        else:
            await message.reply(reply_text)
    else:
        num_chunks = math.ceil(len(reply_text) / 1950)
        last_msg = message
        for i in range(num_chunks):
            chunk = reply_text[i*1950:(i+1)*1950]
            if i == num_chunks - 1 and image_b64:
                img_bytes = base64.b64decode(image_b64)
                await last_msg.reply(chunk, file=discord.File(io.BytesIO(img_bytes), filename="image.png"))
            else:
                last_msg = await last_msg.reply(chunk)

