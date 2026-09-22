"""
لوحة الـ MDT — ثلاثة أزرار (MDT / Vehicle Impound / Suspect Statement)
كل واحد يفتح نافذة تعبئة، يرسل إمبيد لقناة مخصصة له، ويضيف نقاط تلقائية للعسكري.
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


# ==========================================================
#   ✅ الإمبيدات الاحترافية (V1) — تدعم الصورة الكبيرة
# ==========================================================

def _mdt_embed(admin_mention, character_id, suspect_name, charge, fine, image_link):
    embed = discord.Embed(
        title="<:emoji_45:1550961724331397231> ︲ MDT Record",
        color=discord.Color.from_str("#01FFFE"),
    )
    embed.add_field(
        name="\u200b",
        value=(
            f"**1 - <:emoji_38:1550334422274801664>︲Mention the official : ** {admin_mention}\n"
            f"**2 - <:emoji_13:1550308496216432781>︲Id Character : ** {character_id}\n"
            f"**3 - <:emoji_9:1550308305014882344>︲Suspect Name : ** {suspect_name}\n"
            f"**4 - <:emoji_14:1550308740551417956>︲Person’s Charge : ** {charge}\n"
            f"**5 - <:emoji_14:1550308636214169610>︲Financial Fine : ** {fine}"
        ),
        inline=False,
    )
    if image_link:
        embed.set_image(url=image_link)
    embed.set_footer(text="System Police Effect .")
    return embed


def _vehicle_impound_embed(admin_mention, character_id, suspect_name, vehicle_type, plate, charge, image_link):
    embed = discord.Embed(
        title="<:emoji_45:1550961724331397231> ︲ Vehicle Impound",
        color=discord.Color.from_str("#01FFFE"),
    )
    embed.add_field(
        name="\u200b",
        value=(
            f"**1 - <:emoji_38:1550334422274801664>︲Mention the official : ** {admin_mention}\n"
            f"**2 - <:emoji_13:1550308496216432781>︲Id Character : ** {character_id}\n"
            f"**3 - <:emoji_9:1550308305014882344>︲Suspect Name : ** {suspect_name}\n"
            f"**4 - <:emoji_131:1551326444565831813>︲Offending Vehicle Type : ** {vehicle_type}\n"
            f"**5 - <:emoji_39:1550337741936394380>︲Vehicle Plate Number : ** {plate}\n"
            f"**6 - <:FaLcoN:1551327269493153887>︲Recorded Charge : ** {charge}"
        ),
        inline=False,
    )
    if image_link:
        embed.set_image(url=image_link)
    embed.set_footer(text="System Police Effect .")
    return embed


def _suspect_statement_embed(admin_mention, character_id, suspect_name, case, justification, image_link):
    embed = discord.Embed(
        title="<:emoji_45:1550961724331397231> ︲ Suspect Statement",
        color=discord.Color.from_str("#01FFFE"),
    )
    embed.add_field(
        name="\u200b",
        value=(
            f"**1 - <:emoji_38:1550334422274801664>︲Mention the official : ** {admin_mention}\n"
            f"**2 - <:emoji_13:1550308496216432781>︲Id Character : ** {character_id}\n"
            f"**3 - <:emoji_9:1550308305014882344>︲Suspect Name : ** {suspect_name}\n"
            f"**4 - <:emoji:1551351828774522952>︲Defendant’s Case : ** {case}\n"
            f"**5 - <a:emoji_41:1550934952793612399>︲Defendant’s Justifications : ** {justification}"
        ),
        inline=False,
    )
    if image_link:
        embed.set_image(url=image_link)
    embed.set_footer(text="System Police Effect .")
    return embed


async def _finalize(interaction, *, record_type, character_id, summary, embed, points):
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
    await interaction.followup.send(
        f"-# **<:ELRP:1551384064613949603> ︲ تم تسجيل السجل بنجاح ، وتمت اضافة {points} نقطة لك .**",
        ephemeral=True,
    )


# ==========================================================
#   المودالات
# ==========================================================

class MDTModal(discord.ui.Modal, title="𝗠𝗗𝗧"):
    def __init__(self):
        super().__init__()
        self.character_id = discord.ui.TextInput(placeholder="", required=True, max_length=50)
        self.suspect_name = discord.ui.TextInput(placeholder="", required=True, max_length=100)
        self.charge = discord.ui.TextInput(placeholder="", required=True, max_length=300)
        self.fine = discord.ui.TextInput(placeholder="", required=True, max_length=100)
        self.image_link = discord.ui.TextInput(placeholder="", required=False, max_length=500)
        self.add_item(discord.ui.Label(text="Id Character / رقم هوية الشخص", component=self.character_id))
        self.add_item(discord.ui.Label(text="Suspect Name / اسم المُتهم", component=self.suspect_name))
        self.add_item(discord.ui.Label(text="Person’s Charge / تُهمة الشخص", component=self.charge))
        self.add_item(discord.ui.Label(text="Financial Fine / الغرامة المالية", component=self.fine))
        self.add_item(discord.ui.Label(text="Image Link / رابط صورة لوجه المُتهم", component=self.image_link))

    async def on_submit(self, interaction):
        if interaction.guild is None:
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        character_id = str(self.character_id).strip()
        suspect_name = str(self.suspect_name).strip()
        charge = str(self.charge).strip()
        fine = str(self.fine).strip()
        image_link = str(self.image_link).strip()
        admin_mention = interaction.user.mention

        embed = _mdt_embed(admin_mention, character_id, suspect_name, charge, fine, image_link)
        summary = f"Suspect: {suspect_name} | Charge: {charge} | Fine: {fine}"
        await _finalize(interaction, record_type="mdt", character_id=character_id, summary=summary,
                        embed=embed, points=config.MDT_POINTS)


class VehicleImpoundModal(discord.ui.Modal, title="𝗩𝗲𝗵𝗶𝗰𝗹𝗲 𝗜𝗺𝗽𝗼𝘂𝗻𝗱"):
    def __init__(self):
        super().__init__()
        self.character_id = discord.ui.TextInput(placeholder="", required=True, max_length=50)
        self.suspect_name = discord.ui.TextInput(placeholder="", required=True, max_length=100)
        self.vehicle_type = discord.ui.TextInput(placeholder="", required=True, max_length=100)
        self.plate = discord.ui.TextInput(placeholder="", required=True, max_length=50)
        self.charge = discord.ui.TextInput(placeholder="", required=True, max_length=300)
        self.image_link = discord.ui.TextInput(placeholder="", required=False, max_length=500)
        self.add_item(discord.ui.Label(text="Id Character / رقم هوية الشخص", component=self.character_id))
        self.add_item(discord.ui.Label(text="Suspect Name / اسم المُتهم", component=self.suspect_name))
        self.add_item(discord.ui.Label(text="Offending Vehicle Type / نوع المركبة", component=self.vehicle_type))
        self.add_item(discord.ui.Label(text="Vehicle Plate Number / رقم اللوحة", component=self.plate))
        self.add_item(discord.ui.Label(text="Recorded Charge / التُهمة المُسجلة", component=self.charge))
        self.add_item(discord.ui.Label(text="Image Link / رابط صورة لوجه المُتهم", component=self.image_link))

    async def on_submit(self, interaction):
        if interaction.guild is None:
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        character_id = str(self.character_id).strip()
        suspect_name = str(self.suspect_name).strip()
        vehicle_type = str(self.vehicle_type).strip()
        plate = str(self.plate).strip()
        charge = str(self.charge).strip()
        image_link = str(self.image_link).strip()
        admin_mention = interaction.user.mention

        embed = _vehicle_impound_embed(admin_mention, character_id, suspect_name, vehicle_type, plate, charge, image_link)
        summary = f"Suspect: {suspect_name} | Vehicle: {vehicle_type} | Plate: {plate} | Charge: {charge}"
        await _finalize(interaction, record_type="vehicle_impound", character_id=character_id, summary=summary,
                        embed=embed, points=config.VEHICLE_IMPOUND_POINTS)


class SuspectStatementModal(discord.ui.Modal, title="𝗦𝘂𝘀𝗽𝗲𝗰𝘁 𝗦𝘁𝗮𝘁𝗲𝗺𝗲𝗻𝘁"):
    def __init__(self):
        super().__init__()
        self.character_id = discord.ui.TextInput(placeholder="", required=True, max_length=50)
        self.suspect_name = discord.ui.TextInput(placeholder="", required=True, max_length=100)
        self.case = discord.ui.TextInput(placeholder="", required=True, max_length=300)
        self.justification = discord.ui.TextInput(placeholder="", required=True, max_length=1000,
                                                  style=discord.TextStyle.paragraph)
        self.image_link = discord.ui.TextInput(placeholder="", required=False, max_length=500)
        self.add_item(discord.ui.Label(text="Id Character / رقم هوية الشخص", component=self.character_id))
        self.add_item(discord.ui.Label(text="Suspect Name / اسم المُتهم", component=self.suspect_name))
        self.add_item(discord.ui.Label(text="Defendant’s Case / قضية المُتهم", component=self.case))
        self.add_item(discord.ui.Label(text="Defendant’s Justifications / اقوال المُتهم", component=self.justification))
        self.add_item(discord.ui.Label(text="Image Link / رابط صورة لوجه المُتهم", component=self.image_link))

    async def on_submit(self, interaction):
        if interaction.guild is None:
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        character_id = str(self.character_id).strip()
        suspect_name = str(self.suspect_name).strip()
        case = str(self.case).strip()
        justification = str(self.justification).strip()
        image_link = str(self.image_link).strip()
        admin_mention = interaction.user.mention

        embed = _suspect_statement_embed(admin_mention, character_id, suspect_name, case, justification, image_link)
        summary = f"Suspect: {suspect_name} | Case: {case} | Justification: {justification[:200]}"
        await _finalize(interaction, record_type="suspect_statement", character_id=character_id, summary=summary,
                        embed=embed, points=config.SUSPECT_STATEMENT_POINTS)


def _can_use_mdt(member):
    return utils.has_any_role(member, config.MDT_ALLOWED_ROLE_IDS)


def _can_manage_records(member):
    return utils.has_any_role(member, config.SYSTEM_ADMIN_ROLE_IDS)


class MDTPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="MDT", style=discord.ButtonStyle.secondary, custom_id="mdt_panel:mdt", row=0)
    async def mdt_button(self, interaction, button):
        if not isinstance(interaction.user, discord.Member) or not _can_use_mdt(interaction.user):
            await interaction.response.send_message("❌ هذه اللوحة مخصصة للضباط فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(MDTModal())

    @discord.ui.button(label="Vehicle Impound", style=discord.ButtonStyle.secondary, custom_id="mdt_panel:vehicle", row=0)
    async def vehicle_button(self, interaction, button):
        if not isinstance(interaction.user, discord.Member) or not _can_use_mdt(interaction.user):
            await interaction.response.send_message("❌ هذه اللوحة مخصصة للضباط فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(VehicleImpoundModal())

    @discord.ui.button(label="Suspect Statement", style=discord.ButtonStyle.secondary, custom_id="mdt_panel:statement", row=0)
    async def statement_button(self, interaction, button):
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

    async def callback(self, interaction):
        if not isinstance(interaction.user, discord.Member) or not _can_manage_records(interaction.user):
            await interaction.response.send_message("❌ حذف السوابق للأدمن فقط.", ephemeral=True)
            return
        record_id = int(self.values[0])
        deleted = await db.delete_mdt_record(record_id)
        if deleted and interaction.guild:
            await utils.send_log(interaction.guild, "MDT Record Deleted",
                                 f"المنفذ: {interaction.user.mention}\nرقم السجل: {record_id}")
        await interaction.response.send_message(
            "✅ تم حذف السجل." if deleted else "⚠️ ما تم العثور على السجل.",
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

    async def on_submit(self, interaction):
        if interaction.guild is None:
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        character_id = str(self.character_id).strip()
        records = await db.get_mdt_records(interaction.guild.id, character_id)
        if not records:
            await interaction.followup.send(f"✅ لا يوجد أي سابقة مسجلة على الآيدي `{character_id}`.", ephemeral=True)
            return

        # ====== كل سجل بكونتينر منفصل ======
        view = discord.ui.LayoutView(timeout=180)

        # العنوان الرئيسي
        main_container = discord.ui.Container(accent_color=discord.Color.from_str("#2b2d31"))
        main_container.add_item(discord.ui.TextDisplay(
            f"# <:emoji_5:1550307911115218974>︲Record Check ( {character_id} )"
        ))
        main_container.add_item(discord.ui.Separator())
        view.add_item(main_container)

        for row in records[:10]:  # أول 10 سجلات فقط (ديسكورد حد)
            record_id, record_type, officer_id, summary, created_at = row
            officer = interaction.guild.get_member(officer_id)
            officer_text = officer.mention if officer else f"`{officer_id}`"

            c = discord.ui.Container(accent_color=discord.Color.from_str("#01FFFE"))
            c.add_item(discord.ui.TextDisplay(
                f"<:emoji_13:1550308496216432781>︲{RECORD_TYPE_LABELS.get(record_type, record_type)} #{record_id}"
            ))
            c.add_item(discord.ui.TextDisplay(summary or "—"))
            c.add_item(discord.ui.Separator())
            c.add_item(discord.ui.TextDisplay(
                f"-# **<:emoji_38:1550334422274801664>︲Mention the official : ** {officer_text}\n"
                f"-# <:emoji_10:1550308354759327835>︲Registered For : <t:{created_at}:R> **"
            ))
            view.add_item(c)

        await interaction.followup.send(view=view, ephemeral=True)

        # قائمة الحذف برسالة منفصلة
        await interaction.followup.send(
            "**اختر سجل لحذفه:**",
            view=RecordDeleteView(records),
            ephemeral=True,
        )


class RecordCheckPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Check Record", style=discord.ButtonStyle.secondary, custom_id="mdt_panel:record_check")
    async def check_button(self, interaction, button):
        if not isinstance(interaction.user, discord.Member) or not _can_use_mdt(interaction.user):
            await interaction.response.send_message("❌ هذه اللوحة مخصصة للضباط فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(RecordCheckModal())


class MDT(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mdt-panel", description="نشر لوحة الـ MDT وتحديد قنوات استقبال كل نوع")
    @app_commands.describe(
        mdt_channel="القناة اللي تستقبل تقارير MDT",
        vehicle_channel="القناة اللي تستقبل تقارير حجز المركبات",
        statement_channel="القناة اللي تستقبل أقوال المتهمين",
    )
    @app_commands.default_permissions(administrator=True)
    async def mdt_panel(self, interaction, mdt_channel, vehicle_channel, statement_channel):
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
            "-# **<:emoji_13:1550308496216432781>︲ MDT .**\n"
            "-# <:emoji_28:1550309826758840500> ︲**Mdt / ** تُستعمل للمخالفات بشكل عام ضد الشخص الجاني .\n\n"
            "-# **<:emoji_13:1550308496216432781>︲ Vehicle Impound .**\n"
            "-# <:emoji_28:1550309826758840500> ︲**Vehicle Impound . / ** تُستعمل لحجز المركبات المُخالفة .\n\n"
            "-# **<:emoji_13:1550308496216432781>︲ SusPect Statement .**\n"
            "-# <:emoji_28:1550309826758840500> ︲ **SusPect Statement . / ** تُستعمل لتسجيل اقوال المُتهم .\n\n"
            "-# ** <:emoji_21:1550309215162077214> ︲ مُلاحظات هامة .**\n\n"
            "-# <:emoji_14:1550308740551417956> ︲جميع الازرار تُستعمل في الحالات الجنائية مو بكل الحالات تنزلها ، ب استثناء ال ( **MDT** ) .\n"
            "-# <:emoji_14:1550308740551417956> ︲ في حال نزلت السجل ب الشكل السليم **سيتم اعطائك نقاطها من الخادم بدون المُطالبه فيها .**"
        )

        embed = utils.base_embed(
            "<:emoji_45:1550961724331397231> ︲ MDT RecorDs .",
            description,
            image_url=f"attachment://{config.PANEL_BANNER_ASSET}",
        )

        await utils.send_panel(interaction.channel, embed, MDTPanelView(), config.PANEL_BANNER_ASSET)
        await utils.send_log(
            interaction.guild, "MDT Panel",
            f"المنفذ: {interaction.user.mention}\nالقناة: {interaction.channel.mention}\n"
            f"MDT → {mdt_channel.mention}\nVehicle Impound → {vehicle_channel.mention}\n"
            f"Suspect Statement → {statement_channel.mention}",
        )
        await interaction.delete_original_response()

    @app_commands.command(name="record-check-panel", description="نشر لوحة فحص/حذف السوابق في القناة الحالية")
    @app_commands.default_permissions(administrator=True)
    async def record_check_panel(self, interaction):
        if not isinstance(interaction.user, discord.Member) or not _can_manage_records(interaction.user):
            await interaction.response.send_message("❌ لا تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ اختر قناة نصية.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        description = (
            "**<a:STRP:1550940475819687970> From Here, You Can View And Remove The Person’s Recorded Violations And Criminal Records . **"
        )
        embed = utils.base_embed(
            "<:MTRP:1551676689212248215>︲Record Check",
            description,
            image_url=f"attachment://{config.PANEL_BANNER_ASSET}",
        )
        await utils.send_panel(interaction.channel, embed, RecordCheckPanelView(), config.PANEL_BANNER_ASSET)
        await utils.send_log(
            interaction.guild, "Record Check Panel",
            f"المنفذ: {interaction.user.mention}\nالقناة: {interaction.channel.mention}",
        )
        await interaction.delete_original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(MDT(bot))
