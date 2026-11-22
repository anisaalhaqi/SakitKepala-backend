"""Akses SQLite. Database ini milik service (tidak ada port DB yang dibuka ke luar)."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id         INTEGER PRIMARY KEY,
  email      TEXT NOT NULL UNIQUE,
  salt       TEXT NOT NULL,
  pwd_hash   TEXT NOT NULL,
  tier       TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free','pro')),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Konteks Kuota & Langganan: pemakaian sesi per pengguna per hari (WIB)
CREATE TABLE IF NOT EXISTS usage (
  user_id  INTEGER NOT NULL REFERENCES users(id),
  day      TEXT NOT NULL,
  sessions INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, day)
);

-- Konteks Validasi Pemahaman
CREATE TABLE IF NOT EXISTS sessions (
  id            TEXT PRIMARY KEY,
  user_id       INTEGER NOT NULL REFERENCES users(id),
  topic         TEXT NOT NULL,
  question      TEXT NOT NULL,
  explanation   TEXT NOT NULL,
  final_result  TEXT NOT NULL,          -- ditahan di backend; hanya keluar bila UNLOCKED
  key_points    TEXT NOT NULL,          -- JSON list
  status        TEXT NOT NULL DEFAULT 'LOCKED' CHECK (status IN ('LOCKED','UNLOCKED')),
  attempts_used INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, created_at);

CREATE TABLE IF NOT EXISTS checkpoints (
  id         INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  attempt_no INTEGER NOT NULL,
  summary    TEXT NOT NULL,
  passed     INTEGER NOT NULL,
  feedback   TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS proof_of_learning (
  id         INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL UNIQUE REFERENCES sessions(id),
  user_id    INTEGER NOT NULL REFERENCES users(id),
  topic      TEXT NOT NULL,
  attempt_no INTEGER NOT NULL,
  passed_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Kurasi pasangan Q&A konseptual per topic (aset yang dibuka lewat OHS/PL)
CREATE TABLE IF NOT EXISTS qa_pairs (
  id         INTEGER PRIMARY KEY,
  topic      TEXT NOT NULL,
  question   TEXT NOT NULL,
  answer     TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (topic, question)
);
CREATE INDEX IF NOT EXISTS idx_qa_topic ON qa_pairs(topic, id);
"""


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(get_settings().db_path, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """Satu transaksi; rollback otomatis kalau ada exception (termasuk HTTPException)."""
    con = connect()
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    path = get_settings().db_path
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    con = connect()
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def iso(ts: str) -> str:
    """'2026-11-22 10:00:00' (UTC dari SQLite) -> '2026-11-22T10:00:00Z'."""
    return ts.replace(" ", "T") + "Z"
