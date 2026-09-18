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
    1545165163139825776,
    1542128445553909861,
    1542128444471771186,
    1543495406812528811,
    1542128416856477876,
    1542128431301660693,
    1542128413089996882,
    1542128438461079632,
    1542128457117474939,
    1542128420610383946,
    1542128408786505798,
}

# الهوية العامة لجميع اللوحات.
# الهوية العامة لجميع اللوحات.
EMBED_COLOR = 0xFF0000
EMBED_FOOTER = "System Police EvilTown ."
# يُستخدم كمرجع للهوية؛ اللوحات ترفق الأصل المحلي فعلياً عبر send_panel.
EMBED_IMAGE_URL = "attachment://evil_town_banner.png"
LOGIN_EMBED_IMAGE_URL = "attachment://evil_town_banner.png"

# الإيموجيات المخصصة الموجودة في سيرفر البوت.
CUSTOM_EMOJIS = {
    "lspd_logo": "<:LogoLSPD:1496182776452485300>",
    "checkin": "<:emoji_48:1537733596834701434>",
    "count": "<:emoji_51:1537733712123265024>",
    "empty": "<:emoji_45:1537733516953915452>",
    "on_duty": "<:emoji_9:1542967699339087992>",
    "off_duty": "<:emoji_9:1542967668666142861>",
    "bodycam_on": "<:emoji_9:1542967699339087992>",
    "bodycam_off": "<:emoji_9:1542967668666142861>",
    "dispatch": "<:emoji_12:1542967800350515290>",
    "deputy_dispatch": "<:emoji_10:1542967730024620142>",
    "black": "<:emoji_111:1540105812997968042>",
    "orange": "<:emoji_8:1542967637808517232>",
    "staff_tools": "<:emoji_41:1524823438588379370>",
    "bodycam": "<:emoji_112:1540107665303142493>",
    "shift_supervisor": "<:emoji_12:1542971099346640997>",
    "rank_badge": "<:emoji_14:1542971142627917924>",
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
LSPD_BASE_ROLE_ID = 1542128316285460481
LSPD_OFFICERS_ROLE_ID = 1542128304847327232
LSPD_RANK_ROLE_IDS = {
    "Cadet": 1542128315278565386,
    "Officer I": 1542128314041237504,
    "Officer II": 1542128312967503912,
    "Officer III": 1542128312112123914,
    "Senior Officer": 1542128311273136158,
    "Sergeant": 1542128309490688020,
    "First Sergeant": 1542128308249042995,
    "Staff Sergeant": 1542128307473088602,
    "Lieutenant": 1542128303895351437,
    "First Lieutenant": 1542128302775341186,
    "Captain": 1542128301559119874,
    "Major": 1542128299726209145,
    "Colonel": 1542128297582792845,
    "Deputy Police Chief": 1542128290276446208,
    "Police Chief": 1542128289290780672,
}
LSPD_CHIEF_OFFICE_ROLE_ID = 1542128293741072475
LSPD_WING_ROLE_IDS = {
    "Wing Dispatch": 1542128328205533256,
    "Wing Negotiation": 1542128329086206035,
    "Wing Motorcycle": 1542128330504147029,
    "Wing Air Ship": 1542128332274008204,
    "Wing Interceptor": 1542128334354513960,
}
LSPD_KICK_ROLE_IDS = {
    "فصل": 1542128336577368108,
    "إيقاف عن العمل": 1542128350615568404,
}
LSPD_PRESIDENCY_ROLE_IDS = {1535880272854388747, 1535880268781592628}
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
SUMMON_TARGET_ROLE_ID = 1542128316285460481

# نقاط تلقائية عند تسجيل كل نوع من سجلات الـ MDT — عدّل الأرقام كما تحب.
MDT_POINTS = 2
VEHICLE_IMPOUND_POINTS = 1
SUSPECT_STATEMENT_POINTS = 2
SUBMISSION_ACCEPT_POINTS = 3

# رتبة تُعطى تلقائياً لكل عضو جديد ينضم للسيرفر، وهي نفسها رتبة "مرفوض" اللي ترجع له عند الرفض.
DEFAULT_MEMBER_ROLE_ID = 1542828888441491516

# دورة حياة التقديم على العسكرية (submits.py):
SUBMISSION_PENDING_ROLE_ID = 1542827876762521650   # تُعطى فور إرسال الطلب (بانتظار المراجعة)
SUBMISSION_ACCEPTED_ROLE_ID = 1542128353912291372  # تُعطى عند القبول
SUBMISSION_REJECTED_ROLE_ID = 1542828888441491516  # تُعطى عند الرفض (نفس رتبة العضو الافتراضية)
