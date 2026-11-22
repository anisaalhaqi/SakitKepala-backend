"""Konfigurasi dari environment variable. Semua rahasia hanya dari .env, tidak pernah di kode."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


def parse_api_keys(raw: str) -> dict[str, str]:
    """Format: 'siaran-belajar:key1,materi-belajar:key2' -> {nama: key}.

    Satu API key per kelompok mitra supaya mudah dicabut kalau disalahgunakan.
    """
    keys: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise RuntimeError("API_KEYS harus berformat nama:key,nama2:key2")
        name, key = (p.strip() for p in part.split(":", 1))
        if name and key:
            keys[name] = key
    return keys


@dataclass(frozen=True)
class Settings:
    db_path: str
    jwt_secret: str
    jwt_ttl_seconds: int
    api_keys: dict[str, str]
    partner_rate_per_min: int
    # Konteks Kuota & Langganan
    free_daily_quota: int
    subscription_simulation: bool
    # Konteks Validasi Pemahaman
    max_attempts: int
    # Layanan AI eksternal (conformist)
    ai_provider: str  # "mock" (dev/test) | "http" (API kompatibel OpenAI chat completions)
    ai_api_url: str
    ai_api_key: str
    ai_model: str
    ai_timeout: float
    # ACL ke kelompok mitra (opsional)
    partners_enabled: bool
    partner_timeout: float
    partner_cache_ttl: int
    siaran_base_url: str
    siaran_path: str
    siaran_api_key: str
    materi_base_url: str
    materi_path: str
    materi_api_key: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    secret = os.environ.get("JWT_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET wajib diisi (min. 32 karakter). Buat dengan: openssl rand -hex 32")

    provider = os.getenv("AI_PROVIDER", "mock").strip().lower()
    if provider not in {"mock", "http"}:
        raise RuntimeError("AI_PROVIDER harus 'mock' atau 'http'")

    s = Settings(
        db_path=os.getenv("DB_PATH", "/data/app.db"),
        jwt_secret=secret,
        jwt_ttl_seconds=int(os.getenv("JWT_TTL_SECONDS", "3600")),
        api_keys=parse_api_keys(os.getenv("API_KEYS", "")),
        partner_rate_per_min=int(os.getenv("PARTNER_RATE_PER_MIN", "60")),
        free_daily_quota=int(os.getenv("FREE_DAILY_QUOTA", "5")),
        subscription_simulation=_bool("SUBSCRIPTION_SIMULATION", True),
        max_attempts=int(os.getenv("MAX_ATTEMPTS", "3")),
        ai_provider=provider,
        ai_api_url=os.getenv("AI_API_URL", ""),
        ai_api_key=os.getenv("AI_API_KEY", ""),
        ai_model=os.getenv("AI_MODEL", ""),
        ai_timeout=float(os.getenv("AI_TIMEOUT", "30")),
        partners_enabled=_bool("PARTNERS_ENABLED", False),
        partner_timeout=float(os.getenv("PARTNER_TIMEOUT", "4")),
        partner_cache_ttl=int(os.getenv("PARTNER_CACHE_TTL", "300")),
        siaran_base_url=os.getenv("PARTNER_SIARAN_BASE_URL", ""),
        siaran_path=os.getenv("PARTNER_SIARAN_PATH", "/sessions?topic={topic}"),
        siaran_api_key=os.getenv("PARTNER_SIARAN_API_KEY", ""),
        materi_base_url=os.getenv("PARTNER_MATERI_BASE_URL", ""),
        materi_path=os.getenv("PARTNER_MATERI_PATH", "/materials?topic={topic}"),
        materi_api_key=os.getenv("PARTNER_MATERI_API_KEY", ""),
    )
    if provider == "http" and not (s.ai_api_url and s.ai_api_key and s.ai_model):
        raise RuntimeError("AI_PROVIDER=http membutuhkan AI_API_URL, AI_API_KEY, dan AI_MODEL")
    if s.free_daily_quota < 1 or s.max_attempts < 1:
        raise RuntimeError("FREE_DAILY_QUOTA dan MAX_ATTEMPTS minimal 1")
    return s
