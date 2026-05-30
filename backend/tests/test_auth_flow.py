from __future__ import annotations


def test_auth_setup_creates_local_users_and_enables_login(client):
    status = client.get("/api/auth/status")
    assert status.status_code == 200
    assert status.json()["setup_required"] is True

    created = client.post("/api/auth/setup", json={"id": "demo-user", "password": "demo-password"})
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["ok"] is True
    assert created_payload["id"] == "demo-user"
    assert isinstance(created_payload["token"], str)
    assert created_payload["token"]

    configured = client.get("/api/auth/status")
    assert configured.status_code == 200
    configured_payload = configured.json()
    assert configured_payload["configured"] is True
    assert configured_payload["setup_required"] is False
    assert configured_payload["user_ids"] == ["demo-user"]

    duplicate = client.post("/api/auth/setup", json={"id": "demo-user", "password": "demo-password"})
    assert duplicate.status_code == 200
    assert duplicate.json() == {"ok": False, "reason": "USER_ALREADY_EXISTS"}

    second = client.post("/api/auth/setup", json={"id": "other-user", "password": "other-password"})
    assert second.status_code == 200
    assert second.json()["ok"] is True

    users = client.get("/api/auth/status")
    assert users.status_code == 200
    assert users.json()["setup_required"] is False
    assert users.json()["user_ids"] == ["demo-user", "other-user"]

    login = client.post("/api/auth/login", json={"id": "demo-user", "password": "demo-password"})
    assert login.status_code == 200
    login_payload = login.json()
    assert login_payload["ok"] is True
    assert login_payload["id"] == "demo-user"
    assert isinstance(login_payload["token"], str)
    assert login_payload["token"]
