from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import utils


async def _check_point_embed(member: discord.Member) -> discord.Embed:
    points, hours = await db.get_points_hours(member.id)
    session_total = await db.total_duration_seconds(member.id, member.guild.id)
    total = session_total + int(hours * 3600)
    description = (
        f"** <:emoji_143:1542635684286963732> - Officer : {member.mention}\n"
        f"<:ETRP_28:1499883636110135476> - Your Points : ( {points} )\n"
        f"<:ETRP_75:1500185654015823924> - Your Field Commencement Time : ( {utils.format_duration(total)} )**"
    )
    return utils.base_embed("Points Report", description)


async def _top10_embed(guild: discord.Guild) -> discord.Embed:
    rows = await db.top_points_hours(10)
    lines: list[str] = []
    if not rows:
        lines.append("لا توجد بيانات مسجلة حتى الآن.")
    else:
        for index, (user_id, points, hours) in enumerate(rows, start=1):
            member = guild.get_member(user_id)
            name = member.mention if member else f"<@{user_id}>"
            session_total = await db.total_duration_seconds(user_id, guild.id)
            total_seconds = session_total + int(hours * 3600)
            lines.extend(
                [
                    f"{index} - <:emoji_143:1542635684286963732> - Officer : {name}",
                    f"Point : ( {points} )",
                    f"Hours : ( {utils.format_duration(total_seconds)} )",
                    "",
                ]
            )
    return utils.base_embed("Top 10", "\n".join(lines).strip())


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
        await interaction.response.send_message(embed=await _top10_embed(interaction.guild), ephemeral=True)


class PointsHours(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="add-point", aliases=["add-Point"])
    async def add_point_text(self, ctx: commands.Context, member: discord.Member, amount: int):
        if not isinstance(ctx.guild, discord.Guild) or not isinstance(ctx.author, discord.Member) or not utils.has_role(ctx.author, "admin"):
            return await ctx.send("-# **<:ETRP_68:1500142625712242818> لاتمتلك الصلاحية ل اضافة النقاط **", delete_after=8)
        amount = abs(amount)
        await db.add_points(member.id, amount)
        await utils.send_log(ctx.guild, "Add Point", f"Officer: {member.mention}\nPoint: {amount}\nResponsible Officer: {ctx.author.mention}")
        await ctx.send(
            embed=utils.base_embed(
                "Add Point",
                f"**<:emoji_143:1542635684286963732> - Officer : {member.mention}\n"
                f"<:ETRP_28:1499883636110135476> - Point : ( {amount} )\n"
                f"<:ETRP_145:1542162076255002624> - The Responsible Military Officer : {ctx.author.mention} **",
            )
        )

    @commands.command(name="remove-point", aliases=["remove-Point"])
    async def remove_point_text(self, ctx: commands.Context, member: discord.Member, amount: int):
        if not isinstance(ctx.guild, discord.Guild) or not isinstance(ctx.author, discord.Member) or not utils.has_role(ctx.author, "admin"):
            return await ctx.send("-# **<:ETRP_68:1500142625712242818> لاتمتلك الصلاحية ل ازالة النقاط **", delete_after=8)
        amount = abs(amount)
        await db.add_points(member.id, -amount)
        await utils.send_log(ctx.guild, "Remove Point", f"Officer: {member.mention}\nPoint: {amount}\nResponsible Officer: {ctx.author.mention}")
        await ctx.send(
            embed=utils.base_embed(
                "Remove Point",
                f"**<:emoji_143:1542635684286963732> - Officer : {member.mention}\n"
                f"<:ETRP_28:1499883636110135476> - Point : ( {amount} )\n"
                f"<:ETRP_145:1542162076255002624> - The Responsible Military Officer : {ctx.author.mention} **",
            )
        )

    @commands.command(name="add-hours", aliases=["add-Hours"])
    async def add_hours_text(self, ctx: commands.Context, member: discord.Member, hours: float):
        if not isinstance(ctx.guild, discord.Guild) or not isinstance(ctx.author, discord.Member) or not utils.has_role(ctx.author, "admin"):
            return await ctx.send("-# **<:ETRP_68:1500142625712242818> لاتمتلك الصلاحية ل اضافة ساعات العمل **", delete_after=8)
        hours = abs(hours)
        await db.add_hours(member.id, hours)
        await utils.send_log(ctx.guild, "Add Hours", f"Officer: {member.mention}\nHours: {hours}\nResponsible Officer: {ctx.author.mention}")
        await ctx.send(
            embed=utils.base_embed(
                "Add Hours",
                f"**<:emoji_143:1542635684286963732> - Officer : {member.mention}\n"
                f"<:ETRP_75:1500185654015823924> - Hours : ( {utils.format_duration(hours * 3600)} )\n"
                f"<:ETRP_145:1542162076255002624> - The Responsible Military Officer : {ctx.author.mention}**",
            )
        )

    @commands.command(name="remove-hours", aliases=["remove-Hours"])
    async def remove_hours_text(self, ctx: commands.Context, member: discord.Member, hours: float):
        if not isinstance(ctx.guild, discord.Guild) or not isinstance(ctx.author, discord.Member) or not utils.has_role(ctx.author, "admin"):
            return await ctx.send("-# **<:ETRP_68:1500142625712242818> لاتمتلك الصلاحية ل ازالة ساعات العمل **", delete_after=8)
        hours = abs(hours)
        await db.add_hours(member.id, -hours)
        await utils.send_log(ctx.guild, "Remove Hours", f"Officer: {member.mention}\nHours: {hours}\nResponsible Officer: {ctx.author.mention}")
        await ctx.send(
            embed=utils.base_embed(
                "Remove Hours",
                f"**<:emoji_143:1542635684286963732> - Officer : {member.mention}\n"
                f"<:ETRP_75:1500185654015823924> - Hours : ( {utils.format_duration(hours * 3600)} )\n"
                f"<:ETRP_145:1542162076255002624> - The Responsible Military Officer : {ctx.author.mention} **",
            )
        )

    @app_commands.command(name="points-panel", description="نشر لوحة نقاط العسكريين")
    @app_commands.default_permissions(administrator=True)
    async def points_panel(self, interaction: discord.Interaction):
        if not utils.has_role(interaction.user, "admin") or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ ما تملك صلاحية استخدام هذا الأمر.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        description = "**<:ETRP_97:1500190884442931271> - From Here, You Can View Your Military Points And Check The TOP 10 Military Personnel .**"
        embed = utils.base_embed("Officer Points", description, image_url="attachment://evil_town_banner.png")
        await utils.send_panel(interaction.channel, embed, PointsPanelView(), "evil_town_banner.png")
        await interaction.delete_original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(PointsHours(bot))
