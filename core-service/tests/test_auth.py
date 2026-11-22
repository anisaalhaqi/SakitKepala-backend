from .conftest import signup


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_register_login_me(client):
    h = signup(client, "andi@x.id")
    me = client.get("/api/auth/me", headers=h).json()
    assert me["email"] == "andi@x.id" and me["tier"] == "free"


def test_duplicate_email_conflict(client):
    signup(client, "dup@x.id")
    r = client.post("/api/auth/register", json={"email": "dup@x.id", "password": "Rahasia123"})
    assert r.status_code == 409


def test_wrong_password_and_unknown_email_same_error(client):
    signup(client, "u@x.id")
    bad_pwd = client.post("/api/auth/login", json={"email": "u@x.id", "password": "SalahSalah1"})
    no_user = client.post("/api/auth/login", json={"email": "tidak@ada.id", "password": "SalahSalah1"})
    assert bad_pwd.status_code == no_user.status_code == 401
    assert bad_pwd.json() == no_user.json()


def test_validation_rejects_weak_input(client):
    assert client.post("/api/auth/register", json={"email": "bukan-email", "password": "Rahasia123"}).status_code == 422
    assert client.post("/api/auth/register", json={"email": "a@b.id", "password": "pendek"}).status_code == 422


def test_protected_routes_need_token(client):
    assert client.get("/api/sessions").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer sampah"}).status_code == 401
