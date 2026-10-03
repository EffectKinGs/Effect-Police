import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
import utils
from cogs.login_panel import LoginPanelView, build_duty_embed, refresh_duty_panel


def _simple_v2(title: str, text: str) -> discord.ui.LayoutView:
    layout = discord.ui.LayoutView(timeout=None)
    layout.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(f"# {title}"),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(text),
            accent_color=config.EMBED_COLOR,
        )
    )
    return layout


class ConfirmRow(discord.ui.ActionRow):
    def __init__(self, on_confirm):
        super().__init__()
        self.on_confirm = on_confirm

    @discord.ui.button(label="تأكيد", style=discord.ButtonStyle.secondary)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.on_confirm(interaction)

    @discord.ui.button(label="إلغاء", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=_simple_v2("OLD KING", "تم الإلغاء."))


class ConfirmView(discord.ui.LayoutView):
    def __init__(self, title: str, text: str, on_confirm):
        super().__init__(timeout=30)
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"# {title}"),
                discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(text),
                ConfirmRow(on_confirm),
                accent_color=config.EMBED_COLOR,
            )
        )


async def _publish_login_panel(guild: discord.Guild, channel: discord.TextChannel):
    duty_embed = await build_duty_embed(guild)
    message = await utils.send_panel(channel, duty_embed, LoginPanelView(), "duty_ops_banner.png")
    await db.set_setting(f"duty_panel_channel_id:{guild.id}", str(channel.id))
    await db.set_setting(f"duty_panel_message_id:{guild.id}", str(message.id))


class SetupAdmin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="reset-police-system", description="يمسح إعدادات اللوحات والأجنحة وأنواع التذاكر")
    @app_commands.default_permissions(administrator=True)
    async def reset_police_system(self, interaction: discord.Interaction):
        if not utils.has_role(interaction.user, "admin"):
            await interaction.response.send_message("❌ لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return

        async def do_reset(inner: discord.Interaction):
            await db.clear_all_settings()
            await inner.response.edit_message(view=_simple_v2("OLD KING", "✅ تم مسح الإعدادات المحفوظة."))

        await interaction.response.send_message(
            view=ConfirmView("⚠️ تأكيد إعادة التعيين", "سيتم مسح إعدادات القنوات والأجنحة وأنواع التذاكر واللوقات.", do_reset),
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
        text = (
            "**لوحة المباشرة**\n`/login-panel` `/حالة_المباشرة` `-login-on` `-login-off`\n\n"
            "**الإدارة**\n`/logs` `/refresh-panels` `/reset-police-system`"
        )
        await interaction.response.send_message(view=_simple_v2("📖 OLD KING's", text), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupAdmin(bot))
