from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
import utils


async def _check_point_embed(member: discord.Member) -> discord.Embed:
    points, hours = await db.get_points_hours(member.id)
    session_total = await db.total_duration_seconds(member.id, member.guild.id)
    total = session_total + int(hours * 3600)
    lines = [
        f"-# ** <:emoji_36:1550311975643254955>︲OFficer : {member.mention}**",
        f"-# ** <:emoji_12:1550308402520133632>︲Your PoinTs : ( {points} )**",
        f"-# ** <:emoji_10:1550308354759327835>︲Your Field Commencement Time : ( {utils.format_duration(total)} )**",
    ]
    return utils.base_embed(
        "# <:emoji_5:1550307911115218974>︲PoinTs RepoRt .",
        "\n".join(lines),
        panel_key="points",
    )


async def _top10_view(guild: discord.Guild) -> discord.ui.LayoutView:
    rows = await db.top_points_hours(10)

    items: list[discord.ui.Item] = [
        discord.ui.TextDisplay("# <:emoji_17:1550308884852383805> ︲ToP10 ."),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
    ]

    if not rows:
        items.append(discord.ui.TextDisplay("**لا توجد بيانات مسجلة حتى الآن.**"))
    else:
        for index, (user_id, points, hours) in enumerate(rows, start=1):
            member = guild.get_member(user_id)
            mention = member.mention if member else f"<@{user_id}>"
            session_total = await db.total_duration_seconds(user_id, guild.id)
            total_seconds = session_total + int(hours * 3600)
            block = "\n".join(
                [
                    f"-# **{index} - <:emoji_38:1550334422274801664>︲Mention The Officer : {mention}**",
                    f"-# <:emoji_36:1550311975643254955>︲Officer Points : **{points}**",
                    f"-# <:emoji_10:1550308354759327835>︲Officer Working Hours : **{utils.format_duration(total_seconds)}**",
                ]
            )
            items.append(discord.ui.TextDisplay(block))
            if index < len(rows):
                items.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))

    container = discord.ui.Container(*items)
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


class PointsPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="𝗖𝗵𝗲𝗰𝗸 𝗣𝗼𝗶𝗻𝘁", style=discord.ButtonStyle.secondary, custom_id="points_panel:check", row=0)
    async def check_point(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return
        await interaction.response.send_message(embed=await _check_point_embed(interaction.user), ephemeral=True)

    @discord.ui.button(label="𝗧𝗢𝗣 𝟭𝟬", style=discord.ButtonStyle.secondary, custom_id="points_panel:top10", row=0)
    async def top10(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await interaction.response.send_message("هذه اللوحة تعمل داخل السيرفر فقط.", ephemeral=True)
            return
        view = await _top10_view(interaction.guild)
        await interaction.response.send_message(view=view, ephemeral=True)


class PointsHours(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="add-point", aliases=["add-Point"])
    async def add_point_text(self, ctx: commands.Context, member: discord.Member, amount: int):
        if not isinstance(ctx.guild, discord.Guild) or not isinstance(ctx.author, discord.Member) or not utils.has_any_role(ctx.author, config.POINTS_MANAGE_ROLE_IDS):
            return await ctx.send("-# **<:ETRP_68:1500142625712242818> لاتمتلك الصلاحية ل اضافة النقاط **", delete_after=8)
        amount = abs(amount)
        await db.add_points(member.id, amount)
        await utils.send_log(ctx.guild, "Add Point", f"Officer: {member.mention}\nPoint: {amount}\nResponsible Officer: {ctx.author.mention}")
        lines = [
            f"-# **<:emoji_12:1550308402520133632>︲OFficer :  {member.mention}**",
            f"-# **<:emoji_24:1550309675155591249>︲Added Points :  ( {amount} )**",
            f"-# **<:emoji_25:1550309714330390538>︲Points Addition Officer :  {ctx.author.mention} **",
        ]
        await ctx.send(
            embed=utils.base_embed(
                "**<:emoji_187:1551676553413394552>︲Add PoinT .**",
                "\n".join(lines),
            )
        )

    @commands.command(name="remove-point", aliases=["remove-Point"])
    async def remove_point_text(self, ctx: commands.Context, member: discord.Member, amount: int):
        if not isinstance(ctx.guild, discord.Guild) or not isinstance(ctx.author, discord.Member) or not utils.has_any_role(ctx.author, config.POINTS_MANAGE_ROLE_IDS):
            return await ctx.send("-# **<:ETRP_68:1500142625712242818> لاتمتلك الصلاحية ل ازالة النقاط **", delete_after=8)
        amount = abs(amount)
        await db.add_points(member.id, -amount)
        await utils.send_log(ctx.guild, "Remove Point", f"Officer: {member.mention}\nPoint: {amount}\nResponsible Officer: {ctx.author.mention}")
        lines = [
            f"-# **<:emoji_12:1550308402520133632>︲OFficer :  {member.mention}**",
            f"-# **<:emoji_24:1550309675155591249>︲Removed Points :  ( {amount} )**",
            f"-# **<:emoji_25:1550309714330390538>︲Points Removal Officer :  {ctx.author.mention} **",
        ]
        await ctx.send(
            embed=utils.base_embed(
                "**<:MTRP:1551676689212248215>︲REmove PoinTs .**",
                "\n".join(lines),
            )
        )

    @commands.command(name="add-hours", aliases=["add-Hours"])
    async def add_hours_text(self, ctx: commands.Context, member: discord.Member, hours: float):
        if not isinstance(ctx.guild, discord.Guild) or not isinstance(ctx.author, discord.Member) or not utils.has_any_role(ctx.author, config.POINTS_MANAGE_ROLE_IDS):
            return await ctx.send("-# **<:ETRP_68:1500142625712242818> لاتمتلك الصلاحية ل اضافة ساعات العمل **", delete_after=8)
        hours = abs(hours)
        await db.add_hours(member.id, hours)
        await utils.send_log(ctx.guild, "Add Hours", f"Officer: {member.mention}\nHours: {hours}\nResponsible Officer: {ctx.author.mention}")
        lines = [
            f"-# **<:emoji_12:1550308402520133632>︲OFficer :  {member.mention}**",
            f"-# **<:emoji_24:1550309675155591249>︲Added Hours :  ( {utils.format_duration(hours * 3600)} )**",
            f"-# **<:emoji_25:1550309714330390538>︲Hours Addition Officer :  {ctx.author.mention}**",
        ]
        await ctx.send(
            embed=utils.base_embed(
                "**<:emoji_187:1551676553413394552>︲Add HouRs .**",
                "\n".join(lines),
            )
        )

    @commands.command(name="remove-hours", aliases=["remove-Hours"])
    async def remove_hours_text(self, ctx: commands.Context, member: discord.Member, hours: float):
        if not isinstance(ctx.guild, discord.Guild) or not isinstance(ctx.author, discord.Member) or not utils.has_any_role(ctx.author, config.POINTS_MANAGE_ROLE_IDS):
            return await ctx.send("-# **<:ETRP_68:1500142625712242818> لاتمتلك الصلاحية ل ازالة ساعات العمل **", delete_after=8)
        hours = abs(hours)
        await db.add_hours(member.id, -hours)
        await utils.send_log(ctx.guild, "Remove Hours", f"Officer: {member.mention}\nHours: {hours}\nResponsible Officer: {ctx.author.mention}")
        lines = [
            f"-# **<:emoji_12:1550308402520133632>︲OFficer :  {member.mention}**",
            f"-# **<:emoji_24:1550309675155591249>︲Removed Hours :  ( {utils.format_duration(hours * 3600)} )**",
            f"-# **<:emoji_25:1550309714330390538>︲Hours Removal Officer :  {ctx.author.mention} **",
        ]
        await ctx.send(
            embed=utils.base_embed(
                "**<:MTRP:1551676689212248215>︲REmove HouRs .**",
                "\n".join(lines),
            )
        )

    @commands.command(name="Show-all", aliases=["show-all", "ShowAll"])
    async def show_all(self, ctx: commands.Context):
        if not isinstance(ctx.guild, discord.Guild) or not isinstance(ctx.author, discord.Member) or not utils.has_any_role(ctx.author, config.SHOW_ALL_ROLE_IDS):
            return
        rows = await db.top_points_hours(1000)
        if not rows:
            description = "**لا توجد بيانات مسجلة حتى الآن.**"
        else:
            blocks = []
            for index, (user_id, points, hours) in enumerate(rows, start=1):
                member = ctx.guild.get_member(user_id)
                mention = member.mention if member else f"<@{user_id}>"
                total = await db.total_duration_seconds(user_id, ctx.guild.id) + int(hours * 3600)
                block = "\n".join(
                    [
                        f"-# **{index} - <:emoji_38:1550334422274801664>︲Mention The Officer : {mention}**",
                        f"-# <:emoji_36:1550311975643254955>︲Officer Points : **{points}**",
                        f"-# <:emoji_10:1550308354759327835>︲Officer Working Hours : **{utils.format_duration(total)}**",
                    ]
                )
                blocks.append(block)
            description = "\n\n".join(blocks)
        embed = utils.base_embed(
            "<:emoji_46:1550990951525122158> ︲ List All The PoinTs .",
            description,
            image_url="",
            panel_key="points",
        )
        await ctx.send(view=utils.components_v2_view(embed))

    @app_commands.command(name="points-panel", description="نشر لوحة نقاط العسكريين")
    @app_commands.default_permissions(administrator=True)
    async def points_panel(self, interaction: discord.Interaction):
        if not utils.has_any_role(interaction.user, config.POINTS_MANAGE_ROLE_IDS) or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ ما تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        description = "**<:alert:1551325711699026021> - From Here, You Can View Your Military Points And Check The TOP 10 Military Personnel .**"
        embed = utils.base_embed(
            "<:emoji_14:1550308636214169610> ︲Officer PoinTs .",
            description,
            image_url=f"attachment://{config.PANEL_BANNER_ASSET}",
            panel_key="points",
        )
        await utils.send_panel(interaction.channel, embed, PointsPanelView(), config.PANEL_BANNER_ASSET)
        await interaction.delete_original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(PointsHours(bot))
