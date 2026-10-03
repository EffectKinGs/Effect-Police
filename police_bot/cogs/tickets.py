import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
import utils


_ticket_lock = asyncio.Lock()


async def next_ticket_number(type_label: str) -> int:
    """رقم التكت التالي لنوع معيّن؛ كل نوع له عداد مستقل يبدأ من رقمه ويزيد مع كل تكت."""
    async with _ticket_lock:
        last = await db.get_setting(f"ticket_last:{type_label}")
        if last and last.lstrip("-").isdigit():
            number = int(last) + 1
        else:
            start = await db.get_setting(f"ticket_start:{type_label}")
            if start and start.isdigit() and int(start) > 0:
                number = int(start)
            else:
                types = await db.list_ticket_types()
                labels = [row[1] for row in types]
                index = labels.index(type_label) if type_label in labels else len(labels)
                starts = config.TICKET_START_NUMBERS
                number = starts[index] if index < len(starts) else config.TICKET_DEFAULT_START
        await db.set_setting(f"ticket_last:{type_label}", str(number))
        return number


async def _ticket_category(interaction: discord.Interaction):
    raw = await db.get_setting(f"ticket_category_id:{interaction.guild.id}")
    if raw and raw.isdigit():
        category = interaction.guild.get_channel(int(raw))
        if isinstance(category, discord.CategoryChannel):
            return category
    return interaction.channel.category


async def create_ticket_channel(
    interaction: discord.Interaction,
    type_label: str,
    role_id: int,
):
    guild = interaction.guild
    support_role = guild.get_role(role_id)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=False
        ),
        interaction.user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
        ),
    }

    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
        )

    ticket_number = await next_ticket_number(type_label)

    channel = await guild.create_text_channel(
        name=f"ticket-{ticket_number}",
        overwrites=overwrites,
        category=await _ticket_category(interaction),
    )

    await db.create_ticket(
        channel.id,
        interaction.user.id,
        type_label,
    )

    await db.set_setting(
        f"ticket_support_role:{channel.id}",
        str(role_id or 0),
    )

    await utils.send_log(
        guild, "tickets", "Ticket Created", interaction.user, "Open Ticket ( Button )",
        f"النوع : {type_label} | القناة : {channel.mention}",
    )

    embed = utils.base_embed(
        f"",
        "-# ** <:1OL_1ruless:1556050594471612517> - قم بشرح مُشكلتك وانتظر المسوؤلِ يتجاوبو معك . **"
        "",
        image_url="",
    )

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
    value = await db.get_setting(
        f"ticket_support_role:{channel_id}"
    )
    return int(value or 0)


class TicketActionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.success,
        custom_id="ticket:claim",
        emoji="<:emoji_14:1555506715946909869>",
    )
    async def claim_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if (
            not isinstance(interaction.user, discord.Member)
            or interaction.guild is None
        ):
            await interaction.response.send_message(
                "❌ هذا الزر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        owner_id = await _ticket_owner(interaction.channel.id)
        if owner_id == interaction.user.id:
            await interaction.response.send_message(
                "-# **<:emoji_28:1555508053988876309> - انت مستلم التذكرة بالفعل !**",
                ephemeral=True,
            )
            return

        support_role_id = await _support_role_id(
            interaction.channel.id
        )
        is_support = any(
            role.id == support_role_id
            for role in interaction.user.roles
        )

        if not utils.is_system_admin(interaction.user) and not is_support:
            await interaction.response.send_message(
                "-# **<a:amazen:1555520318003609612> -  لاتوجد لديك صلاحية **",
                ephemeral=True,
            )
            return

        current = await db.get_setting(
            f"ticket_assigned:{interaction.channel.id}"
        )
        if current:
            await interaction.response.send_message(
                f"-# **<a:MTRP:1550940537492865124> - التذكرة مُستلمة بالفعل من <@{current}>.**",
                ephemeral=True,
            )
            return

        await db.set_setting(
            f"ticket_assigned:{interaction.channel.id}",
            str(interaction.user.id),
        )

        await utils.send_log(
            interaction.guild, "tickets", "Ticket Claimed", interaction.user, "Claim Ticket ( Button )",
            f"القناة : {interaction.channel.mention}",
        )

        await interaction.response.send_message(
            f"-# **<a:STRP:1550940475819687970> - تم استلام التذكرة بواسطة {interaction.user.mention}. **"
        )

    @discord.ui.button(
        label="Abandon Ticket",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket:unclaim",
        emoji="<:emoji_12:1550308402520133632>",
    )
    async def unclaim_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if (
            not isinstance(interaction.user, discord.Member)
            or interaction.guild is None
        ):
            await interaction.response.send_message(
                "❌ هذا الزر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        current = await db.get_setting(
            f"ticket_assigned:{interaction.channel.id}"
        )
        if not current:
            await interaction.response.send_message(
                "-# **<a:MTRP:1555504111011504138> - التذكرة غير مُستلمه **",
                ephemeral=True,
            )
            return

        if int(current) != interaction.user.id and not utils.is_system_admin(interaction.user):
            await interaction.response.send_message(
                f"-# **<a:MTRP:1550940537492865124> - التذكرة مُستلمة بالفعل من <@{current}>.**",
                ephemeral=True,
            )
            return

        await db.set_setting(
            f"ticket_assigned:{interaction.channel.id}",
            "",
        )

        await utils.send_log(
            interaction.guild, "tickets", "Ticket Released", interaction.user, "Release Ticket ( Button )",
            f"القناة : {interaction.channel.mention}",
        )

        await interaction.response.send_message(
            f"-# **<:emoji_13:1550308496216432781> - تم التخلي من  التذكرة بواسطة {interaction.user.mention} **"
        )

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.danger,
        custom_id="ticket:close",
        emoji="<:emoji_21:1550309452085731498>",
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if (
            not isinstance(interaction.user, discord.Member)
            or interaction.guild is None
        ):
            await interaction.response.send_message(
                "❌ هذا الزر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        owner_id = await _ticket_owner(interaction.channel.id)
        if owner_id == interaction.user.id:
            await interaction.response.send_message(
                "-# **<a:amazen:1555520318003609612> -  لاتوجد لديك صلاحية **",
                ephemeral=True,
            )
            return

        assigned = await db.get_setting(
            f"ticket_assigned:{interaction.channel.id}"
        )
        is_assigned = assigned and int(assigned) == interaction.user.id
        if not utils.is_system_admin(interaction.user) and not is_assigned:
            await interaction.response.send_message(
                "-# **<a:amazen:1555520318003609612> -  لاتوجد لديك صلاحية **",
                ephemeral=True,
            )
            return

        await db.close_ticket(interaction.channel.id)
        await utils.send_log(
            interaction.guild, "tickets", "Ticket Closed", interaction.user, "Close Ticket ( Button )",
            f"القناة : {interaction.channel.mention}",
        )

        close_embed = utils.base_embed(
            "Ticket Closed",
            "-# **<:emoji_28:1550309826758840500> - سيتم اغلاق التذكرة بعد 5 ثوانِ . **",
            image_url="",
        )

        await interaction.response.send_message(
            view=utils.components_v2_view(close_embed)
        )

        await asyncio.sleep(5)

        try:
            await interaction.channel.delete(
                reason=f"Ticket closed by {interaction.user}"
            )
        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            pass


class TicketSelect(discord.ui.Select):
    def __init__(self, ticket_types):
        options = [
            discord.SelectOption(
                label=label,
                value=label,
                emoji=emoji,
            )
            for _id, label, emoji, _role_id in ticket_types
        ]
        super().__init__(
            placeholder="اختر نوع التذكرة...",
            options=options,
            custom_id="ticket_panel:select",
        )
        self.ticket_types = {
            label: role_id
            for _id, label, _emoji, role_id in ticket_types
        }

    async def callback(self, interaction: discord.Interaction):
        type_label = self.values[0]
        role_id = self.ticket_types.get(type_label)
        await interaction.response.defer(ephemeral=True)
        channel = await create_ticket_channel(
            interaction,
            type_label,
            role_id,
        )
        await interaction.followup.send(
            f" تم إنشاء تذكرتك: {channel.mention}",
            ephemeral=True,
        )


class TicketPanelView(discord.ui.View):
    def __init__(self, ticket_types):
        super().__init__(timeout=None)
        if ticket_types:
            self.add_item(TicketSelect(ticket_types))


class UpgradePanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="طلب ترقية",
        style=discord.ButtonStyle.secondary,
        custom_id="upgrade_panel:request",
        emoji="📈",
    )
    async def request_upgrade(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.defer(ephemeral=True)
        channel = await create_ticket_channel(
            interaction,
            "طلب ترقية",
            config.ROLE_IDS["admin"],
        )
        await interaction.followup.send(
            f"✅ تم إنشاء طلب الترقية: {channel.mention}",
            ephemeral=True,
        )


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ticket-add",
        description="إضافة نوع تذكرة جديد",
    )
    @app_commands.default_permissions(administrator=True)
    async def ticket_add(
        self,
        interaction: discord.Interaction,
        label: str,
        role: discord.Role,
        emoji: str = "🎫",
        start_number: int = 0,
    ):
        if (
            not isinstance(interaction.user, discord.Member)
            or not utils.is_system_admin(interaction.user)
        ):
            await interaction.response.send_message(
                "❌ ما تملك صلاحية استخدام هذا الأمر.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        await db.add_ticket_type(label, emoji, role.id)
        if start_number > 0:
            await db.set_setting(f"ticket_start:{label}", str(start_number))
            await db.set_setting(f"ticket_last:{label}", "")
        await interaction.followup.send(
            f"✅ تمت إضافة نوع تذكرة: {emoji} {label} "
            f"(فريق الدعم: {role.mention})"
            + (f" — يبدأ من Ticket {start_number}" if start_number > 0 else ""),
            ephemeral=True,
        )

    @app_commands.command(
        name="ticket-remove",
        description="حذف نوع تذكرة من اللوحة",
    )
    @app_commands.default_permissions(administrator=True)
    async def ticket_remove(
        self,
        interaction: discord.Interaction,
        label: str,
    ):
        if (
            not isinstance(interaction.user, discord.Member)
            or not utils.is_system_admin(interaction.user)
        ):
            await interaction.response.send_message(
                "❌ ما تملك صلاحية استخدام هذا الأمر.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        deleted = await db.delete_ticket_type(label)
        message = (
            "✅ تم الحذف."
            if deleted
            else f"⚠️ ما فيه نوع تذكرة باسم `{label}`."
        )
        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(
        name="ticket-category",
        description="تحديد الكاتقوري اللي تنفتح فيه التكتات",
    )
    @app_commands.default_permissions(administrator=True)
    async def ticket_category(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel,
    ):
        if (
            not isinstance(interaction.user, discord.Member)
            or interaction.guild is None
            or not utils.is_system_admin(interaction.user)
        ):
            await interaction.response.send_message(
                "❌ ما تملك صلاحية استخدام هذا الأمر.",
                ephemeral=True,
            )
            return

        await db.set_setting(f"ticket_category_id:{interaction.guild.id}", str(category.id))
        await interaction.response.send_message(
            f"✅ التكتات الجديدة بتنفتح داخل **{category.name}**.",
            ephemeral=True,
        )

    @app_commands.command(
        name="ticket-panel",
        description="إرسال لوحة التذاكر في القناة الحالية",
    )
    @app_commands.default_permissions(administrator=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        if (
            not isinstance(interaction.user, discord.Member)
            or not utils.is_system_admin(interaction.user)
        ):
            await interaction.response.send_message(
                "❌ ما تملك صلاحية استخدام هذا الأمر.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        ticket_types = await db.list_ticket_types()
        if not ticket_types:
            await interaction.followup.send(
                "⚠️ أضف نوع تذكرة أولاً.",
                ephemeral=True,
            )
            return

        embed = utils.base_embed(
            "<a:emoji_29:1550940499995660338> ︲ Police Support .",
            "-# ** <:emoji_27:1550309790163664906>  '  "
            "Select The Type Of Ticket You Want To Open .**",
            image_url=f"attachment://{config.TICKET_BANNER_ASSET}",
        )

        await utils.send_panel(
            interaction.channel,
            embed,
            TicketPanelView(ticket_types),
            config.TICKET_BANNER_ASSET,
        )
        await db.set_setting(
            "tickets_channel_id",
            str(interaction.channel.id),
        )
        await interaction.delete_original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
