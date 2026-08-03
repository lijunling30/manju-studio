"""鉴权测试（M10）。"""


def test_register_login_me(client):
    r = client.post("/api/auth/register", json={"username": "alice", "password": "123456"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert r.json()["user"]["plan"] == "personal"

    r = client.post("/api/auth/login", json={"username": "alice", "password": "123456"})
    assert r.status_code == 200
    assert r.json()["access_token"]

    r = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 401

    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


def test_register_duplicate(client):
    client.post("/api/auth/register", json={"username": "bob", "password": "123456"})
    r = client.post("/api/auth/register", json={"username": "bob", "password": "123456"})
    assert r.status_code == 400


def test_unauthenticated_rejected(client):
    r = client.get("/api/projects")
    assert r.status_code == 401
