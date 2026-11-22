"""Endpoint autentikasi pengguna aplikasi mobile (konteks Autentikasi & Akses API)."""
from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints

from . import db
from .config import get_settings
from .security import create_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Autentikasi (generic)"])

Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class Credentials(BaseModel):
    email: Email
    password: Password


class RegisterOut(BaseModel):
    id: int
    email: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeOut(BaseModel):
    id: int
    email: str
    tier: str


@router.post("/register", status_code=201, response_model=RegisterOut)
def register(body: Credentials):
    salt, pwd_hash = hash_password(body.password)
    try:
        with db.tx() as con:
            cur = con.execute(
                "INSERT INTO users(email, salt, pwd_hash) VALUES(?,?,?)", (body.email, salt, pwd_hash)
            )
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email sudah terdaftar")
    return RegisterOut(id=user_id, email=body.email)


@router.post("/login", response_model=TokenOut)
def login(body: Credentials):
    with db.tx() as con:
        user = con.execute("SELECT * FROM users WHERE email=?", (body.email,)).fetchone()
    if user is None:
        hash_password(body.password)  # samakan waktu respons agar email tidak bisa ditebak
        raise HTTPException(status_code=401, detail="Email atau password salah")
    if not verify_password(body.password, user["salt"], user["pwd_hash"]):
        raise HTTPException(status_code=401, detail="Email atau password salah")
    return TokenOut(access_token=create_token(user["id"]), expires_in=get_settings().jwt_ttl_seconds)


@router.get("/me", response_model=MeOut)
def me(user=Depends(current_user)):
    return MeOut(id=user["id"], email=user["email"], tier=user["tier"])
