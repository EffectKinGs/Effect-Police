"""لوحة Police Out Zone للمباشرة مع استبيان Login ووضع الأزرار الموسع."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
import utils

PANEL_CHANNEL_KEY = "duty_panel_channel_id"
PANEL_MESSAGE_KEY = "duty_panel_message_id"


def _guild_key(key: str, guild_id: int) -> str:
    return f"{key}:{guild_id}"


def _status_name(status_key: str) -> str:
    return config.STATUS_LABELS.get(status_key, (status_key, ""))[0]


def _tokens(row: tuple, member: discord.Member | None) -> str:
    """يحوّل الحالات المتراكمة إلى الإيموجيات المخصصة بجانب الاسم."""
    if bool(row[10]):
        return ""
    e = config.CUSTOM_EMOJIS
    bodycam_on, bodycam_off = bool(row[5]), bool(row[6])
    dispatch, deputy, period = bool(row[7]), bool(row[8]), bool(row[9])
    parts = [e["bodycam_on"] if bodycam_on else e["bodycam_off"]]
    if dispatch:
        parts.append(e["dispatch"])
    if deputy:
        parts.append(e["deputy_dispatch"])
    if period:
        parts.append(e["shift_supervisor"])
    return "".join(parts)


def _mention(member: discord.Member | None, username: str, user_id: int) -> str:
    return member.mention if member else f"{username} (`{user_id}`)"


def _rank_badge(member: discord.Member | None) -> str:
    """الدائرة السوداء تظهر فقط لحاملي إحدى رتبتي config.LOGIN_ALLOWED_ROLE_IDS."""
    if member and any(role.id in config.LOGIN_ALLOWED_ROLE_IDS for role in member.roles):
        return config.CUSTOM_EMOJIS["rank_badge"] + " "
    return ""


async def build_duty_embed(guild: discord.Guild) -> discord.Embed:
    rows = await db.get_active_sessions(guild.id)
    count = len(rows)
    description = [
        f"** <:emoji_13:1550308496216432781>   '   عدد الوحدات المتواجدة بالميدان . ( {config.MAX_ACTIVE_OFFICERS}/{count} ) **",
        "",
    ]
    if not rows:
        description.append("")
        description.append("-# ** <:emoji_21:1550309215162077214>   '   لايوجد عسكري في مدينة ملوك التأثير . **")
    else:
        members = {member.id: member for member in guild.members}
        for row in rows:
            member = members.get(row[1])
            line = f"- {_mention(member, row[2], row[1])} {_rank_badge(member)}{_tokens(row, member)}".strip()
            description.append(line)
    return utils.base_embed(
        "Login",
        "\n".join(description),
        image_url="attachment://duty_ops_banner.png",
    )


async def _panel_channel(guild: discord.Guild):
    channel_id = await db.get_setting(_guild_key(PANEL_CHANNEL_KEY, guild.id))
    if not channel_id:
        return None
    channel = guild.get_channel(int(channel_id))
    return channel if isinstance(channel, discord.TextChannel) else None


async def refresh_duty_panel(guild: discord.Guild, expanded: bool = False) -> bool:
    channel = await _panel_channel(guild)
    message_id = await db.get_setting(_guild_key(PANEL_MESSAGE_KEY, guild.id))
    if channel is None or not message_id:
        return False
    try:
        message = await channel.fetch_message(int(message_id))
        duty_embed = await build_duty_embed(guild)
        await utils.edit_panel(message, duty_embed, LoginPanelView(expanded=expanded), "duty_ops_banner.png")
        return True
    except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
        return False


async def _reply(interaction: discord.Interaction, text: str):
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


async def _member_check(interaction: discord.Interaction) -> bool:
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        await _reply(interaction, "❌ هذه اللوحة تعمل داخل السيرفر فقط.")
        return False
    if not utils.can_login(interaction.user):
        await _reply(interaction, "❌ هذه اللوحة مخصصة للضباط فقط.")
        return False
    return True


async def _open_login(interaction: discord.Interaction, callsign: str, sector: str, note: str):
    if not await _member_check(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    if not await db.is_login_enabled():
        await _reply(interaction, "**<:emoji_28:1550309826758840500>  '  تسجيل الدخول مُغلق اللان ، انتظر المسوؤلين . **")
        return
    if await db.get_open_session(interaction.guild.id, interaction.user.id):
        await _reply(interaction, "-# **<:emoji_28:1550309826758840500>  '  مسجل دخول ب الفعل ! **")
        return
    count = await db.count_active_sessions(interaction.guild.id)
    if count >= config.MAX_ACTIVE_OFFICERS:
        await _reply(interaction, f"⚠️ اكتمل العدد الأقصى للمباشرين ({config.MAX_ACTIVE_OFFICERS}).")
        return

    await db.open_session(interaction.guild.id, interaction.user.id, str(interaction.user), utils.officer_rank(interaction.user))
    await refresh_duty_panel(interaction.guild, expanded=False)
    await utils.send_log(interaction.guild, "Login", f"العسكري: {interaction.user.mention} (`{interaction.user.id}`)\nتم تسجيل الدخول بنجاح.")
    await interaction.followup.send(
    "✅ تم تنفيذ العملية وتحديث لوحة تسجيل الدخول.",
    ephemeral=True,
    delete_after=1,
)


class LoginModal(discord.ui.Modal, title="Police Department | Login"):
    callsign = discord.ui.TextInput(
        label="النداء أو الرقم العسكري",
        placeholder="مثال: 301 أو Adam-01",
        min_length=1,
        max_length=40,
        required=True,
    )
    sector = discord.ui.TextInput(
        label="القطاع أو الوحدة",
        placeholder="مثال: الدوريات أو المرور",
        max_length=60,
        required=False,
    )
    note = discord.ui.TextInput(
        label="ملاحظات",
        placeholder="اختياري",
        style=discord.TextStyle.paragraph,
        max_length=200,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await _open_login(interaction, str(self.callsign), str(self.sector), str(self.note))


class LoginPanelView(discord.ui.View):
    """الوضع المختصر يعرض Login وLogout والمزيد؛ الموسع يعرض المسؤوليات."""

    def __init__(self, expanded: bool = False):
        super().__init__(timeout=None)
        self.expanded = expanded

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        logging.getLogger(__name__).exception("خطأ غير متوقع بزر لوحة تسجيل الدخول: %s", error)
        message = "⚠️ صار خطأ غير متوقع، حاول مرة ثانية. تم تسجيل التفاصيل للمطور."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            pass
        # لوحة Login الحالية تستخدم الأزرار المباشرة ولا تحتوي Staff Tools أو Back.

    @discord.ui.button(label="On Duty", style=discord.ButtonStyle.secondary, custom_id="dream_duty:login", row=0, emoji=config.CUSTOM_EMOJIS["on_duty"])
    async def login_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await _reply(interaction, "❌ هذه اللوحة تعمل داخل السيرفر فقط.")
            return
        await _open_login(interaction, "", "", "")

    @discord.ui.button(label="Off Duty", style=discord.ButtonStyle.secondary, custom_id="dream_duty:logout", row=0, emoji=config.CUSTOM_EMOJIS["off_duty"])
    async def logout_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await _reply(interaction, "❌ هذه اللوحة تعمل داخل السيرفر فقط.")
            return
        await interaction.response.defer(ephemeral=True)
        result = await db.close_session(interaction.guild.id, interaction.user.id)
        if not result:
            await _reply(interaction, "⚠️ لا توجد مباشرة مفتوحة باسمك.")
            return
        await refresh_duty_panel(interaction.guild, expanded=False)
        await utils.send_log(interaction.guild, "Logout", f"العسكري: {interaction.user.mention} (`{interaction.user.id}`)\nمدة المباشرة: {utils.format_duration(result['duration'])}.")
        await interaction.followup.send(
    "✅ تم تنفيذ العملية وتحديث لوحة تسجيل الدخول.",
    ephemeral=True,
    delete_after=1,
)

    @discord.ui.button(label="𝗕𝗼𝗱𝘆𝗖𝗮𝗺", style=discord.ButtonStyle.secondary, custom_id="dream_duty:bodycam", row=1, emoji=config.CUSTOM_EMOJIS["bodycam"])
    async def bodycam_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "bodycam_on")

    @discord.ui.button(label="𝗗𝗶𝘀𝗽𝗮𝘁𝗰𝗵", style=discord.ButtonStyle.secondary, custom_id="dream_duty:dispatch", row=1, emoji=config.CUSTOM_EMOJIS["dispatch"])
    async def dispatch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "dispatch")

    @discord.ui.button(label="𝗗𝗲𝗽𝘂𝘁𝘆 𝗗𝗶𝘀𝗽𝗮𝘁𝗰𝗵", style=discord.ButtonStyle.secondary, custom_id="dream_duty:deputy_dispatch", row=1, emoji=config.CUSTOM_EMOJIS["deputy_dispatch"])
    async def deputy_dispatch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "deputy_dispatch")

    @discord.ui.button(label="𝗦𝗵𝗶𝗳𝘁 𝗦𝘂𝗽𝗲𝗿𝘃𝗶𝘀𝗼𝗿", style=discord.ButtonStyle.secondary, custom_id="dream_duty:period_manager", row=2, emoji=config.CUSTOM_EMOJIS["shift_supervisor"])
    async def period_manager_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "period_manager")

    @discord.ui.button(label="𝟬.𝟭", style=discord.ButtonStyle.secondary, custom_id="dream_duty:code_01", row=2, emoji=config.CUSTOM_EMOJIS["orange"])
    async def code_01_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "code_01")

    async def _toggle(
        self,
        interaction: discord.Interaction,
        status_key: str,
        panel_expanded: bool = False,
    ):
        if not await _member_check(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        if status_key == "period_manager" and not utils.is_period_manager(interaction.user):
            await _reply(interaction, "-# **<:emoji_28:1550309826758840500>  '  ليست من صلاحياتك استلام مسوؤلية الفترة **")
            return
        if not await db.get_open_session(interaction.guild.id, interaction.user.id):
            await _reply(interaction, "-# ** <:emoji_28:1550309826758840500>  '  سجل دخولك اولاً . **")
            return
        responsibility_statuses = {"dispatch", "deputy_dispatch", "period_manager"}
        if status_key in responsibility_statuses:
            flags = await db.get_active_flags(interaction.guild.id, interaction.user.id)
            if flags and not flags.get(status_key, False):
                conflicts = responsibility_statuses - {status_key}
                if any(flags.get(key, False) for key in conflicts):
                    await _reply(interaction, "-# ** <:emoji_28:1550309826758840500>  '  م تقدر تستعمل اكثر من مسوؤلية بالميدان ، اكتفي بواحدة فقط .**")
                    return
        result = await db.toggle_status(interaction.guild.id, interaction.user.id, status_key)
        if result is None:
            await _reply(interaction, "⚠️ تعذر تحديث الحالة.")
            return
        enabled, _ = result
        if status_key == "bodycam_on":
            await db.set_status(interaction.guild.id, interaction.user.id, "bodycam_off", not enabled)
        await refresh_duty_panel(interaction.guild, expanded=panel_expanded)
        await utils.send_log(interaction.guild, "Duty Status", f"العسكري: {interaction.user.mention} (`{interaction.user.id}`)\nالحالة: {_status_name(status_key)}\nالنتيجة: {'تشغيل' if enabled else 'إيقاف'}")
        await interaction.followup.send(
    "✅ تم تنفيذ العملية وتحديث لوحة تسجيل الدخول.",
    ephemeral=True,
    delete_after=1,
)
        return

    async def _set_explicit(self, interaction: discord.Interaction, status_key: str, enabled: bool):
        if not await _member_check(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        if status_key == "period_manager" and not utils.is_period_manager(interaction.user):
            await _reply(interaction, "-# **<:emoji_28:1550309826758840500>  '  ليست من صلاحياتك استلام مسوؤلية الفترة **")
            return
        if not await db.get_open_session(interaction.guild.id, interaction.user.id):
            await _reply(interaction, "-# ** <:emoji_28:1550309826758840500>  '  سجل دخولك اولاً . **")
            return
        responsibility_statuses = {"dispatch", "deputy_dispatch", "period_manager"}
        if enabled and status_key in responsibility_statuses:
            flags = await db.get_active_flags(interaction.guild.id, interaction.user.id)
            conflicts = responsibility_statuses - {status_key}
            if flags and any(flags.get(key, False) for key in conflicts):
                await _reply(interaction, "-# ** <:emoji_28:1550309826758840500>  '  م تقدر تستعمل اكثر من مسوؤلية بالميدان ، اكتفي بواحدة فقط .**")
                return
        result = await db.set_status(interaction.guild.id, interaction.user.id, status_key, enabled)
        if result is None:
            await _reply(interaction, "⚠️ تعذر تحديث الحالة.")
            return
        await refresh_duty_panel(interaction.guild, expanded=False)
        await utils.send_log(interaction.guild, "Staff Tools", f"العسكري: {interaction.user.mention} (`{interaction.user.id}`)\nالحالة: {_status_name(status_key)}\nالنتيجة: {'تشغيل' if enabled else 'إيقاف'}")
        await interaction.followup.send(
    "✅ تم تنفيذ العملية وتحديث لوحة تسجيل الدخول.",
    ephemeral=True,
    delete_after=1,
)
        return


class LoginPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="LogIn_Panil", description="ينشر لوحة المباشرة الموحدة")
    @app_commands.default_permissions(administrator=True)
    async def publish_panel(self, interaction: discord.Interaction):
        if not utils.has_role(interaction.user, "admin"):
            await interaction.response.send_message("-# **<:emoji_28:1550309826758840500>  '  ليست من صلاحياتك نشرها **", ephemeral=True)
            return
        if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("-# **<:emoji_14:1550308740551417956>   '  قم ب اختيار الروم **", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        embed = await build_duty_embed(interaction.guild)
        existing_id = await db.get_setting(_guild_key(PANEL_MESSAGE_KEY, interaction.guild.id))
        if existing_id and await db.get_setting(_guild_key(PANEL_CHANNEL_KEY, interaction.guild.id)) == str(interaction.channel.id):
            try:
                message = await interaction.channel.fetch_message(int(existing_id))
                await utils.edit_panel(message, embed, LoginPanelView(expanded=False), "duty_ops_banner.png")
                await interaction.delete_original_response()
                return
            except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
                pass

        message = await utils.send_panel(interaction.channel, embed, LoginPanelView(expanded=False), "duty_ops_banner.png")
        await db.set_setting(_guild_key(PANEL_CHANNEL_KEY, interaction.guild.id), str(interaction.channel.id))
        await db.set_setting(_guild_key(PANEL_MESSAGE_KEY, interaction.guild.id), str(message.id))
        await interaction.delete_original_response()

    @app_commands.command(name="Login_On", description="يفتح تسجيل الدخول")
    @app_commands.default_permissions(administrator=True)
    async def open_login(self, interaction: discord.Interaction):
        if not utils.has_role(interaction.user, "admin"):
            await interaction.response.send_message("-# **<:emoji_28:1550309826758840500>  '  ليست من صلاحياتك نشرها **", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await db.set_login_enabled(True)
        if interaction.guild:
            await refresh_duty_panel(interaction.guild)
            await utils.send_log(interaction.guild, "Login Opened", f"المنفذ: {interaction.user.mention}")
        await interaction.followup.send("** <:emoji_5:1550308058448527472>  '  تم فتح تسجيل الدخول . **", ephemeral=True)

    @app_commands.command(name="LogIn_Cloce", description="يقفل تسجيل الدخول ")
    @app_commands.default_permissions(administrator=True)
    async def close_login(self, interaction: discord.Interaction):
        if not utils.has_role(interaction.user, "admin"):
            await interaction.response.send_message("-# **<:emoji_28:1550309826758840500>  '  ليست من صلاحياتك نشرها **", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await db.set_login_enabled(False)
        if interaction.guild:
            await refresh_duty_panel(interaction.guild)
            await utils.send_log(interaction.guild, "Login Closed", f"المنفذ: {interaction.user.mention}")
        await interaction.followup.send("**<:emoji_6:1550308073531252878>  '  تم قفل تسجيل الدخول . **", ephemeral=True)

    @app_commands.command(name="حالة_المباشرة", description="يحدّث لوحة اللوق ان  ")
    @app_commands.default_permissions(administrator=True)
    async def refresh_panel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        updated = bool(interaction.guild and await refresh_duty_panel(interaction.guild))
        if interaction.guild:
            await utils.send_log(interaction.guild, "Duty Panel Refreshed", f"المنفذ: {interaction.user.mention}\nالنتيجة: {'تم التحديث' if updated else 'اللوحة غير منشورة'}")
        if updated:
            await interaction.delete_original_response()
        else:
            await interaction.followup.send(" انشر اللوحة أولاً.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(LoginPanel(bot))
