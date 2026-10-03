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
    "admin": int(os.getenv("ADMIN_ROLE_ID", "1490923336576925716")),
    "officer": int(os.getenv("OFFICER_ROLE_ID", "1511976724240535704")),
}

PERIOD_MANAGER_ROLE_IDS = _role_ids(os.getenv("PERIOD_MANAGER_ROLE_IDS", ""))
MAX_ACTIVE_OFFICERS = int(os.getenv("MAX_ACTIVE_OFFICERS", "30"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0")) or None
LINE_IMAGE_ROLE_IDS = {1353792100541661204, 1462893421352976454, 1525893097983184957, 1490923336576925716}

LINE_IMAGE_AUTO_CHANNEL_IDS = {
    1409342362831818852,
    1378877352125141002,
    1376733955423862785,
    1376725841547100221,
    1376755067922944100,
    1408915237167431790,
    1378927391090413658,
    1377489393396219974,
    1376742657568800779,
    1554996652618678392,
    1554996990054768702,
    1554997109063811132,
    1554997217755009184,
    1554997343206641744,
    1554997715220303993,
    1554997828516839454,
    1554997927833763930,
    1554801161691856964,
}

EMBED_COLOR = 0x01FFFE
EMBED_FOOTER = "System Police OLD KING  ."
PANEL_BANNER_ASSET = "old_king_panel_banner.png"
TICKET_BANNER_ASSET = "old_king_tickets_banner.png"
# أرقام بداية التكتات حسب ترتيب نوع التذكرة (الأول 3170، الثاني 4850، الثالث 683 ...)
TICKET_START_NUMBERS = [3170, 4850, 683]
TICKET_DEFAULT_START = 1000
LOGIN_BANNER_ASSET = "duty_ops_banner.png"
EMBED_IMAGE_URL = f"attachment://{PANEL_BANNER_ASSET}"
LOGIN_EMBED_IMAGE_URL = f"attachment://{LOGIN_BANNER_ASSET}"

LINE_IMAGE_ASSET = "old_king_line.png"

PANEL_TITLE_EMOJIS = {
    "default": "<:emoji_5:1550307911115218974>",
    "login": "<:emoji_5:1550307911115218974>",
    "points": "<:emoji_5:1550307911115218974>",
    "wings": "<:emoji_5:1550307911115218974>",
}

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

_DATA_DIR = os.getenv("RAILWAY_VOLUME_MOUNT_PATH") or os.path.dirname(__file__)
DB_PATH = os.getenv("DB_PATH") or os.path.join(_DATA_DIR, "police_bot.db")

STATUS_LABELS = {
    "bodycam_on": ("بودي كام أون", "🟢"),
    "bodycam_off": ("بودي كام أوف", "🔴"),
    "dispatch": ("دسباتش", "🔵"),
    "deputy_dispatch": ("نائب دسباتش", "🟤"),
    "period_manager": ("مسؤولية فترة", "⚪"),
}

LOGIN_STATUSES = {
    key: {"label": label, "emoji": emoji, "section": label}
    for key, (label, emoji) in STATUS_LABELS.items()
}

DISPATCH_ACCESS_STATUSES = frozenset({"dispatch", "deputy_dispatch"})


LSPD_BASE_ROLE_ID = 1367803324610642012
LSPD_OFFICERS_ROLE_ID = 1366836306516377641
LSPD_RANK_ROLE_IDS = {
    "Cadet": 1367802147357331466,
    "Solo Cadet": 1367802075672612884,
    "Officer I": 1367801922081263686,
    "Officer II": 1367801849956012042,
    "Officer III": 1367801772730744894,
    "Senior Officer": 1367801642291822613,
    "Sergeant": 1367801407859851276,
    "First Sergeant": 1367801345184370738,
    "Staff Sergeant": 1367801209465077790,
    "Lieutenant": 1366835477172457472,
    "First Lieutenant": 1366835339058217011,
    "Captain": 1366835124695601254,
    "Major": 1366834678081785946,
    "Colonel": 1366834494283321524,
    "Deputy Police Chief": 1366833894812418169,
    "Police Chief": 1366833644542628001,
}
LSPD_CHIEF_OFFICE_ROLE_ID = 1490923336576925716
LSPD_WING_ROLE_IDS = {
    "All Wing": 1555690396133363846,
    "Wing Dispatch": 1408922447041794239,
    "Wing Motorcycle": 1367803030770028665,
    "Wing AirShip": 1367802880597295184,
    "Wing Interceptor": 1381296327039779038,
}
LSPD_KICK_ROLE_IDS = {
    "فصل": 1542128336577368108,
    "إيقاف عن العمل": 1542128350615568404,
}
LSPD_PRESIDENCY_ROLE_IDS = {1490923336576925716, 1353792100541661204}
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

LOGIN_ALLOWED_ROLE_IDS = {1511976724240535704}
SYSTEM_ADMIN_ROLE_IDS = {1490923336576925716}
MDT_ALLOWED_ROLE_IDS = {1511976724240535704}
SUBMISSION_REVIEW_ROLE_IDS = {1525893097983184957}
CLOTHING_ROLE_IDS = {1462893421352976454, 1525893097983184957}
SUMMON_ROLE_IDS = {1353792100541661204, 1490923336576925716, 1462893421352976454, 1525893097983184957, 1540332271037583431}
CONTROL_PANEL_ROLE_IDS = {1525893097983184957, 1462893421352976454, 1353792100541661204, 1490923336576925716}
POINTS_MANAGE_ROLE_IDS = {1462893421352976454, 1353792100541661204, 1490923336576925716}
SHOW_ALL_ROLE_IDS = {1353792100541661204, 1462893421352976454, 1525893097983184957, 1490923336576925716}

SUMMON_TARGET_ROLE_ID = 1511976724240535704

MDT_POINTS = 2
VEHICLE_IMPOUND_POINTS = 1
SUSPECT_STATEMENT_POINTS = 2
SUBMISSION_ACCEPT_POINTS = 3

DEFAULT_MEMBER_ROLE_ID = 1353792021164195961

SUBMISSION_PENDING_ROLE_ID = 1542827876762521650
SUBMISSION_ACCEPTED_ROLE_ID = 1542128353912291372
SUBMISSION_REJECTED_ROLE_ID = 1542828888441491516


# ---------------- OLD KING LOGS ----------------
# key -> (رقم القسم, اسم القسم بالعربي)
LOG_CATEGORIES = {
    "points": (1, "إضافة وإزالة الساعات والنقاط"),
    "submits": (2, "قبول ورفض التقديمات"),
    "roles": (3, "إعطاء وإزالة الرتب"),
    "control": (4, "تسجيل وترقية وإعطاء ونق وطرد العسكر"),
    "tickets": (5, "فتح التكت وإغلاقها واستلامها والتخلي عنها"),
    "summon": (6, "الاستدعاءات والأشخاص المستعملين للوحة"),
    "login": (7, "لوحة تسجيل الدخول والأزرار"),
    "mdt": (8, "لوحة الـ MDT بشكل عام"),
}

LOG_TITLE_EMOJI = "<:emoji_288:1555520227939188786>"
LOG_MENTION_EMOJI = "<:emoji_38:1550334422274801664>"
LOG_COMMAND_EMOJI = "<:1DoT3:1555552114993008670>"
LOG_DETAILS_EMOJI = "<:emoji_14:1555506715946909869>"
