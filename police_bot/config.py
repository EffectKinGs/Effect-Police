"""إعدادات بوت Police Out Zone."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _role_ids(value: str) -> tuple[int, ...]:
    result = []
    for raw in value.replace("،", ",").split(","):
        raw = raw.strip()
        if raw.isdigit():
            result.append(int(raw))
    return tuple(result)


BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0")) or None

ROLE_IDS = {
    "admin": int(os.getenv("ADMIN_ROLE_ID", "111111111111111111")),
    "officer": int(os.getenv("OFFICER_ROLE_ID", "444444444444444444")),
}

# ضع معرفات كل الرتب التي يسمح لها بإضافة حالة مسؤولية فترة، مفصولة بفواصل.
PERIOD_MANAGER_ROLE_IDS = _role_ids(os.getenv("PERIOD_MANAGER_ROLE_IDS", ""))
MAX_ACTIVE_OFFICERS = int(os.getenv("MAX_ACTIVE_OFFICERS", "30"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0")) or None
LINE_IMAGE_ROLE_IDS = {1542128293741072475, 1542128304847327232}

# قنوات ترسل صورة "خ" تلقائيًا مع أي رسالة تُكتب فيها (بدون الحاجة لكتابة "خ").
LINE_IMAGE_AUTO_CHANNEL_IDS = {
    1511971784000405635,
    1512727555575255061,
    1511973282184826991,
    1486694504567410809,
    1482269063873953963,
    1353792227322888314,
    1511975518021357568,
    1523040887830089738,
    1512070771797790770,
    1512070851019669657,
    1512072475960148068,
    1512072998029361256,
    1529320387098447954,
    1525004157499478156,
    1533098775285858484,
    1495485865361674290,
    1546242267931611176,
    1542151086947967036,
    1542150747356135566,
    1512846994379378739,
    1541166486561886389,
    1542151292057555014,
    1512847150042841158,
    1540333577420673024,
    1541398594945548318,
}

# الهوية العامة لجميع اللوحات.
# الهوية العامة لجميع اللوحات.
EMBED_COLOR = 0x75FBFD
EMBED_FOOTER = "System Police Effect  ."
# يُستخدم كمرجع للهوية؛ اللوحات ترفق الأصل المحلي فعلياً عبر send_panel.
EMBED_IMAGE_URL = "attachment://evil_town_banner.png"
LOGIN_EMBED_IMAGE_URL = "attachment://evil_town_banner.png"

# الإيموجيات المخصصة الموجودة في سيرفر البوت.
CUSTOM_EMOJIS = {
    "on_duty": "<:emoji_5:1550308058448527472>",
    "off_duty": "<:emoji_6:1550308073531252878>",
    "bodycam_on": "<:emoji_5:1550308058448527472>",
    "bodycam_off": "<:emoji_6:1550308073531252878>",
    "dispatch": "<:emoji_4:1550308008280719521>",
    "deputy_dispatch": "<:emoji_4:1550308034180550797>",
    "orange": "<:emoji_8:1550308095593414666>",
    "bodycam": "<:emoji_40:1550481449302360165>",
    "shift_supervisor": "<:emoji_3:1550307987476840538>",
    "rank_badge": "<:emoji_2:1550307963737210981>",
}

# مسار قاعدة البيانات: لو أضفت Volume دائم بـ Railway، يكتشفه تلقائيًا (RAILWAY_VOLUME_MOUNT_PATH)
# ويحفظ فيه بدل ما تنمسح كل Deploy. تقدر كمان تحدده يدويًا عبر متغير DB_PATH.
_DATA_DIR = os.getenv("RAILWAY_VOLUME_MOUNT_PATH") or os.path.dirname(__file__)
DB_PATH = os.getenv("DB_PATH") or os.path.join(_DATA_DIR, "police_bot.db")

# الحالات التي يمكن تشغيلها أو إيقافها من نفس اللوحة.
STATUS_LABELS = {
    "bodycam_on": ("بودي كام أون", "🟢"),
    "bodycam_off": ("بودي كام أوف", "🔴"),
    "dispatch": ("دسباتش", "🔵"),
    "deputy_dispatch": ("نائب دسباتش", "🟤"),
    "period_manager": ("مسؤولية فترة", "⚪"),
}

# بقية اللوحات القديمة قد تعتمد على هذا الاسم؛ أبقيناه للتوافق.
LOGIN_STATUSES = {
    key: {"label": label, "emoji": emoji, "section": label}
    for key, (label, emoji) in STATUS_LABELS.items()
}

DISPATCH_ACCESS_STATUSES = frozenset({"dispatch", "deputy_dispatch"})


# نظام LSPD Control Panel: الرتبة الأساسية تُمنح لكل عسكري رسمي.
LSPD_BASE_ROLE_ID = 1511976724240535704
LSPD_OFFICERS_ROLE_ID = 1353792100541661204
LSPD_RANK_ROLE_IDS = {
    "Cadet": 1353792077791629433,
    "Solo Cadet": 1353792079821799620,
    "Officer I": 1353792083768643614,
    "Officer II": 1459501432234311876,
    "Officer III": 1397542195795595364,
    "Senior Officer": 1353792085882572820,
    "Sergeant": 1353792087740518662,
    "First Sergeant": 1353792090110427146,
    "Staff Sergeant": 1353792091972571146,
    "Lieutenant": 1353792102638682162,
    "First Lieutenant": 1353792104702152776,
    "Captain": 1353792106921066496,
    "Major": 1353792112952610836,
    "Colonel": 1353792115183714304,
    "Deputy Police Chief": 1353792137422049342,
    "Police Chief": 1353792143461847161,
}
LSPD_CHIEF_OFFICE_ROLE_ID = 1490923336576925716
LSPD_WING_ROLE_IDS = {
    "All Wing": 1486975329695170621,
    "Wing Period": 1537770765661769799
    "Wing Dispatch": 1529415619769012255,
    "Wing Negotiation": 1529414009424580638,
    "Wing Motorcycle": 1353792059483623454,
    "Wing AirShip": 1353792063531122759,
    "Wing Interceptor": 1481917973206929448,
}
LSPD_KICK_ROLE_IDS = {
    "فصل": 1542128336577368108,
    "إيقاف عن العمل": 1542128350615568404,
}
LSPD_PRESIDENCY_ROLE_IDS = {1490923336576925716, 1353792100541661204}
# عكس ترتيب القائمة المنسدلة: البوليس تشيف بالأعلى والكدت بالأسفل.
LSPD_RANK_ORDER = tuple(reversed(LSPD_RANK_ROLE_IDS.keys()))
LSPD_OFFICER_RANKS = {
    "Lieutenant",
    "First Lieutenant",
    "Captain",
    "Major",
    "Colonel",
}
LSPD_PRESIDENCY_RANKS = {"Deputy Police Chief", "Police Chief"}
LSPD_ADMIN_ROLE_IDS = {1535880272854388747, 1535880268781592628, 1535880287341518999}

# رتب مسموح لها فقط باستخدام لوحة تسجيل الدخول (Login/Logout/الحالات).
LOGIN_ALLOWED_ROLE_IDS = {1542128293741072475, 1542128304847327232}

# نظام الاستدعاء (Summon): General Call يستهدف كل من يحمل هذه الرتبة.
SUMMON_TARGET_ROLE_ID = 1511976724240535704

# نقاط تلقائية عند تسجيل كل نوع من سجلات الـ MDT — عدّل الأرقام كما تحب.
MDT_POINTS = 2
VEHICLE_IMPOUND_POINTS = 1
SUSPECT_STATEMENT_POINTS = 2
SUBMISSION_ACCEPT_POINTS = 3

# رتبة تُعطى تلقائياً لكل عضو جديد ينضم للسيرفر، وهي نفسها رتبة "مرفوض" اللي ترجع له عند الرفض.
DEFAULT_MEMBER_ROLE_ID = 1353792021164195961

# دورة حياة التقديم على العسكرية (submits.py):
SUBMISSION_PENDING_ROLE_ID = 1542827876762521650   # تُعطى فور إرسال الطلب (بانتظار المراجعة)
SUBMISSION_ACCEPTED_ROLE_ID = 1542128353912291372  # تُعطى عند القبول
SUBMISSION_REJECTED_ROLE_ID = 1542828888441491516  # تُعطى عند الرفض (نفس رتبة العضو الافتراضية)
