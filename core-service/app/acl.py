"""Anti-Corruption Layer ke Sistem Siaran Belajar dan Sistem Materi Belajar (kelompok mitra).

Format JSON mitra diterjemahkan ke struktur internal kita, jadi perubahan skema mitra tidak
menjalar ke konteks Validasi Pemahaman. Mitra mati/kosong => layanan inti tetap jalan
(timeout pendek + cache + status yang jelas), sesuai aturan "tahan gangguan".

Dimatikan secara default (PARTNERS_ENABLED=false). Dokumen tugas meminta layanan integrasi
(Tugas 3) tidak berjalan di STB; modul ini bisa dipindahkan utuh ke layanan integrasi di server lain.
Path endpoint mitra di env harus disesuaikan dengan kontrak mereka (OpenAPI/Postman di API Registry).
"""
from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Callable
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .config import get_settings
from .security import current_user
from .validation import load_own_session

MAX_ITEMS = 5
_TRANSPORT: httpx.BaseTransport | None = None  # diisi test untuk mock mitra


# --------------------------------------------------------------- penerjemah (ACL)


def _unwrap(payload: Any) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "items", "results", "sessions", "materials", "materi"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def _s(value: Any, limit: int = 300) -> str:
    if value is None or isinstance(value, (dict, list)):
        return ""
    return str(value).strip()[:limit]


def _first(d: dict, *keys: str) -> Any:
    for k in keys:
        if d.get(k):
            return d[k]
    return None


def _tags(value: Any) -> list[str]:
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        return []
    return [t for t in (_s(x, 40) for x in value) if t][:8]


def translate_live_sessions(payload: Any) -> list[dict]:
    """Metadata sesi siaran: title (wajib), description, tags (opsional)."""
    out = []
    for item in _unwrap(payload):
        if not isinstance(item, dict):
            continue
        title = _s(_first(item, "title", "judul", "name"))
        if not title:
            continue
        out.append(
            {
                "title": title,
                "description": _s(_first(item, "description", "deskripsi"), 500),
                "tags": _tags(_first(item, "tags", "tag")),
            }
        )
    return out[:MAX_ITEMS]


def translate_materials(payload: Any) -> list[dict]:
    """Referensi materi: title (wajib), url (hanya http/https), summary."""
    out = []
    for item in _unwrap(payload):
        if not isinstance(item, dict):
            continue
        title = _s(_first(item, "title", "judul", "name"))
        if not title:
            continue
        url = _s(_first(item, "url", "link", "href"), 500)
        out.append(
            {
                "title": title,
                "url": url if url.startswith(("http://", "https://")) else "",
                "summary": _s(_first(item, "summary", "ringkasan", "description", "deskripsi"), 500),
            }
        )
    return out[:MAX_ITEMS]


# --------------------------------------------------------------- klien mitra


class PartnerClient:
    def __init__(self, base_url: str, path: str, api_key: str, translate: Callable[[Any], list[dict]]):
        self.base_url, self.path, self.api_key, self.translate = base_url, path, api_key, translate
        self._cache: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()

    def fetch(self, topic: str) -> dict:
        s = get_settings()
        if not s.partners_enabled or not self.base_url:
            return {"status": "disabled", "items": []}

        now = time.monotonic()
        hit = self._cache.get(topic)
        if hit and now - hit[0] < s.partner_cache_ttl:
            return {"status": "ok" if hit[1] else "empty", "items": hit[1]}

        url = self.base_url.rstrip("/") + self.path.replace("{topic}", quote(topic, safe=""))
        headers = {"Accept": "application/json", "User-Agent": "UjiParhamBelajar/1.0"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        try:
            with httpx.Client(timeout=s.partner_timeout, transport=_TRANSPORT) as client:
                resp = client.get(url, headers=headers)
            resp.raise_for_status()
            items = self.translate(resp.json())
        except (httpx.HTTPError, ValueError):
            if hit:  # mitra mati: pakai data lama daripada kosong
                return {"status": "stale", "items": hit[1]}
            return {"status": "unavailable", "items": []}

        self._cache[topic] = (now, items)
        self._cache.move_to_end(topic)
        while len(self._cache) > 128:
            self._cache.popitem(last=False)
        return {"status": "ok" if items else "empty", "items": items}


_clients: dict[str, PartnerClient] | None = None


def reset_clients() -> None:
    global _clients
    _clients = None


def get_clients() -> dict[str, PartnerClient]:
    global _clients
    if _clients is None:
        s = get_settings()
        _clients = {
            "live_sessions": PartnerClient(s.siaran_base_url, s.siaran_path, s.siaran_api_key, translate_live_sessions),
            "materials": PartnerClient(s.materi_base_url, s.materi_path, s.materi_api_key, translate_materials),
        }
    return _clients


# --------------------------------------------------------------- endpoint

router = APIRouter(prefix="/api", tags=["Referensi mitra (ACL)"])


class PartnerBlock(BaseModel):
    status: str  # ok | empty | stale | unavailable | disabled
    items: list[dict]


class ReferencesOut(BaseModel):
    topic: str
    live_sessions: PartnerBlock
    materials: PartnerBlock


@router.get("/sessions/{sid}/references", response_model=ReferencesOut)
def references(sid: str, user=Depends(current_user)):
    """Sesi siaran + materi terkait topic sesi. Selalu 200; kegagalan mitra hanya tampil di `status`."""
    session = load_own_session(sid, user)
    clients = get_clients()
    return ReferencesOut(
        topic=session["topic"],
        live_sessions=PartnerBlock(**clients["live_sessions"].fetch(session["topic"])),
        materials=PartnerBlock(**clients["materials"].fetch(session["topic"])),
    )
