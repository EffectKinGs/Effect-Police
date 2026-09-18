"""أوامر الإدارة والتهيئة العامة لنظام Police Out Zone."""

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import utils
from cogs.login_panel import LoginPanelView, build_duty_embed, refresh_duty_panel
from cogs.wings import WingsPanelView


class ConfirmView(discord.ui.View):
    def __init__(self, on_confirm):
        super().__init__(timeout=30)
        self.on_confirm = on_confirm

    @discord.ui.button(label="تأكيد", style=discord.ButtonStyle.secondary)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.on_confirm(interaction)
        self.stop()

    @discord.ui.button(label="إلغاء", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="تم الإلغاء.", view=None, embed=None)
        self.stop()


async def _publish_login_panel(guild: discord.Guild, channel: discord.TextChannel):
    duty_embed = await build_duty_embed(guild)
    message = await utils.send_panel(channel, duty_embed, LoginPanelView(), "duty_ops_banner.png")
    await db.set_setting(f"duty_panel_channel_id:{guild.id}", str(channel.id))
    await db.set_setting(f"duty_panel_message_id:{guild.id}", str(message.id))


class SetupAdmin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="set-log-channel", description="إضافة القناة الحالية كقناة استقبال للوقات (يدعم أكثر من قناة)")
    @app_commands.default_permissions(administrator=True)
    async def set_log_channel(self, interaction: discord.Interaction):
        if interaction.guild is None or not utils.has_role(interaction.user, "admin") or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ هذا الأمر للمسؤولين وفي قناة نصية فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        raw = await db.get_setting(f"logs_channel_ids:{interaction.guild.id}") or ""
        ids = {p.strip() for p in raw.split(",") if p.strip()}
        ids.add(str(interaction.channel.id))
        await db.set_setting(f"logs_channel_ids:{interaction.guild.id}", ",".join(ids))
        await utils.send_log(interaction.guild, "Logs Enabled", f"تم إضافة هذه القناة لقنوات اللوقات بواسطة {interaction.user.mention}.")
        await interaction.followup.send(f"✅ تمت إضافة هذه القناة لقنوات اللوقات. (العدد الحالي: {len(ids)})", ephemeral=True)

    @app_commands.command(name="remove-log-channel", description="إزالة القناة الحالية من قنوات استقبال اللوقات")
    @app_commands.default_permissions(administrator=True)
    async def remove_log_channel(self, interaction: discord.Interaction):
        if interaction.guild is None or not utils.has_role(interaction.user, "admin") or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ هذا الأمر للمسؤولين وفي قناة نصية فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        raw = await db.get_setting(f"logs_channel_ids:{interaction.guild.id}") or ""
        ids = {p.strip() for p in raw.split(",") if p.strip()}
        ids.discard(str(interaction.channel.id))
        await db.set_setting(f"logs_channel_ids:{interaction.guild.id}", ",".join(ids))
        if str(interaction.channel.id) == await db.get_setting(f"logs_channel_id:{interaction.guild.id}"):
            await db.set_setting(f"logs_channel_id:{interaction.guild.id}", "")
        await interaction.followup.send(f"✅ تمت إزالة هذه القناة من قنوات اللوقات. (العدد الحالي: {len(ids)})", ephemeral=True)

    @app_commands.command(name="reset-police-system", description="يمسح إعدادات اللوحات والأجنحة وأنواع التذاكر")
    @app_commands.default_permissions(administrator=True)
    async def reset_police_system(self, interaction: discord.Interaction):
        if not utils.has_role(interaction.user, "admin"):
            await interaction.response.send_message("❌ لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return

        async def do_reset(inner: discord.Interaction):
            await db.clear_all_settings()
            await inner.response.edit_message(content="✅ تم مسح الإعدادات المحفوظة.", view=None, embed=None)

        await interaction.response.send_message(
            embed=utils.base_embed("⚠️ تأكيد إعادة التعيين", "سيتم مسح إعدادات القنوات والأجنحة وأنواع التذاكر فقط."),
            view=ConfirmView(do_reset),
            ephemeral=True,
        )

    @app_commands.command(name="refresh-panels", description="يحدّث اللوحات المحفوظة")
    @app_commands.default_permissions(administrator=True)
    async def refresh_panels(self, interaction: discord.Interaction):
        if not utils.has_role(interaction.user, "admin") or interaction.guild is None:
            await interaction.response.send_message("❌ لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        updated = await refresh_duty_panel(interaction.guild)
        if updated:
            await interaction.delete_original_response()
        else:
            await interaction.followup.send("⚠️ لم تُنشر لوحة المباشرة بعد.", ephemeral=True)

    @app_commands.command(name="help", description="عرض أوامر النظام")
    async def help_command(self, interaction: discord.Interaction):
        embed = utils.base_embed("📖 Police Out Zone")
        embed.add_field(name="لوحة المباشرة", value="`/نشر_لوحة_الدخول` `/فتح_تسجيل_الدخول` `/قفل_تسجيل_الدخول`\n`/حالة_المباشرة` `/مدتي`", inline=False)
        embed.add_field(name="الإدارة", value="`/setup-police-system` `/refresh-panels`\n`/set-log-channel` `/reset-police-system`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupAdmin(bot))
