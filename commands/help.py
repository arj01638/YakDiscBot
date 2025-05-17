import discord
from discord.ext import commands

class YakHelp(commands.MinimalHelpCommand):
    async def send_pages(self):
        destination = self.get_destination()
        embed = discord.Embed(
            title='Help',
            description='Ping the bot and type the name of any of the following commands:',
            color=0x00DCB8
        )
        embed.add_field(
            name='@Yak leaderboard',
            value='Karma leaderboard. React with your configured upvote/downvote emojis to influence karma.\nUsage: @Yak leaderboard [number] [b for bottom]',
            inline=False
        )
        embed.add_field(
            name='@Yak karma',
            value='Display your current karma score.',
            inline=False
        )
        embed.add_field(
            name='@Yak tokens / dabloons',
            value='Check your AI resource balance (resets daily at 8pm EST).',
            inline=False
        )
        embed.add_field(
            name='@Yak genimage [prompt]',
            value='Generate an image using DALL-E 3 (with optional "hoz"/"vert" modifiers).',
            inline=False
        )
        embed.add_field(
            name='@Yak sdultra / sdcore / dalle2 / dalle3hd / searchandreplace / imagetovideo / getvideo',
            value='Commands to generate or edit images using Stability or OpenAI APIs.',
            inline=False
        )
        embed.add_field(
            name='@Yak aihelp',
            value='Display this comprehensive help message covering AI commands and advanced prompt modifiers.',
            inline=False
        )
        embed.add_field(
            name='@Yak psychoanalyze',
            value='Perform an in-depth analysis of your message history using OpenAI.',
            inline=False
        )
        embed.add_field(
            name='@Yak qt / qt1 / togglestream',
            value='Custom AI completion commands with adjustable parameters.',
            inline=False
        )
        embed.add_field(
            name='@Yak reactees / reactors / haters / popularity / stats / topalltime',
            value='Commands related to reaction-based karma and statistics.',
            inline=False
        )
        embed.add_field(
            name='@Yak tts',
            value='Convert text to speech (TTS) and return it as a video.',
            inline=False
        )
        await destination.send(embed=embed)

async def setup(bot):
    bot.help_command = YakHelp()
