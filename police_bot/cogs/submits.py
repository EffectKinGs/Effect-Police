"""لوحة التقديم على العسكرية (Submits) — Effect King's Police Department Application."""

from __future__ import annotations

import re

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
import utils

_MENTION_RE = re.compile(r"<@!?(\d+)>")
_REVIEW_CHANNEL_KEY = "submits_review_channel_id:{guild_id}"


def _can_review(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    return utils.has_role(member, "admin")


async def _get_review_channel(guild: discord.Guild) -> discord.TextChannel | None:
    channel_id = await db.get_setting(_REVIEW_CHANNEL_KEY.format(guild_id=guild.id))
    if not channel_id:
        return None
    channel = guild.get_channel(int(channel_id))
    return channel if isinstance(channel, discord.TextChannel) else None


class SubmitModal(discord.ui.Modal, title="𝗘𝘃𝗶𝗹𝗧𝗼𝘄𝗻 ( 𝗦𝘂𝗯𝗺𝗶𝘁𝘀 )"):
    def __init__(self):
        super().__init__()
        self.character_name = discord.ui.TextInput(placeholder="", required=True, max_length=80)
        self.character_age = discord.ui.TextInput(placeholder="", required=True, max_length=3)
        self.experience = discord.ui.TextInput(
            placeholder="", required=True, max_length=1000, style=discord.TextStyle.paragraph,
        )
        self.add_item(discord.ui.Label(text="Character Name / اسم الكركتر", component=self.character_name))
        self.add_item(discord.ui.Label(text="Character Age / عمر الكركتر", component=self.character_age))
        self.add_item(discord.ui.Label(text="Your Experience / خبراتك", component=self.experience))

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return

        name = str(self.character_name).strip()
        age = str(self.character_age).strip()
        experience = str(self.experience).strip()
        if not all((name, age, experience)):
            await interaction.response.send_message("يلزم تعبئة جميع الحقول.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        description = (
            "**\n"
            "<:emoji_15:1550308794297356388> - New Military Application **\n"
            "**\n"
            f"<:emoji_9:1550308305014882344> ︲ Name : {name}\n"
            f"<:emoji_13:1550308496216432781> ︲Age : {age}\n"
            f"<:emoji_27:1550309790163664906> ︲ Experience : {experience}\n"
            "**"
        )
        embed = utils.base_embed("<:emoji_39:1550337741936394380> ︲ Effect Police ( SuBmits ) .", description, image_url="")
        target_channel = await _get_review_channel(interaction.guild) or interaction.channel

        try:
            await target_channel.send(
                content=f"|| <@&1511976724240535704> || {interaction.user.mention}",
                embed=embed,
                view=SubmissionReviewView(),
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send(" تعذر إرسال طلبك، حاول لاحقًا.", ephemeral=True)
            return

        pending_role = interaction.guild.get_role(config.SUBMISSION_PENDING_ROLE_ID)
        if pending_role is not None and isinstance(interaction.user, discord.Member):
            try:
                await interaction.user.add_roles(pending_role, reason="Military application submitted")
            except discord.Forbidden:
                pass

        await interaction.followup.send("**<:emoji_12:1550308402520133632> ︲ Your Application Has Been Submitted. Please Be Patient . **", ephemeral=True)


class SubmissionReviewView(discord.ui.View):
    """
    View ثابت (persistent) بدون حالة داخلية — هوية مقدّم الطلب تُستخرج من منشن الرسالة نفسها،
    عشان يشتغل بعد أي إعادة تشغيل للبوت بدون فقدان الربط بين الزر والمتقدم.
    """

    def __init__(self):
        super().__init__(timeout=None)

    @staticmethod
    def _extract_applicant_id(message: discord.Message) -> int | None:
        match = _MENTION_RE.search(message.content or "")
        return int(match.group(1)) if match else None

    async def _resolve(self, interaction: discord.Interaction, *, accepted: bool):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member) or not _can_review(interaction.user):
            await interaction.response.send_message("❌ هذه اللوحة للمسؤولين فقط.", ephemeral=True)
            return

        applicant_id = self._extract_applicant_id(interaction.message)
        applicant: discord.Member | None = None
        if applicant_id is not None:
            applicant = interaction.guild.get_member(applicant_id)
            if applicant is None:
                try:
                    applicant = await interaction.guild.fetch_member(applicant_id)
                except (discord.NotFound, discord.HTTPException):
                    applicant = None

        await interaction.response.defer()
        for child in self.children:
            child.disabled = True
        try:
            await interaction.message.edit(view=self)
        except discord.HTTPException:
            pass

        status_line = ("**<:ETRP_80:1500187130729730050>  '  Application Accepted .**" if accepted else " **<:ETRP_159:1542609122665435206>  '  Application Rejected . **") + f" By : {interaction.user.mention}"
        if accepted:
            await db.add_points(interaction.user.id, config.SUBMISSION_ACCEPT_POINTS)

        if applicant is not None:
            pending_role = interaction.guild.get_role(config.SUBMISSION_PENDING_ROLE_ID)
            target_role_id = config.SUBMISSION_ACCEPTED_ROLE_ID if accepted else config.SUBMISSION_REJECTED_ROLE_ID
            target_role = interaction.guild.get_role(target_role_id)
            try:
                if pending_role is not None and pending_role in applicant.roles:
                    await applicant.remove_roles(pending_role, reason="Military application reviewed")
                if target_role is not None:
                    await applicant.add_roles(target_role, reason="Military application reviewed")
            except discord.Forbidden:
                status_line += "\n⚠️ تعذر تحديث رتب المتقدم (تأكد أن رتبة البوت أعلى من هذي الرتب)."

        await interaction.followup.send(status_line)

        if accepted:
            description = (
                "** <a:MTRP:1394930696535015576> - ادارة شرطة ايفل تاون تُبارك لك بقبولك . **\n"
                "** <a:MTRP:1394920520134426636> - و مُتمنين لك التوفيق في التدريب العسكري القادم . **"
            )
            result_embed = utils.base_embed("Accept", description, image_url="")
        else:
            description = (
                "   **<a:MTRP:1394930696535015576> - أدارة شرطة ايفل تاون تود ابلاغك برفض طلبك **\n"
                "-# **<a:MTRP:1394920520134426636> - و مُتمنين لك التوفيق في المرات المُقبلة . **"
            )
            result_embed = utils.base_embed("Reject", description, image_url="")
        await utils.send_log_embed(interaction.guild, result_embed)

        await utils.send_log(
            interaction.guild,
            "Military Application Reviewed",
            f"المُراجع: {interaction.user.mention}\n"
            f"مقدم الطلب: {applicant.mention if applicant else (applicant_id or '—')}\n"
            f"النتيجة: {'قبول' if accepted else 'رفض'}",
        )

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="submits:accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._resolve(interaction, accepted=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id="submits:reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._resolve(interaction, accepted=False)


class SubmissionPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Submits", style=discord.ButtonStyle.secondary, custom_id="submits_panel:open", emoji="<:emoji_19:1550309019938459761>")
    async def open_submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SubmitModal())


