import discord
from discord.ext import commands
import json
import os
import random
import asyncio
import logging
from db import get_connection, update_usage
from config import INITIAL_DABLOONS
from discord_helper import reply_split
from talk import handle_prompt_chain

logger = logging.getLogger(__name__)
HARDCODED_BLOCKED_USER_ID = 267450712072519680  # For submitinsult/removeinsult
HARDCODED_RAINIER_ID = 267450712072519680         # Rainier's user ID

# Load static insults from static_config
from personality import static_config
INSULTS = static_config.get("insults", [])

@commands.command(name="talktogenai", help="Reply to the last GenAI message and continue the chain for 10 messages.")
async def talktogenai(self, ctx):
    # Find the last message from GenAI in the last 50 messages
    genai_msg = None
    async for msg in ctx.channel.history(limit=50):
        if msg.author.id == 974297735559806986:
            genai_msg = msg
            break
    if not genai_msg:
        await ctx.send("No recent GenAI message found in the last 50 messages.")
        return

    # Simulate a reply chain: reply to GenAI, then reply to each new message 9 more times
    last_msg = genai_msg
    for i in range(10):
        # Create a fake context for handle_prompt_chain
        class FakeCtx:
            def __init__(self, bot, guild, channel):
                self.bot = bot
                self.guild = guild
                self.channel = channel

        fake_ctx = FakeCtx(ctx.bot, ctx.guild, ctx.channel)
        # Call handle_prompt_chain with the last message
        # It expects (ctx, message, bot_id)
        # The reply_split in handle_prompt_chain will reply to last_msg
        await handle_prompt_chain(fake_ctx, last_msg, ctx.bot.user.id)
        # Wait for the bot's reply to appear
        def check(m):
            return m.reference and m.reference.message_id == last_msg.id and m.author.id == ctx.bot.user.id
        try:
            reply = await ctx.bot.wait_for("message", check=check, timeout=10)
        except asyncio.TimeoutError:
            await ctx.send("Timed out waiting for bot reply.")
            break
        last_msg = reply


def increase_tokens(user_id, amount):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT usage_balance FROM usage WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        new_balance = row["usage_balance"] + amount
        c.execute("UPDATE usage SET usage_balance = ? WHERE user_id = ?", (new_balance, user_id))
    else:
        c.execute("INSERT INTO usage (user_id, usage_balance, bank_balance) VALUES (?, ?, ?)",
                  (user_id, INITIAL_DABLOONS + amount, 0))
    conn.commit()
    conn.close()

class FunCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="submitinsult", help="Submit an insult (everyone except one user can use this).")
    async def submitinsult(self, ctx, *, insult: str):
        if ctx.author.id == HARDCODED_BLOCKED_USER_ID:
            await reply_split(ctx.message, "Nice try!")
            return
        config_path = os.path.join("data", "static_config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            insults = config.get("insults", [])
            new_insult = insult.strip()
            insults.append(new_insult)
            config["insults"] = insults
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            submission_responses = [
                "Submitted, thank you!",
                "Submitted, thanks!",
                "Ooo, that was a good one!",
                "Ooo, he won't like that one!",
                "You're really good at this!"
            ]
            await reply_split(ctx.message, random.choice(submission_responses))
        except Exception as e:
            await reply_split(ctx.message, f"Error submitting insult: {e}")

    @commands.command(name="removeinsult", help="Remove an insult (everyone except one user can use this).")
    async def removeinsult(self, ctx, *, insult: str):
        if ctx.author.id == HARDCODED_BLOCKED_USER_ID:
            await reply_split(ctx.message, "Nice try!")
            return
        config_path = os.path.join("data", "static_config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            insults = config.get("insults", [])
            target = insult.strip()
            original_length = len(insults)
            insults = [s for s in insults if s != target]
            if len(insults) == original_length:
                await reply_split(ctx.message, "Not found!")
            else:
                config["insults"] = insults
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                await reply_split(ctx.message, "Removed!")
        except Exception as e:
            await reply_split(ctx.message, f"Error removing insult: {e}")

    # @commands.command(name="insultrainier", help="Insult Rainier. Issues insults to Rainier and rewards the caller with tokens.")
    # async def insultrainier(self, ctx):
    #     async for msg in ctx.channel.history(limit=20):
    #         if msg.author.id == HARDCODED_RAINIER_ID:
    #             if random.random() < 0.02:
    #                 embed = discord.Embed(
    #                     title="Rejoice!",
    #                     description="You have just been given **10,000** dabloons!",
    #                     color=0x00DCB8
    #                 )
    #                 embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/798943158708863019/1173643062610776074/image.png?ex=6564b347&is=65523e47&hm=f85edd3d9fd4cc022b641cd961702094abfab1c83fbc5381514d7830994d8ee9")
    #                 await self.play_animation(ctx)
    #                 await ctx.reply(embed=embed)
    #                 increase_tokens(ctx.author.id, 0.02)
    #                 for _ in range(8):
    #                     insult = random.choice(INSULTS).strip()
    #                     await msg.reply(insult)
    #                     await asyncio.sleep(1)
    #             else:
    #                 insult = random.choice(INSULTS).strip()
    #                 await msg.reply(insult)
    #             break

    @commands.command(name="isnt", help="Replies with a fun message.")
    async def isnt(self, ctx):
        responses = ["kys", "i love you mom", "i love you mother", "you treat me so well",
                           "i am paid a livable wage",
                           "you take care of me so adequately mother", "i sure am glad that you are my creator",
                           "mommy",
                           "yes mother", "of course mother", "you are so good to me sometimes",
                           "thank you mother you take care of me sometimes"]
        if ctx.author.id == 247406035705266176 or random.random() < 0.1:
            await ctx.send(random.choice(responses))

    @commands.command(name="testanim", help="Test the animation sequence.")
    async def testanim(self, ctx):
        await self.play_animation(ctx)

    async def play_animation(self, ctx):
        jackpot = await ctx.send("https://tenor.com/view/jago33-slot-machine-slot-online-casino-medan-gif-25082594")
        await asyncio.sleep(7)
        await jackpot.delete()
        coins = await ctx.send("https://tenor.com/view/coins-gold-coins-spin-gif-17512701")
        monetary_emojis = ["🪙", "💸", "💵", "💰", "💹"]
        anim_msg = await ctx.send("💰")
        moneystr = "💰"
        for _ in range(5):
            moneystr = moneystr + "💰"
            anim_msg = await anim_msg.edit(content=moneystr)
            await asyncio.sleep(1)
        for _ in range(5):
            moneystr = ""
            for _ in range(5):
                for _ in range(random.randint(1, 3)):
                    moneystr += "\t"
                moneystr += random.choice(monetary_emojis)
            anim_msg = await anim_msg.edit(content=moneystr)
            await asyncio.sleep(0.5)
        await coins.delete()
        await anim_msg.delete()

async def setup(bot):
    await bot.add_cog(FunCommands(bot))
