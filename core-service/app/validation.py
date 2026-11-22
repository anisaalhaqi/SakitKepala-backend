"""Konteks Validasi Pemahaman (CORE): gatekeeper LOCKED/UNLOCKED, logic checkpoint (maks. N percobaan),
riwayat proof-of-learning, dan kurasi Q&A konseptual per topic.

Aturan domain utama: aplikasi mobile TIDAK PERNAH menerima `final_result` sebelum status UNLOCKED.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints

from . import ai_client, db, quota
from .config import get_settings
from .quota import QuotaStatus
from .security import current_user
from .textutil import copy_ratio, norm_topic

LOCKED = "LOCKED"
UNLOCKED = "UNLOCKED"
COPY_THRESHOLD = 0.6  # >= 60% potongan 5-kata identik dengan penjelasan = salinan mentah
QA_PER_TOPIC_CAP = 200  # jaga ukuran DB di microSD

router = APIRouter(prefix="/api", tags=["Validasi Pemahaman (core)"])

Topic = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)]
Summary = Annotated[str, StringConstraints(strip_whitespace=True, min_length=30, max_length=2000)]


class SessionCreate(BaseModel):
    topic: Topic
    question: Question


class CheckpointIn(BaseModel):
    summary: Summary


class SessionOut(BaseModel):
    session_id: str
    topic: str
    question: str
    status: str
    explanation: str
    attempts_left: int
    copy_enabled: bool
    export_enabled: bool
    final_result: str | None = None  # hanya terisi bila UNLOCKED
    created_at: str
    quota: QuotaStatus | None = None  # (nama field `quota` membayangi modul `quota` di dalam kelas ini)


class SessionSummary(BaseModel):
    session_id: str
    topic: str
    status: str
    attempts_left: int
    created_at: str


class CheckpointOut(BaseModel):
    passed: bool
    status: str
    attempts_left: int
    locked_final: bool  # True = percobaan habis, hasil tetap terkunci
    feedback: str
    final_result: str | None = None
    export_enabled: bool


class ProofOut(BaseModel):
    session_id: str
    topic: str
    attempt_no: int
    passed_at: str


class ExportOut(BaseModel):
    session_id: str
    topic: str
    question: str
    explanation: str
    final_result: str
    understanding_notes: str
    proof_of_learning: ProofOut


# ------------------------------------------------------------------ logika domain


def evaluate(session: sqlite3.Row, summary: str) -> tuple[bool, str]:
    """Apakah tulisan pengguna mencerminkan pemahaman (bukan salinan mentah penjelasan)?"""
    if copy_ratio(summary, session["explanation"]) >= COPY_THRESHOLD:
        return False, "Tulisanmu terlalu mirip dengan penjelasan. Tulis ulang intisarinya dengan kata-katamu sendiri."
    return ai_client.judge(session["explanation"], json.loads(session["key_points"]), summary)


def attempts_left(row: sqlite3.Row) -> int:
    return max(0, get_settings().max_attempts - row["attempts_used"])


def load_own_session(sid: str, user: sqlite3.Row) -> sqlite3.Row:
    with db.tx() as con:
        row = con.execute("SELECT * FROM sessions WHERE id=? AND user_id=?", (sid, user["id"])).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")
    return row


def _session_out(row: sqlite3.Row, user: sqlite3.Row, quota_status: quota.QuotaStatus | None = None) -> SessionOut:
    unlocked = row["status"] == UNLOCKED
    return SessionOut(
        session_id=row["id"],
        topic=row["topic"],
        question=row["question"],
        status=row["status"],
        explanation=row["explanation"],
        attempts_left=attempts_left(row),
        copy_enabled=unlocked,
        export_enabled=unlocked and quota.can_export(user),
        final_result=row["final_result"] if unlocked else None,
        created_at=db.iso(row["created_at"]),
        quota=quota_status,
    )


def _quota_exceeded(q: quota.QuotaStatus) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={
            "code": "QUOTA_EXCEEDED",
            "message": f"Kuota harian paket Free ({q.limit} sesi) habis. Coba lagi besok atau upgrade ke Pro.",
            "limit": q.limit,
        },
    )


# ------------------------------------------------------------------ endpoint


@router.post("/sessions", status_code=201, response_model=SessionOut)
def create_session(body: SessionCreate, user=Depends(current_user)):
    """Mulai sesi: penjelasan tampil terbuka, hasil akhir ditahan (LOCKED)."""
    topic = norm_topic(body.topic)

    with db.tx() as con:  # tolak lebih awal sebelum membayar panggilan AI
        q = quota.status(con, user)
    if q.remaining == 0:
        raise _quota_exceeded(q)

    try:
        result = ai_client.generate(topic, body.question)
    except ai_client.AiError:
        raise HTTPException(status_code=503, detail="Layanan AI sedang tidak tersedia. Kuota tidak terpakai.")

    sid = uuid.uuid4().hex
    with db.tx() as con:
        if not quota.try_consume(con, user):  # cek ulang atomik (menutup race antar-request)
            raise _quota_exceeded(quota.status(con, user))
        con.execute(
            "INSERT INTO sessions(id, user_id, topic, question, explanation, final_result, key_points) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                sid,
                user["id"],
                topic,
                body.question,
                result.explanation,
                result.final_result,
                json.dumps(result.key_points, ensure_ascii=False),
            ),
        )
        for qq, aa in result.qa_pairs:  # kurasi Q&A konseptual per topic (tanpa data pengguna)
            con.execute("INSERT OR IGNORE INTO qa_pairs(topic, question, answer) VALUES(?,?,?)", (topic, qq, aa))
        con.execute(
            "DELETE FROM qa_pairs WHERE topic=? AND id NOT IN "
            "(SELECT id FROM qa_pairs WHERE topic=? ORDER BY id DESC LIMIT ?)",
            (topic, topic, QA_PER_TOPIC_CAP),
        )
        row = con.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        q_after = quota.status(con, user)
    return _session_out(row, user, q_after)


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(user=Depends(current_user)):
    with db.tx() as con:
        rows = con.execute(
            "SELECT * FROM sessions WHERE user_id=? ORDER BY created_at DESC, rowid DESC LIMIT 50", (user["id"],)
        ).fetchall()
    return [
        SessionSummary(
            session_id=r["id"],
            topic=r["topic"],
            status=r["status"],
            attempts_left=attempts_left(r),
            created_at=db.iso(r["created_at"]),
        )
        for r in rows
    ]


@router.get("/sessions/{sid}", response_model=SessionOut)
def get_session(sid: str, user=Depends(current_user)):
    return _session_out(load_own_session(sid, user), user)


@router.post("/sessions/{sid}/checkpoint", response_model=CheckpointOut)
def checkpoint(sid: str, body: CheckpointIn, user=Depends(current_user)):
    """Logic checkpoint: tulis ulang intisari pemahaman. Lolos -> UNLOCKED; gagal -> kurangi percobaan."""
    s = get_settings()
    session = load_own_session(sid, user)
    if session["status"] == UNLOCKED:
        raise HTTPException(status_code=409, detail={"code": "ALREADY_UNLOCKED", "message": "Sesi sudah terbuka"})

    # 1) Pesan satu percobaan secara atomik (tanpa menahan lock DB selama menilai)
    with db.tx() as con:
        cur = con.execute(
            "UPDATE sessions SET attempts_used = attempts_used + 1 "
            "WHERE id=? AND status='LOCKED' AND attempts_used < ?",
            (sid, s.max_attempts),
        )
        if cur.rowcount == 0:
            raise HTTPException(
                status_code=409,
                detail={"code": "ATTEMPTS_EXHAUSTED", "message": "Percobaan habis; hasil akhir tetap terkunci."},
            )
        attempt_no = con.execute("SELECT attempts_used FROM sessions WHERE id=?", (sid,)).fetchone()[0]

    # 2) Nilai. Bila penilai AI gagal, percobaan dikembalikan (bukan salah pengguna).
    try:
        passed, feedback = evaluate(session, body.summary)
    except ai_client.AiError:
        with db.tx() as con:
            con.execute("UPDATE sessions SET attempts_used = attempts_used - 1 WHERE id=?", (sid,))
        raise HTTPException(status_code=503, detail="Penilai AI sedang tidak tersedia. Percobaan tidak dihitung.")

    # 3) Catat hasil
    with db.tx() as con:
        con.execute(
            "INSERT INTO checkpoints(session_id, attempt_no, summary, passed, feedback) VALUES(?,?,?,?,?)",
            (sid, attempt_no, body.summary, 1 if passed else 0, feedback),
        )
        if passed:
            con.execute("UPDATE sessions SET status='UNLOCKED' WHERE id=?", (sid,))
            con.execute(
                "INSERT OR IGNORE INTO proof_of_learning(session_id, user_id, topic, attempt_no) VALUES(?,?,?,?)",
                (sid, user["id"], session["topic"], attempt_no),
            )

    left = max(0, s.max_attempts - attempt_no)
    return CheckpointOut(
        passed=passed,
        status=UNLOCKED if passed else LOCKED,
        attempts_left=left,
        locked_final=(not passed and left == 0),
        feedback=feedback,
        final_result=session["final_result"] if passed else None,
        export_enabled=passed and quota.can_export(user),
    )


@router.get("/sessions/{sid}/export", response_model=ExportOut)
def export_session(sid: str, user=Depends(current_user)):
    """Ekspor hasil akhir + catatan pemahaman. Syarat: UNLOCKED dan paket Pro."""
    session = load_own_session(sid, user)
    if session["status"] != UNLOCKED:
        raise HTTPException(status_code=403, detail={"code": "LOCKED", "message": "Selesaikan logic checkpoint dulu."})
    if not quota.can_export(user):
        raise HTTPException(status_code=403, detail={"code": "PRO_REQUIRED", "message": "Ekspor tersedia di paket Pro."})
    with db.tx() as con:
        note = con.execute(
            "SELECT summary FROM checkpoints WHERE session_id=? AND passed=1 ORDER BY id DESC LIMIT 1", (sid,)
        ).fetchone()
        proof = con.execute("SELECT * FROM proof_of_learning WHERE session_id=?", (sid,)).fetchone()
    return ExportOut(
        session_id=sid,
        topic=session["topic"],
        question=session["question"],
        explanation=session["explanation"],
        final_result=session["final_result"],
        understanding_notes=note["summary"] if note else "",
        proof_of_learning=ProofOut(
            session_id=sid, topic=proof["topic"], attempt_no=proof["attempt_no"], passed_at=db.iso(proof["passed_at"])
        ),
    )


@router.get("/proof-of-learning", response_model=list[ProofOut])
def proof_of_learning(user=Depends(current_user)):
    with db.tx() as con:
        rows = con.execute(
            "SELECT * FROM proof_of_learning WHERE user_id=? ORDER BY id DESC LIMIT 100", (user["id"],)
        ).fetchall()
    return [
        ProofOut(session_id=r["session_id"], topic=r["topic"], attempt_no=r["attempt_no"], passed_at=db.iso(r["passed_at"]))
        for r in rows
    ]
