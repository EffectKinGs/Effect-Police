"""طبقة SQLite غير المتزامنة لبوت Effect King's Police."""

from __future__ import annotations

import os
import time
from collections.abc import Iterable

import aiosqlite

import config

_db: aiosqlite.Connection | None = None


async def init_db():
    global _db
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
    _db = await aiosqlite.connect(config.DB_PATH)
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL DEFAULT 0,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            status_key TEXT NOT NULL DEFAULT 'officer',
            officer_rank INTEGER NOT NULL DEFAULT 0,
            login_time INTEGER NOT NULL,
            logout_time INTEGER,
            duration_seconds INTEGER,
            bodycam_on INTEGER NOT NULL DEFAULT 0,
            bodycam_off INTEGER NOT NULL DEFAULT 1,
            dispatch INTEGER NOT NULL DEFAULT 0,
            deputy_dispatch INTEGER NOT NULL DEFAULT 0,
            period_manager INTEGER NOT NULL DEFAULT 0,
            code_01 INTEGER NOT NULL DEFAULT 0,
            code_01_started_at INTEGER
        )
    """)
    await _migrate_sessions()
    await _create_other_tables()
    await _db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('login_enabled', '1')")
    await _db.commit()


async def _migrate_sessions():
    cursor = await db().execute("PRAGMA table_info(sessions)")
    columns = {row[1] for row in await cursor.fetchall()}
    additions = {
        "guild_id": "INTEGER NOT NULL DEFAULT 0",
        "officer_rank": "INTEGER NOT NULL DEFAULT 0",
        "bodycam_on": "INTEGER NOT NULL DEFAULT 0",
        "bodycam_off": "INTEGER NOT NULL DEFAULT 1",
        "dispatch": "INTEGER NOT NULL DEFAULT 0",
        "deputy_dispatch": "INTEGER NOT NULL DEFAULT 0",
        "period_manager": "INTEGER NOT NULL DEFAULT 0",
        "code_01": "INTEGER NOT NULL DEFAULT 0",
        "code_01_started_at": "INTEGER",
        "last_hour_point_at": "INTEGER",
    }
    for name, definition in additions.items():
        if name not in columns:
            await db().execute(f"ALTER TABLE sessions ADD COLUMN {name} {definition}")
    await db().execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_open_guild ON sessions (guild_id, logout_time)"
    )


async def _create_other_tables():
    await db().execute("""CREATE TABLE IF NOT EXISTS periods (
        id INTEGER PRIMARY KEY AUTOINCREMENT, manager_id INTEGER NOT NULL,
        manager_name TEXT NOT NULL, start_time INTEGER NOT NULL,
        end_time INTEGER, duration_seconds INTEGER, active INTEGER DEFAULT 1)""")
    await db().execute("""CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_number TEXT NOT NULL,
        officer_id INTEGER NOT NULL, officer_name TEXT NOT NULL,
        description TEXT NOT NULL, status TEXT DEFAULT 'مفتوحة', created_at INTEGER NOT NULL)""")
    await db().execute("""CREATE TABLE IF NOT EXISTS points (
        user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0, hours REAL DEFAULT 0)""")
    await db().execute("""CREATE TABLE IF NOT EXISTS wings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
        role_id INTEGER NOT NULL, emoji TEXT DEFAULT '🪖', description TEXT DEFAULT '')""")
    await db().execute("""CREATE TABLE IF NOT EXISTS ticket_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT UNIQUE NOT NULL,
        emoji TEXT DEFAULT '🎫', role_id INTEGER NOT NULL)""")
    await db().execute("""CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL, type_label TEXT NOT NULL,
        status TEXT DEFAULT 'مفتوحة', created_at INTEGER NOT NULL)""")
    await _db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    await db().execute("""CREATE TABLE IF NOT EXISTS clothing_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
        description TEXT NOT NULL, image_url TEXT, emoji TEXT DEFAULT '👮')""")
    await _migrate_clothing_items()
    await db().execute("""CREATE TABLE IF NOT EXISTS mdt_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        record_type TEXT NOT NULL,
        character_id TEXT NOT NULL,
        officer_id INTEGER NOT NULL,
        summary TEXT NOT NULL,
        created_at INTEGER NOT NULL)""")


async def _migrate_clothing_items():
    cursor = await db().execute("PRAGMA table_info(clothing_items)")
    columns = {row[1] for row in await cursor.fetchall()}
    if "emoji" not in columns:
        await db().execute("ALTER TABLE clothing_items ADD COLUMN emoji TEXT DEFAULT '👮'")


def db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


async def close_db():
    global _db
    if _db is not None:
        await _db.close()
        _db = None


# ---------------- المباشرة والحالات المتعددة ----------------

async def open_session(guild_id: int, user_id: int, username: str, status_or_rank, officer_rank: int | None = None) -> bool:
    # يقبل الصيغة القديمة (guild, user, name, status, rank) والجديدة (guild, user, name, rank).
    rank = int(officer_rank if officer_rank is not None else status_or_rank)
    if await get_open_session(guild_id, user_id):
        return False
    await db().execute(
        """INSERT INTO sessions
        (guild_id, user_id, username, status_key, officer_rank, login_time,
            bodycam_on, bodycam_off, dispatch, deputy_dispatch, period_manager, code_01, last_hour_point_at)
        VALUES (?, ?, ?, 'officer', ?, ?, 0, 1, 0, 0, 0, 0, ?)""",
        (guild_id, user_id, username, rank, int(time.time()), int(time.time())),
    )
    await db().commit()
    await add_points(user_id, 1)
    return True


async def get_open_session(guild_id: int, user_id: int):
    cursor = await db().execute(
        """SELECT id, status_key, login_time, officer_rank, bodycam_on,
        bodycam_off, dispatch, deputy_dispatch, period_manager, code_01, code_01_started_at
        FROM sessions WHERE guild_id = ? AND user_id = ? AND logout_time IS NULL
        ORDER BY id DESC LIMIT 1""",
        (guild_id, user_id),
    )
    return await cursor.fetchone()


async def get_active_sessions(guild_id: int):
    cursor = await db().execute(
        """SELECT id, user_id, username, login_time, officer_rank,
        bodycam_on, bodycam_off, dispatch, deputy_dispatch, period_manager, code_01, code_01_started_at
        FROM sessions WHERE guild_id = ? AND logout_time IS NULL
        ORDER BY code_01 ASC, officer_rank DESC, login_time ASC, id ASC""",
        (guild_id,),
    )
    return await cursor.fetchall()


async def count_active_sessions(guild_id: int) -> int:
    cursor = await db().execute(
        "SELECT COUNT(*) FROM sessions WHERE guild_id = ? AND logout_time IS NULL",
        (guild_id,),
    )
    row = await cursor.fetchone()
    return int(row[0] or 0)


async def get_active_flags(guild_id: int, user_id: int) -> dict[str, bool] | None:
    session = await get_open_session(guild_id, user_id)
    if not session:
        return None
    return {
        "bodycam_on": bool(session[4]),
        "bodycam_off": bool(session[5]),
        "dispatch": bool(session[6]),
        "deputy_dispatch": bool(session[7]),
        "period_manager": bool(session[8]),
        "code_01": bool(session[9]),
    }


async def toggle_status(guild_id: int, user_id: int, status_key: str) -> tuple[bool, bool] | None:
    """يقلب الحالة ويعيد (القيمة الجديدة، هل توجد جلسة)."""
    allowed = {"bodycam_on", "bodycam_off", "dispatch", "deputy_dispatch", "period_manager", "code_01"}
    if status_key not in allowed:
        return None
    session = await get_open_session(guild_id, user_id)
    if not session:
        return None

    current = bool(session[{"bodycam_on": 4, "bodycam_off": 5, "dispatch": 6,
                            "deputy_dispatch": 7, "period_manager": 8, "code_01": 9}[status_key]])
    new_value = not current
    if status_key == "code_01":
        now = int(time.time())
        if new_value:
            await db().execute("UPDATE sessions SET code_01 = 1, code_01_started_at = ? WHERE id = ?", (now, session[0]))
        else:
            paused_seconds = max(0, now - (session[10] or now))
            await db().execute("UPDATE sessions SET code_01 = 0, code_01_started_at = NULL, login_time = login_time + ? WHERE id = ?", (paused_seconds, session[0]))
    elif status_key == "bodycam_on":
        await db().execute("UPDATE sessions SET bodycam_on = ?, bodycam_off = ? WHERE id = ?", (int(new_value), int(not new_value), session[0]))
    elif status_key == "bodycam_off":
        await db().execute("UPDATE sessions SET bodycam_off = ?, bodycam_on = ? WHERE id = ?", (int(new_value), int(not new_value), session[0]))
    else:
        await db().execute(f"UPDATE sessions SET {status_key} = ? WHERE id = ?", (int(new_value), session[0]))
    await db().commit()
    return new_value, True


async def set_status(guild_id: int, user_id: int, status_key: str, enabled: bool) -> tuple[bool, bool] | None:
    """يضبط الحالة صراحةً على تشغيل أو إيقاف، ويعيد (القيمة، هل توجد جلسة)."""
    allowed = {"bodycam_on", "bodycam_off", "dispatch", "deputy_dispatch", "period_manager", "code_01"}
    if status_key not in allowed:
        return None
    session = await get_open_session(guild_id, user_id)
    if not session:
        return None
    current = bool(session[{"bodycam_on": 4, "bodycam_off": 5, "dispatch": 6, "deputy_dispatch": 7, "period_manager": 8, "code_01": 9}[status_key]])
    if current == enabled:
        return enabled, True
    if status_key == "code_01":
        now = int(time.time())
        if enabled:
            await db().execute("UPDATE sessions SET code_01 = 1, code_01_started_at = ? WHERE id = ?", (now, session[0]))
        else:
            paused_seconds = max(0, now - (session[10] or now))
            await db().execute("UPDATE sessions SET code_01 = 0, code_01_started_at = NULL, login_time = login_time + ? WHERE id = ?", (paused_seconds, session[0]))
    elif status_key == "bodycam_on":
        await db().execute("UPDATE sessions SET bodycam_on = ?, bodycam_off = ? WHERE id = ?", (int(enabled), int(not enabled), session[0]))
    elif status_key == "bodycam_off":
        await db().execute("UPDATE sessions SET bodycam_off = ?, bodycam_on = ? WHERE id = ?", (int(enabled), int(not enabled), session[0]))
    else:
        await db().execute(f"UPDATE sessions SET {status_key} = ? WHERE id = ?", (int(enabled), session[0]))
    await db().commit()
    return enabled, True


async def user_has_active_status(guild_id: int, user_id: int, status_keys: Iterable[str]) -> bool:
    keys = tuple(status_keys)
    flags = await get_active_flags(guild_id, user_id)
    return flags is not None and any(flags.get(key, False) for key in keys)


async def close_session(guild_id: int, user_id: int):
    session = await get_open_session(guild_id, user_id)
    if not session:
        return None
    now = int(time.time())
    duration = max(0, (session[10] if session[9] else now) - session[2])
    await db().execute(
        "UPDATE sessions SET logout_time = ?, duration_seconds = ? WHERE id = ?",
        (now, duration, session[0]),
    )
    await db().commit()
    await add_hours(user_id, duration / 3600)
    return {"status_key": session[1], "login_time": session[2], "logout_time": now, "duration": duration}


async def total_duration_seconds(user_id: int, guild_id: int | None = None) -> int:
    now = int(time.time())
    query = """SELECT COALESCE(SUM(CASE WHEN duration_seconds IS NOT NULL THEN duration_seconds
        WHEN logout_time IS NULL THEN CASE WHEN code_01 = 1 THEN MAX(0, code_01_started_at - login_time)
        ELSE MAX(0, ? - login_time) END ELSE 0 END), 0)
        FROM sessions WHERE user_id = ?"""
    values: tuple = (now, user_id)
    if guild_id is not None:
        query += " AND guild_id = ?"
        values += (guild_id,)
    cursor = await db().execute(query, values)
    row = await cursor.fetchone()
    return int(row[0] or 0)


async def set_login_enabled(enabled: bool):
    await set_setting("login_enabled", "1" if enabled else "0")


async def is_login_enabled() -> bool:
    return (await get_setting("login_enabled")) != "0"


# ---------------- التوافق والأنظمة الأخرى ----------------

async def start_period(manager_id: int, manager_name: str):
    if await get_active_period():
        return None
    await db().execute("INSERT INTO periods (manager_id, manager_name, start_time) VALUES (?, ?, ?)", (manager_id, manager_name, int(time.time())))
    await db().commit()
    return await get_active_period()


async def get_active_period():
    cursor = await db().execute("SELECT id, manager_id, manager_name, start_time FROM periods WHERE active = 1 ORDER BY id DESC LIMIT 1")
    return await cursor.fetchone()


async def end_period():
    period = await get_active_period()
    if not period:
        return None
    now = int(time.time())
    duration = max(0, now - period[3])
    await db().execute("UPDATE periods SET end_time = ?, duration_seconds = ?, active = 0 WHERE id = ?", (now, duration, period[0]))
    await db().commit()
    return {"manager_id": period[1], "manager_name": period[2], "start_time": period[3], "end_time": now, "duration": duration}


async def add_case(case_number: str, officer_id: int, officer_name: str, description: str):
    await db().execute("INSERT INTO cases (case_number, officer_id, officer_name, description, created_at) VALUES (?, ?, ?, ?, ?)", (case_number, officer_id, officer_name, description, int(time.time())))
    await db().commit()


async def update_case_status(case_number: str, status: str) -> bool:
    cursor = await db().execute("UPDATE cases SET status = ? WHERE case_number = ?", (status, case_number))
    await db().commit()
    return cursor.rowcount > 0


async def _ensure_user_row(user_id: int):
    await db().execute("INSERT OR IGNORE INTO points (user_id, points, hours) VALUES (?, 0, 0)", (user_id,))


async def add_points(user_id: int, amount: int):
    await _ensure_user_row(user_id)
    await db().execute("UPDATE points SET points = points + ? WHERE user_id = ?", (amount, user_id))
    await db().commit()


async def add_hours(user_id: int, amount: float):
    await _ensure_user_row(user_id)
    await db().execute("UPDATE points SET hours = hours + ? WHERE user_id = ?", (amount, user_id))
    await db().commit()


async def get_points_hours(user_id: int):
    cursor = await db().execute("SELECT points, hours FROM points WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    return row if row else (0, 0)


async def top_points_hours(limit: int = 10):
    cursor = await db().execute(
        "SELECT user_id, points, hours FROM points ORDER BY points DESC, hours DESC, user_id ASC LIMIT ?",
        (limit,),
    )
    return await cursor.fetchall()


async def award_hourly_session_points() -> list[tuple[int, int, int]]:
    now = int(time.time())
    cursor = await db().execute(
        "SELECT id, guild_id, user_id, last_hour_point_at FROM sessions WHERE logout_time IS NULL AND code_01 = 0"
    )
    rows = await cursor.fetchall()
    awarded: list[tuple[int, int, int]] = []
    for session_id, guild_id, user_id, last_point_at in rows:
        last = int(last_point_at or now)
        hours_due = max(0, (now - last) // 3600)
        if hours_due:
            await db().execute(
                "UPDATE sessions SET last_hour_point_at = ? WHERE id = ?",
                (last + hours_due * 3600, session_id),
            )
            await _ensure_user_row(user_id)
            await db().execute("UPDATE points SET points = points + ? WHERE user_id = ?", (hours_due, user_id))
            awarded.append((int(guild_id), int(user_id), int(hours_due)))
    await db().commit()
    return awarded


async def reset_all_points_hours():
    await db().execute("UPDATE points SET points = 0, hours = 0")
    await db().commit()


async def add_wing(name: str, role_id: int, emoji: str, description: str):
    await db().execute("INSERT OR REPLACE INTO wings (name, role_id, emoji, description) VALUES (?, ?, ?, ?)", (name, role_id, emoji, description))
    await db().commit()


async def delete_wing(name: str) -> bool:
    cursor = await db().execute("DELETE FROM wings WHERE name = ?", (name,))
    await db().commit()
    return cursor.rowcount > 0


async def list_wings():
    cursor = await db().execute("SELECT id, name, role_id, emoji, description FROM wings ORDER BY id")
    return await cursor.fetchall()


async def add_ticket_type(label: str, emoji: str, role_id: int):
    await db().execute("INSERT OR REPLACE INTO ticket_types (label, emoji, role_id) VALUES (?, ?, ?)", (label, emoji, role_id))
    await db().commit()


async def delete_ticket_type(label: str) -> bool:
    cursor = await db().execute("DELETE FROM ticket_types WHERE label = ?", (label,))
    await db().commit()
    return cursor.rowcount > 0


async def list_ticket_types():
    cursor = await db().execute("SELECT id, label, emoji, role_id FROM ticket_types ORDER BY id")
    return await cursor.fetchall()


async def create_ticket(channel_id: int, user_id: int, type_label: str):
    await db().execute("INSERT INTO tickets (channel_id, user_id, type_label, created_at) VALUES (?, ?, ?, ?)", (channel_id, user_id, type_label, int(time.time())))
    await db().commit()


async def close_ticket(channel_id: int):
    await db().execute("UPDATE tickets SET status = 'مغلقة' WHERE channel_id = ?", (channel_id,))
    await db().commit()


async def set_setting(key: str, value: str):
    await db().execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    await db().commit()


async def get_setting(key: str):
    cursor = await db().execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = await cursor.fetchone()
    return row[0] if row else None


async def clear_all_settings():
    await db().execute("DELETE FROM settings")
    await db().execute("DELETE FROM wings")
    await db().execute("DELETE FROM ticket_types")
    await db().execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('login_enabled', '1')")
    await db().commit()




async def add_clothing_item(name: str, description: str, image_url: str | None, emoji: str = "👮"):
    await db().execute(
        "INSERT OR REPLACE INTO clothing_items (name, description, image_url, emoji) VALUES (?, ?, ?, ?)",
        (name, description, image_url, emoji),
    )
    await db().commit()


async def delete_clothing_item(name: str) -> bool:
    cursor = await db().execute("DELETE FROM clothing_items WHERE name = ?", (name,))
    await db().commit()
    return cursor.rowcount > 0


async def list_clothing_items():
    cursor = await db().execute("SELECT id, name, description, image_url, emoji FROM clothing_items ORDER BY id")
    return await cursor.fetchall()


async def add_mdt_record(guild_id: int, record_type: str, character_id: str, officer_id: int, summary: str) -> int:
    cursor = await db().execute(
        "INSERT INTO mdt_records (guild_id, record_type, character_id, officer_id, summary, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (guild_id, record_type, character_id, officer_id, summary, int(time.time())),
    )
    await db().commit()
    return cursor.lastrowid


async def get_mdt_records(guild_id: int, character_id: str):
    cursor = await db().execute(
        "SELECT id, record_type, officer_id, summary, created_at FROM mdt_records "
        "WHERE guild_id = ? AND character_id = ? ORDER BY id DESC",
        (guild_id, character_id),
    )
    return await cursor.fetchall()


async def delete_mdt_record(record_id: int) -> bool:
    cursor = await db().execute("DELETE FROM mdt_records WHERE id = ?", (record_id,))
    await db().commit()
    return cursor.rowcount > 0
