import asyncio
import datetime

from discord.ext import commands
import logging

from logging_setup import setup_logging
from config import DISCORD_TOKEN, INITIAL_DABLOONS, DO_HANDLE_ALARMING_WORDS, UPVOTE_EMOJI, DOWNVOTE_EMOJI
import os
from db import init_db, reset_usage, get_connection, get_meta, set_meta
import discord

from db import update_karma
from safety import ALARMING_WORDS, handle_alarming_words
from talk import handle_prompt_chain

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"), intents=intents)


# Load all command cogs from the commands folder
async def load_cogs():
    for filename in os.listdir("./commands"):
        if filename.endswith(".py") and filename != "__init__.py":
            cog_name = filename[:-3]
            try:
                await bot.load_extension(f"commands.{cog_name}")
                logger.info(f"Loaded cog: {cog_name}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog_name}: {e}")


@bot.event
async def on_ready():
    logger.info(f"Bot is ready. Logged in as {bot.user}")

    await load_cogs()

    init_db(bot.user.id)

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

    ctx = await bot.get_context(message)
    if ctx.valid:
        async with message.channel.typing():
            return await bot.process_commands(message)

    prefixes = await bot.get_prefix(message)
    if isinstance(prefixes,str):
        prefixes = [prefixes]
    if any(message.content.startswith(prefix) for prefix in prefixes):
        async with message.channel.typing():
            return await handle_prompt_chain(ctx, message, bot.user.id)

    # Special handling for messages that are replies to bot messages.
    if message.reference is not None:
        try:
            replied_message = await message.channel.fetch_message(message.reference.message_id)
        except Exception:
            replied_message = None
        if replied_message and replied_message.author == bot.user:
            if message.content.startswith("!tts"):
                await bot.process_commands(message) # todo implement
                return
            elif message.content.startswith("!rw"): # rewrite bot reply
                content = message.content[3:].strip()
                grandparent = replied_message.reference
                if grandparent:
                    try:
                        original_msg = await message.channel.fetch_message(grandparent.message_id) # todo replace all with get_msg type command
                        await original_msg.reply(content)
                    except Exception as e:
                        await message.reply(f"Error rewriting: {e}")
                else:
                    await message.reply("No message to rewrite to.")
                return
            elif message.content.startswith("!rs"): # "resend" grandparent message
                grandparent = replied_message.reference
                if grandparent:
                    try:
                        original_msg = await message.channel.fetch_message(grandparent.message_id)
                        # # Remove "!rs" and any leading/trailing whitespace
                        # extra_content = message.content[3:].strip()
                        # # Compose new content: original + extra
                        # new_content = original_msg.content
                        # if extra_content:
                        #     new_content += " " + extra_content # todo when we implement get_msg make new_content actually do something
                        await handle_prompt_chain(ctx, original_msg, bot.user.id)
                    except Exception as e:
                        await message.reply(f"Error resending: {e}")
                else:
                    await message.reply("No message to resend.")
                return
            else:
                return await handle_prompt_chain(ctx, message, bot.user.id)

    await bot.process_commands(message) # do we need this?


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
    tz = pytz.timezone('US/Eastern')
    last_reset_str = get_meta("last_reset")
    if last_reset_str:
        last_reset = datetime.datetime.strptime(last_reset_str, "%Y-%m-%d").date()
    else:
        last_reset = datetime.datetime.now(tz).date()
        set_meta("last_reset", last_reset.strftime("%Y-%m-%d"))
    while not bot.is_closed():
        now = datetime.datetime.now(tz).date()
        if now != last_reset:
            reset_usage(INITIAL_DABLOONS)
            logger.info("Usage data reset for the new day.")
            last_reset = now
            set_meta("last_reset", last_reset.strftime("%Y-%m-%d"))
        await asyncio.sleep(3600)


def run_bot():
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    run_bot()
