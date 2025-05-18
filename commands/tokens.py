from discord.ext import commands
import discord
from db import get_usage
from db import update_usage

class TokenCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="tokens", help="Display your current token balance.")
    async def tokens(self, ctx, user_id: int = None):
        if user_id is None:
            user_id = ctx.author.id
        data = get_usage(user_id)
        if data:
            usage_balance = data["usage_balance"]
            bank_balance = data["bank_balance"]
        else:
            await ctx.send("No data found for this user.")
            return
        # Convert raw usage to dabloons using a conversion factor (example)
        dabloons = round(usage_balance * 250)
        bank_dabloons = round(bank_balance * 250)
        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Finances",
            description=(f"Dabloons: **{dabloons:,}** 🪙\n"
                         f"Bank Dabloons: **{bank_dabloons:,}** 🏦"),
            color=0x00DCB8
        )
        await ctx.send(embed=embed)

    # Alias command
    @commands.command(name="dabloons", help="Alias for tokens command.")
    async def dabloons(self, ctx, user_id: int = None):
        await self.tokens(ctx, user_id)

async def setup(bot):
    await bot.add_cog(TokenCommands(bot))
