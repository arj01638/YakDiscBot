import asyncio
import discord
import math
import re
import logging

logger = logging.getLogger(__name__)

async def get_message_from_cache(bot, channel, message_id, extra_cache):
    # Check bot's cache first
    msg = discord.utils.get(bot.cached_messages, id=message_id)
    if msg:
        return msg
    # Then extra_cache
    for m in extra_cache:
        if m.id == message_id:
            return m
    # Else fetch from channel
    try:
        msg = await channel.fetch_message(message_id)
        extra_cache.append(msg)
        return msg
    except Exception as e:
        logger.error(f"Error fetching message {message_id}: {e}")
        return None

async def reply_split(message, reply_text):
    if not reply_text.strip():
        await message.reply("Error: Empty response")
        return
    if len(reply_text) <= 1950:
        await message.reply(reply_text)
    else:
        num_chunks = math.ceil(len(reply_text) / 1950)
        last_msg = message
        for i in range(num_chunks):
            chunk = reply_text[i*1950:(i+1)*1950]
            last_msg = await last_msg.reply(chunk)
