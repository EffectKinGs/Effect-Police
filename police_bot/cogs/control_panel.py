from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
import utils


def allowed(member: discord.Member) -> bool:
    return member.guild_permissions.administrator or any(role.id in config.LSPD_ADMIN_ROLE_IDS for role in member.roles)


def get_role(guild: discord.Guild, role_id: int):
    return guild.get_role(role_id)


def all_managed_role_ids() -> set[int]:
    return {
        config.LSPD_BASE_ROLE_ID,
        config.LSPD_OFFICERS_ROLE_ID,
        config.LSPD_CHIEF_OFFICE_ROLE_ID,
        *config.LSPD_RANK_ROLE_IDS.values(),
        *config.LSPD_WING_ROLE_IDS.values(),
        *config.LSPD_KICK_ROLE_IDS.values(),
    }


async def find_member(guild: discord.Guild, user_id_text: str) -> discord.Member | None:
    if not user_id_text.isdigit() or len(user_id_text) < 15:
        return None
    member = guild.get_member(int(user_id_text))
    if member is not None:
        return member
    try:
        return await guild.fetch_member(int(user_id_text))
    except (discord.NotFound, discord.HTTPException):
        return None


async def apply_rank(
    member: discord.Member,
    rank_name: str,
    unit: str | None = None,
    display_name: str | None = None,
):
    guild = member.guild
    managed = [get_role(guild, rid) for rid in all_managed_role_ids()]
    managed = [item for item in managed if item is not None and item in member.roles]
    if managed:
        await member.remove_roles(*managed, reason="LSPD Control Panel rank update")

    new_ids = [config.LSPD_BASE_ROLE_ID, config.LSPD_RANK_ROLE_IDS[rank_name]]
    if rank_name in config.LSPD_OFFICER_RANKS:
        new_ids.append(config.LSPD_OFFICERS_ROLE_ID)
    if rank_name in config.LSPD_PRESIDENCY_RANKS:
        new_ids.append(config.LSPD_CHIEF_OFFICE_ROLE_ID)
    new_roles = [get_role(guild, rid) for rid in new_ids]
    new_roles = [item for item in new_roles if item is not None]
    if new_roles:
        await member.add_roles(*new_roles, reason="LSPD Control Panel rank assignment")

    if unit is not None:
        name = (display_name or member.display_name).strip().split(" | ", 1)[0].strip()
        await member.edit(nick=f"{name} | {unit.strip()}", reason="LSPD unit update")


