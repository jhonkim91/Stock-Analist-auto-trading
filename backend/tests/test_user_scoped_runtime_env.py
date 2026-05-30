from __future__ import annotations

import json
import os

from backend.app.core import runtime_env


def _create_user(client, user_id: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/setup", json={"id": user_id, "password": password})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    return {"Authorization": f"Bearer {payload['token']}"}


def _field(payload: dict, key: str) -> dict:
    for group in payload["groups"]:
        for field in group["fields"]:
            if field["key"] == key:
                return field
    raise AssertionError(f"missing field: {key}")


def _toggle(payload: dict, name: str) -> dict:
    for item in payload["toggles"]:
        if item["name"] == name:
            return item
    raise AssertionError(f"missing toggle: {name}")


def test_runtime_env_values_are_scoped_per_authenticated_user(client, monkeypatch):
    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    monkeypatch.delenv("PAPER_TRADING_ENABLED", raising=False)

    alpha_headers = _create_user(client, "alpha-user", "alpha-password")
    beta_headers = _create_user(client, "beta-user", "beta-password")

    alpha_saved = client.post(
        "/api/settings/environment",
        headers=alpha_headers,
        json={"key": "KIS_APP_KEY", "value": "alpha-key", "confirm": True},
    )
    assert alpha_saved.status_code == 200
    assert alpha_saved.json()["ok"] is True
    assert alpha_saved.json()["scope"] == "user"
    assert alpha_saved.json()["user_id"] == "alpha-user"

    alpha_toggle = client.post(
        "/api/settings/runtime-env/toggle",
        headers=alpha_headers,
        json={"name": "PAPER_TRADING_ENABLED", "enabled": True, "confirm": True},
    )
    assert alpha_toggle.status_code == 200
    assert alpha_toggle.json()["ok"] is True
    assert alpha_toggle.json()["scope"] == "user"

    beta_env = client.get("/api/settings/environment", headers=beta_headers)
    assert beta_env.status_code == 200
    beta_payload = beta_env.json()
    assert beta_payload["scope"] == "user"
    assert beta_payload["user_id"] == "beta-user"
    assert _field(beta_payload, "KIS_APP_KEY")["configured"] is False
    assert "alpha-key" not in json.dumps(beta_payload, ensure_ascii=False)

    beta_runtime = client.get("/api/settings/runtime-env", headers=beta_headers)
    assert beta_runtime.status_code == 200
    beta_runtime_payload = beta_runtime.json()
    assert beta_runtime_payload["scope"] == "user"
    assert _toggle(beta_runtime_payload, "PAPER_TRADING_ENABLED")["enabled"] is False

    alpha_runtime = client.get("/api/settings/runtime-env", headers=alpha_headers)
    assert alpha_runtime.status_code == 200
    alpha_runtime_payload = alpha_runtime.json()
    assert alpha_runtime_payload["scope"] == "user"
    assert _toggle(alpha_runtime_payload, "PAPER_TRADING_ENABLED")["enabled"] is True

    stored = json.loads(runtime_env.RUNTIME_ENV_FILE.read_text(encoding="utf-8"))
    assert stored["global"] == {}
    assert stored["users"]["alpha-user"]["KIS_APP_KEY"] == "alpha-key"
    assert stored["users"]["alpha-user"]["PAPER_TRADING_ENABLED"] == "true"
    assert "KIS_APP_KEY" not in stored["users"].get("beta-user", {})
    assert os.environ.get("KIS_APP_KEY") != "alpha-key"
