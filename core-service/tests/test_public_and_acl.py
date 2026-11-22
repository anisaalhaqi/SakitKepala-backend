"""Open Host Service (endpoint publik mitra) dan Anti-Corruption Layer (API mitra)."""
import httpx

from app import acl

from .conftest import new_session, signup

KEY = {"X-API-Key": "key-siaran"}


def seed(client):
    h = signup(client, "owner@x.id")
    new_session(client, h, topic="Rekursi")  # topic dinormalkan ke huruf kecil
    return h


# ------------------------------------------------------------------ OHS / PL


def test_public_requires_valid_api_key(client):
    seed(client)
    assert client.get("/api/public/v1/qa?topic=rekursi").status_code == 401
    assert client.get("/api/public/v1/qa?topic=rekursi", headers={"X-API-Key": "salah"}).status_code == 401
    # JWT pengguna bukan pengganti API key
    h = signup(client, "lain@x.id")
    assert client.get("/api/public/v1/qa?topic=rekursi", headers=h).status_code == 401


def test_public_qa_published_language(client):
    seed(client)
    body = client.get("/api/public/v1/qa?topic=REKURSI", headers=KEY).json()
    assert body["contract_version"] == "1.0" and body["topic"] == "rekursi" and body["count"] == 2
    assert set(body["items"][0]) == {"question", "answer"}
    qs = client.get("/api/public/v1/questions?topic=rekursi", headers={"X-API-Key": "key-materi"}).json()
    assert qs["count"] == 2 and all(isinstance(q, str) for q in qs["questions"])
    topics = client.get("/api/public/v1/topics", headers=KEY).json()["topics"]
    assert {"topic": "rekursi", "count": 2} in topics


def test_public_does_not_leak_internal_data(client):
    seed(client)
    raw = client.get("/api/public/v1/qa?topic=rekursi", headers=KEY).text
    for secret in ("final_result", "[MOCK]", "owner@x.id", "faktorial"):
        assert secret not in raw


def test_public_unknown_topic_is_empty_not_error(client):
    body = client.get("/api/public/v1/qa?topic=tidak-ada", headers=KEY).json()
    assert body["count"] == 0 and body["items"] == []


def test_public_rate_limit_per_partner(client):
    seed(client)
    codes = [client.get("/api/public/v1/qa?topic=rekursi", headers=KEY).status_code for _ in range(7)]
    assert codes[:5] == [200] * 5 and codes[5:] == [429, 429]
    assert client.get("/api/public/v1/qa?topic=rekursi", headers={"X-API-Key": "key-materi"}).status_code == 200  # bucket terpisah


# ------------------------------------------------------------------ ACL


def test_translators_tolerate_partner_schema_variants():
    live = acl.translate_live_sessions(
        {"data": [{"judul": "Live Rekursi", "deskripsi": "Bahas rekursi", "tags": "cs, algoritma"}, {"x": 1}, "bukan dict"]}
    )
    assert live == [{"title": "Live Rekursi", "description": "Bahas rekursi", "tags": ["cs", "algoritma"]}]
    mats = acl.translate_materials([{"title": "Modul 1", "link": "javascript:alert(1)", "ringkasan": "ringkas"}])
    assert mats == [{"title": "Modul 1", "url": "", "summary": "ringkas"}]  # url non-http dibuang
    assert acl.translate_materials("sampah") == [] and acl.translate_live_sessions(None) == []


def test_references_disabled_by_default(client):
    h = seed(client)
    sid = client.get("/api/sessions", headers=h).json()[0]["session_id"]
    body = client.get(f"/api/sessions/{sid}/references", headers=h).json()
    assert body["live_sessions"]["status"] == "disabled" and body["materials"]["status"] == "disabled"


def _enable_partners(env, handler, ttl="300"):
    from app.config import get_settings

    env.setenv("PARTNERS_ENABLED", "true")
    env.setenv("PARTNER_CACHE_TTL", ttl)
    env.setenv("PARTNER_SIARAN_BASE_URL", "https://siaran.test/api")
    env.setenv("PARTNER_SIARAN_API_KEY", "k-siaran")
    env.setenv("PARTNER_MATERI_BASE_URL", "https://materi.test/api")
    get_settings.cache_clear()
    acl.reset_clients()
    acl._TRANSPORT = httpx.MockTransport(handler)


def test_references_merge_partner_data_by_topic(client, env):
    h = seed(client)
    sid = client.get("/api/sessions", headers=h).json()[0]["session_id"]
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.host, request.url.params.get("topic"), request.headers.get("X-API-Key")))
        if request.url.host == "siaran.test":
            return httpx.Response(200, json={"items": [{"title": "Live Rekursi", "tags": ["cs"]}]})
        return httpx.Response(200, json=[])

    _enable_partners(env, handler)
    body = client.get(f"/api/sessions/{sid}/references", headers=h).json()
    assert body["live_sessions"] == {"status": "ok", "items": [{"title": "Live Rekursi", "description": "", "tags": ["cs"]}]}
    assert body["materials"] == {"status": "empty", "items": []}
    assert ("siaran.test", "rekursi", "k-siaran") in seen


def test_partner_down_does_not_break_core(client, env):
    h = seed(client)
    sid = client.get("/api/sessions", headers=h).json()[0]["session_id"]

    def handler(request):
        raise httpx.ConnectError("mitra mati")

    _enable_partners(env, handler)
    r = client.get(f"/api/sessions/{sid}/references", headers=h)
    assert r.status_code == 200
    assert r.json()["live_sessions"]["status"] == "unavailable"
    assert client.get(f"/api/sessions/{sid}", headers=h).status_code == 200  # inti tetap jalan


def test_partner_error_serves_stale_cache(client, env):
    h = seed(client)
    sid = client.get("/api/sessions", headers=h).json()[0]["session_id"]
    state = {"up": True}

    def handler(request):
        if state["up"]:
            return httpx.Response(200, json=[{"title": "Live Rekursi"}])
        return httpx.Response(500)

    _enable_partners(env, handler, ttl="0")  # ttl 0 = selalu coba segar dulu
    assert client.get(f"/api/sessions/{sid}/references", headers=h).json()["live_sessions"]["status"] == "ok"
    state["up"] = False
    stale = client.get(f"/api/sessions/{sid}/references", headers=h).json()["live_sessions"]
    assert stale["status"] == "stale" and stale["items"][0]["title"] == "Live Rekursi"
