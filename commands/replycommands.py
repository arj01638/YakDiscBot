import logging

from discord.ext import commands

from discord_helper import get_msg
from talk import handle_prompt_chain
from utils import requires_credit

logger = logging.getLogger(__name__)

class ReplyCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="rs", help="Resend the replied message.")
    @requires_credit(lambda ctx, *args, **kwargs: 0.001)
    async def rs(self, ctx, arg):
        if not ctx.message.reference:
            await ctx.send("Error: Please reply to a message.")
            return
        replied_message = await get_msg(self.bot, ctx.message.channel, ctx.message.reference.message_id)
        if not replied_message:
            await ctx.send("Error: Could not find the replied message.")
            return
        if not replied_message.reference:
            await ctx.send("Error: The replied message must be replying to a message.")
            return
        grandparent = replied_message.reference
        grandparent_message = await get_msg(self.bot, ctx.message.channel, grandparent.message_id)
        if not grandparent_message:
            await ctx.send("Error: Could not find the grandparent message to resend.")
            return
        await handle_prompt_chain(ctx, grandparent_message, self.bot.user.id)

    @commands.command(name="rw", help="Rewrite the replied message.")
    async def rw(self, ctx, *, content: str):
        if not ctx.message.reference:
            await ctx.send("Error: Please reply to a message.")
            return
        replied_message = await get_msg(self.bot, ctx.message.channel, ctx.message.reference.message_id)
        if not replied_message:
            await ctx.send("Error: Could not find the replied message.")
            return
        if not replied_message.reference:
            await ctx.send("Error: The replied message must be replying to a message.")
            return
        grandparent = replied_message.reference
        grandparent_message = await get_msg(self.bot, ctx.message.channel, grandparent.message_id)
        if not grandparent_message:
            await ctx.send("Error: Could not find the grandparent message to rewrite.")
            return
        await grandparent_message.reply(content)

async def setup(bot):
    await bot.add_cog(ReplyCommands(bot))

