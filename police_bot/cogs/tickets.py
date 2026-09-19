"""
نظام التذاكر (Tickets)
========================
/ticket-add     - إضافة نوع تذكرة جديد (اسم + إيموجي + رتبة الدعم)
/ticket-remove  - حذف نوع تذكرة من اللوحة
/ticket-panel   - إرسال/تحديث لوحة التذاكر (قائمة اختيار بكل الأنواع)

عند اختيار المستخدم لنوع تذكرة، يُنشأ له روم خاص يشوفه هو + رتبة الدعم فقط.
"""

import discord

import config
from discord import app_commands
from discord.ext import commands

import database as db
import utils


async def create_ticket_channel(interaction: discord.Interaction, type_label: str, role_id: int):
    guild = interaction.guild
    support_role = guild.get_role(role_id)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

    safe_name = "".join(c for c in interaction.user.display_name if c.isalnum()) or "ticket"
    channel = await guild.create_text_channel(
        name=f"ticket-{safe_name}",
        overwrites=overwrites,
        category=interaction.channel.category,
    )
    await db.create_ticket(channel.id, interaction.user.id, type_label)
    await utils.send_log(guild, "Ticket Created", f"المنفذ: {interaction.user.mention}\nالنوع: {type_label}\nالقناة: {channel.mention}")

    embed = utils.base_embed(f"🎫 تذكرة جديدة: {type_label}")
    embed.add_field(name="مقدّم الطلب", value=interaction.user.mention, inline=True)
    if support_role:
        embed.add_field(name="فريق الدعم", value=support_role.mention, inline=True)
    embed.description = "اشرح طلبك بالتفصيل، وسيتم الرد عليك قريباً. استخدم زر الإغلاق أدناه عند الانتهاء."

    await channel.send(
        content=f"{interaction.user.mention} {support_role.mention if support_role else ''}",
        embed=embed,
        view=CloseTicketView(),
    )
    return channel


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التذكرة", style=discord.ButtonStyle.secondary,
                        custom_id="ticket:close", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await db.close_ticket(interaction.channel.id)
        if interaction.guild:
            await utils.send_log(interaction.guild, "Ticket Closed", f"المنفذ: {interaction.user.mention}\nالقناة: {interaction.channel.mention}")
        await interaction.response.send_message("🔒 راح يتم إغلاق التذكرة خلال 5 ثواني...")
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete()


class TicketSelect(discord.ui.Select):
    def __init__(self, ticket_types):
        options = [
            discord.SelectOption(label=label, value=label, emoji=emoji)
            for _id, label, emoji, _role_id in ticket_types
        ]
        super().__init__(placeholder="اختر نوع التذكرة...", options=options, custom_id="ticket_panel:select")
        self.ticket_types = {label: role_id for _id, label, _emoji, role_id in ticket_types}

    async def callback(self, interaction: discord.Interaction):
        type_label = self.values[0]
        role_id = self.ticket_types.get(type_label)
        await interaction.response.defer(ephemeral=True)
        channel = await create_ticket_channel(interaction, type_label, role_id)
        await interaction.followup.send(f"✅ تم إنشاء تذكرتك: {channel.mention}", ephemeral=True)


class TicketPanelView(discord.ui.View):
    def __init__(self, ticket_types):
        super().__init__(timeout=None)
        if ticket_types:
            self.add_item(TicketSelect(ticket_types))


class UpgradePanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="طلب ترقية", style=discord.ButtonStyle.secondary,
                        custom_id="upgrade_panel:request", emoji="📈")
    async def request_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        import config as _config
        role_id = _config.ROLE_IDS.get("admin")
        await interaction.response.defer(ephemeral=True)
        channel = await create_ticket_channel(interaction, "طلب ترقية", role_id)
        await interaction.followup.send(f"✅ تم إنشاء طلب الترقية: {channel.mention}", ephemeral=True)


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ticket-add", description="إضافة نوع تذكرة جديد")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(label="اسم نوع التذكرة", role="رتبة فريق الدعم المسؤول عنها", emoji="إيموجي (اختياري)")
    async def ticket_add(self, interaction: discord.Interaction, label: str, role: discord.Role, emoji: str = "🎫"):
        if not utils.has_role(interaction.user, "admin"):
            await interaction.response.send_message("❌ ما تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await db.add_ticket_type(label, emoji, role.id)
        await interaction.followup.send(f"✅ تمت إضافة نوع تذكرة: {emoji} {label} (فريق الدعم: {role.mention})", ephemeral=True)

    @app_commands.command(name="ticket-remove", description="حذف نوع تذكرة من اللوحة")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(label="اسم نوع التذكرة المراد حذفه")
    async def ticket_remove(self, interaction: discord.Interaction, label: str):
        if not utils.has_role(interaction.user, "admin"):
            await interaction.response.send_message("❌ ما تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        deleted = await db.delete_ticket_type(label)
        if not deleted:
            await interaction.followup.send(f"⚠️ ما فيه نوع تذكرة باسم `{label}`.", ephemeral=True)
            return
        await interaction.followup.send(f"🗑️ تم حذف نوع التذكرة `{label}`.", ephemeral=True)

    @app_commands.command(name="ticket-panel", description="إرسال/تحديث لوحة التذاكر في القناة الحالية")
    @app_commands.default_permissions(administrator=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        if not utils.has_role(interaction.user, "admin"):
            await interaction.response.send_message("❌ ما تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        ticket_types = await db.list_ticket_types()
        if not ticket_types:
            await interaction.followup.send(
                "⚠️ ما فيه أنواع تذاكر مضافة بعد. استخدم `/ticket-add` أول.", ephemeral=True
            )
            return

        embed = utils.base_embed(
    "<a:MTRP:1394920520134426636> ︲ Police Support .",
    (
        "-# ** <:emoji_27:1550309790163664906>  '  Select The Type Of Ticket You Want To Open .**\n"
        "-# **<:emoji_5:1550307911115218974>  '  Ticket** / عليك الالتزام بالانظمه والقوانين وعدم كثرة المنشن"
    ),
    image_url=f"attachment://{config.PANEL_BANNER_ASSET}",
)
        await utils.send_panel(interaction.channel, embed, TicketPanelView(ticket_types), config.PANEL_BANNER_ASSET)
        await db.set_setting("tickets_channel_id", str(interaction.channel.id))
        await interaction.delete_original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
