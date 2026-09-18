"""دوال مساعدة مشتركة بين وحدات البوت."""

from __future__ import annotations

import os

import discord

import config


def has_role(member: discord.Member, role_key: str) -> bool:
    if member.guild_permissions.administrator:
        return True
    role_id = config.ROLE_IDS.get(role_key)
    return role_id is not None and any(role.id == role_id for role in member.roles)


def is_officer(member: discord.Member) -> bool:
    """True when the member has an LSPD officer/presidency role."""
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
    """True فقط عند حمل أحد رتبتي الدخول المحددتين تحديداً (وليس كل رتب is_officer)."""
    if member.guild_permissions.administrator:
        return True
    return any(role.id in config.LOGIN_ALLOWED_ROLE_IDS for role in member.roles)


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



def panel_title(title: str) -> str:
    """عنوان موحد للوحات EvilTown مع الإيموجي في السطر العلوي مرة واحدة."""
    clean = title.replace("**", "").strip()
    if clean.startswith("<:emoji_142:"):
        return clean
    if clean.startswith("Effect King's ("):
        return f"<:emoji_5:1550307911115218974>  '  {clean}"
    return f"<:emoji_5:1550307911115218974>  '  Effect King's ({clean})"


def base_embed(
    title: str,
    description: str = "",
    image_url: str | None = None,
) -> discord.Embed:
    # ترتيب المحتوى يُرسم لاحقاً داخل Container V2؛ العنوان الموحّد يظهر مرة واحدة بالأعلى.
    clean_title = panel_title(title)
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
    """تحويل Embed/View التقليدية إلى Container Components V2 مثل مرجع Control."""
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


# الصور المحلية للوحات: تُرفع كمرفق مع الرسالة وتُستخدم بصيغة attachment:// حتى لا تعتمد على روابط CDN منتهية.
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


async def _log_channels(guild: discord.Guild) -> list[discord.TextChannel]:
    """يجمع كل قنوات اللوقات المُسجّلة (تدعم أكثر من قناة عبر /set-log-channel و/remove-log-channel)."""
    import database as db
    channel_ids: set[int] = set()

    raw_list = await db.get_setting(f"logs_channel_ids:{guild.id}")
    if raw_list:
        for part in raw_list.split(","):
            part = part.strip()
            if part.isdigit():
                channel_ids.add(int(part))

    # التوافق مع الإعداد القديم (قناة واحدة فقط) لمن لم يحدّث بعد.
    legacy_id = await db.get_setting(f"logs_channel_id:{guild.id}")
    if legacy_id and legacy_id.isdigit():
        channel_ids.add(int(legacy_id))

    if not channel_ids and config.LOG_CHANNEL_ID:
        channel_ids.add(config.LOG_CHANNEL_ID)

    return [c for cid in channel_ids if isinstance(c := guild.get_channel(cid), discord.TextChannel)]


async def send_log(
    guild: discord.Guild,
    title: str,
    description: str,
    *,
    colour: int | None = None,
):
    """إرسال سجل نصي مركزي؛ تدعم أكثر من قناة لوقات بنفس الوقت."""
    try:
        channels = await _log_channels(guild)
        if not channels:
            return False

        embed = discord.Embed(title=title, description=description, color=colour or config.EMBED_COLOR)
        embed.set_footer(text=config.EMBED_FOOTER)
        sent_any = False
        for channel in channels:
            try:
                await channel.send(embed=embed)
                sent_any = True
            except (discord.HTTPException, discord.Forbidden):
                continue
        return sent_any
    except (discord.HTTPException, discord.Forbidden, ValueError):
        return False


async def send_log_embed(guild: discord.Guild, embed: discord.Embed):
    """يرسل Embed جاهز (مبني مسبقاً) لكل قنوات اللوقات، بدل بناء واحد نصي جديد."""
    try:
        channels = await _log_channels(guild)
        if not channels:
            return False
        sent_any = False
        for channel in channels:
            try:
                await channel.send(embed=embed)
                sent_any = True
            except (discord.HTTPException, discord.Forbidden):
                continue
        return sent_any
    except (discord.HTTPException, discord.Forbidden, ValueError):
        return False


async def send_panel(channel, embed: discord.Embed, view: discord.ui.View | None, filename: str):
    file = panel_asset(filename)
    if file is None:
        # الملف مفقود من السيرفر (غالباً لم يُرفع لـ GitHub): انشر بدون صورة بدل ما تنهار العملية بالكامل.
        embed.set_image(url=None)
    else:
        panel_embed(embed, filename)
    kwargs = {"view": components_v2_view(embed, view)}
    if file is not None:
        kwargs["file"] = file
    return await channel.send(**kwargs)


async def edit_panel(message, embed: discord.Embed, view: discord.ui.View | None, filename: str):
    """
    يحدّث اللوحة بدون إعادة رفع نفس الصورة كل مرة (الصورة ما تتغيّر بين التحديثات).
    إعادة رفع نفس المرفق بشكل متكرر (كل تسجيل دخول/خروج/تبديل حالة) كانت تسبب
    فلاش/اختفاء مؤقت للرسالة أثناء إعادة معالجة المرفق من ديسكورد.
    لو الملف مفقود من السيرفر لأي سبب، هذا لا يوقف تحديث اللوحة أبداً — يكمل بدون صورة بدل ما ينهار.
    """
    panel_embed(embed, filename)
    try:
        return await message.edit(view=components_v2_view(embed, view))
    except discord.HTTPException:
        # كحل احتياطي: أعد رفع الصورة إن وُجدت، وإلا كمّل بدون صورة بدل ما تنهار العملية.
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
