#!/usr/bin/env python3
"""Smoke test end-to-end terhadap URL publik. Jalankan dari LAPTOP/HP (di luar STB).

    python scripts/smoke_test.py https://ujiparham.stei.fun --api-key KEY_MITRA

Hanya memakai pustaka standar. Membuat satu akun uji acak, satu sesi, dan satu percobaan checkpoint
yang sengaja salinan mentah (harus ditolak). Tidak memerlukan AI_PROVIDER tertentu.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
import urllib.error
import urllib.request

failures = 0


def call(method: str, url: str, body: dict | None = None, headers: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", "TugasBesar-TST/1.0 (smoke-test)")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as err:
        try:
            return err.code, json.loads(err.read() or b"null")
        except ValueError:
            return err.code, None


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    print(f"[{'OK ' if ok else 'GAGAL'}] {name}" + (f"  -> {detail}" if detail and not ok else ""))
    if not ok:
        failures += 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base", help="mis. https://ujiparham.stei.fun")
    ap.add_argument("--api-key", help="X-API-Key milik salah satu kelompok mitra")
    args = ap.parse_args()
    api = args.base.rstrip("/") + "/api"

    st, body = call("GET", f"{api}/health")
    check("health 200", st == 200 and body and body.get("status") == "ok", f"{st} {body}")

    st, _ = call("GET", f"{api}/sessions")
    check("tanpa token -> 401", st == 401, str(st))

    email, pwd = f"smoke-{secrets.token_hex(4)}@example.com", "Rahasia-" + secrets.token_hex(4)
    st, _ = call("POST", f"{api}/auth/register", {"email": email, "password": pwd})
    check("register 201", st == 201, str(st))
    st, tok = call("POST", f"{api}/auth/login", {"email": email, "password": pwd})
    check("login mengembalikan JWT", st == 200 and tok and "access_token" in tok, str(st))
    if not (tok and "access_token" in tok):
        return 1
    auth = {"Authorization": f"Bearer {tok['access_token']}"}

    st, sess = call("POST", f"{api}/sessions", {"topic": "rekursi", "question": "Jelaskan dan buatkan faktorial rekursif"}, auth)
    check("buat sesi 201", st == 201, f"{st} {sess}")
    if st != 201:
        return 1
    check("status awal LOCKED", sess["status"] == "LOCKED")
    check("final_result TIDAK dikirim saat LOCKED", sess.get("final_result") is None)
    check("penjelasan tampil terbuka", bool(sess.get("explanation")))

    st, cp = call("POST", f"{api}/sessions/{sess['session_id']}/checkpoint", {"summary": sess["explanation"][:600]}, auth)
    check("salinan mentah ditolak & tetap LOCKED", st == 200 and cp["passed"] is False and cp["status"] == "LOCKED", f"{st} {cp}")
    check("percobaan berkurang", st == 200 and cp["attempts_left"] == sess["attempts_left"] - 1)

    st, got = call("GET", f"{api}/sessions/{sess['session_id']}", None, auth)
    check("GET sesi masih menyembunyikan hasil akhir", st == 200 and got.get("final_result") is None)

    st, _ = call("GET", f"{api}/public/v1/qa?topic=rekursi")
    check("public API tanpa key -> 401", st == 401, str(st))
    if args.api_key:
        st, qa = call("GET", f"{api}/public/v1/qa?topic=rekursi", None, {"X-API-Key": args.api_key})
        check("public API dengan key -> 200 + Q&A", st == 200 and qa["count"] >= 1, f"{st} {qa}")
        check("public API tidak membocorkan data internal", "final_result" not in json.dumps(qa) and email not in json.dumps(qa))
    else:
        print("[LEWAT] public API dengan key (tidak ada --api-key)")

    print("\nSELESAI:", "semua lolos" if failures == 0 else f"{failures} pemeriksaan gagal")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
