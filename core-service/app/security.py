"""Konteks Autentikasi & Akses API (GENERIC): JWT untuk pengguna app, X-API-Key untuk mitra."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from . import db
from .config import get_settings

_ITERATIONS = 120_000

bearer_scheme = HTTPBearer(auto_error=False, description="JWT dari POST /api/auth/login")
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False, description="API key kelompok mitra")


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS)
    return salt, digest.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    _, actual = hash_password(password, salt)
    return hmac.compare_digest(actual, expected_hash)


def create_token(user_id: int) -> str:
    s = get_settings()
    now = int(time.time())
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + s.jwt_ttl_seconds},
        s.jwt_secret,
        algorithm="HS256",
    )


def _unauthorized(msg: str, scheme: str) -> HTTPException:
    return HTTPException(status_code=401, detail=msg, headers={"WWW-Authenticate": scheme})


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> sqlite3.Row:
    """Pengguna aplikasi mobile yang sudah login (JWT Bearer)."""
    if creds is None:
        raise _unauthorized("Token tidak ada", "Bearer")
    try:
        payload = jwt.decode(
            creds.credentials,
            get_settings().jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        raise _unauthorized("Token tidak valid atau kedaluwarsa", "Bearer")
    with db.tx() as con:
        user = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if user is None:
        raise _unauthorized("Pengguna tidak ditemukan", "Bearer")
    return user


def partner_name(key: str | None = Depends(api_key_scheme)) -> str:
    """Kelompok mitra yang memanggil server-ke-server (X-API-Key). Mengembalikan namanya."""
    if not key:
        raise _unauthorized("X-API-Key tidak ada", "ApiKey")
    found: str | None = None
    for name, expected in get_settings().api_keys.items():
        if hmac.compare_digest(key.encode(), expected.encode()):
            found = name
    if found is None:
        raise _unauthorized("X-API-Key tidak valid", "ApiKey")
    return found
