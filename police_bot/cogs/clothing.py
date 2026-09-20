"""
لوحة الملابس / الرتب (Clothing)
=================================
كتالوج عام: الأدمن يضيف عناصر (اسم + وصف + صورة اختيارية)، وينشر لوحة
فيها قائمة اختيار — كل عنصر لما يُختار يطلع Embed خاص فيه.

/clothing-add     - إضافة عنصر جديد (اسم + وصف + صورة اختيارية)
/clothing-remove  - حذف عنصر من الكتالوج
/clothing-panel   - نشر/تحديث لوحة الكتالوج في القناة الحالية
"""

import discord

import config
from discord import app_commands
from discord.ext import commands

import database as db
import utils


class ClothingSelect(discord.ui.Select):
    def __init__(self, items):
        options = [
            discord.SelectOption(label=name, value=name, emoji=emoji or "👮")
            for _id, name, _desc, _img, emoji in items
        ]
        super().__init__(
            placeholder=" 𝗩𝗶𝗲𝘄 𝗠𝗶𝗹𝗶𝘁𝗮𝗿𝘆 𝗨𝗻𝗶𝗳𝗼𝗿𝗺𝘀",
            options=options,
            custom_id="clothing_panel:select",
        )
        self.items_map = {name: (desc, img) for _id, name, desc, img, _emoji in items}

    async def callback(self, interaction: discord.Interaction):
        name = self.values[0]
        description, image_url = self.items_map.get(name, ("", None))

        embed = utils.base_embed(name, description, image_url=image_url or "")
        if image_url:
            embed.set_image(url=image_url)

        await interaction.response.send_message(
            view=utils.components_v2_view(embed), ephemeral=True
        )


class ClothingPanelView(discord.ui.View):
    def __init__(self, items):
        super().__init__(timeout=None)
        if items:
            self.add_item(ClothingSelect(items))


class Clothing(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="clothing-add",
        description="إضافة عنصر جديد للوحة (رتبة/زي) مع وصف وصورة اختيارية",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        name="اسم العنصر (مثال: Officer I)",
        description="الوصف الكامل",
        image="صورة توضيحية (اختياري)",
        emoji="إيموجي يمثل العنصر (اختياري)",
    )
    async def clothing_add(
        self,
        interaction: discord.Interaction,
        name: str,
        description: str,
        image: discord.Attachment = None,
        emoji: str = "👮",
    ):
        if not utils.has_any_role(interaction.user, config.CLOTHING_ROLE_IDS):
            await interaction.response.send_message(
                "-# **<:ETRP_68:1500142625712242818> لاتمتلك الصلاحية ل اضافة لبس . **",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        image_url = None
        if image:
            file = await image.to_file()
            msg = await interaction.channel.send(
                content=f"📎 صورة عنصر: {name}", file=file
            )
            image_url = msg.attachments[0].url

        await db.add_clothing_item(name, description, image_url, emoji)

        if interaction.guild:
            await utils.send_log(
                interaction.guild,
                "Clothing Added",
                f"المنفذ: {interaction.user.mention}\nالعنصر: {emoji} {name}",
            )

        await interaction.delete_original_response()

    @app_commands.command(
        name="clothing-remove", description="حذف عنصر من كتالوج الملابس/الرتب"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(name="اسم العنصر المراد حذفه")
    async def clothing_remove(self, interaction: discord.Interaction, name: str):
        if not utils.has_any_role(interaction.user, config.CLOTHING_ROLE_IDS):
            await interaction.response.send_message(
                "-# **<:ETRP_68:1500142625712242818> لاتمتلك الصلاحية ل ازالة لبس . **",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        deleted = await db.delete_clothing_item(name)

        if not deleted:
            await interaction.followup.send(
                f"⚠️ ما فيه عنصر باسم `{name}`.", ephemeral=True
            )
            return

        if interaction.guild:
            await utils.send_log(
                interaction.guild,
                "Clothing Deleted",
                f"المنفذ: {interaction.user.mention}\nالعنصر: {name}",
            )

        await interaction.followup.send(
            f"🗑️ تم حذف `{name}` من الكتالوج.", ephemeral=True
        )


    @app_commands.command(
        name="clothing-panel",
        description="نشر/تحديث لوحة الملابس والرتب في القناة الحالية",
    )
    @app_commands.default_permissions(administrator=True)
    async def clothing_panel(self, interaction: discord.Interaction):
        if not utils.has_any_role(interaction.user, config.CLOTHING_ROLE_IDS):
            await interaction.response.send_message(
                "-# **<:ETRP_68:1500142625712242818> لاتمتلك الصلاحية ل ارسال البنل هذا . **",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        items = await db.list_clothing_items()
        if not items:
            await interaction.followup.send(
                "⚠️ ما فيه عناصر مضافة بعد. استخدم `/clothing-add` أول.",
                ephemeral=True,
            )
            return

        embed = utils.base_embed(
            "<a:MTRP:1550940537492865124> ︲ Police ClotHing .",
            "** <:emoji_14:1550308740551417956> ︲ The complete military vest is available here . **",
            image_url=f"attachment://{config.PANEL_BANNER_ASSET}",
        )

        # إرسال اللوحة
        await utils.send_panel(
            interaction.channel,
            embed,
            ClothingPanelView(items),
            config.PANEL_BANNER_ASSET,
        )

        # حفظ الآي دي + حذف الرد المؤقت + إرسال اللوق
        await db.set_setting("clothing_channel_id", str(interaction.channel.id))
        await interaction.delete_original_response()

        if interaction.guild:
            await utils.send_log(
                interaction.guild,
                "Clothing Panel",
                f"المنفذ: {interaction.user.mention}\nالقناة: {interaction.channel.mention}",
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Clothing(bot))
