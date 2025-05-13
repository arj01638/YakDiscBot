import logging
from db import get_name, get_description, set_name

logger = logging.getLogger(__name__)

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