"""Endpoint publik untuk kelompok mitra. Pola DDD: OPEN HOST SERVICE + PUBLISHED LANGUAGE.

Kontrak JSON berversi (/api/public/v1) dan hanya memuat pasangan Q&A konseptual per topic.
Tidak ada logika gatekeeper, hasil akhir, atau data pengguna yang keluar lewat sini.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from . import db
from .config import get_settings
from .security import partner_name
from .textutil import norm_topic

CONTRACT_VERSION = "1.0"

router = APIRouter(prefix="/api/public/v1", tags=["Public Q&A untuk mitra (OHS/PL)"])


class RateLimiter:
    """Jendela geser per kelompok mitra (in-memory; service ini berjalan 1 worker)."""

    def __init__(self, window: float = 60.0):
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()


limiter = RateLimiter()


def partner(name: str = Depends(partner_name)) -> str:
    if not limiter.allow(name, get_settings().partner_rate_per_min):
        raise HTTPException(status_code=429, detail="Batas pemanggilan terlampaui", headers={"Retry-After": "60"})
    return name


class QaItem(BaseModel):
    question: str
    answer: str


class QaOut(BaseModel):
    contract_version: str = CONTRACT_VERSION
    topic: str
    count: int
    items: list[QaItem]


class QuestionsOut(BaseModel):
    contract_version: str = CONTRACT_VERSION
    topic: str
    count: int
    questions: list[str]


class TopicItem(BaseModel):
    topic: str
    count: int


class TopicsOut(BaseModel):
    contract_version: str = CONTRACT_VERSION
    topics: list[TopicItem]


def _rows(topic: str, limit: int):
    with db.tx() as con:
        return con.execute(
            "SELECT question, answer FROM qa_pairs WHERE topic=? ORDER BY id DESC LIMIT ?", (norm_topic(topic), limit)
        ).fetchall()


@router.get("/qa", response_model=QaOut, summary="Pasangan Q&A konseptual per topic (untuk FAQ Sistem Materi Belajar)")
def qa(
    topic: str = Query(..., min_length=2, max_length=80, description="Kata kunci topic (tidak peka huruf besar/kecil)"),
    limit: int = Query(20, ge=1, le=50),
    _: str = Depends(partner),
):
    rows = _rows(topic, limit)
    return QaOut(topic=norm_topic(topic), count=len(rows), items=[QaItem(**dict(r)) for r in rows])


@router.get("/questions", response_model=QuestionsOut, summary="Daftar pertanyaan per topic (pemantik diskusi Siaran Belajar)")
def questions(
    topic: str = Query(..., min_length=2, max_length=80),
    limit: int = Query(20, ge=1, le=50),
    _: str = Depends(partner),
):
    rows = _rows(topic, limit)
    return QuestionsOut(topic=norm_topic(topic), count=len(rows), questions=[r["question"] for r in rows])


@router.get("/topics", response_model=TopicsOut, summary="Topic yang punya Q&A, untuk pencocokan dengan topic mitra")
def topics(limit: int = Query(50, ge=1, le=100), _: str = Depends(partner)):
    with db.tx() as con:
        rows = con.execute(
            "SELECT topic, COUNT(*) AS n FROM qa_pairs GROUP BY topic ORDER BY n DESC, topic LIMIT ?", (limit,)
        ).fetchall()
    return TopicsOut(topics=[TopicItem(topic=r["topic"], count=r["n"]) for r in rows])
