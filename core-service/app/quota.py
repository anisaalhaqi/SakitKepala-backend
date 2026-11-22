"""Konteks Kuota & Langganan (SUPPORTING): freemium.

Free : maks FREE_DAILY_QUOTA sesi/hari (default 5), validasi pemahaman standar, bisa salin hasil.
Pro  : sesi tanpa batas harian + ekspor hasil akhir beserta catatan pemahaman.

Konteks Validasi Pemahaman (downstream, customer-supplier) hanya bertanya lewat fungsi
`status`, `try_consume`, dan `can_export` di sini. Tabel `usage` tidak disentuh konteks lain.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import db
from .config import get_settings
from .security import current_user

WIB = timezone(timedelta(hours=7))  # WIB tidak mengenal DST

router = APIRouter(prefix="/api/subscription", tags=["Kuota & Langganan (supporting)"])


class QuotaStatus(BaseModel):
    tier: str
    limit: int | None  # None = tanpa batas (Pro)
    used: int
    remaining: int | None


def today_wib() -> str:
    return datetime.now(WIB).strftime("%Y-%m-%d")


def status(con: sqlite3.Connection, user: sqlite3.Row) -> QuotaStatus:
    row = con.execute(
        "SELECT sessions FROM usage WHERE user_id=? AND day=?", (user["id"], today_wib())
    ).fetchone()
    used = row[0] if row else 0
    if user["tier"] == "pro":
        return QuotaStatus(tier="pro", limit=None, used=used, remaining=None)
    limit = get_settings().free_daily_quota
    return QuotaStatus(tier="free", limit=limit, used=used, remaining=max(0, limit - used))


def try_consume(con: sqlite3.Connection, user: sqlite3.Row) -> bool:
    """Pakai satu kuota secara atomik. False bila kuota harian Free sudah habis."""
    day = today_wib()
    if user["tier"] == "pro":
        con.execute(
            "INSERT INTO usage(user_id, day, sessions) VALUES(?,?,1) "
            "ON CONFLICT(user_id, day) DO UPDATE SET sessions = sessions + 1",
            (user["id"], day),
        )
        return True
    cur = con.execute(
        "INSERT INTO usage(user_id, day, sessions) VALUES(?,?,1) "
        "ON CONFLICT(user_id, day) DO UPDATE SET sessions = sessions + 1 WHERE usage.sessions < ?",
        (user["id"], day, get_settings().free_daily_quota),
    )
    return cur.rowcount == 1


def can_export(user: sqlite3.Row) -> bool:
    return user["tier"] == "pro"


# ---------------------------------------------------------------- endpoint


@router.get("", response_model=QuotaStatus)
def my_subscription(user=Depends(current_user)):
    with db.tx() as con:
        return status(con, user)


def _set_tier(user: sqlite3.Row, tier: str) -> QuotaStatus:
    if not get_settings().subscription_simulation:
        raise HTTPException(status_code=403, detail="Perubahan paket hanya lewat sistem pembayaran")
    with db.tx() as con:
        con.execute("UPDATE users SET tier=? WHERE id=?", (tier, user["id"]))
        fresh = con.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        return status(con, fresh)


@router.post("/upgrade", response_model=QuotaStatus)
def upgrade(user=Depends(current_user)):
    """SIMULASI pembayaran: langsung mengaktifkan Pro. Matikan dengan SUBSCRIPTION_SIMULATION=false."""
    return _set_tier(user, "pro")


@router.post("/downgrade", response_model=QuotaStatus)
def downgrade(user=Depends(current_user)):
    """SIMULASI: kembali ke Free."""
    return _set_tier(user, "free")
