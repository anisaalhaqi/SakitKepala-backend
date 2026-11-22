#!/usr/bin/env python3
"""Ekspor kontrak OpenAPI ke docs/openapi.json (untuk API Registry / Postman import).

    python scripts/export_openapi.py
"""
import json
import os
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "core-service"))
os.environ.setdefault("JWT_SECRET", "x" * 40)  # hanya agar konfigurasi lolos; tidak dipakai

from app.main import app  # noqa: E402

out = root / "docs" / "openapi.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("ditulis:", out)
