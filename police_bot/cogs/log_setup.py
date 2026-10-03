from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
import utils


def _can_use(member: discord.abc.User) -> bool:
    return isinstance(member, discord.Member) and (
        member.guild_permissions.administrator or utils.has_role(member, "admin")
    )


class LogChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, guild: discord.Guild, category: str, current_id: int | None):
        defaults = []
        if current_id and guild.get_channel(current_id) is not None:
            defaults = [discord.SelectDefaultValue(id=current_id, type=discord.SelectDefaultValueType.channel)]
        super().__init__(
            placeholder="اختر ..",
            channel_types=[discord.ChannelType.text],
            min_values=0,
            max_values=1,
            default_values=defaults,
        )
        self.category = category

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None or not _can_use(interaction.user):
            await interaction.response.send_message("❌ هذا الأمر للمسؤولين فقط.", ephemeral=True)
            return
        key = utils.log_key(interaction.guild.id, self.category)
        if self.values:
            await db.set_setting(key, str(self.values[0].id))
        else:
            await db.set_setting(key, "")
        await interaction.response.edit_message(view=await build_logs_view(interaction.guild))


async def build_logs_view(guild: discord.Guild) -> discord.ui.LayoutView:
    layout = discord.ui.LayoutView(timeout=600)
    items: list[discord.ui.Item] = [
        discord.ui.TextDisplay(f"# {config.LOG_TITLE_EMOJI}︲OLD KING ( Logs )"),
        discord.ui.TextDisplay("-# حدد الروم المخصص لكل قسم من اللوقات . وللإلغاء امسح الاختيار ."),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
    ]
    for key, (number, label) in config.LOG_CATEGORIES.items():
        raw = await db.get_setting(utils.log_key(guild.id, key))
        current = int(raw) if raw and raw.isdigit() else None
        items.append(discord.ui.TextDisplay(f"**{number} /** {label}"))
        items.append(discord.ui.ActionRow(LogChannelSelect(guild, key, current)))
    layout.add_item(discord.ui.Container(*items, accent_color=config.EMBED_COLOR))
    return layout


class LogSetup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="logs", description="تحديد روم كل قسم من أقسام اللوقات")
    @app_commands.default_permissions(administrator=True)
    async def logs(self, interaction: discord.Interaction):
        if interaction.guild is None or not _can_use(interaction.user):
            await interaction.response.send_message("❌ هذا الأمر للمسؤولين فقط.", ephemeral=True)
            return
        await interaction.response.send_message(view=await build_logs_view(interaction.guild), ephemeral=True)

    # ---- القسم 3: إعطاء وإزالة الرتب ----
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles == after.roles:
            return
        managed = {
            config.LSPD_BASE_ROLE_ID,
            config.LSPD_OFFICERS_ROLE_ID,
            config.LSPD_CHIEF_OFFICE_ROLE_ID,
            *config.LSPD_RANK_ROLE_IDS.values(),
            *config.LSPD_WING_ROLE_IDS.values(),
            *config.LSPD_KICK_ROLE_IDS.values(),
        }
        added = [r for r in after.roles if r not in before.roles and r.id in managed]
        removed = [r for r in before.roles if r not in after.roles and r.id in managed]
        if not added and not removed:
            return

        executor = None
        try:
            async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                if entry.target and entry.target.id == after.id:
                    executor = entry.user
                    break
        except (discord.Forbidden, discord.HTTPException):
            pass
        if executor is not None and executor.id == self.bot.user.id:
            return  # تغييرات البوت نفسه تنسجل في قسم لوحة الكنترول

        by = f" — بواسطة {executor.mention}" if executor else ""
        if added:
            await utils.send_log(
                after.guild, "roles", "Role Added", after, "Give Role",
                f"أُعطي : {', '.join(r.mention for r in added)}{by}",
            )
        if removed:
            await utils.send_log(
                after.guild, "roles", "Role Removed", after, "Remove Role",
                f"أُزيل : {', '.join(r.mention for r in removed)}{by}",
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(LogSetup(bot))
