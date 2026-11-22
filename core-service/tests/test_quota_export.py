"""Konteks Kuota & Langganan: Free 5 sesi/hari, Pro tanpa batas + ekspor."""
from app import quota

from .conftest import PASS_TEXT, new_session, signup


def test_free_tier_limited_to_five_sessions_per_day(client):
    h = signup(client)
    for i in range(5):
        r = new_session(client, h, question=f"Pertanyaan nomor {i} tentang rekursi")
        assert r.status_code == 201
    assert r.json()["quota"]["remaining"] == 0
    sixth = new_session(client, h)
    assert sixth.status_code == 429
    assert sixth.json()["detail"]["code"] == "QUOTA_EXCEEDED"


def test_quota_resets_next_day(client, monkeypatch):
    h = signup(client)
    for _ in range(5):
        new_session(client, h)
    assert new_session(client, h).status_code == 429
    monkeypatch.setattr(quota, "today_wib", lambda: "2099-01-01")
    assert new_session(client, h).status_code == 201


def test_quota_is_per_user(client):
    a, b = signup(client, "a@x.id"), signup(client, "b@x.id")
    for _ in range(5):
        new_session(client, a)
    assert new_session(client, a).status_code == 429
    assert new_session(client, b).status_code == 201


def test_pro_has_no_daily_limit(client):
    h = signup(client)
    assert client.post("/api/subscription/upgrade", headers=h).json()["tier"] == "pro"
    for _ in range(7):
        assert new_session(client, h).status_code == 201
    st = client.get("/api/subscription", headers=h).json()
    assert st["limit"] is None and st["remaining"] is None and st["used"] == 7


def test_upgrade_can_be_disabled(client, env):
    from app.config import get_settings

    env.setenv("SUBSCRIPTION_SIMULATION", "false")
    get_settings.cache_clear()
    h = signup(client)
    assert client.post("/api/subscription/upgrade", headers=h).status_code == 403


def test_export_requires_unlocked_and_pro(client):
    h = signup(client)
    sid = new_session(client, h).json()["session_id"]

    locked = client.get(f"/api/sessions/{sid}/export", headers=h)
    assert locked.status_code == 403 and locked.json()["detail"]["code"] == "LOCKED"

    client.post(f"/api/sessions/{sid}/checkpoint", json={"summary": PASS_TEXT}, headers=h)
    free = client.get(f"/api/sessions/{sid}/export", headers=h)
    assert free.status_code == 403 and free.json()["detail"]["code"] == "PRO_REQUIRED"
    # Free tetap bisa menyalin hasil akhir (copy_enabled) setelah UNLOCKED
    assert client.get(f"/api/sessions/{sid}", headers=h).json()["copy_enabled"] is True

    client.post("/api/subscription/upgrade", headers=h)
    ok = client.get(f"/api/sessions/{sid}/export", headers=h)
    assert ok.status_code == 200
    body = ok.json()
    assert body["final_result"].startswith("[MOCK]")
    assert body["understanding_notes"] == PASS_TEXT
    assert body["proof_of_learning"]["attempt_no"] == 1
