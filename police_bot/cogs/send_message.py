from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import database as db

# اسم الخيار الظاهر في القائمة -> اسم الأمر الأصلي (بدون أي تعديل على الأكواد الأصلية)
PANELS = {
    "login": ("ارسال الـ Login", "login-panel"),
    "system": ("ارسال لوحة السستم", "lspd-panel"),
    "points": ("ارسال لوحة النقاط", "points-panel"),
    "tickets": ("ارسال لوحة التكتات", "ticket-panel"),
    "summon": ("ارسال لوحة الاستدعاءات", "summon-panel"),
    "mdt": ("ارسال لوحة الـ MDT", "mdt-panel"),
    "records": ("ارسال لوحة فحص السوابق", "record-check-panel"),
    "clothing": ("ارسال لوحة الملابس", "clothing-panel"),
    "embed": ("ارسال لوحة الإمبيد", "embed-panel"),
    "submits": ("ارسال لوحة التقديمات", "submits-panel"),
}

# /send-message-2  ←  الإضافة والحذف
ADD_REMOVE = {
    "ticket_add": ("إضافة نوع تكت", "ticket-add"),
    "ticket_remove": ("حذف نوع تكت", "ticket-remove"),
    "clothing_add": ("إضافة لبس", "clothing-add"),
    "clothing_remove": ("حذف لبس", "clothing-remove"),
}

# /send-message-3  ←  help / logs / ticket-category / reset وغيرها
SETTINGS = {
    "help": ("عرض الأوامر ( help )", "help"),
    "logs": ("تحديد اللوقات ( logs )", "logs"),
    "ticket_category": ("تحديد كاتقوري التكتات ( ticket-category )", "ticket-category"),
    "submits_channel": ("تحديد روم استقبال التقديمات", "set-submits-channel"),
    "refresh_panels": ("تحديث اللوحات", "refresh-panels"),
    "duty_status": ("تحديث حالة المباشرة", "حالة_المباشرة"),
    "reset": ("إعادة تعيين النظام ( reset )", "reset-police-system"),
}


async def _run(bot: commands.Bot, interaction: discord.Interaction, command_name: str, **kwargs):
    command = bot.tree.get_command(command_name)
    if command is None or getattr(command, "binding", None) is None:
        await interaction.response.send_message("⚠️ هذا الخيار غير متوفر حالياً في البوت.", ephemeral=True)
        return
    await command.callback(command.binding, interaction, **kwargs)


async def _need(interaction: discord.Interaction, text: str) -> None:
    await interaction.response.send_message(f"⚠️ {text}", ephemeral=True)


