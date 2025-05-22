import re

from bot import bot
from config import DEFAULT_MODEL_ENGINE, DEFAULT_TEMPERATURE, DEFAULT_FREQ_PENALTY, DEFAULT_PRES_PENALTY, DEFAULT_TOP_P, \
    BOT_NAME
from discord_helper import reply_split
from openai_helper import get_chat_response
from personality import get_personality
from personalization import get_author_information
from utils import requires_credit


@requires_credit(lambda ctx, *args, **kwargs: 0.001)
async def handle_prompt_chain(ctx, message):
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
    author_ids = [bot.user.id]

    params = {"model_engine": DEFAULT_MODEL_ENGINE,
              "temperature": DEFAULT_TEMPERATURE,
              "freq_penalty": DEFAULT_FREQ_PENALTY,
              "pres_penalty": DEFAULT_PRES_PENALTY,
              "top_p": DEFAULT_TOP_P}
    param_pattern = re.compile(r"\b(usemodel|usetemp|usefreq|usepres|usetopp)\s+(\S+)", re.IGNORECASE)

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

        prompt_lines.append(f"{msg.author.id}: {clean_content}")
        author_ids.append(msg.author.id)

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
    bot_id = bot.user.id
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
