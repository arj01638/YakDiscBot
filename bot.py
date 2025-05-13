import asyncio
import datetime

from discord.ext import commands
import logging

from discord_helper import reply_split
from logging_setup import setup_logging
from config import DISCORD_TOKEN, INITIAL_DABLOONS, DO_HANDLE_ALARMING_WORDS, UPVOTE_EMOJI, DOWNVOTE_EMOJI, DEFAULT_MODEL_ENGINE, DEFAULT_TEMPERATURE, DEFAULT_FREQ_PENALTY, DEFAULT_PRES_PENALTY, DEFAULT_TOP_P
import os
from db import init_db, reset_usage, get_connection
import discord

from personality import get_personality

from db import update_karma
from openai_helper import get_chat_response
from personalization import get_author_information
from safety import ALARMING_WORDS, handle_alarming_words

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize the SQLite database
init_db()

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)


# Load all command cogs from the commands folder
def load_cogs():
    for filename in os.listdir("./commands"):
        if filename.endswith(".py") and filename != "__init__.py":
            cog_name = filename[:-3]
            try:
                bot.load_extension(f"commands.{cog_name}")
                logger.info(f"Loaded cog: {cog_name}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog_name}: {e}")


@bot.event
async def on_ready():
    logger.info(f"Bot is ready. Logged in as {bot.user}")

    bot.loop.create_task(background_task())

    from personality import static_config
    from db import get_karma_snippet, get_usage_snippet, get_identities_snippet

    logger.info("Static configuration loaded:")
    if DO_HANDLE_ALARMING_WORDS:
        user_dict_snippet = dict(list(static_config.get("user_dict", {}).items())[:3])
        insults_count = len(static_config.get("insults", []))
        logger.info(f"User dict snippet: {user_dict_snippet}")
        logger.info(f"Total insults loaded: {insults_count}")

    for guild in bot.guilds:
        snippet = get_karma_snippet(guild.id)
        logger.info(f"Guild '{guild.name}' ({guild.id}) karma snippet: {snippet}")

    usage_snippet = get_usage_snippet()
    logger.info(f"Usage data snippet: {usage_snippet}")

    identities_snippet = get_identities_snippet()
    logger.info(f"Identities data snippet: {identities_snippet}")

    logger.info("Data loaded successfully.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if DO_HANDLE_ALARMING_WORDS:
        if message.guild:
            content_lower = message.content.lower()
            if any(word in content_lower for word in ALARMING_WORDS):
                conn = get_connection()
                c = conn.cursor()
                c.execute("SELECT karma FROM karma WHERE guild_id = ? AND user_id = ?",
                          (message.guild.id, message.author.id))
                row = c.fetchone()
                conn.close()
                current_karma = row["karma"] if row else 0
                await handle_alarming_words(message, current_karma)

    # If message starts with a bot mention, check if it's a valid command;
    # if not, handle it as an LLM prompt.
    if message.content.startswith(f"<@{bot.user.id}>"):
        ctx = await bot.get_context(message)
        if ctx.valid:
            await bot.process_commands(message)
        else:
            await handle_prompt_chain(message)
        return

    # Special handling for messages that are replies to bot messages.
    if message.reference is not None:
        try:
            replied_message = await message.channel.fetch_message(message.reference.message_id)
        except Exception:
            replied_message = None
        if replied_message and replied_message.author == bot.user:
            if message.content.startswith("!tts"):
                await bot.process_commands(message)
                return
            elif message.content.startswith("!rw"):
                content = message.content[4:].strip()
                await replied_message.reply(content)
                return
            elif message.content.startswith("!rs"):
                if replied_message.reference:
                    try:
                        original_msg = await message.channel.fetch_message(replied_message.reference.message_id)
                        new_content = original_msg.content + message.content.replace("!rs", "", 1)
                        await original_msg.reply(new_content)
                    except Exception as e:
                        await message.reply(f"Error resending: {e}")
                return

    # Process commands normally.
    await bot.process_commands(message)

async def handle_prompt_chain(message):
    """
    Collects the conversation from a reply chain, builds a prompt,
    sends it to the AI, and replies using reply_split.
    """
    chain = []
    current = message
    while current:
        chain.append(current)
        if current.reference and current.reference.message_id:
            try:
                current = await message.channel.fetch_message(current.reference.message_id)
            except Exception:
                break
        else:
            break
    chain.reverse()  # earliest first

    prompt_lines = []
    author_ids = []

    for msg in chain:
        prompt_lines.append(f"{msg.author.id}: {message.content}")
        author_ids.append(msg.author.id)

    # authors_information = {author_id: (name, description), ...}
    authors_information = get_author_information(author_ids, message.guild)

    for i, line in enumerate(prompt_lines):
        # this would seem inefficient but this is done to handle pings within messages
        for user_id in author_ids:
            if str(user_id) in line:
                name, _ = authors_information[user_id]
                prompt_lines[i] = line.replace(str(user_id), name)

    personality = get_personality(message.guild.name, prompt_lines)
    system_msg = personality
    for author_id in authors_information:
        name, description = authors_information[author_id]
        if description:
            system_msg += f"\n{name}: {description}"

    messages_prompt = [
        {"role": "system",
         "content": system_msg}
    ]
    for i, line in enumerate(prompt_lines):
        pass # todo
    response = await get_chat_response(messages_prompt,
                                       model_engine="gpt-4o-mini",
                                       temperature=1.7,
                                       freq_penalty=0.2,
                                       pres_penalty=0.0,
                                       top_p=0.9,
                                       stream=False)
    await reply_split(message, response)


@bot.event
async def on_raw_reaction_add(payload):
    try:
        channel = await bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
    except Exception as e:
        logger.error(f"Error in on_raw_reaction_add: {e}")
        return

    from db import add_reaction

    if str(payload.emoji) == UPVOTE_EMOJI:
        update_karma(guild.id, message.author.id, 1)
        add_reaction(message.id, member.id, message.author.id, payload.emoji)
    elif str(payload.emoji) == DOWNVOTE_EMOJI:
        update_karma(guild.id, message.author.id, -1)
        add_reaction(message.id, member.id, message.author.id, payload.emoji)


@bot.event
async def on_raw_reaction_remove(payload):
    try:
        channel = await bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
    except Exception as e:
        logger.error(f"Error in on_raw_reaction_remove: {e}")
        return

    from db import remove_reaction

    if str(payload.emoji) == UPVOTE_EMOJI:
        update_karma(guild.id, message.author.id, -1)
        remove_reaction(message.id, member.id, payload.emoji)
    elif str(payload.emoji) == DOWNVOTE_EMOJI:
        update_karma(guild.id, message.author.id, 1)
        remove_reaction(message.id, member.id, payload.emoji)

async def background_task():
    await bot.wait_until_ready()
    import pytz
    last_reset = datetime.datetime.now(pytz.timezone('US/Eastern')).date()
    while not bot.is_closed():
        await asyncio.sleep(3600)  # Every hour
        # todo, scrape during off hours
        now = datetime.datetime.now(pytz.timezone('US/Eastern')).date()
        if now != last_reset:
            reset_usage(INITIAL_DABLOONS)
            logger.info("Usage data reset for the new day.")
            last_reset = now

def run_bot():
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    run_bot()
