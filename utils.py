import asyncio
import functools
from random import random

from db import get_balance
import aiohttp
import base64
import mimetypes

def truncate_long_values(obj, max_length=300):
    if isinstance(obj, dict):
        return {k: truncate_long_values(v, max_length) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [truncate_long_values(item, max_length) for item in obj]
    elif isinstance(obj, str) and len(obj) > max_length:
        return obj[:max_length] + "...[truncated]"
    return obj

async def url_to_data_uri(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.read()
            mime_type = resp.headers.get("Content-Type")
            if not mime_type:
                ext = url.split('.')[-1]
                mime_type = mimetypes.types_map.get(f".{ext}", "application/octet-stream")
            b64 = base64.b64encode(data).decode("utf-8")
            return f"data:{mime_type};base64,{b64}"

async def run_async(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    wrapped = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, wrapped)

def requires_credit(cost_func):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, ctx, *args, **kwargs):
            user_id = ctx.author.id
            # Fetch user credit from DB (implement this function)
            user_credit = get_balance(user_id)
            # Estimate cost for this command
            cost = cost_func(ctx, *args, **kwargs)
            if user_credit < cost:
                if random() < 0.05:
                    await ctx.reply("get ur bands up brokie 💀")
                else:
                    await ctx.reply("You do not have enough dabloons to do that. Dabloons reset every day.")
                return
            return await func(self, ctx, *args, **kwargs)
        return wrapper
    return decorator