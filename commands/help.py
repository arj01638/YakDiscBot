import discord
from discord.ext import commands

class YakHelp(commands.MinimalHelpCommand):
    async def send_pages(self):
        # todo implement
        pass


async def setup(bot):
    bot.help_command = YakHelp()
