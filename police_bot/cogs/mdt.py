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

ACCENT = 0x01FFFE


def _channel_key(record_type: str, guild_id: int) -> str:
    return f"mdt_{record_type}_channel_id:{guild_id}"


async def _get_target_channel(guild: discord.Guild, record_type: str):
    channel_id = await db.get_setting(_channel_key(record_type, guild.id))
    if not channel_id:
        return None
    channel = guild.get_channel(int(channel_id))
    return channel if isinstance(channel, discord.TextChannel) else None


def _build_record_view(*, title: str, fields: list[tuple[str, str]], image_link: str | None) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=None)
    container = discord.ui.Container(accent_color=discord.Color(ACCENT))

    container.add_item(discord.ui.TextDisplay(f"# {title}"))
    container.add_item(discord.ui.Separator())

    body = "\n".join(f"**{label}** {value}" for label, value in fields)
    container.add_item(discord.ui.TextDisplay(body))

    clean_link = (image_link or "").strip()
    if clean_link.startswith(("http://", "https://")):
        container.add_item(discord.ui.Separator())
        gallery = discord.ui.MediaGallery()
        gallery.add_item(media=clean_link)
        container.add_item(gallery)

    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay("-# System Police Effect ."))

    view.add_item(container)
    return view


def _mdt_view(admin_mention, character_id, suspect_name, charge, fine, image_link):
    return _build_record_view(
        title="<:emoji_45:1550961724331397231> ︲ MDT Record",
        fields=[
            ("1 - <:emoji_38:1550334422274801664>︲Mention the official :", admin_mention),
            ("2 - <:emoji_13:1550308496216432781>︲Id Character :", character_id),
            ("3 - <:emoji_9:1550308305014882344>︲Suspect Name :", suspect_name),
            ("4 - <:emoji_14:1550308740551417956>︲Person’s Charge :", charge),
            ("5 - <:emoji_14:1550308636214169610>︲Financial Fine :", fine),
        ],
        image_link=image_link,
    )


def _vehicle_impound_view(admin_mention, character_id, suspect_name, vehicle_type, plate, charge, image_link):
    return _build_record_view(
        title="<:emoji_45:1550961724331397231> ︲ Vehicle Impound",
        fields=[
            ("1 - <:emoji_38:1550334422274801664>︲Mention the official :", admin_mention),
            ("2 - <:emoji_13:1550308496216432781>︲Id Character :", character_id),
            ("3 - <:emoji_9:1550308305014882344>︲Suspect Name :", suspect_name),
            ("4 - <:emoji_131:1551326444565831813>︲Offending Vehicle Type :", vehicle_type),
            ("5 - <:emoji_39:1550337741936394380>︲Vehicle Plate Number :", plate),
            ("6 - <:FaLcoN:1551327269493153887>︲Recorded Charge :", charge),
        ],
        image_link=image_link,
    )


def _suspect_statement_view(admin_mention, character_id, suspect_name, case, justification, image_link):
    return _build_record_view(
        title="<:emoji_45:1550961724331397231> ︲ Suspect Statement",
        fields=[
            ("1 - <:emoji_38:1550334422274801664>︲Mention the official :", admin_mention),
            ("2 - <:emoji_13:1550308496216432781>︲Id Character :", character_id),
            ("3 - <:emoji_9:1550308305014882344>︲Suspect Name :", suspect_name),
            ("4 - <:emoji_7:1550308237119885437>︲Defendant’s Case :", case),
            ("5 - <:emoji_30:1550311848369782905>︲Defendant’s Justifications :", justification),
        ],
        image_link=image_link,
    )


async def _finalize(interaction: discord.Interaction, *, record_type, character_id, summary, view: discord.ui.LayoutView, points):
    channel = await _get_target_channel(interaction.guild, record_type)
    if channel is None:
        await interaction.followup.send(
            f"⚠️ ما تم تحديد قناة استقبال لـ **{RECORD_TYPE_LABELS[record_type]}** بعد.",
            ephemeral=True,
        )
        return

    try:
        await channel.send(view=view)
    except (discord.Forbidden, discord.HTTPException):
        await interaction.followup.send("⚠️ تعذر الإرسال لقناة الاستقبال.", ephemeral=True)
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