class Submits(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="submits-panel", description="نشر لوحة التقديم على العسكرية في القناة الحالية")
    @app_commands.describe(review_channel="القناة اللي تستقبل رسائل التقديمات (اختياري، الافتراضي نفس قناة اللوحة)")
    @app_commands.default_permissions(administrator=True)
    async def submits_panel(self, interaction: discord.Interaction, review_channel: discord.TextChannel = None):
        if not isinstance(interaction.user, discord.Member) or not _can_review(interaction.user):
            await interaction.response.send_message("❌ لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ اختر قناة نصية.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        if review_channel is not None:
            await db.set_setting(_REVIEW_CHANNEL_KEY.format(guild_id=interaction.guild.id), str(review_channel.id))

        description = (
            "**<:emoji_5:1550307911115218974> - Welcome To The Effect King's Police Department Application "
            "Division, Where You Can Serve And Protect Your Nation While Leaving Your Mark Within Its Ranks .**"
        )
        embed = utils.base_embed(
            "<:emoji_39:1550337741936394380> ︲ Effect Police ( SuBmits ) .",
            description,
            image_url=f"attachment://{config.PANEL_BANNER_ASSET}",
        )
        await utils.send_panel(interaction.channel, embed, SubmissionPanelView(), config.PANEL_BANNER_ASSET)
        await utils.send_log(
            interaction.guild, "Submits Panel",
            f"المنفذ: {interaction.user.mention}\nالقناة: {interaction.channel.mention}\n"
            f"قناة استقبال التقديمات: {review_channel.mention if review_channel else 'نفس قناة اللوحة'}",
        )
        await interaction.delete_original_response()

    @app_commands.command(name="set-submits-channel", description="تحديد قناة استقبال رسائل التقديم على العسكرية")
    @app_commands.default_permissions(administrator=True)
    async def set_submits_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not isinstance(interaction.user, discord.Member) or not _can_review(interaction.user):
            await interaction.response.send_message("❌ لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return
        if interaction.guild is None:
            await interaction.response.send_message("هذا الأمر يعمل داخل السيرفر فقط.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await db.set_setting(_REVIEW_CHANNEL_KEY.format(guild_id=interaction.guild.id), str(channel.id))
        await utils.send_log(
            interaction.guild, "Submits Review Channel",
            f"المنفذ: {interaction.user.mention}\nالقناة الجديدة: {channel.mention}",
        )
        await interaction.followup.send(f"✅ صارت {channel.mention} قناة استقبال تقديمات العسكرية.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Submits(bot))
