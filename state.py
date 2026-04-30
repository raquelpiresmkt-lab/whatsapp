from __future__ import annotations

import aiosqlite
from enum import Enum
from typing import Optional


class Stage(str, Enum):
    LEAD = "lead"
    QUALIFY = "qualified"
    PURCHASE = "purchase"


STAGE_ORDER = {Stage.LEAD: 0, Stage.QUALIFY: 1, Stage.PURCHASE: 2}
STAGE_COLUMN = {Stage.LEAD: "lead_fired_at", Stage.QUALIFY: "qualify_fired_at", Stage.PURCHASE: "purchase_fired_at"}


async def init_db(path: str = "database.db") -> aiosqlite.Connection:
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_phone    TEXT NOT NULL,
            saleswoman_phone TEXT NOT NULL,
            current_stage    TEXT NOT NULL DEFAULT 'lead',
            lead_fired_at    INTEGER,
            qualify_fired_at INTEGER,
            purchase_fired_at INTEGER,
            purchase_value   REAL DEFAULT 0.0,
            created_at       INTEGER DEFAULT (unixepoch()),
            updated_at       INTEGER DEFAULT (unixepoch())
        )
    """)
    await conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_active_conv
        ON conversations(contact_phone, saleswoman_phone)
        WHERE current_stage != 'purchase'
    """)
    await conn.commit()
    return conn


async def get_active_conversation(conn: aiosqlite.Connection, contact: str, saleswoman: str) -> Optional[dict]:
    async with conn.execute(
        "SELECT * FROM conversations WHERE contact_phone=? AND saleswoman_phone=? AND current_stage != 'purchase' ORDER BY id DESC LIMIT 1",
        (contact, saleswoman)
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def advance_stage(
    conn: aiosqlite.Connection,
    contact: str,
    saleswoman: str,
    stage: Stage,
    event_ts: int,
    value: float,
) -> bool:
    conv = await get_active_conversation(conn, contact, saleswoman)

    if stage == Stage.LEAD:
        if conv is not None:
            return False
        await conn.execute(
            "INSERT INTO conversations (contact_phone, saleswoman_phone, current_stage, lead_fired_at) VALUES (?,?,?,?)",
            (contact, saleswoman, Stage.LEAD.value, event_ts)
        )
        await conn.commit()
        return True

    if conv is None:
        return False

    current_order = STAGE_ORDER.get(Stage(conv["current_stage"]), -1)
    new_order = STAGE_ORDER[stage]
    if new_order <= current_order:
        return False

    ts_col = STAGE_COLUMN[stage]
    new_stage = stage.value

    if stage == Stage.PURCHASE:
        await conn.execute(
            f"UPDATE conversations SET current_stage=?, {ts_col}=?, purchase_value=?, updated_at=unixepoch() WHERE id=?",
            (new_stage, event_ts, value, conv["id"])
        )
    else:
        await conn.execute(
            f"UPDATE conversations SET current_stage=?, {ts_col}=?, updated_at=unixepoch() WHERE id=?",
            (new_stage, event_ts, conv["id"])
        )

    await conn.commit()
    return True


async def get_weekly_stats(conn: aiosqlite.Connection, since_ts: int) -> list[dict]:
    async with conn.execute("""
        SELECT
            saleswoman_phone,
            COUNT(*) as leads,
            SUM(CASE WHEN current_stage IN ('qualified','purchase') THEN 1 ELSE 0 END) as qualified,
            SUM(CASE WHEN current_stage = 'purchase' THEN 1 ELSE 0 END) as purchases,
            COALESCE(SUM(CASE WHEN current_stage = 'purchase' THEN purchase_value ELSE 0 END), 0) as revenue
        FROM conversations
        WHERE created_at >= ?
        GROUP BY saleswoman_phone
    """, (since_ts,)) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
