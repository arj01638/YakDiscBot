import json
import os
import random
import math
import gc
from datetime import datetime, timedelta
import requests
import time
import logging
import openai
import tiktoken

logger = logging.getLogger(__name__)

def fix_cdn_url(expired_url):
    from urllib.parse import urlparse, urlunparse, parse_qs
    def fixcdn():
        parsed_url = urlparse(expired_url)
        new_path = parsed_url.path
        return urlunparse(('https', 'fixcdn.hyonsu.com', new_path, '', '', ''))
    parsed_url = urlparse(expired_url)
    query_params = parse_qs(parsed_url.query)
    ex_str = query_params.get('ex', [None])[0]
    if ex_str:
        ex_time = int(ex_str, 16) * 1000
        if ex_time <= int(time.time()*1000):
            return fixcdn()
    response = requests.head(expired_url)
    if response.status_code == 404:
        return fixcdn()
    response = requests.get(expired_url)
    if response.status_code == 200 and 'This content is no longer available' in response.text:
        return fixcdn()
    return expired_url

def generate_messages(user_name, model_engine, randomly_sample=False):
    # Loads messages2.json and processes them into a text file for the given user.
    with open("data/messages2.json", "r") as file:
        messages = json.load(file)
    messages_list_master = []
    for key, value in messages.items():
        # Each message: [msg_id, author, reply_id, reply_author, content, channel, timestamp, attachments]
        messages_list_master.append([
            int(key),
            str(value[0]),
            int(value[1]) if value[1] != "" else "",
            value[2],
            value[3],
            value[4],
            value[5],
            value[6]
        ])
    messages_list_master.reverse()  # oldest first
    # Filter messages
    messages_list = [t for t in messages_list_master if (t[1] == user_name or randomly_sample) and len(t[4]) < 1000]
    old_timestamp = datetime.now() - timedelta(weeks=52)
    messages_list = [t for t in messages_list if t[6] > old_timestamp.timestamp()]
    # Optionally, insert replied-to messages for context (if not randomly sampling)
    if not randomly_sample:
        i = 0
        while i < len(messages_list):
            if messages_list[i][2] != "":
                replied = next((t for t in messages_list_master if t[0] == messages_list[i][2]), None)
                if replied and len(replied[4]) <= 300:
                    messages_list.insert(i, replied)
                    i += 1
            i += 1
    # Purge messages if token count exceeds threshold (using a sigmoid-based purge)
    tokens = get_tokens(messages_list, model_engine)
    while tokens > 64000:
        purge_length = 10
        for _ in range(math.ceil( (200 / ((purge_length/10.0)+math.exp((-0.00002*tokens)+3.6))) - 17 )):
            index = random.randint(0, len(messages_list)-purge_length)
            # Skip if context would be broken
            if index > 2 and messages_list[index-2][4].endswith("\n\n"):
                continue
            for _ in range(purge_length):
                del messages_list[index]
        tokens = get_tokens(messages_list, model_engine)
    # Write to text file
    out_path = f"data/{user_name}.txt"
    with open(out_path, "w+", encoding="utf-8") as file:
        for message in messages_list:
            if message[2] != "":
                replied = next((t for t in messages_list if t[0] == message[2]), None)
                if replied:
                    entry = f"{get_nick(message[1])} replying to {get_nick(replied[1])}: {message[4]}\n"
                else:
                    entry = f"{get_nick(message[1])} replying to Unknown: {message[4]}\n"
            else:
                entry = f"{get_nick(message[1])}: {message[4]}\n"
            file.write(entry)
    return out_path

def get_tokens(messages_list, model_engine):
    encoding = tiktoken.encoding_for_model(model_engine)
    token_count = 0
    for message in messages_list:
        token_count += len(encoding.encode(f"{get_nick(message[1])}: {message[4]}\n"))
    return token_count

def clean_messages():
    # Load raw messages from data/messages.json, substitute names, and add image descriptions.
    with open("data/messages.json", "r+") as file:
        messages = json.load(file)
    # Substitute names using static config (loaded in personality.py)
    from personality import static_config
    user_dict = static_config["user_dict"]
    for key, value in messages.items():
        if value[0] in user_dict:
            value[0] = user_dict[value[0]]
        if value[2] != "" and int(value[2]) in user_dict:
            value[2] = user_dict[int(value[2])]
        for id_str, name in user_dict.items():
            value[3] = value[3].replace(str(id_str), name)
    # Describe images
    if os.path.exists("data/url_to_img_desc.json"):
        with open("data/url_to_img_desc.json", "r") as file:
            url_to_img_desc = json.load(file)
    else:
        url_to_img_desc = {}
    for key, value in messages.items():
        for attachment in value[6]:
            if attachment in url_to_img_desc:
                value[3] += f"\n(Message Attachment: {url_to_img_desc[attachment]})"
            else:
                extensions = [".jpg", ".jpeg", ".png", ".gif"]
                if any(ext in attachment for ext in extensions):
                    fixed_url = fix_cdn_url(attachment)
                    prompt = [{"role": "user", "content": "Describe this image very briefly."}]
                    try:
                        response = openai.ChatCompletion.create(
                            model="gpt-4o-mini",
                            messages=prompt,
                            temperature=1,
                            top_p=1
                        )
                        description = response.choices[0].message.content
                        url_to_img_desc[attachment] = description
                        value[3] += f"\n(Message Attachment: {description})"
                    except Exception as e:
                        value[3] += f"\n(Message Attachment: {attachment})"
                else:
                    value[3] += f"\n(Message Attachment: {attachment})"
    with open("data/url_to_img_desc.json", "w") as file:
        json.dump(url_to_img_desc, file)
    with open("data/messages2.json", "w") as file:
        json.dump(messages, file)

def get_nick(name):
    from personality import static_config
    nick_dict = static_config["nick_dict"]
    return nick_dict.get(name, name[:3])
