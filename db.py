import sqlite3
import os

DB_PATH = os.path.join("data", "bot.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
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
    # Reaction table (optional if you need granular reaction logging)
    c.execute("""
    CREATE TABLE IF NOT EXISTS reactions (
        message_id TEXT,
        user_id INTEGER,
        value INTEGER,
        PRIMARY KEY (message_id, user_id)
    )
    """)
    conn.commit()
    conn.close()

def get_usage(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT usage_balance, bank_balance FROM usage WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row if row else None

def update_usage(user_id, delta, initial_balance):
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
            c.execute("UPDATE usage SET usage_balance = ?, bank_balance = ?, total_usage = total_usage + ? WHERE user_id = ?",
                      (new_balance, new_bank, delta, user_id))
        else:
            c.execute("UPDATE usage SET usage_balance = usage_balance - ?, total_usage = total_usage + ? WHERE user_id = ?",
                      (delta, delta, user_id))
    conn.commit()
    conn.close()

def reset_usage(initial_balance):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE usage SET usage_balance = ?", (initial_balance,))
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