class SendMessage(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------------------------------
    # /send-message-1  ←  اللوحات الأساسية
    # ------------------------------------------------------------------
    @app_commands.command(name="send-message-1", description="1 - إرسال الأنظمة الأساسية")
    @app_commands.rename(panel="send-sys")
    @app_commands.describe(
        panel="اختر النظام اللي تبي ترسله",
        review_channel="( التقديمات ) روم استقبال التقديمات — اختياري",
        mdt_channel="( MDT ) روم استقبال تقارير MDT",
        vehicle_channel="( MDT ) روم استقبال حجز المركبات",
        statement_channel="( MDT ) روم استقبال أقوال المتهمين",
    )
    @app_commands.choices(panel=[app_commands.Choice(name=label, value=key) for key, (label, _) in PANELS.items()])
    @app_commands.default_permissions(administrator=True)
    async def send_message_1(
        self,
        interaction: discord.Interaction,
        panel: app_commands.Choice[str],
        review_channel: discord.TextChannel | None = None,
        mdt_channel: discord.TextChannel | None = None,
        vehicle_channel: discord.TextChannel | None = None,
        statement_channel: discord.TextChannel | None = None,
    ):
        command_name = PANELS[panel.value][1]

        if panel.value == "submits":
            await _run(self.bot, interaction, command_name, review_channel=review_channel)
            return

        if panel.value == "mdt":
            if interaction.guild is None:
                return await _need(interaction, "هذا الأمر يعمل داخل السيرفر فقط.")
            saved = {}
            for key, chosen in (("mdt", mdt_channel), ("vehicle_impound", vehicle_channel), ("suspect_statement", statement_channel)):
                if chosen is not None:
                    saved[key] = chosen
                    continue
                raw = await db.get_setting(f"mdt_{key}_channel_id:{interaction.guild.id}")
                found = interaction.guild.get_channel(int(raw)) if raw and raw.isdigit() else None
                if isinstance(found, discord.TextChannel):
                    saved[key] = found
            if len(saved) < 3:
                return await _need(interaction, "حدد روم MDT وروم حجز المركبات وروم أقوال المتهمين (أول مرة فقط).")
            await _run(
                self.bot, interaction, command_name,
                mdt_channel=saved["mdt"],
                vehicle_channel=saved["vehicle_impound"],
                statement_channel=saved["suspect_statement"],
            )
            return

        await _run(self.bot, interaction, command_name)

    # ------------------------------------------------------------------
    # /send-message-2  ←  الإضافة والحذف
    # ------------------------------------------------------------------
    @app_commands.command(name="send-message-2", description="2 - الإضافة والحذف ( تكتات / ملابس )")
    @app_commands.describe(
        action="اختر العملية",
        name="اسم التكت / اسم اللبس",
        role="( إضافة تكت ) رتبة فريق الدعم",
        emoji="( إضافة تكت / لبس ) الإيموجي — اختياري",
        start_number="( إضافة تكت ) رقم بداية التكت — اختياري",
        description="( إضافة لبس ) الوصف",
        image="( إضافة لبس ) صورة — اختياري",
    )
    @app_commands.choices(action=[app_commands.Choice(name=label, value=key) for key, (label, _) in ADD_REMOVE.items()])
    @app_commands.default_permissions(administrator=True)
    async def send_message_2(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        name: str | None = None,
        role: discord.Role | None = None,
        emoji: str | None = None,
        start_number: int | None = None,
        description: str | None = None,
        image: discord.Attachment | None = None,
    ):
        key = action.value
        command_name = ADD_REMOVE[key][1]

        if key == "ticket_add":
            if not name or role is None:
                return await _need(interaction, "حط اسم التكت ( name ) ورتبة الدعم ( role ).")
            return await _run(
                self.bot, interaction, command_name,
                label=name, role=role, emoji=emoji or "🎫", start_number=start_number or 0,
            )
        if key == "ticket_remove":
            if not name:
                return await _need(interaction, "حط اسم التكت ( name ).")
            return await _run(self.bot, interaction, command_name, label=name)
        if key == "clothing_add":
            if not name or not description:
                return await _need(interaction, "حط اسم اللبس ( name ) ووصفه ( description ).")
            return await _run(
                self.bot, interaction, command_name,
                name=name, description=description, image=image, emoji=emoji or "👮",
            )
        if key == "clothing_remove":
            if not name:
                return await _need(interaction, "حط اسم اللبس ( name ).")
            return await _run(self.bot, interaction, command_name, name=name)

    # ------------------------------------------------------------------
    # /send-message-3  ←  help / logs / ticket-category / reset
    # ------------------------------------------------------------------
    @app_commands.command(name="send-message-3", description="3 - help / logs / ticket-category / reset")
    @app_commands.describe(
        action="اختر العملية",
        category="( كاتقوري التكتات ) الكاتقوري المطلوب",
        channel="( روم التقديمات ) الروم المطلوب",
    )
    @app_commands.choices(action=[app_commands.Choice(name=label, value=key) for key, (label, _) in SETTINGS.items()])
    @app_commands.default_permissions(administrator=True)
    async def send_message_3(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        category: discord.CategoryChannel | None = None,
        channel: discord.TextChannel | None = None,
    ):
        key = action.value
        command_name = SETTINGS[key][1]

        if key == "ticket_category":
            if category is None:
                return await _need(interaction, "حدد الكاتقوري ( category ).")
            return await _run(self.bot, interaction, command_name, category=category)
        if key == "submits_channel":
            if channel is None:
                return await _need(interaction, "حدد الروم ( channel ).")
            return await _run(self.bot, interaction, command_name, channel=channel)

        await _run(self.bot, interaction, command_name)


async def setup(bot: commands.Bot):
    await bot.add_cog(SendMessage(bot))
