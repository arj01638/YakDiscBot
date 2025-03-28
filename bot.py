import asyncio
import datetime
from discord.ext import commands
import logging

from discord_helper import reply_split
from logging_setup import setup_logging
from config import DISCORD_TOKEN, INITIAL_DABLOONS
import os
from db import init_db, reset_usage, get_connection
import discord

from personality import get_personality

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

    # Load static configuration from personality module
    from personality import static_config
    logger.info("Static configuration loaded:")
    # Log a snippet of the user dictionary and insults list
    user_dict_snippet = dict(list(static_config.get("user_dict", {}).items())[:3])
    insults_count = len(static_config.get("insults", []))
    logger.info(f"User dict snippet: {user_dict_snippet}")
    logger.info(f"Total insults loaded: {insults_count}")

    # For each guild, query the top few karma entries and log them
    for guild in bot.guilds:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT user_id, karma FROM karma WHERE guild_id = ? LIMIT 3", (guild.id,))
        rows = c.fetchall()
        conn.close()
        snippet = [{"user_id": row["user_id"], "karma": row["karma"]} for row in rows]
        logger.info(f"Guild '{guild.name}' ({guild.id}) karma snippet: {snippet}")

    # Optionally, check a snippet of usage data from the DB
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, usage_balance, bank_balance FROM usage LIMIT 3")
    usage_rows = c.fetchall()
    conn.close()
    usage_snippet = [{"user_id": row["user_id"], "usage": row["usage_balance"], "bank": row["bank_balance"]} for row in
                     usage_rows]
    logger.info(f"Usage data snippet: {usage_snippet}")

    logger.info("Data loaded successfully.")

@bot.event
async def on_message(message):
    # Ignore messages from bots.
    if message.author.bot:
        return

    # Check for alarming words in guild messages.
    if message.guild:
        from safety import ALARMING_WORDS, handle_alarming_words
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
            # Continue processing commands even if alarming words are present.

    # If message starts with a bot mention, check if it's a valid command;
    # if not, handle it as a prompt chain.
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
            elif message.content.startswith("!rw "):
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
    for msg in chain:
        # Remove bot mentions
        content = msg.content.replace(f"<@{bot.user.id}>", "").strip()
        prompt_lines.append(f"{msg.author.display_name}: {content}")
    prompt_text = "\n".join(prompt_lines)
    system_msg = get_personality(message.guild.name, prompt_lines)
    messages_prompt = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt_text}
    ]
    from openai_helper import get_chat_response
    response = await get_chat_response(messages_prompt,
                                       model_engine="gpt-4o-mini",
                                       temperature=1.7,
                                       freq_penalty=0.2,
                                       pres_penalty=0.0,
                                       top_p=0.9,
                                       stream=False)
    reply_text = response.choices[0].message.content
    await reply_split(message, reply_text)


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
    from config import UPVOTE_EMOJI, DOWNVOTE_EMOJI
    if str(payload.emoji) == UPVOTE_EMOJI:
        from db import update_karma
        update_karma(guild.id, message.author.id, 1)
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO reactions (message_id, reactor_id, recipient_id, value) VALUES (?, ?, ?, ?)",
                  (str(message.id), member.id, message.author.id, 1))
        conn.commit()
        conn.close()
    elif str(payload.emoji) == DOWNVOTE_EMOJI:
        from db import update_karma
        update_karma(guild.id, message.author.id, -1)
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO reactions (message_id, reactor_id, recipient_id, value) VALUES (?, ?, ?, ?)",
                  (str(message.id), member.id, message.author.id, -1))
        conn.commit()
        conn.close()


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
    from config import UPVOTE_EMOJI, DOWNVOTE_EMOJI
    if str(payload.emoji) == UPVOTE_EMOJI:
        from db import update_karma
        update_karma(guild.id, message.author.id, -1)
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM reactions WHERE message_id = ? AND reactor_id = ?", (str(message.id), member.id))
        conn.commit()
        conn.close()
    elif str(payload.emoji) == DOWNVOTE_EMOJI:
        from db import update_karma
        update_karma(guild.id, message.author.id, 1)
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM reactions WHERE message_id = ? AND reactor_id = ?", (str(message.id), member.id))
        conn.commit()
        conn.close()

async def background_task():
    await bot.wait_until_ready()
    import pytz
    last_reset = datetime.datetime.now(pytz.timezone('US/Eastern')).date()
    while not bot.is_closed():
        await asyncio.sleep(3600)  # Every hour
        # (SQLite commits on each update so explicit "saving" isn't needed, but you can run maintenance here.)
        now = datetime.datetime.now(pytz.timezone('US/Eastern')).date()
        if now != last_reset:
            reset_usage(INITIAL_DABLOONS)
            logger.info("Usage data reset for the new day.")
            last_reset = now

def run_bot():
    bot.loop.create_task(background_task())
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    run_bot()
