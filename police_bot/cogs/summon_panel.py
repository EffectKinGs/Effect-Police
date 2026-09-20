"""لوحة استدعاء العسكر — General Call و Specific Personnel."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
import utils

# رتبة الاستدعاء العام (General Call) — الأساسية تُمنح لكل عسكري رسمي، فهي الأشمل.
GENERAL_CALL_ROLE_ID = int(
    getattr(config, "GENERAL_CALL_ROLE_ID", 0)
    or getattr(config, "LSPD_BASE_ROLE_ID", 0)
    or 1542128316285460481
)


def _summon_embed(summoner: discord.abc.User, reason: str | None = None) -> discord.Embed:
    """
    ينشئ رسالة الاستدعاء كـ Embed كامل (نفس هوية بقية لوحات البوت)، تُرسل بالخاص.
    منشن المستقبِل يُرسل خارج الإمبد كـ content منفصل (راجع _dm_summon أدناه) حتى لا يخرب شكل الإمبد.
    """
    reason_line = (reason or "").strip() or "—"
    description = (
        f"** <:ETRP_97:1500190884442931271>  -  ( {reason_line} ) **\n\n"
        f"** <:ETRP_141:1542161889038172180> - You Have Been Summoned By : ( {summoner.mention} ) **"
    )
    return utils.base_embed("Summon", description, image_url="")


async def _dm_summon(member: discord.Member, embed: discord.Embed):
    """يرسل رسالة الاستدعاء بالخاص: منشن الشخص كنص عادي فوق الإمبد + الإمبد نفسه."""
    await member.send(content=member.mention, embed=embed)


async def _role_members_all(guild: discord.Guild, role: discord.Role) -> list[discord.Member]:
    """
    يجيب كل من يحمل الرتبة (أونلاين أو أوفلاين) عبر جلب أعضاء السيرفر مباشرة من ديسكورد،
    بدل الاعتماد فقط على الكاش المحلي (role.members) اللي قد ما يكون مكتمل لأعضاء الأوفلاين.
    """
    found: dict[int, discord.Member] = {m.id: m for m in role.members}
    try:
        async for member in guild.fetch_members(limit=None):
            if role in member.roles:
                found[member.id] = member
    except discord.HTTPException:
        pass
    return list(found.values())


def _can_summon(member: discord.Member) -> bool:
    return utils.has_any_role(member, config.SUMMON_ROLE_IDS)


def _resolve_general_role(guild: discord.Guild) -> discord.Role | None:
    candidates = [
        GENERAL_CALL_ROLE_ID,
        getattr(config, "LSPD_BASE_ROLE_ID", 0),
        getattr(config, "LSPD_OFFICERS_ROLE_ID", 0),
    ]
    seen: set[int] = set()
    for rid in candidates:
        rid = int(rid or 0)
        if not rid or rid in seen:
            continue
        seen.add(rid)
        role = guild.get_role(rid)
        if role is not None:
            return role
    return None


async def find_member(guild: discord.Guild, user_id_text: str) -> discord.Member | None:
    user_id_text = user_id_text.strip()
    if not user_id_text.isdigit() or len(user_id_text) < 15:
        return None
    user_id = int(user_id_text)
    member = guild.get_member(user_id)
    if member is not None:
        return member
    try:
        return await guild.fetch_member(user_id)
    except (discord.NotFound, discord.HTTPException):
        return None


class GeneralCallModal(discord.ui.Modal, title="𝗦𝘂𝗺𝗺𝗼𝗻 ( 𝗚𝗲𝗻𝗲𝗿𝗮𝗹 𝗖𝗮𝗹𝗹 )"):
    def __init__(self):
        super().__init__()
        self.reason = discord.ui.TextInput(
            placeholder="", required=True, max_length=300, style=discord.TextStyle.paragraph,
        )
        self.add_item(discord.ui.Label(text="𝗥𝗲𝗮𝘀𝗼𝗻 / 𝗦𝗲𝗯𝗲𝗯", component=self.reason))

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member) or not _can_summon(interaction.user):
            await interaction.response.send_message("❌ هذه اللوحة مخصصة للضباط والمسؤولين فقط.", ephemeral=True)
            return

        reason = str(self.reason).strip()
        if not reason:
            await interaction.response.send_message("يلزم كتابة السبب.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        role = _resolve_general_role(interaction.guild)
        if role is None:
            await interaction.followup.send(
                "⚠️ لم يتم العثور على رتبة الاستدعاء العام داخل السيرفر.\n"
                f"المعرّف الحالي: `{GENERAL_CALL_ROLE_ID}`\n"
                "أرسل لي آيدي الرتبة الصحيح من إعدادات السيرفر → Roles → انسخ ID.",
                ephemeral=True,
            )
            return

        members = await _role_members_all(interaction.guild, role)
        members = [m for m in members if not m.bot]
        if not members:
            await interaction.followup.send("⚠️ ما فيه أعضاء يحملون هذه الرتبة حاليًا.", ephemeral=True)
            return

        embed = _summon_embed(interaction.user, reason)
        sent, failed = 0, 0
        for member in members:
            try:
                await _dm_summon(member, embed)
                sent += 1
            except (discord.Forbidden, discord.HTTPException):
                failed += 1

        await utils.send_log(
            interaction.guild,
            "General Call Summon",
            f"المستدعي: {interaction.user.mention}\nالرتبة: {role.mention} (`{role.id}`)\nتم الإرسال: {sent}\nفشل: {failed}\nالسبب: {reason}",
        )
        summary = f"✅ تم استدعاء {sent} من أصل {len(members)} بالخاص."
        if failed:
            summary += f" (فشل الإرسال لـ {failed}، الخاص مغلق غالبًا)"
        await interaction.followup.send(summary, ephemeral=True)


class SpecificPersonnelModal(discord.ui.Modal, title="𝗦𝘂𝗺𝗺𝗼𝗻 ( 𝗦𝗽𝗲𝗰𝗶𝗳𝗶𝗰 𝗣𝗲𝗿𝘀𝗼𝗻𝗻𝗲𝗹 )"):
    def __init__(self):
        super().__init__()
        self.discord_user_id = discord.ui.TextInput(placeholder="", required=True, max_length=20)
        self.reason = discord.ui.TextInput(
            placeholder="", required=True, max_length=300, style=discord.TextStyle.paragraph,
        )
        self.add_item(discord.ui.Label(text="𝗗𝗶𝘀𝗰𝗼𝗿𝗱 𝗨𝘀𝗲𝗿 𝗜𝗗 .", component=self.discord_user_id))
        self.add_item(discord.ui.Label(text="𝗥𝗲𝗮𝘀𝗼𝗻 / 𝗦𝗲𝗯𝗲𝗯", component=self.reason))

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member) or not _can_summon(interaction.user):
            await interaction.response.send_message("❌ هذه اللوحة مخصصة للضباط والمسؤولين فقط.", ephemeral=True)
            return

        user_id_text = str(self.discord_user_id).strip()
        reason = str(self.reason).strip()
        if not user_id_text or not reason:
            await interaction.response.send_message("يلزم تعبئة جميع الحقول.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        member = await find_member(interaction.guild, user_id_text)
        if member is None:
            await interaction.followup.send("❌ لم يتم العثور على هذا العضو داخل السيرفر.", ephemeral=True)
            return

        embed = _summon_embed(interaction.user, reason)
        try:
            await _dm_summon(member, embed)
        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send(f"⚠️ تعذر إرسال رسالة خاصة لـ {member.mention} (الخاص مغلق غالبًا).", ephemeral=True)
            return

        await utils.send_log(
            interaction.guild,
            "Specific Personnel Summon",
            f"المستدعي: {interaction.user.mention}\nالمستدعى: {member.mention} (`{member.id}`)\nالسبب: {reason}",
        )
        await interaction.followup.send(f"✅ تم استدعاء {member.mention} بالخاص.", ephemeral=True)


class SummonPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="General Call",
        style=discord.ButtonStyle.secondary,
        custom_id="summon_panel:general",
        row=0,
    )
    async def general_call(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member) or not _can_summon(interaction.user):
            await interaction.response.send_message("❌ هذه اللوحة مخصصة للضباط والمسؤولين فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(GeneralCallModal())

    @discord.ui.button(
        label="Specific Personnel",
        style=discord.ButtonStyle.secondary,
        custom_id="summon_panel:specific",
        row=0,
    )
    async def specific_personnel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member) or not _can_summon(interaction.user):
            await interaction.response.send_message("❌ هذه اللوحة مخصصة للضباط والمسؤولين فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(SpecificPersonnelModal())


class SummonPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="summon-panel", description="نشر لوحة الاستدعاء (General Call / Specific Personnel)")
    @app_commands.default_permissions(administrator=True)
    async def summon_panel(self, interaction: discord.Interaction):
        if not utils.has_role(interaction.user, "admin") or interaction.guild is None:
            await interaction.response.send_message("❌ لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ اختر قناة نصية.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        description = "**<:ETRP_97:1500190884442931271> - Use the buttons below to summon personnel.**"
        embed = utils.base_embed("Effect King's ( Summon )", description, image_url=f"attachment://{config.PANEL_BANNER_ASSET}")
        await utils.send_panel(interaction.channel, embed, SummonPanelView(), config.PANEL_BANNER_ASSET)
        await db.set_setting(f"summon_panel_channel_id:{interaction.guild.id}", str(interaction.channel.id))
        await utils.send_log(
            interaction.guild,
            "Summon Panel",
            f"المنفذ: {interaction.user.mention}\nالقناة: {interaction.channel.mention}",
        )
        await interaction.delete_original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(SummonPanel(bot))
