import asyncio
import logging
import os
import sys

# دعم Railway حتى لو لم يتعامل مسار التشغيل مع مجلد cogs كحزمة Python.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
COGS_ROOT = os.path.join(PROJECT_ROOT, "cogs")
for _path in (PROJECT_ROOT, COGS_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import discord
from discord.ext import commands, tasks

import config
import database as db
import utils

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="-", intents=intents)

COGS = [
    "login_panel",
    "points_hours",
    "wings",
    "tickets",
    "setup_admin",
    "clothing",
    "quick_image",
    "control_panel",
    "summon_panel",
    "submits",
    "custom_embed",
    "mdt",
]

_views_registered = False
_commands_synced = False


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: discord.app_commands.AppCommandError
):
    logging.getLogger(__name__).exception(
        "App command error in /%s",
        getattr(interaction.command, "name", "?"),
        exc_info=error
    )

    message = "⚠️ صار خطأ غير متوقع أثناء تنفيذ الأمر. تم تسجيل التفاصيل للمطور."

    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        pass


@tasks.loop(minutes=1)
async def hourly_points_loop():
    awarded = await db.award_hourly_session_points()

    for guild_id, user_id, hours in awarded:
        guild = bot.get_guild(guild_id)

        if guild is not None:
            await utils.send_log(
                guild,
                "Automatic Hourly Points",
                f"العضو: <@{user_id}> (`{user_id}`)\n"
                f"النقاط المضافة: +{hours}\n"
                f"السبب: إكمال ساعة مباشرة."
            )


@bot.event
async def on_member_join(member: discord.Member):
    role = member.guild.get_role(config.DEFAULT_MEMBER_ROLE_ID)

    if role is None:
        return

    try:
        await member.add_roles(
            role,
            reason="Default role on join"
        )
    except discord.Forbidden:
        logging.getLogger(__name__).warning(
            "Could not add default role to %s: missing permissions",
            member.id
        )


@bot.event
async def on_ready():
    global _views_registered, _commands_synced

    print(f"✅ تم تسجيل الدخول باسم {bot.user} (ID: {bot.user.id})")

    # ==============================
    # حالة البوت / النشاط
    # ==============================
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(
            name="Programmed By SaadEx"
        )
    )

    print("🟢 تم تشغيل حالة البوت: Programmed By SaadEx .")

    if not _views_registered:
        # الأزرار الدائمة يجب تسجيلها مرة واحدة فقط، لتبقى فعّالة بعد إعادة التشغيل.
        from points_hours import PointsPanelView
        from clothing import ClothingPanelView
        from login_panel import LoginPanelView
        from tickets import CloseTicketView, TicketPanelView, UpgradePanelView
        from wings import WingsPanelView
        from control_panel import LSPDControlView
        from summon_panel import SummonPanelView
        from submits import SubmissionPanelView, SubmissionReviewView
        from custom_embed import EmbedPanelView
        from mdt import MDTPanelView, RecordCheckPanelView

        bot.add_view(LoginPanelView(expanded=False))
        bot.add_view(WingsPanelView())
        bot.add_view(PointsPanelView())
        bot.add_view(UpgradePanelView())
        bot.add_view(LSPDControlView())
        bot.add_view(CloseTicketView())
        bot.add_view(SummonPanelView())
        bot.add_view(SubmissionPanelView())
        bot.add_view(SubmissionReviewView())
        bot.add_view(EmbedPanelView())
        bot.add_view(MDTPanelView())
        bot.add_view(RecordCheckPanelView())

        ticket_types = await db.list_ticket_types()

        if ticket_types:
            bot.add_view(TicketPanelView(ticket_types))

        clothing_items = await db.list_clothing_items()

        if clothing_items:
            bot.add_view(ClothingPanelView(clothing_items))

        _views_registered = True

    if not hourly_points_loop.is_running():
        hourly_points_loop.start()

    if not _commands_synced:
        try:
            if config.GUILD_ID:
                target_guild = bot.get_guild(config.GUILD_ID)

                if target_guild is None:
                    visible_ids = ", ".join(
                        str(guild.id) for guild in bot.guilds
                    ) or "لا يوجد"

                    logging.getLogger(__name__).error(
                        "GUILD_ID=%s غير متاح للبوت. السيرفرات المرئية حالياً: %s. "
                        "تحقق من GUILD_ID ومن دعوة البوت مع applications.commands.",
                        config.GUILD_ID,
                        visible_ids,
                    )

                    _commands_synced = True
                    return

                guild = discord.Object(id=config.GUILD_ID)

                bot.tree.copy_global_to(guild=guild)
                synced = await bot.tree.sync(guild=guild)

            else:
                synced = await bot.tree.sync()

            _commands_synced = True

            print(f"🔄 تمت مزامنة {len(synced)} أمر Slash.")

        except discord.Forbidden:
            logging.getLogger(__name__).exception(
                "تعذر مزامنة أوامر Slash بسبب Missing Access. "
                "تحقق من GUILD_ID وعضوية البوت وscope applications.commands."
            )

            _commands_synced = True

        except discord.HTTPException:
            logging.getLogger(__name__).exception(
                "فشلت مزامنة أوامر Slash بسبب خطأ Discord HTTP؛ "
                "سيبقى البوت متصلاً."
            )

            _commands_synced = True


async def main():
    await db.init_db()

    try:
        async with bot:
            for cog in COGS:
                await bot.load_extension(cog)

            await bot.start(config.BOT_TOKEN)

    finally:
        await db.close_db()


if __name__ == "__main__":
    if not config.BOT_TOKEN:
        raise SystemExit("❌ لم يتم ضبط BOT_TOKEN في ملف .env")

    asyncio.run(main())
