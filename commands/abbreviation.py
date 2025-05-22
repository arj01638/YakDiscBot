import discord
from discord.ext import commands
from db import set_abbreviation, get_abbreviation, get_all_abbreviations, delete_abbreviation


async def handle_set_abbreviation(ctx, message, key, value):
    set_abbreviation(message.guild.id, message.author.id, key, value)
    await message.reply(f"Abbreviation `{key}` set.")


async def handle_get_abbreviation(ctx, message, key):
    value = get_abbreviation(message.guild.id, message.author.id, key)
    if value:
        await message.reply(f"`{key}`: {value[:1900]}")  # Discord limit
    else:
        await message.reply(f"No abbreviation found for `{key}`.")


async def handle_list_abbreviations(ctx, message):
    abbrs = get_all_abbreviations(message.guild.id, message.author.id)
    if abbrs:
        keys = ', '.join(abbrs.keys())
        await message.reply(f"Your abbreviations: {keys}")
    else:
        await message.reply("You have no abbreviations.")


async def handle_delete_abbreviation(ctx, message, key):
    delete_abbreviation(message.guild.id, message.author.id, key)
    await message.reply(f"Abbreviation `{key}` deleted.")


class AbbreviationCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setabbr", help="Set an abbreviation: !setabbr key value")
    async def setabbr(self, ctx, key: str, *, value: str):
        set_abbreviation(ctx.guild.id, ctx.author.id, key, value)
        await ctx.reply(f"Abbreviation `{key}` set.")

    @commands.command(name="getabbr", help="Get an abbreviation: !getabbr key")
    async def getabbr(self, ctx, key: str):
        value = get_abbreviation(ctx.guild.id, ctx.author.id, key)
        if value:
            await ctx.reply(f"`{key}`: {value[:1900]}")
        else:
            await ctx.reply(f"No abbreviation found for `{key}`.")

    @commands.command(name="listabbr", help="List your abbreviations")
    async def listabbr(self, ctx):
        abbrs = get_all_abbreviations(ctx.guild.id, ctx.author.id)
        if abbrs:
            keys = ', '.join(abbrs.keys())
            await ctx.reply(f"Your abbreviations: {keys}")
        else:
            await ctx.reply("You have no abbreviations.")

    @commands.command(name="delabbr", help="Delete an abbreviation: !delabbr key")
    async def delabbr(self, ctx, key: str):
        delete_abbreviation(ctx.guild.id, ctx.author.id, key)
        await ctx.reply(f"Abbreviation `{key}` deleted.")


def expand_abbreviations(text, guild_id, user_id):
    abbrs = get_all_abbreviations(guild_id, user_id)
    for key, value in abbrs.items():
        text = text.replace(key, value)
    return text


async def setup(bot):
    await bot.add_cog(AbbreviationCommands(bot))
