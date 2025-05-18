import asyncio
import functools
from random import random

from db import get_balance


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
                    await ctx.reply("You do not have enough dabloons to do that.")
                return
            return await func(self, ctx, *args, **kwargs)
        return wrapper
    return decorator