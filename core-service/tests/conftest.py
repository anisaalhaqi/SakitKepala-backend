import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("API_KEYS", "siaran:key-siaran,materi:key-materi")
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("FREE_DAILY_QUOTA", "5")
    monkeypatch.setenv("MAX_ATTEMPTS", "3")
    monkeypatch.setenv("PARTNER_RATE_PER_MIN", "5")
    monkeypatch.setenv("SUBSCRIPTION_SIMULATION", "true")
    monkeypatch.setenv("PARTNERS_ENABLED", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


@pytest.fixture()
def client(env):
    from app import acl, public_api
    from app.main import app

    public_api.limiter.reset()
    acl.reset_clients()
    acl._TRANSPORT = None
    with TestClient(app) as c:
        yield c


def signup(client, email="a@x.id", pwd="Rahasia123"):
    assert client.post("/api/auth/register", json={"email": email, "password": pwd}).status_code == 201
    token = client.post("/api/auth/login", json={"email": email, "password": pwd}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def new_session(client, headers, topic="rekursi", question="Tolong buatkan fungsi faktorial rekursif"):
    return client.post("/api/sessions", json={"topic": topic, "question": question}, headers=headers)


PASS_TEXT = (
    "Saya paham rekursi lewat langkah demi langkah dan alasan di balik tiap langkahnya, "
    "ditulis dengan kata saya sendiri."
)
FAIL_TEXT = "Saya belum ingat apa isi penjelasan tadi, jadi jawabannya masih kosong dan asal-asalan."
