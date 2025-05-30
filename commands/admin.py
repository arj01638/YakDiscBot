import asyncio
import logging
import time
import tracemalloc
import sqlite3
from discord.ext import commands
from db import update_usage, reset_usage, get_connection
from config import INITIAL_DABLOONS, ADMIN_USER_ID
import json
import os

from discord_helper import get_msg

logger = logging.getLogger(__name__)

def is_admin(ctx):
    return ctx.author.id == ADMIN_USER_ID

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="droptable", help="Drop the provided table (admin only).")
    async def droptable(self, ctx, table_name: str):
        if not is_admin(ctx):
            await ctx.send("You do not have permission to use this command.")
            return
        conn = get_connection()
        c = conn.cursor()
        try:
            c.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.commit()
            await ctx.send(f"Table {table_name} has been dropped.")
        except sqlite3.Error as e:
            await ctx.send(f"Error dropping table: {e}")
        finally:
            conn.close()


    @commands.command(name="profilememory", help="Profile memory usage of a given command. Usage: !profilememory <command_name> [arg]")
    async def profilememory(self, ctx, command_name: str, arg: str = ""):
        if not is_admin(ctx):
            await ctx.send("You do not have permission to use this command.")
            return
        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()
        try:
            func = self.bot.get_command(command_name)
            if func:
                if arg:
                    await ctx.invoke(func, arg)
                else:
                    await ctx.invoke(func)
            else:
                await ctx.send("Command not found.")
        except Exception as e:
            await ctx.send(f"Error: {e}")
        snapshot_after = tracemalloc.take_snapshot()
        stats = snapshot_after.compare_to(snapshot_before, 'lineno')
        diff_text = "\n".join(str(stat) for stat in stats[:10])
        await ctx.send(f"Top 10 memory differences:\n{diff_text}")
        tracemalloc.stop()

    @commands.command(name="scrapedata", help="Scrape all message data from the server (admin only).")
    async def scrapedata(self, ctx):
        if not is_admin(ctx):
            await ctx.send("You do not have permission to use this command.")
            return
        messages = {}
        count = 0
        conn = get_connection()
        c = conn.cursor()
        # Iterate through all text channels of the guild where the command was invoked.
        for channel in ctx.guild.text_channels:
            try:
                async for message in channel.history(limit=None):
                    try:
                        count += 1
                        msg_id = str(message.id)
                        if msg_id not in messages:
                            replied_msg = ""
                            replied_author = ""
                            if message.reference and message.reference.message_id:
                                try:
                                    ref_msg = await get_msg(self.bot, channel, message.reference.message_id)
                                    replied_msg = str(ref_msg.id)
                                    replied_author = str(ref_msg.author.id)
                                except Exception:
                                    replied_msg = ""
                                    replied_author = ""
                            messages[msg_id] = [
                                message.author.id,
                                replied_msg,
                                replied_author,
                                message.content,
                                message.channel.id,
                                message.created_at.timestamp(),
                                [att.url for att in message.attachments]
                            ]
                        # Process reactions for this message
                        for reaction in message.reactions:
                            async for user in reaction.users():
                                try:
                                    # Insert or update reaction in DB
                                    c.execute(
                                        "SELECT * FROM reactions WHERE message_id = ? AND reactor_id = ? AND value = ?",
                                        (msg_id, user.id, str(reaction.emoji)))
                                    row = c.fetchone()
                                    if row:
                                        # Update reactee_id if needed
                                        c.execute(
                                            "UPDATE reactions SET reactee_id = ? WHERE message_id = ? AND reactor_id = ? AND value = ?",
                                            (message.author.id, msg_id, user.id, str(reaction.emoji)))
                                    else:
                                        c.execute(
                                            "INSERT INTO reactions (message_id, reactor_id, reactee_id, value) VALUES (?, ?, ?, ?)",
                                            (msg_id, user.id, message.author.id, str(reaction.emoji)))
                                except Exception as e:
                                    logger.error(f"Error processing reaction: {e}")
                    except Exception as inner_e:
                        logger.error(f"Error processing message: {inner_e}")
            except Exception as e:
                logger.error(f"Error accessing channel {channel.name}: {e}")
        conn.commit()
        conn.close()
        # Write to file
        os.makedirs("data", exist_ok=True)
        with open("data/messages.json", "w", encoding="utf-8") as f:
            json.dump(messages, f)
        await ctx.send(f"Scraped {count} messages and updated reactions.")

    @commands.command(name="resetusagedata", help="Manually reset user token balances (admin only).")
    async def resetusagedata(self, ctx):
        if not is_admin(ctx):
            await ctx.send("You do not have permission to use this command.")
            return
        reset_usage(INITIAL_DABLOONS)
        await ctx.send("Usage data has been reset.")

    @commands.command(name="printusage", help="Print detailed usage statistics (admin only).")
    async def printusage(self, ctx):
        if not is_admin(ctx):
            await ctx.send("You do not have permission to use this command.")
            return
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT user_id, usage_balance, bank_balance, total_usage FROM usage")
        rows = c.fetchall()
        conn.close()
        if not rows:
            await ctx.send("No usage data found.")
            return
        lines = ["| User ID | Usage Balance | Bank Balance | Total Usage |", "|---------|---------------|--------------|-------------|"]
        for row in rows:
            lines.append(f"| {row['user_id']} | {row['usage_balance']} | {row['bank_balance']} | {row['total_usage']} |")
        await ctx.send("\n".join(lines))

    @commands.command(name="addbankdabloons", help="Add bank dabloons to a user (admin only). Usage: !addbankdabloons <user_id> <amount>")
    async def addbankdabloons(self, ctx, user_id: int, amount: float):
        if not is_admin(ctx):
            await ctx.send("You do not have permission to use this command.")
            return
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT bank_balance FROM usage WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row:
            new_bank = row["bank_balance"] + amount
            c.execute("UPDATE usage SET bank_balance = ? WHERE user_id = ?", (new_bank, user_id))
        else:
            c.execute("INSERT INTO usage (user_id, usage_balance, bank_balance) VALUES (?, ?, ?)",
                      (user_id, INITIAL_DABLOONS, amount))
        conn.commit()
        conn.close()
        await ctx.send(f"Added {amount} bank dabloons to user {user_id}.")

    @commands.command(name="adddabloons", help="Add usage dabloons to a user (admin only). Usage: !adddabloons <user_id> <amount>")
    async def adddabloons(self, ctx, user_id: int, amount: float):
        if not is_admin(ctx):
            await ctx.send("You do not have permission to use this command.")
            return
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT usage_balance FROM usage WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row:
            new_usage = row["usage_balance"] + amount
            c.execute("UPDATE usage SET usage_balance = ? WHERE user_id = ?", (new_usage, user_id))
        else:
            c.execute("INSERT INTO usage (user_id, usage_balance, bank_balance) VALUES (?, ?, ?)",
                      (user_id, INITIAL_DABLOONS + amount, 0))
        conn.commit()
        conn.close()
        await ctx.send(f"Added {amount} usage dabloons to user {user_id}.")

    @commands.command(name="modifykarma", help="Modify a user's karma (admin only). Usage: !modifykarma <guild_id> <user_id> <amount>")
    async def modifykarma(self, ctx, guild_id: int, user_id: int, amount: int):
        if not is_admin(ctx):
            await ctx.send("You do not have permission to use this command.")
            return
        from db import update_karma, get_karma
        update_karma(guild_id, user_id, amount)
        new_karma = get_karma(guild_id, user_id)
        await ctx.send(f"Updated karma for user {user_id} in guild {guild_id} by {amount}. New karma: {new_karma}")

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
