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


def test_app_command_uses_single_process_entrypoint_and_fixed_port():
    """단일 프로그램 통합 이후: app_main.py를 고정 host/port로 실행한다(별도 백엔드/프론트 프로세스 없음)."""
    command = launcher.app_command("python")

    assert command == [
        "python",
        str(launcher.APP_ENTRYPOINT),
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    assert launcher.APP_HOST == "127.0.0.1"
    assert launcher.APP_PORT == 8000
    assert launcher.APP_ENTRYPOINT.name == "app_main.py"


def test_port_is_free_when_nothing_is_listening(monkeypatch):
    monkeypatch.setattr(launcher, "is_port_open", lambda host, port, timeout=0.25: False)

    assert launcher.ensure_port_available({}) == "free"


def test_unknown_port_occupancy_fails_closed(monkeypatch):
    """고정 포트를 launcher가 띄우지 않은 알 수 없는 프로세스가 점유하면 fail-closed로 중단한다."""
    monkeypatch.setattr(launcher, "is_port_open", lambda host, port, timeout=0.25: True)
    monkeypatch.setattr(launcher, "process_exists", lambda pid: False)

    with pytest.raises(launcher.LauncherError, match="알 수 없는 프로세스"):
        launcher.ensure_port_available({})


def test_launcher_owned_port_is_allowed(monkeypatch):
    """포트가 launcher state의 살아있는 단일 프로세스(app_pid)에 속하면 재사용을 허용한다."""
    monkeypatch.setattr(launcher, "is_port_open", lambda host, port, timeout=0.25: True)
    monkeypatch.setattr(launcher, "process_exists", lambda pid: True)
    state = {
        "app_pid": 4321,
        "app_host": "127.0.0.1",
        "app_port": 8000,
    }

    assert launcher.ensure_port_available(state) == "launcher-owned"
    assert launcher.launcher_owns_port(state) is True
