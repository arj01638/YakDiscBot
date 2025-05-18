import discord
from discord.ext import commands
import logging
from db import get_connection
from config import UPVOTE_EMOJI, DOWNVOTE_EMOJI

logger = logging.getLogger(__name__)

def get_reaction_stats():
    conn = get_connection()
    c = conn.cursor()
    # Sum up reactions by reactor and recipient.
    c.execute(f"""
        SELECT reactor_id,
               SUM(CASE WHEN value = ? THEN 1 ELSE 0 END) as up_given,
               SUM(CASE WHEN value = ? THEN 1 ELSE 0 END) as down_given
        FROM reactions
        GROUP BY reactor_id
    """, (UPVOTE_EMOJI, DOWNVOTE_EMOJI))
    given = c.fetchall()

    c.execute(f"""
        SELECT reactee_id,
               SUM(CASE WHEN value = ? THEN 1 ELSE 0 END) as up_received,
               SUM(CASE WHEN value = ? THEN 1 ELSE 0 END) as down_received
        FROM reactions
        GROUP BY reactee_id
    """, (UPVOTE_EMOJI, DOWNVOTE_EMOJI))
    received = c.fetchall()

    conn.close()
    return given, received

def get_reaction_details():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM reactions")
    rows = c.fetchall()
    conn.close()
    return rows

class ReactionCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="leaderboard", help="Display the karma leaderboard.")
    async def leaderboard(self, ctx, top_n: int = 10):
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT user_id, karma FROM karma WHERE guild_id = ? ORDER BY karma DESC LIMIT ?",
                  (ctx.guild.id, top_n))
        rows = c.fetchall()
        conn.close()
        if not rows:
            await ctx.send("No karma data available.")
            return
        embed = discord.Embed(title="Karma Leaderboard", color=0x00DCB8)
        rank = 1
        for row in rows:
            user = await self.bot.fetch_user(row["user_id"])
            embed.add_field(name=f"{rank}. {user.display_name}", value=f"Karma: {row['karma']}", inline=False)
            rank += 1
        await ctx.send(embed=embed)

    @commands.command(name="stats", help="Display your reaction statistics (upvotes/downvotes given and received).")
    async def stats(self, ctx, user_id: int = None):
        target = user_id or ctx.author.id
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"""
            SELECT 
                SUM(CASE WHEN reactor_id = ? AND value = ? THEN 1 ELSE 0 END) as up_given,
                SUM(CASE WHEN reactor_id = ? AND value = ? THEN 1 ELSE 0 END) as down_given,
                SUM(CASE WHEN reactee_id = ? AND value = ? THEN 1 ELSE 0 END) as up_received,
                SUM(CASE WHEN reactee_id = ? AND value = ? THEN 1 ELSE 0 END) as down_received
            FROM reactions
        """, (
            target, UPVOTE_EMOJI,
            target, DOWNVOTE_EMOJI,
            target, UPVOTE_EMOJI,
            target, DOWNVOTE_EMOJI,
        ))
        row = c.fetchone()
        conn.close()
        embed = discord.Embed(title=f"Reaction Stats for User {target}", color=0xFFFF00)
        embed.add_field(name="Upvotes Given", value=row["up_given"] or 0, inline=False)
        embed.add_field(name="Downvotes Given", value=row["down_given"] or 0, inline=False)
        embed.add_field(name="Upvotes Received", value=row["up_received"] or 0, inline=False)
        embed.add_field(name="Downvotes Received", value=row["down_received"] or 0, inline=False)
        # Calculate ratios if possible
        ratio_given = (row["up_given"] / row["down_given"]) if row["down_given"] and row["down_given"] > 0 else row["up_given"] or 0
        ratio_received = (row["up_received"] / row["down_received"]) if row["down_received"] and row["down_received"] > 0 else row["up_received"] or 0
        embed.add_field(name="Given Ratio (Higher is nicer)", value=round(ratio_given, 2), inline=False)
        embed.add_field(name="Received Ratio (Higher is popular)", value=round(ratio_received, 2), inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="haters", help="List the most hateful users based on upvote/downvote ratios of reactions given.")
    async def haters(self, ctx, top_n: int = 5):
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"""
            SELECT reactor_id,
                   SUM(CASE WHEN value = ? THEN 1 ELSE 0 END) as up_given,
                   SUM(CASE WHEN value = ? THEN 1 ELSE 0 END) as down_given
            FROM reactions
            GROUP BY reactor_id
        """, (UPVOTE_EMOJI, DOWNVOTE_EMOJI))
        rows = c.fetchall()
        conn.close()
        ratios = []
        for row in rows:
            up = row["up_given"] or 0
            down = row["down_given"] or 0
            ratio = up / down if down > 0 else up  # if down is 0, use up as the metric
            ratios.append((row["reactor_id"], ratio))
        # For haters, we want the lowest ratio.
        ratios.sort(key=lambda x: x[1])
        embed = discord.Embed(title="Most Hateful Users (by reactions given)", color=0x00DCB8)
        rank = 1
        for user_id, ratio in ratios[:top_n]:
            user = await self.bot.fetch_user(user_id)
            embed.add_field(name=f"{rank}. {user.display_name}", value=f"Ratio: {round(ratio, 2)}", inline=False)
            rank += 1
        await ctx.send(embed=embed)

    @commands.command(name="popularity", help="List the most popular users based on reactions received.")
    async def popularity(self, ctx, top_n: int = 5):
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"""
            SELECT reactee_id,
                   SUM(CASE WHEN value = ? THEN 1 ELSE 0 END) as up_received,
                   SUM(CASE WHEN value = ? THEN 1 ELSE 0 END) as down_received
            FROM reactions
            GROUP BY reactee_id
        """, (UPVOTE_EMOJI, DOWNVOTE_EMOJI))
        rows = c.fetchall()
        conn.close()
        ratios = []
        for row in rows:
            up = row["up_received"] or 0
            down = row["down_received"] or 0
            ratio = up / down if down > 0 else up
            ratios.append((row["reactee_id"], ratio))
        # For popularity, we want the highest ratio.
        ratios.sort(key=lambda x: x[1], reverse=True)
        embed = discord.Embed(title="Most Popular Users (by reactions received)", color=0x00DCB8)
        rank = 1
        for user_id, ratio in ratios[:top_n]:
            user = await self.bot.fetch_user(user_id)
            embed.add_field(name=f"{rank}. {user.display_name}", value=f"Ratio: {round(ratio, 2)}", inline=False)
            rank += 1
        await ctx.send(embed=embed)

    @commands.command(name="reactees", help="List the top 5 users you have reacted to.")
    async def reactees(self, ctx, top_n: int = 5):
        target = ctx.author.id
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
                    SELECT reactee_id, COUNT(*) as count
                    FROM reactions
                    WHERE reactor_id = ?
                    GROUP BY reactee_id
                    ORDER BY count DESC
                    LIMIT ?
                """, (target, top_n))
        rows = c.fetchall()
        conn.close()
        embed = discord.Embed(title=f"Users {target} has reacted to", color=0xFFFF00)
        rank = 1
        for row in rows:
            user = await self.bot.fetch_user(row["reactee_id"])
            embed.add_field(name=f"{rank}. {user.display_name}", value=f"Reactions: {row['count']}", inline=False)
            rank += 1
        await ctx.send(embed=embed)

    @commands.command(name="reactors", help="List the top 5 users who have reacted to you.")
    async def reactors(self, ctx, top_n: int = 5):
        target = ctx.author.id
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
                    SELECT reactor_id, COUNT(*) as count
                    FROM reactions
                    WHERE reactee_id = ?
                    GROUP BY reactor_id
                    ORDER BY count DESC
                    LIMIT ?
                """, (target, top_n))
        rows = c.fetchall()
        conn.close()
        embed = discord.Embed(title=f"Users who reacted to {target}", color=0xFFFF00)
        rank = 1
        for row in rows:
            user = await self.bot.fetch_user(row["reactor_id"])
            embed.add_field(name=f"{rank}. {user.display_name}", value=f"Reactions: {row['count']}", inline=False)
            rank += 1
        await ctx.send(embed=embed)

    @commands.command(name="topalltime", help="Show the top posts of all time based on reaction scores.")
    async def topalltime(self, ctx, top_n: int = 3):
        conn = get_connection()
        c = conn.cursor()
        # compute a net score: +1 for upvote, -1 for downvote
        c.execute(f"""
            SELECT message_id,
                   SUM(
                     CASE
                       WHEN value = ? THEN 1
                       WHEN value = ? THEN -1
                       ELSE 0
                     END
                   ) as score
            FROM reactions
            GROUP BY message_id
            ORDER BY score DESC
            LIMIT ?
        """, (UPVOTE_EMOJI, DOWNVOTE_EMOJI, top_n))
        rows = c.fetchall()
        conn.close()
        if not rows:
            await ctx.send("No reaction data available.")
            return
        embed = discord.Embed(title=f"Top {top_n} All-Time Posts", color=0x00DCB8)
        rank = 1
        for row in rows:
            # Try to fetch the message link by iterating through channels.
            msg_link = "Link not found"
            for channel in ctx.guild.text_channels:
                try:
                    msg = await channel.fetch_message(int(row["message_id"]))
                    msg_link = msg.jump_url
                    break
                except Exception:
                    continue
            embed.add_field(name=f"{rank}. Score: {row['score']}", value=f"Message Link: {msg_link}", inline=False)
            rank += 1
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ReactionCommands(bot))
