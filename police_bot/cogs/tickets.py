import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import config
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
    channel = await guild.create_text_channel(name=f"ticket-{safe_name}", overwrites=overwrites, category=interaction.channel.category)
    await db.create_ticket(channel.id, interaction.user.id, type_label)
    await db.set_setting(f"ticket_support_role:{channel.id}", str(role_id or 0))
    await utils.send_log(guild, "Ticket Created", f"المنفذ: {interaction.user.mention}\nالنوع: {type_label}\nالقناة: {channel.mention}")
    embed = utils.base_embed(f"🎫 تذكرة جديدة: {type_label}", "اشرح طلبك بالتفصيل، وسيتم الرد عليك من فريق الدعم. صاحب التذكرة لا يستطيع استلامها أو إغلاقها.")
    embed.description = (
    f"{interaction.user.mention} "
    f"{support_role.mention if support_role else ''}\n\n"
    f"{embed.description}"
)
await channel.send(
    view=utils.components_v2_view(
        embed,
        TicketActionsView(),
    ),
    allowed_mentions=discord.AllowedMentions(
        users=True,
        roles=True,
    ),
)

    return channel


async def _ticket_owner(channel_id: int) -> int | None:
    row = await db.get_ticket(channel_id)
    return int(row[0]) if row else None


async def _support_role_id(channel_id: int) -> int:
    value = await db.get_setting(f"ticket_support_role:{channel_id}")
    return int(value or 0)


class TicketActionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="استلام التذكرة", style=discord.ButtonStyle.success, custom_id="ticket:claim", emoji="📌")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or interaction.guild is None:
            await interaction.response.send_message("❌ هذا الزر يعمل داخل السيرفر فقط.", ephemeral=True)
            return
        owner_id = await _ticket_owner(interaction.channel.id)
        if owner_id == interaction.user.id:
            await interaction.response.send_message("❌ لا يمكنك استلام تذكرتك.", ephemeral=True)
            return
        support_role_id = await _support_role_id(interaction.channel.id)
        if not utils.is_system_admin(interaction.user) and not any(role.id == support_role_id for role in interaction.user.roles):
            await interaction.response.send_message("❌ هذا الزر مخصص لفريق الدعم.", ephemeral=True)
            return
        current = await db.get_setting(f"ticket_assigned:{interaction.channel.id}")
        if current:
            await interaction.response.send_message(f"❌ التذكرة مستلمة بالفعل من <@{current}>.", ephemeral=True)
            return
        await db.set_setting(f"ticket_assigned:{interaction.channel.id}", str(interaction.user.id))
        await utils.send_log(interaction.guild, "Ticket Claimed", f"المستلم: {interaction.user.mention}\nالقناة: {interaction.channel.mention}")
        await interaction.response.send_message(f"✅ تم استلام التذكرة بواسطة {interaction.user.mention}.")

    @discord.ui.button(label="إغلاق التذكرة", style=discord.ButtonStyle.danger, custom_id="ticket:close", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or interaction.guild is None:
            await interaction.response.send_message("❌ هذا الزر يعمل داخل السيرفر فقط.", ephemeral=True)
            return
        owner_id = await _ticket_owner(interaction.channel.id)
        if owner_id == interaction.user.id:
            await interaction.response.send_message("❌ لا يمكنك إغلاق تذكرتك.", ephemeral=True)
            return
        assigned = await db.get_setting(f"ticket_assigned:{interaction.channel.id}")
        allowed = utils.is_system_admin(interaction.user) or (assigned and int(assigned) == interaction.user.id)
        if not allowed:
            await interaction.response.send_message("❌ يجب أن تكون مستلم التذكرة أو تملك صلاحية النظام كاملة.", ephemeral=True)
            return
        await db.close_ticket(interaction.channel.id)
        await utils.send_log(interaction.guild, "Ticket Closed", f"المنفذ: {interaction.user.mention}\nالقناة: {interaction.channel.mention}")
        await interaction.response.send_message(view=utils.components_v2_view(utils.base_embed("Ticket Closed", "سيتم إغلاق التذكرة بعد خمس ثواني.")))
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass


class TicketSelect(discord.ui.Select):
    def __init__(self, ticket_types):
        options = [discord.SelectOption(label=label, value=label, emoji=emoji) for _id, label, emoji, _role_id in ticket_types]
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

    @discord.ui.button(label="طلب ترقية", style=discord.ButtonStyle.secondary, custom_id="upgrade_panel:request", emoji="📈")
    async def request_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        channel = await create_ticket_channel(interaction, "طلب ترقية", config.ROLE_IDS["admin"])
        await interaction.followup.send(f"✅ تم إنشاء طلب الترقية: {channel.mention}", ephemeral=True)


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ticket-add", description="إضافة نوع تذكرة جديد")
    @app_commands.default_permissions(administrator=True)
    async def ticket_add(self, interaction: discord.Interaction, label: str, role: discord.Role, emoji: str = "🎫"):
        if not isinstance(interaction.user, discord.Member) or not utils.is_system_admin(interaction.user):
            await interaction.response.send_message("❌ ما تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await db.add_ticket_type(label, emoji, role.id)
        await interaction.followup.send(f"✅ تمت إضافة نوع تذكرة: {emoji} {label} (فريق الدعم: {role.mention})", ephemeral=True)

    @app_commands.command(name="ticket-remove", description="حذف نوع تذكرة من اللوحة")
    @app_commands.default_permissions(administrator=True)
    async def ticket_remove(self, interaction: discord.Interaction, label: str):
        if not isinstance(interaction.user, discord.Member) or not utils.is_system_admin(interaction.user):
            await interaction.response.send_message("❌ ما تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        deleted = await db.delete_ticket_type(label)
        await interaction.followup.send(f"✅ تم الحذف." if deleted else f"⚠️ ما فيه نوع تذكرة باسم `{label}`.", ephemeral=True)

    @app_commands.command(name="ticket-panel", description="إرسال لوحة التذاكر في القناة الحالية")
    @app_commands.default_permissions(administrator=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not utils.is_system_admin(interaction.user):
            await interaction.response.send_message("❌ ما تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        ticket_types = await db.list_ticket_types()
        if not ticket_types:
            await interaction.followup.send("⚠️ أضف نوع تذكرة أولاً.", ephemeral=True)
            return
        embed = utils.base_embed("<a:emoji_29:1550940499995660338> ︲ Police Support .", "-# ** <:emoji_27:1550309790163664906>  '  Select The Type Of Ticket You Want To Open .**", image_url=f"attachment://{config.PANEL_BANNER_ASSET}")
        await utils.send_panel(interaction.channel, embed, TicketPanelView(ticket_types), config.PANEL_BANNER_ASSET)
        await db.set_setting("tickets_channel_id", str(interaction.channel.id))
        await interaction.delete_original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
''
