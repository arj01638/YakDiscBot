from discord.ext import commands
import asyncio
import logging
from openai_helper import get_chat_response
from personality import get_personality
from db import update_usage
from discord_helper import reply_split

logger = logging.getLogger(__name__)

class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.default_model_engine = "gpt-4o-mini"
        self.temperature = 1.7
        self.freq_penalty = 0.2
        self.pres_penalty = 0.0
        self.top_p = 0.9
        self.streaming = False

    @commands.command(name="psychoanalyze", help="Perform psychoanalysis on a user's message history.")
    async def psychoanalyze(self, ctx, *, args=""):
        author_id = ctx.author.id
        # For brevity, assume message history has been processed into a text file
        file_path = f"data/{ctx.author.name}.txt"
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                history = f.read()
        except Exception as e:
            await reply_split(ctx.message, "Message history not found. Please run the data scrape first.")
            return
        personality = get_personality(ctx.guild.name, [history])
        prompt_text = (f"The following are sampled messages by {ctx.author.name}:\n"
                       f"{history}\n\nPlease provide an in-depth psychological analysis.")
        messages = [
            {"role": "system", "content": personality},
            {"role": "user", "content": prompt_text}
        ]
        response = await get_chat_response(messages, self.default_model_engine,
                                             self.temperature - 0.5,
                                             self.freq_penalty, self.pres_penalty, self.top_p)
        reply_text = response.choices[0].message.content
        await reply_split(ctx.message, reply_text)
        cost = 0.001  # placeholder cost calculation
        await update_usage(author_id, cost, initial_balance=0)

    @commands.command(name="qt", help="Get AI completion from a custom AI model.")
    async def qt(self, ctx, *, arg):
        author_id = ctx.author.id
        prompt = arg if arg.endswith(':') else arg + "\n"
        messages = [{"role": "user", "content": prompt}]
        response = await get_chat_response(messages,
                                             "ft:babbage-002:university-of-georgia::80Y3aADX",
                                             0.6, self.freq_penalty, self.pres_penalty, 0.5,
                                             stream=self.streaming)
        if not self.streaming:
            reply_text = response.choices[0].text
            await reply_split(ctx.message, reply_text)
        else:
            # Implement streaming reply (omitted for brevity)
            pass
        cost = 0.001  # placeholder cost
        await update_usage(author_id, cost, initial_balance=0)

    @commands.command(name="qt1", help="Get the first line of an AI completion (stops at first newline).")
    async def qt1(self, ctx, *, arg):
        author_id = ctx.author.id
        prompt = arg if arg.endswith(':') else arg + "\n"
        messages = [{"role": "user", "content": prompt}]
        # Use stop parameter to break at the first newline
        response = await get_chat_response(messages,
                                             "ft:babbage-002:university-of-georgia::80Y3aADX",
                                             0.6, self.freq_penalty, self.pres_penalty, 0.5,
                                             stream=self.streaming)
        if not self.streaming:
            # Assume the first line is everything up to the first newline
            full_text = response.choices[0].text
            reply_text = full_text.split('\n')[0]
            await reply_split(ctx.message, reply_text)
        else:
            # Implement streaming for qt1 (omitted for brevity)
            pass
        cost = 0.001  # placeholder cost
        await update_usage(author_id, cost, initial_balance=0)

    @commands.command(name="togglestream", help="Toggle streaming mode for QT commands.")
    async def togglestream(self, ctx):
        self.streaming = not self.streaming
        await ctx.send(f"Streaming mode is now set to {self.streaming}")

def setup(bot):
    bot.add_cog(AIChat(bot))
