from __future__ import annotations

import os
import re

import discord

import config


def has_role(member: discord.Member, role_key: str) -> bool:
    if member.guild_permissions.administrator:
        return True
    if role_key == "admin":
        allowed = config.SYSTEM_ADMIN_ROLE_IDS
    elif role_key == "officer":
        allowed = config.LOGIN_ALLOWED_ROLE_IDS
    else:
        role_id = config.ROLE_IDS.get(role_key)
        allowed = {role_id} if role_id else set()
    return any(role.id in allowed for role in member.roles)


def has_any_role(member: discord.Member, role_ids: set[int] | tuple[int, ...]) -> bool:
    return member.guild_permissions.administrator or any(role.id in role_ids for role in member.roles)


def is_system_admin(member: discord.Member) -> bool:
    return has_any_role(member, config.SYSTEM_ADMIN_ROLE_IDS)


def is_officer(member: discord.Member) -> bool:
    officer_role_ids = {
        config.LSPD_OFFICERS_ROLE_ID,
        *(
            config.LSPD_RANK_ROLE_IDS[rank]
            for rank in config.LSPD_OFFICER_RANKS | config.LSPD_PRESIDENCY_RANKS
            if rank in config.LSPD_RANK_ROLE_IDS
        ),
        config.LSPD_CHIEF_OFFICE_ROLE_ID,
    }
    return any(role.id in officer_role_ids for role in member.roles)


def can_login(member: discord.Member) -> bool:
    return member.guild_permissions.administrator or any(role.id in config.LOGIN_ALLOWED_ROLE_IDS for role in member.roles)


def is_period_manager(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    return any(role.id in config.PERIOD_MANAGER_ROLE_IDS for role in member.roles)


def officer_rank(member: discord.Member) -> int:
    return member.top_role.position if member.top_role else 0


def format_duration(seconds: int | float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes = remainder // 60
    return f"{hours}h, {minutes}min"


def panel_title(title: str, panel_key: str = "default") -> str:
    clean = title.replace("**", "").strip()
    emoji = config.PANEL_TITLE_EMOJIS.get(panel_key) or config.PANEL_TITLE_EMOJIS.get("default", "")
    return f"{clean}"


def base_embed(
    title: str,
    description: str = "",
    image_url: str | None = None,
    panel_key: str = "default",
) -> discord.Embed:
    clean_title = panel_title(title, panel_key)
    if clean_title.startswith("#"):
        clean_title = clean_title.lstrip("#").strip(" -—")
    final_description = description.strip()
    embed = discord.Embed(title=clean_title, description=final_description, color=config.EMBED_COLOR)
    embed.set_footer(text=config.EMBED_FOOTER)
    image = config.EMBED_IMAGE_URL if image_url is None else image_url
    if image:
        embed.set_image(url=image)
    return embed


class NoPermission(discord.app_commands.CheckFailure):
    pass


def components_v2_view(embed: discord.Embed, view: discord.ui.View | None = None) -> discord.ui.LayoutView:
    layout = discord.ui.LayoutView(timeout=None)
    title = embed.title or panel_title("System")
    children: list[discord.ui.Item] = [discord.ui.TextDisplay(f"# {title}")]
    if embed.description:
        children.extend(
            (
                discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(embed.description),
            )
        )
    image_url = getattr(embed.image, "url", None)
    if image_url:
        children.extend(
            (
                discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
                discord.ui.MediaGallery(discord.MediaGalleryItem(image_url)),
            )
        )
    footer_text = embed.footer.text or config.EMBED_FOOTER
    children.extend(
        (
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(f"-# **{footer_text}**"),
        )
    )
    if view is not None and view.children:
        rows: dict[int, list[discord.ui.Item]] = {}
        for item in view.children:
            row = int(getattr(item, "row", 0) or 0)
            rows.setdefault(row, []).append(item)
        children.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        for row_items in (rows[key] for key in sorted(rows)):
            children.append(discord.ui.ActionRow(*row_items))
    colour = embed.colour.value if embed.colour else config.EMBED_COLOR
    layout.add_item(discord.ui.Container(*children, accent_color=colour))
    return layout


PANEL_ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")


def panel_asset(filename: str) -> discord.File | None:
    path = os.path.join(PANEL_ASSET_DIR, filename)
    if not os.path.isfile(path):
        return None
    return discord.File(path, filename=filename)


def panel_embed(embed: discord.Embed, filename: str) -> discord.Embed:
    embed.set_image(url=f"attachment://{filename}")
    return embed


def panel_file_exists(filename: str) -> bool:
    return os.path.isfile(os.path.join(PANEL_ASSET_DIR, filename))


def log_key(guild_id: int, category: str) -> str:
    return f"log_channel:{guild_id}:{category}"


async def send_log(
    guild: discord.Guild,
    category: str,
    name: str,
    user: discord.abc.User | discord.Member | int | None,
    command: str,
    details: str = "-",
    *,
    colour: int | None = None,
) -> bool:
    """لوق OLD KING بنظام V2. category = مفتاح القسم من config.LOG_CATEGORIES."""
    import database as db

    try:
        raw = await db.get_setting(log_key(guild.id, category))
        if not raw or not raw.isdigit():
            return False
        channel = guild.get_channel(int(raw))
        if not isinstance(channel, discord.TextChannel):
            return False

        if isinstance(user, int):
            mention = f"<@{user}>"
        elif user is not None:
            mention = user.mention
        else:
            mention = "—"

        body = "\n".join(
            (
                f"{config.LOG_MENTION_EMOJI}︲Mention The Person : {mention}",
                f"{config.LOG_COMMAND_EMOJI}︲Command Used : {command}",
                f"{config.LOG_DETAILS_EMOJI}︲Details : {details}",
            )
        )
        layout = discord.ui.LayoutView(timeout=None)
        layout.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"# {config.LOG_TITLE_EMOJI}︲OLd LOG ( {name} )"),
                discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(f"**\n{body}**"),
                accent_color=colour or config.EMBED_COLOR,
            )
        )
        await channel.send(view=layout, allowed_mentions=discord.AllowedMentions.none())
        return True
    except (discord.HTTPException, discord.Forbidden, ValueError):
        return False


async def send_panel(channel, embed: discord.Embed, view: discord.ui.View | None, filename: str):
    file = panel_asset(filename)
    if file is None:
        embed.set_image(url=None)
    else:
        panel_embed(embed, filename)
    kwargs = {"view": components_v2_view(embed, view)}
    if file is not None:
        kwargs["file"] = file
    return await channel.send(**kwargs)


async def edit_panel(message, embed: discord.Embed, view: discord.ui.View | None, filename: str):
    panel_embed(embed, filename)
    try:
        return await message.edit(view=components_v2_view(embed, view))
    except discord.HTTPException:
        file = panel_asset(filename)
        if file is None:
            embed.set_image(url=None)
            return await message.edit(view=components_v2_view(embed, view))
        return await message.edit(view=components_v2_view(embed, view), attachments=[file])


async def send_panel_with_files(channel, embed: discord.Embed, view: discord.ui.View | None, filenames: list[str]):
    files = [f for name in filenames if (f := panel_asset(name)) is not None]
    if filenames:
        if files:
            panel_embed(embed, filenames[0])
        else:
            embed.set_image(url=None)
    kwargs = {"view": components_v2_view(embed, view)}
    if files:
        kwargs["files"] = files
    return await channel.send(**kwargs)
