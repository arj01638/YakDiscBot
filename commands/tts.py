from discord.ext import commands
import logging
from openai_helper import get_tts
from discord_helper import reply_split
import os
import time
from moviepy.video.VideoClip import ColorClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
import io
import discord
from config import TTS_MODEL, TTS_HD_MODEL, DEFAULT_VOICE
from db import update_usage

logger = logging.getLogger(__name__)

class TTS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # TODO: implement
    # async def reply_with_movie(self, ctx, response):
    #     temp_audio = f"temp_speech{int(time.time())}.mp3"
    #     response.stream_to_file(temp_audio)
    #     # Create a black screen video clip with proper FPS and duration using updated moviepy
    #     video_clip = ColorClip(size=(128, 128), color=(0, 0, 0), duration=AudioFileClip(temp_audio).duration)
    #     audio_clip = AudioFileClip(temp_audio)
    #     video_clip = video_clip.set_audio(audio_clip)
    #     temp_video = f"temp_video{int(time.time())}.mp4"
    #     video_clip.write_videofile(temp_video, codec='libx264', audio_codec='aac', fps=24)
    #     with open(temp_video, "rb") as f:
    #         video_data = f.read()
    #     os.remove(temp_audio)
    #     os.remove(temp_video)
    #     video_file = io.BytesIO(video_data)
    #     discord_file = discord.File(video_file, filename="speech.mp4")
    #     await ctx.reply(file=discord_file)
    #
    # @commands.command(name="tts", help="Generate TTS for the given text. Usage: !tts <voice> <text>")
    # async def tts(self, ctx, voice: str, *, text: str):
    #     author_id = ctx.author.id
    #     model = TTS_MODEL
    #     if voice not in DEFAULT_VOICE:
    #         text = f"{voice} {text}"
    #         voice = DEFAULT_VOICE
    #     if "use-hd" in text or "use-hd" in voice:
    #         model = TTS_HD_MODEL
    #         text = text.replace("use-hd", "")
    #         voice = voice.replace("use-hd", "")
    #     try:
    #         response = await get_tts(model, voice, text)
    #     except Exception as e:
    #         await reply_split(ctx.message, str(e))
    #         return
    #     cost = (len(text) / 1000) * (0.015 if model == TTS_MODEL else 0.03)
    #     await update_usage(author_id, cost)
    #     await self.reply_with_movie(ctx, response)

async def setup(bot):
    await bot.add_cog(TTS(bot))
