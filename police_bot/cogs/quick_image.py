"""أمر خ لإرسال صورة ثابتة للرول المسموح فقط."""

from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord.ext import commands

import config


log = logging.getLogger(__name__)
IMAGE_PATH = Path(__file__).resolve().parent.parent / "assets" / config.LINE_IMAGE_ASSET


class QuickImage(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # أي رسالة تُكتب بهذي القنوات ترسل الصورة تلقائيًا — حتى لو كانت من البوت نفسه
        # (مثل رسائل التقديم بـ Submits)، ما عدا رسالة الصورة ذاتها حتى لا تدخل بحلقة لا نهائية.
        if message.channel.id in config.LINE_IMAGE_AUTO_CHANNEL_IDS:
            if any(attachment.filename == config.LINE_IMAGE_ASSET for attachment in message.attachments):
                return
            await self._send_image(message.channel)
            return

        if message.author.bot or message.content.strip() != "خ":
            return
        if not isinstance(message.author, discord.Member):
            return
        if not any(role.id in config.LINE_IMAGE_ROLE_IDS for role in message.author.roles):
            return

        sent = await self._send_image(message.channel)
        if not sent:
            return

        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
            # الصورة أُرسلت بنجاح، لكن البوت قد يفتقد Manage Messages.
            log.warning("Image sent, but could not delete خ message %s: %s", message.id, exc)

    async def _send_image(self, channel: discord.abc.Messageable) -> bool:
        if not IMAGE_PATH.is_file():
            log.error("quick_x image is missing: %s", IMAGE_PATH)
            return False
        try:
            await channel.send(file=discord.File(IMAGE_PATH, filename=config.LINE_IMAGE_ASSET))
            return True
        except (discord.Forbidden, discord.HTTPException, OSError) as exc:
            log.error("Could not send خ image in channel %s: %s", getattr(channel, "id", "?"), exc)
            return False


async def setup(bot: commands.Bot):
    await bot.add_cog(QuickImage(bot))
