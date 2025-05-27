import base64

import aiohttp
from discord.ext import commands
import logging
import requests
import io
import discord

from discord_helper import reply_split
from openai_helper import get_image, edit_image
from config import STABILITY_API_KEY
from db import update_usage
from utils import requires_credit
from openai_helper import pricing

logger = logging.getLogger(__name__)

class ImageCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="dalle3", help="Generate an image using DALL-E 3.")
    @requires_credit(lambda ctx, *args, **kwargs: pricing["dall-e-3"]["1024x1024"])
    async def dalle3(self, ctx, *, arg):
        author_id = ctx.author.id
        size = "1024x1024"
        if arg.startswith("hoz"):
            size = "1792x1024"
            arg = arg[3:]
        elif arg.startswith("vert"):
            size = "1024x1792"
            arg = arg[4:]
        quality = "standard"
        try:
            logging.info(f"Getting image with parameters: {arg}, {size}, {quality}")
            response = await get_image(model="dall-e-3", prompt=arg,user_id=author_id, n=1, size=size, quality=quality)
        except Exception as e:
            await reply_split(ctx.message, str(e))
            return
        image_url = response.data[0].url
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                img_bytes = await resp.read()
        logging.info(f"Revised Prompt: {response.data[0].revised_prompt}")
        await ctx.reply(file=discord.File(io.BytesIO(img_bytes), filename="image.png"))

    @commands.command(name="dalle2", help="Generate an image using DALL-E 2.")
    @requires_credit(lambda ctx, *args, **kwargs: pricing["dall-e-2"]["1024x1024"])
    async def dalle2(self, ctx, *, arg):
        author_id = ctx.author.id
        size = "1024x1024"
        quality = "standard"
        try:
            logging.info(f"Getting image with parameters: {arg}, {size}, {quality}")
            response = await get_image(model="dall-e-2", prompt=arg, user_id=author_id, n=1, size=size, quality=quality)
        except Exception as e:
            await reply_split(ctx.message, str(e))
            return
        image_url = response.data[0].url
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                img_bytes = await resp.read()
        logging.info(f"Revised Prompt: {response.data[0].revised_prompt}")
        await ctx.reply(file=discord.File(io.BytesIO(img_bytes), filename="image.png"))

    @commands.command(name="genimage", help="Generate a medium-quality image using GPT-IMAGE-1.")
    @requires_credit(lambda ctx, *args, **kwargs: pricing["gpt-image-1"]["medium"])
    async def genimage(self, ctx, *, arg):
        author_id = ctx.author.id
        size = "1024x1024"
        quality = "medium"
        try:
            response = await get_image(model="gpt-image-1", prompt=arg, user_id=author_id, n=1, size=size, quality=quality)
        except Exception as e:
            await reply_split(ctx.message, str(e))
            return
        image_b64 = response.data[0].b64_json
        img_bytes = base64.b64decode(image_b64)
        await ctx.reply(file=discord.File(io.BytesIO(img_bytes), filename="image.png"))

    @commands.command(name="genimagehd", help="Generate a high-quality image using GPT-IMAGE-1.")
    @requires_credit(lambda ctx, *args, **kwargs: pricing["gpt-image-1"]["high"])
    async def genimagehd(self, ctx, *, arg):
        author_id = ctx.author.id
        size = "1024x1024"
        quality = "high"
        try:
            response = await get_image(model="gpt-image-1", prompt=arg, user_id=author_id, n=1, size=size,
                                       quality=quality)
        except Exception as e:
            await reply_split(ctx.message, str(e))
            return
        image_b64 = response.data[0].b64_json
        img_bytes = base64.b64decode(image_b64)
        await ctx.reply(file=discord.File(io.BytesIO(img_bytes), filename="image.png"))

    @commands.command(name="editimage", help="Edit an image using GPT-IMAGE-1.")
    @requires_credit(lambda ctx, *args, **kwargs: pricing["gpt-image-1"]["high"])
    async def editimage(self, ctx, *, arg):
        author_id = ctx.author.id
        # check for message attachments first, then check for replied message attachments if there are no attachments
        images = []
        if ctx.message.attachments:
            images = ctx.message.attachments
        elif ctx.message.reference:
            try:
                replied_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if replied_message.attachments:
                    images = replied_message.attachments
            except Exception as e:
                await reply_split(ctx.message, str(e))
                return
        else:
            await reply_split(ctx.message, "Please attach or reply to an image to use this command!")
            return
        images_urls = [image.url for image in images]
        try:
            response = await edit_image(prompt=arg, user_id=author_id, image_urls=images_urls)
            image_b64 = response.data[0].b64_json
            img_bytes = base64.b64decode(image_b64)
            await ctx.reply(file=discord.File(io.BytesIO(img_bytes), filename="image.png"))
        except Exception as e:
            await reply_split(ctx.message, str(e))


    # @commands.command(name="sdultra", help="Generate an image using Stability SD Ultra.")
    # async def sdultra(self, ctx, *, arg): # todo, move a lot of this function to stability_helper.py
    #     author_id = ctx.author.id
    #     if STABILITY_API_KEY is None:
    #         logger.warning("Stability API key not set up!")
    #         await reply_split(ctx.message, "Stability API is not set up on this bot.")
    #         return
    #     try:
    #         response = requests.post(
    #             f"https://api.stability.ai/v2beta/stable-image/generate/ultra",
    #             headers={
    #                 "authorization": f"Bearer {STABILITY_API_KEY}",
    #                 "accept": "image/*"
    #             },
    #             files={"none": ''},
    #             data={"prompt": arg}
    #         )
    #         if response.status_code == 200:
    #             img_bytes = response.content
    #             await ctx.reply(file=discord.File(io.BytesIO(img_bytes), "image.png"))
    #             cost = 0.08 # todo, double check this
    #             await update_usage(author_id, cost)
    #         else:
    #             await reply_split(ctx.message, str(response.json()))
    #     except Exception as e:
    #         await reply_split(ctx.message, str(e))
    #
    # @commands.command(name="sdcore", help="Generate an image using Stability SD Core.")
    # async def sdcore(self, ctx, *, arg):
    #     author_id = ctx.author.id
    #     if STABILITY_API_KEY is None:
    #         logger.warning("Stability API key not set up!")
    #         await reply_split(ctx.message, "Stability API is not set up on this bot.")
    #         return
    #     try:
    #         response = requests.post(
    #             f"https://api.stability.ai/v2beta/stable-image/generate/core",
    #             headers={
    #                 "authorization": f"Bearer {STABILITY_API_KEY}",
    #                 "accept": "image/*"
    #             },
    #             files={"none": ''},
    #             data={"prompt": arg}
    #         )
    #         if response.status_code == 200:
    #             img_bytes = response.content
    #             await ctx.reply(file=discord.File(io.BytesIO(img_bytes), "image.png"))
    #             cost = 0.03
    #             await update_usage(author_id, cost)
    #         else:
    #             await reply_split(ctx.message, str(response.json()))
    #     except Exception as e:
    #         await reply_split(ctx.message, str(e))
    #
    # @commands.command(name="searchandreplace", help="Edit an image by searching and replacing elements. Attach an image and use the format: search|replace")
    # async def searchandreplace(self, ctx, *, arg):
    #     author_id = ctx.author.id
    #     if STABILITY_API_KEY is None:
    #         logger.warning("Stability API key not set up!")
    #         await reply_split(ctx.message, "Stability API is not set up on this bot.")
    #         return
    #     if not ctx.message.attachments:
    #         await reply_split(ctx.message, "Please attach an image to use this command!")
    #         return
    #     split = arg.split("|")
    #     if len(split) != 2:
    #         await reply_split(ctx.message, "Please use the format: search|replace")
    #         return
    #     search_term, replace_term = split[0].strip(), split[1].strip()
    #     image_url = ctx.message.attachments[0].url
    #     image_bytes = requests.get(image_url).content
    #     try:
    #         response = requests.post(
    #             f"https://api.stability.ai/v2beta/stable-image/edit/search-and-replace",
    #             headers={
    #                 "authorization": f"Bearer {STABILITY_API_KEY}",
    #                 "accept": "image/*"
    #             },
    #             files={"image": image_bytes},
    #             data={
    #                 "prompt": replace_term,
    #                 "search_prompt": search_term
    #             },
    #         )
    #         if response.status_code == 200:
    #             img_bytes = response.content
    #             await ctx.reply(file=discord.File(io.BytesIO(img_bytes), "image.png"))
    #             cost = 0.04
    #             await update_usage(author_id, cost)
    #         else:
    #             await reply_split(ctx.message, str(response.json()))
    #     except Exception as e:
    #         await reply_split(ctx.message, str(e))
    #
    # @commands.command(name="imagetovideo", help="Convert an attached image to a video clip.")
    # async def imagetovideo(self, ctx, *, arg):
    #     author_id = ctx.author.id
    #     if not ctx.message.attachments:
    #         await reply_split(ctx.message, "Please attach an image to use this command!")
    #         return
    #     image_url = ctx.message.attachments[0].url
    #     image_bytes = requests.get(image_url).content
    #     # For simplicity, assume we call Stability API for image-to-video conversion.
    #     try:
    #         response = requests.post(
    #             f"https://api.stability.ai/v2beta/image-to-video",
    #             headers={"authorization": f"Bearer {STABILITY_API_KEY}" if STABILITY_API_KEY else ""},
    #             files={"image": image_bytes},
    #             data={"seed": 0, "cfg_scale": 1.8, "motion_bucket_id": 127},
    #         )
    #         if response.status_code == 200:
    #             video_id = response.json().get('id')
    #             await reply_split(ctx.message, f"Check back later with the command `getvideo [id]`\nVideo ID: {video_id}")
    #         else:
    #             await reply_split(ctx.message, str(response.json()))
    #     except Exception as e:
    #         await reply_split(ctx.message, str(e))
    #
    # @commands.command(name="getvideo", help="Retrieve a video by its ID.")
    # async def getvideo(self, ctx, arg):
    #     try:
    #         response = requests.get(
    #             f"https://api.stability.ai/v2beta/image-to-video/result/{arg.strip()}",
    #             headers={
    #                 "accept": "video/*",
    #                 "authorization": f"Bearer {STABILITY_API_KEY}" if STABILITY_API_KEY else ""
    #             },
    #         )
    #         if response.status_code == 202:
    #             await reply_split(ctx.message, "Generation in-progress, try again later.")
    #         elif response.status_code == 200:
    #             video_bytes = response.content
    #             await ctx.reply(file=discord.File(io.BytesIO(video_bytes), "video.mp4"))
    #         else:
    #             await reply_split(ctx.message, str(response.json()))
    #     except Exception as e:
    #         await reply_split(ctx.message, str(e))

async def setup(bot):
    await bot.add_cog(ImageCommands(bot))
