import sqlite3
import os

from config import INITIAL_DABLOONS, BOT_NAME, ADMIN_USER_ID

DB_PATH = os.path.join("data", "bot.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(bot_id):
    conn = get_connection()
    c = conn.cursor()
    # Usage table: user_id, usage_balance, bank_balance, total_usage
    c.execute("""
    CREATE TABLE IF NOT EXISTS usage (
        user_id INTEGER PRIMARY KEY,
        usage_balance REAL,
        bank_balance REAL,
        total_usage REAL DEFAULT 0
    )
    """)
    # Karma table: guild_id, user_id, karma
    c.execute("""
    CREATE TABLE IF NOT EXISTS karma (
        guild_id INTEGER,
        user_id INTEGER,
        karma INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )
    """)
    # Reaction table: message_id, reactor_id, reactee_id, value
    c.execute("""
    CREATE TABLE IF NOT EXISTS reactions (
        message_id TEXT,
        reactor_id INTEGER,
        reactee_id INTEGER,
        value TEXT,
        PRIMARY KEY (message_id, reactor_id, value)
    )
    """)
    # Identities table: user_id, name, description
    c.execute("""
    CREATE TABLE IF NOT EXISTS identities (
        user_id INTEGER,
        name TEXT,
        description TEXT
    )
    """)

    # add to identities table bot_id as Gluemo
    c.execute("""
    INSERT OR IGNORE INTO identities (user_id, name, description) VALUES (?, ?, ?)
    """, (bot_id, BOT_NAME, ""))

    # meta info, like last reset date
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS abbreviations (
        guild_id INTEGER,
        user_id INTEGER,
        key TEXT,
        value TEXT,
        PRIMARY KEY (guild_id, user_id, key)
    )
    """)

    conn.commit()
    conn.close()

def set_abbreviation(guild_id, user_id, key, value):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO abbreviations (guild_id, user_id, key, value)
        VALUES (?, ?, ?, ?)
    """, (guild_id, user_id, key, value))
    conn.commit()
    conn.close()

def get_abbreviation(guild_id, user_id, key):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT value FROM abbreviations WHERE guild_id = ? AND user_id = ? AND key = ?
    """, (guild_id, user_id, key))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else None

def get_all_abbreviations(guild_id, user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT key, value FROM abbreviations WHERE guild_id = ? AND user_id = ?
    """, (guild_id, user_id))
    rows = c.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

def delete_abbreviation(guild_id, user_id, key):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        DELETE FROM abbreviations WHERE guild_id = ? AND user_id = ? AND key = ?
    """, (guild_id, user_id, key))
    conn.commit()
    conn.close()

def set_meta(key, value):
    conn = get_connection()
    c = conn.cursor()
    c.execute("REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_meta(key):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM meta WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else None

def get_name(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM identities WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["name"] if row else None


def set_name(user_id, name):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO identities (user_id, name) VALUES (?, ?)", (user_id, name))
    conn.commit()
    conn.close()


def get_description(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT description FROM identities WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["description"] if row else None


def set_description(user_id, description):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO identities (user_id, description) VALUES (?, ?)", (user_id, description))
    conn.commit()
    conn.close()


def get_usage(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT usage_balance, bank_balance FROM usage WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row if row else None

def get_balance(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT usage_balance, bank_balance FROM usage WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["usage_balance"] if row else None

def positive_balance(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT usage_balance FROM usage WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["usage_balance"] > 0 if row else False


def update_usage(user_id, delta, initial_balance=INITIAL_DABLOONS):
    conn = get_connection()
    c = conn.cursor()
    usage = get_usage(user_id)
    if usage is None:
        c.execute("INSERT INTO usage (user_id, usage_balance, bank_balance) VALUES (?, ?, ?)",
                  (user_id, initial_balance - delta, 0))
    else:
        new_balance = usage["usage_balance"] - delta
        if new_balance < 0:
            # If not enough usage, subtract the remainder from bank_balance
            remainder = -new_balance
            new_bank = max(usage["bank_balance"] - remainder, 0)
            new_balance = 0
            c.execute(
                "UPDATE usage SET usage_balance = ?, bank_balance = ?, total_usage = total_usage + ? WHERE user_id = ?",
                (new_balance, new_bank, delta, user_id))
        else:
            c.execute(
                "UPDATE usage SET usage_balance = usage_balance - ?, total_usage = total_usage + ? WHERE user_id = ?",
                (delta, delta, user_id))
    conn.commit()
    conn.close()


def reset_usage(initial_balance):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE usage SET usage_balance = ?", (initial_balance,))
    # set admin user_id to 10 * initial_balance
    c.execute("UPDATE usage SET usage_balance = ? WHERE user_id = ?", (10 * initial_balance, ADMIN_USER_ID))
    conn.commit()
    conn.close()


def get_karma(guild_id, user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT karma FROM karma WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    row = c.fetchone()
    conn.close()
    return row["karma"] if row else 0


def update_karma(guild_id, user_id, delta):
    conn = get_connection()
    c = conn.cursor()
    karma = get_karma(guild_id, user_id)
    if karma is None:
        c.execute("INSERT INTO karma (guild_id, user_id, karma) VALUES (?, ?, ?)", (guild_id, user_id, delta))
    else:
        c.execute("UPDATE karma SET karma = karma + ? WHERE guild_id = ? AND user_id = ?", (delta, guild_id, user_id))
    conn.commit()
    conn.close()


def add_reaction(message_id, user_id, author_id, value):
    conn = get_connection()
    c = conn.cursor()
    # Check if the reaction already exists
    c.execute("SELECT * FROM reactions WHERE message_id = ? AND reactor_id = ? AND value = ?",
              (message_id, user_id, value))
    row = c.fetchone()
    if row:
        # Update the existing reaction
        c.execute("UPDATE reactions SET reactee_id = ? WHERE message_id = ? AND reactor_id = ? AND value = ?",
                  (author_id, message_id, user_id, value))
    else:
        # Insert a new reaction
        c.execute("INSERT INTO reactions (message_id, reactor_id, reactee_id, value) VALUES (?, ?, ?, ?)",
                  (message_id, user_id, author_id, value))
    conn.commit()
    conn.close()


def remove_reaction(message_id, user_id, value):
    conn = get_connection()
    c = conn.cursor()
    # Delete the reaction
    c.execute("DELETE FROM reactions WHERE message_id = ? AND reactor_id = ? AND value = ?",
              (message_id, user_id, value))
    conn.commit()
    conn.close()


def get_karma_snippet(guild_id, limit=5):
    """
    Return a snippet (top users by karma) for a guild as a dict {user_id: karma}.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, karma FROM karma WHERE guild_id = ? ORDER BY karma DESC LIMIT ?
    """, (guild_id, limit))
    rows = c.fetchall()
    conn.close()
    return {row["user_id"]: row["karma"] for row in rows}


def get_usage_snippet(limit=5):
    """
    Return a snippet of usage data as a dict {user_id: (usage_balance, bank_balance)}.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, usage_balance, bank_balance FROM usage ORDER BY usage_balance DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return {row["user_id"]: (row["usage_balance"], row["bank_balance"]) for row in rows}


def get_identities_snippet(limit=5):
    """
    Return a snippet of identities as a dict {user_id: (name, description)}.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, name, description FROM identities LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return {row["user_id"]: (row["name"], row["description"]) for row in rows}