class MDTModal(discord.ui.Modal, title="𝗠𝗗𝗧"):
    character_id = discord.ui.TextInput(label="Id Character / رقم هوية الشخص", required=True, max_length=50)
    suspect_name = discord.ui.TextInput(label="Suspect Name / اسم المُتهم", required=True, max_length=100)
    charge = discord.ui.TextInput(label="Person’s Charge / تُهمة الشخص", required=True, max_length=300)
    fine = discord.ui.TextInput(label="Financial Fine / الغرامة المالية", required=True, max_length=100)
    image_link = discord.ui.TextInput(label="Image Link / رابط صورة", required=False, max_length=500)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        view = _mdt_view(
            interaction.user.mention,
            str(self.character_id).strip(),
            str(self.suspect_name).strip(),
            str(self.charge).strip(),
            str(self.fine).strip(),
            str(self.image_link).strip(),
        )
        summary = f"Suspect: {self.suspect_name} | Charge: {self.charge} | Fine: {self.fine}"
        await _finalize(
            interaction, record_type="mdt",
            character_id=str(self.character_id).strip(),
            summary=summary, view=view, points=config.MDT_POINTS,
        )


class VehicleImpoundModal(discord.ui.Modal, title="𝗩𝗲𝗵𝗶𝗰𝗹𝗲 𝗜𝗺𝗽𝗼𝘂𝗻𝗱"):
    character_id = discord.ui.TextInput(label="Id Character / رقم هوية الشخص", required=True, max_length=50)
    suspect_name = discord.ui.TextInput(label="Suspect Name / اسم المُتهم", required=True, max_length=100)
    vehicle_type = discord.ui.TextInput(label="Offending Vehicle Type / نوع المركبة", required=True, max_length=100)
    plate = discord.ui.TextInput(label="Vehicle Plate Number / رقم اللوحة", required=True, max_length=50)
    charge = discord.ui.TextInput(label="Recorded Charge / التُهمة المُسجلة", required=True, max_length=300)
    image_link = discord.ui.TextInput(label="Image Link / رابط صورة", required=False, max_length=500)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        view = _vehicle_impound_view(
            interaction.user.mention,
            str(self.character_id).strip(),
            str(self.suspect_name).strip(),
            str(self.vehicle_type).strip(),
            str(self.plate).strip(),
            str(self.charge).strip(),
            str(self.image_link).strip(),
        )
        summary = f"Suspect: {self.suspect_name} | Vehicle: {self.vehicle_type} | Plate: {self.plate}"
        await _finalize(
            interaction, record_type="vehicle_impound",
            character_id=str(self.character_id).strip(),
            summary=summary, view=view, points=config.VEHICLE_IMPOUND_POINTS,
        )


class SuspectStatementModal(discord.ui.Modal, title="𝗦𝘂𝘀𝗽𝗲𝗰𝘁 𝗦𝘁𝗮𝘁𝗲𝗺𝗲𝗻𝘁"):
    character_id = discord.ui.TextInput(label="Id Character / رقم هوية الشخص", required=True, max_length=50)
    suspect_name = discord.ui.TextInput(label="Suspect Name / اسم المُتهم", required=True, max_length=100)
    case = discord.ui.TextInput(label="Defendant’s Case / قضية المُتهم", required=True, max_length=300)
    justification = discord.ui.TextInput(
        label="Defendant’s Justifications / اقوال المُتهم",
        required=True, max_length=1000, style=discord.TextStyle.paragraph,
    )
    image_link = discord.ui.TextInput(label="Image Link / رابط صورة", required=False, max_length=500)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        view = _suspect_statement_view(
            interaction.user.mention,
            str(self.character_id).strip(),
            str(self.suspect_name).strip(),
            str(self.case).strip(),
            str(self.justification).strip(),
            str(self.image_link).strip(),
        )
        summary = f"Suspect: {self.suspect_name} | Case: {self.case}"
        await _finalize(
            interaction, record_type="suspect_statement",
            character_id=str(self.character_id).strip(),
            summary=summary, view=view, points=config.SUSPECT_STATEMENT_POINTS,
        )


