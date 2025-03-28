import time
import random
import logging

logger = logging.getLogger(__name__)

# Define alarming phrases for crisis response
ALARMING_WORDS = [
    "kill myself", "kms", "am going to commit suicide", "am gonna commit suicide",
    "i will commit suicide", "i want to commit suicide", "i wanna commit suicide",
    "shoot myself", "hang myself", "drown myself", "i should die", "end my life",
    "i want to die", "i crave death", "sewer slide", "i hope i die", "decapitate myself",
    "stab myself", "im gonna jump", "blow myself up", "i wish for the sweet release of death"
]

# Global variable to track the last time an insult was sent.
last_insult_date = 0


def insult_proc():
    """
    Determine if an insult should be issued based on a probability that increases
    over time since the last insult. Once an insult is sent, the timer resets.

    Returns:
        bool: True if an insult should be issued, False otherwise.
    """
    global last_insult_date
    elapsed_time = time.time() - last_insult_date
    # Scale chance from 0.001 to 0.1 over 48 hours
    chance = 0.001 + ((0.1 - 0.001) * (elapsed_time / (48 * 3600)))
    chance = min(0.1, chance)
    rand = random.random()
    logger.info(f"Insult chance check: {rand:.3f} vs {chance:.3f}")
    if rand < chance:
        last_insult_date = time.time()
        return True
    return False


async def handle_alarming_words(message, current_karma):
    """
    If a message contains alarming words, respond either with an insult if the sender
    has negative karma (and if insult_proc returns True) or with a crisis counseling message.
    """
    content = message.content.lower()
    # Special-case for "poopoo" with a fixed chance
    if "poopoo" in content and random.random() < 0.3:
        await message.reply("🟢🐴: peepee")
        return

    # If the user has negative karma and insult_proc() returns True, issue a random insult.
    if current_karma < 0 and insult_proc():
        # For insult text, assume you load a list of insults from static_config
        from personality import static_config
        insults = static_config.get("insults", [])
        if insults:
            insult_text = random.choice(insults)
            await message.reply(insult_text)
            return
    else:
        # Otherwise, provide a crisis message
        await message.reply(
            "🟢🐴: Please check out crisis resources. If you're in danger, call emergency services immediately or text HOME to 741741 for free crisis counseling."
        )
