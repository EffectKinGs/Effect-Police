from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
import utils


class CreateEmbedModal(discord.ui.Modal, title="𝗖𝗿𝗲𝗮𝘁𝗲 𝗘𝗺𝗯𝗲𝗱"):
    def __init__(self):
        super().__init__()
        self.embed_title = discord.ui.TextInput(label="العنوان", required=True, max_length=256)
        self.embed_description = discord.ui.TextInput(label="الوصف", required=True, max_length=4000, style=discord.TextStyle.paragraph)
        self.image_url = discord.ui.TextInput(label="رابط الصورة", placeholder="اختياري", required=False, max_length=500)
        self.add_item(self.embed_title)
        self.add_item(self.embed_description)
        self.add_item(self.image_url)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return
        title = str(self.embed_title).strip() or "‎"
        description = str(self.embed_description).strip() or "‎"
        image_url = str(self.image_url).strip()
        embed = discord.Embed(title=title, description=description, color=config.EMBED_COLOR)
        embed.set_footer(text=config.EMBED_FOOTER)
        if image_url.startswith(("http://", "https://")):
            embed.set_image(url=image_url)
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.channel.send(view=utils.components_v2_view(embed))
        except discord.HTTPException as exc:
            await interaction.followup.send(f"⚠️ تعذر إرسال الإمبيد: {exc}", ephemeral=True)
            return
        await utils.send_log(interaction.guild, "Embed Created", f"المنفذ: {interaction.user.mention}\nالقناة: {interaction.channel.mention}")
        await interaction.delete_original_response()


class EmbedPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Embed", style=discord.ButtonStyle.secondary, custom_id="embed_panel:create")
    async def create_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not utils.is_system_admin(interaction.user):
            await interaction.response.send_message("❌ ما تملك صلاحية استخدام هذا الزر.", ephemeral=True)
            return
        await interaction.response.send_modal(CreateEmbedModal())


class CustomEmbed(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="embed-panel", description="نشر لوحة إنشاء إمبيد يدوي في القناة الحالية")
    @app_commands.default_permissions(administrator=True)
    async def embed_panel(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not utils.is_system_admin(interaction.user):
            await interaction.response.send_message("❌ لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ اختر قناة نصية.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        embed = utils.base_embed("<:emoji_19:1550309019938459761> ︲ Create EmBed .", "-# **<:emoji_15:1550308794297356388>  '  هذه اللوحة وعن طريق الزر ادناه بامكانك انشاء امبيد جديد . **", image_url=f"attachment://{config.PANEL_BANNER_ASSET}")
        await utils.send_panel(interaction.channel, embed, EmbedPanelView(), config.PANEL_BANNER_ASSET)
        await utils.send_log(interaction.guild, "Embed Panel", f"المنفذ: {interaction.user.mention}\nالقناة: {interaction.channel.mention}")
        await interaction.delete_original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(CustomEmbed(bot))
