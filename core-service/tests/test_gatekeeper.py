"""Aturan inti: hasil akhir terkunci sampai logic checkpoint lolos (maks. 3 percobaan)."""
from app import ai_client

from .conftest import FAIL_TEXT, PASS_TEXT, new_session, signup


def test_new_session_is_locked_and_hides_final_result(client):
    h = signup(client)
    r = new_session(client, h)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "LOCKED"
    assert body["final_result"] is None
    assert body["copy_enabled"] is False and body["export_enabled"] is False
    assert body["attempts_left"] == 3
    assert "Penjelasan tentang rekursi" in body["explanation"]  # penjelasan konsep tetap terbuka
    assert "[MOCK]" not in r.text  # hasil akhir tidak bocor di payload mana pun


def test_get_session_still_hides_final_result_while_locked(client):
    h = signup(client)
    sid = new_session(client, h).json()["session_id"]
    got = client.get(f"/api/sessions/{sid}", headers=h).json()
    assert got["final_result"] is None and got["status"] == "LOCKED"


def test_raw_copy_of_explanation_is_rejected(client):
    h = signup(client)
    s = new_session(client, h).json()
    r = client.post(f"/api/sessions/{s['session_id']}/checkpoint", json={"summary": s["explanation"]}, headers=h)
    body = r.json()
    assert r.status_code == 200 and body["passed"] is False and body["status"] == "LOCKED"
    assert body["attempts_left"] == 2 and body["final_result"] is None
    assert "terlalu mirip" in body["feedback"]


def test_understanding_unlocks_and_records_proof(client):
    h = signup(client)
    sid = new_session(client, h).json()["session_id"]
    r = client.post(f"/api/sessions/{sid}/checkpoint", json={"summary": PASS_TEXT}, headers=h).json()
    assert r["passed"] is True and r["status"] == "UNLOCKED"
    assert r["final_result"].startswith("[MOCK]")
    got = client.get(f"/api/sessions/{sid}", headers=h).json()
    assert got["status"] == "UNLOCKED" and got["copy_enabled"] is True and got["final_result"]
    proofs = client.get("/api/proof-of-learning", headers=h).json()
    assert len(proofs) == 1 and proofs[0]["session_id"] == sid and proofs[0]["attempt_no"] == 1


def test_three_failed_attempts_lock_for_good(client):
    h = signup(client)
    sid = new_session(client, h).json()["session_id"]
    left = []
    for _ in range(3):
        r = client.post(f"/api/sessions/{sid}/checkpoint", json={"summary": FAIL_TEXT}, headers=h).json()
        assert r["passed"] is False
        left.append(r["attempts_left"])
    assert left == [2, 1, 0] and r["locked_final"] is True
    # percobaan ke-4 ditolak, bahkan dengan jawaban yang bagus
    r4 = client.post(f"/api/sessions/{sid}/checkpoint", json={"summary": PASS_TEXT}, headers=h)
    assert r4.status_code == 409 and r4.json()["detail"]["code"] == "ATTEMPTS_EXHAUSTED"
    assert client.get(f"/api/sessions/{sid}", headers=h).json()["final_result"] is None
    assert client.get("/api/proof-of-learning", headers=h).json() == []


def test_unlocked_session_cannot_be_checked_again(client):
    h = signup(client)
    sid = new_session(client, h).json()["session_id"]
    client.post(f"/api/sessions/{sid}/checkpoint", json={"summary": PASS_TEXT}, headers=h)
    r = client.post(f"/api/sessions/{sid}/checkpoint", json={"summary": PASS_TEXT}, headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ALREADY_UNLOCKED"


def test_too_short_summary_is_422_and_costs_no_attempt(client):
    h = signup(client)
    sid = new_session(client, h).json()["session_id"]
    assert client.post(f"/api/sessions/{sid}/checkpoint", json={"summary": "singkat"}, headers=h).status_code == 422
    assert client.get(f"/api/sessions/{sid}", headers=h).json()["attempts_left"] == 3


def test_sessions_are_private_per_user(client):
    a, b = signup(client, "a@x.id"), signup(client, "b@x.id")
    sid = new_session(client, a).json()["session_id"]
    assert client.get(f"/api/sessions/{sid}", headers=b).status_code == 404
    assert client.post(f"/api/sessions/{sid}/checkpoint", json={"summary": PASS_TEXT}, headers=b).status_code == 404
    assert client.get("/api/sessions", headers=b).json() == []


def test_ai_failure_on_create_does_not_consume_quota(client, monkeypatch):
    h = signup(client)

    def boom(*a, **k):
        raise ai_client.AiError("mati")

    monkeypatch.setattr(ai_client, "generate", boom)
    assert new_session(client, h).status_code == 503
    assert client.get("/api/subscription", headers=h).json()["used"] == 0


def test_ai_failure_on_judge_does_not_consume_attempt(client, monkeypatch):
    h = signup(client)
    sid = new_session(client, h).json()["session_id"]

    def boom(*a, **k):
        raise ai_client.AiError("mati")

    monkeypatch.setattr(ai_client, "judge", boom)
    r = client.post(f"/api/sessions/{sid}/checkpoint", json={"summary": PASS_TEXT}, headers=h)
    assert r.status_code == 503
    assert client.get(f"/api/sessions/{sid}", headers=h).json()["attempts_left"] == 3
