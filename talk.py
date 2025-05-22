import logging
import re
from commands.abbreviation import expand_abbreviations
from config import DEFAULT_MODEL_ENGINE, DEFAULT_TEMPERATURE, DEFAULT_FREQ_PENALTY, DEFAULT_PRES_PENALTY, DEFAULT_TOP_P, \
    BOT_NAME
from db import get_name, get_description, set_name
from discord_helper import reply_split
from openai_helper import get_chat_response
from personality import get_personality
from utils import requires_credit

logger = logging.getLogger(__name__)

@requires_credit(lambda ctx, *args, **kwargs: 0.001)
async def handle_prompt_chain(ctx, message, bot_id):
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
    author_ids = [bot_id]

    params = {"model_engine": DEFAULT_MODEL_ENGINE,
              "temperature": DEFAULT_TEMPERATURE,
              "freq_penalty": DEFAULT_FREQ_PENALTY,
              "pres_penalty": DEFAULT_PRES_PENALTY,
              "top_p": DEFAULT_TOP_P}
    param_pattern = re.compile(r"\b(usemodel|usetemp|usefreq|usepres|usetopp)\s+(\S+)", re.IGNORECASE)
    user_id_pattern = re.compile(r"<@!?(\d{17,19})>")

    for msg in chain:
        # Extract parameters from message (later messages override earlier ones)
        for match in param_pattern.finditer(msg.content):
            key, val = match.group(1).lower(), match.group(2)
            param_mapping = {
                "usemodel": ("model_engine", str),
                "usetemp": ("temperature", float),
                "usefreq": ("freq_penalty", float),
                "usepres": ("pres_penalty", float),
                "usetopp": ("top_p", float)
            }

            if key in param_mapping:
                param_name, convert_func = param_mapping[key]
                try:
                    params[param_name] = convert_func(val)
                except ValueError:
                    pass

        clean_content = param_pattern.sub("", msg.content).strip()

        if clean_content.startswith("!"):
            clean_content = clean_content[1:]

        clean_content = expand_abbreviations(clean_content, msg.guild.id, msg.author.id)
        prompt_lines.append(f"{msg.author.id}: {clean_content}")

        author_ids.append(msg.author.id)
        mentioned_ids = user_id_pattern.findall(msg.content)
        author_ids.extend(mentioned_ids)

    # authors_information = {author_id: (name, description), ...}
    authors_information = get_author_information(author_ids, message.guild)

    for i, line in enumerate(prompt_lines):
        # this would seem inefficient but this is done to handle pings within messages
        for user_id in author_ids:
            if str(user_id) in line:
                name, _ = authors_information[user_id]
                prompt_lines[i] = prompt_lines[i].replace(str(user_id), name)

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
        if line.startswith(f"{BOT_NAME}:"):
            messages_prompt.append({"role": "assistant", "content": line.replace(f"{BOT_NAME}:", "")})
        else:
            messages_prompt.append({"role": "user", "content": line})

    response = await get_chat_response(messages_prompt,
                                       model_engine=params["model_engine"],
                                       temperature=params["temperature"],
                                       freq_penalty=params["freq_penalty"],
                                       pres_penalty=params["pres_penalty"],
                                       top_p=params["top_p"],
                                       user_id=message.author.id)

    await reply_split(message, response)


def get_author_information(author_ids, guild):
    authors_information = {}
    for author in author_ids:
        name = get_name(author)
        description = get_description(author)
        if name:
            authors_information[author] = (name, description)
        else:
            member = guild.get_member(author)
            if member:
                name = member.nick or member.display_name
                set_name(author, name)
                authors_information[author] = (name, description)
            else:
                logger.warning(f"Could not find member for user ID {author} in guild {guild.id}")
                authors_information[author] = (str(author), description)
    return authors_information
