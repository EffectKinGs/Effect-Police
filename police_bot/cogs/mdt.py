"""
لوحة الـ MDT — ثلاثة أزرار (MDT / Vehicle Impound / Suspect Statement)
كل واحد يفتح نافذة تعبئة، يرسل إمبيد لقناة مخصصة له، ويضيف نقاط تلقائية للعسكري.

كمان: لوحة فحص السوابق (Record Check) — تدخل آيدي شخصية فتطلع كل سوابقه،
مع إمكانية حذف أي سجل منها.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
import utils

RECORD_TYPE_LABELS = {
    "mdt": "MDT",
    "vehicle_impound": "Vehicle Impound",
    "suspect_statement": "Suspect Statement",
}


def _channel_key(record_type: str, guild_id: int) -> str:
    return f"mdt_{record_type}_channel_id:{guild_id}"


async def _get_target_channel(guild: discord.Guild, record_type: str) -> discord.TextChannel | None:
    channel_id = await db.get_setting(_channel_key(record_type, guild.id))
    if not channel_id:
        return None
    channel = guild.get_channel(int(channel_id))
    return channel if isinstance(channel, discord.TextChannel) else None


def _mdt_embed(character_id: str, charge: str, duration: str, fine: str, image_link: str) -> discord.Embed:
    description = (
        f"**1 - <:ETRP_145:1542162076255002624>  '  Id Character : {character_id} **\n"
        f"**2 - <:ETRP_108:1500486542031065253>  '  Person’s Charge : {charge} **\n"
        f"**3 - <:ETRP_75:1500185654015823924>  '  Sentence Duration : {duration} **\n"
        f"** 4 -<:ETRP_139:1542161823128756335>  '  Financial Fine : {fine} **"
    )
    embed = utils.base_embed("MDT", description, image_url="")
    if image_link:
        embed.set_image(url=image_link)
    return embed


def _vehicle_impound_embed(character_id: str, vehicle_type: str, plate: str, charge: str, image_link: str) -> discord.Embed:
    description = (
        f"**1 - <:ETRP_145:1542162076255002624>  '  Id Character : {character_id} **\n"
        f"**2 - <:ETRP_97:1500190884442931271>  '  Offending Vehicle Type : {vehicle_type} **\n"
        f"**3 - <:ETRP_28:1499883636110135476>  '  Vehicle Plate Number : {plate} **\n"
        f"**4 - <:ETRP_139:1542161823128756335>  '  Recorded Charge : {charge} **"
    )
    embed = utils.base_embed("Vehicle Impound", description, image_url="")
    if image_link:
        embed.set_image(url=image_link)
    return embed


def _suspect_statement_embed(character_id: str, case: str, justification: str, image_link: str) -> discord.Embed:
    description = (
        f"**1 - <:ETRP_145:1542162076255002624>  '  Id Character : {character_id} **\n"
        f"**2 - <:GCRP:1542924036458287135>  '  Defendant’s Case : {case} **\n"
        f"**3 - <:ETRP_139:1542161823128756335>  '  Defendant’s Justifications : {justification} **"
    )
    embed = utils.base_embed("Suspect Statement", description, image_url="")
    if image_link:
        embed.set_image(url=image_link)
    return embed


async def _finalize(
    interaction: discord.Interaction, *, record_type: str, character_id: str, summary: str, embed: discord.Embed, points: int,
):
    channel = await _get_target_channel(interaction.guild, record_type)
    if channel is None:
        await interaction.followup.send(
            f"⚠️ ما تم تحديد قناة استقبال لـ **{RECORD_TYPE_LABELS[record_type]}** بعد.\n"
            "اطلب من الأدمن يشغّل `/mdt-panel` ويحدد القنوات أول.",
            ephemeral=True,
        )
        return

    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        await interaction.followup.send("⚠️ تعذر الإرسال لقناة الاستقبال، تأكد من صلاحيات البوت فيها.", ephemeral=True)
        return

    await db.add_mdt_record(interaction.guild.id, record_type, character_id, interaction.user.id, summary)
    await db.add_points(interaction.user.id, points)
    await utils.send_log(
        interaction.guild, f"MDT — {RECORD_TYPE_LABELS[record_type]}",
        f"المُسجِّل: {interaction.user.mention}\nآيدي الشخصية: {character_id}\nالنقاط المُضافة: {points}",
    )
    await interaction.followup.send(f"✅ تم التسجيل بنجاح، وتمت إضافة {points} نقطة لك.", ephemeral=True)


class MDTModal(discord.ui.Modal, title="𝗠𝗗𝗧"):
    def __init__(self):
        super().__init__()
        self.character_id = discord.ui.TextInput(placeholder="", required=True, max_length=50)
        self.charge = discord.ui.TextInput(placeholder="", required=True, max_length=300)
        self.duration = discord.ui.TextInput(placeholder="", required=True, max_length=100)
        self.fine = discord.ui.TextInput(placeholder="", required=True, max_length=100)
        self.image_link = discord.ui.TextInput(placeholder="", required=False, max_length=500)
        self.add_item(discord.ui.Label(text="Id Character / رقم هوية الشخص", component=self.character_id))
        self.add_item(discord.ui.Label(text="Person’s Charge / تُهمة الشخص", component=self.charge))
        self.add_item(discord.ui.Label(text="Sentence Duration / مُدة سجن الشخص", component=self.duration))
        self.add_item(discord.ui.Label(text="Financial Fine / الغرامة المالية", component=self.fine))
        self.add_item(discord.ui.Label(text="Image Link / رابط صورة لوجه المُتهم", component=self.image_link))

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        character_id = str(self.character_id).strip()
        charge = str(self.charge).strip()
        duration = str(self.duration).strip()
        fine = str(self.fine).strip()
        image_link = str(self.image_link).strip()

        embed = _mdt_embed(character_id, charge, duration, fine, image_link)
        summary = f"Charge: {charge} | Sentence: {duration} | Fine: {fine}"
        await _finalize(
            interaction, record_type="mdt", character_id=character_id, summary=summary,
            embed=embed, points=config.MDT_POINTS,
        )


class VehicleImpoundModal(discord.ui.Modal, title="𝗩𝗲𝗵𝗶𝗰𝗹𝗲 𝗜𝗺𝗽𝗼𝘂𝗻𝗱"):
    def __init__(self):
        super().__init__()
        self.character_id = discord.ui.TextInput(placeholder="", required=True, max_length=50)
        self.vehicle_type = discord.ui.TextInput(placeholder="", required=True, max_length=100)
        self.plate = discord.ui.TextInput(placeholder="", required=True, max_length=50)
        self.charge = discord.ui.TextInput(placeholder="", required=True, max_length=300)
        self.image_link = discord.ui.TextInput(placeholder="", required=False, max_length=500)
        self.add_item(discord.ui.Label(text="Id Character / رقم هوية الشخص", component=self.character_id))
        self.add_item(discord.ui.Label(text="Offending Vehicle Type / نوع المركبة", component=self.vehicle_type))
        self.add_item(discord.ui.Label(text="Vehicle Plate Number / رقم اللوحة", component=self.plate))
        self.add_item(discord.ui.Label(text="Recorded Charge / التُهمة المُسجلة", component=self.charge))
        self.add_item(discord.ui.Label(text="Image Link / رابط صورة لوجه المُتهم", component=self.image_link))

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        character_id = str(self.character_id).strip()
        vehicle_type = str(self.vehicle_type).strip()
        plate = str(self.plate).strip()
        charge = str(self.charge).strip()
        image_link = str(self.image_link).strip()

        embed = _vehicle_impound_embed(character_id, vehicle_type, plate, charge, image_link)
        summary = f"Vehicle: {vehicle_type} | Plate: {plate} | Charge: {charge}"
        await _finalize(
            interaction, record_type="vehicle_impound", character_id=character_id, summary=summary,
            embed=embed, points=config.VEHICLE_IMPOUND_POINTS,
        )


class SuspectStatementModal(discord.ui.Modal, title="𝗦𝘂𝘀𝗽𝗲𝗰𝘁 𝗦𝘁𝗮𝘁𝗲𝗺𝗲𝗻𝘁"):
    def __init__(self):
        super().__init__()
        self.character_id = discord.ui.TextInput(placeholder="", required=True, max_length=50)
        self.case = discord.ui.TextInput(placeholder="", required=True, max_length=300)
        self.justification = discord.ui.TextInput(
            placeholder="", required=True, max_length=1000, style=discord.TextStyle.paragraph,
        )
        self.image_link = discord.ui.TextInput(placeholder="", required=False, max_length=500)
        self.add_item(discord.ui.Label(text="Id Character / رقم هوية الشخص", component=self.character_id))
        self.add_item(discord.ui.Label(text="Defendant’s Case / قضية المُتهم", component=self.case))
        self.add_item(discord.ui.Label(text="Defendant’s Justifications / اقوال المُتهم", component=self.justification))
        self.add_item(discord.ui.Label(text="Image Link / رابط صورة لوجه المُتهم", component=self.image_link))

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        character_id = str(self.character_id).strip()
        case = str(self.case).strip()
        justification = str(self.justification).strip()
        image_link = str(self.image_link).strip()

        embed = _suspect_statement_embed(character_id, case, justification, image_link)
        summary = f"Case: {case} | Justification: {justification[:200]}"
        await _finalize(
            interaction, record_type="suspect_statement", character_id=character_id, summary=summary,
            embed=embed, points=config.SUSPECT_STATEMENT_POINTS,
        )


def _can_use_mdt(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    return utils.is_officer(member)


def _can_manage_records(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    return utils.has_role(member, "admin")


class MDTPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="MDT", style=discord.ButtonStyle.secondary, custom_id="mdt_panel:mdt", row=0)
    async def mdt_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not _can_use_mdt(interaction.user):
            await interaction.response.send_message("❌ هذه اللوحة مخصصة للضباط فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(MDTModal())

    @discord.ui.button(label="Vehicle Impound", style=discord.ButtonStyle.secondary, custom_id="mdt_panel:vehicle", row=0)
    async def vehicle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not _can_use_mdt(interaction.user):
            await interaction.response.send_message("❌ هذه اللوحة مخصصة للضباط فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(VehicleImpoundModal())

    @discord.ui.button(label="Suspect Statement", style=discord.ButtonStyle.secondary, custom_id="mdt_panel:statement", row=0)
    async def statement_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not _can_use_mdt(interaction.user):
            await interaction.response.send_message("❌ هذه اللوحة مخصصة للضباط فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(SuspectStatementModal())


class RecordDeleteSelect(discord.ui.Select):
    def __init__(self, records):
        options = [
            discord.SelectOption(
                label=f"#{row[0]} - {RECORD_TYPE_LABELS.get(row[1], row[1])}",
                description=(row[3][:100] if row[3] else None),
                value=str(row[0]),
            )
            for row in records[:25]
        ]
        super().__init__(placeholder="اختر سجل لحذفه...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not _can_manage_records(interaction.user):
            await interaction.response.send_message("❌ حذف السوابق للأدمن فقط.", ephemeral=True)
            return
        record_id = int(self.values[0])
        deleted = await db.delete_mdt_record(record_id)
        if deleted and interaction.guild:
            await utils.send_log(
                interaction.guild, "MDT Record Deleted",
                f"المنفذ: {interaction.user.mention}\nرقم السجل: {record_id}",
            )
        await interaction.response.send_message(
            "✅ تم حذف السجل." if deleted else "⚠️ ما تم العثور على السجل (يمكن انحذف قبل شوي).",
            ephemeral=True,
        )


class RecordDeleteView(discord.ui.View):
    def __init__(self, records):
        super().__init__(timeout=180)
        if records:
            self.add_item(RecordDeleteSelect(records))


class RecordCheckModal(discord.ui.Modal, title="𝗥𝗲𝗰𝗼𝗿𝗱 𝗖𝗵𝗲𝗰𝗸"):
    def __init__(self):
        super().__init__()
        self.character_id = discord.ui.TextInput(placeholder="", required=True, max_length=50)
        self.add_item(discord.ui.Label(text="Id Character / رقم هوية الشخص", component=self.character_id))

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        character_id = str(self.character_id).strip()
        records = await db.get_mdt_records(interaction.guild.id, character_id)
        if not records:
            await interaction.followup.send(f"✅ لا يوجد أي سابقة مسجلة على الآيدي `{character_id}`.", ephemeral=True)
            return

        lines = []
        for row in records:
            record_id, record_type, officer_id, summary, created_at = row
            officer = interaction.guild.get_member(officer_id)
            officer_text = officer.mention if officer else f"`{officer_id}`"
            lines.append(
                f"**#{record_id} - {RECORD_TYPE_LABELS.get(record_type, record_type)}**\n"
                f"{summary}\n"
                f"سجّله: {officer_text} • <t:{created_at}:R>"
            )

        embed = utils.base_embed(f"Record Check ( {character_id} )", "\n\n".join(lines), image_url="")
        note = "" if len(records) <= 25 else f"\n⚠️ يوجد {len(records)} سجل، تقدر تحذف من أول 25 فقط بالقائمة."
        await interaction.followup.send(
            content=note or None, embed=embed, view=RecordDeleteView(records), ephemeral=True,
        )


class RecordCheckPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Check Record", style=discord.ButtonStyle.secondary, custom_id="mdt_panel:record_check")
    async def check_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not _can_use_mdt(interaction.user):
            await interaction.response.send_message("❌ هذه اللوحة مخصصة للضباط فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(RecordCheckModal())


class MDT(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="mdt-panel", description="نشر لوحة الـ MDT وتحديد قنوات استقبال كل نوع")
    @app_commands.describe(
        mdt_channel="القناة اللي تستقبل تقارير MDT",
        vehicle_channel="القناة اللي تستقبل تقارير حجز المركبات",
        statement_channel="القناة اللي تستقبل أقوال المتهمين",
    )
    @app_commands.default_permissions(administrator=True)
    async def mdt_panel(
        self, interaction: discord.Interaction,
        mdt_channel: discord.TextChannel, vehicle_channel: discord.TextChannel, statement_channel: discord.TextChannel,
    ):
        if not isinstance(interaction.user, discord.Member) or not _can_manage_records(interaction.user):
            await interaction.response.send_message("❌ لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ اختر قناة نصية.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await db.set_setting(_channel_key("mdt", interaction.guild.id), str(mdt_channel.id))
        await db.set_setting(_channel_key("vehicle_impound", interaction.guild.id), str(vehicle_channel.id))
        await db.set_setting(_channel_key("suspect_statement", interaction.guild.id), str(statement_channel.id))

        description = (
            "** <:ETRP_108:1500486542031065253>  '  From Here, You Can Record Impound Violations . **\n\n"
            "<:emoji_13:1550308496216432781>︲ **MDT .**\n"
            "<:emoji_28:1550309826758840500> ︲**Mdt / ** تُستعمل للمخالفات بشكل عام ضد الشخص الجاني .\n\n"
            "<:emoji_13:1550308496216432781>︲ **Vehicle Impound .**\n"
            "<:emoji_28:1550309826758840500> ︲**Vehicle Impound . / ** تُستعمل لحجز المركبات المُخالفة .\n\n"
            "<:emoji_13:1550308496216432781>︲ **SusPect Statement .**\n"
            "<:emoji_28:1550309826758840500> ︲ **SusPect Statement . / ** تُستعمل لتسجيل اقوال المُتهم .\n\n"
            "<:emoji_21:1550309215162077214> ︲ **مُلاحظات هامة .**\n\n"
            "<:emoji_14:1550308740551417956> ︲جميع الازرار تُستعمل في الحالات الجنائية مو بكل الحالات تنزلها ، ب استثناء ال ( **MDT** ) .\n"
            "<:emoji_14:1550308740551417956> ︲ في حال نزلت السجل ب الشكل السليم **سيتم اعطائك نقاطها من الخادم بدون المُطالبه فيها .**"
        )

        embed = utils.base_embed(
            "<:emoji_45:1550961724331397231> ︲ MDT RecorDs .",
            description,
            image_url=f"attachment://{config.PANEL_BANNER_ASSET}",
        )

        await utils.send_panel(
            interaction.channel,
            embed,
            MDTPanelView(),
            config.PANEL_BANNER_ASSET,
        )

        await utils.send_log(
            interaction.guild, "MDT Panel",
            f"المنفذ: {interaction.user.mention}\nالقناة: {interaction.channel.mention}\n"
            f"MDT → {mdt_channel.mention}\nVehicle Impound → {vehicle_channel.mention}\n"
            f"Suspect Statement → {statement_channel.mention}",
        )
        await interaction.delete_original_response()

    @app_commands.command(name="record-check-panel", description="نشر لوحة فحص/حذف السوابق في القناة الحالية")
    @app_commands.default_permissions(administrator=True)
    async def record_check_panel(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not _can_manage_records(interaction.user):
            await interaction.response.send_message("❌ لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ اختر قناة نصية.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        description = (
            "** <:ETRP_157:1542608532778647643>  '  From Here, You Can View And Remove The Person’s Recorded Violations And Criminal Records . **"
        )
        embed = utils.base_embed("Record Check", description, image_url=f"attachment://{config.PANEL_BANNER_ASSET}")
        await utils.send_panel(interaction.channel, embed, RecordCheckPanelView(), config.PANEL_BANNER_ASSET)
        await utils.send_log(
            interaction.guild, "Record Check Panel",
            f"المنفذ: {interaction.user.mention}\nالقناة: {interaction.channel.mention}",
        )
        await interaction.delete_original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(MDT(bot))
