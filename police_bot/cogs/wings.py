"""
نظام الأجنحة (Wings)
=====================
أقسام/وحدات داخل الشرطة (مثل SWAT، دوريات).
/add-new-wing      - إضافة جناح جديد (اسم + رتبة مرتبطة)
/delete-wing       - حذف جناح من تعريفات النظام
/setup-wings-panel - نشر لوحة تعرض كل الأجنحة المسجلة
"""

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import utils


class WingsPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="عرض الأجنحة", style=discord.ButtonStyle.secondary,
                        custom_id="wings_panel:list", emoji="🪖")
    async def list_wings(self, interaction: discord.Interaction, button: discord.ui.Button):
        wings = await db.list_wings()
        if not wings:
            await interaction.response.send_message("ℹ️ لا توجد أجنحة مسجلة حالياً.", ephemeral=True)
            return

        embed = utils.base_embed("🪖 الأجنحة المتاحة")
        for _id, name, role_id, emoji, description in wings:
            embed.add_field(
                name=f"{emoji} {name}",
                value=f"الرتبة: <@&{role_id}>" + (f"\n{description}" if description else ""),
                inline=False,
            )
        await interaction.response.send_message(embed=embed)
        if interaction.guild:
            await utils.send_log(interaction.guild, "Wings Viewed", f"المنفذ: {interaction.user.mention}")


class Wings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="add-new-wing", description="إضافة جناح جديد للنظام")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        name="اسم الجناح", role="الرتبة المرتبطة بالجناح",
        emoji="إيموجي يمثل الجناح (اختياري)", description="وصف مختصر (اختياري)"
    )
    async def add_new_wing(self, interaction: discord.Interaction, name: str, role: discord.Role,
                            emoji: str = "🪖", description: str = ""):
        if not utils.has_role(interaction.user, "admin"):
            await interaction.response.send_message("❌ ما تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await db.add_wing(name, role.id, emoji, description)
        if interaction.guild:
            await utils.send_log(interaction.guild, "Wing Added", f"المنفذ: {interaction.user.mention}\nالجناح: {name}\nالرتبة: {role.mention}")
        embed = utils.base_embed("✅ تمت إضافة جناح جديد")
        embed.add_field(name="الجناح", value=f"{emoji} {name}", inline=True)
        embed.add_field(name="الرتبة", value=role.mention, inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="delete-wing", description="حذف جناح من تعريفات النظام")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(name="اسم الجناح المراد حذفه")
    async def delete_wing(self, interaction: discord.Interaction, name: str):
        if not utils.has_role(interaction.user, "admin"):
            await interaction.response.send_message("❌ ما تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        deleted = await db.delete_wing(name)
        if interaction.guild:
            await utils.send_log(interaction.guild, "Wing Deleted", f"المنفذ: {interaction.user.mention}\nالجناح: {name}")

        if not deleted:
            await interaction.followup.send(f"⚠️ ما فيه جناح باسم `{name}`.", ephemeral=True)
            return
        await interaction.followup.send(f"🗑️ تم حذف جناح `{name}` من النظام.", ephemeral=True)

    @app_commands.command(name="setup-wings-panel", description="نشر لوحة الأجنحة في القناة الحالية")
    @app_commands.default_permissions(administrator=True)
    async def setup_wings_panel(self, interaction: discord.Interaction):
        if not utils.has_role(interaction.user, "admin"):
            await interaction.response.send_message("❌ ما تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        embed = utils.base_embed(
            "# — الأجنحة", "استعرض أقسام ووحدات الشرطة المتاحة بالضغط على الزر أدناه.",
            image_url="attachment://evil_town_banner.png",
        )
        await utils.send_panel(interaction.channel, embed, WingsPanelView(), "evil_town_banner.png")
        await db.set_setting("wings_channel_id", str(interaction.channel.id))
        await interaction.delete_original_response()
        if interaction.guild:
            await utils.send_log(interaction.guild, "Wings Panel", f"المنفذ: {interaction.user.mention}\nالقناة: {interaction.channel.mention}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Wings(bot))
