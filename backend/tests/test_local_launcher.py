from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER_PATH = PROJECT_ROOT / "launcher.py"

spec = importlib.util.spec_from_file_location("stock_launcher", LAUNCHER_PATH)
assert spec is not None and spec.loader is not None
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_backend_command_uses_fixed_fastapi_entrypoint_and_port():
    command = launcher.backend_command("python")

    assert command == [
        "python",
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]


def test_frontend_start_command_uses_next_start_fixed_port():
    command = launcher.frontend_start_command("npm.cmd")

    assert command == [
        "npm.cmd",
        "run",
        "start",
        "--",
        "--hostname",
        "127.0.0.1",
        "--port",
        "3000",
    ]


def test_frontend_build_env_pins_public_backend_base_url():
    env = launcher.frontend_build_env({"EXISTING": "1"})

    assert env["EXISTING"] == "1"
    assert env["NEXT_PUBLIC_API_BASE_URL"] == "http://127.0.0.1:8000"


def test_build_metadata_requires_launcher_api_base(tmp_path):
    metadata_path = tmp_path / "launcher-build.json"
    metadata_path.write_text(
        '{"next_public_api_base_url":"http://127.0.0.1:8001","frontend_port":3000,"backend_port":8000}',
        encoding="utf-8",
    )

    assert launcher.build_metadata_is_current(metadata_path) is False

    launcher.save_build_metadata(metadata_path)

    assert launcher.build_metadata_is_current(metadata_path) is True


def test_unknown_port_occupancy_fails_closed(monkeypatch):
    monkeypatch.setattr(launcher, "is_port_open", lambda host, port: True)
    monkeypatch.setattr(launcher, "process_exists", lambda pid: False)

    with pytest.raises(launcher.LauncherError, match="알 수 없는 프로세스"):
        launcher.ensure_ports_available({})


def test_launcher_owned_ports_are_allowed(monkeypatch):
    monkeypatch.setattr(launcher, "is_port_open", lambda host, port: True)
    monkeypatch.setattr(launcher, "process_exists", lambda pid: True)
    state = {
        "backend_pid": 111,
        "backend_host": "127.0.0.1",
        "backend_port": 8000,
        "frontend_pid": 222,
        "frontend_host": "127.0.0.1",
        "frontend_port": 3000,
    }

    statuses = launcher.ensure_ports_available(state)

    assert statuses == {"backend": "launcher-owned", "frontend": "launcher-owned"}
    assert launcher.ensure_complete_launcher_state(statuses) is True


def test_partial_launcher_state_fails_closed():
    statuses = {"backend": "launcher-owned", "frontend": "free"}

    with pytest.raises(launcher.LauncherError, match="일부 프로세스"):
        launcher.ensure_complete_launcher_state(statuses)