class RecordCheckModal(discord.ui.Modal, title="𝗥𝗲𝗰𝗼𝗿𝗱 𝗖𝗵𝗲𝗰𝗸"):
    character_id = discord.ui.TextInput(label="Id Character / رقم هوية الشخص", required=True, max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        character_id = str(self.character_id).strip()
        records = await db.get_mdt_records(interaction.guild.id, character_id)
        if not records:
            await interaction.followup.send(
                f"✅ لا يوجد أي سابقة مسجلة على الآيدي `{character_id}`.",
                ephemeral=True,
            )
            return

        view = discord.ui.LayoutView(timeout=None)
        container = discord.ui.Container(accent_color=discord.Color(ACCENT))

        container.add_item(discord.ui.TextDisplay(
            f"# <:emoji_5:1550307911115218974>︲Record Check ( {character_id} )"
        ))
        container.add_item(discord.ui.Separator())

        for i, row in enumerate(records[:10]):
            record_id, record_type, officer_id, summary, created_at = row
            officer = interaction.guild.get_member(officer_id)
            officer_text = officer.mention if officer else f"`{officer_id}`"
            type_label = RECORD_TYPE_LABELS.get(record_type, record_type)

            container.add_item(discord.ui.TextDisplay(
                f"**<:emoji_13:1550308496216432781>︲{type_label} #{record_id}**"
            ))

            if summary:
                container.add_item(discord.ui.TextDisplay(summary))

            container.add_item(discord.ui.TextDisplay(
                f"-# **<:emoji_38:1550334422274801664>︲Mention The Official : ** {officer_text}\n"
                f"-# <:emoji_10:1550308354759327835>︲Registered For : <t:{created_at}:R> **"
            ))

            if i < len(records[:10]) - 1:
                container.add_item(discord.ui.Separator())

        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("-# System Police Effect ."))

        view.add_item(container)
        await interaction.followup.send(view=view, ephemeral=True)

        if _can_manage_records(interaction.user):
            await interaction.followup.send(
                "**اختر سجل لحذفه:**",
                view=RecordDeleteView(records),
                ephemeral=True,
            )


def _can_use_mdt(member: discord.Member) -> bool:
    try:
        return utils.has_any_role(member, config.MDT_ALLOWED_ROLE_IDS)
    except Exception:
        return False


def _can_manage_records(member: discord.Member) -> bool:
    try:
        return utils.has_any_role(member, config.SYSTEM_ADMIN_ROLE_IDS)
    except Exception:
        return False


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
                label=f"#{row[0]} - {RECORD_TYPE_LABELS.get(row[1], row[1])}"[:100],
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
            "<:emoji_12:1550308402520133632> ' تم حذف السجل." if deleted else "⚠️ ما تم العثور على السجل.",
            ephemeral=True,
        )


class RecordDeleteView(discord.ui.View):
    def __init__(self, records):
        super().__init__(timeout=180)
        if records:
            self.add_item(RecordDeleteSelect(records))


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
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mdt-panel", description="نشر لوحة الـ MDT وتحديد قنوات استقبال كل نوع")
    @app_commands.describe(
        mdt_channel="القناة اللي تستقبل تقارير MDT",
        vehicle_channel="القناة اللي تستقبل تقارير حجز المركبات",
        statement_channel="القناة اللي تستقبل أقوال المتهمين",
    )
    @app_commands.default_permissions(administrator=True)
    async def mdt_panel(
        self,
        interaction: discord.Interaction,
        mdt_channel: discord.TextChannel,
        vehicle_channel: discord.TextChannel,
        statement_channel: discord.TextChannel,
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
            f"المنفذ: {interaction.user.mention}\nالقناة: {interaction.channel.mention}",
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