class LSPDIdentityModal(discord.ui.Modal, title="𝗟𝗦𝗣𝗗 𝗥𝗲𝗴𝗶𝘀𝘁𝗿𝗮𝘁𝗶𝗼𝗻"):
    def __init__(self):
        super().__init__()
        self.discord_user_id = discord.ui.TextInput(placeholder="", required=True, max_length=20)
        self.officer_name = discord.ui.TextInput(placeholder="", required=True, max_length=80)
        self.unit = discord.ui.TextInput(placeholder="", required=True, max_length=40)
        self.rank = discord.ui.Select(
            placeholder="𝗦𝗲𝗹𝗲𝗰𝘁 𝗥𝗮𝗻𝗸",
            options=[discord.SelectOption(label=name, value=name) for name in config.LSPD_RANK_ORDER],
            min_values=1,
            max_values=1,
            required=True,
        )
        self.recruitment_date = discord.ui.TextInput(placeholder="30/04/93", required=True, max_length=8)
        self.add_item(discord.ui.Label(text="Discord User ID", component=self.discord_user_id))
        self.add_item(discord.ui.Label(text="Officer Name", component=self.officer_name))
        self.add_item(discord.ui.Label(text="Unit", component=self.unit))
        self.add_item(discord.ui.Label(text="Officer Rank", component=self.rank))
        self.add_item(discord.ui.Label(text="Date Of Recruitment", component=self.recruitment_date))

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member) or not allowed(interaction.user):
            await interaction.response.send_message("هذه النافذة للمسؤولين فقط.", ephemeral=True)
            return
        user_id_text = str(self.discord_user_id).strip()
        officer_name = str(self.officer_name).strip()
        unit = str(self.unit).strip()
        rank_name = self.rank.values[0] if self.rank.values else ""
        date_text = str(self.recruitment_date).strip()
        if not all((user_id_text, officer_name, unit, rank_name, date_text)):
            await interaction.response.send_message("يلزم تعبئة جميع الحقول.", ephemeral=True)
            return
        from datetime import datetime
        try:
            datetime.strptime(date_text, "%d/%m/%y")
        except ValueError:
            await interaction.response.send_message("Date Of Recruitment يجب أن يكون بالصيغة DD/MM/YY.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        member = await find_member(interaction.guild, user_id_text)
        if member is None:
            await interaction.followup.send("لم يتم العثور على الحساب داخل السيرفر.", ephemeral=True)
            return
        try:
            await apply_rank(member, rank_name, unit=unit, display_name=officer_name)
            await utils.send_log(
                interaction.guild,
                "LSPD Registration",
                f"المنفذ: {interaction.user.mention}\nالعضو: {member.mention} (`{member.id}`)\nالاسم: {officer_name}\nالوحدة: {unit}\nالرتبة: {rank_name}\nتاريخ التسجيل: {date_text}",
            )
        except discord.Forbidden:
            await interaction.followup.send("تعذر إعطاء الرتب أو تغيير الاسم. تأكد أن رتبة البوت أعلى من رتب LSPD.", ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.followup.send("تعذر تنفيذ التسجيل حالياً.", ephemeral=True)
            return
        await interaction.followup.send(f"تم تسجيل **{officer_name} | {unit}** برتبة **{rank_name}**.", ephemeral=True)


class UpgradeModal(discord.ui.Modal, title="𝗟𝗦𝗣𝗗 𝗨𝗽𝗴𝗿𝗮𝗱𝗲"):
    def __init__(self):
        super().__init__()
        self.discord_user_id = discord.ui.TextInput(placeholder="", required=True, max_length=20)
        self.unit = discord.ui.TextInput(placeholder="", required=True, max_length=40)
        self.rank = discord.ui.Select(
            placeholder="𝗦𝗲𝗹𝗲𝗰𝘁 𝗥𝗮𝗻𝗸",
            options=[discord.SelectOption(label=name, value=name) for name in config.LSPD_RANK_ORDER],
            min_values=1,
            max_values=1,
            required=True,
        )
        self.add_item(discord.ui.Label(text="𝗗𝗶𝘀𝗰𝗼𝗿𝗱 𝗨𝘀𝗲𝗿 𝗜𝗗 .", component=self.discord_user_id))
        self.add_item(discord.ui.Label(text="𝗨𝗻𝗶𝘁", component=self.unit))
        self.add_item(discord.ui.Label(text="𝗢𝗳𝗳𝗶𝗰𝗲𝗿 𝗥𝗮𝗻𝗸", component=self.rank))

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member) or not allowed(interaction.user):
            await interaction.response.send_message("هذه النافذة للمسؤولين فقط.", ephemeral=True)
            return
        user_id_text = str(self.discord_user_id).strip()
        unit = str(self.unit).strip()
        rank_name = self.rank.values[0] if self.rank.values else ""
        if not all((user_id_text, unit, rank_name)):
            await interaction.response.send_message("يلزم تعبئة جميع الحقول.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        member = await find_member(interaction.guild, user_id_text)
        if member is None:
            await interaction.followup.send("لم يتم العثور على الحساب داخل السيرفر.", ephemeral=True)
            return
        try:
            await apply_rank(member, rank_name, unit=unit)
            await utils.send_log(
                interaction.guild,
                "LSPD Upgrade",
                f"المنفذ: {interaction.user.mention}\nالعضو: {member.mention} (`{member.id}`)\nالرتبة الجديدة: {rank_name}\nالوحدة الجديدة: {unit}",
            )
        except discord.Forbidden:
            await interaction.followup.send("تعذر تعديل الرتب أو الاسم؛ ارفع رتبة البوت فوق رتب LSPD.", ephemeral=True)
            return
        await interaction.followup.send(f"تم تحديث {member.mention} إلى **{rank_name} | {unit}**.", ephemeral=True)


class WingModal(discord.ui.Modal, title="𝗟𝗦𝗣𝗗 𝗪𝗶𝗻𝗴"):
    def __init__(self):
        super().__init__()
        self.discord_user_id = discord.ui.TextInput(placeholder="", required=True, max_length=20)
        wing_options = [discord.SelectOption(label=name, value=name) for name in config.LSPD_WING_ROLE_IDS]
        self.wing = discord.ui.Select(
            placeholder="𝗦𝗲𝗹𝗲𝗰𝘁 𝗪𝗶𝗻𝗴",
            options=wing_options,
            min_values=1,
            max_values=len(wing_options),
            required=True,
        )
        self.add_item(discord.ui.Label(text="𝗗𝗶𝘀𝗰𝗼𝗿𝗱 𝗨𝘀𝗲𝗿 𝗜𝗗 .", component=self.discord_user_id))
        self.add_item(discord.ui.Label(text="𝗪𝗶𝗻𝗴", component=self.wing))

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member) or not allowed(interaction.user):
            await interaction.response.send_message("هذه النافذة للمسؤولين فقط.", ephemeral=True)
            return
        user_id_text = str(self.discord_user_id).strip()
        wing_names = list(self.wing.values)
        if not user_id_text or not wing_names:
            await interaction.response.send_message("يلزم تعبئة جميع الحقول.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        member = await find_member(interaction.guild, user_id_text)
        wing_roles = [get_role(interaction.guild, config.LSPD_WING_ROLE_IDS.get(name, 0)) for name in wing_names]
        wing_roles = [role for role in wing_roles if role is not None]
        if member is None or len(wing_roles) != len(wing_names):
            await interaction.followup.send("تعذر العثور على الحساب أو إحدى رتب الأجنحة.", ephemeral=True)
            return
        try:
            await member.add_roles(*wing_roles, reason="LSPD Wing assignment")
            await utils.send_log(interaction.guild, "LSPD Wing", f"المنفذ: {interaction.user.mention}\nالعضو: {member.mention} (`{member.id}`)\nالأجنحة: {', '.join(wing_names)}")
        except discord.Forbidden:
            await interaction.followup.send("تعذر إعطاء رتبة الجناح.", ephemeral=True)
            return
        await interaction.followup.send(f"تمت إضافة **{', '.join(wing_names)}** إلى {member.mention}.", ephemeral=True)


class KickModal(discord.ui.Modal, title="𝗟𝗦𝗣𝗗 𝗞𝗶𝗰𝗸 ."):
    def __init__(self):
        super().__init__()
        self.discord_user_id = discord.ui.TextInput(placeholder="", required=True, max_length=20)
        self.action = discord.ui.Select(
            placeholder="𝗦𝗲𝗹𝗲𝗰𝘁 𝗔𝗰𝘁𝗶𝗼𝗻",
            options=[discord.SelectOption(label=name, value=name) for name in config.LSPD_KICK_ROLE_IDS],
            min_values=1,
            max_values=1,
            required=True,
        )
        self.add_item(discord.ui.Label(text="𝗗𝗶𝘀𝗰𝗼𝗿𝗱 𝗨𝘀𝗲𝗿 𝗜𝗗 .", component=self.discord_user_id))
        self.add_item(discord.ui.Label(text="𝗔𝗰𝘁𝗶𝗼𝗻", component=self.action))

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member) or not allowed(interaction.user):
            await interaction.response.send_message("هذه النافذة للمسؤولين فقط.", ephemeral=True)
            return
        user_id_text = str(self.discord_user_id).strip()
        action_name = self.action.values[0] if self.action.values else ""
        if not user_id_text or not action_name:
            await interaction.response.send_message("يلزم تعبئة جميع الحقول.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        member = await find_member(interaction.guild, user_id_text)
        action_role = get_role(interaction.guild, config.LSPD_KICK_ROLE_IDS.get(action_name, 0))
        if member is None or action_role is None:
            await interaction.followup.send("تعذر العثور على الحساب أو رتبة الإجراء.", ephemeral=True)
            return
        try:
            managed = [get_role(interaction.guild, rid) for rid in all_managed_role_ids() if rid != config.LSPD_KICK_ROLE_IDS[action_name]]
            managed = [item for item in managed if item is not None and item in member.roles]
            if managed:
                await member.remove_roles(*managed, reason=f"LSPD action: {action_name}")
            await member.add_roles(action_role, reason=f"LSPD action: {action_name}")
            await utils.send_log(interaction.guild, "LSPD Kick", f"المنفذ: {interaction.user.mention}\nالعضو: {member.mention} (`{member.id}`)\nالإجراء: {action_name}")
        except discord.Forbidden:
            await interaction.followup.send("تعذر تعديل رتب العضو.", ephemeral=True)
            return
        await interaction.followup.send(f"تم تنفيذ **{action_name}** على {member.mention}.", ephemeral=True)


class LSPDControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="𝗟𝗦𝗣𝗗", style=discord.ButtonStyle.secondary, custom_id="lspd:open:register", row=0)
    async def lspd(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not allowed(interaction.user):
            await interaction.response.send_message("هذه اللوحة للمسؤولين فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(LSPDIdentityModal())

    @discord.ui.button(label="𝗨𝗽𝗴𝗿𝗮𝗱𝗲", style=discord.ButtonStyle.secondary, custom_id="lspd:open:upgrade", row=0)
    async def upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not allowed(interaction.user):
            await interaction.response.send_message("هذه اللوحة للمسؤولين فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(UpgradeModal())

    @discord.ui.button(label="𝗪𝗶𝗻𝗴", style=discord.ButtonStyle.secondary, custom_id="lspd:open:wing", row=0)
    async def wing(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not allowed(interaction.user):
            await interaction.response.send_message("هذه اللوحة للمسؤولين فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(WingModal())

    @discord.ui.button(label="𝗞𝗶𝗰𝗸", style=discord.ButtonStyle.danger, custom_id="lspd:open:kick", row=1)
    async def kick(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not allowed(interaction.user):
            await interaction.response.send_message("هذه اللوحة للمسؤولين فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(KickModal())


class ControlPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="lspd-panel", description="نشر لوحة تحكم LSPD")
    @app_commands.default_permissions(administrator=True)
    async def lspd_panel(self, interaction: discord.Interaction):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member) or not allowed(interaction.user):
            await interaction.response.send_message("هذه اللوحة للمسؤولين فقط.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("اختر قناة نصية.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        description = (
    "-# ** <:emoji_12:1550308402520133632>  '  LSPD **\n"
    "-# <:emoji_14:1550308740551417956>  -  Button LSPD : للتوظيف في النظام .\n"
    "-# ** <:emoji_12:1550308402520133632>   '   Upgrade **\n"
    "-# <:emoji_14:1550308740551417956>  -  Button Upgrade / للترقية\n"
    "-# ** <:emoji_12:1550308402520133632>   '  Wing **\n"
    "-# <:emoji_14:1550308740551417956>  -  Button Wing / ل اعطاء ونق للعسكري .\n"
    "-# ** <:emoji_12:1550308402520133632>   '  Kick **\n"
    "-# <:emoji_14:1550308740551417956>  -  Button Kick / للتوقيف عن العمل و الاقصاء من النظام"
)
        embed = utils.base_embed("<:emoji_23:1550309501788360855> ︲ Police SysTem .", description)
        await utils.send_panel(interaction.channel, embed, LSPDControlView(), config.PANEL_BANNER_ASSET)
        await utils.send_log(interaction.guild, "LSPD Panel", f"المنفذ: {interaction.user.mention}\nتم نشر لوحة LSPD في {interaction.channel.mention}")
        await interaction.delete_original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(ControlPanel(bot))
