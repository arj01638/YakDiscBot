import logging
import re
from commands.abbreviation import expand_abbreviations
from config import DEFAULT_MODEL_ENGINE, DEFAULT_TEMPERATURE, DEFAULT_TOP_P, TEST_SERVER_ID
from db import get_name, get_description, set_name
from discord_helper import reply_split
from openai_helper import get_chat_response
from personality import get_personality
from utils import requires_credit
from types import SimpleNamespace

logger = logging.getLogger(__name__)


@requires_credit(lambda ctx, *args, **kwargs: 0.001)
async def handle_prompt_chain(ctx, message, bot_id):
    """
    Collects the conversation from a reply chain, builds a prompt,
    sends it to the AI, and replies using reply_split.
    """
    is_test_server = ctx.guild.id == TEST_SERVER_ID

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
              "top_p": DEFAULT_TOP_P}
    param_pattern = re.compile(r"\b(usemodel|usetemp|usetopp)\s+(\S+)", re.IGNORECASE)
    user_id_pattern = re.compile(r"<@!?(\d{17,19})>")

    for msg in chain:
        # Extract parameters from message (later messages override earlier ones)
        for match in param_pattern.finditer(msg.content):
            key, val = match.group(1).lower(), match.group(2)
            param_mapping = {
                "usemodel": ("model_engine", str),
                "usetemp": ("temperature", float),
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
        prompt_lines.append(["assistant" if msg.author.id == bot_id else "user",
                             f"{clean_content}" if is_test_server or msg.author.id == bot_id else f"{msg.author.id}: {clean_content}",
                             list(msg.attachments)])

        embed_urls = []
        for embed in msg.embeds:
            # main embed image
            if embed.image and embed.image.url:
                embed_urls.append(embed.image.url)
            # thumbnail
            if embed.thumbnail and embed.thumbnail.url:
                embed_urls.append(embed.thumbnail.url)
        for url in embed_urls:
            prompt_lines[-1][2].append(SimpleNamespace(url=url))

        if not is_test_server:
            author_ids.append(msg.author.id)
            mentioned_ids = user_id_pattern.findall(msg.content)
            author_ids.extend(mentioned_ids)

    # Collapse bck-to-back bot messages
    collapsed = []
    for role, text, attachments in prompt_lines:
        if collapsed and role == "assistant" and collapsed[-1][0] == "assistant":
            # merge with previous assistant turn
            collapsed[-1][1] += text
            collapsed[-1][2].extend(attachments)
        else:
            collapsed.append([role, text, attachments])
    prompt_lines = collapsed

    # authors_information = {author_id: (name, description), ...}
    authors_information = get_author_information(author_ids, message.guild)

    for i, line in enumerate(prompt_lines):
        # this would seem inefficient but this is done to handle pings within messages
        for user_id in author_ids:
            if str(user_id) in line[1]:
                name, _ = authors_information[user_id]
                prompt_lines[i][1] = prompt_lines[i][1].replace(str(user_id), name)

    personality = get_personality(message.guild.id, prompt_lines)
    system_msg = personality
    added_memory_section = False
    if not is_test_server:
        system_msg += "\n\nUser IDs:\n"
        for author_id in authors_information:
            name, description = authors_information[author_id]
            system_msg += f"\n{name}: {author_id}"

        for author_id in authors_information:
            name, description = authors_information[author_id]
            if description:
                if not added_memory_section:
                    system_msg += "\n\nUser Memories:\n"
                    added_memory_section = True
                system_msg += f"\n{name}: {description}"

    messages_prompt = [
        {"role": "system",
         "content": system_msg}
    ] if system_msg else []

    for role, text, attachments in prompt_lines:
        if not attachments:
            messages_prompt.append({
                "role": role,
                "content": text
            })
        else:
            content = [{"type": "text", "text": text}]
            for attachment in attachments:
                if attachment.url:
                    content.append({
                        "type": "input_image",
                        "image_url": attachment.url
                    })
                else:
                    logger.warning(f"Attachment URL not found for message ID {attachment.id}")
            messages_prompt.append({
                "role": role,
                "content": content
            })

    response, image = await get_chat_response(messages_prompt,
                                       model_engine=params["model_engine"],
                                       temperature=params["temperature"],
                                       top_p=params["top_p"],
                                       user_id=message.author.id)

    await reply_split(message, response, image)


def get_author_information(author_ids, guild):
    print(f"Author IDs: {author_ids}")
    authors_information = {}
    for author in author_ids:
        name = get_name(int(author))
        if name:
            description = get_description(int(author))
            authors_information[author] = (name, description)
        else:
            member = guild.get_member(author)
            if member:
                name = member.nick or member.display_name
                set_name(author, name)
                authors_information[author] = (name, "")
            else:
                logger.warning(f"Could not find member for user ID {author} in guild {guild.id}")
                authors_information[author] = (str(author), "")
    return authors_information
