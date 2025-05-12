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
        await reply_split(ctx.message, response)
        cost = 0.001  # TODO placeholder cost calculation
        await update_usage(author_id, cost, initial_balance=0)

def setup(bot):
    bot.add_cog(AIChat(bot))
