"""Entry point FastAPI. Semua rute di bawah /api agar cocok dengan Base URL https://<nama>.stei.fun/api."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from . import acl, auth_routes, db, public_api, quota, validation
from .config import get_settings

log = logging.getLogger("ujiparham")

DESCRIPTION = """
Core service **Uji Paham Belajar**: AI sebagai pendamping belajar, bukan penyedia jawaban instan.

* **Autentikasi**: pengguna app memakai `Authorization: Bearer <JWT>`; kelompok mitra memakai `X-API-Key`.
* **Alur utama**: `POST /sessions` -> baca penjelasan -> `POST /sessions/{id}/checkpoint` -> hasil akhir terbuka.
* **Untuk kelompok mitra**: endpoint `/public/v1/*` (Q&A konseptual per topic).
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()  # gagal cepat bila konfigurasi salah
    db.init_db()
    if s.ai_provider == "mock":
        log.warning("AI_PROVIDER=mock: hanya untuk pengembangan. Ganti ke 'http' sebelum demo/penilaian.")
    yield


app = FastAPI(
    title="Uji Paham Belajar - Core Service",
    version="1.0.0",
    description=DESCRIPTION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
    lifespan=lifespan,
)

app.include_router(auth_routes.router)
app.include_router(quota.router)
app.include_router(validation.router)
app.include_router(acl.router)
app.include_router(public_api.router)


@app.get("/api/health", tags=["Health"])
def health():
    try:
        with db.tx() as con:
            con.execute("SELECT 1").fetchone()
    except Exception:
        raise HTTPException(status_code=503, detail="database tidak bisa diakses")
    return {"status": "ok", "service": "ujiparham-core", "version": app.version}
